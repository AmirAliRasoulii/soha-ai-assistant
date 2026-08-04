# RouteDecision 1.0.0

- Status: Accepted and implemented as a bounded baseline
- Owner: Deterministic Routing Policy Boundary
- Schema identifier: `urn:ai-assistant:contracts:route-decision:1.0.0`
- JSON Schema dialect: `https://json-schema.org/draft/2020-12/schema`
- Artifact: `schemas/route-decision/1.0.0.schema.json`


## Bounded baseline status and known limitations (CP-000R)

This contract is **accepted and implemented as a bounded baseline**. Base repository evidence:
`6477c1c`. Bounded implementation existed at base commit `6477c1c`. CP-000R documentation was
accepted at commit `8d94c6a`.
CP-000R changed no field, no type, no validation rule, no schema, and no version of this contract. It
records truthfully what this 1.0.0 contract does and does not yet cover, and who owns the remaining
work.

| Known limitation | Owner |
| --- | --- |
| `RouteLane` in 1.0.0 already contains `deny`, and `deny` is already a **terminal lane** together with `clarify` and `abstain`: it allows no capability, requires no fact, carries no filter and no approved flow reference, and requires an all-zero execution budget. CP-000R re-scoped audit finding C-004 against the committed contract: the gap is runtime, not contractual | AI-002 |
| Canonical deny semantics. An **authorization** deny occurs *before* routing, yields `UNAUTHORIZED`, and requires no `RouteDecision`. A **route or policy** deny is expressed as `RouteDecision(lane="deny")`, yields `POLICY_REJECTED`, carries a zero execution budget, and executes no capability | AI-002 |
| The bounded Runtime and the Walking Skeleton do not yet provide complete terminal handling for `RouteDecision(lane="deny")` (`DEF-118`) | AI-002 |
| `UNAUTHORIZED` and `POLICY_REJECTED` are distinct outcomes and must remain distinguishable in routing and in audit, not collapsed into one generic failure | AI-002 |
| Clarification and abstention routing is a deliberate transitional state (audit finding C-005) and is not yet the final routing taxonomy | AI-002 |
## Purpose

RouteDecision is the immutable output of trusted deterministic routing policy. It freezes the
lane, the controlled route code, the allowed capability set, the required facts, the planner
flag, approved filter references, count-based execution budget, a controlled rationale code,
the policy version, and the correlation identifiers that make the decision replayable.

## AI Core boundary

RouteDecision is not model output, not QueryAnalysis, not authorization evaluation, not an
ExecutionPlan, not a CapabilityRequest, not an executor, not a planner implementation, not a
prompt, not a free-form rationale, not a filter expression, not a database query, not an HTTP
contract, and not a provider-specific routing object. The model never selects the final lane,
route, planner, capability, filter, or budget. QueryAnalysis is evidence consumed by policy;
it carries no routing authority.

## Root field table

| Field | Type | Required | Default | Notes |
| --- | --- | --- | --- | --- |
| `schema_version` | literal `1.0.0` | no | `1.0.0` | Any other value is rejected. |
| `decision_id` | UUID v4 | yes | none | Identity of this decision. |
| `request_id` | UUID v4 | yes | none | Correlates with the originating request. |
| `query_analysis_id` | UUID v4 | yes | none | Evidence reference, not authority. |
| `authorization_decision_id` | UUID v4 | yes | none | Authorization must complete first. |
| `runtime_snapshot_id` | UUID v4 | yes | none | Binds the decision to runtime state. |
| `decided_at` | UtcDateTime | yes | none | Aware timestamp normalized to UTC. |
| `effective_risk_level` | RiskLevel | yes | none | Produced by policy, not copied blindly. |
| `lane` | RouteLane | yes | none | Closed catalog. |
| `route` | canonical code | yes | none | Controlled namespaced code. |
| `allowed_capabilities` | tuple of CapabilityName | no | empty tuple | Maximum 5, unique, order preserved. |
| `required_facts` | tuple of canonical codes | no | empty tuple | Maximum 32, unique, order preserved. |
| `planner_required` | bool | yes | none | True if and only if the lane is `composite`. |
| `filters` | tuple of RouteFilterRef | no | empty tuple | Maximum 32, unique by `(filter_type, filter_ref)`. |
| `budget` | RouteBudget | yes | none | Count-based execution limits. |
| `rationale_code` | canonical code | yes | none | One controlled machine-readable code. |
| `policy_version` | SchemaVersion | yes | none | Version of the deciding policy. |
| `approved_flow_ref` | opaque reference or null | no | null | Allowed only for `deterministic` and `fast`. |

