"""Opening Journey workflow and persona cases for high-school students (T32, DEC-26, 28, FR-WFL-16).

This module defines the opening journey workflow:
1.1 Opening question / exploratory discussion in welcome stage.
1.2 Holland RIASEC introduction and test start in assessment stage.
1.3 Assessment completion, PersonalityCard Digital Aura presentation, explanation and career suggestions in explore/pick_majors stage.
"""
from copy import deepcopy
from typing import Any

from agent_runtime.workflow.constants import STAGE_VARIABLE

OPENING_JOURNEY_WORKFLOW: dict[str, Any] = {
    "entry": "start",
    "variables": [STAGE_VARIABLE],
    "budget": {
        "max_nodes": 30,
        "max_llm_calls": 6,
        "turn_timeout_ms": 25000,
    },
    "nodes": [
        {"id": "start", "type": "start", "title": "Bắt đầu lượt"},
        {
            "id": "check_completed",
            "type": "if_else",
            "title": "Đã hoàn thành trắc nghiệm?",
            "config": {
                "condition": {"==": [{"var": "sys.interaction_outcome"}, "assessment_completed"]}
            },
        },
        {
            "id": "to_explore",
            "type": "assign",
            "title": "Chuyển sang explore",
            "config": {
                "assignments": [{"variable": "conv.stage", "value": "explore"}]
            },
        },
        {
            "id": "answer_completed",
            "type": "answer",
            "title": "Kết quả đánh giá",
            "config": {
                "text": "Chúc mừng bạn đã hoàn thành bài khám phá tính cách! Hãy xem thẻ Digital Aura và nhấn 'Giải thích kết quả' để cùng phân tích các nhóm ngành nghề phù hợp nhé."
            },
        },
        {
            "id": "check_explain",
            "type": "if_else",
            "title": "Yêu cầu giải thích kết quả?",
            "config": {
                "condition": {"==": [{"var": "sys.interaction_outcome"}, "explain_requested"]}
            },
        },
        {
            "id": "explain_agent",
            "type": "agent",
            "title": "Giải thích kết quả và gợi ý ngành",
            "config": {
                "tools": ["result.explain"],
                "instructions": "Giải thích kết quả 6 Hệ tính cách Holland RIASEC và gợi ý các nhóm ngành phù hợp trong career_groups.",
            },
        },
        {
            "id": "to_pick_majors",
            "type": "assign",
            "title": "Chuyển sang chọn ngành",
            "config": {
                "assignments": [{"variable": "conv.stage", "value": "pick_majors"}]
            },
        },
        {
            "id": "answer_explain",
            "type": "answer",
            "title": "Giải thích & Gợi ý ngành",
            "config": {"text": "{{explain_agent.text}}"},
        },
        {
            "id": "in_test",
            "type": "if_else",
            "title": "Đang làm bài trắc nghiệm?",
            "config": {
                "condition": {"==": [{"var": "conv.stage"}, "assessment"]}
            },
        },
        {
            "id": "assess",
            "type": "agent",
            "title": "Hội thoại làm bài trắc nghiệm",
            "config": {
                "tools": [
                    "assessment.set_name",
                    "assessment.current_question",
                    "assessment.propose_answer",
                ],
                "instructions": "Đồng hành cùng học sinh trong quá trình trả lời các câu hỏi tình huống đời thường của bài trắc nghiệm tính cách.",
            },
        },
        {
            "id": "answer_assess",
            "type": "answer",
            "title": "Tiếp tục làm bài",
            "config": {"text": "{{assess.text}}"},
        },
        {
            "id": "check_confirmed",
            "type": "if_else",
            "title": "Hồ sơ vừa được xác nhận?",
            "config": {
                "condition": {"==": [{"var": "sys.interaction_outcome"}, "profile_confirmed"]}
            },
        },
        {
            "id": "check_thpt_level",
            "type": "if_else",
            "title": "Đang học THPT?",
            "config": {
                "condition": {
                    "in": [
                        {"var": "profile.entry_level"},
                        ["thpt_grade_10", "thpt_grade_11", "thpt_grade_12"],
                    ]
                }
            },
        },
        {
            "id": "begin_test",
            "type": "assign",
            "title": "Gán stage assessment",
            "config": {
                "assignments": [{"variable": "conv.stage", "value": "assessment"}]
            },
        },
        {
            "id": "start_test",
            "type": "tool",
            "title": "Khởi động bài đánh giá",
            "config": {
                "tool": "assessment.start",
                "arguments": {"experience_id": "exp_riasec"},
            },
        },
        {
            "id": "answer_start",
            "type": "answer",
            "title": "Giới thiệu Holland và câu 1",
            "config": {
                "text": "Chào mừng bạn bước vào bài khám phá bản thân theo mô hình 6 Hệ tính cách Holland RIASEC! Hãy cho mình biết tên của bạn nhé."
            },
        },
        {
            "id": "answer_other_level",
            "type": "answer",
            "title": "Hỗ trợ đối tượng khác",
            "config": {
                "text": "Chào bạn! Với trình độ của bạn, chúng tôi có các lộ trình đào tạo liên thông hoặc văn bằng 2 phù hợp."
            },
        },
        {
            "id": "intent",
            "type": "intent_classifier",
            "title": "Phân loại ý định mở đầu",
            "config": {
                "input": "{{sys.query}}",
                "labels": [
                    {
                        "id": "lam_bai",
                        "description": "Học sinh muốn bắt đầu làm bài trắc nghiệm khám phá tính cách",
                    },
                    {
                        "id": "tiep_tuc",
                        "description": "Học sinh chia sẻ thông tin hoặc đồng ý tiếp tục",
                    },
                    {
                        "id": "kham_pha_nganh",
                        "description": "Học sinh muốn tìm hiểu về ngành nghề",
                    },
                    {
                        "id": "hoi_hoc_phi",
                        "description": "Học sinh hỏi về học phí, lệ phí",
                    },
                ],
            },
        },
        {
            "id": "prof",
            "type": "profile_propose",
            "title": "Đề xuất thông tin học sinh",
            "config": {
                "fields": ["entry_level", "home_province"],
                "target_step": "career_explore",
                "input": "{{sys.query}}",
            },
        },
        {
            "id": "answer_prof",
            "type": "answer",
            "title": "Phản hồi ghi nhận thông tin học sinh",
            "config": {
                "text": "Mình đã ghi nhận thông tin học tập của bạn! Bạn hãy xác nhận để cùng bắt đầu bài khám phá tính cách nhé."
            },
        },
        {
            "id": "answer_opening",
            "type": "answer",
            "title": "Câu hỏi gợi mở & Mời làm bài",
            "config": {
                "text": "Chào bạn! Mình là IHRD Mentor, người đồng hành hướng nghiệp cho bạn. Để tìm ra ngành nghề phù hợp, bạn có muốn bắt đầu với bài trắc nghiệm 6 Hệ tính cách Holland RIASEC không?"
            },
        },
    ],
    "edges": [
        {"id": "e_start", "source": "start", "source_handle": "next", "target": "check_completed"},
        {"id": "e_comp_true", "source": "check_completed", "source_handle": "true", "target": "to_explore"},
        {"id": "e_comp_false", "source": "check_completed", "source_handle": "false", "target": "check_explain"},
        {"id": "e_to_exp", "source": "to_explore", "source_handle": "next", "target": "answer_completed"},
        {"id": "e_expl_true", "source": "check_explain", "source_handle": "true", "target": "explain_agent"},
        {"id": "e_expl_false", "source": "check_explain", "source_handle": "false", "target": "in_test"},
        {"id": "e_expl_succ", "source": "explain_agent", "source_handle": "success", "target": "to_pick_majors"},
        {"id": "e_expl_hand", "source": "explain_agent", "source_handle": "handoff", "target": "answer_explain"},
        {"id": "e_to_pick", "source": "to_pick_majors", "source_handle": "next", "target": "answer_explain"},
        {"id": "e_test_true", "source": "in_test", "source_handle": "true", "target": "assess"},
        {"id": "e_test_false", "source": "in_test", "source_handle": "false", "target": "check_confirmed"},
        {"id": "e_assess_succ", "source": "assess", "source_handle": "success", "target": "answer_assess"},
        {"id": "e_assess_hand", "source": "assess", "source_handle": "handoff", "target": "answer_assess"},
        {"id": "e_conf_true", "source": "check_confirmed", "source_handle": "true", "target": "check_thpt_level"},
        {"id": "e_conf_false", "source": "check_confirmed", "source_handle": "false", "target": "intent"},
        {"id": "e_lvl_true", "source": "check_thpt_level", "source_handle": "true", "target": "begin_test"},
        {"id": "e_lvl_false", "source": "check_thpt_level", "source_handle": "false", "target": "answer_other_level"},
        {"id": "e_begin", "source": "begin_test", "source_handle": "next", "target": "start_test"},
        {"id": "e_start_test", "source": "start_test", "source_handle": "success", "target": "answer_start"},
        {"id": "e_intent_lam_bai", "source": "intent", "source_handle": "lam_bai", "target": "begin_test"},
        {"id": "e_intent_tiep_tuc", "source": "intent", "source_handle": "tiep_tuc", "target": "prof"},
        {"id": "e_intent_nganh", "source": "intent", "source_handle": "kham_pha_nganh", "target": "answer_opening"},
        {"id": "e_intent_fee", "source": "intent", "source_handle": "hoi_hoc_phi", "target": "answer_opening"},
        {"id": "e_intent_other", "source": "intent", "source_handle": "other", "target": "answer_opening"},
        {"id": "e_prof_prop", "source": "prof", "source_handle": "proposed", "target": "answer_prof"},
        {"id": "e_prof_none", "source": "prof", "source_handle": "none", "target": "answer_opening"},
    ],
}


