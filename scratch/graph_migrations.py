import os
import re

path = 'backend/open_webui/migrations/versions'
files = [f for f in os.listdir(path) if f.endswith('.py')]

all_revs = {}
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

print("graph {")
for rev, down in all_revs.items():
    if down:
        print(f'  "{down}" -> "{rev}"')
    else:
        print(f'  "None" -> "{rev}"')
print("}")
