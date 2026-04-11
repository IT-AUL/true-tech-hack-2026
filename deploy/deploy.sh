#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VERSION="${1:-latest}"

cd "$SCRIPT_DIR"

if [ ! -f .env ]; then
  echo "Error: .env file not found."
  echo "Run: cp .env.example .env  and fill in the required values."
  exit 1
fi

if [ "$VERSION" != "latest" ]; then
  export GPTHUB_IMAGE="gpthub-app:${VERSION}"
fi

echo "Deploying GPTHub version: $VERSION"
docker compose -f docker-compose.prod.yml pull 2>/dev/null || true
docker compose -f docker-compose.prod.yml up -d

echo ""
echo "GPTHub is starting on port ${PORT:-3000}."
echo "Check health: curl -s http://localhost:${PORT:-3000}/health"
