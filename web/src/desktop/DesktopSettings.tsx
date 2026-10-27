/** Settings sections that exist only in the desktop app: workspace and person, AI connections, code database, updates. */
import { useEffect, useState, type ReactNode } from "react";
import { Chips, Row } from "../calm/settings/rows";
import { desktop, useDesktop, useUpdate, type AiConfiguration, type DesktopInfo, type ProviderRow, type UpdateView, type WorkspaceKind } from "./host";
import { personLabel, useSaveBeforeSwitch, useSwitchPerson } from "./People";
import { ModelPicker } from "./ModelPicker";

const WORKSPACES: { value: WorkspaceKind; label: string }[] = [
  { value: "local", label: "This computer" },
  { value: "dev", label: "Local development" },
];

function WorkspaceSection({ info }: { info: DesktopInfo }) {
  const prepare = useSaveBeforeSwitch();
  const people = useSwitchPerson();
  const [error, setError] = useState("");
  const [moving, setMoving] = useState<WorkspaceKind | null>(null);
  async function move(kind: WorkspaceKind) {
    if (kind === info.workspace || moving) return;
    setMoving(kind);
    setError("");
    const reason = await prepare();
    const outcome = reason ? { ok: false as const, message: reason } : await desktop.switchWorkspace(kind);
    if (!outcome.ok) {
      setError(outcome.message);
      setMoving(null);
    }
  }
  return (
    <section className="ac-section" aria-labelledby="dk-s-workspace">
      <h2 id="dk-s-workspace" className="ac-section-title">Workspace</h2>
      <Row label="Data">
        <Chips label="Workspace" value={moving ?? info.workspace} onPick={(kind) => void move(kind)} options={WORKSPACES} />
      </Row>
      {info.workspace === "dev" && (
        <Row label="Person">
          <Chips label="Person" value={people.pending ?? info.person?.profile} onPick={(profile) => void people.choose(profile)}
            options={info.people.map((person) => ({ value: person.profile, label: personLabel(person) }))} />
        </Row>
      )}
      {(error || people.error) && <p className="ac-error is-row" role="alert">{error || people.error}</p>}
      <details className="cf-help">
        <summary>About workspaces</summary>
        <p className="ac-prose">Each workspace keeps its own applications on this computer. Local development has test people who share one database, so an application submitted as the applicant reaches the reviewer for its authority.</p>
      </details>
    </section>
  );
}

function ConnectionActions({ row, act }: { row: ProviderRow; act: (action: Parameters<typeof desktop.providers>[0]) => void }) {
  if (row.kind === "key") {
    if (row.status === "missing") return <button type="button" className="cf-btn is-xs" onClick={() => act("enterKey")}>Add key</button>;
    if (row.status === "saved") return (
      <>
        <button type="button" className="cf-btn is-xs" onClick={() => act("enterKey")}>Replace</button>
        <button type="button" className="cf-btn is-xs is-ghost" onClick={() => act("removeKey")}>Remove</button>
      </>
    );
    return <button type="button" className="cf-btn is-xs" onClick={() => act("enterKey")}>Try again</button>;
  }
  switch (row.runtime?.state) {
    case "missing": return <button type="button" className="cf-btn is-xs is-primary" onClick={() => act("install")}>Install</button>;
    case "outdated": return <button type="button" className="cf-btn is-xs is-primary" onClick={() => act("install")}>Update</button>;
    case "failed": return <button type="button" className="cf-btn is-xs" onClick={() => act("install")}>Try again</button>;
    case "installing": return null;
  }
  switch (row.status.state) {
    case "signed-out": return <button type="button" className="cf-btn is-xs" onClick={() => act("connect")}>Sign in</button>;
    case "error": return <button type="button" className="cf-btn is-xs" onClick={() => act("connect")}>Try again</button>;
    case "pending": return (
      <>
        {row.status.address && <button type="button" className="cf-btn is-xs is-primary" onClick={() => act("openLogin")}>Open page</button>}
        <button type="button" className="cf-btn is-xs is-ghost" onClick={() => act("cancelLogin")}>Cancel</button>
      </>
    );
    case "signed-in": return <button type="button" className="cf-btn is-xs is-ghost" onClick={() => act("disconnect")}>Sign out</button>;
    case "unavailable": return null;
  }
}

