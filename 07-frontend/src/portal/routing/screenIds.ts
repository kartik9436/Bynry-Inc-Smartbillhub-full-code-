// ── Trace ──────────────────────────────────────────────
// Change:   CR-068 §9 (PO 2026-09-03: *"You can assign number CWP-nnn - Assig
//           all unqie numbers"*) · CR-068 §11d (`CWP-###` is mirrored here,
//           "the portal's own, NOT the staff map") · PO 2026-09-03: *"We need
//           unique screen ID - on every screen"*
// Rules:    CR-068 §13 G78's rule (every portal route carries a CWP number from
//           §9's register, and no route invents one) — enforced by
//           10-scripts/gates/g82_cwp_screen_register.py
// Tests:    src/portal/routing/screenIds.test.ts
// ───────────────────────────────────────────────────────
// THE ONE PLACE A PORTAL SCREEN SAYS WHICH SCREEN IT IS.
//
// The staff app keeps `src/routing/screenIds.ts` with A1's `S` ids and r10's
// badges; neither vocabulary numbers a portal screen, and CR-068 §9 says the
// portal's series is deliberately outside the `S` namespace. So the portal
// keeps its own register, mirroring §9 row for row: the `CWP` id, the
// blueprint's own label (`G1`, `P8`, `B1` — kept as the mapping key, exactly
// as the staff map keeps r10's badge), and the route it is served at, relative
// to `/{tenant}/portal`. A route with no row, or a row with an id §9 does not
// allocate, fails G82 — an invented id is an id nobody can look up in a bug
// report.
//
// Rows are added as waves build the screens they name. Wave A: one.

import { matchPath } from "react-router-dom";

export interface PortalScreen {
  /** The route, relative to `/:tenant/portal` — `/` is the front page. */
  readonly path: string;
  /** The `CWP-###` id CR-068 §9 allocates. Quoted, never invented. */
  readonly id: string;
  /** The blueprint's own label, kept as the cross-reference (§9 column 2). */
  readonly blueprint: string;
  /** §9's title, for a reader; never rendered. */
  readonly title: string;
}

