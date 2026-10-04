"""
SecureStego — Pydantic Request/Response Schemas

Validation models for API endpoints. These are the public-facing data contracts.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

class UserRegisterRequest(BaseModel):
    """POST /auth/register — create a new user account."""
    username: str = Field(..., min_length=3, max_length=150, description="Unique username")
    password: str = Field(..., min_length=8, max_length=128, description="Password (min 8 chars)")

    @field_validator("username")
    @classmethod
    def username_alphanumeric(cls, v: str) -> str:
        if not v.replace("_", "").replace("-", "").isalnum():
            raise ValueError("Username must contain only letters, digits, hyphens, and underscores")
        return v.lower()


class UserRegisterResponse(BaseModel):
    """Response after successful registration.

    Returns the private key ONCE. The client must save it — the server will
    never return it again (it's stored encrypted, not in plaintext).
    """
    id: int
    username: str
    private_key_pem: str = Field(
        ...,
        description="RSA private key (PEM). Save this securely — it will NOT be shown again.",
    )
    message: str = "Registration successful. Save your private key — it will not be shown again."


class UserLoginRequest(BaseModel):
    """POST /auth/login — authenticate and receive JWT."""
    username: str
    password: str


class UserLoginResponse(BaseModel):
    """Response after successful login."""
    access_token: str
    token_type: str = "bearer"


# ---------------------------------------------------------------------------
# Encode
# ---------------------------------------------------------------------------

class EncodeResponse(BaseModel):
    """Response after successful encode operation."""
    operation_id: str
    message: str = "Encoding successful."
    download_url: str = Field(..., description="URL to download the stego image")
    mode: str


# ---------------------------------------------------------------------------
# Decode
# ---------------------------------------------------------------------------

class DecodeResponse(BaseModel):
    """Response after successful decode operation."""
    operation_id: str
    message: str = Field(..., description="Decoded plaintext message")
    mode: str


# ---------------------------------------------------------------------------
# General
# ---------------------------------------------------------------------------

class HealthResponse(BaseModel):
    """GET /health — load balancer health check."""
    status: str = "ok"
    service: str = "securestego"


class ErrorResponse(BaseModel):
    """Standard error response.

    Rule 5.3: Wrong-password and unauthorized-recipient errors use the same
    generic detail string so no information leaks about WHY decoding failed.
    """
    detail: str
