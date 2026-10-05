# QM-AWS-001 — AWS Infrastructure

## Region

Default: `ap-south-1` (Mumbai).

## Resources created by CDK

- DynamoDB `DeviceState` table + cell/last-seen GSI;
- DynamoDB `Evidence` table + TTL + stream;
- DynamoDB `Events` table + status/update GSI + stream;
- DynamoDB `AlertDelivery` table;
- Lambda functions: ingress, API, correlator, dispatcher, resolver;
- H3 Lambda layer built as CPython 3.12 manylinux x86-64 artifact;
- AWS IoT Core topic rules for heartbeat and trigger;
- IoT Thing policy named `QuakeMeshDevicePolicy`;
- API Gateway REST API + API key + usage plan;
- EventBridge one-minute resolver schedule;
- CloudWatch Lambda error alarms;
- S3 encrypted/versioned experiment archive (retained on stack deletion).

## Explicitly absent

- VPC;
- NAT Gateway;
- EC2;
- ECS/EKS;
- RDS/Aurora;
- persistent application server.

## H3 Lambda layer

Running `aws/scripts/build_lambda_layer.py` from Windows intentionally uses pip cross-platform flags:

- platform `manylinux2014_x86_64`;
- CPython 3.12;
- binary wheels only.

This avoids the common error of building a Windows `h3` wheel into a Linux Lambda layer.

## CDK interpreter correctness

`aws/scripts/deploy.ps1` creates `aws/infrastructure/.venv-cdk` and invokes the CDK CLI with:

`--app "<absolute path to .venv-cdk Python> app.py"`

The app therefore cannot silently execute under a different global Python environment.

## Cost posture

The baseline uses pay-per-request DynamoDB and short-running Lambdas. CloudWatch, API Gateway, IoT, SNS, DynamoDB and S3 can still incur charges. Teardown should be performed after experiments if resources are no longer required. The S3 archive is retained deliberately to avoid deleting evidence; remove it manually if desired.
