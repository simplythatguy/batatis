import { useEffect, useId, useRef, useState } from "react";
import { entryUnits, measurementText, metricPreview, parseMeasurement, type EntryUnit, type MetricUnit } from "./units";
import "./UnitInput.css";

export interface UnitInputProps {
  id?: string;
  label: string;
  unit: MetricUnit;
  value: string;
  onChange: (value: string) => void;
}

/** The draft includes its unit, so saving never depends on this control's local toggle state. */
export function UnitInput({ id, label, unit, value, onChange }: UnitInputProps) {
  const generated = useId();
  const inputId = id ?? generated;
  const [text, setText] = useState(value);
  const initial = parseMeasurement(value, unit);
  const [selected, setSelected] = useState<EntryUnit>(initial.kind === "value" && initial.enteredUnit.startsWith("ft") ? initial.enteredUnit : unit);
  const emitted = useRef(value);
  const parsed = parseMeasurement(text, unit, selected);
  useEffect(() => {
    if (value === emitted.current) return;
    emitted.current = value;
    setText(value);
    const parsed = parseMeasurement(value, unit);
    setSelected(parsed.kind === "value" && parsed.enteredUnit.startsWith("ft") ? parsed.enteredUnit : unit);
  }, [value, unit]);
  const change = (next: string, choice: EntryUnit) => {
    setText(next);
    setSelected(choice);
    emitted.current = measurementText(next, choice);
    onChange(emitted.current);
  };
  const toggle = (choice: EntryUnit) => {
    if (choice === selected) return;
    const number = text.trim().match(/^(\d+(?:\.\d*)?|\.\d+)\s*(?:[a-z²^2 ]+)?$/i)?.[1];
    // A compound feet-and-inches entry is converted as a whole when changing units.
    const next = number ?? (parsed.kind === "value" ? String(choice.startsWith("ft") ? parsed.value / (unit.endsWith("²") ? (unit === "cm²" ? 929.0304 : 0.09290304) : unit === "mm" ? 304.8 : 0.3048) : parsed.value) : text);
    change(next, choice);
  };
  return <div className="cf-unit-input">
    <div className="cf-inline-answer">
      <label className="cf-sr" htmlFor={inputId}>{label}</label>
      <input id={inputId} className="cf-uline is-number" type="text" inputMode="decimal" value={text}
        aria-invalid={parsed.kind === "error" || undefined} aria-describedby={`${inputId}-conversion`}
        onChange={(e) => {
          const next = e.target.value;
          const read = parseMeasurement(next, unit, selected);
          change(next, read.kind === "value" ? read.enteredUnit.startsWith("ft") ? read.enteredUnit : unit : selected);
        }} placeholder="e.g. 4" />
      <div className="cf-unit-toggle" role="group" aria-label="Units">
        {entryUnits(unit).map((choice) => <button key={choice} type="button" className="cf-chip" aria-pressed={selected === choice} onClick={() => toggle(choice)}>{choice}</button>)}
      </div>
    </div>
    <p id={`${inputId}-conversion`} className="cf-note cf-small" role={parsed.kind === "error" ? "alert" : "status"}>
      {parsed.kind === "value" ? metricPreview(parsed.value, unit) : parsed.kind === "error" ? parsed.error : ""}
    </p>
  </div>;
}
