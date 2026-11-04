// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defect:  `DEF-PAY-6329` — the PO's *"Write-off: Screen and navigation are
//          missing."* The screen is NOT missing. `OutstandingsTab.tsx:834`
//          handed `WriteOffResultPanel` `tenantPath(FINANCE_ROUTE)`, so the
//          only door from payments to the write-off approval queue opened the
//          GENERAL LEDGER — `App.tsx:1518` mounts `GeneralLedgerPage` at the
//          bare `/finance` (S56, the trial balance) and `:1520` mounts
//          `RevenueArPage` at `/finance/revenue` (S36), which is where
//          `WriteOffQueuePanel` lives.
// Change:  `CR-060` T10 moved `/finance`'s landing from Revenue & AR to the
//          trial balance; this href was written against the older landing and
//          was never re-pointed.
// Rules:   `BR-PAY-020` — a write-off is INITIATED in payments and APPROVED in
//          Finance, so this one link is the whole second half of the rule ·
//          CLAUDE.md hard-won law 2's MIRROR · law 7's *looking at the wrong
//          thing*
// Screens: S34 Outstandings (the door) · S36 · FIN-01 Revenue & AR (the queue)
// ───────────────────────────────────────────────────────
//
// ══════════════════════════════════════════════════════════════════════════
// WHY THE EXISTING CASE COULD NEVER HAVE SEEN THIS
// ══════════════════════════════════════════════════════════════════════════
// `OutstandingsTab.test.tsx`'s *"DEF-100: the requester's screen offers NO
// Approve control and points at Finance"* renders `WriteOffResultPanel`
// directly and **hands it the destination**:
//
//     financeQueueHref="/t/brazosbend/finance"
//     …
//     expect(html).toContain('href="/t/brazosbend/finance"');
//
// **The test supplies the answer and then asserts it.** The component's own
// computation of the href is not in that case at all, so it is green for every
// value `OutstandingsTab` could possibly pass — including the wrong one it did
// pass. That is CLAUDE.md law 7's fourth shape, *a test named after an
// assertion it does not make*. Its fixture value is not even the shape this app
// builds (`tenantPath` writes `/{tenant}/…`, never `/t/{tenant}/…`), which is
// the tell nobody read.
//
// ══════════════════════════════════════════════════════════════════════════
// SO THIS FILE ASKS THE TWO QUESTIONS THAT CASE CANNOT
// ══════════════════════════════════════════════════════════════════════════
// **1 · WHAT DOES THE COMPONENT BUILD?** The real `OutstandingsTab` is mounted
// under the REAL path pattern and DRIVEN — select the debtor, Write off, submit
// — until the panel is on screen, and the href is read OFF THE ANCHOR. Nothing
// in this file tells it where to point.
//
// ⚠ **THE PATH PATTERN IS LOAD-BEARING AND IS NOT DECORATION** (`DEF-CWP-3925`,
// CLAUDE.md law 2's mirror): the href is built by `useTenantPath()`, which
// reads the tenant off `useLocation().pathname`. Mount this component bare in a
// `MemoryRouter` with no `/:tenant/…` route and the tenant is `""`, so every
// address it builds comes out `//finance/revenue` — a protocol-relative URL to
// ANOTHER HOST that `toContain("finance/revenue")` reads as a perfect answer.
// The leading-`//` assertion exists so that trap cannot be re-opened.
//
// **2 · WHERE DOES THAT ADDRESS GO?** Asserting the string is what the old case
// did. So the href the component built is handed to the APP'S OWN route table
// (`APP_ROUTES`) and the destination is read back three ways — the **address**,
// the **screen id** (`resolveScreen`), and **the component `App.tsx` mounts
// there**. A test that wrote its own `<Route>` for the destination would be
// testing its own fixture and would have passed on `/finance` just as happily.
//
// ⚠ **THE DESTINATION IS ASSERTED WITHOUT ITS DATA, ON PURPOSE.** Revenue & AR
// draws its panels only once `GET /settings/regional` has yielded a fiscal
// period and the revenue report has loaded, so a case that waited for the
// queue's own rows would be a case about two seeded read models. The three
// answers above need none of that, and the rendered check uses the page's own
// explainer — `finance.explainer.revenue` against `finance.explainer.gl`, a
// string each of the two screens renders in its head and the other never does.
// That the panel itself draws rows and an Approve control is already
// `writeOffOneQueue.test.tsx`'s case; what was missing, and what this file
// adds, is that **the door from payments opens the screen holding it**.
//
// ⚠ **AND THE OLD VALUE IS PINNED AS A CASE OF ITS OWN**, because *"the new
// address opens the queue"* does not say the old one did not. It did not: it
// opens S56 and `GeneralLedgerPage`. That case is the one that states the
// defect, and it is why this file goes red on the code as it stood rather than
// merely green on the code as it stands.
//
// ⚠ **WHAT WOULD MAKE THESE PASS WRONGLY**, asked as CLAUDE.md law 7 (2)
// requires: a catch-all drawing the same screen for any address — and
// `/:tenant/finance/:tab` IS one. The last case opens an address nobody
// declared and pins that it draws the TRIAL BALANCE, so *"Revenue & AR is what
// answered"* is a sentence about this route and not about the router's
// fallback.
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactElement } from "react";
import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {
  MemoryRouter,
  Route,
  RouterProvider,
  Routes,
  createMemoryRouter,
} from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import { APP_ROUTES } from "@/App";
import type { ApiClient } from "@/api/client";
import type { OutstandingRow, OutstandingsResponse, SessionUser, ShellDisplay } from "@/api/endpoints";
import { queryKeys } from "@/api/queryClient";
import { ToastProvider } from "@/components/Toast";
import { FINANCE_ROUTE } from "@/features/ledger/financeShared";
import { GeneralLedgerPage } from "@/features/ledger/GeneralLedgerPage";
import { RevenueArPage } from "@/features/ledger/RevenueArPage";
// ⚠ **READ THROUGH VITE'S OWN `?raw`** — the idiom `IssueCreditDoor.dom.test`,
// `ShellWithSession` and `DataTable` already use. This app's `src` tsconfig
// carries no node types, so `node:fs` is a red typecheck and `?raw` is the one
// that compiles.
import REVENUE_AR_SOURCE from "@/features/ledger/RevenueArPage.tsx?raw";
import { resolveScreen } from "@/routing/screenIds";

