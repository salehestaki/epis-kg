"use client";

import { useEffect, useRef, useState } from "react";

// Subscribes to the API's WebSocket and invokes `onUpdate` (debounced) whenever
// the reasoning worker persists a new document.
export function useGraphSocket(onUpdate: () => void): {
  connected: boolean;
} {
  const [connected, setConnected] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    const url =
      process.env.NEXT_PUBLIC_WS_URL ?? "ws://localhost:8000/ws/graph";
    let socket: WebSocket | null = null;
    let closed = false;
    let attempts = 0;
    const MAX_ATTEMPTS = 6;

    const connect = () => {
      attempts += 1;
      socket = new WebSocket(url);
      socket.onopen = () => {
        attempts = 0;
        setConnected(true);
      };
      socket.onclose = () => {
        setConnected(false);
        // Exponential backoff, and give up after a few tries (e.g. demo mode
        // with no realtime backend) so we don't hammer the network forever.
        if (!closed && attempts < MAX_ATTEMPTS) {
          setTimeout(connect, Math.min(3000 * attempts, 15000));
        }
      };
      socket.onerror = () => socket?.close();
      socket.onmessage = (evt) => {
        try {
          const msg = JSON.parse(evt.data);
          if (msg.type === "graph_updated") {
            if (timer.current) clearTimeout(timer.current);
            timer.current = setTimeout(onUpdate, 800);
          }
        } catch {
          /* ignore malformed frames */
        }
      };
    };

    connect();
    return () => {
      closed = true;
      if (timer.current) clearTimeout(timer.current);
      socket?.close();
    };
  }, [onUpdate]);

  return { connected };
}
