"""
SecureStego — Encode API Route

POST /encode — Upload image + message, encrypt (Mode A or B), embed into image,
               store result, return download URL.

Requires valid JWT. Rate-limited (20/min per user by default).
"""

import os
import tempfile

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.rate_limit import check_rate_limit
from app.core.security import get_current_user
from app.db.mongo import mirror_operation_to_mongo
from app.db.postgres import get_db
from app.models.db_models import Operation, User
from app.models.schemas import EncodeResponse
from app.services.crypto_service import (
    CryptoError,
    encrypt_mode_a,
    encrypt_mode_b,
)
from app.services.stego_service import StegoError, embed
from app.services import storage_service

settings = get_settings()
router = APIRouter(tags=["steganography"])

# Mode flag constants
MODE_A_FLAG = 0x00
MODE_B_FLAG = 0x01


@router.post(
    "/encode",
    response_model=EncodeResponse,
    summary="Encrypt and embed a message into an image",
    description="Upload a cover image and a message. The message is encrypted "
                "(Mode A: password-based, Mode B: user-bound via RSA) and embedded "
                "into the image using LSB steganography.",
)
async def encode(
    image: UploadFile = File(..., description="Cover image (PNG recommended, JPEG rejected)"),
    message: str = Form(..., description="Text message to embed"),
    mode: str = Form(..., description="'password' (Mode A) or 'user_bound' (Mode B)"),
    password: str = Form(None, description="Password for Mode A encryption"),
    recipient_username: str = Form(None, description="Recipient username for Mode B"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Encode a message into an image.

    Flow:
      1. Validate mode and required fields.
      2. Rate-limit check.
      3. Encrypt plaintext (Mode A with password, or Mode B with recipient's public key).
      4. Save uploaded image to temp file.
      5. Embed encrypted payload into image.
      6. Upload result to storage.
      7. Record Operation in Postgres + mirror to Mongo.
      8. Return download URL.

    Never logs plaintext message content (Rule 5.1).
    """
    # Validate mode
    if mode not in ("password", "user_bound"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Mode must be 'password' or 'user_bound'.",
        )

    # Rate limit
    await check_rate_limit(current_user.id, "encode")

    # Encrypt based on mode
    plaintext = message.encode("utf-8")
    recipient_id = None

    if mode == "password":
        if not password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password is required for password mode.",
            )
        try:
            payload = encrypt_mode_a(plaintext, password)
        except CryptoError:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Encryption failed.",
            )
        mode_flag = MODE_A_FLAG

    else:  # user_bound
        if not recipient_username:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Recipient username is required for user_bound mode.",
            )

        # Look up recipient's public key
        result = await db.execute(
            select(User).where(User.username == recipient_username)
        )
        recipient = result.scalar_one_or_none()
        if recipient is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Recipient user not found.",
            )

        recipient_id = recipient.id
        try:
            payload = encrypt_mode_b(plaintext, recipient.public_key_pem.encode("utf-8"))
        except CryptoError:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Encryption failed.",
            )
        mode_flag = MODE_B_FLAG

    # Save uploaded image to temp file
    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = os.path.join(tmpdir, image.filename or "upload.png")
        output_path = os.path.join(tmpdir, "stego_output.png")

        content = await image.read()
        with open(input_path, "wb") as f:
            f.write(content)

        # Embed payload into image
        try:
            actual_output = embed(input_path, payload, mode_flag, output_path)
        except StegoError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e),
            )

        # Upload to storage
        storage_key, download_url = await storage_service.upload_file(
            actual_output, "stego_output.png"
        )

    # Record operation in Postgres
    operation = Operation(
        operation_type="encode",
        mode=mode,
        sender_id=current_user.id,
        recipient_id=recipient_id,
        image_filename=image.filename,
        storage_path=storage_key,
    )
    db.add(operation)
    await db.flush()
    await db.refresh(operation)

    # Mirror to MongoDB (Phase 3 — currently a stub)
    await mirror_operation_to_mongo(operation.to_dict())

    return EncodeResponse(
        operation_id=operation.operation_id,
        download_url=f"/operations/{operation.operation_id}/download",
        mode=mode,
    )
