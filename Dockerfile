# syntax=docker/dockerfile:1

FROM python:3.10-slim-bullseye

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc

COPY requirements.txt .

RUN pip3 install -r requirements.txt

COPY main.py .

ENTRYPOINT ["python3", "main.py"]
