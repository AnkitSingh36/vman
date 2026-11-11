# Local backend verification

11 November 2026 | `a/mark1-backend-r0` | Author-run developer evidence; no product gate closed.

Tested with Windows/Python 3.13.7 and the isolated environment captured in `requirements-dev.lock.txt`. The initial global-environment baseline had two missing-Google-SDK failures in the original Lantern tests. With the declared optional SDK in the isolated environment, the unchanged Lantern suite passes. No Lantern source or original tests were edited.

## Results

| Check | Command from repository root | Observed result |
| --- | --- | --- |
| Application regression suites | `mark1/.venv/Scripts/python.exe -m pytest -q tests mark1/tests` | 74 passed: 42 original Lantern tests and 32 Mark-1 tests, including the package smoke test |
| Contract artifacts | `mark1/.venv/Scripts/python.exe mark1/docs/specs/Mark1-Team-Spec/contracts/validate-contracts.py` | 92 positive/negative schema checks; catalog/source/graph, API/scenario and 28 ticket dependency checks passed |
| Hashing | `mark1/.venv/Scripts/python.exe mark1/docs/specs/Mark1-Team-Spec/contracts/validate-hashes.py` | Two canonical golden hashes and embedded catalog equality passed |
| Combined specification | `mark1/.venv/Scripts/python.exe mark1/docs/specs/build_team_spec.py --check` | Matches all 11 split documents currently on this branch |
| Dependency consistency | `mark1/.venv/Scripts/python.exe -m pip check` | No broken requirements |
| Scripted API journey | `mark1/.venv/Scripts/python.exe -m mark1.server.testing.demo` | Generated snapshot uploaded; identity/preflight/view/question/check/advisory INPUT diagram/escalation; 22 durable events |
| Server startup | Local uvicorn process on `127.0.0.1:18761`, temporary SQLite database | `/health` returned synthetic-demo mode; process stopped and temporary database cleaned |
| Whitespace | `git diff --check` | Passed |

Editable installation was built and installed successfully with the declared setuptools backend. The independent architecture note remains on its separate PR branch; its absence from this branch's combined-spec count is intentional.

## Runtime cases exercised

- Direct HTTP cannot skip preflight; chat cannot impersonate confirmed physical evidence.
- Complete fake-engine investigation and explicit human resolution/escalation; generated image and unavailable-camera paths.
- Actor/tenant/agent isolation, revoked caller access, hidden restrictions and missing policy fail closed.
- Identical-key concurrent retries yield one effect; distinct keys at one revision conflict; old command replay after stop returns fresh non-actionable state and its original receipt identity.
- Wrong model binding, arbitrary model instruction text, unsupported sources/claims, provider exception and timeout cannot release guidance.
- Stop wins over late model output. A policy stop found during failed internal media resolution is committed and cannot be undone by the error response.
- Catalog/record/source immutability, source/diagram/check withdrawal, no republish approval fallback, invalid prerequisites/graph references and changed-catalog session invalidation.
- MIME/decoded-pixel checks, metadata-free reconstructed snapshots, foreign image IDs and current-inference-only cleared handles.
- Atomic rollback on simulated storage failure followed by safe same-key retry; restart reconciliation; backup/restore; terminal-session erasure and replay tombstones.
- Canonical Swagger schema bundling and the selected bearer authentication scheme.

## Limits

These tests establish bounded local backend behavior under the tested conditions, not production safety or diagnosis quality. No real provider, customer data, vault, browser voice/camera UI, moving overlay or SME-reviewed repair content was used. Single worker, editable checkout and synthetic mode are the supported deployment. Live provider/tool metering, independent V/J review, real module integration, browser acceptance, operational retention/restore authorization and pilot gates remain pending.

Startup/shutdown uses FastAPI's documented [lifespan interface](https://fastapi.tiangolo.com/advanced/events/). The complexity-only [Ponytail review](ponytail-review.md) records seven removable lines; its suggested cuts were deliberately not applied during that review.
