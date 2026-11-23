"""Chatflow agent content shared by the chatflow integration suites."""
from agent_runtime.workflow.constants import stage_variable
from tests.helpers.chat import _agent_content


def single_flow(graph: dict, flow_id: str = "main") -> dict:
    """A one-flow chatflow from a single graph: variables and budget move up, the rest is the flow."""
    graph = dict(graph)
    out = {"variables": graph.pop("variables", []), "router": {"default_flow": flow_id}}
    if "budget" in graph:
        out["budget"] = graph.pop("budget")
    out["flows"] = [{"id": flow_id, "title": "Chính", "description": "Mọi câu hỏi của học sinh", **graph}]
    return out


def chatflow_content(workflow):
    content = _agent_content()  # the demo agent, with its start tool pointed at the test experience
    if "flows" not in workflow:
        workflow = single_flow(workflow)
    content.update({"mode": "chatflow", "workflow": workflow,
                    "persona_cases": [{"id": f"c{i}", "title": "x", "mandatory": True,
                                       "turns": [{"input": {"text": "hi"}}]} for i in (1, 2)]})
    return content


STAGE = stage_variable()
FLOW = {"entry": "start", "variables": [STAGE],
        "nodes": [{"id": "start", "type": "start"},
                  {"id": "begin", "type": "assign", "config": {"assignments": [{"variable": "conv.stage", "value": "explore"}]}},
                  {"id": "ask", "type": "intent_classifier", "config": {"labels": [
                      {"id": "hoi_hoc_phi", "description": "hỏi học phí"}, {"id": "lam_bai", "description": "làm bài"}]}},
                  {"id": "reply", "type": "answer", "config": {"text": "Giai đoạn {{conv.stage}}"}}],
        "edges": [{"id": "e1", "source": "start", "source_handle": "next", "target": "begin"},
                  {"id": "e2", "source": "begin", "source_handle": "next", "target": "ask"},
                  {"id": "e3", "source": "ask", "source_handle": "hoi_hoc_phi", "target": "reply"},
                  {"id": "e4", "source": "ask", "source_handle": "lam_bai", "target": "reply"},
                  {"id": "e5", "source": "ask", "source_handle": "other", "target": "reply"}]}
