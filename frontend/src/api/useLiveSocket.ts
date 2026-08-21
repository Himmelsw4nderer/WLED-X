import { useEffect } from "react";
import { liveSocket } from "./ws";

/** Connects the shared live socket once per app and subscribes to a message type. */
export function useLiveMessage(type: string, handler: (message: Record<string, unknown>) => void) {
  useEffect(() => {
    liveSocket.connect();
    return liveSocket.on(type, handler);
  }, [type, handler]);
}
