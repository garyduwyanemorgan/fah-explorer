# FAH Explorer — production container
# Build:  docker build -t fah-explorer .
# Run:    docker run -p 8000:8000 --env-file .env -v fah-data:/app/data fah-explorer

FROM python:3.12-slim

# System deps: Tesseract OCR + Poppler (pdf2image), plus build tools for pykrige
RUN apt-get update && apt-get install -y --no-install-recommends \
        tesseract-ocr \
        tesseract-ocr-eng \
        poppler-utils \
        libgdal-dev \
        gcc \
        g++ \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps before copying source for better layer caching
COPY pyproject.toml .
RUN pip install --no-cache-dir -e ".[dev]" || pip install --no-cache-dir -e .

# Copy application source
COPY backend/ ./backend/
COPY config/  ./config/
COPY frontend/ ./frontend/

# Data directory is a Docker volume so it persists across container restarts
VOLUME ["/app/data"]

EXPOSE 8000

# 2 workers covers multi-core hosts without exceeding SQLite write concurrency.
# --timeout-keep-alive 75 accommodates LLM extraction calls (30-60 s).
CMD ["python", "-m", "uvicorn", "fah.main:app", \
     "--app-dir", "backend", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "2", \
     "--timeout-keep-alive", "75", \
     "--log-level", "info"]
