# Build from repository root: docker compose build mcp-drive
FROM python:3.12-slim-bookworm
ENV PYTHONUNBUFFERED=1
WORKDIR /app

COPY drive-mcp-server/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY drive-mcp-server/app /app/app
ENV PYTHONPATH=/app

EXPOSE 8787
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8787"]
