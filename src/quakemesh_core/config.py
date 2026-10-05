from __future__ import annotations

from dataclasses import dataclass
import os


@dataclass(frozen=True)
class DetectionConfig:
    """Experiment configuration, not a seismological calibration."""

    h3_device_resolution: int = 9
    h3_correlation_resolution: int = 7
    evidence_window_ms: int = 8_000
    min_devices: int = 4
    min_distinct_cells: int = 3
    max_cluster_grid_distance: int = 6
    warning_ring_k: int = 1
    event_merge_window_ms: int = 20_000
    evidence_ttl_seconds: int = 600
    event_resolve_after_ms: int = 30_000
    motion_rms_threshold: float = 0.75
    motion_peak_threshold: float = 1.80
    max_clock_skew_ms: int = 120_000

    @classmethod
    def from_env(cls) -> "DetectionConfig":
        def i(name: str, default: int) -> int:
            return int(os.getenv(name, str(default)))

        def f(name: str, default: float) -> float:
            return float(os.getenv(name, str(default)))

        return cls(
            h3_device_resolution=i("QM_H3_DEVICE_RESOLUTION", 9),
            h3_correlation_resolution=i("QM_H3_CORRELATION_RESOLUTION", 7),
            evidence_window_ms=i("QM_EVIDENCE_WINDOW_MS", 8_000),
            min_devices=i("QM_MIN_DEVICES", 4),
            min_distinct_cells=i("QM_MIN_DISTINCT_CELLS", 3),
            max_cluster_grid_distance=i("QM_MAX_CLUSTER_GRID_DISTANCE", 6),
            warning_ring_k=i("QM_WARNING_RING_K", 1),
            event_merge_window_ms=i("QM_EVENT_MERGE_WINDOW_MS", 20_000),
            evidence_ttl_seconds=i("QM_EVIDENCE_TTL_SECONDS", 600),
            event_resolve_after_ms=i("QM_EVENT_RESOLVE_AFTER_MS", 30_000),
            motion_rms_threshold=f("QM_MOTION_RMS_THRESHOLD", 0.75),
            motion_peak_threshold=f("QM_MOTION_PEAK_THRESHOLD", 1.80),
            max_clock_skew_ms=i("QM_MAX_CLOCK_SKEW_MS", 120_000),
        )
