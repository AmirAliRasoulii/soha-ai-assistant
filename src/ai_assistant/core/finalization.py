"""Trusted finalization services turning one approved AnswerPlan into a FinalAnswer."""

import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Protocol, get_args, runtime_checkable
from uuid import UUID

from ai_assistant.contracts import (
    AnswerLengthBudget,
    AnswerPlan,
    AuthorizationDecision,
    DocumentEvidence,
    DomainError,
    Evidence,
    EvidenceBundle,
    EvidenceFreshness,
    EvidenceType,
    ExecutionPlan,
    FinalAnswer,
    FinalAnswerSection,
    FinalCaveatContent,
    FinalCitation,
    FinalCitationSource,
    FinalClaimContent,
    FinalContentValidationStatus,
    FinalFreshnessNote,
    FinalGenerationMode,
    FinalOutcome,
    FinalResponseMetadata,
    FinalValidatedContent,
    RouteDecision,
    StepResult,
)
from ai_assistant.contracts.errors import ErrorCode
from ai_assistant.core.planning import _require_canonical_plan, _require_canonical_route
from ai_assistant.core.runtime import OrchestrationResult, OrchestrationStatus
from ai_assistant.core.terminal_runtime import (
    TerminalCoordinationResult,
    TerminalCoordinationStatus,
)
from ai_assistant.core.types import (
    AuthorizedRuntimeContext,
    EffectiveIdempotencyKey,
    EvidenceMaterializationRequest,
    RuntimeContext,
)

FINALIZER_VERSION = "1.0.0"
CANONICAL_ROUTE_ERROR = "finalization supports the fast.document route only"
FINALIZER_SUBJECT = "the finalizer"
# The renderer is an untrusted bounded port. Its backend is composed outside
# Core, so the generation mode is always explicitly injected by the caller: it
# is never a hard-coded production constant and it is never guessed here.
FAILED_GENERATION_MODE: FinalGenerationMode = "none"
GENERATION_MODES: tuple[FinalGenerationMode, ...] = get_args(FinalGenerationMode)
PASSED_VALIDATION: FinalContentValidationStatus = "passed"
FAILED_VALIDATION: FinalContentValidationStatus = "not_applicable"
ANSWERED_OUTCOME: FinalOutcome = "answered"
ABSTAINED_OUTCOME: FinalOutcome = "abstained"
FAILED_OUTCOME: FinalOutcome = "failed"
TIMEOUT_ERROR_CODE: ErrorCode = "DEPENDENCY_TIMEOUT"
INTERNAL_ERROR_CODE: ErrorCode = "INTERNAL_ERROR"
RETRYABLE_ERROR_CODES: tuple[ErrorCode, ...] = (
    "DEPENDENCY_TIMEOUT",
    "TRANSIENT_DEPENDENCY",
    "RATE_LIMITED",
    "CAPACITY_REJECTED",
)
ITEM_KINDS: tuple[str, ...] = ("claim", "caveat")
EVIDENCE_TYPES: tuple[str, ...] = get_args(EvidenceType)
FRESHNESS_ORDER: tuple[tuple[EvidenceFreshness, str], ...] = (
    ("current", "freshness.current"),
    ("stale", "freshness.stale"),
    ("unknown", "freshness.unknown"),
)


def _require_exact_text(value: str, field_name: str) -> str:
    if not value.strip():
        raise ValueError(f"{field_name} must contain at least one non-whitespace character")
    if "\x00" in value:
        raise ValueError(f"{field_name} must not contain the NUL character")
    if value != value.strip():
        raise ValueError(f"{field_name} must not have leading or trailing whitespace")
    return value


def _require_version_four(value: UUID, field_name: str) -> UUID:
    if value.version != 4:
        raise ValueError(f"{field_name} must be a version 4 UUID")
    return value


@dataclass(frozen=True, slots=True)
class RenderedAnswerItem:
    """One untrusted rendered realization of a planned claim or caveat."""

    item_kind: Literal["claim", "caveat"]
    item_id: str
    rendered_text: str

    def __post_init__(self) -> None:
        if self.item_kind not in ITEM_KINDS:
            raise ValueError("item_kind must be either claim or caveat")
        _require_exact_text(self.item_id, "item_id")
        _require_exact_text(self.rendered_text, "rendered_text")


@dataclass(frozen=True, slots=True)
class RenderedAnswerSection:
    """One untrusted rendered section preserving planned item order."""

    section_id: str
    items: tuple[RenderedAnswerItem, ...]

    def __post_init__(self) -> None:
        _require_exact_text(self.section_id, "section_id")
        if not self.items:
            raise ValueError("a rendered section requires at least one item")
        keys = tuple((item.item_kind, item.item_id) for item in self.items)
        if len(frozenset(keys)) != len(keys):
            raise ValueError("rendered items must be unique by item kind and identifier")


@dataclass(frozen=True, slots=True)
class RenderedAnswerDraft:
    """The complete untrusted rendering of exactly one AnswerPlan."""

    answer_plan_id: UUID
    sections: tuple[RenderedAnswerSection, ...]

    def __post_init__(self) -> None:
        _require_version_four(self.answer_plan_id, "answer_plan_id")
        if not self.sections:
            raise ValueError("a rendered draft requires at least one section")
        section_ids = tuple(section.section_id for section in self.sections)
        if len(frozenset(section_ids)) != len(section_ids):
            raise ValueError("rendered sections must be unique by section identifier")
        keys = tuple(
            (item.item_kind, item.item_id) for section in self.sections for item in section.items
        )
        if len(frozenset(keys)) != len(keys):
            raise ValueError("each rendered item must appear in exactly one section")


