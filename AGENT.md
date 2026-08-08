# AGENT.md --- Incident OS Engineering Contract

This document is mandatory engineering policy for the Incident OS
repository.

Read this file and `PLAN.md` before making architecture or
implementation decisions.

These documents define the project boundaries. Do not reinterpret them
casually.

------------------------------------------------------------------------

# 1. PROJECT IDENTITY

Product name:

Incident OS

Product definition:

> An external incident investigation and response platform that connects
> to production systems through telemetry and explicitly authorized
> read-only integrations, correlates evidence across distributed
> systems, verifies root-cause hypotheses, and produces evidence-backed
> recommendations.

Incident OS is an external control/analysis plane.

Incident OS is NOT installed inside a customer's application codebase as
the primary product architecture.

Incident OS does NOT require direct write access to customer production
systems.

Incident OS does NOT execute arbitrary production commands.

------------------------------------------------------------------------

# 2. NON-NEGOTIABLE ARCHITECTURE

The system has four boundaries:

``` text
CUSTOMER PRODUCTION
        |
        | telemetry / explicitly authorized read-only data
        v
INTEGRATION LAYER
        |
        v
INCIDENT OS CONTROL PLANE
        |
        v
INVESTIGATION / AI
```

The customer's production environment remains outside Incident OS.

Incident OS must not assume network access to arbitrary customer
infrastructure.

Incident OS must not assume that customer databases, Redis, Kafka,
Kubernetes, or cloud APIs are publicly reachable.

Connections must be explicitly configured.

------------------------------------------------------------------------

# 3. PRODUCTION INTEGRATION MODEL

Incident OS supports these integration classes:

## A. Telemetry Integration

Primary production integration.

Use OpenTelemetry-compatible telemetry.

Supported signal classes:

-   logs
-   metrics
-   traces

Production telemetry enters Incident OS through a controlled ingestion
boundary.

The customer's application does not need to send arbitrary application
state directly to the Incident OS database.

Telemetry must pass through an ingestion/collection layer.

------------------------------------------------------------------------

## B. Source Integrations

Incident OS may consume explicitly authorized read-only information
from:

-   Git providers
-   deployment systems
-   PostgreSQL
-   Redis
-   Kafka
-   other infrastructure sources only after an explicit connector
    contract exists

Every connector MUST define:

-   authentication method
-   authorization scope
-   data collected
-   polling/event mechanism
-   timeout behavior
-   retry behavior
-   rate limits
-   data retention behavior
-   failure behavior
-   secret handling

No connector may silently acquire write privileges.

------------------------------------------------------------------------

## C. Remediation

Production remediation is NOT part of the core MVP.

Incident OS may generate recommendations.

The recommendation is not an executed action.

The system must distinguish:

``` text
Recommendation
```

from:

``` text
Execution
```

Automatic production remediation is forbidden unless a future
architecture explicitly defines:

-   authorization
-   human approval
-   restricted execution
-   audit logging
-   rollback
-   timeout
-   failure handling
-   least privilege

The hackathon implementation must keep remediation in the sandbox.

------------------------------------------------------------------------

# 4. DEMO PRODUCTION ENVIRONMENT

The project contains a controlled production simulator.

The simulator is a real distributed application.

It uses:

-   FastAPI
-   SQLAlchemy
-   PostgreSQL
-   Kafka
-   Redis
-   OpenTelemetry

The simulator produces real:

-   logs
-   metrics
-   traces
-   database activity
-   Redis activity
-   Kafka activity
-   deployment metadata

The simulator connects to Incident OS through the same integration
contracts used for external production systems.

Do NOT insert fake telemetry directly into the final Incident OS
investigation database as the primary demo path.

The intended demo path is:

``` text
Demo Production System
        |
        | real telemetry
        v
Integration Layer
        |
        v
Incident OS
```

Chaos injection happens in the demo production environment.

Incident OS observes the resulting behavior.

------------------------------------------------------------------------

# 5. CHAOS LAB BOUNDARY

Chaos Lab operates ONLY against:

