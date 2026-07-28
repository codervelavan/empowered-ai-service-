import hashlib
import json
import asyncio

import httpx
from openai import OpenAI

from .config import settings
from .schemas import CandidateDossier, CandidateEvaluationRequest, ExamEvaluationRequest, ExamVerdict, SpecialistReport


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
            response.raise_for_status()
            data = response.json()
        return {"source_status": "verified", "summary": f"{data.get('public_repos', 0)} public repositories", "strengths": [], "risks": [], "recommendations": [], "score": None}
    except Exception:
        return _unavailable("GitHub", "source lookup failed")


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
    return schema.model_validate_json(response.output_text)


async def evaluate_candidate(request: CandidateEvaluationRequest) -> dict:
    if settings().ai_provider == "fake":
        return {"run_id": request.runId or hashlib.sha256(request.candidateId.encode()).hexdigest()[:24], "candidate_id": request.candidateId, **_fake_candidate(request), "source_reports": {}}
    reports = await specialist_reports(request)
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
    dossier = _json_completion(
        "Return only JSON matching the requested dossier schema. Ground claims in the supplied reports; mark unavailable sources as unavailable.",
        json.dumps({"candidate": request.model_dump(exclude={"resumeText"}), "reports": reports}, default=str),
        CandidateDossier,
        settings().openai_consolidation_model,
    )
    run_id = request.runId or hashlib.sha256(request.candidateId.encode()).hexdigest()[:24]
    return {"run_id": run_id, "candidate_id": request.candidateId, **dossier.model_dump(), "source_reports": reports}


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
