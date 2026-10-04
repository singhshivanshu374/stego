"""
SecureStego — Decode API Route

POST /decode — Upload stego image, extract payload, decrypt, return plaintext.

Requires valid JWT. Rate-limited more strictly (5/min per user by default — Rule 5.4).

Security rules applied:
  - 5.2: Integrity (HMAC) verified before decryption.
  - 5.3: Wrong-password and unauthorized-recipient errors return the SAME
         generic message ("Decoding failed.") to prevent information leakage.
  - 5.4: /decode is rate-limited more strictly than /encode.
"""

import os
import tempfile

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.rate_limit import check_rate_limit
from app.core.security import get_current_user
from app.db.mongo import mirror_operation_to_mongo
from app.db.postgres import get_db
from app.models.db_models import Operation, User
from app.models.schemas import DecodeResponse
from app.services.crypto_service import (
    CryptoError,
    decrypt_mode_a,
    decrypt_mode_b,
)
from app.services.stego_service import StegoError, extract

settings = get_settings()
router = APIRouter(tags=["steganography"])

# Mode flag constants
MODE_A_FLAG = 0x00
MODE_B_FLAG = 0x01

# Rule 5.3 — generic error message for ALL decode failures.
# Same message for wrong password, wrong key, tampered data, unauthorized recipient.
GENERIC_DECODE_ERROR = "Decoding failed."


@router.post(
    "/decode",
    response_model=DecodeResponse,
    summary="Extract and decrypt a message from a stego image",
    description="Upload a stego image to extract and decrypt the hidden message. "
                "Mode A requires a password. Mode B uses your registered private key.",
)
async def decode(
    image: UploadFile = File(..., description="Stego image containing hidden data"),
    password: str = Form(None, description="Password (required for Mode A)"),
    private_key: str = Form(None, description="Private key PEM (required for Mode B)"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Decode a message from a stego image.

    Flow:
      1. Rate-limit check (stricter than /encode — Rule 5.4).
      2. Save uploaded image to temp file.
      3. Extract payload + mode flag from stego image.
      4. Based on mode flag:
         - Mode A: Decrypt with provided password.
         - Mode B: Decrypt with the provided private key.
      5. Record Operation in Postgres + mirror to Mongo.
      6. Return decoded message.

    All decode failures return the same generic error (Rule 5.3).
    Never logs the decoded plaintext (Rule 5.1).
    """
    # Rate limit — stricter for decode (Rule 5.4)
    await check_rate_limit(current_user.id, "decode")

    # Save uploaded image to temp file
    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = os.path.join(tmpdir, image.filename or "stego.png")
        content = await image.read()
        with open(input_path, "wb") as f:
            f.write(content)

        # Extract payload from stego image
        try:
            payload, mode_flag = extract(input_path)
        except (StegoError, ValueError) as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=GENERIC_DECODE_ERROR,
            )

    # Decrypt based on mode flag
    mode = "password" if mode_flag == MODE_A_FLAG else "user_bound"

    if mode_flag == MODE_A_FLAG:
        # Mode A — password-based
        if not password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password is required for password-mode images.",
            )
        try:
            plaintext = decrypt_mode_a(payload, password)
        except CryptoError:
            # Rule 5.3 — generic error, no info about why it failed
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=GENERIC_DECODE_ERROR,
            )

    elif mode_flag == MODE_B_FLAG:
        # Mode B — user-bound (RSA)
        if not private_key:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Private key file is required for decoding Mode B images.",
            )
        private_key_pem = private_key.encode('utf-8')

        try:
            plaintext = decrypt_mode_b(payload, private_key_pem)
        except CryptoError:
            # Rule 5.3 — same generic message whether it's wrong key, tampered data, etc.
            # If the current user isn't the intended recipient, RSA decryption will fail,
            # which produces the same generic error — no 403 that reveals information.
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=GENERIC_DECODE_ERROR,
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=GENERIC_DECODE_ERROR,
        )

    # Record operation in Postgres
    operation = Operation(
        operation_type="decode",
        mode=mode,
        sender_id=current_user.id,
        image_filename=image.filename,
    )
    db.add(operation)
    await db.flush()
    await db.refresh(operation)

    # Mirror to MongoDB (Phase 3)
    await mirror_operation_to_mongo(operation.to_dict())

    # Decode plaintext to string — never log this (Rule 5.1)
    try:
        message_text = plaintext.decode("utf-8")
    except UnicodeDecodeError:
        message_text = "[Binary data — download via /storage endpoint]"

    return DecodeResponse(
        operation_id=operation.operation_id,
        message=message_text,
        mode=mode,
    )
