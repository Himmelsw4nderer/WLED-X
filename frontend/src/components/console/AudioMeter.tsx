import { useCallback, useState } from "react";
import { useLiveMessage } from "../../api/useLiveSocket";

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
        <div className="audio-meter__level-fill" style={{ width: `${Math.min(level, 1) * 100}%` }} />
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
