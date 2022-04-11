# syntax=docker/dockerfile:1

FROM python:alpine

RUN python -m venv /opt/venv

ENV PATH="/opt/venv/bin:$PATH" PIP_NO_CACHE_DIR=off iSPBTV_docker=True

COPY requirements.txt .

RUN apk add gcc musl-dev build-base linux-headers libffi-dev rust cargo openssl-dev git avahi && \
    pip install --upgrade pip setuptools-rust wheel && \
    pip install -r requirements.txt && \
    apk del gcc musl-dev build-base linux-headers libffi-dev rust cargo openssl-dev git && \
    rm -rf /root/.cache /root/.cargo


COPY requirements.txt .

WORKDIR /app

COPY *.py .

ENTRYPOINT ["/opt/venv/bin/python3", "-u", "main.py"]
