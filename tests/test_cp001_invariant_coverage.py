"""Negative and branch tests closing the remaining CP-001 invariant gaps.

Every test here proves one architectural invariant that had no executed
assertion: identifier validation, hierarchy path consistency, guest fallback,
release ordering, provider selection lineage, legal hold state transitions, and
source revision identity binding. None of these invariants may regress silently.
"""

import unittest
from datetime import UTC, datetime, timedelta

from pydantic import ValidationError

from ai_assistant.contracts.configuration import (
    ConfigurationActivationRef,
    ConfigurationArtifactRef,
    ConfigurationArtifactRevisionRef,
    ConfigurationRelease,
    LogicalModelPool,
)
from ai_assistant.contracts.model_gateway import (
    ModelInvocationResult,
    ProviderSelectionLineage,
)
from ai_assistant.contracts.organization import (
    HierarchyPathRef,
    Organization,
    OrganizationalNode,
)
from ai_assistant.contracts.principal import AuthorizationRequest, RequestActorContext
from ai_assistant.contracts.runtime_lineage import LegalHoldRef, RuntimeLineage
from ai_assistant.contracts.source_registry import (
    CitationSafePublishedSourceMetadata,
    SourceRelationship,
    SourceRevision,
)

ORG_ID = "11111111-1111-4111-8111-111111111111"
OTHER_ORG_ID = "22222222-2222-4222-8222-222222222222"
ROOT_NODE_ID = "33333333-3333-4333-8333-333333333333"
CHILD_NODE_ID = "44444444-4444-4444-8444-444444444444"
GRANDCHILD_NODE_ID = "55555555-5555-4555-8555-555555555555"
PRINCIPAL_ID = "66666666-6666-4666-8666-666666666666"
SECURITY_CONTEXT_ID = "77777777-7777-4777-8777-777777777777"
RECORD_ID = "88888888-8888-4888-8888-888888888888"
SECOND_RECORD_ID = "99999999-9999-4999-8999-999999999999"
SOURCE_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
OTHER_SOURCE_ID = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
REVISION_ID = "cccccccc-cccc-4ccc-8ccc-cccccccccccc"
NEXT_REVISION_ID = "dddddddd-dddd-4ddd-8ddd-dddddddddddd"
# A version 1 identifier: syntactically a UUID, but not an accepted identifier.
NON_V4_ID = "11111111-1111-1111-8111-111111111111"
DIGEST = "sha256:" + "a" * 64
OTHER_DIGEST = "sha256:" + "b" * 64
CREATED_AT = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
UPLOADED_AT = datetime(2026, 1, 1, 9, 0, tzinfo=UTC)
PUBLISHED_AT = datetime(2025, 6, 1, 0, 0, tzinfo=UTC)


def organization_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "organization_id": ORG_ID,
        "display_name": "Central Organization",
        "status": "active",
        "root_node_id": ROOT_NODE_ID,
        "created_at": CREATED_AT,
    }
    payload.update(overrides)
    return payload


def path_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "organization_id": ORG_ID,
        "node_id": CHILD_NODE_ID,
        "root_node_id": ROOT_NODE_ID,
        "ancestor_node_ids": (ROOT_NODE_ID,),
        "depth": 1,
        "path_revision": "paths-1",
    }
    payload.update(overrides)
    return payload


def node_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "organization_id": ORG_ID,
        "node_id": CHILD_NODE_ID,
        "node_type": {"code": "department", "vocabulary_revision": "node-types-3"},
        "display_name": "Cardiology Department",
        "is_root": False,
        "parent": {"organization_id": ORG_ID, "node_id": ROOT_NODE_ID},
        "status": "active",
        "created_at": CREATED_AT,
    }
    payload.update(overrides)
    return payload


def root_node_payload(**overrides: object) -> dict[str, object]:
    payload = node_payload(
        node_id=ROOT_NODE_ID,
        display_name="Central Root",
        is_root=True,
        parent=None,
    )
    payload.update(overrides)
    return payload


def guest_actor_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "actor_kind": "anonymous_guest",
        "guest": {
            "guest_session_id": SECOND_RECORD_ID,
            "organization_id": ORG_ID,
            "established_at": CREATED_AT,
            "visibility_class": "anonymous-public",
        },
    }
    payload.update(overrides)
    return payload


