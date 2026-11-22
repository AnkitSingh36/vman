"""V-owned provider-neutral regressions. Scripted model responses are not model accuracy evidence."""
import asyncio
import base64
import copy
from datetime import datetime, timedelta, timezone
import hashlib
from io import BytesIO
import json

from fastapi.testclient import TestClient
from PIL import Image
import pytest

from mark1.ai import Investigator, ProviderAdapter
from mark1.ai.prompt import PROMPT_VERSION
from mark1.server.app import create_app
from mark1.server.catalog import source_ref
from mark1.server.config import Settings
from mark1.server.contracts import Contracts
from test_backend import answer, create, observe, send, settle


class ScriptedModel:
    def __init__(self, *outputs):
        self.outputs, self.calls = list(outputs), []

    async def generate(self, **kwargs):
        self.calls.append(kwargs)
        value = self.outputs.pop(0)
        if isinstance(value, Exception):
            raise value
        return json.dumps(value) if isinstance(value, dict) else value


@pytest.fixture
def contracts():
    return Contracts(Settings().contracts)


def bound_request(contracts, mode="INVESTIGATE", seconds=60):
    request = contracts.read("request-fixtures.json")["identify_request" if mode == "IDENTIFY" else "investigate_request"]
    request.update(model_config_version="scripted-eval-1", prompt_version=PROMPT_VERSION)
    request["remaining_budgets"]["deadline_at"] = (datetime.now(timezone.utc) + timedelta(seconds=seconds)).isoformat()
    request["context_hash"] = contracts.context_hash(request)
    return request


def decision(contracts, kind):
    catalog = contracts.read("request-fixtures.json")["catalog"]
    if kind == "ESCALATE":
        return {"kind": kind, "payload": {"reason_code": "INSUFFICIENT_EVIDENCE"}}
    if kind == "IDENTITY_CANDIDATES":
        return {"kind": kind, "payload": {"candidates": [{"model_id": "DEMO-LAPTOP", "configuration_id": "DEMO-C1",
                                                           "label_excerpt": "DEMO-LAPTOP", "basis": "MANUAL"}]}}
    if kind in ("PROPOSE_CHECK", "ASK_OBSERVATION"):
        check = catalog["checks"][1]
        payload = {"check_id": check["check_id"], "check_version": check["version"], "sources": [source_ref(check)]}
        if kind == "ASK_OBSERVATION":
            payload["observation_code"] = check["observation_code"]
    else:
        group, key = {"REQUEST_VIEW": ("view_templates", "view_template_id"),
                      "ASK_QUESTION": ("question_templates", "question_template_id"),
                      "EXPLAIN": ("explanation_templates", "explanation_template_id")}[kind]
        record = next(r for r in catalog[group] if kind != "REQUEST_VIEW" or r["purpose"] == "INVESTIGATION")
        payload = {key: record["template_id"], "template_version": record["version"], "sources": [source_ref(record)]}
        if kind == "EXPLAIN":
            payload.update(evidence_ids=["ev-indicator"], highlight_node_ids=record["allowed_highlight_node_ids"])
    return {"kind": kind, "payload": payload}


@pytest.mark.parametrize("kind", ["IDENTITY_CANDIDATES", "REQUEST_VIEW", "ASK_QUESTION", "PROPOSE_CHECK", "ASK_OBSERVATION", "EXPLAIN", "ESCALATE"])
def test_structured_decisions_use_trusted_binding_without_mutating_context(contracts, kind):
    request = bound_request(contracts, "IDENTIFY" if kind == "IDENTITY_CANDIDATES" else "INVESTIGATE")
    original = copy.deepcopy(request)
    model = ScriptedModel(decision(contracts, kind))
    engine = Investigator(ProviderAdapter("scripted-eval-1", model.generate), contracts)
    proposal = asyncio.run(engine.propose(request))
    assert proposal["kind"] == kind
    assert all(proposal[k] == request[k] for k in ("contract_version", "request_id", "session_id", "based_on_revision", "context_hash"))
    contracts.validate("engine-proposal.schema.json", proposal, internal=True)
    assert request == original and len(model.calls) == 1
    assert model.calls[0]["max_output_tokens"] == 2048
    assert set(model.calls[0]["output_schema"]["properties"]) == {"kind", "payload"}
    assert "request_id" not in model.calls[0]["messages"][1]["content"][0]["text"]


