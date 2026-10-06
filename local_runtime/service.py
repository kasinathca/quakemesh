from __future__ import annotations

from dataclasses import asdict
from threading import RLock

from quakemesh_core.config import DetectionConfig
from quakemesh_core.correlation import canonicalize_trigger, detect
from quakemesh_core.events import create_event, event_should_merge, merge_event
from quakemesh_core.geo import GeoIndex
from quakemesh_core.motion import MotionFeatures, passes_motion_gate
from quakemesh_core.validation import parse_heartbeat, parse_trigger, validate_observation_time

from .repository import SQLiteRepository


class QuakeMeshService:
    def __init__(
        self,
        repository: SQLiteRepository,
        geo: GeoIndex,
        config: DetectionConfig,
    ):
        self.repository = repository
        self.repo = repository  # Backward-compatible local integration alias.
        self.geo = geo
        self.config = config
        self._correlation_lock = RLock()

    @staticmethod
    def _provenance(run_id: str | None) -> str:
        return "scenario" if run_id else "physical"

    def _require_run(self, run_id: str | None) -> None:
        if run_id is None:
            return
        run = self.repository.get_scenario_run(run_id)
        if run is None:
            raise ValueError("unknown scenario run")
        if run["status"] != "RUNNING":
            raise ValueError("scenario run is not active")

    def _stage(
        self,
        run_id: str | None,
        occurred_at_ms: int,
        code: str,
        message: str,
        data: dict | None = None,
        *,
        component: str = "local-runtime",
        severity: str = "info",
        status: str = "COMPLETED",
        device_id: str | None = None,
        event_id: str | None = None,
        alert_id: str | None = None,
        duration_ms: int | None = None,
    ) -> None:
        if run_id is None:
            return
        self.repository.add_scenario_stage(
            run_id,
            occurred_at_ms,
            code,
            component,
            severity,
            message,
            data,
            status=status,
            device_id=device_id,
            event_id=event_id,
            alert_id=alert_id,
            duration_ms=duration_ms,
        )

    def heartbeat(
        self,
        payload: dict,
        transport: str = "http",
        received_at_ms: int | None = None,
        run_id: str | None = None,
    ) -> dict:
        self._require_run(run_id)
        occurrence = received_at_ms or int(payload.get("observed_at_ms", 0))
        device_hint = str(payload.get("device_id", "")) or None
        self._stage(
            run_id,
            occurrence,
            "INGRESS_ACCEPTED",
            "Heartbeat accepted by local ingress",
            {"kind": "heartbeat"},
            device_id=device_hint,
        )
        heartbeat = parse_heartbeat(payload, transport)
        if received_at_ms is not None:
            validate_observation_time(
                heartbeat.observed_at_ms,
                received_at_ms,
                self.config.max_clock_skew_ms,
            )
        self._stage(
            run_id,
            occurrence,
            "SCHEMA_VALIDATED",
            "Heartbeat schema and observation time accepted",
            {"kind": "heartbeat"},
            device_id=heartbeat.device_id,
        )
        cell = self.geo.cell(
            heartbeat.latitude,
            heartbeat.longitude,
            self.config.h3_device_resolution,
        )
        coarse = self.geo.parent(cell, self.config.h3_correlation_resolution)
        self._stage(
            run_id,
            occurrence,
            "H3_CANONICALIZED",
            "Heartbeat location canonicalized to H3 cells",
            {"correlation_cell": coarse},
            device_id=heartbeat.device_id,
        )
        accepted = self.repository.update_device(
            heartbeat.device_id,
            heartbeat.seq,
            heartbeat.observed_at_ms,
            cell,
            coarse,
            transport,
            heartbeat.fcm_token,
            self._provenance(run_id),
            run_id,
        )
        self._stage(
            run_id,
            occurrence,
            "REPLAY_GATE_EVALUATED",
            "Heartbeat sequence accepted" if accepted else "Heartbeat replay rejected",
            {"passed": accepted, "sequence": heartbeat.seq},
            status="PASSED" if accepted else "FAILED",
            severity="info" if accepted else "warning",
            device_id=heartbeat.device_id,
        )
        return {
            "accepted": accepted,
            "device_id": heartbeat.device_id,
            "h3_cell": cell,
            "correlation_cell": coarse,
        }

    def trigger(
        self,
        payload: dict,
        transport: str = "http",
        received_at_ms: int | None = None,
        run_id: str | None = None,
    ) -> dict:
        self._require_run(run_id)
        occurrence = received_at_ms or int(payload.get("observed_at_ms", 0))
        device_hint = str(payload.get("device_id", "")) or None
        self._stage(
            run_id,
            occurrence,
            "INGRESS_ACCEPTED",
            "Trigger accepted by local ingress",
            {"kind": "trigger"},
            device_id=device_hint,
        )
        trigger = parse_trigger(payload, transport)
        if received_at_ms is not None:
            validate_observation_time(
                trigger.observed_at_ms,
                received_at_ms,
                self.config.max_clock_skew_ms,
            )
        self._stage(
            run_id,
            occurrence,
            "SCHEMA_VALIDATED",
            "Trigger schema and observation time accepted",
            device_id=trigger.device_id,
        )
        evidence = canonicalize_trigger(trigger, self.geo, self.config)
        self._stage(
            run_id,
            occurrence,
            "H3_CANONICALIZED",
            "Trigger location canonicalized to H3 cells",
            {"correlation_cell": evidence.correlation_cell},
            device_id=evidence.device_id,
        )
        provenance_type = self._provenance(run_id)

        # FastAPI sync endpoints execute in a worker pool. Keep evidence acceptance,
        # correlation and authoritative event mutation in one local critical section.
        with self._correlation_lock:
            state_accepted = self.repository.update_device(
                evidence.device_id,
                evidence.seq,
                evidence.observed_at_ms,
                evidence.h3_cell,
                evidence.correlation_cell,
                transport,
                provenance_type=provenance_type,
                scenario_run_id=run_id,
            )
            self._stage(
                run_id,
                occurrence,
                "REPLAY_GATE_EVALUATED",
                "Trigger sequence accepted" if state_accepted else "Trigger replay rejected",
                {"passed": state_accepted, "sequence": evidence.seq},
                status="PASSED" if state_accepted else "FAILED",
                severity="info" if state_accepted else "warning",
                device_id=evidence.device_id,
            )
            if not state_accepted:
                return {
                    "accepted": False,
                    "duplicate_or_replay": True,
                    "evidence_id": evidence.evidence_id,
                }

            motion_passed = passes_motion_gate(
                MotionFeatures(evidence.motion_rms, evidence.motion_peak, 1),
                self.config,
            )
            self._stage(
                run_id,
                occurrence,
                "MOTION_GATE_EVALUATED",
                "Motion gate passed" if motion_passed else "Motion gate failed",
                {
                    "passed": motion_passed,
                    "motion_rms": evidence.motion_rms,
                    "motion_peak": evidence.motion_peak,
                },
                status="PASSED" if motion_passed else "FAILED",
                severity="info" if motion_passed else "warning",
                device_id=evidence.device_id,
            )
            if not motion_passed:
                return {
                    "accepted": False,
                    "below_motion_gate": True,
                    "evidence_id": evidence.evidence_id,
                }

            evidence_accepted = self.repository.add_evidence(
                evidence,
                scenario_run_id=run_id,
            )
            if not evidence_accepted:
                return {
                    "accepted": False,
                    "duplicate_or_replay": True,
                    "evidence_id": evidence.evidence_id,
                }
            self._stage(
                run_id,
                occurrence,
                "EVIDENCE_STORED",
                "Canonical evidence stored",
                {
                    "evidence_id": evidence.evidence_id,
                    "correlation_cell": evidence.correlation_cell,
                },
                device_id=evidence.device_id,
            )
            self._stage(
                run_id,
                occurrence,
                "CORRELATION_STARTED",
                "Correlation gates started for isolated provenance scope",
                {"provenance_type": provenance_type},
                device_id=evidence.device_id,
            )
            recent = self.repository.recent_evidence(
                occurrence - self.config.evidence_window_ms,
                run_id,
            )
            decision = detect(recent, occurrence, self.geo, self.config)
            recency_passed = bool(decision.evidence_ids)
            device_passed = len(decision.device_ids) >= self.config.min_devices
            spatial_passed = len(decision.cells) >= self.config.min_distinct_cells
            coherence_passed = bool(decision.cells)
            gates = (
                (
                    "RECENCY_GATE_EVALUATED",
                    recency_passed,
                    "Evidence recency window evaluated",
                    {"evidence_count": len(decision.evidence_ids)},
                ),
                (
                    "DEVICE_DIVERSITY_GATE_EVALUATED",
                    device_passed,
                    "Distinct-device threshold evaluated",
                    {
                        "observed": len(decision.device_ids),
                        "required": self.config.min_devices,
                    },
                ),
                (
                    "SPATIAL_DIVERSITY_GATE_EVALUATED",
                    spatial_passed,
                    "Distinct-cell threshold evaluated",
                    {
                        "observed": len(decision.cells),
                        "required": self.config.min_distinct_cells,
                    },
                ),
                (
                    "COHERENCE_GATE_EVALUATED",
                    coherence_passed,
                    "Spatial cluster coherence evaluated",
                    {"reason": decision.reason},
                ),
            )
            for code, passed, message, data in gates:
                self._stage(
                    run_id,
                    occurrence,
                    code,
                    message,
                    {"passed": passed, **data},
                    status="PASSED" if passed else "FAILED",
                    severity="info" if passed else "warning",
                    device_id=evidence.device_id,
                )

            response = {
                "accepted": True,
                "evidence_id": evidence.evidence_id,
                "decision": asdict(decision),
            }
            if not decision.confirmed:
                return response

            active_events = self.repository.active_events(
                occurrence - self.config.event_merge_window_ms,
                provenance_type,
                run_id,
            )
            event = next(
                (
                    item
                    for item in active_events
                    if event_should_merge(item, decision, self.geo, self.config)
                ),
                None,
            )
            if event:
                event = merge_event(event, decision, occurrence, self.geo, self.config)
            else:
                event = create_event(decision, occurrence, self.geo, self.config)
                event.provenance_type = provenance_type
                event.scenario_run_id = run_id
            self.repository.save_event(event)
            self._stage(
                run_id,
                occurrence,
                "EVENT_TRANSITIONED",
                "Experimental event confirmed",
                {"version": event.version},
                event_id=event.event_id,
            )
            self._stage(
                run_id,
                occurrence,
                "FOOTPRINT_COMPUTED",
                "Detection footprint computed from confirmed evidence",
                {"cell_count": len(event.detection_footprint)},
                event_id=event.event_id,
            )
            self._stage(
                run_id,
                occurrence,
                "FRONTIER_COMPUTED",
                "Warning frontier computed around the footprint",
                {"cell_count": len(event.warning_frontier)},
                event_id=event.event_id,
            )
            target_cells = set(event.detection_footprint) | set(event.warning_frontier)
            targets = self.repository.target_devices(
                target_cells,
                occurrence - 120_000,
                provenance_type,
                run_id,
            )
            self._stage(
                run_id,
                occurrence,
                "TARGETING_EVALUATED",
                "Local target records selected without claiming device delivery",
                {"target_count": len(targets)},
                event_id=event.event_id,
            )
            newly_alerted: list[str] = []
            for device in targets:
                recorded = self.repository.record_alert(
                    event.event_id,
                    event.version,
                    device["device_id"],
                    occurrence,
                    device["transport"],
                    provenance_type,
                    run_id,
                    "TARGETED",
                )
                if not recorded:
                    continue
                newly_alerted.append(device["device_id"])
                alert_id = f"{event.event_id}:{device['device_id']}"
                self._stage(
                    run_id,
                    occurrence,
                    "ALERT_RECORDED",
                    "Local alert target record created",
                    {"status": "TARGETED", "transport": device["transport"]},
                    device_id=device["device_id"],
                    event_id=event.event_id,
                    alert_id=alert_id,
                )
            response["event"] = event.as_dict()
            response["new_alert_devices"] = newly_alerted
            return response

    def acknowledge_alert(
        self,
        alert_id: str,
        acknowledged_at_ms: int,
        source: str,
        device_id: str | None = None,
    ) -> tuple[dict | None, bool]:
        alert, changed = self.repository.acknowledge_alert(
            alert_id,
            acknowledged_at_ms,
            source,
            device_id,
        )
        if alert and changed:
            self._stage(
                alert.get("scenario_run_id"),
                acknowledged_at_ms,
                "ALERT_ACKNOWLEDGED",
                "Alert acknowledgement stored",
                {"acknowledgement_source": source},
                device_id=alert["device_id"],
                event_id=alert["event_id"],
                alert_id=alert["alert_id"],
            )
        return alert, changed

    def resolve(self, current_ms: int) -> int:
        return self.repository.resolve_stale(
            current_ms - self.config.event_resolve_after_ms,
            current_ms,
        )
