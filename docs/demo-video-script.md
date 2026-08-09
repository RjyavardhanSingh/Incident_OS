# Incident OS — Demo Video Script

Target length: ~5:30. Narrate in a calm, steady pace. Every scene shows real
screen actions against the **live cloud** deployment
(`https://api-2d4e-8000.prg1.zerops.app`) — no canned footage.

Recommended title text (start card):
**Incident OS — from chaos telemetry to root cause in one command.**

---

## Scene 0 — Problem (00:00–01:00)

**Screen:** title card, then repo overview (`ls`), no narration yet beyond intro.

**Action:**
- Title card (any video editor text, 5s).
- `cd ~/Documents/Incident_OS && ls`
- Open `PLAN.md` or `AGENT.md` briefly (just show it exists).

**Narration:**
> "In production, services fail in the same boring ways every week: a gateway
> starts returning 5xxs, latency climbs, a Kafka consumer falls behind, Redis
> starts timing out. The problem isn't that things break — it's that we find
> out *late*, and then it takes hours to trace a symptom back to a root cause.
>
> This is Incident OS: a platform that watches your OpenTelemetry telemetry,
> detects incidents the moment they start, and then *automatically investigates*
> — gathering evidence across services until it can name the root cause.
>
> Everything you're about to see runs against a real cloud deployment. Let me
> show you the stack, then the app, then the infrastructure it runs on."

---

## Scene 1 — The stack at a glance (01:00–01:30)

**Screen:** `tree -L 2` (or `ls` of `backend/`, `cli/`, `infra/`).

**Action:**
- `tree -L 2 -I .git -I vendor | head -40` (or `ls backend cli infra`)

**Narration:**
> "Three parts. A FastAPI backend exposing a REST API. An investigation worker —
> a Kafka consumer that runs each investigation step. And the client side: a CLI
> with a full-screen terminal dashboard, and a web chaos lab for demos.
>
> The whole thing speaks one language: OpenTelemetry, over the OTLP HTTP
> protocol. That's the key decision — any service that emits standard
> telemetry can plug into Incident OS with almost no work."

---

## Scene 2 — The app: emit → detect (01:30–02:30)

**Screen:** terminal, CLI.

**Action (paste exactly, then wait for output):**
```sh
export INCIDENT_OS_URL=https://api-2d4e-8000.prg1.zerops.app
incident-os health
incident-os incidents list
incident-os emit --profile redis
incident-os incidents list --status OPEN
```

**Narration:**
> "First, health check. The API is live. Now, an empty incident list.
>
> I'm going to *create a failure* — not by breaking code, but by emitting the
> telemetry a broken service would: in this case Redis connection-timeout
> error logs.
>
> Sixty seconds later, the detection engine has turned raw telemetry into an
> incident. Each signal is checked by a detection rule against a sliding
> window — a spike in the 5xx rate, p95 latency crossing its threshold,
> consumer lag, error logs, failing traces. When a rule fires, it dedupes
> against open incidents, so the same incident isn't re-created every minute."

---

## Scene 3 — The app: investigate → root cause (02:30–03:45)

**Screen:** terminal / TUI, watch investigation.

**Action (TUI is the best visual here):**
```sh
incident-os tui
```
- arrow to the OPEN incident
- press `i`, watch the 7 steps poll to READY
- press `v` on a resolved incident for replay, and `q`

**Narration:**
> "Now the part that makes this different. Instead of a page and a pager,
> this starts an *investigation*. The worker pulls seven sources of evidence —
> database, deployment, Kafka, logs, metrics, Redis, traces — and scores them
> against the incident window.
>
> Evidence becomes root-cause *candidates*, each with a confidence score.
> Candidates that pass deterministic verification get selected. Here the
> engine found the cause and gives us a confidence figure and the evidence
> chain that led there.
>
> This is the full terminal dashboard: live incident list on the left,
> detail and investigation on the right. Arrow keys preview, `i` investigates,
> `v` replays a finished investigation. Same flow on the web chaos lab if a
> browser demo reads better."

---

## Scene 4 — Web chaos lab (03:45–04:15)

**Screen:** browser at `http://127.0.0.1:8080`.

