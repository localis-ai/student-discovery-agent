"""Email HTML templates for different email types."""

from typing import Any, Dict

LOGO_URL = "https://meobeo.ai/logo2.png"
BRAND_PRIMARY = "#7c3aed"
BRAND_SECONDARY = "#6d28d9"
TEXT_DARK = "#1f2937"
TEXT_LIGHT = "#6b7280"
BORDER_COLOR = "#e5e7eb"

BASE_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
* { margin: 0; padding: 0; }
body {
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  line-height: 1.6;
  margin: 0;
  padding: 0;
  background-color: #f9fafb;
  -webkit-text-size-adjust: 100%;
  -ms-text-size-adjust: 100%;
}
.container {
  max-width: 600px;
  margin: 0 auto;
  background-color: #ffffff;
  border-radius: 8px;
  overflow: hidden;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
  border-collapse: collapse;
}
.header {
  background-color: #7c3aed;
  color: #ffffff;
  padding: 32px 24px;
  text-align: center;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}
.header h2 {
  margin: 0;
  font-size: 26px;
  font-weight: 700;
  letter-spacing: -0.6px;
  line-height: 1.2;
  word-break: break-word;
}
.content {
  padding: 32px 24px;
  color: #1f2937;
  font-size: 15px;
  line-height: 1.8;
}
.content p {
  margin: 14px 0;
  line-height: 1.8;
  word-wrap: break-word;
  -ms-word-wrap: break-word;
}
.content p:first-child { margin-top: 0; }
.content p:last-child { margin-bottom: 0; }
.otp {
  font-size: 32px;
  font-weight: 700;
  text-align: center;
  padding: 18px 16px;
  margin: 24px 0;
  background-color: #f3f4f6;
  border-radius: 8px;
  border-left-width: 4px;
  border-left-style: solid;
  border-left-color: #7c3aed;
  letter-spacing: 3px;
  font-family: 'Courier New', monospace;
  word-spacing: 4px;
}
.footer {
  padding: 24px;
  text-align: center;
  font-size: 12px;
  color: #6b7280;
  border-top-width: 1px;
  border-top-style: solid;
  border-top-color: #e5e7eb;
  background-color: #fafbfc;
  line-height: 1.6;
}
a {
  color: #7c3aed;
  text-decoration: none;
  font-weight: 600;
  transition: color 0.2s ease;
}
a:hover {
  color: #6d28d9;
  text-decoration: underline;
}
.card-section {
  background-color: #f9fafb;
  border-radius: 8px;
  padding: 20px;
  margin: 20px 0;
  border-left: 4px solid #7c3aed;
}
.card-title {
  font-size: 16px;
  font-weight: 700;
  color: #1f2937;
  margin: 0 0 16px 0;
}
.info-row {
  display: flex;
  align-items: flex-start;
  margin: 12px 0;
  font-size: 14px;
  color: #374151;
  line-height: 1.6;
  gap: 12px;
}
.info-label {
  font-weight: 600;
  color: #6b7280;
  min-width: 100px;
}
.info-value {
  color: #1f2937;
  word-wrap: break-word;
  -ms-word-wrap: break-word;
  flex: 1;
}
.button {
  display: inline-block;
  background-color: #7c3aed;
  color: #ffffff !important;
  padding: 12px 28px;
  border-radius: 6px;
  text-decoration: none !important;
  font-weight: 600;
  font-size: 14px;
  margin: 16px 0;
  text-align: center;
  transition: background-color 0.2s ease;
}
.button:hover {
  background-color: #6d28d9;
  color: #ffffff !important;
  text-decoration: none !important;
}
"""


def get_notification_template(context: Dict[str, Any]) -> str:
    """
    Get HTML template for notification email (Vietnamese).

    Context keys:
    - notification_type: str (e.g., "meeting_reminder", "action_item_due", "new_transcript")
    - title: str
    - message: str
    - action_url: str (optional)
    - action_text: str (optional, default: "Xem chi tiết")
    - icon: str (optional emoji)
    """
    action_button_html = ""
    if context.get("action_url"):
        action_text = context.get("action_text", "Xem chi tiết")
        action_button_html = f"""
                <div style="text-align: center; margin: 24px 0;">
                    <a href="{context["action_url"]}" class="button">{action_text}</a>
                </div>
