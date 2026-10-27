import { useState } from "react";
import "./journey.css";
import { PICTURES_FIELD, picturesWaiting } from "../intakeView";
import { useCase } from "../store";
import { useCurrentApplication } from "./begin";
import { ConfirmDialog, Dot } from "./ui";

/**
 * Pictures (photos, scanned pages) leave the machine only after the applicant allows it: names and
 * addresses can be removed from text, not from pixels. One quiet line while any picture waits.
 */
export function PictureConsent() {
  const { c, dispatch, readDescription } = useCase();
  const { locked } = useCurrentApplication();
  const [asking, setAsking] = useState(false);
  if (locked || !picturesWaiting(c)) return null;
  function allow() {
    setAsking(false);
    dispatch({ type: "setRuleInput", field: PICTURES_FIELD, value: true, rule: "privacy", quote: "Allowed by the applicant" });
    void readDescription();
  }
  return (
    <p className="cf-picture-consent" role="status">
      <Dot tone="pending" />Pictures not read yet
      <button type="button" className="cf-link-btn" onClick={() => setAsking(true)}>Read pictures</button>
      <ConfirmDialog
        open={asking}
        title="Read your pictures?"
        body="Photos and scanned pages can show names and addresses. Batatis can’t remove them from images before the AI reads them."
        confirm="Read pictures"
        cancel="Not now"
        onConfirm={allow}
        onClose={() => setAsking(false)}
      />
    </p>
  );
}
