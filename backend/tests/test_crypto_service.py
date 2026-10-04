"""
Tests for crypto_service.py

Covers: key derivation, AES-GCM, HMAC, RSA, Mode A, Mode B.
All failure tests verify clean exceptions — no crashes, no plaintext leakage.
"""

import os
import pytest

from app.services.crypto_service import (
    derive_key_from_password,
    _derive_sub_keys,
    aes_encrypt,
    aes_decrypt,
    compute_hmac,
    verify_hmac,
    generate_rsa_keypair,
    rsa_encrypt,
    rsa_decrypt,
    encrypt_mode_a,
    decrypt_mode_a,
    encrypt_mode_b,
    decrypt_mode_b,
    IntegrityError,
    DecryptionError,
    CryptoError,
)


# ---------------------------------------------------------------------------
# Key derivation
# ---------------------------------------------------------------------------

class TestKeyDerivation:
    """Tests for PBKDF2 and HKDF key derivation."""

    def test_derive_key_deterministic(self):
        """Same password + salt must produce the same key."""
        salt = os.urandom(16)
        key1 = derive_key_from_password("testpass", salt)
        key2 = derive_key_from_password("testpass", salt)
        assert key1 == key2
        assert len(key1) == 32

    def test_derive_key_different_salt(self):
        """Different salt must produce a different key."""
        salt1 = os.urandom(16)
        salt2 = os.urandom(16)
        key1 = derive_key_from_password("testpass", salt1)
        key2 = derive_key_from_password("testpass", salt2)
        assert key1 != key2

    def test_derive_key_different_password(self):
        """Different password must produce a different key."""
        salt = os.urandom(16)
        key1 = derive_key_from_password("password1", salt)
        key2 = derive_key_from_password("password2", salt)
        assert key1 != key2

    def test_hkdf_sub_keys_are_different(self):
        """HKDF-Expand with different info labels must yield different sub-keys."""
        master = os.urandom(32)
        aes_key, hmac_key = _derive_sub_keys(master)
        assert aes_key != hmac_key
        assert len(aes_key) == 32
        assert len(hmac_key) == 32

    def test_hkdf_deterministic(self):
        """Same master key must produce the same sub-keys."""
        master = os.urandom(32)
        aes1, hmac1 = _derive_sub_keys(master)
        aes2, hmac2 = _derive_sub_keys(master)
        assert aes1 == aes2
        assert hmac1 == hmac2


# ---------------------------------------------------------------------------
# AES-GCM
# ---------------------------------------------------------------------------

class TestAESGCM:
    """Tests for AES-256-GCM encryption/decryption."""

    def test_aes_round_trip(self):
        """Encrypt then decrypt must recover the original plaintext."""
        key = os.urandom(32)
        plaintext = b"Hello, SecureStego!"
        ciphertext, nonce = aes_encrypt(plaintext, key)
        recovered = aes_decrypt(ciphertext, key, nonce)
        assert recovered == plaintext

    def test_aes_wrong_key(self):
        """Decrypting with the wrong key must raise DecryptionError."""
        key1 = os.urandom(32)
        key2 = os.urandom(32)
        plaintext = b"test data"
        ciphertext, nonce = aes_encrypt(plaintext, key1)
        with pytest.raises(DecryptionError):
            aes_decrypt(ciphertext, key2, nonce)

    def test_aes_tampered_ciphertext(self):
        """Modifying the ciphertext must cause GCM tag failure."""
        key = os.urandom(32)
        plaintext = b"integrity test"
        ciphertext, nonce = aes_encrypt(plaintext, key)
        # Flip a bit in the ciphertext
        tampered = bytearray(ciphertext)
        tampered[0] ^= 0xFF
        tampered = bytes(tampered)
        with pytest.raises(DecryptionError):
            aes_decrypt(tampered, key, nonce)

    def test_aes_empty_plaintext(self):
        """AES-GCM should handle empty plaintext."""
        key = os.urandom(32)
        ciphertext, nonce = aes_encrypt(b"", key)
        recovered = aes_decrypt(ciphertext, key, nonce)
        assert recovered == b""

    def test_aes_large_plaintext(self):
        """AES-GCM should handle large payloads."""
        key = os.urandom(32)
        plaintext = os.urandom(1024 * 100)  # 100 KB
        ciphertext, nonce = aes_encrypt(plaintext, key)
        recovered = aes_decrypt(ciphertext, key, nonce)
        assert recovered == plaintext


# ---------------------------------------------------------------------------
# HMAC
# ---------------------------------------------------------------------------

class TestHMAC:
    """Tests for HMAC-SHA256."""

    def test_hmac_round_trip(self):
        """Compute then verify must succeed."""
        key = os.urandom(32)
        data = b"test data for HMAC"
        tag = compute_hmac(data, key)
        assert verify_hmac(data, key, tag) is True

    def test_hmac_tampered_data(self):
        """Modified data must fail verification."""
        key = os.urandom(32)
        data = b"original data"
        tag = compute_hmac(data, key)
        assert verify_hmac(data + b"x", key, tag) is False

    def test_hmac_wrong_key(self):
        """Wrong key must fail verification."""
        key1 = os.urandom(32)
        key2 = os.urandom(32)
        data = b"test data"
        tag = compute_hmac(data, key1)
        assert verify_hmac(data, key2, tag) is False

    def test_hmac_deterministic(self):
        """Same data + key must produce the same tag."""
        key = os.urandom(32)
        data = b"deterministic test"
        tag1 = compute_hmac(data, key)
        tag2 = compute_hmac(data, key)
        assert tag1 == tag2
        assert len(tag1) == 32


