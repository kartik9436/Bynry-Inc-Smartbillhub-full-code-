// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:  CR-035 · AMENDMENT 1 — the Waiting-on TAB folds into the six
//          worklists. PO 2026-08-26: *"We dont need seperate tab for this -
//          this will be directly on each request Request, Connect, Move IN move
//          Out, Trasnfr, Disconnect - seperate queue not reequired"*, "yyes".
// Rules:   BR-SHL-048 (a parked wizard changes nothing — and a WORKLIST is not
//          the unit, the premises or the account, which is what makes this
//          placement lawful) · BR-SHL-046 (ONE declared step list) ·
//          BR-SHL-034 (one date formatter) · B14 rule 15 (icons for row
//          actions) · rule 6 (danger tier) · hard-won law 2 (built is not
//          wired) · law 6 (assert RENDERED OUTPUT, not props)
// ───────────────────────────────────────────────────────
//
// ⚠⚠ **AMENDED 2026-09-20 — THE PANEL IS GONE AND THE DRAFT IS A ROW
// (`DEF-CUS-5994`).** PO, verbatim: *"remove it - it is anyway in the list so
// we dont need it sepretely - if it is not in list add it"*. Every list unions
// `wizard_parks` for its own flow now, so a draft is a row with a real step,
// ordered and paged by the DATABASE alongside the records.
//
// ⚠ **THE AMENDMENT'S TWO REQUIREMENTS DID NOT MOVE WITH THE SURFACE, AND THIS
// FILE STILL EXISTS TO ASSERT THEM. BOTH ARE ABOUT NOT LYING TO A CLERK.**
//
//   1. **A DRAFT MUST BE UNMISTAKABLY A DRAFT.** It wears a `Draft` or
//      `Parked` badge in the STATE cell — read off the DOM, not off a prop,
//      because a prop that nothing renders is the exact defect hard-won law 2
//      was written for.
//   2. **THE COUNT MUST NOT LIE.** This one INVERTED and the requirement did
//      not: the panel kept drafts OUT of `total` because they were not rows.
//      They are rows now, so `total` must COUNT them — and it must be the
//      SERVER's figure over the whole window, never a client-side splice into
//      a server-paged list. The case asserts the screen prints what the server
//      sent rather than a sum computed in two places.
//
// ⚠ **AND ONE ASSERTION THAT ONLY MATTERS BECAUSE A SURFACE WAS REMOVED:
// DISCARD STILL EXISTS.** It lived on the panel and NOWHERE else — the
// Move-outs row had a Resume and no way to throw a draft away — so deleting
// the panel without re-homing it would have removed a live capability with
// nothing to notice (`DEF-CUS-3653`: an absence is invisible to every check
// this repo has). That is the trap in every *"remove the surface"* ruling.
//
// ⚠ **AND ONE NEGATIVE, CARRIED OVER FROM THE TAB IT REPLACES.** BR-SHL-048 (a):
// *"no report, ageing bucket or occupancy query can reach a parked draft by
// joining to it."* A frontend lookup off `subject_ref` is that join with extra
// steps and it is invisible to every other check in this repo — the panel would
// render beautifully. So the request log is asserted, not just the DOM.
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { RouterProvider, createMemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import { APP_ROUTES } from "@/App";
import { queryKeys } from "@/api/queryClient";
import { shellBootSeed } from "@/components/shellBootSeed";
import { defaultRequestState } from "@/components/tableTypes";
import { ToastProvider } from "@/components/Toast";

import { ACCOUNTS_TAB_IDS } from "./AccountsListPage";
import { moveInsQueryKey, moveInsTableConfig } from "./MoveInsTab";
import { ACCOUNTS_PERMISSION } from "./customersShared";
import { resumePath, stepOf, waitingOnLabel } from "./parkedDrafts";
import { PARKED_HOME_PATHS } from "./wizardPark";
import type { WizardParkRow } from "./wizardParkEndpoints";
import { SEEDED_REGIONAL } from "@/components/tenantRegionalFixture";

afterEach(cleanup);

const TEST_TENANT = "brazosbend";

function permissions() {
  return {
    role: "billing_clerk",
    role_name: "Billing Clerk",
    permissions: [{ code: ACCOUNTS_PERMISSION, label: "Premises / Accounts", access: "Full" }],
  };
}

/** BR-SHL-048's own worked case, as the store would serve it back. */
function row(over: Partial<WizardParkRow> = {}): WizardParkRow {
  return {
    id: "park-1",
    flow: "move_in",
    subject_label: "500 Main St · Unit 12",
    subject_ref: { unit_id: "u-12", account_id: null },
    step: 3,
    values: { unit_id: "u-12" },
    waiting_on: "deposit",
    park_note: "Waiting on the $150 deposit.",
    remind_on: "2026-09-02",
    parked_at: "2026-08-26T09:00:00Z",
    parked_by: "user-1",
    parked_by_name: "A. Clerk",
    age_days: 7,
    ...over,
  };
}

// ══════════════════════════════════════════════════════════════════════════
// 1 · THE PURE PIECES — BR-SHL-046, provable without a browser
//     Carried over from `WaitingOnTab.dom.test.tsx` with the functions
//     themselves: they are the contract that stops a `3 of 9` here disagreeing
//     with a `3 of 9` in the wizard, and the fold did not touch it.
// ══════════════════════════════════════════════════════════════════════════

describe("stepOf — the STEP line reads the FLOW'S OWN declared list", () => {
  it("counts a move-in against FOUR and a new connect against FIVE", () => {
    // ⚠ **FOUR SINCE 2026-10-05** — `CR-171-BRC10` P2.15. A draft the seven-
    // step form wrote is read through `moveInStoredStep` (old 3 · Customer →
    // 2 · Customer); one the four-step form wrote carries `step_shape: "four"`
    // and is read as it stands. `DEF-CUS-9703` was this cell and the wizard
    // disagreeing.
    // ⚠ **SEVEN SINCE 2026-09-26** — `b8b560587`, `BR-CUS-1101` (PO: an account
    // takes a SUBSET of its unit's services), *Which services* at step 2.
    // `DEF-CUS-9107`: this read SIX for six days after the list grew.
    // ⚠ **SIX SINCE 2026-09-12** — `CR-094-BRC01` wave H, PO ruling: the
    // *Plan & deposit* step became *Account preferences* and a *Deposit* step
    // was inserted before Review. This case is the CONTRACT that stops a
    // `3 of 6` here disagreeing with the wizard's own rail, so the number
    // moving with the list is the check working, not a test to loosen.
    expect(stepOf(row({ flow: "move_in", step: 3 }))).toEqual({ step: 2, of: 4 });
    expect(stepOf(row({ flow: "move_in", step: 5 }))).toEqual({ step: 3, of: 4 });
    expect(
      stepOf(row({ flow: "move_in", step: 3, values: { step_shape: "four" } })),
    ).toEqual({ step: 3, of: 4 });
    // ⚠ **EIGHT SINCE 2026-09-16** — `DEF-CUS-5186`, the blueprint's own merge
    // of *owner* and *scope* into one step. This line is why the waiting list
    // and the wizard's rail cannot disagree: it reads the SAME declared list.
    //
    // ⚠ **AND A DRAFT PARKED BEFORE THAT MERGE PRINTS ONE STEP LATE HERE.**
    // Its stored `step` was a nine-step number and nothing versions it, so an
    // old row parked on *Map services* (then 5) reads `Step 5 of 8`, which is
    // now Plans. It is a LABEL on a waiting list, not a destination: resuming
    // goes through `resumePath`, which carries `?parked=<id>` and no `?step=`,
    // so the draft reopens at step 1 with everything typed hydrated whole.
    //
    // ⚠ **FIVE SINCE 2026-09-29** — `ed4e7cb30`, `CR-150-BRC09` (the PO's own
    // drawings, *"we need 1 word - for every step"*). A row parked on the old
    // EIGHT is REMAPPED by `NEW_CONNECT_STORED_STEP`: old 3 stays 3, old 6 ·
    // *Charges* reads 4 · *Charges*, never 6 of 5. `DEF-CUS-9107`.
    expect(stepOf(row({ flow: "new_connect", step: 3 }))).toEqual({ step: 3, of: 5 });
    expect(stepOf(row({ flow: "new_connect", step: 6 }))).toEqual({ step: 4, of: 5 });
    // The clamp still keeps an older nine-step row honest: old 9 reads 5 of 5.
    expect(stepOf(row({ flow: "new_connect", step: 9 }))).toEqual({ step: 5, of: 5 });
    expect(stepOf(row({ flow: "transfer", step: 5 }))).toEqual({ step: 5, of: 5 });
  });

  it("BR-SHL-046: the STEP line counts the flow's whole list — move-out counts to FOUR", () => {
    // ⚠ FOUR since `e45a8e034` (2026-09-24, `DEF-CUS-6537`, PO: ACC-06 is four
    // steps). A row parked on the OLD six-step shape is REMAPPED, never
    // clamped (`MOVE_OUT_STORED_STEP`): old 5 · *What happens next* reopens on
    // 4 · *Review & close*, and old 4 · *The shortfall* on 3 · *Bill &
    // deposit*, never one step too far. `DEF-CUS-9107`.
    expect(stepOf(row({ flow: "move_out", step: 5 }))).toEqual({ step: 4, of: 4 });
    expect(stepOf(row({ flow: "move_out", step: 4 }))).toEqual({ step: 3, of: 4 });
  });

  it("clamps a step the flow no longer has, rather than erroring (BR-SHL-011)", () => {
    expect(stepOf(row({ flow: "transfer", step: 42 }))).toEqual({ step: 5, of: 5 });
  });
});

describe("resumePath — one handle, and it is the flow's OWN wizard", () => {
  it("points each flow at its own route with `?parked=`", () => {
    expect(resumePath(row({ flow: "move_in", id: "p1" }))).toBe("/move-ins/new?parked=p1");
    expect(resumePath(row({ flow: "move_out", id: "p2" }))).toBe("/move-outs/new?parked=p2");
    expect(resumePath(row({ flow: "transfer", id: "p3" }))).toBe("/transfers/new?parked=p3");
    expect(resumePath(row({ flow: "disconnect", id: "p4" }))).toBe("/disconnects/new?parked=p4");
    expect(resumePath(row({ flow: "new_connect", id: "p5" }))).toBe("/connections/new?parked=p5");
  });
});

describe("waitingOnLabel — the nine, in the park panel's own vocabulary", () => {
  it("reads B18 §4.2's closed list rather than restating it", () => {
    const t = (_key: string, params?: Record<string, unknown>) =>
      String(params?.defaultValue ?? "");
    expect(waitingOnLabel("deposit", t)).toBe("waiting on a deposit");
    expect(waitingOnLabel("site_access", t)).toBe("waiting on site access");
    expect(waitingOnLabel("something_else", t)).toBe("something_else");
  });
});

// ══════════════════════════════════════════════════════════════════════════
// 2 · THE FOLD — every parked draft lands on the tab for its OWN work
// ══════════════════════════════════════════════════════════════════════════

// ══════════════════════════════════════════════════════════════════════════
// 5 · WIRED, NOT MERELY BUILT — and REQUIREMENT 2, THE COUNT
// ══════════════════════════════════════════════════════════════════════════
//
// ⚠ **THESE GO THROUGH `APP_ROUTES` AND SEED THE QUERY CACHE**, which is the
// technique `MoveEntryPoints.dom.test.tsx` established and its reason applies
// here unchanged: `createApiClient` captures `fetch` at module load, so the
// real transport is not reachable under jsdom and a screen that refetched would
// render a load-failed strip beside the data it already had. `staleTime:
// Infinity` makes the seeded answers the only answers.

/** A `MoveInList` with `n` rows and a TOTAL of `n` — the figure requirement 2
 *  is about. Only the fields these two cases read are filled; the rest are the
 *  server's own "cannot say" shapes, which is what `MoveInsTab` draws anyway. */
function moveInList(n: number) {
  const absence = { code: "MOVE_IN_STEP_UNAVAILABLE", br_ref: "BR-CUS-018", detail: "no case table" };
  return {
    rows: Array.from({ length: n }, (_unused, i) => ({
      account_id: `acc-${i + 1}`,
      account_no: `A-1204${i + 1}`,
      customer: `Occupant ${i + 1}`,
      customer_no: `C-0081${i + 1}`,
      customer_source: "customer_entity",
      customer_absence: null,
      unit_id: `u-${i + 1}`,
      unit: `88 Pine Vista · ${i + 1}`,
      move_in_date: "2026-09-01",
      move_in_date_absence: null,
      step: { reached: null, of: 4, unavailable: null, done: true },
      reads: { state: null, unavailable: absence },
      // `CR-171-BRC10` §9.LIST — a committed move-in.
      status: "completed",
      reference: `MVI-26-00${i + 10}`,
      action: "view",
      services: ["water"],
      opening_read: null,
      deposit: {
        currency: "USD",
        amount: { stored: "150.0000", display: "150.00" },
        recorded: true,
        sentence: null,
        unavailable: [absence],
      },
      state: "scheduled",
      starting_this_week: false,
      booked_in_on: "2026-08-23",
      age_days: 2,
      request: null,
      request_absence: null,
    })),
    kpis: {
      open: n,
      starting_this_week: 0,
      waiting_on: { count: 0, drawn_as: "WAITING ON DOCUMENTS", unavailable: [] },
      deposits_to_carry_over: null,
      deposits_to_carry_over_unavailable: absence,
      oldest: null,
      period_basis: "calendar",
      as_of: "2026-08-26T09:00:00Z",
    },
    page: 1,
    per: 25,
    total: n,
    pages: 1,
    columns: [],
    states: [],
    search: { hint: "", min_chars: 2, legs: [], unavailable: [] },
    exclusion: { callout: "", contract: [], half_account_ids: [] },
    unavailable: [],
    as_of: "2026-08-26T09:00:00Z",
  };
}

function mountAccounts(entry: string, seed: (client: QueryClient) => void = () => undefined) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: Infinity } },
  });
  // DEF-SHL-3964 — this mounts the REAL shell, and the shell now renders no
  // routed screen until it knows the tenant's date format and time zone. A
  // test that mounts the product says which tenant it is testing.
  // DEF-SHL-4272 — the shell boots on `GET /shell/display` (every signed-in
  // role), not on the two Admin/Executive settings reads. Without this seed
  // the shell holds and every address renders a loading skeleton.
  client.setQueryData(queryKeys.shellDisplay, shellBootSeed(SEEDED_REGIONAL));
  client.setQueryData(queryKeys.regionalSettings, SEEDED_REGIONAL);
  client.setQueryData(queryKeys.myPermissions, permissions());
  seed(client);
  const router = createMemoryRouter(APP_ROUTES, { initialEntries: [entry] });
  render(
    <QueryClientProvider client={client}>
      <ToastProvider>
        <RouterProvider router={router} />
      </ToastProvider>
    </QueryClientProvider>,
  );
  return router;
}

