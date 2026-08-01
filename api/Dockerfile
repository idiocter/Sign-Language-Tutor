# SignBridge API. Build from the REPO ROOT (needs both ml/ and api/):
#   docker build -f api/Dockerfile -t signbridge-api .
FROM python:3.12-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1

# Install deps first for layer caching.
COPY ml/pyproject.toml ml/README.md /app/ml/
COPY ml/signbridge /app/ml/signbridge
COPY api/requirements.txt /app/api/requirements.txt
RUN pip install -e "/app/ml[foundation]" && pip install -r /app/api/requirements.txt

# App code + any generated model artifacts present at build time.
COPY ml /app/ml
COPY api /app/api

WORKDIR /app/api
EXPOSE 8000
# Set DATABASE_URL (Postgres) in production; defaults to SQLite otherwise.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
