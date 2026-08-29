import { useEffect, useRef, useState } from "react";
import { useConsoleStore } from "../../store/useConsoleStore";

// The backend only broadcasts console_state on change (hit/set), not every
// tick, so we animate the decay locally instead of waiting on broadcasts.
// This mirrors `settings.hype_decay_seconds`'s backend default -- it isn't
// sent over the wire, so if that setting changes server-side this visual
// will drift slightly out of sync with the actual render-loop decay.
const HYPE_DECAY_SECONDS = 6;

export function HitButton() {
  const hype = useConsoleStore((s) => s.hype);
  const hit = useConsoleStore((s) => s.hit);
  const [displayHype, setDisplayHype] = useState(hype);
  const hitAtRef = useRef(0);

  useEffect(() => {
    hitAtRef.current = performance.now() - (1 - hype) * HYPE_DECAY_SECONDS * 1000;
  }, [hype]);

  useEffect(() => {
    let frame: number;
    const tick = () => {
      const elapsed = (performance.now() - hitAtRef.current) / 1000;
      const remaining = Math.max(1 - elapsed / HYPE_DECAY_SECONDS, 0);
      setDisplayHype(remaining);
      frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, []);

  function handleHit() {
    hitAtRef.current = performance.now();
    setDisplayHype(1);
    hit();
  }

  return (
    <div className="hit-button">
      <button className="hit-button__btn" onClick={handleHit}>
        HIT!
      </button>
      <div className="hit-button__meter">
        <div className="hit-button__meter-fill" style={{ width: `${displayHype * 100}%` }} />
      </div>
    </div>
  );
}
