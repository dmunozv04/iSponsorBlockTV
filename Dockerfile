# syntax=docker/dockerfile:1

FROM python:alpine

RUN python -m venv /opt/venv

ENV PATH="/opt/venv/bin:$PATH" PIP_NO_CACHE_DIR=off

COPY requirements.txt .

RUN apk add gcc musl-dev build-base linux-headers libffi-dev rust cargo openssl-dev git && \
    pip install setuptools-rust && \
    pip install -r requirements.txt && \
    apk del gcc musl-dev build-base linux-headers libffi-dev rust cargo openssl-dev git && \
    rm -rf /root/.cache /root/.cargo


COPY requirements.txt .

WORKDIR /app

COPY main.py .

ENTRYPOINT ["/opt/venv/bin/python3", "-u", "main.py"]
