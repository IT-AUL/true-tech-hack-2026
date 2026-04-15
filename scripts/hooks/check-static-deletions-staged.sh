#!/bin/sh
# Block accidental mass deletion of backend static assets.
# Bypass intentionally with: ALLOW_STATIC_DELETIONS=1 git commit ...

if [ "${ALLOW_STATIC_DELETIONS:-0}" = "1" ]; then
  exit 0
fi

count="$(git diff --cached --name-status -- backend/open_webui/static | awk '$1=="D"{c++} END{print c+0}')"

MAX_DELETIONS=3
if [ "$count" -gt "$MAX_DELETIONS" ]; then
  echo "ERROR: staged deletion count in backend/open_webui/static is $count (limit: $MAX_DELETIONS)."
  echo "If this is intentional, run commit with ALLOW_STATIC_DELETIONS=1."
  exit 1
fi

exit 0