"""

    return f"""
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{context.get("title", "Thông báo")}</title>
        <style>{BASE_CSS}</style>
    </head>
    <body>
        <div class="container">
            <div class="header"><h2>{context.get("title", "Thông báo")}</h2></div>
            <div class="content">
                <p>{context.get("message", "Bạn có một thông báo mới")}</p>
                {action_button_html}
            </div>
            <div class="footer">&copy; Backend API - Đây là một tin nhắn tự động, vui lòng không trả lời.</div>
        </div>
    </body>
    </html>
    """


def get_meeting_creation_template(context: Dict[str, Any]) -> str:
    """
    Get HTML template for meeting creation notification email (Vietnamese).

    Context keys:
    - meeting_title: str
    - meeting_type: str ("online" | "offline" | "hybrid")
    - created_by_name: str
    - created_by_email: str
    - start_time: str (optional)
    - project_name: str (optional)
    - platform: str (optional, for online/hybrid)
    - url: str (optional, for online/hybrid)
    - location: str (optional, for offline/hybrid)
    - action_url: str (optional)
    """
    meeting_type = context.get("meeting_type", "offline").lower()

    type_label = {
        "online": "Trực tuyến",
        "offline": "Trực tiếp",
        "hybrid": "Kết hợp",
    }.get(meeting_type, meeting_type.capitalize())

    # Build type-specific details
    type_details_html = ""
    if meeting_type in ("online", "hybrid") and context.get("platform"):
        type_details_html += f"""
                <div class="info-row">
                    <div class="info-label">Nền tảng:</div>
                    <div class="info-value">{context.get("platform")}</div>
                </div>
"""
    if meeting_type in ("online", "hybrid") and context.get("url"):
        type_details_html += f"""
                <div class="info-row">
                    <div class="info-label">Link tham gia:</div>
                    <div class="info-value"><a href="{context.get("url")}">{context.get("url")}</a></div>
                </div>
"""
    if meeting_type in ("offline", "hybrid") and context.get("location"):
        type_details_html += f"""
                <div class="info-row">
                    <div class="info-label">Địa điểm:</div>
                    <div class="info-value">{context.get("location")}</div>
                </div>
"""

    action_button_html = ""
    if context.get("action_url"):
        action_button_html = f"""
                <div style="text-align: center; margin: 24px 0;">
                    <a href="{context["action_url"]}" class="button">Xem cuộc họp</a>
                </div>
"""

    project_html = ""
    if context.get("project_name"):
        project_html = f"""
                <div class="info-row">
                    <div class="info-label">Dự án:</div>
                    <div class="info-value">{context.get("project_name")}</div>
                </div>
"""

    return f"""
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Cuộc họp mới: {context.get("meeting_title", "Cuộc họp")}</title>
        <style>{BASE_CSS}</style>
    </head>
    <body>
        <div class="container">
            <div class="header"><h2>Cuộc họp mới</h2></div>
            <div class="content">
                <p>Bạn có một cuộc họp mới được tạo bởi <strong>{context.get("created_by_name") or context.get("created_by_email", "N/A")}</strong></p>
                <div class="card-section">
                    <div class="card-title">📋 Chi tiết cuộc họp</div>
                    <div class="info-row">
                        <div class="info-label">Tiêu đề:</div>
                        <div class="info-value">{context.get("meeting_title", "Cuộc họp")}</div>
                    </div>
                    <div class="info-row">
                        <div class="info-label">Hình thức:</div>
                        <div class="info-value">{type_label}</div>
                    </div>
                    {f'<div class="info-row"><div class="info-label">Thời gian:</div><div class="info-value">{context.get("start_time")}</div></div>' if context.get("start_time") else ""}
                    {project_html}
                    {type_details_html}
                </div>
                {action_button_html}
            </div>
            <div class="footer">&copy; Backend API - Đây là một tin nhắn tự động, vui lòng không trả lời.</div>
        </div>
    </body>
    </html>
    """


def get_meeting_note_template(context: Dict[str, Any]) -> str:
    """
    Get HTML template for meeting note email (Vietnamese).

    Context keys:
    - meeting_title: str
    - meeting_date: str
    - meeting_time: str (optional)
    - attendees_count: int (optional)
    - action_url: str (optional)
    """
    action_button_html = ""
    if context.get("action_url"):
        action_button_html = f"""
                <div style="text-align: center; margin: 24px 0;">
                    <a href="{context["action_url"]}" class="button">Xem cuộc họp</a>
                </div>
