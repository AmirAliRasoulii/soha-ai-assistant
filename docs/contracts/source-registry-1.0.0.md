# Source Registry Contract 1.0.0

- Status: implemented in `src/ai_assistant/contracts/source_registry.py`
- Package: CP-001 (Control Plane Contracts)
- Authority: `docs/adr/ADR-CP-007-source-registry-and-content-lifecycle.md`,
  `docs/control-plane/CP-000B-source-lifecycle-matrix.md`,
  `docs/control-plane/CP-000C-index-isolation-blueprint.md`
- Schema artifacts:
  - `schemas/knowledge-source/1.0.0.schema.json` — `urn:ai-assistant:contracts:knowledge-source:1.0.0`
  - `schemas/source-revision/1.0.0.schema.json` — `urn:ai-assistant:contracts:source-revision:1.0.0`
  - `schemas/source-relationship/1.0.0.schema.json` — `urn:ai-assistant:contracts:source-relationship:1.0.0`
- Deferred items addressed: DEF-119 (source metadata class separation),
  DEF-121 (source relationship taxonomy)

## Purpose

Express the stable identity of a knowledge source, the immutable revisions that
carry its content, the four separated metadata classes, and the two canonically
decided relationship kinds. Behavior belongs to CP-005 (registry) and CP-006
(ingestion).

## Shapes

| Type | Purpose |
| --- | --- |
| `KnowledgeSource` | Stable source identity: organization, owner node, source type, stable key, status, optional single active revision. |
| `SourceRevision` | Immutable revision: number, status, the four metadata classes, optional stored content, supersession lineage. |
| `CitationSafePublishedSourceMetadata` | Only what an answer may cite: title, source type, authority, trusted temporal metadata, optional publisher and public locator. |
| `ManagementSourceMetadata` | Owner node, owner principal, upload instant, review state, submitter/reviewer. |
| `LifecycleAuditMetadata` | Audit-only reason code, transition instant, actor, audit event reference. |
| `MandatoryIsolationMetadata` | Index-side mandatory filters: organization, owner node, visibility policy revision, source, revision, index namespace. |
| `RawSourceContentRef` | Opaque stored-content handle, digest, media type, bounded byte size. |
| `TrustedSourceTemporalMetadata` / `ProposedSourceTemporalMetadata` | Recorded (trusted) vs. submitted (untrusted) temporal claims. |
| `SourceAuthorityRef` | Authority class, issuer, assignment policy, catalog revision. |
| `VisibilityPolicyRevisionRef` | Visibility policy identity, revision, digest. |
| `SupersedesLink` / `SupplementsLink` / `SourceRelationship` | The two decided relationship kinds. |

## Invariants

1. `source_type` is a closed union of `uploaded_document` and `official_url`.
   `official_url` requires a public locator; `uploaded_document` forbids one and
   requires stored content.
2. Metadata classes are disjoint value types: citation-safe metadata shares no
   field with management, audit, or raw-content metadata, so ownership, review
   state, reason codes, and storage handles cannot leak into a citation.
3. **Upload time is not publication time.** `uploaded_at` exists only in
   management metadata; `published_at`/`effective_from` exist only in trusted
   temporal metadata.
4. `valid_until` is nullable (open-ended validity) and, when present, must be
   strictly after `effective_from`.
5. Untrusted temporal claims use a separate proposed shape with distinct field
   names, so a submitted claim can never be read as a recorded fact.
6. At most one active revision per source: `active_revision_id` is a single
   optional reference, never a collection, and an archived or revoked source may
   not carry one.
7. Revisions are frozen: status, temporal metadata, and content references cannot
   be mutated in place. Supersession is expressed by a **new** revision plus
   `superseded_by_revision_id`/`superseded_at`; an active revision may not carry
   supersession fields, and a superseded revision must name its successor and may
   not name itself.
8. Isolation metadata must describe exactly this source and revision inside one
   organization, and always carries the visibility policy revision.
9. Ownership grants nothing: neither `KnowledgeSource` nor management metadata has
   any reader, permission, or allowed-principal field.
10. Content digests are `sha256:<64 hex>`, media types are validated, and byte
    size is bounded.

## Relationship taxonomy

- `supersedes` — revision replacement **inside one** `KnowledgeSource`; requires
  two distinct revisions of that source.
- `supplements` — relationship **across two distinct** `KnowledgeSource`s.
- No relationship — independent sources; nothing is inferred.

`AMENDS` and `PARTIALLY_SUPERSEDES` have no canonical decision and are therefore
**not representable**: the closed union rejects them (DEF-121 remains open).

## Out of scope

Registry persistence and lifecycle transitions (CP-005); ingestion, chunking,
embedding, index activation, revoke propagation (CP-006); retrieval filtering and
multi-node isolation enforcement (CP-003).

## Versioning

New families at `1.0.0`. Adding a third relationship kind later is a union change
and requires a new major version.

## Tests

`tests/test_source_and_lineage_contracts.py::SourceRegistryTests` and
`::SourceRelationshipTests`.
