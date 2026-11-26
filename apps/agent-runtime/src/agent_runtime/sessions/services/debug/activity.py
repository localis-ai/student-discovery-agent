"""The debug request's made-up activity, read into what a real turn would hand the tools and the agent prompt."""
from types import SimpleNamespace
from typing import Any

from agent_runtime.sessions.errors import RuntimeSessionError


def _text_or_none(value: Any) -> bool:
    return value is None or isinstance(value, str)


def activity_view(activity: dict | None):
    """(duck-typed activity for the tool executor, phase, display name, AgentContext question) of the fake state.

    A malformed activity is the Admin's input error: 422, never a run that silently ignores it."""
    if not activity:
        return None, "not_started", None, None
    question = activity.get("current_question")
    if question is not None and not isinstance(question, dict):
        raise RuntimeSessionError(422, "INVALID_INPUT")
    options = question.get("options", []) if question else []
    if not isinstance(options, list) or not all(isinstance(item, dict) and isinstance(item.get("id"), str)
                                                and _text_or_none(item.get("label")) for item in options):
        raise RuntimeSessionError(422, "INVALID_INPUT")
    status, display_name = activity.get("status"), activity.get("display_name")
    if not (_text_or_none(status) and _text_or_none(display_name)
            and _text_or_none(question.get("title") if question else None)):
        raise RuntimeSessionError(422, "INVALID_INPUT")
    state = SimpleNamespace(
        status=status or "not_started", display_name=display_name,
        current_question=SimpleNamespace(options=[SimpleNamespace(id=item["id"]) for item in options])
        if question else None)
    context_question = ({"title": question.get("title") or "", "options": [
        {"id": item["id"], "label": item.get("label") or item["id"]} for item in options]} if question else None)
    phase = state.status if state.status in {"collecting_name", "in_progress", "completed"} else "not_started"
    return SimpleNamespace(state=state), phase, state.display_name, context_question
