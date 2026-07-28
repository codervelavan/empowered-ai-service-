# EmpowerED AI Service — what you have, and how to start it

## 1. What actually happened, in plain terms

You gave me an API key starting `sk-or-v1-...`. That prefix means
**OpenRouter**, not OpenAI — a different company that resells access to many
AI models (including some free ones) through an OpenAI-compatible API. I
tested it directly before touching any code, confirmed it's real and has
free-tier quota, and wired it in as an alternate provider.

Along the way I found a **second key already sitting in this repo**
(`sk-proj-...`, a genuine OpenAI key from an earlier session) — it's valid
but has **$0 billing quota**, so it can't make any real calls right now. Both
keys are recorded in `fastapi_app`'s `.env.local` (gitignored, never
committed) so you can switch back to real OpenAI the moment that key has
billing enabled — just remove the `OPENAI_BASE_URL` line.

I also discovered this repo now contains **two separate AI service
implementations** that were built in different sessions:

| | `src/` (TypeScript/Express) | `fastapi_app/` (Python/FastAPI+Celery) |
|---|---|---|
| Built | Earlier session | Later session, per a "migrate to FastAPI" plan |
| Per-source detail | Rich — real scores, repo stats, etc. per source | Thin — one generic `summary` string per source, no scoring |
| Async job handling | Fire-and-forget, no retry | Celery + Redis, retries with backoff |
| Status | Not currently running | **This is what I enabled and tested** |

The `.env.example` in this repo had already been rewritten to match the
FastAPI shape, which is the signal I used to enable that one rather than the
older TypeScript one — but you have both, and only one is live right now.

**A bug I found and fixed:** the FastAPI code labeled successful source
lookups as `"available"`. The Portal's database only accepts
`verified` / `partial` / `unavailable` for that field — so every real
evaluation was silently failing to save (`invalid input value for enum`)
until I fixed it. I proved this by actually running a real evaluation,
watching it fail, reading the exact Postgres error, and fixing the two
places (`evaluation.py`, `schemas.py`) that used the wrong value.

## 2. What's verified working right now (I tested each step for real)

1. ✅ Service boots: `docker compose -f docker-compose.fastapi.yml up -d --build`
2. ✅ `GET /health` → Redis connected, OpenAI-compatible client configured
3. ✅ `POST /evaluate/exam` (synchronous) → real OpenRouter call → valid
   structured JSON verdict, in under 2 seconds
4. ✅ `POST /evaluate/candidate` (async via Celery) → real GitHub API call →
   two real OpenRouter calls (per-source + consolidation) → **a real row
   landed in the Portal's Postgres `ai_evaluation_reports` table**

## 3. Known gap, honestly: the evaluations are currently thin

The FastAPI version's GitHub/LinkedIn/LeetCode/résumé "analysis" is one
generic summary sentence — no numeric scores, no repo quality breakdown, no
consistency score, etc. The `src/` TypeScript service I built earlier does
all of that in real depth. Right now, a real evaluation looks like this
(actual output from my test just now):

```
overall_score: 0.00
hiring_recommendation: "Needs Review"
final_summary: "Insufficient data provided to conduct a meaningful candidate
  assessment. The candidate has a verified GitHub profile with 8 public
  repositories, but no qualitative data or quantitative scores are available..."
```

It's not broken — it's honestly reporting "not enough detail to score
this" — but it won't produce a useful hiring signal until the specialist
reports carry real scoring fields. That's a real next step, not something I
did today; flagging it so it doesn't surprise you later.

## 4. Model choice — one more thing worth knowing

Not every free OpenRouter model actually obeys the strict JSON schema this
service requires. I tested several live:

| Model | Result |
|---|---|
| `openai/gpt-oss-20b:free` | Returns markdown prose instead of JSON — silently ignores the schema |
| `google/gemma-4-26b-a4b-it:free` | ✅ Complies correctly (currently configured) |
| `nvidia/nemotron-3-super-120b-a12b:free` | ✅ Complies, slightly odd wording |
| `nvidia/nemotron-nano-9b-v2:free` | Listed as compliant by OpenRouter but untested |

