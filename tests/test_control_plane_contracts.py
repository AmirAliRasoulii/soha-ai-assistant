"""Tests for the CP-001 organization, membership, principal, and configuration
contract families.

These tests prove architectural invariants, not field presence: cross-organization
parenting, root re-parenting, scope widening, guest fallback, secret leakage, and
unbounded collections must all be unrepresentable.
"""

import json
import unittest
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from ai_assistant.contracts.configuration import (
    CONFIGURATION_RELEASE_SCHEMA_ID,
    MAX_MANIFEST_ENTRIES,
    MODEL_POOL_POLICY_SCHEMA_ID,
    ActiveConfigurationReleaseRef,
    ConfigurationActivationRef,
    ConfigurationArtifactRevisionRef,
    ConfigurationRelease,
    CredentialRef,
    LogicalModelPool,
    LogicalModelPoolRef,
    ModelDeploymentRef,
    ModelPoolPolicy,
    ProbeEvidenceRef,
    ReleaseManifestEntry,
)
from ai_assistant.contracts.membership import (
    MAX_SCOPE_NODES,
    NODE_MEMBERSHIP_SCHEMA_ID,
    SCOPED_ROLE_ASSIGNMENT_SCHEMA_ID,
    AuthorizationScopeRef,
    NodeMembership,
    PermissionRef,
    RoleRef,
    ScopedRoleAssignment,
    ValidityWindow,
)
from ai_assistant.contracts.organization import (
    MAX_HIERARCHY_DEPTH,
    NODE_TYPE_DEPARTMENT,
    ORGANIZATION_SCHEMA_ID,
    ORGANIZATIONAL_NODE_SCHEMA_ID,
    HierarchyPathRef,
    Organization,
    OrganizationalNode,
    OrganizationalNodeRef,
)
from ai_assistant.contracts.principal import (
    AUTHORIZATION_REQUEST_SCHEMA_ID,
    REQUEST_ACTOR_CONTEXT_SCHEMA_ID,
    AnonymousGuest,
    AuthenticatedPrincipalRef,
    AuthorizationRequest,
    ConsultedPolicyRevisionRef,
    DecisionBindingRef,
    RequestActorContext,
)
from ai_assistant.contracts.security import AuthorizationResourceRef

SCHEMAS = Path(__file__).resolve().parents[1] / "schemas"

ORG_ID = "11111111-1111-4111-8111-111111111111"
OTHER_ORG_ID = "22222222-2222-4222-8222-222222222222"
ROOT_NODE_ID = "33333333-3333-4333-8333-333333333333"
CHILD_NODE_ID = "44444444-4444-4444-8444-444444444444"
GRANDCHILD_NODE_ID = "55555555-5555-4555-8555-555555555555"
PRINCIPAL_ID = "66666666-6666-4666-8666-666666666666"
SECURITY_CONTEXT_ID = "77777777-7777-4777-8777-777777777777"
RECORD_ID = "88888888-8888-4888-8888-888888888888"
SECOND_RECORD_ID = "99999999-9999-4999-8999-999999999999"
DIGEST = "sha256:" + "a" * 64
OTHER_DIGEST = "sha256:" + "b" * 64
CREATED_AT = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


def load_artifact(name: str) -> dict[str, Any]:
    artifact: dict[str, Any] = json.loads(
        (SCHEMAS / name / "1.0.0.schema.json").read_text(encoding="utf-8")
    )
    return artifact


def node_type_payload(code: str = NODE_TYPE_DEPARTMENT) -> dict[str, object]:
    return {"code": code, "vocabulary_revision": "node-types-3"}


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


def node_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "organization_id": ORG_ID,
        "node_id": CHILD_NODE_ID,
        "node_type": node_type_payload(),
        "display_name": "Cardiology Department",
        "is_root": False,
        "parent": {"organization_id": ORG_ID, "node_id": ROOT_NODE_ID},
        "status": "active",
        "created_at": CREATED_AT,
    }
    payload.update(overrides)
    return payload


def validity_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {"valid_from": CREATED_AT}
    payload.update(overrides)
    return payload


def scope_payload(node_ids: tuple[str, ...] = (CHILD_NODE_ID,)) -> dict[str, object]:
    return {
        "organization_id": ORG_ID,
        "node_refs": tuple({"organization_id": ORG_ID, "node_id": node_id} for node_id in node_ids),
    }


