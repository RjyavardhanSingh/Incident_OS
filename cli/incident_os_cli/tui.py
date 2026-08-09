"""Interactive terminal dashboard for Incident OS (Textual TUI)."""

import time

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import DataTable, Footer, Header, RichLog, Static

from incident_os_cli.api import Api, ApiError
from incident_os_cli.emit import emit

_ORDER = ["database", "deployment", "kafka", "logs", "metrics", "redis", "traces"]


def _ts(value):
    return (value or "").replace("T", " ")[:19]


def _fmt_incident(inc):
    p = inc.get("payload") or {}
    lines = [
        f"incident     {inc.get('id')}",
        f"title        {inc.get('title')}",
        f"service      {inc.get('service')}  severity {inc.get('severity')}  status {inc.get('status')}",
        f"rule         {inc.get('detection_rule_name') or 'manual'}",
        f"started      {_ts(inc.get('started_at'))}",
        f"detected     {_ts(inc.get('detected_at'))}",
    ]
    if p.get("value") is not None:
        lines.append(f"payload      value={p.get('value')} threshold={p.get('threshold')}")
    return "\n".join(lines)


def _fmt_root_cause(rc):
    lines = [
        f"ROOT CAUSE  {rc.get('title')}",
        f"type {rc.get('root_cause_type')}  confidence {rc.get('confidence')}  mode {rc.get('selection_mode')}",
    ]
    if rc.get("summary"):
        lines.append(rc.get("summary"))
    return "\n".join(lines)


