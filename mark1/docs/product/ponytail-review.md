# Ponytail review: backend implementation diff

11 November 2026. Complexity-only findings; these suggested cuts have not been applied. Correctness fixes and runtime verification are tracked separately.

`mark1/server/service.py:L2: delete: unused copy import. Nothing replaces it.`

`mark1/server/inference.py:L5: delete: unused json import. Nothing replaces it.`

`mark1/server/state.py:L6: delete: unused APIError import. Nothing replaces it.`

`mark1/server/store.py:L91: shrink: six-line connection cleanup wrapper. with closing(self._connection()) as db, db: yield db, two lines.`

Paths above are relative to the outer Mark-1 project directory. The token, schema, policy, transaction and evidence boundaries serve explicit requirements and are not flagged for removal.

net: -7 lines possible.
