# Tencent CVM Incremental Deployment Runbook

This path is for ordinary application-code releases. GitHub Actions builds the frontend artifact from `main` and synchronizes selected files into `/opt/mowayspos/runtime` with SSH and rsync. The CVM continues to use the existing GHCR images as the Python, Alembic, Nginx, and system-dependency runtime base. The workflow does not run `docker build`, `docker pull`, or `docker login`.

## Scope

Use this path for:

- backend Python files under `bowei_ai_dashboard/app`;
- database migration files under `bowei_ai_dashboard/migrations`;
- frontend source and styles processed by `npm run build`.

Do not use it for dependency lockfiles, Dockerfiles, `nginx.conf`, `docker-compose.prod.yml`, or system-runtime changes. Use `cloud-p1b2b-a-ghcr-private-publish.yml` and the existing first-deployment runbook for those changes.

## One-time CVM preparation

The existing Moways stack must already be installed at `/opt/mowayspos`, and the deployment user must be able to write that directory:

```bash
sudo install -d -m 0750 -o "$(id -un)" -g "$(id -gn)" \
  /opt/mowayspos/runtime \
  /opt/mowayspos/runtime/backend \
  /opt/mowayspos/runtime/backend/app \
  /opt/mowayspos/runtime/backend/migrations \
  /opt/mowayspos/runtime/frontend-dist \
  /opt/mowayspos/runtime/backups
```

The Action uploads the incremental Compose override to `/opt/mowayspos/docker-compose.prod.incremental.yml` on every run. Do not put GitHub tokens, SSH private keys, or production environment files in Git.

## Required GitHub Secrets

- `CVM_HOST`: CVM hostname or IP;
- `CVM_USER`: Docker-capable deployment user, for example `ubuntu`;
- `CVM_SSH_KEY`: complete private key for that user;
- `CVM_KNOWN_HOSTS`: pre-verified SSH host key lines.

## Run an ordinary release

The target commit must already be on remote `main`. If the last successful release SHA is known, pass it as `base_sha`; otherwise the Action uses the current commit parent:

```bash
gh workflow run cloud-cvm-incremental-deploy.yml \
  --ref main \
  -f component=all \
  -f base_sha=LAST_SUCCESSFUL_SHA \
  -f run_migrations=false
```

Backend only:

```bash
gh workflow run cloud-cvm-incremental-deploy.yml \
  --ref main \
  -f component=backend \
  -f run_migrations=false
```

Frontend only:

```bash
gh workflow run cloud-cvm-incremental-deploy.yml \
  --ref main \
  -f component=frontend \
  -f run_migrations=false
```

If migration files changed, use `run_migrations=true` and include the backend:

```bash
gh workflow run cloud-cvm-incremental-deploy.yml \
  --ref main \
  -f component=backend \
  -f run_migrations=true
```

The Action stages files, backs up active directories, synchronizes only the selected runtime trees, and recreates only the affected application containers. On failure it restores the backup. On success it writes `/opt/mowayspos/runtime/.last-successful-release`.

Monitor the run:

```bash
gh run list --workflow cloud-cvm-incremental-deploy.yml --limit 5
gh run watch RUN_ID
```

## Post-release checks

```bash
docker compose \
  --env-file /opt/mowayspos/production.env \
  -f /opt/mowayspos/docker-compose.prod.yml \
  -f /opt/mowayspos/docker-compose.prod.incremental.yml \
  ps

curl --fail --silent --show-error http://127.0.0.1:18100/api/health
cat /opt/mowayspos/runtime/.last-successful-release
```

The incremental path does not modify PostgreSQL data, attachment data, the production environment file, or host Nginx. Its purpose is to deploy ordinary code changes without rebuilding the application images.
