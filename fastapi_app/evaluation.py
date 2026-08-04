import hashlib
import json
import asyncio
import time
from datetime import datetime

import httpx
from openai import OpenAI

from .config import settings
from .schemas import (
    CandidateDossier,
    CandidateEvaluationRequest,
    ExamEvaluationRequest,
    ExamVerdict,
    GithubScores,
    LeetcodeScores,
    SpecialistReport,
    VerificationFlag,
)

# LEETCODE_QUERY / github_report()'s two-endpoint fetch are ported from
# empowered-ai-service/src/services/{leetcode,github}.service.ts — the
# older, retired TypeScript implementation. Both had working, real
# integrations (LeetCode's public GraphQL API needs no auth; GitHub's
# REST API was already partially used here) that fastapi_app never had;
# porting them is why src/ is safe to delete rather than merely thin.
LEETCODE_QUERY = """
query userStats($username: String!) {
  matchedUser(username: $username) {
    username
    profile { ranking reputation }
    submitStats {
      acSubmissionNum { difficulty count }
    }
  }
  userContestRanking(username: $username) {
    rating
    globalRanking
    attendedContestsCount
  }
}"""


def _client() -> OpenAI:
    return OpenAI(api_key=settings().openai_api_key, base_url=settings().openai_base_url or None)


def _fake_candidate(request: CandidateEvaluationRequest) -> dict:
    return CandidateDossier(
        overall_score=50,
        confidence_score=0,
        hiring_recommendation="Needs Review",
        final_summary="Deterministic demo evaluation; no external model was called.",
    ).model_dump()


def _fake_exam(request: ExamEvaluationRequest) -> dict:
    passed = request.score >= 50
    return ExamVerdict(
        verdict="Demo pass" if passed else "Demo fail",
        recommendation="Proceed" if passed else "Do not proceed",
        strengths=["Deterministic demo result"] if passed else [],
        concerns=[] if passed else ["Score below demo threshold"],
    ).model_dump()


def _unavailable(source: str, reason: str) -> dict:
    return {"source_status": "unavailable", "summary": f"{source}: {reason}", "strengths": [], "risks": [], "recommendations": []}


async def github_report(username: str | None) -> dict:
    if not username:
        return _unavailable("GitHub", "username not supplied")
    headers = {"accept": "application/vnd.github+json"}
    if settings().github_token:
        headers["authorization"] = f"Bearer {settings().github_token}"
    try:
        async with httpx.AsyncClient(timeout=settings().request_timeout_seconds) as client:
            response = await client.get(f"https://api.github.com/users/{username}", headers=headers)
            if response.status_code == 404:
                # Deterministic — a real HTTP 404 from GitHub's own API, not a
                # judgment call. Distinct from other failures (timeout, rate
                # limit) which stay a plain "source lookup failed" fallback.
                report = _unavailable("GitHub", f"handle '{username}' does not exist on GitHub")
                report["handle_invalid"] = True
                return report
            response.raise_for_status()
            profile = response.json()

            repos_response = await client.get(
                f"https://api.github.com/users/{username}/repos",
                params={"sort": "pushed", "per_page": 30},
                headers=headers,
            )
            repos_response.raise_for_status()
            repos = [r for r in repos_response.json() if not r.get("fork")]
    except Exception:
        return _unavailable("GitHub", "source lookup failed")

    # Deterministic aggregates computed here, not by the model — arithmetic
    # on real data is more reliable and cheaper than asking an LLM to sum
    # (mirrors empowered-ai-service/src/services/github.service.ts's
    # analyzeGithub, the older reference implementation this was ported from).
    total_stars = sum(r.get("stargazers_count") or 0 for r in repos)
    total_forks = sum(r.get("forks_count") or 0 for r in repos)
    sizes = [r["size"] for r in repos if r.get("size")]
    avg_repo_size_kb = round(sum(sizes) / len(sizes)) if sizes else 0
    language_counts: dict[str, int] = {}
    for r in repos:
        lang = r.get("language")
        if lang:
            language_counts[lang] = language_counts.get(lang, 0) + 1
    top_languages = [lang for lang, _ in sorted(language_counts.items(), key=lambda kv: kv[1], reverse=True)[:8]]
    top_repositories = [
        {
            "name": r.get("name") or "repo",
            "url": r.get("html_url"),
            "description": r.get("description"),
            "language": r.get("language"),
            "size_kb": r.get("size"),
            "stargazers_count": r.get("stargazers_count") or 0,
            "forks_count": r.get("forks_count") or 0,
            "open_issues_count": r.get("open_issues_count") or 0,
            "repo_created_at": r.get("created_at"),
            "repo_updated_at": r.get("updated_at"),
            "repo_pushed_at": r.get("pushed_at"),
        }
        for r in sorted(repos, key=lambda r: r.get("stargazers_count") or 0, reverse=True)[:5]
    ]
    push_dates = sorted(r["pushed_at"] for r in repos if r.get("pushed_at"))
    last_activity_at = push_dates[-1] if push_dates else None
    recent_pushes_count = sum(
        1 for r in repos
        if r.get("pushed_at") and (time.time() - datetime.fromisoformat(r["pushed_at"].replace("Z", "+00:00")).timestamp()) < 90 * 86400
    )

    return {
        "source_status": "verified",
        "summary": f"{profile.get('public_repos', 0)} public repositories",
        "strengths": [], "risks": [], "recommendations": [], "score": None,
        "top_languages": top_languages,
        "public_repos": profile.get("public_repos") or 0,
        "public_gists": profile.get("public_gists") or 0,
        "followers": profile.get("followers") or 0,
        "following": profile.get("following") or 0,
        "account_created_at": profile.get("created_at"),
        "last_activity_at": last_activity_at,
        "recent_pushes_count": recent_pushes_count,
        "total_stars": total_stars,
        "total_forks": total_forks,
        "avg_repo_size_kb": avg_repo_size_kb,
        "languages_count": len(language_counts),
        "top_repositories": top_repositories,
    }


