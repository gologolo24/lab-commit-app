# syntax=docker/dockerfile:1.7
# lab-commit backend. Build for Fargate (x86 only):
#   docker build --platform linux/amd64 --build-arg APP_VERSION=$(cat VERSION) -t backend .
# Tests and lint run as their own stage (CI and local):
#   docker build --target test .

# Docker Official Image, pulled from its ECR Public mirror (same digest as Docker Hub,
# no Docker Hub pull limits in CodeBuild).
FROM public.ecr.aws/docker/library/python:3.13-slim@sha256:27b7c9d4f13ca20bb1170148f02095d50a5dfce1f7f2dabf5ca273727e43b7ea AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_ROOT_USER_ACTION=ignore
WORKDIR /app

FROM base AS deps
COPY requirements.txt .
RUN pip install --prefix=/install -r requirements.txt

FROM base AS test
COPY --from=deps /install /usr/local
COPY requirements-dev.txt .
RUN pip install -r requirements-dev.txt
COPY . .
RUN ruff check . && ruff format --check . && pytest -q

FROM base AS runtime
ARG APP_VERSION=0.0.0
ENV APP_VERSION=${APP_VERSION}
COPY --from=deps /install /usr/local
# RDS CA bundle for TLS verification (sslmode=verify-full); the checksum is pinned.
# The folder is created first: ADD --chmod would also give a folder it creates
# mode 0644, and the app user could not open files in it.
RUN mkdir -m 0755 /app/certs
ADD --checksum=sha256:90a6f1a7978a1b1b096dca6c57511ca48d3b8cf052f8e704baf358f34ea2f21b --chmod=0644 \
    https://truststore.pki.rds.amazonaws.com/global/global-bundle.pem /app/certs/rds-global-bundle.pem
COPY app ./app
RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin app
USER 10001
# Fail the build if the app user cannot load the CA bundle.
RUN python -c "import ssl; ssl.create_default_context(cafile='/app/certs/rds-global-bundle.pem')"
EXPOSE 8080
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--no-server-header", "--no-access-log"]
