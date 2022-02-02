# syntax=docker/dockerfile:1

#TEMP IMAGE
FROM python:3.10-alpine as builder

WORKDIR /app

RUN apk update && \ 
    apk add build-base

COPY requirements.txt .

RUN pip wheel --no-cache-dir --no-deps --wheel-dir /app/wheels -r requirements.txt

#FINAL IMAGE
FROM python:3.10-alpine

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

WORKDIR /app

COPY --from=builder /app/wheels /wheels
COPY --from=builder /app/requirements.txt .

RUN pip install --no-cache /wheels/*

COPY . .

ENTRYPOINT [ "python3", "main.py"]