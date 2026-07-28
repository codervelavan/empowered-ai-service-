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


class CandidateDossier(BaseModel):
    model_config = ConfigDict(extra="forbid")
    overall_score: NonNegativeFloat = Field(le=100)
    confidence_score: NonNegativeFloat = Field(le=100)
    hiring_recommendation: Literal["Strong Hire", "Hire", "Needs Interview", "Needs Review", "Do Not Proceed"]
    final_summary: str = Field(default="", max_length=5000)
    top_strengths: list[str] = Field(default_factory=list, max_length=20)
    top_concerns: list[str] = Field(default_factory=list, max_length=20)
    recommended_roles: list[str] = Field(default_factory=list, max_length=20)


class SpecialistReport(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_status: Literal["available", "unavailable"]
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
