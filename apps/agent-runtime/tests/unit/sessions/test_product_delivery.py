import base64
import hashlib
import json
from pathlib import Path

import httpx
import jwt
import pytest

from agent_runtime.evaluations.services.validator import calculate_content_hash
from agent_runtime.infrastructure.product.delivery import CompositeReleaseSource, HttpProductReleaseSource
from agent_runtime.sessions.errors import RuntimeSessionError
from agent_runtime.sessions.schemas.activity import ADAPTIVE_PROFILE

KEY = b"k" * 32
CONTENT = {"greeting_text": "Chào", "allowed_activity_profiles": ["riasec.mean.bounds.v2"]}
TARGET = "/api/v1/internal/releases/active?kind=agent&environment=demo"
GOLDEN = json.loads((Path(__file__).resolve().parents[5] / "contracts/fixtures/runtime-delivery-token.json")
                    .read_text(encoding="utf-8"))


def source(handler):
    client = httpx.Client(transport=httpx.MockTransport(handler), base_url="http://studio-api:3001")
    return HttpProductReleaseSource("http://studio-api:3001", KEY, "runtime", client=client, clock=lambda: 1_800_000_000)


def envelope(data, status=200, success=True):
    return httpx.Response(status, json={"status": status, "success": success, "data": data if success else None,
                                        "error": None if success else {"code": data}})


def descriptor(**overrides):
    return {"environment": "demo", "kind": "agent", "release_id": "agr_" + "a" * 24,
            "content_hash": calculate_content_hash(CONTENT), "delivery_schema_version": "agent.snapshot.v1",
            "content": CONTENT, "is_demo": True, **overrides}


def test_signed_request_returns_the_descriptor():
    seen = {}

    def handler(request):
        seen["request"] = request
        return envelope(descriptor())

    result = source(handler).resolve_active_agent("demo")
    assert result.release_id.startswith("agr_") and result.content == CONTENT
    request = seen["request"]
    assert request.headers["x-internal-caller"] == "sda-agent-runtime"
    claims = jwt.decode(request.headers["x-caller-context"], KEY, algorithms=["HS256"], audience="sda-studio-api",
                        issuer="sda-agent-runtime", options={"verify_exp": False, "verify_iat": False})
    assert claims["request_target"] == TARGET and claims["purpose"] == "release.delivery"
    assert claims["body_sha256"] == hashlib.sha256(b"").hexdigest()
    assert jwt.get_unverified_header(request.headers["x-caller-context"])["kid"] == "runtime"


@pytest.mark.parametrize("case", GOLDEN["cases"], ids=lambda case: case["environment"])
def test_tokens_match_the_fixture_studio_api_verifies(case):
    """studio-api's delivery-auth.test.ts verifies these same tokens; a change on either side breaks one of them."""
    seen = {}

    def handler(request):
        seen["request"] = request
        return envelope(descriptor(environment=case["environment"]))

    golden = HttpProductReleaseSource("http://studio-api:3001", base64.b64decode(GOLDEN["key_base64"]), GOLDEN["kid"],
                                      client=httpx.Client(transport=httpx.MockTransport(handler),
                                                          base_url="http://studio-api:3001"),
                                      clock=lambda: GOLDEN["now"])
    golden.resolve_active_agent(case["environment"])
    assert seen["request"].url.raw_path.decode() == case["target"]
    assert seen["request"].headers["x-caller-context"] == case["token"]


@pytest.mark.parametrize("response,status", [
    (lambda r: envelope(descriptor(content_hash="sha256:" + "0" * 64)), 503),
    (lambda r: envelope(descriptor(kind="experience")), 503),
    (lambda r: envelope(descriptor(environment="production")), 503),
    (lambda r: envelope(descriptor(delivery_schema_version="agent.snapshot.v2")), 503),
    (lambda r: envelope("RES_EXPERIENCE_NOT_CONFIGURED", status=422, success=False), 422),
    (lambda r: httpx.Response(500, text="boom"), 503),
    (lambda r: httpx.Response(200, text="<html>proxy page</html>"), 503),
    (lambda r: envelope("AUTH_CALLER_CONTEXT_INVALID", status=401, success=False), 503),
    (lambda r: envelope("AUTHZ_FORBIDDEN", status=403, success=False), 503),
])
def test_bad_or_missing_releases_fail_closed(response, status):
    with pytest.raises(RuntimeSessionError) as error:
        source(response).resolve_active_agent("demo")
    assert error.value.status == status


