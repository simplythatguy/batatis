/** #/settings: who you are, your role (change uses the onboarding endpoint), how data is handled, sign out. */
import { useId, useState, type ReactNode } from "react";
import { DesktopSettings } from "../../desktop/DesktopSettings";
import { useDesktop } from "../../desktop/host";
import { AccountsError, type ApplicantKind, type AuthorityKey, type Role } from "../../api/accounts";
import { PRIVACY_NOTICE } from "../../privacy";
import { useAccount } from "../account";
import { authorityName } from "../applications";
import { PageHead, clockText, useCountdown } from "../auth/bits";
import { APPLICANT_CHOICES, APPLICANT_LABEL, AUTHORITY_CHOICES, codeNeeded } from "../auth/onboardingSteps";
import { saveOnboarding, signOut } from "../auth/useAuthGate";
import { AiAccessSection } from "./AiAccess";
import { ArchivedApplications } from "./ArchivedApplications";
import { Chips, Row } from "./rows";


function roleLine(role: Role | null, applicantType: string | null, authority: string | null): string {
  if (role === "reviewer") return `Reviewer${authority ? ` · ${authorityName(authority)}` : ""}`;
  if (role === "applicant") return `Applicant${applicantType ? ` · ${APPLICANT_LABEL[applicantType] ?? applicantType}` : ""}`;
  return "Not set";
}

function RoleEditor({ onCancel, onSaved }: { onCancel: () => void; onSaved: () => void }) {
  const { user } = useAccount();
  const id = useId();
  const [role, setRole] = useState<Role | undefined>(user?.role ?? undefined);
  const [type, setType] = useState<ApplicantKind | undefined>((user?.applicant_type as ApplicantKind) ?? undefined);
  const [authority, setAuthority] = useState<AuthorityKey | undefined>((user?.authority as AuthorityKey) ?? undefined);
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [wait, startWait] = useCountdown();
  if (!user) return null;
  const need = role ? codeNeeded({ role: user.role, authority: user.authority }, role, authority) : null;
  const complete = role === "applicant" ? Boolean(type) : role === "reviewer" ? Boolean(authority) : false;
  const canSave = complete && (!need || code.trim().length > 0) && !busy && wait === 0;

  async function save() {
    if (!canSave || !role) return;
    setBusy(true);
    setError("");
    try {
      await saveOnboarding(role === "applicant"
        ? { role, applicant_type: type, ...(need ? { access_code: code.trim() } : {}) }
        : { role, authority, access_code: code.trim() });
      onSaved();
    } catch (e) {
      if (e instanceof AccountsError && e.status === 429) startWait(e.retryAfter);
      else setError(e instanceof AccountsError && e.detail ? e.detail : "That didn’t save. Try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="ac-editor">
      <p className="ac-editor-label">How you use Batatis</p>
      <Chips label="Role" value={role} onPick={(r) => { setRole(r); setError(""); }} options={[{ value: "applicant", label: "Applying for a variance" }, { value: "reviewer", label: "Reviewing for an authority" }]} />
      {role === "applicant" && (
        <>
          <p className="ac-editor-label">Which describes you best</p>
          <Chips label="Applicant type" value={type} onPick={setType} options={APPLICANT_CHOICES} />
        </>
      )}
      {role === "reviewer" && (
        <>
          <p className="ac-editor-label">Authority</p>
          <Chips label="Authority" value={authority} onPick={(a) => { setAuthority(a); setCode(""); }} options={AUTHORITY_CHOICES} />
        </>
      )}
      {need && (
        <div className="ac-field is-editor">
          <label htmlFor={`${id}-code`}>{authorityName(need.authority)} access code</label>
          <input id={`${id}-code`} className="ac-in" autoComplete="off" spellCheck={false} value={code} onChange={(e) => { setCode(e.target.value); setError(""); }} aria-describedby={`${id}-why`} />
          <p id={`${id}-why`} className="ac-help">
            {role === "reviewer" ? "Reviewer access needs your authority’s code." : "Leaving the reviewer role needs your current authority’s code."}
          </p>
        </div>
      )}
      {error && <p className="ac-error" role="alert">{error}</p>}
      {wait > 0 && <p className="ac-error" role="status">Too many attempts. Try again in {clockText(wait)}.</p>}
      <div className="ac-editor-foot">
        <button type="button" className="cf-btn is-sm" onClick={onCancel}>Cancel</button>
        <button type="button" className="cf-btn is-sm is-primary" disabled={!canSave} onClick={() => void save()}>{busy ? "Saving…" : "Save"}</button>
      </div>
      {!complete && role && <p className="ac-help">{role === "applicant" ? "Choose what describes you best." : "Choose an authority."}</p>}
    </div>
  );
}

export function Settings({ phoneTools }: { phoneTools?: ReactNode }) {
  const { user } = useAccount();
  // Local development's test people keep their role; the person switch replaces sign-in and onboarding.
  const testPerson = useDesktop()?.workspace === "dev";
  const [editing, setEditing] = useState(false);
  const [saved, setSaved] = useState(false);
  const [leaving, setLeaving] = useState(false);

  return (
    <div className="ac-page">
      <PageHead title="Settings" phoneTools={phoneTools} />
      <div className="ac-page-body is-narrow">
        <h1 className="ac-page-title">Settings</h1>
        {user ? (
          <>
            <section className="ac-section" aria-labelledby="ac-s-profile">
              <h2 id="ac-s-profile" className="ac-section-title">Account</h2>
              <Row label="Name">{user.name || "—"}</Row>
              <Row label="Email">{user.email}<span className="ac-faint-tag">Can’t be changed here</span></Row>
              <Row
                label="Role"
                action={!editing && !testPerson && <button type="button" className="cf-btn is-xs" onClick={() => { setEditing(true); setSaved(false); }}>Change</button>}
              >
                {roleLine(user.role, user.applicant_type, user.authority)}
                {saved && <span className="ac-saved" role="status">Saved</span>}
              </Row>
              {editing && <RoleEditor onCancel={() => setEditing(false)} onSaved={() => { setEditing(false); setSaved(true); }} />}
            </section>
            <AiAccessSection />
            <ArchivedApplications />
          </>
        ) : (
          <section className="ac-section">
            <h2 className="ac-section-title">Account</h2>
            <p className="ac-muted">Accounts aren’t available on this server. Your application is kept for this visit only.</p>
          </section>
        )}

        <DesktopSettings />

        <section className="ac-section" aria-labelledby="ac-s-data">
          <h2 id="ac-s-data" className="ac-section-title">How your data is handled</h2>
          <details className="cf-help">
            <summary>Details</summary>
            <p className="ac-prose">{PRIVACY_NOTICE}</p>
          </details>
        </section>

        <section className="ac-section" aria-labelledby="ac-s-accuracy">
          <h2 id="ac-s-accuracy" className="ac-section-title">Accuracy</h2>
        </section>

        {user && !testPerson && (
          <section className="ac-section is-last">
            <button type="button" className="cf-btn is-sm" disabled={leaving} onClick={() => { setLeaving(true); void signOut(); }}>
              {leaving ? "Signing out…" : "Sign out"}
            </button>
          </section>
        )}
      </div>
    </div>
  );
}
