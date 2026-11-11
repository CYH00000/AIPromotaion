# -*- coding: utf-8 -*-
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1; see LICENSE.

from fastapi import APIRouter, Depends, HTTPException, status

from api.schemas.filter_rules import FilterRuleDraftRequest, FilterRuleView
from api.services.auth_service import require_admin, require_csrf
from api.services.filter_model_client import (
    FilterModelError,
    generate_filter_definition,
    model_configuration,
    public_model_status,
)
from database.collector_database import collector_session
from database.collector_models import CollectionFilterRule, new_id, utc_now


router = APIRouter(dependencies=[Depends(require_admin)], tags=["filter-rules"])


def _rule_view(rule: CollectionFilterRule) -> dict:
    return {
        "id": rule.id,
        "lineage_id": rule.lineage_id,
        "version": rule.version,
        "parent_rule_id": rule.parent_rule_id,
        "intent": rule.intent,
        "definition": rule.definition,
        "model_name": rule.model_name,
        "status": rule.status,
        "created_at": rule.created_at,
        "approved_at": rule.approved_at,
    }


@router.get("/filter-rules/config")
async def get_filter_model_status():
    """Expose whether server-side model configuration exists, never its secret values."""
    return public_model_status()


@router.post(
    "/filter-rules/drafts",
    response_model=FilterRuleView,
    status_code=status.HTTP_201_CREATED,
)
async def create_filter_rule_draft(
    payload: FilterRuleDraftRequest,
    _csrf: None = Depends(require_csrf),
):
    config = model_configuration()
    if not config["configured"]:
        raise HTTPException(status_code=503, detail="AI model is not configured on the server.")
    try:
        definition = await generate_filter_definition(payload.intent)
    except FilterModelError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    async with collector_session() as session:
        previous = None
        version = 1
        lineage_id = None
        if payload.supersedes_rule_id:
            previous = await session.get(CollectionFilterRule, payload.supersedes_rule_id)
            if previous is None:
                raise HTTPException(status_code=404, detail="Previous filter rule not found.")
            version = previous.version + 1
            lineage_id = previous.lineage_id
        rule = CollectionFilterRule(
            lineage_id=lineage_id or new_id(),
            version=version,
            parent_rule_id=previous.id if previous else None,
            intent=payload.intent,
            definition=definition.model_dump(mode="json"),
            model_name=config["model_name"],
            status="draft",
        )
        session.add(rule)
        await session.flush()
        return _rule_view(rule)


@router.get("/filter-rules/{rule_id}", response_model=FilterRuleView)
async def get_filter_rule(rule_id: str):
    async with collector_session() as session:
        rule = await session.get(CollectionFilterRule, rule_id)
        if rule is None:
            raise HTTPException(status_code=404, detail="Filter rule not found.")
        return _rule_view(rule)


@router.post("/filter-rules/{rule_id}/approve", response_model=FilterRuleView)
async def approve_filter_rule(rule_id: str, _csrf: None = Depends(require_csrf)):
    async with collector_session() as session:
        rule = await session.get(CollectionFilterRule, rule_id)
        if rule is None:
            raise HTTPException(status_code=404, detail="Filter rule not found.")
        if rule.status == "draft":
            rule.status = "approved"
            rule.approved_at = utc_now()
        return _rule_view(rule)
