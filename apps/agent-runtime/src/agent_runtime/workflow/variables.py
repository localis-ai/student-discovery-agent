"""What a ``conv.*`` value may hold: its declared type, then its constraints.

The schema checks a declaration's default with these, the validator an ``assign`` literal, and the runtime a stored or
assigned value at run time. All three must agree, so the rule lives here once. This module imports nothing from the
runtime.
"""
import math
from collections.abc import Mapping
from typing import Any

_JSON_SAFE_INT = 9007199254740991  # same bound as JsonSafeInt in sessions/schemas/common.py

# Which constraint keys each variable type accepts; anything else is workflow_variable_invalid.
CONSTRAINT_KEYS: dict[str, frozenset[str]] = {
    "string": frozenset({"min_length", "max_length"}),
    "number": frozenset({"minimum", "maximum", "integer"}),
    "boolean": frozenset(),
    "enum": frozenset(),
    "string_list": frozenset({"max_items", "item_max_length"}),
}


def fits_type(kind: str, value: Any, values: tuple[str, ...] | None = None) -> bool:
    """``value`` has the variable type ``kind``; for an enum, it is one of ``values``."""
    if kind == "string":
        return isinstance(value, str)
    if kind == "number":
        if isinstance(value, bool):
            return False
        if isinstance(value, int):  # never float() an int: huge JSON integers raise OverflowError
            return abs(value) <= _JSON_SAFE_INT
        return isinstance(value, float) and math.isfinite(value)
    if kind == "boolean":
        return isinstance(value, bool)
    if kind == "enum":
        return isinstance(value, str) and value in (values or ())
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


def within_constraints(value: Any, limits: Mapping[str, Any] | None) -> bool:
    """The constraint check, on a value that already fits its type."""
    if not limits:
        return True
    if isinstance(value, str):
        return limits.get("min_length", 0) <= len(value) <= limits.get("max_length", len(value))
    if isinstance(value, list):
        if len(value) > limits.get("max_items", len(value)):
            return False
        longest = limits.get("item_max_length")
        return longest is None or all(len(item) <= longest for item in value)
    if isinstance(value, int | float) and not isinstance(value, bool):
        if limits.get("integer") and not float(value).is_integer():
            return False
        return limits.get("minimum", value) <= value <= limits.get("maximum", value)
    return True


def value_fits(kind: str, value: Any, values: tuple[str, ...] | None = None,
               constraints: Mapping[str, Any] | None = None) -> bool:
    """Type and constraints together: what a stored or assigned ``conv.*`` value must pass."""
    return fits_type(kind, value, values) and within_constraints(value, constraints)