def thpt_student_opening_case() -> dict[str, Any]:
    """Persona case for high-school student (Lan, Grade 10) journey from start to career suggestions."""
    return {
        "id": "thpt_student_opening_journey",
        "title": "Học sinh THPT làm bài từ đầu",
        "mandatory": True,
        "initial_state": {
            "conv": {"stage": "welcome"},
            "profile": {
                "entry_level": "thpt_grade_10",
                "home_province": "dong_thap",
            },
        },
        "turns": [
            # Turn 1: 1.1 Câu hỏi gợi mở & Đề xuất thông tin học sinh THPT
            {
                "input": {"text": "Em đang học lớp 10 ở Đồng Tháp, chưa biết sau này học gì"},
                "llm_stubs": {
                    "intent": "tiep_tuc",
                    "prof": {"entry_level": "thpt_grade_10", "home_province": "dong_thap"},
                },
                "expect": {
                    "path": [
                        "start",
                        "check_completed",
                        "check_explain",
                        "in_test",
                        "check_confirmed",
                        "intent",
                        "prof",
                        "answer_prof",
                    ],
                    "conv": {"stage": "welcome"},
                    "proposals": 1,
                    "status": "completed",
                },
            },
            # Turn 2: 1.2 Học sinh xác nhận -> Bắt đầu trắc nghiệm Holland RIASEC
            {
                "input": {
                    "interaction": {
                        "action": "confirm_profile",
                        "outcome": "profile_confirmed",
                    }
                },
                "llm_stubs": {},
                "expect": {
                    "path": [
                        "start",
                        "check_completed",
                        "check_explain",
                        "in_test",
                        "check_confirmed",
                        "check_thpt_level",
                        "begin_test",
                        "start_test",
                        "answer_start",
                    ],
                    "conv": {"stage": "assessment"},
                    "proposals": 0,
                    "status": "completed",
                },
            },
            # Turn 3: 1.2 Đang làm bài đánh giá (stage: assessment)
            {
                "input": {"text": "Mình rất thích lắp ráp và tìm hiểu kỹ thuật"},
                "llm_stubs": {
                    "assess": "Mình đã ghi nhận câu trả lời của bạn cho câu hỏi số 1 nhé!",
                },
                "expect": {
                    "path": [
                        "start",
                        "check_completed",
                        "check_explain",
                        "in_test",
                        "assess",
                        "answer_assess",
                    ],
                    "conv": {"stage": "assessment"},
                    "status": "completed",
                },
            },
            # Turn 4: 1.3 Hoàn thành trắc nghiệm -> Thẻ Digital Aura & chuyển sang explore
            {
                "input": {
                    "interaction": {
                        "action": "submit_answer",
                        "outcome": "assessment_completed",
                    }
                },
                "llm_stubs": {},
                "expect": {
                    "path": [
                        "start",
                        "check_completed",
                        "to_explore",
                        "answer_completed",
                    ],
                    "conv": {"stage": "explore"},
                    "status": "completed",
                },
            },
            # Turn 5: 1.3 Yêu cầu giải thích -> result.explain & gợi ý ngành (pick_majors)
            {
                "input": {
                    "interaction": {
                        "action": "explain_result",
                        "outcome": "explain_requested",
                    }
                },
                "llm_stubs": {
                    "explain_agent": "Bạn thuộc Hệ Người Giải Mã (house_i). Bạn có thế mạnh tư duy logic và giải quyết vấn đề. Các nhóm ngành gợi ý phù hợp nhất: Công nghệ thông tin, Khoa học dữ liệu, và Trí tuệ nhân tạo.",
                },
                "expect": {
                    "path": [
                        "start",
                        "check_completed",
                        "check_explain",
                        "explain_agent",
                        "to_pick_majors",
                        "answer_explain",
                    ],
                    "conv": {"stage": "pick_majors"},
                    "status": "completed",
                },
            },
        ],
    }


def opening_journey_workflow() -> dict[str, Any]:
    """Return a deep copy of the opening journey workflow definition."""
    return deepcopy(OPENING_JOURNEY_WORKFLOW)
