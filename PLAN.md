# PLAN.md --- Incident OS Implementation Plan

This plan is the fixed implementation plan for the hackathon unless the
user explicitly approves a change.

The product is an external incident investigation platform.

The customer production environment remains outside Incident OS.

------------------------------------------------------------------------

# 1. PRODUCT

Name:

Incident OS

Purpose:

Reduce the time required to investigate distributed production incidents
by collecting telemetry and authorized read-only infrastructure
evidence, correlating it, verifying root-cause hypotheses, and producing
evidence-backed recommendations.

Primary value:

``` text
Something is broken
        ↓
Incident OS collects evidence
        ↓
Deterministic incident detection
        ↓
Evidence is correlated
        ↓
Candidate root causes are generated
        ↓
Root causes are deterministically verified
        ↓
Root cause is identified
        ↓
LLM explains and synthesizes findings
        ↓
Safe recommendation is produced
        ↓
Incident can be replayed
```

------------------------------------------------------------------------

# 2. HARD ARCHITECTURE BOUNDARY

The architecture is:

``` text
┌─────────────────────────────────────────────┐
│ CUSTOMER PRODUCTION                        │
│                                             │
│ FastAPI / Services / DB / Redis / Kafka     │
│                                             │
│ OpenTelemetry instrumentation               │
└──────────────────────┬──────────────────────┘
                       │
                       │ telemetry
                       ▼
              ┌──────────────────┐
              │ Integration Layer│
              └────────┬─────────┘
                       │
                       ▼
┌─────────────────────────────────────────────┐
│ INCIDENT OS                                 │
│                                             │
│ Ingestion                                   │
│ Deterministic Incident Detection            │
│ Investigation Steps                         │
│ Kafka                                       │
│ Workers                                     │
│ PostgreSQL                                  │
│ Redis                                       │
│ Correlation                                 │
│ Deterministic Verification                  │
│ AI                                          │
│ Next.js                                     │
└─────────────────────────────────────────────┘
```

Incident OS is not injected into customer application processes.

Incident OS does not require arbitrary inbound access to customer
production.

Customer production sends telemetry outward through an explicit
integration.

Infrastructure connectors are separately authorized and read-only.

------------------------------------------------------------------------

# 3. TWO OPERATING MODES

The product has exactly two environments for the hackathon.

## A. Demo Production Mode

A real distributed production simulator.

Components:

``` text
Gateway
Auth
Orders
Payments
Inventory
Notifications
PostgreSQL
Redis
Kafka
OpenTelemetry
```

The simulator emits real telemetry.

Chaos scenarios operate against this environment.

Incident OS consumes the telemetry through the Integration Layer.

------------------------------------------------------------------------

## B. External Production Integration Mode

Represents a real customer system.

Integration methods:

``` text
OpenTelemetry
Git/deployment metadata
Read-only PostgreSQL connector
Read-only Redis connector
Read-only Kafka connector
```

The external system remains outside Incident OS.

No production write access is required for the MVP.

------------------------------------------------------------------------

# 4. INTEGRATION LAYER

The Integration Layer is mandatory.

Initial components:

``` text
otel-ingestor
github-connector
deployment-connector
postgres-connector
redis-connector
kafka-connector
```

Every connector normalizes source data into Incident OS evidence.

Example:

``` text
Vendor Source
      ↓
Connector
      ↓
Normalized Evidence
      ↓
Evidence Store
```

The investigation engine consumes normalized evidence.

The investigation engine must not contain vendor-specific API logic.

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

Live mode:

``` text
LivePostgresSource
LiveRedisSource
LiveKafkaSource
LiveTelemetrySource
```

Replay mode:

``` text
FixturePostgresSource
FixtureRedisSource
FixtureKafkaSource
FixtureTelemetrySource
```

Both modes return the same normalized Evidence contract.

------------------------------------------------------------------------

# 5. OPEN TELEMETRY

OpenTelemetry is the primary telemetry integration.

The demo production system emits:

-   logs
-   metrics
-   traces

The telemetry path is:

``` text
Application
   ↓
OpenTelemetry
   ↓
Collector / ingestion boundary
   ↓
Incident OS
```

