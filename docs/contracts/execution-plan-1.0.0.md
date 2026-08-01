# ExecutionPlan 1.0.0

- Status: proposed for local verification
- Owner: Plan Construction and Validation Boundary
- Schema dialect: https://json-schema.org/draft/2020-12/schema
- Schema identifier: urn:ai-assistant:contracts:execution-plan:1.0.0
- Artifact: schemas/execution-plan/1.0.0.schema.json

## Purpose

ExecutionPlan is the immutable, validated and bounded description of intended
execution for one turn. It declares which approved capabilities may be invoked,
which typed facts they must produce, how steps depend on each other, which steps
may run in parallel, which typed outputs feed later steps, and how missing
evidence is handled.

The contract performs structural validation only. It never runs a step.

## AI Core boundary

ExecutionPlan is not an executor, a scheduler implementation, a model
invocation, a prompt, a tool call, a CapabilityRequest, a StepResult, a query or
SQL payload, an authorization engine, a routing decision, a retry loop, a
persistence model, an HTTP contract, or a provider-specific object.

The plan carries references, controlled codes and structural declarations. It
never carries user text, evidence values, model output, credentials, or
executable expressions.

## Root field table

| Field | Type | Rules |
| --- | --- | --- |
| schema_version | Literal "1.0.0" | default "1.0.0"; any other value rejected |
| plan_id | UUID4 | version 4 enforced |
| request_id | UUID4 | version 4 enforced |
| route_decision_id | UUID4 | authorizing route decision |
| authorization_decision_id | UUID4 | completed authorization decision |
| runtime_snapshot_id | UUID4 | reproducible runtime state |
| planned_at | UtcDateTime | aware input required; normalized to UTC |
| lane | ExecutionLane | deterministic, fast or composite |
| goal | canonical code | controlled goal code |
| allowed_capabilities | tuple[CapabilityName, ...] | 1..5, unique, order preserving |
| required_facts | tuple of canonical codes | 1..32, unique, order preserving |
| steps | tuple[PlanStep, ...] | 1..5, unique by step_id, topologically ordered |
| parallel_groups | tuple[PlanParallelGroup, ...] | 1..5, unique by group_id, layered |
| composition_type | CompositionType | closed catalog |
| success_condition | SuccessCondition | only all_required_facts in 1.0.0 |
| missing_evidence_policy | MissingEvidencePolicy | partial, clarify or abstain |
| budget | RouteBudget | reused without modification |
| revision | strict integer | 0..1; booleans rejected |
| parent_plan_id | UUID4 or null | default null |
| plan_builder_version | SchemaVersion | stable semantic version |

Explicit null collections are rejected. No collection is ever sorted
automatically.

## Nested model tables

### PlanFactSpec

| Field | Type | Rules |
| --- | --- | --- |
| fact_id | canonical code | typed semantic output identifier |
| value_type | canonical code | controlled fact type code |
| data_scope | FactDataScope | general or personal |

A fact specification is a declaration, never the value. It must not carry text
content, JSON payload, SQL, evidence, model output, or user data.

### PlanInputBinding

| Field | Type | Rules |
| --- | --- | --- |
| input_name | canonical code | unique inside a step |
| source_kind | InputSourceKind | closed catalog |
| source_ref | canonical code | produced fact_id for step_output sources |
| source_step_id | canonical code or null | required only for step_output |
| value_type | canonical code | must match the producer for step_output |
| data_scope | FactDataScope | must match the producer for step_output |

### PlanStep

| Field | Type | Rules |
| --- | --- | --- |
| step_id | canonical code | unique inside the plan |
| capability | CapabilityName | must appear in allowed_capabilities |
| operation | canonical code | controlled capability-operation code |
| depends_on | tuple of canonical codes | default (), maximum 4, unique |
| input_bindings | tuple[PlanInputBinding, ...] | default (), maximum 16, unique by input_name |
| produces | tuple[PlanFactSpec, ...] | 1..16, unique by fact_id |
| required | bool | declares whether the step is mandatory |

### PlanParallelGroup