def membership_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "membership_id": RECORD_ID,
        "organization_id": ORG_ID,
        "principal_id": PRINCIPAL_ID,
        "node": {"organization_id": ORG_ID, "node_id": CHILD_NODE_ID},
        "membership_kind": "primary",
        "status": "active",
        "validity": validity_payload(),
        "recorded_at": CREATED_AT,
    }
    payload.update(overrides)
    return payload


def assignment_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "assignment_id": RECORD_ID,
        "organization_id": ORG_ID,
        "principal_id": PRINCIPAL_ID,
        "role": {"role_code": "department-manager", "catalog_revision": "roles-7"},
        "scope": scope_payload(),
        "status": "active",
        "validity": validity_payload(),
        "assigned_at": CREATED_AT,
    }
    payload.update(overrides)
    return payload


def authenticated_actor_payload(organization_id: str = ORG_ID) -> dict[str, object]:
    return {
        "actor_kind": "authenticated_principal",
        "authenticated_principal": {
            "principal_id": PRINCIPAL_ID,
            "security_context_id": SECURITY_CONTEXT_ID,
            "organization_id": organization_id,
        },
    }


def guest_actor_payload(organization_id: str = ORG_ID) -> dict[str, object]:
    return {
        "actor_kind": "anonymous_guest",
        "guest": {
            "guest_session_id": SECOND_RECORD_ID,
            "organization_id": organization_id,
            "established_at": CREATED_AT,
            "visibility_class": "anonymous-public",
        },
    }


def authorization_request_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "request_id": RECORD_ID,
        "organization_id": ORG_ID,
        "actor": authenticated_actor_payload(),
        "action": "read",
        "permission": {"permission_code": "source.read", "catalog_revision": "perms-4"},
        "resource": {
            "resource_type": "document",
            "resource_id": "doc-1",
            "classification": "confidential",
        },
        "requested_scope": scope_payload(),
        "requested_at": CREATED_AT,
        "request_fingerprint": DIGEST,
    }
    payload.update(overrides)
    return payload


def artifact_revision_payload(artifact_id: str = "security-policy") -> dict[str, object]:
    return {
        "namespace": "security-policy",
        "artifact_id": artifact_id,
        "revision": "7",
        "digest": DIGEST,
    }


def manifest_entry_payload(artifact_id: str = "security-policy") -> dict[str, object]:
    return {
        "artifact": artifact_revision_payload(artifact_id),
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


def deployment_payload(
    deployment_ref: str = "deployment-a",
    preference_rank: int = 0,
    compatibility_class: str = "chat-completion-v1",
) -> dict[str, object]:
    return {
        "deployment_ref": deployment_ref,
        "provider_ref": "provider-a",
        "model_ref": "model-a",
        "credential": {
            "credential_ref": "credential-a",
            "credential_class": "model-provider-key",
        },
        "compatibility_class": compatibility_class,
        "preference_rank": preference_rank,
        "request_timeout_ms": 30_000,
    }


def pool_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "pool": {"pool_code": "analysis", "catalog_revision": "pools-2"},
        "compatibility_class": "chat-completion-v1",
        "deployments": (deployment_payload(),),
    }
    payload.update(overrides)
    return payload


def pool_policy_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "policy_revision": "pools-2",
        "published_at": CREATED_AT,
        "pools": (pool_payload(),),
    }
    payload.update(overrides)
    return payload


