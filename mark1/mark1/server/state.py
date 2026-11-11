"""Deterministic policy and canonical output composition; models never grant readiness."""
import copy
from datetime import datetime, timedelta, timezone

from .catalog import GROUPS, authorize, scoped, source_ref
from .errors import APIError
from .store import now, opaque

TERMINAL = {"BLOCKED", "UNKNOWN", "ESCALATED", "COMPLETED"}
ACTIVE = {"AWAITING_IDENTITY", "EVALUATING", "AWAITING_VIEW", "AWAITING_ANSWER", "EXPLAINING", "READY"}


def new_session(session_id, workflow, catalog_version):
    return {"contract_version": "2.0", "session_id": session_id, "revision": 0,
            "status": "AWAITING_IDENTITY", "workflow_id": workflow, "identity": None,
            "identity_candidates": [], "receipt": None, "human_reported_outcome": None,
            "reason_code": None, "selection": None, "catalog_version": catalog_version,
            "manual_label": None, "image_ids": [], "observations": [], "messages": [],
            "answers": [], "view_results": [], "acks": [], "prior_templates": [],
            "inferences_used": 0, "failed_views": {}, "output_contexts": {}}


def halt(session, status, reason):
    session.update(status=status, reason_code=reason, selection=None)


def find(catalog, group, identifier, version):
    records = [r for r in catalog[group] if r[GROUPS[group]] == identifier and r["version"] == version]
    if len(records) != 1:
        raise ValueError("Unapproved, excluded or ambiguous reference")
    return records[0]


def preflight(catalog):
    values = [r for r in catalog["checks"] if r["kind"] == "PREFLIGHT"]
    if len(values) != 1:
        raise ValueError("Required preflight unavailable")
    return values[0]


def prerequisites(session, check):
    for required in check["prerequisites"]:
        matches = [o for o in session["observations"]
                   if (o["check_id"], o["check_version"], o["observation_code"]) ==
                   (required["check_id"], required["check_version"], required["observation_code"])]
        if not matches or matches[-1]["value"] not in required["allowed_values"]:
            return False
    return True


def cleared(session, catalog):
    check = preflight(catalog)
    return any(o["check_id"] == check["check_id"] and o["check_version"] == check["version"]
               and o["observation_code"] == check["observation_code"] and o["value"] == "CLEAR"
               for o in session["observations"])


def claim_evidence(session, template, evidence_ids, catalog):
    rule = template["claim_rule"]
    target = find(catalog, "checks", rule["check_id"], rule["check_version"])
    if target["observation_code"] != rule["observation_code"]:
        raise ValueError("Claim prerequisite is no longer applicable")
    matches = [o for o in session["observations"] if o["record_id"] in evidence_ids
               and o["provenance"] == "HUMAN_CONFIRMED"
               and all(o[k] == rule[k] for k in ("check_id", "check_version", "observation_code"))
               and o["value"] in rule["allowed_values"]]
    known = {o["record_id"] for o in session["observations"]}
    if not matches or not set(evidence_ids) <= known:
        raise ValueError("Unsupported claim evidence")
    return [o["record_id"] for o in matches]


def guard(store, db, principal, session):
    authorize(db, principal, session["workflow_id"])
    catalog = store.catalog(db)
    if session["status"] in TERMINAL:
        return scoped(db, principal, session, catalog)
    row = db.execute("SELECT state FROM policies WHERE tenant=? AND workflow=?",
                     (principal["tenant"], session["workflow_id"])).fetchone()
    if not row or row[0] != "ACTIVE":
        halt(session, "BLOCKED" if row and row[0] == "BLOCKED" else "UNKNOWN", "WORK_UNAVAILABLE")
    elif session["catalog_version"] != catalog["catalog_version"]:
        halt(session, "UNKNOWN", "CONTEXT_CHANGED")
    authorized = scoped(db, principal, session, catalog)
    if session["status"] not in TERMINAL:
        try:
            if not authorized["checks"]:
                raise ValueError("No current coverage")
            if session["identity"]:
                preflight(authorized)
            selection = session["selection"]
            if selection:
                record = find(authorized, selection["group"], selection["id"], selection["version"])
                if selection["group"] == "checks" and not prerequisites(session, record):
                    raise ValueError("Prerequisite invalid")
                is_identity_view = selection["group"] == "view_templates" and record["purpose"] == "IDENTITY"
                is_preflight = selection["group"] == "checks" and record["kind"] == "PREFLIGHT"
                if not is_identity_view and not is_preflight and not cleared(session, authorized):
                    raise ValueError("Preflight missing")
                if selection["group"] == "explanation_templates":
                    claim_evidence(session, record, selection["evidence_ids"], authorized)
        except ValueError:
            halt(session, "BLOCKED", "WORK_UNAVAILABLE")
    return authorized


def select(session, group, record, **extra):
    session["selection"] = {"group": group, "id": record[GROUPS[group]], "version": record["version"],
                            "interaction_id": opaque(), **extra}
    session["status"] = {"checks": "READY", "view_templates": "AWAITING_VIEW",
                         "question_templates": "AWAITING_ANSWER", "explanation_templates": "EXPLAINING"}[group]


