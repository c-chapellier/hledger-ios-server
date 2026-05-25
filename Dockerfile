FROM python:3.13-slim as builder
RUN apt-get update && \
    apt-get install -y --no-install-recommends build-essential python3-dev libffi-dev \
    && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir pdm
WORKDIR /app
COPY pyproject.toml pdm.lock* ./
RUN pdm export -f requirements --prod > requirements.txt

FROM python:3.13-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends build-essential python3-dev libffi-dev libpq5 \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -u 1000 appuser
WORKDIR /app
COPY --from=builder /app/requirements.txt .
RUN chown appuser:appuser /app
USER appuser
RUN pip install --no-cache-dir --user -r requirements.txt

COPY --chown=appuser:appuser . .

ENV PATH="/home/appuser/.local/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
