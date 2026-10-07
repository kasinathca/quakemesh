from __future__ import annotations
from decimal import Decimal
from boto3.dynamodb.conditions import Key,Attr
from botocore.exceptions import ClientError
from .common import boto3,env,log,stream_image
from quakemesh_core.config import DetectionConfig
from quakemesh_core.geo import H3GeoIndex
from quakemesh_core.models import Evidence,EventRecord,EventStatus
from quakemesh_core.correlation import detect
from quakemesh_core.events import create_event,event_should_merge,merge_event

_ddb=boto3.resource("dynamodb");_geo=None

def geo():
    global _geo
    if _geo is None:_geo=H3GeoIndex()
    return _geo

def _evidence(item:dict)->Evidence:
    return Evidence(str(item["evidence_id"]),str(item["device_id"]),int(item["seq"]),int(item["observed_at_ms"]),str(item["h3_cell"]),str(item["correlation_cell"]),float(item["motion_rms"]),float(item["motion_peak"]),str(item["transport"]))

def _recent(now:int,cfg:DetectionConfig,provenance_type:str,scenario_run_id:str|None)->list[Evidence]:
    table=_ddb.Table(env("QM_EVIDENCE_TABLE"));out=[]
    first=(now-cfg.evidence_window_ms)//10_000;last=now//10_000
    partition=f"{provenance_type}#{scenario_run_id or '-'}"
    for b in range(first,last+1):
        kwargs={"KeyConditionExpression":Key("bucket").eq(f"{partition}#B#{b}"),"ConsistentRead":True}
        while True:
            resp=table.query(**kwargs)
            out.extend(_evidence(x) for x in resp.get("Items",[]) if int(x["observed_at_ms"])>=now-cfg.evidence_window_ms)
            lek=resp.get("LastEvaluatedKey")
            if not lek:break
            kwargs["ExclusiveStartKey"]=lek
    return out

def _event(item:dict)->EventRecord:
    return EventRecord(str(item["event_id"]),EventStatus(str(item["status"])),int(item["created_at_ms"]),int(item["updated_at_ms"]),int(item["first_observed_at_ms"]),int(item["last_observed_at_ms"]),list(item.get("device_ids",[])),list(item.get("detection_footprint",[])),list(item.get("warning_frontier",[])),list(item.get("evidence_ids",[])),int(item.get("version",1)),str(item.get("provenance_type","physical")),item.get("scenario_run_id"))

def _active(now:int,cfg:DetectionConfig,provenance_type:str,scenario_run_id:str|None)->list[EventRecord]:
    # Correctness-first V1: strongly consistent base-table scan avoids GSI propagation lag
    # immediately after event creation. This is intentionally small-scale and documented.
    t=_ddb.Table(env("QM_EVENT_TABLE"));out=[]
    provenance_filter=Attr("provenance_type").eq(provenance_type)
    run_filter=Attr("scenario_run_id").eq(scenario_run_id) if scenario_run_id else Attr("scenario_run_id").not_exists()
    kwargs={"FilterExpression":Attr("status").eq("CONFIRMED") & Attr("updated_at_ms").gte(now-cfg.event_merge_window_ms) & provenance_filter & run_filter,"ConsistentRead":True}
    while True:
        resp=t.scan(**kwargs);out.extend(_event(x) for x in resp.get("Items",[]))
        lek=resp.get("LastEvaluatedKey")
        if not lek:break
        kwargs["ExclusiveStartKey"]=lek
    return out

def _save(e:EventRecord,old_version:int|None):
    t=_ddb.Table(env("QM_EVENT_TABLE"));item=e.as_dict();item["session_id"]=env("QM_SESSION_ID")
    if item.get("scenario_run_id") is None:item.pop("scenario_run_id",None)
    if old_version is None:
        t.put_item(Item=item,ConditionExpression="attribute_not_exists(event_id)")
    else:
        try:t.put_item(Item=item,ConditionExpression="#v=:old",ExpressionAttributeNames={"#v":"version"},ExpressionAttributeValues={":old":old_version})
        except ClientError as ex:
            if ex.response.get("Error",{}).get("Code")=="ConditionalCheckFailedException":return False
            raise
    return True

def handler(event,context):
    cfg=DetectionConfig.from_env();changed=[]
    inserts=[]
    for rec in event.get("Records",[]):
        if rec.get("eventName")!="INSERT":continue
        image=rec.get("dynamodb",{}).get("NewImage")
        if image:inserts.append(stream_image(image))
    inserts.sort(key=lambda x:int(x.get("observed_at_ms",0)))
    for inserted in inserts:
        now=int(inserted["observed_at_ms"]);provenance_type=str(inserted.get("provenance_type","physical"));scenario_run_id=inserted.get("scenario_run_id");decision=detect(_recent(now,cfg,provenance_type,scenario_run_id),now,geo(),cfg)
        log("CORRELATION_EVALUATED",device_id=inserted.get("device_id"),evidence_id=inserted.get("evidence_id"),provenance_type=provenance_type,scenario_run_id=scenario_run_id,confirmed=decision.confirmed,distinct_devices=len(decision.device_ids),distinct_cells=len(decision.cells))
        if not decision.confirmed:continue
        active=_active(now,cfg,provenance_type,scenario_run_id);existing=next((x for x in active if event_should_merge(x,decision,geo(),cfg)),None)
        if existing:
            old=existing.version;event_obj=merge_event(existing,decision,now,geo(),cfg)
            if event_obj.version==old:continue
            if _save(event_obj,old):changed.append(event_obj.event_id)
        else:
            event_obj=create_event(decision,now,geo(),cfg)
            event_obj.provenance_type=provenance_type;event_obj.scenario_run_id=scenario_run_id
            event_obj.event_id=f"{provenance_type}#{scenario_run_id or '-'}#{event_obj.event_id}"
            try:
                if _save(event_obj,None):changed.append(event_obj.event_id)
            except ClientError as ex:
                if ex.response.get("Error",{}).get("Code")!="ConditionalCheckFailedException":raise
    for event_id in changed:log("EVENT_TRANSITIONED",event_id=event_id)
    return {"changed_events":changed}
