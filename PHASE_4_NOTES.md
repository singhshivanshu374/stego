# Phase 4 — Scalability & Reliability

## What Was Built

### `backend/Dockerfile` — Multi-Stage Build
- **Stage 1 (builder)**: Installs Python dependencies in a fat image.
- **Stage 2 (runtime)**: Copies only installed packages + app code into `python:3.13-slim`.
- **Non-root user**: App runs as `securestego` user (not root).
- **Health check**: Built-in `HEALTHCHECK` hitting `/health` every 15s.
- **OpenCV deps**: `libgl1` and `libglib2.0-0` for `opencv-python` runtime support.

### `infra/docker-compose.yml` — Full Stack
One command (`docker compose up`) brings up **10 services**:

| Service | Image | Port | Purpose |
|---------|-------|------|---------|
| api-1 | securestego (built) | internal | Backend replica 1 |
| api-2 | securestego (built) | internal | Backend replica 2 |
| api-3 | securestego (built) | internal | Backend replica 3 |
| nginx | nginx:1.27-alpine | **80** | Load balancer (public entry point) |
| postgres | postgres:16-alpine | 5432 | Primary database |
| redis | redis:7-alpine | 6379 | Rate limiting cache |
| minio | minio/minio:latest | 9000, 9001 | S3-compatible object storage |
| mongo | mongo:7 | 27017 | Audit trail database |
| prometheus | prom/prometheus | 9090 | Metrics collection |
| grafana | grafana/grafana | **3000** | Dashboards |

- YAML anchors (`&api-env` / `*api-env`) keep the 3 API replicas' env in sync.
- Health checks on Postgres and Redis — API replicas wait for them before starting.
- Named volumes for all stateful data.
- Single bridge network (`securestego-net`).

### `infra/nginx/nginx.conf` — Load Balancer
- **Round-robin** across 3 API replicas (default; `least_conn` commented as alternative).
- **Passive health checks**: `max_fails=3 fail_timeout=30s` — if a backend fails 3 times, it's removed from rotation for 30 seconds.
- **Automatic retry**: `proxy_next_upstream error timeout http_502 http_503 http_504` — on error, Nginx retries the next available backend.
- 50MB client upload limit for image files.

### `infra/prometheus/prometheus.yml`
- Scrapes `/metrics` from all 3 API replicas every 15 seconds.
- Self-monitoring target for Prometheus itself.

### `scripts/demo_failover.sh` — Failover Demonstration
Automated script that:
1. Starts the full stack
2. Fires health check requests (all 3 replicas active)
3. Kills `api-2`
4. Fires more requests — shows they continue succeeding via api-1 and api-3
5. Restarts api-2
6. Prints success/failure summary

### Cloud-Equivalent Path (documented in ARCHITECTURE.md)
| Local | Cloud (AWS) |
|-------|-------------|
| Nginx | AWS ALB + Auto Scaling Group |
| 3 Docker containers | ECS Fargate or EC2 + ASG |
| Postgres container | RDS PostgreSQL |
| Redis container | ElastiCache Redis |
| MinIO | S3 |
| MongoDB container | MongoDB Atlas |
| Prometheus + Grafana | CloudWatch + Grafana Cloud |

Kubernetes (k3s/minikube) variant is noted as a stretch goal — **not yet implemented**.

## How to Run

```bash
# Start the full stack
cd infra
docker compose up -d --build

# Verify all services are up
docker compose ps

# Access points:
#   API (via LB):     http://localhost
#   MinIO Console:    http://localhost:9001
#   Prometheus:       http://localhost:9090
#   Grafana:          http://localhost:3000 (admin/admin)

# Run failover demo
cd ..
bash scripts/demo_failover.sh

# Tear down
cd infra
docker compose down -v
```