@dataclass(frozen=True, slots=True)
class RenderRequest:
    """Trusted artifacts handed to the untrusted renderer, and nothing else."""

    context: RuntimeContext
    authorization: AuthorizationDecision
    route_decision: RouteDecision
    execution_plan: ExecutionPlan
    evidence_bundle: EvidenceBundle
    answer_plan: AnswerPlan


@runtime_checkable
class AnswerRendererPort(Protocol):
    async def render(self, request: RenderRequest) -> RenderedAnswerDraft: ...


@dataclass(frozen=True, slots=True)
class ResolvedCitationSource:
    """Citation safe source description resolved for one accepted evidence record.

    The source-binding fields (source_type, source_ref, source_version,
    security_scope_ref, locator_ref) are private trust-boundary fields used only
    to validate the resolver result against the exact accepted Evidence record.
    They are never copied verbatim into any externally visible contract, and
    display_label is never used to authorize or bind a source.
    """

    evidence_id: UUID
    evidence_type: EvidenceType
    source_type: str
    source_ref: str
    source_version: str
    security_scope_ref: str
    locator_ref: str
    display_label: str

    def __post_init__(self) -> None:
        _require_version_four(self.evidence_id, "evidence_id")
        if self.evidence_type not in EVIDENCE_TYPES:
            raise ValueError("evidence_type must be a legal EvidenceType")
        _require_exact_text(self.source_type, "source_type")
        _require_exact_text(self.source_ref, "source_ref")
        _require_exact_text(self.source_version, "source_version")
        _require_exact_text(self.security_scope_ref, "security_scope_ref")
        _require_exact_text(self.locator_ref, "locator_ref")
        _require_exact_text(self.display_label, "display_label")


@dataclass(frozen=True, slots=True)
class CitationSourceResolutionRequest:
    """One batched request for the citation sources required by an AnswerPlan."""

    context: RuntimeContext
    authorization: AuthorizationDecision
    evidence_bundle: EvidenceBundle
    answer_plan: AnswerPlan
    evidence_ids: tuple[UUID, ...]

    def __post_init__(self) -> None:
        if not self.evidence_ids:
            raise ValueError("a citation source request requires at least one evidence id")
        if len(frozenset(self.evidence_ids)) != len(self.evidence_ids):
            raise ValueError("requested evidence ids must be unique")
        if self.authorization.decision_id != self.answer_plan.authorization_decision_id:
            raise ValueError("authorization must match the answer plan's authorization decision")
        if self.authorization.decision_id != self.evidence_bundle.authorization_decision_id:
            raise ValueError(
                "authorization must match the evidence bundle's authorization decision"
            )
        # The requested evidence ids must be exactly the ids required by the
        # planned citation slots: same order, same first-occurrence dedup, no
        # missing, extra, foreign, reordered, or duplicate identifier, and
        # never broadened to accepted evidence outside the planned slots.
        expected = _required_evidence_ids(self.answer_plan)
        if self.evidence_ids != expected:
            raise ValueError("requested evidence ids must exactly match the planned citation slots")
        accepted_ids = frozenset(
            item.evidence_id for item in self.evidence_bundle.accepted_evidence
        )
        rejected_ids = frozenset(
            item.evidence_id for item in self.evidence_bundle.rejected_evidence
        )
        for evidence_id in self.evidence_ids:
            if evidence_id in rejected_ids:
                raise ValueError("a citation source request must not target rejected evidence")
            if evidence_id not in accepted_ids:
                raise ValueError("a citation source request must target accepted evidence only")


@runtime_checkable
class CitationSourceResolverPort(Protocol):
    async def resolve(
        self,
        request: CitationSourceResolutionRequest,
    ) -> tuple[ResolvedCitationSource, ...]: ...


@dataclass(frozen=True, slots=True)
class FinalizationArtifacts:
    """Injected identifiers and timestamps for exactly one finalization attempt."""

    final_answer_id: UUID
    citation_ids: tuple[UUID, ...]
    failure_internal_detail_ref: UUID
    finalized_at: datetime

    def __post_init__(self) -> None:
        _require_version_four(self.final_answer_id, "final_answer_id")
        _require_version_four(self.failure_internal_detail_ref, "failure_internal_detail_ref")
        for citation_id in self.citation_ids:
            _require_version_four(citation_id, "citation_id")
        identifiers = (
            self.final_answer_id,
            self.failure_internal_detail_ref,
            *self.citation_ids,
        )
        if len(frozenset(identifiers)) != len(identifiers):
            raise ValueError("finalization identifiers must be pairwise distinct")
        if self.finalized_at.utcoffset() is None:
            raise ValueError("finalized_at must be timezone-aware")


@dataclass(frozen=True, slots=True)
class _CompletedTurn:
    """The complete set of trusted artifacts produced by one completed turn."""

    authorization: AuthorizationDecision
    route_decision: RouteDecision
    execution_plan: ExecutionPlan
    step_result: StepResult
    evidence_bundle: EvidenceBundle
    answer_plan: AnswerPlan


