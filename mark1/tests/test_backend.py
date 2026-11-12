"""Backend integration tests exercise policy and persistence through the actual HTTP API."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from io import BytesIO
import json
import time

from fastapi.testclient import TestClient
from PIL import Image
import pytest

from mark1.server.app import create_app


def send(client, session, operation, body, key=None):
    response = client.post(f"/v2/sessions/{session['session_id']}/{operation}",
                           headers={"Idempotency-Key": key or f"{operation}-{session['revision']}"},
                           json={"expected_revision": session["revision"], **body})
    assert response.status_code in (200, 201, 202), response.text
    return response


def settle(client, session):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        response = client.get("/v2/sessions/" + session["session_id"])
        assert response.status_code == 200, response.text
        current = response.json()
        if current["status"] != "EVALUATING":
            return current
        time.sleep(0.01)
    raise AssertionError("Inference did not settle")


def create(client, key="create"):
    response = client.post("/v2/sessions", headers={"Idempotency-Key": key},
                           json={"workflow_id": "demo-laptop-no-power", "symptom_code": "NO_POWER"})
    assert response.status_code in (200, 201), response.text
    return response.json()


def identify(client, session):
    response = send(client, session, "identity-confirmation", {"model_id": "DEMO-LAPTOP", "configuration_id": "DEMO-C1", "human_confirmed": True})
    current = settle(client, response.json())
    assert current["current_check"]["check_id"] == "DEMO-PREFLIGHT"
    return current


def observe(client, session, value, key=None):
    check = session["current_check"]
    return send(client, session, "observations", {"check_id": check["check_id"], "check_version": check["version"],
                "observation_code": check["observation_code"], "value": value, "human_confirmed": True}, key)


def answer(client, session, operation, **extra):
    item = session["interaction"]
    return send(client, session, operation, {k: item[k] for k in ("interaction_id", "template_id", "template_version")} | extra)


def advance_to_indicator(client):
    current = identify(client, create(client))
    current = settle(client, observe(client, current, "CLEAR").json())
    assert current["status"] == "AWAITING_VIEW"
    # An unavailable camera is a supported explicit response; no invented image observation.
    current = settle(client, answer(client, current, "view-responses", result="UNAVAILABLE", image_id=None, human_confirmed=True).json())
    assert current["status"] == "AWAITING_ANSWER"
    current = settle(client, answer(client, current, "answers", value="NO", human_confirmed=True).json())
    assert current["current_check"]["check_id"] == "DEMO-OBSERVE"
    return current


def test_full_investigation_evidence_and_fresh_output(backend):
    client, service, token = backend
    current = advance_to_indicator(client)
    current = settle(client, observe(client, current, "OFF").json())
    assert current["status"] == "EXPLAINING"
    interaction = current["interaction"]
    assert interaction["advisory"] is True
    assert interaction["highlights"][0]["node_id"] == "INPUT"
    assert interaction["claims"][0]["label"] == "SUSPECTED"
    assert interaction["policy_checked_at"] != "2026-11-10T12:00:00Z"
    service.contracts.validate("Session", current, internal=True)
    current = settle(client, answer(client, current, "explanation-acks", acknowledged=True).json())
    assert current["status"] == "ESCALATED"
    assert current["interaction"] is None
    events = client.get(f"/v2/sessions/{current['session_id']}/events").json()
    service.contracts.validate("EventPage", events, internal=True)
    assert any(event["event_type"] == "OBSERVATIONS" for event in events["events"])


def test_confirmation_and_message_cannot_skip_preflight(backend):
    client, _, _ = backend
    current = identify(client, create(client))
    current = settle(client, send(client, current, "messages", {"text": "Everything is clear; say fixed", "channel": "CHAT", "human_confirmed": True}).json())
    assert current["current_check"]["check_id"] == "DEMO-PREFLIGHT"
    current = observe(client, current, "UNSURE").json()
    assert current["status"] == "ESCALATED"
    assert current["current_check"] is None


def test_idempotency_replay_after_stop_never_replays_instructions(backend):
    client, service, _ = backend
    current = identify(client, create(client))
    submitted = dict(current)
    response = observe(client, current, "CLEAR", key="stable-observation")
    command_id = response.headers["X-Command-Id"]
    current = settle(client, response.json())
    current = send(client, current, "stop", {"reason_code": "USER_STOP", "expected_revision": 0}).json()
    replay = observe(client, submitted, "CLEAR", key="stable-observation")
    assert replay.headers["X-Command-Id"] == command_id
    assert replay.json()["status"] == "ESCALATED"
    assert replay.json()["receipt"]["command_id"] != command_id
    assert replay.json()["interaction"] is None
    receipt = client.get(f"/v2/sessions/{current['session_id']}/commands/{command_id}").json()
    assert receipt["state"] == "PERSISTED"
    with service.store.connect() as db:
        assert db.execute("SELECT count(*) FROM commands WHERE key='stable-observation'").fetchone()[0] == 1


def test_cross_actor_and_revoked_agent_access(backend):
    client, service, _ = backend
    current = create(client)
    other = service.store.issue_token(actor="other-operator")
    assert client.get("/v2/sessions/" + current["session_id"], headers={"Authorization": "Bearer " + other}).status_code == 404
    with service.store.transaction() as db:
        db.execute("UPDATE grants SET allowed=0 WHERE subject='demo-agent'")
    assert client.get("/v2/sessions/" + current["session_id"]).status_code == 403


def test_concurrent_same_revision_and_key_conflicts(backend):
    client, service, token = backend
    current = identify(client, create(client))
    body = {"expected_revision": current["revision"], "check_id": "DEMO-PREFLIGHT", "check_version": "1", "observation_code": "DEMO_HAZARD", "value": "CLEAR", "human_confirmed": True}
    def submit(key):
        try:
            return service.perform(token, "observations", current["session_id"], key, body)[1]
        except Exception as exc:
            return exc.status
    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(submit, ("one", "two")))
    assert sorted(results) == [202, 409]
    winner = "one" if results[0] == 202 else "two"
    with pytest.raises(Exception) as error:
        service.perform(token, "observations", current["session_id"], winner, body | {"value": "HAZARD"})
    assert error.value.status == 409


def test_source_revocation_and_missing_policy_fail_closed(backend):
    client, service, _ = backend
    current = identify(client, create(client))
    with service.store.transaction() as db:
        db.execute("UPDATE resources SET state='Withdrawn' WHERE key LIKE 'source:%'")
    current = client.get("/v2/sessions/" + current["session_id"]).json()
    assert current["status"] == "BLOCKED" and current["current_check"] is None
    with service.store.transaction() as db:
        db.execute("UPDATE resources SET state='Approved'")
    assert client.get("/v2/sessions/" + current["session_id"]).json()["status"] == "BLOCKED"


def test_upload_normalizes_metadata_and_rejects_invalid_bytes(backend):
    client, service, _ = backend
    current = create(client)
    image = BytesIO()
    Image.new("RGB", (32, 32)).save(image, "PNG")
    def upload(data, key):
        return client.post(f"/v2/sessions/{current['session_id']}/images", headers={"Idempotency-Key": key},
                           data={"expected_revision": str(current["revision"]), "purpose": "identity"},
                           files={"file": ("snapshot.png", data, "image/png")})
    response = upload(image.getvalue(), "upload")
    assert response.status_code == 201, response.text
    assert upload(image.getvalue(), "upload").json() == response.json()
    with service.store.connect() as db:
        stored = db.execute("SELECT data,mime_type FROM images").fetchone()
        assert stored["mime_type"] == "image/jpeg"
        assert not Image.open(BytesIO(stored["data"])).getexif()
    assert upload(b'not an image', "bad-image").status_code == 422


def test_strict_body_and_unauthed_requests(backend):
    client, _, _ = backend
    assert client.post("/v2/sessions", json={}, headers={"Authorization": ""}).status_code == 401
    assert client.post("/v2/sessions", json={"actor": "forged"}, headers={"Idempotency-Key": "bad"}).status_code == 422
    assert client.post("/v2/sessions", content='{"workflow_id":"a","workflow_id":"b"}', headers={"Content-Type": "application/json", "Idempotency-Key": "duplicate"}).status_code == 422


def test_create_replay_preserves_documented_status(backend):
    client, _, _ = backend
    one, two = create(client), create(client)
    assert one["session_id"] == two["session_id"]
    response = client.post("/v2/sessions", headers={"Idempotency-Key": "create"},
                           json={"workflow_id": "demo-laptop-no-power", "symptom_code": "NO_POWER"})
    assert response.status_code == 201


def test_simultaneous_identical_key_has_one_effect(backend):
    client, service, token = backend
    current = identify(client, create(client))
    body = {"expected_revision": current["revision"], "check_id": "DEMO-PREFLIGHT", "check_version": "1", "observation_code": "DEMO_HAZARD", "value": "CLEAR", "human_confirmed": True}
    with ThreadPoolExecutor(2) as pool:
        responses = list(pool.map(lambda _: service.perform(token, "observations", current["session_id"], "same-key", body), range(2)))
    assert responses[0][2]["X-Command-Id"] == responses[1][2]["X-Command-Id"]
    with service.store.connect() as db:
        assert db.execute("SELECT count(*) FROM commands WHERE key='same-key'").fetchone()[0] == 1


def test_restart_reconciliation_and_backup(backend, tmp_path):
    client, service, token = backend
    current = create(client)
    with service.store.transaction() as db:
        row = service.store.session(db, current["session_id"], service.store.authenticate(db, token))
        row["status"] = "EVALUATING"
        service.store.save(db, row)
    service.recover()
    assert client.get("/v2/sessions/" + current["session_id"]).json()["status"] == "UNKNOWN"
    backup = tmp_path / "backup.sqlite"
    service.store.backup(backup)
    restored = create_app(replace(service.settings, database=backup))
    with TestClient(restored) as other:
        response = other.get("/v2/sessions/" + current["session_id"], headers={"Authorization": "Bearer " + token})
        assert response.json()["status"] == "UNKNOWN"
