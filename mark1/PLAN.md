# PLAN.md — Mark-1, 10-day plan

Every step ends with passing `python -m pytest -q`. Every formula and guardrail has a unit test.
Scope: BIOS update, overheating, learning centrepiece. Deferred: HMI firmware guide, live 3D AR,
real robot, Rho-alpha, monitoring dashboard beyond the demo.

## Day 1 — Mock vault core
1. Schema: object types, classes, properties (IDs 0/100/38/39; custom from 1000), objects, versions,
   workflows/states, named ACLs + components, users/groups (person + agent), audit log.
   *Accept:* create/read objects and versions; property IDs correct; every read/write audited; tests pass.
2. Machine-agnostic metadata: document type, applies-to model, serial range/config, revision, state, components.
   *Accept:* lookup by metadata works with no device-specific code.

## Day 2 — Demo data and bridge guardrails
3. Seed fictional LX-14: two service tags (Rev A/Rev B), assets, advisory, BIOS packages and procedure
   per revision, model facts, telemetry, service history, fault knowledge, hazard rules.
   *Accept:* seed is deterministic; all names fictional.
4. Bridge (read-only tools + `dispatch`): session identity, ACL for person AND agent (all components),
   approved-version selection (newer drafts reported, ignored), exact-match identifiers, refusal on
   unknown/ambiguous, verbatim steps with source.
   *Accept:* revision trap returns the right package per tag; ACL, draft and ambiguity tests pass;
   write tools absent from declarations/dispatch (tested).

## Day 3 — Learning engine I
5. Bayes belief, entropy, information gain, next check = argmax gain/cost under guardrails, stop at
   tau = 0.90, escalate when checks run out.
   *Accept:* hand-computed examples match; never guesses below tau.
6. Document-prior counts (a0, b0, strength m) and update from confirmed cause.
   *Accept:* priors and updates match the reference file numerically.

## Day 4 — Learning engine II
7. Blueprint graph G=(V,E) per board revision; propagation rules causes in/out; plain-word explanations.
   *Accept:* "ruled out X because Y" text generated from graph data; tests on both revisions.
8. Baseline + CUSUM (k = sigma/2, h = 5 sigma).
   *Accept:* flat series no alarm; drift triggers within expected samples.
9. Wilson lower bound + autonomy levels; promotion needs threshold, min n, recorded person approval.
   *Accept:* no promotion without approval; approval written to vault and audited.

## Day 5 — Training gym
10. Simulated faults/symptoms from vault fault knowledge and blueprint graph; reward = correct - lambda*cost.
    *Accept:* seeded runs reproducible; metrics accuracy, effort, Brier.
11. Learning-curve charts.
    *Accept:* PNG chart shows improvement over episodes on the demo fault set.

## Day 6 — Planner and executor
12. Planner interface; offline simulated planner; Gemini planner (google-genai, function calling,
    configurable model id); fake Gemini client for tests.
    *Accept:* loop tests offline; model text never reaches the user as instructions.
13. Executor interface: `SimulatedExecutor`, `RhoAlphaExecutor` stub (raises NotImplemented).
    *Accept:* demo cannot reach a real flash; confirmation required for critical steps (tested).

## Day 7 — Scenario 1: BIOS update
14. Identify (image -> model -> service tag) -> asset BIOS vs advisory -> prerequisites -> key region ->
    success check "BIOS screen visible" -> stop before flash -> evidence (app-only write).
    *Accept:* Rev A and Rev B get different packages/procedures; offline end-to-end test passes.

## Day 8 — Scenario 2: Overheating
15. CUSUM alert -> belief over causes -> best next checks -> reasoning in words -> x-ray bottom view
    with fan highlighted -> approved cleaning steps -> confirmed cause updates counts.
    *Accept:* end-to-end offline test; belief changes after confirmation.

## Day 9 — Web app
16. FastAPI backend + static page: photo capture (`capture="environment"`), overlay canvas (blink key /
    highlight part; Gemini point every 1–2 s, stored region fallback), step confirmation, speechSynthesis
    toggle, audit view, offline mode with sample images, HTTPS via mkcert or localhost webcam.
    *Accept:* works on a phone over LAN with sample images; API tests pass.

## Day 10 — Learning centrepiece and polish
17. Gym run + learning curve in UI; autonomy record; person approves Level 2 for BIOS pre-checks.
    *Accept:* promotion recorded in vault and visible in audit.
18. Sample images script, README, demo script, full test run, Gemini-mode smoke test if key available.
    *Accept:* fresh clone -> install -> demo in under 10 minutes.
