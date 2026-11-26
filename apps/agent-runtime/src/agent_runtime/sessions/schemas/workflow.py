"""Chatflow schema carried by agent.snapshot.v1 (mode=chatflow). Shape only: graph semantics are the T14 validator.

The limits, reserved ids and the rules both checkers apply live in ``workflow/rules.py``; what a variable value may
hold lives in ``workflow/variables.py``.
"""
from collections.abc import Iterator
from typing import Annotated, Any, Literal

from pydantic import AfterValidator, Field, StringConstraints, model_validator
from pydantic_core import PydanticCustomError

from agent_runtime.workflow.rules import (
    IDENT_PATTERN,
    MAX_EDGES,
    MAX_ENUM_VALUES,
    MAX_FLOWS,
    MAX_NODES,
    MAX_VARIABLES,
    NODE_TYPES,
    cross_flow_duplicates,
    default_flow_routable,
    duplicates,
    flow_id_reserved,
    flow_needs_description,
    node_id_reserved,
)
from agent_runtime.workflow.variables import CONSTRAINT_KEYS, fits_type, within_constraints

from .common import ContractModel, JsonObject, NonEmptyText

Ident = Annotated[str, StringConstraints(pattern=IDENT_PATTERN)]
Title = Annotated[str, StringConstraints(min_length=1, max_length=100, pattern=r"\S")]


def _supported_type(value: str) -> str:
    if value not in NODE_TYPES:
        raise PydanticCustomError("workflow_node_type_unsupported", "node type is not available in chatflow v1")
    return value


NodeType = Annotated[str, AfterValidator(_supported_type)]

Description = Annotated[str, StringConstraints(max_length=300)]
FiniteNumber = Annotated[float, Field(allow_inf_nan=False)]


class VariableConstraints(ContractModel):
    min_length: Annotated[int, Field(strict=True, ge=0, le=4000)] | None = None
    max_length: Annotated[int, Field(strict=True, ge=0, le=4000)] | None = None
    minimum: FiniteNumber | None = None
    maximum: FiniteNumber | None = None
    integer: bool | None = None
    max_items: Annotated[int, Field(strict=True, ge=1, le=100)] | None = None
    item_max_length: Annotated[int, Field(strict=True, ge=1, le=1000)] | None = None


def _invalid(message: str, field: str) -> PydanticCustomError:
    return PydanticCustomError("workflow_variable_invalid", message, {"field": field})


class ConvVariable(ContractModel):
    name: Ident
    description: Description | None = None
    type: Literal["string", "number", "boolean", "enum", "string_list"]
    values: Annotated[tuple[NonEmptyText, ...], Field(min_length=1, max_length=MAX_ENUM_VALUES)] | None = None
    default: Any
    constraints: VariableConstraints | None = None

    @property
    def limits(self) -> dict[str, Any] | None:
        """The set constraint keys, as value_fits() takes them; None when nothing is constrained."""
        limits = self.constraints.model_dump(exclude_none=True) if self.constraints else {}
        return limits or None

    @model_validator(mode="after")
    def consistent(self) -> "ConvVariable":
        if (self.type == "enum") != (self.values is not None):
            raise _invalid("only enum variables carry values, and they must", "values")
        if self.values is not None and len(set(self.values)) != len(self.values):
            raise PydanticCustomError("duplicate_items", "enum values must be unique", {"field": "values"})
        limits = self.limits or {}
        for key in limits:
            if key not in CONSTRAINT_KEYS[self.type]:
                raise _invalid(f"constraint {key} does not apply to {self.type}", f"constraints.{key}")
        for low, high in (("min_length", "max_length"), ("minimum", "maximum")):
            if low in limits and high in limits and limits[low] > limits[high]:
                raise _invalid(f"{low} is above {high}", f"constraints.{low}")
        if not fits_type(self.type, self.default, self.values):
            raise _invalid("default does not fit the variable type", "default")
        if not within_constraints(self.default, limits):
            raise _invalid("default breaks the variable constraints", "default")
        return self


class Position(ContractModel):
    x: Annotated[float, Field(allow_inf_nan=False)]
    y: Annotated[float, Field(allow_inf_nan=False)]


class NodeUi(ContractModel):
    position: Position | None = None


class WorkflowNode(ContractModel):
    id: Ident
    type: NodeType
    title: Title | None = None
    description: Annotated[str, StringConstraints(max_length=500)] | None = None  # authoring note; never read at run time
    config: JsonObject = Field(default_factory=dict)  # per-type schema comes from the node-type catalog (T02/T14)
    ui: NodeUi = NodeUi()


class WorkflowEdge(ContractModel):
    id: Ident
    source: Ident
    source_handle: Ident
    target: Ident


class WorkflowBudget(ContractModel):
    # Defaults are the DEC-24 baseline proposal; hard ceilings are enforced by the T14 validator once DEC-24 is final.
    max_nodes: Annotated[int, Field(strict=True, ge=1)] = 20
    max_llm_calls: Annotated[int, Field(strict=True, ge=1)] = 6
    turn_timeout_ms: Annotated[int, Field(strict=True, ge=1)] = 25000


