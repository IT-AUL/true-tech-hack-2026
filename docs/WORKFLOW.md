# Workflow разработки

## Ветки

```
main        — стабильные релизы, деплой на прод
develop     — интеграция, сюда мержатся все фичи
feat/*      — feature-ветки
fix/*       — багфиксы
chore/*     — инфра, CI, линт
```

## Ежедневная работа

### 1. Взять задачу → создать ветку

```bash
git checkout develop && git pull
git checkout -b feat/backend/auto-routing
```

Именование: `feat/<область>/<что>`, `fix/<область>/<что>`, `chore/<что>`.
Области: `frontend`, `backend`, `mlops`.

### 2. Разработка

```bash
# backend — линт автоматом на каждом коммите (pre-commit)
ruff check backend/
ruff format backend/

# frontend
npx eslint . --max-warnings=0
npm run check   # svelte-check

# запуск
npm run dev            # frontend на :5173
cd backend && bash start.sh  # backend на :8080
```

### 3. Коммит

Pre-commit хуки запускаются автоматически:
- **ruff** — линт и форматирование Python
- **eslint / prettier** — линт и форматирование фронтенда
- **branch-name** — проверка имени ветки (`feat/`, `fix/`, `chore/`, и т.д.)
- **no-debug** — блок `console.log`, `breakpoint()`, `pdb` в коммите
- **no-secrets** — блок API-ключей и паролей в коде
- **no-commit-to-branch** — запрет прямого коммита в `main`
- **check-yaml, check-merge-conflict, check-added-large-files**

```bash
git add .
git commit -m "feat: auto-routing classifier"
```

Формат сообщений: `feat:`, `fix:`, `chore:`, `docs:`, `refactor:`, `test:`, `ci:`.

### 4. Пуш и MR

```bash
git push origin feat/backend/auto-routing
```

GitLab предложит ссылку на создание MR в `develop`.

CI автоматически проверит:
- **validate:branch-name** — имя ветки по конвенции
- **validate:mr-title** — заголовок MR в формате Conventional Commits
- **validate:no-version-drift** — совпадение версий package.json и package-lock.json
- **validate:api-docs** — напоминание обновить API-документацию (warning, не блокирует)
- **lint** и **check** — как обычно

### 5. Code review → merge в develop

Тиммейт смотрит MR, проверяет что ничего не сломано. Merge (требует 1 аппрув).

> **main** защищён: прямой push запрещён, merge только через MR с аппрувом и зелёным CI.
> Настройка GitLab описана в [docs/GITLAB_SETUP.md](GITLAB_SETUP.md).

---

## Релиз

Когда набор изменений в `develop` готов к выпуску:

```bash
git checkout develop && git pull
npm run release
```

Скрипт предложит версию, сделает коммит, тег, спросит про пуш. CI соберёт Docker-образ и создаст Release.

---

## Кейсы

### Кейс 1: Backend-разработчик добавил новый endpoint

```bash
git checkout develop && git pull
git checkout -b feat/backend/mws-models

# ... пишет код в backend/open_webui/routers/
# ... описывает новый endpoint в docs/API_CHANGES.md

git add . && git commit -m "feat: add /api/v1/route endpoint"
git push origin feat/backend/mws-models
# → создать MR в develop
```

### Кейс 2: Frontend-разработчик поправил UI бага

```bash
git checkout develop && git pull
git checkout -b fix/frontend/model-selector-overflow

# ... правит компонент в src/lib/components/chat/ModelSelector/

git add . && git commit -m "fix: model selector overflow on mobile"
git push origin fix/frontend/model-selector-overflow
# → MR в develop
```

### Кейс 3: MLOps обновил docker-compose

```bash
git checkout develop && git pull
git checkout -b chore/mlops/compose-redis

# ... добавляет Redis в docker-compose.dev.yml

git add . && git commit -m "chore: add Redis to dev compose"
git push origin chore/mlops/compose-redis
# → MR в develop
```

### Кейс 4: Выпуск релиза после нескольких MR

```bash
git checkout develop && git pull

npm run release
#   Текущая версия: 0.8.12-gpthub.0
#   Выбираю 1) → 0.8.12-gpthub.1
#   → коммит, тег, пуш
#   → CI: образ в registry, GitLab Release
```

### Кейс 5: Синхронизация с новой версией Open WebUI

```bash
git fetch upstream
git checkout develop
git merge upstream/main
# разрешить конфликты если есть

npm run release
#   Ввожу вручную: 0.9.0-gpthub.0 (новая база)
```

### Кейс 6: Деплой конкретной версии

```bash
cd deploy
cp .env.example .env && vim .env
GPTHUB_IMAGE=registry.../gpthub:0.8.12-gpthub.1 docker compose -f docker-compose.prod.yml up -d
```

Или обновление:
```bash
./upgrade.sh 0.8.12-gpthub.1
```

---

## Чек-лист перед MR

- [ ] Линтер проходит (`ruff check`, `eslint`)
- [ ] Не сломана сборка (`npm run check`)
- [ ] Нет `console.log` / `breakpoint()` в коде
- [ ] Заголовок MR: `feat(backend): add auto-routing endpoint`
- [ ] Новые API описаны в `docs/API_CHANGES.md`
- [ ] Docker собирается (если трогали Dockerfile / compose)

## Чек-лист перед релизом

- [ ] `develop` стабилен, CI зелёный
- [ ] `npm run release` — версия, коммит, тег, пуш
- [ ] Pipeline на теге прошёл
- [ ] Docker-образ в Registry
