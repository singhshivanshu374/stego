"""
Tests for encode/decode API endpoints.

Full API round trips for both modes, unauthorized recipient (Mode B → 403),
wrong password (Mode A → generic error), and rate limiting.

Uses httpx async test client with in-memory SQLite database.
"""

import io
import os
import tempfile

import cv2
import numpy as np
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.core.rate_limit import reset_in_memory_store
from app.db.postgres import create_tables, drop_tables
from app.main import app


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    """Create fresh tables before each test, drop after."""
    await create_tables()
    yield
    await drop_tables()
    reset_in_memory_store()


@pytest_asyncio.fixture
async def client():
    """Async httpx test client."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


def _create_test_png_bytes(width: int = 100, height: int = 100) -> bytes:
    """Create a PNG image in memory and return its bytes."""
    image = np.random.randint(0, 256, (height, width, 3), dtype=np.uint8)
    success, buffer = cv2.imencode(".png", image)
    assert success
    return buffer.tobytes()


async def _register_and_login(client: AsyncClient, username: str, password: str) -> tuple[str, dict]:
    """Helper: register a user and return (jwt_token, register_response_data)."""
    reg_resp = await client.post("/auth/register", json={
        "username": username,
        "password": password,
    })
    assert reg_resp.status_code == 201
    reg_data = reg_resp.json()

    login_resp = await client.post("/auth/login", data={
        "username": username,
        "password": password,
    })
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]

    return token, reg_data


def _auth_headers(token: str) -> dict:
    """Build Authorization header."""
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Mode A — Full API round trip
# ---------------------------------------------------------------------------

class TestEncodeDecodeModeA:
    """End-to-end API tests for Mode A (password-based)."""

    @pytest.mark.asyncio
    async def test_full_round_trip_mode_a(self, client: AsyncClient):
        """Encode → download → decode with correct password returns original message."""
        token, _ = await _register_and_login(client, "alice", "password1234")
        png_bytes = _create_test_png_bytes()

        # Encode
        encode_resp = await client.post(
            "/encode",
            headers=_auth_headers(token),
            data={"message": "Hello Mode A!", "mode": "password", "password": "s3cure_pw"},
            files={"image": ("cover.png", png_bytes, "image/png")},
        )
        assert encode_resp.status_code == 200
        encode_data = encode_resp.json()
        assert encode_data["mode"] == "password"
        assert "download_url" in encode_data
        download_url = encode_data["download_url"]

        # Download stego image
        dl_resp = await client.get(download_url)
        assert dl_resp.status_code == 200
        stego_bytes = dl_resp.content

        # Decode
        decode_resp = await client.post(
            "/decode",
            headers=_auth_headers(token),
            data={"password": "s3cure_pw"},
            files={"image": ("stego.png", stego_bytes, "image/png")},
        )
        assert decode_resp.status_code == 200
        decode_data = decode_resp.json()
        assert decode_data["message"] == "Hello Mode A!"
        assert decode_data["mode"] == "password"

    @pytest.mark.asyncio
    async def test_wrong_password_mode_a(self, client: AsyncClient):
        """Wrong password → clean 4xx error with generic message (Rule 5.3)."""
        token, _ = await _register_and_login(client, "alice", "password1234")
        png_bytes = _create_test_png_bytes()

        # Encode
        encode_resp = await client.post(
            "/encode",
            headers=_auth_headers(token),
            data={"message": "secret", "mode": "password", "password": "correct_pw"},
            files={"image": ("cover.png", png_bytes, "image/png")},
        )
        download_url = encode_resp.json()["download_url"]
        stego_bytes = (await client.get(download_url)).content

        # Decode with wrong password
        decode_resp = await client.post(
            "/decode",
            headers=_auth_headers(token),
            data={"password": "wrong_pw"},
            files={"image": ("stego.png", stego_bytes, "image/png")},
        )
        assert decode_resp.status_code == 400
        assert decode_resp.json()["detail"] == "Decoding failed."


# ---------------------------------------------------------------------------
# Mode B — Full API round trip
# ---------------------------------------------------------------------------

class TestEncodeDecodeModeB:
    """End-to-end API tests for Mode B (user-bound / hybrid RSA+AES)."""

    @pytest.mark.asyncio
    async def test_full_round_trip_mode_b(self, client: AsyncClient):
        """Encode for recipient → recipient decodes with their key."""
        # Register sender and recipient
        sender_token, _ = await _register_and_login(client, "sender", "senderpass123")
        recipient_token, recipient_reg = await _register_and_login(client, "recipient", "recipientpass1")

        png_bytes = _create_test_png_bytes()

        # Encode (sender sends to recipient)
        encode_resp = await client.post(
            "/encode",
            headers=_auth_headers(sender_token),
            data={
                "message": "Hello Mode B!",
                "mode": "user_bound",
                "recipient_username": "recipient",
            },
            files={"image": ("cover.png", png_bytes, "image/png")},
        )
        assert encode_resp.status_code == 200
        encode_data = encode_resp.json()
        assert encode_data["mode"] == "user_bound"
        download_url = encode_data["download_url"]

        # Download stego image
        stego_bytes = (await client.get(download_url)).content

        # Decode (recipient decodes — provides their private key)
        decode_resp = await client.post(
            "/decode",
            headers=_auth_headers(recipient_token),
            data={"private_key": recipient_reg["private_key_pem"]},
            files={"image": ("stego.png", stego_bytes, "image/png")},
        )
        assert decode_resp.status_code == 200
        decode_data = decode_resp.json()
        assert decode_data["message"] == "Hello Mode B!"
        assert decode_data["mode"] == "user_bound"

    @pytest.mark.asyncio
    async def test_unauthorized_recipient_mode_b(self, client: AsyncClient):
        """Wrong user attempting Mode B decode → 403 with generic message (Rule 5.3)."""
        sender_token, _ = await _register_and_login(client, "sender", "senderpass123")
        recipient_token, _ = await _register_and_login(client, "recipient", "recipientpass1")
        intruder_token, intruder_reg = await _register_and_login(client, "intruder", "intruderpass1")

        png_bytes = _create_test_png_bytes()

        # Encode for recipient
        encode_resp = await client.post(
            "/encode",
            headers=_auth_headers(sender_token),
            data={
                "message": "Secret for recipient only",
                "mode": "user_bound",
                "recipient_username": "recipient",
            },
            files={"image": ("cover.png", png_bytes, "image/png")},
        )
        download_url = encode_resp.json()["download_url"]
        stego_bytes = (await client.get(download_url)).content

        # Intruder attempts decode → should fail
        decode_resp = await client.post(
            "/decode",
            headers=_auth_headers(intruder_token),
            data={"private_key": intruder_reg["private_key_pem"]},
            files={"image": ("stego.png", stego_bytes, "image/png")},
        )
        assert decode_resp.status_code == 403
        # Rule 5.3 — same generic error message
        assert decode_resp.json()["detail"] == "Decoding failed."


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------

class TestRateLimiting:
    """Tests for rate limiting on /decode."""

    @pytest.mark.asyncio
    async def test_decode_rate_limit_triggers(self, client: AsyncClient):
        """Rate limit triggers after threshold on /decode (Rule 5.4)."""
        # Temporarily enable rate limiting with a very low threshold
        from app.config import get_settings
        settings = get_settings()
        original_enabled = settings.rate_limit_enabled
        original_limit = settings.rate_limit_decode_per_minute
        settings.rate_limit_enabled = True
        settings.rate_limit_decode_per_minute = 3

        try:
            token, _ = await _register_and_login(client, "ratelimited", "password1234")
            png_bytes = _create_test_png_bytes()

            # Encode a message first
            encode_resp = await client.post(
                "/encode",
                headers=_auth_headers(token),
                data={"message": "test", "mode": "password", "password": "testpw"},
                files={"image": ("cover.png", png_bytes, "image/png")},
            )
            download_url = encode_resp.json()["download_url"]
            stego_bytes = (await client.get(download_url)).content

            # Make requests up to the limit
            responses = []
            for _ in range(5):
                resp = await client.post(
                    "/decode",
                    headers=_auth_headers(token),
                    data={"password": "testpw"},
                    files={"image": ("stego.png", stego_bytes, "image/png")},
                )
                responses.append(resp.status_code)

            # At least one response should be 429 (rate limited)
            assert 429 in responses, f"Expected 429 in responses, got: {responses}"

        finally:
            settings.rate_limit_enabled = original_enabled
            settings.rate_limit_decode_per_minute = original_limit
            reset_in_memory_store()
