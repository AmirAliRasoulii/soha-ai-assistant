"""Provider-neutral model gateway contracts, schema version 1.0.0.

Authority: ADR-CP-008 (model gateway, provider pool, credential boundary),
CP-000E (model integration, audit, and threat baseline), and DEF-037
(provider-neutral AI ports).

CP-001 owns the provider-neutral request, result, stream chunk, and selection
lineage shapes plus the `ModelGatewayPort` protocol in Core. Every concrete
provider adapter, including the gateway library adapter, is a CP-012 obligation,
and runtime model behavior such as retry, fallback execution, and budget
enforcement is an AI-008 obligation.

Boundary properties enforced by these shapes:

- Provider-neutral: a caller addresses a logical pool, never a provider, model
  endpoint, vendor client, or SDK object. No provider or gateway product name
  appears in any field or type.
- Bounded: message count, message size, output tokens, timeouts, and attempt
  counts all have hard ceilings.
- Deadline-aware: every request carries an explicit absolute deadline.
- Cancellable: cancellation is a first-class terminal outcome rather than an
  error to be inferred.
- Credential-free: a request cannot carry a key, token, header, or credential
  reference at all; credentials are resolved outside the AI boundary.
"""

from typing import Annotated, Final, Literal, Self

from pydantic import AfterValidator, ConfigDict, Field, model_validator

from ai_assistant.contracts.base import ContractModel, UtcDateTime
from ai_assistant.contracts.configuration import (
    ConfigurationArtifactRevisionRef,
    LogicalModelPoolRef,
)
from ai_assistant.contracts.control_plane_base import (
    JSON_SCHEMA_DIALECT,
    CanonicalCode,
    OpaqueId,
    Uuid4,
    unique_by,
)

MODEL_INVOCATION_REQUEST_SCHEMA_VERSION: Final[Literal["1.0.0"]] = "1.0.0"
MODEL_INVOCATION_REQUEST_SCHEMA_ID = "urn:ai-assistant:contracts:model-invocation-request:1.0.0"
MODEL_INVOCATION_RESULT_SCHEMA_VERSION: Final[Literal["1.0.0"]] = "1.0.0"
MODEL_INVOCATION_RESULT_SCHEMA_ID = "urn:ai-assistant:contracts:model-invocation-result:1.0.0"

ModelMessageRole = Literal["system", "user", "assistant"]
# Terminal outcomes of one invocation. Cancellation and deadline expiry are
# distinct outcomes, never a generic failure.
ModelInvocationOutcome = Literal[
    "completed",
    "refused",
    "timed_out",
    "cancelled",
    "failed",
]

# Bounds: a bounded prompt assembly step may never hand the gateway an unbounded
# conversation, and one message may never exceed the assembled-prompt ceiling.
MAX_MESSAGES: Final = 32
MAX_MESSAGE_CHARACTERS: Final = 32_768
MAX_OUTPUT_TOKENS: Final = 32_768
MAX_ATTEMPTS: Final = 8
MAX_TIMEOUT_MS: Final = 600_000


def _require_sanitized_text(value: str) -> str:
    if not value.strip():
        raise ValueError("value must contain at least one non-whitespace character")
    if "\x00" in value:
        raise ValueError("value must not contain the NUL character")
    return value


_MessageText = Annotated[
    str,
    Field(min_length=1, max_length=MAX_MESSAGE_CHARACTERS),
    AfterValidator(_require_sanitized_text),
]


class ModelMessage(ContractModel):
    """One provider-neutral message of a bounded invocation.

    The role vocabulary is closed and provider-independent. Content is trusted,
    already-assembled text: this contract carries no tool payload, no raw
    document, and no untyped extension bag.
    """

    role: ModelMessageRole
    content: _MessageText


_Messages = Annotated[
    tuple[ModelMessage, ...],
    Field(min_length=1, max_length=MAX_MESSAGES),
]


class ModelInvocationRequest(ContractModel):
    """One bounded, deadline-aware model invocation addressed to a logical pool."""

    model_config = ConfigDict(
        json_schema_extra={
            "$schema": JSON_SCHEMA_DIALECT,
            "$id": MODEL_INVOCATION_REQUEST_SCHEMA_ID,
        }
    )

    schema_version: Literal["1.0.0"] = MODEL_INVOCATION_REQUEST_SCHEMA_VERSION
    invocation_id: Uuid4
    request_id: Uuid4
    run_id: Uuid4
    # The logical, provider-neutral pool this call is addressed to.
    pool: LogicalModelPoolRef
    # Controlled purpose code, for example analysis or answer generation. It
    # exists for policy and telemetry, never for provider routing by name.
    purpose: CanonicalCode
    messages: _Messages
    max_output_tokens: Annotated[int, Field(ge=1, le=MAX_OUTPUT_TOKENS)]
    # Provider-neutral sampling controls. Absent means the pool default applies.
    temperature: Annotated[float, Field(ge=0.0, le=2.0)] | None = None
    top_p: Annotated[float, Field(gt=0.0, le=1.0)] | None = None
    # Structured output is requested by reference to a versioned schema artifact,
    # never by embedding a schema document in the request.
    structured_output_schema: ConfigurationArtifactRevisionRef | None = None
    stream_requested: bool = False
    issued_at: UtcDateTime
    deadline_at: UtcDateTime
    runtime_snapshot_id: Uuid4

    @model_validator(mode="after")
    def _require_usable_deadline(self) -> Self:
        if self.deadline_at <= self.issued_at:
            raise ValueError("deadline_at must be strictly later than issued_at")
        return self


