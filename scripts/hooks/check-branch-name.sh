#!/bin/sh
branch=$(git rev-parse --abbrev-ref HEAD)
if [ "$branch" = "main" ] || [ "$branch" = "develop" ]; then
  exit 0
fi
echo "$branch" | grep -qE "^(feat|fix|chore|refactor|docs|test)/" || {
  echo "Bad branch name: $branch"
  echo "Use: feat/, fix/, chore/, refactor/, docs/, test/"
  echo "Example: feat/backend/auto-routing"
  exit 1
}