/** For a sign-in page that ends by showing a code: the person pastes it here and the host passes it on. */
function LoginCode({ id }: { id: string }) {
  const [code, setCode] = useState("");
  const [sent, setSent] = useState(false);
  if (sent) return <span className="ac-faint-tag" role="status">Signing in…</span>;
  return (
    <form className="dk-login-code" onSubmit={(event) => {
      event.preventDefault();
      if (!code.trim()) return;
      setSent(true);
      void desktop.submitLoginCode(id, code.trim());
    }}>
      <input className="ac-in" aria-label="Sign-in code" placeholder="Paste code"
        autoComplete="off" spellCheck={false} value={code} onChange={(event) => setCode(event.target.value)} />
      <button type="submit" className="cf-btn is-xs" disabled={!code.trim()}>Continue</button>
    </form>
  );
}

function connectionValue(row: ProviderRow): ReactNode {
  if (row.kind === "key") {
    if (row.status === "saved") return <span className="ac-saved">Saved</span>;
    if (row.status === "missing") return <span className="ac-faint-tag">Not added</span>;
    return <span className="ac-faint-tag">Secure storage unavailable</span>;
  }
  const runtime = row.runtime;
  const mb = (bytes: number) => Math.round(bytes / 1_000_000);
  switch (runtime?.state) {
    case "missing": return <span className="ac-faint-tag">Not installed</span>;
    case "outdated": return <span className="ac-faint-tag">Update needed</span>;
    case "installing": return <span className="ac-faint-tag" role="status">Downloading {mb(runtime.received)} of {mb(runtime.total)} MB</span>;
    case "failed": return <span className="ac-faint-tag" role="alert">{runtime.message}</span>;
  }
  const status = row.status;
  const version = runtime?.state === "installed" && runtime.version ? <span className="dk-runtime-version"> · {runtime.version}</span> : null;
  switch (status.state) {
    case "signed-in": return <span>
      <span className="ac-saved">{status.plan ? `Signed in · ${status.plan}` : "Signed in"}</span>{version}
      {row.workflow && <span className="ac-help" role="status">{row.workflow}</span>}
    </span>;
    case "signed-out": return <span><span className="ac-faint-tag">{status.last ?? "Signed out"}</span>{version}</span>;
    case "pending": return status.userCode
      ? <span className="dk-code-line">Enter <code className="dk-code">{status.userCode}</code> at {status.address}</span>
      : status.acceptsCode
        ? <LoginCode id={row.id} />
        : <span className="ac-faint-tag" role="status">Finish signing in in your browser</span>;
    case "error": return <span className="ac-faint-tag">{status.message}</span>;
    case "unavailable": return <span className="ac-faint-tag">{status.message}</span>;
  }
}

function ConnectionsSection() {
  const prepare = useSaveBeforeSwitch();
  const [rows, setRows] = useState<ProviderRow[] | null>(null);
  const [configuration, setConfiguration] = useState<AiConfiguration | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    let live = true;
    const load = () => {
      void desktop.providers("list").then((next) => { if (live) setRows(next); });
      void desktop.configuration().then((next) => { if (live) setConfiguration(next); });
    };
    load();
    const stop = desktop.onChange(load);
    return () => { live = false; stop(); };
  }, []);
  const change = async (work: () => Promise<void>) => {
    if (busy) return;
    setBusy(true); setError("");
    try {
      const reason = await prepare();
      if (reason) setError(reason);
      else await work();
    } finally {
      setBusy(false);
    }
  };
  const act = (id: string) => (action: Parameters<typeof desktop.providers>[0]) => {
    const work = async () => {
      const next = await desktop.providers(action, id);
      if (action !== "openLogin") setRows(next);
      setConfiguration(await desktop.configuration());
    };
    // Key entry opens the dialog whose Save restarts the engine and replaces this window.
    if (action === "enterKey" || action === "removeKey" || action === "disconnect") void change(work);
    else void work();
  };
  const select = (work: () => ReturnType<typeof desktop.selectScreening>) => change(async () => {
    const outcome = await work();
    if (!outcome.ok) setError(outcome.message);
    setConfiguration(await desktop.configuration());
  });
  return (
    <section className="ac-section" aria-labelledby="dk-s-ai" aria-busy={busy}>
      <h2 id="dk-s-ai" className="ac-section-title">AI connections</h2>
      {configuration && <>
        <Row label="Workflow"><ModelPicker slot="workflow" label="Workflow model" onError={setError} /></Row>
        <Row label="Chat"><ModelPicker slot="chat" label="Chat model" onError={setError} /></Row>
        <Row label={configuration.screeningLabel}>
          <fieldset className="dk-choice" disabled={busy}>
            <Chips label="Optional screening" options={[{ value: "off", label: "Off" }, { value: "on", label: "On" }]}
              value={configuration.screening ? "on" : "off"} onPick={(value) => void select(() => desktop.selectScreening(value === "on"))} />
          </fieldset>
        </Row>
      </>}
      {busy && <p className="ac-faint-tag is-row" role="status">Updating…</p>}
      {(error || configuration?.note) && <p className="ac-error is-row" role="alert">{error || configuration?.note}</p>}
      {rows === null ? <p className="ac-faint-tag" role="status">Loading…</p> : rows.map((row) => (
        <Row key={row.id} label={row.label} action={<fieldset className="dk-choice" disabled={busy}><span className="dk-actions"><ConnectionActions row={row} act={act(row.id)} /></span></fieldset>}>
          {connectionValue(row)}
        </Row>
      ))}
      {rows && rows.length > 0 && (
        <details className="cf-help">
          <summary>About these connections</summary>
          {configuration && <p className="ac-prose">{configuration.help}</p>}
          {rows.map((row) => <p key={row.id} className="ac-prose"><strong>{row.label}.</strong> {row.description}</p>)}
        </details>
      )}
    </section>
  );
}

