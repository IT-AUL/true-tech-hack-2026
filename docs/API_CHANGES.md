# API Changes — GPTHub Fork

This document tracks new and modified API endpoints introduced in our fork.
All team members must update this file **before** implementing new endpoints.

## Conventions

- All new endpoints go under `/api/v1/` prefix
- Request/response format follows the existing Open WebUI patterns (JSON, snake_case)
- Authentication: `Authorization: Bearer <token>` (same as base Open WebUI)

---

## New Endpoints

### POST /api/v1/route

Auto-detect the task type and select the best model.

**Request:**
```json
{
  "messages": [
    {
      "role": "user",
      "content": "Нарисуй кота в шляпе"
    }
  ],
  "attachments": [
    {
      "type": "image|audio|file|url",
      "url": "...",
      "name": "photo.jpg"
    }
  ]
}
```

**Response:**
```json
{
  "recommended_model": "gpt-4o",
  "task_type": "image_generation",
  "confidence": 0.92,
  "reasoning": "User requested image generation based on keyword analysis"
}
```

**Task type values:** `text`, `vision`, `audio_transcription`, `image_generation`, `web_parsing`, `file_analysis`

---

### GET /api/v1/memories/context

Retrieve user memory context relevant to the current conversation.

**Query params:**
- `chat_id` (optional) — scope to specific chat
- `query` (optional) — semantic search query
- `limit` (optional, default 5) — max memories to return

**Response:**
```json
{
  "memories": [
    {
      "id": "mem_abc123",
      "content": "User prefers responses in Russian",
      "created_at": "2026-04-10T12:00:00Z",
      "relevance_score": 0.95
    }
  ]
}
```

---

## Modified Endpoints

### POST /api/chat/completions

**Changes:** Added optional `auto_route` field in the request body.

When `auto_route: true`, the backend will automatically select the appropriate model
based on message content and attachments, overriding the `model` field.

```json
{
  "model": "auto",
  "auto_route": true,
  "messages": [...],
  "stream": true
}
```

The response includes an additional `x-selected-model` header indicating which model was used.

**Failover (auto / `auto_route`):** If the upstream provider returns an error that matches configured retry rules (HTTP status and/or response body substrings), the backend tries the next model from the same ranked candidate list (same scoring as the initial pick), up to `AUTO_ROUTE_FAILOVER_MAX` attempts total. WebSocket status events may include `action: auto_routing_failover` on subsequent attempts.

**Environment (backend):**

| Variable | Default | Purpose |
|----------|---------|---------|
| `AUTO_ROUTE_FAILOVER_MAX` | `15` | Max models to try per request (ranked list capped to this length). After scored picks, vision/image_gen/audio_gen include **all** catalog models of that modality so failover can move across providers. |
| `AUTO_ROUTE_FAILOVER_HTTP_STATUSES` | `400,404,408,429,502,503,504` | Comma-separated HTTP statuses that trigger a retry when using auto-route. |
| `AUTO_ROUTE_FAILOVER_BODY_SUBSTRINGS` | `no available providers`, … | Comma-separated substrings (case-insensitive); only used with **400** responses to trigger retry when the body matches. |

**Auto-route classifier context (backend):** Routing uses the **last user message** plus a **prior transcript** (user/assistant turns before it, truncated) so short follow-ups (e.g. «да» after a request to generate an image) can resolve to the correct task type. The LLM classifier receives this transcript; rules/regex can match keywords in `prior + last` when the last turn is short (see `ROUTER_SHORT_MESSAGE_LEN`). Routing cache keys include a hash of the prior transcript and, when present, `metadata.chat_id` + `metadata.message_id` to avoid cross-chat collisions.

**Routing priority:** production auto-route now treats regex as a **guardrail / fallback**, not the primary classifier for every short prompt. The pipeline is effectively:
- exact guardrails first (image attachment -> `vision`, explicit image/audio generation intent, code blocks, document overrides)
- semantic embeddings and/or LLM classifier for ordinary ambiguous/short requests
- regex fallback only when the higher-level stages are unavailable or inconclusive