import { OutstandingsTab, outstandingsQueryKey } from "./OutstandingsTab";

const TENANT = "brazosbend";
const AS_OF = "2026-08-15";

/** Where the write-off queue actually is. */
/** ⚠ **IT GAINED `?view=writeoffs` ON 2026-09-24 (Finance `P2.23`).** `P2.18`
 *  split Revenue & AR into FIVE views with **Services** as the landing one, so
 *  the bare address this door used to build still resolves — to the
 *  revenue-by-service table, with no queue on it. **That is `DEF-PAY-6329`
 *  happening a second time to the same button**, one level deeper: the clerk
 *  presses *Open the Finance queue*, gets a real working screen, and reports
 *  the write-off screen as missing. */
const QUEUE = `/${TENANT}/finance/revenue?view=writeoffs`;
/** The same address with the query stripped — what `resolveScreen` matches on,
 *  since a screen id is a property of the PATH and the view is a property of
 *  the screen. Kept separate so the two assertions cannot mask each other. */
const QUEUE_PATH = `/${TENANT}/finance/revenue`;
/** What the door pointed at until `DEF-PAY-6329` — the trial balance. */
const TRIAL_BALANCE = `/${TENANT}${FINANCE_ROUTE}`;

// ⚠ **CLEANUP IS EXPLICIT.** This repo's vitest config declares no
// `setupFiles` and no `globals` (see `vite.config.ts`), so
// `@testing-library/react`'s auto-cleanup never runs and the second case in a
// file renders a SECOND copy over the first — every query then throws *"Found
// multiple elements"*, which reads like a product fault rather than a harness
// one.
afterEach(cleanup);

const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

// ══════════════════════════════════════════════════════════════════════════
// FIXTURES
// ══════════════════════════════════════════════════════════════════════════