## RouteFilterRef field table

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `filter_type` | canonical code | yes | 1..128 characters, `^[a-z][a-z0-9._:-]*$`. |
| `filter_ref` | opaque reference | yes | 1..256 characters, preserved exactly. |

## RouteBudget field table

| Field | Type | Required | Range |
| --- | --- | --- | --- |
| `max_steps` | strict integer | yes | 0..5 |
| `max_parallel_steps` | strict integer | yes | 0..3 |
| `max_replans` | strict integer | yes | 0..1 |
| `max_retrieval_retries` | strict integer | yes | 0..1 |
| `max_analytics_repairs` | strict integer | yes | 0..1 |
| `max_answer_repairs` | strict integer | yes | 0..1 |

## Lane catalog

`deterministic`, `fast`, `composite`, `clarify`, `abstain`, `deny`. Unknown lanes fail
validation.

## Capability catalog

`document_retrieval`, `semantic_analytics`, `personal_selector`, `rule_evaluator`,
`official_search`. Unknown capabilities fail validation.

## Route-code semantics

`route` is a controlled, namespaced canonical code. It is not a free user string and not a
closed enumeration in schema 1.0.0. Examples: `fixed.help`, `fixed.capability_overview`,
`flow.loan_eligibility`, `fast.document`, `fast.analytics`, `fast.personal`,
`composite.default`, `terminal.clarify`, `terminal.abstain`, `terminal.deny`. Route semantics
are never enforced through string prefixes; a future versioned Route Catalog defines which
routes are valid for each lane and policy version.

## Rationale-code semantics

`rationale_code` is exactly one controlled machine-readable code, for example
`query.single_document_need`, `query.multiple_evidence_needs`, `query.blocking_ambiguity`,
`authorization.denied`, `policy.high_risk_requires_flow`, or `evidence.unavailable`. The
fields `rationale`, `rationale_text`, `explanation`, `reasoning`, and `chain_of_thought` are
deliberately absent. Human-facing localization happens outside the contract.

## Filter-reference semantics

A `RouteFilterRef` points at an already approved filter or constraint set. It must never
carry field/operator/value triples, SQL, predicates, search DSL, access-control expressions,
arbitrary JSON, executable policy, URLs, or provider objects. Examples:
`filter_type = "authorization.scope"` with `filter_ref = "scope-set:employee-self-service-v3"`,
and `filter_type = "official-source.allowlist"` with
`filter_ref = "official-sources:education-v2"`. The contract neither resolves nor executes
the reference.

## Budget semantics

Only count-based limits are frozen. Cross-field rules: `max_parallel_steps <= max_steps`; a
zero step budget requires zero parallel steps; a positive step budget requires at least one
parallel step. All values are strict integers, so booleans are rejected. Shared deadlines,
token budgets, provider quotas, financial budgets, and capacity reservations belong to future
runtime and capability contracts, and no deadline or token field exists here.

## Planner invariant

`planner_required` is true if and only if `lane == "composite"`. Every other lane requires
`planner_required == false`. A deterministic approved flow may contain multiple predefined
steps, but it never invokes the free planner.

## Terminal-lane invariants

For `clarify`, `abstain`, and `deny`: `allowed_capabilities`, `required_facts`, and `filters`
must be empty, `approved_flow_ref` must be null, and every budget counter must be zero. The
route and rationale codes remain required so that a terminal decision stays replayable and
explainable through controlled codes. No clarification question, denial message, or
abstention prose is carried.

