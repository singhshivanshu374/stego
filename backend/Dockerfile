# ===========================================================================
# SecureStego — Multi-Stage Dockerfile
#
# Stage 1 (frontend): Node.js — builds the React/Vite SPA into static files.
# Stage 2 (builder):  Python  — installs Python dependencies.
# Stage 3 (runtime):  Python  — slim runtime image with app + built frontend.
# Runs as a non-root user for security.
# ===========================================================================

# --- Stage 1: Frontend Build (Node.js) ---
FROM node:20-slim AS frontend

WORKDIR /frontend

# Install dependencies first (layer cache — only re-runs if package.json changes)
COPY ../frontend/package*.json ./
RUN npm ci

# Copy source and build
COPY ../frontend/ ./
RUN npm run build
# Output: /frontend/dist/


# --- Stage 2: Python Dependency Builder ---
FROM python:3.13-slim AS builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt


# --- Stage 3: Runtime ---
FROM python:3.13-slim AS runtime

# Install runtime dependencies (libgl for OpenCV, libpq for Postgres)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libgl1 \
        libglib2.0-0 \
        libpq5 \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed Python packages from builder
COPY --from=builder /install /usr/local

# Create non-root user (security best practice)
RUN groupadd -r securestego && \
    useradd -r -g securestego -d /app -s /sbin/nologin securestego

WORKDIR /app

# Copy application code
COPY app/ ./app/

# Copy the built React SPA from the frontend stage
# FastAPI serves these via the StaticFiles mount + SPA catch-all route
COPY --from=frontend /frontend/dist/ ./static/

# Create storage directory (owned by non-root user)
RUN mkdir -p /app/storage && chown -R securestego:securestego /app

# Switch to non-root user
USER securestego

# Expose the API port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run with uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
