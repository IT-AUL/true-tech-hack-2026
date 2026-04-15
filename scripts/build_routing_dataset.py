#!/usr/bin/env python3
"""
Seed-based synthetic augmentation pipeline for the auto-routing eval dataset.

Generates realistic routing dataset samples by paraphrasing real seed cases
(NOT inventing new facts). Uses separate generator and judge models.

Usage:
  export GENERATOR_API_KEY=...
  export JUDGE_API_KEY=...       # optional, defaults to GENERATOR_API_KEY
  PYTHONPATH=backend python scripts/build_routing_dataset.py \
      --seeds backend/open_webui/test/fixtures/auto_route_eval.jsonl \
      --output router_dataset_augmented.jsonl \
      --target-rows 2000

Requirements:
  pip install httpx
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import os
import random
import re
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import httpx

log = logging.getLogger(__name__)

RANDOM_SEED = 42
random.seed(RANDOM_SEED)

ALLOWED_CATEGORIES = {
    'image_gen', 'audio_gen', 'vision', 'code', 'math_logic',
    'research', 'analytics', 'creative', 'document', 'fallback',
}
ALLOWED_COMPLEXITIES = {'low', 'medium', 'high'}

GENERATION_TYPES = (
    'paraphrase', 'tone_shift', 'compressed', 'expanded',
    'role_shift', 'typo_variant', 'locale_shift',
)

DEFAULT_API_BASE = 'https://api.gpt.mws.ru/v1'
DEFAULT_GENERATOR_MODEL = 'mws-gpt-alpha'
DEFAULT_JUDGE_MODEL = 'mws-gpt-alpha'


@dataclass
class SeedCase:
    id: str
    messages: list[dict[str, str]]
    expected_category: str
    expected_complexity: str = 'medium'
    signals: list[str] = field(default_factory=list)
    source: str = 'eval_fixture'


@dataclass
class SyntheticCase:
    id: str
    source_seed_id: str
    generation_type: str
    messages: list[dict[str, str]]
    expected_category: str
    expected_complexity: str = 'medium'
    signals: list[str] = field(default_factory=list)
    realism_score: float | None = None
    semantic_preservation_score: float | None = None
    quality_score: float | None = None


# ---------------------------------------------------------------------------
# LLM Client
# ---------------------------------------------------------------------------

_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0, connect=5.0),
            limits=httpx.Limits(max_connections=8, max_keepalive_connections=4),
        )
    return _client


async def call_llm(
    base_url: str,
    api_key: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.7,
    max_tokens: int = 2048,
) -> str:
    client = _get_client()
    body = {
        'model': model,
        'messages': [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': user_prompt},
        ],
        'temperature': temperature,
        'max_tokens': max_tokens,
    }
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json',
    }
    for attempt in range(3):
        try:
            resp = await client.post(f'{base_url}/chat/completions', headers=headers, json=body)
            resp.raise_for_status()
            data = resp.json()
            return data['choices'][0]['message']['content'].strip()
        except (httpx.TimeoutException, httpx.HTTPStatusError) as exc:
            if attempt < 2:
                wait = 2 ** attempt
                log.warning('LLM call failed (attempt %d): %s — retrying in %ds', attempt + 1, exc, wait)
                await asyncio.sleep(wait)
            else:
                raise


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_jsonl(path: str | Path) -> list[dict[str, Any]]:
    rows = []
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_jsonl(path: str | Path, rows: list[dict[str, Any]]) -> None:
    with open(path, 'w', encoding='utf-8') as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + '\n')


def hash_messages(messages: list[dict[str, str]]) -> str:
    s = json.dumps(messages, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(s.encode('utf-8')).hexdigest()


def last_user_message(messages: list[dict[str, str]]) -> str:
    for m in reversed(messages):
        if m.get('role') == 'user':
            c = m.get('content', '')
            if isinstance(c, str):
                return c
            if isinstance(c, list):
                return ' '.join(p.get('text', '') for p in c if isinstance(p, dict) and p.get('type') == 'text')
    return ''


def basic_schema_ok(row: dict[str, Any]) -> tuple[bool, str]:
    if row.get('expected_category') not in ALLOWED_CATEGORIES:
        return False, f'bad category: {row.get("expected_category")}'
    msgs = row.get('messages')
    if not isinstance(msgs, list) or len(msgs) == 0:
        return False, 'empty messages'
    for m in msgs:
        if not isinstance(m, dict) or 'role' not in m or 'content' not in m:
            return False, 'malformed message'
        if m['role'] not in ('user', 'assistant', 'system'):
            return False, f'bad role: {m["role"]}'
        c = m['content']
        if isinstance(c, str) and not c.strip():
            return False, 'empty content'
    return True, ''


def heuristic_filter(row: dict[str, Any]) -> str | None:
    lu = last_user_message(row.get('messages', []))
    if len(lu) < 2:
        return 'last_user_message_too_short'
    if len(lu) > 4000:
        return 'last_user_message_too_long'
    return None


def parse_json_maybe(text: str) -> Any:
    text = text.strip()
    if text.startswith('```'):
        text = re.sub(r'^```\w*\n?', '', text)
        text = re.sub(r'\n?```$', '', text)
        text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r'(\[.*\]|\{.*\})', text, re.DOTALL)
        if m:
            return json.loads(m.group(1))
        raise


# ---------------------------------------------------------------------------
# Seed Extraction
# ---------------------------------------------------------------------------

def build_seeds(raw: list[dict[str, Any]]) -> list[SeedCase]:
    seeds = []
    for r in raw:
        cat = r.get('expected_category')
        if cat not in ALLOWED_CATEGORIES:
            continue
        msgs = r.get('messages', [])
        if not msgs:
            continue
        seeds.append(SeedCase(
            id=r.get('id', f'seed_{len(seeds):05d}'),
            messages=msgs,
            expected_category=cat,
            expected_complexity=r.get('expected_complexity', 'medium'),
            signals=r.get('signals', []),
            source=r.get('source', 'eval_fixture'),
        ))
    return seeds


# ---------------------------------------------------------------------------
# Generation Prompts
# ---------------------------------------------------------------------------

GENERATION_SYSTEM = """\
You generate synthetic routing dataset samples for a multimodal AI assistant.

