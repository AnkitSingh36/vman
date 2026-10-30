"""The M-Files bridge: the only way the AI brain can reach vault knowledge.

Rules the bridge enforces (the AI cannot change them):
1. Identity comes from the session, never from the model. Every read is checked
   against BOTH the human user and the agent identity.
2. Only approved (released) versions are used. Newer drafts are reported but ignored.
3. Exact matches only. No guessing: unknown or ambiguous items are refused, with
   close matches offered for a person to confirm.
4. Procedure steps are returned verbatim, with their source.
5. Writing evidence is not an AI tool. The app calls it only after a person confirms.
"""
from __future__ import annotations

import difflib
from datetime import date
from typing import Any, Callable

from ..mockvault.vault import MockVault, ObjectVersion

BLOCKING_SEVERITIES = {"major", "critical"}


def _norm(s: str | None) -> str:
    return "".join((s or "").upper().split())


def _d(s: str | None) -> date | None:
    return date.fromisoformat(s) if s else None


class Bridge:
    def __init__(self, vault: MockVault, user: str, agent: str, today: date | None = None):
        self.vault = vault
        self.user = user
        self.agent = agent
        self.today = today or date.today()

    # ------------------------------------------------------------------ helpers
    def _visible(self, ov: ObjectVersion) -> bool:
        return (self.vault.can_access(self.user, ov.object_id, ov.version)
                and self.vault.can_access(self.agent, ov.object_id, ov.version))

    def _log(self, action: str, details: dict[str, Any], object_id: int | None = None, version: int | None = None):
        self.vault.log(self.agent, action, on_behalf_of=self.user, object_id=object_id, version=version,
                       details=details)

    def _latest_visible(self, object_type: str) -> list[ObjectVersion]:
        out = []
        for oid in self.vault.objects_of_type(object_type):
            ov = self.vault.latest_version(oid)
            if self._visible(ov):
                out.append(ov)
        return out

    def _released_version(self, object_id: int) -> ObjectVersion | None:
        """Newest version whose workflow state is a released/approved state."""
        for ov in reversed(self.vault.versions(object_id)):
            if ov.state_is_released:
                return ov
        return None

    def _parse_ref(self, item_ref: str) -> tuple[str, int]:
        try:
            otype, oid = item_ref.split(":", 1)
            return otype.strip(), int(oid)
        except ValueError as exc:
            raise ValueError(f"Bad item_ref '{item_ref}'. Expected '<ObjectType>:<id>'.") from exc

    def _get_item(self, item_ref: str) -> ObjectVersion | None:
        otype, oid = self._parse_ref(item_ref)
        try:
            ov = self.vault.latest_version(oid)
        except KeyError:
            return None
        if ov.object_type != otype or not self._visible(ov):
            return None
        return ov

    @staticmethod
    def _source(ov: ObjectVersion) -> dict[str, Any]:
        p = ov.properties
        return {
            "ref": ov.ref, "title": ov.title, "revision": p.get("Revision"), "version": ov.version,
            "state": ov.state, "approved_by": p.get("Approved by"), "approved_date": p.get("Approved date"),
        }

    @staticmethod
    def _summary(ov: ObjectVersion) -> dict[str, Any]:
        keep = ("Serial number", "Model", "Site", "Part number", "Revision", "Batch number",
                "Revision on label", "Container ID", "Build order number", "Variant", "Planned build date",
                "Asset tag")
        return {
            "item_ref": f"{ov.object_type}:{ov.object_id}", "object_type": ov.object_type,
            "class": ov.class_name, "title": ov.title,
            "properties": {k: v for k, v in ov.properties.items() if k in keep},
        }

    # ------------------------------------------------------------------ tools
    def identify_item(self, identifier: str) -> dict[str, Any]:
        """Exact lookup by serial number, batch number, container ID, part number or build order."""
        key = _norm(identifier)
        fields = {"Equipment": ["Serial number", "Asset tag"], "Batch": ["Batch number", "Container ID"],
                  "Part": ["Part number"], "Build order": ["Build order number"]}
        matches, known = [], []
        for otype, props in fields.items():
            for ov in self._latest_visible(otype):
                for prop in props:
                    val = ov.properties.get(prop)
                    if val:
                        known.append(str(val))
                        if _norm(str(val)) == key:
                            matches.append(ov)
        self._log("identify_item", {"identifier": identifier, "matches": len(matches)})
        if len(matches) == 1:
            return {"status": "ok", "item": self._summary(matches[0])}
        if len(matches) > 1:
            return {"status": "ambiguous", "message": "More than one item matches. Ask a person to choose.",
                    "candidates": [self._summary(m) for m in matches]}
        close = difflib.get_close_matches(identifier.strip().upper(), [k.upper() for k in known], n=3, cutoff=0.8)
        return {"status": "not_found",
                "message": "No exact match in the vault. Do not guess. Ask a person to confirm the identifier.",
                "close_matches_for_human_review": close}

    def get_approved_job(self, item_ref: str, task: str) -> dict[str, Any]:
        """Return the approved procedure for this exact equipment and task, verbatim, with its source."""
        item = self._get_item(item_ref)
        if item is None:
            return {"status": "not_found", "message": f"{item_ref} is not visible or does not exist."}
        if item.object_type != "Equipment":
            return {"status": "refused",
                    "message": "Procedures apply to equipment. For parts and batches use check_part_for_build."}
        model = item.properties.get("Model")
        seq = item.properties.get("Serial sequence")
        hits, notes = [], []
        for oid in self.vault.objects_of_class("Maintenance procedure"):
            rel = self._released_version(oid)
            if rel is None or not self._visible(rel):
                continue
            p = rel.properties
            if p.get("Applies to model") != model:
                continue
            if not (p.get("Serial from", 0) <= (seq or -1) <= p.get("Serial to", -1)):
                continue
            if _norm(task) not in _norm(p.get("Task")) and _norm(p.get("Task")) not in _norm(task):
                continue
            hits.append(rel)
            latest = self.vault.latest_version(oid)
            if latest.version > rel.version and not latest.state_is_released:
                notes.append(f"A newer revision {latest.properties.get('Revision')} of '{latest.title}' is "
                             f"'{latest.state}' and was NOT used.")
        self._log("get_approved_job", {"item_ref": item_ref, "task": task, "hits": [h.ref for h in hits]},
                  object_id=item.object_id, version=item.version)
        if not hits:
            return {"status": "no_approved_procedure",
                    "message": "No approved procedure covers this item and task. Stop and ask a person."}
        if len(hits) > 1:
            return {"status": "ambiguous", "message": "More than one approved procedure applies. Ask a person.",
                    "sources": [self._source(h) for h in hits]}
        doc = hits[0]
        return {"status": "ok", "item": self._summary(item), "task": doc.properties.get("Task"),
                "steps": [line for line in (doc.content or "").splitlines() if line.strip()],
                "source": self._source(doc), "notes": notes,
                "instruction": "Show these steps exactly as written. Do not reword, merge or add steps."}

    def check_blockers(self, item_ref: str) -> dict[str, Any]:
        """Open deviations, expired or missing certificates, and mandatory bulletins for an item."""
        item = self._get_item(item_ref)
        if item is None:
            return {"status": "not_found", "message": f"{item_ref} is not visible or does not exist."}
        blockers, warnings, required_first = [], [], []
        related_keys = {"Equipment": "Related equipment", "Batch": "Related batch", "Part": "Related part"}
        ids_to_match = {item.object_type: item.object_id}
        part = None
        if item.object_type == "Batch" and item.properties.get("Part"):
            part = self.vault.latest_version(item.properties["Part"])
            ids_to_match["Part"] = part.object_id

        # Open deviations
        for dev in self._latest_visible("Deviation"):
            if not dev.state_is_open:
                continue
            for otype, oid in ids_to_match.items():
                if oid in (dev.properties.get(related_keys[otype]) or []):
                    entry = {"ref": dev.ref, "title": dev.title, "state": dev.state,
                             "severity": dev.properties.get("Severity")}
                    if _norm(dev.properties.get("Severity")).lower() in BLOCKING_SEVERITIES:
                        blockers.append({"type": "open_deviation", **entry})
                    else:
                        warnings.append({"type": "open_deviation", **entry})
                    break

        # Certificates
        certs = [c for c in self._latest_visible("Certificate")
                 if any(oid in (c.properties.get(related_keys[t]) or []) for t, oid in ids_to_match.items()
                        if t in ("Equipment", "Batch"))]
        for c in certs:
            valid_until = _d(c.properties.get("Valid until"))
            if valid_until and valid_until < self.today:
                blockers.append({"type": "expired_certificate", "ref": c.ref, "title": c.title,
                                 "valid_until": c.properties.get("Valid until")})
        if item.object_type == "Batch" and part is not None and part.properties.get("Requires certificate"):
            if not certs:
                blockers.append({"type": "missing_certificate",
                                 "message": f"{part.title} requires a certificate and none is linked to this batch."})

        # Mandatory service bulletins (equipment only)
        if item.object_type == "Equipment":
            seq = item.properties.get("Serial sequence") or -1
            for oid in self.vault.objects_of_class("Service bulletin"):
                rel = self._released_version(oid)
                if rel is None or not self._visible(rel):
                    continue
                p = rel.properties
                if (p.get("Mandatory") and p.get("Applies to model") == item.properties.get("Model")
                        and p.get("Serial from", 0) <= seq <= p.get("Serial to", -1)):
                    required_first.append({"type": "mandatory_service_bulletin", "source": self._source(rel),
                                           "steps": [s for s in (rel.content or "").splitlines() if s.strip()]})

        status = "blocked" if blockers else ("warnings" if (warnings or required_first) else "clear")
        self._log("check_blockers", {"item_ref": item_ref, "status": status, "blockers": len(blockers)},
                  object_id=item.object_id, version=item.version)
        return {"status": status, "item": self._summary(item), "blockers": blockers, "warnings": warnings,
                "required_first": required_first}

    def check_part_for_build(self, item_ref: str, build_order: str, label_revision: str | None = None) -> dict[str, Any]:
        """Is this batch the right part revision for this build, and is it free of holds?"""
        item = self._get_item(item_ref)
        if item is None or item.object_type != "Batch":
            return {"status": "refused", "message": "Give a Batch item_ref (identify the label or container first)."}
        bo = next((b for b in self._latest_visible("Build order")
                   if _norm(b.properties.get("Build order number")) == _norm(build_order)), None)
        if bo is None:
            return {"status": "not_found", "message": f"Build order {build_order} not found. Ask a person."}
        build_date = _d(bo.properties.get("Planned build date"))
        part_id = item.properties.get("Part")
        in_force = None
        for pv in reversed(self.vault.versions(part_id)):
            if not pv.state_is_released or not self._visible(pv):
                continue
            start, end = _d(pv.properties.get("Effective from")), _d(pv.properties.get("Effective to"))
            if (start is None or start <= build_date) and (end is None or build_date <= end):
                in_force = pv
                break
        if in_force is None:
            return {"status": "no_revision_in_force", "message": "No released revision covers this build date."}

        vault_label_rev = item.properties.get("Revision on label")
        reasons, notes = [], []
        if label_revision and _norm(label_revision) != _norm(vault_label_rev):
            notes.append(f"Camera read revision '{label_revision}' but the batch record says '{vault_label_rev}'. "
                         "Using the camera reading; a person should check the label.")
        seen_rev = label_revision or vault_label_rev
        revision_ok = _norm(seen_rev) == _norm(in_force.properties.get("Revision"))
        if not revision_ok:
            reasons.append(f"Wrong revision for {bo.properties.get('Build order number')}: batch is Rev {seen_rev}, "
                           f"Rev {in_force.properties.get('Revision')} is in force from "
                           f"{in_force.properties.get('Effective from')}.")
        blockers = self.check_blockers(item_ref)
        for b in blockers["blockers"]:
            reasons.append(f"{b['type'].replace('_', ' ')}: {b.get('title') or b.get('message')}")
        decision = "cleared" if not reasons else "hold"
        self._log("check_part_for_build", {"item_ref": item_ref, "build_order": build_order, "decision": decision},
                  object_id=item.object_id, version=item.version)
        return {"status": "ok", "decision": decision, "reasons": reasons, "notes": notes,
                "item": self._summary(item), "build_order": self._summary(bo),
                "revision_in_force": {"revision": in_force.properties.get("Revision"),
                                      "source": self._source(in_force), "change_note": self._change_note(in_force)},
                "warnings": blockers["warnings"]}

    def _change_note(self, ov: ObjectVersion) -> str | None:
        row = self.vault.db.execute("SELECT comment FROM object_versions WHERE object_id=? AND version=?",
                                    (ov.object_id, ov.version)).fetchone()
        return row["comment"] if row else None


    # ------------------------------------------------------------------ drone inspection tools
    def _released_docs(self, class_name: str) -> list[tuple[ObjectVersion, list[str]]]:
        """Released, visible versions of a document class, with notes about newer unapproved drafts."""
        out = []
        for oid in self.vault.objects_of_class(class_name):
            rel = self._released_version(oid)
            if rel is None or not self._visible(rel):
                continue
            notes = []
            latest = self.vault.latest_version(oid)
            if latest.version > rel.version and not latest.state_is_released:
                notes.append(f"A newer revision {latest.properties.get('Revision')} of '{latest.title}' is "
                             f"'{latest.state}' and was NOT used.")
            out.append((rel, notes))
        return out

    def check_mission_readiness(self, site: str, drone_ref: str) -> dict[str, Any]:
        """Go/no-go before a drone inspection flight: plan, permit, drone, operator."""
        checks, notes = [], []

        def add(name: str, ok: bool, detail: str, source: dict[str, Any] | None = None):
            checks.append({"check": name, "ok": ok, "detail": detail, **({"source": source} if source else {})})

        plans = [(p, n) for p, n in self._released_docs("Inspection plan")
                 if _norm(p.properties.get("Applies to site")) == _norm(site)]
        plan = None
        if len(plans) == 1:
            plan, plan_notes = plans[0]
            notes += plan_notes
            add("approved_inspection_plan", True, f"{plan.title} Rev {plan.properties.get('Revision')}",
                self._source(plan))
        elif not plans:
            add("approved_inspection_plan", False, f"No approved inspection plan for site '{site}'.")
        else:
            add("approved_inspection_plan", False, "More than one approved plan for this site. Ask a person.")

        if plan is None or plan.properties.get("Requires permit"):
            valid, expired = [], []
            for pm in self._latest_visible("Permit"):
                if _norm(pm.properties.get("Applies to site")) != _norm(site) or not pm.state_is_released:
                    continue
                start, end = _d(pm.properties.get("Valid from")), _d(pm.properties.get("Valid until"))
                if (start is None or start <= self.today) and (end is None or self.today <= end):
                    valid.append(pm)
                else:
                    expired.append(pm)
            if valid:
                add("valid_work_permit", True, f"{valid[0].title}, valid until {valid[0].properties.get('Valid until')}")
            elif expired:
                add("valid_work_permit", False,
                    f"{expired[0].title} expired on {expired[0].properties.get('Valid until')}.")
            else:
                add("valid_work_permit", False, f"No issued work permit for site '{site}'.")

        drone = self._get_item(drone_ref)
        if drone is None or drone.class_name != "Inspection drone":
            add("drone_identified", False, f"{drone_ref} is not a known inspection drone.")
        else:
            add("drone_identified", True, drone.title)
            certs = [c for c in self._latest_visible("Certificate")
                     if drone.object_id in (c.properties.get("Related equipment") or [])]
            live = [c for c in certs if _d(c.properties.get("Valid until")) and _d(c.properties["Valid until"]) >= self.today]
            if live:
                add("drone_certificate", True, f"{live[0].title}, valid until {live[0].properties.get('Valid until')}")
            elif certs:
                add("drone_certificate", False, f"{certs[0].title} expired on {certs[0].properties.get('Valid until')}.")
            else:
                add("drone_certificate", False, "No airworthiness or maintenance certificate linked to the drone.")
            blockers = self.check_blockers(f"Equipment:{drone.object_id}")["blockers"]
            open_devs = [b for b in blockers if b["type"] == "open_deviation"]
            add("drone_open_deviations", not open_devs,
                "None" if not open_devs else "; ".join(b["title"] for b in open_devs))

        quals = [q for q in self._latest_visible("Qualification") if q.properties.get("Holder") == self.user]
        live_q = [q for q in quals if _d(q.properties.get("Valid until")) and _d(q.properties["Valid until"]) >= self.today]
        if live_q:
            add("operator_qualified", True, f"{self.user}: {live_q[0].properties.get('Qualification')}, "
                f"valid until {live_q[0].properties.get('Valid until')}")
        elif quals:
            add("operator_qualified", False, f"{self.user}: qualification expired on "
                f"{quals[0].properties.get('Valid until')}.")
        else:
            add("operator_qualified", False, f"{self.user} has no drone operator qualification on record.")

        decision = "go" if all(c["ok"] for c in checks) else "no_go"
        self._log("check_mission_readiness", {"site": site, "drone_ref": drone_ref, "decision": decision})
        return {"status": "ok", "decision": decision, "site": site, "operator": self.user, "checks": checks,
                "reasons": [c["detail"] for c in checks if not c["ok"]], "notes": notes,
                "plan_steps": [s for s in ((plan.content if plan else "") or "").splitlines() if s.strip()],
                "plan_source": self._source(plan) if plan else None}

    def _criteria(self, item: ObjectVersion) -> list[ObjectVersion]:
        return [d for d, _ in self._released_docs("Inspection criteria")
                if _norm(d.properties.get("Asset tag")) == _norm(item.properties.get("Asset tag"))]

    def get_inspection_criteria(self, item_ref: str) -> dict[str, Any]:
        """Approved inspection criteria (measurement points, limits, checklist) for an asset."""
        item = self._get_item(item_ref)
        if item is None:
            return {"status": "not_found", "message": f"{item_ref} is not visible or does not exist."}
        docs = self._criteria(item)
        self._log("get_inspection_criteria", {"item_ref": item_ref, "found": len(docs)},
                  object_id=item.object_id, version=item.version)
        if not docs:
            return {"status": "no_approved_criteria", "message": "No approved inspection criteria for this asset."}
        return {"status": "ok", "item": self._summary(item), "criteria": [{
            "measurement_point": d.properties.get("Measurement point"), "limit_min": d.properties.get("Limit min"),
            "limit_max": d.properties.get("Limit max"), "unit": d.properties.get("Unit"),
            "checklist": [s for s in (d.content or "").splitlines() if s.strip()], "source": self._source(d)}
            for d in docs]}

    def evaluate_reading(self, item_ref: str, measurement_point: str, value: float, unit: str) -> dict[str, Any]:
        """Compare a reading taken by the agent with the approved limits. The bridge decides, not the model."""
        item = self._get_item(item_ref)
        if item is None:
            return {"status": "not_found", "message": f"{item_ref} is not visible or does not exist."}
        doc = next((d for d in self._criteria(item)
                    if _norm(d.properties.get("Measurement point")) == _norm(measurement_point)), None)
        if doc is None:
            return {"status": "no_approved_criteria",
                    "message": f"No approved limits for {measurement_point} on {item.title}. Ask a person."}
        if _norm(unit) != _norm(doc.properties.get("Unit")):
            return {"status": "refused", "message": f"Unit '{unit}' does not match approved unit "
                    f"'{doc.properties.get('Unit')}'. Ask a person to read the gauge."}
        lo, hi = doc.properties.get("Limit min"), doc.properties.get("Limit max")
        verdict = "within_limits" if lo <= float(value) <= hi else "out_of_limits"
        self._log("evaluate_reading", {"item_ref": item_ref, "point": measurement_point, "value": value,
                                       "verdict": verdict}, object_id=item.object_id, version=item.version)
        return {"status": verdict, "item": self._summary(item), "measurement_point": measurement_point,
                "value": float(value), "unit": unit, "limit_min": lo, "limit_max": hi, "source": self._source(doc)}

    def draft_deviation(self, item_ref: str, title: str, severity: str, note: str | None = None) -> dict[str, Any]:
        """App-only: raise a nonconformance after a person approves. Never an AI tool."""
        item = self._get_item(item_ref)
        if item is None:
            return {"status": "not_found", "message": f"{item_ref} is not visible or does not exist."}
        oid = self.vault.create_object(104, "Nonconformance", title, {
            "Related equipment": [item.object_id], "Severity": severity, "Note": note}, state="Open",
            created_by=self.agent)
        self.vault.commit()
        self._log("draft_deviation", {"item_ref": item_ref, "title": title, "severity": severity},
                  object_id=oid, version=1)
        return {"status": "ok", "deviation_ref": f"Deviation:{oid}", "mock_write": True}

    # ------------------------------------------------------------------ app-only write
    def record_evidence(self, item_ref: str, summary: str, result: str, step: int | None = None,
                        photo_ref: str | None = None, note: str | None = None,
                        source_document: str | None = None) -> dict[str, Any]:
        """Create a Field evidence object. Called by the app after a person confirms, never by the model.

        In this POC it writes to the local mock vault only. The real M-Files MCP beta is read-only.
        """
        nacl = self.vault.db.execute("SELECT nacl_id FROM classes WHERE name = 'Field evidence'").fetchone()["nacl_id"]
        for who in (self.user, self.agent):
            if not self.vault._nacl_grants(nacl, self.vault._user_id(who), need_edit=True):
                return {"status": "denied", "message": f"{who} may not create field evidence."}
        oid = self.vault.create_object(107, "Field evidence", summary, {
            "Evidence for": item_ref, "Step": step, "Result": result, "Photo reference": photo_ref,
            "Note": note, "Recorded by agent": self.agent, "On behalf of": self.user,
            "Source document": source_document}, state="Submitted", created_by=self.agent)
        self.vault.commit()
        self._log("record_evidence", {"item_ref": item_ref, "result": result, "step": step}, object_id=oid, version=1)
        return {"status": "ok", "evidence_ref": f"Evidence:{oid}", "mock_write": True}


