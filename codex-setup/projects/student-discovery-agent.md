# Student Discovery Agent

Repo: `D:\PLUTO\student-discovery-agent`

Backend: Python >=3.12, FastAPI, SQLAlchemy/SQLModel, Neo4j, Redis; dependencies in pyproject.toml and requirements.txt. Read module patterns before changing app/modules/users/crud/user.py. Database migrations live under alembic.

Frontend: `sda-ui`, Next.js 15, React 19, TypeScript, pnpm 9, Node >=20, Vitest.

Candidate validation commands, to run in the correct environment and verify against current repository instructions:

- Backend: `python -m pytest` (check test discovery and service requirements first); `python -m ruff check <changed-files>` when Ruff is installed.
- Frontend from sda-ui: `pnpm typecheck`, `pnpm test`, `pnpm build` as appropriate.

Do not start databases, apply migrations or modify production data merely to validate documentation. No application tests were run for the skill/workspace setup.
