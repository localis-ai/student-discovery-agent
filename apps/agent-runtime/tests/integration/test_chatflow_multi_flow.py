"""A multi-flow chatflow through a real turn: router choice, goto_flow and what the stored trace says about them."""
import pytest

from agent_runtime.agent.model import ModelReply
from agent_runtime.infrastructure.db.trace import DatabaseTraceSink
from tests.helpers.chat import build_chat
from tests.helpers.chatflow import chatflow_content
from tests.integration.test_chatflow_trace import LateSink, stored_turn

pytestmark = pytest.mark.integration


def flow(fid, prefix, text, *, goto=None):
    last = {"id": f"{prefix}_go", "type": "goto_flow", "config": {"flow": goto}} if goto else \
        {"id": f"{prefix}_say", "type": "answer", "config": {"text": text}}
    return {"id": fid, "title": fid, "description": f"hỏi về {fid}", "entry": f"{prefix}_start",
            "nodes": [{"id": f"{prefix}_start", "type": "start"}, last],
            "edges": [{"id": "e1", "source": f"{prefix}_start", "source_handle": "next", "target": last["id"]}]}


def chatflow(*flows):
    return {"router": {"default_flow": "hoc_phi"}, "flows": list(flows)}


@pytest.fixture
def rig(test_database, valid_v2_doc, validator):
    rigs = []

    def make(workflow):
        sink = LateSink()
        made = build_chat(test_database, valid_v2_doc, validator, trace_sink=sink,
                          agent_content=chatflow_content(workflow))
        sink.sink = DatabaseTraceSink(made.uow)
        rigs.append(made)
        return made

    yield make
    for made in rigs:
        made.dispose()


def test_the_router_classifies_the_turn_into_a_flow_and_the_trace_says_which(rig):
    chat = rig(chatflow(flow("hoc_phi", "hp", "phí"), flow("viec_lam", "vl", "việc")))
    chat.model._outcomes.append(ModelReply(text="viec_lam"))
    data = chat.send("ra trường làm gì", revision=0, key="m1").data
    assert data["output"]["blocks"][0]["content"] == "việc"
    trace = stored_turn(chat)["workflow"]
    assert [(run["node_id"], run["flow_id"]) for run in trace["node_runs"]] == [
        ("router", None), ("vl_start", "viec_lam"), ("vl_say", "viec_lam")]
    assert trace["node_runs"][0]["reason"] == {"method": "classifier", "flow": "viec_lam", "label": "viec_lam"}
    assert trace["fallback_at"] is None


def test_goto_flow_hands_the_turn_to_another_flow_in_the_same_turn(rig):
    chat = rig(chatflow(flow("hoc_phi", "hp", "", goto="viec_lam"), flow("viec_lam", "vl", "việc")))
    chat.model._outcomes.append(ModelReply(text="hoc_phi"))
    data = chat.send("học phí", revision=0, key="m1").data
    assert data["output"]["blocks"][0]["content"] == "việc" and len(chat.model.calls) == 1
    trace = stored_turn(chat)["workflow"]
    assert [run["node_id"] for run in trace["node_runs"]] == ["router", "hp_start", "hp_go", "vl_start", "vl_say"]


def test_a_reply_that_names_no_flow_lands_on_the_default_flow_and_is_marked(rig):
    chat = rig(chatflow(flow("hoc_phi", "hp", "phí"), flow("viec_lam", "vl", "việc")))
    chat.model._outcomes.append(ModelReply(text="em không biết"))
    data = chat.send("xin chào", revision=0, key="m1").data
    assert data["output"]["blocks"][0]["content"] == "phí"
    assert stored_turn(chat)["workflow"]["node_runs"][0]["reason"] == {
        "method": "default", "flow": "hoc_phi", "label": "unrecognized"}
