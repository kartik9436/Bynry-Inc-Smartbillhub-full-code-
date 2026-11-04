// ── Trace ──────────────────────────────────────────────
// Story:    US-CUS-004 · US-CUS-005 · US-CUS-013 · US-CUS-014 · US-CUS-015 ·
//           US-CUS-016 · US-CUS-018   Screens: S21 (the account it opens over)
// Change:   CR-094-BRC01 step 2 wave L — the eight quick actions move OVER the
//           account. PO ruling 2026-09-13, verbatim: *"Yes move the eight quick
//           actions over the account"*.
// Rules:    BR-CUS-1051 (every quick action on an account opens over the
//           account) · BR-SHL-025 (a control this deployment cannot honour
//           renders disabled WITH its reason) · B14 rule 38 (where a drawing and
//           our UI rules disagree about how a FORM IS BUILT, the UI rules win) ·
//           B14 rule 30 (DECLINED 2026-08-30 — the PO answered this INSTANCE and
//           no rule is minted)
// Tests:    accountActionOverlays.dom.test.tsx — the eight by ADDRESS, both
//           doors, and the step that survives a reload
// ───────────────────────────────────────────────────────
//
// ══════════════════════════════════════════════════════════════════════════
// MOUNT, DO NOT COPY — AND THE CONTAINER IS A **ROUTE**, NOT A `useState`
// ══════════════════════════════════════════════════════════════════════════
// Wave J left eight of the thirteen quick actions navigating away because each
// already owns a complete, tested, multi-step form with park-and-resume — about
// **7,300 lines** across six wizards and two billing screens. Re-typing any of
// them as a dialog is the duplicate code the PO's standing instruction forbids
// (*"Do all changes based on actual code — also don't create duplicate code"*),
// so **not one field, step or schema is re-authored here.** What moves is the
// CONTAINER.
//
// ⚠ **AND THE CONTAINER IS A NESTED ROUTE RENDERED THROUGH `<Outlet/>`, WHICH
// IS THE ONLY SHAPE THAT KEEPS ALL FOUR PROPERTIES AT ONCE.** A dialog opened
// from a `useState` flag would have cost every one of them:
//
//   1. **`useParams().accountId` KEEPS RESOLVING.** The account route already
//      carries `:accountId`, and a CHILD of it inherits the param — so
//      `MoveOutWizard`, `MoveInWizard`, `CloseOutPage`, `ChangePlanWizard` and
//      `PaymentPlanWizard` read their subject exactly as they always did. Not
//      one of the five needed a prop.
//   2. **THE STEP SURVIVES A RELOAD.** `MoveOutWizard`, `MoveInWizard` and
//      `DisconnectWizard` keep their step in `?step=`; a state-flag dialog would
//      have thrown that away on every refresh, which is park-and-resume's whole
//      point.
//   3. **THE EXIT IS ALREADY WRITTEN.** Every one of these screens leaves by
//      `navigate(tenantPath(accountDetailPath(accountId)))`. Under a nested
//      route that navigation UN-MATCHES the child and the dialog closes — so the
//      close button each screen already had is the close button of the dialog,
//      and nothing was rewired.
//   4. **BOTH DOORS KEEP THEIR ADDRESS.** `/accounts/{id}/move-out` is the same
//      string it was before this wave; it now renders the account underneath.
//      The three screens that were NOT account-scoped keep their own addresses
//      untouched (`/billing/bills/{id}/document`, `/billing/fix?bill=`,
//      `/disconnects/new?account=`) and gain a second, account-scoped one.
//
// The skill's §5 table reserves *"needs an address a person can send"*, *"must
// survive a refresh"* and *"more than one step"* for a SCREEN rather than a
// modal. A ROUTED dialog has all three, which is why the PO's answer to this
// instance does not collide with the estimate precedent it left standing.
//
// ══════════════════════════════════════════════════════════════════════════
// THE HEAD IS BARE ON PURPOSE — AND "BARE" NOW MEANS ABSENT, NOT EMPTY
// ══════════════════════════════════════════════════════════════════════════
// Each mounted screen draws its own `PageHeader` — kicker, 32px title (B14 rule
// 40), roll-up sentence and a back arrow that already points at this account. A
// dialog head carrying the action's name as well would put TWO headings on one
// surface and spend the description budget B14 rule 32 caps at one sentence per
// section. So `ModalShell` takes the action's name as the dialog's ACCESSIBLE
// name instead — the screen's heading stays the screen's, which is the same
// "mount, do not copy" discipline applied to the chrome.
//
// ⚠ **THAT WAS RIGHT, AND IT SHIPPED AS AN 80px BLANK STRIP (`DEF-CUS-5151`).**
// `titleHidden` emptied the head's TEXT and kept the head's BOX, so six of these
// eight drew a lone ✕ over two rules' worth of nothing and began their real
// heading 181px down the card. The Product Owner drove five of them and reported
// it. The repair is `ModalShell`'s, not this file's — a head with no kicker and
// no title is not rendered at all — so no screen has to work around it (B14
// rule 36).
//
// ══════════════════════════════════════════════════════════════════════════
// WHY THESE STAY DIALOGS, DECIDED RATHER THAN ASSUMED
// ══════════════════════════════════════════════════════════════════════════
// The blueprint draws Move-out, Move-in, Close out, Change plan, Payment plan
// and Disconnect as FULL PAGES with the app's nav and their own addresses, and
// the skill's §5 test sends *more than one step* and *needs an address* to a
// SCREEN. **That drawing is the as-built record of the product BEFORE
// `BR-CUS-1051`**, which the PO ruled on 2026-09-13 — verbatim, *"Yes move the
// eight quick actions over the account"* — precisely so that a clerk answering
// a question about arrears does not lose the arrears. **The ruling is newer
// than the drawing and it is about the CONTAINER**, so the container is a
// dialog and everything the drawing draws INSIDE it is unchanged: the back
// arrow, the kicker, the 32px title, the roll-up sentence, the step rail.
// Re-raising the container would be law 13's re-ask. No general modal-vs-screen
// rule is minted here: B14 rule 30 stays DECLINED.
//
// ⚠ **WHAT THE RULING DOES NOT SETTLE IS THE SIZE, SO IT IS MEASURED.** At
// 1440x900 the mounted screens render 876–1585px tall; the card grew past the
// window and `.modal-overlay` scrolled the ✕ off the top. `ModalShell`'s wide
// variant now ends at the window edge and scrolls its own body. The WIDTH stays
// 1120px at both 1280 and 1440 because that is what the drawn content is drawn
// at — the blueprint renders these pages in a 1440 frame behind a 240px nav.
import { useLocation, useNavigate, useOutlet } from "react-router-dom";

