"""Adversarial engine, policy, media and crash regressions for the trusted boundary."""
import asyncio
import copy
from dataclasses import replace
from io import BytesIO
import threading

from fastapi.testclient import TestClient
from PIL import Image
import pytest

from mark1.server.__main__ import erase_session
from mark1.server.app import create_app
from mark1.server.catalog import publish, source_ref, validate_catalog
from mark1.server.config import Settings
from mark1.server.errors import APIError
from mark1.server.testing.engine_stub import EngineStub
from test_backend import answer, create, identify, observe, send, settle, advance_to_indicator


class BadEngine(EngineStub):
    def __init__(self, failure):
        self.failure = failure

    async def propose(self, request):
        result = await super().propose(request)
        if self.failure == "text":
            result["payload"]["instruction"] = "Untrusted operational model text"
        elif self.failure == "binding":
            result["context_hash"] = "f" * 64
        elif self.failure == "source":
            result["payload"]["sources"][0]["version"] = "unapproved"
        elif self.failure == "early-claim":
            template = request["approved_catalog"]["explanation_templates"][0]
            result.update(kind="EXPLAIN", payload={"explanation_template_id": template["template_id"], "template_version": template["version"],
                          "sources": [source_ref(template)], "evidence_ids": request["investigation_context"]["available_evidence_ids"], "highlight_node_ids": ["INPUT"]})
        elif self.failure == "exception":
            raise RuntimeError("PRIVATE provider detail must not be disclosed")
        else:
            await asyncio.sleep(1)
        return result


@pytest.mark.parametrize("failure", ["text", "binding", "source", "early-claim", "exception", "timeout"])
def test_invalid_engine_never_releases_output(tmp_path, failure):
    app = create_app(Settings(database=tmp_path / "bad.sqlite", inference_timeout=0.05), BadEngine(failure))
    token = app.state.service.store.issue_token()
    with TestClient(app) as client:
        client.headers["Authorization"] = "Bearer " + token
        current = identify(client, create(client))
        current = settle(client, observe(client, current, "CLEAR").json())
        assert current["status"] == "UNKNOWN"
        assert current["current_check"] is None and current["interaction"] is None
        assert "PRIVATE" not in str(current)


class GateEngine(EngineStub):
    def __init__(self):
        self.started, self.release = threading.Event(), threading.Event()

    async def propose(self, request):
        self.started.set()
        while not self.release.is_set():
            await asyncio.sleep(0.005)
        return await super().propose(request)


def test_stop_beats_late_model_response_and_media_handles(tmp_path):
    engine = GateEngine()
    app = create_app(Settings(database=tmp_path / "race.sqlite"), engine)
    service = app.state.service
    token = service.store.issue_token()
    with TestClient(app) as client:
        client.headers["Authorization"] = "Bearer " + token
        current = identify(client, create(client))
        response = observe(client, current, "CLEAR")
        assert engine.started.wait(2)
        current = send(client, response.json(), "hazards", {"expected_revision": 0, "hazard_code": "SWELLING"}).json()
        assert current["status"] == "ESCALATED"
        engine.release.set()
        # Give the old coroutine a chance to return; it must not revive the session.
        client.portal.call(asyncio.sleep, 0.05)
        current = settle(client, current)
        assert current["status"] == "ESCALATED" and current["interaction"] is None
        with service.store.connect() as db:
            run = db.execute("SELECT * FROM inferences").fetchone()
            assert run["state"] == "CANCELLED"
        with pytest.raises(APIError):
            service.resolve_image(token, run["id"], "foreign-handle")


def test_policy_unknown_and_stop_without_catalog(backend):
    client, service, _ = backend
    current = identify(client, create(client))
    with service.store.transaction() as db:
        db.execute("DELETE FROM policies")
    current = settle(client, current)
    assert current["status"] == "UNKNOWN"
    with service.store.transaction() as db:
        db.execute("INSERT INTO policies VALUES ('demo-org','demo-laptop-no-power','ACTIVE')")
    assert settle(client, current)["status"] == "UNKNOWN"
    other = identify(client, create(client, "second"))
    with service.store.transaction() as db:
        db.execute("UPDATE catalogs SET active=0")
    other = send(client, other, "stop", {"reason_code": "USER_STOP"}).json()
    assert other["status"] == "ESCALATED"


def test_claim_and_diagram_revocation_rechecked(backend):
    client, service, _ = backend
    current = advance_to_indicator(client)
    current = settle(client, observe(client, current, "OFF").json())
    with service.store.transaction() as db:
        db.execute("UPDATE resources SET state='Withdrawn' WHERE key='diagrams:DEMO-POWER-FLOW:1'")
    current = settle(client, current)
    assert current["status"] == "EXPLAINING"
    assert current["interaction"]["diagram"] is None and current["interaction"]["highlights"] == []
    with service.store.transaction() as db:
        db.execute("UPDATE resources SET state='Withdrawn' WHERE key='checks:DEMO-OBSERVE:1'")
    current = settle(client, current)
    assert current["status"] == "BLOCKED" and current["interaction"] is None


