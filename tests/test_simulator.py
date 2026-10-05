from simulator.fleet import Fleet

class Capture:
    def __init__(self):self.messages=[]
    def heartbeat(self,d,p):self.messages.append(("h",d,p));return {"ok":1}
    def trigger(self,d,p):self.messages.append(("t",d,p));return {"ok":1}
    def close(self):pass

def test_fleet_truth_not_in_payload():
    c=Capture();f=Fleet(Fleet.around(10,12,77),c,seed=1);f.scenario("distributed")
    triggers=[p for k,d,p in c.messages if k=="t"]
    assert triggers and all("scenario" not in p and "simulator_truth" not in p for p in triggers)
    assert any("simulator_truth" in row for row in f.trace if row["kind"]=="trigger")

def test_degraded_injects_loss_deterministically():
    c=Capture();f=Fleet(Fleet.around(20,12,77),c,seed=42);f.scenario("degraded")
    drops=[x for x in f.trace if x["kind"]=="trigger_dropped_by_simulator"]
    assert len(drops)>0

def test_device_ids_unique():
    ps=Fleet.around(100,12,77);assert len({p.device_id for p in ps})==100

def test_default_trigger_timestamps_are_not_future_dated():
    import time
    c=Capture();f=Fleet(Fleet.around(8,12,77),c,seed=7)
    before=int(time.time()*1000)
    f.trigger_devices(list(range(8)))
    after=int(time.time()*1000)
    observed=[p["observed_at_ms"] for k,d,p in c.messages if k=="t"]
    assert observed and max(observed) <= after + 20
    assert min(observed) >= before - 1000


def test_network_jitter_is_trace_truth_not_observation_timestamp():
    c=Capture();f=Fleet(Fleet.around(3,12,77),c,seed=3)
    base=1_000_000
    f.trigger_devices([0,1,2],base_ts=base,jitter_ms=5)
    rows=[r for r in f.trace if r["kind"]=="trigger"]
    assert [r["payload"]["observed_at_ms"] for r in rows] != []
    assert all((r["payload"]["observed_at_ms"]-base)%70==0 for r in rows)
    assert all("network_delay_ms" in r["simulator_truth"] for r in rows)
