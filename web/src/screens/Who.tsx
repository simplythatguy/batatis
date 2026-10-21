import { useState } from "react";
import { Icon } from "../components";
import { useCase } from "../store";
import type { ApplicantType } from "../types";

const CHOICES: { id: ApplicantType; label: string }[] = [
  { id: "manufacturer", label: "Manufacturer" },
  { id: "contractor", label: "General contractor" },
  { id: "homebuilder", label: "Homebuilder" },
];

export function Who() {
  const { beginEmpty, resetNote } = useCase();
  const [role, setRole] = useState<ApplicantType | null>(null);
  return <div className="pane onboarding">
    <div className="role-step">
      <h1>Your role</h1>
      <p className="step-intro">Let’s start your application.</p>
      <div className="role-options" role="group" aria-label="Your role">
        {CHOICES.map(choice => <button key={choice.id} type="button" className="role-option" aria-pressed={role === choice.id} onClick={() => setRole(choice.id)}>
          {choice.label}<span className="role-mark" aria-hidden="true">{role === choice.id && <Icon name="check" />}</span>
        </button>)}
      </div>
      <button className="btn btn-primary role-continue" type="button" disabled={!role} onClick={() => role && beginEmpty(role)}>Continue <Icon name="chevron" /></button>
      {resetNote && <p className="meta" role="status">{resetNote}</p>}
    </div>
  </div>;
}
