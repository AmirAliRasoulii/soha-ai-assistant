# Index Isolation Profile Contract 1.0.0

- Status: implemented in `src/ai_assistant/contracts/visibility_isolation.py`
- Package: CP-001 (Control Plane Contracts)
- Authority: `docs/adr/ADR-CP-003-data-index-isolation-and-multi-node-retrieval.md`
  (rules `T-1`..`T-7`, section "Promotion policy" `P-1`..`P-5`),
  `docs/control-plane/CP-000C-index-isolation-blueprint.md`
- Schema artifacts:
  - `schemas/index-isolation-profile/1.0.0.schema.json` —
    `urn:ai-assistant:contracts:index-isolation-profile:1.0.0`
- Deferred items addressed: DEF-108 (typed isolation profile shape)

## Purpose

Express the trusted, versioned physical placement of one logical tenant, plus the
recorded reason and lineage of a topology change, without expressing any access
meaning and without naming any backend.

## Shapes

| Type | Purpose |
| --- | --- |
| `PhysicalIsolationTier` | Closed `Literal` over the four tiers of `ADR-CP-003`. |
| `IndexIsolationProfile` | Identity, revision, tenant key, tier, provider-neutral policy refs, promotion evidence, and before/after lineage. |

Tiers, in ascending order of physical isolation: `shared_logical_partition`
(the default), `dedicated_shard`, `dedicated_collection`, `dedicated_deployment`.

## Invariants

1. A tier is not a permission (`T-6`). The contract carries no permission, role,
   group, membership, or access field, so no consumer can read breadth from a
   tier. The mandatory trusted-metadata pre-filter is identical at every tier
   (`T-2`).
2. Physical location is resolved from trusted configuration only (`T-4`). There
   is no endpoint, host, region, connection string, provider name, credential, or
   `requested_tier` field, so nothing here can be populated from a request.
3. Promotion above the shared partition requires a controlled `promotion_reason`
   code and a `promotion_evidence_ref` (`P-2`). An informal sensitivity label is
   therefore insufficient (`P-4`), and free-text justification is not accepted.
4. A `dedicated_deployment` additionally requires a residency or encryption
   policy reference, because legal isolation is grounded in an explicit policy
   rather than a label (`P-4`).
5. A topology change is a new revision, never an edit (`P-1`). A recorded
   previous tier and previous revision must be present together, the previous
   revision must differ from the current one, and the recorded change must
   actually change the tier.
6. Promotion is never derived from role count, group count, membership count, or
   organizational depth (`P-3`): those fields are structurally absent.
7. `recorded_at` must not precede `effective_at`; all instants are timezone-aware.
   Every model is frozen and rejects unknown fields. The module holds no mutable
   process-global state: the tier ordering used by `is_promotion` is an immutable
   tuple.
8. Stable references survive relocation (`T-3`): the profile references a logical
   tenant key and opaque routing, capacity, residency, encryption, and index
   configuration references, never a source or citation identity.

## Out of scope

Resolving routing to a physical backend, executing promotion or demotion,
migration, and emitting the audited before/after topology (`T-5`) belong to
CP-003, CP-006, and CP-009. The `VectorStorePort` adapter boundary is not typed
here. No numeric promotion threshold is defined in this package (`P-5`); exact
thresholds remain open pending benchmark and production measurement.

## Versioning

New family at `1.0.0`. Adding a tier, admitting a request-supplied placement
field, or attaching any access semantics to a tier would each be a semantic break
requiring a new major version and an accepted CP-003 decision.

## Tests

`tests/test_visibility_and_isolation_contracts.py::IndexIsolationProfileTests`,
`::SchemaArtifactTests`.
