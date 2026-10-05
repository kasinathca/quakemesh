# ADR-005 — Serialize V1 correlator

**Status:** accepted for academic-scale V1.

The correlator Lambda has reserved concurrency 1. Conditional event version writes remain enabled. This prioritizes deterministic correctness for a small experiment deployment. A production scale-out design would assign correlation ownership by spatial/temporal shard and cannot simply remove this limit without redesigning event ownership.
