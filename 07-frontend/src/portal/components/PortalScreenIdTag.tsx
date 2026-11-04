// ── Trace ──────────────────────────────────────────────
// Change:   PO 2026-09-03: *"We need unique screen ID - on every screen"* ·
//           CR-068 §9 (the portal's own `CWP` series)
// Rules:    the same contract as the staff `ScreenIdTag` — the id rides on
//           `<body data-screen-id>` for the harness, the visible chip is
//           behind the one `VITE_SCREEN_ID_TAG` switch, it can intercept no
//           click, it never prints, it is hidden from a screen reader
// Tests:    src/portal/routing/screenIds.test.ts
// ───────────────────────────────────────────────────────
import { useEffect } from "react";
import { useLocation, useParams } from "react-router-dom";

import { SCREEN_ID_TAG_ENABLED } from "@/routing/screenIds";

import { resolvePortalScreen } from "../routing/screenIds";

/** The part of the path after `/{tenant}/portal`. */
export function portalSubpath(pathname: string, tenant: string | undefined): string {
  const prefix = `/${tenant ?? ""}/portal`;
  const rest = pathname.startsWith(prefix) ? pathname.slice(prefix.length) : pathname;
  return rest === "" ? "/" : rest;
}

export function PortalScreenIdTag() {
  const location = useLocation();
  const params = useParams();
  const screen = resolvePortalScreen(portalSubpath(location.pathname, params.tenant));
  const id = screen?.id ?? null;

  useEffect(() => {
    const { body } = document;
    if (id === null) {
      delete body.dataset.screenId;
    } else {
      body.dataset.screenId = id;
    }
    return () => {
      delete body.dataset.screenId;
    };
  }, [id]);

  if (!SCREEN_ID_TAG_ENABLED || id === null) {
    return null;
  }
  return (
    <div
      className="pointer-events-none fixed bottom-3 right-3 z-70 select-none bg-text px-[9px] py-[3px] font-heading text-xs font-extrabold tabular-nums text-bg opacity-80 print:hidden"
      aria-hidden="true"
      data-testid="screen-id-tag"
      data-screen-id={id}
    >
      {id}
    </div>
  );
}
