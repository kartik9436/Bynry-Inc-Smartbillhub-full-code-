// ── Trace ──────────────────────────────────────────────
// Change:  CR-169-BRC10 — `screen_viewed` names the SCREEN ID (`S22`, `PAY-02`,
//          `CWP-052`, `WRK-21`), never translated text and never a raw
//          address: the id is the same in all eleven languages (§1).
// Tests:   src/analytics/screens.test.ts
// ───────────────────────────────────────────────────────
//
// Three application roots share one origin, each with its OWN screen
// register, so this asks each register about its own addresses rather than
// keeping a fourth list: the staff app's `routing/screenIds.ts`, the portal's
// `portal/routing/screenIds.ts` and the field app's `MOBILE_SCREENS`.
import { matchPath } from "react-router-dom";

import { MOBILE_SCREENS } from "@/features/work/mobile/screenIds";
import { resolvePortalScreen } from "@/portal/routing/screenIds";
import { resolveScreen } from "@/routing/screenIds";
import { tenantFromPathname } from "@/routing/tenantPath";

import type { AnalyticsApp } from "./client";

export interface PageScreen {
  app: AnalyticsApp;
  /** The utility's path segment, or null on a public page. */
  tenant: string | null;
  /** The visible screen id, or null when the register has none for this address. */
  screen: string | null;
  /** The staff app's A1 id where it has one (`S22`). */
  screenA1: string | null;
}

export function pageScreen(pathname: string, search = ""): PageScreen {
  const tenant = tenantFromPathname(pathname) || null;
  if (tenant !== null) {
    const portalPrefix = `/${tenant}/portal`;
    if (pathname === portalPrefix || pathname.startsWith(`${portalPrefix}/`)) {
      const sub = pathname.slice(portalPrefix.length) || "/";
      return { app: "portal", tenant, screen: resolvePortalScreen(sub)?.id ?? null, screenA1: null };
    }
    const fieldPrefix = `/${tenant}/work/mobile`;
    if (pathname === fieldPrefix || pathname.startsWith(`${fieldPrefix}/`)) {
      const sub = pathname.slice(fieldPrefix.length).replace(/^\/+|\/+$/g, "");
      const found = MOBILE_SCREENS.find((one) =>
        one.path === "" ? sub === "" : matchPath(`/${one.path}`, `/${sub}`) !== null,
      );
      return { app: "field", tenant, screen: found?.badge ?? null, screenA1: null };
    }
  }
  const resolved = resolveScreen(pathname, search);
  // An empty id is no id: `r10` is "" where r10 allocates none.
  return { app: "staff", tenant, screen: resolved.r10 || null, screenA1: resolved.a1 || null };
}
