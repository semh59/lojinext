# Digest-pinned python:3.12-slim — same digest as the main backend Dockerfile
# (resolved 2026-06-17). Bumped from 3.11 on 2026-07-30: this service has no
# heavy ML deps (just python-telegram-bot/httpx/fastapi/uvicorn), so it
# carried none of the EasyOCR/torch wheel-compatibility risk that kept
# ocr_service on 3.11.
FROM python:3.12-slim@sha256:d764629ce0ddd8c71fd371e9901efb324a95789d2315a47db7e4d27e78f1b0e9

RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "main.py"]
