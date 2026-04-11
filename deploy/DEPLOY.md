# GPTHub — Self-Hosted Deployment Guide

## Requirements

- Docker 24+ with Docker Compose v2
- 2 GB RAM minimum (4 GB recommended)
- 10 GB disk space
- Network access to your OpenAI-compatible API endpoint

## Quick Start

```bash
cd deploy/
cp .env.example .env
# Edit .env — set OPENAI_API_KEY and WEBUI_SECRET_KEY at minimum
docker compose -f docker-compose.prod.yml up -d
```

The application will be available at `http://localhost:3000` (or the port you set in `.env`).

## Configuration

| Variable | Required | Default | Description |
|---|---|---|---|
| `OPENAI_API_BASE_URL` | Yes | — | OpenAI-compatible API base URL |
| `OPENAI_API_KEY` | Yes | — | API key for the endpoint |
| `WEBUI_SECRET_KEY` | Yes | — | Random string for session encryption |
| `PORT` | No | `3000` | Host port to expose |
| `ENABLE_SIGNUP` | No | `false` | Allow new user registration |
| `DEFAULT_USER_ROLE` | No | `user` | Default role for new users |
| `DATABASE_URL` | No | SQLite | PostgreSQL connection string |
| `GPTHUB_IMAGE` | No | `gpthub-app:latest` | Docker image to use |

## Upgrading

```bash
cd deploy/
./upgrade.sh          # upgrade to latest
./upgrade.sh v1.0.0   # upgrade to specific version
```

The upgrade script automatically backs up your data before pulling the new version.

## Backup & Restore

**Backup:**
```bash
docker cp gpthub:/app/backend/data ./backup-$(date +%Y%m%d)
```

**Restore:**
```bash
docker cp ./backup-20260410/data gpthub:/app/backend/
docker compose -f docker-compose.prod.yml restart
```

## Using PostgreSQL

By default the application uses SQLite stored in a Docker volume. For production with multiple users, switch to PostgreSQL:

```env
DATABASE_URL=postgresql://gpthub:password@postgres-host:5432/gpthub
```

## Reverse Proxy (HTTPS)

Example nginx configuration:

```nginx
server {
    listen 443 ssl;
    server_name gpthub.example.com;

    ssl_certificate     /etc/ssl/certs/gpthub.pem;
    ssl_certificate_key /etc/ssl/private/gpthub.key;

    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # WebSocket support
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

## Troubleshooting

**Check health:**
```bash
curl -s http://localhost:3000/health | jq .
```

**View logs:**
```bash
docker compose -f docker-compose.prod.yml logs -f gpthub
```

**Reset data (caution — deletes all data):**
```bash
docker compose -f docker-compose.prod.yml down -v
docker compose -f docker-compose.prod.yml up -d
```
