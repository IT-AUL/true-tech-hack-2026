with open('/Users/dremotha/Projects/Temp/true-tech-hack-2026/backend/open_webui/utils/middleware.py') as f:
    text = f.read()

import re

pattern = re.compile(
    r'        from open_webui\.utils\.auto_routing import PATTERNS.*?except Exception as e:\n                log\.exception\(f\"Agentic pipeline failed: \{e\}\"\)',
    re.DOTALL,
)

new_text = pattern.sub('', text)
with open('/Users/dremotha/Projects/Temp/true-tech-hack-2026/backend/open_webui/utils/middleware.py', 'w') as f:
    f.write(new_text)
