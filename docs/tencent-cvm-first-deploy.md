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
sudo install -d \
  -m 0750 \
  -o "$(id -un)" \
  -g "$(id -gn)" \
  /opt/mowayspos

install -m 0644 \
  docker-compose.prod.yml \
  /opt/mowayspos/docker-compose.prod.yml

cd /opt/mowayspos
```

Create the data directories with the same current-user ownership before any
Compose command, then initialize the bind-mounted LLM configuration as a
private regular file containing an empty JSON object:

```bash
sudo install -d \
  -m 0750 \
  -o "$(id -un)" \
  -g "$(id -gn)" \
  /data/mowayspos \
  /data/mowayspos/postgres \
  /data/mowayspos/env

install -m 0600 /dev/null \
  /data/mowayspos/env/llm_configs.json

printf '{}\n' > \
  /data/mowayspos/env/llm_configs.json

test -f /data/mowayspos/env/llm_configs.json
test ! -d /data/mowayspos/env/llm_configs.json
```

Create the deployment environment file with private permissions before editing
its real server values:

```bash
install -m 0600 /dev/null \
  /opt/mowayspos/production.env
```

The following template pins the validated release. Replace only the explicit
non-secret placeholders on the server. `DB_PASSWORD` must be a URL-safe,
random strong server password because Compose inserts DB_PASSWORD into the
backend DATABASE_URL.

```dotenv
RELEASE_SHA=4182c9746e498aebbbd9371fe7488d7dd71ae02f
MOWAYS_BACKEND_REPOSITORY=ghcr.io/mikkon-ada/mowayspos-backend
MOWAYS_FRONTEND_REPOSITORY=ghcr.io/mikkon-ada/mowayspos-frontend
MOWAYS_POSTGRES_IMAGE=ghcr.io/mikkon-ada/mowayspos-postgres:linux-amd64-sha256-7a396fd264a2067788b6551122b50f162bf6136312c7fc9d74381cb92c648382
MOWAYS_IMAGE_TAG=4182c9746e498aebbbd9371fe7488d7dd71ae02f
POSTGRES_DB=mowayspos
POSTGRES_USER=mowayspos
DB_PASSWORD=replace_with_url_safe_server_secret
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

Verify the exact GHCR remote manifest digest for every pulled image. The
PostgreSQL source manifest digest
`sha256:7a396fd264a2067788b6551122b50f162bf6136312c7fc9d74381cb92c648382`
is used only in the immutable tag and for source tracing. The expected GHCR
remote manifest is different and is checked explicitly below:

```bash
require_repo_digest() {
  image_ref="$1"
  expected_digest="$2"

  docker image inspect \
    --format '{{range .RepoDigests}}{{println .}}{{end}}' \
    "$image_ref" |
    awk -F@ -v expected="$expected_digest" '
      $2 == expected { found = 1 }
      END { exit(found ? 0 : 1) }
    '
}

require_repo_digest \
  ghcr.io/mikkon-ada/mowayspos-backend:4182c9746e498aebbbd9371fe7488d7dd71ae02f \
  sha256:7fa06bd6579c98b21cfbf949f773daede9df508edd177823ed70c77630e65aa5

require_repo_digest \
  ghcr.io/mikkon-ada/mowayspos-frontend:4182c9746e498aebbbd9371fe7488d7dd71ae02f \
  sha256:49b46fd61da49e047ee3427cd762ce101eb752241018b7ddf36cce446e87a76a

require_repo_digest \
  ghcr.io/mikkon-ada/mowayspos-postgres:linux-amd64-sha256-7a396fd264a2067788b6551122b50f162bf6136312c7fc9d74381cb92c648382 \
  sha256:428f48e250303765f62fdfcf2df623cb4f5bb27fafda6b26e9cb17e53bf8019b
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
