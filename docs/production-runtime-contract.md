# Moways-SOP production runtime contract

The production stack is intentionally isolated from every other Docker project on the host:

```text
public 80/443 -> host Nginx -> pos.moways.com.cn
              -> 127.0.0.1:18100 -> frontend:80
              -> backend:8008 -> postgres:5432
```

Only the frontend publishes a host port. PostgreSQL and the backend are reachable only on the dedicated `mowayspos_app` bridge network. This repository does not define the host Nginx virtual host or TLS certificate workflow.

## First deployment

Create the host directories and the production environment file before starting the stack:

```bash
sudo install -d -m 700 /data/mowayspos/postgres /data/mowayspos/env
sudo cp .env.production.example /data/mowayspos/env/production.env
sudo chmod 600 /data/mowayspos/env/production.env
```

Edit `/data/mowayspos/env/production.env` before use. `DB_PASSWORD` must contain URL-safe characters and must match the password embedded in `DATABASE_URL`. Replace `MOWAYS_IMAGE_TAG` with the deployed Git commit SHA. Never commit the populated file.

Set `AI_CAPABILITY_CENTER_MODE=database` and generate a Fernet-compatible
`AI_CONFIG_ENCRYPTION_KEY` before the first start. Model credentials are
encrypted in PostgreSQL; neither API keys nor the legacy JSON file are mounted
into the production container. To import an existing legacy configuration, run
the one-time administrator migration after the database schema is at head.

## Validate and start

Run Compose with the production environment file so interpolation and the backend `env_file` use the same source:

```bash
docker compose --env-file /data/mowayspos/env/production.env \
  -f docker-compose.prod.yml config --quiet

docker compose --env-file /data/mowayspos/env/production.env \
  -f docker-compose.prod.yml build backend frontend

docker compose --env-file /data/mowayspos/env/production.env \
  -f docker-compose.prod.yml up -d postgres

docker compose --env-file /data/mowayspos/env/production.env \
  -f docker-compose.prod.yml run --rm backend alembic upgrade head

docker compose --env-file /data/mowayspos/env/production.env \
  -f docker-compose.prod.yml up -d backend frontend
```

Verify both frontend and proxied backend health through the loopback listener:

```bash
curl --fail http://127.0.0.1:18100/
curl --fail http://127.0.0.1:18100/api/health
```

The health response must report `status=ok`, `database=ok`, and `env=production`. The host Nginx should proxy `pos.moways.com.cn` to `127.0.0.1:18100` and preserve `X-Forwarded-Proto`; configuring that host proxy and Certbot remains a separate infrastructure step.
