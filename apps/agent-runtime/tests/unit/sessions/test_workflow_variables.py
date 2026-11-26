import pytest
from pydantic import ValidationError

from agent_runtime.sessions.schemas.workflow import ConvVariable, WorkflowNode
from agent_runtime.workflow.variables import value_fits


def var(**overrides):
    return ConvVariable.model_validate({"name": "score", "type": "number", "default": 0, **overrides})


def test_description_is_optional_and_bounded():
    assert var().description is None
    assert var(description="Điểm tạm").description == "Điểm tạm"
    with pytest.raises(ValidationError):
        var(description="x" * 301)


@pytest.mark.parametrize("kind,constraints,good,bad", [
    ("string", {"min_length": 2, "max_length": 3}, "abc", "a"),
    ("string", {"max_length": 3}, "", "abcd"),
    ("number", {"minimum": 0, "maximum": 10}, 10, 10.5),
    ("number", {"integer": True}, 3, 3.5),
    ("string_list", {"max_items": 2}, ["a", "b"], ["a", "b", "c"]),
    ("string_list", {"item_max_length": 2}, ["ab"], ["abc"]),
])
def test_value_fits_applies_constraints(kind, constraints, good, bad):
    assert value_fits(kind, good, None, constraints)
    assert not value_fits(kind, bad, None, constraints)
    assert value_fits(kind, bad)  # without constraints only the type is checked, as before


def test_constraints_must_belong_to_the_type():
    with pytest.raises(ValidationError) as error:
        var(constraints={"max_length": 3})
    assert error.value.errors()[0]["type"] == "workflow_variable_invalid"


def test_min_above_max_is_rejected():
    with pytest.raises(ValidationError):
        var(constraints={"minimum": 5, "maximum": 1})
    with pytest.raises(ValidationError):
        ConvVariable.model_validate({"name": "s", "type": "string", "default": "",
                                     "constraints": {"min_length": 4, "max_length": 2}})


def test_default_must_satisfy_constraints():
    with pytest.raises(ValidationError) as error:
        var(default=20, constraints={"maximum": 10})
    assert error.value.errors()[0]["type"] == "workflow_variable_invalid"


def test_limits_drop_unset_keys():
    assert var().limits is None
    assert var(constraints={"maximum": 10}).limits == {"maximum": 10}


def test_unknown_constraint_key_is_rejected():
    with pytest.raises(ValidationError):
        var(constraints={"pattern": "^a"})


def test_node_description_is_optional_and_bounded():
    assert WorkflowNode.model_validate({"id": "a", "type": "start"}).description is None
    assert WorkflowNode.model_validate({"id": "a", "type": "start", "description": "Vào"}).description == "Vào"
    with pytest.raises(ValidationError):
        WorkflowNode.model_validate({"id": "a", "type": "start", "description": "x" * 501})