def test_network_errors_fail_closed():
    def handler(request):
        raise httpx.ConnectError("down")
    with pytest.raises(RuntimeSessionError) as error:
        source(handler).resolve_active_agent("demo")
    assert error.value.status == 503


def test_composite_routes_agent_and_experience_to_their_sources():
    class Agent:
        def resolve_active_agent(self, environment):
            return "agent"

    class Experience:
        def resolve_active_experience(self, environment, experience_id, profile):
            return "experience"

    composite = CompositeReleaseSource(agent=Agent(), experience=Experience())
    assert composite.resolve_active_agent("demo") == "agent"
    assert composite.resolve_active_experience("demo", "exp", None) == "experience"


EXPERIENCE_FIXTURE = json.loads((Path(__file__).resolve().parents[5] / "contracts/fixtures/experience-delivery-descriptor.json")
                                .read_text(encoding="utf-8"))["descriptor"]
EXP_TARGET = "/api/v1/internal/releases/active?kind=experience&environment=demo&experience_id=exp_riasec"


def experience(**overrides):
    return {**EXPERIENCE_FIXTURE, **overrides}


def test_fixture_descriptor_hashes_like_studio():
    """studio-api's experience-delivery.test.ts checks this fixture against the contract and its own hash."""
    assert calculate_content_hash(EXPERIENCE_FIXTURE["content"]) == EXPERIENCE_FIXTURE["content_hash"]


def test_experience_request_is_signed_and_returns_the_descriptor_with_its_profile():
    seen = {}

    def handler(request):
        seen["request"] = request
        return envelope(experience())

    result = source(handler).resolve_active_experience("demo", "exp_riasec", ADAPTIVE_PROFILE)
    assert result.kind == "experience" and result.release_id == EXPERIENCE_FIXTURE["release_id"]
    assert result.algorithm_profile == ADAPTIVE_PROFILE
    claims = jwt.decode(seen["request"].headers["x-caller-context"], KEY, algorithms=["HS256"],
                        audience="sda-studio-api", issuer="sda-agent-runtime",
                        options={"verify_exp": False, "verify_iat": False})
    assert claims["request_target"] == EXP_TARGET == seen["request"].url.raw_path.decode()
    assert claims["purpose"] == "release.delivery"


@pytest.mark.parametrize("response,status", [
    (lambda r: envelope(experience(content_hash="sha256:" + "0" * 64)), 503),
    (lambda r: envelope(experience(kind="agent")), 503),
    (lambda r: envelope(experience(environment="prod")), 503),
    (lambda r: envelope(experience(delivery_schema_version="experience.snapshot.v2")), 503),
    (lambda r: envelope(experience(definition_schema_version="1.0")), 503),
    (lambda r: envelope(experience(engine_version="other")), 503),
    (lambda r: envelope(experience(definition_schema_version=None)), 503),
    (lambda r: envelope("RES_EXPERIENCE_NOT_CONFIGURED", status=422, success=False), 422),
    (lambda r: httpx.Response(502, text="bad gateway"), 503),
])
def test_bad_or_missing_experience_releases_fail_closed(response, status):
    with pytest.raises(RuntimeSessionError) as error:
        source(response).resolve_active_experience("demo", "exp_riasec", ADAPTIVE_PROFILE)
    assert error.value.status == status


def test_a_profile_mismatch_is_not_configured():
    with pytest.raises(RuntimeSessionError) as error:
        source(lambda r: envelope(experience())).resolve_active_experience("demo", "exp_riasec", None)
    assert (error.value.status, error.value.code) == (422, "EXPERIENCE_NOT_CONFIGURED")


def test_an_unknown_definition_schema_is_not_configured():
    content = {**EXPERIENCE_FIXTURE["content"], "schema_version": "9.0"}
    body = experience(content=content, content_hash=calculate_content_hash(content), definition_schema_version="9.0")
    with pytest.raises(RuntimeSessionError) as error:
        source(lambda r: envelope(body)).resolve_active_experience("demo", "exp_riasec", ADAPTIVE_PROFILE)
    assert (error.value.status, error.value.code) == (422, "EXPERIENCE_NOT_CONFIGURED")
