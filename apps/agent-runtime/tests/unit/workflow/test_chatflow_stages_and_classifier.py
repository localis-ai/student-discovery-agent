"""Tests for Chatflow conversation stages and intent classifier labels (DEC-28, FR-WFL-02, FR-WFL-07)."""
import copy

import pytest

from agent_runtime.agent.model import FakeModel, ModelReply
from agent_runtime.workflow.constants import (
    JOURNEY_CLASSIFIER_LABELS,
    STAGE_CLASSIFIER_LABELS,
    STAGE_VALUES,
    STAGE_VARIABLE,
)
from agent_runtime.workflow.executor import run_workflow
from agent_runtime.workflow.validator import validate_workflow
from tests.helpers.chatflow import chatflow_content
from tests.unit.workflow.helpers import budget_for, ports_for, run_node, scope_for, workflow


def codes(findings):
    return {(item.path, item.code) for item in findings}


def check(wf, kb=None, **agent_kwargs):
    content = chatflow_content(copy.deepcopy(wf))
    content.update(agent_kwargs)
    return validate_workflow(content["workflow"], content, kb or {})


def edge(id, source, handle, target):
    return {"id": id, "source": source, "source_handle": handle, "target": target}


# ---------------------------------------------------------------------------
# 1. Verification of DEC-28 Stage Enum Values & Canonical Definitions
# ---------------------------------------------------------------------------

def test_dec28_stage_values_include_all_required_stages():
    expected = ("welcome", "assessment", "explore", "pick_majors", "need", "fee", "job", "followup")
    assert STAGE_VALUES == expected
    assert STAGE_VARIABLE["name"] == "stage"
    assert STAGE_VARIABLE["type"] == "enum"
    assert STAGE_VARIABLE["default"] == "welcome"
    assert set(expected).issubset(set(STAGE_VARIABLE["values"]))


@pytest.mark.parametrize("stage", [
    "welcome", "assessment", "explore", "pick_majors", "need", "fee", "job", "followup",
])
def test_validator_accepts_all_dec28_stages_in_assign(stage):
    wf = {
        "entry": "start",
        "variables": [STAGE_VARIABLE],
        "nodes": [
            {"id": "start", "type": "start"},
            {"id": "set_stage", "type": "assign", "config": {
                "assignments": [{"variable": "conv.stage", "value": stage}],
            }},
            {"id": "reply", "type": "answer", "config": {"text": "Giai đoạn {{conv.stage}}"}},
        ],
        "edges": [
            edge("e1", "start", "next", "set_stage"),
            edge("e2", "set_stage", "next", "reply"),
        ],
    }
    issues = check(wf)
    assert issues == []


@pytest.mark.parametrize("bad_stage", ["invalid_stage", "unknown", "fee_and_job", 123, True])
def test_validator_rejects_invalid_stage_in_assign(bad_stage):
    wf = {
        "entry": "start",
        "variables": [STAGE_VARIABLE],
        "nodes": [
            {"id": "start", "type": "start"},
            {"id": "set_stage", "type": "assign", "config": {
                "assignments": [{"variable": "conv.stage", "value": bad_stage}],
            }},
            {"id": "reply", "type": "answer", "config": {"text": "Giai đoạn {{conv.stage}}"}},
        ],
        "edges": [
            edge("e1", "start", "next", "set_stage"),
            edge("e2", "set_stage", "next", "reply"),
        ],
    }
    found = codes(check(wf))
    assert ("workflow.nodes[1].config.assignments[0].value", "workflow_assign_invalid") in found


@pytest.mark.parametrize("stage", [
    "welcome", "assessment", "explore", "pick_majors", "need", "fee", "job", "followup",
])
def test_validator_accepts_all_dec28_stages_in_if_else(stage):
    wf = {
        "entry": "start",
        "variables": [STAGE_VARIABLE],
        "nodes": [
            {"id": "start", "type": "start"},
            {"id": "gate", "type": "if_else", "config": {
                "condition": {"==": [{"var": "conv.stage"}, stage]},
            }},
            {"id": "reply_true", "type": "answer", "config": {"text": "Đúng giai đoạn"}},
            {"id": "reply_false", "type": "answer", "config": {"text": "Khác giai đoạn"}},
        ],
        "edges": [
            edge("e1", "start", "next", "gate"),
            edge("e2", "gate", "true", "reply_true"),
            edge("e3", "gate", "false", "reply_false"),
        ],
    }
    issues = check(wf)
    assert issues == []


