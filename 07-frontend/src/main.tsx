import React from "react";
import ReactDOM from "react-dom/client";

import { startAnalytics } from "@/analytics";
import App from "@/App";
import "@/i18n";
import "@/styles/global.css";
// CR-018 Phase 1 — the Tailwind utilities enter the app here, and this line is
// LAST on purpose. `src/styles/tailwind.css` imports `utilities.css` UNLAYERED
// (its header says why: a layered utility loses to any unlayered legacy rule,
// whatever the specificity, and 40 legacy stylesheets are still in the bundle),
// so a utility and a legacy `.class` rule are both 0,1,0 and SOURCE ORDER
// decides. ESM evaluates imports in the order written, so `@/App` above pulls
// in every component stylesheet before this line runs — verified in the built
// CSS, where the utilities start at byte 130,615 of 141,605 and every legacy
// sheet is behind them. Moving this import up silently un-migrates Phase 1.
// Preflight is deliberately NOT imported; see the header of tailwind.css for
// the 684 measured property changes that decision is based on.
import "@/styles/tailwind.css";

const root = document.getElementById("root");
if (root === null) {
  throw new Error("index.html is missing #root");
}

// CR-169-BRC10 — decided once, before the first screen. Off with no key or on a
// host this build was not made for; when on, PostHog loads in its own chunk and
// never delays a screen.
startAnalytics();

ReactDOM.createRoot(root).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
