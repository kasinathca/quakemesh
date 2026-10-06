import { useEffect, useRef } from "react";

import { API_BASE } from "../api/client";

interface TelemetryOptions {
  onUpdate: () => void;
  onConnected: () => void;
  onDisconnected: () => void;
}

export function useTelemetry({ onUpdate, onConnected, onDisconnected }: TelemetryOptions): void {
  const lastSequence = useRef(0);

  useEffect(() => {
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
  }, [onConnected, onDisconnected, onUpdate]);
}
