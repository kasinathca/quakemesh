from __future__ import annotations

from .models import EventRecord, EventStatus, DetectionDecision
from .correlation import stable_event_key, warning_frontier
from .geo import GeoIndex
from .config import DetectionConfig


def create_event(decision: DetectionDecision, now_ms: int, geo: GeoIndex, config: DetectionConfig) -> EventRecord:
    if not decision.confirmed or decision.first_observed_at_ms is None or decision.last_observed_at_ms is None:
        raise ValueError("cannot create event from unconfirmed decision")
    footprint=list(decision.cells)
    return EventRecord(
        event_id=f"QM-{decision.first_observed_at_ms}-{stable_event_key(decision)}",
        status=EventStatus.CONFIRMED,
        created_at_ms=now_ms,
        updated_at_ms=now_ms,
        first_observed_at_ms=decision.first_observed_at_ms,
        last_observed_at_ms=decision.last_observed_at_ms,
        device_ids=list(decision.device_ids),
        detection_footprint=footprint,
        warning_frontier=warning_frontier(footprint, geo, config.warning_ring_k),
        evidence_ids=list(decision.evidence_ids),
        version=1,
    )


def event_should_merge(event: EventRecord, decision: DetectionDecision, geo: GeoIndex, config: DetectionConfig) -> bool:
    if event.status == EventStatus.RESOLVED or decision.first_observed_at_ms is None:
        return False
    if decision.first_observed_at_ms - event.last_observed_at_ms > config.event_merge_window_ms:
        return False
    current=set(event.detection_footprint); incoming=set(decision.cells)
    if current & incoming: return True
    return any(geo.grid_distance(a,b) <= config.max_cluster_grid_distance for a in current for b in incoming)


def merge_event(event: EventRecord, decision: DetectionDecision, now_ms: int, geo: GeoIndex, config: DetectionConfig) -> EventRecord:
    next_last=max(event.last_observed_at_ms, decision.last_observed_at_ms or event.last_observed_at_ms)
    next_devices=sorted(set(event.device_ids)|set(decision.device_ids))
    next_evidence=sorted(set(event.evidence_ids)|set(decision.evidence_ids))
    next_footprint=sorted(set(event.detection_footprint)|set(decision.cells))

    # DynamoDB Streams are at-least-once. Replaying a decision that contributes no
    # new observation must not manufacture a new event version or alert cycle.
    changed=(
        next_last != event.last_observed_at_ms
        or next_devices != sorted(event.device_ids)
        or next_evidence != sorted(event.evidence_ids)
        or next_footprint != sorted(event.detection_footprint)
    )
    if not changed:
        return event

    event.updated_at_ms=now_ms
    event.last_observed_at_ms=next_last
    event.device_ids=next_devices
    event.evidence_ids=next_evidence
    event.detection_footprint=next_footprint
    event.warning_frontier=warning_frontier(event.detection_footprint, geo, config.warning_ring_k)
    event.version += 1
    return event
