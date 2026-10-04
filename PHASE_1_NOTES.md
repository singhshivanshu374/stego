# Phase 1 — Core Crypto & Steganography

## What Was Built

### `backend/app/services/crypto_service.py`
Complete cryptographic service implementing:
- **PBKDF2-HMAC-SHA256** key derivation (100,000 iterations) from user passwords.
- **HKDF-Expand** key separation: every master key (password-derived or random session key) is split into independent AES and HMAC sub-keys via different `info` labels. This applies consistently to **both** Mode A and Mode B.
- **AES-256-GCM** authenticated encryption/decryption.
- **HMAC-SHA256** explicit integrity checking (on top of GCM's built-in auth tag, per spec requirement to demonstrate integrity as its own concept).
- **RSA-2048 with OAEP/SHA-256** for wrapping session keys in Mode B.
- **Mode A** (`encrypt_mode_a` / `decrypt_mode_a`): Password-based. Wire format: `[16B salt][12B nonce][32B HMAC][ciphertext+GCM_tag]`.
- **Mode B** (`encrypt_mode_b` / `decrypt_mode_b`): Hybrid RSA+AES. Wire format: `[2B enc_key_len][encrypted_session_key][12B nonce][32B HMAC][ciphertext+GCM_tag]`.

### `backend/app/services/stego_service.py`
LSB steganography service evolved from `original_steganography.py`:
- **Carried over**: 3-3-2 bit-split across R/G/B channels (`split_byte` / `merge_bits`), BGR channel ordering.
- **Bug fix 1**: Dynamic 4-byte length header replaces hardcoded `qty_to_extract = 26`.
- **Bug fix 2**: Capacity check raises `CapacityError` before embedding if payload won't fit.
- **Bug fix 3**: All hardcoded Windows paths removed — paths are function arguments.
- **Bug fix 4**: 1-byte mode flag (0x00 = Mode A, 0x01 = Mode B) embedded after length header.
- **New**: PNG-only output enforcement; JPEG input rejection with clear error.
- **Design rule**: Stego layer is mode-agnostic (Rule 5.6) — treats payload as opaque bytes.

### `backend/app/cli.py`
Argparse-based CLI for manual testing:
- `encode`: Encrypt + embed a message into a cover image.
- `decode`: Extract + decrypt a message from a stego image (mode auto-detected from flag).
- `keygen`: Generate RSA keypair for Mode B.

### `backend/reference/original_steganography.py`
Original prototype preserved as a documented "before" artifact.

## Key Design Decisions

1. **HKDF key separation in both modes**: Both Mode A and Mode B derive separate AES and HMAC sub-keys from master key material using HKDF-Expand with distinct `info` labels (`securestego-aes-key` / `securestego-hmac-key`). No single key is reused across primitives.

2. **Encrypt-then-MAC**: HMAC is computed over the ciphertext (not plaintext). On decode, HMAC is verified **before** AES-GCM decryption is attempted (Rule 5.2).

3. **Generic error messages**: All `CryptoError` subclasses (`IntegrityError`, `DecryptionError`) return the same string `"Decoding failed."` via `__str__()` (Rule 5.3). Internal exception types differ for debugging, but external representation is identical.

4. **Stego header**: `[4B length][1B mode_flag][payload]` — total 5 bytes overhead. One byte per pixel (3+3+2 = 8 bits). Max payload = (width × height) − 5 bytes.

## Test Summary

**54 tests, all passing** (`pytest tests/ -v`):

| Suite | Tests | Coverage |
|-------|-------|----------|
| `test_crypto_service.py` | 28 | Key derivation, AES-GCM, HMAC, RSA, Mode A, Mode B |
| `test_stego_service.py` | 17 | Bit ops, embed/extract, capacity, JPEG rejection, headers |
| `test_round_trip.py` | 9 | Full pipeline both modes, tampering, wrong credentials, cross-mode |

## How to Run

```bash
cd backend
pip install -r requirements.txt
python -m pytest tests/ -v
```

### CLI usage
```bash
# Mode A
python -m app.cli encode -i cover.png -o stego.png -m "Hello" --mode password -p "secret"
python -m app.cli decode -i stego.png -p "secret"

# Mode B
python -m app.cli keygen -d ./keys/
python -m app.cli encode -i cover.png -o stego.png -m "Hello" --mode user_bound --pubkey ./keys/public.pem
python -m app.cli decode -i stego.png --privkey ./keys/private.pem
```
