"""
SecureStego — Prometheus Metrics

Exposes /metrics endpoint (Prometheus format) with:
  - Request count (labeled by endpoint, method, status)
  - Request latency histogram (labeled by endpoint)
  - Error count (labeled by endpoint)

Implemented as FastAPI middleware — automatically instruments all requests.
"""

import time
import logging

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Metrics storage (in-process — no prometheus_client dependency needed
# for the basic case; compatible with prometheus_client if installed)
# ---------------------------------------------------------------------------

try:
    from prometheus_client import (
        Counter,
        Histogram,
        generate_latest,
        CONTENT_TYPE_LATEST,
    )

    REQUEST_COUNT = Counter(
        "securestego_requests_total",
        "Total HTTP requests",
        ["method", "endpoint", "status", "mode"],
    )

    REQUEST_LATENCY = Histogram(
        "securestego_request_latency_seconds",
        "Request latency in seconds",
        ["method", "endpoint"],
        buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
    )

    ERROR_COUNT = Counter(
        "securestego_errors_total",
        "Total HTTP errors (4xx + 5xx)",
        ["method", "endpoint", "status"],
    )

    PROMETHEUS_AVAILABLE = True

except ImportError:
    PROMETHEUS_AVAILABLE = False
    logger.warning(
        "prometheus_client not installed — /metrics endpoint will return empty. "
        "Install with: pip install prometheus-client"
    )


def get_metrics_response() -> tuple[bytes, str]:
    """Generate Prometheus metrics response.

    Returns:
        (body_bytes, content_type)
    """
    if not PROMETHEUS_AVAILABLE:
        return b"# prometheus_client not installed\n", "text/plain"
    return generate_latest(), CONTENT_TYPE_LATEST


class PrometheusMiddleware(BaseHTTPMiddleware):
    """FastAPI middleware that records request metrics for Prometheus.

    Instruments:
      - Total request count (by method, endpoint, status, mode)
      - Request latency histogram (by method, endpoint)
      - Error count for 4xx/5xx responses

    Rule 5.1: Never logs request body, passwords, or plaintext.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        if not PROMETHEUS_AVAILABLE:
            return await call_next(request)

        # Skip metrics for the /metrics endpoint itself
        path = request.url.path
        if path == "/metrics":
            return await call_next(request)

        # Normalize endpoint path for labeling (strip IDs/keys)
        endpoint = self._normalize_path(path)
        method = request.method

        start_time = time.perf_counter()

        try:
            response = await call_next(request)
            status = str(response.status_code)
            duration = time.perf_counter() - start_time

            # Determine mode from path context (if available)
            mode = "unknown"

            REQUEST_COUNT.labels(
                method=method, endpoint=endpoint, status=status, mode=mode
            ).inc()

            REQUEST_LATENCY.labels(method=method, endpoint=endpoint).observe(duration)

            if response.status_code >= 400:
                ERROR_COUNT.labels(
                    method=method, endpoint=endpoint, status=status
                ).inc()

            return response

        except Exception as exc:
            duration = time.perf_counter() - start_time
            REQUEST_COUNT.labels(
                method=method, endpoint=endpoint, status="500", mode="unknown"
            ).inc()
            ERROR_COUNT.labels(
                method=method, endpoint=endpoint, status="500"
            ).inc()
            REQUEST_LATENCY.labels(method=method, endpoint=endpoint).observe(duration)
            raise

    @staticmethod
    def _normalize_path(path: str) -> str:
        """Normalize URL path for metric labels.

        Replaces dynamic segments (UUIDs, storage keys) with placeholders
        to prevent label cardinality explosion.
        """
        parts = path.strip("/").split("/")
        normalized = []
        for part in parts:
            # Replace storage keys (hex UUIDs with extensions)
            if len(part) > 20 and "." in part:
                normalized.append("{key}")
            else:
                normalized.append(part)
        return "/" + "/".join(normalized) if normalized else "/"
