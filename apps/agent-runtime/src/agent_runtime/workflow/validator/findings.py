"""What every validator module shares: the finding, the collector, and readers for a raw dict that may be malformed."""
from typing import Any, NamedTuple

ASSIGN_SCOPE = "assign chỉ được ghi biến conv.* đã khai báo."


class Finding(NamedTuple):
    path: str
    code: str
    message: str


class Findings:
    """Findings in the order they were found, each (path, code, message) once."""

    def __init__(self) -> None:
        self._items: dict[tuple[str, str, str], Finding] = {}

    def add(self, path: str, code: str, message: str) -> None:
        self._items.setdefault((path, code, message), Finding(path, code, message))

    def extend(self, findings: list[Finding]) -> None:
        for finding in findings:
            self._items.setdefault(tuple(finding), finding)

    def found(self) -> list[Finding]:
        return list(self._items.values())


def as_list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def loc(parts: tuple[Any, ...]) -> str:
    """A pydantic error location as a finding path suffix: ``("labels", 0, "id")`` → ``.labels[0].id``."""
    return "".join(f"[{part}]" if isinstance(part, int) else f".{part}" for part in parts)