"""

    details_html = f"""
                <div class="info-row">
                    <div class="info-label">Tiêu đề:</div>
                    <div class="info-value">{context.get("meeting_title", "Cuộc họp")}</div>
                </div>
                <div class="info-row">
                    <div class="info-label">Ngày:</div>
                    <div class="info-value">{context.get("meeting_date", "N/A")}</div>
                </div>
"""

    if context.get("meeting_time"):
        details_html += f"""
                <div class="info-row">
                    <div class="info-label">Thời gian:</div>
                    <div class="info-value">{context.get("meeting_time")}</div>
                </div>
"""

    if context.get("attendees_count"):
        details_html += f"""
                <div class="info-row">
                    <div class="info-label">Người tham gia:</div>
                    <div class="info-value">{context.get("attendees_count")} người</div>
                </div>
"""

    return f"""
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Biên bản cuộc họp - {context.get("meeting_title", "Cuộc họp")}</title>
        <style>{BASE_CSS}</style>
    </head>
    <body>
        <div class="container">
            <div class="header"><h2>Biên bản cuộc họp</h2></div>
            <div class="content">
                <p>Biên bản cuộc họp cho "<strong>{context.get("meeting_title", "cuộc họp")}</strong>" đã được tạo và được gắn kèm trong email này dưới dạng file PDF.</p>
                <div class="card-section">
                    <div class="card-title">📋 Chi tiết cuộc họp</div>
                    {details_html}
                </div>
                {action_button_html}
            </div>
            <div class="footer">&copy; Backend API - Đây là một tin nhắn tự động, vui lòng không trả lời.</div>
        </div>
    </body>
    </html>
    """


def weekly_usage_report_email_html(project_name: str, user_name: str, week_start: str, week_end: str, usage_data: dict) -> tuple:
    """Return weekly usage report HTML in Vietnamese.

    Args:
        project_name (str): Project name for header
        user_name (str): Name of the user receiving the report
        week_start (str): Formatted start date of the week
        week_end (str): Formatted end date of the week
        usage_data (dict): Usage statistics containing:
          - meetings_count: Number of meetings
          - notes_count: Number of meeting summaries (tóm tắt)
          - tasks_count: Number of action items
          - total_hours: Total meeting hours (optional)
          - insights: Dict with percentage changes (optional)

    Returns:
        tuple: (subject_line, html_content)
    """
    enhanced_css = (
        BASE_CSS
        + """
.stats-section {
  background-color: #f0f9ff;
  border-radius: 8px;
  padding: 24px;
  margin: 20px 0;
  border-left: 4px solid #3b82f6;
}
.stats-title {
  font-size: 16px;
  font-weight: 700;
  color: #1f2937;
  margin: 0 0 20px 0;
}
.stats-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  margin: 16px 0;
}
.stat-card {
  background-color: #ffffff;
  border-radius: 6px;
  padding: 14px;
  border: 1px solid #dbeafe;
  text-align: center;
}
.stat-label {
  font-size: 11px;
  font-weight: 600;
  color: #6b7280;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 6px;
}
.stat-value {
  font-size: 28px;
  font-weight: 700;
  color: #3b82f6;
  line-height: 1;
}
.stat-unit {
  font-size: 11px;
  color: #9ca3af;
  margin-top: 4px;
}
.insights-section {
  background-color: #f0fdf4;
  border-radius: 8px;
  padding: 20px;
  margin: 20px 0;
  border-left: 4px solid #10b981;
}
.insights-title {
  font-size: 16px;
  font-weight: 700;
  color: #1f2937;
  margin: 0 0 16px 0;
}
.insight-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 0;
  border-bottom: 1px solid rgba(16, 185, 129, 0.2);
  font-size: 14px;
}
.insight-row:last-child {
  border-bottom: none;
}
.insight-label {
  color: #374151;
  font-weight: 500;
}
.insight-change {
  font-weight: 700;
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 13px;
}
.insight-change.positive {
  background-color: #dcfce7;
  color: #166534;
}
.insight-change.negative {
  background-color: #fee2e2;
  color: #991b1b;
}
.insight-change.neutral {
  background-color: #f3f4f6;
  color: #6b7280;
}
.date-range {
  font-size: 12px;
  color: #6b7280;
  text-align: center;
  margin: 16px 0;
  font-style: italic;
}
"""
    )

    meetings = usage_data.get("meetings_count", 0)
    notes = usage_data.get("notes_count", 0)
    tasks = usage_data.get("tasks_count", 0)
    total_hours = usage_data.get("total_hours", 0)
    insights = usage_data.get("insights", {})

    email_subject = f"Báo cáo usage hàng tuần - {week_start} đến {week_end}"

    # Build insights section HTML
    insights_html = ""
    if insights and isinstance(insights, dict):
        insights_html = """
                <div class="insights-section">
                    <div class="insights-title">📈 Xu hướng tuần này</div>
