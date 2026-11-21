"""Unit tests for the Opening Journey workflow and high-school persona case (T32, DEC-26, 28, FR-WFL-16)."""

from agent_runtime.agent.model import UnconfiguredModel
from agent_runtime.agent.validation import AgentSnapshotValidator
from agent_runtime.evaluations.services.persona import PersonaRunner, stale_cases
from agent_runtime.sessions.schemas.release import AgentSnapshotV1
from agent_runtime.sessions.services.debug_runs import DebugRunService
from agent_runtime.workflow.constants import STAGE_VALUES
from agent_runtime.workflow.opening_journey import (
    opening_journey_workflow,
    thpt_student_opening_case,
)
from tests.helpers.chat import _agent_content


def thpt_student_direct_case() -> dict:
    """Alternative persona case: student directly says they want to do the assessment."""
    return {
        "id": "thpt_student_direct_start",
        "title": "Học sinh THPT chọn làm bài trực tiếp",
        "mandatory": True,
        "initial_state": {
            "conv": {"stage": "welcome"},
            "profile": {"entry_level": "thpt_grade_11"},
        },
        "turns": [
            {
                "input": {"text": "Mình muốn làm bài trắc nghiệm tính cách"},
                "llm_stubs": {"intent": "lam_bai"},
                "expect": {
                    "path": [
                        "start",
                        "check_completed",
                        "check_explain",
                        "in_test",
                        "check_confirmed",
                        "intent",
                        "begin_test",
                        "start_test",
                        "answer_start",
                    ],
                    "conv": {"stage": "assessment"},
                    "status": "completed",
                },
            }
        ],
    }


def make_opening_content(workflow=None, persona_cases=None) -> dict:
    content = _agent_content()
    # Enable necessary tools for the opening journey nodes
    content["tools"] = [
        {
            "name": "assessment.start",
            "version": 1,
            "params": {
                "experiences": [
                    {
                        "experience_id": "exp_riasec",
                        "algorithm_profile": "riasec.mean.bounds.v2",
                        "label": "Bài khám phá tính cách",
                    }
                ]
            },
        },
        {"name": "assessment.set_name", "version": 1},
        {"name": "assessment.current_question", "version": 1},
        {"name": "assessment.propose_answer", "version": 1},
        {"name": "result.explain", "version": 1},
        {"name": "ui.suggest_replies", "version": 1},
    ]
    wf = workflow or opening_journey_workflow()
    cases = persona_cases or [thpt_student_opening_case(), thpt_student_direct_case()]
    content.update({
        "mode": "chatflow",
        "workflow": wf,
        "persona_cases": cases,
    })
    return content


def test_opening_workflow_structure_and_constants():
    wf = opening_journey_workflow()
    assert wf["entry"] == "start"
    node_ids = {node["id"] for node in wf["nodes"]}
    assert {
        "start",
        "check_completed",
        "to_explore",
        "answer_completed",
        "check_explain",
        "explain_agent",
        "to_pick_majors",
        "answer_explain",
        "in_test",
        "assess",
        "answer_assess",
        "check_confirmed",
        "check_thpt_level",
        "begin_test",
        "start_test",
        "answer_start",
        "answer_other_level",
        "intent",
        "prof",
        "answer_prof",
        "answer_opening",
    }.issubset(node_ids)

    # Check stage variable
    assert wf["variables"][0]["name"] == "stage"
    assert tuple(wf["variables"][0]["values"]) == STAGE_VALUES


def test_opening_journey_snapshot_validation():
    content = make_opening_content()
    checker = AgentSnapshotValidator(knowledge=None, experiences=None, environment="demo")
    result = checker.validate(content)
    assert result.valid is True
    assert result.issues == ()
    assert stale_cases(AgentSnapshotV1.model_validate(content)) == []


