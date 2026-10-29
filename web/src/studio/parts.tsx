// Small pieces shared by the studio screens.
import { useState } from "react";
import { Icon } from "./icons";

export interface Camera {
  stream: MediaStream | null;
  /** The page-lifetime element playing `stream`; the stage paints it as the camera tile. */
  live: HTMLVideoElement;
  error: string | null;
  cams: MediaDeviceInfo[];
  mics: MediaDeviceInfo[];
  retry(): void;
}

export const roomLink = (code: string) => {
  const url = new URL(location.href);
  url.search = "";
  url.searchParams.set("room", code);
  const deck = new URLSearchParams(location.search).get("deck");
  if (deck) url.searchParams.set("deck", deck);
  return url.toString();
};

export function CopyLink({ code }: { code: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      type="button"
      className="st-copy"
      title="Copy the room link"
      aria-label={`Room ${code}, copy link`}
      onClick={() => {
        void navigator.clipboard?.writeText(roomLink(code)).then(() => {
          setCopied(true);
          window.setTimeout(() => setCopied(false), 1500);
        });
      }}
    >
      <span>{code}</span>
      <Icon name={copied ? "check" : "copy"} size={14} />
    </button>
  );
}
