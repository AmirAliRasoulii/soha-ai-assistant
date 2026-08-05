"""Tests for the CP-001 source registry, relationship, runtime lineage, and
model gateway contract families.

The invariants proven here are the ones the architecture depends on: metadata
class separation, immutable revisions, one active revision, nullable open-ended
validity, upload time separated from publication time, the full outcome
taxonomy with authorization denial kept distinct from policy rejection, and a
provider-neutral, credential-free, deadline-aware model boundary.
"""

import json
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from ai_assistant.contracts.model_gateway import (
    MAX_MESSAGE_CHARACTERS,
    MAX_MESSAGES,
    MODEL_INVOCATION_REQUEST_SCHEMA_ID,
    MODEL_INVOCATION_RESULT_SCHEMA_ID,
    ModelInvocationRequest,
    ModelInvocationResult,
    ModelStreamChunk,
    ProviderSelectionLineage,
)
from ai_assistant.contracts.runtime_lineage import (
    MAX_LINEAGE_SOURCE_REVISIONS,
    RUNTIME_LINEAGE_SCHEMA_ID,
    LegalHoldRef,
    LineageTimeScope,
    RetentionPolicyRef,
    RuntimeLineage,
)
from ai_assistant.contracts.source_registry import (
    KNOWLEDGE_SOURCE_SCHEMA_ID,
    SOURCE_RELATIONSHIP_SCHEMA_ID,
    SOURCE_REVISION_SCHEMA_ID,
    CitationSafePublishedSourceMetadata,
    KnowledgeSource,
    LifecycleAuditMetadata,
    ManagementSourceMetadata,
    MandatoryIsolationMetadata,
    ProposedSourceTemporalMetadata,
    RawSourceContentRef,
    SourceRelationship,
    SourceRevision,
    TrustedSourceTemporalMetadata,
)

SCHEMAS = Path(__file__).resolve().parents[1] / "schemas"

ORG_ID = "11111111-1111-4111-8111-111111111111"
OTHER_ORG_ID = "22222222-2222-4222-8222-222222222222"
NODE_ID = "33333333-3333-4333-8333-333333333333"
SOURCE_ID = "44444444-4444-4444-8444-444444444444"
REVISION_ID = "55555555-5555-4555-8555-555555555555"
NEXT_REVISION_ID = "66666666-6666-4666-8666-666666666666"
PRINCIPAL_ID = "77777777-7777-4777-8777-777777777777"
RECORD_ID = "88888888-8888-4888-8888-888888888888"
SECOND_RECORD_ID = "99999999-9999-4999-8999-999999999999"
OTHER_SOURCE_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
DIGEST = "sha256:" + "a" * 64
OTHER_DIGEST = "sha256:" + "b" * 64
UPLOADED_AT = datetime(2026, 1, 10, 9, 0, tzinfo=UTC)
PUBLISHED_AT = datetime(2025, 6, 1, 0, 0, tzinfo=UTC)
CREATED_AT = datetime(2026, 1, 10, 10, 0, tzinfo=UTC)


def load_artifact(name: str) -> dict[str, Any]:
    artifact: dict[str, Any] = json.loads(
        (SCHEMAS / name / "1.0.0.schema.json").read_text(encoding="utf-8")
    )
    return artifact


def authority_payload() -> dict[str, object]:
    return {
        "authority_class_ref": "official-regulation",
        "issuer_ref": "issuer-ministry-of-health",
        "authority_assignment_policy_ref": "authority-assignment-default",
        "catalog_revision": "authority-3",
    }


def temporal_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "effective_from": PUBLISHED_AT,
        "published_at": PUBLISHED_AT,
        "recorded_by_principal_id": PRINCIPAL_ID,
        "recorded_at": CREATED_AT,
    }
    payload.update(overrides)
    return payload


def citation_payload(
    source_type: str = "uploaded_document", **overrides: object
) -> dict[str, object]:
    payload: dict[str, object] = {
        "title": "Admission Regulation 2025",
        "source_type": source_type,
        "authority": authority_payload(),
        "temporal": temporal_payload(),
    }
    if source_type == "official_url":
        payload["public_locator"] = "https://example.org/regulation"
    payload.update(overrides)
    return payload


def management_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "owner_node": {"organization_id": ORG_ID, "node_id": NODE_ID},
        "owner_principal_id": PRINCIPAL_ID,
        "uploaded_at": UPLOADED_AT,
        "review_state": "approved",
    }
    payload.update(overrides)
    return payload


