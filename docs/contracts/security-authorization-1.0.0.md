# SecurityPrincipalContext 1.0.0 and AuthorizationDecision 1.0.0

- Status: Accepted and implemented as a bounded baseline
- Owners: Identity Adapter (SecurityPrincipalContext), Authorization Policy Layer (AuthorizationDecision)
- Schema ids:
  - urn:ai-assistant:contracts:security-principal-context:1.0.0
  - urn:ai-assistant:contracts:authorization-decision:1.0.0
- Artifacts:
  - schemas/security-principal-context/1.0.0.schema.json
  - schemas/authorization-decision/1.0.0.schema.json


## Bounded baseline status and known limitations (CP-000R)

This contract is **accepted and implemented as a bounded baseline**. Base repository evidence:
`6477c1c`. Bounded implementation existed at base commit `6477c1c`. CP-000R documentation was
accepted at commit `8d94c6a`.
CP-000R changed no field, no type, no validation rule, no schema, and no version of this contract. It
records truthfully what this 1.0.0 contract does and does not yet cover, and who owns the remaining
work.

| Known limitation | Owner |
| --- | --- |
| `SecurityPrincipalContext` represents an authenticated principal. A first-class typed anonymous Guest principal does not exist in 1.0.0 (audit finding G-006), and authentication failure must never be downgraded into Guest | CP-002 |
| There is no typed `AuthorizationRequest`, so the request-to-decision binding, decision expiry enforcement, consulted-policy reference, and authorized-scope reference are not contractually carried (audit finding G-004) | CP-001 with CP-002 |
| There is no typed `RetrievalAuthorizationEnvelope` separating the authorization decision from the trusted retrieval filter inputs (audit finding G-005) | CP-002 with AI-003 |
| `AuthorizationDecision` carries `policy_version`; it does not yet carry a pinned `VisibilityPolicyDefinition` revision reference | CP-002 |
| The revocation race is not addressed. The exact finding is that retrieval succeeds, and the source or its visibility policy is then revoked, before finalization and publication. The required future behaviour is a deterministic current-eligibility and revocation recheck before final answer publication. This is not a difference between authorization-decision time and retrieval time, and it is not implemented today (audit finding G-011) | AI-007 with CP-006 |
| Role labels, frontend labels, display names, and model output never authorize | Unchanged rule |
## Trust boundary

| Layer | Responsibility |
| --- | --- |
| Backend / Identity / Policy adapter | Authentication, trusted identity resolution, and membership and policy evaluation |
| AI Core | Receives provider-neutral trusted security inputs only, and makes no authentication or membership decision |
| Django models, sessions, request objects, and ORM state | **Never enter AI Core** in any form |

## Purpose

SecurityPrincipalContext carries trusted identity facts established by the Identity Adapter after authentication. It answers who the caller is and how strongly that was established.

AuthorizationDecision carries the deterministic result of applying one versioned policy to one action on one resource. It answers whether that action is allowed and why.

## Separation of identity facts from authorization decisions

The two contracts are intentionally distinct and must never be merged.

- Roles, groups, allowed scopes, and data classification allowances are authorization inputs. They live only on SecurityPrincipalContext and grant nothing by themselves.
- An effect (allow or deny) exists only on AuthorizationDecision and is produced by deterministic policy code.
- A decision references identity by context_id only. It never restates identity attributes.
- Because both models are closed, an identity attribute placed on a decision, or an effect placed on an identity context, fails validation.

## SecurityPrincipalContext fields

| Field | Type | Required | Default | Rules |
| --- | --- | --- | --- | --- |
| schema_version | literal string | no | 1.0.0 | only 1.0.0 accepted |
| context_id | UUID | yes | none | UUID version 4 |
| principal_id | UUID | yes | none | UUID version 4, internal stable identity |
| principal_type | literal string | yes | none | user or service |
| deployment_id | UUID | yes | none | UUID version 4 |
| issuer | string | yes | none | 1 to 512 characters, not blank, no NUL, preserved exactly |
| authenticated_at | UtcDateTime | yes | none | aware, normalized to UTC |
| authentication_methods | tuple of canonical codes | yes | none | 1 to 8 entries, unique |
| assurance_level | canonical code | yes | none | canonical code rules |
| session_id | UUID or null | no | null | UUID version 4 when present |
| roles | tuple of canonical codes | no | empty | at most 64, unique |
| groups | tuple of canonical codes | no | empty | at most 256, unique |
| allowed_scopes | tuple of canonical codes | no | empty | at most 128, unique |
| data_classification_allowances | tuple of canonical codes | no | empty | at most 32, unique |