"""

        metrics = [
            ("Cuộc họp", insights.get("meetings_change", 0)),
            ("Tóm tắt", insights.get("notes_change", 0)),
            ("Tác vụ", insights.get("tasks_change", 0)),
            ("Tổng giờ", insights.get("hours_change", 0)),
        ]

        for label, change_percent in metrics:
            if change_percent == 0:
                change_class = "neutral"
                sign = "→"
            elif change_percent > 0:
                change_class = "positive"
                sign = "↑"
            else:
                change_class = "negative"
                sign = "↓"

            insights_html += f"""                    <div class="insight-row">
                        <div class="insight-label">{label}</div>
                        <div class="insight-change {change_class}">{sign} {change_percent:+.1f}%</div>
                    </div>
"""

        insights_html += """                </div>
"""

    html_content = f"""
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Báo cáo Usage Hàng Tuần</title>
        <style>{enhanced_css}</style>
    </head>
    <body>
        <div class="container">
            <div class="header"><h2>📊 Báo cáo Usage Hàng Tuần</h2></div>
            <div class="content">
                <p>Xin chào <strong>{user_name}</strong>,</p>
                <p>Dưới đây là báo cáo tổng hợp hoạt động và sử dụng dịch vụ của bạn trong tuần.</p>

                <div class="date-range">Từ {week_start} đến {week_end}</div>

                <div class="stats-section">
                    <div class="stats-title">📈 Tổng hợp hoạt động</div>
                    <div class="stats-grid">
                        <div class="stat-card">
                            <div class="stat-label">📅 Cuộc họp</div>
                            <div class="stat-value">{meetings}</div>
                            <div class="stat-unit">cuộc họp</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-label">⏱️ Tổng giờ</div>
                            <div class="stat-value">{total_hours}</div>
                            <div class="stat-unit">giờ</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-label">📋 Tác vụ</div>
                            <div class="stat-value">{tasks}</div>
                            <div class="stat-unit">tác vụ</div>
                        </div>
                        <div class="stat-card" style="grid-column: 1 / -1;">
                            <div class="stat-label">📝 Tóm tắt</div>
                            <div class="stat-value">{notes}</div>
                            <div class="stat-unit">bản tóm tắt</div>
                        </div>
                    </div>
                </div>

                {insights_html}

                <p style="margin-top: 24px; padding-top: 16px; border-top: 1px solid #e5e7eb; font-size: 14px; color: #6b7280;">
                    Cảm ơn bạn đã sử dụng dịch vụ của chúng tôi. Nếu bạn có bất kỳ câu hỏi nào, vui lòng liên hệ với chúng tôi.
                </p>
            </div>
            <div class="footer">&copy; {project_name} - Đây là một tin nhắn tự động, vui lòng không trả lời.</div>
        </div>
    </body>
    </html>
    """

    return (email_subject, html_content)


def meeting_note_email_html(
    project_name: str,
    meeting_info: dict = None,
    note_summary: list = None,
    keywords: list = None,
    task_count: int = 0,
    meeting_id: str = None,
) -> tuple:
    """Return meeting note HTML with meeting info and AI-generated summary.

    Args:
        project_name (str): Project name for header
        meeting_info (dict, optional): Meeting metadata with keys:
            - title: Meeting title
            - date: Formatted date string
            - time: Formatted time string (e.g., "14:30 - 15:30")
            - duration: Formatted duration string (e.g., "1 hour")
            - organizer_name: Name of meeting organizer (optional)
        note_summary (list, optional): List of bullet point strings
        keywords (list, optional): List of keywords extracted from meeting
        task_count (int, optional): Number of tasks in meeting
        meeting_id (str, optional): Meeting ID for dashboard link

    Returns:
        tuple: (subject_line, html_content) - Subject for email and HTML body
    """

    # Enhanced CSS for meeting info and summary sections
    enhanced_css = (
        BASE_CSS
        + """
