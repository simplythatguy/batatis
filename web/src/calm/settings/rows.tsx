/** Settings rows and choice chips. */
import type { ReactNode } from "react";

export function Chips<T extends string>({ options, value, onPick, label }: { options: { value: T; label: string }[]; value: T | undefined; onPick: (v: T) => void; label: string }) {
  return (
    <div className="cf-chips" role="group" aria-label={label}>
      {options.map((o) => (
        <button key={o.value} type="button" className="cf-chip" aria-pressed={value === o.value} onClick={() => onPick(o.value)}>{o.label}</button>
      ))}
    </div>
  );
}

export function Row({ label, children, action }: { label: string; children: ReactNode; action?: ReactNode }) {
  return (
    <div className="ac-row">
      <span className="ac-row-label">{label}</span>
      <span className="ac-row-value">{children}</span>
      {action && <span className="ac-row-action">{action}</span>}
    </div>
  );
}
