# Phase 3 — Storage & Distributed Data

## What Was Built

### `storage_service.py` — Dual-Backend Object Storage
- **Local backend** (default): Filesystem storage for dev/testing, no external deps.
- **S3 backend**: boto3-powered S3-compatible storage. Works identically against:
  - **AWS S3** (free tier) — set `S3_ENDPOINT_URL` to AWS endpoint
  - **MinIO** (local Docker container) — set `S3_ENDPOINT_URL=http://localhost:9000`
- Config-driven switch via `STORAGE_BACKEND` env var ("local" or "s3").
- **Signed URLs**: S3 backend generates pre-signed download URLs with 15-minute expiry.
- **Unified interface**: `upload_file()`, `get_file_path()`, `get_download_url()`, `delete_file()` — API layer doesn't know which backend is active.
- Auto-creates S3 bucket if it doesn't exist.

### `db/mongo.py` — Full MongoDB Audit Trail
- **Motor async client** for non-blocking MongoDB writes.
- **Fire-and-forget**: If MongoDB is unavailable, operations still succeed (Postgres is the source of truth). Failures are logged but not propagated.
- **Audit metadata**: Each mirrored entry includes `mirrored_at` timestamp and `source: "postgres_mirror"`.
- **Query support**: `get_audit_trail()` for filtering by operation_id or user_id.
- **Graceful shutdown**: `close_mongo_client()` called during app lifespan shutdown.
- Lazy client initialization — only connects when first needed.

### `docs/ARCHITECTURE.md`
- Full architecture document with:
  - ASCII architecture diagram
  - Data flow diagrams for encode/decode
  - Database design (Postgres + MongoDB) with rationale
  - S3 lifecycle rule configuration instructions (AWS Console + MinIO CLI)
  - Security model documentation (HKDF key separation, private key trade-off)
  - Cloud-equivalent path (Docker → AWS mapping)

## Key Design Decisions

1. **Config-driven storage backend**: The `STORAGE_BACKEND` env var switches between local and S3 without any code changes. The API layer calls the same functions regardless.

2. **Why both Postgres and MongoDB**: Documented extensively in code and ARCHITECTURE.md:
   - Postgres = relational integrity, foreign keys, transactions (auth source of truth)
   - MongoDB = distributed, schema-flexible audit mirror (can evolve independently, replicate geographically)

3. **Fire-and-forget audit mirroring**: MongoDB writes never block or fail the API response. This ensures the primary operation (encode/decode) always succeeds even if the audit mirror is degraded.

4. **S3 lifecycle rules**: Documented as a manual configuration step since they can't be automated via the free-tier API without specific IAM permissions.

## Test Summary

**77 tests, all passing** (`pytest tests/ -v`):

| Suite | Tests | Coverage |
|-------|-------|----------|
| `test_crypto_service.py` | 28 | Core crypto |
| `test_stego_service.py` | 17 | LSB steganography |
| `test_round_trip.py` | 9 | Full pipeline integration |
| `test_auth.py` | 9 | Auth API |
| `test_api_encode_decode.py` | 5 | Encode/decode API |
| `test_storage_and_audit.py` | 9 | Storage upload/download, MongoDB audit |

## How to Run

```bash
cd backend
pip install -r requirements.txt
python -m pytest tests/ -v
```

### With MinIO (Docker)
```bash
docker run -d -p 9000:9000 -p 9001:9001 \
  -e MINIO_ROOT_USER=minioadmin \
  -e MINIO_ROOT_PASSWORD=minioadmin \
  minio/minio server /data --console-address ":9001"

# Then set env:
export STORAGE_BACKEND=s3
export S3_ENDPOINT_URL=http://localhost:9000
```
