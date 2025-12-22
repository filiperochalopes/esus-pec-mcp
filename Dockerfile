# Stage 1: Build
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Stage 2: Runtime
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH="/app/mcp-server/src:/app/mcp-client"
ENV UI_HOST=0.0.0.0
ENV UI_PORT=8001
ENV MCP_HTTP_HOST=0.0.0.0
ENV MCP_HTTP_PORT=5174

WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed python packages from builder
COPY --from=builder /install /usr/local

# Create a non-root user
RUN addgroup --system appgroup && adduser --system --group appuser

# Copy project files
COPY . .

# Ensure entrypoint is executable and owned by appuser
RUN chmod +x entrypoint.sh && chown -R appuser:appgroup /app

# Switch to non-root user
USER appuser

# Expose ports
EXPOSE 8001 5174

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8001/health || exit 1

# Run entrypoint
CMD ["./entrypoint.sh"]