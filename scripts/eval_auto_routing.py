#!/usr/bin/env python3
"""
Offline evaluation for auto-route deterministic stages (rules + regex).

Requires project dependencies (same venv as the backend). Run from repo root:

  PYTHONPATH=backend python scripts/eval_auto_routing.py [fixture.jsonl]

Or run the pytest that loads the same fixtures:

  pytest backend/open_webui/test/util/test_auto_routing.py::test_auto_route_eval_jsonl -q
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT / 'backend') not in sys.path:
    sys.path.insert(0, str(_ROOT / 'backend'))


def main() -> int:
    parser = argparse.ArgumentParser(description='Evaluate auto_route_eval JSONL fixtures')
    parser.add_argument(
        'fixture',
        nargs='?',
        default=str(_ROOT / 'backend/open_webui/test/fixtures/auto_route_eval.jsonl'),
        help='Path to JSONL file',
    )
    args = parser.parse_args()
    path = Path(args.fixture)
    if not path.is_file():
        print(f'Fixture not found: {path}', file=sys.stderr)
        return 2

    try:
        from open_webui.utils.auto_routing import evaluate_route_deterministic
    except ModuleNotFoundError as e:
        print(
            'Import failed (install backend deps / use venv). '
            f'Alternatively: pytest ...::test_auto_route_eval_jsonl. ({e})',
            file=sys.stderr,
        )
        return 2

    total = 0
    ok = 0
    rows: list[tuple[str, str, str, str]] = []

    with path.open(encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            eid = row.get('id', '?')
            expected = row['expected_category']
            payload = {'messages': row['messages']}
            d = evaluate_route_deterministic(payload)
            got = d.category
            total += 1
            if got == expected:
                ok += 1
            rows.append((eid, expected, got, d.method))

    print(f'eval_auto_routing: {ok}/{total} passed')
    for eid, expected, got, method in rows:
        mark = 'OK' if expected == got else 'FAIL'
        print(f'  [{mark}] {eid}: expected={expected} got={got} ({method})')

    return 0 if ok == total else 1


if __name__ == '__main__':
    raise SystemExit(main())
