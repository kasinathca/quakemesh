import type { ReactNode } from "react";

export function DataState({ children }: { children?: ReactNode }) {
  return <div className="data-state">{children ?? "Waiting for data"}</div>;
}