class IncidentOSTUI(App):
    TITLE = "Incident OS"
    SUB_TITLE = "terminal interface"

    CSS = """
    Horizontal { height: 1fr; }
    #left { width: 3fr; }
    #right { width: 2fr; }
    #incidents-table { height: 1fr; }
    #detail, #investigation { height: 1fr; border: round $primary; margin-top: 1; }
    .section-label { height: 1; color: $text-muted; text-style: bold; }
    """

    BINDINGS = [
        Binding("r", "reload", "refresh"),
        Binding("i", "investigate", "investigate"),
        Binding("x", "resolve", "resolve"),
        Binding("v", "replay", "replay"),
        Binding("a", "emit_all", "emit all"),
        Binding("h", "emit_http", "emit http"),
        Binding("k", "emit_kafka", "emit kafka"),
        Binding("d", "emit_redis", "emit redis"),
        Binding("t", "emit_trace", "emit trace"),
        Binding("q", "quit", "quit"),
    ]

    def __init__(self, api: Api, refresh_s: float = 10.0):
        super().__init__()
        self.api = api
        self.refresh_s = refresh_s
        self.selected = None
        self._investigation_id = None
        self._investigation_timer = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal():
            with Vertical(id="left"):
                yield Static("incidents", classes="section-label")
                yield DataTable(id="incidents-table")
            with Vertical(id="right"):
                yield Static("incident", classes="section-label")
                yield RichLog(id="detail", highlight=True)
                yield Static("investigation", classes="section-label")
                yield RichLog(id="investigation", highlight=True)
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#incidents-table", DataTable)
        table.add_columns("status", "sev", "service", "rule", "detected", "id")
        table.show_cursor = True
        table.cursor_type = "row"
        self._detail().write(f"connecting to {self.api.base_url}")
        self.reload()
        self.set_interval(self.refresh_s, self.reload)

    # ---- helpers -----------------------------------------------------

    def _detail(self) -> RichLog:
        return self.query_one("#detail", RichLog)

    def _investigation(self) -> RichLog:
        return self.query_one("#investigation", RichLog)

    def _note(self, message: str) -> None:
        self._detail().write(message)

    # ---- workers -----------------------------------------------------

    def reload(self) -> None:
        self.run_worker(self._fetch_incidents, thread=True, exclusive=True, group="load")

    def _fetch_incidents(self):
        return self.api.list_incidents(limit=100)

    def _fetch_detail(self):
        return self.api.get_incident(self.selected)

    def _fetch_replay(self):
        return (
            self.api.get_incident(self.selected),
            self.api.list_incident_investigations(self.selected),
        )

    def _emit(self, profile: str) -> str:
        emit(self.api.base_url + "/api/v1/otlp", profile)
        time.sleep(15)
        return f"emitted {profile} - incidents appear within ~60s"

    def on_worker_state_changed(self, event) -> None:
        worker = event.worker
        if not worker.is_finished:
            return
        try:
            result = worker.result
        except ApiError as exc:
            self._note(f"!! {exc}")
            return
        if result is None:
            return
        if worker.group == "load":
            self._render_incidents(result)
        elif worker.group == "detail":
            self._render_detail(result)
        elif worker.group == "replay":
            self._render_replay(*result)
        elif worker.group == "emit":
            self._note(result)
            self.reload()
        elif worker.group == "start_investigation":
            self._investigation_id = result
            self._investigation_timer = self.set_interval(5, self._poll_investigation)
        elif worker.group == "resolve":
            self._note(f"resolved {result.get('id')}")
            self.reload()

    # ---- rendering ---------------------------------------------------

    def _render_incidents(self, incidents) -> None:
        table = self.query_one("#incidents-table", DataTable)
        table.clear()
        for inc in incidents:
            table.add_row(
                inc.get("status", ""),
                inc.get("severity", ""),
                inc.get("service", ""),
                inc.get("detection_rule_name") or "-",
                _ts(inc.get("detected_at")),
                inc.get("id", ""),
                key=inc.get("id", ""),
            )

    def _render_detail(self, inc) -> None:
        pane = self._detail()
        pane.clear()
        pane.write(_fmt_incident(inc))

    def _render_replay(self, inc, investigations) -> None:
        self._render_detail(inc)
        pane = self._investigation()
        pane.clear()
        if not investigations:
            pane.write("no investigation was run for this incident")
            return
        inv = investigations[0]
        steps = {s["step_type"]: s for s in inv.get("steps", [])}
        for step_type in _ORDER:
            step = steps.get(step_type)
            if not step:
                continue
            pane.write(f"{_ts(step.get('completed_at'))}  step {step_type:<10} {step.get('status')}")
        pane.write(f"{_ts(inv.get('updated_at'))}  investigation {inv.get('status')}")
        if inv.get("status") == "READY":
            try:
                rc = self.api.root_cause(inv["id"])
            except ApiError:
                return
            pane.write("")
            pane.write(_fmt_root_cause(rc))

    # ---- actions -----------------------------------------------------

    def _poll_investigation(self) -> None:
        inv_id = self._investigation_id
        if not inv_id:
            return

    def _render_replay(self, inc, investigations) -> None:
        self._render_detail(inc)
        pane = self._investigation()
        pane.clear()
        if not investigations:
            pane.write("no investigation was run for this incident")
            return
        inv = investigations[0]
        steps = {s["step_type"]: s for s in inv.get("steps", [])}
        for step_type in _ORDER:
            step = steps.get(step_type)
            if not step:
                continue
            pane.write(f"{_ts(step.get('completed_at'))}  step {step_type:<10} {step.get('status')}")
        pane.write(f"{_ts(inv.get('updated_at'))}  investigation {inv.get('status')}")
        if inv.get("status") == "READY":
            try:
                rc = self.api.root_cause(inv["id"])
            except ApiError:
                return
            pane.write("")
            pane.write(_fmt_root_cause(rc))

    # ---- actions -----------------------------------------------------

    def _show_detail_for(self, incident_id) -> None:
        self.selected = incident_id
        self.run_worker(self._fetch_detail, thread=True, group="detail", exclusive=True)

    def on_data_table_row_selected(self, event) -> None:
        self._show_detail_for(event.row_key.value)

    def on_data_table_row_highlighted(self, event) -> None:
        if event.row_key is not None:
            self._show_detail_for(event.row_key.value)

    def action_investigate(self) -> None:
        if not self.selected:
            return
        self._investigation_id = None
        if self._investigation_timer:
            self._investigation_timer.stop()
        pane = self._investigation()
        pane.clear()
        pane.write("starting investigation...")
        self._note(f"investigating {self.selected}")

        def start():
            inv = self.api.investigate(self.selected)
            return inv["id"]

        self.run_worker(start, thread=True, group="start_investigation")

    def _poll_investigation(self) -> None:
        inv_id = self._investigation_id
        if not inv_id:
            return
        try:
            inv = self.api.get_investigation(inv_id)
        except ApiError as exc:
            self._investigation().write(f"!! {exc}")
            return
        pane = self._investigation()
        pane.clear()
        pane.write(f"investigation  {inv.get('id')}")
        pane.write(f"status  {inv.get('status')}   created {_ts(inv.get('created_at'))}")
        for step in inv.get("steps", []):
            err = f"  {step.get('error')}" if step.get("error") else ""
            pane.write(f"  {step['step_type']:<10} {step['status']:<12} attempt={step.get('attempt', 1)}{err}")
        if inv.get("status") in ("READY", "FAILED"):
            if self._investigation_timer:
                self._investigation_timer.stop()
                self._investigation_timer = None
            if inv.get("status") == "READY":
                try:
                    rc = self.api.root_cause(inv_id)
                except ApiError:
                    return
                pane.write("")
                pane.write(_fmt_root_cause(rc))

    def action_resolve(self) -> None:
        if not self.selected:
            return
        self.run_worker(self._resolve, thread=True, group="resolve")

    def _resolve(self) -> None:
        return self.api.resolve_incident(self.selected)

    def action_replay(self) -> None:
        if self.selected:
            self.run_worker(self._fetch_replay, thread=True, group="replay")

    def action_emit_all(self) -> None:
        self.run_worker(self._emit, thread=True, group="emit", profile="all")

    def action_emit_http(self) -> None:
        self.run_worker(self._emit, thread=True, group="emit", profile="http")

    def action_emit_kafka(self) -> None:
        self.run_worker(self._emit, thread=True, group="emit", profile="kafka")

    def action_emit_redis(self) -> None:
        self.run_worker(self._emit, thread=True, group="emit", profile="redis")

    def action_emit_trace(self) -> None:
        self.run_worker(self._emit, thread=True, group="emit", profile="trace")
