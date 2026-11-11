"""Deterministic, metadata-driven demo. It does not inspect or diagnose real images."""
from ..catalog import source_ref


class EngineStub:
    model_config_version = "deterministic-demo-1"
    prompt_version = "no-model-prompt-1"

    async def propose(self, request):
        catalog, context = request["approved_catalog"], request["investigation_context"]
        proposal = {k: request[k] for k in ("contract_version", "request_id", "session_id", "based_on_revision", "context_hash")}

        def emit(kind, payload):
            return dict(proposal, kind=kind, payload=payload)

        def template(kind, field, record, **extra):
            return emit(kind, {field: record["template_id"], "template_version": record["version"],
                               "sources": [source_ref(record)], **extra})

        if request["mode"] == "IDENTIFY":
            label = request["manual_label"]
            matches = {(c["model_id"], c["configuration_id"]) for c in catalog["checks"] if c["model_id"] == label}
            if matches:
                return emit("IDENTITY_CANDIDATES", {"candidates": [{"model_id": m, "configuration_id": c,
                            "label_excerpt": label, "basis": "MANUAL"} for m, c in sorted(matches)][:3]})
            views = [v for v in catalog["view_templates"] if v["purpose"] == "IDENTITY"]
            if views and not context["view_results"]:
                return template("REQUEST_VIEW", "view_template_id", views[0])
            return emit("IDENTITY_CANDIDATES", {"candidates": []})
        for view in catalog["view_templates"]:
            if view["purpose"] == "INVESTIGATION" and view["template_id"] not in context["prior_template_ids"]:
                return template("REQUEST_VIEW", "view_template_id", view)
        for question in catalog["question_templates"]:
            if question["template_id"] not in context["prior_template_ids"]:
                return template("ASK_QUESTION", "question_template_id", question)
        for check in catalog["checks"]:
            if check["check_id"] not in request["completed_check_ids"]:
                return emit("PROPOSE_CHECK", {"check_id": check["check_id"], "check_version": check["version"], "sources": [source_ref(check)]})
        for explanation in catalog["explanation_templates"]:
            rule = explanation["claim_rule"]
            evidence = [o["record_id"] for o in request["observations"]
                        if all(o[k] == rule[k] for k in ("check_id", "check_version", "observation_code")) and o["value"] in rule["allowed_values"]]
            if evidence and explanation["template_id"] not in context["prior_template_ids"]:
                return template("EXPLAIN", "explanation_template_id", explanation,
                                evidence_ids=evidence, highlight_node_ids=explanation["allowed_highlight_node_ids"])
        return emit("ESCALATE", {"reason_code": "EXHAUSTED"})
