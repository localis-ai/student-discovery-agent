import json
from datetime import UTC, datetime

from fastapi.testclient import TestClient

from agent_runtime.api.internal.dependencies import RuntimeContainer, build_runtime
from agent_runtime.config.settings import Settings
from agent_runtime.infrastructure.auth.caller import RawRequestContext
from agent_runtime.infrastructure.auth.verifier import CallerVerifier, ServiceVerifier
from agent_runtime.main import create_app
from agent_runtime.sessions.schemas.common import RuntimePolicy
from tests.helpers.clock import FakeClock
from tests.helpers.signing import sign_service_request

NOW = datetime(2026, 10, 28, tzinfo=UTC)
STUDENT_KEY = b"student-test-key-at-least-32-bytes!!"
STUDIO_KEY = b"studio-test-key-at-least-32-bytes!!"
TARGET = "/api/v1/internal/knowledge/index-runs"


class FakeRunner:
    def __init__(self, answer="started"):
        self.answer, self.requests = answer, 0

    def request(self):
        self.requests += 1
        return self.answer


def call(purpose="knowledge.index", runner=None, body=b"{}"):
    runtime = RuntimeContainer(policy=RuntimePolicy(environment="demo"),
                               verifier=CallerVerifier({"s": STUDENT_KEY}, FakeClock(NOW)),
                               service_verifier=ServiceVerifier({"studio": STUDIO_KEY}, FakeClock(NOW)),
                               knowledge_indexer=runner)
    token = sign_service_request(RawRequestContext("POST", TARGET, body), now=NOW, key=STUDIO_KEY, kid="studio",
                                 purpose=purpose)
    with TestClient(create_app(runtime)) as client:
        return client.post(TARGET, content=body, headers={
            "X-Internal-Caller": "sda-studio-api", "X-Caller-Context": token, "Content-Type": "application/json"})


def test_index_token_gets_202_started():
    runner = FakeRunner()
    response = call(runner=runner)
    assert response.status_code == 202
    assert response.json()["data"] == {"status": "started"}
    assert runner.requests == 1


def test_already_running_is_reported():
    assert call(runner=FakeRunner("already_running")).json()["data"] == {"status": "already_running"}


def test_other_purposes_are_forbidden():
    for purpose in ("knowledge.retrieval", "agent.validate"):
        runner = FakeRunner()
        assert call(purpose=purpose, runner=runner).status_code == 403
        assert runner.requests == 0


def test_retrieval_and_validate_tokens_may_not_be_reused_and_index_token_cannot_retrieve():
    assert call(purpose="knowledge.index", runner=FakeRunner()).status_code == 202


def test_not_configured_is_503():
    response = call(runner=None)
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "SYS_UNAVAILABLE"
    assert response.json()["error"]["details"] == {"kind": "not_configured"}


def test_body_must_be_an_empty_object():
    runner = FakeRunner()
    assert call(runner=runner, body=b'{"x":1}').status_code == 422
    assert runner.requests == 0


def test_runner_is_built_only_when_the_indexer_url_is_set(monkeypatch):
    base = dict(RUNTIME_INTERNAL_KEYRING=None, _env_file=None)
    assert build_runtime(Settings(**base)) is None  # no keyring: unchanged behaviour
    import base64
    keyring = json.dumps({"s": base64.b64encode(STUDENT_KEY).decode()})
    no_url = build_runtime(Settings(RUNTIME_INTERNAL_KEYRING=keyring, _env_file=None))
    assert no_url.knowledge_indexer is None
    with_url = build_runtime(Settings(RUNTIME_INTERNAL_KEYRING=keyring, RUNTIME_KNOWLEDGE_FAKE_EMBEDDING=True,
        RUNTIME_KNOWLEDGE_INDEXER_DATABASE_URL="postgresql+psycopg://u:p@127.0.0.1:1/none", _env_file=None))
    assert with_url.knowledge_indexer is not None
    with_url.knowledge_indexer_engine.dispose()
