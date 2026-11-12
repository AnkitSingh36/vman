"""Authenticated transactional application boundary shared by HTTP and local tooling."""
import copy
import json

from .catalog import GROUPS, authorize, publish, source_ref
from .commands import BODY_SCHEMA, mutate
from .contracts import Contracts, canonical, digest
from .errors import APIError, conflict
from .state import TERMINAL, guard, halt, new_session, public
from .store import Store, now, opaque


class Service:
    def __init__(self, settings):
        self.settings = settings
        self.contracts = Contracts(settings.contracts)
        self.store = Store(settings.database)
        with self.store.connect() as db:
            empty = not db.execute("SELECT 1 FROM catalogs").fetchone()
        if empty:
            catalog = self.contracts.read("request-fixtures.json")["catalog"]
            raw = (settings.contracts / "synthetic-guide.txt").read_bytes()
            sources = {(r["source"]["source_id"], r["source"]["version"]): raw
                       for group in GROUPS for r in catalog[group]}
            publish(self.store, self.contracts, catalog, sources)

    def recover(self):
        """Single worker only. An interrupted inference cannot be recreated by a GET."""
        with self.store.transaction() as db:
            for row in db.execute("SELECT payload FROM sessions").fetchall():
                session = json.loads(row[0])
                if session["status"] in ("EVALUATING", "RECORD_PENDING"):
                    halt(session, "UNKNOWN", "RESTART_REQUIRES_NEW_SESSION")
                    session["revision"] += 1
                    self.store.event(db, session, "RECOVERY_STOP", {})
                    self.store.save(db, session)
            db.execute("UPDATE inferences SET state='CANCELLED',finished_at=?,reason='RESTART' WHERE state='RUNNING'", (now(),))

    def _refresh(self, db, principal, session):
        before = canonical(session)
        try:
            catalog = guard(self.store, db, principal, session)
        except APIError as exc:
            if exc.status != 503:
                raise
            catalog = {group: [] for group in GROUPS}
            if session["status"] not in TERMINAL:
                halt(session, "UNKNOWN", "POLICY_UNAVAILABLE")
        if canonical(session) != before:
            session["revision"] += 1
            self.store.event(db, session, "POLICY_STOP", {"reason_code": session["reason_code"]})
            self.store.save(db, session)
            db.execute("UPDATE inferences SET state='CANCELLED',finished_at=?,reason='POLICY_STOP' WHERE session_id=? AND state='RUNNING'",
                       (now(), session["session_id"]))
        return catalog

    def _public(self, session, catalog):
        result = public(session, catalog, self.settings)
        self.contracts.validate("session.schema.json", result, internal=True)
        return result

    def read(self, token, session_id):
        with self.store.transaction() as db:
            principal = self.store.authenticate(db, token)
            session = self.store.session(db, session_id, principal)
            catalog = self._refresh(db, principal, session)
            return self._public(session, catalog)

    def perform(self, token, operation, session_id, key, data, media=None):
        if not key or not 1 <= len(key) <= 128:
            raise APIError(422, "INVALID_KEY", "A bounded Idempotency-Key is required.")
        error, response = None, None
        with self.store.transaction() as db:
            principal = self.store.authenticate(db, token)
            if operation in BODY_SCHEMA:
                self.contracts.validate(BODY_SCHEMA[operation], data)
            session = self.store.session(db, session_id, principal) if session_id else None
            workflow = session["workflow_id"] if session else data["workflow_id"]
            authorize(db, principal, workflow)
            command = db.execute("SELECT * FROM commands WHERE tenant=? AND actor=? AND session_id=? AND operation=? AND key=?",
                                 (principal["tenant"], principal["actor"], session_id or "", operation, key)).fetchone()
            request_hash = digest(data)
            if command:
                if command["request_hash"] != request_hash:
                    raise conflict(session["revision"] if session else 0)
                metadata = json.loads(command["image_result"]) if command["image_result"] else None
                if not session:
                    if not metadata or not metadata.get("session_id"):
                        raise APIError(404, "NOT_FOUND", "Original session is unavailable.")
                    session = self.store.session(db, metadata["session_id"], principal)
                catalog = self._refresh(db, principal, session)
                result = metadata if operation == "images" else self._public(session, catalog)
                return result, 201 if operation in ("create", "images") else 200, self._headers(command), session["session_id"]
            if session:
                if operation in ("stop", "hazards"):
                    try:
                        catalog = self.store.catalog(db)
                    except APIError:
                        catalog = {group: [] for group in GROUPS}
                else:
                    catalog = self._refresh(db, principal, session)
                if session["status"] in TERMINAL or (operation not in ("stop", "hazards") and data["expected_revision"] != session["revision"]):
                    error = conflict(session["revision"])
            else:
                catalog = self.store.catalog(db)
                if workflow not in {r["workflow_id"] for r in catalog["checks"]}:
                    raise APIError(422, "UNSUPPORTED", "Workflow is unsupported.")
                count = db.execute("SELECT count(*) FROM sessions WHERE tenant=? AND actor=?", (principal["tenant"], principal["actor"])).fetchone()[0]
                if count >= 100:
                    raise APIError(429, "SESSION_LIMIT", "Local demo session limit reached.")
                session = new_session(opaque(), workflow, catalog["catalog_version"])
                db.execute("INSERT INTO sessions VALUES (?,?,?,?)", (session["session_id"], principal["tenant"], principal["actor"], canonical(session)))
            if not error:
                record_id, command_id = opaque(), opaque()
                metadata, sources = None, []
                if operation != "create":
                    metadata, sources = mutate(db, session, operation, data, catalog, record_id, media)
                else:
                    if data.get("symptom_text"):
                        session["messages"].append({"message_id": record_id, "text": data["symptom_text"], "channel": "CHAT", "provenance": "HUMAN_REPORT"})
                    metadata = {"session_id": session["session_id"]}
                session["revision"] += 1
                if operation != "images":
                    session["receipt"] = {"command_id": command_id, "state": "PERSISTED", "record_id": record_id}
                self.store.event(db, session, operation.upper(), data, sources, record=record_id)
                self.store.save(db, session)
                db.execute("INSERT INTO commands VALUES (?,?,?,?,?,?,?,?,?)",
                           (command_id, principal["tenant"], principal["actor"], session_id or "", operation, key,
                            request_hash, record_id, canonical(metadata) if metadata else None))
                # Invalidate old model work atomically with every context-changing command.
                db.execute("UPDATE inferences SET state='CANCELLED',finished_at=?,reason='NEW_CONTEXT' WHERE session_id=? AND state='RUNNING'", (now(), session["session_id"]))
                catalog = self._refresh(db, principal, session)
                result = metadata if operation == "images" else self._public(session, catalog)
                status = 201 if operation in ("create", "images") else 202 if session["status"] == "EVALUATING" else 200
                response = result, status, {"X-Command-Id": command_id, "X-Command-State": "PERSISTED"}, session["session_id"]
        if error:
            raise error
        return response

    @staticmethod
    def _headers(command):
        return {"X-Command-Id": command["id"], "X-Command-State": "PERSISTED"}

    def receipt(self, token, session_id, command_id):
        with self.store.transaction() as db:
            principal = self.store.authenticate(db, token)
            session = self.store.session(db, session_id, principal)
            command = db.execute("SELECT * FROM commands WHERE id=? AND tenant=? AND actor=?",
                                 (command_id, principal["tenant"], principal["actor"])).fetchone()
            metadata = json.loads(command["image_result"]) if command and command["image_result"] else {}
            if not command or (command["session_id"] != session_id and metadata.get("session_id") != session_id):
                raise APIError(404, "NOT_FOUND", "Command is unavailable.")
            self._refresh(db, principal, session)
            return {"command_id": command_id, "state": "PERSISTED", "record_id": command["record_id"]}

    def events(self, token, session_id, cursor=None):
        with self.store.transaction() as db:
            principal = self.store.authenticate(db, token)
            session = self.store.session(db, session_id, principal)
            sequence = 0
            if cursor:
                row = db.execute("SELECT sequence FROM events WHERE id=? AND session_id=?", (cursor, session_id)).fetchone()
                if not row:
                    raise APIError(422, "INVALID_CURSOR", "Cursor is unavailable.")
                sequence = row[0]
            catalog = self._refresh(db, principal, session)
            rows = db.execute("SELECT * FROM events WHERE session_id=? AND sequence>? ORDER BY sequence LIMIT 51", (session_id, sequence)).fetchall()
            safe_refs = {canonical(source_ref(r)) for group in GROUPS for r in catalog[group]}
            events = [{"record_id": row["id"], "session_id": session_id, "event_type": row["event_type"],
                       "created_at": row["created_at"], "human_assertion": canonical(json.loads(row["data"])),
                       "source_refs": [r for r in json.loads(row["sources"]) if canonical(r) in safe_refs]}
                      for row in rows[:50]]
            return {"events": events, "next_cursor": rows[49]["id"] if len(rows) > 50 else None}

    def resolve_image(self, token, inference_id, handle):
        """Internal read-only adapter: resolves only a frame bound to a current inference."""
        error, data = None, None
        with self.store.transaction() as db:
            principal = self.store.authenticate(db, token)
            run = db.execute("SELECT * FROM inferences WHERE id=? AND state='RUNNING'", (inference_id,)).fetchone()
            if not run:
                raise APIError(404, "NOT_FOUND", "Cleared media is unavailable.")
            session = self.store.session(db, run["session_id"], principal)
            self._refresh(db, principal, session)
            bound = json.loads(run["request"])
            frame = next((f for f in bound["cleared_images"] if f["cleared_handle"] == handle), None)
            if session["status"] != "EVALUATING" or session["revision"] != run["revision"] or not frame:
                error = APIError(404, "NOT_FOUND", "Cleared media is unavailable.")
            else:
                row = db.execute("SELECT data,sha256 FROM images WHERE id=? AND session_id=?", (frame["image_id"], session["session_id"])).fetchone()
                if not row or row["sha256"] != frame["sha256"]:
                    error = APIError(404, "NOT_FOUND", "Cleared media is unavailable.")
                else:
                    data = bytes(row["data"])
        # Commit any policy stop before reporting an inaccessible frame.
        if error:
            raise error
        return data
