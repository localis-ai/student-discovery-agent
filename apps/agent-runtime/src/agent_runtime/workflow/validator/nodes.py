"""Per node type: what a node reads, which tools and knowledge bases it names, and what an ``assign`` writes."""
import json
from collections.abc import Mapping
from typing import Any

from agent_runtime.workflow.variables import value_fits

from .expressions import VARIABLE_KINDS, References
from .findings import ASSIGN_SCOPE, Findings, as_dict, as_list
from .structure import FlowGraph

TEMPLATE_FIELDS = {"llm": ("prompt",), "intent_classifier": ("input",), "profile_propose": ("input",),
                   "answer": ("text",), "knowledge_retrieval": ("query",)}


def knowledge_base_ids(raw: object) -> list[str]:
    """Every knowledge base a ``knowledge_retrieval`` node names, so the caller can fetch their fields once.

    ``raw`` is a chatflow (its flows' nodes) or a single graph (its own nodes)."""
    root = as_dict(raw)
    graphs = [as_dict(flow) for flow in as_list(root.get("flows"))] or [root]
    found = [as_dict(node.get("config")).get("knowledge_base_id")
             for graph in graphs for node in as_list(graph.get("nodes"))
             if isinstance(node, dict) and node.get("type") == "knowledge_retrieval"]
    return sorted({item for item in found if isinstance(item, str)})


def _usable_limits(raw: object) -> dict[str, Any]:
    """The constraints of a raw declaration that can be compared against: a malformed limit is the schema layer's
    finding (workflow_variable_invalid), and must not crash this check and hide every other finding."""
    if not isinstance(raw, dict):
        return {}
    return {key: limit for key, limit in raw.items()
            if (key == "integer" and isinstance(limit, bool))
            or (key != "integer" and isinstance(limit, int | float) and not isinstance(limit, bool))}


