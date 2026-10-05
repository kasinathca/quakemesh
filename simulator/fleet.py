from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor,as_completed
from dataclasses import asdict
import json,math,random,time
from pathlib import Path
from .models import VirtualPhone
from .transports import Transport

class Fleet:
    def __init__(self,phones:list[VirtualPhone],transport:Transport,seed:int=42,trace_path:str|Path|None=None):
        self.phones=phones;self.transport=transport;self.rng=random.Random(seed);self.trace=[];self.trace_path=Path(trace_path) if trace_path else None

    @staticmethod
    def around(count:int,center_lat:float,center_lon:float,spacing_deg:float=.012,device_prefix:str="QM-SIM")->list[VirtualPhone]:
        side=math.ceil(math.sqrt(count)); phones=[]
        for i in range(count):
            row,col=divmod(i,side)
            lat=center_lat+(row-(side-1)/2)*spacing_deg
            lon=center_lon+(col-(side-1)/2)*spacing_deg
            phones.append(VirtualPhone(f"{device_prefix}-{i+1:04d}",lat,lon))
        return phones

    def _record(self,kind:str,device:VirtualPhone,payload:dict,result:dict|None,error:str|None,truth:dict|None=None):
        row={"trace_time_ms":int(time.time()*1000),"kind":kind,"device_id":device.device_id,"payload":payload,"result":result,"error":error}
        if truth is not None: row["simulator_truth"]=truth
        self.trace.append(row)

    def _send_heartbeat(self,p:VirtualPhone,ts:int):
        payload={"schema_version":"1.0","device_id":p.device_id,"seq":p.next_seq(),"observed_at_ms":ts,"latitude":p.latitude,"longitude":p.longitude}
        try:r=self.transport.heartbeat(p.device_id,payload);self._record("heartbeat",p,payload,r,None)
        except Exception as e:self._record("heartbeat",p,payload,None,repr(e))

    def heartbeat_all(self,ts:int|None=None,workers:int=16):
        ts=ts or int(time.time()*1000)
        with ThreadPoolExecutor(max_workers=workers) as ex:
            list(ex.map(lambda p:self._send_heartbeat(p,ts),self.phones))
        self.flush_trace()

    def trigger_devices(self,indices:list[int],base_ts:int|None=None,packet_loss:float=0.0,jitter_ms:int=0,truth_label:str="synthetic_distributed_motion"):
        # Physical propagation affects when a device observes motion. Network jitter
        # affects only delivery time. When no base time is supplied, shift the first
        # synthetic observation into the recent past so the last observation is not
        # stamped in the future while jobs are dispatched concurrently.
        max_propagation=max(0,len(indices)-1)*70
        if base_ts is None:
            base_ts=int(time.time()*1000)-max_propagation
        jobs=[]
        for ordinal,i in enumerate(indices):
            p=self.phones[i]
            propagation_ms=ordinal*70
            network_delay_ms=self.rng.randint(0,jitter_ms) if jitter_ms else 0
            hidden={"scenario":truth_label,"injected":True,"ordinal":ordinal,"propagation_ms":propagation_ms,"network_delay_ms":network_delay_ms}
            if self.rng.random()<packet_loss:
                self._record("trigger_dropped_by_simulator",p,{},None,None,hidden);continue
            ts=base_ts+propagation_ms
            rms=round(self.rng.uniform(1.0,1.8),4);peak=round(self.rng.uniform(2.0,3.2),4)
            payload={"schema_version":"1.0","device_id":p.device_id,"seq":p.next_seq(),"observed_at_ms":ts,"latitude":p.latitude,"longitude":p.longitude,"motion_rms":rms,"motion_peak":peak}
            jobs.append((p,payload,hidden,network_delay_ms))
        def send(job):
            p,payload,hidden,network_delay_ms=job
            if network_delay_ms:
                time.sleep(network_delay_ms/1000.0)
            try:r=self.transport.trigger(p.device_id,payload);self._record("trigger",p,payload,r,None,hidden)
            except Exception as e:self._record("trigger",p,payload,None,repr(e),hidden)
        with ThreadPoolExecutor(max_workers=min(32,max(1,len(jobs)))) as ex:list(ex.map(send,jobs))
        self.flush_trace()

    def scenario(self,name:str):
        self.heartbeat_all()
        if name=="isolated": self.trigger_devices([0],truth_label="isolated_false_positive")
        elif name=="same-cell":
            # Same coordinates are intentionally forced for this negative scenario.
            anchor=(self.phones[0].latitude,self.phones[0].longitude)
            original=[(p.latitude,p.longitude) for p in self.phones[:6]]
            try:
                for p in self.phones[:6]:p.latitude,p.longitude=anchor
                self.trigger_devices(list(range(min(6,len(self.phones)))),truth_label="same_cell_negative")
            finally:
                for p,pos in zip(self.phones[:6],original):p.latitude,p.longitude=pos
        elif name=="distributed": self.trigger_devices(list(range(min(8,len(self.phones)))),truth_label="distributed_positive")
        elif name=="degraded": self.trigger_devices(list(range(min(16,len(self.phones)))),packet_loss=.25,jitter_ms=900,truth_label="distributed_degraded_network")
        else: raise ValueError(f"unknown scenario: {name}")


    def collect_transport_alerts(self) -> int:
        drain=getattr(self.transport,"drain_alerts",None)
        if not callable(drain):return 0
        alerts=drain();known={p.device_id:p for p in self.phones}
        for alert in alerts:
            device_id=str(alert.get("device_id","unknown"));device=known.get(device_id)
            self.trace.append({
                "trace_time_ms":int(alert.get("received_at_ms",time.time()*1000)),
                "kind":"alert_received",
                "device_id":device_id,
                "payload":alert.get("payload",{}),
                "result":{"topic":alert.get("topic"),"dup":bool(alert.get("dup",False))},
                "error":None,
            })
        self.flush_trace();return len(alerts)

    def flush_trace(self):
        if self.trace_path:
            self.trace_path.parent.mkdir(parents=True,exist_ok=True)
            self.trace_path.write_text(json.dumps({"trace_schema":"1.0","records":self.trace},indent=2),encoding="utf-8")