def authorization_request_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "request_id": RECORD_ID,
        "organization_id": ORG_ID,
        "actor": {
            "actor_kind": "authenticated_principal",
            "authenticated_principal": {
                "principal_id": PRINCIPAL_ID,
                "security_context_id": SECURITY_CONTEXT_ID,
                "organization_id": ORG_ID,
            },
        },
        "action": "read",
        "permission": {"permission_code": "source.read", "catalog_revision": "perms-4"},
        "resource": {
            "resource_type": "document",
            "resource_id": "doc-1",
            "classification": "confidential",
        },
        "requested_at": CREATED_AT,
        "request_fingerprint": DIGEST,
    }
    payload.update(overrides)
    return payload


def manifest_entry_payload() -> dict[str, object]:
    return {
        "artifact": {
            "namespace": "security-policy",
            "artifact_id": "security-policy",
            "revision": "7",
            "digest": DIGEST,
        },
        "owner_role": "platform-owner",
        "operator_changeable": False,
    }


def release_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "release_id": RECORD_ID,
        "release_label": "2026.01.1",
        "status": "draft",
        "manifest": (manifest_entry_payload(),),
        "manifest_digest": DIGEST,
        "created_at": CREATED_AT,
    }
    payload.update(overrides)
    return payload


def deployment_payload(deployment_ref: str = "deployment-a") -> dict[str, object]:
    return {
        "deployment_ref": deployment_ref,
        "provider_ref": "provider-a",
        "model_ref": "model-a",
        "credential": {
            "credential_ref": "credential-a",
            "credential_class": "model-provider-key",
        },
        "compatibility_class": "chat-completion-v1",
        "preference_rank": 0,
        "request_timeout_ms": 30_000,
    }


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


def exhausted_selection_payload() -> dict[str, object]:
    """Lineage of an invocation where no attempt completed."""
    return {
        "pool": {"pool_code": "analysis", "catalog_revision": "pools-2"},
        "attempts": (
            {
                "attempt_index": 1,
                "deployment_ref": "deployment-a",
                "started_at": CREATED_AT,
                "outcome": "timed_out",
                "reason_code": "deadline-exceeded",
            },
        ),
    }


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


def lineage_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "lineage_id": RECORD_ID,
        "organization_id": ORG_ID,
        "actor_scope": {
            "organization_id": ORG_ID,
            "node_refs": ({"organization_id": ORG_ID, "node_id": CHILD_NODE_ID},),
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
        "retention": {
            "retention_class": "audit-standard",
            "policy_revision": "2",
            "retention_days": 365,
        },
        "recorded_at": CREATED_AT,
    }
    payload.update(overrides)
    return payload


def emergency_action_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "action_id": RECORD_ID,
        "action_code": "disable-source",
        "occurred_at": CREATED_AT,
        "reason_code": "operator-request",
    }
    payload.update(overrides)
    return payload


def authority_payload() -> dict[str, object]:
    return {
        "authority_class_ref": "official-regulation",
        "issuer_ref": "issuer-ministry-of-health",
        "authority_assignment_policy_ref": "authority-assignment-default",
        "catalog_revision": "authority-3",
    }


def temporal_payload() -> dict[str, object]:
    return {
        "effective_from": PUBLISHED_AT,
        "published_at": PUBLISHED_AT,
        "recorded_by_principal_id": PRINCIPAL_ID,
        "recorded_at": CREATED_AT,
    }


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


def isolation_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "organization_id": ORG_ID,
        "owner_node": {"organization_id": ORG_ID, "node_id": CHILD_NODE_ID},
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


def management_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "owner_node": {"organization_id": ORG_ID, "node_id": CHILD_NODE_ID},
        "owner_principal_id": PRINCIPAL_ID,
        "uploaded_at": UPLOADED_AT,
        "review_state": "approved",
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
        "lifecycle_audit": {
            "reason_code": "operator-approval",
            "transitioned_at": CREATED_AT,
            "transitioned_by_principal_id": PRINCIPAL_ID,
        },
        "isolation": isolation_payload(),
        "raw_content": {
            "content_ref": "content-object-1",
            "content_digest": OTHER_DIGEST,
            "media_type": "application/pdf",
            "byte_size": 4096,
        },
    }
    payload.update(overrides)
    return payload