export const PORTAL_SCREENS: readonly PortalScreen[] = [
  { path: "/", id: "CWP-001", blueprint: "G1", title: "The public front page" },
  { path: "/start-service", id: "CWP-008", blueprint: "G8", title: "Can I get service here?" },
  // ⚠ CWP-047 AND CWP-009 SHARE ONE ROUTE, AND THAT IS THE JOURNEY RATHER
  // THAN A SHORTCUT. `08-screen-layouts.md` numbers *About you* (CWP-047,
  // step 2 of 4) and *Check and send* (CWP-009, step 4 of 4) separately
  // because they are two drawings; they are two STEPS of one form on one
  // draft link, and giving each its own address would let somebody bookmark
  // step 4 of a form they have not filled in. The register names the route
  // by the screen a visitor LANDS on, and each step still carries its own
  // `data-screen` for the walkthrough to assert.
  {
    path: "/start-service/:draft",
    id: "CWP-047",
    blueprint: "P33",
    title: "Start service — for someone with no account",
  },
  { path: "/ask", id: "CWP-010", blueprint: "G10", title: "Ask for a quick service" },
  // CR-068 wave P (screen half) — CWP-002, quick pay step 1. ⚠ **ITS OWN
  // ROUTE AND NOT A STEP OF ONE**, unlike `/enrol`'s three drawings: step 2
  // is `CWP-003` and belongs to `US-CWP-004`, which is BLOCKED on payment
  // rails — so there is one screen here today and the register says so
  // rather than reserving an address for a drawing nobody has built.
  { path: "/pay", id: "CWP-002", blueprint: "G2", title: "Quick pay · find the bill" },
  // CR-068 phase 5 — the six payment screens, registered before their lanes
  // start. See the block in `portalRoutes.tsx` for why they are declared in one
  // place rather than by the lane that builds each.
  { path: "/pay/check", id: "CWP-003", blueprint: "G3", title: "Quick pay · check and pay" },
  { path: "/pay/done", id: "CWP-004", blueprint: "G4", title: "Quick pay · done" },
  { path: "/pay-now", id: "CWP-038", blueprint: "P24", title: "Pay now" },
  { path: "/pay-now/check", id: "CWP-076", blueprint: "P55", title: "Check before you pay" },
  { path: "/pay-now/done", id: "CWP-077", blueprint: "P56", title: "Payment made" },
  { path: "/payment-methods", id: "CWP-039", blueprint: "P25", title: "Your payment methods" },
  { path: "/autopay", id: "CWP-040", blueprint: "P26", title: "Autopay" },
  { path: "/fees", id: "CWP-050", blueprint: "P36", title: "Fees to pay" },
  // CR-068 wave D. ⚠ THE `title` COLUMN IS §9's, AND FOR THREE OF THESE FOUR
  // §9's title NAMES A DIFFERENT SCREEN FROM `08-screen-layouts.md`
  // (`DEF-CWP-3728` — ⚠ **THIS COMMENT CITED `DEF-CWP-3647` UNTIL 2026-09-05
  // AND NO SUCH ROW HAS EVER EXISTED IN `10-defect-log.csv`.** A citation to a
  // defect nobody can look up is a dead end for whoever follows it, which is
  // `DEF-CWP-3800`'s fault one family over): §9 reads `CWP-013` *"One centre,
  // its hours and its limits"* and `CWP-014` *"Pay in person, from Pay now"*,
  // while the layout document — written while looking at the wireframes — has
  // `CWP-013` as the LIST and `CWP-014` as one centre, which is also what this
  // wave's demo script says. **The blueprint LABELS agree (`G13`, `G14`, `P46`)
  // and G82 checks the label**, so the ids are exactly as §9 allocates them and
  // nothing is renumbered. The titles below are §9's, quoted, with the
  // divergence recorded rather than quietly reconciled.
  //
  // ⚠ **AND IT IS NOT THREE SCREENS BUT SIX — `CWP-059`..`CWP-062` DIVERGE THE
  // SAME WAY AND THIS COMMENT DID NOT SAY SO (`DEF-CWP-3728`, 2026-09-05).**
  // §9's help block is shifted against the layout document's by one:
  //   CWP-059  §9 *Help and answers — signed in*  = layout, same     ✔
  //   CWP-060  §9 *Under a bill, when it is attached* | layout *One answer*
  //   CWP-061  §9 *Tips*                              | layout *An answer
  //            where the question is asked*
  //   CWP-062  §9 *Nothing at all when none is live*  | layout *A tip where it
  //            lands*
  // **THE ROUTES BELOW FOLLOW THE LAYOUT DOCUMENT AND THE TITLES QUOTE §9**, so
  // `/help/:slug` — one answer — carries §9's *"Under a bill, when it is
  // attached"*. That is the divergence, on one line, and it is why a reader
  // must not take a `title` here as a description of the route beside it.
  // `08-screen-layouts.md` is what the code was built to; §9 is what the change
  // request allocated. NOTHING IS RENUMBERED and no code changes for this.
  { path: "/help", id: "CWP-011", blueprint: "G11", title: "Help and answers" },
  { path: "/help/:slug", id: "CWP-060", blueprint: "P46", title: "Under a bill, when it is attached" },
  { path: "/visit", id: "CWP-013", blueprint: "G13", title: "One centre, its hours and its limits" },
  { path: "/visit/:slug", id: "CWP-014", blueprint: "G14", title: "Pay in person, from Pay now" },
  // CR-068 wave E. ⚠ `/enrol` CARRIES CWP-016 IN THIS REGISTER AND DRAWS
  // THREE SCREENS. The register names a route by the screen a visitor LANDS
  // on — the same reading `/start-service/:draft` takes for `CWP-047` and
  // `CWP-009` — and `CWP-017` and `CWP-018` carry their own `data-screen`
  // for the walkthrough to assert. §9's titles, quoted.
  { path: "/sign-in", id: "CWP-015", blueprint: "P1", title: "Front door" },
  { path: "/enrol", id: "CWP-016", blueprint: "P2", title: "Find my account" },
  { path: "/forgot-password", id: "CWP-019", blueprint: "P5", title: "Forgotten password" },
  // CR-189-BRC10 — §9's next free ground, allocated in the same commit.
  { path: "/update-email", id: "CWP-079", blueprint: "P5u", title: "Update your registered email" },
  { path: "/home", id: "CWP-022", blueprint: "P8", title: "Portal home" },
  // CR-068 wave F — the landlord's four rows and their total.
  { path: "/accounts", id: "CWP-023", blueprint: "P9", title: "All my accounts" },
  { path: "/account", id: "CWP-065", blueprint: "P51", title: "Your account" },
  // ⚠ **`CWP-078` IS CR-068 §9's OWN *"Next free ground"*, TAKEN AND WRITTEN
  // BACK INTO §9 IN THE SAME COMMIT** — G82 refuses an id the register does
  // not allocate, and an id allocated in code but not in §9 is an id nobody
  // can look up in a bug report. ⚠ `blueprint` is the REPORT the screen
  // serves rather than a portal wireframe: the customer-portal blueprint
  // draws no property statement at all, and the shape comes from the Reports
  // Build Brief's `R24c` (p070–p071) scoped by `P4.15`'s ruling. Naming a
  // portal page it does not have would be a cross-reference to nothing.
  { path: "/property", id: "CWP-078", blueprint: "R24c", title: "Property statement" },
  // CR-068 wave G — bills, with owing beside amount.
  { path: "/bills", id: "CWP-027", blueprint: "P13", title: "Bills" },
  // CR-068 wave H — one bill and the two screens that hang off it. ⚠ THREE
  // ROUTES AND THREE IDS, unlike `/enrol`'s one-route-three-drawings: each of
  // these is somewhere a customer is SENT — a bill's detail from the list, its
  // document from an email, its explainer from a *why is this higher* link —
  // and a tab state cannot be put in a link. §9's titles, quoted.
  { path: "/bills/:number/document", id: "CWP-029", blueprint: "P15", title: "The bill as it was printed" },
  { path: "/bills/:number/comparison", id: "CWP-030", blueprint: "P16", title: "Why is this bill different?" },
  { path: "/bills/:number", id: "CWP-028", blueprint: "P14", title: "One bill, line by line" },
  // CR-068 wave G — the two writes a customer may make. ⚠ `/accounts/add` sits
  // BELOW `/accounts` and is listed after it; `matchPath` is exact, so the two
  // cannot shadow each other, and the order here is for a reader rather than
  // for the matcher.
  { path: "/my-details", id: "CWP-024", blueprint: "P10", title: "My details" },
  // CR-068 wave G — CWP-025, the PREFERENCES half of US-CWP-028. ⚠ ITS OWN
  // ADDRESS rather than a tab of `/my-details`: `08-screen-layouts.md`
  // numbers it separately and draws a different template (PreferenceGrid
  // then T4, against CWP-024's T3), and a tab state cannot be put in a
  // link — which is the same reading `/bills/:number/comparison` takes.
  { path: "/my-details/preferences", id: "CWP-025", blueprint: "P11", title: "How we contact you" },
  { path: "/accounts/add", id: "CWP-020", blueprint: "P6", title: "Add another account" },
  // CR-068 wave B. ⚠ CWP-006 AND CWP-007 SHARE ONE ROUTE, and the register
  // carries the one the URL opens on. A stranger who has just sent a report
  // has no session to carry them anywhere, so the confirmation replaces the
  // form in place (BR-CWP-028); each STATE tags itself with its own id in
  // the DOM, which is what a bug report needs, while the ROUTE is what G82
  // reads.
  // CR-068 wave H — what we sent, the plan waiting on a signature, level pay.
  // ⚠ NONE of the three carries an account id in its address. `/documents` and
  // `/plan-offer` read the session's whole set (BR-CWP-010), and `/level-pay`
  // reads one account the switcher already knows — an id in the path would be
  // a database id in a place a person can read and copy (B14 rule 31).
  { path: "/documents", id: "CWP-031", blueprint: "P17", title: "Documents and letters" },
  { path: "/plan-offer", id: "CWP-063", blueprint: "P49", title: "A plan the utility has offered you" },
  // CR-068 — CWP-066 (US-CWP-055). ⚠ **DECLARED BEFORE `/level-pay`, AND HERE
  // THE ORDER IS FOR THE MATCHER AND NOT ONLY FOR A READER.** `matchPath` is
  // exact so `/level-pay` cannot swallow `/level-pay/standing` today; the day
  // either gains a wildcard, the deeper path must already be first. `CWP-044`
  // is the JOINING screen and this is the STANDING one — two questions about
  // one subject, and a customer is sent to each from a different place.
  {
    path: "/level-pay/standing",
    id: "CWP-066",
    blueprint: "P52",
    title: "Where your level pay stands",
  },
  { path: "/level-pay", id: "CWP-044", blueprint: "P30", title: "Level pay" },
  // CR-068 — CWP-032 (US-CWP-037). ⚠ NOT under `/bills/:number`: a customer
  // reaches their final bill from a move-out letter and from the account, not
  // by knowing its number, and there is exactly one per account.
  { path: "/final-bill", id: "CWP-032", blueprint: "P18", title: "Your final bill" },
  // CR-068 wave H — usage, readings and equipment. ⚠ `/readings` and
  // `/equipment` have their own addresses rather than sharing `/usage`: both
  // are places a customer comes back to and both carry a *back to usage* link,
  // which is what `08-screen-layouts.md` draws (`back ← USAGE`). Neither
  // address carries an account id — the switcher knows which account is being
  // read, and a uuid in a URL is a database id on screen (B14 rule 31).
  { path: "/usage", id: "CWP-033", blueprint: "P19", title: "Usage" },
  { path: "/readings", id: "CWP-034", blueprint: "P20", title: "Every reading" },
  // US-CWP-042 · DEF-CWP-10175 — CWP-035 at the address the drawing's own
  // bar carries (`/pine-hill/portal/usage/submit`). Reached from CWP-034's
  // head action, and only while the utility has self-read switched on.
  { path: "/usage/submit", id: "CWP-035", blueprint: "P21", title: "Send us your reading" },
  { path: "/equipment", id: "CWP-037", blueprint: "P23", title: "Meters and equipment" },
  // CR-068 wave G — CWP-041 (US-CWP-048), the money list.
  { path: "/payments", id: "CWP-041", blueprint: "P27", title: "Payments and receipts" },
  // CR-068 wave M — CWP-042 and CWP-043 (US-CWP-051 · US-CWP-052). § 9's
  // titles, quoted. Neither route carries an account id; the switcher names
  // the account (B14 rule 31).
  { path: "/ask-for-a-plan", id: "CWP-042", blueprint: "P28", title: "Ask for a payment plan" },
  { path: "/plan", id: "CWP-043", blueprint: "P29", title: "Your payment plan" },
  // CR-068 — CWP-046 (US-CWP-060). §9's title, quoted. ⚠ NO account id, and
  // for a different reason from every other signed-in route: a portal service
  // request carries no account at all (BR-CWP-026), so this list is the
  // LOGIN's and there is nothing narrower it could be scoped to.
  { path: "/requests", id: "CWP-046", blueprint: "P32", title: "What do you need?" },
  // CR-068 — CWP-052 (US-CWP-062). §9's title, quoted. ⚠ No account id in the
  // address even though the FIGURES are one account's: the switcher names it
  // (B14 rule 31), the same reading `/level-pay` and `/plan` already take.
  {
    path: "/stop-or-restart",
    id: "CWP-052",
    blueprint: "P38",
    title: "Stop or restart service",
  },
  // CR-068 wave L1 — the four arrears screens (US-CWP-056/057/058/059). §9's
  // titles, quoted. ⚠ FOUR ROUTES AND FOUR IDS, unlike `/enrol`'s
  // one-route-three-drawings: each is somewhere a customer is SENT from a
  // different place — the overdue ladder from a bill, help paying from the
  // ladder, the protections list from a notice, money back from the payments
  // list — and none of them is a step of a form. None carries an account id;
  // the switcher names the account (B14 rule 31).
  { path: "/overdue", id: "CWP-057", blueprint: "P43", title: "What happens if this is not paid" },
  { path: "/help-paying", id: "CWP-056", blueprint: "P42", title: "Help paying" },
  { path: "/protections", id: "CWP-064", blueprint: "P50", title: "What is protecting your supply" },
  { path: "/money-back", id: "CWP-045", blueprint: "P31", title: "Credits and refunds" },
  // CR-068 wave R — CWP-051, CWP-055 and CWP-054 (US-CWP-063 · US-CWP-065 ·
  // US-CWP-066). §9's titles and labels, quoted.
  //
  // ⚠ **`:reference` IS AN `SR-` NUMBER AND `:number` IS A `BL-` NUMBER** — not
  // one database id between them (B14 rule 31, PO 2026-08-30: *"no Databse ID
  // on screen - that is a rule"*). Both are printed on paper the customer is
  // holding and are what they read out on the telephone.
  //
  // ⚠ **`/ask-a-question` CARRIES NO BILL IN ITS PATH, AND THAT IS TC-5.** A
  // question with no bill is a normal question, and a path segment cannot be
  // absent — so the bill travels in `?bill=`, where it can be.
  { path: "/requests/:reference", id: "CWP-051", blueprint: "P37", title: "Track your request" },
  { path: "/bills/:number/dispute", id: "CWP-055", blueprint: "P41", title: "Dispute a bill or a reading" },
  { path: "/ask-a-question", id: "CWP-054", blueprint: "P40", title: "Ask a question" },
  { path: "/report", id: "CWP-006", blueprint: "G6", title: "Report a problem" },
  { path: "/track", id: "CWP-012", blueprint: "G12", title: "Track anything" },
];

/** Which portal screen is this sub-path (the part after `/{tenant}/portal`)? */
export function resolvePortalScreen(subpath: string): PortalScreen | null {
  const normalised = subpath === "" ? "/" : subpath;
  for (const screen of PORTAL_SCREENS) {
    if (matchPath(screen.path, normalised) !== null) {
      return screen;
    }
  }
  return null;
}
