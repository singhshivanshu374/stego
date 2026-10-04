"""
SecureStego — Steganography Service

LSB (Least Significant Bit) image steganography: embed arbitrary byte payloads
into PNG images and extract them back.

Evolved from the user's original prototype (see backend/reference/original_steganography.py).
What was carried over:
  - The 3-3-2 bit-split approach across R/G/B channels (split_byte / merge_bits).
  - BGR channel ordering (OpenCV convention).
What was fixed / added:
  - Bug: extract() hardcoded qty_to_extract=26 → now reads a 4-byte length header.
  - Bug: No capacity check → now raises CapacityError before embedding.
  - Bug: Hardcoded Windows paths → all paths are function arguments.
  - New: 1-byte mode flag embedded after the length header.
  - New: PNG-only output enforcement; JPEG input rejection.
  - The stego layer is MODE-AGNOSTIC (Rule 5.6): it stores/retrieves a mode flag
    byte and opaque payload bytes. It never interprets their contents.

Embedding layout (per pixel = 1 byte of data):
  Pixel channel bits used:  Red[2:0]=3 bits, Green[2:0]=3 bits, Blue[1:0]=2 bits
  Total = 8 bits = 1 byte per pixel.

Embedded byte stream layout:
  [4 bytes — payload length as uint32 big-endian]
  [1 byte  — mode flag (0x00=Mode A, 0x01=Mode B)]
  [N bytes — payload (encrypted ciphertext)]
"""

import os
import struct

import cv2
import numpy as np


# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------

class StegoError(Exception):
    """Base class for steganography errors."""
    pass


class CapacityError(StegoError):
    """Payload exceeds the image's embedding capacity."""
    pass


class UnsupportedFormatError(StegoError):
    """Image format is not suitable for LSB steganography (e.g., JPEG)."""
    pass


# ---------------------------------------------------------------------------
# Header constants
# ---------------------------------------------------------------------------

HEADER_LENGTH_BYTES = 4   # uint32 big-endian — payload length
MODE_FLAG_BYTES = 1       # 1 byte — mode flag
HEADER_TOTAL = HEADER_LENGTH_BYTES + MODE_FLAG_BYTES  # 5 bytes overhead


# ---------------------------------------------------------------------------
# Bit manipulation — carried over from original, with corrected naming
# ---------------------------------------------------------------------------

def split_byte(byte_val: int) -> tuple[int, int, int]:
    """Split a byte into (top_3_bits, mid_3_bits, low_2_bits).

    The original prototype called this 'spiltbyte' (typo). Logic is identical:
      byte_val = 0bTTTMMMLL
      top_3  = bits[7:5]  → embedded into Red channel (3 LSBs)
      mid_3  = bits[4:2]  → embedded into Green channel (3 LSBs)
      low_2  = bits[1:0]  → embedded into Blue channel (2 LSBs)

    Args:
        byte_val: Integer 0–255.

    Returns:
        (top_3, mid_3, low_2) — each fits in the stated number of bits.
    """
    top_3 = byte_val >> 5
    mid_3 = (byte_val >> 2) & 0b111
    low_2 = byte_val & 0b11
    return top_3, mid_3, low_2


def merge_bits(red_bits: int, green_bits: int, blue_bits: int) -> int:
    """Reconstruct a byte from its 3-3-2 bit components.

    Inverse of split_byte.

    Args:
        red_bits: Top 3 bits (from Red channel LSBs).
        green_bits: Mid 3 bits (from Green channel LSBs).
        blue_bits: Low 2 bits (from Blue channel LSBs).

    Returns:
        Reconstructed byte (0–255).
    """
    return ((red_bits << 3) | green_bits) << 2 | blue_bits


# ---------------------------------------------------------------------------
# Input validation helpers
# ---------------------------------------------------------------------------

_JPEG_EXTENSIONS = {".jpg", ".jpeg", ".jpe", ".jfif"}
_PNG_EXTENSIONS = {".png"}


def _validate_input_image(image_path: str) -> None:
    """Reject JPEG (lossy) images for embedding."""
    ext = os.path.splitext(image_path)[1].lower()
    if ext in _JPEG_EXTENSIONS:
        raise UnsupportedFormatError(
            f"JPEG images are not supported for steganographic embedding because "
            f"JPEG compression is lossy and will corrupt embedded LSB data. "
            f"Please convert '{image_path}' to PNG first."
        )


def _validate_output_path(output_path: str) -> str:
    """Ensure output path uses PNG extension (lossless)."""
    base, ext = os.path.splitext(output_path)
    if ext.lower() not in _PNG_EXTENSIONS:
        output_path = base + ".png"
    return output_path


