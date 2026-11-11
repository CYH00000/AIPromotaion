# -*- coding: utf-8 -*-
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1; see LICENSE.

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class FilterRuleDefinition(BaseModel):
    """Allowlisted, human-readable semantic criteria returned by the model."""

    model_config = ConfigDict(extra="forbid")

    summary: str = Field(min_length=1, max_length=400)
    required_signals: list[str] = Field(default_factory=list, max_length=8)
    positive_signals: list[str] = Field(min_length=1, max_length=8)
    negative_signals: list[str] = Field(default_factory=list, max_length=8)

    @field_validator("summary")
    @classmethod
    def clean_summary(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Rule summary must not be empty")
        return cleaned

    @field_validator("required_signals", "positive_signals", "negative_signals")
    @classmethod
    def clean_signals(cls, values: list[str]) -> list[str]:
        cleaned = [value.strip() for value in values if value.strip()]
        if len(cleaned) != len(values):
            raise ValueError("Rule signals must be non-empty")
        return cleaned


class FilterRuleDraftRequest(BaseModel):
    intent: str = Field(min_length=1, max_length=2000)
    supersedes_rule_id: str | None = Field(default=None, max_length=36)

    @field_validator("intent")
    @classmethod
    def clean_intent(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Describe the comments you want to match")
        return cleaned


class FilterRuleView(BaseModel):
    id: str
    lineage_id: str
    version: int
    parent_rule_id: str | None
    intent: str
    definition: FilterRuleDefinition
    model_name: str
    status: Literal["draft", "approved"]
    created_at: datetime
    approved_at: datetime | None


class FilterRulePreview(BaseModel):
    configured: bool
    model_name: str | None


class SemanticDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    index: int = Field(ge=0)
    matched: bool
    reason: str = Field(min_length=1, max_length=240)

    @field_validator("reason")
    @classmethod
    def clean_reason(cls, value: str) -> str:
        return value.strip()


class SemanticDecisionBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decisions: list[SemanticDecision] = Field(max_length=20)
