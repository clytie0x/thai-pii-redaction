#!/usr/bin/env bash
set -Eeuo pipefail

# Restore the exact image/Compose set that deploy_production.sh retained before
# mutation. This is called automatically when the separate acceptance job
# fails, so a red release is not left serving as the current candidate.
TEAM="${TEAM:?TEAM is required}"
CI_COMMIT_SHA="${CI_COMMIT_SHA:?CI_COMMIT_SHA is required}"
PROJECT_DIR="${CI_PROJECT_DIR:-$(pwd)}"
ENV_FILE="$(mktemp)"
OLD_COMPOSE="$(mktemp)"

cleanup() { rm -f "$ENV_FILE" "$OLD_COMPOSE"; }
trap cleanup EXIT

wait_healthy() {
  local expected="$1" service status revision attempt all_healthy
  for attempt in $(seq 1 40); do
    all_healthy=1
    for service in core api web; do
      status="$(docker inspect -f '{{.State.Health.Status}}' "${TEAM}-${service}-1" 2>/dev/null || echo none)"
      revision="$(docker inspect -f '{{ index .Config.Labels "org.opencontainers.image.revision" }}' "${TEAM}-${service}-1" 2>/dev/null || true)"
      [[ "$status" == healthy && "$revision" == "$expected" ]] || all_healthy=0
    done
    [[ "$all_healthy" == 1 ]] && return 0
    sleep 5
  done
  return 1
}

current="$(docker inspect -f '{{ index .Config.Labels "org.opencontainers.image.revision" }}' "${TEAM}-core-1")"
[[ "$current" == "$CI_COMMIT_SHA" ]] || {
  echo "refusing rollback: running revision is not the failed candidate"
  exit 1
}

old_revision=""
for service in core api web; do
  candidate="$(docker image inspect -f '{{ index .Config.Labels "org.opencontainers.image.revision" }}' "${TEAM}-rollback-${service}:previous")"
  [[ "$candidate" =~ ^[0-9a-f]{40}$ ]] || { echo "rollback image revision invalid"; exit 1; }
  [[ -z "$old_revision" || "$candidate" == "$old_revision" ]] || { echo "rollback image revisions disagree"; exit 1; }
  old_revision="$candidate"
done
[[ "$old_revision" != "$CI_COMMIT_SHA" ]] || { echo "rollback revision equals failed candidate"; exit 1; }
git cat-file -e "${old_revision}^{commit}"
git show "${old_revision}:docker-compose.yml" > "$OLD_COMPOSE"

umask 077
{
  printf 'APP_AIGUARD_API_KEY=%s\n' "${APP_AIGUARD_API_KEY:-}"
  printf 'APP_AIFT_ACCESS_CODE=%s\n' "${APP_AIFT_ACCESS_CODE:-}"
  printf 'APP_AIFT_COOKIE_SIGNING_KEY=%s\n' "${APP_AIFT_COOKIE_SIGNING_KEY:-}"
  printf 'APP_TOKENMIND_API_KEY=%s\n' "${APP_TOKENMIND_API_KEY:-}"
} > "$ENV_FILE"

for service in core api web; do
  docker image tag "${TEAM}-rollback-${service}:previous" "${TEAM}-${service}:latest"
done
docker compose \
  --project-directory "$PROJECT_DIR" \
  -f "$OLD_COMPOSE" \
  --env-file "$ENV_FILE" \
  -p "$TEAM" \
  up -d --no-build --remove-orphans
wait_healthy "$old_revision"
echo "failed candidate removed; previous exact revision restored and healthy: $old_revision"