Telemetry must include correlation information where available:

``` text
timestamp
service.name
trace_id
span_id
severity
incident correlation
```

Do not fabricate telemetry for the main end-to-end demo.

Deterministic incident detection consumes this telemetry.

------------------------------------------------------------------------

# 6. DEMO PRODUCTION SYSTEM

Build a small distributed system.

Services:

``` text
gateway
auth
orders
payments
inventory
notifications
```

Infrastructure:

``` text
PostgreSQL
Redis
Kafka
```

Every service must have:

``` text
health endpoint
structured logs
metrics
traces
```

At least one service must:

-   write to PostgreSQL
-   read/write Redis
-   publish or consume Kafka messages

The system must have real dependency relationships so failures propagate
naturally.

------------------------------------------------------------------------

# 7. CHAOS LAB

Chaos Lab controls only the isolated demo production system.

Chaos Lab is responsible only for causing the failure.

Chaos Lab MUST NOT directly create the Incident OS incident record.

Incident creation happens through deterministic incident detection.

Initial scenarios:

## Redis Failure

Action:

Stop or make Redis unavailable to the demo system.

Expected symptoms:

``` text
Redis errors
cache misses
latency increase
possible DB load increase
application failures
```

------------------------------------------------------------------------

## Slow PostgreSQL

Action:

Inject controlled query latency.

Expected:

``` text
DB latency increase
request latency increase
timeouts
```

------------------------------------------------------------------------

## PostgreSQL Deadlock

Action:

Create a deterministic deadlock in the demo environment.

Expected:

``` text
transaction failures
request errors
```

------------------------------------------------------------------------

## Kafka Consumer Lag

Action:

Stop or delay a demo consumer.

Expected:

``` text
consumer lag
message backlog
stale downstream state
```

------------------------------------------------------------------------

## Kafka Consumer Crash

Action:

Crash a demo consumer.

Expected:

``` text
consumer stopped
lag increases
downstream processing stops
```

------------------------------------------------------------------------

## Memory Leak

Action:

Make one demo service retain allocated memory.

Expected:

``` text
memory usage increases
service degradation
```

------------------------------------------------------------------------

## CPU Saturation

Action:

Generate controlled CPU load in one demo service.

Expected:

``` text
CPU increase
latency increase
```

------------------------------------------------------------------------

## Bad Deployment

Action:

Deploy a deliberately broken version.

Example:

``` text
Redis timeout:
500ms → 50ms
```

Expected:

``` text
deployment event
configuration/code change
Redis-related failures
payment latency
HTTP 5xx
```

This scenario is required for the final demo because it demonstrates
deployment-to-incident correlation.

------------------------------------------------------------------------

## Incident Detection

Chaos Lab causes the failure.

Deterministic incident detection creates the incident.

Initial detection rules:

- HTTP 5xx rate exceeds a configured threshold for a service.
- p95 latency exceeds a configured threshold for a service.
- Redis error rate exceeds a configured threshold.
- Kafka consumer lag exceeds a configured threshold.
- a deployment followed by configured error/latency thresholds within a
  defined time window.

Rules are configurable and stored as application configuration or
database records.

Do NOT use ML anomaly detection for the initial detector.

Do NOT make the LLM responsible for detecting incidents.

Manual incident creation is a development/debugging endpoint only.

------------------------------------------------------------------------

# 8. CHAOS SCENARIO CONTRACT

Every scenario contains:

``` text
scenario.yaml
injector
expected.json
```

Example:

``` yaml
name: bad_payment_deployment

target_service: payments

injection:
  type: deployment
  change: redis_timeout
  from: 500ms
  to: 50ms

expected:
  affected_services:
    - payments

  root_cause:
    component: redis
    relationship: timeout_configuration

  evidence:
    - deployment_event
    - timeout_configuration_change
    - redis_latency
    - payment_errors

  recommendation:
    action: rollback
```

The evaluator compares actual investigation results with the expected
result.

------------------------------------------------------------------------

# 9. INCIDENT API

FastAPI endpoints:

