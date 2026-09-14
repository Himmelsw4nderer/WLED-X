import { useEffect, useState } from "react";
import { audioApi } from "../../api/resources";
import { useConsoleStore } from "../../store/useConsoleStore";

// The console has a single global audio source that every audio-reading node
// falls back to (see effects/engine.py `audio_source`). This picks which
// configured source is live; per-source device wiring lives in
// AudioSourcePicker. The authoritative value comes from the console_state
// broadcast via the store.
export function GlobalSourceSelect() {
  const audioSource = useConsoleStore((s) => s.audio_source);
  const setAudioSource = useConsoleStore((s) => s.setAudioSource);
  const [names, setNames] = useState<string[]>([]);

  useEffect(() => {
    let cancelled = false;
    audioApi
      .sources()
      .then((sources) => {
        if (!cancelled) setNames(sources.map((s) => s.name));
      })
      .catch(() => {
        if (!cancelled) setNames([]);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // Keep the current value selectable even if it isn't in the fetched list.
  const options = names.includes(audioSource) ? names : [audioSource, ...names];

  return (
    <div className="global-source-select">
      <div className="console-card__sublabel">Audio source</div>
      <select
        value={audioSource}
        onChange={(e) => setAudioSource(e.target.value)}
      >
        {options.map((name) => (
          <option key={name} value={name}>
            {name}
          </option>
        ))}
      </select>
    </div>
  );
}
