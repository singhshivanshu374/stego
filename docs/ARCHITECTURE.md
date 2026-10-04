# SecureStego — Architecture Document

## System Overview

SecureStego is a security-first image steganography platform that hides encrypted messages inside images using LSB (Least Significant Bit) steganography, with two authorization modes:

- **Mode A (Password-based)**: AES-256-GCM encryption, key derived from a user-supplied password via PBKDF2. Anyone with the password can decode.
- **Mode B (User-bound / Hybrid RSA+AES)**: Message encrypted with a random one-time AES key, which is itself encrypted with the recipient's RSA-2048 public key. Only the recipient's registered account can decode.

Both modes apply an explicit HMAC-SHA256 integrity check on top of AES-GCM's built-in authentication. HMAC is verified **before** decryption is attempted (encrypt-then-MAC pattern).

---

## Architecture Diagram

```
┌──────────────────────────────────────────────────────────┐
│                     React Frontend                        │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐             │
│  │ EncodeTab │  │ DecodeTab │  │ ModeToggle│             │
│  └─────┬─────┘  └─────┬─────┘  └───────────┘             │
│        │              │                                   │
│        └──────┬───────┘                                   │
│               │  HTTP/REST                                │
└───────────────┼───────────────────────────────────────────┘
                │
        ┌───────▼───────┐
        │   Nginx LB    │  (round-robin, health checks)
        │  (port 80)    │
        └───┬───┬───┬───┘
            │   │   │
     ┌──────┘   │   └──────┐
     ▼          ▼          ▼
┌─────────┐┌─────────┐┌─────────┐
│ API #1  ││ API #2  ││ API #3  │  FastAPI (3 replicas)
│ :8001   ││ :8002   ││ :8003   │
└────┬────┘└────┬────┘└────┬────┘
     │          │          │
     └────┬─────┴─────┬────┘
          │           │
    ┌─────▼────┐ ┌────▼─────┐
    │ Postgres │ │  Redis   │  Primary DB + Rate Limiter
    │ :5432    │ │  :6379   │
    └──────────┘ └──────────┘

    ┌──────────┐ ┌──────────┐
    │  MinIO   │ │ MongoDB  │  Object Storage + Audit Trail
    │  :9000   │ │  :27017  │
    └──────────┘ └──────────┘

    ┌──────────┐ ┌──────────┐
    │Prometheus│ │ Grafana  │  Monitoring
    │  :9090   │ │  :3000   │
    └──────────┘ └──────────┘
```

---

## Data Flow

### Encode (POST /encode)

```
Client → Nginx → API Instance
  1. Authenticate (JWT)
  2. Rate-limit check (Redis)
  3. Encrypt plaintext:
     Mode A: PBKDF2 → master_key → HKDF → (aes_key, hmac_key)
             AES-GCM encrypt → compute HMAC → build payload
     Mode B: Random session_key → HKDF → (aes_key, hmac_key)
             RSA-encrypt session_key → AES-GCM encrypt → compute HMAC → build payload
  4. Embed payload into image (LSB steganography)
  5. Upload stego image → S3/MinIO
  6. Record Operation → Postgres
  7. Mirror audit entry → MongoDB
  8. Return signed download URL → Client
```

### Decode (POST /decode)

```
Client → Nginx → API Instance
  1. Authenticate (JWT)
  2. Rate-limit check (Redis — stricter: 5/min vs 20/min)
  3. Extract payload from stego image (read length header → mode flag → bytes)
  4. Decrypt:
     Mode A: Re-derive key from password → verify HMAC FIRST → AES-GCM decrypt
     Mode B: RSA-decrypt session key → HKDF sub-keys → verify HMAC FIRST → AES-GCM decrypt
  5. Record Operation → Postgres + MongoDB mirror
  6. Return plaintext → Client
     (All failures return same generic "Decoding failed." message)
```

---

## Database Design

### PostgreSQL (Primary — Relational Integrity)

