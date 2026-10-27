import { engineGeneration } from "../api/sync";
import { useCase } from "../store";
import { accountSession } from "./account";
import type { WorkspaceStep } from "./routes";
import { CompletenessNote } from "./ui";
import { Workspace } from "./workspace/Workspace";

/** The live application document, or a clear empty state before a case exists. */
export function Application({ download, step = "edit", focus = null }: { download: "" | "options" | "draft"; step?: WorkspaceStep; focus?: string | null }) {
  const { phase } = useCase();
  return phase === "case" ? <Workspace key={`${accountSession()}:${engineGeneration()}`} download={download} step={step} focus={focus} /> : <div className="aw-empty">
    <h1>Nothing here yet</h1>
    <a className="cf-btn is-primary" href="#/">Describe your project</a>
    <CompletenessNote />
  </div>;
}