def isolation_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "organization_id": ORG_ID,
        "owner_node": {"organization_id": ORG_ID, "node_id": NODE_ID},
        "visibility_policy": {
            "visibility_policy_id": "visibility-internal",
            "policy_revision": "4",
            "policy_digest": DIGEST,
        },
        "source_id": SOURCE_ID,
        "revision_id": REVISION_ID,
        "index_namespace": "org-index-primary",
    }
    payload.update(overrides)
    return payload


def raw_content_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "content_ref": "content-object-1",
        "content_digest": OTHER_DIGEST,
        "media_type": "application/pdf",
        "byte_size": 4096,
    }
    payload.update(overrides)
    return payload


def audit_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "reason_code": "operator-approval",
        "transitioned_at": CREATED_AT,
        "transitioned_by_principal_id": PRINCIPAL_ID,
    }
    payload.update(overrides)
    return payload


def source_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "source_id": SOURCE_ID,
        "organization_id": ORG_ID,
        "owner_node": {"organization_id": ORG_ID, "node_id": NODE_ID},
        "source_type": "uploaded_document",
        "stable_key": "regulation-admissions",
        "status": "active",
        "created_at": CREATED_AT,
        "active_revision_id": REVISION_ID,
    }
    payload.update(overrides)
    return payload


def revision_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "revision_id": REVISION_ID,
        "source_id": SOURCE_ID,
        "organization_id": ORG_ID,
        "revision_number": 1,
        "source_type": "uploaded_document",
        "status": "active",
        "created_at": CREATED_AT,
        "citation_safe": citation_payload(),
        "management": management_payload(),
        "lifecycle_audit": audit_payload(),
        "isolation": isolation_payload(),
        "raw_content": raw_content_payload(),
    }
    payload.update(overrides)
    return payload


def retention_payload() -> dict[str, object]:
    return {"retention_class": "audit-standard", "policy_revision": "2", "retention_days": 365}


def selection_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "pool": {"pool_code": "analysis", "catalog_revision": "pools-2"},
        "attempts": (
            {
                "attempt_index": 1,
                "deployment_ref": "deployment-a",
                "started_at": CREATED_AT,
                "outcome": "completed",
            },
        ),
        "selected_deployment_ref": "deployment-a",
    }
    payload.update(overrides)
    return payload


def lineage_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "lineage_id": RECORD_ID,
        "organization_id": ORG_ID,
        "actor_scope": {
            "organization_id": ORG_ID,
            "node_refs": ({"organization_id": ORG_ID, "node_id": NODE_ID},),
        },
        "actor_principal_id": PRINCIPAL_ID,
        "subject": {"subject_type": "question", "subject_id": "question-1"},
        "time_scope": {"as_of": CREATED_AT},
        "source_revisions": ({"source_id": SOURCE_ID, "revision_id": REVISION_ID},),
        "consulted_policy": {
            "policy_id": "authorization-policy",
            "policy_revision": "12",
            "policy_digest": DIGEST,
        },
        "configuration_release": {
            "release_id": SECOND_RECORD_ID,
            "release_label": "2026.01.1",
            "manifest_digest": DIGEST,
        },
        "runtime_snapshot": {"snapshot_id": SECOND_RECORD_ID, "content_digest": OTHER_DIGEST},
        "run_id": RECORD_ID,
        "request_id": SECOND_RECORD_ID,
        "outcome": "answered",
        "retention": retention_payload(),
        "recorded_at": CREATED_AT,
    }
    payload.update(overrides)
    return payload


def invocation_request_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "invocation_id": RECORD_ID,
        "request_id": SECOND_RECORD_ID,
        "run_id": RECORD_ID,
        "pool": {"pool_code": "analysis", "catalog_revision": "pools-2"},
        "purpose": "query-analysis",
        "messages": (
            {"role": "system", "content": "You answer only from provided evidence."},
            {"role": "user", "content": "What is the admission deadline?"},
        ),
        "max_output_tokens": 512,
        "issued_at": CREATED_AT,
        "deadline_at": CREATED_AT + timedelta(seconds=30),
        "runtime_snapshot_id": SECOND_RECORD_ID,
    }
    payload.update(overrides)
    return payload


def invocation_result_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "invocation_id": RECORD_ID,
        "request_id": SECOND_RECORD_ID,
        "outcome": "completed",
        "content": "The deadline is 1 September.",
        "finish_reason": "stop",
        "usage": {"input_tokens": 120, "output_tokens": 18},
        "selection": selection_payload(),
        "completed_at": CREATED_AT,
    }
    payload.update(overrides)
    return payload


