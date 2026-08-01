"""FinalAnswer contract: the terminal validated answer artifact of the AI Core."""

from collections.abc import Hashable
from typing import Annotated, Final, Literal, Self
from uuid import UUID

from pydantic import AfterValidator, ConfigDict, Field, StrictBool, model_validator

from ai_assistant.contracts.answer_plan import (
    AnswerLengthBudget,
    AnswerType,
    CitationPlacement,
    CitationTargetKind,
)
from ai_assistant.contracts.base import ContractModel, SchemaVersion, UtcDateTime
from ai_assistant.contracts.errors import DomainError
from ai_assistant.contracts.evidence import EvidenceType

JSON_SCHEMA_DIALECT = "https://json-schema.org/draft/2020-12/schema"
FINAL_ANSWER_SCHEMA_VERSION: Final[Literal["1.0.0"]] = "1.0.0"
FINAL_ANSWER_SCHEMA_ID = "urn:ai-assistant:contracts:final-answer:1.0.0"

# A terminal outcome is a product result, never a transport or policy status.
# Authorization and request rejection happen before an AnswerPlan exists and
# stay on the ErrorEnvelope path, so no "denied" outcome is defined here.
FinalOutcome = Literal[
    "answered",
    "partially_answered",
    "clarification_required",
    "abstained",
    "failed",
]

FinalGenerationMode = Literal[
    "deterministic_template",
    "model_generated",
    "model_repaired",
    "safe_fallback",
    "none",
]

# Content validation is binary at this boundary: user-visible content either
# passed trusted validation, or no content exists at all.
FinalContentValidationStatus = Literal[
    "passed",
    "not_applicable",
]

FinalFreshnessStatus = Literal[
    "current",
    "stale",
    "mixed",
    "unknown",
    "not_applicable",
]

_CANONICAL_CODE_PATTERN = r"^[a-z][a-z0-9._:-]*$"
_OPAQUE_REF_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._:-]*$"
_SOURCE_VERSION_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._:+-]*$"
_LOCALE_TAG_PATTERN = r"^[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})*$"

# Codes are controlled catalog identifiers. Input is never trimmed, lowercased,
# sorted, normalized, or repaired: a malformed code is a defect, not a value to
# silently fix.
_CanonicalCode = Annotated[
    str,
    Field(min_length=1, max_length=128, pattern=_CANONICAL_CODE_PATTERN),
]

# A locator reference is opaque. The pattern excludes whitespace, "/", "\\",
# "?", "#", URL schemes, and filesystem paths so that a citation can never
# smuggle a resolvable address or grant access by itself.
_OpaqueRef = Annotated[
    str,
    Field(min_length=1, max_length=256, pattern=_OPAQUE_REF_PATTERN),
]

_SourceVersion = Annotated[
    str,
    Field(min_length=1, max_length=128, pattern=_SOURCE_VERSION_PATTERN),
]


def _require_exact_text(value: str) -> str:
    if "\x00" in value:
        raise ValueError("text must not contain a NUL character")
    if value != value.strip():
        raise ValueError("text must not have leading or trailing whitespace")
    return value


# Rendered text is already validated user-visible content. Unicode and Persian
# are fully supported and embedded newlines are allowed, but the contract never
# trims or repairs text: the stored value is exactly what was validated.
_RenderedText = Annotated[
    str,
    Field(strict=True, min_length=1, max_length=4000),
    AfterValidator(_require_exact_text),
]

_DisplayLabel = Annotated[
    str,
    Field(strict=True, min_length=1, max_length=256),
    AfterValidator(_require_exact_text),
]

_LocaleTag = Annotated[
    str,
    Field(min_length=2, max_length=35, pattern=_LOCALE_TAG_PATTERN),
    AfterValidator(_require_exact_text),
]


def _require_uuid4(value: UUID) -> UUID:
    if value.version != 4:
        raise ValueError("identifier must be a version 4 UUID")
    return value


_Uuid4 = Annotated[UUID, AfterValidator(_require_uuid4)]


def _require_unique_values[T: Hashable](value: tuple[T, ...]) -> tuple[T, ...]:
    if len(set(value)) != len(value):
        raise ValueError("values must be unique")
    return value


_FreshnessReasonCodes = Annotated[
    tuple[_CanonicalCode, ...],
    Field(max_length=8),
    AfterValidator(_require_unique_values),
]
_OutcomeReasonCodes = Annotated[
    tuple[_CanonicalCode, ...],
    Field(max_length=16),
    AfterValidator(_require_unique_values),
]