``` text
POST /api/v1/incidents
GET  /api/v1/incidents
GET  /api/v1/incidents/{id}

POST /api/v1/incidents/{id}/investigate

GET /api/v1/investigations/{id}
GET /api/v1/investigations/{id}/evidence
GET /api/v1/investigations/{id}/hypotheses
GET /api/v1/investigations/{id}/timeline
GET /api/v1/investigations/{id}/recommendations

POST /api/v1/replays
GET  /api/v1/replays/{id}

GET  /api/v1/chaos/scenarios
POST /api/v1/chaos/scenarios/{id}/run
```

All APIs use:

``` text
/api/v1
```

All request/response contracts use Pydantic schemas.

Manual incident creation is a development/debugging endpoint.

The primary production/demo path creates incidents through deterministic
detection of ingested telemetry.

------------------------------------------------------------------------

# 10. DATABASE

PostgreSQL tables:

``` text
users
projects
services
incidents
investigations
investigation_steps
evidence
hypotheses
verifications
recommendations
deployments
commits
timeline_events
chaos_scenarios
replays
worker_runs
```

Evidence must preserve provenance.

Minimum evidence metadata:

``` text
id
incident_id
investigation_id
source
service
timestamp
type
payload/reference
collector_run_id
```

Use Alembic migrations.

The investigation_steps table records explicit collection steps.

Required fields:

``` text
id
investigation_id
step_type
status
attempt
started_at
completed_at
error
created_at
updated_at
```

Valid statuses:

``` text
PENDING
RUNNING
COMPLETED
FAILED
```

Duplicate Kafka delivery must not create duplicate logical steps.

Retries increment attempt and do not create a new logical step.

PostgreSQL is the authoritative investigation workflow state.

Detection rules are stored as application configuration or in a
detection_rules database record.

------------------------------------------------------------------------

# 11. KAFKA

Kafka topics:

``` text
incident.created
investigation.started

evidence.logs.requested
evidence.metrics.requested
evidence.traces.requested
evidence.database.requested
evidence.redis.requested
evidence.kafka.requested
evidence.deployment.requested
evidence.git.requested

evidence.collected

hypothesis.created
hypothesis.verification.requested
hypothesis.verified

recommendation.created

investigation.completed
investigation.failed

replay.requested
replay.completed
```

Events must include:

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

Consumers must tolerate duplicates.

Kafka is required.

The deployed application uses Zerops-managed Kafka as the event
backbone.

Do NOT replace Kafka with Redis queues.

Kafka client configuration uses the actual credentials and connection
details provided by Zerops.

Do NOT invent Zerops Kafka hostnames, ports, credentials, CLI commands,
or security configuration.

Required concepts:

``` text
topics
producers
consumers
consumer groups
retries
duplicate handling
dead-letter handling
```

Before declaring Kafka integration complete, verify an actual deployed
connection.

Verification must prove:

1.  FastAPI can publish an event.
2.  the Worker Pool can consume the event.
3.  consumer groups function correctly.
4.  authentication works.
5.  multiple messages can be processed.
6.  duplicate delivery does not corrupt investigation state.
7.  failed processing can retry.
8.  unrecoverable messages reach the defined failure/dead-letter path.
9.  the connection uses the security configuration actually supported by
    the deployed Zerops Kafka service.

Do not claim Kafka integration works until these tests have been
executed.

Isolate the Kafka abstraction behind an internal event interface.

Business logic MUST NOT depend directly on the Kafka client
implementation.

------------------------------------------------------------------------

# 12. INVESTIGATION ORCHESTRATOR

Flow:

``` text
POST /investigate
       ↓
Create investigation
       ↓
Create expected investigation steps
       ↓
Publish evidence requests
       ↓
Workers execute independently
       ↓
Evidence stored / steps updated
       ↓
Required steps reach terminal state
       ↓
Correlation triggered
       ↓
Candidate root causes generated
       ↓
Deterministic verification
       ↓
Root cause selected
       ↓
Recommendation generated
       ↓
Investigation READY
```

Do not block the HTTP request until the investigation finishes.

The orchestrator knows exactly which evidence collection steps belong
to an investigation.