# ---------------------------------------------------------------------- AI tool declarations
TOOL_DECLARATIONS: list[dict[str, Any]] = [
    {
        "name": "identify_item",
        "description": ("Look up a physical item in the company vault by the exact identifier read from the image: "
                        "equipment serial number, batch number, container ID, part number or build order. "
                        "Exact match only. Returns item_ref for later calls."),
        "parameters_json_schema": {
            "type": "object",
            "properties": {"identifier": {"type": "string", "description": "Identifier exactly as read from the label."}},
            "required": ["identifier"],
        },
    },
    {
        "name": "get_approved_job",
        "description": ("Get the approved procedure for one equipment item and task. Returns steps verbatim with the "
                        "source document, revision and approval. Refuses if none or several apply."),
        "parameters_json_schema": {
            "type": "object",
            "properties": {
                "item_ref": {"type": "string", "description": "item_ref from identify_item, e.g. 'Equipment:1'."},
                "task": {"type": "string", "description": "The job, e.g. 'Restart after unplanned stop'."},
            },
            "required": ["item_ref", "task"],
        },
    },
    {
        "name": "check_blockers",
        "description": ("Check an item for open deviations, expired or missing certificates and mandatory service "
                        "bulletins. Call this before giving any instructions."),
        "parameters_json_schema": {
            "type": "object",
            "properties": {"item_ref": {"type": "string"}},
            "required": ["item_ref"],
        },
    },
    {
        "name": "check_part_for_build",
        "description": ("For a batch of parts, check the revision in force for a build order and any holds. "
                        "Returns decision 'cleared' or 'hold' with reasons."),
        "parameters_json_schema": {
            "type": "object",
            "properties": {
                "item_ref": {"type": "string", "description": "Batch item_ref from identify_item."},
                "build_order": {"type": "string", "description": "Build order number, e.g. 'BO-7781'."},
                "label_revision": {"type": "string", "description": "Revision letter read from the label, if visible."},
            },
            "required": ["item_ref", "build_order"],
        },
    },
    {
        "name": "check_mission_readiness",
        "description": ("Pre-flight go/no-go for a drone inspection: approved inspection plan for the site, valid "
                        "work permit, drone certificate and open deviations, operator qualification. "
                        "The operator is the signed-in user; you cannot change it."),
        "parameters_json_schema": {
            "type": "object",
            "properties": {
                "site": {"type": "string", "description": "Site name, e.g. 'Tank farm North'."},
                "drone_ref": {"type": "string", "description": "Drone item_ref from identify_item."},
            },
            "required": ["site", "drone_ref"],
        },
    },
    {
        "name": "get_inspection_criteria",
        "description": "Approved inspection criteria for an asset: measurement points, limits, units and checklist.",
        "parameters_json_schema": {
            "type": "object", "properties": {"item_ref": {"type": "string"}}, "required": ["item_ref"],
        },
    },
    {
        "name": "evaluate_reading",
        "description": ("Compare a gauge reading you took from the image with the approved limits. Pass the value "
                        "exactly as read. If you cannot read the gauge, do not call this; say so."),
        "parameters_json_schema": {
            "type": "object",
            "properties": {
                "item_ref": {"type": "string"},
                "measurement_point": {"type": "string", "description": "Gauge tag, e.g. 'PI-102'."},
                "value": {"type": "number"},
                "unit": {"type": "string", "description": "Unit shown on the gauge, e.g. 'bar'."},
            },
            "required": ["item_ref", "measurement_point", "value", "unit"],
        },
    },
]


def dispatch(bridge: Bridge, name: str, args: dict[str, Any]) -> dict[str, Any]:
    """Run an AI tool call. Only the declared read tools are allowed."""
    tools: dict[str, Callable[..., dict[str, Any]]] = {
        "identify_item": bridge.identify_item,
        "get_approved_job": bridge.get_approved_job,
        "check_blockers": bridge.check_blockers,
        "check_part_for_build": bridge.check_part_for_build,
        "check_mission_readiness": bridge.check_mission_readiness,
        "get_inspection_criteria": bridge.get_inspection_criteria,
        "evaluate_reading": bridge.evaluate_reading,
    }
    if name not in tools:
        return {"status": "error", "message": f"Tool '{name}' is not available to the AI."}
    try:
        return tools[name](**args)
    except (TypeError, ValueError) as exc:
        return {"status": "error", "message": str(exc)}
