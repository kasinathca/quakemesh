from __future__ import annotations
import os,time
from botocore.exceptions import ClientError
from .common import boto3,env
from quakemesh_core.config import DetectionConfig
from quakemesh_core.geo import H3GeoIndex
from quakemesh_core.validation import parse_trigger,parse_heartbeat,ValidationError,validate_observation_time
from quakemesh_core.correlation import canonicalize_trigger
from quakemesh_core.motion import MotionFeatures,passes_motion_gate

_ddb=boto3.resource("dynamodb");_sns=boto3.client("sns")
_geo=None

def geo():
    global _geo
    if _geo is None:_geo=H3GeoIndex()
    return _geo

def _topic_identity(topic:str,expected_kind:str)->str:
    parts=topic.split('/')
    if len(parts)!=5 or parts[:3]!=["quakemesh","v1","devices"] or parts[4]!=expected_kind: raise ValidationError("invalid IoT topic")
    return parts[3]

def _register_fcm(token:str|None)->str|None:
    app=os.getenv("QM_SNS_PLATFORM_APPLICATION_ARN")
    if not token or not app:return None
    out=_sns.create_platform_endpoint(PlatformApplicationArn=app,Token=token)
    return out["EndpointArn"]

def _update_device(*,device_id:str,seq:int,observed_at_ms:int,cell:str,coarse:str,transport:str,fcm_endpoint_arn:str|None=None)->bool:
    table=_ddb.Table(env("QM_DEVICE_TABLE"))
    names={"#ls":"last_seq"}; vals={":s":seq,":ts":observed_at_ms,":c":cell,":cc":coarse,":tr":transport}
    update="SET #ls=:s,last_seen_ms=:ts,h3_cell=:c,correlation_cell=:cc,transport=:tr"
    if fcm_endpoint_arn:
        update+=",fcm_endpoint_arn=:fcm";vals[":fcm"]=fcm_endpoint_arn
    try:
        table.update_item(Key={"device_id":device_id},UpdateExpression=update,ExpressionAttributeNames=names,ExpressionAttributeValues=vals,ConditionExpression="attribute_not_exists(#ls) OR #ls < :s")
        return True
    except ClientError as e:
        if e.response.get("Error",{}).get("Code")=="ConditionalCheckFailedException":return False
        raise

def _heartbeat(payload:dict,topic:str|None,transport:str)->dict:
    h=parse_heartbeat(payload,transport)
    if topic and _topic_identity(topic,"heartbeat")!=h.device_id: raise ValidationError("topic/device identity mismatch")
    cfg=DetectionConfig.from_env();validate_observation_time(h.observed_at_ms,int(time.time()*1000),cfg.max_clock_skew_ms);cell=geo().cell(h.latitude,h.longitude,cfg.h3_device_resolution);coarse=geo().parent(cell,cfg.h3_correlation_resolution)
    fcm=_register_fcm(h.fcm_token)
    accepted=_update_device(device_id=h.device_id,seq=h.seq,observed_at_ms=h.observed_at_ms,cell=cell,coarse=coarse,transport=transport,fcm_endpoint_arn=fcm)
    return {"accepted":accepted,"device_id":h.device_id,"h3_cell":cell,"correlation_cell":coarse}

def _trigger(payload:dict,topic:str|None,transport:str)->dict:
    t=parse_trigger(payload,transport)
    if topic and _topic_identity(topic,"trigger")!=t.device_id: raise ValidationError("topic/device identity mismatch")
    cfg=DetectionConfig.from_env();validate_observation_time(t.observed_at_ms,int(time.time()*1000),cfg.max_clock_skew_ms);e=canonicalize_trigger(t,geo(),cfg)
    if not _update_device(device_id=e.device_id,seq=e.seq,observed_at_ms=e.observed_at_ms,cell=e.h3_cell,coarse=e.correlation_cell,transport=transport):
        return {"accepted":False,"duplicate_or_replay":True,"evidence_id":e.evidence_id}
    if not passes_motion_gate(MotionFeatures(e.motion_rms,e.motion_peak,1),cfg):
        return {"accepted":False,"below_motion_gate":True,"evidence_id":e.evidence_id}
    bucket=e.observed_at_ms//10_000;ttl=int(time.time())+cfg.evidence_ttl_seconds
    item={"bucket":f"B#{bucket}","evidence_id":e.evidence_id,"device_id":e.device_id,"seq":e.seq,"observed_at_ms":e.observed_at_ms,"h3_cell":e.h3_cell,"correlation_cell":e.correlation_cell,"motion_rms":str(e.motion_rms),"motion_peak":str(e.motion_peak),"transport":e.transport,"ttl":ttl}
    try:_ddb.Table(env("QM_EVIDENCE_TABLE")).put_item(Item=item,ConditionExpression="attribute_not_exists(evidence_id)")
    except ClientError as ex:
        if ex.response.get("Error",{}).get("Code")=="ConditionalCheckFailedException":return {"accepted":False,"duplicate_or_replay":True,"evidence_id":e.evidence_id}
        raise
    return {"accepted":True,"evidence_id":e.evidence_id,"bucket":item["bucket"]}

def process(payload:dict,kind:str,topic:str|None=None,transport:str="aws-iot"):
    return _heartbeat(payload,topic,transport) if kind=="heartbeat" else _trigger(payload,topic,transport)

def handler(event,context):
    topic=event.get("_topic")
    if not topic: raise ValidationError("IoT Rule must inject _topic=topic()")
    kind=topic.rsplit('/',1)[-1]
    if kind not in {"heartbeat","trigger"}: raise ValidationError("unsupported message kind")
    payload={k:v for k,v in event.items() if k!="_topic"}
    return process(payload,kind,topic,"aws-iot")