# Strict integers reject bool and float. Every count is a structural property of
# the validated content, never a token, cost, or latency measurement.
_SectionCount = Annotated[int, Field(strict=True, ge=0, le=8)]
_ClaimCount = Annotated[int, Field(strict=True, ge=0, le=32)]
_CaveatCount = Annotated[int, Field(strict=True, ge=0, le=32)]
_CitationCount = Annotated[int, Field(strict=True, ge=0, le=64)]
_CharacterCount = Annotated[int, Field(strict=True, ge=0, le=16000)]

# Failure of a request before an AnswerPlan exists is not a FinalAnswer. These
# codes describe normal product or request outcomes and belong to the request,
# authorization, clarification, abstention, or error-envelope paths.
_PROHIBITED_FAILURE_CODES: Final[frozenset[str]] = frozenset(
    {
        "INVALID_INPUT",
        "UNAUTHENTICATED",
        "UNAUTHORIZED",
        "AMBIGUOUS_REQUEST",
        "POLICY_REJECTED",
        "NO_EVIDENCE",
        "CONFLICTING_EVIDENCE",
    }
)

# Only a trusted post-plan finalization failure may produce a failed answer.
_PERMITTED_FAILURE_CODES: Final[frozenset[str]] = frozenset(
    {
        "SCHEMA_INVALID",
        "DEPENDENCY_TIMEOUT",
        "TRANSIENT_DEPENDENCY",
        "BUDGET_EXCEEDED",
        "RATE_LIMITED",
        "CAPACITY_REJECTED",
        "INTERNAL_ERROR",
    }
)

_NARRATIVE_ANSWER_TYPES: Final[frozenset[str]] = frozenset({"clarification", "abstention"})


class FinalClaimContent(ContractModel):
    """One validated claim realization inside the user-visible answer."""

    # The text has already passed trusted claim validation. It realizes exactly
    # one planned claim, carries no additional unsupported factual claim, and
    # embeds no citation label or marker.
    item_kind: Literal["claim"] = "claim"
    item_id: _CanonicalCode
    rendered_text: _RenderedText
    validation_status: Literal["supported"] = "supported"


class FinalCaveatContent(ContractModel):
    """One validated caveat realization inside the user-visible answer."""

    # The text realizes a required caveat without omitting, weakening, or
    # contradicting it, and hides no new claim inside caveat prose.
    item_kind: Literal["caveat"] = "caveat"
    item_id: _CanonicalCode
    rendered_text: _RenderedText
    validation_status: Literal["authorized"] = "authorized"


# Version 1 has no unplanned transition, narrative, heading, or free-text
# variant: connective language must live inside an already validated item.
FinalAnswerItem = Annotated[
    FinalClaimContent | FinalCaveatContent,
    Field(discriminator="item_kind"),
]


def _require_unique_items(
    value: tuple[FinalClaimContent | FinalCaveatContent, ...],
) -> tuple[FinalClaimContent | FinalCaveatContent, ...]:
    keys = [(item.item_kind, item.item_id) for item in value]
    if len(set(keys)) != len(keys):
        raise ValueError("section items must be unique by (item_kind, item_id)")
    return value


_SectionItems = Annotated[
    tuple[FinalAnswerItem, ...],
    Field(min_length=1, max_length=32),
    AfterValidator(_require_unique_items),
]


class FinalAnswerSection(ContractModel):
    """One ordered group of validated answer items."""

    # A section has no title or heading text: a presentation adapter renders a
    # heading from a versioned section-type catalog.
    section_id: _CanonicalCode
    section_type: _CanonicalCode
    items: _SectionItems


def _require_unique_sections(
    value: tuple[FinalAnswerSection, ...],
) -> tuple[FinalAnswerSection, ...]:
    section_ids = [section.section_id for section in value]
    if len(set(section_ids)) != len(section_ids):
        raise ValueError("sections must be unique by section_id")
    keys = [(item.item_kind, item.item_id) for section in value for item in section.items]
    if len(set(keys)) != len(keys):
        raise ValueError("each item must appear in exactly one section")
    return value


_ContentSections = Annotated[
    tuple[FinalAnswerSection, ...],
    Field(min_length=1, max_length=8),
    AfterValidator(_require_unique_sections),
]


class FinalValidatedContent(ContractModel):
    """The complete ordered user-visible content of one final answer."""

    # Section order, item order, and the exact partition are preserved so that
    # trusted validation can compare them with the referenced AnswerPlan.
    sections: _ContentSections


