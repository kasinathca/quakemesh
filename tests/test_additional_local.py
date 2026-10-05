from local_runtime.repository import SQLiteRepository
from local_runtime.service import QuakeMeshService
from quakemesh_core.config import DetectionConfig
from quakemesh_core.geo import SyntheticGeoIndex

def c():return DetectionConfig(h3_device_resolution=7,h3_correlation_resolution=7,min_devices=3,min_distinct_cells=3,max_cluster_grid_distance=4,event_resolve_after_ms=1000)
def t(dev,seq,ts,lat,lon):return {"schema_version":"1.0","device_id":dev,"seq":seq,"observed_at_ms":ts,"latitude":lat,"longitude":lon,"motion_rms":1.2,"motion_peak":2.2}

def make_event(svc,base=10000):
    out=None
    for i,(lat,lon) in enumerate([(12,77),(12.01,77.01),(12.02,77.02)]):out=svc.trigger(t(f"dev{i}",1,base+i*100,lat,lon),received_at_ms=base+i*100)
    return out

def test_event_resolves_after_inactivity(tmp_path):
    repo=SQLiteRepository(tmp_path/"q.db");svc=QuakeMeshService(repo,SyntheticGeoIndex(),c());make_event(svc)
    assert svc.resolve(12000)==1 and repo.list_events()[0].status.value=="RESOLVED"

def test_alert_is_once_per_event_device_even_after_version(tmp_path):
    repo=SQLiteRepository(tmp_path/"q.db");svc=QuakeMeshService(repo,SyntheticGeoIndex(),c());out=make_event(svc);e=repo.list_events()[0]
    assert repo.record_alert(e.event_id,e.version,"extra",20000)
    assert not repo.record_alert(e.event_id,e.version+1,"extra",21000)

def test_heartbeat_does_not_create_evidence(tmp_path):
    repo=SQLiteRepository(tmp_path/"q.db");svc=QuakeMeshService(repo,SyntheticGeoIndex(),c())
    svc.heartbeat({"schema_version":"1.0","device_id":"devx","seq":1,"observed_at_ms":1000,"latitude":12,"longitude":77})
    assert repo.stats()["devices"]==1 and repo.stats()["evidence"]==0