## AuthorizationResourceRef fields

| Field | Type | Required | Default | Rules |
| --- | --- | --- | --- | --- |
| resource_type | canonical code | yes | none | canonical code rules |
| resource_id | string | yes | none | 1 to 256 characters, not blank, no NUL, opaque, preserved exactly |
| classification | canonical code or null | no | null | canonical code rules when present |

## AuthorizationDecision fields

| Field | Type | Required | Default | Rules |
| --- | --- | --- | --- | --- |
| schema_version | literal string | no | 1.0.0 | only 1.0.0 accepted |
| decision_id | UUID | yes | none | UUID version 4 |
| request_id | UUID | yes | none | UUID version 4 |
| security_context_id | UUID | yes | none | UUID version 4, references SecurityPrincipalContext.context_id |
| action | canonical code | yes | none | canonical code rules |
| resource | AuthorizationResourceRef | yes | none | closed nested model |
| effect | literal string | yes | none | allow or deny |
| reason_codes | tuple of canonical codes | yes | none | 1 to 16 entries, unique |
| obligations | tuple of canonical codes | no | empty | at most 16, unique |
| constraint_references | tuple of canonical codes | no | empty | at most 16, unique |
| policy_version | SchemaVersion | yes | none | stable major.minor.patch |
| evaluated_at | UtcDateTime | yes | none | aware, normalized to UTC |
| expires_at | UtcDateTime or null | no | null | strictly later than evaluated_at |

## Trusted origin rules

All fields of both contracts are server-created. No value may be taken directly from a client request body.

| Producer | Fields |
| --- | --- |
| Identity Adapter | every SecurityPrincipalContext field, derived from a verified authentication result |
| Authorization Policy Layer | every AuthorizationDecision field, derived from deterministic policy code |
| Chat Runtime | request_id correlation only |

A client may never supply roles, groups, scopes, classifications, an effect, reason codes, obligations, or a policy version. Model output is never a source for any field in either contract.

## Canonical code rules

Roles, groups, authentication methods, assurance levels, scopes, classifications, actions, resource types, reason codes, obligation codes, and constraint references are internal canonical codes.

- Length 1 to 64 characters.
- Must begin with a lowercase ASCII letter.
- May contain only lowercase ASCII letters, digits, dot, underscore, colon, and hyphen.
- No spaces.
- Never lowercased, trimmed, or otherwise normalized; an unexpected form is rejected.

Accepted examples: user, service, password, mfa, finance.reader, document:read, confidential, policy.denied.
Rejected examples: Finance Admin, UPPERCASE, a leading space, contains/slash, contains@sign.

## Invariants

Shared:

- Both models are closed, frozen, and validate defaults.
- All collections are immutable tuples with order preserved, no automatic sorting, and no duplicate values.
- Missing collection fields become empty tuples; explicit null is rejected.
- All timestamps must be timezone-aware and are normalized to UTC; naive values are rejected.

SecurityPrincipalContext:

- Represents trusted server-created identity facts only.
- Roles, groups, scopes, and classification allowances are authorization inputs, not grants.
- session_id may be absent, which is the normal case for service principals; a session is not required for user principals in this version.
- No organization or tenant identifier exists; each deployment serves one organization.

AuthorizationDecision:

- reason_codes is mandatory and must contain at least one code, for allow and for deny.
- expires_at, when present, must be strictly later than evaluated_at; equal or earlier values are rejected.
- No absent or partial decision is equivalent to allow.
- constraint_references may point to trusted policy artifacts but never carry executable policy, SQL, or filter text.
- resource_id is opaque and is never parsed or resolved by this contract.