class OrganizationHierarchyTests(unittest.TestCase):
    def test_valid_organization_and_node_construct(self) -> None:
        organization = Organization(**organization_payload())
        node = OrganizationalNode(**node_payload())
        self.assertEqual(organization.schema_version, "1.0.0")
        self.assertEqual(node.node_type.code, NODE_TYPE_DEPARTMENT)
        self.assertEqual(str(node.node_ref.node_id), CHILD_NODE_ID)

    def test_department_is_only_a_node_type(self) -> None:
        # The same contract accepts any vocabulary term, so no structural
        # privilege can attach to "department".
        for code in ("department", "faculty", "ward", "project"):
            with self.subTest(code=code):
                node = OrganizationalNode(**node_payload(node_type=node_type_payload(code)))
                self.assertEqual(node.node_type.code, code)

    def test_root_node_cannot_carry_a_parent(self) -> None:
        with self.assertRaises(ValidationError):
            OrganizationalNode(
                **node_payload(
                    node_id=ROOT_NODE_ID,
                    is_root=True,
                    parent={"organization_id": ORG_ID, "node_id": CHILD_NODE_ID},
                )
            )

    def test_non_root_node_requires_a_parent(self) -> None:
        with self.assertRaises(ValidationError):
            OrganizationalNode(**node_payload(parent=None))

    def test_cross_organization_parenting_is_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            OrganizationalNode(
                **node_payload(parent={"organization_id": OTHER_ORG_ID, "node_id": ROOT_NODE_ID})
            )

    def test_node_cannot_be_its_own_parent(self) -> None:
        with self.assertRaises(ValidationError):
            OrganizationalNode(
                **node_payload(parent={"organization_id": ORG_ID, "node_id": CHILD_NODE_ID})
            )

    def test_root_path_must_describe_the_root_itself(self) -> None:
        with self.assertRaises(ValidationError):
            HierarchyPathRef(
                organization_id=ORG_ID,
                node_id=CHILD_NODE_ID,
                root_node_id=ROOT_NODE_ID,
                ancestor_node_ids=(),
                depth=0,
                path_revision="path-1",
            )

    def test_path_depth_must_match_ancestors(self) -> None:
        with self.assertRaises(ValidationError):
            HierarchyPathRef(
                organization_id=ORG_ID,
                node_id=GRANDCHILD_NODE_ID,
                root_node_id=ROOT_NODE_ID,
                ancestor_node_ids=(ROOT_NODE_ID, CHILD_NODE_ID),
                depth=1,
                path_revision="path-1",
            )

    def test_node_must_not_appear_in_its_own_path(self) -> None:
        with self.assertRaises(ValidationError):
            HierarchyPathRef(
                organization_id=ORG_ID,
                node_id=CHILD_NODE_ID,
                root_node_id=ROOT_NODE_ID,
                ancestor_node_ids=(ROOT_NODE_ID, CHILD_NODE_ID),
                depth=2,
                path_revision="path-1",
            )

    def test_hierarchy_depth_is_bounded(self) -> None:
        ancestors = tuple(f"{index:08x}-0000-4000-8000-000000000000" for index in range(40))
        with self.assertRaises(ValidationError):
            HierarchyPathRef(
                organization_id=ORG_ID,
                node_id=CHILD_NODE_ID,
                root_node_id=ancestors[0],
                ancestor_node_ids=ancestors,
                depth=len(ancestors),
                path_revision="path-1",
            )
        self.assertEqual(MAX_HIERARCHY_DEPTH, 32)

    def test_naive_timestamps_are_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            Organization(**organization_payload(created_at=datetime(2026, 1, 1, 12, 0)))

    def test_non_utc_timestamps_are_normalized(self) -> None:
        tehran = timezone(timedelta(hours=3, minutes=30))
        organization = Organization(
            **organization_payload(created_at=datetime(2026, 1, 1, 15, 30, tzinfo=tehran))
        )
        self.assertEqual(organization.created_at, CREATED_AT)

    def test_status_change_cannot_precede_creation(self) -> None:
        with self.assertRaises(ValidationError):
            Organization(
                **organization_payload(status_changed_at=CREATED_AT - timedelta(seconds=1))
            )

    def test_display_name_must_be_meaningful_text(self) -> None:
        for value in ("", "   ", "bad\u0007name"):
            with self.subTest(value=value):
                with self.assertRaises(ValidationError):
                    Organization(**organization_payload(display_name=value))

    def test_models_are_immutable(self) -> None:
        node = OrganizationalNode(**node_payload())
        with self.assertRaises(ValidationError):
            node.display_name = "Renamed"  # type: ignore[misc]

    def test_unknown_fields_are_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            OrganizationalNode(**node_payload(permissions=["read"]))

    def test_round_trip_is_deterministic(self) -> None:
        node = OrganizationalNode(**node_payload())
        dumped = node.model_dump_json()
        self.assertEqual(OrganizationalNode.model_validate_json(dumped), node)
        self.assertEqual(node.model_dump_json(), dumped)

    def test_schema_artifacts_match_the_models(self) -> None:
        self.assertEqual(load_artifact("organization"), Organization.model_json_schema())
        self.assertEqual(
            load_artifact("organizational-node"), OrganizationalNode.model_json_schema()
        )

    def test_schema_identifiers_are_stable(self) -> None:
        self.assertEqual(
            Organization.model_json_schema()["$id"],
            "urn:ai-assistant:contracts:organization:1.0.0",
        )
        self.assertEqual(
            OrganizationalNode.model_json_schema()["$id"],
            "urn:ai-assistant:contracts:organizational-node:1.0.0",
        )
        self.assertEqual(ORGANIZATION_SCHEMA_ID, "urn:ai-assistant:contracts:organization:1.0.0")
        self.assertEqual(
            ORGANIZATIONAL_NODE_SCHEMA_ID,
            "urn:ai-assistant:contracts:organizational-node:1.0.0",
        )


