// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:  `CR-140-BRC07` — a *Write-offs* link at the head of Payments →
//          Debtors, opening the ONE write-off approval queue.
// Ruled:   PO 2026-09-23, verbatim: *"3 Add a Write-offs link on the Debtors
//          tab? (b) add it - fix it"* (`OQ-PAY-12613`, CLOSED). The case put:
//          *Dana requests a $1,202.40 write-off on Monday; on Tuesday she wants
//          to know whether it was approved; from Payments there is no way in.*
// Rules:   `BR-PAY-020` (a write-off is INITIATED in payments and APPROVED in
//          Finance) · `BR-SHL-003` (an inaccessible module's navigation is not
//          drawn) · `BR-SHL-025` (a null access cell hides nothing) · CLAUDE.md
//          hard-won law 2's MIRROR · law 7 (2), *what would make this pass
//          wrongly*
// Screens: S34 · PAY-02 Debtors (the door) → S36 · FIN-01 Revenue & AR (the
//          queue, `WriteOffQueuePanel`)
// ───────────────────────────────────────────────────────
//
// ══════════════════════════════════════════════════════════════════════════
// ONE MORE DOOR TO THE ONE QUEUE — NEVER A SECOND QUEUE
// ══════════════════════════════════════════════════════════════════════════
// Until this change the only way out of Payments to the approval queue was the
// result panel `OutstandingsTab` draws AFTER a write-off is submitted
// (`writeOffQueueDoor.dom.test.tsx` owns that door). A clerk checking the next
// day had nothing to press. This file owns the SECOND door and asks of it
// exactly the questions that file asks of the first:
//
//   1 · **WHAT DOES THE HEAD BUILD?** The app's own route table is opened at
//       the Debtors tab and the href is read OFF THE RENDERED ANCHOR. Nothing
//       here tells the page where to point.
//   2 · **WHERE DOES THAT ADDRESS GO?** It is CLICKED, inside the same router,
//       and the destination is read back three ways — the address, the screen
//       id (`resolveScreen`) and the component `App.tsx` mounts there.
//
// ⚠ **THE ADDRESS IS THE SAME ONE THE RESULT PANEL OPENS — `QUEUE` BELOW, AND
// `writeOffQueueDoor.dom.test.tsx` PINS THAT DOOR TO THE SAME CONSTANT.** Two
// doors, one queue. `/finance/write-offs` stays deleted (`CR-135` P1.10) and
// `writeOffOneQueue.test.tsx` keeps it deleted; a case here pins that this door
// never points at it.
//
// ⚠ **THE TENANT IS THE FIRST ASSERTION, NOT A DETAIL (`DEF-CWP-3925`).** The
// href is built by `useTenantPath()`, which reads the tenant off the address.
// Mount the page in a bare `MemoryRouter` with no `/:tenant/…` pattern and it
// builds `//finance/revenue` — a protocol-relative URL to ANOTHER HOST that
// `toContain("finance/revenue")` reads as a perfect answer.
//
// ⚠ **AND WHO SEES THE DOOR IS PART OF THE DOOR.** Revenue & AR is gated on
// A4's `finance_reconcile_export` cell, which `identity/0003` seeds for System
// Admin and Executive and NOT for a Billing Clerk. A link drawn for a clerk
// would open *"Permission denied"* — a live screen behind a dead door, the
// mirror of hard-won law 2 — so it is drawn only where the cell is not `—`
// (`BR-SHL-003`), and drawn while the cell is unknown (`BR-SHL-025`). The last
// describe block pins all three states. **The drawing's own Dana is a System
// Admin** (p081, *"DW Dana Whitfield · System Admin"*), so the PO's case is the
// first one below.
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactElement } from "react";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { RouterProvider, createMemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import { APP_ROUTES } from "@/App";
import type { MyPermissions, SessionUser, ShellDisplay } from "@/api/endpoints";
import { queryKeys } from "@/api/queryClient";
import { ToastProvider } from "@/components/Toast";
import { GeneralLedgerPage } from "@/features/ledger/GeneralLedgerPage";
import { RevenueArPage } from "@/features/ledger/RevenueArPage";
import { FINANCE_PERMISSION } from "@/features/ledger/financeShared";
import { CELL_FULL, CELL_NONE } from "@/features/metering/meteringShared";
import { resolveScreen } from "@/routing/screenIds";

import { PaymentsSegmentRoute } from "./PaymentDetailPage";
import { PAYMENTS_PERMISSION } from "./paymentsShared";

const TENANT = "brazosbend";

/** The Debtors tab, at the address `App.tsx` mounts it on. */
const DEBTORS = `/${TENANT}/payments/outstandings`;
/** Where the write-off queue is — the SAME constant `writeOffQueueDoor`'s
 *  result-panel door is pinned to. */
const QUEUE = `/${TENANT}/finance/revenue`;
/** The standalone queue page's address, deleted on purpose by `CR-135` P1.10. */
const DELETED_SECOND_QUEUE = `/${TENANT}/finance/write-offs`;

/** The words a clerk reads on the link. Written out rather than asked of
 *  `t()`: a test that reads the catalogue for the string it then finds would
 *  pass with the key and the link deleted together. B14 rule 33 — a label, one
 *  word. */
const LABEL = "Write-offs";

// ⚠ **CLEANUP IS EXPLICIT.** This repo's vitest config declares no
// `setupFiles`, so auto-cleanup never runs and a second case would render over
// the first.
afterEach(cleanup);

// ══════════════════════════════════════════════════════════════════════════
// FIXTURES
// ══════════════════════════════════════════════════════════════════════════

/** p081's Dana — *"DW Dana Whitfield · System Admin"*. */
const DANA_ADMIN: SessionUser = {
  id: "u-dana",
  full_name: "Dana Whitfield",
  email: "dana.whitfield@sample.test",
  phone: null,
  role: "system_admin",
  role_name: "System Admin",
  must_change_password: false,
};

/** A Billing Clerk — who records payments and requests write-offs, and whose
 *  A4 row carries no Finance cell. */
const SAM_CLERK: SessionUser = {
  ...DANA_ADMIN,
  id: "u-sam",
  full_name: "Sam Ortega",
  email: "sam.ortega@sample.test",
  role: "billing_clerk",
  role_name: "Billing Clerk",
};

/** `GET /me/permissions`, as `identity/0003` seeds the two A4 rows this door
 *  reads: payments for both roles, Finance for the admin alone. */
function permissions(user: SessionUser, finance: string): MyPermissions {
  return {
    role: user.role,
    role_name: user.role_name,
    permissions: [
      { code: PAYMENTS_PERMISSION, label: "Payments (record)", access: CELL_FULL },
      { code: FINANCE_PERMISSION, label: "Finance / reconcile / export", access: finance },
    ],
  } as MyPermissions;
}

/** `GET /shell/display` — what the app shell BOOTS on. Without it
 *  `ShellWithSession` returns its skeleton and the route's element never
 *  mounts, so a case asserting an ABSENCE would pass over a screen never drawn. */
const SHELL = {
  regional: {
    country: "US",
    timezone: "America/Chicago",
    language: "en",
    first_day_of_week: "sunday",
    currency: "USD",
    number_format: "1,234.56",
    date_format: "MM/DD/YYYY",
    time_format: "12-hour",
  },
  company: {
    legal_name: "Brazos Bend Utility District No. 1",
    dba_name: "Brazos Bend Utilities",
    has_logo: false,
    mark: { letters: "BB", background_hex: null, ink_hex: null, contrast_ratio: null },
    brand_primary_hex: null,
  },
  period: null,
} as unknown as ShellDisplay;

/**
 * Open one address in **the app's own router**.
 *
 * `createMemoryRouter(APP_ROUTES)`, never a hand-written `<Route>`: the subject
 * is which of `App.tsx`'s rows mounts the Debtors tab and which answers the
 * address its link builds. `perms: null` leaves `/me/permissions` unanswered —
 * the fixture serves nothing over the network, so it stays unknown — which is
 * `BR-SHL-025`'s *"a null cell hides nothing"* state.
 */
function openApp(address: string, user: SessionUser, perms: MyPermissions | null) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: Infinity } },
  });
  client.setQueryData(queryKeys.me, user);
  client.setQueryData(queryKeys.shellDisplay, SHELL);
  if (perms !== null) {
    client.setQueryData(queryKeys.myPermissions, perms);
  }
  const router = createMemoryRouter(APP_ROUTES, { initialEntries: [address] });
  render(
    <QueryClientProvider client={client}>
      <ToastProvider>
        <RouterProvider router={router} />
      </ToastProvider>
    </QueryClientProvider>,
  );
  return router;
}

