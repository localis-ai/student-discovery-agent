"""Canonical stage and classifier-label templates for the IHRD journey chatflow (DEC-28, FR-WFL-02, FR-WFL-07).

These are authoring templates: ``conv.stage`` is a per-workflow enum variable, so a workflow gets these values only by
declaring ``stage_variable()``. Nothing in the runtime reads them implicitly.
"""
import copy
from typing import Any, TypedDict

# SRS 85-workflow: the stages of the original features, plus the DEC-28 additions for the needs-based journey.
# DEC-28 extends the enum; it never removes a value.
BASE_STAGE_VALUES: tuple[str, ...] = ("welcome", "assessment", "explore", "profile", "match", "report", "handoff")
JOURNEY_STAGE_VALUES: tuple[str, ...] = ("pick_majors", "need", "fee", "job", "followup")
STAGE_VALUES: tuple[str, ...] = BASE_STAGE_VALUES + JOURNEY_STAGE_VALUES

_STAGE_VARIABLE: dict[str, Any] = {"name": "stage", "type": "enum", "values": list(STAGE_VALUES), "default": "welcome"}


def stage_variable() -> dict[str, Any]:
    """A fresh ``conv.stage`` declaration: callers may extend it without touching anyone else's copy."""
    return copy.deepcopy(_STAGE_VARIABLE)


class ClassifierLabel(TypedDict):
    id: str
    description: str
    examples: list[str]


# Provisional names: DEC-28 still leaves the final classifier label set to the Product Owner. ``hoi_viec_lam`` follows
# the DEC-28 proposal; the SRS main labels (lam_bai, kham_pha_nganh, tim_truong, bao_cao, gap_tu_van_vien, tiep_tuc)
# belong to the original features and are not repeated here.
JOURNEY_CLASSIFIER_LABELS: tuple[ClassifierLabel, ...] = (
    {"id": "hoi_hoc_phi", "description": "Hỏi về học phí, chính sách tài chính, học bổng",
     "examples": ["học phí bao nhiêu", "chi phí một năm thế nào"]},
    {"id": "hoi_viec_lam", "description": "Hỏi về cơ hội việc làm, doanh nghiệp liên kết, thực tập",
     "examples": ["ra trường làm gì", "có cơ hội việc làm không"]},
    {"id": "chon_nganh", "description": "Hỏi về chọn ngành, danh sách ngành học hoặc làm bài trắc nghiệm",
     "examples": ["muốn chọn ngành", "ngành nào hợp với mình"]},
    {"id": "tu_van_nhu_cau", "description": "Hỏi về tư vấn nhu cầu, định hướng học tập cá nhân",
     "examples": ["tư vấn giúp mình", "mình cần định hướng"]},
    {"id": "hoi_tiep", "description": "Hỏi thêm, tìm hiểu sâu chi tiết hoặc theo dõi tiếp",
     "examples": ["cho mình hỏi thêm", "tìm hiểu thêm về trường"]},
)

# The same intents keyed by the journey stage each one routes to (the label id is the stage name), for flows where
# the classifier handle feeds an ``assign`` of ``conv.stage`` directly. Every id is a member of JOURNEY_STAGE_VALUES.
STAGE_CLASSIFIER_LABELS: tuple[ClassifierLabel, ...] = (
    {"id": "fee", "description": "Hỏi về học phí, ngân sách và chính sách tài chính (Luồng A, DEC-27)",
     "examples": ["học phí bao nhiêu", "học phí các trường"]},
    {"id": "job", "description": "Hỏi về cơ hội việc làm, doanh nghiệp liên kết và thực tập (Luồng B, DEC-27)",
     "examples": ["cơ hội việc làm", "thực tập doanh nghiệp"]},
    {"id": "pick_majors", "description": "Hỏi về chọn ngành và xếp hạng ngành học quan tâm (DEC-26)",
     "examples": ["chọn 3 ngành quan tâm", "xếp hạng ngành"]},
    {"id": "need", "description": "Khảo sát và tư vấn theo nhu cầu học tập",
     "examples": ["tư vấn nhu cầu", "nhu cầu của mình"]},
    {"id": "followup", "description": "Tư vấn mở rộng và theo dõi câu hỏi tiếp theo",
     "examples": ["hỏi thêm thông tin", "theo dõi tiếp"]},
)
