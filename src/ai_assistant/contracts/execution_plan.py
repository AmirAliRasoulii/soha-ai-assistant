"""Canonical bounded execution plan contract, schema version 1.0.0."""

from typing import Annotated, Final, Literal, Self
from uuid import UUID

from pydantic import AfterValidator, ConfigDict, Field, model_validator

from ai_assistant.contracts.base import ContractModel, SchemaVersion, UtcDateTime
from ai_assistant.contracts.route_decision import CapabilityName, RouteBudget

JSON_SCHEMA_DIALECT = "https://json-schema.org/draft/2020-12/schema"
EXECUTION_PLAN_SCHEMA_VERSION: Final[Literal["1.0.0"]] = "1.0.0"
EXECUTION_PLAN_SCHEMA_ID = "urn:ai-assistant:contracts:execution-plan:1.0.0"

ExecutionLane = Literal[
    "deterministic",
    "fast",
    "composite",
]
CompositionType = Literal[
    "single",
    "sectioned",
    "comparison",
    "rule_join",
    "temporal_join",
    "aggregate",
]
MissingEvidencePolicy = Literal[
    "partial",
    "clarify",
    "abstain",
]
InputSourceKind = Literal[
    "query_analysis",
    "route_decision",
    "runtime_snapshot",
    "approved_artifact",
    "step_output",
]
FactDataScope = Literal[
    "general",
    "personal",
]
SuccessCondition = Literal["all_required_facts"]

_ANALYTICS_CAPABILITY: Final[str] = "semantic_analytics"
_STEP_OUTPUT_KIND: Final[str] = "step_output"

_CANONICAL_CODE_PATTERN = r"^[a-z][a-z0-9._:-]*$"

_CanonicalCode = Annotated[
    str,
    Field(min_length=1, max_length=128, pattern=_CANONICAL_CODE_PATTERN),
]


def _require_uuid4(value: UUID) -> UUID:
    if value.version != 4:
        raise ValueError("identifier must be a version 4 UUID")
    return value


_Uuid4 = Annotated[UUID, AfterValidator(_require_uuid4)]
_Revision = Annotated[int, Field(strict=True, ge=0, le=1)]


def _require_unique_values(value: tuple[str, ...]) -> tuple[str, ...]:
    if len(set(value)) != len(value):
        raise ValueError("values must be unique")
    return value


_AllowedCapabilities = Annotated[
    tuple[CapabilityName, ...],
    Field(min_length=1, max_length=5),
    AfterValidator(_require_unique_values),
]
_RequiredFacts = Annotated[
    tuple[_CanonicalCode, ...],
    Field(min_length=1, max_length=32),
    AfterValidator(_require_unique_values),
]
_DependencyIds = Annotated[
    tuple[_CanonicalCode, ...],
    Field(max_length=4),
    AfterValidator(_require_unique_values),
]
_GroupStepIds = Annotated[
    tuple[_CanonicalCode, ...],
    Field(min_length=1, max_length=3),
    AfterValidator(_require_unique_values),
]


class PlanFactSpec(ContractModel):
    """Typed declaration of a semantic fact a step must produce."""

    # This is a declaration only: no text, payload, evidence, model output, or
    # user data may be carried here.
    fact_id: _CanonicalCode
    value_type: _CanonicalCode
    data_scope: FactDataScope


class PlanInputBinding(ContractModel):
    """Typed reference describing where a step input comes from."""

    input_name: _CanonicalCode
    source_kind: InputSourceKind
    source_ref: _CanonicalCode
    source_step_id: _CanonicalCode | None = None
    value_type: _CanonicalCode
    data_scope: FactDataScope

    @model_validator(mode="after")
    def _require_consistent_source(self) -> Self:
        if self.source_kind == _STEP_OUTPUT_KIND and self.source_step_id is None:
            raise ValueError("a step_output binding requires source_step_id")
        if self.source_kind != _STEP_OUTPUT_KIND and self.source_step_id is not None:
            raise ValueError("only a step_output binding may carry source_step_id")
        return self