## Fast invariants

For `fast`: `planner_required == false`, exactly one allowed capability, at least one
required fact, `max_steps == 1`, `max_parallel_steps == 1`, and `max_replans == 0`. Retry and
repair counters may independently be zero or one within their global limits. Fast means one
deterministic execution step; it does not mean unvalidated or unrestricted execution.

## Composite invariants

For `composite`: `planner_required == true`, at least one allowed capability, at least one
required fact, `2 <= max_steps <= 5`, and `1 <= max_parallel_steps <= min(3, max_steps)`.
`max_replans` remains bounded to zero or one. The contract neither creates nor validates the
future ExecutionPlan DAG.

## Deterministic invariants

For `deterministic`: `planner_required == false` and `max_replans == 0`. Two valid forms
exist.

1. Fixed or predefined response: `allowed_capabilities`, `required_facts`, and `filters` are
   empty and every budget counter is zero.
2. Predefined executable flow: 1..5 allowed capabilities, at least one required fact,
   `1 <= max_steps <= 5`, and `1 <= max_parallel_steps <= min(3, max_steps)`. This form may
   carry `approved_flow_ref`.

The flow itself and its steps are not implemented here.

## High-risk and unknown-risk handling

The routing policy produces `effective_risk_level`; it is never copied blindly from the
analyzer and may be upgraded. When `effective_risk_level` is `high` or `unknown` and the lane
is `fast`, a non-null `approved_flow_ref` is required. This records the approved exception
that permits a bounded fast route, so an unapproved high-risk or unresolved-risk request
cannot enter ordinary fast execution. `approved_flow_ref` is allowed only for the
`deterministic` and `fast` lanes and is never resolved or executed by the contract.

## Trust boundary

The producer is trusted deterministic policy code. QueryAnalysis is one input, not the
authority. Authorization must complete before routing, and the allowed capability set is the
output of the capability policy. The contract cannot dereference `authorization_decision_id`,
and it does not prove that the referenced snapshot, policy, filters, or approved flow exist.
Trusted route construction must verify that request and context references match. Unknown or
unavailable policy configuration must fail closed outside this model.

The Pydantic contract enforces the static capability catalog only. The trusted routing-policy
implementation must additionally ensure that each selected capability is enabled in the
effective runtime policy, is allowed for the request, is compatible with authorization
constraints, is healthy and available when policy requires it, and does not exceed
organization policy. Dynamic policy evaluation is not implemented in this contract.

## Authorization ordering

Authorization is evaluated before routing. The decision references the authorization result
by identifier only; routing never re-derives, re-evaluates, or overrides an authorization
outcome, and no principal, role, group, or scope value is carried in the decision.

## Replay semantics

`runtime_snapshot_id` together with `policy_version` binds the decision to reproducible
runtime state. Repeated evaluation with the same validated inputs and the same immutable
policy should produce the same semantic decision. Route codes belong to a future versioned
Route Catalog, so catalog growth does not alter the JSON Schema.

## Security restrictions

The following are not declared fields and are rejected as unknown input at the root and in
both nested models: `raw_message`, `raw_query`, `normalized_query`, `standalone_query`,
`intent`, `entities`, `time_expressions`, `confidence`, `risk_signals`, `model`, `model_name`,
`model_output`, `provider`, `provider_response`, `prompt`, `system_prompt`, `rationale`,
`rationale_text`, `explanation`, `reasoning`, `chain_of_thought`, `clarification_message`,
`denial_message`, `answer`, `execution_plan`, `plan_steps`, `dependency_graph`,
`capability_request`, `tool`, `tool_name`, `tool_arguments`, `sql`, `query`, `where`,
`predicate`, `filter_expression`, `filter_value`, `operator`, `endpoint`, `url`, `api_key`,
`token`, `access_token`, `secret`, `password`, `credentials`, `roles`, `groups`,
`principal_id`, `security_context_id`, `email`, `display_name`, `session_id`, `http_status`,
`headers`, `metadata`, `attributes`, `deadline_ms`, `token_budget`, `cost_budget`.

