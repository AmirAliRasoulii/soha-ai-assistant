"""Typed configurable fakes and builders for the WS-004A finalization tests."""

import asyncio
from datetime import datetime
from uuid import UUID

from ai_assistant.contracts import (
    AnswerPlan,
    Evidence,
    EvidenceBundle,
    EvidenceDecision,
    EvidenceSecurityScope,
    EvidenceSourceRef,
    EvidenceSourceTime,
    EvidenceSubjectRef,
    EvidenceType,
    EvidenceValidityWindow,
    FactEvidenceMapEntry,
    RejectedEvidenceRef,
    RuleEvidence,
    SelectorEvidence,
    WebEvidence,
)
from ai_assistant.core.answer_planning import build_answer_plan
from ai_assistant.core.finalization import (
    CitationSourceResolutionRequest,
    FinalizationArtifacts,
    RenderedAnswerDraft,
    RenderedAnswerItem,
    RenderedAnswerSection,
    RenderRequest,
    ResolvedCitationSource,
)
from ai_assistant.core.runtime import OrchestrationResult, OrchestrationStatus
from ai_assistant.core.terminal_runtime import (
    TerminalCoordinationResult,
    TerminalCoordinationStatus,
)
from ai_assistant.core.types import EffectiveIdempotencyKey, IdempotencyLease
from support.walking_skeleton_fixtures import (
    ANSWER_PLAN_ID,
    AUTHORIZATION_ID,
    BUNDLE_ID,
    CORRELATION_ID,
    DEPLOYMENT_ID,
    DOCUMENT_FACT_ID,
    EVIDENCE_ID,
    HEX_DIGEST,
    IDEMPOTENCY_KEY,
    NOW,
    PLAN_ID,
    PRINCIPAL_ID,
    REQUEST_ID,
    ROUTE_DECISION_ID,
    SNAPSHOT_DIGEST,
    SNAPSHOT_ID,
    allowed_claim,
    authorization,
    authorized_context,
    document_evidence,
    evidence_bundle,
    evidence_provenance,
    execution_plan,
    query_analysis,
    route_decision,
    step_result,
)
from support.walking_skeleton_runtime_fakes import _BlockingFake
from support.walking_skeleton_terminal_fakes import effective_key, lease

CLAIM_TEXT = "Sentinel rendered claim text."
CAVEAT_TEXT = "Sentinel rendered caveat text."
DISPLAY_LABEL = "Document store"
# These must match the source binding of support.walking_skeleton_fixtures'
# document_evidence() exactly: a resolved source is validated against the
# real accepted Evidence record, never against display_label alone.
SOURCE_TYPE = "document_store"
SOURCE_REF = "store:main"
SOURCE_VERSION = "1"
SECURITY_SCOPE_REF = "scope:general"
LOCATOR_REF = "locator:1"
FOREIGN_SOURCE_TYPE = "document_store_other_department"
FOREIGN_SOURCE_REF = "store:other-department"
FOREIGN_SOURCE_VERSION = "999"
FOREIGN_SECURITY_SCOPE_REF = "scope:other-department"
FOREIGN_LOCATOR_REF = "locator:other-department"


# WS-004A-R3: contract-valid non-document evidence used to prove the
# fast.document canonical flow rejects foreign evidence subtypes outright,
# even when every other root identifier lines up with the canonical turn.
def web_evidence(*, evidence_id: UUID) -> WebEvidence:
    return WebEvidence(
        evidence_id=evidence_id,
        subject=EvidenceSubjectRef(subject_type="document", subject_ref="subject:web-1"),
        valid_time=EvidenceValidityWindow(as_of=NOW),
        source_time=EvidenceSourceTime(observed_at=NOW),
        source=EvidenceSourceRef(
            source_type="official_search_index",
            source_ref="index:web-1",
            source_version="1",
        ),
        authority="authority.internal",
        security_scope=EvidenceSecurityScope(
            scope_ref="scope:general",
            data_scope="general",
            classification="classification.internal",
        ),
        validation_status="validated",
        freshness="current",
        provenance=evidence_provenance(capability="official_search", operation="search.query"),
        allowed_uses=("use.answer",),
        retention_class="retention.standard",
        supports_fact_ids=(DOCUMENT_FACT_ID,),
        page_ref="page:web-1",
        allowlist_ref="allowlist:official",
        locator_ref=FOREIGN_LOCATOR_REF,
        content_ref="content:web-1",
        content_sha256=HEX_DIGEST,
    )