def _require_unique_input_names(
    value: tuple[PlanInputBinding, ...],
) -> tuple[PlanInputBinding, ...]:
    names = [item.input_name for item in value]
    if len(set(names)) != len(names):
        raise ValueError("input bindings must be unique by input_name")
    return value


def _require_unique_fact_ids(value: tuple[PlanFactSpec, ...]) -> tuple[PlanFactSpec, ...]:
    fact_ids = [item.fact_id for item in value]
    if len(set(fact_ids)) != len(fact_ids):
        raise ValueError("produced facts must be unique by fact_id")
    return value


_InputBindings = Annotated[
    tuple[PlanInputBinding, ...],
    Field(max_length=16),
    AfterValidator(_require_unique_input_names),
]
_ProducedFacts = Annotated[
    tuple[PlanFactSpec, ...],
    Field(min_length=1, max_length=16),
    AfterValidator(_require_unique_fact_ids),
]


class PlanStep(ContractModel):
    """Bounded declaration of one intended capability invocation."""

    # The operation is a controlled code from a future capability-operation
    # catalog; its semantics are never derived from string prefixes.
    step_id: _CanonicalCode
    capability: CapabilityName
    operation: _CanonicalCode
    depends_on: _DependencyIds = ()
    input_bindings: _InputBindings = ()
    produces: _ProducedFacts
    required: bool

    @model_validator(mode="after")
    def _require_consistent_step(self) -> Self:
        if self.step_id in self.depends_on:
            raise ValueError("a step must not depend on itself")
        consumed_steps = {
            binding.source_step_id
            for binding in self.input_bindings
            if binding.source_kind == _STEP_OUTPUT_KIND
        }
        if self.step_id in consumed_steps:
            raise ValueError("a step must not consume its own output")
        for source_step_id in consumed_steps:
            if source_step_id not in self.depends_on:
                raise ValueError("a step_output binding must name a declared dependency")
        for dependency in self.depends_on:
            if dependency not in consumed_steps:
                raise ValueError(
                    "each declared dependency must be consumed by a step_output binding"
                )
        return self


class PlanParallelGroup(ContractModel):
    """Execution layer whose steps may run concurrently."""

    # The contract declares concurrency permission only; it never schedules.
    group_id: _CanonicalCode
    step_ids: _GroupStepIds


def _require_unique_step_ids(value: tuple[PlanStep, ...]) -> tuple[PlanStep, ...]:
    step_ids = [item.step_id for item in value]
    if len(set(step_ids)) != len(step_ids):
        raise ValueError("steps must be unique by step_id")
    return value


def _require_unique_group_ids(
    value: tuple[PlanParallelGroup, ...],
) -> tuple[PlanParallelGroup, ...]:
    group_ids = [item.group_id for item in value]
    if len(set(group_ids)) != len(group_ids):
        raise ValueError("parallel groups must be unique by group_id")
    return value


_Steps = Annotated[
    tuple[PlanStep, ...],
    Field(min_length=1, max_length=5),
    AfterValidator(_require_unique_step_ids),
]
_ParallelGroups = Annotated[
    tuple[PlanParallelGroup, ...],
    Field(min_length=1, max_length=5),
    AfterValidator(_require_unique_group_ids),
]


