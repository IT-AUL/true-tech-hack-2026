#!/bin/sh
list=$(mktemp)
trap 'rm -f "$list"' EXIT
git diff --cached --name-only --diff-filter=ACM >"$list" || exit 0
[ ! -s "$list" ] && exit 0
while IFS= read -r f; do
	[ -z "$f" ] && continue
	[ -f "$f" ] || continue
	if grep -q '^<<<<<<<' "$f" 2>/dev/null; then
		echo "ERROR: Merge conflict markers in: $f"
		exit 1
	fi
done <"$list"
