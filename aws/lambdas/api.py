from __future__ import annotations
import json
from decimal import Decimal
from .common import boto3,env,json_response
from .ingress import process
from quakemesh_core.validation import ValidationError
from quakemesh_core.geo import H3GeoIndex
_geo=None
def _geo_index():
    global _geo
    if _geo is None:_geo=H3GeoIndex()
    return _geo

def _event_view(row):
    row=_clean(row);g=_geo_index()
    row["footprint_polygons"]=[{"cell":c,"boundary":g.boundary(c)} for c in row.get("detection_footprint",[])]
    row["frontier_polygons"]=[{"cell":c,"boundary":g.boundary(c)} for c in row.get("warning_frontier",[])]
    return row

def _clean(v):
    if isinstance(v,Decimal):return int(v) if v%1==0 else float(v)
    if isinstance(v,list):return [_clean(x) for x in v]
    if isinstance(v,dict):return {k:_clean(x) for k,x in v.items()}
    return v

def handler(event,context):
    method=event.get("httpMethod","");path=event.get("path","")
    try:
        if method=="GET" and path=="/health":return json_response(200,{"status":"ok","mode":"aws"})
        if method=="POST" and path in {"/v1/devices/heartbeat","/v1/evidence/trigger"}:
            body=json.loads(event.get("body") or "{}")
            kind="heartbeat" if path.endswith("heartbeat") else "trigger"
            return json_response(200,process(body,kind,None,"aws-https"))
        if method=="GET" and path=="/v1/events":
            t=boto3.resource("dynamodb").Table(env("QM_EVENT_TABLE"));rows=t.scan(Limit=100).get("Items",[]);rows.sort(key=lambda x:int(x.get("updated_at_ms",0)),reverse=True)
            return json_response(200,{"items":[_event_view(x) for x in rows]})
        if method=="GET" and path=="/v1/alerts":
            t=boto3.resource("dynamodb").Table(env("QM_ALERT_TABLE"));rows=t.scan(Limit=200).get("Items",[]);rows.sort(key=lambda x:int(x.get("created_at_ms",0)),reverse=True)
            return json_response(200,{"items":_clean(rows)})
        return json_response(404,{"error":"not found"})
    except (ValidationError,ValueError,json.JSONDecodeError) as e:return json_response(400,{"error":str(e)})
