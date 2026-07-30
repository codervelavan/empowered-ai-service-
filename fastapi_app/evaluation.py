import hashlib
import json
import asyncio
import time
from datetime import datetime

import httpx
from openai import OpenAI

from .config import settings
from .schemas import CandidateDossier, CandidateEvaluationRequest, ExamEvaluationRequest, ExamVerdict, SpecialistReport, VerificationFlag


def _client() -> OpenAI:
    return OpenAI(api_key=settings().openai_api_key)


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


async def specialist_reports(request: CandidateEvaluationRequest) -> dict[str, dict]:
    github, linkedin, leetcode = await asyncio.gather(
        github_report(request.github),
        asyncio.sleep(0, result=_unavailable("LinkedIn", "no approved read API configured")),
        asyncio.sleep(0, result=_unavailable("LeetCode", "source adapter unavailable")),
    )
    reports = {"github": github, "linkedin": linkedin, "leetcode": leetcode}
    reports["resume"] = _unavailable("Résumé", "resumeText not supplied") if not request.resumeText else {"source_status": "verified", "summary": request.resumeText[:3000], "strengths": [], "risks": [], "recommendations": [], "score": None}
    return reports


def _json_completion(system: str, user: str, schema: type[CandidateDossier] | type[ExamVerdict] | type[SpecialistReport], model: str):
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


async def evaluate_candidate(request: CandidateEvaluationRequest) -> dict:
    if settings().ai_provider == "fake":
        return {"run_id": request.runId or hashlib.sha256(request.candidateId.encode()).hexdigest()[:24], "candidate_id": request.candidateId, **_fake_candidate(request), "source_reports": {}}
    reports = await specialist_reports(request)
    # github_report() already computed real, deterministic GitHub stats
    # (public_repos, total_stars, top_languages, etc.) — the enrichment step
    # below re-generates reports[name] from the generic SpecialistReport
    # schema (which only has source_status/summary/strengths/risks/
    # recommendations/score), so without this it would silently discard
    # those stats. Captured here, re-merged after enrichment.
    _github_stats = {
        k: v for k, v in reports.get("github", {}).items()
        if k not in {"source_status", "summary", "strengths", "risks", "recommendations", "score", "handle_invalid"}
    }
    enrichable = [name for name, report in reports.items() if report.get("source_status") == "verified"]
    if enrichable:
        enriched = await asyncio.gather(*[
            asyncio.to_thread(
                _json_completion,
                "Return only a grounded source report. Do not infer facts not present in the source data.",
                json.dumps({"source": name, "report": reports[name]}, default=str),
                SpecialistReport,
                settings().openai_specialist_model,
            ) for name in enrichable
        ])
        reports.update({name: report.model_dump() for name, report in zip(enrichable, enriched)})
    if "github" in reports and _github_stats:
        # The Portal's github_reports table reads `github_score`, not the
        # generic SpecialistReport `score` field the enrichment step above
        # fills in — rename here rather than adding a duplicate field to a
        # schema shared by every other source.
        reports["github"]["github_score"] = reports["github"].pop("score", None)
        reports["github"].update(_github_stats)
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
