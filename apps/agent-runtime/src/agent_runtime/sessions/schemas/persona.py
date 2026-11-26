"""Persona cases carried by agent.snapshot.v1: scripted conversations the publish gate replays against a chatflow."""
from typing import Annotated, Any, Literal

from pydantic import Field, model_validator
from pydantic_core import PydanticCustomError

from .common import BlockType, ContractModel, JsonObject, NonEmptyText
from .workflow import Ident, Title


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
