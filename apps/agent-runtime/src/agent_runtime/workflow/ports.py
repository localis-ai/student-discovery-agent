"""Everything a node may call. Nothing here touches the database."""
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol

from agent_runtime.agent.model import ChatMessage, ModelPort, UnconfiguredModel
from agent_runtime.agent.prompt import AgentContext
from agent_runtime.knowledge.schemas import MetadataField
from agent_runtime.sessions.schemas.release import AgentSnapshotV1
from agent_runtime.tools.knowledge import KnowledgePort, KnowledgeShowParams

if TYPE_CHECKING:
    from agent_runtime.tools.toolbox import Toolbox


class ProfilePort(Protocol):
    def snapshot(self) -> Mapping[str, Any]:
        """The Student Profile as captured at preflight; fields not set are absent."""

    def accept(self, fields: Mapping[str, Any]) -> Mapping[str, Any]:
        """The subset of model-extracted values that are valid profile values (at most two)."""

    def record_career_groups(self, major_ids: Sequence[str]) -> int:
        """Record ordered career groups into the profile. Returns the resulting profile_revision."""


class NullProfilePort:
    """No Student Profile exists in the runtime yet: nothing is known and nothing is accepted."""

    def snapshot(self) -> Mapping[str, Any]:
        return {}

    def accept(self, fields: Mapping[str, Any]) -> Mapping[str, Any]:
        return {}

    def record_career_groups(self, major_ids: Sequence[str]) -> int:
        return 0


def rank_career_groups(major_ids: Sequence[str], limit: int = 3) -> tuple[str, ...]:
    """Clean, dedupe keeping first occurrence, and keep the top ``limit`` (DEC-26: order is the ranking)."""
    cleaned = [m.strip() for m in major_ids if isinstance(m, str) and m.strip()]
    return tuple(dict.fromkeys(cleaned))[:limit]


class InMemoryProfilePort:
    """In-memory student profile with ordered interested_career_groups and revision tracking (DEC-26)."""

    def __init__(self, initial_profile: Mapping[str, Any] | None = None, initial_revision: int = 1):
        self._profile = dict(initial_profile or {})
        self._revision = initial_revision

    @property
    def revision(self) -> int:
        return self._revision

    def snapshot(self) -> Mapping[str, Any]:
        return {"profile_revision": self._revision, **self._profile}

    def accept(self, fields: Mapping[str, Any]) -> Mapping[str, Any]:
        return {}

    def record_career_groups(self, major_ids: Sequence[str]) -> int:
        """Rank top 3 career groups, deduplicating preserving order (DEC-26).

        Order is semantic data: changing order increments profile_revision.
        Preserving order does not increment profile_revision.
        """
        deduped = rank_career_groups(major_ids)
        current = tuple(self._profile.get("interested_career_groups") or ())
        if current != deduped:
            self._profile["interested_career_groups"] = list(deduped)
            self._revision += 1
        return self._revision


@dataclass(frozen=True)
class Ports:
    agent: AgentSnapshotV1
    model: ModelPort = UnconfiguredModel()
    model_for: Callable[[str], ModelPort] | None = None  # per node id; debug runs stub model nodes here
    tools: "Toolbox | None" = None
    knowledge: KnowledgePort | None = None
    knowledge_fields: Mapping[str, tuple[MetadataField, ...]] = field(default_factory=dict)
    show_params: KnowledgeShowParams | None = None
    profile: ProfilePort = NullProfilePort()
    agent_context: AgentContext | None = None
    history: Sequence[ChatMessage] = ()
    user_text: str = ""

    def model_of(self, node_id: str) -> ModelPort:
        return self.model_for(node_id) if self.model_for else self.model