@pytest.mark.parametrize("bad_stage", ["nonexistent", "random_phase", 456])
def test_validator_rejects_invalid_stage_in_if_else(bad_stage):
    wf = {
        "entry": "start",
        "variables": [STAGE_VARIABLE],
        "nodes": [
            {"id": "start", "type": "start"},
            {"id": "gate", "type": "if_else", "config": {
                "condition": {"==": [{"var": "conv.stage"}, bad_stage]},
            }},
            {"id": "reply_true", "type": "answer", "config": {"text": "Đúng"}},
            {"id": "reply_false", "type": "answer", "config": {"text": "Sai"}},
        ],
        "edges": [
            edge("e1", "start", "next", "gate"),
            edge("e2", "gate", "true", "reply_true"),
            edge("e3", "gate", "false", "reply_false"),
        ],
    }
    found = codes(check(wf))
    assert ("workflow.nodes[1].config.condition", "workflow_type_mismatch") in found


# ---------------------------------------------------------------------------
# 2. Verification of Classifier Labels & Unwired Labels (FR-WFL-02, FR-WFL-07)
# ---------------------------------------------------------------------------

def test_journey_classifier_labels_specification():
    ids = [label["id"] for label in JOURNEY_CLASSIFIER_LABELS]
    assert ids == ["hoi_hoc_phi", "viec_lam", "chon_nganh", "tu_van_nhu_cau", "hoi_tiep"]

    stage_label_ids = [label["id"] for label in STAGE_CLASSIFIER_LABELS]
    assert stage_label_ids == ["fee", "job", "pick_majors", "need", "followup"]


def build_journey_classifier_flow(omit_handle=None):
    labels = list(JOURNEY_CLASSIFIER_LABELS)
    edges = [
        edge("e0", "start", "next", "classify"),
        edge("e_other", "classify", "other", "reply"),
    ]
    for idx, label in enumerate(labels):
        handle = label["id"]
        if handle != omit_handle:
            edges.append(edge(f"e_lbl_{idx}", "classify", handle, "reply"))
    if omit_handle == "other":
        edges = [e for e in edges if e["source_handle"] != "other"]

    nodes = [
        {"id": "start", "type": "start"},
        {"id": "classify", "type": "intent_classifier", "config": {"labels": labels}},
        {"id": "reply", "type": "answer", "config": {"text": "Kết quả"}},
    ]
    return {"entry": "start", "variables": [STAGE_VARIABLE], "nodes": nodes, "edges": edges}


def test_validator_passes_when_all_journey_labels_are_wired():
    wf = build_journey_classifier_flow(omit_handle=None)
    issues = check(wf)
    assert issues == []


@pytest.mark.parametrize("idx,label_id", enumerate(["hoi_hoc_phi", "viec_lam", "chon_nganh", "tu_van_nhu_cau", "hoi_tiep"]))
def test_validator_reports_unwired_classifier_label_at_exact_position(idx, label_id):
    wf = build_journey_classifier_flow(omit_handle=label_id)
    issues = check(wf)
    found = codes(issues)
    expected_path = f"workflow.nodes[1].config.labels[{idx}]"
    assert (expected_path, "workflow_unwired_label") in found

    # Verify message mentions the missing label handle
    issue = next(i for i in issues if i.path == expected_path)
    assert label_id in issue.message


def test_validator_reports_unwired_other_handle_on_classifier_node():
    wf = build_journey_classifier_flow(omit_handle="other")
    issues = check(wf)
    found = codes(issues)
    expected_path = "workflow.nodes[1]"
    assert (expected_path, "workflow_unwired_label") in found

    issue = next(i for i in issues if i.path == expected_path and i.code == "workflow_unwired_label")
    assert "other" in issue.message


def test_unwired_error_handle_remains_optional():
    # Neither e_error is added, nor does validator complain about error
    wf = build_journey_classifier_flow(omit_handle=None)
    issues = check(wf)
    assert not any(i.code == "workflow_unwired_label" for i in issues)


# ---------------------------------------------------------------------------
# 3. Intent Classifier Node Execution with Journey Labels
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("label_id", ["hoi_hoc_phi", "viec_lam", "chon_nganh", "tu_van_nhu_cau", "hoi_tiep"])
def test_classifier_node_executes_and_returns_journey_label(label_id):
    node_dict = {
        "id": "classify",
        "type": "intent_classifier",
        "config": {"labels": list(JOURNEY_CLASSIFIER_LABELS)},
    }
    wf = workflow([node_dict], [], variables=[STAGE_VARIABLE])
    model = FakeModel(ModelReply(text=label_id))
    spec, result, _, _ = run_node(node_dict, wf, model=model, scope=scope_for(wf, query="câu hỏi của học sinh"))
    assert result.handle == label_id
    assert result.output == {"label": label_id}