import { ModalShell } from "@/components/FormModal";
import type { Translator } from "@/features/tenancy/settingsShared";
import { useTenantPath } from "@/routing/tenantPath";

import {
  accountChangePlanPath,
  accountCloseOutPath,
  accountDetailPath,
  accountMoveInPath,
  accountMoveOutPath,
  accountPaymentPlanPath,
} from "./customersShared";

/** The eight the ruling names. The ids are `AccountQuickActionId`'s own, so a
 *  reader can line this table up against `accountQuickActions.ts` without a
 *  mapping table in between. */
export type AccountOverlayId =
  | "moveOut"
  | "moveIn"
  | "closeOut"
  | "printBill"
  | "issueCredit"
  | "changePlan"
  | "disconnectNotice"
  | "paymentPlan";

export interface AccountOverlay {
  id: AccountOverlayId;
  /**
   * The child route's path, RELATIVE to `accounts/:accountId` — the exact
   * string `App.tsx` declares, so the address in the route table and the
   * address this dialog answers to are one literal.
   */
  segment: string;
  /**
   * The label the control on the account ALREADY carries.
   *
   * ⚠ **REUSED, NOT MINTED.** Two strings for one act is how a product grows
   * two names for one thing; `accountQuickActions.ts` says the same about the
   * activate commit. Eleven catalogues already answer all eight.
   */
  titleKey: string;
  /** The screen this MOUNTS — the id on its badge, for the record and for the
   *  law-2 test that asserts each door by address AND by what it opens. */
  screen: string;
  /** The file that screen lives in, relative to `07-frontend/src`. The
   *  by-address test reads it, so `ownsItsHeading` below cannot rot into a
   *  claim about a file that stopped being true. */
  source: string;
  /**
   * **DOES THE MOUNTED SCREEN DRAW ITS OWN `PageHeader`?**
   *
   * Seven of the eight do, and for them the dialog head renders the ✕ alone —
   * two headings on one surface is the description budget B14 rule 32 caps.
   * `issueCredit` mounts `FixABillTab`, which is a TAB: `BillsListPage` draws
   * the head at its own address, so here the DIALOG must, or the surface has no
   * heading at all.
   */
  ownsItsHeading: boolean;
}

