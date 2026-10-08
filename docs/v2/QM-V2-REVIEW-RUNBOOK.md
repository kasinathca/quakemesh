# QuakeMesh V2 presentation runbook

## One-time preparation

Use Windows with the repository on `feature/android-v2`. AWS CLI v2 must authenticate profile `quakemesh-demo`; the scripts resolve the account through STS and refuse the root identity. Double-click `PREPARE_QUAKEMESH_REVIEW.cmd`, or run:

```powershell
.\scripts\review\prepare.ps1 -Bootstrap
```

Preparation validates Python, Node, dashboard/browser tests, Android unit tests/APK/lint, the Lambda layer, CDK synthesis, secrets, and the Git diff. It does not deploy a QuakeMesh session stack. `CDKToolkit` is shared account/region bootstrap infrastructure and remains present. Its asset bucket and supporting resources can incur storage or request charges; session STOP does not delete it.

## Start and present

Double-click `START_QUAKEMESH_REVIEW.cmd`. A successful run ends with `QUAKEMESH REVIEW ENVIRONMENT READY` and reports smoke and distributed warm-up as PASS. Re-running START while that session is healthy reuses it.

- Local API: `http://127.0.0.1:8000`
- Local dashboard: `http://127.0.0.1:8080`
- AWS dashboard: `http://127.0.0.1:8081`
- Read-only status: `STATUS_QUAKEMESH_REVIEW.cmd`
- Local distributed demo: `RUN_LOCAL_DISTRIBUTED_DEMO.cmd`
- AWS distributed demo: `RUN_AWS_DISTRIBUTED_DEMO.cmd`

Suggested order: show Local V2 and the distributed H3 footprint/frontier; show Android monitoring if a phone is present; show AWS V2, API Gateway/Lambda/DynamoDB/IoT/CloudWatch in the console; run the AWS scenario; show the confirmed event and alerts.

START uses ports 8000, 8080, and 8081. It refuses an unrelated listener instead of killing it. The local and AWS dashboard copies have independent ignored `config.js` files. No connected Android device is acceptable: the APK remains ready. Exactly one authorized device is updated with `adb install -r`; multiple devices require manual selection. Firebase is optional.

## Stop and CLEAN

Double-click `STOP_QUAKEMESH_REVIEW.cmd`, including after a failed or interrupted START. STOP restores Android `local.properties`, stops only PID/command pairs owned by the harness, removes exact-session IoT credentials and optional SNS endpoints, destroys the exact tagged stack, and verifies concrete resources from a pre-destroy inventory.

`CLEAN` means: after verification, no known QuakeMesh session-owned AWS application resources remain that can continue generating ongoing application charges. It does not mean the AWS account is empty, that past request charges are reversed, or that shared `CDKToolkit` resources were removed. Any denied inspection or remaining resource produces `INCOMPLETE`, not CLEAN. The sanitized last report is `artifacts/review/last-teardown.json`.

STOP is idempotent. Run it again if uncertain. Do not accept the session as finished unless it reports CLEAN.

## Recovery and limits

State is stored under ignored `artifacts/review/`. START reconciles state with AWS, reuses one healthy owned session, removes stale metadata for an absent stack, and refuses multiple or ambiguously tagged stacks. A Scheduler expiry is a crash/forgotten-stop backstop; manual STOP is primary.

The session defaults to 180 minutes and uses serverless/on-demand services. AWS execution is not guaranteed to cost zero. The live first/idempotent/fresh START and STOP/CLEAN matrix completed in account `101541767123`, region `ap-south-1`, on 2026-10-08. The harness is presentation-ready for its verified no-phone/no-FCM scope. Physical Android behavior, phone heartbeat/trigger, FCM, and automatic expiry execution remain separate evidence scopes unless actually exercised.
