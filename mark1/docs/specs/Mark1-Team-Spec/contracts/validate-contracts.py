"""Offline v2 artifact checks; not backend/AI acceptance tests.

Install validation-requirements.txt into an isolated environment, then run this file.
Schema resources resolve locally; network retrieval is disabled.
"""
from __future__ import annotations

import copy
import csv
import hashlib
import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

ROOT = Path(__file__).resolve().parent
BASE = "https://schemas.mark1.invalid/v2/"


def read(name):
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def main():
    resources = []
    for path in ROOT.glob("*.schema.json"):
        schema = read(path.name)
        Draft202012Validator.check_schema(schema)
        resource = Resource.from_contents(schema)
        resources.extend([(schema["$id"], resource), (path.as_uri(), resource)])
    api = read("public-api.openapi.json")
    api_uri = BASE + "public-api.openapi.json"
    resources.append((api_uri, Resource.from_contents(api, default_specification=DRAFT202012)))
    registry = Registry().with_resources(resources)
    count = 0

    def check(payload, schema_name, expected=True, public=False):
        nonlocal count
        uri = (api_uri + "#/components/schemas/" + schema_name) if public else BASE + schema_name
        validator = Draft202012Validator({"$ref": uri}, registry=registry, format_checker=FormatChecker())
        errors = list(validator.iter_errors(payload))
        if bool(errors) == expected:
            details = " | ".join(f"{list(e.path)}: {e.message}" for e in errors[:3])
            raise AssertionError(f"{schema_name}: expected valid={expected}. {details}")
        count += 1

    fixtures = read("all-fixtures.json")
    for session in [*fixtures["sessions"].values(), *fixtures["session_variants"].values()]:
        check(session, "session.schema.json")
    check(fixtures["sessions"]["READY"], "Session", public=True)
    for proposal in fixtures["engine_proposals"].values():
        check(proposal, "engine-proposal.schema.json")
    for error in fixtures["errors"].values():
        check(error, "Error", public=True)
    requests = read("request-fixtures.json")
    check(requests["catalog"], "catalog.schema.json")
    for name in ("identify_request", "investigate_request"):
        check(requests[name], "engine-request.schema.json")
    bodies = read("public-request-fixtures.json")
    for name, payload in bodies["positive"].items():
        check(payload, name, public=True)
    for case in bodies["variants"]:
        check(case["payload"], case["schema"], public=True)
    for case in bodies["negative"]:
        check(case["payload"], case["schema"], False, public=True)
    examples = read("examples.json")
    for name, payload in examples.items():
        if name.endswith("_session"):
            check(payload, "session.schema.json")
    check(examples["engine_proposal"], "engine-proposal.schema.json")

    def reject_session(state, change):
        payload = copy.deepcopy(fixtures["sessions"][state])
        change(payload)
        check(payload, "session.schema.json", False)

    reject_session("READY", lambda p: p.update(current_check=None))
    reject_session("BLOCKED", lambda p: p.update(current_check=fixtures["sessions"]["READY"]["current_check"]))
    reject_session("RECORD_PENDING", lambda p: p["receipt"].update(state="PERSISTED", record_id="record"))
    reject_session("COMPLETED", lambda p: p["receipt"].update(record_id=None))
    reject_session("READY", lambda p: p["current_check"].pop("stop_conditions"))
    reject_session("READY", lambda p: p["current_check"].pop("guidance_valid_until"))
    reject_session("READY", lambda p: p.update(contract_version="1.0"))
    reject_session("AWAITING_VIEW", lambda p: p.update(interaction=None))
    reject_session("AWAITING_VIEW", lambda p: p.update(identity=None))
    reject_session("AWAITING_ANSWER", lambda p: p.update(identity=None))
    reject_session("EXPLAINING", lambda p: p.update(identity=None))
    reject_session("BLOCKED", lambda p: p.update(interaction=fixtures["sessions"]["AWAITING_VIEW"]["interaction"]))
    reject_session("AWAITING_VIEW", lambda p: p["interaction"].update(kind="QUESTION"))
    reject_session("AWAITING_ANSWER", lambda p: p["interaction"].update(options=[]))
    reject_session("EXPLAINING", lambda p: p["interaction"].update(advisory=False))
    reject_session("EXPLAINING", lambda p: p["interaction"].update(diagram=None))
    reject_session("EXPLAINING", lambda p: p["interaction"]["claims"][0].update(evidence_ids=[]))
    reject_session("EXPLAINING", lambda p: p["interaction"]["diagram"]["nodes"][0].update(x=1001))
    reject_session("AWAITING_VIEW", lambda p: p["interaction"].update(audio_url="https://untrusted.invalid/audio"))
    reject_session("AWAITING_ANSWER", lambda p: p.update(receipt={"command_id": "cmd", "state": "PENDING", "record_id": None}))
    for kind in ("PROPOSE_CHECK", "REQUEST_VIEW", "ASK_QUESTION", "EXPLAIN"):
        bad = copy.deepcopy(fixtures["engine_proposals"][kind])
        bad["payload"]["instruction"] = "Untrusted generated instruction"
        check(bad, "engine-proposal.schema.json", False)
    bad = copy.deepcopy(fixtures["engine_proposals"]["ASK_OBSERVATION"])
    bad["payload"].pop("check_id")
    check(bad, "engine-proposal.schema.json", False)
    bad = copy.deepcopy(fixtures["engine_proposals"]["EXPLAIN"])
    bad["payload"]["evidence_ids"] = []
    check(bad, "engine-proposal.schema.json", False)
    for mutate in (
        lambda r: r.update(confirmed_identity=None),
        lambda r: r["remaining_budgets"].update(calls=17),
        lambda r: r.pop("investigation_context"),
        lambda r: r.update(mode="NEXT_CHECK"),
        lambda r: r["investigation_context"].update(inferences_used=25),
        lambda r: r["approved_catalog"]["checks"][0].update(state="Withdrawn"),
    ):
        bad = copy.deepcopy(requests["investigate_request"])
        mutate(bad)
        check(bad, "engine-request.schema.json", False)
    print(f"{count} positive/negative schema fixture checks passed.")

    # Artifact consistency checks do not implement runtime authorization.
    catalog = requests["catalog"]
    assert all(requests[n]["approved_catalog"] == catalog for n in ("identify_request", "investigate_request"))
    assert set(fixtures["sessions"]) == set(read("session.schema.json")["properties"]["status"]["enum"])
    assert set(fixtures["engine_proposals"]) == set(read("engine-proposal.schema.json")["properties"]["kind"]["enum"])
    digest = hashlib.sha256((ROOT / "synthetic-guide.txt").read_bytes()).hexdigest()
    checks = {(r["check_id"], r["version"]): r for r in catalog["checks"]}
    assert len(checks) == len(catalog["checks"])
    diagrams = {(d["diagram_id"], d["version"]): d for d in catalog["diagrams"]}
    assert len(diagrams) == len(catalog["diagrams"])
    for group in ("checks", "view_templates", "question_templates", "explanation_templates", "diagrams"):
        for record in catalog[group]:
            assert record["source"]["sha256"] == digest
    for d in diagrams.values():
        nodes = {n["node_id"] for n in d["nodes"]}
        assert len(nodes) == len(d["nodes"])
        assert all(e["from_node_id"] in nodes and e["to_node_id"] in nodes for e in d["edges"])
    for template in catalog["explanation_templates"]:
        rule = template["claim_rule"]
        target = checks[(rule["check_id"], rule["check_version"])]
        assert rule["observation_code"] == target["observation_code"]
        assert set(rule["allowed_values"]) <= set(target["options"])
        if template["diagram_id"]:
            d = diagrams[(template["diagram_id"], template["diagram_version"])]
            assert set(template["allowed_highlight_node_ids"]) <= {n["node_id"] for n in d["nodes"]}
    for path, methods in api["paths"].items():
        assert path.startswith("/v2/")
        for method, op in methods.items():
            for response in op["responses"].values():
                for media in response.get("content", {}).values():
                    ref = media["schema"].get("$ref")
                    if ref and ref.startswith("#/components/schemas/"):
                        assert ref.rsplit("/", 1)[1] in api["components"]["schemas"]
            if method == "post":
                assert any(p["name"] == "Idempotency-Key" and p["required"] for p in op["parameters"])
    operations = {op["operationId"] for methods in api["paths"].values() for op in methods.values()}
    assert len(operations) == sum(len(m) for m in api["paths"].values())
    for scenario in read("scenario-fixtures.json")["scenarios"]:
        assert all(state in fixtures["sessions"] for state in scenario["expected_states"])
    with (ROOT.parent / "09-BACKLOG.csv").open(encoding="utf-8", newline="") as stream:
        tickets = list(csv.DictReader(stream))
    owners = {t["ticket"]: t["owner"] for t in tickets}
    assert len(owners) == len(tickets)
    visited, active = set(), set()
    dependencies = {t["ticket"]: list(filter(None, t["depends_on"].split(";"))) for t in tickets}

    def visit(ticket):
        assert ticket not in active, "Backlog dependency cycle"
        if ticket in visited:
            return
        active.add(ticket)
        for dep in dependencies[ticket]:
            assert dep in owners, dep
            visit(dep)
        active.remove(ticket)
        visited.add(ticket)

    for ticket, owner in owners.items():
        assert owner in {"A", "V", "J"} and ticket.startswith(owner + "-")
        visit(ticket)
    print(f"Catalog/source/graph, v2 API, scenario and {len(tickets)} ownership/dependency checks passed.")
    print("Artifacts only: runtime authorization, evidence semantics, speech and AI quality remain unverified.")


if __name__ == "__main__":
    main()
