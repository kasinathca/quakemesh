import sqlite3

from quakemesh_core.config import DetectionConfig
from quakemesh_core.geo import SyntheticGeoIndex
from local_runtime.repository import SQLiteRepository
from local_runtime.service import QuakeMeshService


def test_repository_migrates_legacy_tables_before_creating_v2_indexes(tmp_path):
    database = tmp_path / "legacy.db"
    with sqlite3.connect(database) as connection:
        connection.executescript(
            """
            CREATE TABLE evidence(
              evidence_id TEXT PRIMARY KEY, bucket INTEGER NOT NULL,
              device_id TEXT NOT NULL, seq INTEGER NOT NULL,
              observed_at_ms INTEGER NOT NULL, h3_cell TEXT NOT NULL,
              correlation_cell TEXT NOT NULL, motion_rms REAL NOT NULL,
              motion_peak REAL NOT NULL, transport TEXT NOT NULL
            );
            """
        )
    SQLiteRepository(database)
    with sqlite3.connect(database) as connection:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(evidence)")}
        indexes = {row[1] for row in connection.execute("PRAGMA index_list(evidence)")}
    assert "scenario_run_id" in columns
    assert "idx_evidence_run_time" in indexes


def cfg(): return DetectionConfig(h3_device_resolution=7,h3_correlation_resolution=7,min_devices=4,min_distinct_cells=3,max_cluster_grid_distance=4,evidence_window_ms=8000)

def payload(dev,seq,ts,lat,lon,rms=1.2,peak=2.2): return {"schema_version":"1.0","device_id":dev,"seq":seq,"observed_at_ms":ts,"latitude":lat,"longitude":lon,"motion_rms":rms,"motion_peak":peak}

def test_sqlite_end_to_end(tmp_path):
    repo=SQLiteRepository(tmp_path/"qm.db"); svc=QuakeMeshService(repo,SyntheticGeoIndex(),cfg())
    base=1_000_000
    coords=[(12,77),(12.01,77.01),(12.02,77.02),(12.03,77.03)]
    for i,(lat,lon) in enumerate(coords):
        svc.heartbeat({"schema_version":"1.0","device_id":f"dev{i}","seq":0,"observed_at_ms":base-100,"latitude":lat,"longitude":lon})
    out=None
    for i,(lat,lon) in enumerate(coords): out=svc.trigger(payload(f"dev{i}",1,base+i*100,lat,lon),received_at_ms=base+i*100)
    assert out and "event" in out
    assert repo.stats()["events"]==1 and repo.stats()["evidence"]==4
    assert repo.list_events()[0].status.value=="CONFIRMED"

def test_replay_rejected(tmp_path):
    svc=QuakeMeshService(SQLiteRepository(tmp_path/"q.db"),SyntheticGeoIndex(),cfg())
    p=payload("dev1",1,1000,12,77)
    assert svc.trigger(p,received_at_ms=1000)["accepted"]
    assert not svc.trigger(p,received_at_ms=1001)["accepted"]

def test_raw_coordinates_not_persisted(tmp_path):
    repo=SQLiteRepository(tmp_path/"q.db"); svc=QuakeMeshService(repo,SyntheticGeoIndex(),cfg())
    svc.trigger(payload("dev1",1,1000,12.123456,77.654321),received_at_ms=1000)
    import sqlite3
    with sqlite3.connect(repo.path) as c:
        cols=[x[1] for x in c.execute("PRAGMA table_info(evidence)")]
        assert "latitude" not in cols and "longitude" not in cols

def test_below_motion_gate_is_not_evidence(tmp_path):
    repo=SQLiteRepository(tmp_path/"q.db"); svc=QuakeMeshService(repo,SyntheticGeoIndex(),cfg())
    p=payload("dev-low",1,1000,12,77,rms=0.01,peak=0.02)
    out=svc.trigger(p,received_at_ms=1000)
    assert not out["accepted"] and out["below_motion_gate"]
    assert repo.stats()["devices"]==1 and repo.stats()["evidence"]==0


def test_local_runtime_rejects_excessive_clock_skew(tmp_path):
    repo=SQLiteRepository(tmp_path/"q.db"); svc=QuakeMeshService(repo,SyntheticGeoIndex(),cfg())
    p=payload("dev-old",1,1000,12,77)
    try:
        svc.trigger(p,received_at_ms=1_000_000)
    except Exception as exc:
        assert "clock-skew" in str(exc)
    else:
        raise AssertionError("excessively stale observation accepted")

def test_concurrent_triggers_create_one_authoritative_event(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    repo=SQLiteRepository(tmp_path/"concurrent.db")
    svc=QuakeMeshService(repo,SyntheticGeoIndex(),cfg())
    base=1_000_000
    coords=[(12+i*.01,77+i*.01) for i in range(8)]
    for i,(lat,lon) in enumerate(coords):
        svc.heartbeat({"schema_version":"1.0","device_id":f"dev{i}","seq":0,"observed_at_ms":base-100,"latitude":lat,"longitude":lon})
    def send(i):
        lat,lon=coords[i]
        ts=base+i*10
        return svc.trigger(payload(f"dev{i}",1,ts,lat,lon),received_at_ms=ts)
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(send,range(8)))
    events=repo.list_events()
    assert len(events)==1
    assert len(events[0].device_ids)==8