The orchestrator must NOT trigger correlation merely because one worker
completed.

Correlation is triggered only when the required collection steps reach
terminal state according to the investigation policy.

COMPLETED steps count as successful evidence collection.

FAILED steps are terminal failures.

Correlation records which evidence sources failed.

Never silently pretend failed collection succeeded.

PostgreSQL is the authoritative workflow state.

------------------------------------------------------------------------

# 13. EVIDENCE WORKERS

Workers:

``` text
Log Worker
Metrics Worker
Trace Worker
PostgreSQL Worker
Redis Worker
Kafka Worker
Deployment Worker
Git Worker
```

Each worker:

``` text
consume event
    ↓
collect data
    ↓
normalize evidence
    ↓
persist evidence
    ↓
publish completion
```

Worker failures must be retryable.

Duplicate events must not create duplicate logical evidence.

Each worker updates only its own investigation step.

Kafka duplicate delivery must not create duplicate logical steps.

Retries increment attempt and do not create a new logical step.

Workers execute inside the Worker Pool process.

------------------------------------------------------------------------

# 14. CORRELATION ENGINE

Correlation is deterministic before AI.

Use:

``` text
time relationships
service relationships
trace relationships
deployment relationships
commit relationships
dependency relationships
error relationships
```

Example:

``` text
Deployment at T1
      ↓
Configuration change at T1
      ↓
Redis latency at T2
      ↓
Payment timeout at T3
      ↓
HTTP 5xx at T4
```

The correlation engine produces candidate evidence chains.

Correlation runs only after the required collection steps reach
terminal state.

Correlation produces candidate root causes.

The candidate root causes are the deterministic input to verification.

------------------------------------------------------------------------

# 15. HYPOTHESIS ENGINE

Input:

``` text
incident
timeline
service graph
evidence
candidate correlations
```

Output:

``` text
hypothesis
supporting evidence
contradicting evidence
missing evidence
verification steps
```

The LLM is not allowed to invent missing information.

Candidate root causes from the deterministic correlation engine are the
primary input.

The LLM may generate additional hypotheses from structured evidence.

The LLM must not create the root cause without evidence.

------------------------------------------------------------------------

# 16. VERIFICATION ENGINE

Every important hypothesis must have independent verification.

Verification MUST be deterministic.

The verification engine executes evidence checks against the Evidence
Store and/or explicitly authorized read-only integrations.

The LLM may explain a verification result.

The LLM MUST NOT manufacture verification results.

The LLM MUST NOT be the only verification mechanism.

Example:

``` text
Hypothesis:
Redis latency caused payment failures.
```

Checks executed against actual stored evidence:

``` text
1. Did Redis latency increase during the incident window?
2. Does the payment service depend on Redis?
3. Did payment traces show Redis-related latency/errors?
4. Did payment failures overlap the Redis degradation?
5. Did PostgreSQL remain healthy or contradict this?
6. Did a deployment/configuration change occur before the failures?
```

Example result:

``` text
Redis latency: 8ms → 420ms                    PASS
Payment → Redis dependency: confirmed         PASS
Payment traces contain Redis latency          PASS
Timing overlap: confirmed                     PASS
PostgreSQL latency: normal                    SUPPORTING
Deployment changed Redis timeout: confirmed   SUPPORTING
```

The verification engine produces:

``` text
VERIFIED
CONTRADICTED
UNVERIFIED
```

A root cause must not be marked verified without supporting verification
results.

------------------------------------------------------------------------

# 17. AI FAILURE HANDLING

If the LLM:

-   times out
-   returns invalid JSON
-   exceeds token limits
-   produces unsupported claims
-   returns missing fields

the investigation does not fabricate a result.

Record:

``` text
AI_ERROR
```

Retry only according to an explicit retry policy.

If retries fail:

``` text
Investigation completed with AI analysis unavailable.
```

Deterministic evidence and correlation remain available.

The deterministic pipeline can produce a root-cause candidate without
the LLM.

Required flow:

``` text
Telemetry
→ Evidence
→ Deterministic Correlation
→ Candidate Root Causes
→ Deterministic Verification
→ Root Cause
```

