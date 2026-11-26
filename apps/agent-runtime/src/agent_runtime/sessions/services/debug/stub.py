"""The model a debug run uses for a node the Admin stubbed."""
import json
from typing import Any

from agent_runtime.agent.model import ModelReply, ModelUnavailable


class StubModel:
    """A fixed answer for a model node: a string is the reply text, anything else a JSON reply; no tokens spent."""

    def __init__(self, stub: Any):
        self._stub = stub

    def invoke(self, messages, tools, settings, on_text_delta=None):
        text = self._stub if isinstance(self._stub, str) else json.dumps(self._stub, ensure_ascii=False)
        if on_text_delta is not None and text and on_text_delta(text) is False:
            return ModelUnavailable("cancelled")
        return ModelReply(text=text)