async def leetcode_report(username: str | None) -> dict:
    if not username:
        return _unavailable("LeetCode", "username not supplied")
    try:
        async with httpx.AsyncClient(timeout=settings().request_timeout_seconds) as client:
            response = await client.post(
                "https://leetcode.com/graphql",
                headers={"content-type": "application/json"},
                json={"query": LEETCODE_QUERY, "variables": {"username": username}},
            )
            response.raise_for_status()
            data = response.json().get("data") or {}
    except Exception:
        return _unavailable("LeetCode", "source lookup failed")

    matched_user = data.get("matchedUser")
    if not matched_user:
        return _unavailable("LeetCode", f"user '{username}' was not found")

    profile = matched_user.get("profile") or {}
    solved = (matched_user.get("submitStats") or {}).get("acSubmissionNum") or []
    contest = data.get("userContestRanking")

    return {
        "source_status": "verified",
        "_leetcode_grounding": {
            "ranking": profile.get("ranking"),
            "reputation": profile.get("reputation"),
            "problems_solved_by_difficulty": solved,
            "contest": contest,
        },
    }


async def specialist_reports(request: CandidateEvaluationRequest) -> dict[str, dict]:
    github, linkedin, leetcode = await asyncio.gather(
        github_report(request.github),
        asyncio.sleep(0, result=_unavailable("LinkedIn", "no approved read API configured")),
        leetcode_report(request.leetcode),
    )
    reports = {"github": github, "linkedin": linkedin, "leetcode": leetcode}
    reports["resume"] = _unavailable("Résumé", "resumeText not supplied") if not request.resumeText else {"source_status": "verified", "summary": request.resumeText[:3000], "strengths": [], "risks": [], "recommendations": [], "score": None}
    return reports


def _score_dimensions(source_name: str, grounding: dict, schema: type[GithubScores] | type[LeetcodeScores], model: str) -> dict:
    """Runs the dedicated per-dimension scoring call for GitHub/LeetCode —
    the pattern src/services/{github,leetcode}.service.ts used (a narrow
    schema of just that source's own score fields, not the generic
    SpecialistReport every other source shares). Returns a fallback
    all-null dict (source_status 'partial') on any scoring failure rather
    than raising, so one flaky LLM call doesn't fail the whole evaluation."""
    try:
        scored = _json_completion(
            f"You are a technical recruiter analyzing a {source_name} profile for a candidate "
            "onboarding pipeline. Score 0-100 for each dimension. Be concise and factual, "
            "grounded only in the data given.",
            json.dumps(grounding, default=str),
            schema,
            model,
        )
        return {"source_status": "verified", **scored.model_dump()}
    except Exception as err:
        null_fields = {k: None for k in schema.model_fields if k not in {"summary", "strengths", "risks", "recommendations"}}
        return {
            "source_status": "partial",
            "summary": f"{source_name} profile fetched but AI scoring failed: {err}",
            "strengths": [], "risks": [], "recommendations": [],
            **null_fields,
        }


