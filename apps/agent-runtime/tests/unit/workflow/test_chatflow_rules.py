"""The rules both checkers apply (workflow/rules.py): the schema and the graph validator must agree on every case."""
import pytest
from pydantic import ValidationError

from agent_runtime.sessions.schemas.workflow import Chatflow
from agent_runtime.workflow.rules import (
    cross_flow_duplicates,
    default_flow_routable,
    duplicates,
    flow_id_reserved,
    flow_needs_description,
    node_id_reserved,
)
from agent_runtime.workflow.validator import validate_workflow


def flow(fid, prefix, **extra):
    return {"id": fid, "title": fid, "description": f"hỏi {fid}", "entry": f"{prefix}_s",
            "nodes": [{"id": f"{prefix}_s", "type": "start"},
                      {"id": f"{prefix}_a", "type": "answer", "config": {"text": "x"}}],
            "edges": [{"id": "e1", "source": f"{prefix}_s", "source_handle": "next", "target": f"{prefix}_a"}], **extra}


def chat(*flows, default="a"):
    return {"router": {"default_flow": default}, "flows": list(flows)}


def test_duplicates_yields_every_repeat_and_skips_what_is_not_a_string():
    assert list(duplicates(["a", "b", "a", None, ["x"], "b", "a"])) == [(2, "a"), (5, "b"), (6, "a")]


def test_reserved_ids_are_strings_only():
    assert node_id_reserved("conv") and flow_id_reserved("other")
    assert not node_id_reserved(["conv"]) and not flow_id_reserved({"id": "error"})  # unhashable: no TypeError


@pytest.mark.parametrize(("routable", "description", "needs"), [
    (True, "", True), (True, "   ", True), (True, None, True), ("yes", "", True), (True, "hỏi", False),
    (False, "", False)])
def test_a_routable_flow_needs_a_description(routable, description, needs):
    assert flow_needs_description(routable, description) is needs


def test_default_flow_must_name_a_routable_flow():
    assert default_flow_routable("a", {"a": True})
    assert not default_flow_routable("a", {"a": False})
    assert not default_flow_routable("b", {"a": True})
    assert not default_flow_routable(None, {"a": True})


def test_cross_flow_duplicates_skip_a_repeat_inside_one_flow():
    flows = [("a", ["s", "x", "x"]), ("b", ["t", "x"]), ("c", ["s"])]
    assert list(cross_flow_duplicates(flows)) == [(1, 1, "x", "a"), (2, 0, "s", "a")]


# Each case breaks exactly one shared rule; the schema and the validator must both reject it, with the same code.
CASES = {
    "reserved_node_id": (lambda: chat(flow("a", "a") | {"nodes": [{"id": "conv", "type": "start"}], "entry": "conv",
                                                          "edges": []}), "workflow_node_id_reserved"),
    "reserved_flow_id": (lambda: chat(flow("a", "a"), flow("other", "o")), "workflow_flow_invalid"),
    "routable_without_description": (lambda: chat(flow("a", "a"), flow("b", "b", description=" ")),
                                     "workflow_flow_invalid"),
    "default_not_routable": (lambda: chat(flow("a", "a", routable=False), flow("b", "b")), "workflow_flow_invalid"),
    "default_unknown": (lambda: chat(flow("a", "a"), default="zzz"), "workflow_flow_invalid"),
    "node_id_in_two_flows": (lambda: chat(flow("a", "a"), flow("b", "a")), "workflow_node_id_duplicate"),
    "duplicate_flow_id": (lambda: chat(flow("a", "a"), flow("a", "b")), "duplicate_items"),
}


@pytest.mark.parametrize("name", CASES)
def test_the_schema_and_the_validator_agree(name):
    build, code = CASES[name]
    with pytest.raises(ValidationError) as caught:
        Chatflow.model_validate(build())
    assert code in {error["type"] for error in caught.value.errors()}
    assert code in {finding.code for finding in validate_workflow(build(), {}, {})}


def test_a_clean_chatflow_passes_both():
    raw = chat(flow("a", "a"), flow("b", "b"))
    Chatflow.model_validate(raw)
    assert validate_workflow(raw, {}, {}) == []
