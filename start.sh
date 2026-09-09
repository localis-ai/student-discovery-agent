#!/bin/bash
export PYTHONUNBUFFERED=1

# Start TaskIQ worker in background (green)
stdbuf -oL taskiq worker app.jobs.taskiq_broker:broker 2>&1 | stdbuf -oL sed 's/^/\x1b[32m[TASKIQ]\x1b[0m /' &

# Start Uvicorn in background (blue)
stdbuf -oL uvicorn main:app --host 0.0.0.0 --port 8000 2>&1 | stdbuf -oL sed 's/^/\x1b[34m[UVICORN]\x1b[0m /' &

wait
