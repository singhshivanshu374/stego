"""
SecureStego — Cryptographic Service

All encryption, decryption, key derivation, HMAC, and RSA operations.
Supports two modes:
  - Mode A (password-based): AES-256-GCM with key derived via PBKDF2 from user password.
  - Mode B (user-bound / hybrid RSA+AES): Random AES session key encrypted with
    recipient's RSA public key.

Both modes use HKDF-Expand to derive separate AES and HMAC sub-keys from a single
master key material, ensuring no single key is reused across different cryptographic
primitives.

Both modes apply an explicit HMAC-SHA256 integrity check on top of AES-GCM's built-in
authentication, to separately demonstrate integrity verification as its own concept.
HMAC is always verified BEFORE decryption is attempted (encrypt-then-MAC pattern).

Security rules (spec §5) applied:
  - 5.1: No plaintext, passwords, or private keys are ever logged.
  - 5.2: Integrity (HMAC) verified before any decryption.
  - 5.3: All failure modes surface the same generic message "Decoding failed."
"""

import os
import struct

from cryptography.hazmat.primitives import hashes, hmac as crypto_hmac, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding as asym_padding
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDFExpand
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.exceptions import InvalidTag, InvalidSignature


# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------

class CryptoError(Exception):
    """Base class for all crypto-related errors."""

    def __str__(self) -> str:
        # Rule 5.3 — always return the same generic message externally.
        return "Decoding failed."


class IntegrityError(CryptoError):
    """HMAC verification failed — data may have been tampered with."""
    pass


class DecryptionError(CryptoError):
    """Decryption failed — wrong key, corrupt ciphertext, or GCM tag mismatch."""
    pass


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PBKDF2_ITERATIONS = 100_000
SALT_LENGTH = 16          # bytes
AES_KEY_LENGTH = 32       # 256 bits
NONCE_LENGTH = 12         # bytes — standard for AES-GCM
GCM_TAG_LENGTH = 16       # bytes — appended to ciphertext by AESGCM
HMAC_TAG_LENGTH = 32      # bytes — SHA-256 output
RSA_KEY_SIZE = 2048
HKDF_AES_INFO = b"securestego-aes-key"
HKDF_HMAC_INFO = b"securestego-hmac-key"


# ---------------------------------------------------------------------------
# Key derivation
# ---------------------------------------------------------------------------

def derive_key_from_password(password: str, salt: bytes) -> bytes:
    """Derive a 32-byte master key from a password using PBKDF2-HMAC-SHA256.

    The caller should generate a random salt (16 bytes) and store it alongside
    the ciphertext so the same key can be re-derived for decryption.

    Args:
        password: User-supplied password (any length).
        salt: Random salt bytes (must be the same for derive and verify).

    Returns:
        32-byte derived master key material.
    """
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=AES_KEY_LENGTH,
        salt=salt,
        iterations=PBKDF2_ITERATIONS,
    )
    return kdf.derive(password.encode("utf-8"))


def _derive_sub_keys(master_key: bytes) -> tuple[bytes, bytes]:
    """Derive separate AES and HMAC sub-keys from master key material via HKDF-Expand.

    This ensures no single key is reused across two different cryptographic
    primitives (AES-GCM encryption vs HMAC integrity check).

    Args:
        master_key: 32-byte master key material (from PBKDF2 or random session key).

    Returns:
        (aes_key, hmac_key) — each 32 bytes.
    """
    aes_key = HKDFExpand(
        algorithm=hashes.SHA256(),
        length=AES_KEY_LENGTH,
        info=HKDF_AES_INFO,
    ).derive(master_key)

    hmac_key = HKDFExpand(
        algorithm=hashes.SHA256(),
        length=AES_KEY_LENGTH,
        info=HKDF_HMAC_INFO,
    ).derive(master_key)

    return aes_key, hmac_key


