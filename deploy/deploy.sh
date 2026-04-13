#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_ROOT="${DEPLOY_ROOT:-/opt/gpthub}"
COMPOSE_SRC="$SCRIPT_DIR/docker-compose.prod.yml"
COMPOSE_DST="$DEPLOY_ROOT/docker-compose.prod.yml"
ENV_SRC="$SCRIPT_DIR/.env.example"
ENV_DST="$DEPLOY_ROOT/.env"
VERSION="${1:-latest}"
PRUNE_IMAGES="${PRUNE_IMAGES:-true}"

mkdir -p "$DEPLOY_ROOT"
cp "$COMPOSE_SRC" "$COMPOSE_DST"

if [ ! -f "$ENV_DST" ]; then
  cp "$ENV_SRC" "$ENV_DST"
  echo "Created $ENV_DST from template."
  echo "Fill in OPENAI_API_KEY, WEBUI_SECRET_KEY, and other secrets, then rerun."
  exit 1
fi

CURRENT_IMAGE="$(grep '^GPTHUB_IMAGE=' "$ENV_DST" | tail -1 | cut -d= -f2- || true)"

if [ -z "${GPTHUB_IMAGE:-}" ]; then
  if [ "$VERSION" != "latest" ]; then
    IMAGE_REPO="${CURRENT_IMAGE%:*}"
    if [ -z "$IMAGE_REPO" ] || [ "$IMAGE_REPO" = "$CURRENT_IMAGE" ]; then
      IMAGE_REPO="gpthub-app"
    fi
    GPTHUB_IMAGE="${IMAGE_REPO}:${VERSION}"
  elif [ -n "$CURRENT_IMAGE" ]; then
    GPTHUB_IMAGE="$CURRENT_IMAGE"
  else
    GPTHUB_IMAGE="gpthub-app:latest"
  fi
fi

if grep -q '^GPTHUB_IMAGE=' "$ENV_DST"; then
  sed -i.bak "s|^GPTHUB_IMAGE=.*|GPTHUB_IMAGE=${GPTHUB_IMAGE}|" "$ENV_DST"
else
  printf '\nGPTHUB_IMAGE=%s\n' "$GPTHUB_IMAGE" >> "$ENV_DST"
fi
rm -f "${ENV_DST}.bak"

echo "Deploying GPTHub image: $GPTHUB_IMAGE"
docker compose -f "$COMPOSE_DST" --env-file "$ENV_DST" pull
docker compose -f "$COMPOSE_DST" --env-file "$ENV_DST" up -d

PORT="$(awk -F= '/^PORT=/{print $2}' "$ENV_DST" | tail -1)"
PORT="${PORT:-3000}"

echo "Waiting for health check on port ${PORT}..."
for attempt in $(seq 1 30); do
  if curl -sf "http://127.0.0.1:${PORT}/health" >/dev/null; then
    echo "GPTHub is healthy."
    docker compose -f "$COMPOSE_DST" --env-file "$ENV_DST" ps
    if [ "$PRUNE_IMAGES" = "true" ]; then
      docker image prune -f
    fi
    exit 0
  fi
  sleep 2
done

echo "Deployment completed but health check failed."
docker compose -f "$COMPOSE_DST" --env-file "$ENV_DST" ps
exit 1