class MembershipAndScopeTests(unittest.TestCase):
    def test_valid_membership_and_assignment_construct(self) -> None:
        membership = NodeMembership(**membership_payload())
        assignment = ScopedRoleAssignment(**assignment_payload())
        self.assertEqual(str(membership.node.node_id), CHILD_NODE_ID)
        self.assertEqual(assignment.role.role_code, "department-manager")

    def test_membership_grants_no_permission_field(self) -> None:
        declared = set(NodeMembership.model_fields)
        for forbidden in ("permissions", "role", "scope", "can_read", "access"):
            self.assertNotIn(forbidden, declared)

    def test_scope_has_no_descendant_or_wildcard_flag(self) -> None:
        declared = set(AuthorizationScopeRef.model_fields)
        self.assertEqual(declared, {"organization_id", "node_refs"})
        for forbidden in ("include_descendants", "recursive", "subtree", "all_nodes"):
            self.assertNotIn(forbidden, declared)

    def test_scope_nodes_must_share_the_scope_organization(self) -> None:
        with self.assertRaises(ValidationError):
            AuthorizationScopeRef(
                organization_id=ORG_ID,
                node_refs=(
                    OrganizationalNodeRef(organization_id=OTHER_ORG_ID, node_id=CHILD_NODE_ID),
                ),
            )

    def test_scope_must_not_be_empty_and_is_bounded(self) -> None:
        with self.assertRaises(ValidationError):
            AuthorizationScopeRef(organization_id=ORG_ID, node_refs=())
        too_many = tuple(
            OrganizationalNodeRef(
                organization_id=ORG_ID,
                node_id=f"{index:08x}-0000-4000-8000-000000000000",
            )
            for index in range(MAX_SCOPE_NODES + 1)
        )
        with self.assertRaises(ValidationError):
            AuthorizationScopeRef(organization_id=ORG_ID, node_refs=too_many)

    def test_duplicate_scope_nodes_are_rejected(self) -> None:
        node_ref = OrganizationalNodeRef(organization_id=ORG_ID, node_id=CHILD_NODE_ID)
        with self.assertRaises(ValidationError):
            AuthorizationScopeRef(organization_id=ORG_ID, node_refs=(node_ref, node_ref))

    def test_assignment_scope_must_match_assignment_organization(self) -> None:
        with self.assertRaises(ValidationError):
            ScopedRoleAssignment(**assignment_payload(organization_id=OTHER_ORG_ID))

    def test_membership_node_must_match_membership_organization(self) -> None:
        with self.assertRaises(ValidationError):
            NodeMembership(
                **membership_payload(
                    node={"organization_id": OTHER_ORG_ID, "node_id": CHILD_NODE_ID}
                )
            )

    def test_validity_window_ordering(self) -> None:
        open_ended = ValidityWindow(valid_from=CREATED_AT)
        self.assertIsNone(open_ended.valid_until)
        with self.assertRaises(ValidationError):
            ValidityWindow(valid_from=CREATED_AT, valid_until=CREATED_AT)
        with self.assertRaises(ValidationError):
            ValidityWindow(valid_from=CREATED_AT, valid_until=CREATED_AT - timedelta(days=1))

    def test_role_and_permission_refs_are_catalog_bound(self) -> None:
        self.assertEqual(set(RoleRef.model_fields), {"role_code", "catalog_revision"})
        self.assertEqual(set(PermissionRef.model_fields), {"permission_code", "catalog_revision"})
        with self.assertRaises(ValidationError):
            RoleRef(role_code="Department Manager", catalog_revision="roles-7")

    def test_round_trip_and_schema_parity(self) -> None:
        membership = NodeMembership(**membership_payload())
        assignment = ScopedRoleAssignment(**assignment_payload())
        self.assertEqual(
            NodeMembership.model_validate_json(membership.model_dump_json()), membership
        )
        self.assertEqual(
            ScopedRoleAssignment.model_validate_json(assignment.model_dump_json()), assignment
        )
        self.assertEqual(load_artifact("node-membership"), NodeMembership.model_json_schema())
        self.assertEqual(
            load_artifact("scoped-role-assignment"), ScopedRoleAssignment.model_json_schema()
        )
        self.assertEqual(NodeMembership.model_json_schema()["$id"], NODE_MEMBERSHIP_SCHEMA_ID)
        self.assertEqual(
            ScopedRoleAssignment.model_json_schema()["$id"], SCOPED_ROLE_ASSIGNMENT_SCHEMA_ID
        )