The LLM operates on top of this pipeline.

The LLM is responsible for:

``` text
explaining evidence
synthesizing findings
generating additional hypotheses
producing readable investigation reports
```

The LLM is NOT responsible for:

``` text
inventing evidence
deciding whether telemetry exists
directly querying arbitrary production systems
fabricating verification
creating a root cause without evidence
```

If the LLM is unavailable:

``` text
the investigation continues
deterministic correlation continues
deterministic verification continues
the final result is generated from verified evidence
the AI explanation is marked UNAVAILABLE
```

This is a valid investigation result.

------------------------------------------------------------------------

# 18. REDIS

Redis stores:

``` text
investigation progress
live state
rate limits
cache
pub/sub
```

Example keys:

``` text
incident:{id}:progress
investigation:{id}:state
rate:{subject}:{window}
```

All temporary state has appropriate TTLs.

Redis MUST NOT be the authoritative investigation completion state.

PostgreSQL is the authoritative workflow state.

Redis may be used for fast progress reporting only.

------------------------------------------------------------------------

# 19. LIVE UI

The frontend must show investigation progress without manual refresh.

Use SSE or WebSockets.

Flow:

``` text
Worker
  ↓
Progress event
  ↓
Redis/live state
  ↓
FastAPI stream
  ↓
Next.js
```

Display:

``` text
Logs          ✓
Metrics       ✓
Traces        ✓
PostgreSQL    ✓
Redis         ✓
Kafka         ...
Correlation   ...
Verification  ...
```

------------------------------------------------------------------------

# 20. FRONTEND

Next.js pages:

``` text
/dashboard
/incidents
/incidents/[id]
/investigations/[id]
/replays
/chaos
/integrations
```

Investigation page must display:

``` text
incident
severity
affected services
timeline
evidence
service graph
hypotheses
verification
root cause
recommendation
replay
```

The investigation UI is the main product interface.

------------------------------------------------------------------------

# 21. INTEGRATIONS UI

The integrations page must clearly separate:

## Telemetry

``` text
OpenTelemetry
```

## Source Connectors

``` text
Git
Deployment
PostgreSQL
Redis
Kafka
```

Each connector must display:

``` text
connected
disconnected
error
last successful collection
permission scope
```

Never display secrets.

------------------------------------------------------------------------

# 22. SECURITY MODEL

Production integration is read-only.

Customer credentials:

``` text
never in frontend
never in logs
never in AI prompts
never in Kafka
never in evidence payloads
never in Git
```

Credentials use secret/configuration management.

Connectors must have minimal required privileges.

------------------------------------------------------------------------

# 23. ZEROPS DEPLOYMENT

Incident OS is deployed to Zerops.

Deploy:

``` text
Next.js
FastAPI
Investigation Workers
PostgreSQL
Redis
Kafka
```

Only use services/capabilities actually supported by current Zerops
documentation.

Before implementation of Zerops-specific deployment automation:

-   verify current Zerops documentation
-   verify CLI/API syntax
-   verify networking behavior
-   verify service availability
-   verify scaling behavior

Do not encode unverified Zerops assumptions into the architecture.

The demo must show the actual deployed system.

Initial deployment shape (approximately five application processes):

``` text
1. Next.js
2. FastAPI API
3. Worker Pool
4. Investigation/Correlation/Verification Process
5. Replay/Chaos Controller
```

Logical workers execute inside the Worker Pool unless a later verified
scaling requirement justifies separation.

Do NOT create separate deployment services merely to enlarge the
architecture diagram.

A deployment boundary requires a real operational reason: independent
scaling, independent deployment, independent failure isolation, or
security isolation.

Zerops-managed Kafka is the event backbone.

------------------------------------------------------------------------

# 24. REPLAY

Replay is isolated.

Input:

``` text
incident
timeline
telemetry fixtures
topology
deployment metadata
scenario
```

Flow:

``` text
Replay request
     ↓
Create isolated replay session
     ↓
Load incident context
     ↓
Run investigation
     ↓
Compare result
```

Replay must not modify customer production.

Replay uses the same connector contract as production.

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