-   the local test environment
-   the dedicated demo production environment
-   explicitly isolated replay environments

Chaos Lab MUST NOT operate against an arbitrary customer production
environment.

Supported deterministic scenarios:

-   Redis outage
-   PostgreSQL slow query
-   PostgreSQL deadlock
-   Kafka consumer lag
-   Kafka consumer crash
-   memory leak
-   CPU saturation
-   bad deployment
-   connection-pool exhaustion
-   dependency timeout

Each scenario must have:

``` text
scenario.yaml
injector
expected.json
```

Every scenario must declare:

-   target
-   injection
-   expected symptoms
-   expected affected service
-   expected root cause
-   expected recommendation
-   evaluation criteria

------------------------------------------------------------------------

# 6. CORE INVESTIGATION PIPELINE

The investigation pipeline is fixed:

``` text
Telemetry Ingestion
    |
    v
Deterministic Incident Detection
    |
    v
Incident
    |
    v
Evidence Collection
    |
    v
Correlation
    |
    v
Candidate Root Causes
    |
    v
Deterministic Verification
    |
    v
Root Cause
    |
    v
Recommendation
    |
    v
Replay
```

Do not bypass evidence collection and send raw incident context directly
to the LLM.

Do not allow the LLM to declare an unverified hypothesis as a verified
root cause.

Incident detection is part of the core pipeline.

The normal production flow must NOT begin with a manually created
incident.

Chaos Lab causes failures in the demo production environment.

Chaos Lab MUST NOT directly create the Incident OS incident record.

Detection is deterministic.

Do NOT use ML anomaly detection for the initial detector.

Do NOT make the LLM responsible for detecting incidents.

Manual incident creation is a development/debugging endpoint only.

Initial detection rules:

- HTTP 5xx rate exceeds a configured threshold for a service.
- p95 latency exceeds a configured threshold for a service.
- Redis error rate exceeds a configured threshold.
- Kafka consumer lag exceeds a configured threshold.
- a deployment followed by configured error/latency thresholds within a
  defined time window.

Rules are configurable and stored as application configuration or
database records.

------------------------------------------------------------------------

# 7. EVIDENCE-FIRST RULE

Deterministic systems collect evidence.

AI interprets evidence.

The evidence pipeline has priority over the AI layer.

Evidence sources include:

-   logs
-   metrics
-   traces
-   PostgreSQL observations
-   Redis observations
-   Kafka observations
-   deployments
-   Git commits
-   service topology
-   timeline events

Evidence must be stored with provenance.

Every evidence item should be traceable to:

-   source
-   timestamp
-   service
-   incident
-   investigation
-   collection run

------------------------------------------------------------------------

# 8. FACT / INFERENCE / HYPOTHESIS / VERIFICATION

The system must maintain these distinct categories.

## Fact

Directly observed evidence.

Example:

``` text
Redis p95 latency increased from 8ms to 420ms.
```

## Inference

A logical interpretation of facts.

Example:

``` text
Redis latency may contribute to payment latency.
```

## Hypothesis

A candidate explanation requiring verification.

Example:

``` text
Redis latency caused payment timeouts.
```

## Verified Root Cause

A hypothesis supported by independent evidence and verification.

Never collapse these categories.

## Deterministic Verification

Verification MUST be deterministic.

The verification engine executes evidence checks against the Evidence
Store and/or explicitly authorized read-only integrations.

The LLM may explain a verification result.

The LLM MUST NOT manufacture verification results.

The LLM MUST NOT be the only verification mechanism.

Verification outcomes:

-   VERIFIED
-   CONTRADICTED
-   UNVERIFIED

------------------------------------------------------------------------

# 9. AI BOUNDARIES

The AI MUST NOT:

-   invent evidence
-   invent logs
-   invent metrics
-   invent traces
-   invent timestamps
-   invent commits
-   invent deployments
-   invent infrastructure events
-   invent configuration changes
-   invent database state
-   invent Redis state
-   invent Kafka state
-   invent Zerops capabilities
-   invent API endpoints
-   invent repository files
-   invent successful tests
-   invent deployment success
-   detect incidents

