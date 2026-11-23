"""A chatflow's flows compiled into the one graph the executor runs (spec §3).

Node ids are unique across the agent, so the flows share one node namespace: the router (entry when there are two
or more flows) has one handle per flow wired to that flow's entry, and each goto_flow node gets an edge to its target
flow's entry. Nothing else about running a turn changes.
"""
from collections.abc import Mapping
from dataclasses import dataclass, field

from agent_runtime.sessions.schemas.workflow import Chatflow, ConvVariable, WorkflowBudget, WorkflowEdge, WorkflowNode
from agent_runtime.workflow.nodes.goto_flow import GOTO_HANDLE

ROUTER_ID = "router"


@dataclass(frozen=True)
class RunGraph:
    """What ``run_workflow`` reads: the attributes of ``Workflow`` without its authoring limits."""
    entry: str
    variables: tuple[ConvVariable, ...]
    nodes: tuple[WorkflowNode, ...]
    edges: tuple[WorkflowEdge, ...]
    budget: WorkflowBudget
    flow_of: Mapping[str, str] = field(default_factory=dict)  # node id -> flow id; the router has none


def _edge(source: str, handle: str, target: str) -> WorkflowEdge:
    # Wiring the runtime adds: the executor never reads an edge id, and these need not fit the authored id rules.
    return WorkflowEdge.model_construct(id=f"x_{source}_{handle}"[:40], source=source, source_handle=handle,
                                        target=target)


def compile_chatflow(chatflow: Chatflow) -> RunGraph:
    entries = {flow.id: flow.entry for flow in chatflow.flows}
    nodes: list[WorkflowNode] = []
    edges: list[WorkflowEdge] = []
    flow_of: dict[str, str] = {}
    for flow in chatflow.flows:
        for node in flow.nodes:
            nodes.append(node)
            flow_of[node.id] = flow.id
            target = entries.get(node.config.get("flow")) if node.type == "goto_flow" else None
            if target is not None:
                edges.append(_edge(node.id, GOTO_HANDLE, target))
        edges.extend(flow.edges)
    entry = chatflow.flows[0].entry
    if len(chatflow.flows) > 1:
        router = chatflow.router
        config = {"flows": [{"id": flow.id, "description": flow.description, "examples": list(flow.examples),
                             "trigger": flow.trigger, "routable": flow.routable} for flow in chatflow.flows],
                  "default_flow": router.default_flow, "model": router.model, "instructions": router.instructions,
                  "history_messages": router.history_messages}
        # "router" is not an authorable type (NODE_TYPES), so the node is built past the authoring validators.
        nodes.insert(0, WorkflowNode.model_construct(id=ROUTER_ID, type="router", title=None, description=None,
                                                     config=config))
        edges.extend(_edge(ROUTER_ID, flow.id, flow.entry) for flow in chatflow.flows)
        entry = ROUTER_ID
    return RunGraph(entry, chatflow.variables, tuple(nodes), tuple(edges), chatflow.budget, flow_of)
