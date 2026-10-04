# Phase 2 — API & Data Layer

## What Was Built

### FastAPI Application (`backend/app/main.py`)
- Application entrypoint with lifespan management (auto-creates tables on startup).
- CORS middleware, health check endpoint (`GET /health`).
- Local file serving for stego images (`GET /storage/{key}`).

### Configuration (`backend/app/config.py`)
- Pydantic-settings based, all values from environment / `.env` file.
- Sensible defaults for local dev (SQLite DB, local filesystem storage, rate limiting disabled).
- Configurable JWT secret, database URL, Redis URL, storage backend, MongoDB toggle.

### Database Layer
- **`db/postgres.py`**: Async SQLAlchemy engine/session factory. Supports SQLite (dev/test) and Postgres (production) via config.
- **`db/mongo.py`**: MongoDB audit trail stub — logs intent, full implementation deferred to Phase 3. Documents the Postgres vs Mongo design rationale.

### Models
- **`models/db_models.py`**:
  - `User`: username, bcrypt password hash, RSA public key (plaintext), encrypted private key (AES-GCM at rest — Rule 5.5). Extensive trade-off documentation.
  - `Operation`: audit log of encode/decode ops — type, mode, sender, recipient, storage path, timestamps. `to_dict()` for Mongo mirroring.
- **`models/schemas.py`**: Pydantic request/response models with validation (username format, password length, etc.).

### Core Security (`core/security.py`)
- **Password hashing**: bcrypt directly (passlib had compatibility issues with bcrypt≥4.1 on Python 3.13).
- **JWT**: Creation/verification via `python-jose`. Configurable expiry.
- **Private key encryption at rest**: AES-256-GCM with key derived from server-side master secret via PBKDF2. Documented trade-off vs client-side key management (Rule 5.5).
- **`get_current_user` dependency**: Extracts user from JWT for protected endpoints.

### Rate Limiting (`core/rate_limit.py`)
- Redis-based sliding window rate limiter (Rule 5.4).
- In-memory fallback when Redis is unavailable.
- `/decode` limited to 5/min, `/encode` to 20/min (configurable).

### Storage Service (`services/storage_service.py`)
- Local filesystem storage for Phase 2. Unified interface — Phase 3 will swap in S3/MinIO without API changes.

### API Endpoints
- **`POST /auth/register`**: Creates user, generates RSA keypair server-side, encrypts private key at rest, returns private key ONCE. Documents client-side key gen as the more secure alternative.
- **`POST /auth/login`**: Returns JWT. Generic error for invalid credentials (no username enumeration).
- **`POST /encode`**: Multipart form (image + message + mode + password/recipient). Encrypts, embeds, stores, records Operation, mirrors to Mongo stub.
- **`POST /decode`**: Multipart form (stego image + optional password). Auto-detects mode from embedded flag. Mode B uses server-side private key custody. All failures return same generic "Decoding failed." (Rule 5.3). Stricter rate limiting (Rule 5.4).
- **`GET /health`**: Load balancer probe.
- **`GET /storage/{key}`**: Serve stored stego images (Phase 2 local, Phase 3 signed URLs).

## Key Design Decisions

1. **Direct bcrypt instead of passlib**: passlib 1.7.4 has a `detect_wrap_bug` compatibility issue with bcrypt≥4.1 on Python 3.13+. Using `bcrypt` directly eliminates this without losing functionality.

2. **Server-side private key custody**: For Mode B decode, the server decrypts the user's private key from at-rest storage using a master secret. This is NOT zero-knowledge — documented extensively in `security.py` and `db_models.py`. Client-side key management is noted as the more secure alternative.

3. **Generic decode errors (Rule 5.3)**: Wrong password (Mode A), wrong recipient (Mode B), and tampered data all return `"Decoding failed."` — no information leakage about failure reason.

4. **SQLite for dev/test**: No external database needed to run tests. Production uses Postgres via `DATABASE_URL` env var.

## Test Summary

**68 tests, all passing** (`pytest tests/ -v`):

| Suite | Tests | Coverage |
|-------|-------|----------|
| `test_crypto_service.py` | 28 | Key derivation, AES-GCM, HMAC, RSA, Mode A, Mode B |
| `test_stego_service.py` | 17 | Bit ops, embed/extract, capacity, JPEG rejection, headers |
| `test_round_trip.py` | 9 | Full pipeline both modes, tampering, wrong credentials |
| `test_auth.py` | 9 | Registration, login, validation, unauthorized access |
| `test_api_encode_decode.py` | 5 | API round trips, unauthorized recipient, wrong password, rate limit |

## How to Run

```bash
cd backend
pip install -r requirements.txt
python -m pytest tests/ -v

# Start the API server
uvicorn app.main:app --reload --port 8000
```

### API examples (curl)
```bash
# Register
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username": "alice", "password": "securepass123"}'

# Login
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "alice", "password": "securepass123"}'

# Encode (Mode A)
curl -X POST http://localhost:8000/encode \
  -H "Authorization: Bearer <JWT>" \
  -F "image=@cover.png" \
  -F "message=Hello" \
  -F "mode=password" \
  -F "password=mysecret"

# Decode (Mode A)
curl -X POST http://localhost:8000/decode \
  -H "Authorization: Bearer <JWT>" \
  -F "image=@stego.png" \
  -F "password=mysecret"
```
