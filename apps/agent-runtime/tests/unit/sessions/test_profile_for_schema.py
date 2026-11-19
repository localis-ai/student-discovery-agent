import pytest

from agent_runtime.sessions.schemas.activity import ADAPTIVE_PROFILE, profile_for_schema


def test_known_schemas_map_to_their_profiles():
    assert profile_for_schema("1.0") is None
    assert profile_for_schema("2.0") == ADAPTIVE_PROFILE


@pytest.mark.parametrize("version", ["3.0", "", "2"])
def test_unknown_schema_raises_key_error(version):
    with pytest.raises(KeyError):
        profile_for_schema(version)
