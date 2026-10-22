# lab-commit-app

Application source code for the **AWS Lab – EKS Scaling & Pipeline** assignment (Commit).

> The review guide lives in [lab-commit-infra](https://github.com/gologolo24/lab-commit-infra).

```
Chrome (Windows client) --HTTPS--> internal ALB --> frontend --every 5 s--> backend --SELECT--> RDS PostgreSQL
                                   "Hello Lab-Commit v1.0.0, value from the database: 5"
```

## Services

| Service | What it does | Endpoints |
|---|---|---|
| `frontend/` | Polls the backend **every 5 seconds** (`POLL_INTERVAL_SECONDS`) and serves **"Hello Lab-Commit v&lt;version&gt;"** plus the database value. The open page refreshes itself. If the backend is down it keeps the last value and says so. | `/` page, `/api/message`, `/version`, `/healthz`, `/readyz`, `/metrics` |
| `backend/` | Runs `SELECT value, updated_at FROM lab_values ORDER BY id DESC LIMIT 1` on RDS. Inside the cluster only (no Ingress). | `/api/value`, `/healthz`, `/readyz` (checks the DB), `/metrics` |
| `backend` → `python -m app.migrate` | One-time, idempotent DB setup run as a Kubernetes Job before each deploy: table `lab_values`, seed value `5`, read-only user `app_reader` | – |
| `backend` → `python -m app.set_value <n>` | Demo/admin command: inserts a new value (the page shows it within 5 s). Run as a one-off Job by `scripts/set-db-value.sh` in the infra repo, with the migration job's identity | – |

## Security
- **No database password in the app.** The backend logs in as `app_reader` with a **15-minute IAM auth token** (IRSA role allowed only `rds-db:connect` for that user). `app_reader` may only `SELECT` from `lab_values`.
- **Verified TLS to RDS** (`sslmode=verify-full`, RDS CA bundle baked into the image, checksum pinned).
- The migration job reads the RDS-managed master password from Secrets Manager at run time (its own IRSA role, that one secret only).
- Images: pinned base image digest, non-root user `10001`, no shell login, no build tools at runtime.
- Frontend: strict Content-Security-Policy (no inline scripts), `X-Frame-Options: DENY`, no `Server` header, all HTML values escaped.

## Autoscaling metric
`http_requests_total{handler="/"}` counts **page loads only** (not `/api/message`, health checks or `/metrics`). KEDA scales the frontend on its per-second rate: **10 req/s per pod, 1 to 4 pods**.

## Build and test
```bash
docker build --target test backend      # ruff (lint + format) + pytest
docker build --target test frontend
docker build --platform linux/amd64 --build-arg APP_VERSION=$(cat frontend/VERSION) -t frontend frontend
```
Fargate runs **x86 only**: always build `linux/amd64` (Apple-silicon Macs default to arm64).

## Releases
Each service's version is in its `VERSION` file. A push to `main` that changes `frontend/**` (or `backend/**`) triggers its CodePipeline, which builds the image, tags it with that version in ECR, and updates the image tag in [lab-commit-gitops](https://github.com/gologolo24/lab-commit-gitops). Argo CD then deploys it.

## Related repositories
- [lab-commit-infra](https://github.com/gologolo24/lab-commit-infra): Terraform and the review guide
- [lab-commit-gitops](https://github.com/gologolo24/lab-commit-gitops): Helm charts and Argo CD applications