def selector_evidence(*, evidence_id: UUID) -> SelectorEvidence:
    return SelectorEvidence(
        evidence_id=evidence_id,
        subject=EvidenceSubjectRef(subject_type="document", subject_ref="subject:selector-1"),
        valid_time=EvidenceValidityWindow(as_of=NOW),
        source_time=EvidenceSourceTime(observed_at=NOW),
        source=EvidenceSourceRef(
            source_type="personal_selector_store",
            source_ref="selector:1",
            source_version="1",
        ),
        authority="authority.internal",
        security_scope=EvidenceSecurityScope(
            scope_ref="scope:personal",
            data_scope="personal",
            classification="classification.internal",
        ),
        validation_status="validated",
        freshness="current",
        provenance=evidence_provenance(capability="personal_selector", operation="selector.run"),
        allowed_uses=("use.answer",),
        retention_class="retention.standard",
        supports_fact_ids=(DOCUMENT_FACT_ID,),
        selector_ref="selector:query-1",
        result_ref="result:selector-1",
        result_sha256=HEX_DIGEST,
        field_codes=("field.name",),
    )


def rule_evidence(*, evidence_id: UUID, input_evidence_ids: tuple[UUID, ...]) -> RuleEvidence:
    return RuleEvidence(
        evidence_id=evidence_id,
        subject=EvidenceSubjectRef(subject_type="document", subject_ref="subject:rule-1"),
        valid_time=EvidenceValidityWindow(as_of=NOW),
        source_time=EvidenceSourceTime(observed_at=NOW),
        source=EvidenceSourceRef(
            source_type="rule_engine",
            source_ref="engine:main",
            source_version="1",
        ),
        authority="authority.internal",
        security_scope=EvidenceSecurityScope(
            scope_ref="scope:general",
            data_scope="general",
            classification="classification.internal",
        ),
        validation_status="validated",
        freshness="current",
        provenance=evidence_provenance(capability="rule_evaluator", operation="rule.evaluate"),
        allowed_uses=("use.answer",),
        retention_class="retention.standard",
        supports_fact_ids=(DOCUMENT_FACT_ID,),
        rule_bundle_ref="bundle:rules-1",
        rule_code="rule.eligibility",
        rule_version="1.0.0",
        outcome_ref="outcome:rule-1",
        outcome_sha256=HEX_DIGEST,
        input_evidence_ids=input_evidence_ids,
    )


def foreign_capability_bundle(evidence: Evidence) -> EvidenceBundle:
    """Build an otherwise-canonical bundle whose accepted evidence is foreign.

    Every root identifier matches the canonical fast.document turn exactly;
    only the accepted evidence subtype is not DocumentEvidence. This proves
    the preflight check rejects a foreign evidence subtype on its own merits,
    not because some other lineage binding already failed.
    """
    return EvidenceBundle(
        bundle_id=BUNDLE_ID,
        request_id=REQUEST_ID,
        route_decision_id=ROUTE_DECISION_ID,
        plan_id=PLAN_ID,
        authorization_decision_id=AUTHORIZATION_ID,
        runtime_snapshot_id=SNAPSHOT_ID,
        correlation_id=CORRELATION_ID,
        built_at=NOW,
        required_fact_ids=(DOCUMENT_FACT_ID,),
        accepted_evidence=(evidence,),
        rejected_evidence=(),
        fact_map=(
            FactEvidenceMapEntry(fact_id=DOCUMENT_FACT_ID, evidence_ids=(evidence.evidence_id,)),
        ),
        missing_fact_ids=(),
        conflicts=(),
        sufficient=True,
        decision="answer",
        allowed_claims=(allowed_claim(evidence_ids=(evidence.evidence_id,)),),
        prohibited_claims=(),
        decision_reason_codes=("evidence.complete",),
        evidence_manager_version="1.0.0",
    )