If evidence is missing:

``` text
Missing evidence
```

must be reported.

If a conclusion cannot be verified:

``` text
Unverified hypothesis
```

must be reported.

The AI must never fill missing information with a plausible assumption.

------------------------------------------------------------------------

# 10. AI OUTPUT CONTRACT

AI output must be structured and validated.

Use Pydantic schemas.

Minimum investigation hypothesis shape:

``` json
{
  "hypothesis": "string",
  "confidence": 0.0,
  "supporting_evidence": [],
  "contradicting_evidence": [],
  "missing_evidence": [],
  "verification_steps": []
}
```

The application validates the result.

Invalid model output is an error.

Do not convert malformed model output into a fabricated valid result.

------------------------------------------------------------------------

# 11. CONFIDENCE RULE

Confidence must be derived from an explicit application-defined
strategy.

Do not use arbitrary confidence values.

Every confidence result must be explainable using:

-   supporting evidence
-   contradicting evidence
-   missing evidence
-   verification results

The system must not claim statistical certainty unless a statistical
method has actually been implemented.

------------------------------------------------------------------------

# 12. KAFKA CONTRACT

Kafka is the asynchronous investigation event backbone.

Event fields:

``` text
event_id
event_type
timestamp
incident_id
investigation_id
producer
schema_version
payload
```

Consumers MUST be idempotent.

Duplicate events are expected.

Retries are expected.

Failures are expected.

Consumers must not silently swallow failures.

Dead-letter handling is required for unrecoverable processing failures.

Large telemetry payloads must not be placed directly into Kafka events.

Use references to durable storage for large payloads.

Do not claim exactly-once processing unless it is explicitly implemented
and verified.

Kafka is required.

The deployed application uses Zerops-managed Kafka as the event
backbone.

Do NOT replace Kafka with Redis queues.

Use the actual credentials and connection details provided by Zerops.

Do NOT invent Zerops Kafka hostnames, ports, credentials, CLI commands,
or security configuration.

Before declaring Kafka integration complete, verify an actual deployed
connection.

Required Kafka verifications:

-   FastAPI can publish an event.
-   the Worker Pool can consume the event.
-   consumer groups function correctly.
-   authentication works.
-   multiple messages can be processed.
-   duplicate delivery does not corrupt investigation state.
-   failed processing can retry.
-   unrecoverable messages reach the defined failure/dead-letter path.
-   the connection uses the security configuration actually supported by
    the deployed Zerops Kafka service.

Do not claim Kafka integration works until these tests have been
executed.

The Kafka abstraction MUST remain isolated behind an internal event
interface.

Business logic MUST NOT depend directly on the Kafka client
implementation.

------------------------------------------------------------------------

# 13. REDIS CONTRACT

Redis is ephemeral/high-speed infrastructure.

Allowed uses:

-   investigation progress
-   cache
-   rate limiting
-   live state
-   pub/sub
-   temporary coordination

Redis is NOT durable incident storage.

Redis keys must be namespaced.

Temporary state must have appropriate TTLs.

Application behavior must define what happens when Redis is unavailable.

Redis MUST NOT be the authoritative investigation completion state.

PostgreSQL is the authoritative workflow state.

Redis may report investigation progress only.

------------------------------------------------------------------------

# 14. POSTGRESQL CONTRACT

PostgreSQL is the durable application source of truth.

Use:

-   SQLAlchemy
-   Alembic
-   explicit transactions
-   constraints
-   indexes based on actual query patterns

Do not:

-   expose SQLAlchemy models as API contracts
-   perform unbounded telemetry queries
-   load huge datasets into memory
-   use Redis as durable state

Use explicit Pydantic API schemas.

------------------------------------------------------------------------

# 15. ASYNCHRONOUS INVESTIGATION CONTRACT

Creating an investigation is asynchronous.

The API must:

``` text
validate
create investigation
publish work
return investigation identifier
```

Workers perform analysis asynchronously.