/** The component `App.tsx` mounts at the address the router settled on — the
 *  router's OWN answer to *"which screen opens"*, needing none of its data. */
function screenAt(router: ReturnType<typeof openApp>): unknown {
  // ⚠ The data router's match type declares no `element`; the runtime shape
  // carries one, so the read is narrowed here once.
  const matched = router.state.matches.at(-1)?.route as { element?: ReactElement } | undefined;
  return matched?.element?.type;
}

/**
 * Prove the page on screen IS the Debtors tab before asserting anything about
 * its head — three ways, because a door is a pair of screens and a case that
 * found (or failed to find) the link on another tab proves nothing here.
 *
 * `App.tsx` mounts `PaymentsSegmentRoute` at `/payments/:tab` (`CR-137-BRC07`
 * `P3.9`), which renders `PaymentsPage` for a tab id; the strip's own
 * `aria-selected` is the rendered answer to *"which tab is this"*.
 */
async function expectDebtorsTab(router: ReturnType<typeof openApp>): Promise<void> {
  expect(screenAt(router)).toBe(PaymentsSegmentRoute);
  expect(router.state.matches.at(-1)?.params.tab).toBe("outstandings");
  const tab = await screen.findByRole("tab", { name: "Debtors" });
  expect(tab).toHaveAttribute("aria-selected", "true");
}

