# GPTHub — Self-Hosted Deployment Guide

## Requirements

- Docker 24+ with Docker Compose v2
- 2 GB RAM minimum (4 GB recommended)
- 10 GB disk space
- Network access to your OpenAI-compatible API endpoint

## Quick Start

```bash
sudo mkdir -p /opt/gpthub
cp deploy/.env.example /opt/gpthub/.env
# Edit /opt/gpthub/.env — set OPENAI_API_KEY and WEBUI_SECRET_KEY at minimum
bash deploy/deploy.sh
```

The application will be available at `http://localhost:3000` (or the port you set in `/opt/gpthub/.env`).

`deploy.sh` copies the latest [`docker-compose.prod.yml`](docker-compose.prod.yml) into `/opt/gpthub/`, reads runtime secrets from `/opt/gpthub/.env`, rolls out the selected image, waits for `/health`, and optionally prunes dangling Docker images.

## Demo Stand Workflow

For the demo VPS, the recommended path is a manual GitHub Actions rollout:

1. Push a release tag so the image is built and published.
2. Open `Actions -> Deploy Demo`.
3. Run the workflow with either:
   - `version=0.8.12-gpthub.16`
   - or a full `image=ghcr.io/...:0.8.12-gpthub.16`
4. The deploy runner on the VPS will:
   - sync `docker-compose.prod.yml` into `/opt/gpthub/`
   - reuse `/opt/gpthub/.env`
   - inject `WEBUI_SECRET_KEY` from GitHub Actions secret on each deploy
   - set `GPTHUB_IMAGE`
   - run `docker compose pull && docker compose up -d`
   - wait for `/health`
   - prune dangling images

This keeps release and rollout separate: you can redeploy the same image without creating a new tag.

Before first rollout, add repository secret `WEBUI_SECRET_KEY` in GitHub:
`Settings -> Secrets and variables -> Actions`.

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
| `GPTHUB_IMAGE` | No | `gpthub-app:latest` | Docker image to use; updated automatically by the demo deploy workflow |

## Upgrading

```bash
bash deploy/upgrade.sh latest                 # upgrade to latest image
bash deploy/upgrade.sh 0.8.12-gpthub.16      # upgrade to specific version
```

The upgrade script automatically backs up your data from the running container before calling `deploy.sh`.

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
docker compose -f /opt/gpthub/docker-compose.prod.yml --env-file /opt/gpthub/.env logs -f gpthub
```

**Reset data (caution — deletes all data):**
```bash
docker compose -f /opt/gpthub/docker-compose.prod.yml --env-file /opt/gpthub/.env down -v
bash deploy/deploy.sh
```
