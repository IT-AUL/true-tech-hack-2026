import os
import re

path = 'backend/open_webui/migrations/versions'
files = [f for f in os.listdir(path) if f.endswith('.py')]

all_revs = {}
all_down_revs = []

for f in files:
    content = open(os.path.join(path, f)).read()
    rev_match = re.search(r"revision\s*:\s*str\s*=\s*['\"](\w+)['\"]", content)
    down_rev_match = re.search(r"down_revision\s*:\s*str\s*\|\s*None\s*=\s*['\"](\w+)['\"]", content)
    if not down_rev_match:
        down_rev_match = re.search(r"down_revision\s*=\s*['\"](\w+)['\"]", content)
    
    if rev_match:
        rev = rev_match.group(1)
        down_rev = down_rev_match.group(1) if down_rev_match else None
        all_revs[rev] = down_rev
        if down_rev:
            all_down_revs.append(down_rev)

heads = [r for r in all_revs if r not in all_down_revs]
print(f"Heads: {heads}")

for h in heads:
    print(f"Head {h} -> Down revision: {all_revs[h]}")