# ---------------------------------------------------------------------------
# AES-GCM encryption / decryption
# ---------------------------------------------------------------------------

def aes_encrypt(plaintext: bytes, key: bytes) -> tuple[bytes, bytes]:
    """Encrypt plaintext using AES-256-GCM.

    AES-GCM provides authenticated encryption — the returned ciphertext includes
    a 16-byte GCM authentication tag appended by the library.

    Args:
        plaintext: Data to encrypt.
        key: 32-byte AES key.

    Returns:
        (ciphertext_with_tag, nonce) — ciphertext has GCM tag appended.
    """
    nonce = os.urandom(NONCE_LENGTH)
    aesgcm = AESGCM(key)
    ciphertext_with_tag = aesgcm.encrypt(nonce, plaintext, None)
    return ciphertext_with_tag, nonce


def aes_decrypt(ciphertext_with_tag: bytes, key: bytes, nonce: bytes) -> bytes:
    """Decrypt AES-256-GCM ciphertext.

    Args:
        ciphertext_with_tag: Ciphertext with GCM tag appended.
        key: 32-byte AES key (must match encryption key).
        nonce: 12-byte nonce used during encryption.

    Returns:
        Decrypted plaintext bytes.

    Raises:
        DecryptionError: If GCM tag verification fails (wrong key or tampered data).
    """
    aesgcm = AESGCM(key)
    try:
        return aesgcm.decrypt(nonce, ciphertext_with_tag, None)
    except InvalidTag:
        raise DecryptionError("GCM authentication tag verification failed.")


# ---------------------------------------------------------------------------
# HMAC-SHA256
# ---------------------------------------------------------------------------

def compute_hmac(data: bytes, key: bytes) -> bytes:
    """Compute HMAC-SHA256 over data.

    Args:
        data: Data to authenticate.
        key: HMAC key (32 bytes).

    Returns:
        32-byte HMAC tag.
    """
    h = crypto_hmac.HMAC(key, hashes.SHA256())
    h.update(data)
    return h.finalize()


def verify_hmac(data: bytes, key: bytes, tag: bytes) -> bool:
    """Verify an HMAC-SHA256 tag (constant-time comparison).

    Args:
        data: Data that was authenticated.
        key: HMAC key (32 bytes).
        tag: Expected HMAC tag.

    Returns:
        True if tag is valid, False otherwise. Never raises — caller decides
        what to do on failure.
    """
    h = crypto_hmac.HMAC(key, hashes.SHA256())
    h.update(data)
    try:
        h.verify(tag)
        return True
    except InvalidSignature:
        return False


# ---------------------------------------------------------------------------
# RSA key management
# ---------------------------------------------------------------------------

def generate_rsa_keypair() -> tuple[bytes, bytes]:
    """Generate a 2048-bit RSA keypair.

    Returns:
        (public_key_pem, private_key_pem) — PEM-encoded bytes.
    """
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=RSA_KEY_SIZE,
    )

    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )

    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    return public_pem, private_pem


def rsa_encrypt(data: bytes, public_key_pem: bytes) -> bytes:
    """Encrypt data with an RSA public key using OAEP/SHA-256 padding.

    Intended for wrapping short secrets (e.g., 32-byte AES session keys).
    Max plaintext size for RSA-2048/OAEP/SHA-256 ≈ 190 bytes.

    Args:
        data: Data to encrypt (must be ≤ ~190 bytes for RSA-2048).
        public_key_pem: PEM-encoded RSA public key.

    Returns:
        RSA-encrypted ciphertext (256 bytes for RSA-2048).
    """
    public_key = serialization.load_pem_public_key(public_key_pem)
    return public_key.encrypt(
        data,
        asym_padding.OAEP(
            mgf=asym_padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None,
        ),
    )


