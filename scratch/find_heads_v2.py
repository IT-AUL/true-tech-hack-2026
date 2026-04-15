import os
import re

path = 'backend/open_webui/migrations/versions'
files = [f for f in os.listdir(path) if f.endswith('.py')]

revisions = []
down_revisions = []

for f in files:
    with open(os.path.join(path, f), 'r') as fh:
        content = fh.read()
        rev_match = re.search(r"^revision\s*[:\w\s|]*=\s*['\"](\w+)['\"]", content, re.M)
        down_rev_match = re.search(r"^down_revision\s*[:\w\s|]*=\s*['\"](\w+)['\"]", content, re.M)
        
        if rev_match:
            revisions.append(rev_match.group(1))
        if down_rev_match:
            down_revisions.append(down_rev_match.group(1))

heads = [r for r in revisions if r not in down_revisions]
print(f"Total files: {len(files)}")
print(f"Total revisions: {len(revisions)}")
print(f"Heads: {heads}")