def _require_entry(context: RuntimeContext, entered_at: datetime) -> None:
    if entered_at.utcoffset() is None:
        raise ValueError("entered_at must be timezone-aware")
    if entered_at < context.started_at:
        raise ValueError("entered_at must not precede the runtime start")


def _require_completed_turn(result: OrchestrationResult) -> _CompletedTurn:
    if result.status is not OrchestrationStatus.COMPLETED:
        raise ValueError("finalization supports a completed orchestration result only")
    authorization = result.authorization
    route_decision = result.route_decision
    execution_plan = result.execution_plan
    step_result = result.step_result
    evidence_bundle = result.evidence_bundle
    answer_plan = result.answer_plan
    if (
        authorization is None
        or route_decision is None
        or execution_plan is None
        or step_result is None
        or evidence_bundle is None
        or answer_plan is None
    ):
        raise ValueError("a completed orchestration result requires every turn artifact")
    return _CompletedTurn(
        authorization=authorization,
        route_decision=route_decision,
        execution_plan=execution_plan,
        step_result=step_result,
        evidence_bundle=evidence_bundle,
        answer_plan=answer_plan,
    )


def _require_pending_finalization(pending: TerminalCoordinationResult) -> _CompletedTurn:
    if not isinstance(pending, TerminalCoordinationResult):
        raise ValueError("pending must be a TerminalCoordinationResult")
    if pending.status is not TerminalCoordinationStatus.PENDING_FINALIZATION:
        raise ValueError("finalization supports a pending finalization coordination only")
    if pending.lease is None:
        raise ValueError("a pending finalization requires the acquired lease")
    if pending.outcome is not None:
        raise ValueError("a pending finalization must not already carry a terminal outcome")
    result = pending.orchestration_result
    if result is None:
        raise ValueError("a pending finalization requires an orchestration result")
    return _require_completed_turn(result)


def _derive_effective_key(context: RuntimeContext) -> EffectiveIdempotencyKey:
    """Derive the identity- and runtime-scoped idempotency key of this context."""
    principal = context.principal
    snapshot = context.runtime_snapshot
    return EffectiveIdempotencyKey(
        deployment_id=str(principal.deployment_id),
        principal_id=str(principal.principal_id),
        client_key=str(context.turn_input.idempotency_key),
        runtime_snapshot_id=str(snapshot.snapshot_id),
        runtime_snapshot_digest=snapshot.integrity.digest,
    )


def _require_identity_binding(
    context: RuntimeContext,
    pending: TerminalCoordinationResult,
) -> None:
    """Rebind the pending idempotency identity to the current RuntimeContext.

    A pending finalization must never be honored under a different deployment,
    principal, client idempotency key, or runtime snapshot than the one it was
    coordinated under. No async port may be called before this check passes.
    """
    derived = _derive_effective_key(context)
    if pending.effective_key != derived:
        raise ValueError("the pending finalization must bind the current runtime identity")
    lease = pending.lease
    if lease is None or lease.key != derived:
        raise ValueError("the acquired lease must bind the current runtime identity")


def _require_canonical_evidence_types(bundle: EvidenceBundle) -> None:
    """Require the fast.document canonical flow's document-only evidence shape.

    The Walking Skeleton's only canonical route materializes DocumentEvidence
    through the document_retrieval capability. A contract-valid EvidenceBundle
    populated with any other evidence subtype (WebEvidence, SqlEvidence,
    SelectorEvidence, RuleEvidence) belongs to a different capability and must
    never be finalized as if it were document evidence, even though it shares
    matching root identifiers (request, route, plan, authorization, snapshot).
    This check runs before any renderer or resolver call and never fabricates
    a failed FinalAnswer or selects alternative evidence: it simply fails
    closed with ValueError.
    """
    for item in bundle.accepted_evidence:
        if not isinstance(item, DocumentEvidence):
            raise ValueError("accepted evidence must be DocumentEvidence for this route")
    for rejected in bundle.rejected_evidence:
        if rejected.evidence_type != "document":
            raise ValueError("rejected evidence must declare the document evidence type")


def _require_bundle_lineage(
    context: RuntimeContext,
    turn: _CompletedTurn,
) -> None:
    bundle = turn.evidence_bundle
    if bundle.request_id != context.turn_input.request_id:
        raise ValueError("evidence bundle request_id must match the runtime context")
    if bundle.route_decision_id != turn.route_decision.decision_id:
        raise ValueError("evidence bundle route_decision_id must match the route decision")
    if bundle.plan_id != turn.execution_plan.plan_id:
        raise ValueError("evidence bundle plan_id must match the execution plan")
    if bundle.authorization_decision_id != turn.authorization.decision_id:
        raise ValueError("evidence bundle authorization_decision_id must match the decision")
    if bundle.runtime_snapshot_id != context.runtime_snapshot.snapshot_id:
        raise ValueError("evidence bundle runtime_snapshot_id must match the runtime context")
    if str(bundle.correlation_id) != context.correlation_id:
        raise ValueError("evidence bundle correlation_id must match the runtime context")
    if bundle.required_fact_ids != turn.execution_plan.required_facts:
        raise ValueError("evidence bundle required facts must match the execution plan")
    _require_canonical_evidence_types(bundle)


