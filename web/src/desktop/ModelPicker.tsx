/**
 * Chooses what answers one kind of AI work, after T3 Code's composer model picker: a button naming the
 * current model, a menu of models grouped by connection, and an effort row for the chosen model.
 * Settings shows one for the workflow and one for chat; the assistant's composer shows the chat one.
 */
import { useEffect, useId, useRef, useState } from "react";
import { Icon24 } from "../calm/icons";
import { desktop, isOn, useAiConfiguration, type AiConfiguration, type Pick, type Slot } from "./host";

const capital = (text: string) => text.charAt(0).toUpperCase() + text.slice(1);

export function pickLabel(configuration: AiConfiguration, pick: Pick): string {
  if (!isOn(pick)) return "Off";
  const menu = configuration.sources.find((item) => item.value === pick.source);
  const model = menu?.models.find((item) => item.id === pick.model);
  return model && menu ? `${model.label} · ${capital(pick.effort)}` : "Off";
}

const same = (a: Pick, b: Pick) => (isOn(a) && isOn(b) ? a.source === b.source && a.model === b.model && a.effort === b.effort : a.source === b.source);

export function ModelPicker({ slot, label, compact = false, onError }: { slot: Slot; label: string; compact?: boolean; onError?: (message: string) => void }) {
  const configuration = useAiConfiguration();
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  const button = useRef<HTMLButtonElement>(null);
  const id = useId();

  useEffect(() => {
    if (!open) return;
    const outside = (event: PointerEvent) => { if (!root.current?.contains(event.target as Node)) setOpen(false); };
    const key = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      setOpen(false);
      button.current?.focus();
    };
    document.addEventListener("pointerdown", outside);
    document.addEventListener("keydown", key);
    root.current?.querySelector<HTMLElement>("[aria-checked=true], [role=menuitemradio]")?.focus();
    return () => { document.removeEventListener("pointerdown", outside); document.removeEventListener("keydown", key); };
  }, [open]);

  if (!configuration) return null;
  const current = configuration[slot];
  const currentModel = !isOn(current) ? null
    : configuration.sources.find((item) => item.value === current.source)?.models.find((item) => item.id === current.model) ?? null;

  async function choose(pick: Pick, close = true) {
    if (busy || same(pick, current)) { if (close) setOpen(false); return; }
    setBusy(true);
    const outcome = await desktop.selectModel(slot, pick);
    setBusy(false);
    if (!outcome.ok && outcome.message) onError?.(outcome.message);
    if (close) { setOpen(false); button.current?.focus(); }
  }

  return (
    <div ref={root} className={`dk-picker${compact ? " is-compact" : ""}`}>
      <button ref={button} type="button" className="dk-picker-btn" aria-haspopup="menu" aria-expanded={open} aria-controls={open ? id : undefined}
        aria-label={`${label}: ${pickLabel(configuration, current)}`} disabled={busy} onClick={() => setOpen((value) => !value)}>
        <span>{pickLabel(configuration, current)}</span>
        <Icon24 name="down" size={14} stroke={2} />
      </button>
      {open && (
        <div id={id} className="dk-picker-menu" role="menu" aria-label={label}>
          <button type="button" role="menuitemradio" aria-checked={current.source === "off"} className="dk-picker-item" onClick={() => void choose({ source: "off" })}>
            Off{current.source === "off" && <Icon24 name="check" size={15} stroke={2} />}
          </button>
          {configuration.sources.map((source) => (
            <div key={source.value} role="group" aria-label={source.label}>
              <p className="dk-picker-group" aria-hidden="true">{source.label}</p>
              {source.models.map((model) => {
                const checked = isOn(current) && current.source === source.value && current.model === model.id;
                const effort = checked && isOn(current) ? current.effort
                  : model.id === source.default.model ? source.default.effort : model.efforts[0];
                return (
                  <button key={model.id} type="button" role="menuitemradio" aria-checked={checked} className="dk-picker-item"
                    aria-label={`${source.label} ${model.label}`} onClick={() => void choose({ source: source.value, model: model.id, effort })}>
                    {model.label}{checked && <Icon24 name="check" size={15} stroke={2} />}
                  </button>
                );
              })}
            </div>
          ))}
          {isOn(current) && currentModel && currentModel.efforts.length > 1 && (
            <div className="dk-picker-effort" role="group" aria-label="Effort">
              {currentModel.efforts.map((effort) => (
                <button key={effort} type="button" role="menuitemradio" aria-checked={current.effort === effort} className="cf-chip"
                  onClick={() => void choose({ ...current, effort }, false)}>{capital(effort)}</button>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
