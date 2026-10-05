# ADR-002 — Serverless/event-driven AWS V1

**Status:** accepted.

Use AWS IoT Core, Lambda, DynamoDB, API Gateway, EventBridge, SNS, S3 and CloudWatch. Do not introduce VPC/NAT/EC2/RDS in V1. Rationale: cloud-computing course relevance, low idle cost, managed scaling and less operational surface for one-PC development.
