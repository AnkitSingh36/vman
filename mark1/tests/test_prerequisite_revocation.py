"""A completed check remains evidence, but revoked authority cannot authorize dependent output."""
import asyncio
import copy
import threading

from fastapi.testclient import TestClient
import pytest

from mark1.server.app import create_app
from mark1.server.catalog import publish
from mark1.server.config import Settings
from mark1.server.testing.engine_stub import EngineStub
from test_backend import advance_to_indicator, observe, settle


@pytest.fixture
def chain(tmp_path):
    app = create_app(Settings(database=tmp_path / "chain.sqlite"))
    service = app.state.service
    catalog = service.contracts.read("request-fixtures.json")["catalog"]
    catalog["catalog_version"] = "revocation-chain"
    ancestor = catalog["checks"][1]
    ancestor["version"] = "chain-1"
    # Isolate the ancestor's source: withdrawing it must not directly withdraw
    # the current check, preflight or explanation and conceal a dependency bug.
    ancestor["source"]["source_id"] = "DEMO-ANCESTOR"
    previous = ancestor
    for identifier in ("DEMO-MIDDLE", "DEMO-FOLLOWUP"):
        check = copy.deepcopy(catalog["checks"][1])
        check.update(check_id=identifier, version="1", source=copy.deepcopy(catalog["checks"][0]["source"]),
                     prerequisites=[{"check_id": previous["check_id"], "check_version": previous["version"],
                                     "observation_code": previous["observation_code"], "allowed_values": ["OFF"]}])
        catalog["checks"].append(check)
        previous = check
    catalog["explanation_templates"][0]["version"] = "chain-1"
    catalog["explanation_templates"][0]["claim_rule"].update(check_id="DEMO-FOLLOWUP", check_version="1")
    raw = (service.settings.contracts / "synthetic-guide.txt").read_bytes()
    publish(service.store, service.contracts, catalog, {("DEMO-GUIDE", "2"): raw, ("DEMO-ANCESTOR", "2"): raw})
    token = service.store.issue_token()
    with TestClient(app) as client:
        client.headers["Authorization"] = "Bearer " + token
        yield client, service


def advance_chain(client, stage):
    current = advance_to_indicator(client)
    current = settle(client, observe(client, current, "OFF").json())
    assert current["current_check"]["check_id"] == "DEMO-MIDDLE"
    if stage in ("transitive", "explanation"):
        current = settle(client, observe(client, current, "OFF").json())
        assert current["current_check"]["check_id"] == "DEMO-FOLLOWUP"
    if stage == "explanation":
        current = settle(client, observe(client, current, "OFF").json())
        assert current["status"] == "EXPLAINING" and current["interaction"]["highlights"]
    return current


def revoke(service, authority):
    with service.store.transaction() as db:
        if authority in ("actor", "agent"):
            subject = "demo-operator" if authority == "actor" else "demo-agent"
            db.execute("UPDATE grants SET allowed=0 WHERE subject=? AND resource='source:DEMO-ANCESTOR'", (subject,))
        else:
            key = "checks:DEMO-OBSERVE:chain-1" if authority == "record" else "source:DEMO-ANCESTOR:2"
            db.execute("UPDATE resources SET state='Withdrawn' WHERE key=?", (key,))


@pytest.mark.parametrize("stage", ["direct", "transitive", "explanation"])
@pytest.mark.parametrize("authority", ["record", "source", "actor", "agent"])
@pytest.mark.parametrize("surface", ["read", "submit"])
def test_revoked_ancestor_blocks_dependent_guidance(chain, stage, authority, surface):
    client, service = chain
    current = advance_chain(client, stage)
    sid = current["session_id"]
    with service.store.connect() as db:
        observations = db.execute("SELECT count(*) FROM events WHERE session_id=? AND event_type='OBSERVATIONS'", (sid,)).fetchone()[0]
    revoke(service, authority)
    if surface == "submit":
        if stage == "explanation":
            item = current["interaction"]
            operation = "explanation-acks"
            body = {k: item[k] for k in ("interaction_id", "template_id", "template_version")}
            body["acknowledged"] = True
        else:
            item = current["current_check"]
            operation = "observations"
            body = {"check_id": item["check_id"], "check_version": item["version"],
                    "observation_code": item["observation_code"], "value": "OFF", "human_confirmed": True}
        body["expected_revision"] = current["revision"]
        response = client.post(f"/v2/sessions/{sid}/{operation}", json=body,
                               headers={"Idempotency-Key": "after-revocation"})
        assert response.status_code == 409
    response = client.get(f"/v2/sessions/{sid}")
    assert response.status_code == 200
    blocked = response.json()
    assert blocked["status"] == "BLOCKED"
    assert blocked["reason_code"] == "WORK_UNAVAILABLE"
    assert blocked["current_check"] is None and blocked["interaction"] is None
    with service.store.connect() as db:
        assert db.execute("SELECT count(*) FROM events WHERE session_id=? AND event_type='OBSERVATIONS'", (sid,)).fetchone()[0] == observations
        assert not db.execute("SELECT 1 FROM commands WHERE key='after-revocation'").fetchone()


def test_command_replay_cannot_restore_revoked_dependent_output(chain):
    client, service = chain
    current = advance_to_indicator(client)
    check = current["current_check"]
    body = {"expected_revision": current["revision"], "check_id": check["check_id"], "check_version": check["version"],
            "observation_code": check["observation_code"], "value": "OFF", "human_confirmed": True}
    path = f"/v2/sessions/{current['session_id']}/observations"
    headers = {"Idempotency-Key": "ancestor-observation"}
    first = client.post(path, json=body, headers=headers)
    assert first.status_code == 202
    assert settle(client, first.json())["current_check"]["check_id"] == "DEMO-MIDDLE"
    revoke(service, "record")
    replay = client.post(path, json=body, headers=headers)
    assert replay.status_code == 200
    assert replay.headers["X-Command-Id"] == first.headers["X-Command-Id"]
    assert replay.json()["status"] == "BLOCKED" and replay.json()["current_check"] is None
    with service.store.transaction() as db:
        db.execute("UPDATE resources SET state='Approved' WHERE key='checks:DEMO-OBSERVE:chain-1'")
    assert client.get(f"/v2/sessions/{current['session_id']}").json()["status"] == "BLOCKED"


@pytest.mark.parametrize("output", ["check", "explanation"])
def test_revocation_during_inference_cannot_release_dependent_output(chain, output):
    class DelayedEngine(EngineStub):
        def __init__(self):
            self.started, self.release = threading.Event(), threading.Event()

        async def propose(self, request):
            proposal = await super().propose(request)
            self.started.set()
            while not self.release.is_set():
                await asyncio.sleep(0.005)
            return proposal

    client, service = chain
    current = advance_to_indicator(client) if output == "check" else advance_chain(client, "transitive")
    engine = DelayedEngine()
    client.app.state.runner.engine = engine
    response = observe(client, current, "OFF")
    try:
        assert engine.started.wait(2)
        revoke(service, "record")
    finally:
        engine.release.set()
    stopped = settle(client, response.json())
    assert stopped["status"] in ("BLOCKED", "UNKNOWN")
    assert stopped["current_check"] is None and stopped["interaction"] is None
