"""
Tests for auth API endpoints (/auth/register, /auth/login).

Uses httpx async test client with an in-memory SQLite database.
"""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.db.postgres import Base, engine, create_tables, drop_tables
from app.main import app


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    """Create fresh tables before each test, drop after."""
    await create_tables()
    yield
    await drop_tables()


@pytest_asyncio.fixture
async def client():
    """Async httpx test client."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

class TestRegister:
    """Tests for POST /auth/register."""

    @pytest.mark.asyncio
    async def test_register_success(self, client: AsyncClient):
        """Successful registration returns user info + private key."""
        resp = await client.post("/auth/register", json={
            "username": "testuser",
            "password": "securepass123",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["username"] == "testuser"
        assert "private_key_pem" in data
        assert data["private_key_pem"].startswith("-----BEGIN PRIVATE KEY-----")
        assert data["id"] > 0

    @pytest.mark.asyncio
    async def test_register_duplicate_username(self, client: AsyncClient):
        """Duplicate username returns 409."""
        await client.post("/auth/register", json={
            "username": "testuser",
            "password": "securepass123",
        })
        resp = await client.post("/auth/register", json={
            "username": "testuser",
            "password": "differentpass456",
        })
        assert resp.status_code == 409

    @pytest.mark.asyncio
    async def test_register_short_password(self, client: AsyncClient):
        """Password shorter than 8 chars is rejected."""
        resp = await client.post("/auth/register", json={
            "username": "testuser",
            "password": "short",
        })
        assert resp.status_code == 422  # Pydantic validation error

    @pytest.mark.asyncio
    async def test_register_short_username(self, client: AsyncClient):
        """Username shorter than 3 chars is rejected."""
        resp = await client.post("/auth/register", json={
            "username": "ab",
            "password": "securepass123",
        })
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_register_invalid_username_chars(self, client: AsyncClient):
        """Username with special chars is rejected."""
        resp = await client.post("/auth/register", json={
            "username": "test user!",
            "password": "securepass123",
        })
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------

class TestLogin:
    """Tests for POST /auth/login."""

    @pytest.mark.asyncio
    async def test_login_success(self, client: AsyncClient):
        """Successful login returns a JWT."""
        # Register first
        await client.post("/auth/register", json={
            "username": "testuser",
            "password": "securepass123",
        })
        # Login
        resp = await client.post("/auth/login", data={
            "username": "testuser",
            "password": "securepass123",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert len(data["access_token"]) > 20

    @pytest.mark.asyncio
    async def test_login_wrong_password(self, client: AsyncClient):
        """Wrong password returns 401."""
        await client.post("/auth/register", json={
            "username": "testuser",
            "password": "securepass123",
        })
        resp = await client.post("/auth/login", data={
            "username": "charlie",
            "password": "wrongpassword",
        })
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_login_nonexistent_user(self, client: AsyncClient):
        """Non-existent username returns 401 (same as wrong password — no enumeration)."""
        resp = await client.post("/auth/login", data={
            "username": "bob",
            "password": "bobpassword123",
        })
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_protected_endpoint_without_token(self, client: AsyncClient):
        """Accessing a protected endpoint without JWT returns 401."""
        resp = await client.post("/encode", data={
            "message": "test",
            "mode": "password",
            "password": "test",
        })
        assert resp.status_code == 401