class ModelInvocationAttemptRef(ContractModel):
    """One recorded attempt against one deployment of the addressed pool."""

    attempt_index: Annotated[int, Field(ge=1, le=MAX_ATTEMPTS)]
    deployment_ref: OpaqueId
    started_at: UtcDateTime
    outcome: ModelInvocationOutcome
    # Controlled reason code for a non-completed attempt. Never provider text,
    # never an exception message, never a raw response body.
    reason_code: CanonicalCode | None = None

    @model_validator(mode="after")
    def _require_reason_for_non_completion(self) -> Self:
        if self.outcome != "completed" and self.reason_code is None:
            raise ValueError(f"attempt outcome {self.outcome!r} requires a reason code")
        return self


_Attempts = Annotated[
    tuple[ModelInvocationAttemptRef, ...],
    Field(min_length=1, max_length=MAX_ATTEMPTS),
    AfterValidator(unique_by("attempt_index", "attempt indexes")),
]


class ProviderSelectionLineage(ContractModel):
    """Which pool was addressed, which deployment answered, and what was tried.

    This is lineage, not behavior: it records selection and fallback that already
    happened so an audit record can explain a run without naming a provider SDK.
    """

    pool: LogicalModelPoolRef
    attempts: _Attempts
    # Absent when no attempt completed.
    selected_deployment_ref: OpaqueId | None = None

    @model_validator(mode="after")
    def _require_consistent_selection(self) -> Self:
        attempted = {attempt.deployment_ref for attempt in self.attempts}
        completed = [attempt for attempt in self.attempts if attempt.outcome == "completed"]
        if len(completed) > 1:
            raise ValueError("at most one attempt may complete")
        if self.selected_deployment_ref is None:
            if completed:
                raise ValueError("a completed attempt requires the selected deployment")
        else:
            if self.selected_deployment_ref not in attempted:
                raise ValueError("the selected deployment must appear among the attempts")
            if not completed:
                raise ValueError("a selected deployment requires a completed attempt")
            if completed[0].deployment_ref != self.selected_deployment_ref:
                raise ValueError("the completed attempt must be the selected deployment")
        return self

    @property
    def fallback_used(self) -> bool:
        """Whether more than one deployment had to be attempted."""
        return len(self.attempts) > 1


class ModelInvocationUsage(ContractModel):
    """Bounded token accounting of one invocation."""

    input_tokens: Annotated[int, Field(ge=0, le=1_000_000)]
    output_tokens: Annotated[int, Field(ge=0, le=1_000_000)]


class ModelInvocationResult(ContractModel):
    """Terminal, provider-neutral result of one invocation.

    A refusal, a timeout, and a cancellation are distinct outcomes with no
    content, so no caller can read partial or absent output as an answer. No
    provider payload, header, or error object crosses this boundary: only
    controlled codes and bounded text.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "$schema": JSON_SCHEMA_DIALECT,
            "$id": MODEL_INVOCATION_RESULT_SCHEMA_ID,
        }
    )

    schema_version: Literal["1.0.0"] = MODEL_INVOCATION_RESULT_SCHEMA_VERSION
    invocation_id: Uuid4
    request_id: Uuid4
    outcome: ModelInvocationOutcome
    content: _MessageText | None = None
    finish_reason: CanonicalCode | None = None
    reason_code: CanonicalCode | None = None
    usage: ModelInvocationUsage
    selection: ProviderSelectionLineage
    completed_at: UtcDateTime
    # Opaque reference to an internal diagnostic record. It carries no detail
    # itself and is never resolved by a contract.
    internal_detail_ref: Uuid4 | None = None

    @model_validator(mode="after")
    def _require_consistent_outcome(self) -> Self:
        if self.outcome == "completed":
            if self.content is None:
                raise ValueError("outcome 'completed' requires content")
            if self.selection.selected_deployment_ref is None:
                raise ValueError("outcome 'completed' requires a selected deployment")
        else:
            if self.content is not None:
                raise ValueError(f"outcome {self.outcome!r} must not carry content")
            if self.reason_code is None:
                raise ValueError(f"outcome {self.outcome!r} requires a reason code")
            if self.outcome != "refused" and self.usage.output_tokens != 0:
                raise ValueError(f"outcome {self.outcome!r} must not report output tokens")
        return self


class ModelStreamChunk(ContractModel):
    """One ordered fragment of a streamed invocation.

    Streaming is contractually ordered and terminated: the sequence index is
    monotonic per invocation and the final chunk is explicit, so a truncated
    stream can never be mistaken for a complete answer.
    """

    invocation_id: Uuid4
    sequence_index: Annotated[int, Field(ge=0, le=100_000)]
    delta: _MessageText | None = None
    is_final: bool

    @model_validator(mode="after")
    def _require_delta_or_final(self) -> Self:
        if self.delta is None and not self.is_final:
            raise ValueError("a non-final chunk requires a delta")
        return self