def _one_completion(system: str, user: str, schema: type, model: str):
    response = _client().responses.create(
        model=model,
        input=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        text={
            "format": {
                "type": "json_schema",
                "name": schema.__name__,
                "strict": True,
                "schema": schema.model_json_schema(),
            }
        },
    )
    text = response.output_text.strip()
    # Not every model honors strict json_schema mode consistently — some
    # wrap otherwise-valid JSON in a markdown code fence despite the
    # explicit json_schema format request (confirmed live: reproducible on
    # every retry for this exact model/prompt, not a one-off). Strip it
    # rather than let a cosmetic wrapper trigger 5 retries and a dropped
    # evaluation.
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[: -3]
        text = text.strip()
    return schema.model_validate_json(text)


def _json_completion(
    system: str,
    user: str,
    schema: type[CandidateDossier] | type[ExamVerdict] | type[SpecialistReport] | type[GithubScores] | type[LeetcodeScores] | type,
    model: str,
):
    try:
        return _one_completion(system, user, schema, model)
    except Exception as primary_error:
        fallback = settings().openai_fallback_model
        # Only worth a second attempt if the fallback is actually a
        # different model — retrying the same model that just failed
        # structured-output compliance isn't a retry strategy, it's just
        # re-asking the same non-compliant model. Celery's own
        # retry/backoff (see tasks.py) already covers transient failures
        # (timeouts, rate limits) for the whole task; this is specifically
        # for "the model didn't honor the schema," a different failure class.
        if fallback == model:
            raise
        return _one_completion(system, user, schema, fallback)