def test_classifier_node_fallback_to_other_on_unrecognized():
    node_dict = {
        "id": "classify",
        "type": "intent_classifier",
        "config": {"labels": list(JOURNEY_CLASSIFIER_LABELS)},
    }
    wf = workflow([node_dict], [], variables=[STAGE_VARIABLE])
    model = FakeModel(ModelReply(text="hoan_toan_xa_la"))
    spec, result, _, _ = run_node(node_dict, wf, model=model, scope=scope_for(wf, query="chào bot"))
    assert result.handle == "other"
    assert result.output == {"label": "other"}


# ---------------------------------------------------------------------------
# 4. End-to-End Chatflow Workflow Execution with Stage Transitions
# ---------------------------------------------------------------------------

def test_chatflow_journey_stage_transitions_end_to_end():
    labels = list(STAGE_CLASSIFIER_LABELS)  # fee, job, pick_majors, need, followup
    nodes = [
        {"id": "start", "type": "start"},
        {"id": "ask", "type": "intent_classifier", "config": {"labels": labels}},
        {"id": "set_fee", "type": "assign", "config": {"assignments": [{"variable": "conv.stage", "value": "fee"}]}},
        {"id": "set_job", "type": "assign", "config": {"assignments": [{"variable": "conv.stage", "value": "job"}]}},
        {"id": "set_pick", "type": "assign", "config": {"assignments": [{"variable": "conv.stage", "value": "pick_majors"}]}},
        {"id": "set_need", "type": "assign", "config": {"assignments": [{"variable": "conv.stage", "value": "need"}]}},
        {"id": "set_follow", "type": "assign", "config": {"assignments": [{"variable": "conv.stage", "value": "followup"}]}},
        {"id": "reply", "type": "answer", "config": {"text": "Giai đoạn hiện tại: {{conv.stage}}"}},
    ]
    edges = [
        ("start", "next", "ask"),
        ("ask", "fee", "set_fee"),
        ("ask", "job", "set_job"),
        ("ask", "pick_majors", "set_pick"),
        ("ask", "need", "set_need"),
        ("ask", "followup", "set_follow"),
        ("ask", "other", "reply"),
        ("set_fee", "next", "reply"),
        ("set_job", "next", "reply"),
        ("set_pick", "next", "reply"),
        ("set_need", "next", "reply"),
        ("set_follow", "next", "reply"),
    ]

    wf = workflow(nodes, edges, variables=[STAGE_VARIABLE])

    # 1. Validate workflow cleanly
    wf_dict = wf.model_dump(mode="json")
    issues = check(wf_dict)
    assert issues == []

    # 2. Simulate model answering "fee" -> conv.stage becomes "fee"
    scope = scope_for(wf, query="học phí thế nào", conv={"stage": "welcome"})
    model = FakeModel(ModelReply(text="fee"))
    run = run_workflow(wf, scope, ports_for(model=model), budget=budget_for(wf))
    assert run.status == "completed"
    assert run.conv == {"stage": "fee"}

    # 3. Simulate model answering "job" -> conv.stage becomes "job"
    scope = scope_for(wf, query="cơ hội việc làm", conv={"stage": "welcome"})
    model = FakeModel(ModelReply(text="job"))
    run = run_workflow(wf, scope, ports_for(model=model), budget=budget_for(wf))
    assert run.status == "completed"
    assert run.conv == {"stage": "job"}

    # 4. Simulate model answering "pick_majors" -> conv.stage becomes "pick_majors"
    scope = scope_for(wf, query="chọn ngành", conv={"stage": "welcome"})
    model = FakeModel(ModelReply(text="pick_majors"))
    run = run_workflow(wf, scope, ports_for(model=model), budget=budget_for(wf))
    assert run.status == "completed"
    assert run.conv == {"stage": "pick_majors"}

    # 5. Simulate model answering unrecognized -> other -> conv.stage stays "welcome"
    scope = scope_for(wf, query="không rõ", conv={"stage": "welcome"})
    model = FakeModel(ModelReply(text="khong_biet"))
    run = run_workflow(wf, scope, ports_for(model=model), budget=budget_for(wf))
    assert run.status == "completed"
    assert run.conv == {"stage": "welcome"}
