"""Tests for major selection handler and profile ranking (DEC-26, FR-WFL-08)."""
import pytest

from agent_runtime.workflow.ports import InMemoryProfilePort, NullProfilePort


def test_null_profile_port_record_career_groups():
    null_port = NullProfilePort()
    assert null_port.snapshot() == {}
    assert null_port.record_career_groups(["cntt", "marketing"]) == 0


def test_in_memory_profile_port_ranking_and_revision():
    port = InMemoryProfilePort(initial_revision=1)
    assert port.revision == 1
    assert port.snapshot() == {"profile_revision": 1}

    # 1. Record 3 majors -> revision increments to 2
    rev = port.record_career_groups(["cntt", "marketing", "kinh_te"])
    assert rev == 2
    assert port.revision == 2
    assert port.snapshot()["interested_career_groups"] == ["cntt", "marketing", "kinh_te"]

    # 2. Record same majors in same order -> revision does NOT increment
    rev = port.record_career_groups(["cntt", "marketing", "kinh_te"])
    assert rev == 2
    assert port.revision == 2

    # 3. Record same majors with duplicates -> deduplicated preserving order -> revision does NOT increment
    rev = port.record_career_groups(["cntt", "marketing", "cntt", "kinh_te"])
    assert rev == 2
    assert port.revision == 2
    assert port.snapshot()["interested_career_groups"] == ["cntt", "marketing", "kinh_te"]

    # 4. Change order -> semantic change -> revision increments to 3
    rev = port.record_career_groups(["marketing", "cntt", "kinh_te"])
    assert rev == 3
    assert port.revision == 3
    assert port.snapshot()["interested_career_groups"] == ["marketing", "cntt", "kinh_te"]

    # 5. Provide more than 3 majors -> truncates to top 3 preserving order
    # Here ["marketing", "cntt", "kinh_te", "du_lich"] -> top 3 is ["marketing", "cntt", "kinh_te"] (no change)
    rev = port.record_career_groups(["marketing", "cntt", "kinh_te", "du_lich"])
    assert rev == 3
    assert port.revision == 3

    # 6. Change top 3 majors
    rev = port.record_career_groups(["du_lich", "marketing", "cntt"])
    assert rev == 4
    assert port.revision == 4
    assert port.snapshot()["interested_career_groups"] == ["du_lich", "marketing", "cntt"]
