// ── Trace ──────────────────────────────────────────────
// Change:  CR-169-BRC10 — one `screen_viewed` per screen a person opens, in
//          all three apps, from ONE mount above every route (App.tsx's
//          `RootChrome`, beside `ScreenIdTag`, for the same reason it is there).
// ───────────────────────────────────────────────────────
import { useEffect } from "react";
import { useLocation } from "react-router-dom";

import { setPageContext, track } from "./client";
import { pageScreen } from "./screens";

export function AnalyticsPageViews(): null {
  const { pathname, search } = useLocation();
  const page = pageScreen(pathname, search);
  const key = `${page.app}|${page.tenant ?? ""}|${page.screen ?? pathname}`;

  useEffect(() => {
    setPageContext(page.app, page.tenant);
    // Keyed on the SCREEN, not the address: opening a second account on the
    // same screen is not a new screen, and the address is never sent raw.
    track("screen_viewed", { screen: page.screen ?? "unregistered", screen_a1: page.screenA1 });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  return null;
}