class SourceRegistryTests(unittest.TestCase):
    def test_valid_source_and_revision_construct(self) -> None:
        source = KnowledgeSource(**source_payload())
        revision = SourceRevision(**revision_payload())
        self.assertEqual(source.status, "active")
        self.assertEqual(revision.revision_number, 1)

    def test_only_two_source_types_are_representable(self) -> None:
        for source_type in ("uploaded_document", "official_url"):
            with self.subTest(source_type=source_type):
                self.assertEqual(
                    KnowledgeSource(**source_payload(source_type=source_type)).source_type,
                    source_type,
                )
        with self.assertRaises(ValidationError):
            KnowledgeSource(**source_payload(source_type="crawled_page"))

    def test_metadata_classes_are_separate_resources(self) -> None:
        # A reader receiving citation-safe metadata can never receive owner,
        # review, audit, or raw-content fields through the same value.
        citation_fields = set(CitationSafePublishedSourceMetadata.model_fields)
        for forbidden in (
            "owner_node",
            "owner_principal_id",
            "review_state",
            "reason_code",
            "content_ref",
            "raw_locator",
            "uploaded_at",
            "status",
        ):
            self.assertNotIn(forbidden, citation_fields)
        self.assertEqual(citation_fields & set(ManagementSourceMetadata.model_fields), set())
        self.assertEqual(citation_fields & set(LifecycleAuditMetadata.model_fields), set())
        self.assertEqual(citation_fields & set(RawSourceContentRef.model_fields), set())

    def test_upload_time_is_not_publication_time(self) -> None:
        revision = SourceRevision(**revision_payload())
        self.assertNotIn("uploaded_at", set(TrustedSourceTemporalMetadata.model_fields))
        self.assertNotIn("published_at", set(ManagementSourceMetadata.model_fields))
        self.assertEqual(revision.management.uploaded_at, UPLOADED_AT)
        self.assertEqual(revision.citation_safe.temporal.published_at, PUBLISHED_AT)
        self.assertLess(revision.citation_safe.temporal.published_at, UPLOADED_AT)

    def test_valid_until_is_nullable_and_ordered(self) -> None:
        open_ended = TrustedSourceTemporalMetadata(**temporal_payload())
        self.assertIsNone(open_ended.valid_until)
        with self.assertRaises(ValidationError):
            TrustedSourceTemporalMetadata(**temporal_payload(valid_until=PUBLISHED_AT))

    def test_proposed_temporal_metadata_is_a_separate_untrusted_shape(self) -> None:
        proposal = ProposedSourceTemporalMetadata(
            proposed_effective_from=PUBLISHED_AT,
            proposed_by_principal_id=PRINCIPAL_ID,
            proposed_at=UPLOADED_AT,
        )
        self.assertEqual(
            set(type(proposal).model_fields) & set(TrustedSourceTemporalMetadata.model_fields),
            set(),
        )
        with self.assertRaises(ValidationError):
            ProposedSourceTemporalMetadata(
                proposed_effective_from=PUBLISHED_AT,
                proposed_valid_until=PUBLISHED_AT,
                proposed_by_principal_id=PRINCIPAL_ID,
                proposed_at=UPLOADED_AT,
            )

    def test_official_url_requires_a_public_locator_and_upload_must_not_have_one(self) -> None:
        with self.assertRaises(ValidationError):
            CitationSafePublishedSourceMetadata(
                **citation_payload("official_url", public_locator=None)
            )
        with self.assertRaises(ValidationError):
            CitationSafePublishedSourceMetadata(
                **citation_payload("uploaded_document", public_locator="https://example.org/x")
            )

    def test_uploaded_document_requires_stored_content(self) -> None:
        with self.assertRaises(ValidationError):
            SourceRevision(**revision_payload(raw_content=None))

    def test_revision_isolation_metadata_must_describe_this_revision(self) -> None:
        with self.assertRaises(ValidationError):
            SourceRevision(
                **revision_payload(isolation=isolation_payload(revision_id=NEXT_REVISION_ID))
            )
        with self.assertRaises(ValidationError):
            SourceRevision(
                **revision_payload(isolation=isolation_payload(source_id=OTHER_SOURCE_ID))
            )

    def test_isolation_metadata_must_stay_inside_one_organization(self) -> None:
        with self.assertRaises(ValidationError):
            MandatoryIsolationMetadata(**isolation_payload(organization_id=OTHER_ORG_ID))

    def test_isolation_metadata_carries_the_visibility_policy_revision(self) -> None:
        isolation = MandatoryIsolationMetadata(**isolation_payload())
        self.assertEqual(isolation.visibility_policy.policy_revision, "4")

    def test_active_revision_carries_no_supersession(self) -> None:
        with self.assertRaises(ValidationError):
            SourceRevision(
                **revision_payload(
                    superseded_by_revision_id=NEXT_REVISION_ID,
                    superseded_at=CREATED_AT,
                )
            )

    def test_superseded_revision_must_name_its_successor(self) -> None:
        with self.assertRaises(ValidationError):
            SourceRevision(**revision_payload(status="superseded"))
        superseded = SourceRevision(
            **revision_payload(
                status="superseded",
                superseded_by_revision_id=NEXT_REVISION_ID,
                superseded_at=CREATED_AT + timedelta(days=1),
            )
        )
        self.assertEqual(str(superseded.superseded_by_revision_id), NEXT_REVISION_ID)

    def test_revision_cannot_supersede_itself(self) -> None:
        with self.assertRaises(ValidationError):
            SourceRevision(
                **revision_payload(
                    status="superseded",
                    superseded_by_revision_id=REVISION_ID,
                    superseded_at=CREATED_AT + timedelta(days=1),
                )
            )

    def test_revision_is_immutable_in_place(self) -> None:
        revision = SourceRevision(**revision_payload())
        with self.assertRaises(ValidationError):
            revision.status = "superseded"  # type: ignore[misc]
        with self.assertRaises(ValidationError):
            revision.citation_safe.temporal.valid_until = CREATED_AT  # type: ignore[misc]

    def test_at_most_one_active_revision_is_expressible(self) -> None:
        annotation = KnowledgeSource.model_fields["active_revision_id"].annotation
        self.assertNotIn("tuple", str(annotation).lower())
        self.assertNotIn("list", str(annotation).lower())

    def test_inactive_source_cannot_carry_an_active_revision(self) -> None:
        for status in ("archived", "revoked"):
            with self.subTest(status=status):
                with self.assertRaises(ValidationError):
                    KnowledgeSource(**source_payload(status=status))
                source = KnowledgeSource(**source_payload(status=status, active_revision_id=None))
                self.assertIsNone(source.active_revision_id)

    def test_ownership_states_no_access(self) -> None:
        for model in (KnowledgeSource, ManagementSourceMetadata):
            declared = set(model.model_fields)
            for forbidden in ("readers", "permissions", "can_read", "allowed_principals"):
                self.assertNotIn(forbidden, declared)

    def test_owner_node_must_belong_to_the_source_organization(self) -> None:
        with self.assertRaises(ValidationError):
            KnowledgeSource(
                **source_payload(owner_node={"organization_id": OTHER_ORG_ID, "node_id": NODE_ID})
            )

    def test_media_type_and_size_are_validated(self) -> None:
        with self.assertRaises(ValidationError):
            RawSourceContentRef(**raw_content_payload(media_type="not-a-media-type"))
        with self.assertRaises(ValidationError):
            RawSourceContentRef(**raw_content_payload(byte_size=0))
        with self.assertRaises(ValidationError):
            RawSourceContentRef(**raw_content_payload(content_digest="deadbeef"))

    def test_round_trip_and_schema_parity(self) -> None:
        source = KnowledgeSource(**source_payload())
        revision = SourceRevision(**revision_payload())
        self.assertEqual(KnowledgeSource.model_validate_json(source.model_dump_json()), source)
        self.assertEqual(SourceRevision.model_validate_json(revision.model_dump_json()), revision)
        self.assertEqual(load_artifact("knowledge-source"), KnowledgeSource.model_json_schema())
        self.assertEqual(load_artifact("source-revision"), SourceRevision.model_json_schema())
        self.assertEqual(KnowledgeSource.model_json_schema()["$id"], KNOWLEDGE_SOURCE_SCHEMA_ID)
        self.assertEqual(SourceRevision.model_json_schema()["$id"], SOURCE_REVISION_SCHEMA_ID)


