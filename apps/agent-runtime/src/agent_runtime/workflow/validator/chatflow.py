"""Checks above one flow: sizes, ids across flows, the router, triggers, goto_flow targets and the budget. Each flow's
own graph is checked by ``check_flow``."""
from collections import defaultdict
from collections.abc import Mapping
from typing import Any

from agent_runtime.workflow.budget import HARD_CEILING
from agent_runtime.workflow.expressions import ExpressionError, parse, variables
from agent_runtime.workflow.nodes.goto_flow import MAX_FLOW_SWITCHES
from agent_runtime.workflow.rules import (
    MAX_FLOWS,
    MAX_VARIABLES,
    cross_flow_duplicates,
    default_flow_routable,
    duplicates,
    flow_id_reserved,
    flow_needs_description,
)

from .expressions import References
from .findings import Finding, Findings, as_dict, as_list
from .nodes import NodeChecks
from .structure import FlowGraph

_HEADS = frozenset({"conv", "sys", "profile", "result"})


def check_flow(raw: dict[str, Any], agent: Mapping[str, Any], kb_fields: Mapping[str, frozenset[str]], *,
               at: str) -> list[Finding]:
    """One flow's graph (``raw`` holds entry, nodes, edges and the chatflow's variables), structure first."""
    out = Findings()
    graph = FlowGraph(raw, at, out)
    graph.check()
    NodeChecks(graph, References(graph, raw.get("variables"), out), agent, kb_fields, out).run()
    return out.found()


