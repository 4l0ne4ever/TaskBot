# Build from repository root: docker compose build frontend
FROM node:20-bookworm-slim
WORKDIR /app

ENV NEXT_TELEMETRY_DISABLED=1

COPY frontend/package.json ./
RUN npm install

COPY frontend/ ./

EXPOSE 3000
CMD ["npx", "next", "dev", "-H", "0.0.0.0", "-p", "3000"]
