"""Pydantic request models."""

from typing import Optional

from pydantic import BaseModel, Field


class AssessRequest(BaseModel):
    project_name: Optional[str] = None
    city: Optional[str] = None
    land_use: Optional[str] = None
    plot_area_m2: Optional[float] = Field(default=None, ge=0)
    floors: Optional[float] = Field(default=None, ge=0)
    building_height_m: Optional[float] = Field(default=None, ge=0)
    setback_front_m: Optional[float] = Field(default=None, ge=0)
    setback_side_m: Optional[float] = Field(default=None, ge=0)
    setback_rear_m: Optional[float] = Field(default=None, ge=0)
    coverage_ratio: Optional[float] = Field(default=None, ge=0, le=1)
    far: Optional[float] = Field(default=None, ge=0)
    parking_spaces: Optional[float] = Field(default=None, ge=0)
    units: Optional[float] = Field(default=None, ge=0)
    rule_codes: Optional[list] = None


class AssistantRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    context: Optional[dict] = None


class DesignSuggestRequest(BaseModel):
    land_use: Optional[str] = "residential"
    plot_area_m2: Optional[float] = Field(default=None, ge=0)
    floors: Optional[float] = Field(default=None, ge=0)
    coverage_ratio: Optional[float] = Field(default=None, ge=0, le=1)


class DesignByAlarrabRequest(BaseModel):
    """Project record read by the seven senior discipline agents."""

    project_name: Optional[str] = Field(default=None, max_length=200)
    city: Optional[str] = Field(default=None, max_length=100)
    office: Optional[str] = Field(default=None, max_length=200)
    land_use: Optional[str] = Field(default=None, max_length=50)
    building_type: Optional[str] = Field(default=None, max_length=50)
    plot_w: Optional[float] = Field(default=None, gt=0, le=1000)
    plot_d: Optional[float] = Field(default=None, gt=0, le=1000)
    sb_f: Optional[float] = Field(default=None, ge=0, le=100)
    sb_s: Optional[float] = Field(default=None, ge=0, le=100)
    sb_r: Optional[float] = Field(default=None, ge=0, le=100)
    floors: Optional[float] = Field(default=None, ge=1, le=60)
    floor_h: Optional[float] = Field(default=None, ge=2, le=12)
    units: Optional[float] = Field(default=None, ge=1, le=2000)
    parking: Optional[float] = Field(default=None, ge=0, le=5000)


class PermitReadinessRequest(BaseModel):
    documents: dict = Field(default_factory=dict)


class BimReviewRequest(BaseModel):
    model_info: dict = Field(default_factory=dict)


class ReportGenerateRequest(BaseModel):
    title: Optional[str] = None
    project: Optional[dict] = None
    assessment: Optional[dict] = None
    permit: Optional[dict] = None


class CandidateReview(BaseModel):
    candidate_id: str
    decision: str = ""
    clause: str = ""
    last_reviewed_date: str = ""
    confidence_level: str = ""
    validated_by: str = ""
    title_ar: Optional[str] = None
    title_en: Optional[str] = None
    category: Optional[str] = None
    check: Optional[dict] = None
    rule_suffix: Optional[str] = "001"


class CandidateReviewBatch(BaseModel):
    reviews: list = Field(default_factory=list)


class TokenRequest(BaseModel):
    email: str
    password: str