class ChatflowCheck:
    def __init__(self, raw: object, agent: Mapping[str, Any], kb_fields: Mapping[str, frozenset[str]]):
        self.raw, self.agent, self.kb_fields = raw, agent, kb_fields
        self.out = Findings()
        self.by_flow: dict[str, tuple[int, dict[str, Any]]] = {}

    def run(self) -> list[Finding]:
        if not isinstance(self.raw, dict):
            self.out.add("workflow", "type_error", "Workflow phải là một JSON object.")
            return self.out.found()
        variables, flows = as_list(self.raw.get("variables")), as_list(self.raw.get("flows"))
        if len(variables) > MAX_VARIABLES:
            self.out.add("workflow.variables", "workflow_too_large", f"Tối đa {MAX_VARIABLES} biến.")
        if not flows:
            self.out.add("workflow.flows", "workflow_flow_invalid", "Cần ít nhất một nghiệp vụ.")
        if len(flows) > MAX_FLOWS:
            self.out.add("workflow.flows", "workflow_too_large", f"Tối đa {MAX_FLOWS} nghiệp vụ.")
        self._unique(variables, "name", "workflow.variables")
        self._unique(flows, "id", "workflow.flows")
        self.by_flow = {flow["id"]: (k, flow) for k, flow in enumerate(flows)
                        if isinstance(flow, dict) and isinstance(flow.get("id"), str)}
        declared = {item["name"] for item in variables if isinstance(item, dict) and isinstance(item.get("name"), str)}
        self._flows(flows)
        self._router(as_dict(self.raw.get("router")))
        self._node_ids(flows)
        for k, flow in enumerate(flows):
            if not isinstance(flow, dict):
                continue
            self._trigger(flow.get("trigger"), f"workflow.flows[{k}].trigger", declared)
            view = {"entry": flow.get("entry"), "nodes": flow.get("nodes"), "edges": flow.get("edges"),
                    "variables": variables}
            self.out.extend(check_flow(view, self.agent, self.kb_fields, at=f"workflow.flows[{k}]"))
        self._gotos(flows)
        self._budget(as_dict(self.raw.get("budget")))
        return self.out.found()

    def _unique(self, items: list[Any], key: str, at: str) -> None:
        for index, value in duplicates(as_dict(item).get(key) for item in items):
            self.out.add(f"{at}[{index}].{key}", "duplicate_items", f"'{value}' bị trùng.")

    def _flows(self, flows: list[Any]) -> None:
        for k, flow in enumerate(flows):
            flow = as_dict(flow)
            if flow_id_reserved(flow.get("id")):
                self.out.add(f"workflow.flows[{k}].id", "workflow_flow_invalid",
                             "Id nghiệp vụ không được là other hoặc error.")
            if flow_needs_description(flow.get("routable", True), flow.get("description")):
                self.out.add(f"workflow.flows[{k}].description", "workflow_flow_invalid",
                             "Nghiệp vụ định tuyến được cần mô tả để router chọn.")

    def _router(self, router: dict[str, Any]) -> None:
        routable = {flow_id: flow.get("routable", True) for flow_id, (_k, flow) in self.by_flow.items()}
        if not default_flow_routable(router.get("default_flow"), routable):
            self.out.add("workflow.router.default_flow", "workflow_flow_invalid",
                         "default_flow phải là một nghiệp vụ định tuyến được.")

    def _node_ids(self, flows: list[Any]) -> None:
        pairs = ((as_dict(flow).get("id"), (as_dict(node).get("id") for node in as_list(as_dict(flow).get("nodes"))))
                 for flow in flows)
        for k, i, node_id, first in cross_flow_duplicates(pairs):
            self.out.add(f"workflow.flows[{k}].nodes[{i}].id", "workflow_node_id_duplicate",
                         f"Id node '{node_id}' đã dùng ở nghiệp vụ '{first}'.")

    def _trigger(self, trigger: Any, at: str, declared: set[str]) -> None:
        if trigger is None:
            return
        try:
            expression = parse(trigger)
        except ExpressionError as error:
            self.out.add(at, "workflow_trigger_invalid", f"Điều kiện kích hoạt không hợp lệ: {error}")
            return
        for path in sorted(variables(expression)):
            head, _, name = path.partition(".")
            if head not in _HEADS or (head == "conv" and name not in declared):
                self.out.add(at, "workflow_trigger_invalid", f"Điều kiện kích hoạt đọc biến không tồn tại: {path}.")

    def _gotos(self, flows: list[Any]) -> None:
        links: dict[str, list[tuple[str, str]]] = defaultdict(list)  # flow -> [(target flow, node path)]
        for k, flow in enumerate(flows):
            flow = as_dict(flow)
            for i, node in enumerate(as_list(flow.get("nodes"))):
                node = as_dict(node)
                if node.get("type") != "goto_flow":
                    continue
                target = as_dict(node.get("config")).get("flow")
                at = f"workflow.flows[{k}].nodes[{i}]"
                if not isinstance(target, str) or target not in self.by_flow or target == flow.get("id"):
                    self.out.add(f"{at}.config.flow", "workflow_goto_invalid",
                                 "Nghiệp vụ đích không tồn tại hoặc chính là nghiệp vụ này.")
                elif isinstance(flow.get("id"), str):
                    links[flow["id"]].append((target, at))
        state: dict[str, int] = {}
        cyclic = False

        def visit(flow_id: str) -> None:
            nonlocal cyclic
            state[flow_id] = 1
            for target, at in links.get(flow_id, ()):
                if state.get(target) == 1:
                    cyclic = True
                    self.out.add(at, "workflow_goto_cycle", "Các nghiệp vụ chuyển vòng qua nhau bằng goto_flow.")
                elif target not in state:
                    visit(target)
            state[flow_id] = 2

        for flow_id in list(links):
            if flow_id not in state:
                visit(flow_id)
        if not cyclic:
            self._goto_depth(links)

    def _goto_depth(self, links: dict[str, list[tuple[str, str]]]) -> None:
        """A turn may switch flows at most MAX_FLOW_SWITCHES times: a longer acyclic chain always fails at run time."""
        depth: dict[str, int] = {}

        def jumps(flow_id: str) -> int:  # the goto links form a DAG here: cycles were reported before
            if flow_id not in depth:
                depth[flow_id] = max((1 + jumps(target) for target, _ in links.get(flow_id, ())), default=0)
            return depth[flow_id]

        for targets in links.values():
            for target, at in targets:
                if 1 + jumps(target) > MAX_FLOW_SWITCHES:
                    self.out.add(f"{at}.config.flow", "workflow_goto_invalid",
                                 f"Chuỗi chuyển nghiệp vụ từ đây dài hơn {MAX_FLOW_SWITCHES} lần chuyển trong một lượt.")

    def _budget(self, budget: dict[str, Any]) -> None:
        for key, ceiling in (("max_nodes", HARD_CEILING.max_nodes), ("max_llm_calls", HARD_CEILING.max_llm_calls),
                             ("turn_timeout_ms", HARD_CEILING.turn_timeout_ms)):
            value = budget.get(key)
            if isinstance(value, int) and not isinstance(value, bool) and value > ceiling:
                self.out.add(f"workflow.budget.{key}", "workflow_budget_exceeds_ceiling",
                             f"{key} không được vượt trần {ceiling}.")