class NodeChecks:
    """The semantic checks of one flow's typed nodes, after ``FlowGraph.check()``."""

    def __init__(self, graph: FlowGraph, refs: References, agent: Mapping[str, Any],
                 kb_fields: Mapping[str, frozenset[str]], out: Findings):
        self.graph, self.refs, self.agent, self.kb_fields, self.out = graph, refs, agent, kb_fields, out
        # version is checked where it is used
        self.enabled = {tool["name"]: tool.get("version") for tool in as_list(agent.get("tools"))
                        if isinstance(tool, dict) and isinstance(tool.get("name"), str)}

    def run(self) -> None:
        for node_id, index in self.graph.typed.items():
            node = self.graph.nodes[index]
            kind, config = node["type"], as_dict(node.get("config"))
            at = f"{self.graph.at}.nodes[{index}].config"
            if kind == "if_else":
                self.refs.expression(node_id, config.get("condition"), f"{at}.condition")
            for field in TEMPLATE_FIELDS.get(kind, ()):
                self.refs.template(node_id, config.get(field), f"{at}.{field}")
            if kind == "knowledge_retrieval":
                self._knowledge(node_id, config, at)
            elif kind == "assign":
                self._assign(node_id, config, at)
            elif kind == "tool":
                self._tool(node_id, index, config, at)
            elif kind == "agent":
                self._agent(node_id, index, config, at)

    def _knowledge(self, node_id: str, config: dict[str, Any], at: str) -> None:
        base = config.get("knowledge_base_id")
        fields = self.kb_fields.get(base) if isinstance(base, str) else None
        if isinstance(base, str) and fields is None:
            self.out.add(f"{at}.knowledge_base_id", "knowledge_base_not_found",
                         f"Không tìm thấy knowledge base '{base}'.")
        for field, path in as_dict(config.get("filter_from_vars")).items():
            if fields is not None and field not in fields:
                self.out.add(f"{at}.filter_from_vars.{field}", "field_not_found",
                             f"Knowledge base không có trường '{field}'.")
            if isinstance(path, str):
                self.refs.lookup(path, node_id, f"{at}.filter_from_vars.{field}")
        for position, item in enumerate(as_list(as_dict(config.get("fixed_filter")).get("conditions"))):
            name = as_dict(item).get("name")
            if fields is not None and isinstance(name, str) and name not in fields:
                self.out.add(f"{at}.fixed_filter.conditions[{position}].name", "field_not_found",
                             f"Knowledge base không có trường '{name}'.")

    def _assign(self, node_id: str, config: dict[str, Any], at: str) -> None:
        for position, item in enumerate(as_list(config.get("assignments"))):
            if not isinstance(item, dict) or not isinstance(item.get("variable"), str):
                continue
            base = f"{at}.assignments[{position}]"
            self.refs.walk(node_id, item.get("value"), f"{base}.value")
            declared = self.refs.conv(item["variable"])
            if declared is None:
                self.out.add(f"{base}.variable", "workflow_assign_invalid", ASSIGN_SCOPE)
            else:
                self._assign_type(node_id, declared, item, base)

    def _assign_type(self, node_id: str, declared: dict[str, Any], item: dict[str, Any], base: str) -> None:
        kind, operation = declared["type"], item.get("operation", "set")
        if not isinstance(operation, str):
            return  # the schema layer rejects it; nothing here can be judged against it
        needed = {"append": "string_list", "add": "number"}.get(operation)
        if needed and kind != needed:
            self.out.add(f"{base}.operation", "workflow_assign_invalid", f"Phép '{operation}' chỉ dùng cho biến {needed}.")
            return
        if operation == "clear" or "value" not in item:
            return
        value = item["value"]
        if isinstance(value, dict) and set(value) == {"var"} and isinstance(value["var"], str):
            got = self.refs.lookup(value["var"], node_id, f"{base}.value", report=False)
            want = {"append": "string", "add": "number"}.get(operation, VARIABLE_KINDS[kind])
            if got is not None and got != want:
                self.out.add(f"{base}.value", "workflow_assign_invalid",
                             f"Giá trị kiểu {got} không khớp biến kiểu {want}.")
            return
        if isinstance(value, str) and "{{" in value:
            return  # a template renders to text; what it renders to is only known at run time
        if operation == "append":
            fits = isinstance(value, str)
        elif operation == "add":
            fits = isinstance(value, int | float) and not isinstance(value, bool)
        else:
            listed = declared.get("values")
            allowed = tuple(item for item in listed if isinstance(item, str)) if isinstance(listed, list) else None
            fits = value_fits(kind, value, allowed or None)
            limits = _usable_limits(declared.get("constraints"))
            if fits and limits and not value_fits(kind, value, allowed or None, limits):
                shown = json.dumps(value, ensure_ascii=False)
                self.out.add(f"{base}.value", "workflow_assign_invalid",
                             f"Giá trị {shown} vi phạm ràng buộc của conv.{declared['name']}.")
                return
        if not fits:
            self.out.add(f"{base}.value", "workflow_assign_invalid", f"Giá trị không khớp biến kiểu {kind}.")

    def _is_handoff(self, name: str) -> bool:
        from agent_runtime.tools.registry import find  # lazy, as in workflow/trace.py

        tool = find(name, self.enabled.get(name))
        return bool(tool and tool.kind == "handoff")

    def _terminal(self, node_id: str, index: int, handle: str) -> None:
        for _edge, source, edge_handle, target in self.graph.good:
            if source == node_id and edge_handle == handle and self.graph.node_type(target) != "answer":
                self.out.add(f"{self.graph.at}.nodes[{index}]", "workflow_handoff_not_terminal",
                             f"Handle '{handle}' của node '{node_id}' phải nối thẳng tới node answer.")

    def _tool(self, node_id: str, index: int, config: dict[str, Any], at: str) -> None:
        name = config.get("tool")
        if isinstance(name, str):
            if name not in self.enabled:
                self.out.add(f"{at}.tool", "workflow_tool_not_enabled", f"Công cụ '{name}' chưa được bật trong snapshot.")
            elif self._is_handoff(name):
                self._terminal(node_id, index, "success")
        self.refs.walk(node_id, config.get("arguments"), f"{at}.arguments")

    def _agent(self, node_id: str, index: int, config: dict[str, Any], at: str) -> None:
        for position, name in enumerate(as_list(config.get("tools"))):
            if isinstance(name, str) and name not in self.enabled:
                self.out.add(f"{at}.tools[{position}]", "workflow_tool_not_enabled",
                             f"Công cụ '{name}' chưa được bật trong snapshot.")
        limit = as_dict(self.agent.get("limits")).get("max_tool_steps", 4)
        steps = config.get("max_tool_steps")
        if isinstance(steps, int) and isinstance(limit, int) and steps > limit:
            self.out.add(f"{at}.max_tool_steps", "workflow_budget_exceeds_ceiling",
                         f"max_tool_steps không được vượt limits.max_tool_steps ({limit}).")
        self._terminal(node_id, index, "handoff")
