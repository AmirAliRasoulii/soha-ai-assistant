"""Evidence and evidence bundle contracts, schema version 1.0.0."""

from typing import Annotated, Final, Literal, Self
from uuid import UUID

from pydantic import AfterValidator, ConfigDict, Field, model_validator

from ai_assistant.contracts.base import ContractModel, SchemaVersion, UtcDateTime
from ai_assistant.contracts.execution_plan import FactDataScope
from ai_assistant.contracts.route_decision import CapabilityName

JSON_SCHEMA_DIALECT = "https://json-schema.org/draft/2020-12/schema"
EVIDENCE_SCHEMA_VERSION: Final[Literal["1.0.0"]] = "1.0.0"
EVIDENCE_SCHEMA_ID = "urn:ai-assistant:contracts:evidence:1.0.0"

EvidenceType = Literal[
    "document",
    "sql",
    "selector",
    "rule",
    "web",
]

# Rejected evidence never reaches the accepted collection, so the accepted
# status catalog only distinguishes fully validated from degraded records.
EvidenceValidationStatus = Literal[
    "validated",
    "degraded",
]

# Freshness describes source timing only. It is never a confidence score.
EvidenceFreshness = Literal[
    "current",
    "stale",
    "unknown",
]

EvidenceConflictStatus = Literal[
    "resolved",
    "unresolved",
]

EvidenceDecision = Literal[
    "answer",
    "partial_answer",
    "clarify",
    "abstain",
]

_CANONICAL_CODE_PATTERN = r"^[a-z][a-z0-9._:-]*$"
_SHA256_PATTERN = r"^[0-9a-f]{64}$"

_CanonicalCode = Annotated[
    str,
    Field(min_length=1, max_length=128, pattern=_CANONICAL_CODE_PATTERN),
]
# Digests are compared exactly: uppercase input is rejected rather than folded.
_Sha256Digest = Annotated[str, Field(pattern=_SHA256_PATTERN)]
_Score = Annotated[float, Field(strict=True, ge=0.0, le=1.0, allow_inf_nan=False)]


def _require_exact_text(value: str) -> str:
    # Opaque references are handles, not locators: malformed input is rejected
    # rather than trimmed, rewritten, or repaired by validation.
    if not value.strip():
        raise ValueError("value must contain at least one non-whitespace character")
    if "\x00" in value:
        raise ValueError("value must not contain the NUL character")
    if value != value.strip():
        raise ValueError("value must not have leading or trailing whitespace")
    return value


_OpaqueRef = Annotated[
    str,
    Field(min_length=1, max_length=256),
    AfterValidator(_require_exact_text),
]


def _require_uuid4(value: UUID) -> UUID:
    if value.version != 4:
        raise ValueError("identifier must be a version 4 UUID")
    return value


_Uuid4 = Annotated[UUID, AfterValidator(_require_uuid4)]


def _require_unique_values[HashableT](
    value: tuple[HashableT, ...],
) -> tuple[HashableT, ...]:
    if len(set(value)) != len(value):
        raise ValueError("values must be unique")
    return value


_AllowedUses = Annotated[
    tuple[_CanonicalCode, ...],
    Field(min_length=1, max_length=8),
    AfterValidator(_require_unique_values),
]
_SupportedFactIds = Annotated[
    tuple[_CanonicalCode, ...],
    Field(min_length=1, max_length=16),
    AfterValidator(_require_unique_values),
]
_RequiredCodes16 = Annotated[
    tuple[_CanonicalCode, ...],
    Field(min_length=1, max_length=16),
    AfterValidator(_require_unique_values),
]
_OptionalCodes16 = Annotated[
    tuple[_CanonicalCode, ...],
    Field(max_length=16),
    AfterValidator(_require_unique_values),
]
_RequiredFactIds = Annotated[
    tuple[_CanonicalCode, ...],
    Field(min_length=1, max_length=32),
    AfterValidator(_require_unique_values),
]
_MissingFactIds = Annotated[
    tuple[_CanonicalCode, ...],
    Field(max_length=32),
    AfterValidator(_require_unique_values),
]
_RuleInputEvidenceIds = Annotated[
    tuple[_Uuid4, ...],
    Field(min_length=1, max_length=16),
    AfterValidator(_require_unique_values),
]
_MappedEvidenceIds = Annotated[
    tuple[_Uuid4, ...],
    Field(min_length=1, max_length=64),
    AfterValidator(_require_unique_values),
]
_ConflictEvidenceIds = Annotated[
    tuple[_Uuid4, ...],
    Field(min_length=2, max_length=16),
    AfterValidator(_require_unique_values),
]
_ClaimEvidenceIds = Annotated[
    tuple[_Uuid4, ...],
    Field(min_length=1, max_length=32),
    AfterValidator(_require_unique_values),
]


