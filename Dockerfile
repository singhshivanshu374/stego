# ===========================================================================
# SecureStego — Root-level Multi-Stage Dockerfile
#
# Build context must be the PROJECT ROOT (not backend/).
# Stage 1 (frontend): Node.js  — builds the React/Vite SPA.
# Stage 2 (builder):  Python   — installs Python dependencies.
# Stage 3 (runtime):  Python   — slim image with app + built frontend.
# ===========================================================================

# --- Stage 1: Frontend Build ---
FROM node:20-slim AS frontend

WORKDIR /frontend

# Cache node_modules layer separately (only re-runs on package.json change)
COPY frontend/package*.json ./
RUN npm ci

# Copy source and build the SPA
COPY frontend/ ./
RUN npm run build
# Output lives at /frontend/dist/


# --- Stage 2: Python Dependency Builder ---
FROM python:3.13-slim AS builder

WORKDIR /build

RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt


# --- Stage 3: Runtime ---
FROM python:3.13-slim AS runtime

# Runtime system deps (OpenCV needs libgl1/libglib2.0-0, asyncpg needs libpq5)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libgl1 \
        libglib2.0-0 \
        libpq5 \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed Python packages from builder stage
COPY --from=builder /install /usr/local

# Non-root user (security best practice)
RUN groupadd -r securestego && \
    useradd -r -g securestego -d /app -s /sbin/nologin securestego

WORKDIR /app

# Copy FastAPI application code
COPY backend/app/ ./app/

# Copy the built React SPA — FastAPI serves it via StaticFiles + SPA catch-all
COPY --from=frontend /frontend/dist/ ./static/

# Create local storage directory
RUN mkdir -p /app/storage && chown -R securestego:securestego /app

USER securestego

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
