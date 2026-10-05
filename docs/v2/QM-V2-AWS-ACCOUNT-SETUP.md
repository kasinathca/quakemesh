# AWS account and SSO setup

Account creation, billing details, MFA, and IAM Identity Center configuration require the account owner in the AWS console. QuakeMesh does not automate those steps and never stores long-lived access keys in the repository.

After installing AWS CLI v2, configure a named SSO profile:

```powershell
aws configure sso --profile quakemesh-demo
aws sso login --profile quakemesh-demo
aws sts get-caller-identity --profile quakemesh-demo
```

Use region `ap-south-1` unless the project metadata intentionally records another region. Preflight must display the resolved account, ARN, profile, region, session ID, and TTL without printing tokens. A different account than the previously recorded account requires explicit confirmation.

The principal needs only the services synthesized for the academic session: CloudFormation/CDK deployment assets, Lambda, DynamoDB, API Gateway, IoT Core, EventBridge/Scheduler, CloudWatch Logs/alarms, S3, IAM roles for those resources, and optional SNS mobile push. Restrict permissions to QuakeMesh session tags/names where AWS supports it. Do not attach broad administrator access merely to bypass a failed preflight.