/**
 * The move-ins list key.
 *
 * ⚠ **BUILT BY `moveInsQueryKey` ITSELF, AND IT WAS HAND-COPIED UNTIL CR-045
 * WAVE G.** It read `["move-ins", "", 1, DEFAULT_PAGE_SIZE]` — the right shape
 * on the day it was written and a SILENT break the day the key grew a fifth
 * member (`state.filters`, `DEF-1702`). The seeded payload then matched no
 * query, so the tab rendered EMPTY and this case failed on
 * `Unable to find an element with the text: Occupant 3` — a failure that says
 * nothing about parked drafts, which is what this file is for. A key copied by
 * hand is a second implementation of the thing it is testing around.
 */
const MOVE_INS_KEY = moveInsQueryKey(
  defaultRequestState(
    moveInsTableConfig(
      (key: string, params?: Record<string, unknown>) =>
        String((params as { defaultValue?: string } | undefined)?.defaultValue ?? key),
      {
        // Stubs — the real cells are routed and the KEY needs none of them.
        reference: () => <span />,
        moveInDate: () => <span />,
        action: () => <span />,
      },
    ),
  ),
);

/** A parked MOVE-IN as the LIST now serves it — one row of `move_ins_list`.
 *
 *  ⚠ **THE SHAPE IS THE RECORD ROW'S, WITH A NAMED ABSENCE IN EVERY CELL A
 *  DRAFT CANNOT ANSWER.** That is `move_in_park_row`'s whole posture and the
 *  reason the old objection fell: a row that simply OMITTED a cell would render
 *  blank, and a blank cell and an absent fact are indistinguishable once drawn
 *  (`DEF-127`). The fixture is built from the server's real keys so a change on
 *  either side shows up here rather than in production. */
