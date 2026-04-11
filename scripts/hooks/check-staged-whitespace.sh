#!/bin/sh
# Fails if staged diff introduces trailing whitespace (same idea as pre-commit-hooks)
git diff --cached --check || exit 1
