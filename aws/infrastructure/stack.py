from __future__ import annotations

import os
from pathlib import Path

from aws_cdk import (
    CfnOutput,
    Duration,
    RemovalPolicy,
    Stack,
    Tags,
    aws_apigateway as apigw,
    aws_cloudwatch as cloudwatch,
    aws_dynamodb as dynamodb,
    aws_events as events,
    aws_events_targets as event_targets,
    aws_iam as iam,
    aws_iot as iot,
    aws_lambda as lambda_,
    aws_lambda_event_sources as lambda_events,
    aws_logs as logs,
)
from constructs import Construct

ROOT = Path(__file__).resolve().parents[2]


class QuakeMeshStack(Stack):
    """Session-scoped QuakeMesh V2 serverless stack.

    The stack contains no retained data resources. A session is the ownership
    boundary; deterministic teardown deletes only this exact CloudFormation stack.
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        session_id: str,
        expires_at: str,
        **kwargs,
    ):
        super().__init__(scope, construct_id, **kwargs)
        for key, value in {
            "Project": "QuakeMesh",
            "Architecture": "V2",
            "Environment": "AcademicDemo",
            "Ephemeral": "true",
            "SessionId": session_id,
            "ExpiresAt": expires_at,
        }.items():
            Tags.of(self).add(key, value)

        device = dynamodb.Table(
            self,
            "DeviceState",
            partition_key=dynamodb.Attribute(name="device_key", type=dynamodb.AttributeType.STRING),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
        )
        device.add_global_secondary_index(
            index_name="cell-lastseen-index",
            partition_key=dynamodb.Attribute(
                name="correlation_cell", type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(name="last_seen_ms", type=dynamodb.AttributeType.NUMBER),
            projection_type=dynamodb.ProjectionType.ALL,
        )
        evidence = dynamodb.Table(
            self,
            "Evidence",
            partition_key=dynamodb.Attribute(name="bucket", type=dynamodb.AttributeType.STRING),
            sort_key=dynamodb.Attribute(name="evidence_id", type=dynamodb.AttributeType.STRING),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            time_to_live_attribute="ttl",
            stream=dynamodb.StreamViewType.NEW_IMAGE,
            removal_policy=RemovalPolicy.DESTROY,
        )
        event = dynamodb.Table(
            self,
            "Events",
            partition_key=dynamodb.Attribute(name="event_id", type=dynamodb.AttributeType.STRING),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            stream=dynamodb.StreamViewType.NEW_AND_OLD_IMAGES,
            removal_policy=RemovalPolicy.DESTROY,
        )
        event.add_global_secondary_index(
            index_name="status-updated-index",
            partition_key=dynamodb.Attribute(name="status", type=dynamodb.AttributeType.STRING),
            sort_key=dynamodb.Attribute(name="updated_at_ms", type=dynamodb.AttributeType.NUMBER),
            projection_type=dynamodb.ProjectionType.ALL,
        )
        alert = dynamodb.Table(
            self,
            "AlertDelivery",
            partition_key=dynamodb.Attribute(name="alert_id", type=dynamodb.AttributeType.STRING),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
        )

        layer_dir = ROOT / "artifacts" / "lambda-layer"
        if not layer_dir.exists():
            raise FileNotFoundError(
                f"Missing {layer_dir}. Run: python aws/scripts/build_lambda_layer.py"
            )
        h3_layer = lambda_.LayerVersion(
            self,
            "H3Layer",
            code=lambda_.Code.from_asset(str(layer_dir)),
            compatible_runtimes=[lambda_.Runtime.PYTHON_3_12],
            description=f"QuakeMesh V2 H3 layer for {session_id}",
            removal_policy=RemovalPolicy.DESTROY,
        )
        code = lambda_.Code.from_asset(
            str(ROOT),
            exclude=[
                ".git",
                ".venv",
                ".venv-cdk",
                "venv",
                "aws/infrastructure/.venv-cdk",
                "aws/infrastructure/cdk.out",
                "android",
                "docs",
                "tests",
                "artifacts",
                "*.zip",
                "__pycache__",
                ".pytest_cache",
                "dashboard/node_modules",
                "dashboard/dist",
            ],
        )
        common_env = {
            "QM_SESSION_ID": session_id,
            "QM_EXPIRES_AT": expires_at,
            "QM_DEVICE_TABLE": device.table_name,
            "QM_EVIDENCE_TABLE": evidence.table_name,
            "QM_EVENT_TABLE": event.table_name,
            "QM_ALERT_TABLE": alert.table_name,
            "QM_H3_DEVICE_RESOLUTION": "9",
            "QM_H3_CORRELATION_RESOLUTION": "7",
            "QM_EVIDENCE_WINDOW_MS": "8000",
            "QM_MIN_DEVICES": "4",
            "QM_MIN_DISTINCT_CELLS": "3",
            "QM_MAX_CLUSTER_GRID_DISTANCE": "6",
            "QM_WARNING_RING_K": "1",
            "QM_EVENT_MERGE_WINDOW_MS": "20000",
            "QM_EVENT_RESOLVE_AFTER_MS": "30000",
            "QM_EVIDENCE_TTL_SECONDS": "600",
            "QM_MAX_CLOCK_SKEW_MS": "120000",
        }
        platform_arn = os.getenv("QM_SNS_PLATFORM_APPLICATION_ARN", "")
        if platform_arn:
            common_env["QM_SNS_PLATFORM_APPLICATION_ARN"] = platform_arn

        functions: dict[str, lambda_.Function] = {}

        def function(
            name: str,
            handler: str,
            timeout: int = 15,
            memory: int = 256,
            layers: tuple[lambda_.ILayerVersion, ...] = (),
            reserved: int | None = None,
        ) -> lambda_.Function:
            fn = lambda_.Function(
                self,
                name,
                runtime=lambda_.Runtime.PYTHON_3_12,
                architecture=lambda_.Architecture.X86_64,
                handler=handler,
                code=code,
                timeout=Duration.seconds(timeout),
                memory_size=memory,
                environment=common_env,
                layers=list(layers),
                tracing=lambda_.Tracing.ACTIVE,
                reserved_concurrent_executions=reserved,
            )
            logs.LogGroup(
                self,
                f"{name}LogGroup",
                log_group_name=f"/aws/lambda/{fn.function_name}",
                retention=logs.RetentionDays.ONE_WEEK,
                removal_policy=RemovalPolicy.DESTROY,
            )
            functions[name] = fn
            return fn

        ingress = function("IngressFn", "aws.lambdas.ingress.handler", 20, 384, (h3_layer,))
        api_fn = function("ApiFn", "aws.lambdas.api.handler", 20, 384, (h3_layer,))
        correlator = function(
            "CorrelatorFn", "aws.lambdas.correlator.handler", 30, 512, (h3_layer,), 1
        )
        dispatcher = function("DispatcherFn", "aws.lambdas.dispatcher.handler", 30, 384, (), 1)
        resolver = function("ResolverFn", "aws.lambdas.resolver.handler", 20, 256)

        device.grant_read_write_data(ingress)
        evidence.grant_write_data(ingress)
        device.grant_read_write_data(api_fn)
        evidence.grant_write_data(api_fn)
        event.grant_read_data(api_fn)
        alert.grant_read_write_data(api_fn)
        evidence.grant_read_data(correlator)
        event.grant_read_write_data(correlator)
        device.grant_read_data(dispatcher)
        alert.grant_read_write_data(dispatcher)
        event.grant_read_write_data(resolver)
        correlator.add_event_source(
            lambda_events.DynamoEventSource(
                evidence,
                starting_position=lambda_.StartingPosition.LATEST,
                batch_size=20,
                retry_attempts=2,
                bisect_batch_on_error=True,
            )
        )
        dispatcher.add_event_source(
            lambda_events.DynamoEventSource(
                event,
                starting_position=lambda_.StartingPosition.LATEST,
                batch_size=10,
                retry_attempts=2,
                bisect_batch_on_error=True,
            )
        )

        dispatcher.add_to_role_policy(
            iam.PolicyStatement(actions=["iot:DescribeEndpoint"], resources=["*"])
        )
        topic_root = f"quakemesh/v1/{session_id}/devices"
        dispatcher.add_to_role_policy(
            iam.PolicyStatement(
                actions=["iot:Publish"],
                resources=[
                    self.format_arn(
                        service="iot", resource="topic", resource_name=f"{topic_root}/*/alerts"
                    )
                ],
            )
        )
        if platform_arn:
            endpoint_arn = (
                f"arn:{self.partition}:sns:{self.region}:{self.account}:endpoint/GCM/*/*"
            )
            for fn in (ingress, api_fn):
                fn.add_to_role_policy(
                    iam.PolicyStatement(
                        actions=[
                            "sns:CreatePlatformEndpoint",
                            "sns:GetEndpointAttributes",
                            "sns:SetEndpointAttributes",
                        ],
                        resources=[platform_arn, endpoint_arn],
                    )
                )
            dispatcher.add_to_role_policy(
                iam.PolicyStatement(actions=["sns:Publish"], resources=[endpoint_arn])
            )

        for kind in ("heartbeat", "trigger"):
            rule = iot.CfnTopicRule(
                self,
                f"{kind.title()}Rule",
                topic_rule_payload=iot.CfnTopicRule.TopicRulePayloadProperty(
                    sql=(
                        f"SELECT *, topic() AS _topic FROM "
                        f"'{topic_root}/+/{kind}'"
                    ),
                    aws_iot_sql_version="2016-03-23",
                    actions=[
                        iot.CfnTopicRule.ActionProperty(
                            lambda_=iot.CfnTopicRule.LambdaActionProperty(
                                function_arn=ingress.function_arn
                            )
                        )
                    ],
                    rule_disabled=False,
                ),
            )
            rule_arn = self.format_arn(service="iot", resource="rule", resource_name=rule.ref)
            ingress.add_permission(
                f"AllowIot{kind.title()}",
                principal=iam.ServicePrincipal("iot.amazonaws.com"),
                source_arn=rule_arn,
            )

        thing_var = "${iot:Connection.Thing.ThingName}"
        policy_document = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": ["iot:Connect"],
                    "Resource": [
                        self.format_arn(
                            service="iot", resource="client", resource_name=thing_var
                        )
                    ],
                },
                {
                    "Effect": "Allow",
                    "Action": ["iot:Publish"],
                    "Resource": [
                        self.format_arn(
                            service="iot",
                            resource="topic",
                            resource_name=f"{topic_root}/{thing_var}/heartbeat",
                        ),
                        self.format_arn(
                            service="iot",
                            resource="topic",
                            resource_name=f"{topic_root}/{thing_var}/trigger",
                        ),
                    ],
                },
                {
                    "Effect": "Allow",
                    "Action": ["iot:Subscribe"],
                    "Resource": [
                        self.format_arn(
                            service="iot",
                            resource="topicfilter",
                            resource_name=f"{topic_root}/{thing_var}/alerts",
                        )
                    ],
                },
                {
                    "Effect": "Allow",
                    "Action": ["iot:Receive"],
                    "Resource": [
                        self.format_arn(
                            service="iot",
                            resource="topic",
                            resource_name=f"{topic_root}/{thing_var}/alerts",
                        )
                    ],
                },
            ],
        }
        policy = iot.CfnPolicy(
            self,
            "DevicePolicy",
            policy_name=f"QuakeMeshV2-{session_id}-DevicePolicy",
            policy_document=policy_document,
        )

        api = apigw.RestApi(
            self,
            "RestApi",
            rest_api_name=f"QuakeMesh V2 Demo {session_id}",
            cloud_watch_role=False,
            deploy_options=apigw.StageOptions(
                stage_name="v2", tracing_enabled=True, metrics_enabled=True
            ),
            default_cors_preflight_options=apigw.CorsOptions(
                allow_origins=apigw.Cors.ALL_ORIGINS,
                allow_methods=["GET", "POST", "OPTIONS"],
                allow_headers=["Content-Type", "X-Api-Key"],
            ),
        )
        integration = apigw.LambdaIntegration(api_fn, proxy=True)
        api.root.add_resource("health").add_method("GET", integration)
        v1 = api.root.add_resource("v1")
        devices = v1.add_resource("devices")
        devices.add_method("GET", integration)
        devices.add_resource("heartbeat").add_method(
            "POST", integration, api_key_required=True
        )
        evidence_resource = v1.add_resource("evidence")
        evidence_resource.add_resource("trigger").add_method(
            "POST", integration, api_key_required=True
        )
        v1.add_resource("events").add_method("GET", integration)
        alerts = v1.add_resource("alerts")
        alerts.add_method("GET", integration)
        alerts.add_resource("{alert_id}").add_resource("ack").add_method(
            "POST", integration, api_key_required=True
        )
        api_key = api.add_api_key(
            "DemoApiKey", api_key_name=f"QuakeMeshV2-{session_id}-WriteKey"
        )
        plan = api.add_usage_plan(
            "UsagePlan",
            name=f"QuakeMeshV2-{session_id}-Plan",
            throttle=apigw.ThrottleSettings(rate_limit=50, burst_limit=100),
            quota=apigw.QuotaSettings(limit=100000, period=apigw.Period.MONTH),
        )
        plan.add_api_key(api_key)
        plan.add_api_stage(stage=api.deployment_stage)

        events.Rule(
            self,
            "ResolverSchedule",
            schedule=events.Schedule.rate(Duration.minutes(1)),
            targets=[event_targets.LambdaFunction(resolver)],
        )
        for name, fn in functions.items():
            cloudwatch.Alarm(
                self,
                f"{name}Errors",
                metric=fn.metric_errors(period=Duration.minutes(5)),
                threshold=1,
                evaluation_periods=1,
                treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
            )

        for key, value in {
            "SessionId": session_id,
            "ExpiresAt": expires_at,
            "ApiBaseUrl": api.url,
            "ApiKeyId": api_key.key_id,
            "DevicePolicyName": policy.policy_name or "",
            "DeviceTableName": device.table_name,
            "EvidenceTableName": evidence.table_name,
            "EventTableName": event.table_name,
            "AlertTableName": alert.table_name,
            "Region": self.region,
        }.items():
            CfnOutput(self, key, value=value)
