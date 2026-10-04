"""
SecureStego — Security Module

JWT creation/verification and password hashing.

Security rules applied:
  - 5.1: Passwords are hashed with bcrypt, never stored or logged in plaintext.
  - 5.5: User private keys are encrypted at rest with a server-side master key.
         Trade-off: this is NOT zero-knowledge — the server holds the master key.
         The more secure alternative (client-side key generation and custody) is
         documented here and in db_models.py.
"""

import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
import bcrypt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

from app.config import get_settings
from app.db.postgres import get_db

settings = get_settings()

# ---------------------------------------------------------------------------
# Password hashing (bcrypt directly — passlib has compatibility issues
# with bcrypt>=4.1 on Python 3.13)
# ---------------------------------------------------------------------------


def hash_password(password: str) -> str:
    """Hash a password with bcrypt."""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its bcrypt hash."""
    return bcrypt.checkpw(
        plain_password.encode("utf-8"),
        hashed_password.encode("utf-8"),
    )


# ---------------------------------------------------------------------------
# JWT
# ---------------------------------------------------------------------------

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token.

    Args:
        data: Payload claims (must include 'sub' with user identifier).
        expires_delta: Token lifetime. Defaults to config value.

    Returns:
        Encoded JWT string.
    """
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.jwt_access_token_expire_minutes)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    """Decode and verify a JWT access token.

    Raises:
        HTTPException 401: If the token is invalid or expired.
    """
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
):
    """FastAPI dependency — extracts and validates the current user from JWT.

    Returns the User ORM object.

    Raises:
        HTTPException 401: If token is invalid or user not found.
    """
    payload = decode_access_token(token)
    username: str = payload.get("sub")
    if username is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload.",
        )

    # Import here to avoid circular imports
    from app.models.db_models import User
    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found.",
        )
    return user


# ---------------------------------------------------------------------------
# Private key encryption at rest (Rule 5.5)
# ---------------------------------------------------------------------------
#
# Trade-off documentation:
#   The private key is encrypted using AES-256-GCM with a key derived from a
#   server-side master secret (PRIVATE_KEY_MASTER_SECRET in config/env).
#
#   This means:
#     - Private keys are NEVER stored in plaintext in the database. ✓
#     - The server CAN decrypt them (it holds the master key). ✗ not zero-knowledge.
#     - If the master key is compromised, all private keys are compromised.
#
#   More secure alternative (noted per spec):
#     Client-side key generation — the server never receives the private key.
#     The client generates the RSA keypair, sends only the public key during
#     registration, and manages the private key entirely on their own device.
#     This makes Mode B decode a client-side operation. Chosen against here
#     for simplicity in a portfolio/demo context where the API needs to perform
#     Mode B decryption server-side.

_MASTER_KEY_SALT = b"securestego-pk-encryption-salt-v1"  # Fixed salt (acceptable: master secret is high-entropy)


def _derive_master_encryption_key() -> bytes:
    """Derive a 32-byte AES key from the server-side master secret."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=_MASTER_KEY_SALT,
        iterations=100_000,
    )
    return kdf.derive(settings.private_key_master_secret.encode("utf-8"))


def encrypt_private_key(private_key_pem: bytes) -> str:
    """Encrypt a PEM private key for at-rest storage.

    Returns:
        Hex-encoded string: nonce (12 bytes) + ciphertext (includes GCM tag).
    """
    key = _derive_master_encryption_key()
    nonce = os.urandom(12)
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(nonce, private_key_pem, None)
    return (nonce + ciphertext).hex()


def decrypt_private_key(encrypted_hex: str) -> bytes:
    """Decrypt a stored private key from its hex-encoded encrypted form.

    Returns:
        PEM-encoded private key bytes.
    """
    raw = bytes.fromhex(encrypted_hex)
    nonce = raw[:12]
    ciphertext = raw[12:]
    key = _derive_master_encryption_key()
    aesgcm = AESGCM(key)
    return aesgcm.decrypt(nonce, ciphertext, None)
