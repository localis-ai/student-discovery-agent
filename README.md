# SDA Backend API

Backend của **IHRD GenZ Career Agent** (Student Discovery Agent, SDA) — chatbot tư vấn hướng nghiệp cho học sinh THPT lớp 10–12 ở ĐBSCL, nhúng vào `ihrd.vn` dưới dạng widget chat mobile. Agent chỉ tư vấn trong mạng lưới 12 trường liên kết.

Thiết kế cốt lõi: **hồ sơ học sinh là trung tâm** (slot có kiểu, append-only, có bằng chứng), LLM chỉ đảm nhận 4 vai trò hẹp (sàng lọc an toàn, thông dịch, diễn đạt, trả lời câu mở), và **mọi con số hiển thị đều đến từ kho sự kiện, không từ LLM** — được chặn bằng cổng kiểm số trước khi phát. Chi tiết: [docs/superpowers/specs/2026-09-23-ihrd-career-agent-architecture.md](docs/superpowers/specs/2026-09-23-ihrd-career-agent-architecture.md).

> **Trạng thái: scaffold.** Đã có phần nền — auth, users, admin, versioning và hạ tầng dùng chung (Postgres, Redis, TaskIQ, MinIO). Phần agent (hồ sơ/slot, resolver, catalog, RAG, cổng kiểm) đang ở giai đoạn thiết kế, chưa triển khai.

---

## Base modules (scaffold)

- Auth: email/password, JWT, refresh tokens
- Admin: admin auth, user CRUD, bulk ops
- Users: profile, avatar, password management
- Common: response wrapping, request tracking, error standardization, timeouts, logging
- Versioning module

---

## Tech Stack

| Component       | Tech                            |
|-----------------|---------------------------------|
| Language        | Python 3.12                     |
| Framework       | FastAPI + Uvicorn               |
| ORM             | SQLAlchemy 2.0 / SQLModel       |
| App DB          | Postgres (Supabase)             |
| Kho sự kiện + tri thức (thiết kế) | Postgres + pgvector (chưa triển khai) |
| Agent framework (thiết kế) | Agno SDK, nhúng trong FastAPI (chưa triển khai) |
| LLM | Gemini qua `google-genai` |
| Cache / broker  | Redis                           |
| Task queue      | TaskIQ + Redis                  |
| Object storage  | MinIO                           |
| Auth            | JWT, argon2 / bcrypt            |

---

## Project Structure

```
├── app
│   ├── constants/          # Messages, shared constants
│   ├── core/               # Config, OAuth utils, vault loader
│   ├── db/                 # Engine and session (Postgres)
│   ├── exception_handlers/ # HTTP + error middleware
│   ├── jobs/               # TaskIQ broker
│   ├── models/             # SQLAlchemy / SQLModel models
│   └── modules/            # Feature modules
│       ├── admin/
│       ├── common/         # shared services + utils (redis, llm, minio, ...)
│       ├── users/
│       └── version/
├── docs/
│   ├── openapi/            # OpenAPI 3.0.3 specs
│   ├── superpowers/specs/  # Thiết kế kiến trúc agent
│   └── mockup/             # Mockup + steps.json (bản ghi vàng 41 bước)
├── templates/              # Coding/API standards
├── sda-ui/                 # Frontend (Next.js) — see sda-ui/README.md
├── main.py
├── docker-compose.local.yml
├── Dockerfile
├── pyproject.toml
└── requirements.txt
```

Module layout: `crud/`, `routes/`, `schemas/`, `services/`, `utils/`.

---

## Getting Started

Requirements: Docker, Docker Compose.

```bash
cp .env.example .env
docker-compose -f docker-compose.local.yml up --build
```

Brings up: `api`, `db` (Postgres), `redis`, `minio`, `adminer`, và `neo4j` (còn sót từ scaffold, xem lưu ý bên dưới).

For the LLM module (Gemini via `google-genai`), set `GOOGLE_API_KEY` in `.env` (or `GOOGLE_CLOUD_PROJECT`/`GOOGLE_CLOUD_LOCATION` to use Vertex AI instead).

> **Lưu ý:** hướng Neo4j/Graphiti/GraphRAG đã bị loại bỏ trong thiết kế (truy vấn nông, quy mô cỡ nghìn bản ghi — không bù nổi chi phí vận hành thêm một hệ). Dependency `neo4j`, `graphiti-core`, `neo4j_client.py` và service `neo4j` trong compose còn sót từ scaffold, sẽ được gỡ.

---

## Frontend

Next.js app lives in [`sda-ui/`](sda-ui/README.md) — separate `package.json`, run independently (see its README for dev/Docker instructions).

---

## API Documentation

| Module | Spec                                          |
|--------|-----------------------------------------------|
| Users  | [user-api.yaml](docs/openapi/user-api.yaml)   |
| Admin  | [admin-api.yaml](docs/openapi/admin-api.yaml) |

Error codes: [docs/openapi/error_codes.md](docs/openapi/error_codes.md).

---

## Standards

See `templates/`:

| #  | File                                                                            |
|----|---------------------------------------------------------------------------------|
| 01 | [Coding_Convention](templates/01_Coding_Convention.md)                          |
| 02 | [API_Naming_Convention](templates/02_API_Naming_Convention.md)                  |
| 03 | [API_Response_Guideline](templates/03_API_Response_Guideline.md)                |
| 04 | [Error_Code_Guideline](templates/04_Error_Code_Guideline.md)                    |
| 05 | [API_Timeout_Configuration](templates/05_API_Timeout_Configuration.md)          |
| 06 | [Readme template](templates/06_Readme.md)                                       |
| 07 | [TL_QA_review_checklist](templates/07_TL_QA_review_checklist.md)                |

---

## Testing

No test suite yet (scaffold). `pytest` is configured via `pytest.ini`; add tests under `tests/`.

```bash
pytest
```

---

## Commit Convention

Format: `<type>(scope): subject` per [.github/commit_guide.instructions.md](.github/commit_guide.instructions.md).