| Field | Type | Rules |
| --- | --- | --- |
| group_id | canonical code | unique inside the plan |
| step_ids | tuple of canonical codes | 1..3, unique, order preserving |

## Execution-lane catalog

| Lane | Meaning |
| --- | --- |
| deterministic | predefined executable flow built by trusted code |
| fast | one bounded deterministic execution step |
| composite | bounded multi-step plan produced by a bounded planner |

Terminal RouteDecision lanes (clarify, abstain, deny) never produce an
ExecutionPlan.

## Composition catalog

| Composition | Meaning |
| --- | --- |
| single | one independently sufficient step |
| sectioned | multiple fact groups presented in distinct sections |
| comparison | facts represent comparable subjects, versions, periods or policies |
| rule_join | general rule facts and personal facts feed deterministic rule evaluation |
| temporal_join | facts are combined across ordered time periods |
| aggregate | a deterministic calculation or aggregation combines validated facts |

The contract implements no composition algorithm. Important calculations are
performed by trusted code, never by the answer generator.

## Missing-evidence catalog

| Policy | Permitted downstream behavior |
| --- | --- |
| partial | a bounded partial answer is permitted |
| clarify | a clarification turn is permitted |
| abstain | abstention is required |

The policy declares permitted behavior only. The future Evidence Manager and
Orchestrator decide whether it applies. A missing-evidence policy is not an
exception policy: no clarification text, fallback answer, denial text, or
exception detail may appear in the plan.

## Fact and typed-binding semantics

- Every produced fact identifier is globally unique inside the plan.
- Every required fact is produced exactly once.
- Every step produces at least one fact.
- A produced fact is valid only when it is listed in required_facts or consumed
  by a later step through a step_output binding.
- A step whose outputs are neither required nor consumed is rejected.
- No binding may reference an unknown fact.
- A step_output binding must match the producer value_type and data_scope.
- The producer must be listed as a direct dependency of the consumer.
- Downstream consumers cannot silently reinterpret fact type or scope.

Actual fact values are never stored in the plan.

## RouteDecision binding

- route_decision_id identifies the trusted decision authorizing this plan.
- lane, allowed_capabilities, required_facts and budget must be copied from that
  decision by trusted plan-building code.
- The contract cannot dereference RouteDecision and cannot prove equality by
  itself.
- The future PlanValidator must compare these fields against the referenced
  RouteDecision and fail closed on any mismatch.
- A terminal RouteDecision must never produce an ExecutionPlan.
- The RouteDecision model is referenced, never embedded.

## DAG and topological-order semantics

The steps tuple must be topologically ordered:

- every dependency names an existing step;
- every dependency appears earlier in the steps tuple;
- forward dependencies are rejected;
- self-dependency is rejected;
- therefore no cycle can exist;
- duplicate step identifiers are rejected.

The bounded graph never exceeds five steps, so deterministic validation is
sufficient and no graph library is used.

## Parallel-group semantics

- Every plan step appears in exactly one parallel group.
- No unknown step may appear in a group.
- No step may appear in more than one group.
- Every group size is at most budget.max_parallel_steps.
- The number of steps is at most budget.max_steps.
- Dependencies must appear in an earlier group.
- Dependent steps cannot share a group.
- Group order is preserved and represents execution layers.

The contract declares concurrency permission only; it never schedules.

## Capability-allowlist semantics

Every step capability must appear in allowed_capabilities, and every listed
allowed capability must be used by at least one step. This prevents unused or
silently expanded capability authority.

## Personal-data and Semantic Analytics restriction

For any step whose capability is semantic_analytics:

- every input binding must declare data_scope "general";
- every produced fact must declare data_scope "general".

A Semantic Analytics step that consumes a personal fact, declares a personal
external binding, or produces a personal fact is rejected. Personal data may be
consumed by rule_evaluator where policy permits, but this contract does not
authorize that access. Authorization and policy checks remain external trusted
responsibilities.

## Budget semantics

RouteBudget is reused without modification. The plan additionally enforces:

