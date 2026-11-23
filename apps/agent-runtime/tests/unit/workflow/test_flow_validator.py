"""The graph validator above one flow: ids across flows, the router, triggers and goto_flow (spec §6)."""
from agent_runtime.workflow.validator import validate_workflow


def flow(fid, prefix, **extra):
    return {"id": fid, "title": fid, "description": f"hỏi {fid}", "entry": f"{prefix}_s",
            "nodes": [{"id": f"{prefix}_s", "type": "start"},
                      {"id": f"{prefix}_a", "type": "answer", "config": {"text": "x"}}],
            "edges": [{"id": "e1", "source": f"{prefix}_s", "source_handle": "next", "target": f"{prefix}_a"}], **extra}


def goto(raw, target):
    raw["nodes"][1] = {"id": raw["nodes"][1]["id"], "type": "goto_flow", "config": {"flow": target}}
    return raw


def chat(*flows, default="a", **extra):
    return {"router": {"default_flow": default}, "flows": list(flows), **extra}


def codes(raw):
    return {(finding.path, finding.code) for finding in validate_workflow(raw, {}, {})}


def test_two_clean_flows():
    assert codes(chat(flow("a", "a"), flow("b", "b"))) == set()


def test_graph_findings_point_into_their_flow():
    broken = flow("b", "b")
    broken["edges"] = []
    assert ("workflow.flows[1].nodes[1]", "workflow_unreachable_node") in codes(chat(flow("a", "a"), broken))


def test_a_node_id_used_in_two_flows():
    assert ("workflow.flows[1].nodes[0].id", "workflow_node_id_duplicate") in codes(chat(flow("a", "a"), flow("b", "a")))


def test_goto_to_an_unknown_flow_or_to_itself():
    found = codes(chat(goto(flow("a", "a"), "zzz"), goto(flow("b", "b"), "b")))
    assert ("workflow.flows[0].nodes[1].config.flow", "workflow_goto_invalid") in found
    assert ("workflow.flows[1].nodes[1].config.flow", "workflow_goto_invalid") in found


def test_flows_that_goto_each_other():
    assert any(code == "workflow_goto_cycle" for _, code in codes(chat(goto(flow("a", "a"), "b"),
                                                                        goto(flow("b", "b"), "a"))))


def test_goto_flow_ends_its_branch():
    assert codes(chat(goto(flow("a", "a"), "b"), flow("b", "b"))) == set()


def test_triggers_are_parsed_and_read_known_variables():
    unknown = flow("b", "b", trigger={"==": [{"var": "conv.nope"}, "x"]})
    unparsable = flow("c", "c", trigger={"regex": [1]})
    known = flow("d", "d", trigger={"==": [{"var": "sys.interaction_outcome"}, "assessment_completed"]})
    found = codes(chat(flow("a", "a"), unknown, unparsable, known))
    assert ("workflow.flows[1].trigger", "workflow_trigger_invalid") in found
    assert ("workflow.flows[2].trigger", "workflow_trigger_invalid") in found
    assert not any(path.startswith("workflow.flows[3]") for path, _ in found)


def test_router_flow_rules_and_limits():
    assert ("workflow.router.default_flow", "workflow_flow_invalid") in codes(chat(flow("a", "a"), default="x"))
    hidden = flow("a", "a", routable=False, description="")
    assert ("workflow.router.default_flow", "workflow_flow_invalid") in codes(chat(hidden))
    assert ("workflow.flows[0].description", "workflow_flow_invalid") in codes(chat(flow("a", "a", description=" ")))
    assert ("workflow.flows[0].id", "workflow_flow_invalid") in codes(chat(flow("other", "o"), default="other"))
    many = chat(*[flow(f"f{i}", f"p{i}") for i in range(11)], default="f0")
    assert ("workflow.flows", "workflow_too_large") in codes(many)
    sixty_one = chat(flow("a", "a"), variables=[{"name": f"v{i}", "type": "string", "default": ""} for i in range(61)])
    assert ("workflow.variables", "workflow_too_large") in codes(sixty_one)


def test_the_router_id_is_reserved():
    taken = flow("a", "a")
    taken["nodes"][1]["id"] = "router"
    taken["edges"][0]["target"] = "router"
    assert ("workflow.flows[0].nodes[1].id", "workflow_node_id_reserved") in codes(chat(taken))


def test_a_non_string_flow_id_is_a_finding_not_a_crash():
    broken = flow("a", "a")
    broken["edges"] = []
    found = codes(chat(broken, {**flow("b", "b"), "id": ["b"]}))  # the bad id itself is the schema layer's finding
    assert ("workflow.flows[0].nodes[1]", "workflow_unreachable_node") in found


def test_a_goto_chain_longer_than_the_turn_allows_is_rejected():
    within = [goto(flow(f, f), t) for f, t in zip("abc", "bcd", strict=True)] + [flow("d", "d")]
    assert not any(code == "workflow_goto_invalid" for _, code in codes(chat(*within)))
    too_long = [goto(flow(f, f), t) for f, t in zip("abcd", "bcde", strict=True)] + [flow("e", "e")]
    assert ("workflow.flows[0].nodes[1].config.flow", "workflow_goto_invalid") in codes(chat(*too_long))
