"""
Tests for stego_service.py

Covers: embed/extract round-trip, mode flag preservation, capacity errors,
JPEG rejection, dynamic header lengths, edge cases.

All tests use programmatically-generated test images (no external fixtures).
"""

import os
import struct
import tempfile

import cv2
import numpy as np
import pytest

from app.services.stego_service import (
    embed,
    extract,
    split_byte,
    merge_bits,
    CapacityError,
    UnsupportedFormatError,
    HEADER_TOTAL,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_test_image(path: str, width: int = 100, height: int = 100) -> str:
    """Create a solid-color PNG test image and return its path."""
    # Use a varied color pattern so LSB changes are realistic
    image = np.random.randint(0, 256, (height, width, 3), dtype=np.uint8)
    cv2.imwrite(path, image)
    return path


def _create_jpeg_image(path: str, width: int = 100, height: int = 100) -> str:
    """Create a JPEG test image."""
    image = np.random.randint(0, 256, (height, width, 3), dtype=np.uint8)
    cv2.imwrite(path, image, [cv2.IMWRITE_JPEG_QUALITY, 90])
    return path


# ---------------------------------------------------------------------------
# Bit manipulation
# ---------------------------------------------------------------------------

class TestBitOps:
    """Tests for split_byte and merge_bits — carried over from original."""

    def test_split_merge_round_trip_all_values(self):
        """Every byte value (0–255) must survive split→merge."""
        for val in range(256):
            top_3, mid_3, low_2 = split_byte(val)
            reconstructed = merge_bits(top_3, mid_3, low_2)
            assert reconstructed == val, f"Failed for byte value {val}"

    def test_split_known_value(self):
        """Test with ASCII 'a' = 97 = 0b01100001."""
        top_3, mid_3, low_2 = split_byte(97)
        assert top_3 == 3   # 011
        assert mid_3 == 0   # 000
        assert low_2 == 1   # 01

    def test_merge_known_value(self):
        """Merge (3, 0, 1) should give 97 = 'a'."""
        assert merge_bits(3, 0, 1) == 97


# ---------------------------------------------------------------------------
# Embed / Extract round-trip
# ---------------------------------------------------------------------------

class TestEmbedExtract:
    """Tests for LSB embedding and extraction."""

    def test_embed_extract_round_trip(self):
        """Raw bytes must survive embed → extract."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cover_path = _create_test_image(os.path.join(tmpdir, "cover.png"))
            output_path = os.path.join(tmpdir, "stego.png")

            payload = b"Hello, steganography!"
            mode_flag = 0x00

            embed(cover_path, payload, mode_flag, output_path)
            extracted_payload, extracted_flag = extract(output_path)

            assert extracted_payload == payload
            assert extracted_flag == mode_flag

    def test_mode_flag_preserved_mode_a(self):
        """Mode A flag (0x00) must be correctly stored and retrieved."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cover_path = _create_test_image(os.path.join(tmpdir, "cover.png"))
            output_path = os.path.join(tmpdir, "stego.png")

            embed(cover_path, b"test", 0x00, output_path)
            _, flag = extract(output_path)
            assert flag == 0x00

    def test_mode_flag_preserved_mode_b(self):
        """Mode B flag (0x01) must be correctly stored and retrieved."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cover_path = _create_test_image(os.path.join(tmpdir, "cover.png"))
            output_path = os.path.join(tmpdir, "stego.png")

            embed(cover_path, b"test", 0x01, output_path)
            _, flag = extract(output_path)
            assert flag == 0x01

    def test_binary_payload(self):
        """Binary (non-text) payload must survive round-trip."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cover_path = _create_test_image(os.path.join(tmpdir, "cover.png"))
            output_path = os.path.join(tmpdir, "stego.png")

            payload = bytes(range(256))  # All possible byte values
            embed(cover_path, payload, 0x00, output_path)
            extracted, _ = extract(output_path)
            assert extracted == payload

    def test_empty_payload(self):
        """Empty payload should work (only header is embedded)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cover_path = _create_test_image(os.path.join(tmpdir, "cover.png"))
            output_path = os.path.join(tmpdir, "stego.png")

            embed(cover_path, b"", 0x00, output_path)
            extracted, flag = extract(output_path)
            assert extracted == b""
            assert flag == 0x00

    def test_header_dynamic_length_small(self):
        """Small payload must extract correctly (header-driven, no hardcoding)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cover_path = _create_test_image(os.path.join(tmpdir, "cover.png"))
            output_path = os.path.join(tmpdir, "stego.png")

            payload = b"Hi"
            embed(cover_path, payload, 0x00, output_path)
            extracted, _ = extract(output_path)
            assert extracted == payload
            assert len(extracted) == 2

    def test_header_dynamic_length_large(self):
        """Larger payload must also extract correctly via header-driven length."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Use a larger image to hold more data
            cover_path = _create_test_image(os.path.join(tmpdir, "cover.png"), 200, 200)
            output_path = os.path.join(tmpdir, "stego.png")

            payload = os.urandom(1000)  # 1000 random bytes
            embed(cover_path, payload, 0x01, output_path)
            extracted, flag = extract(output_path)
            assert extracted == payload
            assert flag == 0x01

    def test_max_capacity_payload(self):
        """Payload that exactly fills the image should work."""
        with tempfile.TemporaryDirectory() as tmpdir:
            width, height = 20, 20  # 400 pixels → 400 bytes max
            cover_path = _create_test_image(os.path.join(tmpdir, "cover.png"), width, height)
            output_path = os.path.join(tmpdir, "stego.png")

            max_payload = (width * height) - HEADER_TOTAL  # 400 - 5 = 395
            payload = os.urandom(max_payload)
            embed(cover_path, payload, 0x00, output_path)
            extracted, _ = extract(output_path)
            assert extracted == payload


# ---------------------------------------------------------------------------
# Error cases
# ---------------------------------------------------------------------------

class TestStegoErrors:
    """Tests for error handling in stego operations."""

    def test_capacity_error(self):
        """Payload larger than image capacity must raise CapacityError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # 10x10 = 100 pixels = 100 bytes max, minus 5 header = 95 bytes payload max
            cover_path = _create_test_image(os.path.join(tmpdir, "cover.png"), 10, 10)
            output_path = os.path.join(tmpdir, "stego.png")

            oversized_payload = os.urandom(100)  # 100 + 5 header = 105 > 100
            with pytest.raises(CapacityError) as exc_info:
                embed(cover_path, oversized_payload, 0x00, output_path)
            assert "105" in str(exc_info.value) or "100" in str(exc_info.value)

    def test_jpeg_rejected(self):
        """JPEG input must be rejected with UnsupportedFormatError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            jpeg_path = _create_jpeg_image(os.path.join(tmpdir, "cover.jpg"))
            output_path = os.path.join(tmpdir, "stego.png")

            with pytest.raises(UnsupportedFormatError) as exc_info:
                embed(jpeg_path, b"test", 0x00, output_path)
            assert "JPEG" in str(exc_info.value)
            assert "lossy" in str(exc_info.value).lower()

    def test_jpeg_extension_variations(self):
        """All JPEG extension variants must be rejected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "stego.png")
            # Create a base .jpg file, then copy it to other extensions.
            # OpenCV can only write .jpg/.jpeg natively; .jpe/.jfif are
            # detected by our extension check, not by OpenCV's writer.
            base_jpg = _create_jpeg_image(os.path.join(tmpdir, "cover.jpg"))
            for ext in [".jpg", ".jpeg", ".jpe", ".jfif"]:
                target = os.path.join(tmpdir, f"cover{ext}")
                if not os.path.exists(target):
                    import shutil
                    shutil.copy2(base_jpg, target)
                with pytest.raises(UnsupportedFormatError):
                    embed(target, b"test", 0x00, output_path)

    def test_output_forced_to_png(self):
        """Output path should be forced to .png extension."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cover_path = _create_test_image(os.path.join(tmpdir, "cover.png"))
            # Request .bmp output — should be corrected to .png
            output_path = os.path.join(tmpdir, "stego.bmp")
            actual_output = embed(cover_path, b"test", 0x00, output_path)
            assert actual_output.endswith(".png")
            assert os.path.exists(actual_output)

    def test_nonexistent_input_image(self):
        """Non-existent input image must raise FileNotFoundError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with pytest.raises(FileNotFoundError):
                embed(
                    os.path.join(tmpdir, "nonexistent.png"),
                    b"test", 0x00,
                    os.path.join(tmpdir, "stego.png"),
                )

    def test_extract_nonexistent_image(self):
        """Extracting from non-existent image must raise FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            extract("/nonexistent/path/image.png")
