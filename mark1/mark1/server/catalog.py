"""A's publication/bridge boundary; catalog authoring remains V-owned."""
import copy
import hashlib

from .contracts import canonical
from .errors import APIError

GROUPS = {"checks": "check_id", "view_templates": "template_id", "question_templates": "template_id",
          "explanation_templates": "template_id", "diagrams": "diagram_id"}


def resource_key(group, record):
    return f"{group}:{record[GROUPS[group]]}:{record['version']}"


def source_ref(record):
    return {key: record["source"][key] for key in ("source_id", "version", "locator")}


def validate_catalog(contracts, catalog, sources):
    contracts.validate("catalog.schema.json", catalog, internal=True)
    indexes = {}
    for group, id_key in GROUPS.items():
        index = {(r[id_key], r["version"]): r for r in catalog[group]}
        if len(index) != len(catalog[group]):
            raise ValueError("Duplicate catalog identity/version")
        indexes[group] = index
        for record in index.values():
            src = record["source"]
            raw = sources.get((src["source_id"], src["version"]))
            if raw is None or hashlib.sha256(raw).hexdigest() != src["sha256"]:
                raise ValueError("Source bytes/hash mismatch")
            if not src["rights_record_id"].startswith("synthetic-") or not record["approval_record_id"].startswith("synthetic-"):
                raise ValueError("This demo accepts synthetic approval and rights records only")
    checks = indexes["checks"]
    scope = lambda r: (r["model_id"], r["configuration_id"], r["workflow_id"])
    preflights = {}
    for key, check in checks.items():
        if check["kind"] == "PREFLIGHT":
            if scope(check) in preflights or check["prerequisites"]:
                raise ValueError("Exactly one root preflight per supported scope is required")
            if set(check["options"]) != {"CLEAR", "HAZARD", "UNSURE"} or set(check["stop_values"]) != {"HAZARD", "UNSURE"}:
                raise ValueError("Invalid preflight stop values")
            preflights[scope(check)] = key
        if not set(check["stop_values"]) <= set(check["options"]):
            raise ValueError("Invalid stop values")
    visiting, done = set(), {}

    def visit(key):
        if key in visiting:
            raise ValueError("Cyclic prerequisites")
        if key in done:
            return done[key]
        visiting.add(key)
        check = checks[key]
        reachable_clear = set()
        for pre in check["prerequisites"]:
            target_key = (pre["check_id"], pre["check_version"])
            target = checks.get(target_key)
            if not target or scope(target) != scope(check) or target["observation_code"] != pre["observation_code"]:
                raise ValueError("Missing or mismatched prerequisite")
            if not set(pre["allowed_values"]) <= set(target["options"]):
                raise ValueError("Invalid prerequisite values")
            reachable_clear |= visit(target_key)
            if target["kind"] == "PREFLIGHT" and pre["allowed_values"] == ["CLEAR"]:
                reachable_clear.add(target_key)
        visiting.remove(key)
        done[key] = reachable_clear
        return reachable_clear

    for key, check in checks.items():
        reachable = visit(key)
        if scope(check) not in preflights:
            raise ValueError("Scope missing preflight")
        if check["kind"] != "PREFLIGHT" and preflights[scope(check)] not in reachable:
            raise ValueError("Every check must depend transitively on preflight CLEAR")
    for diagram in catalog["diagrams"]:
        nodes = {n["node_id"] for n in diagram["nodes"]}
        edges = {e["edge_id"] for e in diagram["edges"]}
        if len(nodes) != len(diagram["nodes"]) or len(edges) != len(diagram["edges"]):
            raise ValueError("Duplicate graph identity")
        if any(e["from_node_id"] not in nodes or e["to_node_id"] not in nodes for e in diagram["edges"]):
            raise ValueError("Dangling graph edge")
    all_scopes = set(preflights)
    for group in ("view_templates", "question_templates", "explanation_templates", "diagrams"):
        for record in catalog[group]:
            if scope(record) not in all_scopes:
                raise ValueError("Unsupported template/diagram scope")
    for template in catalog["view_templates"]:
        target = template["target_node_id"]
        nodes = {n["node_id"] for d in catalog["diagrams"] if scope(d) == scope(template) for n in d["nodes"]}
        if target and target not in nodes:
            raise ValueError("Unknown camera target")
        if template["purpose"] == "IDENTITY" and target:
            raise ValueError("Identity framing must not target machine internals")
    for template in catalog["explanation_templates"]:
        rule = template["claim_rule"]
        check = checks.get((rule["check_id"], rule["check_version"]))
        if not check or scope(check) != scope(template) or rule["observation_code"] != check["observation_code"]:
            raise ValueError("Invalid claim rule")
        if not set(rule["allowed_values"]) <= set(check["options"]):
            raise ValueError("Invalid claim values")
        if template["diagram_id"]:
            diagram = indexes["diagrams"].get((template["diagram_id"], template["diagram_version"]))
            if not diagram or scope(diagram) != scope(template):
                raise ValueError("Unknown/inapplicable diagram")
            if not set(template["allowed_highlight_node_ids"]) <= {n["node_id"] for n in diagram["nodes"]}:
                raise ValueError("Unknown highlight node")


