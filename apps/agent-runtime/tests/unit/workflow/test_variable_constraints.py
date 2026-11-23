import pytest

import agent_runtime.workflow.nodes  # noqa: F401  (registers the node types)
from agent_runtime.workflow.nodes.base import NodeError
from agent_runtime.workflow.validator import validate_workflow
from tests.unit.workflow.helpers import run_node, scope_for, workflow

SCORE = {"name": "score", "type": "number", "default": 0, "constraints": {"minimum": 0, "maximum": 10}}


def assign_node(value, operation="set"):
    return {"id": "a", "type": "assign", "config": {"assignments": [
        {"variable": "conv.score", "operation": operation, "value": value}]}}


def test_scope_falls_back_to_default_when_a_stored_value_breaks_a_constraint():
    wf = workflow([{"id": "s", "type": "start"}], [], variables=[SCORE])
    assert scope_for(wf, conv={"score": 99}).get("conv.score") == 0
    assert scope_for(wf, conv={"score": 7}).get("conv.score") == 7


def test_assign_takes_the_error_branch_when_the_new_value_breaks_a_constraint():
    node = assign_node(5, operation="add")
    wf = workflow([node], [], variables=[SCORE])
    with pytest.raises(NodeError) as error:
        run_node(node, wf, scope=scope_for(wf, conv={"score": 9}))
    assert error.value.error_type == "invalid_output"
    _, result, scope, _ = run_node(node, wf, scope=scope_for(wf, conv={"score": 4}))
    assert scope.get("conv.score") == 9


def test_validator_reports_a_literal_that_breaks_a_constraint():
    def check(value):
        raw = {
            "entry": "start",
            "variables": [SCORE],
            "nodes": [{"id": "start", "type": "start"}, assign_node(value), {"id": "done", "type": "answer", "config": {"text": "ok"}}],
            "edges": [{"id": "e1", "source": "start", "source_handle": "next", "target": "a"},
                      {"id": "e2", "source": "a", "source_handle": "next", "target": "done"}],
        }
        return validate_workflow(raw, {}, {})

    findings = check(42)
    assert any(f.code == "workflow_assign_invalid" and "ràng buộc" in f.message
               and f.path.endswith("assignments[0].value") for f in findings), findings
    assert not [f for f in check(4) if f.code == "workflow_assign_invalid"]


@pytest.mark.parametrize("bad", [{"maximum": None}, {"maximum": "3"}, {"maximum": True}, {"integer": "yes"}, ["maximum"]])
def test_validator_skips_malformed_constraints_instead_of_hiding_every_finding(bad):
    raw = {
        "entry": "start",
        "variables": [{**SCORE, "constraints": bad}],
        "nodes": [{"id": "start", "type": "start"}, assign_node(42),
                  {"id": "done", "type": "answer", "config": {"text": "ok"}},
                  {"id": "orphan", "type": "answer", "config": {"text": "never reached"}}],
        "edges": [{"id": "e1", "source": "start", "source_handle": "next", "target": "a"},
                  {"id": "e2", "source": "a", "source_handle": "next", "target": "done"}],
    }
    codes = {f.code for f in validate_workflow(raw, {}, {})}
    assert "workflow_unverifiable" not in codes
    assert codes  # the unreachable node is still reported