def _require_answer_plan_lineage(
    context: RuntimeContext,
    turn: _CompletedTurn,
) -> None:
    plan = turn.answer_plan
    bundle = turn.evidence_bundle
    if plan.request_id != context.turn_input.request_id:
        raise ValueError("answer plan request_id must match the runtime context")
    if plan.evidence_bundle_id != bundle.bundle_id:
        raise ValueError("answer plan evidence_bundle_id must match the evidence bundle")
    if plan.route_decision_id != turn.route_decision.decision_id:
        raise ValueError("answer plan route_decision_id must match the route decision")
    if plan.plan_id != turn.execution_plan.plan_id:
        raise ValueError("answer plan plan_id must match the execution plan")
    if plan.authorization_decision_id != turn.authorization.decision_id:
        raise ValueError("answer plan authorization_decision_id must match the decision")
    if plan.runtime_snapshot_id != context.runtime_snapshot.snapshot_id:
        raise ValueError("answer plan runtime_snapshot_id must match the runtime context")
    if plan.correlation_id != bundle.correlation_id:
        raise ValueError("answer plan correlation_id must match the evidence bundle")
    if plan.decision != bundle.decision:
        raise ValueError("answer plan decision must match the evidence decision")
    if plan.tone_constraints.response_locale != context.turn_input.locale:
        raise ValueError("answer plan response locale must match the runtime context")


def _require_supported_decision(turn: _CompletedTurn) -> FinalOutcome:
    plan = turn.answer_plan
    if plan.decision == "answer":
        if plan.answer_type in ("clarification", "abstention"):
            raise ValueError("an answered plan must not use a narrative answer type")
        return ANSWERED_OUTCOME
    if plan.decision == "abstain":
        if plan.answer_type != "abstention":
            raise ValueError("an abstained plan requires the abstention answer type")
        return ABSTAINED_OUTCOME
    raise ValueError("finalization supports answer and abstain decisions only")


def _require_lineage(context: RuntimeContext, turn: _CompletedTurn) -> FinalOutcome:
    # The authorized context re-proves the request and security-context binding
    # of the authorization decision through the existing trusted value type.
    authorized = AuthorizedRuntimeContext(runtime=context, authorization=turn.authorization)
    _require_canonical_route(turn.route_decision, route_error=CANONICAL_ROUTE_ERROR)
    _require_canonical_plan(turn.route_decision, turn.execution_plan, subject=FINALIZER_SUBJECT)
    # The materialization request re-proves route, plan, step, snapshot,
    # correlation, capability and operation bindings without duplicating them.
    EvidenceMaterializationRequest(
        context=authorized,
        route_decision=turn.route_decision,
        execution_plan=turn.execution_plan,
        step_results=(turn.step_result,),
    )
    _require_bundle_lineage(context, turn)
    _require_answer_plan_lineage(context, turn)
    return _require_supported_decision(turn)


def _require_generation_mode(generation_mode: FinalGenerationMode) -> None:
    if generation_mode not in GENERATION_MODES:
        raise ValueError("generation_mode must be a legal FinalGenerationMode")
    if generation_mode == FAILED_GENERATION_MODE:
        raise ValueError("generation_mode must not be none for content finalization")


def _require_citation_count(
    answer_plan: AnswerPlan,
    artifacts: FinalizationArtifacts,
) -> None:
    slot_count = len(answer_plan.citation_slots)
    if len(artifacts.citation_ids) != slot_count:
        raise ValueError("injected citation ids must match the planned citation slot count")
    if slot_count == 0 and artifacts.citation_ids != ():
        raise ValueError("no citation ids may be injected when no citation slot is planned")


def _require_finalization_timestamp(
    artifacts: FinalizationArtifacts,
    entered_at: datetime,
    answer_plan: AnswerPlan,
) -> None:
    if artifacts.finalized_at < entered_at:
        raise ValueError("finalized_at must not precede the finalization entry time")
    if artifacts.finalized_at < answer_plan.built_at:
        raise ValueError("finalized_at must not precede the answer plan build time")


def _final_item(item: RenderedAnswerItem) -> FinalClaimContent | FinalCaveatContent:
    # Only the authorized identifier and the validated rendered text cross the
    # boundary: evidence, codes, confidence and reasoning never do.
    if item.item_kind == "claim":
        return FinalClaimContent(item_id=item.item_id, rendered_text=item.rendered_text)
    return FinalCaveatContent(item_id=item.item_id, rendered_text=item.rendered_text)


