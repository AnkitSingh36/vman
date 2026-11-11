"""Contract handoff, current media resolution and immutable knowledge regression checks."""
import asyncio
import copy
from dataclasses import replace
from io import BytesIO
import json

from fastapi.testclient import TestClient
from PIL import Image
import pytest

from mark1.server.app import create_app
from mark1.server.catalog import publish
from mark1.server.config import Settings
from mark1.server.errors import APIError
from mark1.server.testing.demo import main as run_demo
from test_backend import create, identify, observe, send, settle
from test_fail_closed import GateEngine


def test_canonical_swagger_has_bearer_and_no_external_refs(backend):
    client, _, _ = backend
    document = client.get("/openapi.json").json()
    assert document["security"] == [{"bearerAuth": []}]
    assert '"$ref"' not in json.dumps(document)
    assert "/v2/sessions/{id}/view-responses" in document["paths"]
    assert client.get("/docs").status_code == 200


def test_current_media_handle_is_scoped_and_sanitized(tmp_path):
    engine = GateEngine()
    app = create_app(Settings(database=tmp_path / "media.sqlite"), engine)
    service = app.state.service
    token = service.store.issue_token()
    other = service.store.issue_token(tenant="another-org")
    with TestClient(app) as client:
        client.headers["Authorization"] = "Bearer " + token
        current = create(client)
        frame = BytesIO()
        Image.new("RGB", (32, 32)).save(frame, "PNG")
        result = client.post(f"/v2/sessions/{current['session_id']}/images", headers={"Idempotency-Key": "frame"},
                             data={"expected_revision": current["revision"], "purpose": "identity"},
                             files={"file": ("demo.png", frame.getvalue(), "image/png")})
        assert result.status_code == 201
        current = settle(client, current)
        result = send(client, current, "identity-candidates", {"image_id": result.json()["image_id"]})
        assert engine.started.wait(2)
        with service.store.connect() as db:
            run = db.execute("SELECT * FROM inferences WHERE state='RUNNING'").fetchone()
        handle = json.loads(run["request"])["cleared_images"][0]["cleared_handle"]
        assert Image.open(BytesIO(service.resolve_image(token, run["id"], handle))).format == "JPEG"
        with pytest.raises(APIError):
            service.resolve_image(other, run["id"], handle)
        with service.store.transaction() as db:
            db.execute("UPDATE resources SET state='Withdrawn' WHERE key LIKE 'source:%'")
        with pytest.raises(APIError):
            service.resolve_image(token, run["id"], handle)
        # A failed media resolution must retain the policy stop even if an operator
        # later restores test authority. Production CLI cannot reverse withdrawals.
        with service.store.transaction() as db:
            db.execute("UPDATE resources SET state='Approved'")
        current = settle(client, current)
        assert current["status"] == "BLOCKED"
        with pytest.raises(APIError):
            service.resolve_image(token, run["id"], handle)
        engine.release.set()
        client.portal.call(asyncio.sleep, 0.02)


def test_record_immutable_across_new_catalog_and_catalog_change_stops(backend):
    client, service, _ = backend
    current = identify(client, create(client))
    catalog = service.contracts.read("request-fixtures.json")["catalog"]
    raw = (service.settings.contracts / "synthetic-guide.txt").read_bytes()
    sources = {("DEMO-GUIDE", "2"): raw}
    bad = copy.deepcopy(catalog)
    bad["catalog_version"] = "demo-new"
    bad["checks"][0]["instruction"] += " altered"
    with pytest.raises(ValueError):
        publish(service.store, service.contracts, bad, sources)
    catalog["catalog_version"] = "demo-new"
    publish(service.store, service.contracts, catalog, sources)
    current = settle(client, current)
    assert current["status"] == "UNKNOWN" and current["current_check"] is None


def test_hidden_restriction_and_replay_auth_first(backend):
    client, service, token = backend
    current = create(client)
    with service.store.transaction() as db:
        db.execute("UPDATE policies SET state='BLOCKED'")
    current = settle(client, current)
    assert current["status"] == "BLOCKED"
    assert current["reason_code"] == "WORK_UNAVAILABLE"
    with service.store.transaction() as db:
        db.execute("UPDATE principals SET active=0")
    replay = client.post("/v2/sessions", json={"workflow_id": "demo-laptop-no-power", "symptom_code": "NO_POWER"}, headers={"Idempotency-Key": "create"})
    assert replay.status_code == 401 and "current_check" not in replay.json()


def test_human_outcome_is_explicit_and_persisted(backend):
    client, service, token = backend
    current = identify(client, create(client))
    premature = client.post(f"/v2/sessions/{current['session_id']}/outcome", headers={"Idempotency-Key": "early"},
                            json={"expected_revision": current["revision"], "human_reported_outcome": "RESOLVED", "human_confirmed": True})
    assert premature.status_code == 409
    current = settle(client, observe(client, current, "CLEAR").json())
    current = send(client, current, "outcome", {"human_reported_outcome": "RESOLVED", "human_confirmed": True}).json()
    assert current["status"] == "COMPLETED"
    assert current["human_reported_outcome"] == "RESOLVED"
    assert current["receipt"]["state"] == "PERSISTED"
    assert current["interaction"] is None


def test_generated_snapshot_http_demo(capsys):
    run_demo()
    output = capsys.readouterr().out
    assert "Suspected node: INPUT" in output
    assert "ESCALATED" in output
