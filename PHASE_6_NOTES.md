# Phase 6: Frontend Integration & End-to-End Delivery

## Overview
Phase 6 completes the SecureStego platform by delivering a responsive, secure React SPA built with Vite and Tailwind CSS v4. The frontend fully integrates with the backend API, strictly enforcing all cryptographic workflows and constraints established in earlier phases.

## Key Features & Implementations
1. **Zero-Knowledge Architecture UI**:
   - The frontend auto-downloads the recipient's RSA `.pem` private key upon registration.
   - For Mode B decryption, the `.pem` file must be uploaded by the user. The backend refuses to decrypt without it, as the server does not store the private key.
2. **Dynamic Constraints**:
   - The `/encode` tab calculates exact byte capacity dynamically based on the uploaded image dimensions `(W * H * 3 / 8 - 5)`.
3. **Containerized Deployment**:
   - The frontend is built as a multi-stage Docker image, serving static assets via a lightweight Nginx container.
   - The main API Load Balancer (`infra/nginx/nginx.conf`) was updated to route `/auth`, `/encode`, `/decode`, `/operations`, `/storage`, `/health`, and `/metrics` to the backend cluster, and all other traffic to the frontend SPA.

## End-to-End Test Checklist
- [x] **Registration & Key Download**: Register a new user and confirm `private_key.pem` downloads instantly.
- [x] **Mode A (Password) Encode/Decode**: 
  - Encode a payload with a password.
  - Decode with correct password → success.
  - Decode with incorrect password → generic "Decoding failed." message (Rule 5.3).
- [x] **Mode B (User-Bound) Encode/Decode**:
  - Encode a payload specifying recipient B.
  - Recipient B decodes by uploading their `.pem` file → success.
  - Recipient A (or an attacker) tries to decode → generic error.
- [x] **Recent Activity**: The `GET /operations/recent` table successfully fetches the current user's history and displays success/error states.
- [x] **Docker Compose Full Stack**: `docker compose up` brings up 3 API replicas, 1 Frontend container, Nginx LB, Postgres, Redis, MinIO, Mongo, Prometheus, and Grafana. Nginx successfully routes traffic on port `80`.

## Instructions
1. Run `docker compose up --build -d` in the `infra/` folder.
2. Navigate to `http://localhost` to access the SecureStego SPA.
3. Access Prometheus metrics at `http://localhost:9090` and Grafana at `http://localhost:3000`.
