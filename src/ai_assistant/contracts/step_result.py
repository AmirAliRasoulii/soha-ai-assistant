"""Canonical capability step result contract, schema version 1.0.0."""

from typing import Annotated, Final, Literal, Self
from uuid import UUID

from pydantic import AfterValidator, ConfigDict, Field, model_validator

from ai_assistant.contracts.base import ContractModel, SchemaVersion, UtcDateTime
from ai_assistant.contracts.errors import ErrorCode
from ai_assistant.contracts.execution_plan import FactDataScope
from ai_assistant.contracts.route_decision import CapabilityName

JSON_SCHEMA_DIALECT = "https://json-schema.org/draft/2020-12/schema"
STEP_RESULT_SCHEMA_VERSION: Final[Literal["1.0.0"]] = "1.0.0"
STEP_RESULT_SCHEMA_ID = "urn:ai-assistant:contracts:step-result:1.0.0"

StepStatus = Literal[
    "success",
    "partial",
    "failed",
]

# Retry eligibility is limited to transient dependency conditions. Any other
# failure class must be resolved by policy rather than by repeating the step.
_RETRYABLE_FAILURE_CODES: Final[frozenset[str]] = frozenset(
    {
        "DEPENDENCY_TIMEOUT",
        "TRANSIENT_DEPENDENCY",
        "RATE_LIMITED",
        "CAPACITY_REJECTED",
    }
)
_RETRYABLE_STATUSES: Final[frozenset[str]] = frozenset({"partial", "failed"})
_MAX_LATENCY_MS: Final[int] = 2147483647

_CANONICAL_CODE_PATTERN = r"^[a-z][a-z0-9._:-]*$"
_SHA256_PATTERN = r"^[0-9a-f]{64}$"

_CanonicalCode = Annotated[
    str,
    Field(min_length=1, max_length=128, pattern=_CANONICAL_CODE_PATTERN),
]
# Digests are compared exactly: uppercase input is rejected rather than folded.
_Sha256Digest = Annotated[str, Field(pattern=_SHA256_PATTERN)]
_LatencyMilliseconds = Annotated[int, Field(strict=True, ge=0, le=_MAX_LATENCY_MS)]
# Two total attempts express one bounded retry and nothing more.
_AttemptCount = Annotated[int, Field(strict=True, ge=1, le=2)]


def _require_exact_text(value: str) -> str:
    # Artifact references are opaque handles: malformed input is rejected rather
    # than trimmed, rewritten, or repaired by validation.
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


def _require_unique_values(value: tuple[str, ...]) -> tuple[str, ...]:
    if len(set(value)) != len(value):
        raise ValueError("values must be unique")
    return value


_MissingFactIds = Annotated[
    tuple[_CanonicalCode, ...],
    Field(max_length=16),
    AfterValidator(_require_unique_values),
]
_SupportedFactIds = Annotated[
    tuple[_CanonicalCode, ...],
    Field(min_length=1, max_length=16),
    AfterValidator(_require_unique_values),
]


class StepTypedOutputRef(ContractModel):
    """Immutable reference to one validated typed output of a step attempt."""

    # The value itself is never embedded: only the approved schema reference,
    # the immutable value reference, and the digest that binds them.
    fact_id: _CanonicalCode
    value_type: _CanonicalCode
    data_scope: FactDataScope
    schema_ref: _OpaqueRef
    value_ref: _OpaqueRef
    sha256: _Sha256Digest


class StepEvidenceRef(ContractModel):
    """Reference to evidence supporting one or more typed outputs."""

    # Evidence content, snippets, citations, and source metadata belong to the
    # future Evidence contract and are never copied here.
    evidence_id: _Uuid4
    supports_fact_ids: _SupportedFactIds


class StepRetryMetadata(ContractModel):
    """Bounded retry eligibility record for one step attempt."""

    attempt: _AttemptCount
    max_attempts: _AttemptCount
    retryable: bool
    previous_result_id: _Uuid4 | None = None

    @model_validator(mode="after")
    def _require_consistent_attempts(self) -> Self:
        if self.attempt > self.max_attempts:
            raise ValueError("attempt must not exceed max_attempts")
        if self.attempt == 1 and self.previous_result_id is not None:
            raise ValueError("a first attempt must not reference a previous result")
        if self.attempt == 2:
            if self.max_attempts != 2:
                raise ValueError("a second attempt requires max_attempts of two")
            if self.previous_result_id is None:
                raise ValueError("a second attempt requires previous_result_id")
        if self.retryable and self.attempt >= self.max_attempts:
            raise ValueError("the final permitted attempt must not be retryable")
        if self.max_attempts == 1 and self.retryable:
            raise ValueError("a single permitted attempt must not be retryable")
        return self


class StepProvenance(ContractModel):
    """Provider-neutral description of what produced the step result."""

    # Provider model names, endpoints, SDK objects, and credentials are outside
    # this boundary; only controlled codes and digests appear here.
    capability: CapabilityName
    operation: _CanonicalCode
    implementation_version: SchemaVersion
    input_digest: _Sha256Digest


