# Cost safety

QuakeMesh strict sessions avoid EC2, RDS, NAT Gateway, ECS, EKS, and custom VPC resources. They use request-driven managed services: IoT Core, Lambda, DynamoDB on-demand, API Gateway, EventBridge/Scheduler, CloudWatch, S3, and optional SNS.

Session deletion stops future accumulation from session-owned resources; it cannot reverse usage already consumed. TTL cleanup is a backstop, not a substitute for normal stop and verification. An account-level AWS Budget and billing alert are recommended, but remain outside per-session teardown.

Before start, review the synthesized template, account/region, device count, and TTL. During a session, the UI must show expiry. At stop, export evidence locally and require a `CLEAN` verification report. Access-denied or API failures produce `INCOMPLETE`, never a presumed clean result. Shared CDK bootstrap resources are not deleted unless a dedicated qualifier and ownership metadata prove they belong only to QuakeMesh.
