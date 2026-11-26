"""Several flows compiled into one graph: the runtime's router node and goto_flow (spec §3, §5)."""
from agent_runtime.agent.model import FakeModel, ModelReply
from agent_runtime.sessions.schemas.workflow import Chatflow
from agent_runtime.workflow.executor import run_workflow
from agent_runtime.workflow.flows import ROUTER_ID, compile_chatflow
from tests.unit.workflow.helpers import budget_for, ports_for, scope_for


def flow(fid, prefix, text, **extra):
    return {"id": fid, "title": fid, "description": f"hỏi về {fid}", "entry": f"{prefix}_start",
            "nodes": [{"id": f"{prefix}_start", "type": "start"},
                      {"id": f"{prefix}_say", "type": "answer", "config": {"text": text}}],
            "edges": [{"id": "e1", "source": f"{prefix}_start", "source_handle": "next", "target": f"{prefix}_say"}],
            **extra}


def goto(raw, target):
    raw["nodes"][1] = {"id": raw["nodes"][1]["id"].replace("_say", "_go"), "type": "goto_flow",
                       "config": {"flow": target}}
    raw["edges"][0]["target"] = raw["nodes"][1]["id"]
    return raw


def chat(*flows, default="hoc_phi"):
    return Chatflow.model_validate({"router": {"default_flow": default}, "flows": list(flows)})


def labels(*texts):
    return FakeModel(*(ModelReply(text=text) for text in texts))


def run(chatflow, *, model=None, outcome="none", interaction=None, halt_after=None):
    graph = compile_chatflow(chatflow)
    scope = scope_for(graph, outcome=outcome, interaction=interaction)
    return run_workflow(graph, scope, ports_for(model=model or labels()), budget=budget_for(graph),
                        halt_after=halt_after)


TWO = (flow("hoc_phi", "hp", "phí"), flow("viec_lam", "vl", "việc"))


def test_a_single_flow_compiles_without_a_router():
    graph = compile_chatflow(chat(flow("hoc_phi", "hp", "phí")))
    assert graph.entry == "hp_start" and ROUTER_ID not in {node.id for node in graph.nodes}
    assert run(chat(flow("hoc_phi", "hp", "phí"))).path == ("hp_start", "hp_say")


def test_the_classifier_picks_a_flow():
    result = run(chat(*TWO), model=labels("viec_lam"))
    assert result.path == ("router", "vl_start", "vl_say") and result.status == "completed"
    assert result.records[0].reason == {"method": "classifier", "flow": "viec_lam", "label": "viec_lam"}
    assert result.records[0].output == {"flow": "viec_lam"}


def test_other_and_a_model_error_go_to_the_default_flow():
    other = run(chat(*TWO), model=labels("other"))
    assert other.path[1] == "hp_start" and other.records[0].reason == {"method": "default", "flow": "hoc_phi",
                                                                        "label": "other"}
    # A reply that names no flow still lands on the default flow, but says so instead of passing for "other".
    garbled = run(chat(*TWO), model=labels("khong_ro"))
    assert garbled.path[1] == "hp_start" and garbled.records[0].reason == {"method": "default", "flow": "hoc_phi",
                                                                          "label": "unrecognized"}
    from agent_runtime.agent.model import ModelUnavailable
    failed = run(chat(*TWO), model=FakeModel(ModelUnavailable("timeout")))
    assert failed.path[1] == "hp_start" and failed.records[0].reason["label"] == "error"


def test_a_trigger_wins_without_calling_the_model():
    trigger = {"==": [{"var": "sys.interaction_outcome"}, "assessment_completed"]}
    result = run(chat(*TWO, flow("ket_qua", "kq", "kết quả", trigger=trigger, routable=False, description="")),
                 outcome="assessment_completed")
    assert result.path[1] == "kq_start" and result.llm_calls == 0
    assert result.records[0].reason == {"method": "trigger", "flow": "ket_qua"}


def test_an_interaction_without_a_trigger_goes_to_the_default_flow():
    result = run(chat(*TWO), interaction="set_name")
    assert result.path[1] == "hp_start" and result.records[0].reason["method"] == "default" and result.llm_calls == 0


def test_one_routable_flow_skips_the_classifier():
    result = run(chat(flow("hoc_phi", "hp", "phí"), flow("an", "an", "ẩn", routable=False, description="")))
    assert result.path[1] == "hp_start" and result.records[0].reason["method"] == "single" and result.llm_calls == 0


def test_goto_flow_runs_the_target_entry_in_the_same_turn():
    result = run(chat(goto(flow("hoc_phi", "hp", "phí"), "viec_lam"), flow("viec_lam", "vl", "việc")),
                 model=labels("hoc_phi"))
    assert result.path == ("router", "hp_start", "hp_go", "vl_start", "vl_say") and result.status == "completed"


def test_a_fourth_flow_switch_falls_back():
    flows = [goto(flow(f"f{i}", f"p{i}", "x"), target) for i, target in enumerate(["f1", "f2", "f3", "f0"])]
    result = run(chat(*flows, default="f0"), model=labels("f0"))
    assert result.status == "fallback" and result.fallback == "workflow_node_error"


def test_halt_after_the_router_only_routes():
    result = run(chat(*TWO), model=labels("viec_lam"), halt_after=ROUTER_ID)
    assert result.path == ("router",) and result.status == "completed" and result.blocks == ()


def test_the_compiled_graph_knows_each_nodes_flow():
    graph = compile_chatflow(chat(*TWO))
    assert graph.flow_of == {"hp_start": "hoc_phi", "hp_say": "hoc_phi", "vl_start": "viec_lam", "vl_say": "viec_lam"}


def test_a_production_trace_keeps_the_routing_decision_and_each_nodes_flow():
    from agent_runtime.workflow.budget import Budget
    from agent_runtime.workflow.trace import Redaction, build_trace

    graph = compile_chatflow(chat(*TWO))
    budget = Budget(graph.budget)
    result = run_workflow(graph, scope_for(graph, query="em hỏi việc làm"), ports_for(model=labels("viec_lam")),
                          budget=budget)
    trace = build_trace(result, redaction=Redaction("production", {}), agent_release_id=None, content_hash=None,
                        mode="chatflow", budget=budget, flow_of=graph.flow_of)
    router, *rest = trace.node_runs
    assert router.flow_id is None and router.output == {"flow": "viec_lam"}
    assert router.reason == {"method": "classifier", "flow": "viec_lam", "label": "viec_lam"}
    assert [run.flow_id for run in rest] == ["viec_lam", "viec_lam"]
    assert "em hỏi việc làm" not in trace.model_dump_json()
