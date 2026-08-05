"""Runtime lineage, outcome taxonomy, and retention reference contracts, schema
version 1.0.0.

Authority: ADR-CP-010 (audit, retention, emergency controls, threat model),
ADR-CP-006 (runtime snapshot factory, cache, LKG), DEF-114 (audit outcome
taxonomy), and DEF-115 (runtime lineage in audit and durable completion).

CP-001 owns the typed lineage and outcome shapes. Durable storage, emission
semantics, and the pre-completion versus durable-completion meaning of the
turn-completed event are CP-009, CP-012, AI-002, and AI-007 obligations, and
none of them are implemented here.

`AuditEvent 1.0.0` is deliberately untouched: its published `outcome` union
stays exactly as committed. This module adds the complete taxonomy as a new
contract family so no published wire contract is broken in place, and so the
successor version of `AuditEvent` can be decided under the repository
compatibility-governance obligation (DEF-016) rather than guessed here.
"""

from typing import Annotated, Final, Literal, Self

from pydantic import AfterValidator, ConfigDict, Field, model_validator

from ai_assistant.contracts.base import ContractModel, UtcDateTime
from ai_assistant.contracts.control_plane_base import (
    JSON_SCHEMA_DIALECT,
    CanonicalCode,
    ContentDigest,
    OpaqueId,
    RevisionLabel,
    UniqueValues,
    Uuid4,
    unique_by,
)
from ai_assistant.contracts.membership import AuthorizationScopeRef
from ai_assistant.contracts.model_gateway import ProviderSelectionLineage
from ai_assistant.contracts.principal import ConsultedPolicyRevisionRef

RUNTIME_LINEAGE_SCHEMA_VERSION: Final[Literal["1.0.0"]] = "1.0.0"
RUNTIME_LINEAGE_SCHEMA_ID = "urn:ai-assistant:contracts:runtime-lineage:1.0.0"

# DEF-114 taxonomy, plus the cancellation outcome the terminal lifecycle already
# distinguishes. `authorization_denied` and `policy_rejected` are separate terms
# and are never interchangeable: a denial is an identity-and-scope decision,
# while a rejection is a content or safety policy result.
RuntimeOutcome = Literal[
    "answered",
    "partial",
    "clarification_required",
    "abstained",
    "policy_rejected",
    "authorization_denied",
    "failed",
    "cancelled",
]
# Every outcome except a clean answer must state at least one controlled reason.
_OUTCOMES_REQUIRING_REASON: Final[frozenset[str]] = frozenset(
    {
        "partial",
        "clarification_required",
        "abstained",
        "policy_rejected",
        "authorization_denied",
        "failed",
        "cancelled",
    }
)

LegalHoldState = Literal["active", "released"]

# A run cites a bounded number of source revisions, matching the bounded
# evidence and citation budgets already committed in the answer contracts.
MAX_LINEAGE_SOURCE_REVISIONS: Final = 64
MAX_REASON_CODES: Final = 16

_ReasonCodes = Annotated[
    tuple[CanonicalCode, ...],
    Field(max_length=MAX_REASON_CODES),
    UniqueValues,
]


class RetentionPolicyRef(ContractModel):
    """Reference to the retention rule that governs one audit record.

    The class and its revision are carried so a record can always be explained
    against the exact rule in force. Enforcement, expiry, and deletion are
    CP-009 and CP-012 obligations.
    """

    retention_class: CanonicalCode
    policy_revision: RevisionLabel
    # Absent means the retention duration is defined by the referenced policy
    # revision rather than pinned on the record. It never means "keep forever"
    # and never means "delete immediately".
    retention_days: Annotated[int, Field(ge=1, le=36_500)] | None = None


class LegalHoldRef(ContractModel):
    """Reference to a legal hold and its state.

    A hold is released by recording a release instant, never by deleting the
    hold, so an active hold and a released hold are structurally distinct.
    """

    hold_id: Uuid4
    state: LegalHoldState
    reason_code: CanonicalCode
    placed_at: UtcDateTime
    released_at: UtcDateTime | None = None

    @model_validator(mode="after")
    def _require_consistent_state(self) -> Self:
        if self.state == "released":
            if self.released_at is None:
                raise ValueError("a released hold requires released_at")
            if self.released_at <= self.placed_at:
                raise ValueError("released_at must be strictly later than placed_at")
        elif self.released_at is not None:
            raise ValueError("an active hold must not carry released_at")
        return self


class EmergencyActionRef(ContractModel):
    """Reference to one recorded configuration or emergency control action.

    Only the controlled action code and its provenance are carried. Executing,
    authorizing, or reversing an emergency action is a CP-009 obligation.
    """

    action_id: Uuid4
    action_code: CanonicalCode
    organization_id: Uuid4 | None = None
    occurred_at: UtcDateTime
    actor_principal_id: Uuid4 | None = None
    reason_code: CanonicalCode