def _validate_rendered_content(
    draft: RenderedAnswerDraft,
    answer_plan: AnswerPlan,
) -> tuple[FinalAnswerSection, ...]:
    """Require the rendered draft to realize the approved plan exactly."""
    if draft.answer_plan_id != answer_plan.answer_plan_id:
        raise ValueError("the rendered draft must realize the approved answer plan")
    if len(draft.sections) != len(answer_plan.sections):
        raise ValueError("the rendered draft must contain exactly the planned sections")
    sections: tuple[FinalAnswerSection, ...] = ()
    for rendered, planned in zip(draft.sections, answer_plan.sections, strict=True):
        if rendered.section_id != planned.section_id:
            raise ValueError("rendered section identifiers and order must match the plan")
        if len(rendered.items) != len(planned.items):
            raise ValueError("a rendered section must contain exactly the planned items")
        items: tuple[FinalClaimContent | FinalCaveatContent, ...] = ()
        for item, reference in zip(rendered.items, planned.items, strict=True):
            if item.item_kind != reference.item_kind:
                raise ValueError("a rendered item must keep the planned item kind")
            if item.item_id != reference.item_id:
                raise ValueError("rendered item identifiers and order must match the plan")
            items = (*items, _final_item(item))
        sections = (
            *sections,
            FinalAnswerSection(
                section_id=planned.section_id,
                section_type=planned.section_type,
                items=items,
            ),
        )
    return sections


def _claim_count(sections: tuple[FinalAnswerSection, ...]) -> int:
    return sum(1 for section in sections for item in section.items if item.item_kind == "claim")


def _caveat_count(sections: tuple[FinalAnswerSection, ...]) -> int:
    return sum(1 for section in sections for item in section.items if item.item_kind == "caveat")


def _authorized_evidence_ids(
    answer_plan: AnswerPlan,
    kind: str,
    target_id: str,
) -> tuple[UUID, ...]:
    if kind == "claim":
        for claim in answer_plan.claims:
            if claim.claim_id == target_id:
                return claim.evidence_ids
        raise ValueError("a citation slot must target a planned claim")
    for caveat in answer_plan.caveats:
        if caveat.caveat_id == target_id:
            return caveat.evidence_ids
    raise ValueError("a citation slot must target a planned caveat")


def _rendered_keys(sections: tuple[FinalAnswerSection, ...]) -> tuple[tuple[str, str], ...]:
    return tuple((item.item_kind, item.item_id) for section in sections for item in section.items)


def _require_authorized_citations(
    answer_plan: AnswerPlan,
    evidence_bundle: EvidenceBundle,
    sections: tuple[FinalAnswerSection, ...],
) -> None:
    rendered = _rendered_keys(sections)
    accepted = tuple(item.evidence_id for item in evidence_bundle.accepted_evidence)
    rejected = tuple(item.evidence_id for item in evidence_bundle.rejected_evidence)
    for slot in answer_plan.citation_slots:
        if (slot.target_kind, slot.target_id) not in rendered:
            raise ValueError("a citation slot must target a rendered claim or caveat")
        authorized = _authorized_evidence_ids(answer_plan, slot.target_kind, slot.target_id)
        for evidence_id in slot.evidence_ids:
            if evidence_id in rejected:
                raise ValueError("a citation slot must not cite rejected evidence")
            if evidence_id not in accepted:
                raise ValueError("a citation slot must cite accepted evidence only")
            if evidence_id not in authorized:
                raise ValueError("cited evidence must be authorized for the slot target")


def _required_evidence_ids(answer_plan: AnswerPlan) -> tuple[UUID, ...]:
    required: tuple[UUID, ...] = ()
    for slot in answer_plan.citation_slots:
        for evidence_id in slot.evidence_ids:
            if evidence_id not in required:
                required = (*required, evidence_id)
    return required


def _accepted_evidence(evidence_bundle: EvidenceBundle, evidence_id: UUID) -> Evidence:
    # Only EvidenceBundle.accepted_evidence is ever consulted: there is no
    # global or process-local source registry, and no fallback to any other
    # collection when a source is missing here.
    for item in evidence_bundle.accepted_evidence:
        if item.evidence_id == evidence_id:
            return item
    raise ValueError("a resolved citation source must describe accepted evidence")


def _resolved_for(
    resolved: tuple[ResolvedCitationSource, ...],
    evidence_id: UUID,
) -> ResolvedCitationSource:
    for source in resolved:
        if source.evidence_id == evidence_id:
            return source
    raise ValueError("the resolver must return one source per requested evidence id")


def _require_source_binding(source: ResolvedCitationSource, evidence: Evidence) -> None:
    """Validate a resolved source against the exact accepted Evidence record.

    Matching evidence_id and evidence_type alone is never sufficient: every
    private source-binding field is checked against the real Evidence record,
    and a foreign source_type, source_ref, source_version, security_scope_ref,
    or locator_ref is rejected even when the identifier and type match. This
    check never consults display_label, a source name, or a department name.
    """
    if source.evidence_id != evidence.evidence_id:
        raise ValueError("a resolved citation source must match the accepted evidence id")
    if source.evidence_type != evidence.evidence_type:
        raise ValueError("a resolved citation source must match the accepted evidence type")
    if source.source_type != evidence.source.source_type:
        raise ValueError("a resolved citation source must match the accepted evidence source_type")
    if source.source_ref != evidence.source.source_ref:
        raise ValueError("a resolved citation source must match the accepted evidence source_ref")
    if source.source_version != evidence.source.source_version:
        raise ValueError(
            "a resolved citation source must match the accepted evidence source_version"
        )
    if source.security_scope_ref != evidence.security_scope.scope_ref:
        raise ValueError(
            "a resolved citation source must match the accepted evidence security scope"
        )
    # The canonical fast.document flow resolves DocumentEvidence exclusively:
    # a foreign evidence subtype is rejected outright, and the locator binding
    # is unconditional rather than only enforced when the type already matches.
    if not isinstance(evidence, DocumentEvidence):
        raise ValueError("a resolved citation source must describe document evidence only")
    if source.locator_ref != evidence.locator_ref:
        raise ValueError(
            "a resolved citation source must match the accepted document evidence locator_ref"
        )


