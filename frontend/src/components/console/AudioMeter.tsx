import { useCallback, useState } from "react";
import { useLiveMessage } from "../../api/useLiveSocket";

// Meters are stacked segments, never a smooth bar, per the WLED-X house
// rules -- lime under 60%, gold to 85%, ember above.
const LEVEL_SEGMENTS = 12;

function segmentColor(index: number, total: number): string {
  const threshold = (index + 1) / total;
  if (threshold > 0.85) return "var(--ember)";
  if (threshold > 0.6) return "var(--gold)";
  return "var(--lime)";
}

export function AudioMeter() {
  const [level, setLevel] = useState(0);
  const [bands, setBands] = useState<number[]>([]);
  const [beat, setBeat] = useState(0);
  const [bpm, setBpm] = useState(0);

  const handleAudio = useCallback((message: Record<string, unknown>) => {
    setLevel(typeof message.level === "number" ? message.level : 0);
    setBands(Array.isArray(message.bands) ? (message.bands as number[]) : []);
    setBeat(typeof message.beat === "number" ? message.beat : 0);
    setBpm(typeof message.bpm === "number" ? message.bpm : 0);
  }, []);

  useLiveMessage("audio", handleAudio);

  return (
    <div className="audio-meter">
      <div
        className="audio-meter__beat-dot"
        style={{ opacity: 0.25 + beat * 0.75, transform: `scale(${1 + beat * 0.6})` }}
      />
      <div className="audio-meter__level">
        {Array.from({ length: LEVEL_SEGMENTS }, (_, i) => {
          const lit = Math.min(level, 1) * LEVEL_SEGMENTS > i;
          return (
            <div
              key={i}
              className="audio-meter__level-segment"
              style={{ background: lit ? segmentColor(i, LEVEL_SEGMENTS) : undefined }}
            />
          );
        })}
      </div>
      <div className="audio-meter__bands">
        {bands.map((b, i) => (
          <div key={i} className="audio-meter__band" style={{ height: `${Math.max(Math.min(b, 1), 0.03) * 100}%` }} />
        ))}
        {bands.length === 0 && <span className="audio-meter__idle">no audio signal</span>}
      </div>
      {bpm > 0 && <div className="audio-meter__bpm">{Math.round(bpm)} BPM</div>}
    </div>
  );
}