def publish(store, contracts, catalog, sources):
    validate_catalog(contracts, catalog, sources)
    with store.transaction() as db:
        version, payload = catalog["catalog_version"], canonical(catalog)
        old = db.execute("SELECT payload FROM catalogs WHERE version=?", (version,)).fetchone()
        if old and old[0] != payload:
            raise ValueError("Approved catalog versions are immutable")
        if not old:
            db.execute("INSERT INTO catalogs VALUES (?,?,0)", (version, payload))
        db.execute("UPDATE catalogs SET active=0")
        db.execute("UPDATE catalogs SET active=1 WHERE version=?", (version,))
        for group in GROUPS:
            for record in catalog[group]:
                identity = resource_key(group, record)
                old_record = db.execute("SELECT payload FROM catalog_records WHERE key=?", (identity,)).fetchone()
                if old_record and old_record[0] != canonical(record):
                    raise ValueError("Approved record versions are immutable across catalogs")
                db.execute("INSERT OR IGNORE INTO catalog_records VALUES (?,?)", (identity, canonical(record)))
                source_key = f"source:{record['source']['source_id']}:{record['source']['version']}"
                old_source = db.execute("SELECT sha256 FROM source_hashes WHERE key=?", (source_key,)).fetchone()
                if old_source and old_source[0] != record["source"]["sha256"]:
                    raise ValueError("Approved source versions are immutable")
                db.execute("INSERT OR IGNORE INTO source_hashes VALUES (?,?)", (source_key, record["source"]["sha256"]))
                for key in (resource_key(group, record), f"source:{record['source']['source_id']}:{record['source']['version']}"):
                    # An existing withdrawal can never be undone by republishing a catalog.
                    db.execute("INSERT OR IGNORE INTO resources VALUES (?,'Approved')", (key,))
        store.authority(db, "CATALOG_PUBLISHED", {"catalog_version": version})


def authorize(db, principal, workflow):
    resources = ["workflow:" + workflow]
    for subject in (principal["actor"], principal["agent"]):
        for resource in resources:
            row = db.execute("SELECT allowed FROM grants WHERE tenant=? AND subject=? AND resource=?",
                             (principal["tenant"], subject, resource)).fetchone()
            if not row or row[0] != 1:
                raise APIError(403, "UNAUTHORIZED", "Work is not authorized.")


def allowed(db, principal, group, record):
    keys = (resource_key(group, record), f"source:{record['source']['source_id']}:{record['source']['version']}")
    if any(not (r := db.execute("SELECT state FROM resources WHERE key=?", (k,)).fetchone()) or r[0] != "Approved" for k in keys):
        return False
    for subject in (principal["actor"], principal["agent"]):
        row = db.execute("SELECT allowed FROM grants WHERE tenant=? AND subject=? AND resource=?",
                         (principal["tenant"], subject, "source:" + record["source"]["source_id"])).fetchone()
        if not row or row[0] != 1:
            return False
    return True


def scoped(db, principal, session, catalog):
    result = {"catalog_version": catalog["catalog_version"]}
    identity = session["identity"]
    for group in GROUPS:
        result[group] = [copy.deepcopy(r) for r in catalog[group]
                         if r["workflow_id"] == session["workflow_id"]
                         and (not identity or all(r[k] == identity[k] for k in ("model_id", "configuration_id")))
                         and allowed(db, principal, group, r)]
    return result
