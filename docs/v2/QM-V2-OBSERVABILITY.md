# Observability specification

Structured records use UTC epoch milliseconds and carry `run_id`, `event_id`, `device_id`, and `request_id` only when applicable. Severity is `debug`, `info`, `warning`, or `error`; user-visible messages contain no credentials, FCM tokens, certificate material, raw coordinates, or full payload dumps.

Local mode persists bounded scenario stages in SQLite and streams or adaptively polls snapshots. AWS mode uses DynamoDB run/stage tables plus structured Lambda logs; log groups have explicit short retention and strict deletion. Metrics include counts and measured durations for ingestion, correlation, confirmation, dispatch, and scenario completion. A measurement records start/end source and does not imply network warning lead time.

Retention defaults: evidence 10 minutes, local review records until reset/export, AWS session records until teardown, CloudWatch logs no longer than the documented demo retention. Export redacts secrets and captures build/schema/session metadata.
