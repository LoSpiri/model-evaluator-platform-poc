#!/bin/bash
set -e
uv run alembic upgrade head
exec uv run uvicorn qml_platform.main:app --host "${HOST:-0.0.0.0}" --port "${PORT:-8000}"