/** The link's href as the browser would read it, off the rendered anchor. */
async function doorHref(): Promise<string> {
  const door = await screen.findByRole("link", { name: LABEL });
  return door.getAttribute("href") ?? "";
}

// ══════════════════════════════════════════════════════════════════════════
// 1 · WHAT THE DEBTORS HEAD BUILDS
// ══════════════════════════════════════════════════════════════════════════

describe("CR-140-BRC07 · the Write-offs door the Debtors head builds", () => {
  it("is on the Debtors tab — the screen App.tsx mounts at that address", async () => {
    const router = openApp(DEBTORS, DANA_ADMIN, permissions(DANA_ADMIN, CELL_FULL));
    await expectDebtorsTab(router);
    expect(resolveScreen(DEBTORS).a1).toBe("S34");
    expect(await screen.findByRole("link", { name: LABEL })).toBeInTheDocument();
  }, 30000);

  it("carries the tenant, so it is not an address on another host", async () => {
    // ⚠ `DEF-CWP-3925` IN ONE ASSERTION — with no tenant in scope this is
    // `//finance/revenue`, which a browser reads as `https://finance/revenue`.
    openApp(DEBTORS, DANA_ADMIN, permissions(DANA_ADMIN, CELL_FULL));
    const href = await doorHref();
    expect(href.startsWith("//")).toBe(false);
    expect(href).toBe(QUEUE);
  }, 30000);

  it("points at the queue's screen — S36, not the trial balance, not a second queue", async () => {
    openApp(DEBTORS, DANA_ADMIN, permissions(DANA_ADMIN, CELL_FULL));
    const href = await doorHref();
    expect(resolveScreen(href).a1).toBe("S36");
    expect(resolveScreen(href).r10).toBe("FIN-01");
    // S56 is what `DEF-PAY-6329` found the other door opening.
    expect(resolveScreen(href).a1).not.toBe("S56");
    // One more door to the one queue — never the standalone page's address.
    expect(href).not.toBe(DELETED_SECOND_QUEUE);
  }, 30000);
});

