# Tencent CVM first deployment from private GHCR images

This runbook starts only the isolated Moways Compose project from the three
images validated and published by GitHub Actions run `29687343105`. It does not
build images on the CVM and it does not alter any existing Docker project.

## 1. Create the server pull credential

Manually create a dedicated GitHub token for this server with only
`read:packages` access to the private packages. Do not put the token in the
deployment environment file, shell history, Git, logs, or this document.

Enter it interactively and pass it to Docker only through standard input:

```bash
read -s GHCR_READ_TOKEN
printf '%s' "$GHCR_READ_TOKEN" | docker login ghcr.io -u MIkkon-ada --password-stdin
unset GHCR_READ_TOKEN
```

## 2. Prepare the isolated deployment directory

Create the application directory without changing existing KAP, WeKnora, or
OnlyOffice directories, containers, networks, or configuration:

```bash
sudo install -d -m 0750 /opt/mowayspos
sudo install -m 0644 docker-compose.prod.yml /opt/mowayspos/docker-compose.prod.yml
cd /opt/mowayspos
```

Create `/opt/mowayspos/production.env` with mode `0600`. The following values
pin the validated release; replace only the explicit non-secret placeholders on
the server. `DB_PASSWORD` must be URL-safe and must match the password embedded
in `DATABASE_URL` inside the same file.

```dotenv
RELEASE_SHA=4182c9746e498aebbbd9371fe7488d7dd71ae02f
MOWAYS_BACKEND_REPOSITORY=ghcr.io/mikkon-ada/mowayspos-backend
MOWAYS_FRONTEND_REPOSITORY=ghcr.io/mikkon-ada/mowayspos-frontend
MOWAYS_POSTGRES_IMAGE=ghcr.io/mikkon-ada/mowayspos-postgres:linux-amd64-sha256-7a396fd264a2067788b6551122b50f162bf6136312c7fc9d74381cb92c648382
MOWAYS_IMAGE_TAG=4182c9746e498aebbbd9371fe7488d7dd71ae02f
POSTGRES_DB=mowayspos
POSTGRES_USER=mowayspos
DB_PASSWORD=replace_with_url_safe_server_secret
DATABASE_URL=postgresql+psycopg://mowayspos:replace_with_same_url_safe_server_secret@postgres:5432/mowayspos
MOWAYS_ENV_FILE=/opt/mowayspos/production.env
MOWAYS_DATA_ROOT=/data/mowayspos
SESSION_COOKIE_NAME=moways_session
```

Do not place the GHCR token in this file. Supply any production LLM API keys
only through the protected server environment file, never in the repository.

## 3. Validate and pull the immutable release

Every Compose invocation names both the deployment environment file and the
production Compose file explicitly:

```bash
docker compose --env-file /opt/mowayspos/production.env -f docker-compose.prod.yml config --quiet
docker compose --env-file /opt/mowayspos/production.env -f docker-compose.prod.yml pull
```

Verify that all three pulled images expose registry digests. The PostgreSQL
mirror must also resolve to the reviewed upstream content digest:

```bash
test -n "$(docker image inspect --format '{{join .RepoDigests ""}}' ghcr.io/mikkon-ada/mowayspos-backend:4182c9746e498aebbbd9371fe7488d7dd71ae02f)"
test -n "$(docker image inspect --format '{{join .RepoDigests ""}}' ghcr.io/mikkon-ada/mowayspos-frontend:4182c9746e498aebbbd9371fe7488d7dd71ae02f)"
docker image inspect --format '{{join .RepoDigests "\n"}}' ghcr.io/mikkon-ada/mowayspos-postgres:linux-amd64-sha256-7a396fd264a2067788b6551122b50f162bf6136312c7fc9d74381cb92c648382 | grep -F '@sha256:7a396fd264a2067788b6551122b50f162bf6136312c7fc9d74381cb92c648382'
```

Do not continue if any check fails.

## 4. Start without building

Start the pinned images exactly once, with Compose builds disabled:

```bash
docker compose --env-file /opt/mowayspos/production.env -f docker-compose.prod.yml up -d --no-build
docker compose --env-file /opt/mowayspos/production.env -f docker-compose.prod.yml ps
```

Wait until `mowayspos-postgres`, `mowayspos-backend`, and
`mowayspos-frontend` all report `healthy`. The backend and PostgreSQL services
must have no host port bindings. The frontend is the only host listener and is
limited to `127.0.0.1:18100`:

```bash
docker inspect --format '{{.Name}} {{if .State.Health}}{{.State.Health.Status}}{{end}} {{json .HostConfig.PortBindings}}' mowayspos-postgres mowayspos-backend mowayspos-frontend
```

## 5. Verify the loopback application

Verify the login page, the proxied health API, and the unauthenticated auth API
boundary from the host only:

```bash
curl --fail http://127.0.0.1:18100/
curl --fail http://127.0.0.1:18100/api/health
test "$(curl -sS -o /dev/null -w '%{http_code}' http://127.0.0.1:18100/api/auth/me)" = "401"
```

The health JSON must contain `status=ok`, `database=ok`, and `env=production`.

Stop here. Do not modify host Nginx. Do not modify DNS. Do not run Certbot.
Do not expose another host port, and do not change or restart KAP, WeKnora, or
OnlyOffice. Host proxying and HTTPS are separate, explicitly authorized tasks.
