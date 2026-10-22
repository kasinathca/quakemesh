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


def poisson_rate_interval(events: int, exposure: float, z: float = 1.959963984540054) -> list[float] | None:
    """Two-sided 95% Poisson-rate interval using the Byar approximation."""
    if exposure <= 0 or events < 0:
        return None
    if events == 0:
        return [0.0, -math.log(0.025) / exposure]
    lower_count = events * (1 - 1 / (9 * events) - z / (3 * math.sqrt(events))) ** 3
    upper_base = events + 1
    upper_count = upper_base * (1 - 1 / (9 * upper_base) + z / (3 * math.sqrt(upper_base))) ** 3
    return [max(0.0, lower_count / exposure), upper_count / exposure]


def classification_metrics(tp: int, tn: int, fp: int, fn: int) -> dict:
    total = tp + tn + fp + fn
    definitions = {
        "accuracy": (tp + tn, total),
        "precision": (tp, tp + fp),
        "recall": (tp, tp + fn),
        "specificity": (tn, tn + fp),
        "f1": (2 * tp, 2 * tp + fp + fn),
        "f2": (5 * tp, 5 * tp + 4 * fn + fp),
        "false_positive_rate": (fp, fp + tn),
        "false_negative_rate": (fn, fn + tp),
        "positive_predictive_value": (tp, tp + fp),
        "negative_predictive_value": (tn, tn + fn),
    }
    result: dict[str, object] = {}
    for name, (numerator, denominator) in definitions.items():
        result[name] = safe_ratio(numerator, denominator)
        result[f"{name}_ci95"] = wilson_interval(numerator, denominator)
    recall = result["recall"]
    specificity = result["specificity"]
    result["balanced_accuracy"] = (
        None if recall is None or specificity is None else (recall + specificity) / 2
    )
    mcc_denominator = math.sqrt((tp + fp) * (tp + fn) * (tn + fp) * (tn + fn))
    result["matthews_correlation_coefficient"] = (
        None if not mcc_denominator else (tp * tn - fp * fn) / mcc_denominator
    )
    return result


def error_metrics(actual: Iterable[float], predicted: Iterable[float]) -> dict[str, float | None]:
    """Describe errors for a genuinely continuous target with paired ground truth."""
    pairs = list(zip(actual, predicted, strict=True))
    if not pairs:
        return {
            "count": 0,
            "mae": None,
            "mse": None,
            "rmse": None,
            "median_absolute_error": None,
            "absolute_error_p50": None,
            "absolute_error_p95": None,
            "absolute_error_p99": None,
        }
    absolute = sorted(abs(observed - estimate) for observed, estimate in pairs)
    squared = [(observed - estimate) ** 2 for observed, estimate in pairs]

    def percentile(fraction: float) -> float:
        position = fraction * (len(absolute) - 1)
        lower = int(math.floor(position))
        upper = int(math.ceil(position))
        if lower == upper:
            return absolute[lower]
        return absolute[lower] + (absolute[upper] - absolute[lower]) * (position - lower)

    mae = sum(absolute) / len(absolute)
    mse = sum(squared) / len(squared)
    return {
        "count": len(pairs),
        "mae": mae,
        "mse": mse,
        "rmse": math.sqrt(mse),
        "median_absolute_error": percentile(0.5),
        "absolute_error_p50": percentile(0.5),
        "absolute_error_p95": percentile(0.95),
        "absolute_error_p99": percentile(0.99),
    }
