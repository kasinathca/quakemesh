# Security and privacy

Threats include forged observations, replay/out-of-order sequences, scenario-control abuse, leaked API keys/certificates/tokens, over-broad cleanup, cross-session access, payload/log injection, and unexpected resource retention.

Controls: closed schemas, clock/sequence guards, Thing-scoped IoT policy, session-scoped demo credentials, rate limits, least-privilege cleanup bound to exact stack/session identifiers, encrypted S3, HTTPS/mTLS, secret-path ignores/scans, coarse H3 persistence, and redacted structured logs. Raw coordinates are processed to cells and not stored in the current local evidence schema.

The dashboard is not a general user-account system. Public read access must be an explicit academic-demo choice; scenario/reset/ACK controls are never anonymous in AWS mode. Local mode binds to loopback by default. Cleanup treats ambiguous ownership as a stop condition, not permission to delete.