class SourceRelationshipTests(unittest.TestCase):
    def supersedes_payload(self, **overrides: object) -> dict[str, object]:
        payload: dict[str, object] = {
            "relationship_id": RECORD_ID,
            "organization_id": ORG_ID,
            "relationship_type": "supersedes",
            "supersedes": {
                "source_id": SOURCE_ID,
                "superseding_revision_id": NEXT_REVISION_ID,
                "superseded_revision_id": REVISION_ID,
            },
            "declared_at": CREATED_AT,
            "reason_code": "new-edition",
        }
        payload.update(overrides)
        return payload

    def supplements_payload(self, **overrides: object) -> dict[str, object]:
        payload: dict[str, object] = {
            "relationship_id": RECORD_ID,
            "organization_id": ORG_ID,
            "relationship_type": "supplements",
            "supplements": {"from_source_id": SOURCE_ID, "to_source_id": OTHER_SOURCE_ID},
            "declared_at": CREATED_AT,
            "reason_code": "clarifies",
        }
        payload.update(overrides)
        return payload

    def test_supersedes_is_within_one_source(self) -> None:
        relationship = SourceRelationship(**self.supersedes_payload())
        self.assertIsNotNone(relationship.supersedes)
        assert relationship.supersedes is not None
        self.assertEqual(str(relationship.supersedes.source_id), SOURCE_ID)
        self.assertNotIn("to_source_id", set(type(relationship.supersedes).model_fields))

    def test_supplements_is_across_two_distinct_sources(self) -> None:
        relationship = SourceRelationship(**self.supplements_payload())
        assert relationship.supplements is not None
        self.assertNotEqual(
            relationship.supplements.from_source_id, relationship.supplements.to_source_id
        )
        with self.assertRaises(ValidationError):
            SourceRelationship(
                **self.supplements_payload(
                    supplements={"from_source_id": SOURCE_ID, "to_source_id": SOURCE_ID}
                )
            )

    def test_supersedes_requires_two_distinct_revisions(self) -> None:
        with self.assertRaises(ValidationError):
            SourceRelationship(
                **self.supersedes_payload(
                    supersedes={
                        "source_id": SOURCE_ID,
                        "superseding_revision_id": REVISION_ID,
                        "superseded_revision_id": REVISION_ID,
                    }
                )
            )

    def test_relationship_type_and_link_must_agree(self) -> None:
        with self.assertRaises(ValidationError):
            SourceRelationship(**self.supersedes_payload(supersedes=None))
        with self.assertRaises(ValidationError):
            SourceRelationship(
                **self.supersedes_payload(
                    supplements={"from_source_id": SOURCE_ID, "to_source_id": OTHER_SOURCE_ID}
                )
            )
        with self.assertRaises(ValidationError):
            SourceRelationship(**self.supplements_payload(supplements=None))

    def test_deferred_relationship_kinds_are_unrepresentable(self) -> None:
        # AMENDS and PARTIALLY_SUPERSEDES have no canonical decision yet, so the
        # closed union must reject them rather than let anyone infer them.
        for relationship_type in ("amends", "partially_supersedes", "AMENDS"):
            with self.subTest(relationship_type=relationship_type):
                with self.assertRaises(ValidationError):
                    SourceRelationship(
                        **self.supersedes_payload(relationship_type=relationship_type)
                    )

    def test_round_trip_and_schema_parity(self) -> None:
        relationship = SourceRelationship(**self.supplements_payload())
        self.assertEqual(
            SourceRelationship.model_validate_json(relationship.model_dump_json()), relationship
        )
        self.assertEqual(
            load_artifact("source-relationship"), SourceRelationship.model_json_schema()
        )
        self.assertEqual(
            SourceRelationship.model_json_schema()["$id"], SOURCE_RELATIONSHIP_SCHEMA_ID
        )