- len(steps) <= budget.max_steps;
- maximum parallel-group size <= budget.max_parallel_steps;
- budget.max_steps >= 1 and budget.max_parallel_steps >= 1, because a plan always
  has at least one step.

No deadline, token budget, cost budget, provider quota, or latency value exists
in this contract. Those are deferred to runtime and CapabilityRequest binding.

## Revision and replan lineage

| Revision | Requirements |
| --- | --- |
| 0 | parent_plan_id is null |
| 1 | parent_plan_id is not null and budget.max_replans == 1 |

Revision values above one are rejected, and a plan must not reference itself as
its parent. The contract does not load or compare the parent plan. Trusted
replanning code must preserve request, route decision, authorization decision
and runtime snapshot bindings.

## Fast invariants

- exactly one step and exactly one parallel group;
- the group contains that single step;
- exactly one allowed capability, equal to the step capability;
- composition_type == "single";
- budget.max_steps == 1 and budget.max_parallel_steps == 1;
- budget.max_replans == 0;
- revision == 0 and parent_plan_id is null.

Fast plans are deterministic one-step plans and are not produced by the free
planner.

## Composite invariants

- 2 <= len(steps) <= 5;
- composition_type != "single";
- 2 <= budget.max_steps <= 5;
- 1 <= budget.max_parallel_steps <= 3.

Revision may be zero or one according to the replan rules. The contract
validates the bounded DAG but never executes composition.

## Deterministic invariants

- budget.max_replans == 0;
- revision == 0 and parent_plan_id is null;
- one step requires composition_type == "single";
- more than one step requires composition_type != "single".

This represents a predefined executable flow only. A deterministic fixed
response with zero steps does not need an ExecutionPlan and must not be
represented here.

## Trust boundary

### Trusted route-policy layer

Produces or supplies the route decision reference, lane, capability allowlist,
required facts and frozen budget.

### Trusted plan builder or bounded planner

Produces the plan identifier, goal, steps, dependencies, parallel groups,
composition, missing-evidence policy, revision lineage and plan-builder version.

### Trusted PlanValidator

Must verify the RouteDecision binding, authorization and runtime reference
consistency, the capability allowlist, the DAG, the parallel groups, typed
bindings, required-fact coverage, personal-data restrictions, hard budget limits
and revision lineage.

A model may propose a composite plan, but it cannot authorize or directly
execute it. Model-produced data remains untrusted until full deterministic
validation. Fast and deterministic plans should be built by code rather than
free-form model planning.

## Security restrictions

The following names are forbidden and rejected at the root and in every nested
model: raw_message, raw_query, normalized_query, standalone_query, query_text,
prompt, system_prompt, model, model_name, model_output, provider,
provider_response, rationale, rationale_text, reasoning, chain_of_thought,
answer, clarification_message, denial_message, tool, tool_name, tool_arguments,
function_call, sql, query, statement, where, predicate, filter_expression,
endpoint, url, api_key, token, access_token, secret, password, credentials,
roles, groups, principal_id, security_context_id, email, display_name,
session_id, headers, http_status, metadata, attributes, input_value,
output_value, typed_output, evidence, evidence_ids, error, exception,
retry_loop, deadline_ms, token_budget and cost_budget.

## Retention

- The contract does not authorize persistence.
- The plan contains references, codes and structural declarations rather than raw
  user content.
- Plans may be retained for replay and evaluation only under approved retention
  policy.
- Actual input values, model output, prompts, credentials, SQL and evidence
  content must never be copied into the plan.
- Telemetry should normally use plan identifier, revision, lane, goal, capability
  codes, step count, group count, policy-bound references and plan-builder
  version.

## Compatibility

ExecutionPlan 1.0.0 is closed.

- PATCH changes must not alter accepted or serialized payloads.
- Adding, removing or renaming a field is a major change.
- Changing lane, composition, missing-evidence, source-kind, data-scope or
  success-condition literals is a major change.
- Changing DAG, binding, fact-consumer, budget, revision, route-binding or
  personal-data semantics is a major change.
