# Phase 5 — Observability & CI/CD

## What Was Built

### 1. Prometheus Metrics (FastAPI Middleware)
- **`app/monitoring/metrics.py`**: A custom middleware that auto-instruments all requests.
- **Metrics Collected**:
  - `securestego_requests_total` (Counter): Total requests labeled by method, endpoint, status, and mode.
  - `securestego_request_latency_seconds` (Histogram): Request duration labeled by method and endpoint.
  - `securestego_errors_total` (Counter): 4xx and 5xx errors labeled by method, endpoint, and status.
- **Cardinality Protection**: Dynamic path segments (like UUIDs for `/storage/{key}`) are stripped from labels via `_normalize_path` to prevent label cardinality explosion.
- **Graceful Degradation**: If `prometheus_client` is not installed (e.g. in minimal environments), the middleware acts as a no-op and `/metrics` returns a warning instead of crashing.

### 2. Structured JSON Logging
- **`app/main.py`**: Integrated a custom `JSONFormatter` for production logging.
- **Security**: The custom formatter ensures log lines never include the request body, passwords, or plaintext data (enforcing Rule 5.1).
- Outputs human-readable logs in `DEBUG` mode, and machine-readable JSON in `INFO` mode (production).

### 3. GitHub Actions CI Pipeline
- **`.github/workflows/ci.yml`**:
  - Runs on every push and pull request to `main` or `develop`.
  - **Test Matrix**: Tests the backend against Python 3.11, 3.12, and 3.13.
  - **Docker Build Test**: Builds the multi-stage Docker image and briefly runs it to verify the `HEALTHCHECK` endpoint succeeds, preventing broken builds from passing.

### 4. Locust Load Testing
- **`loadtest/locustfile.py`**: Simulates realistic user behavior.
  - **Setup**: Registers a new user and logs in to get a JWT token.
  - **Tasks**: Weighted tasks (3x `/encode` vs 1x `/decode` vs 1x `/health`).
  - **Assets**: Dynamically generates a minimal valid PNG in-memory to avoid disk I/O bottlenecks on the load generator side.
- Enables baseline throughput and latency measurements.

## Test Summary
- **77 tests, all passing** (`pytest tests/ -v`). 
- The addition of the Prometheus middleware was verified to not break any existing tests or routes.

## How to Run Load Tests
```bash
# Install Locust
pip install locust

# Against local docker compose stack:
locust -f loadtest/locustfile.py --host http://localhost

# Headless mode (for CI/automated runs):
locust -f loadtest/locustfile.py --host http://localhost --headless -u 20 -r 5 -t 60s --csv results
```
