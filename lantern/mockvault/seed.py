"""Seed the mock vault with an M-Files-like structure and fictional sample data.

All companies, products, people and numbers here are invented for the POC.
"""
from __future__ import annotations

from .vault import MockVault

# ---- object types (0 = Document, as in M-Files)
OT_DOCUMENT, OT_EQUIPMENT, OT_PART, OT_BATCH, OT_DEVIATION, OT_CERTIFICATE, OT_BUILD_ORDER, OT_EVIDENCE = (
    0, 101, 102, 103, 104, 105, 106, 107)
OT_PERMIT, OT_QUALIFICATION = 108, 109

# ---- workflows
WF_DOC, WF_DEVIATION, WF_EVIDENCE, WF_PART, WF_PERMIT = 201, 202, 203, 204, 205

# ---- groups and named ACLs
G_ALL, G_SERVICE, G_LOGISTICS, G_QUALITY, G_ENGINEERING, G_AGENTS, G_DRONE = 1, 2, 3, 4, 5, 6, 7
NACL_ALL_INTERNAL, NACL_SERVICE_DOCS, NACL_SUPPLY_CHAIN, NACL_ENGINEERING_ONLY, NACL_EVIDENCE, NACL_INSPECTION = (
    300, 301, 302, 303, 304, 305)

DOC_STEPS_REV_A = """1. Lock out the start circuit and tag it (LOTO-ME450-01).
2. Read the fault code on the control panel and record it.
3. Check the fuel filter. Replace the element if it is visibly contaminated.
4. Remove the lockout and perform a supervised restart.
5. Run at idle for 5 minutes and confirm the oil pressure warning is off."""

DOC_STEPS_REV_B = """1. Lock out the start circuit and tag it (LOTO-ME450-02).
2. Read the fault code on the control panel and record it.
3. Check lube oil pressure sensor connector X14 and reseat it if loose.
4. Check fuel filter differential pressure. Replace the element if above 1.0 bar.
5. Remove the lockout and perform a supervised restart.
6. Run at idle for 10 minutes. Confirm oil pressure is between 3.0 and 5.0 bar."""

DOC_STEPS_REV_C = """1. Lock out the start circuit and tag it (LOTO-ME450-03).
2. Read the fault code on the control panel and record it.
3. Check lube oil pressure sensor connector X14 and reseat it if loose.
4. Check fuel filter differential pressure. Replace the element if above 0.8 bar.
5. Remove the lockout and perform a supervised restart.
6. Run at idle for 10 minutes. Confirm oil pressure is between 3.5 and 5.0 bar."""

DOC_STEPS_REV_D_DRAFT = """1. Lock out the start circuit and tag it (LOTO-ME450-04).
2. Read the fault code on the control panel and record it.
3. Check lube oil pressure sensor connector X14 and reseat it if loose.
4. Check fuel filter differential pressure. Replace the element if above 0.6 bar.
5. Remove the lockout and perform a supervised restart.
6. Run at idle for 15 minutes. Confirm oil pressure is between 3.5 and 5.0 bar."""

SB_STEPS = """1. Before any restart, inspect fuel injector seals on cylinders 1 to 6 for weeping.
2. Replace any seal showing residue using seal kit PN-77102.
3. Record the injector serial numbers inspected."""


