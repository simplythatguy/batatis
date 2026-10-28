/**
 * What answers each kind of AI work: one pick for the workflow (intake, document review, code picks)
 * and one for the assistant chat, after T3 Code's per-thread model picker. A pick is a source plus a
 * model and effort from that source's menu; Off sends nothing. Only desktop/ names sources and models.
 */

export type Source = "chatgpt" | "claude" | "openai" | "batatis";
export type Slot = "workflow" | "chat";

export type Pick =
  | { source: "off" }
  | { source: Source; model: string; effort: string };

export interface AiSelection { workflow: Pick; chat: Pick; screening: boolean }

export interface MenuModel { id: string; label: string; efforts: readonly string[] }
/** `included`: the Batatis team pays, through an access code. */
export interface SourceMenu { label: string; billing: "subscription" | "api" | "included"; models: readonly MenuModel[]; default: { model: string; effort: string } }

const CLAUDE_EFFORTS = ["low", "medium", "high"] as const;

/**
 * ChatGPT and the OpenAI key stay on the reviewed Luna profile: the managed Codex runtime's catalog and
 * context checks cover that model and effort only. Claude defaults to Haiku 5.5 at medium effort, the
 * model's own default effort on the Anthropic API.
 */
export const MENU: Readonly<Record<Source, SourceMenu>> = {
  chatgpt: { label: "ChatGPT", billing: "subscription", models: [{ id: "gpt-6-luna", label: "Luna", efforts: ["medium"] }], default: { model: "gpt-6-luna", effort: "medium" } },
  claude: {
    label: "Claude", billing: "subscription",
    models: [
      { id: "claude-haiku-5-5", label: "Haiku 5.5", efforts: CLAUDE_EFFORTS },
      { id: "claude-sonnet-5-5", label: "Sonnet 5.5", efforts: CLAUDE_EFFORTS },
      { id: "claude-opus-5-5", label: "Opus 5.5", efforts: CLAUDE_EFFORTS },
    ],
    default: { model: "claude-haiku-5-5", effort: "medium" },
  },
  openai: { label: "OpenAI API key", billing: "api", models: [{ id: "gpt-6-luna", label: "Luna", efforts: ["medium"] }], default: { model: "gpt-6-luna", effort: "medium" } },
  batatis: { label: "Batatis AI", billing: "included", models: [{ id: "gpt-6-luna", label: "Luna", efforts: ["medium"] }], default: { model: "gpt-6-luna", effort: "medium" } },
};

export const OFF: Pick = { source: "off" };
export const DEFAULT_SELECTION: AiSelection = { workflow: OFF, chat: OFF, screening: false };

export const isSource = (value: unknown): value is Source => value === "chatgpt" || value === "claude" || value === "openai" || value === "batatis";
export const isSlot = (value: unknown): value is Slot => value === "workflow" || value === "chat";

export function defaultPick(source: Source): Pick {
  return { source, ...MENU[source].default };
}

/** A pick from untrusted input (settings file, renderer), or null when it names nothing on the menu. */
export function parsePick(value: unknown): Pick | null {
  if (typeof value !== "object" || value === null) return null;
  const { source, model, effort } = value as Record<string, unknown>;
  if (source === "off") return OFF;
  if (!isSource(source)) return null;
  const entry = MENU[source].models.find((item) => item.id === model);
  return entry && typeof effort === "string" && entry.efforts.includes(effort) ? { source, model: entry.id, effort } : null;
}

/** Settings written before the two pickers held one `generation` for everything. */
export function parseSelection(value: unknown): AiSelection | null {
  if (typeof value !== "object" || value === null) return null;
  const raw = value as Record<string, unknown>;
  const screening = raw.screening === true;
  if ("generation" in raw) {
    const pick = raw.generation === "off" ? OFF : isSource(raw.generation) ? defaultPick(raw.generation) : null;
    return pick && { workflow: pick, chat: pick, screening };
  }
  const workflow = parsePick(raw.workflow), chat = parsePick(raw.chat);
  return workflow && chat ? { workflow, chat, screening } : null;
}

export const slotForTask = (task: string): Slot => (task === "assistant" ? "chat" : "workflow");
