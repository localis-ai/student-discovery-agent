"""What a node may read: variable paths as seen from one node, and the templates and expressions built from them."""
from typing import Any

from agent_runtime.workflow.catalog import NAMESPACES
from agent_runtime.workflow.expressions import COMPARISONS, ExpressionError, Lit, Op, Var, parse, variables
from agent_runtime.workflow.templates import placeholders

from .findings import Findings, as_list
from .structure import FlowGraph

# The kind a variable of each declared type reads as in an expression.
VARIABLE_KINDS = {"string": "string", "enum": "string", "number": "number", "boolean": "boolean",
                  "string_list": "string_list"}
_STATIC_KINDS = {item["name"]: {v["name"]: v["type"] for v in item["variables"]}
                 for item in NAMESPACES if item["name"] in ("sys", "result")}


def _literal_kind(value: Any) -> str | None:
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int | float):
        return "number"
    if isinstance(value, str):
        return "string"
    return "list" if isinstance(value, tuple) else None


class References:
    """``variables`` is the chatflow's raw ``conv`` declarations; only the readable ones are kept in ``declared``."""

    def __init__(self, graph: FlowGraph, variables: list[Any], out: Findings):
        self.graph, self.out = graph, out
        self.declared: dict[str, dict[str, Any]] = {}
        for item in as_list(variables):
            if (isinstance(item, dict) and isinstance(item.get("name"), str) and isinstance(item.get("type"), str)
                    and item["type"] in VARIABLE_KINDS):
                self.declared.setdefault(item["name"], item)

    def conv(self, path: str) -> dict[str, Any] | None:
        """The declaration of a ``conv.*`` path, if there is one."""
        return self.declared.get(path.removeprefix("conv.")) if path.startswith("conv.") else None

    def lookup(self, path: str, node_id: str, at: str, *, report: bool = True) -> str | None:
        """The kind of a variable path as seen from ``node_id`` (None when unknown or not typed here)."""
        head, _, rest = path.partition(".")
        kind: str | None = None
        if head in _STATIC_KINDS:
            kind = _STATIC_KINDS[head].get(rest)
            known = kind is not None
        elif head == "profile":
            known = True  # the runtime has no profile catalog yet: the namespace is all that can be checked
        elif head == "conv":
            variable = self.declared.get(rest)
            known = variable is not None
            kind = VARIABLE_KINDS[variable["type"]] if variable else None
        else:
            known = head in self.graph.typed and head in self.graph.ancestors(node_id)
        if not known and report:
            self.out.add(at, "workflow_unknown_variable",
                         f"Biến '{path}' không tồn tại hoặc node chứa nó không chạy trước node này.")
        return kind

    def template(self, node_id: str, text: Any, at: str) -> None:
        if isinstance(text, str):
            for path in placeholders(text):
                self.lookup(path, node_id, at)

    def walk(self, node_id: str, value: Any, at: str) -> None:
        """Templates and ``{"var": path}`` references anywhere inside a nested value."""
        if isinstance(value, str):
            self.template(node_id, value, at)
        elif isinstance(value, dict) and set(value) == {"var"} and isinstance(value["var"], str):
            self.lookup(value["var"], node_id, at)
        elif isinstance(value, dict):
            for key, item in value.items():
                self.walk(node_id, item, f"{at}.{key}")
        elif isinstance(value, list):
            for position, item in enumerate(value):
                self.walk(node_id, item, f"{at}[{position}]")

    def expression(self, node_id: str, raw: Any, at: str) -> None:
        try:
            tree = parse(raw)
        except ExpressionError as error:
            self.out.add(at, error.code, f"Biểu thức không hợp lệ: {error}")
            return
        for path in variables(tree):
            self.lookup(path, node_id, at)
        self._compare(tree, node_id, at)

    def _kind_of(self, expression: Any, node_id: str, at: str) -> str | None:
        if isinstance(expression, Var):
            return self.lookup(expression.path, node_id, at, report=False)
        return _literal_kind(expression.value) if isinstance(expression, Lit) else None

    def _compare(self, expression: Any, node_id: str, at: str) -> None:
        if not isinstance(expression, Op):
            return
        for argument in expression.args:
            self._compare(argument, node_id, at)
        if len(expression.args) != 2:
            return
        left, right = expression.args
        if expression.op in COMPARISONS:
            kinds = (self._kind_of(left, node_id, at), self._kind_of(right, node_id, at))
            if expression.op not in ("==", "!="):
                if any(kind not in (None, "number") for kind in kinds):
                    self.out.add(at, "workflow_type_mismatch", f"Phép '{expression.op}' chỉ so sánh số.")
            elif None not in kinds and kinds[0] != kinds[1]:
                self.out.add(at, "workflow_type_mismatch", f"Không thể so sánh {kinds[0]} với {kinds[1]}.")
            for variable, literal in ((left, right), (right, left)):
                declared = self.conv(variable.path) if isinstance(variable, Var) else None
                if (declared and declared.get("type") == "enum" and isinstance(literal, Lit)
                        and isinstance(literal.value, str) and isinstance(declared.get("values"), list)
                        and literal.value not in declared["values"]):
                    self.out.add(at, "workflow_type_mismatch",
                                 f"'{literal.value}' không thuộc danh sách giá trị của {variable.path}.")
        elif expression.op == "in" and self._kind_of(right, node_id, at) == "string":
            self.out.add(at, "workflow_type_mismatch", "Vế phải của 'in' phải là danh sách hoặc biến string_list.")