function parkedMoveInRow(over: Record<string, unknown> = {}) {
  const absence = { code: "x", br_ref: "BR-SHL-048", detail: "d" };
  return {
    move_no: "MVI-26-0119",
    move_no_unavailable: null,
    row_kind: "parked_move_in",
    park_id: "park-1",
    job_id: null,
    account_id: null,
    account_no: null,
    account_absence: { ...absence, code: "parked_move_in_has_no_account_yet" },
    customer: null,
    customer_no: null,
    customer_source: null,
    customer_absence: { ...absence, code: "parked_move_in_customer_is_still_being_typed" },
    unit_id: "u-12",
    unit: "500 Main St · Unit 12",
    move_in_date: "2026-09-30",
    move_in_date_absence: null,
    // ✅ THE REAL STEP — the half of this ruling that is an IMPROVEMENT rather
    // than a move. `MoveStepBar`'s docstring is explicit that `reached` is the
    // SERVER's answer and the component never derives one.
    step: { reached: 3, of: 4, id: "billing", name: "Billing", unavailable: null },
    reads: { state: null, unavailable: absence },
    // `CR-171-BRC10` §9.LIST — the redesigned list's keys.
    status: "draft",
    reference: "MVI-26-0119",
    action: "resume",
    services: null,
    opening_read: null,
    deposit: {
      currency: null,
      amount: null,
      recorded: false,
      sentence: null,
      unavailable: [absence],
    },
    state: "parked",
    starting_this_week: false,
    booked_in_on: "2026-08-26",
    age_days: 7,
    request: null,
    request_absence: absence,
    documents_outstanding: null,
    waiting_on: "deposit",
    park_note: "Waiting on the $150 deposit.",
    remind_on: "2026-09-02",
    parked_at: "2026-08-26T09:00:00Z",
    parked_by_name: "A. Clerk",
    ...over,
  };
}

