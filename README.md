# GPTHub — Единое ИИ-пространство

[![CI](https://github.com/IT-AUL/true-tech-hack-2026/actions/workflows/ci.yml/badge.svg?branch=develop)](https://github.com/IT-AUL/true-tech-hack-2026/actions/workflows/ci.yml)
[![release](https://img.shields.io/static/v1?label=release&message=0.8.12-gpthub.16&color=blue)](https://github.com/IT-AUL/true-tech-hack-2026/releases/latest)
[![upstream](https://img.shields.io/static/v1?label=upstream&message=Open%20WebUI%200.8.12&color=8A2BE2&logo=github)](https://github.com/open-webui/open-webui)
[![license](https://img.shields.io/badge/license-BSD--3--Clause-green.svg)](LICENSE)
[![Docker Hub](https://img.shields.io/docker/pulls/itaul/gpthub?logo=docker&logoColor=white)](https://hub.docker.com/r/itaul/gpthub)
[![self-hosted](https://img.shields.io/badge/self--hosted-supported-success.svg)](#деплой-для-компаний-self-hosted)

[![SvelteKit](https://img.shields.io/badge/SvelteKit-2-FF3E00.svg?logo=svelte&logoColor=white)](https://kit.svelte.dev/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.135-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB.svg?logo=python&logoColor=white)](https://python.org/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.5-3178C6.svg?logo=typescript&logoColor=white)](https://typescriptlang.org/)
[![Tailwind CSS](https://img.shields.io/badge/Tailwind_CSS-4-06B6D4.svg?logo=tailwindcss&logoColor=white)](https://tailwindcss.com/)

> Форк [Open WebUI](https://github.com/open-webui/open-webui), расширенный для работы как единый мультимодальный ИИ-хаб с интеллектуальной маршрутизацией моделей и долгосрочной памятью.

## Возможности

- **Мультимодальный чат** — текст, голос, изображения, файлы, аудио в одном интерфейсе
- **Авто-маршрутизация** — система автоматически выбирает подходящую модель (LLM / VLM / ASR / ImageGen)
- **Ручной выбор модели** — переключение между моделями в любой момент
- **Долгосрочная память** — сохранение контекста и фактов о пользователе между сессиями
- **Веб-поиск и парсинг** — анализ веб-страниц по ссылке
- **Self-hosted** — развёртывание на своих мощностях одной командой

## Быстрый старт

```bash
# Клонировать репозиторий
git clone https://git.truetecharena.ru/tta/true-tech-hack-in2026-gpthub-git/it-aul-misisxcuxkfu/task-repo.git
cd task-repo

# Запуск (одна команда)
OPENAI_API_KEY=<your-key> docker compose -f docker-compose.dev.yml up --build
```

Приложение будет доступно на `http://localhost:3000`.

## Разработка

### Требования

- Node.js 22+
- Python 3.11+
- Docker & Docker Compose v2

### Локальный запуск (без Docker)

**Backend:**
```bash
cd backend
pip install -r requirements.txt
bash start.sh
```

**Frontend:**
```bash
npm ci
npm run dev
```

### Линтинг

```bash
# Frontend
npx eslint . --max-warnings=0
npx prettier --check "src/**/*.{js,ts,svelte,css,json}"

# Backend
ruff check backend/
ruff format --check backend/

# Проверка типов (frontend)
npm run check
```

### Pre-commit хуки

Конфиг в `.pre-commit-config.yaml` **не подключается сам**: пока не выполнишь `pre-commit install`, при `git commit` ничего не запустится.

```bash
brew install ruff pipx
pipx install pre-commit
pre-commit install       # один раз в корне репозитория
```

Ruff в хуках идёт как **`ruff` в PATH** (без отдельного Python-окружения под Ruff). Сам `pre-commit` лучше ставить через **pipx**, чтобы не зависеть от поломанного Homebrew Python 3.14 у `brew install pre-commit`.

Проверить: `test -f .git/hooks/pre-commit && echo OK` — должен вывести `OK`.

## Деплой для компаний (self-hosted)

```bash
cd deploy/
cp .env.example .env
# Отредактируйте .env — укажите OPENAI_API_KEY и WEBUI_SECRET_KEY
docker compose -f docker-compose.prod.yml up -d
```

Подробная инструкция: [deploy/DEPLOY.md](deploy/DEPLOY.md)

## Версионирование и релизы

Формат: `0.8.12-gpthub.1` — база Open WebUI + номер релиза форка. Подробнее: [docs/VERSIONING.md](docs/VERSIONING.md).

```bash
npm run release   # интерактивный выбор версии → коммит → тег → пуш
```

При пуше тега CI собирает Docker-образ и публикует его на [Docker Hub](https://hub.docker.com/r/gpthub/gpthub) и [GHCR](https://github.com/IT-AUL/true-tech-hack-2026/pkgs/container/true-tech-hack-2026), а также создаёт [GitHub Release](https://github.com/IT-AUL/true-tech-hack-2026/releases) с changelog.

## Структура проекта

```
├── src/                    # Frontend (SvelteKit 2 + Svelte 5 + Tailwind)
│   ├── lib/components/     #   UI-компоненты
│   ├── lib/apis/           #   API-клиенты
│   ├── lib/stores/         #   Svelte stores
│   └── routes/             #   Страницы
├── backend/                # Backend (FastAPI + Python 3.11)
│   └── open_webui/
│       ├── main.py         #   Точка входа
│       ├── routers/        #   REST API endpoints
│       ├── models/         #   SQLAlchemy ORM
│       ├── utils/          #   Chat pipeline, routing, auth
│       └── retrieval/      #   RAG и векторный поиск
├── deploy/                 # Self-hosted deployment
├── docs/                   # Документация API-изменений
├── .gitlab-ci.yml          # CI/CD pipeline
├── docker-compose.dev.yml        # Compose для разработки
└── docker-compose.yaml     # Compose по умолчанию (GPTHub + MWS / OpenAI)
```

## Команда

| Роль | Область | Ключевые файлы |
|------|---------|-----------------|
| Frontend | `src/` | Компоненты чата, ModelSelector, мультимодальный ввод |
| Backend | `backend/` | Роутеры, маршрутизация моделей, API интеграция |
| MLOps | Docker, память, RAG | docker-compose, memories, retrieval |

## Ветвление и workflow

- `main` — стабильные релизы (защищённая ветка)
- `develop` — интеграция фич
- `feat/<область>/<описание>` — feature-ветки

Полный workflow с кейсами и примерами: **[docs/WORKFLOW.md](docs/WORKFLOW.md)**

## API бекенда моделей

MWS GPT API (OpenAI-совместимый):
- Base URL: `https://api.gpt.mws.ru/v1`
- Endpoints: `/models`, `/chat/completions`, `/completions`, `/embeddings`

## Лицензия

Основано на Open WebUI. См. [LICENSE](LICENSE).
