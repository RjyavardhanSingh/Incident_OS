import argparse

from incident_os_cli.api import Api, ApiError, DEFAULT_URL
from incident_os_cli import demo as demo_cmd
from incident_os_cli import output
from incident_os_cli.emit import PROFILES


def _api(args):
    return Api(args.url)


def cmd_health(args):
    try:
        status = _api(args).health()
    except ApiError as exc:
        print(f"unhealthy: {exc}")
        return 1
    for key, value in status.items():
        print(f"{key:<14} {value}")
    return 0


def cmd_incidents_list(args):
    try:
        incidents = _api(args).list_incidents(
            service=args.service, status=args.status, limit=args.limit
        )
    except ApiError as exc:
        print(f"error: {exc}")
        return 1
    if args.json:
        output.dump_json(incidents)
        return 0
    if not incidents:
        print("no incidents")
        return 0
    output.print_table(
        ["ID", "STATUS", "SEV", "SERVICE", "RULE", "STARTED", "DETECTED"],
        [
            [
                output.short_id(i["id"]),
                i["status"],
                i["severity"],
                i["service"],
                i["detection_rule_name"],
                i["started_at"][:19].replace("T", " "),
                i["detected_at"][:19].replace("T", " "),
            ]
            for i in incidents
        ],
    )
    return 0


def cmd_incidents_show(args):
    api = _api(args)
    try:
        incident_id = api.resolve_incident_id(args.id)
        incident = api.get_incident(incident_id)
    except ApiError as exc:
        print(f"error: {exc}")
        return 1
    if args.json:
        output.dump_json(incident)
        return 0
    output.kv(
        "incident",
        [
            ("id", incident["id"]),
            ("title", incident.get("title")),
            ("service", incident.get("service")),
            ("severity", incident.get("severity")),
            ("status", incident.get("status")),
            ("rule", incident.get("detection_rule_name")),
            ("started_at", incident.get("started_at")),
            ("detected_at", incident.get("detected_at")),
        ],
    )
    if incident.get("payload"):
        output.kv("payload", sorted(incident["payload"].items()))
    return 0


def cmd_incidents_investigate(args):
    api = _api(args)
    try:
        incident_id = api.resolve_incident_id(args.id)
        investigation = api.investigate(incident_id)
    except ApiError as exc:
        print(f"error: {exc}")
        return 1
    if args.json:
        output.dump_json(investigation)
        return 0
    output.kv(
        "investigation",
        [
            ("id", investigation["id"]),
            ("incident_id", investigation.get("incident_id")),
            ("status", investigation.get("status")),
            ("created_at", investigation.get("created_at")),
        ],
    )
    return 0


def cmd_incidents_resolve(args):
    api = _api(args)
    try:
        incident_id = api.resolve_incident_id(args.id)
        incident = api.resolve_incident(incident_id)
    except ApiError as exc:
        print(f"error: {exc}")
        return 1
    if args.json:
        output.dump_json(incident)
        return 0
    output.kv(
        "resolved",
        [
            ("id", incident["id"]),
            ("title", incident.get("title")),
            ("service", incident.get("service")),
            ("status", incident.get("status")),
        ],
    )
    return 0


def _print_investigation(investigation):
    output.kv(
        "investigation",
        [
            ("id", investigation["id"]),
            ("incident_id", investigation.get("incident_id")),
            ("status", investigation.get("status")),
            ("created_at", investigation.get("created_at")),
            ("updated_at", investigation.get("updated_at")),
        ],
    )
    for step in investigation.get("steps", []):
        error = f" error={step['error']}" if step.get("error") else ""
        print(
            f"  step {step['step_type']:<28} {step['status']:<10} "
            f"attempt={step.get('attempt', 1)}{error}"
        )
    print()


def cmd_investigation_status(args):
    api = _api(args)
    try:
        investigation = api.get_investigation(args.id)
    except ApiError as exc:
        print(f"error: {exc}")
        return 1
    if args.json:
        output.dump_json(investigation)
        return 0
    _print_investigation(investigation)
    if args.watch and investigation["status"] not in ("READY", "FAILED"):
        import time

        deadline = time.monotonic() + args.timeout
        while investigation["status"] not in ("READY", "FAILED"):
            if time.monotonic() >= deadline:
                print("investigation still running after the watch window")
                return 1
            time.sleep(5)
            investigation = api.get_investigation(args.id)
            print(f"status: {investigation['status']}")
        _print_investigation(investigation)
    return 0


def cmd_investigation_evidence(args):
    try:
        records = _api(args).evidence(args.id)
    except ApiError as exc:
        print(f"error: {exc}")
        return 1
    if args.json:
        output.dump_json(records)
        return 0
    if not records:
        print("no evidence")
        return 0
    output.print_table(
        ["ID", "SOURCE", "SERVICE", "SIGNAL", "TIMESTAMP"],
        [
            [
                output.short_id(r["id"]),
                r.get("source", "-"),
                r.get("service", "-"),
                r.get("signal", "-"),
                str(r.get("timestamp", "-"))[:19],
            ]
            for r in records
        ],
    )
    return 0


def cmd_investigation_candidates(args):
    try:
        candidates = _api(args).candidates(args.id)
    except ApiError as exc:
        print(f"error: {exc}")
        return 1
    if args.json:
        output.dump_json(candidates)
        return 0
    if not candidates:
        print("no candidates")
        return 0
    output.print_table(
        ["ID", "ROOT_CAUSE_TYPE", "STATUS", "CONFIDENCE", "SELECTED"],
        [
            [
                output.short_id(c["id"]),
                c.get("root_cause_type", "-"),
                c.get("status", "-"),
                str(c.get("confidence", "-")),
                str(c.get("is_selected", "-")),
            ]
            for c in candidates
        ],
    )
    return 0