Investigation states:

``` text
CREATED
COLLECTING
ANALYZING
VERIFYING
READY
FAILED
```

State transitions must be explicit.

Workers must not independently overwrite final state without
coordination.

For every investigation, the orchestrator creates explicit
investigation_steps.

Required fields:

-   id
-   investigation_id
-   step_type
-   status
-   attempt
-   started_at
-   completed_at
-   error
-   created_at
-   updated_at

Valid statuses:

-   PENDING
-   RUNNING
-   COMPLETED
-   FAILED

Workers update only their own step.

Kafka duplicate delivery must not create duplicate logical steps.

Retries increment attempt and do not create a new logical step.

Correlation is triggered only when the required collection steps reach
terminal state according to the investigation policy.

COMPLETED steps count as successful evidence collection.

FAILED steps are terminal failures.

Correlation must record which evidence sources failed.

Never silently pretend failed collection succeeded.

PostgreSQL is the authoritative workflow state.

------------------------------------------------------------------------

# 16. SERVICE BOUNDARY RULE

Do not create a service solely to increase the service count.

A service boundary must exist because of one or more of:

-   independent scaling
-   independent failure handling
-   independent deployment
-   clear domain ownership
-   asynchronous processing
-   security boundary

The initial logical services are:

``` text
API
Investigation Orchestrator
Log Worker
Metrics Worker
Trace Worker
PostgreSQL Worker
Redis Worker
Kafka Worker
Deployment/Git Worker
Correlation Engine
Verification Worker
Replay Engine
Chaos Controller
```

These may initially exist as modules/processes where that is simpler.

Deployment boundaries must follow actual operational needs.

The initial deployment uses approximately five application
processes/services:

1.  Next.js
2.  FastAPI API
3.  Worker Pool
4.  Investigation/Correlation/Verification Process
5.  Replay/Chaos Controller

Plus infrastructure:

-   PostgreSQL
-   Redis
-   Kafka

The logical workers (Log, Metrics, Trace, PostgreSQL, Redis, Kafka,
Deployment, Git) execute inside the Worker Pool unless a later verified
scaling requirement justifies separation.

Do NOT create separate deployment services merely to enlarge the
architecture diagram.

A deployment boundary requires a real operational reason: independent
scaling, independent deployment, independent failure isolation, or
security isolation.

------------------------------------------------------------------------

# 17. INTEGRATION LAYER

The Integration Layer is a first-class architectural component.

It contains controlled connectors.

Initial connector classes:

``` text
OpenTelemetry
Git
PostgreSQL
Redis
Kafka
Deployment metadata
```

OpenTelemetry is the primary telemetry path.

Source connectors are explicitly authorized and read-only.

Every connector must expose a stable internal contract to the
investigation system.

Example:

``` text
Connector
    |
normalized evidence
    |
Evidence Store
```

The investigation engine must not depend directly on vendor-specific
APIs.

Define an internal evidence-source interface before implementing live
connectors.

Conceptually:

``` text
EvidenceSource

    collect(context) -> Evidence[]
```

The investigation engine MUST depend on EvidenceSource.

It MUST NOT depend directly on a specific database, Redis client, Kafka
client, or fixture implementation.

Live mode uses:

-   LivePostgresSource
-   LiveRedisSource
-   LiveKafkaSource
-   LiveTelemetrySource

Replay mode uses:

-   FixturePostgresSource
-   FixtureRedisSource
-   FixtureKafkaSource
-   FixtureTelemetrySource

Both modes return the same normalized Evidence contract.

------------------------------------------------------------------------

# 18. CREDENTIAL BOUNDARY

Customer credentials must never be placed into:

-   frontend code
-   LLM prompts
-   Kafka payloads
-   logs
-   Git repositories
-   PostgreSQL evidence records

Secrets must be stored using the deployment environment's
secret/configuration mechanism.

Connector credentials must use least privilege.

Production connectors must default to read-only access.

------------------------------------------------------------------------

# 19. OBSERVABILITY OF INCIDENT OS

