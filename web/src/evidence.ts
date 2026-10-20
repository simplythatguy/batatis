import type { Case } from "./types";

/** A task label from the looked-up function, not an invented evidence document. */
export function evidenceTask(c: Case, item: { provision_id?: string; provision?: { provision_id: string } | null; function?: string | null; objective?: string | null }): string {
  const provision = item.provision?.provision_id ?? item.provision_id;
  const row = c.sectionC.find(r => r.provision === provision);
  const text = item.function ? row?.terms?.[item.function] : undefined;
  if (!text) return provision ? "Ask your designer to identify the benchmark" : "Choose a code reference first";
  const purpose = text.replace(/^To\s+/i, "").split(/[.;]/)[0];
  const scope = item.objective?.startsWith("OS") ? "People" : item.objective?.startsWith("OP") ? "Building" : "Performance";
  const task = item.function === "F03" ? "compare fire spread evidence"
    : item.function === "F04" ? "compare fire collapse evidence" : `review how to ${purpose}`;
  const label = `${scope}: ${task}`;
  return label.length > 100 ? `${label.slice(0, 97)}…` : label;
}
