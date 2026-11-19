"""Product HTTP delivery: active agent and experience releases come from studio-api, signed per request."""
import hashlib
import time
from urllib.parse import urlencode

import httpx
import jwt
from pydantic import ValidationError

from agent_runtime.evaluations.services.validator import calculate_content_hash
from agent_runtime.infrastructure.http.logging import logger
from agent_runtime.sessions.errors import RuntimeSessionError
from agent_runtime.sessions.ports import ProductReleaseSource
from agent_runtime.sessions.schemas.activity import profile_for_schema
from agent_runtime.sessions.schemas.release import ReleaseDescriptor

_PATH = "/api/v1/internal/releases/active"
_TIMEOUT_SECONDS = 3.0
_EXPERIENCE_SCHEMA = "experience.snapshot.v1"


def _unavailable(kind: str = "dependency_down") -> RuntimeSessionError:
    return RuntimeSessionError(503, "SERVICE_UNAVAILABLE", {"kind": kind})


class HttpProductReleaseSource:
    """Fail closed: any delivery problem is an error, never a silent fallback to local files."""

    def __init__(self, base_url: str, key: bytes, kid: str, *, client: httpx.Client | None = None, clock=time.time):
        self._key, self._kid, self._clock = key, kid, clock
        # trust_env=False: studio-api is on the internal network; never route it through an outbound proxy.
        self._client = client or httpx.Client(base_url=base_url, timeout=_TIMEOUT_SECONDS, trust_env=False)

    def _token(self, target: str) -> str:
        now = int(self._clock())
        return jwt.encode({
            "iss": "sda-agent-runtime", "aud": "sda-studio-api", "caller_type": "runtime_service",
            "purpose": "release.delivery", "iat": now, "exp": now + 60, "method": "GET",
            "request_target": target, "body_sha256": hashlib.sha256(b"").hexdigest(),
        }, self._key, algorithm="HS256", headers={"typ": "sda-internal+jwt", "kid": self._kid})

    def _get(self, query: dict[str, str], kind: str) -> object:
        """Signed GET of the active release; the descriptor JSON, or an error for anything else."""
        target = f"{_PATH}?{urlencode(query)}"
        try:
            response = self._client.get(target, headers={
                "x-internal-caller": "sda-agent-runtime", "x-caller-context": self._token(target)})
        except httpx.HTTPError:
            logger.error("{} release delivery unreachable", kind)
            raise _unavailable() from None
        try:
            body = response.json()
        except ValueError:
            body = None
        if response.status_code == 422 and isinstance(body, dict) and (body.get("error") or {}).get("code") == "RES_EXPERIENCE_NOT_CONFIGURED":
            raise RuntimeSessionError(422, "EXPERIENCE_NOT_CONFIGURED")
        if response.status_code != 200 or not isinstance(body, dict) or body.get("success") is not True:
            logger.error("{} release delivery failed: status {}", kind, response.status_code)
            raise _unavailable()
        return body.get("data")

    @staticmethod
    def _descriptor(data: object, kind: str) -> ReleaseDescriptor:
        try:
            return ReleaseDescriptor.model_validate(data)
        except ValidationError as error:
            logger.error("{} release delivery rejected: invalid descriptor at {}", kind,
                         ", ".join(".".join(map(str, item["loc"])) for item in error.errors()[:5]))
            raise _unavailable() from None

    def resolve_active_agent(self, environment: str) -> ReleaseDescriptor:
        descriptor = self._descriptor(self._get({"kind": "agent", "environment": environment}, "agent"), "agent")
        mismatch = (descriptor.kind != "agent" or descriptor.environment != environment
                    or descriptor.delivery_schema_version != "agent.snapshot.v1")
        if mismatch or calculate_content_hash(descriptor.content) != descriptor.content_hash:
            logger.error("agent release delivery rejected: descriptor mismatch")
            raise _unavailable()
        return descriptor

    def resolve_active_experience(self, environment, experience_id, algorithm_profile) -> ReleaseDescriptor:
        query = {"kind": "experience", "environment": environment, "experience_id": experience_id}
        descriptor = self._descriptor(self._get(query, "experience"), "experience")
        content = descriptor.content
        mismatch = (descriptor.kind != "experience" or descriptor.environment != environment
                    or descriptor.delivery_schema_version != _EXPERIENCE_SCHEMA
                    or content.get("schema_version") != descriptor.definition_schema_version
                    or content.get("engine_version") != descriptor.engine_version)
        if mismatch or calculate_content_hash(content) != descriptor.content_hash:
            logger.error("experience release delivery rejected: descriptor mismatch")
            raise _unavailable()
        try:
            profile = profile_for_schema(descriptor.definition_schema_version)
        except KeyError:
            raise RuntimeSessionError(422, "EXPERIENCE_NOT_CONFIGURED") from None
        # Same answer as the local source: an experience on another profile is not configured for this request.
        if profile != algorithm_profile:
            raise RuntimeSessionError(422, "EXPERIENCE_NOT_CONFIGURED")
        return descriptor.model_copy(update={"algorithm_profile": profile})


class CompositeReleaseSource:
    def __init__(self, agent: ProductReleaseSource, experience: ProductReleaseSource):
        self._agent, self._experience = agent, experience

    def resolve_active_agent(self, environment: str) -> ReleaseDescriptor:
        return self._agent.resolve_active_agent(environment)

    def resolve_active_experience(self, environment, experience_id, algorithm_profile) -> ReleaseDescriptor:
        return self._experience.resolve_active_experience(environment, experience_id, algorithm_profile)
