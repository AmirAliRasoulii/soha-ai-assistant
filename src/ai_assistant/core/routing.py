"""Deterministic routing policy for the bounded fast document flow."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from ai_assistant.contracts import (
    CapabilityName,
    EvidenceNeed,
    QueryAnalysis,
    RiskLevel,
    RouteBudget,
    RouteDecision,
)
from ai_assistant.core.types import AuthorizedRuntimeContext

ROUTING_POLICY_VERSION = "1.0.0"
DOCUMENT_CAPABILITY: CapabilityName = "document_retrieval"
DOCUMENT_EVIDENCE_NEED: EvidenceNeed = "document"
DOCUMENT_FACT_ID = "fact.document"
FAST_DOCUMENT_ROUTE = "fast.document"
CLARIFY_ROUTE = "clarify.ambiguous_query"
ABSTAIN_ROUTE = "abstain.unsupported_flow"
SINGLE_DOCUMENT_RATIONALE = "query.single_document_need"
CLARIFICATION_RATIONALE = "query.requires_clarification"
UNSUPPORTED_FLOW_RATIONALE = "query.unsupported_flow"
UNRESOLVED_RISK_RATIONALE = "risk.not_eligible_for_fast"

_FAST_BUDGET = RouteBudget(
    max_steps=1,
    max_parallel_steps=1,
    max_replans=0,
    max_retrieval_retries=0,
    max_analytics_repairs=0,
    max_answer_repairs=0,
)
_TERMINAL_BUDGET = RouteBudget(
    max_steps=0,
    max_parallel_steps=0,
    max_replans=0,
    max_retrieval_retries=0,
    max_analytics_repairs=0,
    max_answer_repairs=0,
)


def _require_analysis_binding(context: AuthorizedRuntimeContext, analysis: QueryAnalysis) -> None:
    turn_input = context.runtime.turn_input
    if analysis.request_id != turn_input.request_id:
        raise ValueError("query analysis request_id must match the runtime context")
    if analysis.message_id != turn_input.message_id:
        raise ValueError("query analysis message_id must match the runtime context")
    if analysis.runtime_snapshot_id != context.runtime.runtime_snapshot.snapshot_id:
        raise ValueError("query analysis runtime_snapshot_id must match the runtime context")


def _effective_risk_level(analysis: QueryAnalysis) -> RiskLevel:
    # Confidence is deliberately absent here: it never influences risk, denial,
    # capability allowlisting, or lane selection.
    if analysis.risk_level == "normal" and not analysis.risk_signals:
        return "normal"
    if analysis.risk_level == "high":
        return "high"
    return "unknown"


def _is_supported_fast_shape(analysis: QueryAnalysis, effective_risk: RiskLevel) -> bool:
    return (
        analysis.intent == "factual"
        and analysis.evidence_needs == (DOCUMENT_EVIDENCE_NEED,)
        and analysis.ambiguity_level == "none"
        and not analysis.is_personal
        and not analysis.is_multi_part
        and effective_risk == "normal"
    )


def _terminal_decision(
    context: AuthorizedRuntimeContext,
    analysis: QueryAnalysis,
    *,
    decision_id: UUID,
    decided_at: datetime,
    effective_risk: RiskLevel,
    lane: Literal["clarify", "abstain"],
    route: str,
    rationale_code: str,
) -> RouteDecision:
    return RouteDecision(
        decision_id=decision_id,
        request_id=context.runtime.turn_input.request_id,
        query_analysis_id=analysis.analysis_id,
        authorization_decision_id=context.authorization.decision_id,
        runtime_snapshot_id=context.runtime.runtime_snapshot.snapshot_id,
        decided_at=decided_at,
        effective_risk_level=effective_risk,
        lane=lane,
        route=route,
        allowed_capabilities=(),
        required_facts=(),
        planner_required=False,
        filters=(),
        budget=_TERMINAL_BUDGET,
        rationale_code=rationale_code,
        policy_version=ROUTING_POLICY_VERSION,
        approved_flow_ref=None,
    )


def route_query(
    context: AuthorizedRuntimeContext,
    analysis: QueryAnalysis,
    *,
    decision_id: UUID,
    decided_at: datetime,
) -> RouteDecision:
    """Derive the deterministic route for one already authorized turn."""
    _require_analysis_binding(context, analysis)
    effective_risk = _effective_risk_level(analysis)
    if analysis.ambiguity_level != "none":
        return _terminal_decision(
            context,
            analysis,
            decision_id=decision_id,
            decided_at=decided_at,
            effective_risk=effective_risk,
            lane="clarify",
            route=CLARIFY_ROUTE,
            rationale_code=CLARIFICATION_RATIONALE,
        )
    if not _is_supported_fast_shape(analysis, effective_risk):
        unsupported_shape = effective_risk == "normal"
        return _terminal_decision(
            context,
            analysis,
            decision_id=decision_id,
            decided_at=decided_at,
            effective_risk=effective_risk,
            lane="abstain",
            route=ABSTAIN_ROUTE,
            rationale_code=(
                UNSUPPORTED_FLOW_RATIONALE if unsupported_shape else UNRESOLVED_RISK_RATIONALE
            ),
        )
    return RouteDecision(
        decision_id=decision_id,
        request_id=context.runtime.turn_input.request_id,
        query_analysis_id=analysis.analysis_id,
        authorization_decision_id=context.authorization.decision_id,
        runtime_snapshot_id=context.runtime.runtime_snapshot.snapshot_id,
        decided_at=decided_at,
        effective_risk_level="normal",
        lane="fast",
        route=FAST_DOCUMENT_ROUTE,
        allowed_capabilities=(DOCUMENT_CAPABILITY,),
        required_facts=(DOCUMENT_FACT_ID,),
        planner_required=False,
        filters=(),
        budget=_FAST_BUDGET,
        rationale_code=SINGLE_DOCUMENT_RATIONALE,
        policy_version=ROUTING_POLICY_VERSION,
        approved_flow_ref=None,
    )