def seed(vault: MockVault) -> MockVault:
    v = vault

    # ------------------------------------------------------------- structure
    for oid, name in [(OT_DOCUMENT, "Document"), (OT_EQUIPMENT, "Equipment"), (OT_PART, "Part"),
                      (OT_BATCH, "Batch"), (OT_DEVIATION, "Deviation"), (OT_CERTIFICATE, "Certificate"),
                      (OT_BUILD_ORDER, "Build order"), (OT_EVIDENCE, "Evidence"), (OT_PERMIT, "Permit"),
                      (OT_QUALIFICATION, "Qualification")]:
        v.add_object_type(oid, name)

    # (state_id, name, is_released, is_open)
    v.add_workflow(WF_DOC, "Document control", [
        (2011, "Draft", False, False), (2012, "In review", False, False),
        (2013, "Approved", True, False), (2014, "Obsolete", False, False)])
    v.add_workflow(WF_DEVIATION, "Deviation handling", [
        (2021, "Open", False, True), (2022, "Under investigation", False, True), (2023, "Closed", False, False)])
    v.add_workflow(WF_EVIDENCE, "Evidence review", [
        (2031, "Submitted", False, True), (2032, "Reviewed", True, False)])
    v.add_workflow(WF_PART, "Part release", [
        (2041, "Draft", False, False), (2042, "Released", True, False), (2043, "Superseded", False, False)])
    v.add_workflow(WF_PERMIT, "Work permit", [
        (2051, "Requested", False, False), (2052, "Issued", True, False), (2053, "Closed", False, False)])

    for gid, name in [(G_ALL, "All internal users"), (G_SERVICE, "Service technicians"),
                      (G_LOGISTICS, "Logistics operators"), (G_QUALITY, "Quality"),
                      (G_ENGINEERING, "Engineering"), (G_AGENTS, "Physical agents"), (G_DRONE, "Drone operators")]:
        v.add_group(gid, name)

    v.add_user(11, "anna.tech", "Anna (service technician)", [G_ALL, G_SERVICE])
    v.add_user(12, "ravi.logistics", "Ravi (logistics operator)", [G_ALL, G_LOGISTICS])
    v.add_user(13, "qa.lead", "Quality lead", [G_ALL, G_QUALITY])
    v.add_user(14, "eero.engineer", "Eero (engineer)", [G_ALL, G_ENGINEERING])
    v.add_user(15, "agent.er2-cell-1", "Physical agent ER2 cell 1", [G_ALL, G_AGENTS])
    v.add_user(16, "mikko.pilot", "Mikko (drone operator)", [G_ALL, G_DRONE])
    v.add_user(17, "sara.pilot", "Sara (drone operator)", [G_ALL, G_DRONE])

    # (principal_type, principal_id, can_read, can_edit)
    v.add_nacl(NACL_ALL_INTERNAL, "Full control for all internal users", [("group", G_ALL, True, True)])
    v.add_nacl(NACL_SERVICE_DOCS, "Service documentation", [
        ("group", G_SERVICE, True, False), ("group", G_QUALITY, True, True),
        ("group", G_ENGINEERING, True, True), ("group", G_AGENTS, True, False)])
    v.add_nacl(NACL_SUPPLY_CHAIN, "Supply chain records", [
        ("group", G_LOGISTICS, True, False), ("group", G_QUALITY, True, True),
        ("group", G_SERVICE, True, False), ("group", G_AGENTS, True, False), ("group", G_DRONE, True, False)])
    v.add_nacl(NACL_ENGINEERING_ONLY, "Engineering only", [
        ("group", G_ENGINEERING, True, True), ("group", G_QUALITY, True, False)])
    v.add_nacl(NACL_EVIDENCE, "Field evidence", [
        ("group", G_ALL, True, False), ("group", G_SERVICE, True, True),
        ("group", G_LOGISTICS, True, True), ("group", G_AGENTS, True, True), ("group", G_QUALITY, True, True),
        ("group", G_DRONE, True, True)])
    v.add_nacl(NACL_INSPECTION, "Inspection operations", [
        ("group", G_DRONE, True, False), ("group", G_SERVICE, True, False), ("group", G_QUALITY, True, True),
        ("group", G_ENGINEERING, True, False), ("group", G_AGENTS, True, False)])

    # classes: (id, name, object type, workflow, automatic ACL component)
    for cid, name, ot, wf, nacl in [
        (1, "Maintenance procedure", OT_DOCUMENT, WF_DOC, NACL_SERVICE_DOCS),
        (2, "Service bulletin", OT_DOCUMENT, WF_DOC, NACL_SERVICE_DOCS),
        (3, "Engineering analysis", OT_DOCUMENT, WF_DOC, NACL_ENGINEERING_ONLY),
        (10, "Engine", OT_EQUIPMENT, None, NACL_ALL_INTERNAL),
        (11, "Compressor", OT_EQUIPMENT, None, NACL_ALL_INTERNAL),
        (20, "Purchased part", OT_PART, WF_PART, NACL_SUPPLY_CHAIN),
        (30, "Incoming batch", OT_BATCH, None, NACL_SUPPLY_CHAIN),
        (40, "Nonconformance", OT_DEVIATION, WF_DEVIATION, NACL_ALL_INTERNAL),
        (50, "Certificate", OT_CERTIFICATE, None, NACL_SUPPLY_CHAIN),
        (60, "Build order", OT_BUILD_ORDER, None, NACL_SUPPLY_CHAIN),
        (70, "Field evidence", OT_EVIDENCE, WF_EVIDENCE, NACL_EVIDENCE),
        (4, "Inspection plan", OT_DOCUMENT, WF_DOC, NACL_INSPECTION),
        (5, "Inspection criteria", OT_DOCUMENT, WF_DOC, NACL_INSPECTION),
        (12, "Inspection drone", OT_EQUIPMENT, None, NACL_INSPECTION),
        (13, "Storage tank", OT_EQUIPMENT, None, NACL_ALL_INTERNAL),
        (80, "Work permit", OT_PERMIT, WF_PERMIT, NACL_INSPECTION),
        (90, "Operator qualification", OT_QUALIFICATION, None, NACL_INSPECTION),
    ]:
        v.add_class(cid, name, ot, wf, nacl)

    for pid, name, dt, lookup in [
        (1001, "Serial number", "text", None), (1002, "Model", "text", None), (1003, "Site", "text", None),
        (1005, "Serial sequence", "integer", None),
        (1010, "Applies to model", "text", None), (1011, "Serial from", "integer", None),
        (1012, "Serial to", "integer", None), (1013, "Task", "text", None), (1014, "Revision", "text", None),
        (1016, "Approved by", "text", None), (1017, "Approved date", "date", None), (1018, "Mandatory", "boolean", None),
        (1020, "Part number", "text", None), (1021, "Requires certificate", "boolean", None),
        (1022, "Effective from", "date", None), (1023, "Effective to", "date", None),
        (1030, "Batch number", "text", None), (1031, "Part", "lookup", OT_PART),
        (1032, "Revision on label", "text", None), (1033, "Container ID", "text", None),
        (1040, "Related equipment", "multilookup", OT_EQUIPMENT), (1041, "Related part", "multilookup", OT_PART),
        (1042, "Related batch", "multilookup", OT_BATCH), (1043, "Severity", "text", None),
        (1050, "Valid until", "date", None), (1051, "Certificate type", "text", None),
        (1060, "Build order number", "text", None), (1061, "Variant", "text", None),
        (1062, "Planned build date", "date", None),
        (1070, "Evidence for", "text", None), (1071, "Step", "integer", None), (1072, "Result", "text", None),
        (1073, "Photo reference", "text", None), (1074, "Note", "multiline", None),
        (1075, "Recorded by agent", "text", None), (1076, "On behalf of", "text", None),
        (1077, "Source document", "text", None),
        (1080, "Applies to site", "text", None), (1081, "Requires permit", "boolean", None),
        (1082, "Assets on route", "text", None), (1083, "Valid from", "date", None), (1084, "Holder", "text", None),
        (1085, "Qualification", "text", None), (1086, "Asset tag", "text", None),
        (1087, "Measurement point", "text", None), (1088, "Limit min", "number", None),
        (1089, "Limit max", "number", None), (1090, "Unit", "text", None), (1091, "Reading", "number", None),
    ]:
        v.add_property_def(pid, name, dt, lookup)

    # ------------------------------------------------------------- manufacturing data
    e1 = v.create_object(OT_EQUIPMENT, "Engine", "ME-450 engine, serial ME450-21877", {
        "Serial number": "ME450-21877", "Model": "ME-450", "Serial sequence": 21877, "Site": "Plant North, line 3"})
    e2 = v.create_object(OT_EQUIPMENT, "Engine", "ME-450 engine, serial ME450-19950", {
        "Serial number": "ME450-19950", "Model": "ME-450", "Serial sequence": 19950, "Site": "Plant North, line 1"})
    v.create_object(OT_EQUIPMENT, "Compressor", "MX-200 compressor, serial MX200-00412", {
        "Serial number": "MX200-00412", "Model": "MX-200", "Serial sequence": 412, "Site": "Plant North, utilities"})

    # Procedure for older serials: two approved revisions
    p1 = v.create_object(OT_DOCUMENT, "Maintenance procedure", "ME-450 restart after unplanned stop", {
        "Applies to model": "ME-450", "Serial from": 10000, "Serial to": 20999,
        "Task": "Restart after unplanned stop", "Revision": "A",
        "Approved by": "qa.lead", "Approved date": "2024-05-06"},
        state="Approved", content=DOC_STEPS_REV_A, created_by="eero.engineer", created_at="2024-05-02T09:00:00+00:00")
    v.new_version(p1, properties={"Revision": "B", "Approved date": "2025-02-11"}, state="Approved",
                  content=DOC_STEPS_REV_B, created_by="eero.engineer", created_at="2025-02-10T09:00:00+00:00",
                  comment="Revision B: added sensor connector check")

    # Procedure for newer serials: approved Rev C, plus a newer Rev D draft still in review
    p2 = v.create_object(OT_DOCUMENT, "Maintenance procedure", "ME-450 restart after unplanned stop (S/N 21000+)", {
        "Applies to model": "ME-450", "Serial from": 21000, "Serial to": 99999,
        "Task": "Restart after unplanned stop", "Revision": "C",
        "Approved by": "qa.lead", "Approved date": "2026-03-02"},
        state="Approved", content=DOC_STEPS_REV_C, created_by="eero.engineer", created_at="2026-03-01T09:00:00+00:00")
    v.new_version(p2, properties={"Revision": "D", "Approved by": None, "Approved date": None}, state="In review",
                  content=DOC_STEPS_REV_D_DRAFT, created_by="eero.engineer", created_at="2026-09-20T09:00:00+00:00",
                  comment="Revision D draft: tighter filter threshold, longer idle run")

    v.create_object(OT_DOCUMENT, "Service bulletin", "SB-2026-014 Inspect fuel injector seals before restart", {
        "Applies to model": "ME-450", "Serial from": 21500, "Serial to": 22500, "Task": "Any restart",
        "Revision": "1", "Mandatory": True, "Approved by": "qa.lead", "Approved date": "2026-08-15"},
        state="Approved", content=SB_STEPS, created_by="eero.engineer", created_at="2026-08-14T09:00:00+00:00")

    v.create_object(OT_DOCUMENT, "Engineering analysis", "Injector seal failure analysis ME-450 (internal)", {
        "Applies to model": "ME-450", "Related equipment": [e1], "Revision": "1"},
        state="Approved", content="Internal engineering analysis. Not for field use.", created_by="eero.engineer")

    v.create_object(OT_DEVIATION, "Nonconformance", "NC-2026-118 Coolant weeping at pump flange", {
        "Related equipment": [e1], "Severity": "Minor"}, state="Under investigation", created_by="qa.lead")

    v.create_object(OT_CERTIFICATE, "Certificate", "Pressure equipment inspection ME450-21877", {
        "Related equipment": [e1], "Certificate type": "Periodic inspection", "Valid until": "2027-03-31"})
    v.create_object(OT_CERTIFICATE, "Certificate", "Pressure equipment inspection ME450-19950", {
        "Related equipment": [e2], "Certificate type": "Periodic inspection", "Valid until": "2026-09-01"})

    # ------------------------------------------------------------- logistics data
    pt1 = v.create_object(OT_PART, "Purchased part", "PN-88213 Injector bracket", {
        "Part number": "PN-88213", "Revision": "A", "Requires certificate": False,
        "Effective from": "2025-01-01", "Effective to": "2026-09-30"},
        state="Released", created_by="eero.engineer", created_at="2025-01-01T08:00:00+00:00")
    v.new_version(pt1, properties={"Revision": "B", "Effective from": "2026-10-01", "Effective to": None},
                  state="Released", created_by="eero.engineer", created_at="2026-09-15T08:00:00+00:00",
                  comment="ECO-5521: bracket thickness increased; Rev B effective 2026-10-01")
    pt2 = v.create_object(OT_PART, "Purchased part", "PN-77102 Seal kit", {
        "Part number": "PN-77102", "Revision": "C", "Requires certificate": False, "Effective from": "2026-01-01"},
        state="Released")
    pt3 = v.create_object(OT_PART, "Purchased part", "PN-55410 Hose assembly", {
        "Part number": "PN-55410", "Revision": "A", "Requires certificate": True, "Effective from": "2025-06-01"},
        state="Released")
    pt4 = v.create_object(OT_PART, "Purchased part", "PN-60001 Clamp", {
        "Part number": "PN-60001", "Revision": "F", "Requires certificate": False, "Effective from": "2024-01-01"},
        state="Released")

    def batch(number, part, rev, container):
        return v.create_object(OT_BATCH, "Incoming batch", f"Batch {number}", {
            "Batch number": number, "Part": part, "Revision on label": rev, "Container ID": container})

    b1 = batch("B-2026-0915", pt1, "A", "CNT-48812")
    b2 = batch("B-2026-0912", pt2, "C", "CNT-48807")
    b3 = batch("B-2026-0930", pt3, "A", "CNT-48830")
    batch("B-2026-1002", pt4, "F", "CNT-48841")
    batch("B-2026-1003", pt1, "B", "CNT-48850")

    v.create_object(OT_DEVIATION, "Nonconformance", "NC-2026-121 Seal kit hardness out of specification", {
        "Related part": [pt2], "Related batch": [b2], "Severity": "Major"}, state="Open", created_by="qa.lead")
    v.create_object(OT_CERTIFICATE, "Certificate", "Certificate of conformity B-2026-0930", {
        "Related batch": [b3], "Related part": [pt3], "Certificate type": "Certificate of conformity",
        "Valid until": "2026-09-30"})
    # b1 (rev A) needs no certificate; its problem is the revision for the build.
    _ = b1

    v.create_object(OT_BUILD_ORDER, "Build order", "BO-7781 ME-450 Marine", {
        "Build order number": "BO-7781", "Variant": "ME-450 Marine", "Planned build date": "2026-10-15"})

    seed_drone_inspection(v)
    v.commit()
    return v


