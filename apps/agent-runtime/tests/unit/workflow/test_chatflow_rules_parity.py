"""Pins the runtime's chatflow rules to contracts/: the OpenAPI schema and chatflow-rules.json (which Studio also tests).

A failure here means one side changed alone: update the runtime, chatflow.yaml and chatflow-rules.json together.
"""
import json
import re
from pathlib import Path

import pytest
import yaml

from agent_runtime.sessions.schemas import workflow as schema
from agent_runtime.workflow import rules
from agent_runtime.workflow.nodes.goto_flow import MAX_FLOW_SWITCHES
from agent_runtime.workflow.templates import placeholders

CONTRACTS = Path(__file__).resolve().parents[5] / "contracts"
RULES = json.loads((CONTRACTS / "fixtures/chatflow-rules.json").read_text(encoding="utf-8"))
OPENAPI = yaml.safe_load((CONTRACTS / "openapi/schemas/chatflow.yaml").read_text(encoding="utf-8"))["components"]["schemas"]
PYDANTIC = schema.Chatflow.model_json_schema()
DEFS = PYDANTIC["$defs"]


def _bounds(field: dict) -> dict:
    """minimum/maximum of a pydantic optional int field (anyOf [int, null])."""
    number = next(option for option in field["anyOf"] if option.get("type") == "integer")
    return {"minimum": number["minimum"], "maximum": number["maximum"]}


def test_identifier_and_reserved_ids():
    assert RULES["identifier_pattern"] == rules.IDENT_PATTERN == OPENAPI["ChatflowIdentifier"]["pattern"]
    assert set(RULES["reserved_node_ids"]) == rules.RESERVED_NODE_IDS
    assert set(RULES["reserved_flow_ids"]) == rules.RESERVED_FLOW_IDS


def test_fixture_limits_match_openapi():
    limits = RULES["limits"]
    assert limits["flows"] == OPENAPI["ChatflowWorkflow"]["properties"]["flows"]["maxItems"]
    assert limits["variables"] == OPENAPI["ChatflowWorkflow"]["properties"]["variables"]["maxItems"]
    assert limits["nodes_per_flow"] == OPENAPI["ChatflowFlow"]["properties"]["nodes"]["maxItems"]
    assert limits["edges_per_flow"] == OPENAPI["ChatflowFlow"]["properties"]["edges"]["maxItems"]
    assert limits["flow_examples"] == OPENAPI["ChatflowFlow"]["properties"]["examples"]["maxItems"]
    assert limits["enum_values"] == OPENAPI["ChatflowVariable"]["properties"]["values"]["maxItems"]
    assert limits["variable_description"] == OPENAPI["ChatflowVariable"]["properties"]["description"]["maxLength"]
    constraints = OPENAPI["ChatflowVariable"]["properties"]["constraints"]["properties"]
    for key, bounds in RULES["variable_constraint_bounds"].items():
        assert {"minimum": constraints[key]["minimum"], "maximum": constraints[key]["maximum"]} == bounds, key


def test_runtime_limits_match_fixture():
    limits = RULES["limits"]
    assert (rules.MAX_FLOWS, rules.MAX_VARIABLES, rules.MAX_NODES, rules.MAX_EDGES, rules.MAX_ENUM_VALUES) == (
        limits["flows"], limits["variables"], limits["nodes_per_flow"], limits["edges_per_flow"], limits["enum_values"])
    assert MAX_FLOW_SWITCHES == limits["max_flow_switches"]
    # The pydantic models must enforce what the constants say, not a stale literal.
    assert PYDANTIC["properties"]["flows"]["maxItems"] == limits["flows"]
    assert PYDANTIC["properties"]["variables"]["maxItems"] == limits["variables"]
    assert DEFS["Flow"]["properties"]["nodes"]["maxItems"] == limits["nodes_per_flow"]
    assert DEFS["Flow"]["properties"]["edges"]["maxItems"] == limits["edges_per_flow"]
    assert DEFS["Flow"]["properties"]["examples"]["maxItems"] == limits["flow_examples"]
    values = next(option for option in DEFS["ConvVariable"]["properties"]["values"]["anyOf"] if option.get("type") == "array")
    assert values["maxItems"] == limits["enum_values"]
    description = next(option for option in DEFS["ConvVariable"]["properties"]["description"]["anyOf"]
                       if option.get("type") == "string")
    assert description["maxLength"] == limits["variable_description"]
    constraints = DEFS["VariableConstraints"]["properties"]
    for key, bounds in RULES["variable_constraint_bounds"].items():
        assert _bounds(constraints[key]) == bounds, key


def test_node_types_match_openapi():
    assert set(OPENAPI["ChatflowNodeType"]["enum"]) == rules.NODE_TYPES


@pytest.mark.parametrize("case", RULES["placeholder_cases"], ids=lambda case: case["text"])
def test_placeholder_grammar(case):
    assert list(placeholders(case["text"])) == case["paths"]


def test_identifier_pattern_compiles_the_same_in_python():
    assert re.fullmatch(RULES["identifier_pattern"], "a" * 40)
    assert not re.fullmatch(RULES["identifier_pattern"], "a" * 41)
