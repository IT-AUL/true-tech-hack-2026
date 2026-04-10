#!/bin/sh
# Uses system python3 + PyYAML if available; skips if yaml module missing
python3 -c "import yaml" 2>/dev/null || exit 0
list=$(mktemp)
trap 'rm -f "$list"' EXIT
git diff --cached --name-only --diff-filter=ACM | grep -E '\.(ya?ml)$' >"$list" || exit 0
[ ! -s "$list" ] && exit 0
while IFS= read -r f; do
	[ -z "$f" ] && continue
	[ -f "$f" ] || continue
	python3 -c "
import sys
from pathlib import Path
import yaml
p = Path(sys.argv[1])
text = p.read_text(encoding='utf-8', errors='replace')
for _ in yaml.safe_load_all(text):
    pass
" "$f" || exit 1
done <"$list"