.logo-container {
  text-align: center;
  padding: 20px 24px;
  background-color: #7c3aed;
}
.logo-img {
  height: 100px;
  display: inline-block;
}
.meeting-info-section {
  background-color: #f9fafb;
  border-radius: 8px;
  padding: 20px;
  margin: 20px 0;
  border-left: 4px solid #7c3aed;
}
.meeting-info-title {
  font-size: 16px;
  font-weight: 700;
  color: #1f2937;
  margin: 0 0 16px 0;
}
.info-row {
  display: flex;
  align-items: flex-start;
  margin: 12px 0;
  font-size: 14px;
  color: #374151;
  line-height: 1.6;
  gap: 12px;
}
.info-icon {
  min-width: 20px;
  font-size: 16px;
  flex-shrink: 0;
}
.info-label {
  font-weight: 600;
  color: #6b7280;
  min-width: 100px;
  display: inline-block;
}
.info-value {
  color: #1f2937;
  word-wrap: break-word;
  -ms-word-wrap: break-word;
  flex: 1;
}
.in-this-meeting-section {
  background-color: #eff6ff;
  border-radius: 8px;
  padding: 20px;
  margin: 20px 0;
  border-left: 4px solid #3b82f6;
}
.in-this-meeting-title {
  font-size: 16px;
  font-weight: 700;
  color: #1f2937;
  margin: 0 0 16px 0;
}
.meeting-stats {
  display: flex;
  gap: 16px;
  margin: 16px 0;
  flex-wrap: wrap;
  justify-content: center;
}
.stat-badge {
  background-color: #dbeafe;
  border-radius: 6px;
  padding: 4px 10px;
  margin: 4px 10px;
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
  font-size: 14px;
  color: #0c4a6e;
}
.stat-badge.tasks {
  background-color: #fee2e2;
  color: #7c2d12;
}
.keywords-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin: 12px 0;
  justify-content: center;
  padding: 0 10px;
}
.keyword-tag {
  background-color: #dbeafe;
  color: #0c4a6e;
  padding: 4px 10px;
  margin: 4px;
  border-radius: 16px;
  font-size: 12px;
  font-weight: 500;
  white-space: normal;
}
.summary-section {
  background-color: #f9fafb;
  border-radius: 8px;
  padding: 20px;
  margin: 20px 0;
  border-left: 4px solid #10b981;
}
.summary-title {
  font-size: 16px;
  font-weight: 700;
  color: #1f2937;
  margin: 0 0 16px 0;
}
.summary-list {
  list-style: none;
  padding: 0;
  margin: 0;
}
.summary-bullet {
  display: flex;
  align-items: flex-start;
  margin: 10px 0;
  font-size: 14px;
  color: #374151;
  line-height: 1.6;
}
.bullet-point {
  min-width: 20px;
  margin-right: 10px;
  color: #10b981;
  font-weight: 700;
}
.bullet-text {
  color: #1f2937;
  word-wrap: break-word;
  -ms-word-wrap: break-word;
}
.view-button {
  display: inline-block;
  background-color: #7c3aed;
  color: #ffffff !important;
  padding: 12px 28px;
  border-radius: 6px;
  text-decoration: none !important;
  font-weight: 600;
  font-size: 14px;
  margin: 16px 0;
  text-align: center;
  transition: background-color 0.2s ease;
}
.view-button:hover {
  background-color: #6d28d9;
  color: #ffffff !important;
  text-decoration: none !important;
}
"""
    )

    # Build logo section
    logo_section = """
            <div class="logo-container">
                <img src="https://meeting-agent-stag.wc504.io.vn/images/logos/logo.png" alt="Logo" class="logo-img">
            </div>
"""

    # Build in-this-meeting section
    in_this_meeting_html = """
            <div class="in-this-meeting-section">
                <div class="in-this-meeting-title">📊 Trong cuộc họp này</div>
                <div class="meeting-stats">
