# Incident OS

**From chaos telemetry to root cause in one command.**

Incident OS watches your services' OpenTelemetry telemetry, detects incidents
the moment they start, and then *automatically investigates* — gathering
evidence across services until it can name a verified root cause with a
confidence score.

Built for the **We Make Devs × Zerops Challenge**. The API and the
investigation worker run in the cloud on **Zerops**; the interface is
deliberately a local terminal CLI, a full-screen TUI, and a local web chaos
lab — no CORS hacks, no dashboard-only API endpoints.

> **Live deployment:** https://api-2d4e-8000.prg1.zerops.app
> **Interactive API docs (Swagger):** https://api-2d4e-8000.prg1.zerops.app/docs

---

## The loop

1. **Ingest** — services emit standard OpenTelemetry (OTLP HTTP/Protobuf):
   metrics, logs, and traces. No agents, no proprietary SDKs.
2. **Detect** — detection rules watch sliding windows: 5xx rate, p95 latency,
   Kafka consumer lag, Redis error logs, failing traces. Rules dedupe against
   open incidents, so the same failure doesn't spam new incidents every minute.
3. **Investigate** — a Kafka-backed worker pulls seven evidence sources
   (database, deployment, Kafka, logs, metrics, Redis, traces) and scores
   root-cause candidates, each with a confidence figure.
4. **Verify** — candidates that pass deterministic verification are selected,
   and the root cause is reported with its evidence chain.

## Architecture

```
            ┌─────────────── your services ───────────────┐
            │  OTel SDK / incident_os_cli.client           │
            └───────────────┬─────────────────────────────┘
                            │ OTLP (HTTP/Protobuf, TLS)
                            ▼
            ┌───────────────────────────────┐
            │  API (FastAPI, Zerops)        │
            │  POST /api/v1/otlp            │
            │  detection rules + dedupe     │
            │  REST API for incidents,      │
            │  investigations, root cause   │
            └───────┬───────────────┬───────┘
                    │ writes        │ events
                    ▼               ▼
            ┌──────────────┐  ┌──────────────┐
            │  PostgreSQL  │  │  Kafka       │  (managed on Zerops)
            │  (Zerops)    │  │  (Zerops)    │
            └──────────────┘  └──────┬───────┘
                                    │ consume
                                    ▼
            ┌───────────────────────────────┐
            │  Investigation worker (Zerops)│
            │  evidence -> candidates ->    │
            │  verification -> root cause   │
            └───────────────────────────────┘

            Clients (your machine, intentional):
              incident-os CLI   incident-os tui   incident-os lab (web)
```

## Repository layout

```
backend/   FastAPI API, detection engine, investigation worker, sources
cli/       incident-os CLI + terminal dashboard + local web chaos lab
infra/     local docker-compose for Kafka + Redis, Zerops import blueprint
simulator/ fault telemetry generators
docs/      demo video script
```

---

## Quick start (terminal)

You need Python 3.10+ and `uv` (or pip).

```sh
git clone ssh://git@github.com/RjyavardhanSingh/Incident_OS.git
cd Incident_OS

# one-time install of the CLI (editable, tracks the repo)
uv tool install --editable ./cli

# point at the live cloud deployment
export INCIDENT_OS_URL=https://api-2d4e-8000.prg1.zerops.app

incident-os health
incident-os incidents list
```

### Full workflow in one command

```sh
incident-os demo
```

Emit failure telemetry → wait for detection → start an investigation → watch it
through to a verified root cause.

### Individual commands

```sh
incident-os health                          # API + database status

incident-os incidents list [--service gateway] [--status OPEN]
incident-os incidents show <id>
incident-os incidents investigate <id>
incident-os incidents resolve <id>          # clears dedupe for a re-run
incident-os incidents investigations <id>

incident-os investigation status <id> [--watch]
incident-os investigation evidence <id>
incident-os investigation candidates <id>
incident-os investigation root-cause <id>

incident-os emit [--profile all|http|kafka|redis|trace]
incident-os tui [--refresh 10]              # full-screen terminal dashboard
incident-os lab [--port 8080]               # web chaos lab
```

Incident IDs may be abbreviated to a unique prefix. Add `--json` anywhere for
raw JSON output.

### Terminal dashboard (TUI)

```sh
INCIDENT_OS_URL=https://api-2d4e-8000.prg1.zerops.app incident-os tui
```

- `up` / `down` — move through incidents and preview detail
- `i` — start an investigation (live step polling to root cause)
- `v` — replay a finished investigation
- `x` — resolve the selected open incident
- `a h k d t` — emit all / HTTP / Kafka / Redis / trace chaos
- `r` refresh, `q` quit

---

## Web chaos lab

The web interface is intentionally a **local** dashboard (`incident-os lab`)
that proxies your `INCIDENT_OS_URL` — it works with the cloud deployment and
needs no CORS configuration.

```sh
INCIDENT_OS_URL=https://api-2d4e-8000.prg1.zerops.app incident-os lab
# open http://127.0.0.1:8080
```

