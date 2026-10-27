/** Measurements cross this boundary once; facts and rule limits remain in the requested metric unit. */
export type MetricUnit = "m" | "mm" | "m²" | "cm²";
export type EntryUnit = MetricUnit | "ft" | "ft²";
export type Measurement =
  | { kind: "empty" }
  | { kind: "error"; error: string }
  | { kind: "value"; value: number; quote: string; enteredUnit: EntryUnit };

const AMOUNT = "(?:\\d+(?:\\.\\d*)?|\\.\\d+)";
const SIMPLE = new RegExp(`^(${AMOUNT})\\s*(.*?)$`);
const FEET_INCHES = new RegExp(`^(${AMOUNT})\\s*(?:ft|foot|feet|')\\s*(?:and\\s+)?(${AMOUNT})\\s*(?:in|inch|inches|\")?$`, "i");
const LENGTH: Record<string, { factor: number; unit: EntryUnit }> = {
  m: { factor: 1, unit: "m" }, metre: { factor: 1, unit: "m" }, metres: { factor: 1, unit: "m" }, meter: { factor: 1, unit: "m" }, meters: { factor: 1, unit: "m" },
  cm: { factor: 0.01, unit: "m" }, centimetres: { factor: 0.01, unit: "m" }, centimeters: { factor: 0.01, unit: "m" },
  mm: { factor: 0.001, unit: "mm" }, millimetres: { factor: 0.001, unit: "mm" }, millimeters: { factor: 0.001, unit: "mm" },
  ft: { factor: 0.3048, unit: "ft" }, foot: { factor: 0.3048, unit: "ft" }, feet: { factor: 0.3048, unit: "ft" }, "'": { factor: 0.3048, unit: "ft" },
  in: { factor: 0.0254, unit: "ft" }, inch: { factor: 0.0254, unit: "ft" }, inches: { factor: 0.0254, unit: "ft" }, '"': { factor: 0.0254, unit: "ft" },
};
const AREA: Record<string, { factor: number; unit: EntryUnit }> = {
  "m²": { factor: 1, unit: "m²" }, m2: { factor: 1, unit: "m²" }, "m^2": { factor: 1, unit: "m²" },
  "sq m": { factor: 1, unit: "m²" }, "square metres": { factor: 1, unit: "m²" }, "square meters": { factor: 1, unit: "m²" },
  "cm²": { factor: 0.0001, unit: "cm²" }, cm2: { factor: 0.0001, unit: "cm²" }, "sq cm": { factor: 0.0001, unit: "cm²" },
  "ft²": { factor: 0.09290304, unit: "ft²" }, ft2: { factor: 0.09290304, unit: "ft²" }, "ft^2": { factor: 0.09290304, unit: "ft²" },
  "sq ft": { factor: 0.09290304, unit: "ft²" }, sqft: { factor: 0.09290304, unit: "ft²" }, "square feet": { factor: 0.09290304, unit: "ft²" }, "square foot": { factor: 0.09290304, unit: "ft²" },
};

export function metricUnit(unit: string | undefined): MetricUnit | null {
  return unit === "m" || unit === "mm" || unit === "m²" || unit === "cm²" ? unit : null;
}

export function entryUnits(unit: MetricUnit): readonly EntryUnit[] {
  return unit.endsWith("²") ? [unit, "ft²"] : [unit, "ft"];
}

/** Strict whole-input parsing: never accepts the number at the start of an unknown unit or sentence. */
export function parseMeasurement(raw: string, target: MetricUnit, selected: EntryUnit = target): Measurement {
  const quote = raw.trim();
  if (!quote) return { kind: "empty" };
  const text = quote.toLowerCase().replace(/[′‘’]/g, "'").replace(/[″“”]/g, '"').replace(/\s+/g, " ");
  const area = target.endsWith("²");
  const scale = target === "mm" ? 1000 : target === "cm²" ? 10000 : 1;
  const compound = !area && text.match(FEET_INCHES);
  if (compound) {
    const inches = Number(compound[2]);
    if (inches >= 12) return { kind: "error", error: "Use inches below 12 after the feet." };
    const value = Number(((Number(compound[1]) * 0.3048 + inches * 0.0254) * scale).toPrecision(12));
    return Number.isFinite(value) ? { kind: "value", value, quote, enteredUnit: "ft" } : { kind: "error", error: "Enter a finite measurement." };
  }
  const simple = text.match(SIMPLE);
  if (!simple) return { kind: "error", error: "Enter a measurement, for example 4 ft." };
  const token = simple[2].replace(/\bsq\.\s*/g, "sq ") || selected;
  const found = (area ? AREA : LENGTH)[token];
  if (!found) return { kind: "error", error: area ? "Use m² or ft² for area." : "Use m, cm, mm, ft or ft and in." };
  const value = Number((Number(simple[1]) * found.factor * scale).toPrecision(12));
  return Number.isFinite(value)
    ? { kind: "value", value, quote, enteredUnit: found.unit }
    : { kind: "error", error: "Enter a finite measurement." };
}

/** The typed number takes the selected unit; explicit units always retain their exact wording. */
export function measurementText(text: string, selected: EntryUnit): string {
  return new RegExp(`^${AMOUNT}$`).test(text.trim()) ? `${text.trim()} ${selected}` : text;
}

export function metricPreview(value: number, unit: MetricUnit): string {
  return `= ${new Intl.NumberFormat("en-CA", { maximumFractionDigits: 2 }).format(value)} ${unit}`;
}
