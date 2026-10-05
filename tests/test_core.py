from quakemesh_core.config import DetectionConfig
from quakemesh_core.geo import SyntheticGeoIndex
from quakemesh_core.models import TelemetryTrigger
from quakemesh_core.correlation import canonicalize_trigger, detect, warning_frontier, stable_event_key
from quakemesh_core.events import create_event, merge_event
from quakemesh_core.validation import parse_trigger, ValidationError
from quakemesh_core.motion import extract_motion_features, passes_motion_gate


def cfg(**kw):
    base=DetectionConfig(h3_device_resolution=7,h3_correlation_resolution=7,min_devices=4,min_distinct_cells=3,max_cluster_grid_distance=4,warning_ring_k=1)
    return DetectionConfig(**{**base.__dict__, **kw})

def ev(dev, seq, ts, lat, lon):
    t=TelemetryTrigger("1.0",dev,seq,ts,lat,lon,1.2,2.2,"test")
    return canonicalize_trigger(t,SyntheticGeoIndex(),cfg())

def test_positive_confirmation():
    g=SyntheticGeoIndex(); c=cfg()
    evidence=[ev("dev1",1,1000,12.0,77.0),ev("dev2",1,1200,12.01,77.01),ev("dev3",1,1400,12.02,77.02),ev("dev4",1,1600,12.03,77.03)]
    d=detect(evidence,2000,g,c)
    assert d.confirmed and len(d.device_ids)==4 and len(d.cells)>=3

def test_same_cell_rejected():
    g=SyntheticGeoIndex(); c=cfg()
    evidence=[ev(f"dev{i}",1,1000+i,12.0,77.0) for i in range(1,6)]
    d=detect(evidence,2000,g,c)
    assert not d.confirmed and "spatial" in d.reason

def test_isolated_device_rejected():
    d=detect([ev("dev1",1,1000,12,77)],1500,SyntheticGeoIndex(),cfg())
    assert not d.confirmed and "devices" in d.reason

def test_duplicate_device_does_not_inflate():
    e=[ev("dev1",1,1000,12,77),ev("dev1",2,1100,12.01,77.01),ev("dev2",1,1200,12.02,77.02),ev("dev3",1,1300,12.03,77.03)]
    d=detect(e,1500,SyntheticGeoIndex(),cfg())
    assert not d.confirmed
    assert len(d.device_ids)==3

def test_stale_evidence_ignored():
    d=detect([ev("dev1",1,1000,12,77),ev("dev2",1,1100,12.01,77.01),ev("dev3",1,1200,12.02,77.02),ev("dev4",1,1300,12.03,77.03)],20000,SyntheticGeoIndex(),cfg(evidence_window_ms=1000))
    assert not d.confirmed

def test_distant_components_do_not_mix():
    g=SyntheticGeoIndex(); c=cfg(max_cluster_grid_distance=2,min_devices=3,min_distinct_cells=3)
    evidence=[ev("dev1",1,1000,0,0),ev("dev2",1,1050,0.01,0.01),ev("dev3",1,1100,50,50),ev("dev4",1,1150,50.01,50.01)]
    assert not detect(evidence,1500,g,c).confirmed

def test_frontier_excludes_footprint():
    g=SyntheticGeoIndex(); cells=["g7:100:100","g7:101:100"]
    f=warning_frontier(cells,g,1)
    assert not set(f)&set(cells) and len(f)>0

def test_event_creation_and_merge_version():
    g=SyntheticGeoIndex(); c=cfg(min_devices=3,min_distinct_cells=3)
    e1=[ev("dev1",1,1000,12,77),ev("dev2",1,1100,12.01,77.01),ev("dev3",1,1200,12.02,77.02)]
    d1=detect(e1,1500,g,c); event=create_event(d1,1500,g,c)
    e2=e1+[ev("dev4",1,1300,12.03,77.03)]
    d2=detect(e2,1600,g,c); merge_event(event,d2,1600,g,c)
    assert event.version==2 and "dev4" in event.device_ids

def test_stable_event_key_repeatable():
    g=SyntheticGeoIndex(); c=cfg(min_devices=3,min_distinct_cells=3)
    d=detect([ev("dev1",1,1000,12,77),ev("dev2",1,1100,12.01,77.01),ev("dev3",1,1200,12.02,77.02)],1500,g,c)
    assert stable_event_key(d)==stable_event_key(d)

def test_validation_bounds():
    try:
        parse_trigger({"schema_version":"1.0","device_id":"dev1","seq":1,"observed_at_ms":1,"latitude":100,"longitude":0,"motion_rms":1,"motion_peak":2})
        assert False
    except ValidationError:
        pass

def test_motion_gate():
    c=cfg(motion_rms_threshold=.5,motion_peak_threshold=1.0)
    samples=[(0,0,9.80665),(0,0,12.0),(0,0,7.0),(0,0,11.0)]
    assert passes_motion_gate(extract_motion_features(samples),c)


def test_merge_event_replay_is_noop_without_new_evidence():
    from quakemesh_core.events import create_event, merge_event
    from quakemesh_core.correlation import detect
    from quakemesh_core.models import Evidence
    from quakemesh_core.config import DetectionConfig
    from quakemesh_core.geo import SyntheticGeoIndex

    geo = SyntheticGeoIndex()
    cfg = DetectionConfig(min_devices=4, min_distinct_cells=3)
    now = 10_000
    evidence = [
        Evidence(f"e{i}", f"device-{i}", 1, now - i, f"R9:{i}:0", f"R7:{i}:0", 2.0, 3.0, "test")
        for i in range(4)
    ]
    decision = detect(evidence, now, geo, cfg)
    event = create_event(decision, now, geo, cfg)
    before = event.as_dict().copy()
    merged = merge_event(event, decision, now + 1000, geo, cfg)
    assert merged.as_dict() == before

def test_validation_rejects_nonfinite_numbers():
    import math
    bad={"schema_version":"1.0","device_id":"dev1","seq":1,"observed_at_ms":1,"latitude":math.nan,"longitude":0,"motion_rms":1,"motion_peak":2}
    try:
        parse_trigger(bad)
    except ValidationError as exc:
        assert "finite" in str(exc)
    else:
        raise AssertionError("non-finite coordinate accepted")


def test_observation_clock_skew_guard():
    from quakemesh_core.validation import validate_observation_time
    validate_observation_time(1000, 1100, 200)
    try:
        validate_observation_time(1000, 1500, 200)
    except ValidationError as exc:
        assert "clock-skew" in str(exc)
    else:
        raise AssertionError("stale timestamp accepted")

def test_runtime_validation_matches_closed_json_contract():
    base={"schema_version":"1.0","device_id":"dev1","seq":1,"observed_at_ms":1,"latitude":12.0,"longitude":77.0,"motion_rms":1.0,"motion_peak":2.0}
    for mutate in (
        lambda x: x.update(extra="nope"),
        lambda x: x.update(seq=1.5),
        lambda x: x.update(latitude="12.0"),
        lambda x: x.update(device_id=1234),
    ):
        payload=dict(base); mutate(payload)
        try:
            parse_trigger(payload)
        except ValidationError:
            pass
        else:
            raise AssertionError(f"invalid payload accepted: {payload}")
