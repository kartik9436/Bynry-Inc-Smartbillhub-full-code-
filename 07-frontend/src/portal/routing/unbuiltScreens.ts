// ── Trace ──────────────────────────────────────────────
// Defects: DEF-CWP-3988 (ten screens the drawing describes have no address in
//          the product; three are already pointed at by LIVE controls) ·
//          DEF-CWP-3925 (a live screen behind a dead control — the mirror of
//          dead UI, and the fault this file exists to make impossible) ·
//          DEF-CWP-3959 · DEF-CWP-3962
// Rules:   CLAUDE.md hard-won law 2, mirror clause — *"when you write a hold,
//          write the test that fires when the hold expires, in the same
//          commit … and when you land a screen, grep for the control that was
//          holding it"* · CR-068 R3
// Tests:   src/portal/routing/unbuiltScreens.test.ts
// Impacts: holds.ts · screenIds.ts · shell/PortalShell.tsx ·
//          06-backend/apps/portal/selectors.py (ERRAND_HELD_UNTIL)
// ───────────────────────────────────────────────────────
//
// THE TEN SCREENS THE DRAWING DESCRIBES AND THE PRODUCT DOES NOT SERVE — AND,
// FOR EACH, WHAT WOULD HAVE TO BE RELEASED ON THE DAY IT LANDS.
//
// `08-screen-layouts.md` draws 75 screens; `PORTAL_SCREENS` registers 50. Of
// the 25 without an address, four are steps or states inside a screen that IS
// built, seven are staff-side settings screens that exist in the staff app,
// and four the drawing itself marks deferred or blocked. **These ten are
// simply not built** (DEF-CWP-3988).
//
// ⚠ **NOTHING IS WRONG TODAY AND THAT IS THE WHOLE DIFFICULTY.** Every hold
// pointing at these screens is HONEST right now. The fault arrives later, on
// the day one of them lands, because landing a screen and releasing the
// control that pointed at it are two acts and only the first feels like the
// work. That is `DEF-CWP-3925` — the portal's front page had two working doors
// out of eight, every refusal written correctly and every one of them false by
// the time a customer read it — and it cost a week.
//
// ⚠ **WHY THIS REGISTER IS SEPARATE FROM `holds.ts`, WHICH IS NOT AN
// ACCIDENT.** `holds.ts` is keyed by a hold's i18n REASON key and answers *is
// this refusal still true*. It can only see a screen that something REFUSES to
// open. Seven of these ten have no control pointing at them at all — nothing
// refuses, so there is no reason key, so `holds.ts` cannot hold a row and
// `G103` cannot fire. This register is keyed by the SCREEN, so the seven that
// nothing points at are visible as rows rather than as an absence, which is
// the one thing no check in this repo can see (`DEF-CUS-3653`'s lesson: an
// absence is invisible to every check we have).
//
// ⚠ **THE THREE LIVE-CONTROLLED ONES ARE COVERED BY THREE DIFFERENT
// MECHANISMS, WHICH IS WHY NOBODY COULD ANSWER "ARE THEY ALL COVERED".** A
// hold register read by a Python gate, a server dict read by a Django test,
// and a self-releasing route helper read by a vitest case. Each is sound and
// none of them knows about the other two. `unbuiltScreens.test.ts` is the one
// place that asks the question across all three.

/** How the day-it-lands failure would be caught — or the admission that it would not. */
export type ScreenPointer =
  /**
   * A held control names this screen through `PORTAL_HOLDS`.
   * **WATCHED** by `g103_holds_cannot_rot.py`, which fails the merge the day
   * the screen gains a row in `PORTAL_SCREENS`.
   */
  | { readonly kind: "hold"; readonly reasonKey: string; readonly note: string }
  /**
   * The SERVER decides, and names the releasing screen in its own dict.
   * **WATCHED** by `06-backend/tests/test_cwp_holds_expire.py`.
   */
  | { readonly kind: "server"; readonly symbol: string; readonly note: string }
  /**
   * The control RELEASES ITSELF — it reads `PORTAL_SCREENS` at render time and
   * draws nothing while the screen is unbuilt, so it cannot rot. **WATCHED**
   * by the named front-end case, which fires when the screen lands and names
   * the work that is still outstanding.
   *
   * ⚠ This is the STRONGEST of the four and the least visible, because there
   * is no refusal anywhere to grep for. `BR-CWP-093` — *nothing empty ever
   * appears* — is why: an unbuilt destination is ABSENT, never a greyed
   * control, so there is no stale sentence to find.
   */
  | { readonly kind: "self-releasing"; readonly symbol: string; readonly note: string }
  /**
   * **NOTHING POINTS AT THIS SCREEN AT ALL**, so no gate can fire when it
   * lands. The honest admission, and the residual risk DEF-CWP-3988 should be
   * read for. The count of these is asserted by the test so it can only fall
   * deliberately — the same posture `holds.ts` takes with `unwatched`.
   */
  | { readonly kind: "none"; readonly note: string };

export interface UnbuiltScreen {
  /** The `CWP-###` `08-screen-layouts.md` allocates and `PORTAL_SCREENS` lacks. */
  readonly id: string;
  /** The drawing's own heading, so a reader need not open the document. */
  readonly drawnAs: string;
  readonly pointer: ScreenPointer;
}

