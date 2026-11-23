"""goto_flow: end this flow and run another flow's entry in the same turn; there is no return."""
from agent_runtime.sessions.schemas.common import ContractModel
from agent_runtime.sessions.schemas.workflow import Ident
from agent_runtime.workflow.nodes.base import NodeContext, NodeError, NodeResult, NodeSpec
from agent_runtime.workflow.registry import register

MAX_FLOW_SWITCHES = 3
# Internal: compile_chatflow wires it to the target flow's entry. Authors see no handle, so the node ends its branch.
GOTO_HANDLE = "goto"


class GotoFlowConfig(ContractModel):
    flow: Ident


def run(ctx: NodeContext, config: GotoFlowConfig) -> NodeResult:
    ctx.state.flow_switches += 1
    if ctx.state.flow_switches > MAX_FLOW_SWITCHES:  # the validator rejects goto cycles; this caps what it allows
        raise NodeError("invalid_output", cause="flow_switch_limit")
    return NodeResult(GOTO_HANDLE, {"flow": config.flow}, reason={"flow": config.flow})


register(NodeSpec("goto_flow", GotoFlowConfig, lambda config: (),
                  {"type": "object", "properties": {"flow": {"type": "string"}}}, run))
