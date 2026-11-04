// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-CWP-9162 — PO 2026-10-02, verbatim: *"The Customer Portal does
//          not display the application/version number."* The staff frame has
//          shown `v<version>` since CR-004 §7 (2026-08-16); the two portal
//          frames never did, so a portal defect report could not name a build.
// Rules:   change process §7 (one source of truth, derived everywhere, visible
//          on screen) · B14 rule 43 (built as a component) · rule 21
//          (utilities; this file is on route-b-migrated.txt) · rule 33 (a
//          label is ≤ 3 words — *Version*)
// Tests:   src/portal/shell/GuestFrame.test.tsx · PortalShell.test.tsx
//          (*the build version on every … page*) · src/components/AppShell.test.tsx
// ───────────────────────────────────────────────────────
/**
 * THE BUILD THIS BROWSER IS RUNNING — one source, every frame.
 *
 * ⚠ **`package.json`'s `version` IS THE SOURCE, EXACTLY AS IT IS FOR THE STAFF
 * FRAME** (`AppShell.tsx`, whose header records why: it is the one version
 * field that already exists, that npm and vite require anyway, and that the
 * running app can read with no build-config change). This file re-exports it so
 * there is ONE import of it, and the staff frame and both portal frames read the
 * same constant.
 */
import { useTranslation } from "react-i18next";

import { version as PACKAGE_VERSION } from "../../package.json";

/** The running build, e.g. `2.455.1`. */
export const APP_VERSION: string = PACKAGE_VERSION;

/**
 * `Version 2.455.1`, quietly, for a frame's footer.
 *
 * ⚠ **THE WORD IS SPOKEN AND THE NUMBER IS NOT TRANSLATED.** A bare `v2.455.1`
 * is read aloud as *"v, two point four…"*; the catalogue's *Version* in front of
 * it makes it a fact a screen reader can say. The number reads identically in
 * all eleven locales and is never a catalogue value — the staff frame's own
 * reason.
 */
export function BuildVersion(props: { className?: string }) {
  const { t } = useTranslation();
  return (
    <span className={props.className} data-testid="app-version" data-version={APP_VERSION}>
      {t("common.buildVersion", { version: APP_VERSION })}
    </span>
  );
}
