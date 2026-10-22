import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "@fontsource-variable/inter/opsz.css";
import "@fontsource-variable/geist-mono";
import "../../docs/design/tokens.css";
import "./styles.css";
import "./calm/calm.css";
import { App } from "./App";
import { CaseProvider } from "./store";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <CaseProvider>
      <App />
    </CaseProvider>
  </StrictMode>,
);
