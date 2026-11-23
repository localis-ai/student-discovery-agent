"""Importing this package registers every node type."""
from agent_runtime.workflow.nodes import (  # noqa: F401
    agent,
    answer,
    assign,
    goto_flow,
    if_else,
    intent_classifier,
    knowledge_retrieval,
    llm,
    profile_propose,
    router,
    start,
    tool,
)
