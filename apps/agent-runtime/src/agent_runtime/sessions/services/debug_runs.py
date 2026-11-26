"""Isolated chatflow debug run (FR-WFL-14): same executor, other ports. No unit of work, no repository, no writes.

The run is the Admin's own: the request carries a draft and a made-up state, the result goes back to Studio and
is never stored here, so its node runs use the ``full`` redaction. The production trace path is not involved.
"""
import logging
import time
from collections.abc import Callable
from datetime import UTC, date, datetime
from types import SimpleNamespace
from typing import Annotated, Any, Literal, get_args

from pydantic import Field, ValidationError, model_validator

from agent_runtime.agent.loop import TextDelta
from agent_runtime.agent.model import UnconfiguredModel
from agent_runtime.agent.prompt import AgentContext
from agent_runtime.sessions.errors import RuntimeSessionError
from agent_runtime.sessions.schemas.common import BlockType, ContractModel, JsonObject
from agent_runtime.sessions.schemas.release import AgentSnapshotV1
from agent_runtime.sessions.services.chatflow_turns import knowledge_base_ids_of
from agent_runtime.sessions.services.debug.activity import activity_view
from agent_runtime.sessions.services.debug.result import build_result, iso
from agent_runtime.sessions.services.debug.stub import StubModel

# The button-press summary is shared with real turns so a debug run behaves like one.
from agent_runtime.sessions.services.message_turns import interaction_summary
from agent_runtime.tools.kit import TurnWorld
from agent_runtime.tools.knowledge import KnowledgeShowParams
from agent_runtime.tools.toolbox import open_turn
from agent_runtime.workflow.budget import Budget
from agent_runtime.workflow.constants import EXPLAIN_OUTCOME, INTERACTION_OUTCOMES
from agent_runtime.workflow.events import NodeFinished, NodeStarted
from agent_runtime.workflow.executor import WorkflowRun, run_workflow
from agent_runtime.workflow.flows import ROUTER_ID, compile_chatflow
from agent_runtime.workflow.ports import NullProfilePort, Ports
from agent_runtime.workflow.scope import Scope

_OUTCOMES = {**INTERACTION_OUTCOMES, "explain_result": EXPLAIN_OUTCOME}
_BLOCK_TYPES = list(get_args(BlockType))  # a debug run's client supports every block type

Emit = Callable[[str, dict], None]
StopCheck = Callable[[], bool]

logger = logging.getLogger(__name__)


class DebugInteraction(ContractModel):
    action: str
    outcome: str | None = None
    option_id: str | None = None


class DebugState(ContractModel):
    profile: JsonObject = Field(default_factory=dict)
    result: JsonObject | None = None
    conv: JsonObject = Field(default_factory=dict)
    activity: JsonObject | None = None
    # sys.turn_index the run sees: 0 is a conversation's first turn; a later turn skips first-turn triggers.
    turn_index: Annotated[int, Field(strict=True, ge=0, le=1000)] = 0


class DebugRequest(ContractModel):
    message: Annotated[str, Field(min_length=1, max_length=4000)] | None = None
    interaction: DebugInteraction | None = None
    state: DebugState = DebugState()
    llm_stubs: dict[str, Any] = Field(default_factory=dict)
    stop_after: Literal["route"] | None = None  # route only: the Nghiệp vụ tab's routing test

    @model_validator(mode="after")
    def one_input(self) -> "DebugRequest":
        if (self.message is None) == (self.interaction is None):
            raise ValueError("exactly one of message or interaction")
        return self