class LineageSubjectRef(ContractModel):
    """Opaque reference to what a run was about.

    The subject type is a controlled code and the identifier is opaque: neither
    is parsed, resolved, or used as an authorization input.
    """

    subject_type: CanonicalCode
    subject_id: OpaqueId


class LineageTimeScope(ContractModel):
    """The time scope a run answered for.

    `as_of` is the instant the run treated as now. The optional window states
    which business validity range was considered.
    """

    as_of: UtcDateTime
    valid_from: UtcDateTime | None = None
    valid_until: UtcDateTime | None = None

    @model_validator(mode="after")
    def _require_ordered_window(self) -> Self:
        start = self.valid_from
        end = self.valid_until
        if start is not None and end is not None and end <= start:
            raise ValueError("valid_until must be strictly later than valid_from")
        return self


class SourceRevisionLineageRef(ContractModel):
    """Reference to one exact source revision a run relied on."""

    source_id: Uuid4
    revision_id: Uuid4


class ConfigurationReleaseLineageRef(ContractModel):
    """Reference to the configuration release a run was executed under."""

    release_id: Uuid4
    release_label: RevisionLabel
    manifest_digest: ContentDigest


class RuntimeSnapshotLineageRef(ContractModel):
    """Reference to the runtime snapshot a run was executed under.

    This is a reference only. `RuntimeSnapshot 1.0.0` keeps its published shape
    and is neither restated nor rewritten here.
    """

    snapshot_id: Uuid4
    content_digest: ContentDigest


_SourceRevisions = Annotated[
    tuple[SourceRevisionLineageRef, ...],
    Field(max_length=MAX_LINEAGE_SOURCE_REVISIONS),
    AfterValidator(unique_by("revision_id", "source revision identifiers")),
]


class RuntimeLineage(ContractModel):
    """The complete lineage of one run (DEF-115).

    All nine required elements are representable and none of them is optional by
    accident: organization, actor scope, subject, time scope, source version,
    policy version, configuration release, runtime snapshot, and the run and
    request identifiers.

    This contract is a fact record. It emits nothing, stores nothing, and makes
    no claim about whether durable completion has happened.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "$schema": JSON_SCHEMA_DIALECT,
            "$id": RUNTIME_LINEAGE_SCHEMA_ID,
        }
    )

    schema_version: Literal["1.0.0"] = RUNTIME_LINEAGE_SCHEMA_VERSION
    lineage_id: Uuid4
    # 1. organization
    organization_id: Uuid4
    # 2. actor scope: the explicit node scope the actor acted under. Absent means
    # no node scope applied, never "every node".
    actor_scope: AuthorizationScopeRef | None = None
    actor_principal_id: Uuid4 | None = None
    # 3. subject
    subject: LineageSubjectRef
    # 4. time scope
    time_scope: LineageTimeScope
    # 5. source version
    source_revisions: _SourceRevisions = ()
    # 6. policy version
    consulted_policy: ConsultedPolicyRevisionRef
    # 7. configuration release
    configuration_release: ConfigurationReleaseLineageRef
    # 8. runtime snapshot
    runtime_snapshot: RuntimeSnapshotLineageRef
    # 9. run and request identity
    run_id: Uuid4
    request_id: Uuid4
    outcome: RuntimeOutcome
    reason_codes: _ReasonCodes = ()
    authorization_decision_id: Uuid4 | None = None
    retention: RetentionPolicyRef
    legal_hold: LegalHoldRef | None = None
    provider_selection: ProviderSelectionLineage | None = None
    emergency_action: EmergencyActionRef | None = None
    recorded_at: UtcDateTime

    @model_validator(mode="after")
    def _require_consistent_scope(self) -> Self:
        if self.actor_scope is not None:
            if self.actor_scope.organization_id != self.organization_id:
                raise ValueError("actor scope must belong to the lineage organization")
        if self.emergency_action is not None:
            action_organization = self.emergency_action.organization_id
            if action_organization is not None and action_organization != self.organization_id:
                raise ValueError("emergency action must belong to the lineage organization")
        return self

    @model_validator(mode="after")
    def _require_consistent_outcome(self) -> Self:
        if self.outcome in _OUTCOMES_REQUIRING_REASON and not self.reason_codes:
            raise ValueError(f"outcome {self.outcome!r} requires at least one reason code")
        if self.outcome == "authorization_denied":
            # A denial is always traceable to the decision that produced it.
            if self.authorization_decision_id is None:
                raise ValueError("outcome 'authorization_denied' requires the decision reference")
        elif self.outcome == "policy_rejected":
            # A content or safety rejection is never an authorization denial, so
            # it must not borrow an authorization decision to explain itself.
            if self.authorization_decision_id is not None:
                raise ValueError(
                    "outcome 'policy_rejected' must not carry an authorization decision reference"
                )
        if self.outcome == "answered" and not self.source_revisions:
            raise ValueError("outcome 'answered' requires at least one source revision")
        return self
