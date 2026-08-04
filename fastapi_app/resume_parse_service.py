import json

from .config import settings
from .evaluation import _json_completion
from .resume_parse import ResumeParseConfidence, ResumeParseFields, ResumeParseResult


def parse_resume_text(resume_text: str) -> dict:
    if settings().ai_provider == "fake":
        return ResumeParseResult(
            fields=ResumeParseFields(),
            confidence=ResumeParseConfidence(),
        ).model_dump()

    system = (
        "Extract candidate registration fields from the résumé text. Return only JSON matching "
        "the schema. Use null for any field not clearly present — never guess. "
        "For each non-null field, set matching confidence to 'high' if explicitly stated, "
        "'low' if inferred. Do NOT set preferredIndustry or preferredDomain — the candidate "
        "chooses those manually. Extract languagesKnown as spoken/written language names "
        "when a Languages section exists. mobileNumber should be digits only (no country code). "
        "countryCode like '+91' when phone country is clear. graduationYear and cgpa as numbers."
    )
    result = _json_completion(
        system,
        json.dumps({"resumeText": resume_text[:50_000]}),
        ResumeParseResult,
        settings().openai_specialist_model,
    )
    return {
        "fields": {k: v for k, v in result.fields.model_dump().items() if v is not None and v != []},
        "confidence": {k: v for k, v in result.confidence.model_dump().items() if v is not None},
    }
