"""The debug run result Studio receives (``WorkflowDebugRunResult`` in contracts/openapi/schemas/chatflow-authoring.yaml)."""
from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4

from agent_runtime.workflow.effects import ActivityChange, AssignConv, KbRefsUsed, ProfileProposal
from agent_runtime.workflow.executor import WorkflowRun
from agent_runtime.workflow.flows import ROUTER_ID, RunGraph
from agent_runtime.workflow.trace import NodeRunTrace, Redaction, fallback_at_view

KEEP_SECONDS = 24 * 3600


def iso(moment: datetime) -> str:
    return moment.isoformat(timespec="seconds").replace("+00:00", "Z")


def effect_view(effect) -> dict[str, Any]:
    if isinstance(effect, AssignConv):
        return {"kind": "assign_conv", "variable": effect.variable, "value": effect.value, "operation": effect.operation}
    if isinstance(effect, ActivityChange):
        return {"kind": "activity_change", "tool": effect.handoff.name}
    if isinstance(effect, ProfileProposal):
        return {"kind": "profile_proposal", "fields": dict(effect.fields), "target_step": effect.target_step}
    if isinstance(effect, KbRefsUsed):
        return {"kind": "kb_refs_used", "kb_id": effect.kb_id, "refs": list(effect.refs)}
    return {"kind": type(effect).__name__}


def build_result(run: WorkflowRun, workflow: RunGraph, created: datetime, stubs: dict[str, Any],
                 route: dict[str, Any] | None = None) -> dict:
    # The Admin's own run, never persisted by the runtime: node inputs and values are shown in full.
    full = Redaction("full", {variable.name: variable for variable in workflow.variables})
    node_runs = []
    for record in run.records:
        item = NodeRunTrace(node_id=record.node_id, type=record.type, flow_id=workflow.flow_of.get(record.node_id),
                            order=record.order, handle=record.handle,
                            duration_ms=record.duration_ms, reason=full.reason(record),
                            input=full.input(record.input), output=full.io(record.type, record.output),
                            llm_calls=record.llm_calls, tokens={"input": record.tokens[0], "output": record.tokens[1]},
                            refs=record.refs, error=record.error).model_dump(mode="json")
        node_runs.append({key: value for key, value in item.items()
                          if value is not None or key in {"handle", "error", "flow_id"}})
    if route is None and run.records and run.records[0].node_id == ROUTER_ID and run.records[0].error is None:
        route = dict(run.records[0].reason)
    return {"run_id": "dbg_" + uuid4().hex[:24],
            "status": run.status, "fallback_reason": run.fallback, "fallback_at": fallback_at_view(run),
            "conv_reset": list(run.conv_reset), "conv_dropped": list(run.conv_dropped),
            "path": list(run.path), "node_runs": node_runs, "route": route,
            "blocks": [block.model_dump(mode="json") for block in run.blocks],
            "effects": [effect_view(effect) for effect in run.effects], "llm_calls": run.llm_calls,
            "live_llm_calls": sum(record.llm_calls for record in run.records if record.node_id not in stubs),
            "tokens": {"input": run.usage.input_tokens, "output": run.usage.output_tokens},
            "created_at": iso(created), "expires_at": iso(created + timedelta(seconds=KEEP_SECONDS))}