# ---------------------------------------------------------------------------
# RSA
# ---------------------------------------------------------------------------

class TestRSA:
    """Tests for RSA keypair generation, encryption, and decryption."""

    def test_rsa_round_trip(self):
        """Generate keypair, encrypt with public, decrypt with private."""
        public_pem, private_pem = generate_rsa_keypair()
        data = os.urandom(32)  # Typical AES session key
        encrypted = rsa_encrypt(data, public_pem)
        recovered = rsa_decrypt(encrypted, private_pem)
        assert recovered == data

    def test_rsa_wrong_key(self):
        """Decrypting with a mismatched private key must raise DecryptionError."""
        pub1, priv1 = generate_rsa_keypair()
        _pub2, priv2 = generate_rsa_keypair()
        data = os.urandom(32)
        encrypted = rsa_encrypt(data, pub1)
        with pytest.raises(DecryptionError):
            rsa_decrypt(encrypted, priv2)

    def test_rsa_keypair_format(self):
        """Generated keys must be valid PEM-encoded bytes."""
        public_pem, private_pem = generate_rsa_keypair()
        assert public_pem.startswith(b"-----BEGIN PUBLIC KEY-----")
        assert private_pem.startswith(b"-----BEGIN PRIVATE KEY-----")


# ---------------------------------------------------------------------------
# Mode A — Password-based
# ---------------------------------------------------------------------------

class TestModeA:
    """Tests for Mode A (password-based) high-level encrypt/decrypt."""

    def test_mode_a_round_trip(self):
        """Encrypt then decrypt with correct password recovers plaintext."""
        plaintext = b"Secret message for Mode A testing!"
        password = "strong_password_123!"
        payload = encrypt_mode_a(plaintext, password)
        recovered = decrypt_mode_a(payload, password)
        assert recovered == plaintext

    def test_mode_a_wrong_password(self):
        """Wrong password must raise IntegrityError or DecryptionError, never crash."""
        plaintext = b"Another secret"
        payload = encrypt_mode_a(plaintext, "correct_password")
        with pytest.raises(CryptoError):
            decrypt_mode_a(payload, "wrong_password")

    def test_mode_a_generic_error_message(self):
        """Error message must be the same generic string regardless of failure type (Rule 5.3)."""
        plaintext = b"test"
        payload = encrypt_mode_a(plaintext, "correct")
        try:
            decrypt_mode_a(payload, "wrong")
            assert False, "Should have raised"
        except CryptoError as e:
            assert str(e) == "Decoding failed."

    def test_mode_a_tampered_payload(self):
        """Tampered payload must be detected by HMAC check."""
        payload = encrypt_mode_a(b"secret", "password")
        # Tamper with the ciphertext portion (after salt+nonce+hmac = 60 bytes)
        tampered = bytearray(payload)
        if len(tampered) > 61:
            tampered[61] ^= 0xFF
        payload = bytes(tampered)
        with pytest.raises(CryptoError):
            decrypt_mode_a(payload, "password")

    def test_mode_a_empty_message(self):
        """Should handle empty plaintext."""
        payload = encrypt_mode_a(b"", "password")
        recovered = decrypt_mode_a(payload, "password")
        assert recovered == b""

    def test_mode_a_unicode_message(self):
        """Should handle unicode messages."""
        plaintext = "Hello 世界 🌍 émojis".encode("utf-8")
        payload = encrypt_mode_a(plaintext, "password")
        recovered = decrypt_mode_a(payload, "password")
        assert recovered == plaintext


# ---------------------------------------------------------------------------
# Mode B — Hybrid RSA + AES
# ---------------------------------------------------------------------------

class TestModeB:
    """Tests for Mode B (user-bound / hybrid RSA+AES) high-level encrypt/decrypt."""

    def test_mode_b_round_trip(self):
        """Encrypt with public key, decrypt with matching private key."""
        public_pem, private_pem = generate_rsa_keypair()
        plaintext = b"Secret message for Mode B testing!"
        payload = encrypt_mode_b(plaintext, public_pem)
        recovered = decrypt_mode_b(payload, private_pem)
        assert recovered == plaintext

    def test_mode_b_wrong_key(self):
        """Wrong private key must raise CryptoError, never crash."""
        pub1, _priv1 = generate_rsa_keypair()
        _pub2, priv2 = generate_rsa_keypair()
        plaintext = b"Mode B secret"
        payload = encrypt_mode_b(plaintext, pub1)
        with pytest.raises(CryptoError):
            decrypt_mode_b(payload, priv2)

    def test_mode_b_generic_error_message(self):
        """Error message must be the same generic string (Rule 5.3)."""
        pub1, _priv1 = generate_rsa_keypair()
        _pub2, priv2 = generate_rsa_keypair()
        payload = encrypt_mode_b(b"test", pub1)
        try:
            decrypt_mode_b(payload, priv2)
            assert False, "Should have raised"
        except CryptoError as e:
            assert str(e) == "Decoding failed."

    def test_mode_b_tampered_payload(self):
        """Tampered payload must be caught by HMAC or GCM."""
        public_pem, private_pem = generate_rsa_keypair()
        payload = encrypt_mode_b(b"secret", public_pem)
        # Tamper with ciphertext portion (near the end)
        tampered = bytearray(payload)
        tampered[-1] ^= 0xFF
        payload = bytes(tampered)
        with pytest.raises(CryptoError):
            decrypt_mode_b(payload, private_pem)

    def test_mode_b_empty_message(self):
        """Should handle empty plaintext."""
        public_pem, private_pem = generate_rsa_keypair()
        payload = encrypt_mode_b(b"", public_pem)
        recovered = decrypt_mode_b(payload, private_pem)
        assert recovered == b""