def test_thpt_student_opening_persona_case_passes():
    content = make_opening_content()
    runner = PersonaRunner(DebugRunService(models=lambda provider: UnconfiguredModel(), knowledge=None))
    snapshot = AgentSnapshotV1.model_validate(content)
    report = runner.run(snapshot, content)

    # Acceptance Criteria: Persona "học sinh THPT làm bài từ đầu" pass
    thpt_case = next(c for c in report.cases if c.id == "thpt_student_opening_journey")
    assert thpt_case.passed is True
    assert thpt_case.mismatches == ()

    # Direct case also pass
    direct_case = next(c for c in report.cases if c.id == "thpt_student_direct_start")
    assert direct_case.passed is True
    assert direct_case.mismatches == ()


def test_debug_run_opening_intent_branching():
    content = make_opening_content()
    debug = DebugRunService(models=lambda provider: UnconfiguredModel(), knowledge=None)

    # 1. Intent kham_pha_nganh -> goes to answer_opening
    res_nganh = debug.run(
        content,
        {
            "message": "Cho em tìm hiểu ngành nghề",
            "llm_stubs": {"intent": "kham_pha_nganh"},
            "state": {"conv": {"stage": "welcome"}},
        },
    )
    assert res_nganh["status"] == "completed"
    assert res_nganh["path"] == [
        "start",
        "check_completed",
        "check_explain",
        "in_test",
        "check_confirmed",
        "intent",
        "answer_opening",
    ]

    # 2. Intent hoi_hoc_phi -> goes to answer_opening
    res_fee = debug.run(
        content,
        {
            "message": "Học phí bao nhiêu",
            "llm_stubs": {"intent": "hoi_hoc_phi"},
            "state": {"conv": {"stage": "welcome"}},
        },
    )
    assert res_fee["status"] == "completed"
    assert res_fee["path"] == [
        "start",
        "check_completed",
        "check_explain",
        "in_test",
        "check_confirmed",
        "intent",
        "answer_opening",
    ]

    # 3. Intent other -> goes to answer_opening
    res_other = debug.run(
        content,
        {
            "message": "Thời tiết hôm nay thế nào",
            "llm_stubs": {"intent": "other"},
            "state": {"conv": {"stage": "welcome"}},
        },
    )
    assert res_other["status"] == "completed"
    assert res_other["path"] == [
        "start",
        "check_completed",
        "check_explain",
        "in_test",
        "check_confirmed",
        "intent",
        "answer_opening",
    ]


def test_non_thpt_level_routes_to_other_level():
    content = make_opening_content()
    debug = DebugRunService(models=lambda provider: UnconfiguredModel(), knowledge=None)

    # Student with entry_level = "cao_dang" confirms profile
    res = debug.run(
        content,
        {
            "interaction": {"action": "confirm_profile", "outcome": "profile_confirmed"},
            "state": {
                "conv": {"stage": "welcome"},
                "profile": {"entry_level": "cao_dang"},
            },
        },
    )
    assert res["status"] == "completed"
    assert res["path"] == [
        "start",
        "check_completed",
        "check_explain",
        "in_test",
        "check_confirmed",
        "check_thpt_level",
        "answer_other_level",
    ]
    # conv.stage stays welcome because begin_test was not reached
    assert "stage" not in [e.get("variable") for e in res["effects"] if e.get("kind") == "assign_conv"]


def test_profile_propose_none_branch_routes_to_answer_opening():
    content = make_opening_content()
    debug = DebugRunService(models=lambda provider: UnconfiguredModel(), knowledge=None)

    # Model extraction has no valid fields -> prof goes to none -> answer_opening
    res = debug.run(
        content,
        {
            "message": "Em muốn tâm sự",
            "llm_stubs": {
                "intent": "tiep_tuc",
                "prof": {},  # empty extracted fields -> none handle
            },
            "state": {"conv": {"stage": "welcome"}},
        },
    )
    assert res["status"] == "completed"
    assert res["path"] == [
        "start",
        "check_completed",
        "check_explain",
        "in_test",
        "check_confirmed",
        "intent",
        "prof",
        "answer_opening",
    ]
