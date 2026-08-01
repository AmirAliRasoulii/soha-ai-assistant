# ADR-002: AuditEvent and the CloudEvents Boundary

Status: accepted for CONTRACT-005 implementation

## Context

The AI Core needs a canonical, safe, minimal audit fact that trusted runtime code can emit whenever a runtime action completes, is denied, or fails. This audit fact must be replayable, closed, and free of raw diagnostic, prompt, model, provider, or secret content, so it can be safely retained, delivered, and inspected without becoming a second copy of application data.

Separately, operational systems commonly use CloudEvents 1.0 as a transport envelope format for asynchronous event delivery across message brokers. The AI Core must not depend on any particular delivery mechanism, broker client, or transport envelope.

## Decision

1. AuditEvent is the canonical AI Core audit payload.
2. Operational adapters wrap AuditEvent in a CloudEvents 1.0 envelope when asynchronous delivery is used.
3. No CloudEvents SDK or transport field exists in the AI Core model.
4. Adapter mapping from AuditEvent to a CloudEvents envelope should use:
   - CloudEvents id from event_id;
   - CloudEvents type from event_type;
   - CloudEvents time from occurred_at;
   - CloudEvents data as the serialized AuditEvent;
   - CloudEvents source from deployment-controlled configuration;
   - CloudEvents dataschema from the published AuditEvent schema URN (urn:ai-assistant:contracts:audit-event:1.0.0).
5. Event persistence must be append-only or equivalently tamper-evident at the operational layer; this is not enforced by the Pydantic contract.
6. Duplicate delivery is deduplicated by event_id.
7. Delivery order is not assumed by consumers of AuditEvent.
8. Audit, logs, and traces remain separate but correlated through shared identifiers such as correlation_id and request_id.
9. Exact delivery guarantees, retention, integrity, and storage mechanisms are deferred to future operational adapter work.

This repository does not implement a CloudEvents Pydantic model. CloudEvents 1.0 is referenced here only to describe the intended adapter boundary. CloudEvents 1.0 obsoletes no prior specification of its own; it is mentioned here by name as the target transport-envelope standard for future adapters.

## Consequences

- The AI Core stays vendor-neutral: no broker client, queue library, or CloudEvents SDK is a dependency of this repository.
- Every downstream delivery mechanism (broker, webhook, file sink, or test harness) can wrap the same AuditEvent payload consistently.
- Consumers must implement their own deduplication by event_id and must not assume delivery order.
- Changing AuditEvent semantics is a contract-versioning decision, independent of how the event is eventually transported.

## Alternatives considered

- Embedding a CloudEvents envelope directly in the AI Core model. Rejected: this would couple the AI Core to a specific transport concern and would require CloudEvents-specific fields (specversion, datacontenttype, source) that are operational, not domain, concerns.
- Adding a broker-specific delivery field, such as a Kafka partition key, to AuditEvent. Rejected: delivery routing is an operational adapter concern and is deployment-specific.
- Making AuditEvent itself append-only aware, for example by embedding a hash chain. Rejected for 1.0.0: tamper-evidence and integrity are operational storage-layer responsibilities, not part of the minimal audit fact contract.

## Security considerations

- AuditEvent never carries raw prompts, responses, exceptions, credentials, tokens, or provider payloads; only references and controlled codes are recorded.
- internal_detail_ref is opaque and is never resolved or persisted by this contract; it exists solely to correlate with an internal error record governed by separate access controls.
- Only trusted server-side runtime code may construct an AuditEvent; client input can influence the audited action but cannot supply audit identifiers, outcomes, or codes directly.
- Because AuditEvent is immutable and closed to unknown fields, an operational adapter cannot silently smuggle additional sensitive data through the audit path without a contract change.

## Deferred work

- A versioned Audit Event Catalog defining allowed event_type values and their operational meaning.
- A CloudEvents adapter implementation and its own tests.
- Message broker delivery, retry, and dead-letter handling.
- Append-only or tamper-evident persistence and its integrity guarantees.
- Retention and deletion policy execution.
- Integration of AuditEvent with ErrorEnvelope, FinalAnswer, StepResult, and configuration-change auditing.