class DebugRunService:
    def __init__(self, models: Callable[[str], Any], knowledge=None, *, clock: Callable[[], float] = time.monotonic,
                 now: Callable[[], datetime] = lambda: datetime.now(UTC), strict_knowledge: bool = False):
        self.models, self.knowledge, self._clock, self._now = models, knowledge, clock, now
        # strict: an unreachable knowledge store is a 503, not a silently emptier run (persona gate must not blame the stubs).
        self._strict_knowledge = strict_knowledge

    def run(self, content: dict, request: dict, emit: Emit | None = None, should_stop: StopCheck | None = None) -> dict:
        return self.prepare(content, request)(emit, should_stop)

    def prepare(self, content: dict, request: dict) -> Callable[..., dict]:
        """Validates now (so a bad request is a plain 422); the returned ``work(emit, should_stop)`` does the run."""
        try:
            agent = AgentSnapshotV1.model_validate(content)
            parsed = DebugRequest.model_validate(request)
        except ValidationError:
            raise RuntimeSessionError(422, "INVALID_INPUT") from None
        if agent.mode != "chatflow" or agent.workflow is None:
            raise RuntimeSessionError(422, "INVALID_INPUT")
        view = activity_view(parsed.state.activity)

        def work(emit: Emit | None = None, should_stop: StopCheck | None = None) -> dict:
            return self._execute(agent, parsed, view, emit, should_stop)
        return work

    def _fields(self, kb_ids) -> dict:
        if self.knowledge is None or not kb_ids:
            return {}
        try:
            return self.knowledge.fields(sorted(kb_ids))
        except Exception as error:
            if self._strict_knowledge:
                logger.error("debug run: knowledge store unavailable (%s)", type(error).__name__)  # type only: no DB URL
                raise RuntimeSessionError(503, "SERVICE_UNAVAILABLE", {"kind": "dependency_down"}) from None
            logger.warning("debug run: knowledge fields unavailable (%s)", type(error).__name__)
            return {}  # an unreachable knowledge store degrades the run, as in a real turn

    def _execute(self, agent: AgentSnapshotV1, request: DebugRequest, view, emit: Emit | None,
                 should_stop: StopCheck | None) -> dict:
        created = self._now()
        sink = emit or (lambda name, data: None)
        workflow = compile_chatflow(agent.workflow)
        deadline = self._clock() + agent.limits.turn_timeout_ms / 1000
        base = self.models(agent.model.provider) if agent.model else UnconfiguredModel()
        stubs = request.llm_stubs
        activity, phase, display_name, question = view
        interaction = request.interaction
        outcome = "none"
        user_text = request.message or ""
        if interaction is not None:
            outcome = interaction.outcome or _OUTCOMES.get(interaction.action, "none")
            user_text = interaction_summary(interaction.action, display_name=display_name,
                                            option_id=interaction.option_id)
        scope = Scope(sys={"query": request.message or "", "interaction": interaction.action if interaction else None,
                           "interaction_outcome": outcome, "turn_index": request.state.turn_index, "client_blocks": _BLOCK_TYPES,
                           "activity_status": activity.state.status if activity else None},
                      conv=request.state.conv, profile=request.state.profile, result=request.state.result,
                      variables=workflow.variables)
        fields = self._fields(knowledge_base_ids_of(agent))
        state_view = SimpleNamespace(agent=agent, activity=activity, result_card=request.state.result)
        show = agent.tool("knowledge.show")
        ports = Ports(agent=agent, model=base,
                      model_for=lambda node_id: StubModel(stubs[node_id]) if node_id in stubs else base,
                      tools=open_turn(TurnWorld(state_view, self.knowledge, fields)),
                      knowledge=self.knowledge, knowledge_fields=fields,
                      show_params=KnowledgeShowParams.model_validate(show.params) if show else None,
                      profile=NullProfilePort(),
                      agent_context=AgentContext(today=date.today(), phase=phase, display_name=display_name,
                                                 current_question=question),
                      user_text=user_text)
        budget = Budget(workflow.budget, clock=self._clock, deadline=deadline)
        current: dict[str, Any] = {"type": None, "held": []}

        def on_event(event) -> None:
            if isinstance(event, NodeStarted):
                current.update(type=event.type, held=[])
                sink("workflow.node_started", {"event": "workflow.node_started", "node_id": event.node_id,
                                               "type": event.type, "order": event.order,
                                               "started_at": iso(self._now())})
            elif isinstance(event, NodeFinished):
                sink("workflow.node_finished", {"event": "workflow.node_finished", "node_id": event.node_id,
                                                "handle": event.handle, "duration_ms": event.duration_ms,
                                                "llm_calls": event.llm_calls,
                                                "tokens": {"input": event.input_tokens, "output": event.output_tokens},
                                                "error": event.error})
                for text in current["held"]:  # an answer's text is the reply: it follows the node that wrote it
                    sink("delta", {"event": "delta", "text": text})
                current.update(type=None, held=[])
            elif isinstance(event, TextDelta):
                if current["type"] == "answer":
                    current["held"].append(event.text)
                else:  # model nodes stream live, inside their started/finished pair
                    sink("delta", {"event": "delta", "text": event.text})

        if request.stop_after == "route" and workflow.entry != ROUTER_ID:  # one flow: nothing to route, no model call
            only = agent.workflow.flows[0].id
            empty = WorkflowRun("completed", (), (), (), scope.conv_values())
            return build_result(empty, workflow, created, stubs, route={"flow": only, "method": "single"})
        run = run_workflow(workflow, scope, ports, budget=budget, on_event=on_event, should_stop=should_stop,
                           reply_required=interaction is None,
                           halt_after=ROUTER_ID if request.stop_after == "route" else None)
        return build_result(run, workflow, created, stubs)
