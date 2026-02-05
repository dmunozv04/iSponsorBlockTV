# syntax=docker/dockerfile:1
FROM python:3.13-alpine3.21 AS base

# Build frontend
FROM node:20-alpine AS frontend

WORKDIR /frontend

COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install

COPY frontend/ ./
COPY src/iSponsorBlockTV/ /src/iSponsorBlockTV/
RUN npm run build

# Compile Python
FROM base AS compiler

WORKDIR /app

COPY src .

# Copy built frontend to web/static
COPY --from=frontend /src/iSponsorBlockTV/web/static ./iSponsorBlockTV/web/static

RUN python3 -m compileall -b -f . && \
    find . -name "*.py" -type f -delete

FROM base AS dep_installer

COPY requirements.txt .

RUN apk add --no-cache gcc musl-dev libffi-dev && \
    pip install --upgrade pip wheel && \
    pip install -r requirements.txt && \
    pip uninstall -y pip wheel && \
    apk del gcc musl-dev libffi-dev && \
    python3 -m compileall -b -f /usr/local/lib/python3.13/site-packages && \
    find /usr/local/lib/python3.13/site-packages -name "*.py" -type f -delete && \
    find /usr/local/lib/python3.13/ -name "__pycache__" -type d -exec rm -rf {} +

FROM base

ENV PIP_NO_CACHE_DIR=off iSPBTV_docker=True iSPBTV_data_dir=data TERM=xterm-256color COLORTERM=truecolor ISPONSORBLOCKTV_PORT=42069

EXPOSE 42069

COPY requirements.txt .

COPY --from=dep_installer /usr/local /usr/local

WORKDIR /app

COPY --from=compiler /app .

# Default to web interface, can override with command
ENTRYPOINT ["python3", "-u", "-m", "iSponsorBlockTV.web"]
