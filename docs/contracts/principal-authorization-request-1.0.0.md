# Principal and Authorization Request Contract 1.0.0

- Status: implemented in `src/ai_assistant/contracts/principal.py`
- Package: CP-001 (Control Plane Contracts)
- Authority: `docs/adr/ADR-CP-002-membership-role-and-authorization-scope.md`,
  `docs/adr/ADR-CP-003-data-index-isolation-and-multi-node-retrieval.md`,
  `docs/control-plane/CP-000A-authorization-matrix.md`,
  `docs/contracts/security-authorization-1.0.0.md`
- Schema artifacts:
  - `schemas/request-actor-context/1.0.0.schema.json` — `urn:ai-assistant:contracts:request-actor-context:1.0.0`
  - `schemas/authorization-request/1.0.0.schema.json` — `urn:ai-assistant:contracts:authorization-request:1.0.0`
- Deferred items addressed: DEF-106 (authorized scope reference), DEF-108
  (request-to-decision binding)

## Purpose

Name the actor of a request and the exact question asked of the authorization
boundary, and bind an issued decision back to the request that produced it. This
contract expresses inputs and bindings only; it never expresses a decision
outcome.

## Shapes

| Type | Purpose |
| --- | --- |
| `AuthenticatedPrincipalRef` | Opaque principal plus security context and organization. |
| `AnonymousGuest` | Guest session, organization, establishment instant, visibility class. |
| `RequestActorContext` | Closed discriminated actor: authenticated principal **or** guest. |
| `AuthorizationRequest` | Organization, actor, action, permission, resource, optional requested scope, instants, request fingerprint. |
| `ConsultedPolicyRevisionRef` | Policy identity, revision, and digest actually consulted. |
| `DecisionBindingRef` | Binds `request_id` + fingerprint to `decision_id`, consulted policy, authorized scope, and expiry. |

`AuthorizationRequest.resource` reuses the published `AuthorizationResourceRef`
from `security` 1.0.0; the existing `AuthorizationDecision` remains the decision
contract and is not modified.

## Invariants

1. `actor_kind` and the populated actor value must agree, and exactly one actor
   value may be present. An empty actor context is invalid, so a failed
   authentication cannot degrade into a guest by omission.
2. `AuthenticatedPrincipalRef` and `AnonymousGuest` are disjoint types: a guest
   has no `principal_id` and a principal has no `guest_session_id`.
3. The actor's organization and any requested scope's organization must equal the
   request's organization.
4. `deadline_at`, when present, must be strictly after `requested_at`.
5. `request_fingerprint` is a `sha256:<64 hex>` digest, validated for syntax and
   length without naming any storage or provider technology.
6. `AuthorizationRequest` contains no decision field (`allowed`, `effect`,
   `obligations`, ...): a request can never be mistaken for a grant.
7. `DecisionBindingRef.expires_at`, when present, must be strictly after
   `bound_at`, and the binding always carries the consulted policy revision.

## Retrieval authorization envelope inputs

The inputs a future `RetrievalAuthorizationEnvelope` (CP-002/CP-003) needs are now
all expressible: organization, `RequestActorContext`, `PermissionRef`,
`AuthorizationScopeRef` (authorized scope carried by `DecisionBindingRef`),
`ConsultedPolicyRevisionRef`, and the decision expiry. The envelope aggregate
itself is **not** created here — see the open decisions in
`docs/control-plane/CP-001-control-plane-contracts.md`.

## Out of scope

Policy evaluation, decision issuance, scope expansion, session management,
authentication, and guest escalation rules belong to CP-002 and the Backend
integration boundary (ADR-CP-009).

## Versioning

New family at `1.0.0`. `security` 1.0.0 (`SecurityPrincipalContext`,
`AuthorizationDecision`) is reused unchanged.

## Tests

`tests/test_control_plane_contracts.py::PrincipalBoundaryTests`.