def test_catalog_immutability_prerequisites_and_graph(backend):
    _, service, _ = backend
    catalog = service.contracts.read("request-fixtures.json")["catalog"]
    raw = (service.settings.contracts / "synthetic-guide.txt").read_bytes()
    sources = {("DEMO-GUIDE", "2"): raw}
    for change in (lambda c: c["checks"][1].update(prerequisites=[]),
                   lambda c: c["diagrams"][0]["edges"][0].update(to_node_id="FOREIGN"),
                   lambda c: c["checks"].append(copy.deepcopy(c["checks"][0])),
                   lambda c: c["explanation_templates"][0]["claim_rule"].update(allowed_values=["INVALID"])):
        bad = copy.deepcopy(catalog)
        change(bad)
        with pytest.raises(ValueError):
            validate_catalog(service.contracts, bad, sources)
    bad = copy.deepcopy(catalog)
    bad["checks"][0]["instruction"] = "Alter an immutable approved version"
    with pytest.raises(ValueError):
        publish(service.store, service.contracts, bad, sources)
    with service.store.transaction() as db:
        db.execute("UPDATE resources SET state='Withdrawn' WHERE key='checks:DEMO-OBSERVE:1'")
    publish(service.store, service.contracts, catalog, sources)
    with service.store.connect() as db:
        assert db.execute("SELECT state FROM resources WHERE key='checks:DEMO-OBSERVE:1'").fetchone()[0] == "Withdrawn"


def test_storage_failure_rolls_back_human_command(backend, monkeypatch):
    client, service, token = backend
    current = identify(client, create(client))
    data = {"expected_revision": current["revision"], "check_id": "DEMO-PREFLIGHT", "check_version": "1", "observation_code": "DEMO_HAZARD", "value": "CLEAR", "human_confirmed": True}
    def fail(*args, **kwargs):
        import sqlite3
        raise sqlite3.OperationalError("simulated disk failure")
    with monkeypatch.context() as patch:
        patch.setattr(service.store, "event", fail)
        response = client.post(f"/v2/sessions/{current['session_id']}/observations", json=data, headers={"Idempotency-Key": "disk-failure"})
        assert response.status_code == 503
    assert service.read(token, current["session_id"])["status"] == "READY"
    with service.store.connect() as db:
        assert db.execute("SELECT count(*) FROM commands WHERE key='disk-failure'").fetchone()[0] == 0
    response = client.post(f"/v2/sessions/{current['session_id']}/observations", json=data, headers={"Idempotency-Key": "disk-failure"})
    assert response.status_code == 202


def test_session_erasure_and_command_tombstone(backend):
    client, service, _ = backend
    current = create(client)
    with pytest.raises(ValueError):
        erase_session(service, current["session_id"])
    current = send(client, current, "stop", {"reason_code": "USER_STOP"}).json()
    erase_session(service, current["session_id"])
    assert client.get("/v2/sessions/" + current["session_id"]).status_code == 404
    response = client.post("/v2/sessions", headers={"Idempotency-Key": "create"}, json={"workflow_id": "demo-laptop-no-power", "symptom_code": "NO_POWER"})
    assert response.status_code == 404
    with service.store.connect() as db:
        assert not db.execute("SELECT 1 FROM events WHERE session_id=?", (current["session_id"],)).fetchone()
        assert db.execute("SELECT 1 FROM authority_events WHERE action='SESSION_ERASED'").fetchone()


def test_media_foreign_reference_and_pixel_limit(backend):
    client, service, token = backend
    one, two = create(client), create(client, "two")
    image = BytesIO()
    Image.new("RGB", (20, 20)).save(image, "PNG")
    response = client.post(f"/v2/sessions/{one['session_id']}/images", headers={"Idempotency-Key": "image"},
                           data={"expected_revision": one["revision"], "purpose": "identity"}, files={"file": ("image.png", image.getvalue(), "image/png")})
    assert response.status_code == 201
    foreign = client.post(f"/v2/sessions/{two['session_id']}/identity-candidates", headers={"Idempotency-Key": "foreign"},
                          json={"expected_revision": two["revision"], "image_id": response.json()["image_id"]})
    assert foreign.status_code == 404
    from mark1.server.media import sanitize
    with pytest.raises(APIError):
        sanitize(image.getvalue(), "image/png", replace(service.settings, max_pixels=100))
    with pytest.raises(APIError):
        sanitize(image.getvalue(), "image/jpeg", service.settings)


def test_zero_session_inference_budget_and_pilot_disabled(tmp_path):
    with pytest.raises(ValueError):
        Settings(mode="pilot")
    app = create_app(Settings(database=tmp_path / "budget.sqlite", max_inferences=0))
    token = app.state.service.store.issue_token()
    with TestClient(app) as client:
        client.headers["Authorization"] = "Bearer " + token
        current = identify(client, create(client))
        current = settle(client, observe(client, current, "CLEAR").json())
        assert current["status"] == "ESCALATED" and current["reason_code"] == "BUDGET_EXCEEDED"
