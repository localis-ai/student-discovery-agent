"""Canonical constants and variable definitions for Chatflow workflows (DEC-28, FR-WFL-02, FR-WFL-07)."""

# DEC-28: Canonical stages for the student consultation journey
STAGE_VALUES: tuple[str, ...] = (
    "welcome",
    "assessment",
    "explore",
    "pick_majors",
    "need",
    "fee",
    "job",
    "followup",
)

STAGE_VARIABLE: dict = {
    "name": "stage",
    "type": "enum",
    "values": list(STAGE_VALUES),
    "default": "welcome",
}

# FR-WFL-02, FR-WFL-07: Canonical intent classifier journey labels (Vietnamese identifiers)
JOURNEY_CLASSIFIER_LABELS: tuple[dict, ...] = (
    {
        "id": "hoi_hoc_phi",
        "description": "Hỏi về học phí, chính sách tài chính, học bổng",
        "examples": ["học phí bao nhiêu", "chi phí một năm thế nào"],
    },
    {
        "id": "viec_lam",
        "description": "Hỏi về cơ hội việc làm, doanh nghiệp liên kết, thực tập",
        "examples": ["ra trường làm gì", "có cơ hội việc làm không"],
    },
    {
        "id": "chon_nganh",
        "description": "Hỏi về chọn ngành, danh sách ngành học hoặc làm bài trắc nghiệm",
        "examples": ["muốn chọn ngành", "ngành nào hợp với mình"],
    },
    {
        "id": "tu_van_nhu_cau",
        "description": "Hỏi về tư vấn nhu cầu, định hướng học tập cá nhân",
        "examples": ["tư vấn giúp mình", "mình cần định hướng"],
    },
    {
        "id": "hoi_tiep",
        "description": "Hỏi thêm, tìm hiểu sâu chi tiết hoặc theo dõi tiếp",
        "examples": ["cho mình hỏi thêm", "tìm hiểu thêm về trường"],
    },
)

# Stage-named classifier labels directly corresponding to DEC-28 stage names
STAGE_CLASSIFIER_LABELS: tuple[dict, ...] = (
    {
        "id": "fee",
        "description": "Hỏi về học phí, ngân sách và chính sách tài chính (Luồng A)",
        "examples": ["học phí bao nhiêu", "học phí các trường"],
    },
    {
        "id": "job",
        "description": "Hỏi về cơ hội việc làm, doanh nghiệp liên kết và thực tập (Luồng B)",
        "examples": ["cơ hội việc làm", "thực tập doanh nghiệp"],
    },
    {
        "id": "pick_majors",
        "description": "Hỏi về chọn ngành và xếp hạng ngành học quan tâm (DEC-26)",
        "examples": ["chọn 3 ngành quan tâm", "xếp hạng ngành"],
    },
    {
        "id": "need",
        "description": "Khảo sát và tư vấn theo nhu cầu học tập",
        "examples": ["tư vấn nhu cầu", "nhu cầu của mình"],
    },
    {
        "id": "followup",
        "description": "Tư vấn mở rộng và theo dõi câu hỏi tiếp theo",
        "examples": ["hỏi thêm thông tin", "theo dõi tiếp"],
    },
)
