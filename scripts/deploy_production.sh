#!/usr/bin/env bash
set -Eeuo pipefail

# Exact-stack deployment with one recoverable previous image set.  This script
# is CI-only: application secrets arrive through inherited protected variables,
# are materialized to one mode-600 temporary file, and are never printed.

TEAM="${TEAM:?TEAM is required}"
CI_COMMIT_SHA="${CI_COMMIT_SHA:?CI_COMMIT_SHA is required}"
PROJECT_DIR="${CI_PROJECT_DIR:-$(pwd)}"
ENV_FILE="$(mktemp)"
OLD_COMPOSE="$(mktemp)"
ROLLBACK_READY=0
MUTATION_STARTED=0
OLD_REVISION=""

require_latest_main() {
  if [[ -n "${CI_SERVER_HOST:-}" ]]; then
    local latest
    latest="$(git ls-remote origin refs/heads/main | awk '{print $1}')"
    [[ -n "$latest" && "$latest" == "$CI_COMMIT_SHA" ]] || {
      echo "refusing an outdated main deployment"
      return 1
    }
  fi
}

wait_healthy() {
  local expected_revision="$1" service status revision attempt all_healthy
  for attempt in $(seq 1 40); do
    all_healthy=1
    for service in core api web; do
      status="$(docker inspect -f '{{.State.Health.Status}}' "${TEAM}-${service}-1" 2>/dev/null || echo none)"
      revision="$(docker inspect -f '{{ index .Config.Labels "org.opencontainers.image.revision" }}' "${TEAM}-${service}-1" 2>/dev/null || true)"
      if [[ "$status" != healthy || "$revision" != "$expected_revision" ]]; then
        all_healthy=0
      fi
    done
    [[ "$all_healthy" == 1 ]] && return 0
    sleep 5
  done
  echo "stack did not become healthy at the expected revision"
  return 1
}

snapshot_previous() {
  local service revision image_id
  for service in core api web; do
    docker inspect "${TEAM}-${service}-1" >/dev/null 2>&1 || return 0
  done
  OLD_REVISION="$(docker inspect -f '{{ index .Config.Labels "org.opencontainers.image.revision" }}' "${TEAM}-core-1")"
  [[ "$OLD_REVISION" =~ ^[0-9a-f]{40}$ ]] || return 0
  for service in core api web; do
    revision="$(docker inspect -f '{{ index .Config.Labels "org.opencontainers.image.revision" }}' "${TEAM}-${service}-1")"
    [[ "$revision" == "$OLD_REVISION" ]] || return 0
  done
  git cat-file -e "${OLD_REVISION}^{commit}" 2>/dev/null || return 0
  git show "${OLD_REVISION}:docker-compose.yml" > "$OLD_COMPOSE"
  for service in core api web; do
    image_id="$(docker inspect -f '{{.Image}}' "${TEAM}-${service}-1")"
    docker image tag "$image_id" "${TEAM}-rollback-${service}:previous"
  done
  ROLLBACK_READY=1
  echo "recoverable previous revision prepared: $OLD_REVISION"
}

rollback_previous() {
  [[ "$ROLLBACK_READY" == 1 ]] || {
    echo "automatic rollback unavailable: no complete previous exact-revision stack"
    return 1
  }
  echo "candidate gate failed; restoring previous exact revision"
  local service
  for service in core api web; do
    docker image tag "${TEAM}-rollback-${service}:previous" "${TEAM}-${service}:latest"
  done
  docker compose \
    --project-directory "$PROJECT_DIR" \
    -f "$OLD_COMPOSE" \
    --env-file "$ENV_FILE" \
    -p "$TEAM" \
    up -d --no-build --remove-orphans
  wait_healthy "$OLD_REVISION"
  echo "previous revision restored and healthy: $OLD_REVISION"
}

cleanup() {
  local code=$?
  set +e
  if [[ "$code" -ne 0 && "$MUTATION_STARTED" == 1 ]]; then
    rollback_previous || echo "automatic rollback failed; platform intervention required"
  fi
  rm -f "$ENV_FILE" "$OLD_COMPOSE"
  exit "$code"
}
trap cleanup EXIT

require_latest_main
umask 077
{
  printf 'APP_AIGUARD_API_KEY=%s\n' "${APP_AIGUARD_API_KEY:-}"
  printf 'APP_AIFT_ACCESS_CODE=%s\n' "${APP_AIFT_ACCESS_CODE:-}"
  printf 'APP_AIFT_COOKIE_SIGNING_KEY=%s\n' "${APP_AIFT_COOKIE_SIGNING_KEY:-}"
  printf 'APP_TOKENMIND_API_KEY=%s\n' "${APP_TOKENMIND_API_KEY:-}"
} > "$ENV_FILE"

snapshot_previous
# This helper is authorized only for an existing production stack. Never
# replace it unless the exact prior source and all three image IDs are already
# recoverable.
[[ "$ROLLBACK_READY" == 1 ]] || {
  echo "refusing production mutation without a recoverable exact prior stack"
  exit 1
}
docker compose --env-file "$ENV_FILE" -p "$TEAM" build
require_latest_main
MUTATION_STARTED=1
docker compose --env-file "$ENV_FILE" -p "$TEAM" up -d --no-build --remove-orphans
wait_healthy "$CI_COMMIT_SHA"
require_latest_main

# Runner Docker-executor loopback is not the daemon host.  Probe inside the
# exact healthy containers without placing cookies, credentials or bodies in
# argv/logs.
docker exec "${TEAM}-api-1" wget -q -O /dev/null http://127.0.0.1:8000/health
docker exec "${TEAM}-web-1" wget -q -O /dev/null http://127.0.0.1:3000/
docker compose -p "$TEAM" ps
echo "candidate revision deployed and healthy: $CI_COMMIT_SHA"