/** US-PAY-012 TC-1's own debtor: A-10802 Novak, $948.20, 91 days late. */
const NOVAK: OutstandingRow = {
  account_id: "acc-10802",
  account_no: "A-10802",
  customer_name: "Novak, P.",
  balance: "948.2000",
  days_late: 91,
  bucket: "90+",
  open_bills: 3,
  last_payment_on: "2026-04-22",
  notice_summary: "final_48_hour sent",
  collection_tier: "final_48_hour",
  next_step_due: null,
  plan_status: null,
  autopay: false,
  bad_address: false,
} as unknown as OutstandingRow;

/** One debtor, and the tiles folded from that same row — `debtorTiles` reads
 *  `ageing`, so a response without it is a crash rather than an empty screen. */
function outstandings(): OutstandingsResponse {
  return {
    as_of: AS_OF,
    rows: [NOVAK],
    totals: { accounts: 1, owed: "948.2000", dso_days: null },
    ageing: [
      { bucket: "current", amount: "0.0000", accounts: 0, share: "0.0" },
      { bucket: "1-30", amount: "0.0000", accounts: 0, share: "0.0" },
      { bucket: "31-60", amount: "0.0000", accounts: 0, share: "0.0" },
      { bucket: "61-90", amount: "0.0000", accounts: 0, share: "0.0" },
      { bucket: "90+", amount: "948.2000", accounts: 1, share: "100.0" },
    ],
    problems: [],
    debtors_window: { page: 1, per: null, count: 1, pages: 1 },
  } as unknown as OutstandingsResponse;
}

/** ⚠ **A STUB THAT ANSWERS EVERYTHING CERTIFIES NOTHING.** It serves the one
 *  path this journey posts to and THROWS on any other, so a screen that starts
 *  calling something else fails loudly here instead of being waved through. */
function writeOffClient(): ApiClient {
  const refuse = async (path: string): Promise<never> => {
    throw new Error(`the fixture was asked for ${path}, which it does not serve`);
  };
  return {
    get: refuse,
    put: refuse,
    patch: refuse,
    delete: refuse,
    post: async (path: string) => {
      if (path !== "/write-offs") {
        return refuse(path);
      }
      return {
        status: 201,
        headers: {},
        data: {
          id: "wo-1",
          status: "requested",
          account_id: NOVAK.account_id,
          amount: NOVAK.balance,
          posted_to_ledger: false,
          problems: [],
        },
      };
    },
  } as unknown as ApiClient;
}

/** A clerk with the reach S34's bulk bar grants. */
const DANA: SessionUser = {
  id: "u-dana",
  full_name: "Dana Whitfield",
  email: "dana.whitfield@sample.test",
  phone: null,
  role: "billing_clerk",
  role_name: "Billing Clerk",
  must_change_password: false,
};

/** `GET /shell/display` — what the app shell BOOTS on. Without it
 *  `ShellWithSession` returns its skeleton, the route's element never mounts,
 *  and a case asserting an ABSENCE passes over a screen never drawn. */
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

// ══════════════════════════════════════════════════════════════════════════
// 1 · WHAT THE COMPONENT BUILDS
// ══════════════════════════════════════════════════════════════════════════

/**
 * Drive S34 to the write-off result panel and hand back the door's href.
 *
 * The journey is the real one — select the debtor, press the bulk bar's Write
 * off, write the note the schema requires, submit — because the panel exists
 * only after a request has been made, and a fixture that force-rendered the
 * panel would be back to supplying the answer.
 */