def _require_resolved_sources(
    resolved: tuple[ResolvedCitationSource, ...],
    requested: tuple[UUID, ...],
    evidence_bundle: EvidenceBundle,
) -> tuple[ResolvedCitationSource, ...]:
    identifiers = tuple(source.evidence_id for source in resolved)
    if len(frozenset(identifiers)) != len(identifiers):
        raise ValueError("resolved citation sources must be unique by evidence id")
    if len(resolved) != len(requested):
        raise ValueError("the resolver must return exactly the requested citation sources")
    ordered: tuple[ResolvedCitationSource, ...] = ()
    for evidence_id in requested:
        source = _resolved_for(resolved, evidence_id)
        # Fails closed with ValueError: a missing or unauthorized source is
        # never substituted with any alternative or fallback source.
        evidence = _accepted_evidence(evidence_bundle, evidence_id)
        _require_source_binding(source, evidence)
        ordered = (*ordered, source)
    return ordered


def _final_source(source: ResolvedCitationSource) -> FinalCitationSource:
    return FinalCitationSource(
        evidence_id=source.evidence_id,
        evidence_type=source.evidence_type,
        display_label=source.display_label,
        source_version=source.source_version,
        locator_ref=source.locator_ref,
    )


def _compile_citations(
    answer_plan: AnswerPlan,
    citation_ids: tuple[UUID, ...],
    resolved: tuple[ResolvedCitationSource, ...],
) -> tuple[FinalCitation, ...]:
    """Compile one citation per planned slot, entirely inside trusted Core."""
    slots = answer_plan.citation_slots
    if len(citation_ids) != len(slots):
        raise ValueError("exactly one injected citation id is required per planned slot")
    citations: tuple[FinalCitation, ...] = ()
    for slot, citation_id in zip(slots, citation_ids, strict=True):
        sources = tuple(
            _final_source(_resolved_for(resolved, evidence_id)) for evidence_id in slot.evidence_ids
        )
        citations = (
            *citations,
            FinalCitation(
                citation_id=citation_id,
                slot_id=slot.slot_id,
                target_kind=slot.target_kind,
                target_id=slot.target_id,
                placement=slot.placement,
                sources=sources,
            ),
        )
    return citations


def _freshness_note(evidence_bundle: EvidenceBundle, outcome: FinalOutcome) -> FinalFreshnessNote:
    """Derive freshness from trusted evidence only, never from a port result."""
    if outcome is not ANSWERED_OUTCOME:
        return FinalFreshnessNote(status="not_applicable")
    accepted = evidence_bundle.accepted_evidence
    if not accepted:
        return FinalFreshnessNote(status="unknown", reason_codes=("freshness.unknown",))
    present = tuple(
        (status, code)
        for status, code in FRESHNESS_ORDER
        if any(item.freshness == status for item in accepted)
    )
    if len(present) > 1:
        return FinalFreshnessNote(
            status="mixed",
            reason_codes=tuple(code for _, code in present),
        )
    single, code = present[0]
    if single == "unknown":
        return FinalFreshnessNote(status="unknown", reason_codes=(code,))
    observed = min(item.source_time.observed_at for item in accepted)
    if single == "current":
        return FinalFreshnessNote(status="current", data_as_of=observed)
    return FinalFreshnessNote(status="stale", data_as_of=observed, reason_codes=(code,))


def _is_degraded(evidence_bundle: EvidenceBundle, outcome: FinalOutcome) -> bool:
    if outcome is not ANSWERED_OUTCOME:
        return True
    return any(
        item.validation_status == "degraded" or item.freshness != "current"
        for item in evidence_bundle.accepted_evidence
    )


def _response_metadata(
    answer_plan: AnswerPlan,
    evidence_bundle: EvidenceBundle,
    outcome: FinalOutcome,
    sections: tuple[FinalAnswerSection, ...],
    citations: tuple[FinalCitation, ...],
    generation_mode: FinalGenerationMode,
) -> FinalResponseMetadata:
    return FinalResponseMetadata(
        response_locale=answer_plan.tone_constraints.response_locale,
        answer_type=answer_plan.answer_type,
        generation_mode=generation_mode,
        validation_status=PASSED_VALIDATION,
        degraded=_is_degraded(evidence_bundle, outcome),
        section_count=len(sections),
        claim_count=_claim_count(sections),
        caveat_count=_caveat_count(sections),
        citation_count=len(citations),
        character_count=_character_count(sections),
    )


def _character_count(sections: tuple[FinalAnswerSection, ...]) -> int:
    # Only validated claim and caveat text counts: citation labels, headings and
    # transport formatting are presentation concerns outside this budget.
    return sum(len(item.rendered_text) for section in sections for item in section.items)


