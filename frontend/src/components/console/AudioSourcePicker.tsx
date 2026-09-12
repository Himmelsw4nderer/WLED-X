import { useCallback, useEffect, useState } from "react";
import { audioApi } from "../../api/resources";
import type { AudioDeviceOption, AudioSource, AudioSourceUpdate } from "../../types";

// Fixed slots the render loop and every audio-reading node type refer to by
// name (see the audio nodes' "Source" param) -- not arbitrary user rows, so
// this just has two fixed pickers rather than a generic add/remove list.
const SLOTS: { name: string; label: string }[] = [
  { name: "desktop", label: "Desktop audio" },
  { name: "mic", label: "Microphone" },
];

const UNKNOWN_OPTION = "__unknown__";

export function AudioSourcePicker() {
  const [devices, setDevices] = useState<AudioDeviceOption[]>([]);
  const [sources, setSources] = useState<Record<string, AudioSource>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const [deviceList, sourceList] = await Promise.all([audioApi.devices(), audioApi.sources()]);
      setDevices(deviceList);
      setSources(Object.fromEntries(sourceList.map((s) => [s.name, s])));
      setError(null);
    } catch {
      setError("Couldn't load audio devices.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  async function updateSource(name: string, patch: AudioSourceUpdate) {
    const previous = sources[name];
    if (!previous) return;
    setSources((s) => ({ ...s, [name]: { ...previous, ...patch } }));
    try {
      const saved = await audioApi.updateSource(name, patch);
      setSources((s) => ({ ...s, [name]: saved }));
    } catch {
      setSources((s) => ({ ...s, [name]: previous }));
      setError(`Couldn't update ${name}.`);
    }
  }

  if (loading) return null;

  const loopbackOptions = devices.filter((d) => d.mode === "loopback");
  const inputOptions = devices.filter((d) => d.mode === "input");

  return (
    <div className="audio-source-picker">
      {error && <p className="audio-source-picker__error">{error}</p>}
      {SLOTS.map(({ name, label }) => {
        const source = sources[name];
        if (!source) return null;
        const selected = devices.find((d) => d.mode === source.mode && d.device === source.device);

        return (
          <div key={name} className="audio-source-picker__row">
            <label className="audio-source-picker__enabled console-card__row-label">
              <input
                type="checkbox"
                checked={source.enabled}
                onChange={(e) => void updateSource(name, { enabled: e.target.checked })}
              />
              {label}
            </label>
            <select
              className="audio-source-picker__select"
              value={selected?.id ?? UNKNOWN_OPTION}
              disabled={!source.enabled}
              onChange={(e) => {
                const option = devices.find((d) => d.id === e.target.value);
                if (option) void updateSource(name, { mode: option.mode, device: option.device });
              }}
            >
              {!selected && (
                <option value={UNKNOWN_OPTION} disabled>
                  {source.device ?? "unknown device"} (not currently available)
                </option>
              )}
              <optgroup label="System audio">
                {loopbackOptions.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.label}
                  </option>
                ))}
              </optgroup>
              <optgroup label="Microphone / line-in">
                {inputOptions.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.label}
                  </option>
                ))}
              </optgroup>
            </select>
          </div>
        );
      })}
    </div>
  );
}
