# Mark-1 delivery plan - specification 2.0

10 November 2026. This replaces the older 10-day BIOS/overheating/learning plan. No calendar commitment is inferred from team strengths; confirm available hours first.

1. **A baseline/contracts:** A-01/A-02 reconcile package layout/runtime/auth/limits and publish v2 contracts, engine stub and all-state fixtures. V/J review interfaces.
2. **V knowledge / J screens:** V-01 authors fictional source/check/view/question/explanation/diagram and scenario data. J-01 maps camera/chat/voice/cutaway and failure states.
3. **Independent implementation:** A-03..A-07 implement local trusted backend using A-owned test doubles. V-02..V-06 build investigator/provider/explanation selection. J-02..J-06 build phone experience using API mocks.
4. **Integrated demo:** J-07, A-08 demonstrate image ->retrieval ->contextual question ->source-backed cutaway ->approved check ->durable human outcome, plus rejection/recovery paths. A-09 documents run/recovery/operations.
5. **Evaluate:** V-07 frozen held-out investigator/perception evaluation. R0 remains synthetic and advisory. A-10 supervised pilot evidence and V-08/A-11 real diagnosis gates are later evidence-dependent work.

Streaming, tracked overlays, learning and autonomy are deferred. No real M-Files/customer data is authorized. A can complete local backend without V/J implementations; integrated camera/voice/AI experience needs both.

Use the [full delivery specification](docs/specs/Mark1-Team-Spec/08-DELIVERY-AND-OPERATIONS.md), [28-ticket backlog](docs/specs/Mark1-Team-Spec/09-BACKLOG.csv), and [role/ownership map](docs/specs/Mark1-Team-Spec/02-OWNERSHIP-AND-HANDOFFS.md). Each nontrivial module needs meaningful owner tests; application acceptance requires runtime tests beyond contract artifacts. Run contract checks using [these instructions](docs/specs/Mark1-Team-Spec/contracts/README.md).
