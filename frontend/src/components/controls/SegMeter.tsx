import "./controls.css";

interface SegMeterProps {
  /** Normalised fill, 0..1 (clamped). */
  value: number;
  /** Number of discrete segments. */
  segments?: number;
  orientation?: "horizontal" | "vertical";
  /** Optional peak-hold marker, 0..1. */
  peak?: number;
}

// Stacked segments, never a smooth bar (WLED-X house rule): lime under 60%,
// gold to 85%, ember above. Shared by the audio meter, the hype readout and
// the 3D viewport HUD so they all read the same way.
function segmentColor(fraction: number): string {
  if (fraction > 0.85) return "var(--ember)";
  if (fraction > 0.6) return "var(--gold)";
  return "var(--lime)";
}

export function SegMeter({ value, segments = 12, orientation = "horizontal", peak }: SegMeterProps) {
  const clamped = Math.max(0, Math.min(1, value));
  const peakIndex =
    peak != null ? Math.round(Math.max(0, Math.min(1, peak)) * segments) - 1 : -1;

  return (
    <div className={`seg-meter seg-meter--${orientation} well`} role="meter" aria-valuenow={clamped}>
      {Array.from({ length: segments }, (_, i) => {
        // Vertical meters fill from the bottom, so flip the index.
        const ordinal = orientation === "vertical" ? segments - 1 - i : i;
        const fraction = (ordinal + 1) / segments;
        const lit = clamped * segments > ordinal;
        return (
          <span
            key={i}
            className={`seg-meter__seg ${lit ? "seg-meter__seg--lit" : ""} ${
              ordinal === peakIndex ? "seg-meter__seg--peak" : ""
            }`}
            style={lit ? { background: segmentColor(fraction) } : undefined}
          />
        );
      })}
    </div>
  );
}
