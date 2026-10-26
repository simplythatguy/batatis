import { createHash } from "node:crypto";
import { unavailableProvider, type HostProvider } from "./providers";

/** Only the explicit packaged acceptance runner installs this offline fixture. It checks no account. */
export function workflowFixture() {
  const calls: { task: string; model: string; effort: string; contextSha256: string }[] = [];
  const provider: HostProvider = {
    ...unavailableProvider(),
    status: async () => ({ state: "signed-out", last: { loginId: null, result: "prerequisite", message: "Offline workflow fixture. No account checked." } }),
    workflowReadiness: async () => ({ ready: true }),
    completeJson: async (request, signal) => {
      if (signal.aborted) return { ok: false, reason: "cancelled", message: "Offline fixture cancelled." };
      calls.push({ task: request.task, model: request.model, effort: request.effort,
        contextSha256: createHash("sha256").update(JSON.stringify({ system: request.system, user: request.user, schema: request.schema })).digest("hex") });
      const payloads: Record<string, Record<string, unknown>> = {
        intake: { facts: [] },
        "document-review": { documents: [], flags: [], facts: [], conflicts: [], provisions: [], missing: [], questions: [] },
        "identify-picks": { picks: [] },
        assistant: { answer: "Offline workflow fixture. Ask the responsible author for authentic supporting evidence." },
      };
      const json = payloads[request.task];
      return json ? { ok: true, json, model: request.model, effort: request.effort, usage: null }
        : { ok: false, reason: "refused_or_invalid", message: "Unknown offline fixture task." };
    },
  };
  return { provider, calls, adapterConstructed: false };
}
