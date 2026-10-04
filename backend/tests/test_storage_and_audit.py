"""
Tests for storage_service.py and MongoDB audit trail (Phase 3).

Storage tests use the local filesystem backend (STORAGE_BACKEND=local).
Docker-based tests with MinIO are run via docker compose in Phase 4.

MongoDB tests verify the mirror logic works when Mongo is enabled,
and gracefully degrades when Mongo is disabled/unavailable.
"""

import os
import tempfile

import cv2
import numpy as np
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.config import get_settings
from app.core.rate_limit import reset_in_memory_store
from app.db.mongo import mirror_operation_to_mongo
from app.db.postgres import create_tables, drop_tables
from app.main import app
from app.services import storage_service


settings = get_settings()


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
    """Create a PNG image in memory."""
    image = np.random.randint(0, 256, (height, width, 3), dtype=np.uint8)
    success, buffer = cv2.imencode(".png", image)
    assert success
    return buffer.tobytes()


async def _register_and_login(client: AsyncClient, username: str, password: str) -> str:
    """Register a user and return JWT token."""
    await client.post("/auth/register", json={
        "username": username,
        "password": password,
    })
    resp = await client.post("/auth/login", data={
        "username": username,
        "password": password,
    })
    return resp.json()["access_token"]


# ---------------------------------------------------------------------------
# Storage — Local Backend
# ---------------------------------------------------------------------------

class TestLocalStorage:
    """Tests for the local filesystem storage backend."""

    @pytest.mark.asyncio
    async def test_upload_download_round_trip(self):
        """Upload a file and verify it can be retrieved."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a test file
            test_file = os.path.join(tmpdir, "test.png")
            img = np.random.randint(0, 256, (50, 50, 3), dtype=np.uint8)
            cv2.imwrite(test_file, img)

            # Upload
            key, url = await storage_service.upload_file(test_file, "test.png")
            assert key.endswith(".png")
            assert url.startswith("/storage/")

            # Retrieve path
            path = await storage_service.get_file_path(key)
            assert os.path.exists(path)

            # Get download URL
            dl_url = await storage_service.get_download_url(key)
            assert dl_url == f"/storage/{key}"

            # Cleanup
            await storage_service.delete_file(key)

    @pytest.mark.asyncio
    async def test_upload_preserves_content(self):
        """Uploaded file content must match the original."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = os.path.join(tmpdir, "test.png")
            img = np.zeros((10, 10, 3), dtype=np.uint8)
            cv2.imwrite(test_file, img)

            with open(test_file, "rb") as f:
                original_content = f.read()

            key, _ = await storage_service.upload_file(test_file, "test.png")
            path = await storage_service.get_file_path(key)

            with open(path, "rb") as f:
                stored_content = f.read()

            assert stored_content == original_content
            await storage_service.delete_file(key)

    @pytest.mark.asyncio
    async def test_delete_removes_file(self):
        """Deleting a file removes it from storage."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = os.path.join(tmpdir, "test.png")
            img = np.zeros((10, 10, 3), dtype=np.uint8)
            cv2.imwrite(test_file, img)

            key, _ = await storage_service.upload_file(test_file, "test.png")
            path = await storage_service.get_file_path(key)
            assert os.path.exists(path)

            await storage_service.delete_file(key)
            with pytest.raises(FileNotFoundError):
                await storage_service.get_file_path(key)

    @pytest.mark.asyncio
    async def test_get_nonexistent_file(self):
        """Retrieving a non-existent key raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            await storage_service.get_file_path("nonexistent_key.png")


# ---------------------------------------------------------------------------
# Storage — API Integration
# ---------------------------------------------------------------------------

class TestStorageAPIIntegration:
    """Tests verifying storage works through the full API pipeline."""

    @pytest.mark.asyncio
    async def test_encode_creates_stored_file(self, client: AsyncClient):
        """POST /encode should produce a downloadable file via storage."""
        token = await _register_and_login(client, "alice", "password1234")
        png_bytes = _create_test_png_bytes()

        resp = await client.post(
            "/encode",
            headers={"Authorization": f"Bearer {token}"},
            data={"message": "Storage test!", "mode": "password", "password": "testpw"},
            files={"image": ("cover.png", png_bytes, "image/png")},
        )
        assert resp.status_code == 200
        download_url = resp.json()["download_url"]

        # Verify the file is accessible
        dl_resp = await client.get(download_url)
        assert dl_resp.status_code == 200
        assert len(dl_resp.content) > 0

    @pytest.mark.asyncio
    async def test_encode_decode_through_storage(self, client: AsyncClient):
        """Full encode→download→decode round trip through storage."""
        token = await _register_and_login(client, "alice", "password1234")
        png_bytes = _create_test_png_bytes()

        # Encode
        encode_resp = await client.post(
            "/encode",
            headers={"Authorization": f"Bearer {token}"},
            data={"message": "Round trip storage test", "mode": "password", "password": "pw123"},
            files={"image": ("cover.png", png_bytes, "image/png")},
        )
        download_url = encode_resp.json()["download_url"]

        # Download
        stego_bytes = (await client.get(download_url)).content

        # Decode
        decode_resp = await client.post(
            "/decode",
            headers={"Authorization": f"Bearer {token}"},
            data={"password": "pw123"},
            files={"image": ("stego.png", stego_bytes, "image/png")},
        )
        assert decode_resp.status_code == 200
        assert decode_resp.json()["message"] == "Round trip storage test"


# ---------------------------------------------------------------------------
# MongoDB Audit Trail
# ---------------------------------------------------------------------------

class TestMongoAuditTrail:
    """Tests for MongoDB audit mirror functionality.

    These tests verify the mirror logic works correctly when Mongo is
    disabled (the default for testing without Docker).
    """

    @pytest.mark.asyncio
    async def test_mirror_returns_false_when_disabled(self):
        """When MONGO_ENABLED=false, mirror should return False (no-op)."""
        assert settings.mongo_enabled is False  # Default for testing
        result = await mirror_operation_to_mongo({
            "operation_id": "test-123",
            "operation_type": "encode",
            "mode": "password",
            "sender_id": 1,
        })
        assert result is False

    @pytest.mark.asyncio
    async def test_mirror_does_not_crash_when_disabled(self):
        """Mirror should never raise even when Mongo is down."""
        result = await mirror_operation_to_mongo({
            "operation_id": "test-456",
            "operation_type": "decode",
        })
        # Should not crash, should return False
        assert result is False

    @pytest.mark.asyncio
    async def test_encode_succeeds_without_mongo(self, client: AsyncClient):
        """API /encode should succeed even when Mongo is disabled.

        This verifies the fire-and-forget behavior: the audit mirror
        failure does not affect the API response.
        """
        token = await _register_and_login(client, "alice", "password1234")
        png_bytes = _create_test_png_bytes()

        resp = await client.post(
            "/encode",
            headers={"Authorization": f"Bearer {token}"},
            data={"message": "Mongo disabled test", "mode": "password", "password": "testpw"},
            files={"image": ("cover.png", png_bytes, "image/png")},
        )
        assert resp.status_code == 200
        assert "operation_id" in resp.json()
