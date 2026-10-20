import { useCallback, useEffect, useRef, useState } from "react";

const COMMIT_DELAY = 300;

/**
 * Text a field holds while the applicant types. A keystroke re-renders only this field; the case
 * (and every gap count) updates ~300 ms after typing stops, on blur, or when the field unmounts.
 * A change to `value` from elsewhere (Reset, Confirm) replaces the draft unless an edit is pending.
 */
export function useDraft(value: string, commit: (v: string) => void) {
  const [draft, setDraft] = useState(value);
  const timer = useRef<number | undefined>(undefined);
  const latest = useRef({ draft: value, commit });
  latest.current.commit = commit;

  useEffect(() => {
    if (timer.current === undefined) {
      setDraft(value);
      latest.current.draft = value;
    }
  }, [value]);

  const flush = useCallback(() => {
    if (timer.current === undefined) return;
    window.clearTimeout(timer.current);
    timer.current = undefined;
    latest.current.commit(latest.current.draft);
  }, []);

  useEffect(() => flush, [flush]);

  const onChange = useCallback(
    (v: string) => {
      setDraft(v);
      latest.current.draft = v;
      window.clearTimeout(timer.current);
      timer.current = window.setTimeout(flush, COMMIT_DELAY);
    },
    [flush],
  );

  return { value: draft, onChange, onBlur: flush };
}
