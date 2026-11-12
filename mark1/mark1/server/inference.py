"""Durable inference binding and bounded asynchronous execution outside write transactions."""
import asyncio
import copy
from datetime import datetime, timedelta, timezone
import json
import logging
import time

from .contracts import canonical
from .errors import APIError
from .state import apply_proposal, cleared, halt, preflight, select
from .store import now, opaque

LOG = logging.getLogger("mark1.inference")


def prepare(service, token, session_id, model_version, prompt_version):
    store = service.store
    with store.transaction() as db:
        principal = store.authenticate(db, token)
        session = store.session(db, session_id, principal)
        catalog = service._refresh(db, principal, session)
        if session["status"] != "EVALUATING":
            return None
        if db.execute("SELECT 1 FROM inferences WHERE session_id=? AND state='RUNNING'", (session_id,)).fetchone():
            return None
        if session["identity"] and not cleared(session, catalog):
            select(session, "checks", preflight(catalog))
            session["revision"] += 1
            store.event(db, session, "PREFLIGHT_REQUIRED", {})
            store.save(db, session)
            return None
        if session["inferences_used"] >= service.settings.max_inferences or any(v >= service.settings.max_view_failures for v in session["failed_views"].values()):
            halt(session, "ESCALATED", "BUDGET_EXCEEDED")
            session["revision"] += 1
            store.save(db, session)
            store.event(db, session, "BUDGET_STOP", {})
            return None
        session["inferences_used"] += 1
        session["revision"] += 1
        store.save(db, session)
        images = []
        for image_id in dict.fromkeys(session["image_ids"][-3:]):
            row = db.execute("SELECT * FROM images WHERE id=? AND session_id=?", (image_id, session_id)).fetchone()
            if row:
                images.append({"image_id": row["id"], "sha256": row["sha256"], "mime_type": row["mime_type"], "cleared_handle": row["id"]})
        context = {"messages": session["messages"][-20:], "answers": session["answers"],
                   "view_results": session["view_results"], "acknowledged_explanation_ids": session["acks"],
                   "available_evidence_ids": [o["record_id"] for o in session["observations"]]
                   + [m["message_id"] for m in session["messages"]]
                   + [a["evidence_id"] for a in session["answers"] + session["view_results"]],
                   "prior_template_ids": session["prior_templates"], "omitted_message_count": max(0, len(session["messages"]) - 20),
                   "inferences_used": session["inferences_used"],
                   "failed_view_attempts": [{"template_id": k, "count": v} for k, v in session["failed_views"].items()]}
        request = {"contract_version": "2.0", "request_id": opaque(), "session_id": session_id,
                   "based_on_revision": session["revision"], "context_hash": "0" * 64,
                   "mode": "INVESTIGATE" if session["identity"] else "IDENTIFY", "workflow_id": session["workflow_id"],
                   "confirmed_identity": session["identity"], "manual_label": session["manual_label"],
                   "cleared_images": images, "approved_catalog": catalog, "observations": session["observations"],
                   "completed_check_ids": [o["check_id"] for o in session["observations"]],
                   "remaining_budgets": {"turns": 8, "calls": 16, "deadline_at": (datetime.now(timezone.utc) + timedelta(seconds=service.settings.inference_timeout)).isoformat().replace("+00:00", "Z")},
                   "model_config_version": model_version, "prompt_version": prompt_version,
                   "catalog_version": catalog["catalog_version"], "investigation_context": context}
        request["context_hash"] = service.contracts.context_hash(request)
        service.contracts.validate("engine-request.schema.json", request, internal=True)
        db.execute("INSERT INTO inferences VALUES (?,?,?,?,?,?,NULL,NULL)",
                   (request["request_id"], session_id, session["revision"], canonical(request), "RUNNING", now()))
        store.event(db, session, "INFERENCE_STARTED", {"request_id": request["request_id"]})
        return request, principal


def finish(service, token, request, principal, proposal=None, reason=None):
    store = service.store
    with store.transaction() as db:
        run = db.execute("SELECT state FROM inferences WHERE id=?", (request["request_id"],)).fetchone()
        session = store.session(db, request["session_id"], principal)
        if not run or run[0] != "RUNNING" or session["revision"] != request["based_on_revision"] or session["status"] != "EVALUATING":
            return  # A newer command, stop or inference already invalidated this response.
        try:
            current = store.authenticate(db, token)
            catalog = service._refresh(db, current, session)
            if session["status"] == "EVALUATING":
                if reason:
                    halt(session, "UNKNOWN", reason)
                else:
                    service.contracts.validate("engine-proposal.schema.json", proposal, internal=True)
                    apply_proposal(session, catalog, request, proposal)
        except APIError:
            halt(session, "UNKNOWN", "AUTHORIZATION_UNAVAILABLE")
        except (ValueError, KeyError, TypeError):
            halt(session, "UNKNOWN", "INVALID_ENGINE_PROPOSAL")
        session["revision"] += 1
        service._public(session, catalog if 'catalog' in locals() else {})
        store.save(db, session)
        store.event(db, session, "INFERENCE_FINISHED", {"request_id": request["request_id"], "status": session["status"]})
        db.execute("UPDATE inferences SET state=?,finished_at=?,reason=? WHERE id=?",
                   ("FINISHED", now(), session["reason_code"], request["request_id"]))


class Runner:
    def __init__(self, service, engine):
        self.service, self.engine = service, engine
        self.model_version = engine.model_config_version
        self.prompt_version = engine.prompt_version
        if not all(isinstance(v, str) and v for v in (self.model_version, self.prompt_version)):
            raise ValueError("Engine must declare its model and prompt configuration versions")
        self.tasks = set()

    def schedule(self, token, session_id):
        task = asyncio.create_task(self.run(token, session_id))
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)

    async def run(self, token, session_id):
        bound = None
        try:
            bound = await asyncio.to_thread(prepare, self.service, token, session_id, self.model_version, self.prompt_version)
            if not bound:
                return
            request, principal = bound
            start = time.monotonic()
            LOG.info("inference input images=%d messages=%d", len(request["cleared_images"]), len(request["investigation_context"]["messages"]))
            proposal = await asyncio.wait_for(self.engine.propose(copy.deepcopy(request)), self.service.settings.inference_timeout)
            reason = "INFERENCE_TIMEOUT" if time.monotonic() - start > self.service.settings.inference_timeout else None
            await asyncio.to_thread(finish, self.service, token, request, principal, proposal, reason)
            LOG.info("inference output proposals=1")
        except asyncio.CancelledError:
            raise  # Startup recovery marks unfinished RUNNING work UNKNOWN after restart.
        except Exception:
            LOG.warning("inference output proposals=0; controlled failure")
            if bound:
                request, principal = bound
                try:
                    await asyncio.to_thread(finish, self.service, token, request, principal, None, "ENGINE_UNAVAILABLE")
                except Exception:
                    LOG.error("inference persistence unresolved; startup reconciliation required")

    async def close(self):
        for task in list(self.tasks):
            task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)
