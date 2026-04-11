#!/bin/sh
set -e
if ! command -v ruff >/dev/null 2>&1; then
	echo "ruff not found. Install: pip install ruff  or  brew install ruff"
	exit 1
fi
ruff check backend/ --fix
ruff format backend/