class FinalCitationSource(ContractModel):
    """One compiled evidence source backing a citation."""

    # Produced by trusted Citation Compiler code. The label is safe user-visible
    # source identification and the locator is an opaque reference resolved
    # outside this contract; neither grants access by itself.
    evidence_id: _Uuid4
    evidence_type: EvidenceType
    display_label: _DisplayLabel
    source_version: _SourceVersion
    locator_ref: _OpaqueRef


def _require_unique_sources(
    value: tuple[FinalCitationSource, ...],
) -> tuple[FinalCitationSource, ...]:
    evidence_ids = [source.evidence_id for source in value]
    if len(set(evidence_ids)) != len(evidence_ids):
        raise ValueError("citation sources must be unique by evidence_id")
    return value


_CitationSources = Annotated[
    tuple[FinalCitationSource, ...],
    Field(min_length=1, max_length=32),
    AfterValidator(_require_unique_sources),
]


class FinalCitation(ContractModel):
    """One compiled citation realizing exactly one planned citation slot."""

    citation_id: _Uuid4
    slot_id: _CanonicalCode
    target_kind: CitationTargetKind
    target_id: _CanonicalCode
    placement: CitationPlacement
    sources: _CitationSources


class FinalFreshnessNote(ContractModel):
    """Disclosed freshness of the evidence behind the final answer."""

    # Freshness prose is never stored here: when a user-visible statement is
    # required it must be a planned and validated caveat item.
    status: FinalFreshnessStatus
    data_as_of: UtcDateTime | None = None
    reason_codes: _FreshnessReasonCodes = ()

    @model_validator(mode="after")
    def _require_consistent_freshness(self) -> Self:
        has_date = self.data_as_of is not None
        has_reasons = len(self.reason_codes) > 0
        match self.status:
            case "current":
                if not has_date:
                    raise ValueError("current freshness requires data_as_of")
            case "stale":
                if not has_date:
                    raise ValueError("stale freshness requires data_as_of")
                if not has_reasons:
                    raise ValueError("stale freshness requires at least one reason code")
            case "mixed":
                if not has_reasons:
                    raise ValueError("mixed freshness requires at least one reason code")
            case "unknown":
                if has_date:
                    raise ValueError("unknown freshness must not carry data_as_of")
                if not has_reasons:
                    raise ValueError("unknown freshness requires at least one reason code")
            case "not_applicable":
                if has_date:
                    raise ValueError("not_applicable freshness must not carry data_as_of")
                if has_reasons:
                    raise ValueError("not_applicable freshness must not carry reason codes")
        return self


class FinalResponseMetadata(ContractModel):
    """Trace-safe structural description of the final response."""

    # This metadata carries no identity, message text, source content, model or
    # provider name, token count, cost, HTTP data, or vendor trace identifier.
    # Component and configuration versions are reachable through
    # runtime_snapshot_id, and finalizer_version stays a top-level field.
    response_locale: _LocaleTag | None = None
    answer_type: AnswerType | None = None
    generation_mode: FinalGenerationMode
    validation_status: FinalContentValidationStatus
    degraded: StrictBool
    section_count: _SectionCount
    claim_count: _ClaimCount
    caveat_count: _CaveatCount
    citation_count: _CitationCount
    character_count: _CharacterCount


def _require_unique_citations(value: tuple[FinalCitation, ...]) -> tuple[FinalCitation, ...]:
    citation_ids = [citation.citation_id for citation in value]
    if len(set(citation_ids)) != len(citation_ids):
        raise ValueError("citations must be unique by citation_id")
    slot_ids = [citation.slot_id for citation in value]
    if len(set(slot_ids)) != len(slot_ids):
        raise ValueError("citations must be unique by slot_id")
    # Two citations that carry the same target, placement, and sources are the
    # same statement rendered twice, which would double-cite the answer.
    semantic_keys = [
        (
            citation.target_kind,
            citation.target_id,
            citation.placement,
            tuple(source.evidence_id for source in citation.sources),
        )
        for citation in value
    ]
    if len(set(semantic_keys)) != len(semantic_keys):
        raise ValueError("citations must not repeat the same target, placement, and sources")
    return value


_Citations = Annotated[
    tuple[FinalCitation, ...],
    Field(max_length=64),
    AfterValidator(_require_unique_citations),
]