## Retention

- The contract does not authorize persistence.
- RouteDecision contains references and controlled codes rather than user text.
- Full decisions may be stored in replay or audit systems only under approved retention
  policy.
- Raw prompts, user messages, model output, credentials, SQL, and executable filter
  expressions must never be copied into it.
- Telemetry should normally use decision ID, lane, route, capability codes, rationale code,
  policy version, and runtime snapshot ID.

## Compatibility

RouteDecision 1.0.0 is closed.

- PATCH changes must not alter accepted or serialized payloads.
- Adding, removing, or renaming a field is a major change.
- Adding or changing a lane or capability literal is a major change.
- Changing lane, planner, budget, risk, filter, replay, trust, or capability-policy semantics
  is a major change.
- Adding a controlled route or rationale catalog entry does not change the JSON Schema.
- Version 1.0.0 becomes immutable after approval.

## Valid example: deterministic fixed response

```json
{
  "schema_version": "1.0.0",
  "decision_id": "11111111-1111-4111-8111-111111111111",
  "request_id": "22222222-2222-4222-8222-222222222222",
  "query_analysis_id": "33333333-3333-4333-8333-333333333333",
  "authorization_decision_id": "44444444-4444-4444-8444-444444444444",
  "runtime_snapshot_id": "55555555-5555-4555-8555-555555555555",
  "decided_at": "2026-01-01T08:30:00Z",
  "effective_risk_level": "normal",
  "lane": "deterministic",
  "route": "fixed.capability_overview",
  "allowed_capabilities": [],
  "required_facts": [],
  "planner_required": false,
  "filters": [],
  "budget": {
    "max_steps": 0,
    "max_parallel_steps": 0,
    "max_replans": 0,
    "max_retrieval_retries": 0,
    "max_analytics_repairs": 0,
    "max_answer_repairs": 0
  },
  "rationale_code": "query.capability_help",
  "policy_version": "1.0.0",
  "approved_flow_ref": null
}
```

## Valid example: deterministic predefined flow

```json
{
  "lane": "deterministic",
  "route": "flow.loan_eligibility",
  "allowed_capabilities": ["rule_evaluator"],
  "required_facts": ["fact.eligibility_rule"],
  "planner_required": false,
  "filters": [
    {
      "filter_type": "authorization.scope",
      "filter_ref": "scope-set:employee-self-service-v3"
    }
  ],
  "budget": {
    "max_steps": 2,
    "max_parallel_steps": 1,
    "max_replans": 0,
    "max_retrieval_retries": 1,
    "max_analytics_repairs": 0,
    "max_answer_repairs": 0
  },
  "rationale_code": "policy.approved_flow",
  "policy_version": "1.0.0",
  "approved_flow_ref": "flow:loan-eligibility-v4"
}
```

## Valid example: fast lane

```json
{
  "lane": "fast",
  "route": "fast.document",
  "effective_risk_level": "normal",
  "allowed_capabilities": ["document_retrieval"],
  "required_facts": ["fact.document"],
  "planner_required": false,
  "budget": {
    "max_steps": 1,
    "max_parallel_steps": 1,
    "max_replans": 0,
    "max_retrieval_retries": 1,
    "max_analytics_repairs": 0,
    "max_answer_repairs": 1
  },
  "rationale_code": "query.single_document_need",
  "policy_version": "1.0.0"
}
```

## Valid example: high-risk fast lane with an approved flow

```json
{
  "lane": "fast",
  "route": "fast.personal",
  "effective_risk_level": "high",
  "allowed_capabilities": ["personal_selector"],
  "required_facts": ["fact.personal_record"],
  "planner_required": false,
  "budget": {
    "max_steps": 1,
    "max_parallel_steps": 1,
    "max_replans": 0,
    "max_retrieval_retries": 0,
    "max_analytics_repairs": 0,
    "max_answer_repairs": 0
  },
  "rationale_code": "policy.high_risk_requires_flow",
  "policy_version": "1.0.0",
  "approved_flow_ref": "flow:personal-high-risk-v2"
}
```