Incident OS must observe itself.

Required identifiers:

``` text
incident_id
investigation_id
run_id
trace_id
```

Important operations must emit:

-   structured logs
-   metrics
-   traces

The full investigation path must be traceable:

``` text
Next.js
→ FastAPI
→ Kafka
→ Worker
→ Evidence Store
→ Correlation
→ Verification
→ AI
→ Result
```

------------------------------------------------------------------------

# 20. FRONTEND CONTRACT

The investigation UI must answer:

1.  What broke?
2.  What evidence exists?
3.  Why is this hypothesis likely?
4.  What evidence verifies it?
5.  What should the engineer do?

Primary views:

-   Dashboard
-   Incidents
-   Investigation
-   Evidence
-   Timeline
-   Service Graph
-   Hypotheses
-   Recommendations
-   Replay
-   Chaos Lab

The product is NOT a generic chat application.

------------------------------------------------------------------------

# 21. SECURITY CONTRACT

Never commit:

-   passwords
-   API keys
-   access tokens
-   private keys
-   cloud credentials
-   database credentials

Never log secrets.

Never execute arbitrary LLM-generated shell commands.

Never allow the AI to directly obtain unrestricted production
credentials.

Production remediation is outside the MVP.

------------------------------------------------------------------------

# 22. ZEROPS CONTRACT

Zerops hosts the Incident OS control plane and its required services
where supported.

Zerops is not treated as a fictional infrastructure abstraction.

Before implementing a Zerops-specific feature:

1.  verify the current official Zerops documentation
2.  verify the available project configuration/API/CLI
3.  test the behavior when possible

Never invent:

-   Zerops services
-   Zerops APIs
-   Zerops CLI flags
-   Zerops scaling semantics
-   Zerops networking semantics
-   Zerops deployment semantics
-   Zerops preview environment behavior

If a Zerops capability is unavailable, do not pretend that it exists.

Use an explicitly documented fallback.

------------------------------------------------------------------------

# 23. REPLAY CONTRACT

Replay must not modify customer production.

Replay uses:

-   incident timeline
-   telemetry fixtures
-   service topology
-   deployment metadata
-   scenario configuration

Replay creates an isolated investigation context.

Do not implement full distributed state restoration unless explicitly
required by a future approved architecture change.

Replay MUST use the same connector contract as production.

Both modes return the same normalized Evidence contract:

``` text
Production:

Live Source
    → Evidence
    → Investigation

Replay:

Fixture Source
    → Evidence
    → Same Investigation
```

The investigation engine MUST NOT know whether evidence came from
production or replay fixtures.

Establish this abstraction before deeply coupling the investigation
engine to live infrastructure.

------------------------------------------------------------------------

# 24. DEVELOPMENT PROCESS

Before changing code:

1.  Read relevant files.
2.  Read the relevant sections of `AGENT.md` and `PLAN.md`.
3.  Identify current behavior.
4.  Identify contracts affected.
5.  Identify failure modes.
6.  Identify tests.

Then implement the smallest correct change.

After implementation:

1.  run relevant tests
2.  run type/static checks where configured
3.  verify integration behavior where possible
4.  report exactly what was verified
5.  report what remains unverified

------------------------------------------------------------------------

# 25. NO UNVERIFIED CLAIMS

The following statements require actual evidence:

``` text
"works"
"fixed"
"production-ready"
"scales"
"secure"
"Zerops supports this"
"tests pass"
"deployment succeeded"
"Kafka integration works"
"incident detection works"
"investigation steps are tracked"
"deterministic verification runs"
"Zerops Kafka connection works"
"the LLM is not required for a root-cause result"
```

If it was not verified, say:

``` text
Not verified.
```

or:

``` text
Implemented but not executed.
```

------------------------------------------------------------------------

# 26. ASK BEFORE MATERIAL AMBIGUITY

Ask the user before proceeding when:

-   a production integration contract is missing
-   a security boundary is unclear
-   a destructive operation is requested
-   two incompatible architectures are possible
-   a public API contract is unclear
-   a database migration can cause data loss
-   Zerops capability is unverified and materially affects architecture
-   existing behavior may intentionally conflict with the requested
    change

