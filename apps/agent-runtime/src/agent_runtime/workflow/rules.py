"""The chatflow rules, in one place (ADR-004).

Two checkers apply them:
- the pydantic schema (``sessions/schemas/workflow.py``) on the parsed model: it stops at the first break, in English;
- the graph validator (``workflow/validator``) on the raw dict: it reports every break, in Vietnamese.

Each rule is written here once, as a predicate over plain values, and the callers only word the finding.
``contracts/fixtures/chatflow-rules.json`` pins the constants to the OpenAPI schema and Studio. This module imports
nothing from the runtime, so the schema layer can depend on it.
"""
from collections.abc import Iterable, Iterator, Mapping

NODE_TYPES = frozenset({"start", "if_else", "intent_classifier", "llm", "agent", "knowledge_retrieval",
                        "tool", "profile_propose", "assign", "answer", "goto_flow"})
# Registered node types the runtime builds itself and an author can never use (not in the catalog).
INTERNAL_NODE_TYPES = frozenset({"router"})

# Scope routes the first four path heads to a namespace, so a node with such an id could never have its output read;
# "router" is the runtime's own routing node of a multi-flow chatflow.
RESERVED_NODE_IDS = frozenset({"sys", "conv", "profile", "result", "router"})
# The router classifies with these as handles of its own, so no flow may take them as an id.
RESERVED_FLOW_IDS = frozenset({"other", "error"})
MAX_VARIABLES, MAX_FLOWS, MAX_NODES, MAX_EDGES, MAX_ENUM_VALUES = 60, 10, 50, 100, 30
IDENT_PATTERN = r"^[a-z][a-z0-9_]{0,39}$"


def duplicates(values: Iterable[object]) -> Iterator[tuple[int, str]]:
    """(position, value) of every string equal to an earlier one. Non-strings are skipped: their shape is the
    schema's finding, not a duplicate."""
    seen: set[str] = set()
    for index, value in enumerate(values):
        if isinstance(value, str):
            if value in seen:
                yield index, value
            seen.add(value)


def node_id_reserved(node_id: object) -> bool:
    return isinstance(node_id, str) and node_id in RESERVED_NODE_IDS


def flow_id_reserved(flow_id: object) -> bool:
    return isinstance(flow_id, str) and flow_id in RESERVED_FLOW_IDS


def flow_needs_description(routable: object, description: object) -> bool:
    """A routable flow (``routable`` is anything but False) whose description is missing or blank: the router sends
    the description to the model, so it cannot pick such a flow."""
    return routable is not False and not (isinstance(description, str) and description.strip())


def default_flow_routable(default: object, routable_by_flow: Mapping[str, object]) -> bool:
    """``router.default_flow`` names a flow, and that flow is routable."""
    return isinstance(default, str) and default in routable_by_flow and routable_by_flow[default] is not False


def cross_flow_duplicates(flows: Iterable[tuple[object, Iterable[object]]]) -> Iterator[tuple[int, int, str, str]]:
    """Node ids used by more than one flow: stubs, persona paths and traces name a node by id alone.

    ``flows`` gives (flow id, node ids) per flow. Yields (flow position, node position, node id, the flow that used
    it first). A duplicate inside one flow is that flow's own ``duplicates`` finding, so it is skipped here."""
    first: dict[str, str] = {}
    for k, (flow_id, node_ids) in enumerate(flows):
        local: set[str] = set()
        for i, node_id in enumerate(node_ids):
            if not isinstance(node_id, str) or node_id in local:
                continue
            local.add(node_id)
            if node_id in first:
                yield k, i, node_id, first[node_id]
            else:
                first[node_id] = str(flow_id)
