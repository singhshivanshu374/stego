"""
Integration tests — full encrypt → embed → extract → decrypt round-trip.

These tests exercise the complete pipeline as a user would use it:
  1. Encrypt plaintext via crypto_service (Mode A or B).
  2. Embed the encrypted payload into an image via stego_service.
  3. Extract the payload from the stego image.
  4. Decrypt the payload back to plaintext.

Also tests tamper detection and wrong-credential scenarios through the full pipeline.

Security rules verified:
  - 5.2: Integrity (HMAC) checked before decryption.
  - 5.3: All failures produce the same generic error message.
"""

import os
import tempfile

import cv2
import numpy as np
import pytest

from app.services.crypto_service import (
    encrypt_mode_a,
    decrypt_mode_a,
    encrypt_mode_b,
    decrypt_mode_b,
    generate_rsa_keypair,
    CryptoError,
)
from app.services.stego_service import embed, extract


# Mode flag constants
MODE_A_FLAG = 0x00
MODE_B_FLAG = 0x01


def _create_test_image(path: str, width: int = 200, height: int = 200) -> str:
    """Create a random-noise PNG test image large enough for typical payloads."""
    image = np.random.randint(0, 256, (height, width, 3), dtype=np.uint8)
    cv2.imwrite(path, image)
    return path


# ---------------------------------------------------------------------------
# Mode A — Full pipeline
# ---------------------------------------------------------------------------

class TestFullPipelineModeA:
    """End-to-end tests for Mode A through the full stego pipeline."""

    def test_full_round_trip_mode_a(self):
        """encrypt → embed → extract → decrypt must recover original plaintext."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cover_path = _create_test_image(os.path.join(tmpdir, "cover.png"))
            stego_path = os.path.join(tmpdir, "stego.png")

            plaintext = b"This is a secret message for Mode A!"
            password = "my_secure_password_2024!"

            # Encrypt
            payload = encrypt_mode_a(plaintext, password)

            # Embed
            embed(cover_path, payload, MODE_A_FLAG, stego_path)

            # Extract
            extracted_payload, mode_flag = extract(stego_path)
            assert mode_flag == MODE_A_FLAG

            # Decrypt
            recovered = decrypt_mode_a(extracted_payload, password)
            assert recovered == plaintext

    def test_wrong_password_mode_a_via_pipeline(self):
        """Wrong password through full pipeline → generic CryptoError (Rule 5.3)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cover_path = _create_test_image(os.path.join(tmpdir, "cover.png"))
            stego_path = os.path.join(tmpdir, "stego.png")

            payload = encrypt_mode_a(b"secret", "correct_password")
            embed(cover_path, payload, MODE_A_FLAG, stego_path)

            extracted_payload, _ = extract(stego_path)

            with pytest.raises(CryptoError) as exc_info:
                decrypt_mode_a(extracted_payload, "wrong_password")
            # Rule 5.3 — generic message
            assert str(exc_info.value) == "Decoding failed."

    def test_tampered_stego_image_mode_a(self):
        """Flipping bits in the stego image must trigger integrity failure (Rule 5.2)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cover_path = _create_test_image(os.path.join(tmpdir, "cover.png"))
            stego_path = os.path.join(tmpdir, "stego.png")

            payload = encrypt_mode_a(b"integrity test with enough data to tamper", "password123")
            embed(cover_path, payload, MODE_A_FLAG, stego_path)

            # Tamper: flip bits deep in the ciphertext region.
            # Stego header = 5 bytes, crypto header (salt+nonce+hmac) = 60 bytes,
            # so ciphertext starts at pixel index ~65. Tamper several pixels there.
            image = cv2.imread(stego_path)
            width = image.shape[1]
            for pixel_idx in range(70, 80):
                r = pixel_idx // width
                c = pixel_idx % width
                image[r, c, 0] ^= 0x03  # Flip blue LSBs
                image[r, c, 1] ^= 0x07  # Flip green LSBs
                image[r, c, 2] ^= 0x07  # Flip red LSBs
            cv2.imwrite(stego_path, image)

            extracted_payload, _ = extract(stego_path)

            # Decryption must fail with integrity/crypto error
            with pytest.raises(CryptoError):
                decrypt_mode_a(extracted_payload, "password123")

    def test_mode_a_unicode_pipeline(self):
        """Unicode text through the full pipeline must survive."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cover_path = _create_test_image(os.path.join(tmpdir, "cover.png"))
            stego_path = os.path.join(tmpdir, "stego.png")

            plaintext = "Héllo Wörld 🌍 日本語テスト".encode("utf-8")
            password = "unicode_test_pwd"

            payload = encrypt_mode_a(plaintext, password)
            embed(cover_path, payload, MODE_A_FLAG, stego_path)
            extracted_payload, _ = extract(stego_path)
            recovered = decrypt_mode_a(extracted_payload, password)
            assert recovered == plaintext