Both modes return the same normalized Evidence contract.

The investigation engine must not know whether evidence came from
production or replay fixtures.

Fixture sources:

``` text
FixturePostgresSource
FixtureRedisSource
FixtureKafkaSource
FixtureTelemetrySource
```

Replay does not touch production.

------------------------------------------------------------------------

# 25. TESTING

## Unit Tests

Required for:

- Pydantic schemas
- parsers
- incident detection rules
- investigation step state transitions
- correlation rules
- hypothesis scoring
- state transitions
- domain services

## Integration Tests

Required for:

``` text
FastAPI ↔ PostgreSQL
FastAPI ↔ Redis
FastAPI ↔ Kafka
Worker ↔ Kafka
Worker ↔ PostgreSQL
Worker ↔ Redis
Detection rules ↔ ingested telemetry
Orchestrator ↔ step completion
```

## End-to-End Tests

Every major chaos scenario must execute:

``` text
inject
→ real application failure
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

## End-to-End Tests

Every major chaos scenario must execute:

``` text
inject
→ real application failure
→ telemetry
→ ingestion
→ investigation
→ evidence
→ correlation
→ verification
→ result
```

------------------------------------------------------------------------

# 26. EVALUATION

For every deterministic scenario calculate:

``` text
incident_detection_accuracy
incident_detection_latency
root_cause_accuracy
affected_service_accuracy
evidence_accuracy
recommendation_accuracy
hallucination_rate
investigation_duration
```

Expected results come from `expected.json`.

The evaluator must distinguish:

``` text
correct
incorrect
unsupported
unverified
```

------------------------------------------------------------------------

# 27. DEVELOPMENT PHASES

Implement in this order.

Do not implement the LLM first.

Do not implement replay after tightly coupling the investigation engine
to live infrastructure.

Do not implement Kafka using unverified Zerops configuration.

## Prerequisites

The demo production system, telemetry ingestion, and local
infrastructure (PostgreSQL, Redis, Kafka) described earlier in this plan
are the foundation for the phases below.

## Phase 1 --- Incident Detection

Implement deterministic incident detection rules on ingested telemetry.

Deliverable:

Real failure produces telemetry and a deterministic rule creates the
incident automatically.

## Phase 2 --- Investigation Step State Machine

Implement investigation_steps.

Deliverable:

All expected steps are tracked; retries work; duplicate events do not
duplicate logical work; correlation does not run prematurely.

## Phase 3 --- EvidenceSource Abstraction

Define the internal evidence-source interface before live connectors.

Deliverable:

The investigation engine depends on EvidenceSource, not on concrete
infrastructure clients.

## Phase 4 --- Deterministic Correlation Engine

Deliverable:

Correlation runs only after required steps reach terminal state and
produces candidate root causes.

## Phase 5 --- Deterministic Verification Engine

Deliverable:

Verification executes deterministic checks against stored evidence and
returns VERIFIED/CONTRADICTED/UNVERIFIED.

## Phase 6 --- Deterministic Fallback Root-Cause Engine

Deliverable:

The deterministic pipeline produces a root-cause candidate without the
LLM.

## Phase 7 --- Kafka Integration on Zerops

Deliverable:

Verified Zerops-managed Kafka connection: producer, consumer, consumer
group, retries, duplicate safety, and failure/dead-letter path.

## Phase 8 --- LLM Integration

Deliverable:

LLM explains evidence, synthesizes findings, and generates additional
hypotheses on top of the deterministic pipeline. LLM failure does not
destroy the investigation.

## Phase 9 --- Replay with Fixture EvidenceSources

Deliverable:

Fixture connectors implement the same EvidenceSource contract and reach
the same investigation engine.

## Phase 10 --- End-to-End Chaos Scenarios

Deliverable:

Chaos injection → real failure → telemetry → incident detection →
investigation → evidence → correlation → verification → root cause →
recommendation → replay.

The investigation UI and self-observability are developed in parallel
where they do not conflict with these phases.

------------------------------------------------------------------------

# 28. FINAL DEMO

The final demo uses the real demo production system.

Sequence:

``` text
1.  Show service topology.

