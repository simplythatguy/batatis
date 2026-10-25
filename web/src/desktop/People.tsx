/** Local development only: who is signed in, and a one-click switch to another test person. */
import { useState } from "react";
import { getSession } from "../calm/session";
import { authorityName } from "../calm/applications";
import { Icon24 } from "../calm/icons";
import { useCase } from "../store";
import { desktop, useDesktop, type Person } from "./host";
import { saveBeforeSwitch } from "./switching";

export function personLabel(person: Person): string {
  return person.kind === "reviewer" ? `Reviewer · ${authorityName(person.authority)}` : "Applicant";
}

/** Saves this visit's work first; a failed save keeps the current person with the reason on screen. */
export function useSaveBeforeSwitch(): () => Promise<string | null> {
  const store = useCase();
  return () => saveBeforeSwitch({
    read: () => {
      const session = getSession();
      return {
        phase: store.phase, saveStatus: store.saveStatus, submitting: store.submitting, submissionDispatched: store.submissionDispatched,
        uploading: session.uploading.length, held: session.held.length, unstarted: Boolean(session.draft.trim() || session.draftFiles.length),
      };
    },
    saveDraft: store.saveDraft,
    saved: () => store.readSync().saved,
  });
}

export function useSwitchPerson() {
  const prepare = useSaveBeforeSwitch();
  const info = useDesktop();
  const [pending, setPending] = useState<string | null>(null);
  const [error, setError] = useState("");
  async function choose(profile: string) {
    if (pending || profile === info?.person?.profile) return;
    setPending(profile);
    setError("");
    const reason = await prepare();
    const outcome = reason ? { ok: false as const, message: reason } : await desktop.switchPerson(profile);
    // On success the host replaces this window; nothing here runs as the new person.
    if (!outcome.ok) {
      setError(outcome.message);
      setPending(null);
    }
  }
  return { pending, error, choose };
}

/** The account menu's quick switch. Items are menu radios so the menu's arrow keys reach them. */
export function PeopleMenu() {
  const info = useDesktop();
  const { pending, error, choose } = useSwitchPerson();
  if (!info || info.workspace !== "dev") return null;
  return (
    <div className="dk-people" role="group" aria-label="Switch person">
      <span className="dk-tag">Local development</span>
      {info.people.map((person) => {
        const current = person.profile === info.person?.profile;
        return (
          <button key={person.profile} type="button" role="menuitemradio" tabIndex={-1} aria-checked={current}
            disabled={pending !== null} onClick={() => void choose(person.profile)}>
            <Icon24 name={person.kind === "reviewer" ? "landmark" : "user"} size={16} />
            <span className="dk-person-name">{personLabel(person)}</span>
            {current && <span className="dk-check"><Icon24 name="check" size={14} stroke={2.2} /></span>}
            {pending === person.profile && <span className="cf-dot is-pending cf-pulse" aria-label="Switching" />}
          </button>
        );
      })}
      {error && <p className="ac-error is-row" role="alert">{error}</p>}
    </div>
  );
}
