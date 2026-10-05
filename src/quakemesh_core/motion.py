from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from .config import DetectionConfig


@dataclass(frozen=True)
class MotionFeatures:
    rms: float
    peak: float
    sample_count: int


def extract_motion_features(samples: list[tuple[float, float, float]], gravity: float = 9.80665) -> MotionFeatures:
    if not samples:
        return MotionFeatures(0.0, 0.0, 0)
    deviations: list[float] = []
    for x, y, z in samples:
        magnitude = sqrt(x*x + y*y + z*z)
        deviations.append(abs(magnitude - gravity))
    rms = sqrt(sum(v*v for v in deviations) / len(deviations))
    return MotionFeatures(rms=rms, peak=max(deviations), sample_count=len(deviations))


def passes_motion_gate(features: MotionFeatures, config: DetectionConfig) -> bool:
    return features.sample_count > 0 and features.rms >= config.motion_rms_threshold and features.peak >= config.motion_peak_threshold