- Adding controlled operation, goal, fact-type or source-reference catalog
  entries does not change the JSON Schema.
- Version 1.0.0 becomes immutable after approval.

## Valid example: fast plan

```json
{
  "schema_version": "1.0.0",
  "plan_id": "11111111-1111-4111-8111-111111111111",
  "request_id": "22222222-2222-4222-8222-222222222222",
  "route_decision_id": "33333333-3333-4333-8333-333333333333",
  "authorization_decision_id": "44444444-4444-4444-8444-444444444444",
  "runtime_snapshot_id": "55555555-5555-4555-8555-555555555555",
  "planned_at": "2026-01-01T08:30:00Z",
  "lane": "fast",
  "goal": "goal.answer_question",
  "allowed_capabilities": ["document_retrieval"],
  "required_facts": ["fact.document"],
  "steps": [
    {
      "step_id": "step.retrieve",
      "capability": "document_retrieval",
      "operation": "document.retrieve",
      "depends_on": [],
      "input_bindings": [],
      "produces": [
        {
          "fact_id": "fact.document",
          "value_type": "type.document",
          "data_scope": "general"
        }
      ],
      "required": true
    }
  ],
  "parallel_groups": [
    { "group_id": "group.retrieve", "step_ids": ["step.retrieve"] }
  ],
  "composition_type": "single",
  "success_condition": "all_required_facts",
  "missing_evidence_policy": "clarify",
  "budget": {
    "max_steps": 1,
    "max_parallel_steps": 1,
    "max_replans": 0,
    "max_retrieval_retries": 1,
    "max_analytics_repairs": 0,
    "max_answer_repairs": 0
  },
  "revision": 0,
  "parent_plan_id": null,
  "plan_builder_version": "1.0.0"
}
```

## Valid example: composite plan

```json
{
  "schema_version": "1.0.0",
  "plan_id": "11111111-1111-4111-8111-111111111111",
  "request_id": "22222222-2222-4222-8222-222222222222",
  "route_decision_id": "33333333-3333-4333-8333-333333333333",
  "authorization_decision_id": "44444444-4444-4444-8444-444444444444",
  "runtime_snapshot_id": "55555555-5555-4555-8555-555555555555",
  "planned_at": "2026-01-01T08:30:00Z",
  "lane": "composite",
  "goal": "goal.compare_policies",
  "allowed_capabilities": ["document_retrieval", "semantic_analytics"],
  "required_facts": ["fact.analysis"],
  "steps": [
    {
      "step_id": "step.retrieve",
      "capability": "document_retrieval",
      "operation": "document.retrieve",
      "depends_on": [],
      "input_bindings": [],
      "produces": [
        {
          "fact_id": "fact.document",
          "value_type": "type.document",
          "data_scope": "general"
        }
      ],
      "required": true
    },
    {
      "step_id": "step.analyze",
      "capability": "semantic_analytics",
      "operation": "analytics.execute_logical_plan",
      "depends_on": ["step.retrieve"],
      "input_bindings": [
        {
          "input_name": "input.document",
          "source_kind": "step_output",
          "source_ref": "fact.document",
          "source_step_id": "step.retrieve",
          "value_type": "type.document",
          "data_scope": "general"
        }
      ],
      "produces": [
        {
          "fact_id": "fact.analysis",
          "value_type": "type.analysis",
          "data_scope": "general"
        }
      ],
      "required": true
    }
  ],
  "parallel_groups": [
    { "group_id": "group.retrieve", "step_ids": ["step.retrieve"] },
    { "group_id": "group.analyze", "step_ids": ["step.analyze"] }
  ],
  "composition_type": "sectioned",
  "success_condition": "all_required_facts",
  "missing_evidence_policy": "partial",
  "budget": {
    "max_steps": 3,
    "max_parallel_steps": 2,
    "max_replans": 1,
    "max_retrieval_retries": 1,
    "max_analytics_repairs": 1,
    "max_answer_repairs": 0
  },
  "revision": 1,
  "parent_plan_id": "77777777-7777-4777-8777-777777777777",
  "plan_builder_version": "1.0.0"
}
```

