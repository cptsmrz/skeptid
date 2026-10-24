FROM python:3.12-slim

WORKDIR /app

# Install system dependencies required for OpenCV headless and audio processing
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY main.py pyproject.toml README.md ./
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.lock

COPY src/ ./src/
COPY web/ ./web/
COPY config/ ./config/
COPY data/ ./data/

ENV PORT=8000
EXPOSE 8000

CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT}"]