def public(session, catalog, settings):
    keys = ("contract_version", "session_id", "revision", "status", "workflow_id", "identity",
            "identity_candidates", "receipt", "human_reported_outcome", "reason_code")
    result = {key: copy.deepcopy(session[key]) for key in keys}
    result.update(current_check=None, interaction=None)
    selection = session["selection"]
    if not selection or session["status"] in TERMINAL:
        return result
    record = find(catalog, selection["group"], selection["id"], selection["version"])
    freshness = {"source": source_ref(record), "policy_checked_at": now(),
                 "guidance_valid_until": (datetime.now(timezone.utc) + timedelta(seconds=settings.lease_seconds)).isoformat().replace("+00:00", "Z"),
                 "safety_notice": record["safety_notice"], "stop_conditions": record["stop_conditions"]}
    if selection["group"] == "checks":
        result["current_check"] = {k: record[k] for k in ("check_id", "version", "instruction", "observation_code", "options")}
        result["current_check"].update(freshness)
        return result
    interaction = dict(freshness, interaction_id=selection["interaction_id"], template_id=record["template_id"],
                       template_version=record["version"], text=record["text"])
    if selection["group"] == "view_templates":
        interaction.update(kind="VIEW", purpose=record["purpose"], target_node_id=record["target_node_id"])
    elif selection["group"] == "question_templates":
        interaction.update(kind="QUESTION", options=record["options"])
    else:
        evidence = claim_evidence(session, record, selection["evidence_ids"], catalog)
        diagrams = [d for d in catalog["diagrams"] if d["diagram_id"] == record["diagram_id"] and d["version"] == record["diagram_version"]]
        diagram = None
        if diagrams:
            diagram = {k: copy.deepcopy(diagrams[0][k]) for k in ("diagram_id", "version", "title", "nodes", "edges")}
            diagram["source"] = source_ref(diagrams[0])
        interaction.update(kind="EXPLANATION", advisory=True, diagram=diagram,
                           claims=[{"label": "SUSPECTED", "text": record["text"], "evidence_ids": evidence}],
                           highlights=[{"node_id": n, "label": "SUSPECTED", "evidence_ids": evidence}
                                       for n in selection["highlight_node_ids"]] if diagram else [])
    result["interaction"] = interaction
    return result


def apply_proposal(session, catalog, request, proposal):
    if any(proposal[k] != request[k] for k in ("request_id", "session_id", "based_on_revision", "context_hash")):
        raise ValueError("Stale or foreign inference binding")
    kind, payload = proposal["kind"], proposal["payload"]
    if kind == "ESCALATE":
        halt(session, "ESCALATED", payload["reason_code"])
        return
    if request["mode"] == "IDENTIFY":
        if kind == "IDENTITY_CANDIDATES":
            supported = {(c["model_id"], c["configuration_id"]) for c in catalog["checks"]}
            if any((c["model_id"], c["configuration_id"]) not in supported for c in payload["candidates"]):
                raise ValueError("Unsupported identity")
            session.update(status="AWAITING_IDENTITY", identity_candidates=payload["candidates"], selection=None)
            return
        if kind != "REQUEST_VIEW":
            raise ValueError("Invalid identification proposal")
    elif kind == "IDENTITY_CANDIDATES" or not cleared(session, catalog):
        raise ValueError("Invalid investigator mode or preflight")
    if kind in ("PROPOSE_CHECK", "ASK_OBSERVATION"):
        group, identifier, version = "checks", payload["check_id"], payload["check_version"]
    else:
        group, field = {"REQUEST_VIEW": ("view_templates", "view_template_id"),
                        "ASK_QUESTION": ("question_templates", "question_template_id"),
                        "EXPLAIN": ("explanation_templates", "explanation_template_id")}[kind]
        identifier, version = payload[field], payload["template_version"]
    record = find(catalog, group, identifier, version)
    if payload["sources"] != [source_ref(record)]:
        raise ValueError("Unsupported source mapping")
    if group == "checks":
        if not prerequisites(session, record) or any(o["check_id"] == identifier and o["check_version"] == version for o in session["observations"]):
            raise ValueError("Repeated or ineligible check")
        if kind == "ASK_OBSERVATION" and payload["observation_code"] != record["observation_code"]:
            raise ValueError("Mismatched observation")
    if group == "view_templates":
        if record["purpose"] != ("IDENTITY" if request["mode"] == "IDENTIFY" else "INVESTIGATION"):
            raise ValueError("View purpose mismatch")
    fingerprint = tuple(request["investigation_context"]["available_evidence_ids"])
    if session["output_contexts"].get(identifier) == list(fingerprint):
        raise ValueError("No new evidence for repeated interaction")
    session["output_contexts"][identifier] = list(fingerprint)
    extra = {}
    if group == "explanation_templates":
        claim_evidence(session, record, payload["evidence_ids"], catalog)
        if not set(payload["highlight_node_ids"]) <= set(record["allowed_highlight_node_ids"]):
            raise ValueError("Unsupported highlight")
        extra = {k: payload[k] for k in ("evidence_ids", "highlight_node_ids")}
    select(session, group, record, **extra)
