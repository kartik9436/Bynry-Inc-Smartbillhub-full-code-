// ── Trace ──────────────────────────────────────────────
// Defects: DEF-729 (no way to raise a service request from the Accounts →
//          Requests tab: the fallback CTA renders only on an EMPTY list) ·
//          DEF-730 (five tabs disable their create CTA with a `ctaReason`, and
//          `NewConnectsTab`'s reason went FALSE the night the wizard shipped)
// Rules:   B14 rule 4 / BR-SHL-044 (EXACTLY ONE primary per screen — the fix
//          honours it, it does not bypass it) · BR-SHL-025 (a control that
//          cannot be used renders DISABLED WITH ITS REASON) · hard-won law 1
//          (a stated refusal is not a guarantee — it has to change with the
//          fact) · hard-won law 2 (built is not wired)
// ───────────────────────────────────────────────────────
//
// ⚠ **THE ASSERTION THAT WAS MISSING, AND IT IS THE WHOLE OF THIS FILE.**
// Both defects escaped a suite that was already green, because every existing
// case covered a state that DOES NOT SHIP:
//
//   * `ServiceRequestsListPage.test.tsx` renders the STANDALONE route, which
//     owns a page header and therefore has the `+ New request` primary. The
//     copy that ships inside the Accounts tab suppresses that header (correctly
//     — two H1s and two primaries break B14 rule 4) and the comment claimed the
//     route was *"not lost … the empty state's CTA below still offers it"*.
//   * Every tab suite renders the EMPTY list, where that CTA exists.
//
// The PO's tab held ONE ROW. So: **a tab WITH ROWS in it offers a way to create
// one.** That sentence is the case below, written once per tab, and it is what
// nothing in this repo asserted.
//
// ⚠ **AND THE SECOND HALF IS THE DISABLED CONTROL.** A tab whose create action
// genuinely cannot start here must still SAY SO on screen (BR-SHL-025) and the
// sentence must be TRUE today. `move-ins` / `move-outs` are that case and are
// asserted as that case — disabled, with a reason, and NOT claiming the wizard
// is unbuilt, because both wizards are built and routed.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import type { MyPermissions } from "@/api/endpoints";
import { queryKeys } from "@/api/queryClient";
import { ToastProvider } from "@/components/Toast";
import { defaultRequestState } from "@/components/tableTypes";

import { ACCOUNTS_TAB_IDS, AccountsListPage } from "./AccountsListPage";
import type { AccountsTab } from "./AccountsListPage";
import {
  ServiceRequestsListPage,
  DEFAULT_SEGMENT,
  requestsTableConfig,
  serviceRequestsQueryKey,
  withSegment,
} from "./ServiceRequestsListPage";
import { ACCOUNTS_PERMISSION } from "./customersShared";
import type { ServiceRequestList } from "./serviceRequestEndpoints";
import { SERVICE_REQUESTS_ROUTE } from "./serviceRequestShared";

const TEST_TENANT = "brazosbend";
const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

/** A full-access clerk. The role is never what is under test here. */
function permissions(): MyPermissions {
  return {
    role: "billing_clerk",
    role_name: "Billing Clerk",
    permissions: [{ code: ACCOUNTS_PERMISSION, label: "Premises / Accounts", access: "Full" }],
  };
}

/**
 * The embedded Requests list's OWN query key.
 *
 * ⚠ It is not the standalone screen's: `urlState={false}` seeds the table state
 * from `defaultRequestState` and never reads the outer page's query string
 * (DEF-664), so the key is the default state's key and nothing else. Seeding
 * the wrong one renders an empty tab and the case below would pass for the
 * wrong reason.
 *
 * ⛔ **`DEF-CUS-5011` — AND `withSegment` IS NOW PART OF THAT DEFAULT.** The
 * list applies its drawn default (`Show: Open`) as a REAL filter rather than
 * an invisible fallback, so its query key carries `segment: open`. This key
 * was the unfiltered one and the tab rendered its loading skeleton — the case
 * below failed on `expect(html).toContain("SR-26-0001")`, which is the useful
 * kind of failure: the fixture stopped modelling the component the moment the
 * component moved.
 */
const EMBEDDED_REQUESTS_KEY = serviceRequestsQueryKey(
  SERVICE_REQUESTS_ROUTE,
  withSegment(
    defaultRequestState(
      requestsTableConfig(t, {
        request: () => <span />,
        type: () => <span />,
        received: () => <span />,
        channel: () => <span />,
        age: () => <span />,
        waitingOn: () => <span />,
        state: () => <span />,
        actions: () => <span />,
      }),
    ),
    DEFAULT_SEGMENT,
  ),
);

