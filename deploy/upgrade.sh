#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VERSION="${1:-latest}"
DEPLOY_ROOT="${DEPLOY_ROOT:-/opt/gpthub}"
COMPOSE_FILE="$DEPLOY_ROOT/docker-compose.prod.yml"
ENV_FILE="$DEPLOY_ROOT/.env"
BACKUP_DIR="$DEPLOY_ROOT/backup-$(date +%Y%m%d-%H%M%S)"

cd "$SCRIPT_DIR"

if [ ! -f "$ENV_FILE" ]; then
  echo "Error: $ENV_FILE file not found."
  exit 1
fi

CONTAINER_ID=$(docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" ps -q gpthub 2>/dev/null || true)

if [ -n "$CONTAINER_ID" ]; then
  echo "Backing up data to $BACKUP_DIR ..."
  mkdir -p "$BACKUP_DIR"
  docker cp "$CONTAINER_ID":/app/backend/data "$BACKUP_DIR/data"
  echo "Backup complete."
else
  echo "Warning: no running container found, skipping backup."
fi

echo "Pulling version: $VERSION ..."
bash "$SCRIPT_DIR/deploy.sh" "$VERSION"

echo ""
echo "Upgraded to $VERSION."
[ -d "$BACKUP_DIR" ] && echo "Previous data backed up to: $BACKUP_DIR"