async function openDoorHref(): Promise<string> {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  queryClient.setQueryData(outstandingsQueryKey(AS_OF, "", false), outstandings());
  const user = userEvent.setup();
  render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        {/* ⚠ THE REAL PATH PATTERN — `DEF-CWP-3925`. See this file's header. */}
        <MemoryRouter initialEntries={[`/${TENANT}/payments/outstandings`]}>
          <Routes>
            <Route
              path="/:tenant/payments/:tab"
              element={
                <OutstandingsTab
                  client={writeOffClient()}
                  asOf={AS_OF}
                  onAsOfChange={() => undefined}
                  currency="USD"
                  writeBlockedReason={null}
                />
              }
            />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );

  // ⚠ **THE ROW IS RE-RENDERED AFTER FIRST PAINT AND THE FIRST NODE IS
  // DETACHED.** `DataTable` reads its stored column preference in an effect, so
  // the table draws three times on mount; a `findBy*` that resolves on the
  // first of those hands back an element that is gone by the time it is
  // clicked, and **the click then lands on nothing at all — silently**. The
  // checkbox even reports `checked` afterwards, because an orphaned input is
  // nobody's controlled input, so the fixture looks like it worked and the bulk
  // bar simply never appears. Wait for the row, let the effects settle, then
  // query AGAIN and click that.
  const rowBox = t("payments.outstandings.selectRow", { account: "A-10802" });
  await screen.findByLabelText(rowBox);
  await new Promise((resolve) => setTimeout(resolve, 0));
  await user.click(screen.getByLabelText(rowBox));
  // ⚠ **`Write off` IS IN THE OVERFLOW, AND THE MENU IS A `<details>`.**
  // `P4.11` dropped the bulk bar to *"two plus an overflow"* (B14 rule 15), so
  // this control is one click further in than it reads on the drawing. Scoped
  // to the bulk bar, because every ROW draws a `More actions` trigger too and
  // an unscoped query would take whichever came first.
  const bulkBar = within(await screen.findByTestId("debtor-bulk-bar"));
  await user.click(bulkBar.getByLabelText(t("table.rowActions.more")));
  await user.click(
    await screen.findByRole("button", { name: t("payments.outstandings.action.writeOff") }),
  );
  await user.type(
    await screen.findByLabelText(new RegExp(t("payments.writeOff.note"))),
    "uncollectible",
  );
  await user.click(await screen.findByRole("button", { name: t("payments.writeOff.submit") }));

  const door = await screen.findByRole("link", { name: t("payments.writeOff.openFinanceQueue") });
  return door.getAttribute("href") ?? "";
}

describe("DEF-PAY-6329 · the door S34 builds", () => {
  it("carries the tenant, so it is not an address on another host", async () => {
    // ⚠ `DEF-CWP-3925` IN ONE ASSERTION. With no tenant in scope this comes out
    // `//finance/revenue`, which a browser reads as `https://finance/revenue`
    // and which every `toContain` in this repo would call a pass.
    const href = await openDoorHref();
    expect(href.startsWith("//")).toBe(false);
    expect(href).toBe(QUEUE);
    // `P2.23` — and the VIEW is asserted on its own, because a typo'd
    // `?view=writeoff` resolves silently to the landing view and renders a
    // perfectly good screen with no queue on it.
    expect(new URL(href, "https://x").searchParams.get("view")).toBe("writeoffs");
  }, 30000);

  it("points at the write-off QUEUE's screen, not the trial balance's", async () => {
    // The screen id is the second half of the hold-expiry pattern CLAUDE.md
    // prescribes: an address that looks right can open a different screen, and
    // S56 against S36 is exactly the difference the PO reported as *"missing"*.
    const href = await openDoorHref();
    const path = href.split("?")[0];
    expect(path).toBe(QUEUE_PATH);
    expect(resolveScreen(path).a1).toBe("S36");
    expect(resolveScreen(path).r10).toBe("FIN-01");
    expect(resolveScreen(path).a1).not.toBe("S56");
  }, 30000);
});

// ══════════════════════════════════════════════════════════════════════════
// 2 · WHERE THAT ADDRESS GOES, THROUGH THE APP'S OWN ROUTE TABLE
// ══════════════════════════════════════════════════════════════════════════

/** Open one address in **the app's own router** and let its effects run.
 *
 *  `createMemoryRouter(APP_ROUTES)`, never a hand-written `<Route>`: a test
 *  that declares its own route table is testing its own fixture, and the whole
 *  subject here is which of `App.tsx`'s two finance rows answers. */
