# ADR-004: Chatflow rules, snapshot evolution and flow routing

| Field | Value |
|---|---|
| **Status** | ACCEPTED 2026-11-26. Part 1 is implemented. Parts 2 and 3 are recorded rules and limitations; no code yet. |
| **Module** | `contracts/`, `apps/agent-runtime` (workflow), `apps/web-ui` (Studio chatflow editor) |
| **Related** | [ADR-003](ADR-003-chatflow-canvas.md), `contracts/openapi/schemas/chatflow.yaml`, `contracts/fixtures/chatflow-rules.json` |

## Context

The chatflow schema grew to multi-flow (router and `goto_flow`) and typed conversation variables. An architecture
review found three risks that get more expensive with every new node type or flow:

1. The same rules (limits, reserved ids, identifier and placeholder grammar) were hand-copied into the runtime
   schema, the runtime validator, the OpenAPI schema and several Studio files. Nothing caught a mismatch, and one
   already existed: Studio accepted upper-case segments in `{{…}}` placeholders, and the runtime prints those as
   literal text.
2. A published snapshot is re-validated with the current pydantic models whenever a conversation pinned to it is
   replayed (`agent.snapshot.v1`). Tightening a rule therefore changes how old releases load.
3. The router decides the flow from scratch on every turn. There is no "active flow".

## Decision

### 1. One source for chatflow rules (implemented)

- `contracts/openapi/schemas/chatflow.yaml` is the public shape. `contracts/fixtures/chatflow-rules.json` holds
  the rules the OpenAPI schema cannot express (placeholder grammar cases, reserved ids, `max_flow_switches`), plus
  the numeric limits.
- Runtime: the limits, reserved ids and node types live once in `workflow/rules.py`. So do the rules both checkers
  apply (duplicate ids, reserved flow ids, a routable flow needs a description, `default_flow` must be routable),
  written as predicates over plain values. The pydantic schema and the graph validator (`workflow/validator/`) call
  them and only word the finding. What a `conv.*` value may hold lives in `workflow/variables.py`.
  `tests/unit/workflow/test_chatflow_rules_parity.py` pins the YAML, the fixture, the constants and the pydantic
  JSON schema to each other, and runs the placeholder cases through `workflow/templates.py`.
  `tests/unit/workflow/test_chatflow_rules.py` checks that the schema and the validator reject the same cases.
- Studio: `pnpm gen:api` copies the fixture to `src/generated/`, and `model/workflow/rules.ts` derives every limit
  and pattern from it. `rules.test.ts` reads `contracts/` directly and runs the same placeholder cases.
- To change a limit, edit `chatflow.yaml`, `chatflow-rules.json` and the runtime constant together. Studio follows
  through `gen:api`.

### 2. Evolving the snapshot schema (rule)

- While the product is pre-production, `agent.snapshot.v1` may still be edited in place (see the MVP rule: no new
  migrations or schema versions, and local DBs are dropped).
- From the first production release on, a published chatflow is never re-validated under stricter rules.
  Loosening a rule, or adding an optional field or a node type, stays in v1. Tightening a limit, renaming or
  removing a node type, or changing a placeholder or expression grammar needs a `chatflow_schema_version` on the
  chatflow. The runtime then keeps one validator per version it still serves.
- The version field is added before go-live, not when the first breaking change arrives.

### 3. Flow continuity (known limitation, deferred)

- Today, a button press (`sys.interaction`) goes to the router. A matching flow `trigger` wins; otherwise the press
  goes to `default_flow`, and is never classified. Text turns use trigger, then classifier, then default.
- Consequence: a button shown by a non-default flow is handled by the default flow unless the author adds a trigger
  for it. Each routed text turn also spends one classifier LLM call.
- Until this is designed, authors put the follow-up of an interaction in the default flow, or give the owning flow
  a trigger on `sys.interaction` (or on `conv.stage`).
- The likely design is a runtime-owned `sys.active_flow`: an interaction goes back to the flow that rendered it.
  Decide it before authors build several flows that each show buttons.

## Consequences

- A rule that changes on one side only fails CI on both stacks.
- Studio no longer offers JSON output field names a placeholder cannot reach (lower-case only, starting with a
  letter). It also checks the variable constraint bounds that publish would reject.
- Parts 2 and 3 cost nothing now, but must be revisited before the first production release (part 2), and before
  multi-flow agents with interactive blocks (part 3).
