# Dependency Baseline — verified September 2026

The release intentionally pins or documents these versions:

| Dependency | Baseline |
|---|---:|
| Python | 3.10+; 3.12 recommended |
| h3-py | 4.5.0 |
| FastAPI | 0.141.1 |
| Uvicorn | 0.52.4 |
| Boto3 | 1.43.89 |
| AWS IoT Device SDK for Python v2 (`awsiotsdk`) | 1.31.0 |
| pytest | 9.1.1 |
| Ruff | 0.16.6 |
| aws-cdk-lib | 2.268.0 |
| AWS CDK Toolkit CLI | 2.1140.0 |
| Android Gradle Plugin | 9.4.0 |
| Gradle | 9.6.0 |
| Firebase Android BoM | 34.18.0 |
| google-services Gradle plugin | 4.5.0 |

The deployment scripts pin AWS CDK Toolkit CLI 2.1140.0 for reproducibility. AWS documents that a construct library is compatible with the Toolkit version current at its release and any newer Toolkit version, so this newer CLI is compatible with `aws-cdk-lib` 2.268.0.
