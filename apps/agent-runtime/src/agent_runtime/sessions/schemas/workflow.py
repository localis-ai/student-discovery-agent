"""Chatflow schema carried by agent.snapshot.v1 (mode=chatflow). Shape only: graph semantics are the T14 validator."""
import math
from collections.abc import Mapping
from typing import Annotated, Any, Literal

from pydantic import AfterValidator, Field, StringConstraints, model_validator
from pydantic_core import PydanticCustomError

from .common import ContractModel, JsonObject, NonEmptyText

NODE_TYPES = frozenset({"start", "if_else", "intent_classifier", "llm", "agent", "knowledge_retrieval",
                        "tool", "profile_propose", "assign", "answer"})

# Scope routes these path heads to a namespace, so a node with such an id could never have its output read.
RESERVED_NODE_IDS = frozenset({"sys", "conv", "profile", "result"})

_JSON_SAFE_INT = 9007199254740991  # same bound as JsonSafeInt in common.py

Ident = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]{0,39}$")]
Title = Annotated[str, StringConstraints(min_length=1, max_length=100, pattern=r"\S")]


def _supported_type(value: str) -> str:
    if value not in NODE_TYPES:
        raise PydanticCustomError("workflow_node_type_unsupported", "node type is not available in chatflow v1")
    return value


NodeType = Annotated[str, AfterValidator(_supported_type)]


def _fits(kind: str, value: Any, values: tuple[str, ...] | None) -> bool:
    if kind == "string":
        return isinstance(value, str)
    if kind == "number":
        if isinstance(value, bool):
            return False
        if isinstance(value, int):  # never float() an int: huge JSON integers raise OverflowError
            return abs(value) <= _JSON_SAFE_INT
        return isinstance(value, float) and math.isfinite(value)
    if kind == "boolean":
        return isinstance(value, bool)
    if kind == "enum":
        return isinstance(value, str) and value in (values or ())
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


Description = Annotated[str, StringConstraints(max_length=300)]
FiniteNumber = Annotated[float, Field(allow_inf_nan=False)]

# Which constraint keys each variable type accepts; anything else is workflow_variable_invalid.
CONSTRAINT_KEYS: dict[str, frozenset[str]] = {
    "string": frozenset({"min_length", "max_length"}),
    "number": frozenset({"minimum", "maximum", "integer"}),
    "boolean": frozenset(),
    "enum": frozenset(),
    "string_list": frozenset({"max_items", "item_max_length"}),
}


def _within(value: Any, limits: Mapping[str, Any] | None) -> bool:
    """Constraint check on a value that already fits its type."""
    if not limits:
        return True
    if isinstance(value, str):
        return limits.get("min_length", 0) <= len(value) <= limits.get("max_length", len(value))
    if isinstance(value, list):
        if len(value) > limits.get("max_items", len(value)):
            return False
        longest = limits.get("item_max_length")
        return longest is None or all(len(item) <= longest for item in value)
    if isinstance(value, int | float) and not isinstance(value, bool):
        if limits.get("integer") and not float(value).is_integer():
            return False
        return limits.get("minimum", value) <= value <= limits.get("maximum", value)
    return True


def value_fits(kind: str, value: Any, values: tuple[str, ...] | None = None,
               constraints: Mapping[str, Any] | None = None) -> bool:
    """Public form of the variable type and constraint check, shared with the chatflow runtime."""
    return _fits(kind, value, values) and _within(value, constraints)


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
    values: Annotated[tuple[NonEmptyText, ...], Field(min_length=1, max_length=30)] | None = None
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
        if not _fits(self.type, self.default, self.values):
            raise _invalid("default does not fit the variable type", "default")
        if not _within(self.default, limits):
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


class Workflow(ContractModel):
    entry: Ident
    variables: Annotated[tuple[ConvVariable, ...], Field(max_length=30)] = ()
    nodes: Annotated[tuple[WorkflowNode, ...], Field(min_length=1, max_length=50)]
    edges: Annotated[tuple[WorkflowEdge, ...], Field(max_length=100)] = ()
    budget: WorkflowBudget = WorkflowBudget()

    @model_validator(mode="after")
    def unique_ids(self) -> "Workflow":
        for index, node in enumerate(self.nodes):
            if node.id in RESERVED_NODE_IDS:
                raise PydanticCustomError("workflow_node_id_reserved", "node id is a reserved namespace",
                                          {"field": f"nodes.{index}.id"})
        for collection, key in (("variables", "name"), ("nodes", "id"), ("edges", "id")):
            seen: set[str] = set()
            for index, item in enumerate(getattr(self, collection)):
                value = getattr(item, key)
                if value in seen:  # first duplicate only; reporting every one is the T14 validator's job
                    raise PydanticCustomError("duplicate_items", "ids must be unique",
                                              {"field": f"{collection}.{index}.{key}"})
                seen.add(value)
        return self


BlockType = Literal["text", "markdown", "suggestions", "assessment_question", "assessment_clarification",
                    "personality_card", "knowledge_card"]


class PersonaInteraction(ContractModel):
    action: NonEmptyText
    outcome: NonEmptyText | None = None
    option_id: NonEmptyText | None = None


class PersonaInput(ContractModel):
    text: Annotated[str, Field(min_length=1, max_length=4000)] | None = None
    interaction: PersonaInteraction | None = None

    @model_validator(mode="after")
    def exactly_one(self) -> "PersonaInput":
        if (self.text is None) == (self.interaction is None):
            raise PydanticCustomError("persona_input_invalid", "exactly one of text or interaction")
        return self


class PersonaExpect(ContractModel):
    path: tuple[Ident, ...] | None = None  # the nodes that ran, exactly and in order
    blocks_present: tuple[BlockType, ...] = ()
    blocks_absent: tuple[BlockType, ...] = ()
    conv: dict[str, Any] = Field(default_factory=dict)  # only these keys are checked, after the turn
    proposals: Annotated[int, Field(strict=True, ge=0)] | None = None
    status: Literal["completed", "fallback"] | None = None


class PersonaState(ContractModel):
    profile: JsonObject = Field(default_factory=dict)
    result: JsonObject | None = None
    conv: JsonObject = Field(default_factory=dict)
    activity: JsonObject | None = None


class PersonaTurn(ContractModel):
    input: PersonaInput
    llm_stubs: dict[str, Any] = Field(default_factory=dict)
    expect: PersonaExpect = PersonaExpect()


class PersonaCase(ContractModel):
    id: Ident
    title: Title
    mandatory: bool = False
    initial_state: PersonaState = PersonaState()
    turns: Annotated[tuple[PersonaTurn, ...], Field(min_length=1, max_length=20)]
