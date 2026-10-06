import {
  Activity,
  Bell,
  Boxes,
  FlaskConical,
  Gauge,
  Map,
  RadioTower,
  Server,
  Smartphone,
} from "lucide-react";
import type { ReactNode } from "react";

import type { ConnectionState } from "../types/contracts";
import { StatusBadge } from "./StatusBadge";

export type ViewId =
  | "overview"
  | "map"
  | "scenarios"
  | "events"
  | "devices"
  | "alerts"
  | "experiments"
  | "infrastructure"
  | "session";

const navigation: Array<{ id: ViewId; label: string; icon: typeof Gauge }> = [
  { id: "overview", label: "Overview", icon: Gauge },
  { id: "map", label: "Live Map", icon: Map },
  { id: "scenarios", label: "Scenario Lab", icon: FlaskConical },
  { id: "events", label: "Events", icon: Activity },
  { id: "devices", label: "Devices", icon: Smartphone },
  { id: "alerts", label: "Alerts", icon: Bell },
  { id: "experiments", label: "Experiments", icon: Boxes },
  { id: "infrastructure", label: "Infrastructure", icon: Server },
  { id: "session", label: "Session", icon: RadioTower },
];

interface LayoutProps {
  active: ViewId;
  onNavigate: (view: ViewId) => void;
  connection: ConnectionState;
  lastUpdated: number | null;
  error: string | null;
  children: ReactNode;
}

export function Layout({ active, onNavigate, connection, lastUpdated, error, children }: LayoutProps) {
  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">QM</div>
          <div><strong>QuakeMesh</strong><span>Operations console</span></div>
        </div>
        <nav aria-label="Primary navigation">
          {navigation.map(({ id, label, icon: Icon }) => (
            <button
              className={active === id ? "active" : ""}
              key={id}
              onClick={() => onNavigate(id)}
              type="button"
            >
              <Icon size={18} aria-hidden="true" />
              <span>{label}</span>
            </button>
          ))}
        </nav>
        <div className="scope-label">Academic prototype<br />Not an official warning system</div>
      </aside>
      <div className="workspace">
        <header className="topbar">
          <div>
            <h1>{navigation.find((item) => item.id === active)?.label}</h1>
            <span>{lastUpdated ? `Updated ${new Date(lastUpdated).toLocaleTimeString()}` : "Waiting for data"}</span>
          </div>
          <div className="connection-block" title={error ?? undefined}>
            <StatusBadge value={connection} />
            <span>LOCAL</span>
          </div>
        </header>
        {connection === "disconnected" ? (
          <div className="connection-banner" role="status">
            API disconnected. The last verified snapshot remains visible while recovery continues.
          </div>
        ) : null}
        <main>{children}</main>
      </div>
    </div>
  );
}
