#!/usr/bin/env python3
import os,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
import aws_cdk as cdk
from aws.infrastructure.stack import QuakeMeshStack
app=cdk.App()
QuakeMeshStack(app,"QuakeMeshStack",env=cdk.Environment(account=os.getenv("CDK_DEFAULT_ACCOUNT"),region=os.getenv("CDK_DEFAULT_REGION","ap-south-1")))
app.synth()