/**
 * The eight, in the order `ACCOUNT_QUICK_ACTION_IDS` declares them.
 *
 * ⚠ **`printBill` IS THE ONLY ONE WITH A PARAMETER IN ITS SEGMENT**, because it
 * is the only one of the eight whose subject is a BILL rather than the account:
 * `BillDocumentPage` reads `useParams().invoiceId` and there is nothing
 * account-shaped for it to read. The rail resolves *which* bill (the newest
 * ISSUED one) exactly as it did when the glyph navigated to billing — that
 * derivation is `accountRailReadiness.ts`'s and is not re-made here.
 */
export const ACCOUNT_ACTION_OVERLAYS: readonly AccountOverlay[] = [
  {
    id: "moveOut",
    segment: "move-out",
    titleKey: "customers.account.action.moveOut",
    screen: "ACC-06",
    source: "features/customers/MoveOutWizard.tsx",
    ownsItsHeading: true,
  },
  {
    id: "moveIn",
    segment: "move-in",
    titleKey: "customers.account.action.moveIn",
    screen: "ACC-05",
    source: "features/customers/MoveInWizard.tsx",
    ownsItsHeading: true,
  },
  {
    id: "closeOut",
    segment: "close-out",
    titleKey: "customers.account.action.closeOut",
    screen: "ACC-02.closeOut",
    source: "features/customers/CloseOutPage.tsx",
    ownsItsHeading: true,
  },
  {
    id: "printBill",
    segment: "bills/:invoiceId/document",
    titleKey: "customers.account.action.printBill",
    screen: "BIL-05.document",
    source: "features/billing/BillDocumentPage.tsx",
    ownsItsHeading: true,
  },
  {
    id: "issueCredit",
    segment: "issue-credit",
    titleKey: "customers.account.action.issueCredit",
    screen: "BIL-01",
    source: "features/billing/FixABillTab.tsx",
    ownsItsHeading: false,
  },
  {
    id: "changePlan",
    segment: "change-plan",
    titleKey: "customers.account.action.changePlan",
    screen: "PLN-04",
    source: "features/customers/ChangePlanWizard.tsx",
    ownsItsHeading: true,
  },
  {
    id: "disconnectNotice",
    segment: "disconnect",
    titleKey: "customers.account.action.disconnectNotice",
    screen: "DSC-02",
    source: "features/customers/DisconnectWizard.tsx",
    ownsItsHeading: true,
  },
  {
    id: "paymentPlan",
    segment: "payment-plan",
    titleKey: "customers.account.action.paymentPlan",
    screen: "ACC-02.paymentPlan",
    source: "features/customers/PaymentPlanWizard.tsx",
    ownsItsHeading: true,
  },
];

/** One overlay by id, or `undefined` where none is declared. */
export function accountOverlayFor(id: AccountOverlayId): AccountOverlay | undefined {
  return ACCOUNT_ACTION_OVERLAYS.find((overlay) => overlay.id === id);
}

/**
 * The tenant-relative address that opens `id` over `accountId`.
 *
 * `params` fill the `:name` placeholders of a segment — only `printBill` has
 * one. An unfilled placeholder is a defect rather than a `:invoiceId` in the
 * URL bar, so it THROWS: a link that half-resolves is hard-won law 2's dead
 * control wearing a plausible href.
 */
export function accountOverlayPath(
  id: AccountOverlayId,
  accountId: string,
  params: Readonly<Record<string, string>> = {},
): string {
  const overlay = accountOverlayFor(id);
  if (overlay === undefined) {
    throw new Error(`no account overlay declared for "${id}"`);
  }
  const filled = overlay.segment
    .split("/")
    .map((part) => {
      if (!part.startsWith(":")) {
        return part;
      }
      const value = params[part.slice(1)];
      if (value === undefined || value === "") {
        throw new Error(`account overlay "${id}" needs "${part.slice(1)}"`);
      }
      return encodeURIComponent(value);
    })
    .join("/");
  return `${accountDetailPath(accountId)}/${filled}`;
}

