"""Comprehensive tests for major selection handler, profile ranking and outcome (DEC-26, FR-WFL-08)."""
from dataclasses import make_dataclass
from datetime import date, datetime, timezone
from types import SimpleNamespace

from agent_runtime.evaluations.services.compatibility import PILOT_ENGINE_REGISTRY
from agent_runtime.sessions.schemas.release import AgentSnapshotV1
from agent_runtime.sessions.schemas.turn import SelectMajorsInteraction, SelectMajorsPayload
from agent_runtime.sessions.services import chatflow_turns
from agent_runtime.sessions.services.chatflow_turns import (
    interaction_outcome,
    run_interaction_turn,
)
from agent_runtime.sessions.services.message_turns import interaction_summary
from agent_runtime.sessions.services.turn_handlers import PinnedAssessmentEngine, TurnHandler
from agent_runtime.sessions.services.turn_response import finalize_turn
from agent_runtime.workflow.executor import WorkflowRun
from agent_runtime.workflow.ports import InMemoryProfilePort, NullProfilePort
from tests.helpers.turns import make_turn_snapshot
from tests.unit.workflow.helpers import MIN

COMMITTED_AT = datetime(2026, 10, 20, 3, 0, 5, tzinfo=timezone.utc)
INPUT_ID = "b" * 32


# ---------------------------------------------------------------------------
# Unit tests: NullProfilePort & InMemoryProfilePort
# ---------------------------------------------------------------------------

def test_null_profile_port_record_career_groups():
    null_port = NullProfilePort()
    assert null_port.snapshot() == {}
    assert null_port.record_career_groups(["cntt", "marketing"]) == 0


def test_in_memory_profile_port_ranking_and_revision():
    port = InMemoryProfilePort(initial_revision=1)
    assert port.revision == 1
    assert port.snapshot() == {"profile_revision": 1}

    # 1. Record 3 majors -> revision increments to 2
    rev = port.record_career_groups(["cntt", "marketing", "kinh_te"])
    assert rev == 2
    assert port.revision == 2
    assert port.snapshot()["interested_career_groups"] == ["cntt", "marketing", "kinh_te"]

    # 2. Record same majors in same order -> revision does NOT increment
    rev = port.record_career_groups(["cntt", "marketing", "kinh_te"])
    assert rev == 2
    assert port.revision == 2

    # 3. Record same majors with duplicates -> deduplicated preserving order -> revision does NOT increment
    rev = port.record_career_groups(["cntt", "marketing", "cntt", "kinh_te"])
    assert rev == 2
    assert port.revision == 2
    assert port.snapshot()["interested_career_groups"] == ["cntt", "marketing", "kinh_te"]

    # 4. Change order -> semantic change -> revision increments to 3 (DEC-26)
    rev = port.record_career_groups(["marketing", "cntt", "kinh_te"])
    assert rev == 3
    assert port.revision == 3
    assert port.snapshot()["interested_career_groups"] == ["marketing", "cntt", "kinh_te"]

    # 5. Provide more than 3 majors -> truncates to top 3 preserving order
    # Here ["marketing", "cntt", "kinh_te", "du_lich"] -> top 3 is ["marketing", "cntt", "kinh_te"] (no change)
    rev = port.record_career_groups(["marketing", "cntt", "kinh_te", "du_lich"])
    assert rev == 3
    assert port.revision == 3

    # 6. Change top 3 majors
    rev = port.record_career_groups(["du_lich", "marketing", "cntt"])
    assert rev == 4
    assert port.revision == 4
    assert port.snapshot()["interested_career_groups"] == ["du_lich", "marketing", "cntt"]


# ---------------------------------------------------------------------------
# Unit tests: TurnHandler.prepare with select_majors
# ---------------------------------------------------------------------------

def test_turn_handler_prepare_select_majors(valid_v2_doc):
    profile = InMemoryProfilePort(initial_revision=1)
    handler = TurnHandler(PinnedAssessmentEngine(PILOT_ENGINE_REGISTRY), profile=profile)

    snapshot = make_turn_snapshot(valid_v2_doc)
    request = SelectMajorsInteraction(
        type="interaction",
        expected_revision=1,
        idempotency_key="key-select-1",
        activity_id=snapshot.activity.id,
        action="select_majors",
        payload=SelectMajorsPayload(major_ids=("cntt", "marketing", "kinh_te")),
    )

    draft = handler.prepare(snapshot, request)
    assert draft.completion is None
    # Activity state is preserved
    assert draft.next_state.status == snapshot.activity.state.status

    # Profile was updated and revision was bumped
    assert profile.revision == 2
    assert profile.snapshot()["interested_career_groups"] == ["cntt", "marketing", "kinh_te"]


# ---------------------------------------------------------------------------
# Unit tests: finalize_turn with select_majors
# ---------------------------------------------------------------------------

