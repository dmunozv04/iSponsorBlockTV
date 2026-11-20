# syntax=docker/dockerfile:1
FROM node:22-alpine AS frontend-builder
WORKDIR /app/frontend
COPY dashboard/frontend/package*.json ./
RUN npm ci
COPY dashboard/frontend/index.html dashboard/frontend/vite.config.js ./
COPY dashboard/frontend/src ./src
COPY dashboard/frontend/public/LogoSponsorBlocker256px.png ./public/LogoSponsorBlocker256px.png
RUN npm run build

FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app/src HOME=/tmp
WORKDIR /app
COPY requirements.txt /app/requirements.txt
COPY dashboard/backend/requirements.txt /app/dashboard-requirements.txt
RUN pip install --no-cache-dir -r requirements.txt -r dashboard-requirements.txt
COPY src /app/src
COPY dashboard/backend/ /app/dashboard/backend/
COPY LICENSE.md /app/LICENSE.md
COPY --from=frontend-builder /app/frontend/dist /app/static
RUN mkdir -p /app/data
EXPOSE 8080
HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health', timeout=3)"
CMD ["uvicorn", "dashboard.backend.main:app", "--host", "0.0.0.0", "--port", "8080", "--no-access-log"]