def rsa_decrypt(encrypted_data: bytes, private_key_pem: bytes) -> bytes:
    """Decrypt RSA-encrypted data with a private key.

    Args:
        encrypted_data: RSA ciphertext.
        private_key_pem: PEM-encoded RSA private key.

    Returns:
        Decrypted plaintext bytes.

    Raises:
        DecryptionError: If decryption fails (wrong key or corrupt data).
    """
    private_key = serialization.load_pem_private_key(private_key_pem, password=None)
    try:
        return private_key.decrypt(
            encrypted_data,
            asym_padding.OAEP(
                mgf=asym_padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None,
            ),
        )
    except (ValueError, TypeError) as exc:
        raise DecryptionError(f"RSA decryption failed: {exc}")


# ---------------------------------------------------------------------------
# Mode A — Password-based encryption
# ---------------------------------------------------------------------------
#
# Payload wire format:
#   [16 bytes salt][12 bytes nonce][32 bytes HMAC tag][N bytes ciphertext+GCM_tag]
#
# Total fixed overhead: 60 bytes.
#
# Flow:
#   Encrypt: password → PBKDF2 → master_key → HKDF → (aes_key, hmac_key)
#            plaintext → AES-GCM(aes_key) → ciphertext
#            HMAC(hmac_key, ciphertext) → hmac_tag
#            Concatenate: salt ‖ nonce ‖ hmac_tag ‖ ciphertext
#
#   Decrypt: Extract salt → re-derive master_key → HKDF → (aes_key, hmac_key)
#            Verify HMAC FIRST (Rule 5.2) → then AES-GCM decrypt.

def encrypt_mode_a(plaintext: bytes, password: str) -> bytes:
    """Encrypt plaintext using Mode A (password-based).

    Args:
        plaintext: Message bytes to encrypt.
        password: User-supplied password.

    Returns:
        Complete payload bytes ready for embedding (salt ‖ nonce ‖ hmac ‖ ciphertext).
    """
    salt = os.urandom(SALT_LENGTH)
    master_key = derive_key_from_password(password, salt)
    aes_key, hmac_key = _derive_sub_keys(master_key)

    ciphertext_with_tag, nonce = aes_encrypt(plaintext, aes_key)
    hmac_tag = compute_hmac(ciphertext_with_tag, hmac_key)

    return salt + nonce + hmac_tag + ciphertext_with_tag


def decrypt_mode_a(payload: bytes, password: str) -> bytes:
    """Decrypt a Mode A payload.

    Verifies HMAC integrity BEFORE attempting decryption (Rule 5.2).

    Args:
        payload: Complete payload bytes (salt ‖ nonce ‖ hmac ‖ ciphertext).
        password: User-supplied password.

    Returns:
        Decrypted plaintext bytes.

    Raises:
        IntegrityError: If HMAC verification fails.
        DecryptionError: If AES-GCM decryption fails.
    """
    # Unpack fixed-length fields
    offset = 0
    salt = payload[offset:offset + SALT_LENGTH]
    offset += SALT_LENGTH

    nonce = payload[offset:offset + NONCE_LENGTH]
    offset += NONCE_LENGTH

    hmac_tag = payload[offset:offset + HMAC_TAG_LENGTH]
    offset += HMAC_TAG_LENGTH

    ciphertext_with_tag = payload[offset:]

    # Re-derive keys
    master_key = derive_key_from_password(password, salt)
    aes_key, hmac_key = _derive_sub_keys(master_key)

    # Rule 5.2 — verify integrity BEFORE decryption
    if not verify_hmac(ciphertext_with_tag, hmac_key, hmac_tag):
        raise IntegrityError("HMAC verification failed — data may be tampered or wrong password.")

    return aes_decrypt(ciphertext_with_tag, aes_key, nonce)


