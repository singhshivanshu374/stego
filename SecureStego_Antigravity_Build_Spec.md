# SecureStego — Autonomous Build Specification
### Give this entire file to the agent as its first prompt. It is self-contained — do not ask the user clarifying questions; make the reasonable assumptions stated below and proceed.

---

## 0. Instructions to the Agent

You are building **SecureStego**, a security-first image steganography platform, as a portfolio/interview project. Work **phase by phase, in order**. After each phase:
1. Write working code for that phase only.
2. Write unit/integration tests for that phase and run them.
3. Confirm tests pass before moving to the next phase.
4. Write a short `PHASE_X_NOTES.md` summarizing what was built, key design decisions, and how to run/test it.

Do not skip ahead to later phases before earlier ones are tested and working. Do not ask the user which library/framework to use — this document already specifies the stack. If something genuinely blocks progress (e.g., a paid API key needed), stub it with a clear `# TODO: requires API key` comment and continue with everything else, using a mock/local equivalent (e.g., MinIO instead of real S3, local Postgres instead of a cloud instance) so the whole system still runs end-to-end locally.

Assume a Python 3.11+ backend, a React frontend, Docker for containerization, and free-tier equivalents for any cloud service so the entire project can be developed and demoed without spending money.

### 0.1 About the reference file in this workspace