# ---------------------------------------------------------------------------
# Mode B — Full pipeline
# ---------------------------------------------------------------------------

class TestFullPipelineModeB:
    """End-to-end tests for Mode B through the full stego pipeline."""

    def test_full_round_trip_mode_b(self):
        """encrypt → embed → extract → decrypt must recover original plaintext."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cover_path = _create_test_image(os.path.join(tmpdir, "cover.png"))
            stego_path = os.path.join(tmpdir, "stego.png")

            public_pem, private_pem = generate_rsa_keypair()
            plaintext = b"This is a secret message for Mode B!"

            # Encrypt
            payload = encrypt_mode_b(plaintext, public_pem)

            # Embed
            embed(cover_path, payload, MODE_B_FLAG, stego_path)

            # Extract
            extracted_payload, mode_flag = extract(stego_path)
            assert mode_flag == MODE_B_FLAG

            # Decrypt
            recovered = decrypt_mode_b(extracted_payload, private_pem)
            assert recovered == plaintext

    def test_wrong_key_mode_b_via_pipeline(self):
        """Wrong private key through full pipeline → generic CryptoError (Rule 5.3)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cover_path = _create_test_image(os.path.join(tmpdir, "cover.png"))
            stego_path = os.path.join(tmpdir, "stego.png")

            pub1, _priv1 = generate_rsa_keypair()
            _pub2, priv2 = generate_rsa_keypair()

            payload = encrypt_mode_b(b"secret mode b", pub1)
            embed(cover_path, payload, MODE_B_FLAG, stego_path)

            extracted_payload, _ = extract(stego_path)

            with pytest.raises(CryptoError) as exc_info:
                decrypt_mode_b(extracted_payload, priv2)
            assert str(exc_info.value) == "Decoding failed."

    def test_tampered_stego_image_mode_b(self):
        """Flipping bits in the stego image must trigger integrity failure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cover_path = _create_test_image(os.path.join(tmpdir, "cover.png"))
            stego_path = os.path.join(tmpdir, "stego.png")

            public_pem, private_pem = generate_rsa_keypair()
            payload = encrypt_mode_b(b"integrity test mode b with enough data", public_pem)
            embed(cover_path, payload, MODE_B_FLAG, stego_path)

            # Tamper deep in the ciphertext region.
            # Stego header = 5 bytes, Mode B crypto header ≈ 302 bytes
            # (2 enc_key_len + 256 enc_key + 12 nonce + 32 hmac),
            # so ciphertext starts around pixel 307. Tamper there.
            image = cv2.imread(stego_path)
            width = image.shape[1]
            for pixel_idx in range(310, 320):
                r = pixel_idx // width
                c = pixel_idx % width
                image[r, c, 0] ^= 0x03
                image[r, c, 1] ^= 0x07
                image[r, c, 2] ^= 0x07
            cv2.imwrite(stego_path, image)

            extracted_payload, _ = extract(stego_path)

            with pytest.raises(CryptoError):
                decrypt_mode_b(extracted_payload, private_pem)

    def test_mode_b_binary_file_pipeline(self):
        """Binary data (simulating a file) through the full pipeline."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cover_path = _create_test_image(os.path.join(tmpdir, "cover.png"), 300, 300)
            stego_path = os.path.join(tmpdir, "stego.png")

            public_pem, private_pem = generate_rsa_keypair()
            # Simulate a small binary file
            plaintext = os.urandom(500)

            payload = encrypt_mode_b(plaintext, public_pem)
            embed(cover_path, payload, MODE_B_FLAG, stego_path)
            extracted_payload, _ = extract(stego_path)
            recovered = decrypt_mode_b(extracted_payload, private_pem)
            assert recovered == plaintext


# ---------------------------------------------------------------------------
# Cross-mode tests
# ---------------------------------------------------------------------------

class TestCrossMode:
    """Tests that verify mode isolation — Mode A data can't be decoded as Mode B, etc."""

    def test_mode_a_payload_with_mode_b_decrypt_fails(self):
        """Attempting to Mode-B-decrypt a Mode-A payload must fail cleanly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cover_path = _create_test_image(os.path.join(tmpdir, "cover.png"))
            stego_path = os.path.join(tmpdir, "stego.png")

            # Encode with Mode A
            payload = encrypt_mode_a(b"mode a data", "password")
            embed(cover_path, payload, MODE_A_FLAG, stego_path)

            extracted_payload, mode_flag = extract(stego_path)
            assert mode_flag == MODE_A_FLAG  # Should detect correct mode

            # Trying to decrypt as Mode B should fail
            _pub, priv = generate_rsa_keypair()
            with pytest.raises(Exception):  # Could be CryptoError or ValueError
                decrypt_mode_b(extracted_payload, priv)
