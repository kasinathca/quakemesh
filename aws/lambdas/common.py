from __future__ import annotations
import os,sys,json,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
SRC=ROOT/"src"
if str(SRC) not in sys.path: sys.path.insert(0,str(SRC))

import boto3
from boto3.dynamodb.types import TypeDeserializer

_d=TypeDeserializer()
def stream_image(image:dict)->dict: return {k:_d.deserialize(v) for k,v in image.items()}
def env(name:str)->str:
    v=os.getenv(name)
    if not v: raise RuntimeError(f"missing environment variable {name}")
    return v
def now_ms()->int:return int(time.time()*1000)
def json_response(status:int,body:dict,headers:dict|None=None)->dict:
    h={"Content-Type":"application/json","Access-Control-Allow-Origin":"*"};h.update(headers or {})
    return {"statusCode":status,"headers":h,"body":json.dumps(body,separators=(",",":"))}
