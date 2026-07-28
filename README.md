# EmpowerED AI Service

A standalone service that replaces n8n's entire remaining AI footprint in
the EmpowerED candidate pipeline: the 4-agent hiring-evaluation chain
(LinkedIn/GitHub/LeetCode/Résumé → consolidated report) and the
exam-performance verdict (previously a direct Frappe→Gemini call). One
service, one LLM provider config, two callers (the Portal and the Frappe
automation app).

See the architecture plan this implements for the full picture of where
this sits in the pipeline.

## Why a separate service, not a module in the existing Express server

- **Crash/latency isolation.** The candidate-facing registration API must
  never be slowed down or taken down by a slow model call or a flaky
  external API (GitHub, LeetCode).
- **Natural home for async orchestration.** The hiring evaluation makes
  4+ external calls plus 2 LLM calls per candidate — real wall-clock time,
  not something to run inline in a request handler.
- **One place for LLM provider config.** Frappe no longer needs its own
  Gemini/OpenAI credential at all.

## Endpoints

Both require `Authorization: Bearer <SERVICE_AUTH_TOKEN>`. Neither is ever
public-facing — only the Portal and Frappe call this service, over a
private network path.

### `POST /evaluate/candidate` — async

```jsonc
// request
{
  "candidateId": "EMP-2026-000123",
  "candidateName": "...", "email": "...",
  "domain": "cloud", "college": "...", "cgpa": 8.5,
  "github": "octocat", "linkedin": "https://linkedin.com/in/...",
  "leetcode": "...", "resumeText": null
}
// response: 202 immediately; the evaluation runs in the background and is
// pushed to the Portal's existing POST /api/webhooks/ai-evaluation once done.
{ "accepted": true }
```

`resumeText` is accepted but not yet populated by any real caller — the
Portal only stores résumé metadata (filename/size), not extracted text.
Until that's built, the résumé analysis runs in an honest fallback mode
(`source_status: "unavailable"`), same as LinkedIn (no compliant profile
API exists at all).

### `POST /evaluate/exam` — synchronous

```jsonc
// request
{ "candidateName": "...", "score": 82 }
// response
{ "verdict": "...", "recommendation": "...", "strengths": [...], "concerns": [...] }
```

Called by Frappe's `empowered_automation` app's grade-poll job, replacing
its previous direct Gemini call. One model call, so the caller waits for
the response directly — same shape as before, just a different target URL.

## What's real vs. honest fallback

| Source | Status |
|---|---|
| GitHub | **Real** — public REST API (profile + repos), deterministic stat aggregation in code, one LLM call for qualitative scoring |
| LeetCode | **Real** — public GraphQL API, one LLM call for scoring |
| Résumé | **Real once résumé text exists.** Currently always falls back — the Portal doesn't extract résumé text yet. This is a data-availability gap, not a code gap; wiring real text through requires building résumé storage + extraction first. |
| LinkedIn | **Always falls back, by design.** There is no compliant public API for reading an arbitrary candidate's LinkedIn profile. Not something a different LLM or more code fixes — a data-access gap. |
| `placement_probability` | **Deliberately never computed.** Sent as `null`, matching the Portal's own documented stance: never fabricate a number no model actually produces. |

## Setup

```bash
cp .env.example .env
# fill in OPENAI_API_KEY, SERVICE_AUTH_TOKEN, PORTAL_WEBHOOK_SECRET
# (PORTAL_WEBHOOK_SECRET must equal the Portal's own WEBHOOK_SECRET)
npm install
npm run dev     # -> http://localhost:4200
```

`GET /health` reports `{status, openaiConfigured, time}` — no auth required,
safe for a load-balancer health check.

## Testing & quality gates

```bash
npm run typecheck
npm test
```

## Known gaps (tracked, not hidden)

- No retry queue if the Portal is unreachable when a hiring evaluation
  finishes — the failure is logged, not retried. Low risk today (this
  service and the Portal are expected to be co-located), worth revisiting
  before either is deployed independently.
- Résumé text extraction (see table above) is a real prerequisite, not
  optional polish, before the Résumé Agent's output means anything.
- LinkedIn analysis will not produce real data without a licensed data
  source — out of scope for a code change.
