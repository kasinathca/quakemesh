from __future__ import annotations
from boto3.dynamodb.conditions import Key
from .common import boto3,env,now_ms
from quakemesh_core.config import DetectionConfig

def handler(event,context):
    cfg=DetectionConfig.from_env();now=now_ms();cutoff=now-cfg.event_resolve_after_ms;t=boto3.resource("dynamodb").Table(env("QM_EVENT_TABLE"));resolved=[]
    kwargs={"IndexName":"status-updated-index","KeyConditionExpression":Key("status").eq("CONFIRMED")&Key("updated_at_ms").lt(cutoff)}
    while True:
        resp=t.query(**kwargs)
        for item in resp.get("Items",[]):
            try:
                t.update_item(Key={"event_id":item["event_id"]},UpdateExpression="SET #s=:r,updated_at_ms=:now,#v=#v+:one",ConditionExpression="#s=:c AND #v=:old",ExpressionAttributeNames={"#s":"status","#v":"version"},ExpressionAttributeValues={":r":"RESOLVED",":c":"CONFIRMED",":now":now,":one":1,":old":int(item["version"])})
                resolved.append(str(item["event_id"]))
            except t.meta.client.exceptions.ConditionalCheckFailedException:pass
        lek=resp.get("LastEvaluatedKey")
        if not lek:break
        kwargs["ExclusiveStartKey"]=lek
    return {"resolved":resolved}