def _require_unique_output_facts(
    value: tuple[StepTypedOutputRef, ...],
) -> tuple[StepTypedOutputRef, ...]:
    fact_ids = [output.fact_id for output in value]
    if len(set(fact_ids)) != len(fact_ids):
        raise ValueError("typed output fact identifiers must be unique")
    return value


def _require_unique_evidence_ids(
    value: tuple[StepEvidenceRef, ...],
) -> tuple[StepEvidenceRef, ...]:
    evidence_ids = [reference.evidence_id for reference in value]
    if len(set(evidence_ids)) != len(evidence_ids):
        raise ValueError("evidence identifiers must be unique")
    return value


_TypedOutputs = Annotated[
    tuple[StepTypedOutputRef, ...],
    Field(max_length=16),
    AfterValidator(_require_unique_output_facts),
]
_EvidenceRefs = Annotated[
    tuple[StepEvidenceRef, ...],
    Field(max_length=32),
    AfterValidator(_require_unique_evidence_ids),
]


class StepResult(ContractModel):
    """Immutable validated result envelope for one planned step attempt."""

    model_config = ConfigDict(
        json_schema_extra={
            "$schema": JSON_SCHEMA_DIALECT,
            "$id": STEP_RESULT_SCHEMA_ID,
        }
    )

    schema_version: Literal["1.0.0"] = STEP_RESULT_SCHEMA_VERSION
    result_id: _Uuid4
    request_id: _Uuid4
    plan_id: _Uuid4
    step_id: _CanonicalCode
    runtime_snapshot_id: _Uuid4
    correlation_id: _Uuid4
    completed_at: UtcDateTime
    status: StepStatus
    typed_outputs: _TypedOutputs = ()
    missing_fact_ids: _MissingFactIds = ()
    evidence_refs: _EvidenceRefs = ()
    latency_ms: _LatencyMilliseconds
    retry: StepRetryMetadata
    # Opaque reference to a protected operational error record. The contract
    # never loads it and never carries raw error text.
    failure_code: ErrorCode | None = None
    internal_detail_ref: _Uuid4 | None = None
    provenance: StepProvenance

    @model_validator(mode="after")
    def _require_consistent_result(self) -> Self:
        self._require_status_shape()
        self._require_disjoint_fact_ids()
        self._require_supported_outputs()
        self._require_retry_consistency()
        return self

    def _require_status_shape(self) -> None:
        if self.status == "success":
            self._require_success_shape()
        elif self.status == "partial":
            self._require_partial_shape()
        else:
            self._require_failed_shape()

    def _require_success_shape(self) -> None:
        if not self.typed_outputs:
            raise ValueError("a successful step must produce at least one typed output")
        if self.missing_fact_ids:
            raise ValueError("a successful step must not report missing facts")
        if self.failure_code is not None:
            raise ValueError("a successful step must not carry a failure code")
        if self.internal_detail_ref is not None:
            raise ValueError("a successful step must not carry an internal detail reference")
        if self.retry.retryable:
            raise ValueError("a successful step must not be marked retryable")

    def _require_partial_shape(self) -> None:
        if not self.typed_outputs:
            raise ValueError("a partial step must produce at least one typed output")
        if not self.missing_fact_ids:
            raise ValueError("a partial step must report at least one missing fact")
        if self.failure_code is None:
            raise ValueError("a partial step must carry a failure code")

    def _require_failed_shape(self) -> None:
        if self.typed_outputs:
            raise ValueError("a failed step must not carry typed outputs")
        if not self.missing_fact_ids:
            raise ValueError("a failed step must report at least one missing fact")
        if self.evidence_refs:
            raise ValueError("a failed step must not carry evidence references")
        if self.failure_code is None:
            raise ValueError("a failed step must carry a failure code")

    def _require_disjoint_fact_ids(self) -> None:
        produced = {output.fact_id for output in self.typed_outputs}
        overlapping = produced.intersection(self.missing_fact_ids)
        if overlapping:
            raise ValueError("a fact must not be both produced and missing")

    def _require_supported_outputs(self) -> None:
        produced = {output.fact_id for output in self.typed_outputs}
        for reference in self.evidence_refs:
            unknown = set(reference.supports_fact_ids).difference(produced)
            if unknown:
                raise ValueError("evidence must support declared typed outputs only")

    def _require_retry_consistency(self) -> None:
        if self.retry.previous_result_id == self.result_id:
            raise ValueError("a result must not reference itself as the previous result")
        if not self.retry.retryable:
            return
        if self.status not in _RETRYABLE_STATUSES:
            raise ValueError("only a partial or failed step may be retryable")
        if self.failure_code not in _RETRYABLE_FAILURE_CODES:
            raise ValueError("only a transient failure code may be retryable")
