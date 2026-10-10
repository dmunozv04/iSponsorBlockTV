# syntax=docker/dockerfile:1
FROM python:3.13-alpine3.21 AS base

FROM base AS compiler

WORKDIR /app

COPY src .

RUN python3 -m compileall -b -f . && \
    find . -name "*.py" -type f -delete

FROM base AS dep_installer

COPY requirements.txt .

RUN apk add --no-cache gcc musl-dev && \
    pip install --upgrade pip wheel && \
    pip install -r requirements.txt && \
    pip uninstall -y pip wheel && \
    apk del gcc musl-dev && \
    python3 -m compileall -b -f /usr/local/lib/python3.13/site-packages && \
    find /usr/local/lib/python3.13/site-packages -name "*.py" -type f -delete && \
    find /usr/local/lib/python3.13/ -name "__pycache__" -type d -exec rm -rf {} +

FROM base AS playback

ENV PIP_NO_CACHE_DIR=off iSPBTV_docker=True iSPBTV_data_dir=data TERM=xterm-256color COLORTERM=truecolor

COPY requirements.txt .

COPY --from=dep_installer /usr/local /usr/local

WORKDIR /app

COPY --from=compiler /app .

ENTRYPOINT ["python3", "-u", "main.pyc"]

# Install discovery dependencies separately from the playback service.
FROM base AS web_dependencies
RUN apk add --no-cache gcc musl-dev
RUN pip install --no-cache-dir --target /paneldeps PyChromecast==14.0.10

# Combine our compiled playback service with the web panel.
FROM playback AS web
COPY --from=web_dependencies /paneldeps /paneldeps
COPY webui/server.py webui/cast_helper.py /web/
COPY webui/static /web/static

ENV WEB_PORT=1166 \
    DATA_DIR=/app/data \
    ALLOWED_NETWORKS=192.168.0.0/16

EXPOSE 1166

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD python3 -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:'+os.getenv('WEB_PORT','1166')+'/health',timeout=3)" || exit 1

ENTRYPOINT ["python3", "-u", "/web/server.py"]