class EvidenceSubjectRef(ContractModel):
    """Controlled reference to the subject an evidence record describes."""

    # Display text and personal values never appear here: the subject is a
    # typed code plus an opaque handle resolved outside this contract.
    subject_type: _CanonicalCode
    subject_ref: _OpaqueRef


class EvidenceValidityWindow(ContractModel):
    """Validity context of an evidence record relative to an observation."""

    as_of: UtcDateTime
    valid_from: UtcDateTime | None = None
    valid_to: UtcDateTime | None = None

    @model_validator(mode="after")
    def _require_consistent_window(self) -> Self:
        if self.valid_from is not None and self.valid_to is not None:
            if self.valid_from > self.valid_to:
                raise ValueError("valid_from must not be later than valid_to")
        if self.valid_from is not None and self.valid_from > self.as_of:
            raise ValueError("valid_from must not be later than as_of")
        if self.valid_to is not None and self.as_of > self.valid_to:
            raise ValueError("as_of must not be later than valid_to")
        return self


class EvidenceSourceTime(ContractModel):
    """Observation and publication timing of the underlying source."""

    observed_at: UtcDateTime
    published_at: UtcDateTime | None = None

    @model_validator(mode="after")
    def _require_consistent_times(self) -> Self:
        if self.published_at is not None and self.published_at > self.observed_at:
            raise ValueError("published_at must not be later than observed_at")
        return self


class EvidenceSourceRef(ContractModel):
    """Provider-neutral reference to the source system of an evidence record."""

    source_type: _CanonicalCode
    source_ref: _OpaqueRef
    source_version: _OpaqueRef


class EvidenceSecurityScope(ContractModel):
    """Descriptive security binding of an evidence record."""

    # This is a label only. Authorization has already completed elsewhere and
    # is never granted or implied by this contract.
    scope_ref: _OpaqueRef
    data_scope: FactDataScope
    classification: _CanonicalCode


class EvidenceProvenance(ContractModel):
    """Provider-neutral description of what materialized an evidence record."""

    step_result_id: _Uuid4
    plan_id: _Uuid4
    step_id: _CanonicalCode
    capability: CapabilityName
    operation: _CanonicalCode
    materializer_version: SchemaVersion
    input_digest: _Sha256Digest


class _EvidenceBase(ContractModel):
    """Common controlled metadata shared by every accepted evidence variant."""

    evidence_id: _Uuid4
    subject: EvidenceSubjectRef
    valid_time: EvidenceValidityWindow
    source_time: EvidenceSourceTime
    source: EvidenceSourceRef
    authority: _CanonicalCode
    security_scope: EvidenceSecurityScope
    validation_status: EvidenceValidationStatus
    freshness: EvidenceFreshness
    provenance: EvidenceProvenance
    allowed_uses: _AllowedUses
    retention_class: _CanonicalCode
    supports_fact_ids: _SupportedFactIds


class DocumentEvidence(_EvidenceBase):
    """Normalized evidence produced by document retrieval."""

    evidence_type: Literal["document"] = "document"
    document_ref: _OpaqueRef
    document_version: _OpaqueRef
    chunk_ref: _OpaqueRef
    locator_ref: _OpaqueRef
    content_ref: _OpaqueRef
    content_sha256: _Sha256Digest
    # Retrieval-local ordering signal only. It is never a global answer
    # confidence and never participates in sufficiency decisions.
    ranking_score: _Score | None = None

    @model_validator(mode="after")
    def _require_document_capability(self) -> Self:
        if self.provenance.capability != "document_retrieval":
            raise ValueError("document evidence requires document_retrieval provenance")
        return self