class RuntimeLineageTests(unittest.TestCase):
    def test_valid_lineage_constructs_with_all_nine_elements(self) -> None:
        lineage = RuntimeLineage(**lineage_payload())
        self.assertEqual(str(lineage.organization_id), ORG_ID)
        self.assertIsNotNone(lineage.actor_scope)
        self.assertEqual(lineage.subject.subject_type, "question")
        self.assertEqual(lineage.time_scope.as_of, CREATED_AT)
        self.assertEqual(len(lineage.source_revisions), 1)
        self.assertEqual(lineage.consulted_policy.policy_revision, "12")
        self.assertEqual(lineage.configuration_release.release_label, "2026.01.1")
        self.assertEqual(str(lineage.runtime_snapshot.snapshot_id), SECOND_RECORD_ID)
        self.assertEqual(str(lineage.run_id), RECORD_ID)
        self.assertEqual(str(lineage.request_id), SECOND_RECORD_ID)

    def test_full_outcome_taxonomy_is_representable(self) -> None:
        outcomes = {
            "answered": {},
            "partial": {"reason_codes": ("evidence-incomplete",)},
            "clarification_required": {"reason_codes": ("ambiguous-question",)},
            "abstained": {"reason_codes": ("no-supporting-evidence",)},
            "policy_rejected": {"reason_codes": ("unsafe-request",)},
            "authorization_denied": {
                "reason_codes": ("scope-not-authorized",),
                "authorization_decision_id": SECOND_RECORD_ID,
            },
            "failed": {"reason_codes": ("internal-error",)},
            "cancelled": {"reason_codes": ("client-cancelled",)},
        }
        for outcome, extra in outcomes.items():
            with self.subTest(outcome=outcome):
                lineage = RuntimeLineage(**lineage_payload(outcome=outcome, **extra))
                self.assertEqual(lineage.outcome, outcome)

    def test_authorization_denied_and_policy_rejected_are_never_the_same(self) -> None:
        denied = RuntimeLineage(
            **lineage_payload(
                outcome="authorization_denied",
                reason_codes=("scope-not-authorized",),
                authorization_decision_id=SECOND_RECORD_ID,
            )
        )
        rejected = RuntimeLineage(
            **lineage_payload(outcome="policy_rejected", reason_codes=("unsafe-request",))
        )
        self.assertNotEqual(denied.outcome, rejected.outcome)
        # A denial must be traceable to a decision.
        with self.assertRaises(ValidationError):
            RuntimeLineage(
                **lineage_payload(
                    outcome="authorization_denied", reason_codes=("scope-not-authorized",)
                )
            )
        # A content rejection must not borrow an authorization decision.
        with self.assertRaises(ValidationError):
            RuntimeLineage(
                **lineage_payload(
                    outcome="policy_rejected",
                    reason_codes=("unsafe-request",),
                    authorization_decision_id=SECOND_RECORD_ID,
                )
            )

    def test_non_answer_outcomes_require_reason_codes(self) -> None:
        with self.assertRaises(ValidationError):
            RuntimeLineage(**lineage_payload(outcome="failed"))

    def test_answered_outcome_requires_source_lineage(self) -> None:
        with self.assertRaises(ValidationError):
            RuntimeLineage(**lineage_payload(source_revisions=()))

    def test_actor_scope_must_belong_to_the_lineage_organization(self) -> None:
        foreign_scope = {
            "organization_id": OTHER_ORG_ID,
            "node_refs": ({"organization_id": OTHER_ORG_ID, "node_id": NODE_ID},),
        }
        with self.assertRaises(ValidationError):
            RuntimeLineage(**lineage_payload(actor_scope=foreign_scope))

    def test_source_lineage_is_bounded_and_unique(self) -> None:
        duplicated = (
            {"source_id": SOURCE_ID, "revision_id": REVISION_ID},
            {"source_id": OTHER_SOURCE_ID, "revision_id": REVISION_ID},
        )
        with self.assertRaises(ValidationError):
            RuntimeLineage(**lineage_payload(source_revisions=duplicated))
        too_many = tuple(
            {
                "source_id": SOURCE_ID,
                "revision_id": f"{index:08x}-0000-4000-8000-000000000000",
            }
            for index in range(MAX_LINEAGE_SOURCE_REVISIONS + 1)
        )
        with self.assertRaises(ValidationError):
            RuntimeLineage(**lineage_payload(source_revisions=too_many))

    def test_time_scope_window_must_be_ordered(self) -> None:
        with self.assertRaises(ValidationError):
            LineageTimeScope(as_of=CREATED_AT, valid_from=CREATED_AT, valid_until=CREATED_AT)

    def test_retention_reference_carries_no_deletion_behavior(self) -> None:
        retention = RetentionPolicyRef(**retention_payload())
        self.assertEqual(retention.retention_days, 365)
        for forbidden in ("delete_after", "purge", "deleted", "expired"):
            self.assertNotIn(forbidden, set(RetentionPolicyRef.model_fields))
        with self.assertRaises(ValidationError):
            RetentionPolicyRef(
                retention_class="audit-standard", policy_revision="2", retention_days=0
            )

    def test_legal_hold_state_is_consistent(self) -> None:
        active = LegalHoldRef(
            hold_id=RECORD_ID,
            state="active",
            reason_code="litigation",
            placed_at=CREATED_AT,
        )
        self.assertIsNone(active.released_at)
        with self.assertRaises(ValidationError):
            LegalHoldRef(
                hold_id=RECORD_ID,
                state="active",
                reason_code="litigation",
                placed_at=CREATED_AT,
                released_at=CREATED_AT + timedelta(days=1),
            )
        with self.assertRaises(ValidationError):
            LegalHoldRef(
                hold_id=RECORD_ID,
                state="released",
                reason_code="litigation",
                placed_at=CREATED_AT,
            )

    def test_published_audit_event_outcome_union_is_untouched(self) -> None:
        from ai_assistant.contracts.audit import AuditEvent

        committed = json.loads(
            (SCHEMAS / "audit-event" / "1.0.0.schema.json").read_text(encoding="utf-8")
        )
        self.assertEqual(committed, AuditEvent.model_json_schema())
        self.assertEqual(
            committed["properties"]["outcome"]["enum"], ["success", "denied", "failed"]
        )

    def test_round_trip_and_schema_parity(self) -> None:
        lineage = RuntimeLineage(**lineage_payload())
        self.assertEqual(RuntimeLineage.model_validate_json(lineage.model_dump_json()), lineage)
        self.assertEqual(load_artifact("runtime-lineage"), RuntimeLineage.model_json_schema())
        self.assertEqual(RuntimeLineage.model_json_schema()["$id"], RUNTIME_LINEAGE_SCHEMA_ID)