A file named `original_steganography.py` (the user's original, pre-existing project) is present in this same workspace folder. Treat it as follows:

- **Read it first, before writing any Phase 1 code.** It contains the original LSB embed/extract logic (`spiltbyte`, `merge_bits`, `embed`, `extract`) that this whole project is evolving from.
- **Do not copy it as-is.** It has known bugs that Phase 1 must fix, specifically:
  - `extract()` hardcodes `qty_to_extract = 26` — must become a dynamic length read from an embedded header.
  - No capacity check — must be added (raise a clear error if payload won't fit).
  - Hardcoded Windows file paths in `main()` — must be replaced with proper function arguments / CLI args.
  - No mode flag, no encryption, no HMAC — all of this is new in this project and doesn't exist in the original at all.
- **Do reuse the core bit-manipulation approach** (`spiltbyte`'s 3-3-2 bit split across B/G/R channels, and `merge_bits`'s reconstruction) as the basis for the new `stego_service.py`, since it's correct and it keeps a genuine throughline from the user's original work to the final project — useful for the user to explain in interviews ("I evolved my own working prototype").
- **Move the original file into `backend/reference/original_steganography.py`** in the new repo structure once read, so it stays as a documented "before" artifact and isn't confused with the new `stego_service.py`. Reference it once, in a code comment at the top of `stego_service.py`, noting what was carried over and what was fixed.
- Do not preserve any of its bugs "for compatibility" — this is a clean rebuild informed by the original, not a wrapper around it.

---

## 1. Project Overview

A platform that hides encrypted messages/files inside images using LSB (Least Significant Bit) steganography, with two selectable authorization modes:

- **Mode A — Password-based**: AES-256 encryption, key derived from a user-supplied password via PBKDF2. Anyone with the password can decode.
- **Mode B — User-bound (Hybrid RSA+AES)**: message encrypted with a random one-time AES key, which is itself encrypted with the recipient's RSA public key. Only the recipient's registered account (with matching private key) can decode — password not required.

Both modes embed data into the image using the **same LSB algorithm**; only the encrypted payload differs.

All operations are integrity-checked with **HMAC** before decryption is attempted.

The system is exposed via a load-balanced, containerized FastAPI backend with PostgreSQL (relational data), Redis (rate limiting), S3-compatible object storage (images), an optional MongoDB replica set (distributed audit trail), Prometheus/Grafana (monitoring), and GitHub Actions (CI/CD). Frontend is a React SPA.

---

## 2. Tech Stack (fixed — do not substitute without noting why)

| Concern | Choice |
|---|---|
| Language | Python 3.11+ (backend), TypeScript/JavaScript (frontend) |
| Web framework | FastAPI |
| Image processing | OpenCV (`opencv-python`) |
| Crypto | `cryptography` library (AES-GCM or AES-CBC+HMAC, RSA via `cryptography.hazmat`) |
| Auth | JWT (`python-jose` or `pyjwt`), passwords hashed with `bcrypt`/`passlib` |
| Primary DB | PostgreSQL (SQLAlchemy + Alembic for migrations) |
| Cache/rate-limit | Redis (`redis-py`, or `fastapi-limiter`) |
| Object storage | S3-compatible — use `boto3` against real AWS S3 free tier, or **MinIO** locally as a drop-in stub if no AWS account is configured |
| Distributed audit DB | MongoDB Atlas free-tier replica set (`pymongo` / `motor`); local `mongod` replica set as fallback stub |
| Containerization | Docker + Docker Compose |
| Load balancer | Nginx (local/dev); note AWS ALB as the cloud-equivalent in docs only |
| Monitoring | `prometheus-client` (FastAPI middleware) + Prometheus + Grafana (docker-compose services) |
| CI/CD | GitHub Actions |
| Load testing | Locust |
| Frontend | React (Vite), fetch/axios for API calls, plain CSS or Tailwind |
| Testing | `pytest`, `pytest-asyncio`, `httpx` for API tests |

---

## 3. Repository Structure (create exactly this layout)

```
securestego/
├── backend/
│   ├── app/
│   │   ├── main.py                 # FastAPI app entrypoint
│   │   ├── config.py                # settings via pydantic-settings, .env driven
│   │   ├── api/
│   │   │   ├── auth.py              # /register, /login
│   │   │   ├── encode.py            # /encode
│   │   │   └── decode.py            # /decode
│   │   ├── core/
│   │   │   ├── security.py          # JWT creation/verification, password hashing
│   │   │   └── rate_limit.py        # Redis-based limiter, stricter on decode
│   │   ├── services/
│   │   │   ├── crypto_service.py     # AES, PBKDF2, RSA hybrid, HMAC (Mode A + B)
│   │   │   ├── stego_service.py      # LSB embed/extract, dynamic length header, mode-flag byte
│   │   │   └── storage_service.py    # S3/MinIO upload/download, signed URLs
│   │   ├── models/
│   │   │   ├── db_models.py          # SQLAlchemy models: User, Operation
│   │   │   └── schemas.py            # Pydantic request/response models
│   │   ├── db/
│   │   │   ├── postgres.py           # session/engine setup
│   │   │   └── mongo.py              # motor client, audit mirror writes
│   │   └── monitoring/
│   │       └── metrics.py            # Prometheus counters/histograms
│   ├── tests/
│   │   ├── test_crypto_service.py
│   │   ├── test_stego_service.py
│   │   ├── test_api_encode_decode.py
│   │   └── test_auth.py
│   ├── alembic/                      # migrations
│   ├── requirements.txt
│   ├── Dockerfile
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── App.tsx
│   │   ├── components/
│   │   │   ├── EncodeTab.tsx
│   │   │   ├── DecodeTab.tsx
│   │   │   ├── ModeToggle.tsx
│   │   │   └── Uploader.tsx
│   │   └── api/client.ts
│   ├── package.json
│   └── Dockerfile
├── infra/
│   ├── docker-compose.yml            # api x3 + nginx + postgres + redis + minio + mongo + prometheus + grafana
│   ├── nginx/nginx.conf               # round-robin LB + health checks
│   └── prometheus/prometheus.yml
├── loadtest/
│   └── locustfile.py
├── .github/workflows/ci.yml
├── docs/
│   ├── ARCHITECTURE.md               # copy of the architecture doc (provided separately, or regenerate from this spec)
│   └── API.md                        # auto-generated/OpenAPI reference notes
└── README.md
```

---

## 4. Phase-by-Phase Requirements

### Phase 1 — Core Crypto & Steganography (no API yet)
**Build:**
- `crypto_service.py`:
  - `derive_key_from_password(password, salt) -> bytes` (PBKDF2-HMAC-SHA256, ≥100k iterations)
  - `aes_encrypt(plaintext, key) -> (ciphertext, nonce/iv)` and `aes_decrypt(ciphertext, key, nonce) -> plaintext` (use AES-GCM so it gives you authenticated encryption; still implement a separate explicit HMAC step as well so the design explicitly demonstrates integrity-checking as its own concept)
  - `compute_hmac(data, key) -> bytes` and `verify_hmac(data, key, tag) -> bool`
  - `generate_rsa_keypair() -> (public_key_pem, private_key_pem)`
  - `rsa_encrypt(session_key, public_key_pem) -> bytes` and `rsa_decrypt(encrypted_session_key, private_key_pem) -> bytes`
  - `encrypt_mode_a(plaintext, password) -> payload_bytes` (bundles salt + HMAC + ciphertext with clear length-prefixed framing)
  - `decrypt_mode_a(payload_bytes, password) -> plaintext` (raises specific exceptions: `IntegrityError` vs `DecryptionError`)
  - `encrypt_mode_b(plaintext, recipient_public_key_pem) -> payload_bytes` (bundles encrypted session key + HMAC + ciphertext)
  - `decrypt_mode_b(payload_bytes, recipient_private_key_pem) -> plaintext`
- `stego_service.py`:
  - Fix all bugs from the original script: dynamic length header (store payload length as a fixed-size prefix, e.g., first 32 bits), a **1-byte mode flag** (0x00 = Mode A, 0x01 = Mode B) embedded right after the length header, and a capacity check that raises a clear error if `payload_size > rows*cols*bits_per_pixel_available`.
  - `embed(image_path, payload_bytes, output_path)` and `extract(image_path) -> payload_bytes` (extract reads the header first to know exactly how many bytes to pull — no hardcoded quantities).
  - Enforce PNG-only for output (lossless) and reject/warn on JPEG input for embedding.
- Remove all hardcoded Windows paths; use `argparse` for a CLI entrypoint (`python -m app.cli embed ...`, `python -m app.cli extract ...`) so it's independently testable before the API exists.

**Tests (must pass before Phase 2):**
- Round-trip: encrypt→embed→extract→decrypt returns original plaintext, both modes.
- Wrong password (Mode A) → clean exception, no crash.
- Wrong/mismatched private key (Mode B) → clean exception.
- Tampered stego image (flip a bit post-embed) → HMAC/GCM integrity failure detected, decryption not attempted.
- Payload larger than image capacity → raises a capacity error before attempting to embed.
- JPEG passed as embedding target → rejected with clear error.

### Phase 2 — API & Data Layer
**Build:**
- `POST /auth/register` — creates user, generates RSA keypair server-side for simplicity (note in code comments that client-side key generation is the more secure alternative and why), stores public key in Postgres, returns private key **once** to the client (never stored in plaintext server-side — if persisted at all, encrypt-at-rest with a key derived from the user's password).
- `POST /auth/login` — returns JWT.
- `POST /encode` — multipart form: image file, message (text or file), mode (`password` or `user_bound`), password (if mode A) or recipient_username (if mode B). Requires valid JWT. Calls crypto_service + stego_service, uploads result to storage_service, writes an `Operation` row to Postgres and mirrors it to Mongo, returns a signed download URL.
- `POST /decode` — multipart form: stego image, password (if mode A, optional field). Requires valid JWT. If mode B, checks that `current_user.id == operation.recipient_id` before attempting decrypt — return 403 with a generic message if not. Returns plaintext message or a file download. Never logs plaintext.
- `GET /health` — for load balancer checks.
- Rate limiting: `/decode` limited more strictly than `/encode` (e.g., 5/min vs 20/min per user) via Redis.

**Tests:**
- Full API round trip for both modes via `httpx` test client.
- Unauthorized recipient attempting Mode B decode → 403.
- Wrong password on Mode A decode via API → clean 4xx error, generic message.
- Rate limit triggers after threshold on `/decode`.

### Phase 3 — Storage & Distributed Data
**Build:**
- `storage_service.py` using `boto3` against real S3 if `.env` has AWS credentials, else auto-fallback to a local **MinIO** container (same S3 API) — make this switch config-driven, not hardcoded.
- Signed URL generation with an expiry (e.g., 15 minutes).
- S3 lifecycle rule (documented in `docs/ARCHITECTURE.md` if not automatable via free tier — note as manual console step).
- `db/mongo.py`: mirror every `Operation` write into a MongoDB collection (Atlas free-tier replica set if configured, else local replica set via docker-compose) — this is the "distributed audit trail." Document clearly in code comments *why* both DBs exist (Postgres = relational integrity for auth/ops; Mongo = distributed, schema-flexible audit mirror).

**Tests:**
- Upload/download round trip against MinIO in CI (docker-compose service).
- Confirm audit entry appears in both Postgres and Mongo after an `/encode` call.

### Phase 4 — Scalability & Reliability
**Build:**
- `Dockerfile` for backend (multi-stage build, non-root user).
- `infra/docker-compose.yml`: 3 backend replicas, Nginx LB in front (round-robin, `least_conn` optional), Postgres, Redis, MinIO, Mongo, Prometheus, Grafana — one command (`docker compose up`) brings up the whole stack.
- `infra/nginx/nginx.conf`: passive health checks against `/health`; document how to demonstrate failover (`docker stop <container>` mid-load-test, show requests keep succeeding via the other replicas).
- Document (in `docs/ARCHITECTURE.md`) the cloud-equivalent path: AWS ALB + Auto Scaling Group, or k3s/minikube Deployment+Service+liveness/readiness probes — implement the k3s/minikube variant only if time permits, otherwise leave as a documented stretch goal, clearly marked as **not yet implemented** (do not claim it's done if it isn't).

**Tests/Demo script:**
- A `scripts/demo_failover.sh` that starts the stack, fires continuous requests (curl loop or Locust), kills one replica, and shows the response stream uninterrupted.

### Phase 5 — Observability & CI/CD
**Build:**
- `monitoring/metrics.py`: expose `/metrics` (Prometheus format) — request count, latency histogram, error count, labeled by endpoint and mode.
- `infra/prometheus/prometheus.yml` scraping all 3 backend replicas; a Grafana dashboard JSON (import-ready) showing request rate, p95 latency, error rate.
- Structured JSON logging (use `structlog` or stdlib `logging` with a JSON formatter) on every request — include request_id, user_id (if authenticated), endpoint, status, latency_ms. Never log plaintext message content or passwords.
- `.github/workflows/ci.yml`: on every push — install deps, run `pytest` (backend), run frontend build/lint, build Docker image (don't need to push anywhere unless a registry is configured).
- `loadtest/locustfile.py`: simulate encode/decode traffic; capture before/after latency with 1 replica vs 3 replicas behind the LB, save results to `docs/LOAD_TEST_RESULTS.md`.

### Phase 6 — Frontend
**Build:**
- React app (Vite): `EncodeTab`, `DecodeTab`, `ModeToggle` (Password vs Send-to-User), `Uploader` (drag-and-drop, shared between tabs).
- Encode tab: image upload, message/file input, mode toggle → password field or recipient search/dropdown, submit → shows signed download link.
- Decode tab: stego image upload, mode auto-detected from a small unencrypted flag or manual toggle, password field (Mode A) or nothing extra needed (Mode B, identity via JWT), submit → shows decrypted message/file or a clear, generic error.
- Basic auth screens: register/login, store JWT in memory (not localStorage — note why: XSS risk; use an httpOnly cookie or in-memory store).
- Optional: a histogram/diff view (canvas or a small Python endpoint returning a matplotlib PNG) comparing original vs. stego image to visually demonstrate imperceptibility.

---

## 5. Non-negotiable Security/Design Rules (apply throughout, all phases)

1. Never log plaintext messages, passwords, or private keys — anywhere, including debug logs.
2. Always verify integrity (HMAC or AES-GCM tag) **before** returning any decrypted content or a "success" response.
3. Wrong-password and unauthorized-recipient errors must return **the same generic message** to the caller so no information is leaked about *why* decoding failed.
4. Rate limit `/decode` more strictly than `/encode`.
5. Never store raw private keys in plaintext at rest; if server-side custody is used at all, encrypt them with a key derived from the user's own credentials, and document this trade-off clearly rather than presenting it as fully zero-knowledge.
6. Keep the LSB embedding/extraction logic mode-agnostic — it must not know or care whether it's embedding a Mode A or Mode B payload; only the payload bytes and a 1-byte mode flag differ.
7. Do not claim a feature as complete in `docs/` or `README.md` unless it has passing tests demonstrating it.

---

## 6. Definition of Done (overall)

- `docker compose up` in `infra/` brings up the entire stack (3 API replicas + Nginx LB + Postgres + Redis + MinIO + Mongo + Prometheus + Grafana) with one command.
- Both encode modes and both decode modes work end-to-end through the React frontend.
- Full pytest suite passes (crypto, stego, API, auth).
- CI pipeline runs green on GitHub Actions for a fresh push.
- `docs/ARCHITECTURE.md` and `docs/LOAD_TEST_RESULTS.md` exist and accurately reflect what was actually built (not aspirational).
- A `demo_failover.sh` script can visibly demonstrate one replica dying without dropping requests.

---

## 7. Final Instruction to the Agent

Proceed autonomously through Phases 1–6 in order. After finishing all phases, produce a top-level `README.md` with: project summary, architecture diagram (ASCII is fine), setup instructions (`docker compose up`), how to run tests, how to run the load test/failover demo, and a short "known limitations / stretch goals not implemented" section listing anything from this spec that was stubbed or skipped, so the user can speak accurately about the project's actual state in an interview.