/**
 * Which overlay — if any — the browser is standing on.
 *
 * Pure, and exported so it can be asserted without a browser. It reads the
 * pathname rather than `useMatches`, and that is DELIBERATE: `useMatches`
 * throws outside a data router, and every test in this folder mounts its screen
 * under `<MemoryRouter><Routes>`. A container that only works under
 * `createBrowserRouter` would have taken thirty test files down with it.
 */
export function accountOverlayAt(pathname: string, accountId: string): AccountOverlay | null {
  if (accountId === "") {
    return null;
  }
  const home = `${accountDetailPath(accountId)}/`;
  const at = pathname.indexOf(home);
  if (at === -1) {
    return null;
  }
  const tail = pathname.slice(at + home.length).replace(/\/+$/, "");
  if (tail === "") {
    return null;
  }
  const parts = tail.split("/");
  return (
    ACCOUNT_ACTION_OVERLAYS.find((overlay) => {
      const want = overlay.segment.split("/");
      return (
        want.length === parts.length &&
        want.every((part, index) => part.startsWith(":") || part === parts[index])
      );
    }) ?? null
  );
}

export interface AccountActionOverlayProps {
  /** The account the dialog opens OVER — the page's own `accountId`. */
  accountId: string;
  /** The account's headline, so the dialog says WHICH account it is acting on
   *  even though its head carries no title of its own. */
  kicker: string;
  t: Translator;
}

/**
 * The dialog that hosts whichever of the eight the URL names.
 *
 * Renders NOTHING when no child route matches, which is the account's ordinary
 * state — so mounting this on `AccountDetailPage` costs an un-navigated page
 * one `useOutlet()` call and no markup.
 */
export function AccountActionOverlay(props: AccountActionOverlayProps) {
  const outlet = useOutlet();
  const location = useLocation();
  const navigate = useNavigate();
  const tenantPath = useTenantPath();

  if (outlet === null) {
    return null;
  }
  const overlay = accountOverlayAt(location.pathname, props.accountId);
  // ⚠ **A MATCHED CHILD ALWAYS RENDERS, NAMED OR NOT.** Returning `null` here
  // when the table and the route list disagree would hide a live screen behind
  // a blank page and pass every test — the exact shape hard-won law 2 is about.
  // `accountActionOverlays.dom.test.tsx` proves the two lists agree; this
  // fallback is what happens if they ever stop.
  const title = overlay === null ? props.kicker : props.t(overlay.titleKey);

  return (
    <ModalShell
      title={title}
      kicker={overlay !== null && !overlay.ownsItsHeading ? props.kicker : undefined}
      titleHidden={overlay === null || overlay.ownsItsHeading}
      size="wide"
      onClose={() => navigate(tenantPath(accountDetailPath(props.accountId)))}
    >
      {/* 24px all round, the same inset `.modal-body` gives every other dialog
          in the product — but not `.modal-body` itself, because that class also
          imposes a 20px field-to-field flex gap (B14 rule 39) and what is
          mounted here is a whole screen with its own rhythm, not a field
          stack. */}
      <div className="p-6">{outlet}</div>
    </ModalShell>
  );
}

/** The five addresses that existed BEFORE this wave, re-exported so the
 *  by-address test can prove the overlay table did not invent a new spelling
 *  for a door the product already had (hard-won law 5: one literal). */
export const PRE_EXISTING_OVERLAY_PATHS: Readonly<
  Record<"moveOut" | "moveIn" | "closeOut" | "changePlan" | "paymentPlan", (id: string) => string>
> = {
  moveOut: accountMoveOutPath,
  moveIn: accountMoveInPath,
  closeOut: accountCloseOutPath,
  changePlan: accountChangePlanPath,
  paymentPlan: accountPaymentPlanPath,
};

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-094-BRC01 step 2 wave L · BR-CUS-1051 · decision log 2026-09-13 · 14-ui-conventions.md rules 30 (declined), 32, 38, 39, 40
// generated: 2026-09-13 by the CR-094 wave L build lane
// checklist: A✔ B✔ C✔ D=n/a(no endpoint of its own — every mounted screen keeps its own) E✔ F✔ G✔ H=n/a
// gates: tsc · vitest accountActionOverlays.dom.test.tsx · routeBUtilities (listed on src/styles/route-b-migrated.txt)
// exceptions: E3 `printBill` mounts `BillDocumentPage`, which is BILL-scoped — its segment carries `:invoiceId` and the rail resolves which bill, exactly as it did when the glyph navigated away
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
