#!/usr/bin/env bash
# =============================================================================
# GPTHub Production Deploy Script
# Использование: ./deploy/deploy.sh [build|up|down|restart|logs|status]
# =============================================================================

set -euo pipefail

COMPOSE_FILE="$(dirname "$0")/docker-compose.prod.yml"
ENV_FILE="$(dirname "$0")/.env.prod"
PROJECT_NAME="gpthub"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'

log()   { echo -e "${GREEN}[DEPLOY]${NC} $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

# Проверяем наличие .env.prod
if [ ! -f "$ENV_FILE" ]; then
    error ".env.prod not found at $ENV_FILE\nCopy deploy/.env.prod, fill in WEBUI_SECRET_KEY and CORS_ALLOW_ORIGIN first."
fi

# Проверяем что WEBUI_SECRET_KEY задан
if grep -q "ЗАМЕНИ_НА_СЛУЧАЙНУЮ_СТРОКУ" "$ENV_FILE" 2>/dev/null; then
    error "WEBUI_SECRET_KEY still has placeholder value! Generate one:\n  python3 -c \"import secrets; print(secrets.token_hex(32))\""
fi

CMD="${1:-up}"

case "$CMD" in
  build)
    log "Building Docker image..."
    cd "$(dirname "$0")/.."
    docker build \
      --build-arg BUILD_HASH="$(git rev-parse --short HEAD 2>/dev/null || echo 'unknown')" \
      --build-arg USE_SLIM=true \
      -t gpthub-app:latest \
      -t "gpthub-app:$(git rev-parse --short HEAD 2>/dev/null || echo 'local')" \
      .
    log "Build complete: gpthub-app:latest"
    ;;

  up)
    log "Starting GPTHub stack..."
    docker compose -p "$PROJECT_NAME" -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d
    log "Stack started. Check logs: ./deploy/deploy.sh logs"
    log "Health: curl http://localhost:3000/health"
    ;;

  down)
    warn "Stopping GPTHub stack (data volumes preserved)..."
    docker compose -p "$PROJECT_NAME" -f "$COMPOSE_FILE" --env-file "$ENV_FILE" down
    ;;

  restart)
    warn "Restarting GPTHub app only (Qdrant/Redis keep running)..."
    docker compose -p "$PROJECT_NAME" -f "$COMPOSE_FILE" --env-file "$ENV_FILE" restart gpthub
    ;;

  pull)
    log "Pulling latest code from git..."
    cd "$(dirname "$0")/.."
    git pull origin develop
    log "Run './deploy/deploy.sh build' then './deploy/deploy.sh restart' to apply."
    ;;

  logs)
    docker compose -p "$PROJECT_NAME" -f "$COMPOSE_FILE" --env-file "$ENV_FILE" \
      logs -f --tail=100 "${2:-gpthub}"
    ;;

  status)
    log "=== Container Status ==="
    docker compose -p "$PROJECT_NAME" -f "$COMPOSE_FILE" --env-file "$ENV_FILE" ps
    echo ""
    log "=== Qdrant Health ==="
    curl -s http://localhost:6333/readyz | python3 -m json.tool 2>/dev/null || echo "Qdrant not responding"
    echo ""
    log "=== Redis Health ==="
    docker exec gpthub-redis redis-cli ping 2>/dev/null || echo "Redis not responding"
    echo ""
    log "=== App Health ==="
    curl -s http://localhost:3000/health | python3 -m json.tool 2>/dev/null || echo "App not responding"
    ;;

  qdrant-drop-collection)
    COLLECTION="${2:-project_memories_v1}"
    warn "Dropping Qdrant collection: $COLLECTION"
    curl -sf -X DELETE "http://localhost:6333/collections/$COLLECTION" | python3 -m json.tool
    log "Collection dropped. It will be recreated with correct dims on next memory write."
    ;;

  *)
    echo "Usage: $0 [build|up|down|restart|pull|logs|status|qdrant-drop-collection]"
    echo ""
    echo "  build                     Build Docker image from source"
    echo "  up                        Start all services (detached)"
    echo "  down                      Stop all services"
    echo "  restart                   Restart only gpthub container"
    echo "  pull                      Pull latest git code"
    echo "  logs [service]            Tail logs (default: gpthub)"
    echo "  status                    Show health of all services"
    echo "  qdrant-drop-collection    Drop Qdrant collection (triggers re-index)"
    ;;
esac
