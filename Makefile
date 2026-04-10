COMPOSE_FILE ?= docker-compose.dev.yml

ifneq ($(shell which docker-compose 2>/dev/null),)
    DOCKER_COMPOSE := docker-compose
else
    DOCKER_COMPOSE := docker compose
endif

.PHONY: up down build lint lint-frontend lint-backend check dev

up:
	$(DOCKER_COMPOSE) -f $(COMPOSE_FILE) up -d

build:
	$(DOCKER_COMPOSE) -f $(COMPOSE_FILE) up -d --build

down:
	$(DOCKER_COMPOSE) -f $(COMPOSE_FILE) down

logs:
	$(DOCKER_COMPOSE) -f $(COMPOSE_FILE) logs -f

lint: lint-frontend lint-backend

lint-frontend:
	npx eslint . --max-warnings=0
	npx prettier --check "src/**/*.{js,ts,svelte,css,json}"

lint-backend:
	ruff check backend/
	ruff format --check backend/

check:
	npm run check

dev:
	npm run dev
