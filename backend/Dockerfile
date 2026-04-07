# Build from repository root: docker compose build backend
FROM python:3.12-slim-bookworm
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY backend/ /app/backend/

RUN chmod +x /app/backend/docker-entrypoint.sh

WORKDIR /app/backend
ENV PYTHONPATH=/app/backend

EXPOSE 8000
ENTRYPOINT ["/app/backend/docker-entrypoint.sh"]