STRICT RULES:
1. Do NOT invent companies, numbers, facts, files, links, or context not present in the seed.
2. PRESERVE the same expected_category — this is ground truth, never change it.
3. You may ONLY vary: phrasing, tone, role, wording, length, typos, ambiguity level, follow-up style.
4. If the seed is a follow-up, keep it a follow-up with compatible history.
5. Output ONLY a valid JSON array. No markdown fences, no explanation."""

JUDGE_SYSTEM = """\
You validate synthetic routing dataset samples against their original seed.
Return ONLY a JSON object with these fields:
- semantic_preservation_score: 1-5
- realism_score: 1-5
- quality_score: 1-5
- same_category: true/false
- issues: [list of strings, empty if none]
- approved: true/false

Reject if: category drift, invented facts/files/context, unnatural wording, obvious templating."""


def generation_prompt(seed: SeedCase, n: int) -> str:
    return f"""Generate {n} realistic variants of this seed case.

Seed:
{json.dumps(asdict(seed), ensure_ascii=False, indent=2)}

Return a JSON array where each item has:
- messages (OpenAI format)
- expected_category (MUST be "{seed.expected_category}")
- expected_complexity
- generation_type (one of: {', '.join(GENERATION_TYPES)})

Constraints:
- Same category as seed
- Semantically faithful
- Realistic user language (mix of formal/informal, with occasional typos)
- No hallucinated external facts"""


def judge_prompt(seed: SeedCase, candidate: dict[str, Any]) -> str:
    return f"""Compare:

Seed:
{json.dumps(asdict(seed), ensure_ascii=False, indent=2)}