/** `moveInList(n)` with a parked draft as the FIRST row and `total` counting
 *  it — which is what the server does now (`_move_in_page_keys` unions three
 *  arms and `total` is the union's own `COUNT(*)`). */
function moveInListWithDraft(records: number) {
  const base = moveInList(records);
  return {
    ...base,
    rows: [parkedMoveInRow(), ...base.rows],
    total: records + 1,
  };
}

// ══════════════════════════════════════════════════════════════════════════
// 5 · THE PANEL IS GONE FROM ALL FIVE TABS — `DEF-CUS-5994`
// ══════════════════════════════════════════════════════════════════════════
//
// ⚠ **THIS IS THE ASSERTION THAT WOULD HAVE CAUGHT THE DEFECT ITSELF, AND IT
// IS WRITTEN AS AN ABSENCE ON PURPOSE.** Nothing in this repo asks whether two
// surfaces state the same fact; the Move-outs list unioned `wizard_parks` on
// 2026-09-19 and the panel above it became pure duplication in the same
// commit, with every check green. A person looking at the screen found it
// (hard-won law 6). What a test CAN do is refuse the panel's return.
describe("`DEF-CUS-5994` — no tab draws a parked-drafts panel any more", () => {
  const TABS = [
    "new-connects",
    "move-ins",
    "move-outs",
    "transfers",
    "disconnects",
  ] as const;

  for (const tab of TABS) {
    it(`\`?tab=${tab}\` renders no panel above the list`, async () => {
      mountAccounts(`/${TEST_TENANT}/accounts?tab=${tab}`);
      await screen.findAllByRole("tab");
      // The panel's own marker, on the element it rendered as. A `querySelector`
      // rather than a testing-library query because the assertion is that
      // NOTHING matches, and `getBy*` cannot express that without throwing.
      expect(document.body.querySelector("[data-parked-drafts]")).toBeNull();
      // …and its rows' marker, which is the thing a clerk actually saw.
      expect(document.body.querySelector("[data-parked-draft]")).toBeNull();
    });
  }
});

