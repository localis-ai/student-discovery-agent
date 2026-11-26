"""One flow's graph as far as it can be read: ids, sizes, node configs, the start node, edges, reachability, cycles
and unwired handles. The semantic checks read what this accepted (``typed``, ``configs``, ``good``)."""
import re
from collections import defaultdict, deque
from typing import Any

from pydantic import ValidationError

from agent_runtime.workflow import registry
from agent_runtime.workflow.catalog import HANDLE_SPECS
from agent_runtime.workflow.rules import IDENT_PATTERN, MAX_EDGES, MAX_NODES, NODE_TYPES, duplicates, node_id_reserved

from .findings import ASSIGN_SCOPE, Findings, as_dict, as_list, loc

IDENT = re.compile(IDENT_PATTERN)
_NAMES = {"nodes": "node", "edges": "cạnh"}


class FlowGraph:
    """``raw`` is one flow (entry, nodes, edges); ``at`` is its finding path. ``check()`` reports into ``out``."""

    def __init__(self, raw: dict[str, Any], at: str, out: Findings):
        self.raw, self.at, self.out = raw, at, out
        self.nodes: list[Any] = as_list(raw.get("nodes"))
        self.edges: list[Any] = as_list(raw.get("edges"))
        self.by_id: dict[str, int] = {}  # every well-formed id, first occurrence
        self.typed: dict[str, int] = {}  # the subset whose type is supported: the nodes the graph can use
        self.configs: dict[int, Any] = {}  # parsed config of the nodes whose config is valid
        self.good: list[tuple[int, str, str, str]] = []  # (edge index, source, handle, target) between typed nodes
        self.wired: set[tuple[str, str]] = set()
        self.start_id: str | None = None
        self._ancestors_cache: dict[str, set[str]] = {}

    def check(self) -> None:
        self._sizes()
        self._duplicates()
        self._nodes()
        self._start()
        self._edges()
        reached = self._reachable()
        self._cycles()
        if reached is not None:
            self._wiring(reached)

    def node_type(self, node_id: str) -> str:
        """The type of a node in ``typed``."""
        return self.nodes[self.typed[node_id]]["type"]

    def ancestors(self, node_id: str) -> set[str]:
        """Every node with a path to ``node_id``: the nodes whose output it may read."""
        if node_id not in self._ancestors_cache:
            reverse: dict[str, list[str]] = defaultdict(list)
            for _index, source, _handle, target in self.good:
                reverse[target].append(source)
            seen: set[str] = set()
            queue = deque([node_id])
            while queue:
                for source in reverse[queue.popleft()]:
                    if source not in seen:
                        seen.add(source)
                        queue.append(source)
            self._ancestors_cache[node_id] = seen
        return self._ancestors_cache[node_id]

    def handles(self, index: int) -> set[str]:
        node = self.nodes[index]
        if index in self.configs:
            return set(registry.get(node["type"]).handles(self.configs[index]))
        handles = set(HANDLE_SPECS[node["type"]]["static"])  # the config is invalid: the labels as written will do
        if node["type"] == "intent_classifier":
            handles |= {item["id"] for item in as_list(as_dict(node.get("config")).get("labels"))
                        if isinstance(item, dict) and isinstance(item.get("id"), str)}
        return handles

    def _sizes(self) -> None:
        for name, items, limit in (("nodes", self.nodes, MAX_NODES), ("edges", self.edges, MAX_EDGES)):
            if len(items) > limit:
                self.out.add(f"{self.at}.{name}", "workflow_too_large", f"Tối đa {limit} {_NAMES[name]}.")

    def _duplicates(self) -> None:
        for name, items in (("nodes", self.nodes), ("edges", self.edges)):
            for index, value in duplicates(as_dict(item).get("id") for item in items):
                self.out.add(f"{self.at}.{name}[{index}].id", "duplicate_items", f"'{value}' bị trùng.")

    def _nodes(self) -> None:
        for index, node in enumerate(self.nodes):
            if not isinstance(node, dict):
                continue
            at = f"{self.at}.nodes[{index}]"
            node_id, kind = node.get("id"), node.get("type")
            well_formed = isinstance(node_id, str) and IDENT.match(node_id) is not None
            if well_formed:
                self.by_id.setdefault(node_id, index)
                if node_id_reserved(node_id):
                    self.out.add(f"{at}.id", "workflow_node_id_reserved",
                                 "Id node không được trùng tên dành riêng (sys, conv, profile, result, router).")
            if not isinstance(kind, str) or kind not in NODE_TYPES:
                self.out.add(f"{at}.type", "workflow_node_type_unsupported",
                             "Loại node này chưa được hỗ trợ trong chatflow.")
                continue
            if well_formed and self.by_id[node_id] == index:
                self.typed[node_id] = index
            self._config(index, at, kind, node.get("config", {}))

    def _config(self, index: int, at: str, kind: str, config: Any) -> None:
        try:
            self.configs[index] = registry.get(kind).config_model.model_validate(config)
        except ValidationError as error:
            for item in error.errors():
                code, message = _config_error(kind, item)
                self.out.add(f"{at}.config{loc(item['loc'])}", code, message)

    def _start(self) -> None:
        starts = [(i, as_dict(n).get("id")) for i, n in enumerate(self.nodes) if as_dict(n).get("type") == "start"]
        if len(starts) != 1:
            self.out.add(f"{self.at}.nodes", "workflow_start_invalid", "Đồ thị phải có đúng một node start.")
            return
        start_id = starts[0][1]
        if isinstance(start_id, str):
            self.start_id = start_id
        if self.raw.get("entry") != start_id:
            self.out.add(f"{self.at}.entry", "workflow_start_invalid", "entry phải là id của node start.")

    def _edges(self) -> None:
        for index, edge in enumerate(self.edges):
            if not isinstance(edge, dict):
                continue
            at = f"{self.at}.edges[{index}]"
            source, handle, target = edge.get("source"), edge.get("source_handle"), edge.get("target")
            for key, node_id in (("source", source), ("target", target)):
                if isinstance(node_id, str) and node_id not in self.by_id:
                    self.out.add(f"{at}.{key}", "workflow_edge_invalid", f"Node '{node_id}' không tồn tại.")
            source_ok = isinstance(source, str) and source in self.typed
            target_ok = isinstance(target, str) and target in self.typed
            if target_ok and self.node_type(target) == "start":
                self.out.add(f"{at}.target", "workflow_edge_invalid", "Không được nối cạnh vào node start.")
            if source_ok and isinstance(handle, str):
                if handle not in self.handles(self.typed[source]):
                    self.out.add(f"{at}.source_handle", "workflow_unknown_handle",
                                 f"Node '{source}' không có handle '{handle}'.")
                elif (source, handle) in self.wired:
                    self.out.add(f"{at}.source_handle", "workflow_duplicate_handle_edge",
                                 f"Handle '{handle}' của node '{source}' chỉ được có một cạnh.")
                else:
                    self.wired.add((source, handle))
            if source_ok and target_ok:
                self.good.append((index, source, handle if isinstance(handle, str) else "", target))

    def _graph(self) -> dict[str, list[tuple[int, str]]]:
        graph: dict[str, list[tuple[int, str]]] = defaultdict(list)
        for index, source, _handle, target in self.good:
            graph[source].append((index, target))
        return graph

    def _reachable(self) -> set[str] | None:
        if self.start_id is None or self.start_id not in self.typed:
            return None
        graph = self._graph()
        seen, queue = {self.start_id}, deque([self.start_id])
        while queue:
            for _, target in graph[queue.popleft()]:
                if target not in seen:
                    seen.add(target)
                    queue.append(target)
        for node_id, index in self.typed.items():
            if node_id not in seen:
                self.out.add(f"{self.at}.nodes[{index}]", "workflow_unreachable_node",
                             f"Node '{node_id}' không đi tới được từ start.")
        return seen

    def _cycles(self) -> None:
        graph = self._graph()
        state: dict[str, int] = {}  # 1 on the current path, 2 finished
        for root in self.typed:
            if root in state:
                continue
            state[root] = 1
            stack, iterators = [root], {root: iter(graph[root])}
            while stack:
                node = stack[-1]
                step = next(iterators[node], None)
                if step is None:
                    state[node] = 2
                    stack.pop()
                    continue
                edge_index, target = step
                if state.get(target) == 1:
                    ring = [*stack[stack.index(target):], target]
                    self.out.add(f"{self.at}.edges[{edge_index}]", "workflow_cycle",
                                 "Chu trình giữa các node: " + " → ".join(ring) + ".")
                elif target not in state:
                    state[target] = 1
                    stack.append(target)
                    iterators[target] = iter(graph[target])

    def _wiring(self, reached: set[str]) -> None:
        """Every handle but ``error`` needs an edge; with a DAG and an edge-less ``answer`` that ends every path."""
        for node_id in sorted(reached, key=lambda item: self.typed[item]):
            index = self.typed[node_id]
            loose = sorted(handle for handle in self.handles(index)
                           if handle != "error" and (node_id, handle) not in self.wired)
            if self.node_type(node_id) == "intent_classifier":
                labels = as_list(as_dict(self.nodes[index].get("config")).get("labels"))
                for handle in loose:
                    position = next((j for j, item in enumerate(labels) if as_dict(item).get("id") == handle), None)
                    at = f"{self.at}.nodes[{index}]" + (f".config.labels[{position}]" if position is not None else "")
                    self.out.add(at, "workflow_unwired_label", f"Nhãn '{handle}' của node '{node_id}' chưa được nối.")
            elif loose:
                self.out.add(f"{self.at}.nodes[{index}]", "workflow_dead_end",
                             f"Node '{node_id}' có nhánh chưa nối ({', '.join(loose)}) "
                             "nên đường đi không kết thúc ở answer.")


def _config_error(kind: str, item: Any) -> tuple[str, str]:
    if kind == "assign" and item["loc"][-1:] == ("variable",) and item["type"] == "string_pattern_mismatch":
        return "workflow_assign_invalid", ASSIGN_SCOPE
    code = item["type"]
    if code == "value_error":  # a model validator may carry one of our codes as "workflow_x: reason"
        match = re.search(r"(workflow_[a-z_]+):", item["msg"])
        code = match.group(1) if match else code
    return code, "Cấu hình node không hợp lệ: " + str(item["msg"])