2.  Show healthy application.

3.  Deploy bad Payments version.

4.  Show application operating normally.

5.  Trigger the failure.

6.  Show real telemetry changing.

7.  Show deterministic detection firing and the incident being created
    automatically.

8.  Open Incident OS.

9.  Start investigation.

10. Show parallel workers.

11. Show evidence arriving.

12. Show step completion tracking.

13. Show correlation chain and candidate root causes.

14. Show deterministic verification.

15. Show verified root cause.

16. Show recommendation.

17. Replay incident.

18. Show deployed Incident OS architecture on Zerops.
```

The demo must not depend on manually inserting the final answer into the
database.

The demo must not depend on manually creating the incident.

------------------------------------------------------------------------

# 29. FEATURES NOT IN MVP

The following are explicitly outside the MVP:

``` text
automatic production remediation
arbitrary shell execution
full Kubernetes control
full distributed database snapshotting
automatic production chaos injection
unrestricted customer infrastructure access
generic chatbot
billing
complex RBAC
mobile application
```

These must not be implemented before P0 is complete.

------------------------------------------------------------------------

# 30. P0 DEFINITION OF DONE

The project is P0-complete only when:

``` text
A real demo production system can fail.

The failure produces real telemetry.

Incident OS receives that telemetry through its integration boundary.

Deterministic detection creates the incident from that telemetry.

An investigation can be started.

Expected investigation steps are created and tracked.

Multiple evidence workers execute.

Correlation runs only after required steps reach terminal state.

Evidence is persisted.

Deterministic verification returns VERIFIED/CONTRADICTED/UNVERIFIED.

At least one hypothesis is independently verified.

The root cause is shown with supporting evidence.

A recommendation is produced.

The entire investigation is visible in Next.js.

The incident can be replayed through the same EvidenceSource contract.

The complete system is deployed and verified on Zerops.
```

------------------------------------------------------------------------

# 31. HARD STOP CONDITIONS

Stop implementation and ask the user if:

-   a production connector requires unknown permissions
-   a destructive production action is requested
-   Zerops behavior is undocumented/unverified
-   a database migration may destroy data
-   an API contract has conflicting consumers
-   a requested feature contradicts `AGENT.md`
-   the implementation would require inventing missing information
-   a security boundary would be weakened
-   the proposed change materially changes the architecture

Do not continue through these conditions by assumption.

------------------------------------------------------------------------

# 32. FINAL RULE

This project is built on one principle:

``` text
OBSERVE
→ COLLECT
→ CORRELATE
→ VERIFY
→ EXPLAIN
```

Not:

``` text
GUESS
→ GENERATE
→ CLAIM
```

Every important production conclusion must have evidence.

Every external integration must have an explicit contract.

Every security-sensitive action must have an explicit boundary.

Every unverified capability must remain unverified until tested.

Every implementation must be tested before it is declared complete.

------------------------------------------------------------------------

# 33. REQUIRED VERIFICATION BEFORE CLAIMING COMPLETION

Do not describe the system as production-ready for the hackathon demo
until these checks pass.

## Incident Detection

``` text
failure produces telemetry
telemetry triggers a deterministic rule
the incident is automatically created
```

## Investigation Coordination

``` text
all expected steps are tracked
retries work
duplicate events do not duplicate logical work
correlation does not run prematurely
```

## Verification

``` text
verification executes deterministic checks
verification uses real evidence
verification can return VERIFIED/CONTRADICTED/UNVERIFIED
```

## Kafka

``` text
the Zerops Kafka connection works
producer works
consumer works
consumer group works
retry works
duplicate processing is safe
the failure path works
```

## LLM

``` text
LLM unavailable does not destroy the investigation
malformed LLM output is rejected
the deterministic root cause remains available
```

## Replay

``` text
fixture connectors implement the same EvidenceSource contract
replay reaches the same investigation engine
replay does not touch production
```

## End-to-End

``` text
chaos injection
real application failure
real telemetry
incident detection
investigation
evidence collection
correlation
verification
root cause
recommendation
replay
```

Only after these checks pass should the system be described as
production-ready for the hackathon demo.
