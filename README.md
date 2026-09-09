# SDA Backend API

Backend for the **Student Discovery Agent (SDA)** — the single API layer over a Neo4j knowledge graph of local knowledge, built to serve GraphRAG: vector search in Neo4j → Cypher traversal → LLM answer with cited sources.

> **Status: scaffold.** The base is in place — auth, users, admin, versioning, and shared infrastructure (Postgres, Redis, Neo4j, TaskIQ). Product modules (GraphRAG, AI Local Guide, itinerary, discovery) are built on top of this.

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
| Knowledge Graph | Neo4j + Graphiti (native vector index) |
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
│       ├── common/         # shared services + utils (redis, neo4j_client, llm, minio, ...)
│       ├── users/
│       └── version/
├── docs/openapi/           # OpenAPI 3.0.3 specs
├── templates/              # Coding/API standards
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

Brings up: `api`, `db` (Postgres), `redis`, `neo4j`, `minio`, `adminer`.

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
