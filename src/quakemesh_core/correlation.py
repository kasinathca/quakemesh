from __future__ import annotations

import hashlib
from collections import defaultdict, deque
from .config import DetectionConfig
from .geo import GeoIndex
from .models import Evidence, DetectionDecision


def canonicalize_trigger(trigger, geo: GeoIndex, config: DetectionConfig) -> Evidence:
    cell = geo.cell(trigger.latitude, trigger.longitude, config.h3_device_resolution)
    coarse = geo.parent(cell, config.h3_correlation_resolution)
    return Evidence(
        evidence_id=f"{trigger.device_id}:{trigger.seq}",
        device_id=trigger.device_id,
        seq=trigger.seq,
        observed_at_ms=trigger.observed_at_ms,
        h3_cell=cell,
        correlation_cell=coarse,
        motion_rms=trigger.motion_rms,
        motion_peak=trigger.motion_peak,
        transport=trigger.transport,
    )


def _dedupe_latest_per_device(evidence: list[Evidence]) -> list[Evidence]:
    latest: dict[str, Evidence] = {}
    for item in sorted(evidence, key=lambda e: (e.observed_at_ms, e.seq)):
        latest[item.device_id] = item
    return list(latest.values())


def _connected_components(items: list[Evidence], geo: GeoIndex, max_distance: int) -> list[list[Evidence]]:
    if not items:
        return []
    by_cell: dict[str, list[Evidence]] = defaultdict(list)
    for item in items:
        by_cell[item.correlation_cell].append(item)
    cells = sorted(by_cell)
    neighbours: dict[str, set[str]] = {c: set() for c in cells}
    for i, a in enumerate(cells):
        for b in cells[i:]:
            if geo.grid_distance(a, b) <= max_distance:
                neighbours[a].add(b); neighbours[b].add(a)
    seen: set[str] = set(); out: list[list[Evidence]] = []
    for start in cells:
        if start in seen: continue
        q=deque([start]); seen.add(start); component_cells=[]
        while q:
            c=q.popleft(); component_cells.append(c)
            for n in neighbours[c]:
                if n not in seen:
                    seen.add(n); q.append(n)
        out.append([e for c in component_cells for e in by_cell[c]])
    return out


def detect(evidence: list[Evidence], now_ms: int, geo: GeoIndex, config: DetectionConfig) -> DetectionDecision:
    recent = [e for e in evidence if 0 <= now_ms - e.observed_at_ms <= config.evidence_window_ms]
    recent = _dedupe_latest_per_device(recent)
    components = _connected_components(recent, geo, config.max_cluster_grid_distance)
    components.sort(key=lambda c: (len({e.device_id for e in c}), len({e.correlation_cell for e in c})), reverse=True)
    if not components:
        return DetectionDecision(False, (), (), (), None, None, "no recent evidence")
    best = components[0]
    devices = sorted({e.device_id for e in best})
    cells = sorted({e.correlation_cell for e in best})
    if len(devices) < config.min_devices:
        return DetectionDecision(False, tuple(devices), tuple(cells), tuple(sorted(e.evidence_id for e in best)), min(e.observed_at_ms for e in best), max(e.observed_at_ms for e in best), "insufficient distinct devices")
    if len(cells) < config.min_distinct_cells:
        return DetectionDecision(False, tuple(devices), tuple(cells), tuple(sorted(e.evidence_id for e in best)), min(e.observed_at_ms for e in best), max(e.observed_at_ms for e in best), "insufficient spatial diversity")
    return DetectionDecision(True, tuple(devices), tuple(cells), tuple(sorted(e.evidence_id for e in best)), min(e.observed_at_ms for e in best), max(e.observed_at_ms for e in best), "thresholds satisfied")


def warning_frontier(cells: list[str] | tuple[str, ...], geo: GeoIndex, ring_k: int) -> list[str]:
    footprint=set(cells); expanded=set()
    for c in footprint: expanded.update(geo.disk(c, ring_k))
    return sorted(expanded-footprint)


def stable_event_key(decision: DetectionDecision) -> str:
    seed = "|".join(decision.evidence_ids) + f"|{decision.first_observed_at_ms}"
    return hashlib.sha256(seed.encode()).hexdigest()[:16]