function openApp(address: string) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: Infinity } },
  });
  client.setQueryData(queryKeys.me, DANA);
  client.setQueryData(queryKeys.shellDisplay, SHELL);
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
 *  router's OWN answer to *"which screen opens"*, needing none of that screen's
 *  data to be true. */
function screenAt(router: ReturnType<typeof openApp>): unknown {
  // ⚠ The data router's own match type is `AgnosticDataRouteObject`, which
  // declares no `element` — it is the runtime shape that carries one, so the
  // read is narrowed here rather than asserted at each call site.
  const matched = router.state.matches.at(-1)?.route as { element?: ReactElement } | undefined;
  return matched?.element?.type;
}

describe("DEF-PAY-6329 · where that address opens", () => {
  it("opens Revenue & AR — by address, by screen id and by mounted component", () => {
    const router = openApp(QUEUE);
    expect(router.state.location.pathname).toBe(QUEUE_PATH);
    expect(resolveScreen(QUEUE_PATH).a1).toBe("S36");
    expect(screenAt(router)).toBe(RevenueArPage);
    expect(screenAt(router)).not.toBe(GeneralLedgerPage);
    // And it really drew that screen: the head's own explainer, which only
    // Revenue & AR renders.
    expect(document.body.textContent).toContain(t("finance.explainer.revenue"));
  }, 30000);

  it("and the address it pointed at until today opens the TRIAL BALANCE", () => {
    // ⚠ **THIS IS THE DEFECT, STATED AS A TEST.** A clerk pressed *"Open the
    // Finance queue"*, landed here, found no queue, and reported the screen as
    // missing. Nothing 404s and nothing is red — which is why it survived three
    // weeks and why the report reads as *"the screen is missing"*.
    const router = openApp(TRIAL_BALANCE);
    expect(router.state.location.pathname).toBe(TRIAL_BALANCE);
    expect(resolveScreen(TRIAL_BALANCE).a1).toBe("S56");
    expect(screenAt(router)).toBe(GeneralLedgerPage);
    expect(document.body.textContent).toContain(t("finance.explainer.gl"));
    expect(document.body.textContent).not.toContain(t("finance.explainer.revenue"));
  }, 30000);

  it("an address nobody declared falls to the trial balance, not to Revenue & AR", () => {
    // ⚠ **WHAT WOULD MAKE EVERY CASE ABOVE PASS WRONGLY:** `/:tenant/finance/:tab`
    // is a catch-all, so without this case *"Revenue & AR answered"* could be a
    // sentence about the router's fallback rather than about `/finance/revenue`.
    const router = openApp(`/${TENANT}/finance/revenue-that-never-existed`);
    expect(screenAt(router)).toBe(GeneralLedgerPage);
    expect(document.body.textContent).not.toContain(t("finance.explainer.revenue"));
  }, 30000);

  it("and Revenue & AR is the screen that holds the queue", () => {
    // ⚠ **THE LINK BETWEEN THIS FILE AND `writeOffOneQueue.test.tsx`, AND IT
    // HAS TO BE READ FROM SOURCE.** That file proves `WriteOffQueuePanel`
    // renders its rows and its Approve control; the cases above prove the door
    // opens `RevenueArPage`. Neither says the panel is ON that page, and the
    // panel needs a fiscal period and a loaded revenue report before it draws —
    // so a rendered assertion here would be a case about two seeded read models
    // rather than about the door. **If this goes red, the queue has moved and
    // the door above is pointing at a screen that no longer holds it.**
    expect(REVENUE_AR_SOURCE).toContain("<WriteOffQueuePanel");
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: DEF-PAY-6329 (lane FINANCE-DOOR) — filed by lane PAY-TRIAGE from the
//         PO's payments validation, 2026-09-23
// generated: 2026-09-23 by lane FINANCE-DOOR
// proof: RED FIRST, in vitest, the harness that runs it — run against the
//        pre-fix `tenantPath(FINANCE_ROUTE)` the two "door S34 builds" cases
//        failed on `expected '/brazosbend/finance' to be
//        '/brazosbend/finance/revenue'` and `expected 'S56' to be 'S36'`.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
