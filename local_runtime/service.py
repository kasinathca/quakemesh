from __future__ import annotations

from dataclasses import asdict
from threading import RLock
from quakemesh_core.config import DetectionConfig
from quakemesh_core.correlation import canonicalize_trigger, detect
from quakemesh_core.events import create_event, event_should_merge, merge_event
from quakemesh_core.motion import MotionFeatures, passes_motion_gate
from quakemesh_core.geo import GeoIndex
from quakemesh_core.validation import parse_trigger, parse_heartbeat, validate_observation_time
from .repository import SQLiteRepository

class QuakeMeshService:
    def __init__(self, repo: SQLiteRepository, geo: GeoIndex, config: DetectionConfig):
        self.repo=repo; self.geo=geo; self.config=config; self._correlation_lock=RLock()

    def heartbeat(self,payload:dict,transport:str="http",received_at_ms:int|None=None) -> dict:
        h=parse_heartbeat(payload,transport)
        if received_at_ms is not None:
            validate_observation_time(h.observed_at_ms, received_at_ms, self.config.max_clock_skew_ms)
        cell=self.geo.cell(h.latitude,h.longitude,self.config.h3_device_resolution)
        coarse=self.geo.parent(cell,self.config.h3_correlation_resolution)
        accepted=self.repo.update_device(h.device_id,h.seq,h.observed_at_ms,cell,coarse,transport,h.fcm_token)
        return {"accepted":accepted,"device_id":h.device_id,"h3_cell":cell,"correlation_cell":coarse}

    def _stage(self,run_id:str|None,at_ms:int,code:str,message:str,data:dict|None=None,severity:str="info") -> None:
        if run_id:self.repo.add_scenario_stage(run_id,at_ms,code,"local-runtime",severity,message,data)

    def trigger(self,payload:dict,transport:str="http",received_at_ms:int|None=None,run_id:str|None=None)->dict:
        t=parse_trigger(payload,transport)
        now=t.observed_at_ms if received_at_ms is None else received_at_ms
        if received_at_ms is not None:
            validate_observation_time(t.observed_at_ms, received_at_ms, self.config.max_clock_skew_ms)
        self._stage(run_id,now,"SCHEMA_VALIDATED","Trigger schema and observation time accepted",{"device_id":t.device_id})
        e=canonicalize_trigger(t,self.geo,self.config)

        # FastAPI runs sync endpoints in a worker pool. Keep evidence acceptance,
        # correlation and authoritative event mutation in one local critical section
        # so concurrent simulator requests cannot manufacture duplicate events.
        with self._correlation_lock:
            state_accepted=self.repo.update_device(e.device_id,e.seq,e.observed_at_ms,e.h3_cell,e.correlation_cell,transport)
            if not state_accepted:
                return {"accepted":False,"duplicate_or_replay":True,"evidence_id":e.evidence_id}
            if not passes_motion_gate(MotionFeatures(e.motion_rms,e.motion_peak,1), self.config):
                self._stage(run_id,now,"MOTION_GATE_EVALUATED","Motion gate failed",{"passed":False,"device_id":e.device_id})
                return {"accepted":False,"below_motion_gate":True,"evidence_id":e.evidence_id}
            self._stage(run_id,now,"MOTION_GATE_EVALUATED","Motion gate passed",{"passed":True,"device_id":e.device_id})
            evidence_accepted=self.repo.add_evidence(e,scenario_run_id=run_id)
            if not evidence_accepted:
                return {"accepted":False,"duplicate_or_replay":True,"evidence_id":e.evidence_id}
            self._stage(run_id,now,"EVIDENCE_STORED","Evidence stored",{"evidence_id":e.evidence_id,"correlation_cell":e.correlation_cell})
            recent=self.repo.recent_evidence(now-self.config.evidence_window_ms,run_id)
            decision=detect(recent,now,self.geo,self.config)
            self._stage(run_id,now,"CORRELATION_EVALUATED",decision.reason,{"confirmed":decision.confirmed,"device_count":len(decision.device_ids),"cell_count":len(decision.cells),"required_devices":self.config.min_devices,"required_cells":self.config.min_distinct_cells})
            response={"accepted":True,"evidence_id":e.evidence_id,"decision":asdict(decision)}
            if not decision.confirmed:
                return response
            active=self.repo.active_events(now-self.config.event_merge_window_ms)
            event=next((x for x in active if event_should_merge(x,decision,self.geo,self.config)),None)
            if event:
                event=merge_event(event,decision,now,self.geo,self.config)
            else:
                event=create_event(decision,now,self.geo,self.config)
            self.repo.save_event(event)
            self._stage(run_id,now,"EVENT_TRANSITIONED","Experimental event confirmed",{"event_id":event.event_id,"version":event.version})
            target_cells=set(event.detection_footprint)|set(event.warning_frontier)
            targets=self.repo.target_devices(target_cells,now-120_000)
            newly_alerted=[]
            for device in targets:
                if self.repo.record_alert(event.event_id,event.version,device["device_id"],now):
                    newly_alerted.append(device["device_id"])
            response["event"]=event.as_dict(); response["new_alert_devices"]=newly_alerted
            return response

    def resolve(self,now_ms:int)->int:
        return self.repo.resolve_stale(now_ms-self.config.event_resolve_after_ms,now_ms)
