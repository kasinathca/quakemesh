import type { ControlPlane } from "../../app/types";
import { DataState } from "../../components/DataState";
import { Panel } from "../../components/Panel";
import { EventMap } from "./EventMap";

export function LiveMap({ control }: { control: ControlPlane }) {
  const event = control.snapshot.events?.[0] ?? null;
  return (
    <div className="page-stack">
      <Panel title="Live event geometry" description="Detection footprint and warning frontier; network tiles are optional.">
        <EventMap event={event} />
      </Panel>
      <Panel title="Geometry inventory">
        {event ? (
          <div className="two-column compact">
            <div><h3>Footprint</h3><div className="token-list">{event.detection_footprint.map((cell) => <code key={cell}>{cell}</code>)}</div></div>
            <div><h3>Frontier</h3><div className="token-list">{event.warning_frontier.map((cell) => <code key={cell}>{cell}</code>)}</div></div>
          </div>
        ) : <DataState>No confirmed event geometry</DataState>}
      </Panel>
    </div>
  );
}
