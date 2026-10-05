# Firebase + Amazon SNS Setup (Account-Specific Step)

The repository cannot create Firebase credentials on your behalf. Do not place service-account private material in Git.

1. In Firebase Console, create/select a project.
2. Add Android app package `com.quakemesh.app`.
3. Download `google-services.json` to `android/app/google-services.json` (gitignored).
4. Ensure Cloud Messaging is enabled for the project.
5. In AWS SNS, create a **Google Firebase Cloud Messaging (FCM)** platform application using the supported FCM HTTP v1 authentication method and your Firebase project credentials.
6. Copy the resulting SNS PlatformApplication ARN.
7. Before CDK deploy in PowerShell:

```powershell
$env:QM_SNS_PLATFORM_APPLICATION_ARN="arn:aws:sns:ap-south-1:ACCOUNT:app/GCM/YOUR_APP"
.\aws\scripts\deploy.ps1
```

At Android heartbeat time, the backend uses the FCM token to create/retrieve an SNS platform endpoint and stores the endpoint ARN with H3 device state. The dispatcher publishes FCM v1-formatted messages through SNS.

If the ARN is not configured, QuakeMesh still deploys and simulator MQTT warnings work; Android FCM dispatch is simply inactive.