// ══════════════════════════════════════════════════════════════════════════
// 6 · A DRAFT IS A ROW OF ITS OWN FLOW'S LIST — the PO's other half
// ══════════════════════════════════════════════════════════════════════════
//
// PO, verbatim: *"if it is not in list add it"*.
//
// ⚠ **MOUNTED UNDER THE REAL `/:tenant/accounts` PATTERN.** A bare
// `MemoryRouter` with no such route leaves `useParams().tenant` undefined and
// every address the page builds comes out `//portal/…` — a protocol-relative
// URL to another host, which reads as a perfectly good string to `toContain`.
// That is the fixture trap hard-won law 2 records, and it is why the resume
// href below is read out of the DOM and compared to a WHOLE path.
describe("`DEF-CUS-5994` — the draft is a row of the Move-ins list (redrawn by `CR-171-BRC10` P2.02)", () => {
  // ⚠ **REWRITTEN 2026-10-05 FOR THE REDESIGNED LIST (images 01–02).** The
  // draft is still a ROW — that ruling stands — and it now wears image 01's
  // one pill, `Draft · 7 days`, its four-step cell and ONE icon, Resume.
  // **Discard left the row and lives on the draft's details view** (image 12,
  // `moveRecordActions`' `discardDraft`), which is where image 01 puts it: one
  // icon per row. The why-line, the reminder and `Parked by` are not drawn on
  // the list any more; they are the draft's own facts on its details view.
  it("sits IN the table with its pill and the step it reached", async () => {
    mountAccounts(`/${TEST_TENANT}/accounts?tab=move-ins`, (client) => {
      client.setQueryData(MOVE_INS_KEY, moveInListWithDraft(3));
    });
    const tab = await screen.findByRole("tab", { name: "Move-ins" });
    expect(tab).toHaveAttribute("aria-selected", "true");
    // Re-queried inside `waitFor`: a held handle to a React node is a snapshot.
    await waitFor(() => {
      const pill = screen.getByText("Draft · 7 days");
      expect(pill.closest("table")).not.toBeNull();
    });
    const step = document.body.querySelector('[data-step-progress="3/4"]');
    expect(step?.textContent).toBe("3 of 4 · Billing");
  });

  it("RESUME is the row's one icon, onto this flow's own wizard, at this tenant's path", async () => {
    mountAccounts(`/${TEST_TENANT}/accounts?tab=move-ins`, (client) => {
      client.setQueryData(MOVE_INS_KEY, moveInListWithDraft(1));
    });
    const resume = await screen.findByRole("link", { name: "Resume MVI-26-0119" });
    // ⚠ **THE WHOLE PATH, NOT A FRAGMENT.** `toContain("/move-ins/new")` passes
    // on `//move-ins/new`, which is what a bare `MemoryRouter` produces.
    expect(resume.getAttribute("href")).toBe(`/${TEST_TENANT}/move-ins/new?parked=park-1`);
    // One icon per row (image 01): no Discard beside it.
    expect(screen.queryByRole("button", { name: "Discard" })).toBeNull();
  });

  it("the draft's REFERENCE opens its details view, where Discard lives", async () => {
    mountAccounts(`/${TEST_TENANT}/accounts?tab=move-ins`, (client) => {
      client.setQueryData(MOVE_INS_KEY, moveInListWithDraft(1));
    });
    const reference = await screen.findByRole("link", { name: "MVI-26-0119" });
    expect(reference.getAttribute("href")).toBe(`/${TEST_TENANT}/moves/MVI-26-0119`);
  });

  it("requirement 2 — THE COUNT DOES NOT LIE: the server's total, one window", async () => {
    mountAccounts(`/${TEST_TENANT}/accounts?tab=move-ins`, (client) => {
      client.setQueryData(MOVE_INS_KEY, moveInListWithDraft(3));
    });
    await screen.findByText("Draft · 7 days");
    // The pager's own element, whole string — `/\b4\b/` over the page also
    // matched the app version once (`DEF-CUS-6195`).
    const pager = document.body.querySelector(".table-pager-range");
    expect(pager?.textContent?.trim()).toBe("1–4 of 4");
    expect(document.body.querySelectorAll("table tbody tr").length).toBe(4);
  });
});

