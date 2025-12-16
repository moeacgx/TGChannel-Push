# ============================================
# Stage 1: Build frontend
# ============================================
FROM node:20-alpine AS frontend-builder

WORKDIR /app/web

# Copy frontend files
COPY web/package*.json ./

# Install dependencies
RUN npm install

# Copy source and build
COPY web/ ./
RUN npm run build

# ============================================
# Stage 2: Python runtime
# ============================================
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy Python project files
COPY pyproject.toml README.md ./
COPY src/ ./src/

# Install Python dependencies
RUN pip install --no-cache-dir -e .

# Copy built frontend from stage 1
COPY --from=frontend-builder /app/web/dist ./web/dist

# Create data directory
RUN mkdir -p /app/data /app/logs

# Set environment variables (all have sensible defaults)
ENV PYTHONUNBUFFERED=1
ENV PYTHONIOENCODING=utf-8
ENV TZ=Asia/Shanghai

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8000/api/health')" || exit 1

# Run the application
CMD ["python", "-m", "tgchannel_push"]