def _require_within_budget(
    sections: tuple[FinalAnswerSection, ...],
    budget: AnswerLengthBudget,
) -> None:
    if len(sections) > budget.max_sections:
        raise ValueError("the rendered section count exceeds the approved length budget")
    if _claim_count(sections) > budget.max_claims:
        raise ValueError("the rendered claim count exceeds the approved length budget")
    if _caveat_count(sections) > budget.max_caveats:
        raise ValueError("the rendered caveat count exceeds the approved length budget")
    if _character_count(sections) > budget.max_characters:
        raise ValueError("the rendered character count exceeds the approved length budget")


def _outcome_reason_codes(answer_plan: AnswerPlan, outcome: FinalOutcome) -> tuple[str, ...]:
    if outcome is ANSWERED_OUTCOME:
        return ()
    return answer_plan.decision_reason_codes


def _require_final_bindings(
    final_answer: FinalAnswer,
    context: RuntimeContext,
    turn: _CompletedTurn,
    artifacts: FinalizationArtifacts,
) -> None:
    plan = turn.answer_plan
    bindings = (
        (final_answer.final_answer_id, artifacts.final_answer_id),
        (final_answer.request_id, context.turn_input.request_id),
        (final_answer.answer_plan_id, plan.answer_plan_id),
        (final_answer.evidence_bundle_id, turn.evidence_bundle.bundle_id),
        (final_answer.route_decision_id, turn.route_decision.decision_id),
        (final_answer.plan_id, turn.execution_plan.plan_id),
        (final_answer.authorization_decision_id, turn.authorization.decision_id),
        (final_answer.runtime_snapshot_id, context.runtime_snapshot.snapshot_id),
        (final_answer.correlation_id, plan.correlation_id),
    )
    for actual, expected in bindings:
        if actual != expected:
            raise ValueError("the final answer must bind every referenced artifact exactly")
    if final_answer.finalized_at != artifacts.finalized_at:
        raise ValueError("the final answer must use the injected finalization timestamp")
    if final_answer.applied_length_budget != plan.length_budget:
        raise ValueError("the final answer must apply the approved length budget")


def _construct_final_answer(
    context: RuntimeContext,
    turn: _CompletedTurn,
    artifacts: FinalizationArtifacts,
    outcome: FinalOutcome,
    sections: tuple[FinalAnswerSection, ...],
    citations: tuple[FinalCitation, ...],
    generation_mode: FinalGenerationMode,
) -> FinalAnswer:
    plan = turn.answer_plan
    final_answer = FinalAnswer(
        final_answer_id=artifacts.final_answer_id,
        request_id=context.turn_input.request_id,
        answer_plan_id=plan.answer_plan_id,
        evidence_bundle_id=turn.evidence_bundle.bundle_id,
        route_decision_id=turn.route_decision.decision_id,
        plan_id=turn.execution_plan.plan_id,
        authorization_decision_id=turn.authorization.decision_id,
        runtime_snapshot_id=context.runtime_snapshot.snapshot_id,
        correlation_id=plan.correlation_id,
        finalized_at=artifacts.finalized_at,
        outcome=outcome,
        validated_content=FinalValidatedContent(sections=sections),
        citations=citations,
        outcome_reason_codes=_outcome_reason_codes(plan, outcome),
        freshness_note=_freshness_note(turn.evidence_bundle, outcome),
        applied_length_budget=plan.length_budget,
        response_metadata=_response_metadata(
            plan,
            turn.evidence_bundle,
            outcome,
            sections,
            citations,
            generation_mode,
        ),
        finalizer_version=FINALIZER_VERSION,
    )
    _require_final_bindings(final_answer, context, turn, artifacts)
    return final_answer


def _failed_answer(
    context: RuntimeContext,
    turn: _CompletedTurn,
    artifacts: FinalizationArtifacts,
    code: ErrorCode,
) -> FinalAnswer:
    """Build the safe failed answer for one controlled post-plan failure."""
    plan = turn.answer_plan
    final_answer = FinalAnswer(
        final_answer_id=artifacts.final_answer_id,
        request_id=context.turn_input.request_id,
        answer_plan_id=plan.answer_plan_id,
        evidence_bundle_id=turn.evidence_bundle.bundle_id,
        route_decision_id=turn.route_decision.decision_id,
        plan_id=turn.execution_plan.plan_id,
        authorization_decision_id=turn.authorization.decision_id,
        runtime_snapshot_id=context.runtime_snapshot.snapshot_id,
        correlation_id=plan.correlation_id,
        finalized_at=artifacts.finalized_at,
        outcome=FAILED_OUTCOME,
        validated_content=None,
        citations=(),
        outcome_reason_codes=(f"finalization.{code.lower()}",),
        safe_error=DomainError(
            code=code,
            safe_message_key=f"error.{code.lower()}",
            retryable=code in RETRYABLE_ERROR_CODES,
            internal_detail_ref=artifacts.failure_internal_detail_ref,
        ),
        freshness_note=FinalFreshnessNote(status="not_applicable"),
        applied_length_budget=plan.length_budget,
        response_metadata=FinalResponseMetadata(
            generation_mode=FAILED_GENERATION_MODE,
            validation_status=FAILED_VALIDATION,
            degraded=True,
            section_count=0,
            claim_count=0,
            caveat_count=0,
            citation_count=0,
            character_count=0,
        ),
        finalizer_version=FINALIZER_VERSION,
    )
    _require_final_bindings(final_answer, context, turn, artifacts)
    return final_answer


