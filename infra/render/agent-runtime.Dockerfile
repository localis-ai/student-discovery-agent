# Render build from the repository root; see .dockerignore for what is sent.
# The agent and experiences come from studio-api (Product delivery); no releases are packaged in the image.
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src

WORKDIR /app

COPY apps/agent-runtime/requirements.txt apps/agent-runtime/pyproject.toml ./
RUN pip install --no-cache-dir -r requirements.txt

COPY apps/agent-runtime/src ./src
COPY apps/agent-runtime/alembic.ini ./
COPY apps/agent-runtime/migrations ./migrations
RUN pip install --no-cache-dir --no-deps .

RUN groupadd -r appuser && useradd -r -g appuser appuser
USER appuser

EXPOSE 10000

# Render injects PORT; exec keeps uvicorn as PID 1 so SIGTERM reaches it.
CMD ["sh", "-c", "exec uvicorn agent_runtime.main:app --host 0.0.0.0 --port ${PORT:-10000} --no-access-log"]