class PrincipalBoundaryTests(unittest.TestCase):
    def test_authenticated_and_guest_actors_construct(self) -> None:
        authenticated = RequestActorContext(**authenticated_actor_payload())
        guest = RequestActorContext(**guest_actor_payload())
        self.assertEqual(str(authenticated.organization_id), ORG_ID)
        self.assertEqual(str(guest.organization_id), ORG_ID)

    def test_actor_kind_and_payload_must_agree(self) -> None:
        # An authentication failure cannot silently become a guest: the actor
        # kind and the actor value are validated against each other, and an
        # empty actor is not a valid context at all.
        with self.assertRaises(ValidationError):
            RequestActorContext(actor_kind="authenticated_principal")
        with self.assertRaises(ValidationError):
            RequestActorContext(actor_kind="anonymous_guest")
        with self.assertRaises(ValidationError):
            RequestActorContext(
                actor_kind="authenticated_principal",
                authenticated_principal={
                    "principal_id": PRINCIPAL_ID,
                    "security_context_id": SECURITY_CONTEXT_ID,
                    "organization_id": ORG_ID,
                },
                guest={
                    "guest_session_id": SECOND_RECORD_ID,
                    "organization_id": ORG_ID,
                    "established_at": CREATED_AT,
                    "visibility_class": "anonymous-public",
                },
            )

    def test_guest_and_authenticated_principals_are_distinct_types(self) -> None:
        self.assertNotIn("principal_id", set(AnonymousGuest.model_fields))
        self.assertNotIn("guest_session_id", set(AuthenticatedPrincipalRef.model_fields))

    def test_request_actor_organization_must_match_request(self) -> None:
        with self.assertRaises(ValidationError):
            AuthorizationRequest(
                **authorization_request_payload(actor=authenticated_actor_payload(OTHER_ORG_ID))
            )

    def test_requested_scope_must_match_request_organization(self) -> None:
        foreign_scope = {
            "organization_id": OTHER_ORG_ID,
            "node_refs": ({"organization_id": OTHER_ORG_ID, "node_id": CHILD_NODE_ID},),
        }
        with self.assertRaises(ValidationError):
            AuthorizationRequest(**authorization_request_payload(requested_scope=foreign_scope))

    def test_request_deadline_must_follow_request_instant(self) -> None:
        with self.assertRaises(ValidationError):
            AuthorizationRequest(**authorization_request_payload(deadline_at=CREATED_AT))

    def test_request_carries_no_decision_fields(self) -> None:
        declared = set(AuthorizationRequest.model_fields)
        for forbidden in ("allowed", "decision", "effect", "reason", "obligations"):
            self.assertNotIn(forbidden, declared)

    def test_request_fingerprint_syntax_is_validated(self) -> None:
        for value in ("deadbeef", "sha256:zz", "sha1:" + "a" * 40, "sha256:" + "A" * 64):
            with self.subTest(value=value):
                with self.assertRaises(ValidationError):
                    AuthorizationRequest(**authorization_request_payload(request_fingerprint=value))

    def test_decision_binding_requires_ordered_expiry(self) -> None:
        policy = ConsultedPolicyRevisionRef(
            policy_id="authorization-policy",
            policy_revision="12",
            policy_digest=DIGEST,
        )
        binding = DecisionBindingRef(
            request_id=RECORD_ID,
            decision_id=SECOND_RECORD_ID,
            request_fingerprint=DIGEST,
            consulted_policy=policy,
            authorized_scope=AuthorizationScopeRef(**scope_payload()),
            bound_at=CREATED_AT,
            expires_at=CREATED_AT + timedelta(minutes=5),
        )
        self.assertEqual(binding.consulted_policy.policy_revision, "12")
        with self.assertRaises(ValidationError):
            DecisionBindingRef(
                request_id=RECORD_ID,
                decision_id=SECOND_RECORD_ID,
                request_fingerprint=DIGEST,
                consulted_policy=policy,
                bound_at=CREATED_AT,
                expires_at=CREATED_AT,
            )

    def test_round_trip_and_schema_parity(self) -> None:
        request = AuthorizationRequest(**authorization_request_payload())
        self.assertEqual(
            AuthorizationRequest.model_validate_json(request.model_dump_json()), request
        )
        self.assertEqual(
            load_artifact("authorization-request"), AuthorizationRequest.model_json_schema()
        )
        self.assertEqual(
            load_artifact("request-actor-context"), RequestActorContext.model_json_schema()
        )
        self.assertEqual(
            AuthorizationRequest.model_json_schema()["$id"], AUTHORIZATION_REQUEST_SCHEMA_ID
        )
        self.assertEqual(
            RequestActorContext.model_json_schema()["$id"], REQUEST_ACTOR_CONTEXT_SCHEMA_ID
        )

    def test_existing_resource_reference_is_reused(self) -> None:
        request = AuthorizationRequest(**authorization_request_payload())
        self.assertIsInstance(request.resource, AuthorizationResourceRef)


