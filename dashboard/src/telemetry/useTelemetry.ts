import { useEffect, useRef } from "react";

import { API_BASE } from "../api/client";

interface TelemetryOptions {
  enabled: boolean;
  onUpdate: () => void;
  onConnected: () => void;
  onDisconnected: () => void;
}

export function useTelemetry({ enabled, onUpdate, onConnected, onDisconnected }: TelemetryOptions): void {
  const lastSequence = useRef(0);

  useEffect(() => {
    if (!enabled) return undefined;
    const source = new EventSource(`${API_BASE}/v1/telemetry/stream?after=${lastSequence.current}`);
    source.onopen = onConnected;
    source.addEventListener("scenario.stage", (event) => {
      const parsed = JSON.parse((event as MessageEvent<string>).data) as { sequence: number };
      if (parsed.sequence > lastSequence.current) {
        lastSequence.current = parsed.sequence;
        onUpdate();
      }
    });
    source.onerror = onDisconnected;
    return () => source.close();
  }, [enabled, onConnected, onDisconnected, onUpdate]);
}