// ══════════════════════════════════════════════════════════════════════════
// 2 · WHERE IT GOES WHEN IT IS PRESSED
// ══════════════════════════════════════════════════════════════════════════

describe("CR-140-BRC07 · pressing it opens Revenue & AR", () => {
  it("by address, by screen id and by the component mounted there", async () => {
    const router = openApp(DEBTORS, DANA_ADMIN, permissions(DANA_ADMIN, CELL_FULL));
    const user = userEvent.setup();
    await user.click(await screen.findByRole("link", { name: LABEL }));

    // ⚠ **PRESSED, NOT RE-OPENED.** Handing the href to a fresh router would
    // prove the address is good; pressing it in the SAME router proves the
    // control is a router link that actually navigates there.
    expect(router.state.location.pathname).toBe(QUEUE);
    expect(resolveScreen(router.state.location.pathname).a1).toBe("S36");
    expect(screenAt(router)).toBe(RevenueArPage);
    expect(screenAt(router)).not.toBe(GeneralLedgerPage);
    // And the screen really drew: the head's own explainer, which only
    // Revenue & AR renders and the trial balance never does.
    expect(
      await screen.findByText(i18n.t("finance.explainer.revenue")),
    ).toBeInTheDocument();
    expect(document.body.textContent).not.toContain(i18n.t("finance.explainer.gl"));
  }, 30000);
});

// ══════════════════════════════════════════════════════════════════════════
// 3 · WHO SEES IT, AND WHERE
// ══════════════════════════════════════════════════════════════════════════

describe("CR-140-BRC07 · the door is drawn only where it leads somewhere", () => {
  it("is drawn while the Finance cell is still unknown (BR-SHL-025)", async () => {
    // ⚠ **WHAT WOULD MAKE THE ABSENCE CASE BELOW PASS WRONGLY:** a link that
    // is never drawn at all. This case, with no permissions answer, is what
    // tells a hidden-for-a-clerk door from a door that simply is not there.
    openApp(DEBTORS, DANA_ADMIN, null);
    expect(await doorHref()).toBe(QUEUE);
  }, 30000);

  it("is NOT drawn for a Billing Clerk, whose A4 row has no Finance cell (BR-SHL-003)", async () => {
    const router = openApp(DEBTORS, SAM_CLERK, permissions(SAM_CLERK, CELL_NONE));
    // Prove the Debtors head DREW before asserting what it lacks — an absence
    // over an unmounted page is the false pass `SHELL` exists to prevent. The
    // ladder's link is the Debtors head's other door (`P0.9`), so it is the
    // proof the head this link would sit in is on screen.
    await expectDebtorsTab(router);
    expect(
      await screen.findByRole("link", { name: i18n.t("payments.tab.collections") }),
    ).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: LABEL })).toBeNull();
  }, 30000);

  it("is the Debtors tab's alone — the Payments tab's head does not draw it", async () => {
    openApp(`/${TENANT}/payments/record`, DANA_ADMIN, permissions(DANA_ADMIN, CELL_FULL));
    // The strip draws on every tab; wait for it, then assert the absence —
    // over a head that is really the Payments tab's, not Debtors'.
    expect(await screen.findByRole("tab", { name: "Payments" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    expect(screen.queryByRole("link", { name: LABEL })).toBeNull();
  }, 30000);
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-140-BRC07 · OQ-PAY-12613 (CLOSED 2026-09-23, option b) · decision
//         log 2026-09-23 "RULED: A *WRITE-OFFS* LINK ON THE DEBTORS TAB" ·
//         blueprint p081 7·1 and p086 7·3b rendered at 1.3
// generated: 2026-09-23 by lane WRITEOFFS-LINK
// proof: RED FIRST, in vitest — see the CR's §5 for the failures quoted
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