class IdentifierAndTextValidationTests(unittest.TestCase):
    def test_non_version_4_identifier_is_rejected(self) -> None:
        # A predictable or sequential identifier must never enter a contract.
        with self.assertRaises(ValidationError):
            Organization(**organization_payload(organization_id=NON_V4_ID))

    def test_display_text_rejects_the_nul_character(self) -> None:
        # A NUL byte can truncate a label in a log, export, or citation.
        with self.assertRaises(ValidationError):
            Organization(**organization_payload(display_name="Central\x00Organization"))

    def test_display_text_rejects_surrounding_whitespace(self) -> None:
        # Padding is rejected rather than normalized, so two labels can never
        # compare unequal while rendering identically.
        with self.assertRaises(ValidationError):
            Organization(**organization_payload(display_name=" Central Organization "))

    def test_duplicate_reason_codes_are_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            RuntimeLineage(
                **lineage_payload(
                    outcome="failed",
                    reason_codes=("upstream-timeout", "upstream-timeout"),
                )
            )

    def test_duplicate_ancestor_identifiers_are_rejected(self) -> None:
        # A repeated ancestor would describe a cycle in a materialized path.
        with self.assertRaises(ValidationError):
            HierarchyPathRef(
                **path_payload(
                    ancestor_node_ids=(ROOT_NODE_ID, ROOT_NODE_ID),
                    depth=2,
                )
            )


class HierarchyPathTests(unittest.TestCase):
    def test_first_ancestor_must_be_the_root_node(self) -> None:
        with self.assertRaises(ValidationError):
            HierarchyPathRef(
                **path_payload(
                    node_id=GRANDCHILD_NODE_ID,
                    ancestor_node_ids=(CHILD_NODE_ID, ROOT_NODE_ID),
                    depth=2,
                )
            )

    def test_consistent_path_is_accepted(self) -> None:
        path = HierarchyPathRef(**path_payload())
        self.assertEqual(path.depth, 1)
        self.assertEqual(str(path.ancestor_node_ids[0]), ROOT_NODE_ID)


class OrganizationalNodeStructureTests(unittest.TestCase):
    def test_root_node_without_a_parent_is_accepted(self) -> None:
        node = OrganizationalNode(**root_node_payload())
        self.assertTrue(node.is_root)
        self.assertIsNone(node.parent)

    def test_status_change_must_not_precede_creation(self) -> None:
        with self.assertRaises(ValidationError):
            OrganizationalNode(**node_payload(status_changed_at=CREATED_AT - timedelta(minutes=1)))

    def test_path_must_describe_this_node(self) -> None:
        with self.assertRaises(ValidationError):
            OrganizationalNode(**node_payload(path=path_payload(node_id=GRANDCHILD_NODE_ID)))
        with self.assertRaises(ValidationError):
            OrganizationalNode(
                **node_payload(
                    path=path_payload(
                        organization_id=OTHER_ORG_ID,
                        ancestor_node_ids=(),
                        depth=0,
                        root_node_id=CHILD_NODE_ID,
                    )
                )
            )

    def test_root_node_requires_a_depth_zero_path(self) -> None:
        with self.assertRaises(ValidationError):
            OrganizationalNode(
                **root_node_payload(
                    path=path_payload(
                        node_id=ROOT_NODE_ID,
                        root_node_id=GRANDCHILD_NODE_ID,
                        ancestor_node_ids=(GRANDCHILD_NODE_ID,),
                        depth=1,
                    )
                )
            )

    def test_non_root_node_requires_a_non_empty_ancestor_path(self) -> None:
        with self.assertRaises(ValidationError):
            OrganizationalNode(
                **node_payload(
                    path=path_payload(
                        root_node_id=CHILD_NODE_ID,
                        ancestor_node_ids=(),
                        depth=0,
                    )
                )
            )

    def test_last_ancestor_must_be_the_declared_parent(self) -> None:
        with self.assertRaises(ValidationError):
            OrganizationalNode(
                **node_payload(
                    path=path_payload(
                        ancestor_node_ids=(ROOT_NODE_ID, GRANDCHILD_NODE_ID),
                        depth=2,
                    )
                )
            )

    def test_consistent_node_and_path_are_accepted(self) -> None:
        node = OrganizationalNode(**node_payload(path=path_payload()))
        root = OrganizationalNode(
            **root_node_payload(
                path=path_payload(
                    node_id=ROOT_NODE_ID,
                    root_node_id=ROOT_NODE_ID,
                    ancestor_node_ids=(),
                    depth=0,
                )
            )
        )
        self.assertIsNotNone(node.path)
        self.assertIsNotNone(root.path)


