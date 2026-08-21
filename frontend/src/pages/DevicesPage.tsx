import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { useDeviceStore } from "../store/useDeviceStore";
import { deviceDiscoveryApi } from "../api/resources";
import type { DiscoveredDevice } from "../api/resources";
import "./DevicesPage.css";

export function DevicesPage() {
  const { devices, loading, refresh, add, update, remove } = useDeviceStore();

  const [discovered, setDiscovered] = useState<DiscoveredDevice[]>([]);
  const [scanning, setScanning] = useState(false);
  const [scanError, setScanError] = useState<string | null>(null);
  const [addingIp, setAddingIp] = useState<string | null>(null);

  const [renamingId, setRenamingId] = useState<number | null>(null);
  const [renameValue, setRenameValue] = useState("");
  const [renameError, setRenameError] = useState<string | null>(null);

  const [manualName, setManualName] = useState("");
  const [manualIp, setManualIp] = useState("");
  const [manualLedCount, setManualLedCount] = useState("");
  const [manualError, setManualError] = useState<string | null>(null);
  const [manualSubmitting, setManualSubmitting] = useState(false);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  async function scan() {
    setScanning(true);
    setScanError(null);

    const [mdnsResult, scanResult] = await Promise.allSettled([
      deviceDiscoveryApi.mdns(),
      deviceDiscoveryApi.scan(),
    ]);

    const found: DiscoveredDevice[] = [];
    let failures = 0;
    if (mdnsResult.status === "fulfilled") found.push(...mdnsResult.value);
    else failures++;
    if (scanResult.status === "fulfilled") found.push(...scanResult.value);
    else failures++;

    const byIp = new Map<string, DiscoveredDevice>();
    for (const d of found) byIp.set(d.ip, d);
    setDiscovered([...byIp.values()]);

    if (failures === 2) setScanError("Discovery is unavailable right now. Try again later or add a device by IP.");
    else if (failures === 1) setScanError("One discovery method failed; showing partial results.");

    setScanning(false);
  }

  async function addDiscovered(d: DiscoveredDevice) {
    setAddingIp(d.ip);
    try {
      await add({ name: d.name, ip: d.ip, led_count: d.led_count });
      setDiscovered((prev) => prev.filter((x) => x.ip !== d.ip));
    } catch {
      setScanError(`Failed to add ${d.ip}.`);
    } finally {
      setAddingIp(null);
    }
  }

  async function submitManual(e: FormEvent) {
    e.preventDefault();
    setManualError(null);
    if (!manualName.trim() || !manualIp.trim()) {
      setManualError("Name and IP are required.");
      return;
    }
    setManualSubmitting(true);
    try {
      await add({
        name: manualName.trim(),
        ip: manualIp.trim(),
        led_count: manualLedCount ? Number(manualLedCount) : undefined,
      });
      setManualName("");
      setManualIp("");
      setManualLedCount("");
    } catch {
      setManualError("Failed to add device. Check the IP and try again.");
    } finally {
      setManualSubmitting(false);
    }
  }

  function startRename(id: number, currentName: string) {
    setRenamingId(id);
    setRenameValue(currentName);
    setRenameError(null);
  }

  async function commitRename(id: number, previousName: string) {
    const trimmed = renameValue.trim();
    setRenamingId(null);
    if (!trimmed || trimmed === previousName) return;
    try {
      await update(id, { name: trimmed });
    } catch {
      setRenameError(`Failed to rename device.`);
    }
  }

  const knownIps = new Set(devices.map((d) => d.ip));
  const newlyDiscovered = discovered.filter((d) => !knownIps.has(d.ip));

  return (
    <div className="page devices-page">
      <header className="devices-page__header">
        <h1>Devices</h1>
        <button className="btn btn--accent" onClick={() => void scan()} disabled={scanning}>
          {scanning ? "Scanning…" : "Scan network"}
        </button>
      </header>

      {scanError && <div className="banner banner--error">{scanError}</div>}

      {newlyDiscovered.length > 0 && (
        <section className="devices-page__section">
          <h2>Discovered</h2>
          <ul className="device-list">
            {newlyDiscovered.map((d) => (
              <li key={d.ip} className="device-row">
                <span className="device-row__dot device-row__dot--unknown" />
                <span className="device-row__name">{d.name || d.ip}</span>
                <span className="device-row__ip">{d.ip}</span>
                <span className="device-row__leds">{d.led_count} LEDs</span>
                <button
                  className="btn btn--small"
                  onClick={() => void addDiscovered(d)}
                  disabled={addingIp === d.ip}
                >
                  {addingIp === d.ip ? "Adding…" : "Add to project"}
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}

      <section className="devices-page__section">
        <h2>In project</h2>
        {loading && devices.length === 0 ? (
          <p className="devices-page__empty">Loading…</p>
        ) : devices.length === 0 ? (
          <p className="devices-page__empty">No devices yet. Scan the network or add one by IP below.</p>
        ) : (
          <ul className="device-list">
            {devices.map((d) => (
              <li key={d.id} className="device-row">
                <span
                  className={`device-row__dot ${d.online ? "device-row__dot--online" : "device-row__dot--offline"}`}
                  title={d.online ? "Online" : "Offline"}
                />
                {renamingId === d.id ? (
                  <input
                    className="device-row__rename-input"
                    autoFocus
                    value={renameValue}
                    onChange={(e) => setRenameValue(e.target.value)}
                    onBlur={() => void commitRename(d.id, d.name)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") e.currentTarget.blur();
                      if (e.key === "Escape") setRenamingId(null);
                    }}
                  />
                ) : (
                  <span className="device-row__name">{d.name}</span>
                )}
                <span className="device-row__ip">{d.ip}</span>
                <span className="device-row__leds">{d.led_count} LEDs</span>
                <button className="btn btn--small" onClick={() => startRename(d.id, d.name)}>
                  Rename
                </button>
                <button className="btn btn--small btn--danger" onClick={() => void remove(d.id)}>
                  Remove
                </button>
              </li>
            ))}
          </ul>
        )}
        {renameError && <p className="banner banner--error">{renameError}</p>}
      </section>

      <section className="devices-page__section">
        <h2>Add device by IP</h2>
        <form className="manual-add-form" onSubmit={(e) => void submitManual(e)}>
          <input
            type="text"
            placeholder="Name"
            value={manualName}
            onChange={(e) => setManualName(e.target.value)}
          />
          <input
            type="text"
            placeholder="192.168.1.50"
            value={manualIp}
            onChange={(e) => setManualIp(e.target.value)}
          />
          <input
            type="number"
            placeholder="LED count (optional)"
            value={manualLedCount}
            onChange={(e) => setManualLedCount(e.target.value)}
            min={0}
          />
          <button className="btn" type="submit" disabled={manualSubmitting}>
            {manualSubmitting ? "Adding…" : "Add"}
          </button>
        </form>
        {manualError && <p className="banner banner--error">{manualError}</p>}
      </section>
    </div>
  );
}
