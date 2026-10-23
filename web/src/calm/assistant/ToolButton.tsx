import { useId, type ButtonHTMLAttributes } from "react";

/** A named icon control with the same short label available to pointer and keyboard users. */
export function ToolButton({ title, children, ...props }: ButtonHTMLAttributes<HTMLButtonElement>) {
  const id = useId();
  return <span className="cf-av-tool">
    <button {...props} aria-describedby={id}>{children}</button>
    <span id={id} role="tooltip" className="cf-av-tooltip">{title || props["aria-label"]}</span>
  </span>;
}
