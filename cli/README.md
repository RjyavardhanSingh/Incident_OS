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
```

Incident ids may be abbreviated to a unique prefix.

Add `--json` anywhere to get raw JSON instead of tables.

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
