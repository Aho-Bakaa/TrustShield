# TrustShield backend — Python 3.10 + FastAPI + Playwright
FROM python:3.10-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libasound2 libsndfile1 ffmpeg \
    libnss3 libnspr4 libatk-bridge2.0-0 libdrm2 libxkbcommon0 \
    libgbm1 libxcomposite1 libxdamage1 libxrandr2 libpango-1.0-0 \
    libcairo2 libasound2t64 libatspi2.0-0 libcups2 \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir playwright && \
    python -m playwright install --with-deps chromium

COPY backend/ .
COPY backend/app/data/models/ /app/app/data/models/

EXPOSE 8000
ENV PYTHONUNBUFFERED=1
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
