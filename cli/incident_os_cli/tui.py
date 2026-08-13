"""Interactive terminal dashboard for Incident OS (Textual TUI)."""

import time
from functools import partial

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import DataTable, Footer, Header, RichLog, Static
from textual.worker import WorkerState

from incident_os_cli.api import Api
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
    #detail, #investigation { height: 1fr; min-height: 4; border: round $primary; margin-top: 1; }
    .section-label { height: 1; color: $text-muted; text-style: bold; }
    """

    BINDINGS = [
        Binding("r", "reload", "refresh"),
        Binding("i", "investigate", "investigate"),
        Binding("x", "resolve", "resolve"),
        Binding("C", "clear", "clear incidents"),
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
        self._clear_arm = False
        self._suppress_highlight = False

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
        inc = self.api.get_incident(self.selected)
        inv = None
        rc = None
        try:
            investigations = self.api.list_incident_investigations(self.selected)
        except Exception:
            investigations = []
        if investigations:
            inv = investigations[0]
            if inv.get("status") == "READY":
                try:
                    rc = self.api.root_cause(inv["id"])
                except Exception:
                    rc = None
        return inc, inv, rc

    def _fetch_replay(self):
        inc = self.api.get_incident(self.selected)
        investigations = self.api.list_incident_investigations(self.selected)
        rc = None
        if investigations:
            inv = investigations[0]
            if inv.get("status") == "READY":
                try:
                    rc = self.api.root_cause(inv["id"])
                except Exception:
                    rc = None
        return inc, investigations, rc

    def _emit(self, profile: str) -> str:
        emit(self.api.base_url + "/api/v1/otlp", profile)
        time.sleep(15)
        return f"emitted {profile} - incidents appear within ~60s"

    def on_worker_state_changed(self, event) -> None:
        worker = event.worker
        if not worker.is_finished:
            return
        if worker.state == WorkerState.ERROR:
            self._note(f"!! {worker.group} failed: {worker.error or 'unknown error'}")
            return
        result = worker.result
        if result is None:
            return
        if worker.group == "load":
            self._render_incidents(result)
        elif worker.group == "detail":
            self._render_detail(*result)
        elif worker.group == "replay":
            self._render_replay(*result)
        elif worker.group == "emit":
            self._note(result)
            self.reload()
        elif worker.group == "start_investigation":
            self._investigation_id = result
            self._investigation_timer = self.set_interval(5, self._poll_investigation)
        elif worker.group == "poll_investigation":
            self._render_investigation(*result)
        elif worker.group == "resolve":
            self._note(f"resolved {result}")
            self.reload()
            self._show_detail_for(self.selected)
        elif worker.group == "clear":
            self._note(f"cleared {result} incident(s)")
            self.selected = None
            self._investigation_id = None
            if self._investigation_timer:
                self._investigation_timer.stop()
                self._investigation_timer = None
            self._investigation().clear()
            self.reload()

    # ---- rendering ---------------------------------------------------

    def _render_incidents(self, incidents) -> None:
        table = self.query_one("#incidents-table", DataTable)
        prev_selected = self.selected
        ids = {inc.get("id") for inc in incidents}
        self._suppress_highlight = True
        try:
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
            if prev_selected and prev_selected in ids:
                table.move_cursor(row=table.get_row_index(prev_selected))
            elif incidents:
                self._show_detail_for(incidents[0]["id"])
        finally:
            self._suppress_highlight = False

    def _render_detail(self, inc, inv, rc) -> None:
        pane = self._detail()
        pane.clear()
        pane.write(_fmt_incident(inc))
        inv_pane = self._investigation()
        inv_pane.clear()
        if not inv:
            inv_pane.write("no investigation was run for this incident")
            return
        self._write_investigation(inv_pane, inv, rc)

    def _write_investigation(self, pane, inv, rc) -> None:
        pane.write(f"investigation  {inv.get('id')}")
        pane.write(f"status  {inv.get('status')}   created {_ts(inv.get('created_at'))}")
        for step in inv.get("steps", []):
            err = f"  {step.get('error')}" if step.get("error") else ""
            pane.write(f"  {step['step_type']:<10} {step['status']:<12} attempt={step.get('attempt', 1)}{err}")
        if rc:
            pane.write("")
            pane.write(_fmt_root_cause(rc))

    def _render_replay(self, inc, investigations, rc) -> None:
        pane = self._detail()
        pane.clear()
        pane.write(_fmt_incident(inc))
        inv_pane = self._investigation()
        inv_pane.clear()
        if not investigations:
            inv_pane.write("no investigation was run for this incident")
            return
        inv = investigations[0]
        steps = {s["step_type"]: s for s in inv.get("steps", [])}
        for step_type in _ORDER:
            step = steps.get(step_type)
            if not step:
                continue
            inv_pane.write(f"{_ts(step.get('completed_at'))}  step {step_type:<10} {step.get('status')}")
        inv_pane.write(f"{_ts(inv.get('updated_at'))}  investigation {inv.get('status')}")
        if rc:
            inv_pane.write("")
            inv_pane.write(_fmt_root_cause(rc))

    # ---- actions -----------------------------------------------------

    def _show_detail_for(self, incident_id) -> None:
        self.selected = incident_id
        self.run_worker(self._fetch_detail, thread=True, group="detail", exclusive=True)

    def on_data_table_row_selected(self, event) -> None:
        self._show_detail_for(event.row_key.value)

    def on_data_table_row_highlighted(self, event) -> None:
        if self._suppress_highlight:
            return
        if event.row_key is not None:
            self._show_detail_for(event.row_key.value)

    def action_investigate(self) -> None:
        if not self.selected:
            self._note("select an incident first (move with arrows / Enter), then press i")
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
        self.run_worker(
            self._fetch_investigation,
            thread=True,
            group="poll_investigation",
            exclusive=True,
        )

    def _fetch_investigation(self):
        inv_id = self._investigation_id
        if not inv_id:
            return None, "no investigation id"
        try:
            inv = self.api.get_investigation(inv_id)
        except Exception as exc:
            return None, f"investigation poll failed: {exc}"
        rc = None
        if inv.get("status") == "READY":
            try:
                rc = self.api.root_cause(inv_id)
            except Exception:
                rc = None
        return inv, rc

    def _render_investigation(self, inv, rc) -> None:
        pane = self._investigation()
        pane.clear()
        if inv is None:
            pane.write(rc or "investigation poll failed")
            return
        self._write_investigation(pane, inv, rc)
        if inv.get("status") in ("READY", "FAILED"):
            if self._investigation_timer:
                self._investigation_timer.stop()
                self._investigation_timer = None

    def action_resolve(self) -> None:
        if not self.selected:
            self._note("select an incident first (move with arrows / Enter), then press x")
            return
        self.run_worker(self._resolve, thread=True, group="resolve")

    def _resolve(self) -> None:
        return self.api.resolve_incident(self.selected)["id"]

    def action_replay(self) -> None:
        if self.selected:
            self.run_worker(self._fetch_replay, thread=True, group="replay")

    def action_clear(self) -> None:
        if not self._clear_arm:
            self._clear_arm = True
            self._note("press C again to confirm: delete ALL incidents (investigations too)")
            self.set_timer(5, self._disarm_clear)
            return
        self._clear_arm = False
        self.run_worker(self._clear_all, thread=True, group="clear")

    def _disarm_clear(self) -> None:
        self._clear_arm = False

    def _clear_all(self):
        result = self.api.clear_incidents()
        return result.get("deleted", 0)

    def action_emit_all(self) -> None:
        self.run_worker(partial(self._emit, "all"), thread=True, group="emit")

    def action_emit_http(self) -> None:
        self.run_worker(partial(self._emit, "http"), thread=True, group="emit")

    def action_emit_kafka(self) -> None:
        self.run_worker(partial(self._emit, "kafka"), thread=True, group="emit")

    def action_emit_redis(self) -> None:
        self.run_worker(partial(self._emit, "redis"), thread=True, group="emit")

    def action_emit_trace(self) -> None:
        self.run_worker(partial(self._emit, "trace"), thread=True, group="emit")
