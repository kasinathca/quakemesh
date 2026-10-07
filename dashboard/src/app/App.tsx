import { useEffect, useState } from "react";

import { Layout, type ViewId } from "../components/Layout";
import { AlertsView } from "../features/alerts/AlertsView";
import { DevicesView } from "../features/devices/DevicesView";
import { EventsView } from "../features/events/EventsView";
import { ExperimentsView } from "../features/experiments/ExperimentsView";
import { InfrastructureView } from "../features/infrastructure/InfrastructureView";
import { LiveMap } from "../features/map/LiveMap";
import { Overview } from "../features/overview/Overview";
import { ScenarioLab } from "../features/scenarios/ScenarioLab";
import { SessionView } from "../features/session/SessionView";
import { useControlPlane } from "./useControlPlane";

const views = new Set<ViewId>([
  "overview", "map", "scenarios", "events", "devices", "alerts", "experiments", "infrastructure", "session",
]);

function initialView(): ViewId {
  const hash = window.location.hash.slice(1) as ViewId;
  return views.has(hash) ? hash : "overview";
}

export function App() {
  const [view, setView] = useState<ViewId>(initialView);
  const control = useControlPlane();

  useEffect(() => {
    const update = () => setView(initialView());
    window.addEventListener("hashchange", update);
    return () => window.removeEventListener("hashchange", update);
  }, []);

  function navigate(next: ViewId): void {
    window.location.hash = next;
    setView(next);
  }

  const content = {
    overview: <Overview control={control} />,
    map: <LiveMap control={control} />,
    scenarios: <ScenarioLab control={control} />,
    events: <EventsView control={control} />,
    devices: <DevicesView control={control} />,
    alerts: <AlertsView control={control} />,
    experiments: <ExperimentsView control={control} />,
    infrastructure: <InfrastructureView control={control} />,
    session: <SessionView control={control} />,
  }[view];

  return (
    <Layout
      active={view}
      onNavigate={navigate}
      connection={control.connection}
      lastUpdated={control.snapshot.lastUpdated}
      error={control.error}
      environmentLabel={control.environment.label}
      region={control.environment.region}
    >
      {content}
    </Layout>
  );
}