class ExecutionPlan(ContractModel):
    """Immutable, bounded description of intended execution for one turn."""

    model_config = ConfigDict(
        json_schema_extra={
            "$schema": JSON_SCHEMA_DIALECT,
            "$id": EXECUTION_PLAN_SCHEMA_ID,
        }
    )

    schema_version: Literal["1.0.0"] = EXECUTION_PLAN_SCHEMA_VERSION
    plan_id: _Uuid4
    request_id: _Uuid4
    # The referenced route decision authorizes this plan; trusted plan-building
    # code copies lane, capabilities, required facts, and budget from it.
    route_decision_id: _Uuid4
    authorization_decision_id: _Uuid4
    runtime_snapshot_id: _Uuid4
    planned_at: UtcDateTime
    lane: ExecutionLane
    goal: _CanonicalCode
    allowed_capabilities: _AllowedCapabilities
    required_facts: _RequiredFacts
    steps: _Steps
    parallel_groups: _ParallelGroups
    composition_type: CompositionType
    success_condition: SuccessCondition
    missing_evidence_policy: MissingEvidencePolicy
    budget: RouteBudget
    revision: _Revision
    parent_plan_id: _Uuid4 | None = None
    plan_builder_version: SchemaVersion

    @model_validator(mode="after")
    def _require_consistent_plan(self) -> Self:
        step_positions = {step.step_id: index for index, step in enumerate(self.steps)}
        self._require_capability_allowlist()
        self._require_topological_order(step_positions)
        group_positions = self._require_parallel_groups(step_positions)
        self._require_group_ordering(group_positions)
        self._require_fact_production(step_positions)
        self._require_analytics_scope()
        self._require_budget_limits()
        self._require_revision_lineage()
        self._require_lane_shape()
        return self

    def _require_capability_allowlist(self) -> None:
        used = {step.capability for step in self.steps}
        for step in self.steps:
            if step.capability not in self.allowed_capabilities:
                raise ValueError(
                    f"step {step.step_id!r} uses a capability outside allowed_capabilities"
                )
        for capability in self.allowed_capabilities:
            if capability not in used:
                raise ValueError(f"allowed capability {capability!r} is not used by any step")

    def _require_topological_order(self, step_positions: dict[str, int]) -> None:
        for index, step in enumerate(self.steps):
            for dependency in step.depends_on:
                if dependency not in step_positions:
                    raise ValueError(
                        f"step {step.step_id!r} depends on unknown step {dependency!r}"
                    )
                if step_positions[dependency] >= index:
                    raise ValueError(
                        f"step {step.step_id!r} must appear after dependency {dependency!r}"
                    )

    def _require_parallel_groups(self, step_positions: dict[str, int]) -> dict[str, int]:
        group_positions: dict[str, int] = {}
        for index, group in enumerate(self.parallel_groups):
            if len(group.step_ids) > self.budget.max_parallel_steps:
                raise ValueError(f"group {group.group_id!r} exceeds budget.max_parallel_steps")
            for step_id in group.step_ids:
                if step_id not in step_positions:
                    raise ValueError(f"group {group.group_id!r} names unknown step {step_id!r}")
                if step_id in group_positions:
                    raise ValueError(f"step {step_id!r} appears in more than one group")
                group_positions[step_id] = index
        for step_id in step_positions:
            if step_id not in group_positions:
                raise ValueError(f"step {step_id!r} does not appear in any parallel group")
        return group_positions

    def _require_group_ordering(self, group_positions: dict[str, int]) -> None:
        for step in self.steps:
            for dependency in step.depends_on:
                if group_positions[dependency] >= group_positions[step.step_id]:
                    raise ValueError(
                        f"dependency {dependency!r} must run in a group before "
                        f"step {step.step_id!r}"
                    )

    def _require_fact_production(self, step_positions: dict[str, int]) -> None:
        producers: dict[str, tuple[str, PlanFactSpec]] = {}
        for step in self.steps:
            for fact in step.produces:
                if fact.fact_id in producers:
                    raise ValueError(f"fact {fact.fact_id!r} is produced more than once")
                producers[fact.fact_id] = (step.step_id, fact)
        for fact_id in self.required_facts:
            if fact_id not in producers:
                raise ValueError(f"required fact {fact_id!r} is not produced by any step")
        consumed = self._require_typed_bindings(producers, step_positions)
        for fact_id in producers:
            if fact_id not in self.required_facts and fact_id not in consumed:
                raise ValueError(
                    f"fact {fact_id!r} is neither required nor consumed by a later step"
                )

    def _require_typed_bindings(
        self,
        producers: dict[str, tuple[str, PlanFactSpec]],
        step_positions: dict[str, int],
    ) -> set[str]:
        consumed: set[str] = set()
        for step in self.steps:
            for binding in step.input_bindings:
                if binding.source_kind != _STEP_OUTPUT_KIND:
                    continue
                producer = producers.get(binding.source_ref)
                if producer is None or producer[0] != binding.source_step_id:
                    raise ValueError(
                        f"binding {binding.input_name!r} references unknown produced fact "
                        f"{binding.source_ref!r}"
                    )
                producer_step_id, fact = producer
                if step_positions[producer_step_id] >= step_positions[step.step_id]:
                    raise ValueError(
                        f"binding {binding.input_name!r} must consume an earlier step output"
                    )
                if binding.value_type != fact.value_type:
                    raise ValueError(
                        f"binding {binding.input_name!r} does not match the produced value type"
                    )
                if binding.data_scope != fact.data_scope:
                    raise ValueError(
                        f"binding {binding.input_name!r} does not match the produced data scope"
                    )
                consumed.add(binding.source_ref)
        return consumed

    def _require_analytics_scope(self) -> None:
        for step in self.steps:
            if step.capability != _ANALYTICS_CAPABILITY:
                continue
            for binding in step.input_bindings:
                if binding.data_scope != "general":
                    raise ValueError(
                        f"semantic analytics step {step.step_id!r} must not consume personal data"
                    )
            for fact in step.produces:
                if fact.data_scope != "general":
                    raise ValueError(
                        f"semantic analytics step {step.step_id!r} must not produce personal data"
                    )

    def _require_budget_limits(self) -> None:
        if len(self.steps) > self.budget.max_steps:
            raise ValueError("the plan declares more steps than budget.max_steps permits")
        if self.budget.max_parallel_steps < 1:
            raise ValueError("an execution plan requires at least one parallel step")

    def _require_revision_lineage(self) -> None:
        if self.parent_plan_id is not None and self.parent_plan_id == self.plan_id:
            raise ValueError("a plan must not reference itself as its parent")
        if self.revision == 0 and self.parent_plan_id is not None:
            raise ValueError("an initial plan must not carry a parent plan reference")
        if self.revision == 1:
            if self.parent_plan_id is None:
                raise ValueError("a replanned plan requires a parent plan reference")
            if self.budget.max_replans != 1:
                raise ValueError("a replanned plan requires a budget permitting one replan")

    def _require_lane_shape(self) -> None:
        if self.lane == "fast":
            self._require_fast_shape()
        elif self.lane == "composite":
            self._require_composite_shape()
        else:
            self._require_deterministic_shape()

    def _require_fast_shape(self) -> None:
        if len(self.steps) != 1 or len(self.parallel_groups) != 1:
            raise ValueError("a fast plan requires exactly one step and one parallel group")
        if len(self.allowed_capabilities) != 1:
            raise ValueError("a fast plan requires exactly one allowed capability")
        if self.steps[0].capability != self.allowed_capabilities[0]:
            raise ValueError("the fast step capability must equal the allowed capability")
        if self.composition_type != "single":
            raise ValueError("a fast plan requires the 'single' composition type")
        if self.budget.max_steps != 1 or self.budget.max_parallel_steps != 1:
            raise ValueError("a fast plan requires a one-step budget")
        if self.budget.max_replans != 0:
            raise ValueError("a fast plan must not permit replanning")
        if self.revision != 0 or self.parent_plan_id is not None:
            raise ValueError("a fast plan must be an initial plan")

    def _require_composite_shape(self) -> None:
        if len(self.steps) < 2:
            raise ValueError("a composite plan requires at least two steps")
        if self.composition_type == "single":
            raise ValueError("a composite plan must not use the 'single' composition type")
        if self.budget.max_steps < 2:
            raise ValueError("a composite plan requires a budget of at least two steps")
        if self.budget.max_parallel_steps < 1:
            raise ValueError("a composite plan requires at least one parallel step")

    def _require_deterministic_shape(self) -> None:
        if self.budget.max_replans != 0:
            raise ValueError("a deterministic plan must not permit replanning")
        if self.revision != 0 or self.parent_plan_id is not None:
            raise ValueError("a deterministic plan must be an initial plan")
        if len(self.steps) == 1 and self.composition_type != "single":
            raise ValueError("a one-step deterministic plan requires the 'single' composition")
        if len(self.steps) > 1 and self.composition_type == "single":
            raise ValueError(
                "a multi-step deterministic plan must not use the 'single' composition"
            )
