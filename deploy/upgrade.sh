#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VERSION="${1:-latest}"
BACKUP_DIR="$SCRIPT_DIR/backup-$(date +%Y%m%d-%H%M%S)"

cd "$SCRIPT_DIR"

if [ ! -f .env ]; then
  echo "Error: .env file not found."
  exit 1
fi

CONTAINER_ID=$(docker compose -f docker-compose.prod.yml ps -q gpthub 2>/dev/null || true)

if [ -n "$CONTAINER_ID" ]; then
  echo "Backing up data to $BACKUP_DIR ..."
  mkdir -p "$BACKUP_DIR"
  docker cp "$CONTAINER_ID":/app/backend/data "$BACKUP_DIR/data"
  echo "Backup complete."
else
  echo "Warning: no running container found, skipping backup."
fi

if [ "$VERSION" != "latest" ]; then
  export GPTHUB_IMAGE="gpthub-app:${VERSION}"
fi

echo "Pulling version: $VERSION ..."
docker compose -f docker-compose.prod.yml pull 2>/dev/null || true
docker compose -f docker-compose.prod.yml up -d

echo ""
echo "Upgraded to $VERSION."
[ -d "$BACKUP_DIR" ] && echo "Previous data backed up to: $BACKUP_DIR"
