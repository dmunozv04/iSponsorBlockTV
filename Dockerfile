# syntax=docker/dockerfile:1
FROM python:3.11-alpine3.19 as BASE

FROM base as compiler

WORKDIR /app

COPY src .

RUN python3 -m compileall -b -f . && \
    find . -name "*.py" -type f -delete

FROM base as DEP_INSTALLER

COPY requirements.txt .

RUN apk add --no-cache gcc musl-dev && \
    pip install --upgrade pip wheel && \
    pip install --user -r requirements.txt && \
    pip uninstall -y pip wheel && \
    apk del gcc musl-dev && \
    python3 -m compileall -b -f /root/.local/lib/python3.11/site-packages && \
    find /root/.local/lib/python3.11/site-packages -name "*.py" -type f -delete && \
    find /root/.local/lib/python3.11/ -name "__pycache__" -type d -exec rm -rf {} +

FROM base

ENV PIP_NO_CACHE_DIR=off iSPBTV_docker=True iSPBTV_data_dir=data TERM=xterm-256color COLORTERM=truecolor

COPY requirements.txt .

COPY --from=dep_installer /root/.local /root/.local

WORKDIR /app

COPY --from=compiler /app .

ENTRYPOINT ["python3", "-u", "main.pyc"]
