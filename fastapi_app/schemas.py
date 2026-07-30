from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, NonNegativeFloat


class CandidateEvaluationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    candidateId: str = Field(min_length=1, max_length=120)
    candidateName: str = Field(min_length=1, max_length=160)
    email: str = Field(min_length=3, max_length=254)
    runId: str | None = Field(default=None, min_length=1, max_length=160)
    domain: str | None = Field(default=None, max_length=120)
    college: str | None = Field(default=None, max_length=240)
    cgpa: NonNegativeFloat | None = Field(default=None, le=10)
    github: str | None = Field(default=None, max_length=240)
    linkedin: str | None = Field(default=None, max_length=240)
    leetcode: str | None = Field(default=None, max_length=240)
    resumeText: str | None = Field(default=None, max_length=100_000)


class ExamEvaluationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    candidateName: str = Field(min_length=1, max_length=160)
    score: NonNegativeFloat = Field(le=100)


class VerificationFlag(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # "github_handle_invalid" is set deterministically in Python (evaluation.py)
    # from the actual GitHub API response, never by the model. Everything else
    # (e.g. "cgpa_mismatch", "college_mismatch") is model-derived from
    # cross-checking the claimed fields against résumé text and is advisory —
    # never used to gate admission or enrollment. See VERIFICATION FLAGS in
    # evaluation.py's system prompt for what "confident" means here.
    code: str = Field(min_length=1, max_length=60)
    severity: Literal["info", "warning", "critical"]
    claimed: str = Field(default="", max_length=240)
    observed: str = Field(default="", max_length=240)
    detail: str = Field(default="", max_length=500)


class CandidateDossier(BaseModel):
    model_config = ConfigDict(extra="forbid")
    overall_score: NonNegativeFloat = Field(le=100)
    confidence_score: NonNegativeFloat = Field(le=100)
    hiring_recommendation: Literal["Strong Hire", "Hire", "Needs Interview", "Needs Review", "Do Not Proceed"]
    final_summary: str = Field(default="", max_length=5000)
    top_strengths: list[str] = Field(default_factory=list, max_length=20)
    top_concerns: list[str] = Field(default_factory=list, max_length=20)
    recommended_roles: list[str] = Field(default_factory=list, max_length=20)
    verification_flags: list[VerificationFlag] = Field(default_factory=list, max_length=20)
    # Cross-source category scores shown on the Portal's Candidate Deep-Dive
    # "Technical" tab. Deliberately no salary_expectation_fit_score field —
    # the registration form no longer collects any salary expectation, so
    # there is nothing to ground that score in (see PROJECT_MANAGER.md).
    academic_score: NonNegativeFloat | None = Field(default=None, le=100)
    domain_alignment_score: NonNegativeFloat | None = Field(default=None, le=100)
    professional_presence_score: NonNegativeFloat | None = Field(default=None, le=100)
    engineering_score: NonNegativeFloat | None = Field(default=None, le=100)
    coding_assessment_score: NonNegativeFloat | None = Field(default=None, le=100)


class SpecialistReport(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # Must match the Portal's source_status DB enum exactly (db/schema.sql):
    # verified | partial | unavailable. "available" (the prior value here)
    # isn't a member -- every enriched specialist report failed
    # ai_evaluation_reports' enum constraint until this was caught live.
    source_status: Literal["verified", "partial", "unavailable"]
    summary: str = Field(default="", max_length=5000)
    strengths: list[str] = Field(default_factory=list, max_length=20)
    risks: list[str] = Field(default_factory=list, max_length=20)
    recommendations: list[str] = Field(default_factory=list, max_length=20)
    score: NonNegativeFloat | None = Field(default=None, le=100)


class ExamVerdict(BaseModel):
    model_config = ConfigDict(extra="forbid")
    verdict: str = Field(default="", max_length=3000)
    recommendation: str = Field(default="", max_length=1000)
    strengths: list[str] = Field(default_factory=list, max_length=20)
    concerns: list[str] = Field(default_factory=list, max_length=20)
