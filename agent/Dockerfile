# Build from repository root: docker compose build agent
FROM python:3.12-slim-bookworm
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY agent/ /app/agent/

WORKDIR /app/agent
ENV PYTHONPATH=/app/agent

CMD ["python", "-m", "app.scheduler.worker"]