def _check_capacity(rows: int, cols: int, total_bytes_needed: int) -> None:
    """Verify the image can hold the required number of bytes.

    Each pixel holds exactly 1 byte (3+3+2 = 8 bits across BGR channels).
    Max capacity = rows × cols bytes.

    Raises:
        CapacityError: If the payload (including header) won't fit.
    """
    max_bytes = rows * cols
    if total_bytes_needed > max_bytes:
        raise CapacityError(
            f"Payload requires {total_bytes_needed} bytes but the image can hold "
            f"at most {max_bytes} bytes ({rows}×{cols} pixels). "
            f"Use a larger image or a shorter message."
        )


# ---------------------------------------------------------------------------
# Core embed / extract
# ---------------------------------------------------------------------------

def embed(image_path: str, payload: bytes, mode_flag: int, output_path: str) -> str:
    """Embed a byte payload into an image using LSB steganography.

    The stego layer is mode-agnostic (Rule 5.6). It embeds:
      [4 bytes length header][1 byte mode flag][N bytes payload]
    It does not interpret the payload contents.

    Args:
        image_path: Path to the cover image (must not be JPEG).
        payload: Encrypted payload bytes to embed.
        mode_flag: Mode identifier byte (0x00=Mode A, 0x01=Mode B).
        output_path: Path for the output stego image (forced to .png).

    Returns:
        The actual output path used (may have .png appended).

    Raises:
        CapacityError: If payload + header won't fit in the image.
        UnsupportedFormatError: If input image is JPEG.
        FileNotFoundError: If input image doesn't exist.
    """
    # Validate input format
    _validate_input_image(image_path)
    output_path = _validate_output_path(output_path)

    # Load image
    image = cv2.imread(image_path)
    if image is None:
        raise FileNotFoundError(f"Could not load image: {image_path}")

    rows, cols = image.shape[:2]

    # Build the full byte stream: [length][mode_flag][payload]
    payload_length = len(payload)
    header = struct.pack(">I", payload_length) + struct.pack("B", mode_flag)
    data = header + payload
    total_bytes = len(data)

    # Capacity check (Bug fix #2)
    _check_capacity(rows, cols, total_bytes)

    # Embed byte-by-byte, one byte per pixel
    idx = 0
    for r in range(rows):
        if idx >= total_bytes:
            break
        for c in range(cols):
            if idx >= total_bytes:
                break

            top_3, mid_3, low_2 = split_byte(data[idx])

            # Clear LSBs: Blue=2, Green=3, Red=3 (OpenCV BGR order)
            image[r, c, 0] = (image[r, c, 0] & 0xFC) | low_2   # Blue: clear 2 LSBs, set low_2
            image[r, c, 1] = (image[r, c, 1] & 0xF8) | mid_3   # Green: clear 3 LSBs, set mid_3
            image[r, c, 2] = (image[r, c, 2] & 0xF8) | top_3   # Red: clear 3 LSBs, set top_3

            idx += 1

    # Save as PNG (lossless)
    cv2.imwrite(output_path, image)
    return output_path


def extract(image_path: str) -> tuple[bytes, int]:
    """Extract a payload from a stego image.

    Reads the 4-byte length header first (Bug fix #1 — no hardcoded quantities),
    then reads the 1-byte mode flag, then reads exactly `payload_length` bytes.

    Args:
        image_path: Path to the stego image.

    Returns:
        (payload_bytes, mode_flag) — the raw payload and the mode flag byte.

    Raises:
        FileNotFoundError: If image doesn't exist.
        ValueError: If the embedded header indicates more data than the image
                    could possibly hold (corrupt or non-stego image).
    """
    image = cv2.imread(image_path)
    if image is None:
        raise FileNotFoundError(f"Could not load image: {image_path}")

    rows, cols = image.shape[:2]
    max_bytes = rows * cols

    def _read_byte_at(pixel_index: int) -> int:
        """Read one embedded byte from the pixel at the given linear index."""
        r = pixel_index // cols
        c = pixel_index % cols
        red_bits = image[r, c, 2] & 0b111
        green_bits = image[r, c, 1] & 0b111
        blue_bits = image[r, c, 0] & 0b11
        return merge_bits(red_bits, green_bits, blue_bits)

    # Read the 4-byte length header
    if max_bytes < HEADER_TOTAL:
        raise ValueError("Image too small to contain a steganographic header.")

    header_bytes = bytes(_read_byte_at(i) for i in range(HEADER_LENGTH_BYTES))
    payload_length = struct.unpack(">I", header_bytes)[0]

    # Read the 1-byte mode flag
    mode_flag = _read_byte_at(HEADER_LENGTH_BYTES)

    # Sanity check — payload_length should be reasonable
    total_needed = HEADER_TOTAL + payload_length
    if total_needed > max_bytes:
        raise ValueError(
            f"Embedded header claims payload length {payload_length} bytes, but the "
            f"image only has capacity for {max_bytes - HEADER_TOTAL} payload bytes. "
            f"The image may not contain steganographic data or is corrupted."
        )

    # Read the payload bytes
    payload = bytes(
        _read_byte_at(HEADER_TOTAL + i) for i in range(payload_length)
    )

    return payload, mode_flag