class ActorAndRequestTests(unittest.TestCase):
    def test_guest_actor_must_not_carry_an_authenticated_principal(self) -> None:
        # A failed authentication must never be downgraded into a guest that
        # still carries principal identity.
        with self.assertRaises(ValidationError):
            RequestActorContext(
                **guest_actor_payload(
                    authenticated_principal={
                        "principal_id": PRINCIPAL_ID,
                        "security_context_id": SECURITY_CONTEXT_ID,
                        "organization_id": ORG_ID,
                    }
                )
            )

    def test_absent_requested_scope_is_accepted_and_grants_nothing(self) -> None:
        # An absent scope is a narrower request, never "every node".
        request = AuthorizationRequest(**authorization_request_payload())
        self.assertIsNone(request.requested_scope)


class ConfigurationReleaseTests(unittest.TestCase):
    def test_artifact_revision_exposes_its_unversioned_identity(self) -> None:
        revision = ConfigurationArtifactRevisionRef(
            namespace="security-policy",
            artifact_id="security-policy",
            revision="7",
            digest=DIGEST,
        )
        self.assertEqual(
            revision.artifact_ref,
            ConfigurationArtifactRef(namespace="security-policy", artifact_id="security-policy"),
        )
        self.assertEqual(revision.qualified_id, "security-policy/security-policy")

    def test_validation_must_not_precede_creation(self) -> None:
        with self.assertRaises(ValidationError):
            ConfigurationRelease(
                **release_payload(
                    status="validated",
                    validated_at=CREATED_AT - timedelta(minutes=1),
                )
            )

    def test_activation_target_and_previous_release_must_differ(self) -> None:
        with self.assertRaises(ValidationError):
            ConfigurationActivationRef(
                activation_id=RECORD_ID,
                kind="rollback",
                target_release_id=SECOND_RECORD_ID,
                previous_release_id=SECOND_RECORD_ID,
                occurred_at=CREATED_AT,
                reason_code="operator-request",
            )

    def test_probe_evidence_of_a_pool_deployment_is_accepted(self) -> None:
        pool = LogicalModelPool(
            pool={"pool_code": "analysis", "catalog_revision": "pools-2"},
            compatibility_class="chat-completion-v1",
            deployments=(deployment_payload(),),
            probe_evidence=(
                {
                    "probe_id": RECORD_ID,
                    "deployment_ref": "deployment-a",
                    "probe_kind": "capability-probe",
                    "evaluated_at": CREATED_AT,
                    "evidence_digest": DIGEST,
                },
            ),
        )
        self.assertEqual(len(pool.probe_evidence), 1)


class ProviderSelectionLineageTests(unittest.TestCase):
    def test_non_completed_attempt_requires_a_reason_code(self) -> None:
        with self.assertRaises(ValidationError):
            ProviderSelectionLineage(
                pool={"pool_code": "analysis", "catalog_revision": "pools-2"},
                attempts=(
                    {
                        "attempt_index": 1,
                        "deployment_ref": "deployment-a",
                        "started_at": CREATED_AT,
                        "outcome": "failed",
                    },
                ),
            )

    def test_completed_attempt_requires_a_selected_deployment(self) -> None:
        with self.assertRaises(ValidationError):
            ProviderSelectionLineage(**selection_payload(selected_deployment_ref=None))

    def test_selected_deployment_requires_a_completed_attempt(self) -> None:
        with self.assertRaises(ValidationError):
            ProviderSelectionLineage(
                pool={"pool_code": "analysis", "catalog_revision": "pools-2"},
                attempts=(
                    {
                        "attempt_index": 1,
                        "deployment_ref": "deployment-a",
                        "started_at": CREATED_AT,
                        "outcome": "timed_out",
                        "reason_code": "deadline-exceeded",
                    },
                ),
                selected_deployment_ref="deployment-a",
            )

    def test_selected_deployment_must_be_the_completed_one(self) -> None:
        with self.assertRaises(ValidationError):
            ProviderSelectionLineage(
                pool={"pool_code": "analysis", "catalog_revision": "pools-2"},
                attempts=(
                    {
                        "attempt_index": 1,
                        "deployment_ref": "deployment-a",
                        "started_at": CREATED_AT,
                        "outcome": "timed_out",
                        "reason_code": "deadline-exceeded",
                    },
                    {
                        "attempt_index": 2,
                        "deployment_ref": "deployment-b",
                        "started_at": CREATED_AT,
                        "outcome": "completed",
                    },
                ),
                selected_deployment_ref="deployment-a",
            )


