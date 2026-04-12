#!/bin/sh
secret_prefix='sk-'
secret_body='[a-zA-Z0-9]{20}'
private_key_pattern='PRIVATE[.]KEY'

if git diff --cached --diff-filter=ACM --unified=0 --no-color | grep -nEi "^\+[^+].*(${secret_prefix}${secret_body}|${private_key_pattern})"; then
  echo "ERROR: Possible secret detected. Use env vars instead."
  exit 1
fi