class SqlEvidence(_EvidenceBase):
    """Normalized evidence produced by governed semantic analytics."""

    evidence_type: Literal["sql"] = "sql"
    semantic_query_ref: _OpaqueRef
    semantic_catalog_version: SchemaVersion
    result_ref: _OpaqueRef
    result_sha256: _Sha256Digest
    metric_codes: _RequiredCodes16
    filter_codes: _OptionalCodes16 = ()
    result_shape: _CanonicalCode
    suppression_applied: bool

    @model_validator(mode="after")
    def _require_analytics_boundary(self) -> Self:
        if self.provenance.capability != "semantic_analytics":
            raise ValueError("sql evidence requires semantic_analytics provenance")
        if self.security_scope.data_scope != "general":
            raise ValueError("sql evidence requires a general data scope")
        return self


class SelectorEvidence(_EvidenceBase):
    """Normalized evidence produced by the governed personal selector."""

    evidence_type: Literal["selector"] = "selector"
    selector_ref: _OpaqueRef
    result_ref: _OpaqueRef
    result_sha256: _Sha256Digest
    field_codes: _RequiredCodes16

    @model_validator(mode="after")
    def _require_personal_boundary(self) -> Self:
        if self.provenance.capability != "personal_selector":
            raise ValueError("selector evidence requires personal_selector provenance")
        if self.security_scope.data_scope != "personal":
            raise ValueError("selector evidence requires a personal data scope")
        return self


class RuleEvidence(_EvidenceBase):
    """Normalized evidence produced by deterministic rule evaluation."""

    evidence_type: Literal["rule"] = "rule"
    rule_bundle_ref: _OpaqueRef
    rule_code: _CanonicalCode
    rule_version: SchemaVersion
    outcome_ref: _OpaqueRef
    outcome_sha256: _Sha256Digest
    input_evidence_ids: _RuleInputEvidenceIds

    @model_validator(mode="after")
    def _require_rule_boundary(self) -> Self:
        if self.provenance.capability != "rule_evaluator":
            raise ValueError("rule evidence requires rule_evaluator provenance")
        if self.evidence_id in self.input_evidence_ids:
            raise ValueError("rule evidence must not reference itself as an input")
        return self


class WebEvidence(_EvidenceBase):
    """Normalized evidence produced by allowlisted official web search."""

    evidence_type: Literal["web"] = "web"
    page_ref: _OpaqueRef
    allowlist_ref: _OpaqueRef
    locator_ref: _OpaqueRef
    content_ref: _OpaqueRef
    content_sha256: _Sha256Digest

    @model_validator(mode="after")
    def _require_web_boundary(self) -> Self:
        if self.provenance.capability != "official_search":
            raise ValueError("web evidence requires official_search provenance")
        if self.security_scope.data_scope != "general":
            raise ValueError("web evidence requires a general data scope")
        return self


Evidence = Annotated[
    DocumentEvidence | SqlEvidence | SelectorEvidence | RuleEvidence | WebEvidence,
    Field(discriminator="evidence_type"),
]

_EvidenceItem = DocumentEvidence | SqlEvidence | SelectorEvidence | RuleEvidence | WebEvidence


class RejectedEvidenceRef(ContractModel):
    """Controlled record of evidence excluded during normalization."""

    # Rejected source content and raw error text are never copied here: only
    # the identifier, the type, and controlled reason codes.
    evidence_id: _Uuid4
    evidence_type: EvidenceType
    reason_codes: _RequiredCodes16


class FactEvidenceMapEntry(ContractModel):
    """Exact mapping between one required fact and its supporting evidence."""

    fact_id: _CanonicalCode
    evidence_ids: _MappedEvidenceIds


