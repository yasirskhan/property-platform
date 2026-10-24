"""Bounded operator-key rotation progress; no secret material or tax PII."""
from pydantic import BaseModel, Field


class TaxRotationIn(BaseModel):
    after_profile_id: int = Field(default=0, ge=0)
    after_document_id: int = Field(default=0, ge=0)
    limit: int = Field(default=5, ge=1, le=10)


class TaxRotationOut(BaseModel):
    profiles_rewrapped: int
    documents_rewrapped: int
    next_profile_id: int
    next_document_id: int
    more_profiles: bool
    more_documents: bool