If you ever swap the model in `.env.local`, re-test it the same way before
trusting it — a model that returns 200 with prose instead of JSON is exactly
the failure mode that silently corrupted the old n8n pipeline this replaces.

---

## 5. Simple way to start everything

You have four independent pieces. Each is its own repo/folder with its own
start command. Order matters a little (Portal before form/AI service, since
they call it).

### One-time setup (already done, just documenting it)
- `deploy/staging/.env.staging` (Portal) has your real Google SMTP, campaign
  scan config, and `FRAPPE_*` pointing at your local Frappe bench.
- `fastapi_app/.env.local` (AI service) has your OpenRouter key.
- Neither file is committed to git — both are gitignored.

### Start the Portal (API + web + Postgres + MariaDB + Mailpit)
```bash
cd "C:\Users\Senthilvelaven\OneDrive\Desktop\uu\empowered"
docker compose --env-file deploy/staging/.env.staging -f deploy/staging/docker-compose.staging.yml up -d
```
- Portal API: http://localhost:4000 (or `http://192.168.0.8:4000` on the LAN)
- Portal/admin UI: http://localhost:3000
- Check it's healthy: `curl http://localhost:4000/api/health`

### Start the candidate registration form
```bash
cd "C:\Users\Senthilvelaven\OneDrive\Desktop\form-engine"
docker compose --env-file deploy/staging/.env.staging -f deploy/staging/docker-compose.staging.yml up -d
```
- Form: http://localhost:3001/forms/candidate-registration

### Start local Frappe (if not already running)
This runs directly in WSL, not Docker — check first with:
```bash
wsl -d Ubuntu-24.04 -e bash -lc 'ps aux | grep bench_helper | grep -v grep'
```
If nothing's listed, start it from the bench's `sites` directory:
```bash
wsl -d Ubuntu-24.04
cd ~/Development/empowered-dev-bench-py314/sites
nohup ../env/bin/python -m frappe.utils.bench_helper frappe serve --port 8001 --noreload > /tmp/frappe-web.log 2>&1 &
nohup ../env/bin/python -m frappe.utils.bench_helper frappe worker --queue short,default,long > /tmp/frappe-worker.log 2>&1 &
```

### Start the AI service (what we just enabled)
```bash
cd "C:\Users\Senthilvelaven\OneDrive\Desktop\empowered-ai-service"
docker compose -f docker-compose.fastapi.yml up -d
```
- AI service: http://localhost:8000
- Check it's healthy: `curl http://localhost:8000/health`

### To actually use the AI service in a real candidate run
Right now the Portal doesn't call it automatically — that switch
(`AI_SERVICE_ENABLED=true` + `AI_SERVICE_BASE_URL`/`AI_SERVICE_TOKEN` in
`.env.staging`) hasn't been flipped yet. Say the word if you want me to wire
that up and run one real candidate through the whole thing (QR → form →
Portal → AI evaluation → Frappe/Moodle → email → login).

### Checking what's running
```bash
docker ps --format "table {{.Names}}\t{{.Status}}"
```
You should see `staging-*` (Portal), `staging-form-1` (form), and
`empowered-ai-service-*` (AI service) containers, plus the two WSL Frappe
processes if you started them.

### Stopping everything
```bash
cd "C:\Users\Senthilvelaven\OneDrive\Desktop\uu\empowered" && docker compose -f deploy/staging/docker-compose.staging.yml down
cd "C:\Users\Senthilvelaven\OneDrive\Desktop\form-engine" && docker compose -f deploy/staging/docker-compose.staging.yml down
cd "C:\Users\Senthilvelaven\OneDrive\Desktop\empowered-ai-service" && docker compose -f docker-compose.fastapi.yml down
```
(Frappe in WSL: find the PIDs from `ps aux | grep bench_helper` and `kill` them.)
