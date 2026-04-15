#!/usr/bin/env python3
"""
Offline evaluation for auto-route deterministic stages (rules + regex).

Reports:
  - Per-row pass/fail
  - Per-category precision / recall / F1
  - Confusion matrix
  - Overall accuracy

Run from repo root:
  PYTHONPATH=backend python scripts/eval_auto_routing.py [fixture.jsonl]

Or via pytest:
  pytest backend/open_webui/test/util/test_auto_routing.py::test_auto_route_eval_jsonl -q
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT / 'backend') not in sys.path:
    sys.path.insert(0, str(_ROOT / 'backend'))


def _f1(p: float, r: float) -> float:
    return 2 * p * r / (p + r) if (p + r) > 0 else 0.0


def main() -> int:
    parser = argparse.ArgumentParser(description='Evaluate auto_route_eval JSONL fixtures')
    parser.add_argument(
        'fixture',
        nargs='?',
        default=str(_ROOT / 'backend/open_webui/test/fixtures/auto_route_eval.jsonl'),
        help='Path to JSONL file',
    )
    parser.add_argument('--verbose', '-v', action='store_true', help='Show every row')
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

    # confusion[expected][predicted] = count
    confusion: dict[str, Counter] = defaultdict(Counter)
    # For precision/recall
    tp: Counter = Counter()
    fp: Counter = Counter()
    fn: Counter = Counter()
    method_counts: Counter = Counter()

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
            confusion[expected][got] += 1
            method_counts[d.method] += 1

            if got == expected:
                ok += 1
                tp[expected] += 1
            else:
                fp[got] += 1
                fn[expected] += 1
            rows.append((eid, expected, got, d.method))

    # --- Summary ---
    accuracy = ok / total if total else 0
    print(f'\n=== Auto-Routing Eval: {ok}/{total} passed ({accuracy:.1%}) ===\n')

    # --- Per-row details (failures always, all rows with --verbose) ---
    failures = [(eid, exp, got, m) for eid, exp, got, m in rows if exp != got]
    if failures:
        print(f'--- Failures ({len(failures)}) ---')
        for eid, expected, got, method in failures:
            print(f'  [FAIL] {eid}: expected={expected} got={got} ({method})')
        print()

    if args.verbose:
        print('--- All rows ---')
        for eid, expected, got, method in rows:
            mark = 'OK' if expected == got else 'FAIL'
            print(f'  [{mark}] {eid}: expected={expected} got={got} ({method})')
        print()

    # --- Per-category precision / recall / F1 ---
    all_cats = sorted(set(list(tp.keys()) + list(fp.keys()) + list(fn.keys())))
    print('--- Per-Category Metrics ---')
    print(f'{"Category":<16} {"Prec":>6} {"Recall":>6} {"F1":>6} {"TP":>4} {"FP":>4} {"FN":>4}')
    print('-' * 60)
    macro_p, macro_r, macro_f1 = 0.0, 0.0, 0.0
    for cat in all_cats:
        t = tp[cat]
        f_p = fp[cat]
        f_n = fn[cat]
        precision = t / (t + f_p) if (t + f_p) > 0 else 0.0
        recall = t / (t + f_n) if (t + f_n) > 0 else 0.0
        f1 = _f1(precision, recall)
        macro_p += precision
        macro_r += recall
        macro_f1 += f1
        print(f'{cat:<16} {precision:>6.1%} {recall:>6.1%} {f1:>6.1%} {t:>4} {f_p:>4} {f_n:>4}')

    n_cats = len(all_cats) or 1
    print('-' * 60)
    print(f'{"Macro avg":<16} {macro_p/n_cats:>6.1%} {macro_r/n_cats:>6.1%} {macro_f1/n_cats:>6.1%}')
    print()

    # --- Confusion Matrix ---
    print('--- Confusion Matrix (rows=expected, cols=predicted) ---')
    pred_cats = sorted(set(g for row_cats in confusion.values() for g in row_cats))
    header = f'{"":>16} ' + ' '.join(f'{c[:8]:>8}' for c in pred_cats)
    print(header)
    for expected_cat in sorted(confusion.keys()):
        vals = ' '.join(f'{confusion[expected_cat][p]:>8}' for p in pred_cats)
        print(f'{expected_cat:>16} {vals}')
    print()

    # --- Method distribution ---
    print('--- Method Distribution ---')
    for method, count in method_counts.most_common():
        print(f'  {method}: {count}')
    print()

    return 0 if ok == total else 1


if __name__ == '__main__':
    raise SystemExit(main())
