"""Pydantic request/response schemas for the FactMesh API."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


# ── Document schemas ──────────────────────────────────────────────

class DocumentOut(BaseModel):
    id: UUID
    filename: str
    uploaded_at: datetime
    page_count: int | None
    status: str
    sha256: str
    fact_count: int | None = None
    issue_count: int | None = None

    model_config = {"from_attributes": True}


class DocumentDetail(DocumentOut):
    fact_count: int = 0
    issue_count: int = 0
    relationship_count: int = 0


# ── Fact schemas ──────────────────────────────────────────────────

class FactOut(BaseModel):
    id: UUID
    document_id: UUID
    page_number: int
    fact_type: str
    entity: str | None
    metric: str | None
    value: str | None
    normalized_value: float | None
    unit: str | None
    time_period: str | None
    scope: str | None
    evidence_quote: str
    confidence: float
    attributes: dict | None = None
    created_at: datetime
    document_filename: str | None = None

    model_config = {"from_attributes": True}


class FactDetail(FactOut):
    relationships: list["RelationshipOut"] = []


# ── Relationship schemas ──────────────────────────────────────────

class RelationshipOut(BaseModel):
    id: UUID
    fact_a_id: UUID
    fact_b_id: UUID
    relationship_type: str
    reasoning: str
    confidence: float
    created_at: datetime
    fact_a: FactOut | None = None
    fact_b: FactOut | None = None

    model_config = {"from_attributes": True}


# ── Extraction Issue schemas ──────────────────────────────────────

class IssueOut(BaseModel):
    id: UUID
    document_id: UUID
    page_number: int | None
    issue_type: str
    raw_text_snippet: str | None
    detail: str | None
    created_at: datetime
    document_filename: str | None = None

    model_config = {"from_attributes": True}


# ── Upload response ──────────────────────────────────────────────

class UploadResponse(BaseModel):
    document_id: UUID
    message: str
    status: str


class ErrorResponse(BaseModel):
    detail: str


# Rebuild forward refs
FactDetail.model_rebuild()
