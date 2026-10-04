# SecureStego

SecureStego is a security-first, full-stack image steganography platform. It allows users to hide encrypted messages or files inside images using LSB (Least Significant Bit) steganography. 

The platform supports two secure authorization workflows:
- **Mode A (Password-based)**: AES-GCM encryption derived from a user-supplied password via PBKDF2.
- **Mode B (User-Bound Hybrid Crypto)**: A zero-knowledge architecture where payloads are encrypted with a random session key, which is itself encrypted using the recipient's RSA public key. The recipient decodes the payload locally by supplying their private `.pem` key. 

All operations are validated with HMAC integrity checks prior to decryption, guaranteeing tamper resistance.

## Architecture

```text
       [ Clients / Browsers ]
                 │ (React SPA)
                 ▼
       ┌─────────────────────┐
       │ Nginx Load Balancer │
       └────┬───────┬───────┬┘
            │       │       │
       ┌────▼┐ ┌────▼┐ ┌────▼┐
       │ API │ │ API │ │ API │ (FastAPI Replicas)
       └─┬─┬─┘ └─┬─┬─┘ └─┬─┬─┘
         │ │     │ │     │ │
   ┌─────┘ │     │ │     │ └─────┐
   ▼       ▼     ▼ ▼     ▼       ▼
┌──────┐ ┌──────┐ ┌────────┐ ┌───────┐
│ Redis│ │ MinIO│ │Postgres│ │MongoDB│
└──────┘ └──────┘ └────────┘ └───────┘
(Rate)   (S3)     (State)    (Audit)

           [ Monitoring ]
       Prometheus ──▶ Grafana
```

## Setup & Running the Stack

The entire architecture is containerized using Docker Compose.

1. Ensure Docker Desktop / Docker Engine is running on your machine.
2. From the root directory, navigate to the `infra` folder:
   ```bash
   cd infra
   docker compose up --build
   ```
3. Once running, access the platform via your browser:
   - **Frontend App**: `http://localhost`
   - **MinIO Console**: `http://localhost:9001` (u/p: minioadmin / minioadmin)
   - **Grafana Dashboards**: `http://localhost:3000` (u/p: admin / admin)

## Running the Tests

To run the full backend unit and integration test suite:

```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
python -m pytest tests/ -v
```

## Load Testing & Failover Demo

To simulate load traffic and demonstrate the high-availability failover capabilities of the Nginx Load Balancer:

1. Start the stack: `docker compose up -d` in the `infra/` folder.
2. In a new terminal, run the continuous health check script to observe traffic:
   ```bash
   while true; do curl -s http://localhost/nginx-health; sleep 0.5; done
   ```
3. In another terminal, run Locust to simulate heavy load against the APIs:
   ```bash
   cd loadtest
   pip install locust
   locust -f locustfile.py --host=http://localhost
   ```
4. Mid-load test, kill one of the API replicas:
   ```bash
   docker stop securestego-api-2
   ```
5. Observe the Locust test and health-check loops. You'll notice 0 dropped requests as Nginx seamlessly reroutes traffic to `api-1` and `api-3`.

## Known Limitations / Stretch Goals Not Implemented

As per the build specification, the core requirements have been met. The following stretch goals were stubbed out or left for future implementation:

1. **Cloud Deployments (K3s/Minikube)**: The architecture is fully prepared for a Kubernetes deployment (or AWS ALB + Auto Scaling Group), but only the Docker Compose orchestration was implemented for local testing.
2. **Client-Side Key Generation**: For Phase 2 simplicity, the RSA key pair is generated on the server during registration and returned once. In a true zero-knowledge environment, the keypair would be generated in the browser via the Web Crypto API, with only the public key sent to the backend.
3. **Automated S3 Lifecycle Rules**: The AWS S3 bucket lifecycle (purging images after 15 minutes) is documented as a manual AWS console step rather than being automated via `boto3` infrastructure-as-code scripts.
4. **Visual Histogram Diff**: The optional frontend visual UI to show a pixel histogram comparing the original and stego image (demonstrating imperceptibility) was not implemented.