Candidate:
{json.dumps(candidate, ensure_ascii=False, indent=2)}"""


# ---------------------------------------------------------------------------
# Main Pipeline
# ---------------------------------------------------------------------------

async def generate_variants(
    seed: SeedCase, n: int,
    base_url: str, api_key: str, model: str,
) -> list[dict[str, Any]]:
    raw = await call_llm(base_url, api_key, model, GENERATION_SYSTEM, generation_prompt(seed, n), temperature=0.9)
    data = parse_json_maybe(raw)
    if not isinstance(data, list):
        raise ValueError('Generator did not return a JSON array')
    return data


async def judge_candidate(
    seed: SeedCase, candidate: dict[str, Any],
    base_url: str, api_key: str, model: str,
) -> dict[str, Any]:
    raw = await call_llm(base_url, api_key, model, JUDGE_SYSTEM, judge_prompt(seed, candidate), temperature=0.1)
    return parse_json_maybe(raw)


def dedup_exact(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out = []
    for row in rows:
        h = hash_messages(row.get('messages', []))
        if h not in seen:
            seen.add(h)
            out.append(row)
    return out


async def run_pipeline(args: argparse.Namespace) -> int:
    gen_base = args.gen_api_base or os.environ.get('GENERATOR_API_BASE', DEFAULT_API_BASE)
    gen_key = args.gen_api_key or os.environ.get('GENERATOR_API_KEY', '')
    gen_model = args.gen_model or os.environ.get('GENERATOR_MODEL', DEFAULT_GENERATOR_MODEL)

    judge_base = args.judge_api_base or os.environ.get('JUDGE_API_BASE', gen_base)
    judge_key = args.judge_api_key or os.environ.get('JUDGE_API_KEY', gen_key)
    judge_model = args.judge_model or os.environ.get('JUDGE_MODEL', DEFAULT_JUDGE_MODEL)

    if not gen_key:
        print('ERROR: No API key. Set GENERATOR_API_KEY or --gen-api-key', file=sys.stderr)
        return 1

    raw = load_jsonl(args.seeds)
    seeds = build_seeds(raw)
    if not seeds:
        print('ERROR: No valid seeds found', file=sys.stderr)
        return 1

    random.shuffle(seeds)
    target = args.target_rows

    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    aug_per_seed = max(3, min(12, target // max(len(seeds), 1)))

    print(f'Seeds: {len(seeds)}, target: {target}, aug/seed: {aug_per_seed}')
    t0 = time.monotonic()

    for si, seed in enumerate(seeds):
        if len(accepted) >= target:
            break

        try:
            variants = await generate_variants(seed, aug_per_seed, gen_base, gen_key, gen_model)
        except Exception as e:
            log.warning('Generation failed for %s: %s', seed.id, e)
            rejected.append({'source_seed_id': seed.id, 'stage': 'generation_error', 'error': str(e)})
            continue

        for cand in variants:
            cand['source_seed_id'] = seed.id

            ok, reason = basic_schema_ok(cand)
            if not ok:
                rejected.append({'source_seed_id': seed.id, 'stage': 'schema', 'reason': reason})
                continue

            hr = heuristic_filter(cand)
            if hr:
                rejected.append({'source_seed_id': seed.id, 'stage': 'heuristic', 'reason': hr})
                continue

            if cand.get('expected_category') != seed.expected_category:
                rejected.append({
                    'source_seed_id': seed.id, 'stage': 'category_drift',
                    'expected': seed.expected_category, 'got': cand.get('expected_category'),
                })
                continue

            if not args.skip_judge:
                try:
                    verdict = await judge_candidate(seed, cand, judge_base, judge_key, judge_model)
                except Exception as e:
                    log.warning('Judge failed for seed %s: %s', seed.id, e)
                    rejected.append({'source_seed_id': seed.id, 'stage': 'judge_error', 'error': str(e)})
                    continue

                cand['realism_score'] = verdict.get('realism_score')
                cand['semantic_preservation_score'] = verdict.get('semantic_preservation_score')
                cand['quality_score'] = verdict.get('quality_score')

                if not (
                    verdict.get('approved') is True
                    and verdict.get('same_category') is True
                    and verdict.get('semantic_preservation_score', 0) >= 4
                    and verdict.get('realism_score', 0) >= 4
                    and verdict.get('quality_score', 0) >= 4
                ):
                    rejected.append({'source_seed_id': seed.id, 'stage': 'judge_reject', 'verdict': verdict})
                    continue

            cand['id'] = f'syn_{len(accepted):07d}'
            accepted.append(cand)

            if len(accepted) >= target:
                break

        if (si + 1) % 10 == 0:
            elapsed = time.monotonic() - t0
            print(f'  [{si+1}/{len(seeds)}] accepted={len(accepted)} rejected={len(rejected)} ({elapsed:.0f}s)')

    accepted = dedup_exact(accepted)
    write_jsonl(args.output, accepted)

    rejects_path = args.output.replace('.jsonl', '_rejects.jsonl')
    write_jsonl(rejects_path, rejected)

    review_n = min(args.review_sample, len(accepted))
    if review_n > 0:
        review_path = args.output.replace('.jsonl', '_review.jsonl')
        review = random.sample(accepted, review_n)
        write_jsonl(review_path, review)
        print(f'Review sample: {review_path} ({review_n} rows)')

    elapsed = time.monotonic() - t0
    print(f'\nDone in {elapsed:.0f}s. Accepted={len(accepted)} Rejected={len(rejected)}')
    print(f'Output: {args.output}')
    print(f'Rejects: {rejects_path}')

    # Category distribution
    cats: dict[str, int] = {}
    for r in accepted:
        c = r.get('expected_category', '?')
        cats[c] = cats.get(c, 0) + 1
    print('\nCategory distribution:')
    for c, n in sorted(cats.items(), key=lambda x: -x[1]):
        print(f'  {c}: {n}')

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description='Build augmented routing dataset from seeds')
    parser.add_argument('--seeds', required=True, help='Path to seed JSONL (e.g. auto_route_eval.jsonl)')
    parser.add_argument('--output', default='router_dataset_augmented.jsonl', help='Output JSONL path')
    parser.add_argument('--target-rows', type=int, default=2000, help='Target number of augmented rows')
    parser.add_argument('--review-sample', type=int, default=100, help='Number of rows for human review sample')
    parser.add_argument('--skip-judge', action='store_true', help='Skip LLM judge (faster, less filtering)')
    parser.add_argument('--gen-api-base', help='Generator API base URL')
    parser.add_argument('--gen-api-key', help='Generator API key')
    parser.add_argument('--gen-model', help='Generator model ID')
    parser.add_argument('--judge-api-base', help='Judge API base URL')
    parser.add_argument('--judge-api-key', help='Judge API key')
    parser.add_argument('--judge-model', help='Judge model ID')
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    return asyncio.run(run_pipeline(args))


if __name__ == '__main__':
    raise SystemExit(main())