class EvidenceConflict(ContractModel):
    """Detected disagreement between accepted evidence about one fact."""

    conflict_id: _Uuid4
    fact_id: _CanonicalCode
    evidence_ids: _ConflictEvidenceIds
    status: EvidenceConflictStatus
    resolution_code: _CanonicalCode | None = None
    controlling_evidence_id: _Uuid4 | None = None

    @model_validator(mode="after")
    def _require_consistent_resolution(self) -> Self:
        # Precedence policy lives in trusted deterministic code. This model only
        # records the outcome that policy already produced.
        if self.status == "unresolved":
            if self.resolution_code is not None:
                raise ValueError("an unresolved conflict must not carry a resolution code")
            if self.controlling_evidence_id is not None:
                raise ValueError("an unresolved conflict must not carry controlling evidence")
            return self
        if self.resolution_code is None:
            raise ValueError("a resolved conflict requires a resolution code")
        if self.controlling_evidence_id is None:
            raise ValueError("a resolved conflict requires controlling evidence")
        if self.controlling_evidence_id not in self.evidence_ids:
            raise ValueError("controlling evidence must belong to the conflict")
        return self


class AllowedEvidenceClaim(ContractModel):
    """Authorized semantic claim shape backed by accepted evidence."""

    # The claim shape is authorized here; claim prose is produced later under
    # the answer boundary and is never stored in this contract.
    claim_id: _CanonicalCode
    claim_code: _CanonicalCode
    claim_type: _CanonicalCode
    subject: EvidenceSubjectRef
    supporting_fact_ids: _SupportedFactIds
    evidence_ids: _ClaimEvidenceIds


class ProhibitedEvidenceClaim(ContractModel):
    """Claim shape that trusted policy forbids for this bundle."""

    claim_code: _CanonicalCode
    reason_codes: _RequiredCodes16


def _require_unique_accepted(value: tuple[_EvidenceItem, ...]) -> tuple[_EvidenceItem, ...]:
    identifiers = [item.evidence_id for item in value]
    if len(set(identifiers)) != len(identifiers):
        raise ValueError("accepted evidence identifiers must be unique")
    return value


def _require_unique_rejected(
    value: tuple[RejectedEvidenceRef, ...],
) -> tuple[RejectedEvidenceRef, ...]:
    identifiers = [item.evidence_id for item in value]
    if len(set(identifiers)) != len(identifiers):
        raise ValueError("rejected evidence identifiers must be unique")
    return value


def _require_unique_mapped_facts(
    value: tuple[FactEvidenceMapEntry, ...],
) -> tuple[FactEvidenceMapEntry, ...]:
    fact_ids = [entry.fact_id for entry in value]
    if len(set(fact_ids)) != len(fact_ids):
        raise ValueError("fact map entries must be unique by fact identifier")
    return value


def _require_unique_conflicts(
    value: tuple[EvidenceConflict, ...],
) -> tuple[EvidenceConflict, ...]:
    identifiers = [conflict.conflict_id for conflict in value]
    if len(set(identifiers)) != len(identifiers):
        raise ValueError("conflict identifiers must be unique")
    semantic = [(conflict.fact_id, conflict.evidence_ids) for conflict in value]
    if len(set(semantic)) != len(semantic):
        raise ValueError("duplicate semantic conflicts are not permitted")
    return value


def _require_unique_allowed_claims(
    value: tuple[AllowedEvidenceClaim, ...],
) -> tuple[AllowedEvidenceClaim, ...]:
    identifiers = [claim.claim_id for claim in value]
    if len(set(identifiers)) != len(identifiers):
        raise ValueError("allowed claim identifiers must be unique")
    return value


def _require_unique_prohibited_claims(
    value: tuple[ProhibitedEvidenceClaim, ...],
) -> tuple[ProhibitedEvidenceClaim, ...]:
    codes = [claim.claim_code for claim in value]
    if len(set(codes)) != len(codes):
        raise ValueError("prohibited claim codes must be unique")
    return value


_AcceptedEvidence = Annotated[
    tuple[Evidence, ...],
    Field(max_length=64),
    AfterValidator(_require_unique_accepted),
]
_RejectedEvidence = Annotated[
    tuple[RejectedEvidenceRef, ...],
    Field(max_length=64),
    AfterValidator(_require_unique_rejected),
]
_FactMap = Annotated[
    tuple[FactEvidenceMapEntry, ...],
    Field(max_length=32),
    AfterValidator(_require_unique_mapped_facts),
]
_Conflicts = Annotated[
    tuple[EvidenceConflict, ...],
    Field(max_length=32),
    AfterValidator(_require_unique_conflicts),
]
_AllowedClaims = Annotated[
    tuple[AllowedEvidenceClaim, ...],
    Field(max_length=64),
    AfterValidator(_require_unique_allowed_claims),
]
_ProhibitedClaims = Annotated[
    tuple[ProhibitedEvidenceClaim, ...],
    Field(max_length=64),
    AfterValidator(_require_unique_prohibited_claims),
]


