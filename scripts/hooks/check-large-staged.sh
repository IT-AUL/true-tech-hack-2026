#!/bin/sh
# Max 500 KB per staged file (excluding lock and png)
MAX=512000
list=$(mktemp)
trap 'rm -f "$list"' EXIT
git diff --cached --name-only --diff-filter=ACM >"$list" || exit 0
while IFS= read -r f; do
	[ -z "$f" ] && continue
	case "$f" in
	*package-lock.json|*.lock|*.png|CHANGELOG.md) continue ;;
	esac
	[ -f "$f" ] || continue
	sz=$(wc -c <"$f" | tr -d ' ')
	if [ "$sz" -gt "$MAX" ]; then
		echo "ERROR: Staged file exceeds ${MAX} bytes: $f"
		exit 1
	fi
done <"$list"