## Sensitive data restrictions

Neither contract may accept passwords, tokens, access tokens, cookies, raw claims, raw HTTP headers, provider payloads or responses, email addresses, display names, permissions, normalized query text, model rationale, raw policy expressions, SQL, filter expressions, URLs, or filesystem paths. Their presence alone is a validation failure because both models forbid unknown fields.

principal_id is an internal stable identifier and must not be an email address or display name. issuer and resource_id are opaque values and are stored exactly as received.

## Trace guidance

Traces, logs, and metrics should record context_id and decision_id references rather than full identity payloads. Do not copy principal_id, issuer, roles, groups, scopes, or resource_id into traces by default. Full contract payloads may be retained only where a later audit policy explicitly authorizes it.

## Error semantics

Validation failure is represented by Pydantic ValidationError. Domain and API error mapping are deferred; no error envelope, HTTP error, or user-facing message is defined here.

## Compatibility

Both 1.0.0 models are closed.

- PATCH changes must not alter the accepted or serialized payload set.
- Adding, removing, or renaming a field requires a new major schema version.
- Changing validation rules, enum values, trust meaning, or field semantics is a major change.
- Version 1.0.0 becomes immutable after approval.

## Valid examples

SecurityPrincipalContext:

```json
{
  "schema_version": "1.0.0",
  "context_id": "11111111-1111-4111-8111-111111111111",
  "principal_id": "22222222-2222-4222-8222-222222222222",
  "principal_type": "user",
  "deployment_id": "33333333-3333-4333-8333-333333333333",
  "issuer": "internal.identity.adapter",
  "authenticated_at": "2026-01-01T08:30:00Z",
  "authentication_methods": ["password", "mfa"],
  "assurance_level": "aal2",
  "session_id": "44444444-4444-4444-8444-444444444444",
  "roles": ["finance.reader"],
  "groups": ["finance"],
  "allowed_scopes": ["document:read"],
  "data_classification_allowances": ["confidential"]
}
```

AuthorizationDecision:

```json
{
  "schema_version": "1.0.0",
  "decision_id": "55555555-5555-4555-8555-555555555555",
  "request_id": "66666666-6666-4666-8666-666666666666",
  "security_context_id": "11111111-1111-4111-8111-111111111111",
  "action": "document:read",
  "resource": {
    "resource_type": "document",
    "resource_id": "doc-0001",
    "classification": "confidential"
  },
  "effect": "allow",
  "reason_codes": ["policy.allowed"],
  "obligations": ["audit.write"],
  "constraint_references": ["policy.constraint.time-window"],
  "policy_version": "1.2.3",
  "evaluated_at": "2026-01-01T08:30:00Z",
  "expires_at": "2026-01-01T09:30:00Z"
}
```

## Invalid examples

| Payload change | Reason |
| --- | --- |
| principal context with token or password field | unknown field, fails closed |
| principal context with email or display_name | identity PII is not part of this contract |
| principal context with effect or permissions | authorization output on an identity contract |
| authentication_methods set to an empty list | at least one method required |
| roles containing the same code twice | duplicate collection value |
| roles set to null | explicit null is not an empty tuple |
| assurance_level set to Finance Admin | not a canonical code |
| authenticated_at set to 2026-01-01T12:00:00 | timezone-naive value |
| decision without reason_codes | reason codes are mandatory |
| decision with reason_codes set to an empty list | at least one reason code required |
| decision effect set to maybe | unsupported effect |
| decision policy_version set to 1.0 | not a stable major.minor.patch version |
| expires_at equal to or earlier than evaluated_at | expiry must be strictly later |
| decision with roles, sql, filter, or model_rationale | unknown field, fails closed |
| resource with url, filesystem_path, or credentials | unknown field, fails closed |

## Non-goals

Policy evaluation, a policy engine, permission derivation, delegation, impersonation, break-glass access, organization or tenant identifiers, token parsing or introspection, session management, provider payload storage, audit or trace implementation, persistence, and API error mapping are outside these contracts.