"""

    if task_count > 0:
        in_this_meeting_html += f"""                    <div class="stat-badge tasks">📋 {task_count} việc cần làm</div>
"""

    in_this_meeting_html += """                </div>
"""

    # Add keywords if available
    if keywords and isinstance(keywords, list) and len(keywords) > 0:
        in_this_meeting_html += """                <div style="margin-top: 20px; padding-top: 16px; border-top: 1px solid rgba(59, 130, 246, 0.2);">
                    <div style="font-weight: 700; font-size: 14px; color: #1f2937; margin-bottom: 12px; text-align: center;">Từ khóa:</div>
                    <div class="keywords-list">
"""
        for keyword in keywords[:10]:  # Display up to 10 keywords
            in_this_meeting_html += f"""                        <span class="keyword-tag">{keyword}</span>
"""
        in_this_meeting_html += """                    </div>
                </div>
"""

    in_this_meeting_html += """            </div>
"""

    # Build header with dynamic title
    header_title = meeting_info.get("title", "Meeting Note") if meeting_info else "Meeting Note"
    header_html = f"""<h2>Meeting note của bạn - {header_title}</h2>"""

    # Prepare email subject
    email_subject = f"Meeting note của bạn - {header_title}"

    # Build meeting info section
    meeting_info_html = ""
    if meeting_info:
        meeting_info_html = """
            <div class="meeting-info-section">
                <div class="meeting-info-title">📋 Chi tiết cuộc họp</div>
"""

        # Date
        if meeting_info.get("date"):
            meeting_info_html += f"""
                <div class="info-row">
                    <div class="info-icon">📆</div>
                    <div><span class="info-label">Ngày:</span><span class="info-value">{meeting_info["date"]}</span></div>
                </div>
"""

        # Time
        if meeting_info.get("time"):
            meeting_info_html += f"""
                <div class="info-row">
                    <div class="info-icon">🕒</div>
                    <div><span class="info-label">Thời gian:</span><span class="info-value">{meeting_info["time"]}</span></div>
                </div>
"""

        # Duration
        if meeting_info.get("duration"):
            meeting_info_html += f"""
                <div class="info-row">
                    <div class="info-icon">⏱️</div>
                    <div><span class="info-label">Thời lượng:</span><span class="info-value">{meeting_info["duration"]}</span></div>
                </div>
"""

        meeting_info_html += """
            </div>
"""

    # Build summary section
    summary_section_html = ""
    if note_summary and isinstance(note_summary, list) and len(note_summary) > 0:
        summary_section_html = """
            <div class="summary-section">
                <div class="summary-title">✨ Tóm tắt nhanh</div>
                <ul class="summary-list">
"""
        for bullet in note_summary[:5]:  # Limit to 5 bullets
            # Truncate if too long
            if len(bullet) > 120:
                bullet = bullet[:117] + "..."
            summary_section_html += f"""
                    <li class="summary-bullet">
                        <span class="bullet-point">•</span>
                        <span class="bullet-text">{bullet}</span>
                    </li>
"""
        summary_section_html += """
                </ul>
            </div>
"""

    # Build view button section
    button_html = ""
    if meeting_id:
        meeting_url = f"https://meeting-agent-stag.wc504.io.vn/dashboard/meetings/{meeting_id}"
        button_html = f"""
                <div style="text-align: center; margin: 24px 0; color: #ffffff; text-decoration: none;">
                    <a href="{meeting_url}" class="view-button">Xem Cuộc Họp</a>
                </div>
"""

    html_content = f"""
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{header_title}</title>
        <style>{enhanced_css}</style>
    </head>
    <body>
        <div class="container">
            {logo_section}
            <div class="header">{header_html}</div>
            <div class="content">
                {in_this_meeting_html}

                {meeting_info_html}

                {summary_section_html}

                {button_html}

                <p style="margin-top: 24px; padding-top: 16px; border-top: 1px solid #e5e7eb; font-size: 14px; color: #6b7280;">
                    Chúng tôi đã đính kèm ghi chú đầy đủ dưới dạng tệp PDF để bạn dễ dàng tham khảo và chia sẻ.
                </p>
            </div>
            <div class="footer">&copy; {project_name} - Đây là một tin nhắn tự động, vui lòng không trả lời.</div>
        </div>
    </body>
    </html>
    """

    return (email_subject, html_content)
