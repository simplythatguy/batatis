import { TONES } from "./deck";
import "./toneLegend.css";

/** The reading cues used in the transcript. Studio only: never painted on the stage. */
export function ToneLegend() {
  return (
    <details className="st-tones">
      <summary aria-label="What the emojis mean">
        {TONES.map(([emoji, meaning]) => (
          <span key={emoji} title={meaning}>{emoji}</span>
        ))}
      </summary>
      <dl>
        {TONES.map(([emoji, meaning]) => (
          <div key={emoji}>
            <dt>{emoji}</dt>
            <dd>{meaning}</dd>
          </div>
        ))}
      </dl>
    </details>
  );
}
