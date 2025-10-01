"""Schemas for proxy voting endpoints."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ProxyVoteCreate(BaseModel):
    meeting_id: str = Field(..., max_length=64)
    shareholder_id: str = Field(..., max_length=36)
    ballot_choices: dict[str, str]
    submitted_by: str | None = Field(default=None, max_length=128)


class ProxyVoteRead(ProxyVoteCreate):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str


class ProxyVoteSummary(BaseModel):
    meeting_id: str
    totals: dict[str, dict[str, int]]
    total_ballots: int


__all__ = ["ProxyVoteCreate", "ProxyVoteRead", "ProxyVoteSummary"]
