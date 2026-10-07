#!/usr/bin/env python3
import os,re,sys
from datetime import datetime,timezone,timedelta
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
import aws_cdk as cdk
from aws.infrastructure.stack import QuakeMeshStack
app=cdk.App()
session_id=os.getenv("QM_SESSION_ID","synth-local")
if not re.fullmatch(r"[a-z0-9][a-z0-9-]{2,39}",session_id):
    raise ValueError("QM_SESSION_ID must be 3-40 lowercase letters, digits, or hyphens")
expires_at=os.getenv("QM_EXPIRES_AT") or (datetime.now(timezone.utc)+timedelta(hours=2)).isoformat().replace("+00:00","Z")
stack_id=f"QuakeMesh-V2-Demo-{session_id}"
QuakeMeshStack(app,stack_id,session_id=session_id,expires_at=expires_at,env=cdk.Environment(account=os.getenv("CDK_DEFAULT_ACCOUNT"),region=os.getenv("CDK_DEFAULT_REGION","ap-south-1")))
app.synth()
