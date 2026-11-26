"""Chatflow graph validator (FR-WFL-07): reads the raw workflow dict and reports every issue in one pass.

It works on the raw dict, not the parsed model, so one bad node cannot hide the rest. Each check only uses what the
earlier checks accepted; anything it cannot read is skipped here and reported by the schema layer instead.

- ``chatflow.py``: the checks above one flow (router, triggers, goto_flow, budget), then each flow in turn;
- ``structure.py``: one flow's graph (ids, sizes, configs, edges, reachability, cycles, wiring);
- ``expressions.py``: variable paths, templates and expressions as seen from one node;
- ``nodes.py``: the per-type checks (knowledge, assign, tool, agent).

The rules the schema layer also applies come from ``workflow/rules.py``.
"""
import logging
from collections.abc import Mapping
from typing import Any

from .chatflow import ChatflowCheck
from .findings import Finding
from .nodes import knowledge_base_ids

__all__ = ["Finding", "knowledge_base_ids", "validate_workflow"]

logger = logging.getLogger(__name__)


def validate_workflow(raw: object, agent: Mapping[str, Any], kb_fields: Mapping[str, frozenset[str]]) -> list[Finding]:
    """Every finding of a chatflow (``agent.workflow``): its flows one by one, then how they route to each other."""
    try:
        return ChatflowCheck(raw, agent, kb_fields).run()
    except Exception as error:  # the input is hostile by nature: a checker bug must read as a failure, never a 500
        logger.error("workflow validation failed to run: %s", type(error).__name__)
        return [Finding("workflow", "workflow_unverifiable", "Không kiểm tra được workflow này; kiểm tra lại cấu trúc JSON.")]