def cmd_investigation_root_cause(args):
    try:
        root_cause = _api(args).root_cause(args.id)
    except ApiError as exc:
        print(f"error: {exc}")
        return 1
    if args.json:
        output.dump_json(root_cause)
        return 0
    output.kv(
        "root cause",
        [
            ("id", root_cause.get("id")),
            ("candidate_id", root_cause.get("candidate_id")),
            ("selection_mode", root_cause.get("selection_mode")),
            ("root_cause_type", root_cause.get("root_cause_type")),
            ("title", root_cause.get("title")),
            ("confidence", root_cause.get("confidence")),
            ("related_services", ", ".join(root_cause.get("related_services", []) or [])),
        ],
    )
    for key in ("summary", "reasoning"):
        if root_cause.get(key):
            print(f"{key}: {root_cause[key]}")
    print()
    if root_cause.get("evidence_chain"):
        output.kv("evidence chain", [("step", e) for e in root_cause["evidence_chain"]])
    return 0


def cmd_emit(args):
    from incident_os_cli.emit import emit

    try:
        emit(_api(args).base_url + "/api/v1/otlp", args.profile)
    except Exception as exc:
        print(f"error: {exc}")
        return 1
    return 0


def cmd_demo(args):
    return demo_cmd.run(_api(args), args.profile, args.wait)


def build_parser():
    parser = argparse.ArgumentParser(
        prog="incident-os",
        description="Incident OS CLI: emit telemetry, browse incidents, and run investigations.",
    )
    parser.add_argument(
        "--url",
        default=DEFAULT_URL,
        help=f"Incident OS API base URL (env INCIDENT_OS_URL, default {DEFAULT_URL})",
    )
    parser.add_argument("--json", action="store_true", help="emit raw JSON instead of tables")
    sub = parser.add_subparsers(dest="command", required=True)

    def add_json(p):
        p.add_argument("--json", action="store_true", help=argparse.SUPPRESS)

    p_health = sub.add_parser("health", help="check API health")
    p_health.set_defaults(func=cmd_health)
    add_json(p_health)

    p_incidents = sub.add_parser("incidents", help="browse and investigate incidents")
    p_incidents_sub = p_incidents.add_subparsers(dest="incident_command", required=True)
    add_json(p_incidents)

    p_list = p_incidents_sub.add_parser("list", help="list incidents")
    p_list.add_argument("--service", help="filter by service")
    p_list.add_argument("--status", help="filter by status (OPEN, ...)")
    p_list.add_argument("--limit", type=int, default=100, help="max results (1-1000)")
    p_list.set_defaults(func=cmd_incidents_list)
    add_json(p_list)

    p_show = p_incidents_sub.add_parser("show", help="show a single incident")
    p_show.add_argument("id", help="incident id")
    p_show.set_defaults(func=cmd_incidents_show)
    add_json(p_show)

    p_inv = p_incidents_sub.add_parser("investigate", help="start an investigation")
    p_inv.add_argument("id", help="incident id")
    p_inv.set_defaults(func=cmd_incidents_investigate)
    add_json(p_inv)

    p_resolve = p_incidents_sub.add_parser("resolve", help="resolve an open incident")
    p_resolve.add_argument("id", help="incident id")
    p_resolve.set_defaults(func=cmd_incidents_resolve)
    add_json(p_resolve)

    p_investigation = sub.add_parser("investigation", help="inspect investigations")
    p_investigation_sub = p_investigation.add_subparsers(dest="investigation_command", required=True)

    p_status = p_investigation_sub.add_parser("status", help="show investigation status")
    p_status.add_argument("id", help="investigation id")
    p_status.add_argument("--watch", action="store_true", help="poll until READY or FAILED")
    p_status.add_argument("--timeout", type=int, default=600, help="watch timeout in seconds")
    p_status.set_defaults(func=cmd_investigation_status)
    add_json(p_status)

    p_evidence = p_investigation_sub.add_parser("evidence", help="list gathered evidence")
    p_evidence.add_argument("id", help="investigation id")
    p_evidence.set_defaults(func=cmd_investigation_evidence)
    add_json(p_evidence)

    p_candidates = p_investigation_sub.add_parser("candidates", help="list root-cause candidates")
    p_candidates.add_argument("id", help="investigation id")
    p_candidates.set_defaults(func=cmd_investigation_candidates)
    add_json(p_candidates)

    p_root = p_investigation_sub.add_parser("root-cause", help="show the selected root cause")
    p_root.add_argument("id", help="investigation id")
    p_root.set_defaults(func=cmd_investigation_root_cause)
    add_json(p_root)

    p_emit = sub.add_parser("emit", help="emit failure telemetry via OpenTelemetry")
    p_emit.add_argument(
        "--profile",
        default="all",
        choices=PROFILES,
        help="which telemetry to emit (default: all)",
    )
    p_emit.set_defaults(func=cmd_emit)
    add_json(p_emit)

    p_demo = sub.add_parser(
        "demo", help="full workflow: emit -> detect -> investigate -> root cause"
    )
    p_demo.add_argument("--profile", default="all", choices=PROFILES)
    p_demo.add_argument("--wait", type=int, default=480, help="detection wait in seconds")
    p_demo.set_defaults(func=cmd_demo)
    add_json(p_demo)

    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        return args.func(args) or 0
    except ApiError as exc:
        print(f"error: {exc}")
        return 1
    except KeyboardInterrupt:
        print()
        return 130