async def evaluate_candidate(request: CandidateEvaluationRequest) -> dict:
    if settings().ai_provider == "fake":
        return {"run_id": request.runId or hashlib.sha256(request.candidateId.encode()).hexdigest()[:24], "candidate_id": request.candidateId, **_fake_candidate(request), "source_reports": {}}
    reports = await specialist_reports(request)

    # GitHub and LeetCode get their own dedicated 5-dimension scoring call
    # (mirroring the retired src/services/{github,leetcode}.service.ts) —
    # they're excluded from the generic SpecialistReport enrichment pass
    # below so they aren't scored twice (once narrowly, once generically)
    # and so the deterministic stats github_report() already computed
    # can't be clobbered by a schema that has no room for them.
    if reports.get("github", {}).get("source_status") == "verified":
        github_stats = {
            k: v for k, v in reports["github"].items()
            if k not in {"source_status", "summary", "strengths", "risks", "recommendations", "score"}
        }
        grounding = {
            "public_repos": reports["github"].get("public_repos"),
            "followers": reports["github"].get("followers"),
            "following": reports["github"].get("following"),
            "aggregate_stats": {
                "total_stars": reports["github"].get("total_stars"),
                "total_forks": reports["github"].get("total_forks"),
                "languages_count": reports["github"].get("languages_count"),
                "top_languages": reports["github"].get("top_languages"),
                "recent_pushes_count": reports["github"].get("recent_pushes_count"),
            },
            "top_repositories": reports["github"].get("top_repositories"),
        }
        scored = await asyncio.to_thread(_score_dimensions, "GitHub", grounding, GithubScores, settings().openai_specialist_model)
        reports["github"] = {**scored, **github_stats}  # deterministic stats always win over anything the model might echo back

    if reports.get("leetcode", {}).get("source_status") == "verified":
        grounding = reports["leetcode"].pop("_leetcode_grounding", {})
        reports["leetcode"] = await asyncio.to_thread(_score_dimensions, "LeetCode", grounding, LeetcodeScores, settings().openai_specialist_model)

    # Only linkedin/resume go through the generic pass now (linkedin is
    # always 'unavailable' by design, so this is effectively resume-only —
    # see PROJECT_MANAGER.md §9 for why linkedin has no dedicated path).
    enrichable = [
        name for name, report in reports.items()
        if name not in {"github", "leetcode"} and report.get("source_status") == "verified"
    ]
    if enrichable:
        enriched = await asyncio.gather(*[
            asyncio.to_thread(
                _json_completion,
                "Return a grounded source report. If summarizing a résumé, write a concise "
                "2-4 sentence synthesis of the candidate's background, key skills, and standout "
                "projects -- never reproduce the source text verbatim or at length. Do not infer "
                "facts not present in the source data.",
                json.dumps({"source": name, "report": reports[name]}, default=str),
                SpecialistReport,
                settings().openai_specialist_model,
            ) for name in enrichable
        ])
        reports.update({name: report.model_dump() for name, report in zip(enrichable, enriched)})
    dossier = _json_completion(
        "Return only JSON matching the requested dossier schema. Ground claims in the supplied "
        "reports; mark unavailable sources as unavailable.\n\n"
        "VERIFICATION FLAGS: the `candidate` object's cgpa/college fields are what the candidate "
        "typed themselves; reports.resume.summary (when not unavailable) is real résumé text. Add a "
        "verification_flags entry ONLY when the résumé text clearly and specifically contradicts a "
        "claimed field (e.g. résumé states a different CGPA, or a different college than claimed) — "
        "never for a field the résumé simply doesn't mention. These are advisory hints for a human "
        "reviewer, not a rejection signal, so only flag things you are genuinely confident about; "
        "when in doubt, add nothing. Use severity 'warning' for a clear factual contradiction and "
        "'info' for a minor discrepancy (e.g. rounding). Never use 'critical' — you are not "
        "authorized to make that call. Do not add a github_handle_invalid flag yourself; that one is "
        "added deterministically outside this call.\n\n"
        "CATEGORY SCORES (0-100): null means ONLY 'every source this category "
        "depends on is unavailable/absent' — never use null to express low confidence or a "
        "weak/negative signal. If even one relevant source has real data, you MUST return a "
        "number; a candidate with modest signal gets a low number (even 10-20), not null. Null "
        "and 'low score' mean different things to the reader — collapsing them loses information.\n"
        "- academic_score: depends on college/cgpa (candidate object). These are always present in "
        "this pipeline, so this should essentially never be null.\n"
        "- domain_alignment_score: depends on the candidate's domain field plus reports.github's "
        "top_languages/top_repositories and reports.resume's stated skills. Null only if github AND "
        "resume are BOTH unavailable — otherwise score the overlap you can see, even if it's weak.\n"
        "- professional_presence_score: depends on reports.github, reports.linkedin, reports.resume "
        "together. Null only if all three are unavailable. Do not penalize a source that is "
        "'unavailable' for structural reasons (e.g. LinkedIn has no read API for anyone) — score "
        "based on whichever sources ARE present, don't let an absent one drag this to null.\n"
        "- engineering_score: depends on reports.github's languages/stars/repo activity plus any "
        "technical depth mentioned in reports.resume. Null only if github AND resume are BOTH "
        "unavailable — a github profile with modest stars/activity is still real signal, score it "
        "low rather than null.\n"
        "- coding_assessment_score: depends on reports.leetcode (problem-solving/DSA signal) plus "
        "resume-stated skills. Null only if BOTH are unavailable. This is NOT the same thing as the "
        "candidate's qualifying-exam score (a separate pipeline) — do not confuse the two or infer "
        "one from the other.",
        json.dumps({"candidate": request.model_dump(exclude={"resumeText"}), "reports": reports}, default=str),
        CandidateDossier,
        settings().openai_consolidation_model,
    )
    run_id = request.runId or hashlib.sha256(request.candidateId.encode()).hexdigest()[:24]
    dumped = dossier.model_dump()

    # Deterministic flag, added outside the LLM call so it can never be
    # hallucinated away or duplicated by the model.
    if reports.get("github", {}).get("handle_invalid"):
        dumped["verification_flags"] = [
            *dumped.get("verification_flags", []),
            VerificationFlag(
                code="github_handle_invalid",
                severity="warning",
                claimed=request.github or "",
                observed="404 from GitHub API",
                detail=f"GitHub handle '{request.github}' does not resolve to a real profile.",
            ).model_dump(),
        ]

    return {"run_id": run_id, "candidate_id": request.candidateId, **dumped, "source_reports": reports}


def evaluate_exam(request: ExamEvaluationRequest) -> dict:
    if settings().ai_provider == "fake":
        return _fake_exam(request)
    verdict = _json_completion(
        "Return only JSON matching the exam verdict schema. Be concise and base the recommendation on the normalized 0-100 score.",
        request.model_dump_json(),
        ExamVerdict,
        settings().openai_consolidation_model,
    )
    return verdict.model_dump()