## Valid example: composite lane

```json
{
  "lane": "composite",
  "route": "composite.default",
  "allowed_capabilities": ["document_retrieval", "semantic_analytics"],
  "required_facts": ["fact.document", "fact.analytics"],
  "planner_required": true,
  "budget": {
    "max_steps": 3,
    "max_parallel_steps": 2,
    "max_replans": 1,
    "max_retrieval_retries": 1,
    "max_analytics_repairs": 1,
    "max_answer_repairs": 1
  },
  "rationale_code": "query.multiple_evidence_needs",
  "policy_version": "1.0.0"
}
```

## Valid examples: terminal lanes

```json
{
  "lane": "clarify",
  "route": "terminal.clarify",
  "planner_required": false,
  "budget": {
    "max_steps": 0,
    "max_parallel_steps": 0,
    "max_replans": 0,
    "max_retrieval_retries": 0,
    "max_analytics_repairs": 0,
    "max_answer_repairs": 0
  },
  "rationale_code": "query.blocking_ambiguity",
  "policy_version": "1.0.0"
}
```

The `abstain` lane uses `route = "terminal.abstain"` with
`rationale_code = "evidence.unavailable"`, and the `deny` lane uses
`route = "terminal.deny"` with `rationale_code = "authorization.denied"`. Both keep the same
empty collections and all-zero budget.

## Representative invalid examples

| Invalid input | Reason |
| --- | --- |
| `"schema_version": "2.0.0"` | Only the exact literal `1.0.0` is accepted. |
| `"lane": "planner"` | The lane catalog is closed. |
| `"allowed_capabilities": ["web_search"]` | The capability catalog is closed. |
| `"planner_required": true` with `lane = "fast"` | Planner is allowed only for `composite`. |
| `"planner_required": false` with `lane = "composite"` | Composite always requires the planner. |
| `clarify` lane with `max_steps = 1` | Terminal lanes require an all-zero budget. |
| `deny` lane with a filter | Terminal lanes carry no filters. |
| `fast` lane with two capabilities | Fast allows exactly one capability. |
| `fast` lane with `max_steps = 2` | Fast allows exactly one step. |
| `composite` lane with `max_steps = 1` | Composite requires at least two steps. |
| `composite` lane with `max_steps = 6` | The global step maximum is five. |
| `max_parallel_steps = 2` with `max_steps = 1` | Parallelism cannot exceed steps. |
| `max_steps = 2` with `max_parallel_steps = 0` | A positive step budget needs parallelism. |
| `max_steps: true` | Budget counters are strict integers, so booleans are rejected. |
| `deterministic` lane with facts but no capabilities | The fixed form must be empty. |
| `high` risk `fast` lane without `approved_flow_ref` | An approved exception is required. |
| `composite` lane with `approved_flow_ref` | Approved flows are limited to two lanes. |
| `"route": "Fast.Document"` | Route codes must match the canonical code pattern. |
| `"filter_ref": " scope:x "` | Opaque references are never trimmed or repaired. |
| `"rationale_text": "..."` | Free-form rationale is forbidden. |
| `"sql": "select 1"` | Query, provider, identity, and secret fields are forbidden. |

## Non-goals

- Implementing routing policy, capability policy, or planner behavior.
- Building or validating an ExecutionPlan DAG.
- Resolving or executing filter references or approved flows.
- Evaluating or re-deriving authorization.
- Carrying user text, prompts, model output, or provider payloads.
- Defining deadlines, token budgets, or financial budgets.

## Deferred implementation work

- Deterministic routing-policy implementation.
- Route Catalog and rationale-code catalog.
- Capability-policy evaluation.
- Filter-reference resolution and approved-flow registry.
- Route replay evaluator.
- Budget and deadline binding.
- RouteDecision integration with ExecutionPlan.
- Route-policy evaluation fixtures.
- Model-independent regression tests using QueryAnalysis fixtures.
