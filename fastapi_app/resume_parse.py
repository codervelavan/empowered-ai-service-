from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ResumeParseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    resumeText: str = Field(min_length=20, max_length=100_000)


class ResumeParseFields(BaseModel):
    model_config = ConfigDict(extra="forbid")
    firstName: str | None = Field(default=None, max_length=60)
    lastName: str | None = Field(default=None, max_length=60)
    email: str | None = Field(default=None, max_length=254)
    countryCode: str | None = Field(default=None, max_length=8)
    mobileNumber: str | None = Field(default=None, max_length=20)
    dateOfBirth: str | None = Field(default=None, max_length=20)
    gender: str | None = Field(default=None, max_length=30)
    country: str | None = Field(default=None, max_length=80)
    state: str | None = Field(default=None, max_length=80)
    city: str | None = Field(default=None, max_length=80)
    highestQualification: str | None = Field(default=None, max_length=80)
    isWorkingProfessional: bool | None = None
    college: str | None = Field(default=None, max_length=120)
    university: str | None = Field(default=None, max_length=120)
    branch: str | None = Field(default=None, max_length=120)
    graduationYear: int | None = Field(default=None, ge=1980, le=2100)
    cgpa: float | None = Field(default=None, ge=0, le=10)
    company: str | None = Field(default=None, max_length=120)
    designation: str | None = Field(default=None, max_length=120)
    yearsOfExperience: float | None = Field(default=None, ge=0, le=50)
    skills: list[str] = Field(default_factory=list, max_length=40)
    languagesKnown: list[str] = Field(default_factory=list, max_length=20)
    certifications: list[str] = Field(default_factory=list, max_length=40)
    technologies: list[str] = Field(default_factory=list, max_length=40)
    githubUrl: str | None = Field(default=None, max_length=240)
    linkedinUrl: str | None = Field(default=None, max_length=240)
    websiteUrl: str | None = Field(default=None, max_length=240)
    leetcodeUrl: str | None = Field(default=None, max_length=240)
    hackerrankUrl: str | None = Field(default=None, max_length=240)


class ResumeParseConfidence(BaseModel):
    model_config = ConfigDict(extra="forbid")
    firstName: Literal["high", "low"] | None = None
    lastName: Literal["high", "low"] | None = None
    email: Literal["high", "low"] | None = None
    countryCode: Literal["high", "low"] | None = None
    mobileNumber: Literal["high", "low"] | None = None
    dateOfBirth: Literal["high", "low"] | None = None
    gender: Literal["high", "low"] | None = None
    country: Literal["high", "low"] | None = None
    state: Literal["high", "low"] | None = None
    city: Literal["high", "low"] | None = None
    highestQualification: Literal["high", "low"] | None = None
    isWorkingProfessional: Literal["high", "low"] | None = None
    college: Literal["high", "low"] | None = None
    university: Literal["high", "low"] | None = None
    branch: Literal["high", "low"] | None = None
    graduationYear: Literal["high", "low"] | None = None
    cgpa: Literal["high", "low"] | None = None
    company: Literal["high", "low"] | None = None
    designation: Literal["high", "low"] | None = None
    yearsOfExperience: Literal["high", "low"] | None = None
    skills: Literal["high", "low"] | None = None
    languagesKnown: Literal["high", "low"] | None = None
    certifications: Literal["high", "low"] | None = None
    technologies: Literal["high", "low"] | None = None
    githubUrl: Literal["high", "low"] | None = None
    linkedinUrl: Literal["high", "low"] | None = None
    websiteUrl: Literal["high", "low"] | None = None
    leetcodeUrl: Literal["high", "low"] | None = None
    hackerrankUrl: Literal["high", "low"] | None = None


class ResumeParseResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    fields: ResumeParseFields
    confidence: ResumeParseConfidence
