# Contract 2.0 artifacts

These describe the proposed visual investigation API and engine port. They do not implement a server or establish product readiness. See [the normative contract](../06-CONTRACTS.md) for operation/state, policy, receipt and evidence rules beyond JSON Schema.

- `public-api.openapi.json`: public `/v2` operations, bodies, errors and receipts.
- `session.schema.json`: all eleven server states and output restrictions.
- `investigation.schema.json`: view/question/explanation, diagram and investigation context definitions.
- `catalog.schema.json`: scoped approved checks, templates, claim rules and diagrams.
- `engine-request.schema.json`, `engine-proposal.schema.json`: context-bound internal port.
- `all-fixtures.json`: independent state/proposal/error payloads and identity-view/missing-diagram variants.
- `public-request-fixtures.json`, `request-fixtures.json`, `examples.json`: public bodies, internal requests and display examples.
- `scenario-fixtures.json`: branching integration test plans; these are not executed traces.
- `synthetic-guide.txt`: fictional source text; catalog hashes match its exact bytes.
- `hash-golden.json`: canonical decision-context bytes and SHA-256 examples.

Schema identifiers use `schemas.mark1.invalid` as an offline namespace, not a hosted service. The validator registers local files and never retrieves schemas over the network. Embedded catalog schema must equal its standalone definition. Public request field types do not prove a value is currently allowed for the active catalog interaction; runtime validation is mandatory.

## Verify

From the repository root, use an isolated environment. On Windows, no activation script or PowerShell execution-policy change is required:

```powershell
python -m venv mark1/.venv-spec
mark1/.venv-spec/Scripts/python.exe -m pip install -r mark1/docs/specs/Mark1-Team-Spec/contracts/validation-requirements.txt
mark1/.venv-spec/Scripts/python.exe mark1/docs/specs/Mark1-Team-Spec/contracts/validate-contracts.py
mark1/.venv-spec/Scripts/python.exe mark1/docs/specs/Mark1-Team-Spec/contracts/validate-hashes.py
python mark1/docs/specs/build_team_spec.py --check
```

On other platforms use the environment's `bin/python`. The PowerShell wrapper calls the same two Python validators. Keep virtual environments untracked. The hash checker uses Python's standard library only.

Fixed demo timestamps are deliberately historical. A server stub must create fresh policy leases, inference bindings and command receipts; serving the JSON unchanged is not a runnable authorized demo. Diagram highlights and fault claims in examples are synthetic and advisory. No real M-Files, provider call, customer data or repair is involved in these checks.