async def _render(
    renderer: AnswerRendererPort,
    request: RenderRequest,
) -> RenderedAnswerDraft | None:
    try:
        result = await renderer.render(request)
    except asyncio.CancelledError:
        # Cancellation, including the structured timeout, is never an outcome.
        raise
    except ValueError:
        # A renderer-raised ValueError is a trusted-boundary rejection, never an
        # opaque internal error: it must propagate, not be swallowed here.
        raise
    except Exception:
        return None
    if not isinstance(result, RenderedAnswerDraft):
        raise ValueError("the renderer must return a RenderedAnswerDraft")
    return result


async def _resolve(
    citation_source_resolver: CitationSourceResolverPort,
    request: CitationSourceResolutionRequest,
) -> tuple[ResolvedCitationSource, ...] | None:
    try:
        result = await citation_source_resolver.resolve(request)
    except asyncio.CancelledError:
        raise
    except ValueError:
        # A resolver-raised ValueError is a trusted-boundary rejection, never an
        # opaque internal error: it must propagate, not be swallowed here.
        raise
    except Exception:
        return None
    if not isinstance(result, tuple):
        raise ValueError("the resolver must return a tuple of ResolvedCitationSource")
    for item in result:
        if not isinstance(item, ResolvedCitationSource):
            raise ValueError("the resolver must return ResolvedCitationSource items only")
    return result


async def _finalize(
    context: RuntimeContext,
    turn: _CompletedTurn,
    outcome: FinalOutcome,
    *,
    renderer: AnswerRendererPort,
    citation_source_resolver: CitationSourceResolverPort,
    artifacts: FinalizationArtifacts,
    generation_mode: FinalGenerationMode,
) -> FinalAnswer:
    plan = turn.answer_plan
    draft = await _render(
        renderer,
        RenderRequest(
            context=context,
            authorization=turn.authorization,
            route_decision=turn.route_decision,
            execution_plan=turn.execution_plan,
            evidence_bundle=turn.evidence_bundle,
            answer_plan=plan,
        ),
    )
    if draft is None:
        return _failed_answer(context, turn, artifacts, INTERNAL_ERROR_CODE)
    sections = _validate_rendered_content(draft, plan)
    _require_within_budget(sections, plan.length_budget)
    _require_authorized_citations(plan, turn.evidence_bundle, sections)
    requested = _required_evidence_ids(plan)
    resolved: tuple[ResolvedCitationSource, ...] = ()
    if requested:
        returned = await _resolve(
            citation_source_resolver,
            CitationSourceResolutionRequest(
                context=context,
                authorization=turn.authorization,
                evidence_bundle=turn.evidence_bundle,
                answer_plan=plan,
                evidence_ids=requested,
            ),
        )
        if returned is None:
            return _failed_answer(context, turn, artifacts, INTERNAL_ERROR_CODE)
        resolved = _require_resolved_sources(returned, requested, turn.evidence_bundle)
    citations = _compile_citations(plan, artifacts.citation_ids, resolved)
    return _construct_final_answer(
        context, turn, artifacts, outcome, sections, citations, generation_mode
    )


async def finalize_pending_answer(
    context: RuntimeContext,
    pending: TerminalCoordinationResult,
    *,
    renderer: AnswerRendererPort,
    citation_source_resolver: CitationSourceResolverPort,
    artifacts: FinalizationArtifacts,
    entered_at: datetime,
    generation_mode: FinalGenerationMode,
) -> FinalAnswer:
    """Turn one pending finalization into the trusted FinalAnswer of the turn.

    generation_mode is a required, explicitly injected legal FinalGenerationMode
    for this attempt: it is never a hard-coded production constant, and "none"
    is rejected before the renderer is ever called. Every synchronous preflight
    check below (entry, pending shape, identity binding, lineage, generation
    mode, citation count, and timestamp ordering) runs before any async port
    call, so a failing preflight check causes zero renderer or resolver calls.
    """
    _require_entry(context, entered_at)
    turn = _require_pending_finalization(pending)
    _require_identity_binding(context, pending)
    outcome = _require_lineage(context, turn)
    _require_generation_mode(generation_mode)
    _require_citation_count(turn.answer_plan, artifacts)
    _require_finalization_timestamp(artifacts, entered_at, turn.answer_plan)
    deadline_at = context.deadline_at
    if deadline_at is None:
        return await _finalize(
            context,
            turn,
            outcome,
            renderer=renderer,
            citation_source_resolver=citation_source_resolver,
            artifacts=artifacts,
            generation_mode=generation_mode,
        )
    remaining_seconds = (deadline_at - entered_at).total_seconds()
    if remaining_seconds <= 0:
        # The request budget was already spent before any port was reachable.
        return _failed_answer(context, turn, artifacts, TIMEOUT_ERROR_CODE)
    try:
        async with asyncio.timeout(remaining_seconds):
            return await _finalize(
                context,
                turn,
                outcome,
                renderer=renderer,
                citation_source_resolver=citation_source_resolver,
                artifacts=artifacts,
                generation_mode=generation_mode,
            )
    except TimeoutError:
        return _failed_answer(context, turn, artifacts, TIMEOUT_ERROR_CODE)