def rule_evidence_bundle() -> EvidenceBundle:
    """Build a contract-valid bundle whose accepted evidence includes both a
    real DocumentEvidence and a RuleEvidence that references it as an input.

    Every root identifier matches the canonical fast.document turn exactly.
    RuleEvidence.input_evidence_ids must reference evidence accepted in the
    same bundle, so a real DocumentEvidence is included alongside it and the
    fact map/allowed claim reflect every declared support from both accepted
    records. This proves the preflight check rejects the bundle because it
    contains a non-DocumentEvidence item, not because some other contract or
    lineage binding already failed.
    """
    document = document_evidence()
    rule = rule_evidence(
        evidence_id=FOREIGN_EVIDENCE_ID,
        input_evidence_ids=(document.evidence_id,),
    )
    accepted: tuple[Evidence, ...] = (document, rule)
    mapped_ids = tuple(item.evidence_id for item in accepted)
    return EvidenceBundle(
        bundle_id=BUNDLE_ID,
        request_id=REQUEST_ID,
        route_decision_id=ROUTE_DECISION_ID,
        plan_id=PLAN_ID,
        authorization_decision_id=AUTHORIZATION_ID,
        runtime_snapshot_id=SNAPSHOT_ID,
        correlation_id=CORRELATION_ID,
        built_at=NOW,
        required_fact_ids=(DOCUMENT_FACT_ID,),
        accepted_evidence=accepted,
        rejected_evidence=(),
        fact_map=(FactEvidenceMapEntry(fact_id=DOCUMENT_FACT_ID, evidence_ids=mapped_ids),),
        missing_fact_ids=(),
        conflicts=(),
        sufficient=True,
        decision="answer",
        allowed_claims=(allowed_claim(evidence_ids=mapped_ids),),
        prohibited_claims=(),
        decision_reason_codes=("evidence.complete",),
        evidence_manager_version="1.0.0",
    )


def foreign_typed_rejected_bundle() -> EvidenceBundle:
    """Build a canonical bundle whose rejected evidence declares a foreign type.

    Proves the preflight check inspects declared evidence_type on rejected
    entries too, not only isinstance checks on accepted evidence.
    """
    accepted = (document_evidence(),)
    return EvidenceBundle(
        bundle_id=BUNDLE_ID,
        request_id=REQUEST_ID,
        route_decision_id=ROUTE_DECISION_ID,
        plan_id=PLAN_ID,
        authorization_decision_id=AUTHORIZATION_ID,
        runtime_snapshot_id=SNAPSHOT_ID,
        correlation_id=CORRELATION_ID,
        built_at=NOW,
        required_fact_ids=(DOCUMENT_FACT_ID,),
        accepted_evidence=accepted,
        rejected_evidence=(
            RejectedEvidenceRef(
                evidence_id=FOREIGN_EVIDENCE_ID,
                evidence_type="web",
                reason_codes=("evidence.excluded",),
            ),
        ),
        fact_map=(FactEvidenceMapEntry(fact_id=DOCUMENT_FACT_ID, evidence_ids=(EVIDENCE_ID,)),),
        missing_fact_ids=(),
        conflicts=(),
        sufficient=True,
        decision="answer",
        allowed_claims=(allowed_claim(),),
        prohibited_claims=(),
        decision_reason_codes=("evidence.complete",),
        evidence_manager_version="1.0.0",
    )


def finalization_identifier(index: int) -> UUID:
    """Return a deterministic version 4 UUID reserved for finalization tests."""
    return UUID(f"{index:08d}-0000-4000-8000-000000000000")


FINAL_ANSWER_ID = finalization_identifier(50)
CITATION_ID = finalization_identifier(51)
FAILURE_DETAIL_REF = finalization_identifier(52)
SECOND_CITATION_ID = finalization_identifier(53)
FOREIGN_EVIDENCE_ID = finalization_identifier(54)
ABSTAIN_PLAN_ID = finalization_identifier(55)
NON_UUID4 = UUID("00000056-0000-1000-8000-000000000000")

