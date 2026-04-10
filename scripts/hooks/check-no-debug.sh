#!/bin/sh
fail=0

if git diff --cached --diff-filter=ACM -- "*.py" | grep -nE "^\+.*(breakpoint\(\)|pdb\.set_trace|import pdb)"; then
  echo "ERROR: Remove debug statements (breakpoint/pdb) before committing"
  fail=1
fi

if git diff --cached --diff-filter=ACM -- "*.ts" "*.svelte" "*.js" | grep -nE '^\+.*console\.(log|debug)\('; then
  echo "ERROR: Remove console.log/debug before committing"
  fail=1
fi

exit $fail
