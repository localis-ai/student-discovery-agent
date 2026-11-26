"""Log an unexpected exception so it can be debugged without leaking what it carried.

Exception messages and arguments may hold student text, model output, URLs or secrets, so they are never logged.
What is logged instead is enough to find the bug: the exception type (and its causes' types) and the code location
of each frame, innermost last, e.g. ``KeyError at executor.py:141:run_workflow <- flows.py:42:compile_chatflow``.
"""
import logging
import traceback
from pathlib import Path

_MAX_FRAMES = 8
_MAX_CAUSES = 3


def _where(error: BaseException) -> str:
    frames = traceback.extract_tb(error.__traceback__)[-_MAX_FRAMES:]
    return " <- ".join(f"{Path(frame.filename).name}:{frame.lineno}:{frame.name}" for frame in reversed(frames))


def describe_error(error: BaseException) -> str:
    """Type and code location of an exception and of its first causes; never a message or a value."""
    parts: list[str] = []
    current: BaseException | None = error
    while current is not None and len(parts) < _MAX_CAUSES:
        where = _where(current)
        parts.append(f"{type(current).__qualname__} at {where}" if where else type(current).__qualname__)
        current = current.__cause__ or (None if current.__suppress_context__ else current.__context__)
    return " | caused by ".join(parts)


def log_unexpected(logger: logging.Logger, event: str, error: BaseException) -> None:
    """One ERROR line for an exception a caller turns into a generic failure (500, unavailable, failed turn)."""
    logger.error("%s: %s", event, describe_error(error))
