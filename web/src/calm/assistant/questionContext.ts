import type { DeckItem } from "../deck";
import type { AssistContext } from "./assistant";

/** The actual visible question follows every entry point, including the header's Ask. */
export function questionContext(item: Pick<DeckItem, "key" | "title" | "why" | "provision">, n: number): AssistContext {
  return {
    screen: "question",
    focus: {
      kind: item.provision ? "provision" : "card",
      id: item.provision ?? item.key,
      ...(item.title.trim() ? { prompt: item.title.trim().slice(0, 600) } : {}),
      ...(item.why.trim() ? { why: item.why.trim().slice(0, 1200) } : {}),
    },
    label: `question ${n}${item.provision ? ` and ${item.provision}` : ""}`,
    suggestions: item.provision ? ["Explain the code", "What does this question mean?"] : ["What does this question mean?", "What should I have ready?"],
  };
}
