"""Bounded structured investigation using only A's scoped catalog and cleared snapshots."""
import asyncio
import base64
from datetime import datetime, timezone
import hashlib
import json
import logging

from ..server.catalog import source_ref
from ..server.contracts import canonical
from .prompt import PROMPT_VERSION, SYSTEM

LOG = logging.getLogger("mark1.ai")
BINDINGS = ("contract_version", "request_id", "session_id", "based_on_revision", "context_hash")


def parse_decision(raw):
    if not isinstance(raw, str) or len(raw.encode("utf-8")) > 16_384:
        raise ValueError("Invalid bounded model output")

    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("Duplicate JSON field")
            result[key] = value
        return result

    def invalid_number(value):
        raise ValueError("Unexpected numeric output")

    result = json.loads(raw, object_pairs_hook=pairs, parse_float=invalid_number, parse_constant=invalid_number)
    if not isinstance(result, dict) or set(result) != {"kind", "payload"}:
        raise ValueError("Expected one structured decision")
    return result


class Investigator:
    """propose(request) is the engine port; A optionally supplies a scoped read_image callback.

    One model call per request, zero tools/retries. No session or permission writes.
    Output is still independently validated by server.state before any UI guidance.
    """
    accepts_cleared_media = True
    prompt_version = PROMPT_VERSION

    def __init__(self, provider, contracts):
        self.provider, self.contracts = provider, contracts
        self.model_config_version = provider.model_config_version
        schema = contracts.read("engine-proposal.schema.json")
        schema.pop("$id", None)
        schema["properties"] = {k: v for k, v in schema["properties"].items() if k in ("kind", "payload")}
        schema["required"] = ["kind", "payload"]
        self.output_schema = schema

    async def propose(self, request, *, read_image=None):
        self.contracts.validate("engine-request.schema.json", request, internal=True)
        if (request["context_hash"] != self.contracts.context_hash(request)
                or request["model_config_version"] != self.model_config_version
                or request["prompt_version"] != self.prompt_version):
            raise ValueError("Invalid investigator request binding")
        binding = {k: request[k] for k in BINDINGS}

        def escalate(reason):
            LOG.info("investigation output proposals=1 kind=ESCALATE reason=%s", reason)
            return dict(binding, kind="ESCALATE", payload={"reason_code": reason})

        budget = request["remaining_budgets"]
        seconds = min(60, (datetime.fromisoformat(budget["deadline_at"].replace("Z", "+00:00"))
                           - datetime.now(timezone.utc)).total_seconds())
        if budget["calls"] < 1 or budget["turns"] < 1 or seconds <= 0:
            return escalate("BUDGET_EXCEEDED")
        if request["cleared_images"] and read_image is None:
            return escalate("INSUFFICIENT_EVIDENCE")
        # Bindings and opaque handles are never model input. Only A resolves image bytes.
        context = {k: v for k, v in request.items() if k not in BINDINGS}
        context["cleared_images"] = [{k: v for k, v in frame.items() if k != "cleared_handle"}
                                     for frame in request["cleared_images"]]
        LOG.info("investigation input images=%d messages=%d catalog_records=%d",
                 len(request["cleared_images"]), len(request["investigation_context"]["messages"]),
                 sum(len(v) for v in request["approved_catalog"].values() if isinstance(v, list)))
        try:
            async with asyncio.timeout(seconds):
                content = [{"type": "text", "text": canonical(context)}]
                for frame in request["cleared_images"]:
                    raw = await read_image(frame["cleared_handle"])
                    if not isinstance(raw, bytes) or hashlib.sha256(raw).hexdigest() != frame["sha256"]:
                        raise ValueError("Cleared image binding mismatch")
                    content.append({"type": "image", "image_id": frame["image_id"], "mime_type": frame["mime_type"],
                                    "data": base64.b64encode(raw).decode("ascii")})
                messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": content}]
                raw = await self.provider.complete(messages, self.output_schema, budget["deadline_at"])
                decision = parse_decision(raw)
                proposal = dict(binding, **decision)
                self.contracts.validate("engine-proposal.schema.json", proposal, internal=True)
                self._references(request, proposal)
                LOG.info("investigation output proposals=1 kind=%s", proposal["kind"])
                return proposal
        except TimeoutError:
            return escalate("BUDGET_EXCEEDED")
        except Exception:
            # Do not log provider messages, private payloads, images or credentials.
            # asyncio cancellation is a BaseException and deliberately propagates.
            return escalate("MODEL_FAILURE")

    @staticmethod
    def _references(request, proposal):
        """Reject unsupported references early; A remains the independent policy authority."""
        kind, payload, catalog = proposal["kind"], proposal["payload"], request["approved_catalog"]
        if kind == "ESCALATE":
            return
        if kind == "IDENTITY_CANDIDATES":
            if request["mode"] != "IDENTIFY":
                raise ValueError("Wrong mode")
            supported = {(c["model_id"], c["configuration_id"]) for c in catalog["checks"]}
            for candidate in payload["candidates"]:
                if (candidate["model_id"], candidate["configuration_id"]) not in supported:
                    raise ValueError("Unsupported identity")
                if candidate["basis"] == "IMAGE" and not request["cleared_images"]:
                    raise ValueError("No image supplied")
                if candidate["basis"] == "MANUAL" and (not request["manual_label"] or not candidate["label_excerpt"]
                                                       or candidate["label_excerpt"] not in request["manual_label"]):
                    raise ValueError("No matching manual label")
            return
        group, key = {"PROPOSE_CHECK": ("checks", "check_id"), "ASK_OBSERVATION": ("checks", "check_id"),
                      "REQUEST_VIEW": ("view_templates", "view_template_id"),
                      "ASK_QUESTION": ("question_templates", "question_template_id"),
                      "EXPLAIN": ("explanation_templates", "explanation_template_id")}[kind]
        version = payload["check_version"] if group == "checks" else payload["template_version"]
        id_key = "check_id" if group == "checks" else "template_id"
        records = [r for r in catalog[group] if r[id_key] == payload[key] and r["version"] == version]
        if len(records) != 1 or payload["sources"] != [source_ref(records[0])]:
            raise ValueError("Unknown or unsupported reference")
        if request["mode"] == "IDENTIFY" and (kind != "REQUEST_VIEW" or records[0]["purpose"] != "IDENTITY"):
            raise ValueError("Wrong identification proposal")
        if request["mode"] == "INVESTIGATE" and kind == "REQUEST_VIEW" and records[0]["purpose"] != "INVESTIGATION":
            raise ValueError("Wrong investigation view")
