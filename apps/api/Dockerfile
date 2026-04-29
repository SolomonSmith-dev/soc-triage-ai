FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Copy workspace structure for path-based deps
COPY services/triage-worker /app/services/triage-worker
COPY apps/api /app/apps/api

RUN pip install --upgrade pip \
 && pip install -e /app/services/triage-worker \
 && pip install -e /app/apps/api

WORKDIR /app/apps/api

EXPOSE 8000
CMD ["uvicorn", "soc_api.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
