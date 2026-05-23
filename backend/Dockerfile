FROM python:3.11-slim

WORKDIR /app

# System deps for building Python wheels (a few transitive deps need this).
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps first so layers cache when source changes.
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY app/ ./app/

# Runtime storage (also volume-mounted in docker-compose so they persist)
RUN mkdir -p /app/uploads /app/chroma_db

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
