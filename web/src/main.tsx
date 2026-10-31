import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { Analytics } from "@vercel/analytics/react";
import { SpeedInsights } from "@vercel/speed-insights/react";
import "@fontsource-variable/inter/opsz.css";
import "@fontsource-variable/geist-mono";
import "../../docs/design/tokens.css";
import "./shared.css";
import "./calm/calm.css";
import "./calm/mercury.css";
import { App } from "./App";
import { CaseProvider } from "./store";

// /studio is the team's pitch recorder (src/studio), loaded only on that path.
const STUDIO_RETURN = "batatis.studio.return";
if (location.pathname.startsWith("/studio")) {
  void import("./studio/entry");
} else {
  // Signing in from the studio comes back to it once the app leaves the sign-in pages.
  const back = sessionStorage.getItem(STUDIO_RETURN);
  if (back) {
    window.addEventListener("hashchange", () => {
      if (/^#\/(signin|signup|onboarding)\b/.test(location.hash)) return;
      sessionStorage.removeItem(STUDIO_RETURN);
      location.replace(back);
    });
  }
  createRoot(document.getElementById("root")!).render(
    <StrictMode>
      <CaseProvider>
        <App />
        <Analytics />
        <SpeedInsights />
      </CaseProvider>
    </StrictMode>,
  );
}
