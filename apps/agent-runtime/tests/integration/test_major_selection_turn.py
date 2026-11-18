# ruff: noqa: F811  (fixtures are imported from test_turn_completion and used as arguments)
"""T30 over signed internal HTTP and real PostgreSQL: a major selection is accepted on a finished activity,
stored with the interaction, and written to the profile only once the turn has committed (DEC-26)."""
import pytest
from sqlalchemy import select

from agent_runtime.infrastructure.db.tables import messages
from agent_runtime.sessions.services.turn_input import parse_turn_input
from agent_runtime.workflow.ports import InMemoryProfilePort
from tests.helpers.turns import current_state, post_turn
from tests.integration.test_turn_completion import capped_definition, completion_http, favour, name, run_answers  # noqa: F401

pytestmark = pytest.mark.integration

MAJORS = ["cntt", "marketing", "kinh_te"]


def selection(rig, major_ids, *, key, revision=None):
    current_revision, activity_revision, _ = current_state(rig)
    return parse_turn_input({
        "type": "interaction", "activity_id": rig.activity_id, "action": "select_majors",
        "payload": {"major_ids": major_ids}, "expected_revision": revision or current_revision,
        "expected_activity_revision": activity_revision, "idempotency_key": key})


def finished(completion_http):
    client, rig, _ = completion_http
    name(client, rig)
    run_answers(client, rig, favour("r"), 12)
    assert current_state(rig)[2]["status"] == "completed"
    rig.service.profile = InMemoryProfilePort(initial_revision=1)
    return client, rig


def test_selection_is_accepted_after_the_assessment_completed_and_projected_after_commit(completion_http):
    client, rig = finished(completion_http)
    before = current_state(rig)[0]
    response = post_turn(client, rig, selection(rig, MAJORS, key="pick-1"))
    assert response.status_code == 200, response.json()
    data = response.json()["data"]
    assert data["status"] == "completed", data.get("error")
    assert data["activity"]["status"] == "completed"
    assert data["output"]["blocks"][0]["type"] == "text"
    assert current_state(rig)[0] == before + 1
    with rig.uow.begin() as session:
        stored = session.scalars(select(messages.c.interaction).where(
            messages.c.conversation_id == rig.conversation_id, messages.c.role == "user")
            .order_by(messages.c.ordinal.desc()).limit(1)).one()
    assert stored["action"] == "select_majors" and stored["major_ids"] == MAJORS
    assert rig.service.profile.snapshot()["interested_career_groups"] == MAJORS
    assert rig.service.profile.revision == 2


def test_a_rejected_selection_never_reaches_the_profile(completion_http):
    client, rig = finished(completion_http)
    stale = selection(rig, MAJORS, key="pick-stale", revision=1)
    assert post_turn(client, rig, stale).status_code == 409
    assert rig.service.profile.revision == 1
    assert "interested_career_groups" not in rig.service.profile.snapshot()


def test_reordering_a_committed_selection_bumps_the_profile_revision(completion_http):
    client, rig = finished(completion_http)
    assert post_turn(client, rig, selection(rig, MAJORS, key="pick-1")).status_code == 200
    assert post_turn(client, rig, selection(rig, MAJORS, key="pick-2")).status_code == 200
    assert rig.service.profile.revision == 2  # same order: idempotent
    assert post_turn(client, rig, selection(rig, MAJORS[::-1], key="pick-3")).status_code == 200
    assert rig.service.profile.revision == 3
    assert rig.service.profile.snapshot()["interested_career_groups"] == MAJORS[::-1]