**Action:**
```sh
incident-os lab
```
- click "Redis" chaos button, then "Investigate" on the new incident
- show the root-cause card

**Narration:**
> "For demos, the chaos lab gives you buttons instead of commands. Click a
> failure profile — HTTP, Kafka, Redis, trace — and watch the incident land,
> investigate it, and read the root cause. Same API, same detection, same
> investigation pipeline; this is just a friendlier face on it."

---

## Scene 5 — How Zerops helped (04:15–05:10)

**Screen:** `zerops.yaml`, then Zerops dashboard (project → services, logs).

**Action:**
- open `zerops.yaml`
- show project services list: `api`, `worker`, managed `kafka`, `postgres`, `redis`
- `zcli service log -P ... -S ... --limit 20` (worker logs) — optional

**Narration:**
> "Now, how does this actually run? Zerops does the heavy lifting.
>
> One declarative file — `zerops.yaml` — defines two services. The `api` runs
> uvicorn on port 8000 with a readiness check against `/api/v1/health`. The
> `worker` runs the investigation loop. Both are Python 3.12, dependencies
> vendored at build time, and a `zsc execOnce` init step runs database
> migrations — exactly once, on the right instance.
>
> But the clever part is the data plane. The detection rules read PostgreSQL,
> the worker consumes Kafka, and Redis keeps investigation state — and all
> three are *managed Zerops services*. I get a real Kafka cluster with SASL
> authentication and a Postgres instance without running any of that
> infrastructure myself.
>
> Deployment is a git push. No SSH, no Dockerfiles hand-rolled — push the
> branch, Zerops builds the vendored image and swaps the running service.
> Scaling, TLS, and secrets-as-environment-variables come from the platform
> config, not my code."

---

## Scene 6 — Wrap up (05:10–05:30)

**Screen:** title card again (or repo root).

**Narration:**
> "So the loop closes: OpenTelemetry in, incidents detected on detection
> rules, investigations that name a root cause with evidence and confidence —
> and a cloud platform that runs the whole thing without you operating Kafka,
> Postgres, or Redis yourself.
>
> Incident OS turns 'something is wrong, go look' into 'here is what failed,
> and why.'"

---

## Technical terms (drop these naturally, don't read the list)

- **OpenTelemetry (OTel)** — vendor-neutral standard for telemetry
  (metrics, logs, traces).
- **OTLP (HTTP/Protobuf)** — the wire protocol telemetry travels over.
- **Signal** — one of metrics / logs / traces (e.g. `http.server.request.duration`).
- **Histogram / p95 latency** — distribution of request durations; p95 = 95%
  of requests finish within X ms.
- **5xx rate** — share of HTTP responses that are server errors, per window.
- **Gauge** — a single instantaneous value, e.g. `kafka.consumer.lag`.
- **Span** — a named unit of work in a trace; a 500 span flags a failing path.
- **Detection rule / sliding window** — threshold + time window per signal.
- **Dedupe** — rules skip re-firing while the same incident is open.
- **Investigation pipeline / evidence** — the 7 steps the worker runs
  (database, deployment, kafka, logs, metrics, redis, traces).
- **Candidate / confidence / verification** — root-cause hypotheses scored,
  then deterministically verified before selection.
- **FastAPI + uvicorn** — the async Python API stack.
- **Managed Kafka (SASL/PLAIN)** — Zerops-hosted Kafka; auth handled by the
  platform, not your code.
- **`zsc execOnce`** — run a one-time init (alembic migration) once per deploy.
- **Readiness check** — `/api/v1/health` tells the platform when the service
  can take traffic.
- **Declarative deployment (`zerops.yaml`)** — infra as config, deploy via
  git push.

## Recording checklist

- Fresh incident state for a clean run: `incident-os incidents resolve <id>`
  for any OPEN incidents, or re-push the API after `incident-os incidents list --status OPEN` shows none.
- Have `INCIDENT_OS_URL` exported in every terminal.
- Wait the full 60s detection window on-screen before investigating (or
  `--wait 60` if you use `incident-os demo`).
- Record at 1080p, monospace font, generous terminal width so the TUI
  two-column layout fits.
- Mute notifications; record only the demo window.
