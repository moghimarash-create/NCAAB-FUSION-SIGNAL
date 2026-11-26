# Stage 1: Compile pyswisseph C extension & Python dependencies cleanly
FROM python:3.12-slim-bookworm AS builder

RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    ca-certificates \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /build
COPY requirements.txt ./
RUN pip install --no-cache-dir --break-system-packages --prefix=/install -r requirements.txt

# Stage 2: Minimal production runtime (no compiler toolchain bloat)
FROM python:3.12-slim-bookworm AS runner

RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
  && rm -rf /var/lib/apt/lists/*

COPY --from=builder /install /usr/local

WORKDIR /app
COPY src ./src
COPY data ./data
COPY shards ./shards
COPY main.py requirements.txt ./

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PORT=8080

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD curl -fsS "http://127.0.0.1:${PORT:-8080}/api/health" || exit 1

CMD ["python3", "main.py"]