export const DRAWN_BUT_UNBUILT: readonly UnbuiltScreen[] = [
  {
    id: "CWP-021",
    drawnAs: "P7 · Accept an invitation",
    pointer: {
      kind: "none",
      note: "The invitation flow's landing screen. `CWP-026` (people with access) is the screen that would SEND one and is itself unbuilt, so there is no control anywhere to hold — the whole feature is absent rather than deferred.",
    },
  },
  {
    id: "CWP-026",
    drawnAs: "P12 · People with access",
    pointer: {
      kind: "none",
      note: "The drawing gives it a head action *+ Invite someone*, already marked **held** in `08-screen-layouts.md` — but the screen that would carry it is not built, so the hold is drawn and not coded. Nothing in the product points here.",
    },
  },
  // ⚠ **`CWP-035` · P21 · Send your own reading STOOD HERE, `kind: "hold"`,
  // AND IT LANDED 2026-10-17 (`DEF-CWP-10175`, `US-CWP-042`).** It was the
  // one screen of the ten held by a control that NAMED it, and the release
  // went exactly as this register was built for: the screen got its row in
  // `PORTAL_SCREENS`, the suite went red naming the Readings head action, and
  // the `HeldButton` became a link to `/usage/submit` in the same commit.
  {
    id: "CWP-048",
    drawnAs: "P34 · Moving out or moving on",
    pointer: {
      kind: "server",
      symbol: "ERRAND_HELD_UNTIL",
      note: "`CWP-046`'s *Moving out* errand card. The server names the releasing screen per card — `move_out: \"CWP-048\"` — and `tests/test_cwp_holds_expire.py` reads it against `PORTAL_SCREENS`. Its two siblings (`move_home`, `add_service`) are `None`: no screen is allocated for them at all, which the dict states rather than implies.",
    },
  },
  {
    id: "CWP-049",
    drawnAs: "P35 · Documents we need from you",
    pointer: {
      kind: "none",
      note: "Nothing points here. ⚠ `BR-CWP-089` is the reason it is not merely late: the portal accepts NO upload, so the screen cannot be built as drawn without a ruling. `portal.yourAccount.sendCertificateHeld` is a `policy` hold about the same constraint on a different screen.",
    },
  },
  {
    id: "CWP-053",
    drawnAs: "P39 · Messages",
    pointer: {
      kind: "self-releasing",
      symbol: "messagesRoute",
      note: "The *Messages* word in the signed-in header. `MESSAGES_SCREEN_ID` is the hold WRITTEN AS DATA (`DEF-CWP-3982`) and `messagesRoute()` resolves it against `PORTAL_SCREENS` on every render, so the link appears the moment the screen lands and cannot go stale. `PortalShell.test.tsx`'s HOLD EXPIRY case fires then and names the unread COUNT (`US-CWP-067`, `DEF-CWP-3901`) as the work still outstanding.",
    },
  },
  {
    id: "CWP-059",
    drawnAs: "P45 · Help and answers — signed in",
    pointer: {
      kind: "none",
      note: "The signed-in twin of `CWP-011`, which IS built and which the header's *Help* link opens for everyone. So a signed-in customer reaches a working screen — the guest one — and nothing refuses. There is no control to release, only a screen to replace.",
    },
  },
  {
    id: "CWP-061",
    drawnAs: "P47 · An answer where the question is asked",
    pointer: {
      kind: "none",
      note: "⚠ NOT A SCREEN OF ITS OWN — the drawing calls it *`CWP-028` + one block*: the `AttachedAnswerCard` slot under the bill's charges panel. `DEF-CWP-3945` is the same gap seen from the other end (a clerk pins an answer and the customer never sees it) and is where the work is tracked. Listed here so the two rows cannot be closed independently of each other.",
    },
  },
  {
    id: "CWP-062",
    drawnAs: "P48 · A tip where it lands",
    pointer: {
      kind: "none",
      note: "⚠ ALSO NOT A SCREEN — `CWP-033` with the `TipBar` filled. Unlike `CWP-061` its server side IS reachable: `tenancy_seam.tip_for_screen(tenant_id, screen)` exists and is the worked example `DEF-CWP-3945` is told to copy.",
    },
  },
  {
    id: "CWP-068",
    drawnAs: "P54 · Everything we sent you, and what came back",
    pointer: {
      kind: "none",
      note: "The delivery log. `CWP-031` (documents and letters) is built and is the nearest thing a customer has; nothing on it points here, so nothing rots. Its drawn head action *↓ Download a year* is the same one `CWP-031` now SERVES, live, through `GET accounts/{id}/documents/year.zip` (`CR-085` `CPB-15`, 2026-09-08) — the hold it used to name is gone.",
    },
  },
];

/** The ids, for a caller that only needs membership. */
export const UNBUILT_SCREEN_IDS: readonly string[] = DRAWN_BUT_UNBUILT.map((s) => s.id);

/**
 * How many of the ten nothing points at — the number DEF-CWP-3988 says the row
 * should be read for.
 *
 * ⚠ **ASSERTED IN THE TEST SO IT CAN ONLY FALL DELIBERATELY.** It is not a
 * target and it is not a failure; it is the count of screens whose arrival no
 * check in this repo can notice. Seven today.
 */
export const UNPOINTED_COUNT = DRAWN_BUT_UNBUILT.filter((s) => s.pointer.kind === "none").length;