## Valid example: deterministic predefined flow

```json
{
  "schema_version": "1.0.0",
  "plan_id": "11111111-1111-4111-8111-111111111111",
  "request_id": "22222222-2222-4222-8222-222222222222",
  "route_decision_id": "33333333-3333-4333-8333-333333333333",
  "authorization_decision_id": "44444444-4444-4444-8444-444444444444",
  "runtime_snapshot_id": "55555555-5555-4555-8555-555555555555",
  "planned_at": "2026-01-01T08:30:00Z",
  "lane": "deterministic",
  "goal": "goal.loan_eligibility",
  "allowed_capabilities": ["personal_selector", "rule_evaluator"],
  "required_facts": ["fact.eligibility"],
  "steps": [
    {
      "step_id": "step.personal",
      "capability": "personal_selector",
      "operation": "personal.select_self",
      "depends_on": [],
      "input_bindings": [],
      "produces": [
        {
          "fact_id": "fact.profile",
          "value_type": "type.profile",
          "data_scope": "personal"
        }
      ],
      "required": true
    },
    {
      "step_id": "step.rule",
      "capability": "rule_evaluator",
      "operation": "rule.evaluate",
      "depends_on": ["step.personal"],
      "input_bindings": [
        {
          "input_name": "input.profile",
          "source_kind": "step_output",
          "source_ref": "fact.profile",
          "source_step_id": "step.personal",
          "value_type": "type.profile",
          "data_scope": "personal"
        }
      ],
      "produces": [
        {
          "fact_id": "fact.eligibility",
          "value_type": "type.eligibility",
          "data_scope": "general"
        }
      ],
      "required": true
    }
  ],
  "parallel_groups": [
    { "group_id": "group.personal", "step_ids": ["step.personal"] },
    { "group_id": "group.rule", "step_ids": ["step.rule"] }
  ],
  "composition_type": "rule_join",
  "success_condition": "all_required_facts",
  "missing_evidence_policy": "abstain",
  "budget": {
    "max_steps": 2,
    "max_parallel_steps": 1,
    "max_replans": 0,
    "max_retrieval_retries": 0,
    "max_analytics_repairs": 0,
    "max_answer_repairs": 0
  },
  "revision": 0,
  "parent_plan_id": null,
  "plan_builder_version": "1.0.0"
}
```

## Representative invalid examples

| Attempt | Reason |
| --- | --- |
| lane "clarify" | terminal lanes never produce a plan |
| composite plan with composition_type "single" | composite requires multi-fact composition |
| fast plan with two steps | fast permits exactly one step |
| step depending on a later step | forward dependency breaks topological order |
| dependency and dependent in the same group | dependencies must run in an earlier layer |
| step missing from every parallel group | groups must partition the steps |
| group of three with max_parallel_steps 2 | group size exceeds the frozen budget |
| binding value_type different from producer | typed binding mismatch |
| binding data_scope different from producer | scope reinterpretation is forbidden |
| semantic_analytics step producing a personal fact | analytics must remain general-scope |
| produced fact neither required nor consumed | dead output and dead steps are rejected |
| revision 1 without parent_plan_id | replan lineage incomplete |
| revision 1 with max_replans 0 | budget does not permit replanning |
| parent_plan_id equal to plan_id | self-parent lineage |
| root field "sql" or "prompt" | forbidden field |

## Non-goals

- executing, scheduling or retrying steps;
- invoking a model or provider;
- constructing prompts, tool calls or queries;
- evaluating authorization or routing policy;
- resolving operations, fact types or artifacts;
- persisting plans or evidence.

## Deferred implementation work

- deterministic FastPlan builder;
- predefined-flow plan builder;
- bounded composite planner;
- PlanValidator implementation;
- route-decision binding verification;
- capability-operation catalog;
- fact-type catalog;
- typed binding resolver;
- graph scheduler;
- deadline and cancellation binding;
- plan replay evaluator;
- plan regression fixtures;
- ExecutionPlan integration with StepResult and CapabilityRequest.