FOREIGN_DEPLOYMENT_ID = finalization_identifier(60)
FOREIGN_PRINCIPAL_ID = finalization_identifier(61)
FOREIGN_CLIENT_KEY = finalization_identifier(62)
FOREIGN_SNAPSHOT_ID = finalization_identifier(63)
FOREIGN_SNAPSHOT_DIGEST = "sha256:" + "b" * 64


def expected_key() -> EffectiveIdempotencyKey:
    """Build the effective key the terminal runtime derives for the fixtures."""
    return effective_key(
        deployment_id=str(DEPLOYMENT_ID),
        principal_id=str(PRINCIPAL_ID),
        client_key=str(IDEMPOTENCY_KEY),
        runtime_snapshot_id=str(SNAPSHOT_ID),
        runtime_snapshot_digest=SNAPSHOT_DIGEST,
    )


def mismatched_key(
    *,
    deployment_id: UUID = DEPLOYMENT_ID,
    principal_id: UUID = PRINCIPAL_ID,
    client_key: UUID = IDEMPOTENCY_KEY,
    runtime_snapshot_id: UUID = SNAPSHOT_ID,
    runtime_snapshot_digest: str = SNAPSHOT_DIGEST,
) -> EffectiveIdempotencyKey:
    """Build an effective key, overriding exactly the components under test.

    Used to prove independent mismatches (deployment, principal, client key,
    snapshot id, snapshot digest) are each individually rejected.
    """
    return effective_key(
        deployment_id=str(deployment_id),
        principal_id=str(principal_id),
        client_key=str(client_key),
        runtime_snapshot_id=str(runtime_snapshot_id),
        runtime_snapshot_digest=runtime_snapshot_digest,
    )


def acquired_lease(key: EffectiveIdempotencyKey | None = None) -> IdempotencyLease:
    return lease(key if key is not None else expected_key())


def planned_answer(
    *,
    decision: EvidenceDecision = "answer",
    answer_plan_id: UUID | None = None,
) -> AnswerPlan:
    """Build the canonical AnswerPlan through the trusted WS-002 builder."""
    bundle = evidence_bundle(decision=decision)
    identifier = answer_plan_id
    if identifier is None:
        identifier = ANSWER_PLAN_ID if decision == "answer" else ABSTAIN_PLAN_ID
    return build_answer_plan(
        authorized_context(),
        query_analysis(),
        route_decision(),
        execution_plan(),
        bundle,
        answer_plan_id=identifier,
        built_at=NOW,
    )


def completed_result(
    *,
    answer_plan: AnswerPlan | None = None,
    bundle: EvidenceBundle | None = None,
    decision: EvidenceDecision = "answer",
) -> OrchestrationResult:
    """Build a completed orchestration result carrying every turn artifact."""
    return OrchestrationResult(
        status=OrchestrationStatus.COMPLETED,
        authorization=authorization(),
        route_decision=route_decision(),
        execution_plan=execution_plan(),
        step_result=step_result(),
        evidence_bundle=bundle if bundle is not None else evidence_bundle(decision=decision),
        answer_plan=answer_plan if answer_plan is not None else planned_answer(decision=decision),
    )


def pending_finalization(
    *,
    result: OrchestrationResult | None = None,
    decision: EvidenceDecision = "answer",
    effective_key_override: EffectiveIdempotencyKey | None = None,
    lease_key_override: EffectiveIdempotencyKey | None = None,
) -> TerminalCoordinationResult:
    """Build the pending finalization coordination result under test.

    effective_key_override and lease_key_override let adversarial tests bind
    pending.effective_key and pending.lease.key independently of each other
    and independently of the current RuntimeContext under test.
    """
    key = expected_key()
    return TerminalCoordinationResult(
        status=TerminalCoordinationStatus.PENDING_FINALIZATION,
        effective_key=effective_key_override if effective_key_override is not None else key,
        lease=lease(lease_key_override if lease_key_override is not None else key),
        orchestration_result=result if result is not None else completed_result(decision=decision),
    )


def artifacts(
    *,
    citation_ids: tuple[UUID, ...] = (CITATION_ID,),
    final_answer_id: UUID = FINAL_ANSWER_ID,
    failure_internal_detail_ref: UUID = FAILURE_DETAIL_REF,
    finalized_at: datetime = NOW,
) -> FinalizationArtifacts:
    return FinalizationArtifacts(
        final_answer_id=final_answer_id,
        citation_ids=citation_ids,
        failure_internal_detail_ref=failure_internal_detail_ref,
        finalized_at=finalized_at,
    )


