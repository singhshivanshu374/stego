"""
SecureStego — Locust Load Test

Simulates encode/decode traffic to measure:
  - Request throughput (requests/sec)
  - Latency percentiles (p50, p95, p99)
  - Error rates under load

Usage:
  # Against local docker compose stack:
  locust -f loadtest/locustfile.py --host http://localhost

  # Headless mode (for CI):
  locust -f loadtest/locustfile.py --host http://localhost \
    --headless -u 20 -r 5 -t 60s --csv results

Compare results with:
  - 1 replica:  docker compose up --scale api-1=1 --scale api-2=0 --scale api-3=0
  - 3 replicas: docker compose up (default)
"""

import io
import os
import random
import string

import numpy as np

from locust import HttpUser, between, task

# Pre-generate a small PNG for uploads (avoid generating per-request)
def _make_png_bytes() -> bytes:
    """Create a minimal PNG image for load testing."""
    try:
        import cv2
        img = np.random.randint(0, 256, (100, 100, 3), dtype=np.uint8)
        success, buffer = cv2.imencode(".png", img)
        if success:
            return buffer.tobytes()
    except ImportError:
        pass
    # Fallback: minimal valid PNG (1x1 pixel, red)
    return (
        b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01'
        b'\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00'
        b'\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00'
        b'\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82'
    )


PNG_BYTES = _make_png_bytes()


def _random_string(length: int = 16) -> str:
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=length))


class SecureStegoUser(HttpUser):
    """Simulated user performing encode/decode operations."""

    wait_time = between(0.5, 2.0)

    def on_start(self):
        """Register and login before starting tasks."""
        self.username = f"loadtest_{_random_string(8)}"
        self.password = f"loadtest_pw_{_random_string(12)}"
        self.encode_password = f"stego_pw_{_random_string(8)}"
        self.stego_image = None

        # Register
        resp = self.client.post("/auth/register", json={
            "username": self.username,
            "password": self.password,
        })
        if resp.status_code != 201:
            # User might already exist in a long-running test
            pass

        # Login
        resp = self.client.post("/auth/login", data={
            "username": self.username,
            "password": self.password,
        })
        if resp.status_code == 200:
            self.token = resp.json()["access_token"]
        else:
            self.token = None

    def _auth_headers(self) -> dict:
        if self.token:
            return {"Authorization": f"Bearer {self.token}"}
        return {}

    @task(3)
    def encode_message(self):
        """Encode a message (Mode A) — weighted 3x more than decode."""
        message = f"Load test message {_random_string(32)}"

        resp = self.client.post(
            "/encode",
            headers=self._auth_headers(),
            data={
                "message": message,
                "mode": "password",
                "password": self.encode_password,
            },
            files={"image": ("test.png", PNG_BYTES, "image/png")},
            name="/encode",
        )
        if resp.status_code == 200:
            download_url = resp.json().get("download_url", "")
            if download_url:
                # Download the stego image for decode tasks
                dl_resp = self.client.get(download_url, name="/storage/{key}")
                if dl_resp.status_code == 200:
                    self.stego_image = dl_resp.content

    @task(1)
    def decode_message(self):
        """Decode a message (Mode A) — weighted 1x."""
        if not self.stego_image:
            return  # Skip if no stego image available yet

        self.client.post(
            "/decode",
            headers=self._auth_headers(),
            data={"password": self.encode_password},
            files={"image": ("stego.png", self.stego_image, "image/png")},
            name="/decode",
        )

    @task(1)
    def health_check(self):
        """Hit the health endpoint (simulates LB probes)."""
        self.client.get("/health", name="/health")