/** ONE row — the PO's own tab, which is the state neither defect's suite had. */
function oneRequest(): ServiceRequestList {
  return {
    count: 1,
    next: null,
    previous: null,
    results: [
      {
        id: "sr-0001",
        request_no: "SR-26-0001",
        number_absence: null,
        channel: "walk_in",  // CR-068 wave B — BR-CWP-076's new column
        type: "move_in",
        type_absence: null,
        applicant: "Osei, Grace",
        address: "3450 Oak Ridge Dr",
        address_unit: null,
        received_at: "2026-08-08T09:00:00Z",
        age_days: 15,
        age_is_accented: true,
        waiting_on: "documents",
        state: "more_info",
      },
    ],
    kpis: {
      open: 1,
      waiting_on_customer: 1,
      oldest_waiting: { days: 15, request_no: "SR-26-0001", waiting_on: "documents" },
      approved_not_started: 0,
      refused_this_month: 0,
      period_basis: "server_month_to_date",
    },
    segment: "open",
  };
}

function renderTab(tab: AccountsTab, seed: { requests?: ServiceRequestList } = {}): string {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  queryClient.setQueryData(queryKeys.myPermissions, permissions());
  if (seed.requests !== undefined) {
    queryClient.setQueryData(EMBEDDED_REQUESTS_KEY, seed.requests);
  }
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TEST_TENANT}/accounts?tab=${tab}`]}>
          <AccountsListPage />
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

/** The page head, up to the first table frame: where the ONE primary lives. */
function header(html: string): string {
  const end = html.indexOf("data-table-frame");
  return end === -1 ? html : html.slice(0, end);
}

/**
 * The page header's ACTION ROW alone — `<div class="page-header-actions">`, up
 * to the tab strip that follows it.
 *
 * ⚠ **THIS IS NARROWER THAN `header()` ON PURPOSE, AND THE FIRST DRAFT WAS
 * WRONG WITHOUT IT.** Counting `data-variant="primary"` over everything before
 * the table reported TWO on `new-connects` and `disconnects` — and the second
 * was `WorklistSegments`' SELECTED SEGMENT (`data-size="sm"`,
 * `data-segment="all"`), which is a segmented control's on-state, not a page
 * action. B14 rule 4 is about the page's ONE primary ACTION; a count that
 * cannot tell those apart would either fail on correct code or force the
 * segment strip to change to satisfy a test about a different control.
 *
 * ⚠ **THE CONTROL THAT MOTIVATED IT IS GONE AS OF 2026-08-27 (CR-045 wave G,
 * `DEF-1702`) AND THE NARROWING STAYS — hard-won law 1: the sentence is amended,
 * not deleted, and the scope is not widened back.** `WorklistSegments` was an
 * inert strip in the filter slot and was removed with its five mounts, so
 * `data-segment="all"` no longer renders anywhere. Widening this back to
 * `header()` would go green TODAY and re-arm the exact trap the paragraph above
 * records: the next selected-state control that renders `data-variant="primary"`
 * before the table — a segmented field, a toggle, a chip — would fail a test
 * about page ACTIONS. The narrowing is right for the reason, not for the
 * instance.
 */
function headerActions(html: string): string {
  const start = html.indexOf('class="page-header-actions"');
  if (start === -1) {
    return "";
  }
  const end = html.indexOf('class="page-header-tabs"', start);
  return end === -1 ? html.slice(start) : html.slice(start, end);
}

/**
 * The ONE `<button>` tag carrying `label`.
 *
 * ⚠ **THIS EXISTS BECAUSE A DOCUMENT-WIDE `toContain("disabled")` CANNOT GO
 * RED.** The column chooser alone renders four disabled Move-up / Move-down
 * buttons and the segment strips render four more, so "the page contains a
 * disabled button" is true on every tab whatever the primary does. The
 * assertions below are about ONE control, so they read one tag —
 * `NewConnectsTab.test.tsx`'s `segmentTag`, same reason, same defect family.
 */
function buttonTag(html: string, label: string): string {
  const match = new RegExp(`<button[^>]*>${label.replace(/[+.]/g, "\\$&")}</button>`).exec(html);
  return match === null ? "" : match[0];
}

/** What the ACTIVE tab's create action is called, and whether it may act. */
const EXPECTED: Readonly<Record<AccountsTab, { label: string; live: boolean }>> = {
  // ⛔ `DEF-CUS-10049` (PO 2026-10-11): `+ New account` is DISABLED, with its
  // reason. Still the tab's ONE primary, still visible — asserted below.
  accounts: { label: "+ New account", live: false },
  requests: { label: "+ New request", live: true },
  "new-connects": { label: "+ New connect", live: true },
  // ✅ **LIVE FROM 2026-08-26 — PO ruling, and this row is the ruling.** It
  // read `live: false` with a note that the two wizards were mounted ONLY at
  // `/accounts/:accountId/move-in|move-out` because the ENDPOINT is
  // account-scoped. The endpoints have not changed; the conclusion was wrong.
  // Both wizards now ALSO mount standalone (`/move-ins/new`, `/move-outs/new`
  // — verified against `App.tsx`), and each one's FIRST STEP was already the
  // picker the header was said to be missing.
  // ⚠ The label is `customers.accounts.action.moveIn` — the header's own
  // vocabulary, translated in all eleven locales — and NOT the tab's
  // `+ New move-in`, which no catalogue answers. See `tabPrimary`.
  // `CR-171-BRC10` P2.01 — image 01 draws the Move-ins tab's primary as
  // `+ New move-in`, the tab's own catalogued key.
  "move-ins": { label: "+ New move-in", live: true },
  "move-outs": { label: "Move-out", live: true },
  transfers: { label: "+ New transfer", live: true },
  disconnects: { label: "Start a disconnect", live: true },
  // ⛔ **`"waiting-on": { label: "Park a job", live: false }` STOOD HERE FOR ONE
  // DAY AND IS SUPERSEDED — CR-035 · AMENDMENT 1, PO 2026-08-26:** *"seperate
  // queue not reequired"*. The tab is folded into the six worklists, so the one
  // deliberately-not-live primary on this screen is gone with it and **every
  // row below is `live: true` again** — which is the state DEF-729/DEF-730 were
  // filed to reach.
  // ── CR-094-BRC01 WAVE G (2026-09-12) · THE NINTH AND TENTH ─────────────
  // PO ruling: *"in the main tab list, add complaints and services."* Each
  // primary is LIVE in the commit that adds the tab, pointing at a route
  // registered in the same commit — landing a screen and releasing the door
  // that reaches it are one act (`DEF-CWP-3925`).
  complaints: { label: "+ Log a complaint", live: true },
  services: { label: "+ Raise a service", live: true },
  imports: { label: "↑ New import", live: true },
};

describe("DEF-729 / DEF-730 — every Accounts tab offers its create action", () => {
  // ⚠ **AMENDED 2026-09-20 (`DEF-CUS-5939`) — THE TIER MOVED AND THE COUNT DID
  // NOT.** Every assertion below read `data-variant="primary"`, and the tab
  // action is now `ghost`: the Accounts blueprint draws this control four times
  // (p117 `+ New move-out`, p131 `+ New transfer`, p41 `+ Log a complaint`,
  // p48 `+ Request a service`) and every one of them is plain words top right —
  // no fill, no border, no underline. BR-SHL-044's clause (c) says in terms
  // that *"a tab may legitimately have NO header action"*, so the law is a CAP
  // of one and not a requirement of one.
  //
  // ⛔ **THE CASE IS AMENDED, NOT WEAKENED, AND THE SECOND HALF IS NEW.** It
  // still demands exactly ONE tab action carrying the active tab's own words —
  // that is DEF-729/DEF-730's whole subject and it is untouched. What is added
  // is the assertion that NO filled primary survives anywhere in the action
  // row: dropping the old line without replacing it would have let the loud
  // tier come back on any one of the ten tabs with nothing objecting, which is
  // exactly how DEF-730's stale reason survived the night its route landed.
  /**
   * ⚠⚠ **THE TIER REVERSED ON 2026-09-22 AND THIS CASE WAS NOT MOVED WITH IT —
   * `DEF-CUS-6193`, dated with `git log -S 'variant="ghost"' --
   * AccountsListPage.tsx` to commit `74511fa68`, 10:56 that morning.**
   *
   * `DEF-CUS-5939` had made this control `ghost` — the blueprint's quiet text
   * control — and the PO then walked the deployed build and could not SEE the
   * only way to create anything on the page. Item 1 of their report:
   * `+ New request` is the primary tier now, on all ten tabs.
   *
   * **WHAT THIS CASE IS ACTUALLY FOR IS UNCHANGED AND STILL ASSERTED**: EXACTLY
   * ONE header action, and it is the ACTIVE tab's. `PageHeader` renders
   * `active.primaryAction` and nothing else, so B14 rule 4 and `BR-SHL-044`'s
   * *status → secondaries → ONE primary* are honoured by the change rather
   * than strained by it. Only the TIER moved, and the case moves with it —
   * including the negative, which now names `ghost`, so a silent revert to the
   * quiet control goes red here.
   */
  it("B14 rule 4 / BR-SHL-044: each of the TEN tabs renders EXACTLY ONE header action, and it is the ACTIVE tab's", () => {
    for (const tab of ACCOUNTS_TAB_IDS) {
      const actions = headerActions(renderTab(tab));
      // The fix must satisfy at-most-one-action, never bypass it: a second tab
      // action on this page is a failure, not a fix.
      expect(actions.match(/data-variant="primary"/g) ?? []).toHaveLength(1);
      // ⛔ AND THE QUIET TIER IS GONE FROM THE ROW — PO report 2026-09-22 item 1.
      expect(actions).not.toContain('data-variant="ghost"');
      // ⚠ **THE TEXT OF THAT ONE ACTION IS THE ACTIVE TAB'S, READ OFF THE
      // TAG.** An earlier draft asserted `toContain(label)` on the whole action
      // row plus a `not.toContain` loop over the other seven labels — and that
      // loop is unsound, because the Accounts tab legitimately renders
      // `Move-in` / `Move-out` as SECONDARIES beside its own action. Reading
      // the action tag's own text asks the real question and cannot be
      // confused by a neighbouring control.
      const action = /<button[^>]*data-variant="primary"[^>]*>([^<]*)<\/button>/.exec(actions);
      expect(action?.[1]).toBe(EXPECTED[tab].label);
    }
  });

  it("DEF-729: the Requests tab WITH A ROW IN IT still offers `+ New request` — the empty state is not the only way in", () => {
    const html = renderTab("requests", { requests: oneRequest() });
    // The PO's own tab: one row, so the empty state never renders.
    expect(html).toContain("SR-26-0001");
    expect(html).not.toContain("No requests");
    // The way in is the PAGE's primary slot, and it is LIVE.
    const tag = buttonTag(header(html), "+ New request");
    expect(tag).not.toBe("");
    // `primary` since the PO's report of 2026-09-22 item 1 — it was `ghost`
    // under `DEF-CUS-5939` and the PO could not SEE it on the deployed build.
    // What this case is about is that the way in EXISTS when the list is not
    // empty; the tier is the head's, and the case above pins it for all ten
    // tabs.
    expect(tag).toContain('data-variant="primary"');
    // ⚠ `disabled=""`, NOT the substring "disabled": every button in the kit
    // carries `disabled:opacity-45` in its class list, so the loose form is
    // true of a live button and the case could never go red.
    expect(tag).not.toContain('disabled=""');
    // Still ONE header on the page — the embedded list keeps its own
    // suppressed, which is what makes the slot above lawful.
    expect(html.match(/<h1/g) ?? []).toHaveLength(1);
  });

  it("DEF-730: `+ New connect` is LIVE, and the sentence that said the wizard was unbuilt is gone from the product", () => {
    const html = renderTab("new-connects");
    const tag = buttonTag(header(html), "+ New connect");
    expect(tag).not.toBe("");
    expect(tag).not.toContain('disabled=""');
    // ⚠ HARD-WON LAW 1, ASSERTED. `NewConnectWizard` shipped 2026-08-25 at
    // `/connections/new`; the refusal became a falsehood the moment the route
    // landed, and a disabled control with a stale reason reads as DECIDED.
    expect(html).not.toContain("The new-connect wizard is not built yet");
  });

  it("DEF-730: Transfers and Disconnects carry their own live primary", () => {
    for (const tab of ["transfers", "disconnects"] as const) {
      const tag = buttonTag(header(renderTab(tab)), EXPECTED[tab].label);
      expect(tag).not.toBe("");
      expect(tag).not.toContain('disabled=""');
    }
  });

  // ══════════════════════════════════════════════════════════════════════════
  // PO RULING 2026-08-26 — the last two disabled primaries go live
  // ══════════════════════════════════════════════════════════════════════════
  // The case that stood here asserted the OPPOSITE: that `move-ins` and
  // `move-outs` render `disabled=""` carrying the words "one account". It was a
  // correct test of what the product then did, and the PO overruled what the
  // product did — quoting this repository's own justification back at it:
  //
  //   *"Move-in and move-out stay disabled, on purpose: both wizards are built,
  //   but a move-in creates the next occupant of a particular account's unit and
  //   no account is chosen in that header. The live control is on the account's
  //   own page and the button says so. -Enable Move in /move out"*
  //
  // So it is INVERTED rather than deleted. A deleted case would let the sentence
  // and the disabled state come back with nothing objecting — which is precisely
  // how DEF-730's stale reason survived the night its route landed.
  it("PO 2026-08-26: move-in / move-out are LIVE, and the reason that said otherwise is gone from the product", () => {
    for (const tab of ["move-ins", "move-outs"] as const) {
      const head = header(renderTab(tab));
      const tag = buttonTag(head, EXPECTED[tab].label);
      // VISIBLE, not hidden: nobody hunts for a control somebody removed.
      expect(tag).not.toBe("");
      // `primary` since the PO's report of 2026-09-22 item 1 (`DEF-CUS-6193`
      // — dated to `74511fa68`); VISIBLE is what this case guards, and the
      // tier is pinned for all ten tabs by the case at the top of this file.
      expect(tag).toContain('data-variant="primary"');
      // ⚠ `disabled=""`, NOT the substring "disabled" — every button in the kit
      // carries `disabled:opacity-45` in its class list, so the loose form is
      // true of a live button and this case could never go red.
      expect(tag).not.toContain('disabled=""');
      // ⛔ THE OVERRULED SENTENCE, GONE. `customers.accounts.action.moveBlocked`
      // is in all ELEVEN catalogues reading "Move-in and move-out each act on
      // one account, and none is selected here…" — a catalogue entry beats a
      // code default, so the only way that sentence leaves the product is for
      // the screen to stop ASKING for the key. This asserts it stopped.
      expect(head).not.toContain("each act on one account");
      expect(head).not.toContain("none is selected here");
      // ⚠ Both wizards ARE built. A refusal saying otherwise is DEF-730.
      expect(head).not.toContain("is not built yet");
    }
  });

  // ⛔ **`DEF-CUS-10049` — PO ruling 2026-10-11, verbatim: *"this si correct 0
  // fix it"*.** `+ New account` renders, greyed and unpressable, and says why;
  // Move-in and Move-out beside it are untouched and LIVE. A full-access clerk
  // is the fixture, so the role cannot be what disables it.
  it("DEF-CUS-10049: `+ New account` is DISABLED with its reason; Move-in / Move-out stay live", () => {
    const head = header(renderTab("accounts"));
    const tag = buttonTag(head, EXPECTED.accounts.label);
    expect(tag).not.toBe("");
    expect(tag).toContain('disabled=""');
    expect(tag).toContain(`title="${t("customers.accounts.action.newDisabled")}"`);
    for (const label of [
      t("customers.accounts.action.moveIn"),
      t("customers.accounts.action.moveOut"),
    ]) {
      const secondary = buttonTag(head, label);
      expect(secondary).not.toBe("");
      expect(secondary).not.toContain('disabled=""');
    }
  });

  // ⛔ **THE TWO TABS' OWN EMPTY-STATE CTAs ARE NOT ASSERTED HERE, DELIBERATELY,
  // AND THE FIRST DRAFT OF THIS FILE GOT IT WRONG.** A case here reading
  // `expect(renderTab("move-ins")).not.toContain("begins on the unit's own
  // page")` PASSES WHETHER OR NOT THE FIX IS PRESENT — this harness seeds no
  // list, so the tab's query is pending, the empty state never renders, and the
  // sentence is absent for the wrong reason. It was proved against the
  // unfixed code and stayed green. A check whose output cannot distinguish pass
  // from fail is worse than no check, because it is trusted (DEF-182).
  // The real cases live where the empty list can be seeded:
  // `MoveInsTab.test.tsx` and `MoveOutsTab.test.tsx`, one each.
});

describe("DEF-729 — the embedded Requests list keeps its own header suppressed", () => {
  it("the standalone route owns the header and the primary; the embedded copy owns neither", () => {
    const standalone = renderToStaticMarkup(
      <QueryClientProvider
        client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
      >
        <MemoryRouter initialEntries={[`/${TEST_TENANT}/requests`]}>
          <ServiceRequestsListPage />
        </MemoryRouter>
      </QueryClientProvider>,
    );
    expect(standalone).toContain("+ New request");
    expect(standalone.match(/<h1/g) ?? []).toHaveLength(1);

    const embedded = renderToStaticMarkup(
      <QueryClientProvider
        client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
      >
        <MemoryRouter initialEntries={[`/${TEST_TENANT}/accounts?tab=requests`]}>
          <ServiceRequestsListPage urlState={false} />
        </MemoryRouter>
      </QueryClientProvider>,
    );
    expect(embedded).not.toContain("<h1");
    expect(embedded).toContain('data-embedded=""');
  });
});