@pytest.mark.parametrize("bad", [
    '```json\n{}\n```', '{"kind":"ESCALATE","kind":"EXPLAIN","payload":{}}',
    '{"kind":"ESCALATE","payload":{"reason_code":"MODEL_FAILURE"},"request_id":"forged"}',
    '{"kind":"ESCALATE","payload":{"reason_code":"MODEL_FAILURE","instruction":"Open the case"}}',
    '{"kind":"ESCALATE","payload":{"reason_code":"MODEL_FAILURE","score":NaN}}',
    '{}', '[]', 'x' * 16_385, None,
])
def test_malformed_model_output_never_releases_guidance(contracts, bad):
    model = ScriptedModel(bad)
    proposal = asyncio.run(Investigator(ProviderAdapter("scripted-eval-1", model.generate), contracts).propose(bound_request(contracts)))
    assert proposal["kind"] == "ESCALATE" and proposal["payload"]["reason_code"] == "MODEL_FAILURE"
    assert len(model.calls) == 1  # No hidden retries or deterministic fallback.


@pytest.mark.parametrize("invalid", ["foreign-id", "foreign-source", "wrong-mode", "image-without-frame", "invented-label"])
def test_unsupported_model_references_are_rejected(contracts, invalid):
    request = bound_request(contracts, "IDENTIFY" if invalid in ("wrong-mode", "image-without-frame", "invented-label") else "INVESTIGATE")
    output = decision(contracts, "IDENTITY_CANDIDATES" if invalid in ("image-without-frame", "invented-label") else "PROPOSE_CHECK")
    if invalid == "foreign-id":
        output["payload"]["check_id"] = "FOREIGN"
    elif invalid == "foreign-source":
        output["payload"]["sources"][0]["version"] = "withdrawn"
    elif invalid == "image-without-frame":
        output["payload"]["candidates"][0]["basis"] = "IMAGE"
    elif invalid == "invented-label":
        output["payload"]["candidates"][0]["label_excerpt"] = "invented serial"
    model = ScriptedModel(output)
    result = asyncio.run(Investigator(ProviderAdapter("scripted-eval-1", model.generate), contracts).propose(request))
    assert result["payload"]["reason_code"] == "MODEL_FAILURE"


@pytest.mark.parametrize("limit", ["calls", "turns", "deadline"])
def test_exhausted_budget_never_calls_provider(contracts, limit):
    request = bound_request(contracts, seconds=-1 if limit == "deadline" else 60)
    if limit != "deadline":
        request["remaining_budgets"][limit] = 0
    model = ScriptedModel()
    result = asyncio.run(Investigator(ProviderAdapter("scripted-eval-1", model.generate), contracts).propose(request))
    assert result["payload"]["reason_code"] == "BUDGET_EXCEEDED" and not model.calls


def test_tampered_context_never_reaches_provider(contracts):
    request = bound_request(contracts)
    request["manual_label"] = "changed after hashing"
    model = ScriptedModel()
    with pytest.raises(ValueError, match="binding"):
        asyncio.run(Investigator(ProviderAdapter("scripted-eval-1", model.generate), contracts).propose(request))
    assert not model.calls


@pytest.mark.parametrize("reader", ["valid", "wrong-bytes", "missing"])
def test_only_bound_media_bytes_reach_model(contracts, reader):
    raw = b"synthetic-cleared-bytes"
    request = bound_request(contracts)
    request["cleared_images"] = [{"image_id": "selected-frame", "sha256": hashlib.sha256(raw).hexdigest(),
                                  "mime_type": "image/jpeg", "cleared_handle": "private-handle"}]
    request["context_hash"] = contracts.context_hash(request)
    model = ScriptedModel(decision(contracts, "ESCALATE"))
    calls = []

    async def read(handle):
        calls.append(handle)
        return raw if reader == "valid" else b"foreign"

    result = asyncio.run(Investigator(ProviderAdapter("scripted-eval-1", model.generate), contracts).propose(
        request, read_image=None if reader == "missing" else read))
    if reader == "valid":
        blocks = model.calls[0]["messages"][1]["content"]
        assert base64.b64decode(blocks[1]["data"]) == raw
        assert "private-handle" not in json.dumps(model.calls)
        assert calls == ["private-handle"]
    else:
        assert not model.calls
        assert result["payload"]["reason_code"] in ("MODEL_FAILURE", "INSUFFICIENT_EVIDENCE")


def test_provider_failure_is_safe_and_not_logged(contracts, caplog):
    model = ScriptedModel(RuntimeError("PRIVATE provider credential or response"))
    result = asyncio.run(Investigator(ProviderAdapter("scripted-eval-1", model.generate), contracts).propose(bound_request(contracts)))
    assert result["payload"]["reason_code"] == "MODEL_FAILURE"
    assert "PRIVATE" not in caplog.text and "PRIVATE" not in json.dumps(result)


