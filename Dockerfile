FROM python:3.11-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1
ENV HF_HOME=/tmp/huggingface

COPY backend/requirements-runtime.txt ./requirements-runtime.txt
RUN pip install --no-cache-dir -r requirements-runtime.txt

COPY backend/ ./

CMD ["sh", "-c", "exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}"]