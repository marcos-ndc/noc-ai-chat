# ── Stage 1: Build deps ───────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt --target /app/deps

# ── Stage 2: Runtime ──────────────────────────────────────────────────────────
FROM python:3.12-slim AS runner

WORKDIR /app

# Copy installed packages
COPY --from=builder /app/deps /usr/local/lib/python3.12/site-packages

# Copy app
COPY app/ ./app/

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
  CMD python -c "import httpx; r=httpx.get('http://localhost:8000/health', timeout=3); exit(0 if r.status_code==200 else 1)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--log-level", "info"]