Do not ask for confirmation for trivial implementation details that are
already defined by this document.

------------------------------------------------------------------------

# 27. TESTING CONTRACT

Testing levels:

## Unit

Test:

-   parsers
-   schemas
-   correlation rules
-   incident detection rules
-   investigation step state transitions
-   scoring
-   domain logic

## Integration

Test:

``` text
FastAPI
PostgreSQL
Kafka
Redis
Workers
Incident detection
Investigation step completion
```

## End-to-End

Test complete chaos scenarios:

``` text
Inject
→ telemetry
→ ingestion
→ incident detection
→ investigation
→ evidence
→ step completion
→ correlation
→ verification
→ result
```

## Evaluation

Measure:

-   incident detection accuracy
-   incident detection latency
-   root cause accuracy
-   affected service accuracy
-   evidence accuracy
-   recommendation accuracy
-   hallucination rate
-   investigation duration

------------------------------------------------------------------------

# 28. GOLDEN PATH

This path must remain working:

``` text
Demo Production System
→
Real Failure
→
Real Telemetry
→
Integration Layer
→
Deterministic Incident Detection
→
Incident Created
→
Investigation Created
→
Kafka Events
→
Parallel Evidence Workers
→
Investigation Step Completion Tracking
→
Deterministic Correlation
→
Candidate Root Causes
→
Deterministic Verification
→
Verified Root Cause
→
LLM Explanation / Synthesis
→
Recommendation
→
Replay
```

The LLM is not allowed to bypass:

-   telemetry
-   evidence
-   correlation
-   verification

Do not replace this with fabricated telemetry injected directly into the
final analysis database.

------------------------------------------------------------------------

# 29. PRIORITY

P0:

-   production simulator
-   OpenTelemetry integration
-   deterministic chaos
-   deterministic incident detection
-   evidence ingestion
-   investigation pipeline
-   investigation step tracking
-   correlation
-   deterministic verification
-   investigation UI
-   Zerops deployment
-   Zerops Kafka
-   replay

P1:

-   Git integration
-   deployment integration
-   service graph
-   additional scenarios
-   stronger evaluation
-   self-observability

P2:

-   production remediation
-   historical incident similarity
-   advanced automation
-   additional infrastructure connectors

Do not sacrifice P0 for P1 or P2.

------------------------------------------------------------------------

# 30. FINAL ENGINEERING RULE

The application must behave according to evidence, not assumptions.

When information is missing:

ASK OR VERIFY.

When behavior is unknown:

DO NOT INVENT IT.

When a feature is unsupported:

DO NOT PRETEND IT EXISTS.

When code is changed:

TEST IT.

When a test is not run:

DO NOT CLAIM IT PASSED.

When production access is required:

USE THE MINIMUM READ-ONLY ACCESS NECESSARY.

When the AI is uncertain:

SHOW THE UNCERTAINTY.

The system exists to make production debugging more reliable, not to
produce confident-looking guesses.

------------------------------------------------------------------------

# 31. MANDATORY ARCHITECTURE CORRECTIONS

The following architecture corrections are fixed engineering decisions.

Do not reopen them unless implementation evidence proves that a
decision is technically impossible.

1.  Incident detection is part of the core pipeline.

2.  Collection completion is explicit (investigation steps).

3.  Verification is deterministic.

4.  Deployment service sprawl is limited to approximately five
    application processes.

5.  Kafka is required and Zerops Kafka is the event backbone.

6.  LLM failure must not destroy the investigation.

7.  Replay uses the same connector contract (EvidenceSource).

8.  The final golden path includes detection and step completion.

9.  Implementation order: detection → steps → EvidenceSource →
    correlation → verification → fallback engine → Kafka on Zerops →
    LLM → replay → end-to-end chaos.

10. Completion is not claimed until the verification checklist passes.

The LLM is not allowed to bypass telemetry, evidence, correlation, or
verification.
