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

---

## Changelog

| Date | Author | Change |
|------|--------|--------|
| 2026-04-10 | Team | Initial API design |