class ModelGatewayContractTests(unittest.TestCase):
    def test_valid_request_and_result_construct(self) -> None:
        request = ModelInvocationRequest(**invocation_request_payload())
        result = ModelInvocationResult(**invocation_result_payload())
        self.assertEqual(request.pool.pool_code, "analysis")
        self.assertEqual(result.outcome, "completed")

    def test_request_addresses_a_logical_pool_not_a_provider(self) -> None:
        declared = set(ModelInvocationRequest.model_fields)
        for forbidden in (
            "provider",
            "provider_ref",
            "model",
            "model_name",
            "deployment_ref",
            "base_url",
            "endpoint",
            "api_key",
            "credential",
            "credential_ref",
            "headers",
        ):
            self.assertNotIn(forbidden, declared)

    def test_request_is_deadline_aware(self) -> None:
        with self.assertRaises(ValidationError):
            ModelInvocationRequest(**invocation_request_payload(deadline_at=CREATED_AT))
        with self.assertRaises(ValidationError):
            payload = invocation_request_payload()
            del payload["deadline_at"]
            ModelInvocationRequest(**payload)

    def test_messages_are_bounded_and_sanitized(self) -> None:
        with self.assertRaises(ValidationError):
            ModelInvocationRequest(**invocation_request_payload(messages=()))
        too_many = tuple(
            {"role": "user", "content": f"question {index}"} for index in range(MAX_MESSAGES + 1)
        )
        with self.assertRaises(ValidationError):
            ModelInvocationRequest(**invocation_request_payload(messages=too_many))
        oversized = ({"role": "user", "content": "x" * (MAX_MESSAGE_CHARACTERS + 1)},)
        with self.assertRaises(ValidationError):
            ModelInvocationRequest(**invocation_request_payload(messages=oversized))
        for content in ("   ", "bad\x00content"):
            with self.subTest(content=content):
                with self.assertRaises(ValidationError):
                    ModelInvocationRequest(
                        **invocation_request_payload(
                            messages=({"role": "user", "content": content},)
                        )
                    )

    def test_output_budget_is_bounded(self) -> None:
        for value in (0, 1_000_000):
            with self.subTest(value=value):
                with self.assertRaises(ValidationError):
                    ModelInvocationRequest(**invocation_request_payload(max_output_tokens=value))

    def test_non_completed_outcomes_carry_no_content(self) -> None:
        for outcome in ("refused", "timed_out", "cancelled", "failed"):
            with self.subTest(outcome=outcome):
                with self.assertRaises(ValidationError):
                    ModelInvocationResult(**invocation_result_payload(outcome=outcome))
                result = ModelInvocationResult(
                    **invocation_result_payload(
                        outcome=outcome,
                        content=None,
                        finish_reason=None,
                        reason_code="deadline-exceeded",
                        usage={"input_tokens": 120, "output_tokens": 0},
                        selection=selection_payload(
                            attempts=(
                                {
                                    "attempt_index": 1,
                                    "deployment_ref": "deployment-a",
                                    "started_at": CREATED_AT,
                                    "outcome": outcome,
                                    "reason_code": "deadline-exceeded",
                                },
                            ),
                            selected_deployment_ref=None,
                        ),
                    )
                )
                self.assertIsNone(result.content)

    def test_completed_result_requires_content_and_a_selected_deployment(self) -> None:
        with self.assertRaises(ValidationError):
            ModelInvocationResult(**invocation_result_payload(content=None))

    def test_selection_lineage_records_fallback(self) -> None:
        selection = ProviderSelectionLineage(
            **selection_payload(
                attempts=(
                    {
                        "attempt_index": 1,
                        "deployment_ref": "deployment-a",
                        "started_at": CREATED_AT,
                        "outcome": "failed",
                        "reason_code": "upstream-unavailable",
                    },
                    {
                        "attempt_index": 2,
                        "deployment_ref": "deployment-b",
                        "started_at": CREATED_AT + timedelta(seconds=1),
                        "outcome": "completed",
                    },
                ),
                selected_deployment_ref="deployment-b",
            )
        )
        self.assertTrue(selection.fallback_used)
        single = ProviderSelectionLineage(**selection_payload())
        self.assertFalse(single.fallback_used)

    def test_selected_deployment_must_be_a_completed_attempt(self) -> None:
        with self.assertRaises(ValidationError):
            ProviderSelectionLineage(
                **selection_payload(selected_deployment_ref="deployment-unknown")
            )
        with self.assertRaises(ValidationError):
            ProviderSelectionLineage(
                **selection_payload(
                    attempts=(
                        {
                            "attempt_index": 1,
                            "deployment_ref": "deployment-a",
                            "started_at": CREATED_AT,
                            "outcome": "completed",
                        },
                        {
                            "attempt_index": 2,
                            "deployment_ref": "deployment-b",
                            "started_at": CREATED_AT,
                            "outcome": "completed",
                        },
                    )
                )
            )

    def test_attempt_indexes_are_unique_and_bounded(self) -> None:
        with self.assertRaises(ValidationError):
            ProviderSelectionLineage(
                **selection_payload(
                    attempts=(
                        {
                            "attempt_index": 1,
                            "deployment_ref": "deployment-a",
                            "started_at": CREATED_AT,
                            "outcome": "failed",
                            "reason_code": "upstream-unavailable",
                        },
                        {
                            "attempt_index": 1,
                            "deployment_ref": "deployment-b",
                            "started_at": CREATED_AT,
                            "outcome": "completed",
                        },
                    ),
                    selected_deployment_ref="deployment-b",
                )
            )

    def test_stream_chunks_are_ordered_and_terminated(self) -> None:
        chunk = ModelStreamChunk(
            invocation_id=RECORD_ID, sequence_index=0, delta="partial", is_final=False
        )
        final = ModelStreamChunk(invocation_id=RECORD_ID, sequence_index=1, is_final=True)
        self.assertFalse(chunk.is_final)
        self.assertTrue(final.is_final)
        with self.assertRaises(ValidationError):
            ModelStreamChunk(invocation_id=RECORD_ID, sequence_index=0, is_final=False)

    def test_gateway_contracts_carry_no_secret_or_provider_payload(self) -> None:
        request = ModelInvocationRequest(**invocation_request_payload())
        result = ModelInvocationResult(**invocation_result_payload())
        for serialized in (request.model_dump_json(), result.model_dump_json()):
            for marker in ("api_key", "sk-", "authorization", "bearer", "litellm", "openai"):
                self.assertNotIn(marker, serialized.lower())

    def test_round_trip_and_schema_parity(self) -> None:
        request = ModelInvocationRequest(**invocation_request_payload())
        result = ModelInvocationResult(**invocation_result_payload())
        self.assertEqual(
            ModelInvocationRequest.model_validate_json(request.model_dump_json()), request
        )
        self.assertEqual(
            ModelInvocationResult.model_validate_json(result.model_dump_json()), result
        )
        self.assertEqual(
            load_artifact("model-invocation-request"), ModelInvocationRequest.model_json_schema()
        )
        self.assertEqual(
            load_artifact("model-invocation-result"), ModelInvocationResult.model_json_schema()
        )
        self.assertEqual(
            ModelInvocationRequest.model_json_schema()["$id"],
            MODEL_INVOCATION_REQUEST_SCHEMA_ID,
        )
        self.assertEqual(
            ModelInvocationResult.model_json_schema()["$id"], MODEL_INVOCATION_RESULT_SCHEMA_ID
        )


if __name__ == "__main__":
    unittest.main()