class ConfigurationReleaseTests(unittest.TestCase):
    def test_valid_release_constructs(self) -> None:
        release = ConfigurationRelease(**release_payload())
        self.assertEqual(release.status, "draft")
        self.assertEqual(release.manifest[0].artifact.revision, "7")

    def test_validated_release_requires_validation_instant(self) -> None:
        with self.assertRaises(ValidationError):
            ConfigurationRelease(**release_payload(status="validated"))
        release = ConfigurationRelease(
            **release_payload(status="validated", validated_at=CREATED_AT + timedelta(minutes=1))
        )
        self.assertIsNotNone(release.validated_at)

    def test_draft_release_must_not_claim_validation(self) -> None:
        with self.assertRaises(ValidationError):
            ConfigurationRelease(**release_payload(validated_at=CREATED_AT + timedelta(minutes=1)))

    def test_release_cannot_supersede_itself(self) -> None:
        with self.assertRaises(ValidationError):
            ConfigurationRelease(**release_payload(previous_release_id=RECORD_ID))

    def test_manifest_must_be_non_empty_bounded_and_unique(self) -> None:
        with self.assertRaises(ValidationError):
            ConfigurationRelease(**release_payload(manifest=()))
        duplicated = (manifest_entry_payload(), manifest_entry_payload())
        with self.assertRaises(ValidationError):
            ConfigurationRelease(**release_payload(manifest=duplicated))
        too_many = tuple(
            manifest_entry_payload(f"artifact-{index}") for index in range(MAX_MANIFEST_ENTRIES + 1)
        )
        with self.assertRaises(ValidationError):
            ConfigurationRelease(**release_payload(manifest=too_many))

    def test_credential_reference_carries_no_secret(self) -> None:
        declared = set(CredentialRef.model_fields)
        self.assertEqual(declared, {"credential_ref", "credential_class", "rotated_at"})
        for forbidden in ("api_key", "secret", "token", "password", "value", "headers"):
            self.assertNotIn(forbidden, declared)
        with self.assertRaises(ValidationError):
            CredentialRef(
                credential_ref="credential-a",
                credential_class="model-provider-key",
                api_key="sk-live-1234",
            )

    def test_no_configuration_field_name_looks_like_a_secret(self) -> None:
        secret_names = {
            "api_key",
            "secret",
            "secret_value",
            "token",
            "password",
            "credential_value",
        }
        for model in (
            ConfigurationRelease,
            ConfigurationArtifactRevisionRef,
            ReleaseManifestEntry,
            ModelDeploymentRef,
            ProbeEvidenceRef,
            LogicalModelPool,
            ModelPoolPolicy,
            ActiveConfigurationReleaseRef,
            ConfigurationActivationRef,
        ):
            with self.subTest(model=model.__name__):
                self.assertEqual(set(model.model_fields) & secret_names, set())

    def test_serialized_release_contains_no_secret_material(self) -> None:
        policy = ModelPoolPolicy(**pool_policy_payload())
        serialized = policy.model_dump_json()
        for marker in ("sk-", "api_key", "password", "authorization:"):
            self.assertNotIn(marker, serialized)

    def test_pool_deployments_must_share_the_pool_compatibility_class(self) -> None:
        with self.assertRaises(ValidationError):
            LogicalModelPool(
                **pool_payload(
                    deployments=(deployment_payload(compatibility_class="embedding-v1"),)
                )
            )

    def test_pool_preference_ranks_must_be_unique(self) -> None:
        with self.assertRaises(ValidationError):
            LogicalModelPool(
                **pool_payload(
                    deployments=(
                        deployment_payload("deployment-a", 0),
                        deployment_payload("deployment-b", 0),
                    )
                )
            )

    def test_probe_evidence_must_reference_a_pool_deployment(self) -> None:
        with self.assertRaises(ValidationError):
            LogicalModelPool(
                **pool_payload(
                    probe_evidence=(
                        {
                            "probe_id": SECOND_RECORD_ID,
                            "deployment_ref": "deployment-unknown",
                            "probe_kind": "compatibility",
                            "evaluated_at": CREATED_AT,
                            "evidence_digest": OTHER_DIGEST,
                        },
                    )
                )
            )

    def test_pool_policy_pool_codes_are_unique(self) -> None:
        with self.assertRaises(ValidationError):
            ModelPoolPolicy(**pool_policy_payload(pools=(pool_payload(), pool_payload())))

    def test_pool_reference_is_provider_neutral(self) -> None:
        self.assertEqual(set(LogicalModelPoolRef.model_fields), {"pool_code", "catalog_revision"})

    def test_activation_and_rollback_are_distinguishable(self) -> None:
        activation = ConfigurationActivationRef(
            activation_id=RECORD_ID,
            kind="activation",
            target_release_id=SECOND_RECORD_ID,
            occurred_at=CREATED_AT,
            reason_code="operator-request",
        )
        rollback = ConfigurationActivationRef(
            activation_id=RECORD_ID,
            kind="rollback",
            target_release_id=SECOND_RECORD_ID,
            previous_release_id=RECORD_ID,
            occurred_at=CREATED_AT,
            reason_code="operator-request",
        )
        self.assertEqual(activation.kind, "activation")
        self.assertEqual(rollback.kind, "rollback")

    def test_rollback_requires_the_release_it_moves_away_from(self) -> None:
        # A rollback that cannot name what it rolled back from is not auditable.
        with self.assertRaises(ValidationError):
            ConfigurationActivationRef(
                activation_id=RECORD_ID,
                kind="rollback",
                target_release_id=SECOND_RECORD_ID,
                occurred_at=CREATED_AT,
                reason_code="operator-request",
            )

    def test_round_trip_and_schema_parity(self) -> None:
        release = ConfigurationRelease(**release_payload())
        policy = ModelPoolPolicy(**pool_policy_payload())
        self.assertEqual(
            ConfigurationRelease.model_validate_json(release.model_dump_json()), release
        )
        self.assertEqual(ModelPoolPolicy.model_validate_json(policy.model_dump_json()), policy)
        self.assertEqual(
            load_artifact("configuration-release"), ConfigurationRelease.model_json_schema()
        )
        self.assertEqual(load_artifact("model-pool-policy"), ModelPoolPolicy.model_json_schema())
        self.assertEqual(
            ConfigurationRelease.model_json_schema()["$id"], CONFIGURATION_RELEASE_SCHEMA_ID
        )
        self.assertEqual(ModelPoolPolicy.model_json_schema()["$id"], MODEL_POOL_POLICY_SCHEMA_ID)


if __name__ == "__main__":
    unittest.main()
