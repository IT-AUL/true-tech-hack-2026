# Версионирование

## Формат

```
0.8.12-gpthub.1
│          │
│          └─ номер релиза форка (наши фичи/фиксы)
└──────────── версия Open WebUI, от которой форк
```

Связь с upstream видна в `package.json` → `gpthub.upstreamVersion` и в бейдже README.

## Как выпустить релиз

```bash
npm run release
```

Скрипт покажет текущую версию и предложит варианты:

```
  GPTHub Release
  ─────────────────────────────────────
  Текущая версия:  0.8.12-gpthub.0
  Upstream (база):  Open WebUI 0.8.12

  Выберите версию:

    1)  0.8.12-gpthub.1  — gpthub (фикс/фича форка)
    2)  0.8.13-gpthub.0  — patch (базовый патч)
    3)  0.9.0-gpthub.0   — minor (новый минор)
    4)  1.0.0-gpthub.0   — major (мажорный)
    5)  Ввести вручную

  Ваш выбор [1-5]:
```

Дальше скрипт сам:
1. Обновит `package.json`, `package-lock.json`, бейджи в `README.md`.
2. Сделает коммит `chore: release vX.Y.Z-gpthub.N`.
3. Поставит тег `vX.Y.Z-gpthub.N`.
4. Спросит, пушить ли — и запушит ветку + тег.

## Что происходит в CI после пуша тега

```
release:verify  →  release:docker  →  release:publish
   совпадение        Docker-образ       GitLab Release
   тега и             :версия            с описанием
   package.json       :latest            и ссылками
```

## Где хранится версия

| Файл | Что |
|------|-----|
| `package.json` → `version` | Единственный источник правды |
| `package.json` → `gpthub.upstreamVersion` | На какой версии Open WebUI основан форк |
| README бейджи `release` / `upstream` | Обновляются скриптом |
| Git-тег `v…` | Триггер CI |

## Если `release-cli` недоступен

Джоб `release:publish` тянет `registry.gitlab.com/gitlab-org/release-cli`. Если раннер не имеет доступа — удалите этот джоб из `.gitlab-ci.yml`, Docker-образ всё равно соберётся и запушится.
