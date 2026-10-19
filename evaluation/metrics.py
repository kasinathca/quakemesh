from __future__ import annotations

import math
import random
from collections.abc import Iterable


def safe_ratio(numerator: int | float, denominator: int | float) -> float | None:
    """Return a ratio, or None when the statistic is mathematically undefined."""
    return float(numerator) / float(denominator) if denominator else None


def wilson_interval(successes: int, total: int, z: float = 1.959963984540054) -> list[float] | None:
    if total <= 0:
        return None
    p = successes / total
    denominator = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denominator
    margin = z * math.sqrt((p * (1 - p) + z * z / (4 * total)) / total) / denominator
    lower, upper = max(0.0, center - margin), min(1.0, center + margin)
    return [0.0 if lower < 1e-15 else lower, 1.0 if upper > 1 - 1e-15 else upper]


def percentile_interval(values: Iterable[float], seed: int = 73021, samples: int = 2_000) -> list[float] | None:
    data = list(values)
    if not data:
        return None
    rng = random.Random(seed)
    means = sorted(sum(rng.choice(data) for _ in data) / len(data) for _ in range(samples))
    return [means[int(0.025 * (samples - 1))], means[int(0.975 * (samples - 1))]]


def classification_metrics(tp: int, tn: int, fp: int, fn: int) -> dict:
    total = tp + tn + fp + fn
    definitions = {
        "accuracy": (tp + tn, total),
        "precision": (tp, tp + fp),
        "recall": (tp, tp + fn),
        "specificity": (tn, tn + fp),
        "f1": (2 * tp, 2 * tp + fp + fn),
        "false_positive_rate": (fp, fp + tn),
        "false_negative_rate": (fn, fn + tp),
    }
    result: dict[str, object] = {}
    for name, (numerator, denominator) in definitions.items():
        result[name] = safe_ratio(numerator, denominator)
        result[f"{name}_ci95"] = wilson_interval(numerator, denominator)
    return result