def rendered_text_for(item_kind: str) -> str:
    return CLAIM_TEXT if item_kind == "claim" else CAVEAT_TEXT


def faithful_draft(answer_plan: AnswerPlan) -> RenderedAnswerDraft:
    """Render the plan exactly, as a well behaved renderer adapter would."""
    sections = tuple(
        RenderedAnswerSection(
            section_id=section.section_id,
            items=tuple(
                RenderedAnswerItem(
                    item_kind=item.item_kind,
                    item_id=item.item_id,
                    rendered_text=rendered_text_for(item.item_kind),
                )
                for item in section.items
            ),
        )
        for section in answer_plan.sections
    )
    return RenderedAnswerDraft(answer_plan_id=answer_plan.answer_plan_id, sections=sections)


def resolved_source(
    *,
    evidence_id: UUID = EVIDENCE_ID,
    evidence_type: EvidenceType = "document",
    source_type: str = SOURCE_TYPE,
    source_ref: str = SOURCE_REF,
    source_version: str = SOURCE_VERSION,
    security_scope_ref: str = SECURITY_SCOPE_REF,
    locator_ref: str = LOCATOR_REF,
    display_label: str = DISPLAY_LABEL,
) -> ResolvedCitationSource:
    """Build a resolved source that binds exactly to the fixture's real evidence.

    Callers override individual source-binding fields (never evidence_id or
    evidence_type alone) to prove that a foreign source_type, source_ref,
    source_version, security_scope_ref, or locator_ref is rejected even when
    evidence_id and evidence_type still match.
    """
    return ResolvedCitationSource(
        evidence_id=evidence_id,
        evidence_type=evidence_type,
        source_type=source_type,
        source_ref=source_ref,
        source_version=source_version,
        security_scope_ref=security_scope_ref,
        locator_ref=locator_ref,
        display_label=display_label,
    )


class AnswerRendererFake(_BlockingFake):
    """Configurable AnswerRendererPort double."""

    def __init__(
        self,
        *,
        draft: RenderedAnswerDraft | None = None,
        result: object | None = None,
        error: Exception | None = None,
        started: asyncio.Event | None = None,
        gate: asyncio.Event | None = None,
    ) -> None:
        super().__init__(started=started, gate=gate)
        self.draft = draft
        self.result = result
        self.error = error
        self.calls = 0
        self.requests: tuple[RenderRequest, ...] = ()

    async def render(self, request: RenderRequest) -> RenderedAnswerDraft:
        self.calls += 1
        self.requests = (*self.requests, request)
        await self._pause()
        if self.error is not None:
            raise self.error
        if self.result is not None:
            # Deliberately untyped: proves runtime isinstance validation of an
            # untrusted port return value, independent of any raised exception.
            return self.result  # type: ignore[return-value]
        if self.draft is None:
            raise ValueError("the renderer fake requires a configured draft")
        return self.draft


class CitationSourceResolverFake(_BlockingFake):
    """Configurable CitationSourceResolverPort double."""

    def __init__(
        self,
        *,
        sources: tuple[ResolvedCitationSource, ...] = (),
        result: object | None = None,
        use_result: bool = False,
        error: Exception | None = None,
        started: asyncio.Event | None = None,
        gate: asyncio.Event | None = None,
    ) -> None:
        super().__init__(started=started, gate=gate)
        self.sources = sources
        self.result = result
        self.use_result = use_result
        self.error = error
        self.calls = 0
        self.requests: tuple[CitationSourceResolutionRequest, ...] = ()

    async def resolve(
        self,
        request: CitationSourceResolutionRequest,
    ) -> tuple[ResolvedCitationSource, ...]:
        self.calls += 1
        self.requests = (*self.requests, request)
        await self._pause()
        if self.error is not None:
            raise self.error
        if self.use_result:
            # Deliberately untyped: proves runtime isinstance validation of an
            # untrusted port return value, independent of any raised exception.
            return self.result  # type: ignore[return-value]
        return self.sources