// ══════════════════════════════════════════════════════════════════════════
// 7 · THE NINTH TAB IS STILL GONE — carried over unchanged
// ══════════════════════════════════════════════════════════════════════════
describe("hard-won law 2 — the ninth tab is gone and stays gone", () => {
  it("no `Waiting on` tab, and `?tab=waiting-on` falls back to Accounts", async () => {
    mountAccounts(`/${TEST_TENANT}/accounts?tab=waiting-on`);
    // The strip is back to B18 §4's EIGHT.
    const tabs = await screen.findAllByRole("tab");
    expect(tabs).toHaveLength(ACCOUNTS_TAB_IDS.length);
    expect(ACCOUNTS_TAB_IDS as readonly string[]).not.toContain("waiting-on");
    expect(screen.queryByRole("tab", { name: "Waiting on" })).toBeNull();
    // An unknown `?tab=` has always fallen back to Accounts
    // (`accountsTabFromParam`), so a stale bookmark lands somewhere real
    // instead of on a blank tab body.
    expect(screen.getByRole("tab", { name: /^Accounts/ })).toHaveAttribute(
      "aria-selected",
      "true",
    );
  });

  it("`PARKED_HOME_PATHS` names five REAL tabs — a renamed tab fails here", () => {
    for (const path of Object.values(PARKED_HOME_PATHS)) {
      const tab = new URL(path, "http://t").searchParams.get("tab");
      expect(ACCOUNTS_TAB_IDS as readonly string[]).toContain(tab);
    }
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// screens: S17
// packet: `DEF-CUS-5994` (PO 2026-09-20) · CR-035 · AMENDMENT 1 (PO
//         2026-08-26) · US-CUS-031 · BR-SHL-048 · BR-SHL-046 · B14 rules 6,
//         15, 33
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