**Users table:**
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | Auto-increment |
| username | VARCHAR(150) | Unique, indexed |
| password_hash | VARCHAR(255) | bcrypt hash |
| public_key_pem | TEXT | RSA public key (plaintext — it's public) |
| encrypted_private_key | TEXT | AES-GCM encrypted with server master key |
| created_at | TIMESTAMPTZ | UTC |

**Operations table:**
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | Auto-increment |
| operation_id | VARCHAR(36) | UUID, unique |
| operation_type | ENUM | 'encode' or 'decode' |
| mode | ENUM | 'password' or 'user_bound' |
| sender_id | FK → users.id | Who performed the operation |
| recipient_id | FK → users.id | Mode B recipient (nullable) |
| image_filename | VARCHAR(500) | Original upload filename |
| storage_path | VARCHAR(1000) | S3 key / local path |
| status | VARCHAR(50) | 'completed', 'failed' |
| created_at | TIMESTAMPTZ | UTC |

### MongoDB (Audit Mirror — Distributed)

**Why both?**
- **Postgres**: Relational integrity, foreign keys, transactions. The authoritative source of truth.
- **MongoDB**: Schema-flexible, distributed audit trail. Can be replicated across regions independently via Atlas replica sets. Audit schema can evolve without Alembic migrations.

Every Operation write to Postgres is mirrored to MongoDB asynchronously (fire-and-forget). If MongoDB is unavailable, the operation still succeeds.

**Collection: `operations`**
```json
{
  "operation_id": "uuid-string",
  "operation_type": "encode",
  "mode": "password",
  "sender_id": 1,
  "recipient_id": null,
  "image_filename": "cover.png",
  "storage_path": "abc123.png",
  "status": "completed",
  "created_at": "2024-01-01T00:00:00+00:00",
  "mirrored_at": "2024-01-01T00:00:01+00:00",
  "source": "postgres_mirror"
}
```

---

## Object Storage

### Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| STORAGE_BACKEND | `local` | `local` or `s3` |
| S3_ENDPOINT_URL | `http://localhost:9000` | MinIO or AWS S3 endpoint |
| S3_ACCESS_KEY | `minioadmin` | Access key |
| S3_SECRET_KEY | `minioadmin` | Secret key |
| S3_BUCKET_NAME | `securestego` | Bucket name |

### S3 Lifecycle Rules (Manual Configuration)

To auto-delete old stego images, configure a lifecycle rule:

**AWS S3 (Console):**
1. Navigate to S3 → your bucket → Management tab
2. Create lifecycle rule → "Delete objects after 30 days"
3. Apply to all objects in the bucket

**MinIO (CLI):**
```bash
mc ilm rule add myminio/securestego --expiry-days 30
```

### Signed URLs

When `STORAGE_BACKEND=s3`, the `/encode` response includes a pre-signed download URL with a 15-minute expiry. This URL allows downloading the stego image without authentication, but expires after the configured time.

---

## Security Model

### Key Derivation (HKDF Key Separation)

Both modes derive separate AES and HMAC sub-keys from master key material:

```
Master Key (from PBKDF2 or random)
    ├─ HKDF-Expand(info="securestego-aes-key")  → AES-256 encryption key
    └─ HKDF-Expand(info="securestego-hmac-key") → HMAC-SHA256 key
```

No single key is reused across primitives.

### Private Key Storage (Trade-off)

User RSA private keys are encrypted at rest using AES-256-GCM with a key derived from a server-side master secret (`PRIVATE_KEY_MASTER_SECRET` in config).

**Trade-off**: The server holds the master key → it can decrypt any user's private key → this is NOT zero-knowledge. The more secure alternative is client-side key management where the server never receives the private key. Server-side custody is used here for simplicity so Mode B decode can work without the user supplying their key.

### Error Handling (Rule 5.3)

All decode failures (wrong password, wrong recipient, tampered data) return the same generic error: `"Decoding failed."` — no information about WHY it failed is leaked.

---

## Cloud-Equivalent Path

| Local (Docker Compose) | Cloud (AWS) |
|------------------------|-------------|
| Nginx round-robin | AWS ALB + Auto Scaling Group |
| 3 FastAPI containers | ECS Fargate tasks or EC2 + ASG |
| PostgreSQL container | RDS PostgreSQL |
| Redis container | ElastiCache Redis |
| MinIO container | S3 |
| MongoDB container | MongoDB Atlas (free tier) |
| Prometheus + Grafana | CloudWatch + Grafana Cloud |

**Kubernetes alternative**: A `k3s` / `minikube` Deployment + Service + liveness/readiness probes configuration is a documented stretch goal — **not yet implemented**.

---

## Not Yet Implemented

- [ ] Frontend (React) — Phase 6
- [ ] Kubernetes manifests — stretch goal
- [ ] Alembic migrations — using auto-create tables for dev
- [ ] Client-side key generation — documented trade-off, server-side custody used