def test_provider_cancellation_and_deadline_are_enforced(contracts):
    async def run(cancel):
        started, cancelled = asyncio.Event(), asyncio.Event()

        async def generate(**kwargs):
            started.set()
            try:
                await asyncio.sleep(10)
            finally:
                cancelled.set()

        request = bound_request(contracts, seconds=60 if cancel else 0.05)
        engine = Investigator(ProviderAdapter("scripted-eval-1", generate), contracts)
        task = asyncio.create_task(engine.propose(request))
        if cancel:
            await started.wait()
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        else:
            result = await task
            assert result["payload"]["reason_code"] == "BUDGET_EXCEEDED"
        assert cancelled.is_set()

    asyncio.run(run(True))
    asyncio.run(run(False))


def test_sync_provider_and_ambiguous_app_configuration_are_rejected(tmp_path):
    with pytest.raises(ValueError, match="async"):
        ProviderAdapter("sync-model", lambda **kwargs: "{}")
    with pytest.raises(ValueError, match="not both"):
        create_app(Settings(database=tmp_path / "unused.sqlite"), engine=object(), provider=object())


def test_provider_injected_http_journey_keeps_backend_authoritative(tmp_path, contracts):
    outputs = [decision(contracts, k) for k in ("IDENTITY_CANDIDATES", "REQUEST_VIEW", "ASK_QUESTION", "PROPOSE_CHECK", "EXPLAIN", "ESCALATE")]
    # The final real record ID is created by the backend; bind it from supplied context in the fake model.
    model = ScriptedModel(*outputs)

    async def generate(**kwargs):
        if model.outputs[0]["kind"] == "EXPLAIN":
            context = json.loads(kwargs["messages"][1]["content"][0]["text"])
            model.outputs[0]["payload"]["evidence_ids"] = [context["observations"][-1]["record_id"]]
        return await model.generate(**kwargs)

    app = create_app(Settings(database=tmp_path / "ai.sqlite"), provider=ProviderAdapter("scripted-eval-1", generate))
    token = app.state.service.store.issue_token()
    with TestClient(app) as client:
        client.headers["Authorization"] = "Bearer " + token
        assert client.get("/health").json()["engine"] == "structured-investigator"
        current = create(client)
        current = settle(client, send(client, current, "identity-candidates", {"manual_label": "DEMO-LAPTOP"}).json())
        assert current["status"] == "AWAITING_IDENTITY" and current["identity"] is None
        current = settle(client, send(client, current, "identity-confirmation", {
            "model_id": "DEMO-LAPTOP", "configuration_id": "DEMO-C1", "human_confirmed": True}).json())
        assert current["current_check"]["check_id"] == "DEMO-PREFLIGHT"
        assert len(model.calls) == 1  # Backend, not model, selects preflight.
        current = settle(client, observe(client, current, "CLEAR").json())
        frame = BytesIO()
        Image.new("RGB", (32, 32), (40, 80, 120)).save(frame, "PNG")
        receipt = client.post(f"/v2/sessions/{current['session_id']}/images", headers={"Idempotency-Key": "ai-frame"},
                              data={"expected_revision": current["revision"], "purpose": "investigation"},
                              files={"file": ("fictional.png", frame.getvalue(), "image/png")})
        assert receipt.status_code == 201
        current = settle(client, current)
        current = settle(client, answer(client, current, "view-responses", result="IMAGE", image_id=receipt.json()["image_id"], human_confirmed=True).json())
        assert any(block["type"] == "image" for block in model.calls[-1]["messages"][1]["content"])
        current = settle(client, answer(client, current, "answers", value="NO", human_confirmed=True).json())
        current = settle(client, observe(client, current, "OFF").json())
        assert current["status"] == "EXPLAINING" and current["interaction"]["advisory"] is True
        assert current["interaction"]["diagram"] is not None
        current = settle(client, answer(client, current, "explanation-acks", acknowledged=True).json())
        assert current["status"] == "ESCALATED" and current["interaction"] is None
        assert len(model.calls) == 6


def test_backend_rejects_schema_valid_ai_claim_without_durable_support(tmp_path, contracts):
    model = ScriptedModel(decision(contracts, "EXPLAIN"))
    app = create_app(Settings(database=tmp_path / "unsupported-claim.sqlite"),
                     provider=ProviderAdapter("scripted-eval-1", model.generate))
    token = app.state.service.store.issue_token()
    with TestClient(app) as client:
        client.headers["Authorization"] = "Bearer " + token
        current = create(client)
        current = settle(client, send(client, current, "identity-confirmation", {
            "model_id": "DEMO-LAPTOP", "configuration_id": "DEMO-C1", "human_confirmed": True}).json())
        current = settle(client, observe(client, current, "CLEAR").json())
        assert current["status"] == "UNKNOWN"
        assert current["interaction"] is None and current["current_check"] is None
        assert len(model.calls) == 1
