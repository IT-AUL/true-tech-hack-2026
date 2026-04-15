# Настройка GitLab

Основной репозиторий проекта: **[github.com/IT-AUL/true-tech-hack-2026](https://github.com/IT-AUL/true-tech-hack-2026)**. Разработка, проверка изменений и автоматические сборки выполняются там.

Репозиторий в GitLab дублирует содержимое и обновляется при переносе ветки `main` с GitHub. Документ ниже описывает разовую настройку проекта в GitLab для администратора (роль Maintainer).

## 1. Защита ветки main

Settings → Repository → Protected branches:

| Параметр | Значение |
|----------|----------|
| Branch | `main` |
| Allowed to merge | Maintainers |
| Allowed to push | No one |
| Allowed to force push | Off |
| Require approval | 1 approval |

Теперь в `main` нельзя пушить напрямую — только через MR с аппрувом.

## 2. Защита ветки develop (опционально)

Если хотите требовать MR и в develop:

| Параметр | Значение |
|----------|----------|
| Branch | `develop` |
| Allowed to merge | Developers + Maintainers |
| Allowed to push | No one |

## 3. Merge request approvals

Settings → Merge requests → Merge request approvals:

- Approvals required: **1**
- Can override approvals: **Off**
- Remove approvals on push: **On**

## 4. Merge checks

Settings → Merge requests → Merge checks:

- [x] Pipelines must succeed
- [x] All discussions must be resolved

## 5. Push rules (если доступно)

Settings → Repository → Push rules:

- Branch name regex: `^(main|develop|(feat|fix|chore|refactor|docs|test)\/.+)$`
- Commit message regex: `^(feat|fix|chore|refactor|docs|test|ci|perf|style|build|revert)(\(.+\))?: .+`
- Reject unsigned commits: Off (на усмотрение)
- Max file size: 10 MB

## 6. CI/CD variables

Settings → CI/CD → Variables (если используется Container Registry):

Переменные `CI_REGISTRY`, `CI_REGISTRY_USER`, `CI_REGISTRY_PASSWORD` обычно проставляются GitLab автоматически при включённом Registry.
