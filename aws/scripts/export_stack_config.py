from __future__ import annotations
import json,os
from pathlib import Path
import boto3
region=os.getenv("AWS_REGION","ap-south-1");cf=boto3.client("cloudformation",region_name=region);api=boto3.client("apigateway",region_name=region);iot=boto3.client("iot",region_name=region)
st=cf.describe_stacks(StackName="QuakeMeshStack")["Stacks"][0];outs={x["OutputKey"]:x["OutputValue"] for x in st.get("Outputs",[])}
key=api.get_api_key(apiKey=outs["ApiKeyId"],includeValue=True)["value"];endpoint=iot.describe_endpoint(endpointType="iot:Data-ATS")["endpointAddress"]
conf={"region":region,"api_base_url":outs["ApiBaseUrl"],"api_key":key,"iot_endpoint":endpoint,"archive_bucket":outs["ExperimentArchiveBucket"]}
p=Path("artifacts/runtime-config.json");p.parent.mkdir(exist_ok=True);p.write_text(json.dumps(conf,indent=2));print(f"Wrote {p}. It contains a demo API key and is gitignored.")
