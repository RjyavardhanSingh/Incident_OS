# incident-os CLI

Thin command-line interface for Incident OS. Emit OpenTelemetry, browse
incidents, and run investigations against an Incident OS API instance.

## Install

```sh
pip install -e ./cli
```

Requires Python 3.10+. Read-only commands use only the standard library; the
`emit` and `demo` commands pull in the OpenTelemetry SDK on demand.

## Configure

The API base URL comes from `--url` or the `INCIDENT_OS_URL` environment
variable (default `http://localhost:8000`).

```sh
export INCIDENT_OS_URL=https://api-2d4e-8000.prg1.zerops.app
```

## Usage

```sh
incident-os health

incident-os incidents list [--service gateway] [--status OPEN] [--limit 100]
incident-os incidents show <id>
incident-os incidents investigate <id>
incident-os incidents resolve <id>

incident-os investigation status <id> [--watch]
incident-os investigation evidence <id>
incident-os investigation candidates <id>
incident-os investigation root-cause <id>

incident-os emit [--profile all|http|kafka|redis|trace]
incident-os demo [--profile all] [--wait 480]
incident-os lab [--port 8080]      # web chaos lab dashboard
incident-os tui [--refresh 10]     # interactive terminal dashboard
```

Incident ids may be abbreviated to a unique prefix.

Add `--json` anywhere to get raw JSON instead of tables.

## Web chaos lab

`incident-os lab` starts a local dashboard (default http://127.0.0.1:8080)
with chaos buttons, a live incident list, and an investigation panel. It
proxies the Incident OS API locally, so it works with any
`INCIDENT_OS_URL` and needs no CORS setup.

```sh
INCIDENT_OS_URL=https://api-2d4e-8000.prg1.zerops.app incident-os lab
```

Then open http://127.0.0.1:8080 and use the chaos buttons to emit failure
telemetry, click an incident to investigate, and watch the investigation
run through to the root cause. The CLI remains the primary interface;
the lab is a demo/dashboard view.

## Terminal dashboard (TUI)

`incident-os tui` is the full-screen terminal interface. It needs the
`textual` package (installed with the CLI):

```sh
INCIDENT_OS_URL=https://api-2d4e-8000.prg1.zerops.app incident-os tui
```

Layout and keys:

- left: incident list (open and resolved), right: incident detail and
  investigation panes; auto-refreshes every `--refresh` seconds
- `up`/`down` move the row cursor and preview the incident detail
- `i` start an investigation on the selected incident (live step polling)
- `v` replay a completed investigation to its root cause
- `x` resolve the selected open incident
- `a h k d t` emit all / http / kafka / redis / trace telemetry
- `r` refresh, `q` quit

## Plug your own service into Incident OS

`incident_os_cli.client` is a small integration client. It sends your
service's telemetry to Incident OS over standard OpenTelemetry (OTLP over
HTTPS) - Incident OS only *reads* telemetry, it never runs inside or
touches your production system.

```python
import os
from incident_os_cli import client

incidentos = client.install(
    service=os.environ["SERVICE_NAME"],
    endpoint=os.environ["INCIDENT_OS_URL"],
)

# your app code
incidentos.http(status_code=502, duration_ms=1230, method="POST", route="/api/v1/checkout")
incidentos.kafka_lag(topic="orders", lag=2000)          # consumer lag
incidentos.redis_error("redis connection timeout attempt=1")
```

Each call feeds a detection rule:

| call                            | rule / signal                          |
|---------------------------------|----------------------------------------|
| `http(status, ms)`              | 5xx rate / p95 latency metric          |
| `kafka_lag(topic, n)`           | consumer lag metric                    |
| `redis_error("connection timeout")` | error log                            |
| `trace_error(name)`             | failing span                           |

Wrap framework-specific hooks once: a FastAPI/Flask middleware around
`http()`, your kafka consumer loop around `kafka_lag()`, and your redis
client's error path around `redis_error()`. No dependency on the CLI's
network layout - `client.install()` configures the same
`OTEL_EXPORTER_OTLP_ENDPOINT`/`OTEL_EXPORTER_OTLP_PROTOCOL` environment
variables any OpenTelemetry app uses, so standard OTel auto-instrumentation
libraries also work against it unchanged.

## Production integration

To wire any real service into Incident OS:

1. **Keep it outbound-only.** The service only exports telemetry over
   TLS to `https://<incident-os>/api/v1/otlp`. Incident OS never gets
   credentials, file access, or write access to your system - it consumes
   the same signals a normal observability backend would.
2. **Configure by environment.** In your deployment set `INCIDENT_OS_URL`
   (and per-service `SERVICE_NAME`), then call `client.install()` at
   process start. Rotating the endpoint is a config change, not a deploy.
3. **Instrument at the framework boundary.** One middleware for HTTP,
   one wrapper for your queue consumer, one hook in the redis error path.
   These are the same 3-4 call sites in any codebase.
4. **Add it to CI/health checks.** `incident-os health` works as a
   readiness check; monitoring the platform is read-only and does not
   require installing anything into production.

The same pattern applies in any language - the platform only consumes
standard OTLP (HTTP/Protobuf): send `http.server.request.duration` as a
histogram with `http.status_code` attributes, a `kafka.consumer.lag`
gauge with a `topic` attribute, error-level logs containing redis
"connection timeout", or a span tagged with HTTP status 500.

## End-to-end demo

```sh
incident-os demo
```

This runs the whole workflow in one command:

1. emit failure telemetry over OTLP
2. watch for new incidents
3. start an investigation on the newest incident
4. watch it through COLLECTING -> ANALYZING -> READY
5. print the selected root cause

Rules dedupe on open incidents, so a rule only fires again after its open
incident is resolved. Reset the loop with:

```sh
incident-os incidents list --status OPEN
incident-os incidents resolve <id>
```