class ModelInvocationResultTests(unittest.TestCase):
    def test_completed_result_requires_a_selected_deployment(self) -> None:
        with self.assertRaises(ValidationError):
            ModelInvocationResult(
                **invocation_result_payload(selection=exhausted_selection_payload())
            )

    def test_non_completed_result_requires_a_reason_code(self) -> None:
        with self.assertRaises(ValidationError):
            ModelInvocationResult(
                **invocation_result_payload(
                    outcome="failed",
                    content=None,
                    finish_reason=None,
                    usage={"input_tokens": 120, "output_tokens": 0},
                    selection=exhausted_selection_payload(),
                )
            )

    def test_non_completed_result_must_not_report_output_tokens(self) -> None:
        with self.assertRaises(ValidationError):
            ModelInvocationResult(
                **invocation_result_payload(
                    outcome="failed",
                    content=None,
                    finish_reason=None,
                    reason_code="upstream-failure",
                    usage={"input_tokens": 120, "output_tokens": 12},
                    selection=exhausted_selection_payload(),
                )
            )


class RuntimeLineageScopeTests(unittest.TestCase):
    def test_released_hold_requires_a_later_release_instant(self) -> None:
        with self.assertRaises(ValidationError):
            LegalHoldRef(
                hold_id=RECORD_ID,
                state="released",
                reason_code="litigation-closed",
                placed_at=CREATED_AT,
                released_at=CREATED_AT,
            )

    def test_absent_actor_scope_is_accepted_and_means_no_scope(self) -> None:
        lineage = RuntimeLineage(**lineage_payload(actor_scope=None))
        self.assertIsNone(lineage.actor_scope)

    def test_emergency_action_must_belong_to_the_lineage_organization(self) -> None:
        with self.assertRaises(ValidationError):
            RuntimeLineage(
                **lineage_payload(
                    emergency_action=emergency_action_payload(organization_id=OTHER_ORG_ID)
                )
            )

    def test_platform_wide_emergency_action_is_accepted(self) -> None:
        lineage = RuntimeLineage(**lineage_payload(emergency_action=emergency_action_payload()))
        self.assertIsNotNone(lineage.emergency_action)


class SourceRevisionIdentityTests(unittest.TestCase):
    def test_official_url_citation_metadata_carries_its_locator(self) -> None:
        citation = CitationSafePublishedSourceMetadata(**citation_payload("official_url"))
        self.assertEqual(citation.source_type, "official_url")
        self.assertIsNotNone(citation.public_locator)

    def test_isolation_metadata_must_match_the_revision_organization(self) -> None:
        with self.assertRaises(ValidationError):
            SourceRevision(
                **revision_payload(
                    isolation=isolation_payload(
                        organization_id=OTHER_ORG_ID,
                        owner_node={"organization_id": OTHER_ORG_ID, "node_id": CHILD_NODE_ID},
                    )
                )
            )

    def test_owner_node_must_belong_to_the_revision_organization(self) -> None:
        with self.assertRaises(ValidationError):
            SourceRevision(
                **revision_payload(
                    management=management_payload(
                        owner_node={"organization_id": OTHER_ORG_ID, "node_id": CHILD_NODE_ID}
                    )
                )
            )

    def test_citation_metadata_must_declare_the_same_source_type(self) -> None:
        with self.assertRaises(ValidationError):
            SourceRevision(**revision_payload(citation_safe=citation_payload("official_url")))

    def test_supersession_instant_must_not_precede_creation(self) -> None:
        with self.assertRaises(ValidationError):
            SourceRevision(
                **revision_payload(
                    status="superseded",
                    superseded_by_revision_id=NEXT_REVISION_ID,
                    superseded_at=CREATED_AT - timedelta(minutes=1),
                )
            )

    def test_supplements_relationship_must_not_carry_a_supersedes_link(self) -> None:
        with self.assertRaises(ValidationError):
            SourceRelationship(
                relationship_id=RECORD_ID,
                organization_id=ORG_ID,
                relationship_type="supplements",
                supplements={"from_source_id": SOURCE_ID, "to_source_id": OTHER_SOURCE_ID},
                supersedes={
                    "source_id": SOURCE_ID,
                    "superseding_revision_id": NEXT_REVISION_ID,
                    "superseded_revision_id": REVISION_ID,
                },
                declared_at=CREATED_AT,
                reason_code="operator-declared",
            )


if __name__ == "__main__":
    unittest.main()
