/**
 * The AI connections the desktop host owns, and the seam a managed account adapter fills.
 *
 * An AI connection is never a Batatis identity: signing in here creates, links or changes no Batatis
 * user, role or case. Provider names live in desktop/ only; web/src stays provider-neutral and shows
 * the labels the host sends.
 */

export type ProviderId = "chatgpt" | "claude" | "openai" | "jev" | "batatis";
/** The managed account connections, each with its own downloadable runtime. */
export type AccountId = Extract<ProviderId, "chatgpt" | "claude">;
export type KeyProviderId = Extract<ProviderId, "openai" | "jev" | "batatis">;
export type GenerationChoice = "off" | "chatgpt" | "openai";

export function isGenerationChoice(value: unknown): value is GenerationChoice {
  return value === "off" || value === "chatgpt" || value === "openai";
}

/** Exact identifiers, chosen by the workflow's own configuration. An adapter never substitutes either. */
export type ModelId = string & { readonly __brand: "ModelId" };
export type ReasoningEffort = string & { readonly __brand: "ReasoningEffort" };

export function isModelId(value: unknown): value is ModelId {
  return typeof value === "string" && /^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$/.test(value);
}

export function isReasoningEffort(value: unknown): value is ReasoningEffort {
  return typeof value === "string" && /^[a-z]{1,16}$/.test(value);
}

export interface HostModel {
  id: ModelId;
  label: string;
  /** Efforts this model accepts; a request outside the list fails as model_unavailable. */
  efforts: readonly ReasoningEffort[];
  defaultEffort: ReasoningEffort | null;
  /** The runtime constrains the final message to the request's JSON schema. */
  structuredOutput: boolean;
}

/** How the last device login ended, shown until the next attempt. */
export type LoginOutcome =
  | { loginId: string; result: "cancelled" }
  | { loginId: string; result: "failed"; message: string }
  /** Device-code sign-in is off for this account or workspace; the message names the setting to enable. */
  | { loginId: string | null; result: "prerequisite"; message: string };

/** Sign-in status only. It says nothing about whether application work may use the connection. */
export type ConnectionState =
  | { state: "unavailable"; reason: "adapter-missing" | "runtime-missing" | "unsupported-platform" | "keyring-unavailable"; message: string }
  | { state: "signed-out"; last: LoginOutcome | null }
  /**
   * Sign-in in progress: the person opens verificationUrl and, for device-code sign-in, enters userCode (empty otherwise).
   * acceptsCode: the sign-in page may end by showing a code for the person to paste back into the app.
   */
  | { state: "pending"; loginId: string; verificationUrl: string; userCode: string; acceptsCode?: true }
  | { state: "signed-in"; plan: string | null }
  | { state: "error"; message: string };

/** Whether a workflow task may send work through this connection. Separate from ConnectionState. */
export type WorkflowReadiness =
  | { ready: true }
  | { ready: false; reason: "unavailable" | "signed-out" | "context_unverified"; message: string };

export interface CompleteJsonRequest {
  /** The engine's name for the task, for example "intake". */
  task: string;
  system: string;
  user: string;
  /** The full output schema, applied exactly; the adapter validates the final JSON against it. */
  schema: Record<string, unknown>;
  model: ModelId;
  effort: ReasoningEffort;
  /** The workflow's budget; null when the workflow sets none. Not a server-side ceiling. */
  maxOutputTokens: number | null;
}

export interface TokenUsage {
  inputTokens: number;
  outputTokens: number;
}

export type CompletionFailure =
  | "unavailable"
  | "context_unverified"
  | "auth"
  | "quota"
  | "model_unavailable"
  | "cancelled"
  | "incomplete"
  | "refused_or_invalid"
  | "runtime";

export type CompleteJsonResult =
  /** usage is null when the runtime did not report it; it is never recorded as zero. */
  | { ok: true; json: Record<string, unknown>; model: ModelId; effort: ReasoningEffort; usage: TokenUsage | null }
  | { ok: false; reason: CompletionFailure; message: string };

/**
 * A managed account connection. Every method resolves with a typed result instead of throwing for
 * an expected condition. Main installs it, routes settings to it and disposes of it at quit.
 */
export interface HostProvider {
  readonly id: AccountId;
  status(): Promise<ConnectionState>;
  workflowReadiness(): Promise<WorkflowReadiness>;
  /** Starts sign-in. Pending state carries the page to open and, for device-code sign-in, the code to enter. */
  startLogin(): Promise<ConnectionState>;
  cancelLogin(loginId: string): Promise<ConnectionState>;
  /** Hands a pasted sign-in code to the pending login that offered acceptsCode. */
  submitLoginCode?(loginId: string, code: string): Promise<ConnectionState>;
  logout(): Promise<ConnectionState>;
  models(): Promise<readonly HostModel[]>;
  completeJson(request: CompleteJsonRequest, signal: AbortSignal): Promise<CompleteJsonResult>;
  /** Login completed, cancelled or failed elsewhere; main re-reads status() and tells the window. */
  onChange(listener: () => void): () => void;
  /** Quit or replacement: cancel pending work and stop every process the provider started. */
  dispose(): Promise<void>;
}

/** What main hands a provider factory. Every path is app-owned; none comes from the renderer. */
export interface HostProviderContext {
  /** Persistent, canonical state directory for this provider (for example the runtime's home). */
  readonly stateDir: string;
  /** An empty private working directory outside any repository. */
  readonly workDir: string;
  /** Packaged resources, or the repository root in development. */
  readonly resourcesDir: string;
  readonly appVersion: string;
  /** Scrubbed diagnostics: never a token, key, code, prompt or answer. */
  readonly log: (message: string) => void;
}

export type HostProviderFactory = (context: HostProviderContext) => HostProvider;

/** The truthful stand-in until an adapter is installed. */
export function unavailableProvider(message = "This connection isn’t available in this version.", id: AccountId = "chatgpt"): HostProvider {
  const state: ConnectionState = { state: "unavailable", reason: "adapter-missing", message };
  return {
    id,
    status: async () => state,
    workflowReadiness: async () => ({ ready: false, reason: "unavailable", message }),
    startLogin: async () => state,
    cancelLogin: async () => state,
    logout: async () => state,
    models: async () => [],
    completeJson: async () => ({ ok: false, reason: "unavailable", message }),
    onChange: () => () => {},
    dispose: async () => {},
  };
}

/** Labels and the one-line description each settings row shows. Only desktop/ names providers. */
export const PROVIDER_LABELS: Record<ProviderId, { label: string; description: string }> = {
  chatgpt: {
    label: "ChatGPT",
    description: "Uses your ChatGPT subscription through the managed Codex runtime when selected. Separate from your Batatis identity. Sign-in and workflow readiness are checked separately; token usage may be unknown.",
  },
  openai: {
    label: "OpenAI API key",
    description: "Uses API billing only when explicitly selected. Kept in this computer’s OS-protected vault. A subscription error never switches to API billing.",
  },
  claude: {
    label: "Claude",
    description: "Uses your Claude subscription through the managed Claude Code runtime when selected. Separate from your Batatis identity. Sign-in and workflow readiness are checked separately.",
  },
  batatis: {
    label: "Batatis access code",
    description: "Uses the Batatis team's AI, unlocked with an access code. Requests go through the Batatis website, which holds the keys; the code stays in this computer's OS-protected vault.",
  },
  jev: { label: "Jev API key", description: "Optional, separately billed screening and reranking with the pinned Jev profile. Without it, code identification shows its keyword fallback. Off disables this too." },
};
