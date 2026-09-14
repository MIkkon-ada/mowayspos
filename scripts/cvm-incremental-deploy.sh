#!/usr/bin/env bash
set -Eeuo pipefail

: "${RELEASE_SHA:?RELEASE_SHA is required}"
: "${COMPONENT:?COMPONENT is required}"
: "${RUN_MIGRATIONS:=false}"
: "${STAGING_ROOT:?STAGING_ROOT is required}"

COMPOSE_ROOT="${COMPOSE_ROOT:-/opt/mowayspos}"
RUNTIME_ROOT="${RUNTIME_ROOT:-/opt/mowayspos/runtime}"

[[ "$RELEASE_SHA" =~ ^[0-9a-f]{40}$ ]]
[[ "$COMPOSE_ROOT" == "/opt/mowayspos" ]]
[[ "$RUNTIME_ROOT" == "/opt/mowayspos/runtime" ]]
[[ "$STAGING_ROOT" == "$RUNTIME_ROOT/staging/"* ]]

case "$COMPONENT" in
  backend|frontend|all) ;;
  *)
    echo "Unsupported component: $COMPONENT" >&2
    exit 2
    ;;
esac

command -v docker >/dev/null
command -v rsync >/dev/null
command -v curl >/dev/null
test -f "$COMPOSE_ROOT/production.env"
test -f "$COMPOSE_ROOT/docker-compose.prod.yml"
test -f "$COMPOSE_ROOT/docker-compose.prod.incremental.yml"

export MOWAYS_RUNTIME_ROOT="$RUNTIME_ROOT"
compose=(
  docker compose
  --env-file "$COMPOSE_ROOT/production.env"
  -f "$COMPOSE_ROOT/docker-compose.prod.yml"
  -f "$COMPOSE_ROOT/docker-compose.prod.incremental.yml"
)

active_backend_app="$RUNTIME_ROOT/backend/app"
active_backend_migrations="$RUNTIME_ROOT/backend/migrations"
active_frontend_dist="$RUNTIME_ROOT/frontend-dist"
mkdir -p "$active_backend_app" "$active_backend_migrations" "$active_frontend_dist"

timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
backup_root="$RUNTIME_ROOT/backups/${RELEASE_SHA}-${timestamp}"
mkdir -p "$RUNTIME_ROOT/backups" "$backup_root"

backup_tree() {
  local source="$1"
  local destination="$2"
  mkdir -p "$destination"
  if [[ -d "$source" ]]; then
    rsync -aH --delete "$source/" "$destination/"
  fi
}

activate_tree() {
  local source="$1"
  local destination="$2"
  test -d "$source"
  mkdir -p "$destination"
  rsync -aH --delete "$source/" "$destination/"
}

restore_tree() {
  local source="$1"
  local destination="$2"
  mkdir -p "$destination"
  if [[ -d "$source" ]]; then
    rsync -aH --delete "$source/" "$destination/"
  else
    find "$destination" -mindepth 1 -maxdepth 1 -exec rm -rf -- {} +
  fi
}

restore_on_failure() {
  local status="$1"
  set +e
  if [[ "$status" != "0" && "$backup_ready" == "1" ]]; then
    restore_tree "$backup_root/backend-app" "$active_backend_app"
    restore_tree "$backup_root/backend-migrations" "$active_backend_migrations"
    restore_tree "$backup_root/frontend-dist" "$active_frontend_dist"
    for service in "${services[@]}"; do
      "${compose[@]}" up -d --no-build --no-deps --force-recreate "$service" >/tmp/mowayspos-incremental-rollback.log 2>&1 || true
    done
    echo "Incremental deployment failed; restored backup $backup_root" >&2
  fi
  exit "$status"
}

wait_healthy() {
  local service="$1"
  local container="mowayspos-$service"
  for attempt in $(seq 1 60); do
    status="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$container" 2>/dev/null || true)"
    if [[ "$status" == "healthy" ]]; then
      return 0
    fi
    if [[ "$status" == "exited" || "$status" == "dead" ]]; then
      docker logs --tail 100 "$container" >&2 || true
      return 1
    fi
    sleep 2
  done
  docker logs --tail 100 "$container" >&2 || true
  return 1
}

services=()
backup_ready=0
trap 'restore_on_failure "$?"' EXIT
case "$COMPONENT" in
  backend)
    services=(backend)
    backup_tree "$active_backend_app" "$backup_root/backend-app"
    backup_tree "$active_backend_migrations" "$backup_root/backend-migrations"
    backup_ready=1
    activate_tree "$STAGING_ROOT/backend/app" "$active_backend_app"
    activate_tree "$STAGING_ROOT/backend/migrations" "$active_backend_migrations"
    ;;
  frontend)
    services=(frontend)
    backup_tree "$active_frontend_dist" "$backup_root/frontend-dist"
    backup_ready=1
    activate_tree "$STAGING_ROOT/frontend/dist" "$active_frontend_dist"
    ;;
  all)
    services=(backend frontend)
    backup_tree "$active_backend_app" "$backup_root/backend-app"
    backup_tree "$active_backend_migrations" "$backup_root/backend-migrations"
    backup_tree "$active_frontend_dist" "$backup_root/frontend-dist"
    backup_ready=1
    activate_tree "$STAGING_ROOT/backend/app" "$active_backend_app"
    activate_tree "$STAGING_ROOT/backend/migrations" "$active_backend_migrations"
    activate_tree "$STAGING_ROOT/frontend/dist" "$active_frontend_dist"
    ;;
esac

"${compose[@]}" config --quiet

if [[ "$RUN_MIGRATIONS" == "true" && "$COMPONENT" != "frontend" ]]; then
  "${compose[@]}" run --rm --no-build --no-deps --pull never backend alembic upgrade head
fi

for service in "${services[@]}"; do
  "${compose[@]}" up -d --no-build --no-deps --force-recreate "$service"
done

for service in "${services[@]}"; do
  wait_healthy "$service"
done

curl --fail --silent --show-error http://127.0.0.1:18100/api/health >/dev/null
printf '%s\n' "$RELEASE_SHA" > "$RUNTIME_ROOT/.last-successful-release"

rm -rf -- "$STAGING_ROOT"
find "$RUNTIME_ROOT/backups" -mindepth 1 -maxdepth 1 -type d -printf '%T@ %p\n' |
  sort -rn |
  awk 'NR > 5 { sub(/^[^ ]+ /, ""); print }' |
  while IFS= read -r old_backup; do
    [[ "$old_backup" == "$RUNTIME_ROOT/backups/"* ]] || exit 1
    rm -rf -- "$old_backup"
  done

backup_ready=0
trap - EXIT
echo "incremental_deploy=ok release_sha=$RELEASE_SHA component=$COMPONENT"
