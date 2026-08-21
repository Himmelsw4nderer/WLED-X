import { useCallback, useEffect, useRef, useState } from "react";

/**
 * Local slider state that mirrors a remote value but throttles outgoing
 * commits to one per animation frame, so dragging doesn't flood the WS.
 * Remote updates are ignored while the user is actively dragging so an
 * in-flight broadcast can't yank the handle out from under their cursor.
 */
export function useThrottledSlider(remoteValue: number, commit: (value: number) => void) {
  const [local, setLocal] = useState(remoteValue);
  const draggingRef = useRef(false);
  const pendingRef = useRef<number | null>(null);
  const frameRef = useRef<number | null>(null);

  useEffect(() => {
    if (!draggingRef.current) setLocal(remoteValue);
  }, [remoteValue]);

  useEffect(
    () => () => {
      if (frameRef.current !== null) cancelAnimationFrame(frameRef.current);
    },
    [],
  );

  const onChange = useCallback(
    (value: number) => {
      setLocal(value);
      pendingRef.current = value;
      if (frameRef.current === null) {
        frameRef.current = requestAnimationFrame(() => {
          frameRef.current = null;
          if (pendingRef.current !== null) {
            commit(pendingRef.current);
            pendingRef.current = null;
          }
        });
      }
    },
    [commit],
  );

  const onDragStart = useCallback(() => {
    draggingRef.current = true;
  }, []);

  const onDragEnd = useCallback(() => {
    draggingRef.current = false;
  }, []);

  return { local, onChange, onDragStart, onDragEnd };
}
