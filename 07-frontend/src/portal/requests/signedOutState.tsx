// ── Trace ──────────────────────────────────────────────
// Story:    US-CWP-062 (CWP-052) · US-CWP-037 (CWP-032) — the two signed-in
//           screens `CR-085` step 2 lane 3 owns.
// Rules:    R-10 (PO 2026-09-11, verbatim: *"when a screen tells a customer
//           something bad, the thing they can do about it must be on that same
//           screen, next to the message. Not a page away. Not in a menu. Right
//           there."*) · R-22 (PO 2026-09-11, verbatim: *"differntiate it using
//           text message"* — three states, three SENTENCES, one picture) ·
//           blueprint spec `CPB-17` (a signed-out visitor at a signed-in
//           address is offered a sign-in) · B14 rules 21, 32, 36 ·
//           BR-CWP-007 (the tenant is read off the address, never typed)
// Defects:  DEF-CWP-4931 — every signed-in portal address drew the STAFF
//           failure panel: *Failed · We could not open this page · Retry ·
//           Download error report · Cancel*, with no way to sign in. Measured
//           signed out at 1280 and 390 on 2026-09-11 on `/stop-or-restart`,
//           `/final-bill` and `/account`.
// Tests:    src/portal/requests/StopOrRestart.dom.test.tsx
// ───────────────────────────────────────────────────────
import { useTranslation } from "react-i18next";

import { PortalState } from "../components/states";
import { usePortalPath } from "../components/primitives";

/**
 * The loading and failed states for a signed-in portal screen, as a CUSTOMER
 * should meet them.
 *
 * ⚠ **ONE FILE BECAUSE THE ALTERNATIVE IS TWO COPIES OF ONE VISUAL DECISION**
 * (B14 rule 36). `Signed` serves four routes and two of them are this lane's;
 * passing the same eight lines from each page is how the portal ended up with
 * two `TwoCol`s and three `Panel`s.
 *
 * ⚠ **WHAT IT REPLACES, AND WHY THAT PANEL WAS WRONG RATHER THAN MERELY
 * PLAIN.** `@/components/StateFrame`'s `FailedWithRetry` is the STAFF panel: a
 * red *Failed* pill, *"the address may be wrong"*, and a **Download error
 * report** button. A customer has nowhere to send an error report and no idea
 * what one is — `components/states.tsx` records the same finding on the
 * service-centre finder — and the panel offered **no way to sign in** to the
 * one visitor who most needs one: somebody whose session has ended at a
 * signed-in address.
 *
 * ⚠ **THE SENTENCE IS THE REFUSAL'S OWN, NOT A SENTENCE OF OURS.**
 * `errors.auth-001` already reads *"You're signed out. Sign in again to
 * continue."*, which is exactly right and is what `refusalText` returns for a
 * 401. R-22 asks that the three states differ by their WORDS; the loading
 * sentence is the screen's own (*"Looking up your final bill…"*) and the
 * failed one is the server's. Inventing a third here would put our words over
 * the server's on the one screen where the server knows more than we do.
 *
 * ⚠ **TWO WAYS OUT, AND BOTH ARE REAL.** *Sign in* is a real address, so a
 * ⌘-click opens it in a second tab and the address bar tells a person where
 * they are (`ButtonLink`, which `PortalState` composes for a `to`). *Retry* is
 * the shell's own refetch. Neither is a control wired to nothing, which is
 * `DEF-MET-4764`'s defect and the reason `PortalState` leaves `waysOut`
 * optional rather than demanding one it cannot supply.
 */
export function useSignedOutState() {
  const { t } = useTranslation();
  const portalPath = usePortalPath();
  return (state: { kind: "loading" | "failed"; sentence: string; retry: () => void }, reading: string) => {
    if (state.kind === "loading") {
      return <PortalState kind="loading" sentence={reading} />;
    }
    // `DEF-CWP-10563`: this card IS the whole page on `/final-bill` and
    // `/stop-or-restart` when signed out, and it drew no heading. The other 34
    // signed-in addresses show the shared failure card titled "We could not
    // open this page."; the same words are this page's h1, hidden so nothing
    // on screen moves.
    return (
      <>
      <h1 className="sr-only">{t("portal.failedTitle")}</h1>
      <PortalState
        kind="failed"
        sentence={state.sentence}
        waysOut={[
          {
            label: t("portal.signIn.commit"),
            // ⚠ RESOLVED HERE, never a bare `/sign-in`: a bare path comes out
            // `//portal/sign-in`, a protocol-relative URL to another host that
            // reads as a perfectly good string to every assertion we own
            // (`BR-CWP-007`, hard-won law 2).
            to: portalPath("/sign-in"),
            tone: "primary",
            testKey: "sign-in",
          },
          { label: t("states.failed.retry"), onClick: state.retry, testKey: "retry" },
        ]}
      />
      </>
    );
  };
}
