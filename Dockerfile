# syntax=docker/dockerfile:1

FROM python:3.10-bullseye

WORKDIR /app

RUN apk update && \ 
    apk add build-base

COPY requirements.txt .

RUN pip3 install -r requirements.txt

COPY . .

ENTRYPOINT [ "python3", "main.py"]
