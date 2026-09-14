import type { CSSProperties, ReactNode } from "react";
import type { ControlAccent } from "../controls/Fader";
import "./ConsoleCard.css";

interface ConsoleCardProps {
  title: string;
  accent?: ControlAccent;
  actions?: ReactNode;
  className?: string;
  children: ReactNode;
}

/** The one card shell every panel on the console page is built from -- a
 * title, an optional right-aligned action (a button, a meta readout), and a
 * body. Every card getting its own hand-rolled header (different font sizes,
 * different alignment, some with no title at all) is exactly what made the
 * page read as inconsistent; this is the single place that pattern lives. */
export function ConsoleCard({ title, accent = "gold", actions, className, children }: ConsoleCardProps) {
  return (
    <section
      className={`console-card panel${className ? ` ${className}` : ""}`}
      style={{ "--console-card-accent": `var(--${accent})` } as CSSProperties}
    >
      <div className="console-card__head">
        <h2 className="console-card__title">{title}</h2>
        {actions && <div className="console-card__actions">{actions}</div>}
      </div>
      <div className="console-card__body">{children}</div>
    </section>
  );
}
