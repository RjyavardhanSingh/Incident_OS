import sys
import time
from datetime import datetime, timezone

from incident_os_cli.api import Api, ApiError
from incident_os_cli import output


def _poll(predicate, label, timeout_s, interval_s=5):
    deadline = time.monotonic() + timeout_s
    while True:
        value = predicate()
        if value:
            return value
        if time.monotonic() >= deadline:
            return None
        elapsed = int(timeout_s - (deadline - time.monotonic()))
        sys.stdout.write(f"\r  {label}... {elapsed}s elapsed")
        sys.stdout.flush()
        time.sleep(interval_s)


def _newest(incidents):
    return max(incidents, key=lambda i: i.get("detected_at") or "")


def _as_dt(value):
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    return datetime.min.replace(tzinfo=timezone.utc)


def run(api: Api, profile: str, wait_s: int) -> int:
    started = datetime.now(timezone.utc)
    print(f"1/5 emitting {profile!r} failure telemetry")
    from incident_os_cli.emit import emit

    emit(api.base_url + "/api/v1/otlp", profile)

    def new_incidents():
        incidents = api.list_incidents(limit=50)
        return [i for i in incidents if _as_dt(i.get("detected_at")) >= started]

    print(f"2/5 watching for new incidents (up to {wait_s}s)")
    incidents = _poll(new_incidents, "watching for incidents", wait_s)
    print()
    if incidents is None:
        print("  no new incidents detected within the wait window")
        print("  hint: rules dedupe on OPEN incidents; resolve them first, e.g.")
        print("    incident-os incidents list --status OPEN")
        print("    incident-os incidents resolve <id>")
        return 1
    print(f"  detected {len(incidents)} new incident(s)")
    output.print_table(
        ["ID", "STATUS", "SEV", "SERVICE", "RULE", "DETECTED"],
        [
            [
                output.short_id(i["id"]),
                i["status"],
                i["severity"],
                i["service"],
                i["detection_rule_name"],
                i["detected_at"][:19].replace("T", " "),
            ]
            for i in incidents
        ],
    )
    print()

    incident = _newest(incidents)
    print(f"3/5 investigating {incident['id']}")
    try:
        investigation = api.investigate(incident["id"])
    except ApiError as exc:
        print(f"  investigation failed: {exc}")
        return 1
    investigation_id = investigation["id"]
    print(f"  investigation {investigation_id} ({investigation['status']})")

    def _completed():
        inv = api.get_investigation(investigation_id)
        return inv if inv["status"] in ("READY", "FAILED") else None

    print(f"4/5 watching investigation (up to {wait_s}s)")
    done = _poll(_completed, "waiting for investigation", wait_s)
    if done is None:
        print("\n  investigation still running after the wait window")
        return 1
    print()
    print(f"  investigation status: {done['status']}")

    output.kv("steps", [])
    for step in done.get("steps", []):
        status = step["status"]
        print(f"  {step['step_type']:<28} {status:<12} attempt={step.get('attempt', 1)}")
    print()

    print("5/5 fetching root cause")
    try:
        root_cause = api.root_cause(investigation_id)
    except ApiError:
        root_cause = None
    if root_cause is None:
        print("  no root cause produced (see candidates)")
        try:
            candidates = api.candidates(investigation_id)
            for c in candidates:
                print(f"  candidate {c.get('id', '-')} {c.get('status', '-')} confidence={c.get('confidence')}")
        except ApiError as exc:
            print(f"  could not list candidates: {exc}")
        return 0

    output.kv(
        "root cause",
        [
            ("title", root_cause.get("title")),
            ("root_cause_type", root_cause.get("root_cause_type")),
            ("selection_mode", root_cause.get("selection_mode")),
            ("confidence", root_cause.get("confidence")),
            ("related_services", ", ".join(root_cause.get("related_services", []) or [])),
        ],
    )
    if root_cause.get("summary"):
        print(f"  summary: {root_cause['summary']}")
    if root_cause.get("reasoning"):
        print(f"  reasoning: {root_cause['reasoning']}")
    return 0
