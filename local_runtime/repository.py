from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from threading import RLock
from typing import Iterable

from quakemesh_core.models import Evidence, EventRecord, EventStatus


SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS devices(
 device_id TEXT PRIMARY KEY,
 h3_cell TEXT NOT NULL,
 correlation_cell TEXT NOT NULL,
 last_seen_ms INTEGER NOT NULL,
 last_seq INTEGER NOT NULL,
 transport TEXT NOT NULL,
 fcm_token TEXT,
 provenance_type TEXT NOT NULL DEFAULT 'physical',
 scenario_run_id TEXT
);
CREATE TABLE IF NOT EXISTS evidence(
 evidence_id TEXT PRIMARY KEY,
 bucket INTEGER NOT NULL,
 device_id TEXT NOT NULL,
 seq INTEGER NOT NULL,
 observed_at_ms INTEGER NOT NULL,
 h3_cell TEXT NOT NULL,
 correlation_cell TEXT NOT NULL,
 motion_rms REAL NOT NULL,
 motion_peak REAL NOT NULL,
 transport TEXT NOT NULL,
 scenario_run_id TEXT
);
CREATE INDEX IF NOT EXISTS idx_evidence_time ON evidence(observed_at_ms);
CREATE INDEX IF NOT EXISTS idx_evidence_cell_time ON evidence(correlation_cell,observed_at_ms);
CREATE INDEX IF NOT EXISTS idx_evidence_run_time ON evidence(scenario_run_id,observed_at_ms);
CREATE TABLE IF NOT EXISTS events(
 event_id TEXT PRIMARY KEY,
 status TEXT NOT NULL,
 created_at_ms INTEGER NOT NULL,
 updated_at_ms INTEGER NOT NULL,
 first_observed_at_ms INTEGER NOT NULL,
 last_observed_at_ms INTEGER NOT NULL,
 version INTEGER NOT NULL,
 device_ids_json TEXT NOT NULL,
 footprint_json TEXT NOT NULL,
 frontier_json TEXT NOT NULL,
 evidence_ids_json TEXT NOT NULL,
 provenance_type TEXT NOT NULL DEFAULT 'physical',
 scenario_run_id TEXT
);
CREATE INDEX IF NOT EXISTS idx_events_status_updated ON events(status,updated_at_ms);
CREATE INDEX IF NOT EXISTS idx_events_run ON events(scenario_run_id,updated_at_ms);
CREATE TABLE IF NOT EXISTS alerts(
 alert_id TEXT PRIMARY KEY,
 event_id TEXT NOT NULL,
 event_version INTEGER NOT NULL,
 device_id TEXT NOT NULL,
 created_at_ms INTEGER NOT NULL,
 transport TEXT NOT NULL,
 status TEXT NOT NULL,
 provenance_type TEXT NOT NULL DEFAULT 'physical',
 scenario_run_id TEXT,
 sent_at_ms INTEGER,
 acknowledged_at_ms INTEGER,
 acknowledgement_source TEXT,
 failure_detail TEXT,
 UNIQUE(event_id,event_version,device_id)
);
CREATE INDEX IF NOT EXISTS idx_alerts_run ON alerts(scenario_run_id,created_at_ms);
CREATE TABLE IF NOT EXISTS scenario_runs(
 run_id TEXT PRIMARY KEY,
 scenario TEXT NOT NULL,
 source TEXT NOT NULL,
 mode TEXT NOT NULL,
 catalog_version TEXT NOT NULL DEFAULT '2.0',
 seed INTEGER NOT NULL,
 devices INTEGER NOT NULL,
 status TEXT NOT NULL,
 expected_result TEXT NOT NULL,
 observed_result TEXT,
 created_at_ms INTEGER NOT NULL,
 started_at_ms INTEGER,
 completed_at_ms INTEGER,
 parameters_json TEXT NOT NULL,
 event_ids_json TEXT NOT NULL,
 error TEXT
);
CREATE INDEX IF NOT EXISTS idx_scenario_runs_created ON scenario_runs(created_at_ms DESC);
CREATE INDEX IF NOT EXISTS idx_scenario_runs_active ON scenario_runs(status,created_at_ms);
CREATE TABLE IF NOT EXISTS scenario_stages(
 stage_id INTEGER PRIMARY KEY AUTOINCREMENT,
 run_id TEXT NOT NULL,
 sequence INTEGER NOT NULL,
 occurred_at_ms INTEGER NOT NULL,
 code TEXT NOT NULL,
 component TEXT NOT NULL,
 severity TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'COMPLETED',
 message TEXT NOT NULL,
 data_json TEXT NOT NULL,
 device_id TEXT,
 event_id TEXT,
 alert_id TEXT,
 duration_ms INTEGER,
 FOREIGN KEY(run_id) REFERENCES scenario_runs(run_id) ON DELETE CASCADE,
 UNIQUE(run_id,sequence)
);
CREATE INDEX IF NOT EXISTS idx_scenario_stages_run ON scenario_stages(run_id,sequence);
"""


class ActiveScenarioRunError(RuntimeError):
    def __init__(self, run_id: str):
        super().__init__(f"active scenario run: {run_id}")
        self.run_id = run_id


class SQLiteRepository:
    def __init__(self, path: str | Path):
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        with self._connect() as connection:
            connection.executescript(SCHEMA)
            self._migrate(connection)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    @staticmethod
    def _ensure_column(connection: sqlite3.Connection, table: str, name: str, definition: str) -> None:
        columns = {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}
        if name not in columns:
            connection.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")

    def _migrate(self, connection: sqlite3.Connection) -> None:
        migrations = {
            "devices": {
                "provenance_type": "TEXT NOT NULL DEFAULT 'physical'",
                "scenario_run_id": "TEXT",
            },
            "evidence": {"scenario_run_id": "TEXT"},
            "events": {
                "provenance_type": "TEXT NOT NULL DEFAULT 'physical'",
                "scenario_run_id": "TEXT",
            },
            "alerts": {
                "provenance_type": "TEXT NOT NULL DEFAULT 'physical'",
                "scenario_run_id": "TEXT",
                "sent_at_ms": "INTEGER",
                "acknowledged_at_ms": "INTEGER",
                "acknowledgement_source": "TEXT",
                "failure_detail": "TEXT",
            },
            "scenario_runs": {"catalog_version": "TEXT NOT NULL DEFAULT '2.0'"},
            "scenario_stages": {
                "sequence": "INTEGER",
                "status": "TEXT NOT NULL DEFAULT 'COMPLETED'",
                "device_id": "TEXT",
                "event_id": "TEXT",
                "alert_id": "TEXT",
                "duration_ms": "INTEGER",
            },
        }
        for table, columns in migrations.items():
            for name, definition in columns.items():
                self._ensure_column(connection, table, name, definition)
        connection.execute(
            """UPDATE scenario_stages SET sequence=(
                SELECT COUNT(*) FROM scenario_stages earlier
                WHERE earlier.run_id=scenario_stages.run_id
                  AND earlier.stage_id<=scenario_stages.stage_id
            ) WHERE sequence IS NULL"""
        )

    def update_device(
        self,
        device_id: str,
        seq: int,
        observed_at_ms: int,
        h3_cell: str,
        correlation_cell: str,
        transport: str,
        fcm_token: str | None = None,
        provenance_type: str = "physical",
        scenario_run_id: str | None = None,
    ) -> bool:
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT last_seq,provenance_type,scenario_run_id FROM devices WHERE device_id=?",
                (device_id,),
            ).fetchone()
            if row and seq <= row["last_seq"]:
                return False
            if row and (row["provenance_type"], row["scenario_run_id"]) != (
                provenance_type,
                scenario_run_id,
            ):
                return False
            connection.execute(
                """INSERT INTO devices(
                   device_id,h3_cell,correlation_cell,last_seen_ms,last_seq,transport,fcm_token,
                   provenance_type,scenario_run_id
                   ) VALUES(?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(device_id) DO UPDATE SET
                   h3_cell=excluded.h3_cell,correlation_cell=excluded.correlation_cell,
                   last_seen_ms=excluded.last_seen_ms,last_seq=excluded.last_seq,
                   transport=excluded.transport,
                   fcm_token=COALESCE(excluded.fcm_token,devices.fcm_token)""",
                (
                    device_id,
                    h3_cell,
                    correlation_cell,
                    observed_at_ms,
                    seq,
                    transport,
                    fcm_token,
                    provenance_type,
                    scenario_run_id,
                ),
            )
            return True

    def list_devices(self, limit: int = 500) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT device_id,correlation_cell,last_seen_ms,last_seq,transport,
                   provenance_type,scenario_run_id
                   FROM devices ORDER BY last_seen_ms DESC LIMIT ?""",
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def add_evidence(
        self,
        evidence: Evidence,
        bucket_ms: int = 10_000,
        scenario_run_id: str | None = None,
    ) -> bool:
        with self._lock, self._connect() as connection:
            try:
                connection.execute(
                    """INSERT INTO evidence(
                       evidence_id,bucket,device_id,seq,observed_at_ms,h3_cell,correlation_cell,
                       motion_rms,motion_peak,transport,scenario_run_id
                       ) VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        evidence.evidence_id,
                        evidence.observed_at_ms // bucket_ms,
                        evidence.device_id,
                        evidence.seq,
                        evidence.observed_at_ms,
                        evidence.h3_cell,
                        evidence.correlation_cell,
                        evidence.motion_rms,
                        evidence.motion_peak,
                        evidence.transport,
                        scenario_run_id,
                    ),
                )
            except sqlite3.IntegrityError:
                return False
            return True

    def recent_evidence(self, since_ms: int, scenario_run_id: str | None = None) -> list[Evidence]:
        with self._connect() as connection:
            if scenario_run_id is None:
                rows = connection.execute(
                    """SELECT * FROM evidence
                       WHERE observed_at_ms>=? AND scenario_run_id IS NULL
                       ORDER BY observed_at_ms""",
                    (since_ms,),
                ).fetchall()
            else:
                rows = connection.execute(
                    """SELECT * FROM evidence
                       WHERE observed_at_ms>=? AND scenario_run_id=?
                       ORDER BY observed_at_ms""",
                    (since_ms, scenario_run_id),
                ).fetchall()
        return [
            Evidence(
                row["evidence_id"],
                row["device_id"],
                row["seq"],
                row["observed_at_ms"],
                row["h3_cell"],
                row["correlation_cell"],
                row["motion_rms"],
                row["motion_peak"],
                row["transport"],
            )
            for row in rows
        ]

    def save_event(self, event: EventRecord) -> None:
        with self._lock, self._connect() as connection:
            connection.execute(
                """INSERT INTO events(
                   event_id,status,created_at_ms,updated_at_ms,first_observed_at_ms,
                   last_observed_at_ms,version,device_ids_json,footprint_json,frontier_json,
                   evidence_ids_json,provenance_type,scenario_run_id
                   ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(event_id) DO UPDATE SET
                   status=excluded.status,updated_at_ms=excluded.updated_at_ms,
                   last_observed_at_ms=excluded.last_observed_at_ms,version=excluded.version,
                   device_ids_json=excluded.device_ids_json,footprint_json=excluded.footprint_json,
                   frontier_json=excluded.frontier_json,evidence_ids_json=excluded.evidence_ids_json""",
                (
                    event.event_id,
                    event.status.value,
                    event.created_at_ms,
                    event.updated_at_ms,
                    event.first_observed_at_ms,
                    event.last_observed_at_ms,
                    event.version,
                    json.dumps(event.device_ids),
                    json.dumps(event.detection_footprint),
                    json.dumps(event.warning_frontier),
                    json.dumps(event.evidence_ids),
                    event.provenance_type,
                    event.scenario_run_id,
                ),
            )

    @staticmethod
    def _event(row: sqlite3.Row) -> EventRecord:
        return EventRecord(
            event_id=row["event_id"],
            status=EventStatus(row["status"]),
            created_at_ms=row["created_at_ms"],
            updated_at_ms=row["updated_at_ms"],
            first_observed_at_ms=row["first_observed_at_ms"],
            last_observed_at_ms=row["last_observed_at_ms"],
            device_ids=json.loads(row["device_ids_json"]),
            detection_footprint=json.loads(row["footprint_json"]),
            warning_frontier=json.loads(row["frontier_json"]),
            evidence_ids=json.loads(row["evidence_ids_json"]),
            version=row["version"],
            provenance_type=row["provenance_type"],
            scenario_run_id=row["scenario_run_id"],
        )

    def active_events(
        self,
        since_ms: int,
        provenance_type: str = "physical",
        scenario_run_id: str | None = None,
    ) -> list[EventRecord]:
        with self._connect() as connection:
            if scenario_run_id is None:
                rows = connection.execute(
                    """SELECT * FROM events WHERE status!='RESOLVED' AND updated_at_ms>=?
                       AND provenance_type=? AND scenario_run_id IS NULL
                       ORDER BY updated_at_ms DESC""",
                    (since_ms, provenance_type),
                ).fetchall()
            else:
                rows = connection.execute(
                    """SELECT * FROM events WHERE status!='RESOLVED' AND updated_at_ms>=?
                       AND provenance_type=? AND scenario_run_id=?
                       ORDER BY updated_at_ms DESC""",
                    (since_ms, provenance_type, scenario_run_id),
                ).fetchall()
        return [self._event(row) for row in rows]

    def list_events(self, limit: int = 100, scenario_run_id: str | None = None) -> list[EventRecord]:
        with self._connect() as connection:
            if scenario_run_id is None:
                rows = connection.execute(
                    "SELECT * FROM events ORDER BY updated_at_ms DESC LIMIT ?", (limit,)
                ).fetchall()
            else:
                rows = connection.execute(
                    "SELECT * FROM events WHERE scenario_run_id=? ORDER BY updated_at_ms DESC LIMIT ?",
                    (scenario_run_id, limit),
                ).fetchall()
        return [self._event(row) for row in rows]

    def get_event(self, event_id: str) -> EventRecord | None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM events WHERE event_id=?", (event_id,)).fetchone()
        return self._event(row) if row else None

    def resolve_stale(self, cutoff_ms: int, current_ms: int) -> int:
        with self._lock, self._connect() as connection:
            cursor = connection.execute(
                """UPDATE events SET status='RESOLVED',updated_at_ms=?,version=version+1
                   WHERE status='CONFIRMED' AND last_observed_at_ms<?""",
                (current_ms, cutoff_ms),
            )
            return cursor.rowcount

    def target_devices(
        self,
        cells: Iterable[str],
        seen_after_ms: int,
        provenance_type: str = "physical",
        scenario_run_id: str | None = None,
    ) -> list[dict]:
        unique_cells = sorted(set(cells))
        if not unique_cells:
            return []
        placeholders = ",".join("?" for _ in unique_cells)
        with self._connect() as connection:
            if scenario_run_id is None:
                rows = connection.execute(
                    f"""SELECT device_id,correlation_cell,last_seen_ms,last_seq,transport,
                        provenance_type,scenario_run_id FROM devices
                        WHERE correlation_cell IN ({placeholders}) AND last_seen_ms>=?
                        AND provenance_type=? AND scenario_run_id IS NULL""",
                    (*unique_cells, seen_after_ms, provenance_type),
                ).fetchall()
            else:
                rows = connection.execute(
                    f"""SELECT device_id,correlation_cell,last_seen_ms,last_seq,transport,
                        provenance_type,scenario_run_id FROM devices
                        WHERE correlation_cell IN ({placeholders}) AND last_seen_ms>=?
                        AND provenance_type=? AND scenario_run_id=?""",
                    (*unique_cells, seen_after_ms, provenance_type, scenario_run_id),
                ).fetchall()
        return [dict(row) for row in rows]

    def record_alert(
        self,
        event_id: str,
        event_version: int,
        device_id: str,
        created_at_ms: int,
        transport: str = "local",
        provenance_type: str = "physical",
        scenario_run_id: str | None = None,
        status: str = "TARGETED",
    ) -> bool:
        alert_id = f"{event_id}:{device_id}"
        with self._lock, self._connect() as connection:
            try:
                connection.execute(
                    """INSERT INTO alerts(
                       alert_id,event_id,event_version,device_id,created_at_ms,transport,status,
                       provenance_type,scenario_run_id
                       ) VALUES(?,?,?,?,?,?,?,?,?)""",
                    (
                        alert_id,
                        event_id,
                        event_version,
                        device_id,
                        created_at_ms,
                        transport,
                        status,
                        provenance_type,
                        scenario_run_id,
                    ),
                )
            except sqlite3.IntegrityError:
                return False
            return True

    def list_alerts(self, limit: int = 200, scenario_run_id: str | None = None) -> list[dict]:
        with self._connect() as connection:
            if scenario_run_id is None:
                rows = connection.execute(
                    "SELECT * FROM alerts ORDER BY created_at_ms DESC LIMIT ?", (limit,)
                ).fetchall()
            else:
                rows = connection.execute(
                    """SELECT * FROM alerts WHERE scenario_run_id=?
                       ORDER BY created_at_ms DESC LIMIT ?""",
                    (scenario_run_id, limit),
                ).fetchall()
        return [dict(row) for row in rows]

    def get_alert(self, alert_id: str) -> dict | None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM alerts WHERE alert_id=?", (alert_id,)).fetchone()
        return dict(row) if row else None

    def acknowledge_alert(
        self,
        alert_id: str,
        acknowledged_at_ms: int,
        source: str,
        device_id: str | None = None,
    ) -> tuple[dict | None, bool]:
        with self._lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT * FROM alerts WHERE alert_id=?", (alert_id,)).fetchone()
            if not row:
                connection.rollback()
                return None, False
            if device_id is not None and row["device_id"] != device_id:
                connection.rollback()
                raise ValueError("alert device does not match acknowledgement device")
            if row["status"] == "ACKNOWLEDGED":
                connection.commit()
                return dict(row), False
            connection.execute(
                """UPDATE alerts SET status='ACKNOWLEDGED',acknowledged_at_ms=?,
                   acknowledgement_source=? WHERE alert_id=?""",
                (acknowledged_at_ms, source, alert_id),
            )
            updated = connection.execute("SELECT * FROM alerts WHERE alert_id=?", (alert_id,)).fetchone()
            connection.commit()
            return dict(updated), True

    def create_scenario_run(self, run: dict) -> dict:
        with self._lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            active = connection.execute(
                """SELECT run_id FROM scenario_runs
                   WHERE status IN ('QUEUED','RUNNING') ORDER BY created_at_ms LIMIT 1"""
            ).fetchone()
            if active:
                connection.rollback()
                raise ActiveScenarioRunError(active["run_id"])
            connection.execute(
                """INSERT INTO scenario_runs(
                   run_id,scenario,source,mode,catalog_version,seed,devices,status,
                   expected_result,observed_result,created_at_ms,started_at_ms,completed_at_ms,
                   parameters_json,event_ids_json,error
                   ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    run["run_id"],
                    run["scenario"],
                    run["source"],
                    run["mode"],
                    run.get("catalog_version", "2.0"),
                    run["seed"],
                    run["devices"],
                    run["status"],
                    run["expected_result"],
                    run.get("observed_result"),
                    run["created_at_ms"],
                    run.get("started_at_ms"),
                    run.get("completed_at_ms"),
                    json.dumps(run.get("parameters", {}), sort_keys=True),
                    json.dumps(run.get("event_ids", [])),
                    run.get("error"),
                ),
            )
            connection.execute(
                """INSERT INTO scenario_stages(
                   run_id,sequence,occurred_at_ms,code,component,severity,status,message,data_json
                   ) VALUES(?,?,?,?,?,?,?,?,?)""",
                (
                    run["run_id"],
                    1,
                    run["created_at_ms"],
                    "RUN_REQUESTED",
                    "scenario-control",
                    "info",
                    "COMPLETED",
                    f"Scenario {run['scenario']} requested",
                    json.dumps(
                        {"source": run["source"], "parameters": run.get("parameters", {})},
                        sort_keys=True,
                    ),
                ),
            )
            connection.commit()
        created = self.get_scenario_run(run["run_id"])
        if created is None:
            raise RuntimeError("scenario run disappeared after creation")
        return created

    def mark_scenario_running(self, run_id: str, started_at_ms: int) -> bool:
        with self._lock, self._connect() as connection:
            cursor = connection.execute(
                """UPDATE scenario_runs SET status='RUNNING',started_at_ms=?
                   WHERE run_id=? AND status='QUEUED'""",
                (started_at_ms, run_id),
            )
            return cursor.rowcount == 1

    def update_scenario_run(self, run_id: str, **changes) -> None:
        allowed = {
            "status",
            "observed_result",
            "started_at_ms",
            "completed_at_ms",
            "event_ids",
            "error",
        }
        unknown = set(changes) - allowed
        if unknown:
            raise ValueError(f"unsupported scenario-run fields: {sorted(unknown)}")
        if not changes:
            return
        assignments: list[str] = []
        values: list[object] = []
        for key, value in changes.items():
            assignments.append(f"{'event_ids_json' if key == 'event_ids' else key}=?")
            values.append(json.dumps(value) if key == "event_ids" else value)
        with self._lock, self._connect() as connection:
            cursor = connection.execute(
                f"UPDATE scenario_runs SET {','.join(assignments)} WHERE run_id=?",
                (*values, run_id),
            )
            if cursor.rowcount != 1:
                raise KeyError(run_id)

    def add_scenario_stage(
        self,
        run_id: str,
        occurred_at_ms: int,
        code: str,
        component: str,
        severity: str,
        message: str,
        data: dict | None = None,
        *,
        status: str = "COMPLETED",
        device_id: str | None = None,
        event_id: str | None = None,
        alert_id: str | None = None,
        duration_ms: int | None = None,
    ) -> dict:
        with self._lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            sequence = connection.execute(
                "SELECT COALESCE(MAX(sequence),0)+1 FROM scenario_stages WHERE run_id=?",
                (run_id,),
            ).fetchone()[0]
            cursor = connection.execute(
                """INSERT INTO scenario_stages(
                   run_id,sequence,occurred_at_ms,code,component,severity,status,message,
                   data_json,device_id,event_id,alert_id,duration_ms
                   ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    run_id,
                    sequence,
                    occurred_at_ms,
                    code,
                    component,
                    severity,
                    status,
                    message,
                    json.dumps(data or {}, sort_keys=True),
                    device_id,
                    event_id,
                    alert_id,
                    duration_ms,
                ),
            )
            row = connection.execute(
                "SELECT * FROM scenario_stages WHERE stage_id=?", (cursor.lastrowid,)
            ).fetchone()
            connection.commit()
        return self._stage(row)

    @staticmethod
    def _scenario_run(row: sqlite3.Row) -> dict:
        result = dict(row)
        result["parameters"] = json.loads(result.pop("parameters_json"))
        result["event_ids"] = json.loads(result.pop("event_ids_json"))
        return result

    @staticmethod
    def _stage(row: sqlite3.Row) -> dict:
        result = dict(row)
        result["data"] = json.loads(result.pop("data_json"))
        return result

    def list_scenario_runs(self, limit: int = 50) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM scenario_runs ORDER BY created_at_ms DESC LIMIT ?", (limit,)
            ).fetchall()
        return [self._scenario_run(row) for row in rows]

    def get_scenario_run(self, run_id: str) -> dict | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM scenario_runs WHERE run_id=?", (run_id,)
            ).fetchone()
            if not row:
                return None
            stages = connection.execute(
                "SELECT * FROM scenario_stages WHERE run_id=? ORDER BY sequence", (run_id,)
            ).fetchall()
        result = self._scenario_run(row)
        result["stages"] = [self._stage(stage) for stage in stages]
        return result

    def active_scenario_run(self) -> dict | None:
        with self._connect() as connection:
            row = connection.execute(
                """SELECT * FROM scenario_runs WHERE status IN ('QUEUED','RUNNING')
                   ORDER BY created_at_ms LIMIT 1"""
            ).fetchone()
        return self._scenario_run(row) if row else None

    def list_stages_after(self, stage_id: int, limit: int = 250) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM scenario_stages WHERE stage_id>? ORDER BY stage_id LIMIT ?",
                (stage_id, limit),
            ).fetchall()
        return [self._stage(row) for row in rows]

    def reset_scenario_data(self) -> dict[str, int]:
        with self._lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            active = connection.execute(
                "SELECT run_id FROM scenario_runs WHERE status IN ('QUEUED','RUNNING') LIMIT 1"
            ).fetchone()
            if active:
                connection.rollback()
                raise ActiveScenarioRunError(active["run_id"])
            counts: dict[str, int] = {}
            statements = (
                ("alerts", "DELETE FROM alerts WHERE provenance_type='scenario'"),
                ("events", "DELETE FROM events WHERE provenance_type='scenario'"),
                ("evidence", "DELETE FROM evidence WHERE scenario_run_id IS NOT NULL"),
                ("devices", "DELETE FROM devices WHERE provenance_type='scenario'"),
                ("scenario_stages", "DELETE FROM scenario_stages"),
                ("scenario_runs", "DELETE FROM scenario_runs"),
            )
            for name, statement in statements:
                counts[name] = connection.execute(statement).rowcount
            connection.commit()
            return counts

    def stats(self) -> dict:
        with self._connect() as connection:
            return {
                name: connection.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]
                for name in (
                    "devices",
                    "evidence",
                    "events",
                    "alerts",
                    "scenario_runs",
                    "scenario_stages",
                )
            }
