# syntax=docker/dockerfile:1

FROM python:3.11-alpine

ENV PIP_NO_CACHE_DIR=off iSPBTV_docker=True iSPBTV_data_dir=data TERM=xterm-256color COLORTERM=truecolor

COPY requirements.txt .

RUN pip install --upgrade pip wheel && \
    pip install -r requirements.txt


WORKDIR /app

RUN python -m compileall

COPY src .

ENTRYPOINT ["python3", "-u", "main.py"]