**Small-talk short-circuit:** the old blanket `text_len <= 50` behavior was narrowed. Only genuine no-context greetings / acknowledgements (`привет`, `ок`, `спасибо`, `yes`, `thanks`, etc.) short-circuit to `fallback`. Short but intentful prompts like «сделай логотип», «хочу картинку котика», `make me an image` still go through semantic / LLM routing.

**Image generation handoff:** when auto-route resolves to `image_gen`, `/api/chat/completions` now uses the real image-generation flow instead of sending the chosen image model to `/chat/completions`. The selected image model is forwarded into `image_generations(...)`, image files are emitted back to the chat, and `image_gen` failover stays inside image models only.

**Attachments:** `metadata.files` from the chat request is merged only into the **latest** user message when building multimodal content for auto-route. Previously it was applied to every user message in `messages`, which could inject images into a new text-only turn (e.g. «Привет») and force **vision** routing. Very short text-only turns with no prior transcript use a **trivial** fast path to `fallback` (no LLM/embeddings) to avoid modality misclassification. **Audio/video attachments alone** no longer route the turn to **audio_gen** (music APIs); intent for music/sound generation still comes from explicit keywords in the user text (see `PATTERNS['audio_gen']` in `auto_routing.py`).

**Failover list:** Image/audio *generation* models (Flux, Lyria, …) are excluded from non-generation routes (`fallback`, `vision`, `code`, …) using both registry `kind` and keyword inference on id/name, so mislabeled `text` entries in the catalog cannot appear in the auto-route retry chain for ordinary chat.

| Variable | Default | Purpose |
|----------|---------|---------|
| `ROUTER_CONTEXT_MAX_MESSAGES` | `8` | Max prior user/assistant messages to include in the routing transcript (before the last user turn). |
| `ROUTER_CONTEXT_MAX_CHARS` | `3000` | Max characters of that transcript (suffix preserved if truncated). |
| `ROUTER_SHORT_MESSAGE_LEN` | `24` | If the last user text is at most this many characters and a prior transcript exists, regex/rules and semantic query use **transcript + last message** for pattern matching and embeddings. |
| `ROUTER_DISABLE_ROUTING_CACHE` | unset | If `true`/`1`/`yes`, routing decisions are not read from or written to the in-process TTL cache (useful for debugging). |

**Offline eval:** `backend/open_webui/test/fixtures/auto_route_eval.jsonl` holds deterministic scenarios (rules + regex only). Run `scripts/eval_auto_routing.py` with `PYTHONPATH=backend` and backend deps installed, or `pytest backend/open_webui/test/util/test_auto_routing.py::test_auto_route_eval_jsonl`.

---

## Changelog

| Date | Author | Change |
|------|--------|--------|
| 2026-04-14 | Team | Auto-route: dialog context for classifier, improved routing cache key, `ROUTER_CONTEXT_*` / `ROUTER_SHORT_MESSAGE_LEN` / `ROUTER_DISABLE_ROUTING_CACHE`; JSONL eval fixture + script. |
| 2026-04-14 | Team | Auto-route: voice/video attachments no longer map to music generation (`audio_gen`); image_gen regex extended for «сгенерируй изображение» and «generate an image». |
| 2026-04-14 | Team | Auto-route priority reworked: only true small-talk short-circuits early; semantic/LLM stages run before regex fallback for ordinary short prompts; status payload now includes fallback/candidate metadata. |
| 2026-04-14 | Team | Auto-route `image_gen` now executes the actual image generation path and no longer fails over into text models. |
| 2026-04-14 | Team | Auto-route upstream failover for `POST /api/chat/completions` (`AUTO_ROUTE_FAILOVER_*` env vars). |
| 2026-04-10 | Team | Initial API design |