class EvidenceBundle(ContractModel):
    """Deterministic evidence normalization and sufficiency decision."""

    model_config = ConfigDict(
        json_schema_extra={
            "$schema": JSON_SCHEMA_DIALECT,
            "$id": EVIDENCE_SCHEMA_ID,
        }
    )

    schema_version: Literal["1.0.0"] = EVIDENCE_SCHEMA_VERSION
    bundle_id: _Uuid4
    request_id: _Uuid4
    route_decision_id: _Uuid4
    plan_id: _Uuid4
    authorization_decision_id: _Uuid4
    runtime_snapshot_id: _Uuid4
    correlation_id: _Uuid4
    built_at: UtcDateTime
    required_fact_ids: _RequiredFactIds
    accepted_evidence: _AcceptedEvidence = ()
    rejected_evidence: _RejectedEvidence = ()
    fact_map: _FactMap = ()
    missing_fact_ids: _MissingFactIds = ()
    conflicts: _Conflicts = ()
    sufficient: bool
    decision: EvidenceDecision
    allowed_claims: _AllowedClaims = ()
    prohibited_claims: _ProhibitedClaims = ()
    decision_reason_codes: _RequiredCodes16
    evidence_manager_version: SchemaVersion

    @model_validator(mode="after")
    def _require_consistent_bundle(self) -> Self:
        self._require_distinct_evidence()
        self._require_declared_support()
        self._require_exact_partition()
        self._require_exact_fact_map()
        self._require_valid_conflicts()
        self._require_valid_claims()
        self._require_consistent_decision()
        return self

    def _accepted_ids(self) -> set[UUID]:
        return {item.evidence_id for item in self.accepted_evidence}

    def _require_distinct_evidence(self) -> None:
        accepted = self._accepted_ids()
        rejected = {item.evidence_id for item in self.rejected_evidence}
        if accepted.intersection(rejected):
            raise ValueError("evidence must not be both accepted and rejected")
        for item in self.accepted_evidence:
            if item.provenance.plan_id != self.plan_id:
                raise ValueError("accepted evidence must originate from the referenced plan")
            if isinstance(item, RuleEvidence):
                unknown = set(item.input_evidence_ids).difference(accepted)
                if unknown:
                    raise ValueError("rule evidence inputs must be accepted in the same bundle")

    def _require_declared_support(self) -> None:
        required = set(self.required_fact_ids)
        for item in self.accepted_evidence:
            unknown = set(item.supports_fact_ids).difference(required)
            if unknown:
                raise ValueError("accepted evidence must support required facts only")

    def _require_exact_partition(self) -> None:
        mapped = {entry.fact_id for entry in self.fact_map}
        missing = set(self.missing_fact_ids)
        required = set(self.required_fact_ids)
        if mapped.intersection(missing):
            raise ValueError("a fact must not be both mapped and missing")
        if not mapped.issubset(required):
            raise ValueError("the fact map must reference required facts only")
        if not missing.issubset(required):
            raise ValueError("missing facts must be required facts")
        if mapped.union(missing) != required:
            raise ValueError("required facts must be partitioned into mapped and missing facts")

    def _require_exact_fact_map(self) -> None:
        accepted = self._accepted_ids()
        declared = {
            (fact_id, item.evidence_id)
            for item in self.accepted_evidence
            for fact_id in item.supports_fact_ids
        }
        mapped: set[tuple[str, UUID]] = set()
        for entry in self.fact_map:
            unknown = set(entry.evidence_ids).difference(accepted)
            if unknown:
                raise ValueError("the fact map must reference accepted evidence only")
            for evidence_id in entry.evidence_ids:
                mapped.add((entry.fact_id, evidence_id))
        if mapped.difference(declared):
            raise ValueError("mapped evidence must declare support for the mapped fact")
        if declared.difference(mapped):
            raise ValueError("every declared evidence support must appear in the fact map")

    def _require_valid_conflicts(self) -> None:
        accepted = self._accepted_ids()
        required = set(self.required_fact_ids)
        supported = {
            item.evidence_id: set(item.supports_fact_ids) for item in self.accepted_evidence
        }
        for conflict in self.conflicts:
            if conflict.fact_id not in required:
                raise ValueError("a conflict must reference a required fact")
            unknown = set(conflict.evidence_ids).difference(accepted)
            if unknown:
                raise ValueError("a conflict must reference accepted evidence only")
            for evidence_id in conflict.evidence_ids:
                if conflict.fact_id not in supported[evidence_id]:
                    raise ValueError("conflicting evidence must support the conflicting fact")

    def _require_valid_claims(self) -> None:
        accepted = self._accepted_ids()
        mapped_facts = {entry.fact_id for entry in self.fact_map}
        supported = {
            item.evidence_id: set(item.supports_fact_ids) for item in self.accepted_evidence
        }
        for claim in self.allowed_claims:
            claim_facts = set(claim.supporting_fact_ids)
            if not claim_facts.issubset(mapped_facts):
                raise ValueError("an allowed claim must use covered facts only")
            unknown = set(claim.evidence_ids).difference(accepted)
            if unknown:
                raise ValueError("an allowed claim must reference accepted evidence only")
            for evidence_id in claim.evidence_ids:
                if not supported[evidence_id].intersection(claim_facts):
                    raise ValueError("claim evidence must support a claim fact")
            for fact_id in claim.supporting_fact_ids:
                backing = [
                    evidence_id
                    for evidence_id in claim.evidence_ids
                    if fact_id in supported[evidence_id]
                ]
                if not backing:
                    raise ValueError("each claim fact requires listed supporting evidence")
        allowed_codes = {claim.claim_code for claim in self.allowed_claims}
        prohibited_codes = {claim.claim_code for claim in self.prohibited_claims}
        if allowed_codes.intersection(prohibited_codes):
            raise ValueError("allowed and prohibited claim codes must be disjoint")

    def _has_unresolved_conflict(self) -> bool:
        return any(conflict.status == "unresolved" for conflict in self.conflicts)

    def _require_consistent_decision(self) -> None:
        # Sufficiency and the answer decision are two views of the same trusted
        # deterministic outcome and can never disagree.
        if self.sufficient != (self.decision == "answer"):
            raise ValueError("sufficiency must hold exactly when the decision is answer")
        if self.decision == "answer":
            self._require_answer_shape()
        elif self.decision == "partial_answer":
            self._require_partial_shape()
        elif self.decision == "clarify":
            self._require_clarify_shape()
        else:
            self._require_abstain_shape()

    def _require_answer_shape(self) -> None:
        if self.missing_fact_ids:
            raise ValueError("an answer decision requires complete fact coverage")
        if self._has_unresolved_conflict():
            raise ValueError("an answer decision requires no unresolved conflict")
        if not self.allowed_claims:
            raise ValueError("an answer decision requires at least one allowed claim")

    def _require_partial_shape(self) -> None:
        if not self.allowed_claims:
            raise ValueError("a partial answer requires at least one allowed claim")
        degraded = any(item.validation_status == "degraded" for item in self.accepted_evidence)
        stale = any(item.freshness != "current" for item in self.accepted_evidence)
        if not (self.missing_fact_ids or self._has_unresolved_conflict() or degraded or stale):
            raise ValueError("a partial answer requires a missing, conflicting, or weakened fact")

    def _require_clarify_shape(self) -> None:
        if not self.missing_fact_ids:
            raise ValueError("a clarify decision requires at least one missing fact")
        if self.allowed_claims:
            raise ValueError("a clarify decision must not carry allowed claims")

    def _require_abstain_shape(self) -> None:
        if self.allowed_claims:
            raise ValueError("an abstain decision must not carry allowed claims")
        if not (
            self.missing_fact_ids or self._has_unresolved_conflict() or not self.accepted_evidence
        ):
            raise ValueError("an abstain decision requires a missing, conflicting, or empty basis")
