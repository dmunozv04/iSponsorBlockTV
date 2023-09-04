# syntax=docker/dockerfile:1

FROM python:alpine3.11

ENV PIP_NO_CACHE_DIR=off iSPBTV_docker=True TERM=xterm-256color COLORTERM=truecolor

COPY requirements.txt .

RUN pip install --upgrade pip wheel && \
    pip install -r requirements.txt

COPY requirements.txt .

WORKDIR /app

COPY . .

ENTRYPOINT ["python3", "-u", "main.py"]