class FinalAnswer(ContractModel):
    """The single successfully finalized answer artifact returned by the AI Core."""

    model_config = ConfigDict(
        json_schema_extra={
            "$schema": JSON_SCHEMA_DIALECT,
            "$id": FINAL_ANSWER_SCHEMA_ID,
        }
    )

    schema_version: Literal["1.0.0"] = FINAL_ANSWER_SCHEMA_VERSION
    final_answer_id: _Uuid4
    request_id: _Uuid4
    # A FinalAnswer only exists after a valid AnswerPlan, so the plan reference
    # is required even for a post-plan finalization failure.
    answer_plan_id: _Uuid4
    evidence_bundle_id: _Uuid4
    route_decision_id: _Uuid4
    plan_id: _Uuid4
    authorization_decision_id: _Uuid4
    runtime_snapshot_id: _Uuid4
    correlation_id: _Uuid4
    finalized_at: UtcDateTime
    outcome: FinalOutcome
    validated_content: FinalValidatedContent | None = None
    citations: _Citations = ()
    outcome_reason_codes: _OutcomeReasonCodes = ()
    # DomainError is reused unchanged: it already carries the canonical code,
    # safe message key, retryability, and opaque internal reference. Embedding
    # ErrorEnvelope would duplicate identity and schema version at this level.
    safe_error: DomainError | None = None
    freshness_note: FinalFreshnessNote
    applied_length_budget: AnswerLengthBudget
    response_metadata: FinalResponseMetadata
    finalizer_version: SchemaVersion

    def _content_items(self) -> tuple[tuple[str, str], ...]:
        if self.validated_content is None:
            return ()
        return tuple(
            (item.item_kind, item.item_id)
            for section in self.validated_content.sections
            for item in section.items
        )

    def _section_count(self) -> int:
        if self.validated_content is None:
            return 0
        return len(self.validated_content.sections)

    def _claim_count(self) -> int:
        return sum(1 for kind, _ in self._content_items() if kind == "claim")

    def _caveat_count(self) -> int:
        return sum(1 for kind, _ in self._content_items() if kind == "caveat")

    def _character_count(self) -> int:
        # The canonical count is the sum of rendered item text lengths in Python
        # Unicode code points. Citation labels, UI separators, UI headings, and
        # transport syntax are never counted.
        if self.validated_content is None:
            return 0
        return sum(
            len(item.rendered_text)
            for section in self.validated_content.sections
            for item in section.items
        )

    def _require_valid_citation_links(self) -> None:
        known_items = set(self._content_items())
        for citation in self.citations:
            target = (citation.target_kind, citation.target_id)
            if target not in known_items:
                raise ValueError(
                    f"citation slot {citation.slot_id!r} targets unknown "
                    f"{citation.target_kind} {citation.target_id!r}"
                )
        cited_claims = {
            citation.target_id for citation in self.citations if citation.target_kind == "claim"
        }
        for kind, item_id in self._content_items():
            # A caveat may stand without a citation, but a factual claim must
            # always disclose at least one compiled source.
            if kind == "claim" and item_id not in cited_claims:
                raise ValueError(f"claim {item_id!r} requires at least one citation")

    def _require_consistent_counts(self) -> None:
        metadata = self.response_metadata
        expected = (
            ("section_count", self._section_count(), metadata.section_count),
            ("claim_count", self._claim_count(), metadata.claim_count),
            ("caveat_count", self._caveat_count(), metadata.caveat_count),
            ("citation_count", len(self.citations), metadata.citation_count),
            ("character_count", self._character_count(), metadata.character_count),
        )
        for name, actual, declared in expected:
            if actual != declared:
                raise ValueError(f"{name} must be {actual}, not {declared}")

    def _require_within_budget(self) -> None:
        budget = self.applied_length_budget
        limits = (
            ("sections", self._section_count(), budget.max_sections),
            ("claims", self._claim_count(), budget.max_claims),
            ("caveats", self._caveat_count(), budget.max_caveats),
            ("citations", len(self.citations), budget.max_citations),
            ("characters", self._character_count(), budget.max_characters),
        )
        for name, actual, allowed in limits:
            if actual > allowed:
                raise ValueError(f"{name} count {actual} exceeds the applied budget {allowed}")

    def _require_content_outcome(self) -> FinalValidatedContent:
        if self.validated_content is None:
            raise ValueError(f"{self.outcome} requires validated content")
        if self.safe_error is not None:
            raise ValueError(f"{self.outcome} must not carry a safe error")
        metadata = self.response_metadata
        if metadata.response_locale is None:
            raise ValueError(f"{self.outcome} requires a response locale")
        if metadata.generation_mode == "none":
            raise ValueError(f"{self.outcome} requires a real generation mode")
        if metadata.validation_status != "passed":
            raise ValueError(f"{self.outcome} requires passed content validation")
        return self.validated_content

    def _require_answered_shape(self) -> None:
        self._require_content_outcome()
        if self._claim_count() < 1:
            raise ValueError("answered requires at least one claim item")
        if self.outcome_reason_codes:
            raise ValueError("answered must not carry outcome reason codes")
        answer_type = self.response_metadata.answer_type
        if answer_type is None:
            raise ValueError("answered requires an answer type")
        if answer_type in _NARRATIVE_ANSWER_TYPES:
            raise ValueError(f"answered must not use answer type {answer_type!r}")

    def _require_partial_shape(self) -> None:
        self._require_content_outcome()
        if self._claim_count() < 1:
            raise ValueError("partially_answered requires at least one claim item")
        if self._caveat_count() < 1:
            raise ValueError("partially_answered requires at least one caveat item")
        if not self.outcome_reason_codes:
            raise ValueError("partially_answered requires at least one outcome reason code")
        if self.response_metadata.degraded is not True:
            raise ValueError("partially_answered requires degraded to be true")
        answer_type = self.response_metadata.answer_type
        if answer_type is None:
            raise ValueError("partially_answered requires an answer type")
        if answer_type in _NARRATIVE_ANSWER_TYPES:
            raise ValueError(f"partially_answered must not use answer type {answer_type!r}")

    def _require_narrative_shape(self, expected_answer_type: str) -> None:
        self._require_content_outcome()
        if self._claim_count() != 0:
            raise ValueError(f"{self.outcome} must not contain a claim item")
        if self._caveat_count() < 1:
            raise ValueError(f"{self.outcome} requires at least one caveat item")
        if not self.outcome_reason_codes:
            raise ValueError(f"{self.outcome} requires at least one outcome reason code")
        if self.response_metadata.answer_type != expected_answer_type:
            raise ValueError(f"{self.outcome} requires answer type {expected_answer_type!r}")
        for citation in self.citations:
            if citation.target_kind != "caveat":
                raise ValueError(f"{self.outcome} citations must target a caveat")

    def _require_failed_shape(self) -> None:
        if self.validated_content is not None:
            raise ValueError("failed must not carry validated content")
        if self.citations:
            raise ValueError("failed must not carry citations")
        if self.safe_error is None:
            raise ValueError("failed requires a safe error")
        if not self.outcome_reason_codes:
            raise ValueError("failed requires at least one outcome reason code")
        if self.freshness_note.status != "not_applicable":
            raise ValueError("failed requires not_applicable freshness")
        metadata = self.response_metadata
        if metadata.response_locale is not None:
            raise ValueError("failed must not carry a response locale")
        if metadata.answer_type is not None:
            raise ValueError("failed must not carry an answer type")
        if metadata.generation_mode != "none":
            raise ValueError("failed requires generation mode 'none'")
        if metadata.validation_status != "not_applicable":
            raise ValueError("failed requires not_applicable content validation")
        if metadata.degraded is not True:
            raise ValueError("failed requires degraded to be true")
        zero_counts = (
            metadata.section_count,
            metadata.claim_count,
            metadata.caveat_count,
            metadata.citation_count,
            metadata.character_count,
        )
        if any(count != 0 for count in zero_counts):
            raise ValueError("failed requires every response count to be zero")
        # A failed FinalAnswer is a trusted post-plan finalization failure. Codes
        # describing a request, authorization, or normal product outcome belong
        # to the error-envelope and routing paths instead.
        code = self.safe_error.code
        if code in _PROHIBITED_FAILURE_CODES:
            raise ValueError(f"failed must not use pre-finalization error code {code!r}")
        if code not in _PERMITTED_FAILURE_CODES:
            raise ValueError(f"failed must not use error code {code!r}")

    @model_validator(mode="after")
    def _require_consistent_final_answer(self) -> Self:
        self._require_valid_citation_links()
        self._require_consistent_counts()
        self._require_within_budget()
        match self.outcome:
            case "answered":
                self._require_answered_shape()
            case "partially_answered":
                self._require_partial_shape()
            case "clarification_required":
                self._require_narrative_shape("clarification")
            case "abstained":
                self._require_narrative_shape("abstention")
            case "failed":
                self._require_failed_shape()
        return self
