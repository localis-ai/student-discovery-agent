"""The runtime's routing node: entry of a multi-flow chatflow, one handle per flow. Never authored (spec §3)."""
from typing import Annotated, Any

from pydantic import Field, field_validator

from agent_runtime.sessions.schemas.common import ContractModel
from agent_runtime.sessions.schemas.workflow import Ident
from agent_runtime.workflow.expressions import ExpressionError, evaluate, parse
from agent_runtime.workflow.nodes import intent_classifier
from agent_runtime.workflow.nodes.base import NodeContext, NodeError, NodeResult, NodeSpec
from agent_runtime.workflow.registry import register


class RoutedFlow(ContractModel):
    id: Ident
    description: str = ""
    examples: tuple[str, ...] = ()
    trigger: dict[str, Any] | None = None
    routable: bool = True

    @field_validator("trigger")
    @classmethod
    def safe(cls, value: dict[str, Any] | None) -> dict[str, Any] | None:
        if value is not None:
            try:
                parse(value)
            except ExpressionError as error:
                raise ValueError(f"{error.code}: {error}") from None
        return value


class RouterConfig(ContractModel):
    flows: Annotated[tuple[RoutedFlow, ...], Field(min_length=2)]
    default_flow: Ident
    model: str | None = None
    instructions: str = ""
    history_messages: int = 0


def _to(flow: str, method: str, label: str | None = None) -> NodeResult:
    reason = {"method": method, "flow": flow} | ({"label": label} if label is not None else {})
    return NodeResult(flow, {"flow": flow}, reason=reason)


def run(ctx: NodeContext, config: RouterConfig) -> NodeResult:
    for flow in config.flows:  # a trigger wins the turn, in list order (D3)
        if flow.trigger is not None and evaluate(parse(flow.trigger), ctx.scope.get).matched:
            return _to(flow.id, "trigger")
    if ctx.scope.get("sys.interaction") is not None:  # a button press is no sentence to classify
        return _to(config.default_flow, "default")
    routable = [flow for flow in config.flows if flow.routable]
    if len(routable) == 1:
        return _to(routable[0].id, "single")
    labels = tuple(intent_classifier.Label(id=flow.id, description=flow.description, examples=flow.examples[:5])
                   for flow in routable)
    classifier = intent_classifier.ClassifierConfig(labels=labels, instructions=config.instructions,
                                                    model=config.model, history_messages=config.history_messages)
    try:
        classified = intent_classifier.run(ctx, classifier)
    except NodeError:  # a router that cannot classify still answers: from the default flow
        return _to(config.default_flow, "default", "error")
    label = classified.handle
    if label == "other":  # "unrecognized": the model named no flow at all, which an author should see
        return _to(config.default_flow, "default", "unrecognized" if classified.reason.get("unrecognized") else "other")
    return _to(label, "classifier", label)


register(NodeSpec("router", RouterConfig, lambda config: tuple(flow.id for flow in config.flows),
                  {"type": "object", "properties": {"flow": {"type": "string"}}}, run))
