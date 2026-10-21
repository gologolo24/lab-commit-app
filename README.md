# lab-commit-app

Application source code for the **AWS Lab – EKS Scaling & Pipeline** assignment (Commit).

> 🚧 Work in progress. The review guide lives in [lab-commit-infra](https://github.com/gologolo24/lab-commit-infra).

## Services

| Service | What it does |
|---|---|
| `frontend/` | FastAPI app. Polls the backend every 5 seconds and serves `Hello Lab-Commit v<version>` with the value from the database over HTTPS (through the internal ALB). |
| `backend/` | FastAPI app. Runs a `SELECT` query on RDS PostgreSQL (IAM database authentication, TLS). Not exposed outside the cluster. |

Each service has its own `Dockerfile`, `VERSION` file, tests and `buildspec.yml`.
A push to `main` that changes `frontend/**` (or `backend/**`) triggers its CodePipeline. The pipeline builds the image, pushes it to ECR and updates the image tag in [lab-commit-gitops](https://github.com/gologolo24/lab-commit-gitops), and Argo CD then deploys it.

## Related repositories

- [lab-commit-infra](https://github.com/gologolo24/lab-commit-infra): Terraform and the review guide
- [lab-commit-gitops](https://github.com/gologolo24/lab-commit-gitops): Helm charts and Argo CD applications