function CodeDbSection({ info }: { info: DesktopInfo }) {
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState("");
  async function choose() {
    setBusy(true);
    setNote("");
    const outcome = await desktop.chooseCodeDb();
    if (!outcome.ok && outcome.message) setNote(outcome.message);
    setBusy(false);
  }
  return (
    <section className="ac-section" aria-labelledby="dk-s-codedb">
      <h2 id="dk-s-codedb" className="ac-section-title">Code database</h2>
      <Row label="NBC(AE) 2023" action={
        <button type="button" className="cf-btn is-xs" disabled={busy} onClick={() => void choose()}>{busy ? "Checking…" : info.codeDb.available ? "Replace…" : "Choose file…"}</button>
      }>
        {info.codeDb.available ? <span className="ac-saved">Ready</span> : <span className="ac-faint-tag">Not set up</span>}
      </Row>
      {note && <p className="ac-error is-row" role="alert">{note}</p>}
      {!info.codeDb.available && <p className="ac-help">Code lookups, Section C and submitting need it. Choose a code database built by Batatis on this computer.</p>}
    </section>
  );
}

function updateStatus(view: UpdateView | null): ReactNode {
  switch (view?.status) {
    case undefined: return null;
    case "unavailable": return <span className="ac-faint-tag">{view.message}</span>;
    case "idle": return view.checked ? <span className="ac-saved">Up to date</span> : null;
    case "checking": return <span className="ac-faint-tag">Checking…</span>;
    case "available": return <span className="ac-faint-tag">{view.release.version} available</span>;
    case "downloading": return <span className="ac-faint-tag">Downloading {view.release.version}</span>;
    case "ready": return <span className="ac-saved">{view.release.version} ready</span>;
    case "failed": return <span className="ac-faint-tag">Couldn’t update</span>;
  }
}

function UpdatesSection({ info }: { info: DesktopInfo }) {
  const view = useUpdate();
  const idle = view?.status === "idle" || view?.status === "failed" || view?.status === "available";
  const changeable = idle || view?.status === "ready";
  return (
    <section className="ac-section" aria-labelledby="dk-s-updates">
      <h2 id="dk-s-updates" className="ac-section-title">Updates</h2>
      <Row label={`Batatis ${info.version}`} action={view && view.status !== "unavailable" && (
        <button type="button" className="cf-btn is-xs" disabled={!idle} onClick={() => void desktop.updates.check()}>Check for updates</button>
      )}>
        {updateStatus(view)}
      </Row>
      {view && view.status !== "unavailable" && (
        <Row label="Updates from">
          <Chips label="Update channel" value={view.beta ? "beta" : "stable"} onPick={(v) => { if (changeable) void desktop.updates.setBeta(v === "beta"); }}
            options={[{ value: "stable", label: "Stable" }, { value: "beta", label: "Beta" }]} />
        </Row>
      )}
      {view?.status === "failed" && <p className="ac-error is-row" role="alert">{view.message}</p>}
    </section>
  );
}

export function DesktopSettings() {
  const info = useDesktop();
  if (!info) return null;
  return (
    <>
      <WorkspaceSection info={info} />
      <ConnectionsSection />
      <CodeDbSection info={info} />
      <UpdatesSection info={info} />
    </>
  );
}