def seed_drone_inspection(v: MockVault) -> None:
    """Drone inspection round on a tank farm: plans, permits, drone, operators, assets, criteria."""
    drone = v.create_object(OT_EQUIPMENT, "Inspection drone", "Inspection drone UAV-D7-0041", {
        "Serial number": "UAV-D7-0041", "Model": "D7 dock drone", "Site": "Tank farm North"})
    v.create_object(OT_CERTIFICATE, "Certificate", "Airworthiness and maintenance check UAV-D7-0041", {
        "Related equipment": [drone], "Certificate type": "Airworthiness and maintenance", "Valid until": "2027-01-15"})
    for tag in ("TK-101", "TK-102"):
        v.create_object(OT_EQUIPMENT, "Storage tank", f"Storage tank {tag}", {
            "Asset tag": tag, "Model": "Atmospheric storage tank", "Site": "Tank farm North"})

    plan_n = v.create_object(OT_DOCUMENT, "Inspection plan", "Tank farm North weekly drone inspection route", {
        "Applies to site": "Tank farm North", "Requires permit": True, "Assets on route": "TK-101, TK-102",
        "Revision": "3", "Approved by": "qa.lead", "Approved date": "2026-07-01"}, state="Approved",
        content="1. Launch from dock North-1.\n2. Fly route waypoints WP1 to WP6 at 25 m.\n"
                "3. Capture gauge and nameplate images at TK-101 and TK-102.\n4. Return to dock and upload.",
        created_by="qa.lead", created_at="2026-06-28T09:00:00+00:00")
    v.new_version(plan_n, properties={"Revision": "4", "Approved by": None, "Approved date": None},
                  state="In review", created_by="qa.lead", comment="Revision 4 draft: new waypoint near TK-103")
    v.create_object(OT_DOCUMENT, "Inspection plan", "Tank farm South weekly drone inspection route", {
        "Applies to site": "Tank farm South", "Requires permit": True, "Assets on route": "TK-201",
        "Revision": "2", "Approved by": "qa.lead", "Approved date": "2026-05-12"}, state="Approved",
        content="1. Launch from dock South-1.\n2. Fly route waypoints WP1 to WP4 at 25 m.\n3. Return and upload.")

    v.create_object(OT_PERMIT, "Work permit", "WP-2026-0457 Drone flights, Tank farm North", {
        "Applies to site": "Tank farm North", "Valid from": "2026-10-01", "Valid until": "2026-10-31"}, state="Issued")
    v.create_object(OT_PERMIT, "Work permit", "WP-2026-0391 Drone flights, Tank farm South", {
        "Applies to site": "Tank farm South", "Valid from": "2026-09-01", "Valid until": "2026-09-30"}, state="Issued")

    v.create_object(OT_QUALIFICATION, "Operator qualification", "Drone remote pilot: mikko.pilot", {
        "Holder": "mikko.pilot", "Qualification": "Drone remote pilot", "Valid until": "2027-05-31"})
    v.create_object(OT_QUALIFICATION, "Operator qualification", "Drone remote pilot: sara.pilot", {
        "Holder": "sara.pilot", "Qualification": "Drone remote pilot", "Valid until": "2026-08-31"})

    for tag, point in (("TK-101", "PI-101"), ("TK-102", "PI-102")):
        v.create_object(OT_DOCUMENT, "Inspection criteria", f"{tag} pressure gauge {point} limits", {
            "Asset tag": tag, "Measurement point": point, "Limit min": 0.5, "Limit max": 6.0, "Unit": "bar",
            "Revision": "2", "Approved by": "qa.lead", "Approved date": "2026-04-20"}, state="Approved",
            content=f"1. Read pressure gauge {point}. Acceptable range 0.5 to 6.0 bar.\n"
                    "2. Check the inlet flange for visible leaks or staining.\n"
                    "3. Photograph the gauge face and the tank nameplate.")


def build_vault(path: str = ":memory:") -> MockVault:
    return seed(MockVault(path))