# ---------------------------------------------------------------------------
# Mode B — Hybrid RSA + AES encryption
# ---------------------------------------------------------------------------
#
# Payload wire format:
#   [2 bytes enc_key_len][M bytes encrypted_session_key][12 bytes nonce]
#   [32 bytes HMAC tag][N bytes ciphertext+GCM_tag]
#
# Flow:
#   Encrypt: Generate random 32-byte session_key
#            session_key → HKDF → (aes_key, hmac_key)
#            RSA-encrypt session_key with recipient's public key
#            plaintext → AES-GCM(aes_key) → ciphertext
#            HMAC(hmac_key, ciphertext) → hmac_tag
#            Concatenate: enc_key_len ‖ enc_session_key ‖ nonce ‖ hmac_tag ‖ ciphertext
#
#   Decrypt: Extract enc_key_len → RSA-decrypt session_key with private key
#            session_key → HKDF → (aes_key, hmac_key)
#            Verify HMAC FIRST → then AES-GCM decrypt.

def encrypt_mode_b(plaintext: bytes, recipient_public_key_pem: bytes) -> bytes:
    """Encrypt plaintext using Mode B (hybrid RSA+AES, user-bound).

    A random one-time AES session key is generated and RSA-encrypted with the
    recipient's public key. Only the holder of the matching private key can
    recover the session key and decrypt the message.

    Args:
        plaintext: Message bytes to encrypt.
        recipient_public_key_pem: Recipient's PEM-encoded RSA public key.

    Returns:
        Complete payload bytes ready for embedding.
    """
    # Generate random session key and derive sub-keys
    session_key = os.urandom(AES_KEY_LENGTH)
    aes_key, hmac_key = _derive_sub_keys(session_key)

    # RSA-encrypt the session key
    encrypted_session_key = rsa_encrypt(session_key, recipient_public_key_pem)
    enc_key_len = len(encrypted_session_key)

    # AES-GCM encrypt the plaintext
    ciphertext_with_tag, nonce = aes_encrypt(plaintext, aes_key)

    # HMAC over ciphertext
    hmac_tag = compute_hmac(ciphertext_with_tag, hmac_key)

    # Pack: [2-byte enc_key_len][enc_session_key][nonce][hmac_tag][ciphertext]
    return (
        struct.pack(">H", enc_key_len)
        + encrypted_session_key
        + nonce
        + hmac_tag
        + ciphertext_with_tag
    )


def decrypt_mode_b(payload: bytes, recipient_private_key_pem: bytes) -> bytes:
    """Decrypt a Mode B payload.

    Verifies HMAC integrity BEFORE attempting AES decryption (Rule 5.2).

    Args:
        payload: Complete payload bytes.
        recipient_private_key_pem: Recipient's PEM-encoded RSA private key.

    Returns:
        Decrypted plaintext bytes.

    Raises:
        DecryptionError: If RSA or AES-GCM decryption fails.
        IntegrityError: If HMAC verification fails.
    """
    offset = 0

    # Unpack encrypted session key length
    enc_key_len = struct.unpack(">H", payload[offset:offset + 2])[0]
    offset += 2

    # Extract encrypted session key
    encrypted_session_key = payload[offset:offset + enc_key_len]
    offset += enc_key_len

    # Extract nonce
    nonce = payload[offset:offset + NONCE_LENGTH]
    offset += NONCE_LENGTH

    # Extract HMAC tag
    hmac_tag = payload[offset:offset + HMAC_TAG_LENGTH]
    offset += HMAC_TAG_LENGTH

    # Remaining bytes are ciphertext + GCM tag
    ciphertext_with_tag = payload[offset:]

    # RSA-decrypt the session key
    session_key = rsa_decrypt(encrypted_session_key, recipient_private_key_pem)

    # Derive sub-keys from session key
    aes_key, hmac_key = _derive_sub_keys(session_key)

    # Rule 5.2 — verify integrity BEFORE decryption
    if not verify_hmac(ciphertext_with_tag, hmac_key, hmac_tag):
        raise IntegrityError("HMAC verification failed — data may be tampered.")

    return aes_decrypt(ciphertext_with_tag, aes_key, nonce)
