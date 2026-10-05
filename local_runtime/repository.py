from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from threading import RLock
from typing import Iterable

from quakemesh_core.models import Evidence, EventRecord, EventStatus, DeviceHeartbeat

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
 fcm_token TEXT
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
CREATE INDEX IF NOT EXISTS idx_evidence_cell_time ON evidence(correlation_cell, observed_at_ms);
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
 evidence_ids_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events_status_updated ON events(status, updated_at_ms);
CREATE TABLE IF NOT EXISTS alerts(
 alert_id TEXT PRIMARY KEY,
 event_id TEXT NOT NULL,
 event_version INTEGER NOT NULL,
 device_id TEXT NOT NULL,
 created_at_ms INTEGER NOT NULL,
 transport TEXT NOT NULL,
 status TEXT NOT NULL,
 UNIQUE(event_id,event_version,device_id)
);
CREATE TABLE IF NOT EXISTS scenario_runs(
 run_id TEXT PRIMARY KEY,
 scenario TEXT NOT NULL,
 source TEXT NOT NULL,
 mode TEXT NOT NULL,
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
CREATE TABLE IF NOT EXISTS scenario_stages(
 stage_id INTEGER PRIMARY KEY AUTOINCREMENT,
 run_id TEXT NOT NULL,
 occurred_at_ms INTEGER NOT NULL,
 code TEXT NOT NULL,
 component TEXT NOT NULL,
 severity TEXT NOT NULL,
 message TEXT NOT NULL,
 data_json TEXT NOT NULL,
 FOREIGN KEY(run_id) REFERENCES scenario_runs(run_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_scenario_stages_run ON scenario_stages(run_id,stage_id);
"""

class SQLiteRepository:
    def __init__(self, path: str | Path):
        self.path=str(path); Path(self.path).parent.mkdir(parents=True,exist_ok=True)
        self._lock=RLock()
        with self._connect() as c:
            c.executescript(SCHEMA)
            columns={row[1] for row in c.execute("PRAGMA table_info(evidence)")}
            if "scenario_run_id" not in columns:c.execute("ALTER TABLE evidence ADD COLUMN scenario_run_id TEXT")

    def _connect(self):
        c=sqlite3.connect(self.path, timeout=10); c.row_factory=sqlite3.Row; return c

    def update_device(self, device_id: str, seq: int, observed_at_ms: int, h3_cell: str, correlation_cell: str, transport: str, fcm_token: str|None=None) -> bool:
        with self._lock, self._connect() as c:
            row=c.execute("SELECT last_seq FROM devices WHERE device_id=?",(device_id,)).fetchone()
            if row and seq <= row["last_seq"]: return False
            c.execute("""INSERT INTO devices(device_id,h3_cell,correlation_cell,last_seen_ms,last_seq,transport,fcm_token)
                         VALUES(?,?,?,?,?,?,?) ON CONFLICT(device_id) DO UPDATE SET
                         h3_cell=excluded.h3_cell,correlation_cell=excluded.correlation_cell,last_seen_ms=excluded.last_seen_ms,
                         last_seq=excluded.last_seq,transport=excluded.transport,
                         fcm_token=COALESCE(excluded.fcm_token,devices.fcm_token)""",
                      (device_id,h3_cell,correlation_cell,observed_at_ms,seq,transport,fcm_token))
            return True

    def add_evidence(self, e: Evidence, bucket_ms: int=10_000, scenario_run_id: str|None=None) -> bool:
        with self._lock, self._connect() as c:
            try:
                c.execute("""INSERT INTO evidence(evidence_id,bucket,device_id,seq,observed_at_ms,h3_cell,correlation_cell,motion_rms,motion_peak,transport,scenario_run_id)
                             VALUES(?,?,?,?,?,?,?,?,?,?,?)""",(e.evidence_id,e.observed_at_ms//bucket_ms,e.device_id,e.seq,e.observed_at_ms,e.h3_cell,e.correlation_cell,e.motion_rms,e.motion_peak,e.transport,scenario_run_id))
            except sqlite3.IntegrityError: return False
            return True

    def recent_evidence(self, since_ms: int, scenario_run_id: str|None=None) -> list[Evidence]:
        with self._connect() as c:
            if scenario_run_id is None:
                rows=c.execute("SELECT * FROM evidence WHERE observed_at_ms>=? AND scenario_run_id IS NULL ORDER BY observed_at_ms",(since_ms,)).fetchall()
            else:
                rows=c.execute("SELECT * FROM evidence WHERE observed_at_ms>=? AND scenario_run_id=? ORDER BY observed_at_ms",(since_ms,scenario_run_id)).fetchall()
        return [Evidence(r["evidence_id"],r["device_id"],r["seq"],r["observed_at_ms"],r["h3_cell"],r["correlation_cell"],r["motion_rms"],r["motion_peak"],r["transport"]) for r in rows]

    def save_event(self, e: EventRecord) -> None:
        with self._lock, self._connect() as c:
            c.execute("""INSERT INTO events(event_id,status,created_at_ms,updated_at_ms,first_observed_at_ms,last_observed_at_ms,version,device_ids_json,footprint_json,frontier_json,evidence_ids_json)
                         VALUES(?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(event_id) DO UPDATE SET
                         status=excluded.status,updated_at_ms=excluded.updated_at_ms,last_observed_at_ms=excluded.last_observed_at_ms,
                         version=excluded.version,device_ids_json=excluded.device_ids_json,footprint_json=excluded.footprint_json,
                         frontier_json=excluded.frontier_json,evidence_ids_json=excluded.evidence_ids_json""",
                      (e.event_id,e.status.value,e.created_at_ms,e.updated_at_ms,e.first_observed_at_ms,e.last_observed_at_ms,e.version,
                       json.dumps(e.device_ids),json.dumps(e.detection_footprint),json.dumps(e.warning_frontier),json.dumps(e.evidence_ids)))

    def _event(self,r) -> EventRecord:
        return EventRecord(r["event_id"],EventStatus(r["status"]),r["created_at_ms"],r["updated_at_ms"],r["first_observed_at_ms"],r["last_observed_at_ms"],
                           json.loads(r["device_ids_json"]),json.loads(r["footprint_json"]),json.loads(r["frontier_json"]),json.loads(r["evidence_ids_json"]),r["version"])

    def active_events(self, since_ms: int) -> list[EventRecord]:
        with self._connect() as c:
            rows=c.execute("SELECT * FROM events WHERE status!='RESOLVED' AND updated_at_ms>=? ORDER BY updated_at_ms DESC",(since_ms,)).fetchall()
        return [self._event(r) for r in rows]

    def list_events(self, limit: int=100) -> list[EventRecord]:
        with self._connect() as c:
            rows=c.execute("SELECT * FROM events ORDER BY updated_at_ms DESC LIMIT ?",(limit,)).fetchall()
        return [self._event(r) for r in rows]

    def get_event(self,event_id:str) -> EventRecord|None:
        with self._connect() as c: r=c.execute("SELECT * FROM events WHERE event_id=?",(event_id,)).fetchone()
        return self._event(r) if r else None

    def resolve_stale(self, cutoff_ms: int, now_ms: int) -> int:
        with self._lock, self._connect() as c:
            cur=c.execute("UPDATE events SET status='RESOLVED',updated_at_ms=?,version=version+1 WHERE status='CONFIRMED' AND last_observed_at_ms<?",(now_ms,cutoff_ms))
            return cur.rowcount

    def target_devices(self, cells: Iterable[str], seen_after_ms: int) -> list[dict]:
        cells=list(set(cells))
        if not cells: return []
        q=",".join("?" for _ in cells)
        with self._connect() as c:
            rows=c.execute(f"SELECT * FROM devices WHERE correlation_cell IN ({q}) AND last_seen_ms>=?",(*cells,seen_after_ms)).fetchall()
        return [dict(r) for r in rows]

    def record_alert(self, event_id:str,event_version:int,device_id:str,created_at_ms:int,transport:str="local") -> bool:
        alert_id=f"{event_id}:{device_id}"
        with self._lock,self._connect() as c:
            try: c.execute("INSERT INTO alerts(alert_id,event_id,event_version,device_id,created_at_ms,transport,status) VALUES(?,?,?,?,?,?,?)",(alert_id,event_id,event_version,device_id,created_at_ms,transport,"DELIVERED_LOCAL"))
            except sqlite3.IntegrityError: return False
            return True

    def list_alerts(self,limit:int=200)->list[dict]:
        with self._connect() as c: rows=c.execute("SELECT * FROM alerts ORDER BY created_at_ms DESC LIMIT ?",(limit,)).fetchall()
        return [dict(r) for r in rows]

    def stats(self)->dict:
        with self._connect() as c:
            return {name:c.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0] for name in ("devices","evidence","events","alerts","scenario_runs","scenario_stages")}

    def create_scenario_run(self, run: dict) -> None:
        with self._lock, self._connect() as c:
            c.execute(
                """INSERT INTO scenario_runs(run_id,scenario,source,mode,seed,devices,status,expected_result,
                   observed_result,created_at_ms,started_at_ms,completed_at_ms,parameters_json,event_ids_json,error)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (run["run_id"],run["scenario"],run["source"],run["mode"],run["seed"],run["devices"],run["status"],
                 run["expected_result"],run.get("observed_result"),run["created_at_ms"],run.get("started_at_ms"),
                 run.get("completed_at_ms"),json.dumps(run.get("parameters",{}),sort_keys=True),
                 json.dumps(run.get("event_ids",[])),run.get("error")),
            )

    def update_scenario_run(self, run_id: str, **changes) -> None:
        allowed={"status","observed_result","started_at_ms","completed_at_ms","event_ids","error"}
        unknown=set(changes)-allowed
        if unknown: raise ValueError(f"unsupported scenario-run fields: {sorted(unknown)}")
        if not changes: return
        assignments=[];values=[]
        for key,value in changes.items():
            assignments.append(f"{'event_ids_json' if key=='event_ids' else key}=?")
            values.append(json.dumps(value) if key=="event_ids" else value)
        with self._lock,self._connect() as c:
            cur=c.execute(f"UPDATE scenario_runs SET {','.join(assignments)} WHERE run_id=?",(*values,run_id))
            if cur.rowcount != 1: raise KeyError(run_id)

    def add_scenario_stage(self, run_id: str, occurred_at_ms: int, code: str, component: str, severity: str, message: str, data: dict|None=None) -> int:
        with self._lock,self._connect() as c:
            cur=c.execute("INSERT INTO scenario_stages(run_id,occurred_at_ms,code,component,severity,message,data_json) VALUES(?,?,?,?,?,?,?)",
                          (run_id,occurred_at_ms,code,component,severity,message,json.dumps(data or {},sort_keys=True)))
            return int(cur.lastrowid)

    @staticmethod
    def _scenario_run(row) -> dict:
        out=dict(row);out["parameters"]=json.loads(out.pop("parameters_json"));out["event_ids"]=json.loads(out.pop("event_ids_json"));return out

    def list_scenario_runs(self, limit: int=50) -> list[dict]:
        with self._connect() as c: rows=c.execute("SELECT * FROM scenario_runs ORDER BY created_at_ms DESC LIMIT ?",(limit,)).fetchall()
        return [self._scenario_run(row) for row in rows]

    def get_scenario_run(self, run_id: str) -> dict|None:
        with self._connect() as c:
            row=c.execute("SELECT * FROM scenario_runs WHERE run_id=?",(run_id,)).fetchone()
            if not row:return None
            stages=c.execute("SELECT * FROM scenario_stages WHERE run_id=? ORDER BY stage_id",(run_id,)).fetchall()
        out=self._scenario_run(row);out["stages"]=[]
        for stage in stages:
            item=dict(stage);item["data"]=json.loads(item.pop("data_json"));out["stages"].append(item)
        return out
