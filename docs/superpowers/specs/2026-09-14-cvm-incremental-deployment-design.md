# CVM Incremental Deployment Design

## Goal

Add a `main -> GitHub Actions -> CVM` incremental deployment path. Ordinary backend Python code, database migrations, and frontend build output are synchronized with `rsync` into fixed CVM runtime directories. The existing immutable GHCR images remain the runtime base. Dependency, Dockerfile, Nginx, or base-runtime changes continue to use the full image release path.

## Constraints

- Production Compose uses immutable `MOWAYS_IMAGE_TAG` images.
- Backend application code is at `/app/app`; migrations are at `/app/migrations`; frontend files are at `/usr/share/nginx/html`.
- The CVM deployment root is `/opt/mowayspos` and the production environment file is `/opt/mowayspos/production.env`.
- Production credentials stay outside Git. The Action receives the CVM host, user, private key, and known-hosts data through GitHub Secrets.
- This change adds only focused deployment-contract checks; it does not expand the existing full test suite.

## Design

### GitHub Actions entry point

The new manual `cloud-cvm-incremental-deploy.yml` workflow runs only from `main` and accepts `component` (`backend`, `frontend`, or `all`), an optional `base_sha`, and `run_migrations`.

Before synchronization it rejects changes to dependency files, Dockerfiles, `nginx.conf`, the production Compose file, or the production environment template. Frontend deployment runs `npm ci` and `npm run build`, then uploads only `frontend/dist`. Backend deployment uploads `bowei_ai_dashboard/app` and `bowei_ai_dashboard/migrations`.

### Compose override

The new `docker-compose.prod.incremental.yml` adds read-only mounts for backend application code, backend migrations, and frontend static output. It preserves the existing attachment mounts and does not change images, ports, networks, or database volumes.

### Remote activation and rollback

The Action stages files under `/opt/mowayspos/runtime/staging/<commit-sha>`. The remote script backs up active directories, synchronizes staged files with `rsync --delete`, validates Compose, optionally runs Alembic, recreates only affected application containers with `--no-build --no-deps`, and checks container health plus `/api/health`. A failed activation restores the saved directories and restarts the affected services. Five backups are retained.

## Security

The workflow uses `CVM_HOST`, `CVM_USER`, `CVM_SSH_KEY`, and `CVM_KNOWN_HOSTS`. SSH uses strict known-host verification and never runs `ssh-keyscan`. The workflow does not build, pull, or log in to a registry.

## Verification

Local verification is limited to Bash syntax, the focused Python contract test, and `git diff --check`. Runtime verification is performed by the Action through Compose configuration, container health, and the loopback health endpoint.