def test_finalize_turn_select_majors(valid_v2_doc):
    profile = InMemoryProfilePort(initial_revision=1)
    handler = TurnHandler(PinnedAssessmentEngine(PILOT_ENGINE_REGISTRY), profile=profile)

    snapshot = make_turn_snapshot(valid_v2_doc)
    request = SelectMajorsInteraction(
        type="interaction",
        expected_revision=1,
        idempotency_key="key-select-2",
        activity_id=snapshot.activity.id,
        action="select_majors",
        payload=SelectMajorsPayload(major_ids=("cntt", "marketing", "kinh_te")),
    )

    draft = handler.prepare(snapshot, request)
    output = finalize_turn(snapshot, request, draft, COMMITTED_AT, input_message_id=INPUT_ID)

    user, assistant = output.patch.append_messages
    assert user.role == "user"
    assert user.message_id == INPUT_ID
    assert user.interaction.action == "select_majors"
    assert user.interaction.major_ids == ("cntt", "marketing", "kinh_te")
    assert user.interaction.question_id is None
    assert user.interaction.option_id is None

    assert assistant.role == "assistant"
    assert len(assistant.blocks) >= 1
    assert output.result.turn_id == user.turn_id == assistant.turn_id


# ---------------------------------------------------------------------------
# Unit tests: interaction_summary & outcome
# ---------------------------------------------------------------------------

def test_interaction_summary_for_select_majors():
    summary = interaction_summary("select_majors", major_ids=["cntt", "marketing", "kinh_te"])
    assert summary == "[Học sinh chọn ngành: cntt, marketing, kinh_te]"

    summary_empty = interaction_summary("select_majors", major_ids=[])
    assert summary_empty == "[Học sinh chọn ngành: ]"


def test_interaction_outcome_for_select_majors():
    req = SimpleNamespace(action="select_majors")
    draft_no_comp = SimpleNamespace(completion=None)
    assert interaction_outcome(req, draft_no_comp) == "selection_made"


# ---------------------------------------------------------------------------
# Integration tests: Chatflow Scope exposes profile.interested_career_groups & outcome
# ---------------------------------------------------------------------------

class Activity(SimpleNamespace):
    def model_copy(self, *, update):
        return Activity(**{**vars(self), **update})


def replace_snapshot(namespace):
    fields = vars(namespace)
    return make_dataclass("Snap", list(fields), frozen=True)(**fields)


def chatflow_agent():
    return AgentSnapshotV1.model_validate(MIN)


def captured_scope(monkeypatch):
    seen = []

    def capture(workflow, scope, ports, **kwargs):
        seen.append((scope, ports))
        return WorkflowRun("completed", (), (), (), scope.conv_values())

    monkeypatch.setattr(chatflow_turns, "run_workflow", capture)
    return seen


def test_chatflow_interaction_turn_exposes_profile_and_selection_made(monkeypatch):
    seen = captured_scope(monkeypatch)
    profile = InMemoryProfilePort(initial_revision=1)
    profile.record_career_groups(["cntt", "marketing", "kinh_te"])

    activity_view = Activity(state=SimpleNamespace(status="completed", display_name="Nam", current_question=None))
    parent = SimpleNamespace(
        conv_vars={"stage": "pick_majors"},
        capability_snapshot=SimpleNamespace(
            supported_blocks=(SimpleNamespace(type="text"), SimpleNamespace(type="markdown"))
        ),
        display_name="Nam",
    )
    chat = replace_snapshot(
        SimpleNamespace(
            agent=chatflow_agent(),
            parent=parent,
            activity=activity_view,
            result_card=None,
            current_result=None,
            history=(),
            today=date(2026, 11, 10),
            user_turns=1,
        )
    )

    req = SelectMajorsInteraction(
        type="interaction",
        expected_revision=1,
        idempotency_key="key-select-3",
        activity_id="act-1",
        action="select_majors",
        payload=SelectMajorsPayload(major_ids=("cntt", "marketing", "kinh_te")),
    )
    draft = SimpleNamespace(
        completion=None,
        next_state=SimpleNamespace(status="completed", display_name="Nam", current_question=None),
    )

    run_interaction_turn(
        chat,
        req,
        draft,
        model=None,
        toolbox=None,
        knowledge_port=None,
        profile=profile,
        clock=lambda: 0.0,
    )

    assert len(seen) == 1
    scope, ports = seen[0]

    # Verify Scope values (DEC-26, FR-WFL-08)
    assert scope.get("sys.interaction") == "select_majors"
    assert scope.get("sys.interaction_outcome") == "selection_made"
    assert scope.get("profile.interested_career_groups") == ["cntt", "marketing", "kinh_te"]
    assert scope.get("profile.profile_revision") == 2
    assert ports.user_text == "[Học sinh chọn ngành: cntt, marketing, kinh_te]"
