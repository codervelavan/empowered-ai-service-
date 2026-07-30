# EmpowerED AI Service

A standalone service that replaces n8n's entire remaining AI footprint in
the EmpowerED candidate pipeline: the 4-agent hiring-evaluation chain
(LinkedIn/GitHub/LeetCode/Résumé → consolidated report) and the
exam-performance verdict (previously a direct Frappe→Gemini call). One
service, one LLM provider config, two callers (the Portal and the Frappe
automation app).

**This is a Python/FastAPI + Celery service (`fastapi_app/`) — the only
implementation.** An earlier TypeScript/Express implementation
(`src/`) existed briefly alongside it; once `fastapi_app/` had the same
real GitHub/LeetCode integrations ported into it (see `TUTORIAL.md`),
`src/` was retired rather than maintaining two services with one
capability.

See `architectural_plan_and_prompt.md` (referenced from this repo, kept
alongside it per `CLEANUP_REPORT.md`'s recommendation) for the full
picture of where this sits in the pipeline.

## Why a separate service, not a module in the existing Express server

- **Crash/latency isolation.** The candidate-facing registration API must
  never be slowed down or taken down by a slow model call or a flaky
  external API (GitHub, LeetCode).
- **Natural home for async orchestration.** The hiring evaluation makes
  4+ external calls plus multiple LLM calls per candidate — real
  wall-clock time, handled by Celery with retry/backoff, not something
  to run inline in a request handler.
- **One place for LLM provider config.** Frappe no longer needs its own
  Gemini/OpenAI credential at all.

## Endpoints

Both require `Authorization: Bearer <SERVICE_AUTH_TOKEN>`. Neither is ever
public-facing — only the Portal and Frappe call this service, over a
private network path.

### `POST /evaluate/candidate` — async (Celery)

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
{ "accepted": true, "jobId": "...", "status": "queued" }
```

### `POST /evaluate/exam` — synchronous

```jsonc
// request
{ "candidateName": "...", "score": 82 }
// response
{ "verdict": "...", "recommendation": "...", "strengths": [...], "concerns": [...] }
```

Called by Frappe's `empowered_automation` app's grade-poll job, replacing
its previous direct Gemini call.

## What's real vs. honest fallback

| Source | Status |
|---|---|
| GitHub | **Real** — public REST API (profile + repos), deterministic stat aggregation in code (`public_repos`/`total_stars`/`total_forks`/`top_languages`/`top_repositories`/etc.), plus a dedicated LLM call scoring 5 dimensions (`github_score`, `repo_quality_score`, `consistency_score`, `contribution_score`, `collaboration_score`, `open_source_score`). |
| LeetCode | **Real** — public GraphQL API (no auth needed), a dedicated LLM call scoring 5 dimensions (`leetcode_score`, `problem_solving_score`, `contest_score`, `consistency_score`, `dsa_depth_score`). |
| Résumé | **Partial.** Résumé text extraction is built on the Portal side (byte storage + PDF/DOCX extraction), and this service receives real `resumeText` when available — but only truncates it into a generic summary today, not the richer structured scoring (`ats_score`, `domain_fit_score`, etc.) an earlier prototype had. That richer scoring was not ported — a real future-improvement item, not a data-availability gap like LinkedIn's. |
| LinkedIn | **Always falls back, by design.** There is no compliant public API for reading an arbitrary candidate's LinkedIn profile. Not something a different LLM or more code fixes — a data-access gap. |
| Cross-source category scores | **Real** — `academic_score`, `domain_alignment_score`, `professional_presence_score`, `engineering_score`, `coding_assessment_score` are derived by the consolidation call from whichever sources have real data. No `salary_expectation_fit_score` — the Portal's registration form no longer collects any salary expectation. |
| `placement_probability` | **Deliberately never computed.** Sent as `null`, matching the Portal's own documented stance: never fabricate a number no model actually produces. |

## Setup

```bash
cp .env.example .env.local
# fill in OPENAI_API_KEY (or an OpenRouter key + OPENAI_BASE_URL),
# SERVICE_AUTH_TOKEN / PORTAL_AUTH_TOKEN / FRAPPE_AUTH_TOKEN,
# PORTAL_CALLBACK_URL / PORTAL_CALLBACK_SECRET
docker compose -f docker-compose.fastapi.yml up -d --build
curl http://localhost:8000/health
```

`GET /health` reports `{status, redis, queueConfigured, openaiConfigured,
provider}` — no auth required, safe for a load-balancer health check.

## Testing & quality gates

No test suite exists for `fastapi_app/` yet (tracked as a gap, not
hidden — see below). CI (`.github/workflows/ci.yml`) runs a compile +
import check on every push.

## Known gaps (tracked, not hidden)

- **No test suite.** `fastapi_app/` has zero automated tests. Given how
  many real bugs this pipeline has caught only by actually running it
  (a field-name/enum mismatch, a URL-vs-handle bug, a markdown-fence
  JSON-parsing bug — all found live, not by a test), this is a real gap,
  not a nice-to-have.
- **Model-compliance risk.** Not every model on OpenRouter's free tier
  reliably honors strict `json_schema` output — one confirmed case
  returned the correct JSON wrapped in a markdown code fence (now
  defended against); a model returning prose instead of any JSON at all
  would still fail every retry identically. No fallback-to-a-different-
  model exists yet.
- **Résumé scoring is thin** (see table above) — real text is available,
  but only summarized, not structurally scored.
- **LinkedIn analysis will not produce real data without a licensed data
  source** — out of scope for a code change.
