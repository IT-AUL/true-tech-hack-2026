#!/bin/sh
if git diff --cached --diff-filter=ACM | grep -nEi 'sk-[a-zA-Z0-9]{20}|PRIVATE.KEY'; then
  echo "ERROR: Possible secret detected. Use env vars instead."
  exit 1
fi
