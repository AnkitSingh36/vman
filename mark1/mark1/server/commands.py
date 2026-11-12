"""Human-command validation and transitions. Called only inside a database transaction."""
from .catalog import source_ref
from .errors import APIError, conflict
from .state import ACTIVE, find, halt, prerequisites
from .store import opaque

STATES = {
    "identity-candidates": {"AWAITING_IDENTITY"}, "identity-confirmation": {"AWAITING_IDENTITY"},
    "images": {"AWAITING_IDENTITY", "AWAITING_VIEW", "READY"}, "observations": {"READY"},
    "view-responses": {"AWAITING_VIEW"}, "answers": {"AWAITING_ANSWER"},
    "explanation-acks": {"EXPLAINING"}, "messages": ACTIVE,
    "outcome": {"READY", "EVALUATING", "AWAITING_VIEW", "AWAITING_ANSWER", "EXPLAINING"},
    "stop": ACTIVE | {"RECORD_PENDING"}, "hazards": ACTIVE | {"RECORD_PENDING"},
}
BODY_SCHEMA = {"create": "CreateSession", "identity-candidates": "IdentityCandidates",
               "identity-confirmation": "ConfirmIdentity", "observations": "Observation", "outcome": "Outcome",
               "stop": "Stop", "hazards": "Hazard", "view-responses": "ViewResponse", "answers": "Answer",
               "messages": "Message", "explanation-acks": "ExplanationAck"}


def owned_image(db, session, image_id, purpose=None):
    row = db.execute("SELECT id,purpose FROM images WHERE id=? AND session_id=?",
                     (image_id, session["session_id"])).fetchone()
    if not row or (purpose and row["purpose"] != purpose):
        raise APIError(404, "NOT_FOUND", "Session or referenced object is unavailable.")


def mutate(db, session, operation, data, catalog, record_id, media=None):
    if session["status"] not in STATES[operation]:
        raise conflict(session["revision"])
    if operation in ("stop", "hazards"):
        halt(session, "ESCALATED", "HAZARD_REPORTED" if operation == "hazards" else "USER_STOP")
        return None, []
    selection = session["selection"]
    current = find(catalog, selection["group"], selection["id"], selection["version"]) if selection else None
    sources = [source_ref(current)] if current else []
    if operation == "images":
        if db.execute("SELECT count(*) FROM images WHERE session_id=?", (session["session_id"],)).fetchone()[0] >= 32:
            raise APIError(429, "IMAGE_LIMIT", "Local session image limit reached.")
        expected = "identity" if session["status"] == "AWAITING_IDENTITY" else "observation" if session["status"] == "READY" else "identity" if current["purpose"] == "IDENTITY" else "investigation"
        if data["purpose"] != expected:
            raise APIError(422, "INVALID_REQUEST", "Image purpose does not match the current operation.")
        image_id = opaque()
        db.execute("INSERT INTO images VALUES (?,?,?,?,?,?)",
                   (image_id, session["session_id"], media["sha256"], media["mime_type"], media["bytes"], data["purpose"]))
        session["image_ids"] = (session["image_ids"] + [image_id])[-3:]
        return {"image_id": image_id, "session_id": session["session_id"],
                "revision": session["revision"] + 1, "status": "STORED"}, []
    if operation == "identity-candidates":
        if data.get("image_id"):
            owned_image(db, session, data["image_id"], "identity")
            session["image_ids"] = (session["image_ids"] + [data["image_id"]])[-3:]
        session["manual_label"] = data.get("manual_label")
    elif operation == "identity-confirmation":
        supported = {(c["model_id"], c["configuration_id"]) for c in catalog["checks"]}
        if (data["model_id"], data["configuration_id"]) not in supported:
            raise APIError(422, "UNSUPPORTED", "The exact configuration is not supported.")
        session["identity"] = {k: data[k] for k in ("model_id", "configuration_id", "human_confirmed")}
        session["identity_candidates"] = []
    elif operation in ("view-responses", "answers", "explanation-acks"):
        if any(data[k] != value for k, value in (("interaction_id", selection["interaction_id"]),
                                                ("template_id", selection["id"]), ("template_version", selection["version"]))):
            raise conflict(session["revision"])
        session["prior_templates"].append(selection["id"])
        if operation == "view-responses":
            if data["result"] == "IMAGE":
                purpose = "identity" if current["purpose"] == "IDENTITY" else "investigation"
                owned_image(db, session, data["image_id"], purpose)
                session["image_ids"] = (session["image_ids"] + [data["image_id"]])[-3:]
            else:
                key = current["template_id"]
                session["failed_views"][key] = session["failed_views"].get(key, 0) + 1
            session["view_results"].append({k: data[k] for k in ("interaction_id", "template_id", "template_version", "result", "image_id")})
            session["view_results"][-1]["evidence_id"] = record_id
        elif operation == "answers":
            if data["value"] not in current["options"]:
                raise APIError(422, "INVALID_VALUE", "Answer is not an approved option.")
            session["answers"].append({**{k: data[k] for k in ("interaction_id", "template_id", "template_version", "value")},
                                       "evidence_id": record_id, "provenance": "HUMAN_REPORT"})
        else:
            session["acks"].append(selection["interaction_id"])
    elif operation == "messages":
        if len(session["messages"]) >= 100:
            raise APIError(429, "MESSAGE_LIMIT", "Local session message limit reached.")
        session["messages"].append({"message_id": record_id, "text": data["text"], "channel": data["channel"], "provenance": "HUMAN_REPORT"})
    elif operation == "observations":
        if any(data[k] != current[k] for k in ("check_id", "observation_code")) or data["check_version"] != current["version"]:
            raise conflict(session["revision"])
        if data["value"] not in current["options"] or not prerequisites(session, current):
            raise APIError(422, "INVALID_VALUE", "Observation does not match the approved check.")
        if data.get("image_id"):
            owned_image(db, session, data["image_id"], "observation")
        session["observations"].append({**{k: data[k] for k in ("check_id", "check_version", "observation_code", "value")},
                                        "provenance": "HUMAN_CONFIRMED", "record_id": record_id})
        if data["value"] in current["stop_values"]:
            halt(session, "ESCALATED", "HAZARD_OR_UNCERTAINTY")
            return None, sources
    elif operation == "outcome":
        if not session["observations"]:
            raise conflict(session["revision"])
        outcome = data["human_reported_outcome"]
        session["human_reported_outcome"] = outcome
        halt(session, "COMPLETED" if outcome == "RESOLVED" else "ESCALATED", None if outcome == "RESOLVED" else "HUMAN_UNRESOLVED")
        return None, sources
    session.update(status="EVALUATING", selection=None, reason_code=None)
    return None, sources