What it gives you:

- **Chaos buttons** — emit failure telemetry (full failure / HTTP / Kafka /
  Redis / trace) without touching a terminal.
- **Live incident table** — open incidents on top, history below, auto-refresh
  every 10s.
- **Investigate on click** — watch the seven evidence steps complete.
- **Root-cause card** — the verified cause, confidence, and evidence chain.
- **Replay** — animated timeline replay of any resolved incident's
  investigation.
- **Resolve all** — clear open incidents to reset the dedupe loop.

---

## Run it yourself (local backend)

### 1. Local infrastructure

Redis and Kafka run via docker compose; PostgreSQL runs on port `5433`
(the dev default in `backend/app/core/config.py`).

```sh
docker compose -f infra/docker-compose.yml up -d
```

### 2. Backend

```sh
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env     # or set DATABASE_URL/KAFKA_BOOTSTRAP_SERVERS
alembic -c alembic.ini upgrade head

# API
uvicorn app.main:app --port 8000

# investigation worker (second terminal)
python -m app.worker
```

Local defaults: `postgresql+psycopg://incident_os:incident_os_dev@localhost:5433/incident_os_dev`,
Kafka `localhost:9092` (PLAINTEXT), Redis `redis://localhost:6379/0`.

### 3. Tests

```sh
cd backend && pytest
```

---

## Deploy to Zerops

The whole stack — API, investigation worker, managed Kafka, PostgreSQL, and
Redis — is declared in `zerops.yaml`. Deployment is a git push.

```yaml
# zerops.yaml (abridged) — see the repo for the full file
zerops:
  - setup: api
    build:
      base: ubuntu/python@3.12
      buildCommands:
        - python -m pip install --upgrade --no-cache-dir --target=./vendor ./backend
    run:
      base: ubuntu/python@3.12
      initCommands:
        - zsc execOnce ${appVersionId} --retryUntilSuccessful -- python -m alembic -c /var/www/backend/alembic.ini upgrade head
      start: python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
      ports:
        - port: 8000
          httpSupport: true
      envVariables:
        PYTHONPATH: /var/www/vendor

  - setup: worker
    build: ...same build...
    run:
      base: ubuntu/python@3.12
      start: python -m app.worker
```

Highlights:

- **Managed services** — Kafka (SASL/PLAIN auth), PostgreSQL, and Redis are
  provisioned by Zerops; credentials are injected as environment refs.
- **One-time migrations** — `zsc execOnce` runs Alembic exactly once per
  deployed app version.
- **Readiness** — `/api/v1/health` gates traffic to the service.
- **Vendored deps + cache** — build deps install into `vendor/` with caching
  for fast, reproducible builds.

---

## Integrations with live projects — coming soon

Incident OS is built to plug into *any* codebase that emits standard
OpenTelemetry. The integration client (`incident_os_cli.client`) is already
shipped — one call wires a service up:

```python
import os
from incident_os_cli import client

incidentos = client.install(
    service=os.environ["SERVICE_NAME"],
    endpoint=os.environ["INCIDENT_OS_URL"],
)

incidentos.http(status_code=502, duration_ms=1230)   # 5xx rate / p95 latency
incidentos.kafka_lag(topic="orders", lag=2000)       # consumer lag
incidentos.redis_error("redis connection timeout")   # error logs
incidentos.trace_error("checkout")                   # failing span
```

**Coming soon:**

- Ready-made auto-instrumentation bundles for **FastAPI, Flask, Django,
  Express/Node, Go (net/http)** — import once, no manual call sites.
- One-line deployment agents that run alongside your service and forward
  existing OTLP exporters to Incident OS with zero code changes.
- CI/CD pipeline checks: fail a build if the last deploy correlates with an
  incident spike.
- Webhook / Slack notifications when a root cause is verified.
- GitHub Actions integration for on-demand incident replays.

Until then, any standard OTLP exporter already works — Incident OS consumes
`http.server.request.duration` histograms, `kafka.consumer.lag` gauges,
error logs containing Redis timeouts, and failing spans, exactly like any
OpenTelemetry backend.

---

## Live deployment

| Resource | URL |
|---|---|
| API base | `https://api-2d4e-8000.prg1.zerops.app` |
| Swagger docs | `https://api-2d4e-8000.prg1.zerops.app/docs` |
| Incidents feed | `https://api-2d4e-8000.prg1.zerops.app/api/v1/incidents` |

## Tech stack

- **Backend:** Python 3.12, FastAPI, SQLAlchemy, Alembic, pydantic-settings
- **Investigation worker:** Python + confluent-kafka consumer
- **Telemetry:** OpenTelemetry SDK + OTLP HTTP/Protobuf
- **Data plane:** PostgreSQL, Redis, Kafka (managed on Zerops)
- **Interface:** Python CLI (stdlib HTTP), Textual TUI, stdlib HTTP-server
  web chaos lab
- **Cloud:** Zerops — `zerops.yaml` declarative deployment, managed services