def _check_reserved(nodes: tuple[WorkflowNode, ...], prefix: str = "") -> None:
    for index, node in enumerate(nodes):
        if node_id_reserved(node.id):
            raise PydanticCustomError("workflow_node_id_reserved", "node id is a reserved namespace",
                                      {"field": f"{prefix}nodes.{index}.id"})


def _check_unique(owner: Any, collections: tuple[tuple[str, str], ...]) -> None:
    for collection, key in collections:
        found = next(duplicates(getattr(item, key) for item in getattr(owner, collection)), None)
        if found is not None:  # first duplicate only; reporting every one is the T14 validator's job
            raise PydanticCustomError("duplicate_items", "ids must be unique", {"field": f"{collection}.{found[0]}.{key}"})


class Workflow(ContractModel):
    """One graph: a flow as the executor and the node tests see it (entry, nodes, edges, variables, budget)."""
    entry: Ident
    variables: Annotated[tuple[ConvVariable, ...], Field(max_length=MAX_VARIABLES)] = ()
    nodes: Annotated[tuple[WorkflowNode, ...], Field(min_length=1, max_length=MAX_NODES)]
    edges: Annotated[tuple[WorkflowEdge, ...], Field(max_length=MAX_EDGES)] = ()
    budget: WorkflowBudget = WorkflowBudget()

    @model_validator(mode="after")
    def unique_ids(self) -> "Workflow":
        _check_reserved(self.nodes)
        _check_unique(self, (("variables", "name"), ("nodes", "id"), ("edges", "id")))
        return self


def _flow_invalid(message: str, field: str) -> PydanticCustomError:
    return PydanticCustomError("workflow_flow_invalid", message, {"field": field})


Example = Annotated[str, StringConstraints(min_length=1, max_length=200, pattern=r"\S")]


class Flow(ContractModel):
    """One business flow (nghiệp vụ): a graph plus what the router reads to pick it."""
    id: Ident
    title: Title
    description: Description = ""  # the router sends it to the model: configuration, not an authoring note
    examples: Annotated[tuple[Example, ...], Field(max_length=5)] = ()
    trigger: JsonObject | None = None  # DEC-23 condition, checked by the graph validator; a match wins the turn
    routable: bool = True  # False: only reached through a trigger or goto_flow
    entry: Ident
    nodes: Annotated[tuple[WorkflowNode, ...], Field(min_length=1, max_length=MAX_NODES)]
    edges: Annotated[tuple[WorkflowEdge, ...], Field(max_length=MAX_EDGES)] = ()

    @model_validator(mode="after")
    def consistent(self) -> "Flow":
        if flow_id_reserved(self.id):
            raise _flow_invalid("flow id cannot be other or error", "id")
        if flow_needs_description(self.routable, self.description):
            raise _flow_invalid("a routable flow needs a description", "description")
        _check_reserved(self.nodes)
        _check_unique(self, (("nodes", "id"), ("edges", "id")))
        return self


class ChatflowRouter(ContractModel):
    default_flow: Ident
    model: NonEmptyText | None = None  # None: the agent's model
    instructions: Annotated[str, StringConstraints(max_length=2000)] = ""
    history_messages: Annotated[int, Field(strict=True, ge=0, le=6)] = 0


class Chatflow(ContractModel):
    """agent.snapshot.v1 ``workflow``: shared variables and budget, the router, and one to ten flows."""
    variables: Annotated[tuple[ConvVariable, ...], Field(max_length=MAX_VARIABLES)] = ()
    budget: WorkflowBudget = WorkflowBudget()
    router: ChatflowRouter
    # No min_length: pydantic would also report one bad flow as too_short; emptiness is checked below.
    flows: Annotated[tuple[Flow, ...], Field(max_length=MAX_FLOWS)]

    def flow(self, flow_id: str) -> Flow | None:
        return next((flow for flow in self.flows if flow.id == flow_id), None)

    def nodes(self) -> Iterator[tuple[Flow, WorkflowNode]]:
        for flow in self.flows:
            for node in flow.nodes:
                yield flow, node

    @model_validator(mode="after")
    def consistent(self) -> "Chatflow":
        if not self.flows:
            raise _flow_invalid("a chatflow needs at least one flow", "flows")
        _check_unique(self, (("variables", "name"), ("flows", "id")))
        # agent-wide: stubs, persona paths and traces name a node by id alone
        found = next(cross_flow_duplicates((flow.id, (node.id for node in flow.nodes)) for flow in self.flows), None)
        if found is not None:
            raise PydanticCustomError("workflow_node_id_duplicate", "node ids are unique across flows",
                                      {"field": f"flows.{found[0]}.nodes.{found[1]}.id"})
        if not default_flow_routable(self.router.default_flow, {flow.id: flow.routable for flow in self.flows}):
            raise _flow_invalid("default_flow must name a routable flow", "router.default_flow")
        return self
