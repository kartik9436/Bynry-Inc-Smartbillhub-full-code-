// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:  PO ruling 2026-08-26, verbatim — the PO quoted this repository's own
//          justification back at it and overruled it:
//            *"Move-in and move-out stay disabled, on purpose: both wizards are
//            built, but a move-in creates the next occupant of a particular
//            account's unit and no account is chosen in that header. The live
//            control is on the account's own page and the button says so.
//            -Enable Move in /move out"*
// Screens: S19 (`/move-ins/new`) · S20 (`/move-outs/new`) · S17 (the Accounts
//          header that opens them)
// Rules:   BR-CUS-020 (only VACANT units are offered, and only the server
//          decides) · BR-CUS-017 (at most ONE active account per unit) ·
//          BR-CUS-056 (the OUTGOING account pays the move day; the incoming
//          one starts the day AFTER) · BR-CUS-053 (ONE box finds an account) ·
//          BR-SHL-046 (the rail and the `Step n of N` line come from ONE
//          declared step list) · BR-SHL-025 (a control that cannot act is
//          disabled WITH its reason — and one that CAN act is not) ·
//          B14 rule 4 / BR-SHL-044 (exactly one primary per screen) ·
//          hard-won law 1 (a stated reason has to change with the fact) ·
//          hard-won law 2 (built is not wired)
// ───────────────────────────────────────────────────────
//
// ⚠ **WHAT WAS MISSING WAS NEVER THE WIZARD.** Both have been built and routed
// since 2026-08-11, and `MOVE_OUT_STEPS[0]` has been `Find account` and
// `MOVE_IN_STEPS[0]` `Unit` the whole time. What was missing was an ENTRY POINT:
// a URL with nothing in it, so that the first step asks instead of confirms.
//
// ⚠ **THE MOVE-IN ASKS FOR A UNIT AND THE MOVE-OUT ASKS FOR AN ACCOUNT, AND
// THAT ASYMMETRY IS THE PO'S OWN SENTENCE.** A move-out closes ONE NAMED
// ACCOUNT. A move-in *"creates the next occupant of a particular account's
// unit"* — so the unit is the question a clerk can answer, and the outgoing
// account is DERIVED from it by the server's own rule
// (`selectors.last_closed_account_for_unit`, mirrored in
// `moveShared.lastClosedAccountForUnit`).
//
// ⚠ **AND THE DERIVATION HAS A HONEST DEAD END, WHICH IS ASSERTED RATHER THAN
// PAPERED OVER.** A vacant unit with no finished tenancy has no closing account
// for a move-in to succeed, and `apps/customers/api.py` says so in as many
// words: *"the STANDALONE S19 entry … has no path of its own. It is served by
// `POST /accounts` with an occupying status."* The step says that and links to
// S18. No endpoint is invented, here or anywhere in this change.
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { RouterProvider, createMemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import { APP_ROUTES } from "@/App";
import type {
  AccountDetail,
  AccountRow,
  AccountsPage,
  MyPermissions,
  Paginated,
  UnitRow,
} from "@/api/endpoints";
import { moveInMoneyKeys } from "@/api/moveInMoneyEndpoints";
import { queryKeys } from "@/api/queryClient";
import { shellBootSeed } from "@/components/shellBootSeed";
import { ToastProvider } from "@/components/Toast";

import { accountDetailQueryKey } from "./AccountDetailPage";
import type { MoveInUnitRow } from "./moveInWizard/moveInUnitSearch";
import { unitAssetsQueryKey } from "./UnitAssetsPanel";
import { ACCOUNTS_PERMISSION } from "./customersShared";
import {
  MOVE_IN_WIZARD_ROUTE,
  MOVE_OUT_WIZARD_ROUTE,
  lastClosedAccountForUnit,
} from "./moveShared";
import { SEEDED_REGIONAL } from "@/components/tenantRegionalFixture";

const TEST_TENANT = "brazosbend";

afterEach(cleanup);

// ── Fixtures ───────────────────────────────────────────────────────────────

function permissions(access = "Full"): MyPermissions {
  return {
    role: "billing_clerk",
    role_name: "Billing Clerk",
    permissions: [{ code: ACCOUNTS_PERMISSION, label: "Premises / Accounts", access }],
  };
}

function unit(over: Partial<UnitRow> = {}): UnitRow {
  return {
    id: "u-10432a",
    unit_no: "U-10432-A",
    premises_id: "p-10432",
    premise_no: "P-10432",
    premise_address: "1408 Elm St",
    label: "Unit A",
    unit_type: "residential",
    floor_label: null,
    square_feet: null,
    rate_plan_id: null,
    plan_effective_from: null,
    plan_locked: false,
    vacant_standby_auto: false,
    is_common_area: false,
    // CR-089 wave A · BR-MET-1162 — a unit's own point. `null` is the state
    // all 1,109 units are in today, and `point.source: "premises"` is the
    // ruled fallback: this unit reads its building's.
    lat: null,
    lng: null,
    point: { lat: null, lng: null, source: "premises" as const },
    active: true,
    services: ["electric", "water"],
    meters: [],
    // BR-MET-036 — DERIVED. Every row this picker sees is vacant, because the
    // SERVER was asked for vacant ones.
    occupancy: "vacant",
    occupant: null,
    account_no: null,
    status: "vacant",
    // DEF-755 — *what is METERED here*, now under its own name. `services`
    // above is what the unit's PREMISES offers; the two answer different
    // questions and no longer share a word.
    metered_services: [],
    sub_metered: false,
    ...over,
  };
}

function units(rows: UnitRow[]): Paginated<UnitRow> {
  return { count: rows.length, next: null, previous: null, results: rows };
}

/** `DEF-CUS-10190` — what `GET /move-ins/units` answers for these units, at
 *  the wizard's own query key (empty term, page 1): each VACANT, `move_in`. */
function searchRows(rows: UnitRow[]): Paginated<MoveInUnitRow> {
  return {
    count: rows.length,
    next: null,
    previous: null,
    results: rows.map((u) => ({
      id: u.id,
      unit_no: u.unit_no,
      label: u.label,
      premise_no: u.premise_no,
      premise_name: null,
      address: { line1: u.premise_address, city: null, state: null, postal_code: null },
      meters: [],
      state: "vacant" as const,
      occupant: null,
      selectable: true,
      path: "move_in" as const,
      reason_key: null,
    })),
  };
}

/** The row's *Use* button, by the unit NUMBER it carries (never an id on screen). */
function useButton(unitNo: string): HTMLElement {
  const found = document.querySelector<HTMLElement>(`[data-move-in-unit-use="${unitNo}"]`);
  if (found === null) throw new Error(`no Use button for ${unitNo}`);
  return found;
}

function row(over: Partial<AccountRow> = {}): AccountRow {
  return {
    id: "acc-10432",
    account_no: "A-10432",
    customer_no: "C-00417",
    kind: "regular",
    name: "Miller, Sarah",
    unit_id: "u-10432a",
    unit_label: "A",
    premise: "1408 Elm St · A",
    services: ["electric", "water"],
    balance: "0.000000",
    balance_currency: "USD",
    balance_basis: "posting",
    balance_source: "ledger",
    balance_unavailable: [],
    // BR-CUS-510 / DEF-628 — the DEFAULT is `false`: this fixture's zero,
    // wherever it has one, is a real answer about money owed.
    balance_not_yet_billable: false,
    balance_cached: "0.000000",
    currency: "USD",
    status: "closed",
    status_name: "Closed",
    status_behavior_class: "terminal",
    account_type: "residential",
    account_subtype: null,
    autopay: false,
    opened_at: "2024-02-14",
    closed_at: "2026-08-14",
    last_bill_at: null,
    aging: null,
    ...over,
  };
}

function accountsPage(rows: AccountRow[]): AccountsPage {
  return {
    count: rows.length,
    next: null,
    previous: null,
    results: rows,
    rollup: {
      accounts: rows.length,
      outstanding: "0.000000",
      currency: "USD",
      outstanding_basis: "posting",
      outstanding_unavailable: [],
      past_due_60_plus: null,
      // PO ruling 2026-09-28 — the Accounts strip's four status tiles read
      // `rollup.by_status`. This suite is about the MOVE entry points and
      // asserts nothing about the strip; the field is here because the
      // envelope now carries it, and an empty list is the honest fixture for a
      // tenant this test never seeds statuses into (every tile then draws a
      // dash and none of them presses, which is exactly what should happen).
      by_status: [],
    },
  };
}

function detail(over: Partial<AccountDetail> = {}): AccountDetail {
  return {
    ...row(),
    deposit_on_file: "150.000000",
    deposit_received_on: "2024-02-14",
    credit_tier: null,
    tax_exempt: false,
    tax_exempt_ref: null,
    tax_exempt_expires: null,
    bad_address: false,
    nsf_count: 0,
    preferred_language: null,
    custom_data: {},
    contacts: [
      {
        id: "c-1",
        full_name: "Miller, Sarah",
        email: null,
        phone: null,
        dob: null,
        gov_id_last4: null,
        is_primary: true,
      },
    ],
    addresses: [],
    service_agreements: [],
    meters: [],
    plan: null,
    plan_snapshot_unavailable: "BR-CUS-029",
    // DEF-2419 — the plan the UNIT stands on. Null here: these fixtures are
    // about a flow, not about the plan cell, and null is a real state
    // (a unit with no plan) rather than a placeholder.
    unit_plan: null,
    customer: null,
    ...over,
  };
}

/**
 * Mount THE APPLICATION'S OWN ROUTE TABLE at a URL.
 *
 * ⚠ **HARD-WON LAW 2, AND IT IS WHY EVERY CASE BELOW GOES THROUGH `APP_ROUTES`
 * RATHER THAN A `MemoryRouter` THIS FILE BUILT.** A wizard that renders
 * perfectly in a test its own file routed to is exactly the shape law 2 warns
 * about. Delete either route line in `App.tsx` and these go red on "there is
 * nothing at this address", which is the failure the PO actually met.
 */
/** `CR-171-BRC10` P2.18 (lane MVI-WIZ-UNIT) — step 1's unit card reads
 *  `GET /units/{id}/move-in-facts`; this is that answer, at the key the step
 *  asks for. `previous` names the tenancy the move-in follows. */
function unitFacts(
  unitId: string,
  previous: { account_no: string; name: string; closed_at: string } | null,
): Record<string, unknown> {
  return {
    unit: {
      id: unitId,
      unit_no: unitId === "u-new" ? "U-NEW" : "U-10432-A",
      label: "A",
      unit_type: "residential",
      floor_label: null,
      square_feet: null,
      is_common_area: false,
      occupancy: "vacant",
      address: { line1: "1408 Elm St", city: "Austin", state: "TX", postal_code: "78704" },
    },
    building: {
      premise_no: "P-10432",
      name: null,
      premises_type: null,
      premises_type_name: null,
      inside_city_limits: null,
      area_code: null,
      area_name: null,
      parcel: null,
      parcel_verified: null,
      routes: [],
    },
    owner: null,
    history: { first_occupant: previous === null, previous, plan_changes: null },
  };
}

function mount(url: string, seed: (client: QueryClient) => void = () => undefined) {
  // ⚠ `staleTime: Infinity` so the seeded answers are the ONLY answers. Without
  // it react-query refetches each seeded key on mount, the real transport is not
  // reachable under jsdom, and the screen renders a search-failed strip beside
  // the data it already had — a state the product never shows and this file
  // would otherwise be asserting around.
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
  const router = createMemoryRouter(APP_ROUTES, { initialEntries: [`/${TEST_TENANT}${url}`] });
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
 * The wizard rail's step labels, in order.
 *
 * ⚠ Read off the rail's own `<nav data-wizard="rail">` rather than by
 * `getByText`: each rail button's text is the NUMBER badge followed by the
 * label ("1Find account"), so a text query for the label alone never matches
 * and a case built on one is red for the wrong reason.
 */
function railLabels(): string[] {
  const rail = document.body.querySelector('[data-wizard="rail"]');
  return [...(rail?.querySelectorAll("button") ?? [])].map((button) =>
    (button.textContent ?? "").replace(/^\d+/, ""),
  );
}

// ══════════════════════════════════════════════════════════════════════════
// 1 · THE PURE DERIVATION — the unit's most recent finished tenancy
// ══════════════════════════════════════════════════════════════════════════

describe("lastClosedAccountForUnit — the server's own rule, client side", () => {
  it("takes the TERMINAL account with the latest `closed_at`", () => {
    const picked = lastClosedAccountForUnit([
      row({ id: "old", account_no: "A-1", closed_at: "2025-01-31" }),
      row({ id: "new", account_no: "A-2", closed_at: "2026-08-14" }),
    ]);
    expect(picked?.id).toBe("new");
  });

  it("SKIPS a terminal account carrying no `closed_at` — there is nothing for BR-CUS-056 to measure against", () => {
    // `selectors.last_closed_account_for_unit` skips exactly this, and its own
    // docstring says why: slice 2 could write that state directly, and "closed
    // on some unknown day" cannot be compared with an incoming start date.
    expect(lastClosedAccountForUnit([row({ id: "dateless", closed_at: null })])).toBeNull();
  });

  it("ignores an account that is not TERMINAL — the CLASS, never the tenant's renamable label", () => {
    expect(
      lastClosedAccountForUnit([
        row({ id: "live", status_behavior_class: "billable", closed_at: "2026-08-14" }),
        row({ id: "draft", status_behavior_class: "non_billable", closed_at: "2026-08-14" }),
      ]),
    ).toBeNull();
  });

  it("answers null for a unit that has never been occupied", () => {
    expect(lastClosedAccountForUnit([])).toBeNull();
  });
});

// ══════════════════════════════════════════════════════════════════════════
// 2 · MOVE-OUT · `/move-outs/new`
// ══════════════════════════════════════════════════════════════════════════

describe("S20 standalone — the move-out finds its own account", () => {
  it("law 2 — the address is REACHED by the application's own route table, and it draws the wizard", () => {
    mount(MOVE_OUT_WIZARD_ROUTE);
    // The wizard's own H1 (`customers.moveOut.title`), not a 404 and not the
    // Accounts list.
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(
      "Close an account and free the unit.",
    );
  });

  it("step 1 is the SHARED account finder — one box, no uuid asked for (DEF-732)", () => {
    mount(MOVE_OUT_WIZARD_ROUTE);
    // The finder itself, by the marker `accountFinder.tsx` renders — not a
    // prop, not an import: the box is ON THE PAGE.
    expect(document.body.querySelector("[data-account-finder]")).not.toBeNull();
    // ⊕ `DEF-CUS-6475` — ONE control, and it is a `combobox`. The role is
    // asked for by name rather than by label alone, because the kit gives the
    // listbox the same accessible NAME as its input (BR-SHL-033's ARIA
    // pattern), so a bare label match now finds two elements and the error it
    // raises reads like a broken screen rather than a sharpened question.
    expect(screen.getByRole("combobox", { name: /^Account/ })).toBeInTheDocument();
  });

  it("BR-SHL-046 — the rail still addresses FOUR steps while the account is unchosen", () => {
    // FOUR since `e45a8e034` (2026-09-24, `DEF-CUS-6537`, PO ruling: ACC-06 is
    // four steps) — `DEF-CUS-9107`.
    mount(MOVE_OUT_WIZARD_ROUTE);
    // The number is an INDEX (a Move-outs row reopens the wizard AT one), so a
    // step that vanished while the account was being found would misaddress
    // every step after it.
    //
    // ⚠ **A PREFIX MATCH SINCE 2026-09-13, AND THE LANE THAT BROKE IT FIXED IT
    // HERE RATHER THAN LEAVING THE RED.** The blueprint writes `Step 1 of 6 ·
    // Find account` under the title of every move-out screen and the line drew
    // the number alone; adding the step's NAME made this exact `getByText`
    // stop matching, because the whole line is ONE text node — which it has to
    // be, since the separator and the word order move with the language
    // (`{{of}}단계 중 {{step}} · {{name}}` in Korean). What this case is FOR is
    // the SIX, and the prefix still asserts it exactly.
    expect(screen.getByText(/^Step 1 of 4\b/)).toBeInTheDocument();
    expect(railLabels()).toEqual([
      "Find account",
      "Date & reads",
      // PO 2026-09-24 — the drawn title of the merged money step.
      "Bill & deposit",
      "Review & close",
    ]);
  });

  it("choosing an account in the box makes step 1 CONFIRM it, and Continue opens", async () => {
    const user = userEvent.setup();
    mount(MOVE_OUT_WIZARD_ROUTE, (client) => {
      // What `GET /accounts?q=` answers, at the finder's own query key.
      client.setQueryData(
        ["account-finder", "A-10432"],
        accountsPage([row({ status: "active", status_name: "Active", status_behavior_class: "billable", closed_at: null })]),
      );
      client.setQueryData(
        accountDetailQueryKey("acc-10432"),
        detail({ status: "active", status_name: "Active", status_behavior_class: "billable", closed_at: null }),
      );
    });

    // ⊕ **ONE CONTROL NOW, AND THIS CASE PROVES IT FROM THE CLERK'S SIDE —
    // `DEF-CUS-6475`.** It used to `type` into an *Account* box and then
    // `selectOptions` a separate *Matching account* select: two gestures for
    // one choice, which is exactly what the Product Owner reported on
    // 2026-09-24. The box a clerk types in and the list they pick from are the
    // same control now, so the walk is type → click the option.
    await user.type(screen.getByRole("combobox", { name: /^Account/ }), "A-10432");
    // The match list is the SERVER's, rendered by the shared finder through the
    // kit's `RemoteSearchSelectField`. `role="option"` is the ARIA combobox
    // pattern that component implements (BR-SHL-033), so this asks the question
    // a screen reader would.
    const option = await screen.findByRole("option", { name: /A-10432/ });
    await user.click(option);
    // ⛔ **THE SECOND CONTROL IS GONE, AND ITS ABSENCE IS ASSERTED** — an
    // absence is invisible to every other check this repo has, so a lane
    // reinstating the two-field pair turns this red instead of passing quietly.
    expect(screen.queryByLabelText(/Matching account/)).toBeNull();

    // ⚠ RENDERED OUTPUT, not a prop: the chosen account's own facts are now on
    // the step, which is the same `AccountStep` the account-scoped road draws.
    expect(await screen.findByText("1408 Elm St · A")).toBeInTheDocument();
    // BR-CUS-030's refusal is NOT shown — this account occupies, so it may close.
    expect(screen.queryByText(/cannot be moved out/i)).toBeNull();

    // ⚠ **HARD-WON LAW 1, AND THIS IS THE HALF THAT IS EASY TO MISS.**
    // `customers.moveOut.account.hint` is in all eleven catalogues reading
    // *"…the server closes the account named in the address bar, so there is no
    // search on this step. Go back to Accounts to move a different one out."*
    // On THIS road the search IS this step, and there is nothing in the address
    // bar — so that sentence must not be drawn beside the box that disproves it.
    expect(document.body.textContent).not.toContain("there is no search on this step");
  });
});

// ══════════════════════════════════════════════════════════════════════════
// 3 · MOVE-IN · `/move-ins/new`
// ══════════════════════════════════════════════════════════════════════════

describe("S19 standalone — the move-in finds its UNIT, and derives the account", () => {
  it("law 2 — the address is REACHED by the application's own route table, and it draws the wizard", () => {
    mount(MOVE_IN_WIZARD_ROUTE, (client) => {
      client.setQueryData(["move-in-unit-search", "", 1], searchRows([unit()]));
    });
    // `CR-171-BRC10` P2.17 — image 30's title.
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("New move-in");
  });

  it("BR-CUS-020 — step 1 offers the VACANT units the SERVER returned, and asks for no account", () => {
    mount(MOVE_IN_WIZARD_ROUTE, (client) => {
      client.setQueryData(["move-in-unit-search", "", 1], searchRows([unit()]));
    });
    // `DEF-CUS-10190` (PO 2026-10-17) — a SEARCH across every unit replaced
    // the vacant-only select; the server's rows are drawn with a *Use* button.
    expect(screen.getByLabelText(/Find unit/)).toBeInTheDocument();
    expect(screen.queryByLabelText(/Vacant unit/)).toBeNull();
    expect(useButton("U-10432-A")).toBeInTheDocument();
    expect(document.querySelector('[data-move-in-unit-results]')?.textContent).toContain("1408 Elm St");
    // ⛔ THE POINT OF THE PO's RULING: no account is asked for here.
    expect(screen.queryByLabelText(/Matching account/)).toBeNull();
    expect(document.body.querySelector("[data-account-finder]")).toBeNull();
  });

  it("hard-won law 1 — the two account-scoped sentences that would be FALSE here are not drawn", async () => {
    const user = userEvent.setup();
    mount(MOVE_IN_WIZARD_ROUTE, (client) => {
      client.setQueryData(["move-in-unit-search", "", 1], searchRows([unit()]));
      client.setQueryData(["move-in-unit-accounts", "u-10432a"], accountsPage([row()]));
      client.setQueryData(accountDetailQueryKey("acc-10432"), detail());
      client.setQueryData(
        ["move-in-step-unit-facts", "u-10432a"],
        unitFacts("u-10432a", { account_no: "A-10432", name: "Miller, Sarah", closed_at: "2026-08-14" }),
      );
    });
    // ⚠ THE UNIT HAS TO BE CHOSEN, or step 1's card never renders and the two
    // sentences under test are absent for the wrong reason — a case that cannot
    // tell pass from fail is worse than no case (DEF-182's lesson).
    await user.click(useButton("U-10432-A"));
    // `CR-171-BRC10` P2.18 — the tenancy followed is named by the card's
    // History group (image 30), which replaced the note under the picker.
    await waitFor(() =>
      expect(document.querySelector('[data-unit-group="history"]')?.textContent).toContain("A-10432"),
    );
    // `customers.moveIn.unit.noPicker` — *"There is no picker here because the
    // server takes the unit from the account in the address bar"*. There IS a
    // picker, on this very step, and there is no account in the address bar.
    expect(document.body.textContent).not.toContain("There is no picker here");
    // `customers.moveIn.unit.hint` — *"It is fixed by the account you started
    // from, so there is nothing to choose on this step."* The clerk just chose it.
    expect(document.body.textContent).not.toContain("there is nothing to choose on this step");
  });

  it("choosing the unit DERIVES the outgoing account, names it, and opens the flow", async () => {
    const user = userEvent.setup();
    mount(MOVE_IN_WIZARD_ROUTE, (client) => {
      client.setQueryData(["move-in-unit-search", "", 1], searchRows([unit()]));
      // `GET /accounts?f.unit_id=u-10432a` — the PUBLISHED filter. Two finished
      // tenancies, so the derivation has to pick, not merely find.
      client.setQueryData(
        ["move-in-unit-accounts", "u-10432a"],
        accountsPage([
          row({ id: "acc-99", account_no: "A-99", closed_at: "2024-01-31" }),
          row(),
        ]),
      );
      client.setQueryData(accountDetailQueryKey("acc-10432"), detail());
      client.setQueryData(
        ["move-in-step-unit-facts", "u-10432a"],
        unitFacts("u-10432a", { account_no: "A-10432", name: "Miller, Sarah", closed_at: "2026-08-14" }),
      );
    });

    await user.click(useButton("U-10432-A"));

    // ⚠ THE DERIVED ACCOUNT IS NAMED ON SCREEN — `CR-171-BRC10` P2.18: by the
    // unit card's History group (image 30), which replaced the note under the
    // picker. And the flow opens on the unit derived from it: the card is
    // read for `u-10432a`, the outgoing account's unit.
    await waitFor(() =>
      expect(document.querySelector('[data-unit-group="history"]')?.textContent).toContain("A-10432"),
    );
    const history = document.querySelector('[data-unit-group="history"]')?.textContent ?? "";
    expect(history).toContain("Miller, Sarah");
    // …and NOT the older tenancy.
    expect(history).not.toContain("A-99");
    // The BR-CUS-056 boundary is still the derived account's move day: the
    // date box proposes the day after it.
    expect(screen.getByLabelText(/Move-in date/)).toBeInTheDocument();
    expect(screen.getByText("U-10432-A · A")).toBeInTheDocument();
  });

  it("an OCCUPIED unit from the search warns ONCE and offers Start move-out (DEF-CUS-10190 · DEF-CUS-10192)", async () => {
    const user = userEvent.setup();
    mount(MOVE_IN_WIZARD_ROUTE, (client) => {
      const page = searchRows([unit({ id: "u-occ", unit_no: "U-OCC" })]);
      page.results[0] = {
        ...page.results[0],
        state: "active",
        path: "move_out_first",
        occupant: { account_id: "acc-occ", account_no: "A-77", name: "Rosa Diaz", status_name: "Active", closed_at: null },
      };
      client.setQueryData(["move-in-unit-search", "", 1], page);
      client.setQueryData(["move-in-unit-accounts", "u-occ"], accountsPage([]));
      client.setQueryData(["move-in-step-unit-facts", "u-occ"], unitFacts("u-occ", null));
    });
    await user.click(useButton("U-OCC"));
    await waitFor(() =>
      expect(document.querySelector("[data-move-in-unit-occupied]")?.textContent).toContain(
        "Rosa Diaz is still on this unit. Start a move-out for them first.",
      ),
    );
    expect(screen.getByRole("button", { name: "Start move-out" })).toBeInTheDocument();
    // ⛔ ONE warning: the account-scoped road's long strip is not drawn too.
    expect(document.body.textContent).not.toContain("This account still holds the unit");
  });

  it("a vacant unit with NO finished tenancy is a FIRST OCCUPANT, and the move-in carries on (DEF-CUS-6353)", async () => {
    const user = userEvent.setup();
    mount(MOVE_IN_WIZARD_ROUTE, (client) => {
      client.setQueryData(["move-in-unit-search", "", 1], searchRows([unit({ id: "u-new", unit_no: "U-NEW" })]));
      client.setQueryData(["move-in-unit-accounts", "u-new"], accountsPage([]));
      client.setQueryData(["move-in-step-unit-facts", "u-new"], unitFacts("u-new", null));
    });

    await user.click(useButton("U-NEW"));

    // ⚠ **THIS CASE ASSERTED THE OPPOSITE UNTIL 2026-09-23.** It read *"says so
    // and points at S18 — no endpoint is invented"*: the step refused the unit
    // and linked to New account. The PO's move-in approval ruling sends an
    // approved request for such a unit here, so the refusal was retired (not
    // reworded) and `POST /units/{unit_id}/move-in` takes it.
    // `CR-171-BRC10` P2.18 — said by the unit card (a chip and the History
    // group, image 30), which replaced the two notes that said it before.
    await waitFor(() =>
      expect(document.querySelector('[data-unit-group="history"]')?.textContent).toContain("First occupant"),
    );
    expect(screen.queryByText(/no finished tenancy to follow/)).toBeNull();
    expect(screen.queryByRole("link", { name: "+ New account" })).toBeNull();

    // And step 1 is ANSWERED: Continue walks on to the customer step. Since
    // `CR-171-BRC10` the move-in date is on step 1 too, so it is typed first.
    await user.type(screen.getByLabelText(/Move-in date/), "2026-08-01");
    await user.click(screen.getByRole("button", { name: "Continue" }));
    await waitFor(() => {
      expect(document.body.querySelector('[data-wizard-step="2"]')?.getAttribute("data-state")).toBe(
        "active",
      );
    });
  });

  it("a FIRST OCCUPANT's deposit row reads the plan's figure for the unit chosen on step 1 (DEF-CUS-6353 × DEF-CUS-6369 · DEF-CUS-9769)", async () => {
    // ⚠ **THE INTERACTION BETWEEN TWO LANES' FIXES, PINNED.** The deposit step
    // reads `GET /accounts/deposit-standard` for a UNIT and a CATEGORY. On the
    // account road the unit is the outgoing account's; a first occupant has no
    // outgoing account, so the unit is the one picked on step 1 — and passing
    // `outgoing.unit_id` would leave the step holding forever on "reading".
    const user = userEvent.setup();
    mount(MOVE_IN_WIZARD_ROUTE, (client) => {
      client.setQueryData(["move-in-unit-search", "", 1], searchRows([unit({ id: "u-new", unit_no: "U-NEW" })]));
      client.setQueryData(["move-in-unit-accounts", "u-new"], accountsPage([]));
      client.setQueryData(unitAssetsQueryKey("u-new"), {
        unit: {
          id: "u-new",
          unit_no: "U-NEW",
          label: "Unit A",
          premises_id: "p-10432",
          premise_no: "P-10432",
          premise_address: "1408 Elm St",
        },
        groups: [],
        counts: {},
        reading_expected: { served: false, reason: "", tracks: null },
      });
      client.setQueryData(["move-in-step-unit-facts", "u-new"], unitFacts("u-new", null));
      // ⚠ **RE-POINTED 2026-10-05 (`DEF-CUS-9769`).** This seeded the old
      // `deposit-standard` read and asked the retired Deposit form for its
      // Amount; since 2.545.0 step 3 · Billing prices the deposit as a row of
      // its Fees table, from ONE read — `GET /move-ins/pricing` — keyed on the
      // unit. It is seeded ONLY for the unit picked on step 1, so a step that
      // asked about any other unit (the outgoing account's, which a first
      // occupant has not got) reads nothing, shows no deposit row, and this
      // case goes red.
      client.setQueryData(moveInMoneyKeys.pricing({ unitId: "u-new", accountType: "residential", services: [] }), {
        unit_id: "u-new",
        account_type: "residential",
        services: [],
        plan_absent: "unit_has_no_plan",
        plan: null,
        deposit: null,
        fees: {
          rows: [
            {
              kind: "deposit",
              source: "plan",
              code: "DEPOSIT",
              name: "Security deposit",
              amount: "150.0000",
              locked: true,
              refusal: null,
              taxed_at_move_in: false,
            },
          ],
          total: "150.0000",
          currency: "USD",
        },
        assets: [],
        move_in_fees_taxed: false,
      });
    });
    await user.click(useButton("U-NEW"));
    await waitFor(() =>
      expect(document.querySelector('[data-unit-group="history"]')?.textContent).toContain("First occupant"),
    );
    const onStep = (n: number) =>
      waitFor(() =>
        expect(
          document.body.querySelector(`[data-wizard-step="${n}"]`)?.getAttribute("data-state"),
        ).toBe("active"),
      );
    // ⚠ **FOUR STEPS SINCE `CR-171-BRC10` (2026-10-05).** It was seven
    // (`DEF-CUS-9107`); the date now sits on step 1 · Unit and the deposit on
    // step 3 · Billing. The walk is the same walk, three steps shorter.
    await user.type(screen.getByLabelText(/Move-in date/), "2026-08-01");
    await user.click(screen.getByRole("button", { name: "Continue" }));
    await onStep(2);
    await user.type(screen.getByLabelText(/Full name/), "Okonjo, Ada");
    await user.click(screen.getByRole("radio", { name: "Person" }));
    await user.type(screen.getByLabelText(/^Phone/), "512-555-0177");
    await user.click(screen.getByRole("button", { name: "Continue" }));
    await onStep(3);

    // The Fees table's DEPOSIT row reads the plan's figure for THIS unit.
    const deposit = await waitFor(() => {
      const row = [...document.body.querySelectorAll<HTMLElement>("[data-editable-row]")].find((candidate) =>
        candidate.textContent?.includes("Security deposit"),
      );
      expect(row).toBeDefined();
      return row as HTMLElement;
    });
    expect(deposit).toHaveTextContent("$150.00");
  });

  it("BR-SHL-046 — the rail still addresses ALL FOUR steps while the unit is unchosen", () => {
    // FOUR since `CR-171-BRC10` (2026-10-05); seven before (`DEF-CUS-9107`).
    // The point of this case is unchanged and is the reason it asserts the
    // WORDS in order rather than a count: the step number is an INDEX, so a
    // rail that hid a step it could not serve yet would misaddress every step
    // after it.
    mount(MOVE_IN_WIZARD_ROUTE, (client) => {
      client.setQueryData(["move-in-unit-search", "", 1], searchRows([unit()]));
    });
    expect(railLabels()).toEqual(["Unit", "Customer", "Billing", "Review"]);
  });
});

// ══════════════════════════════════════════════════════════════════════════
// 4 · THE BUTTON REACHES THE SCREEN — both ends of hard-won law 2
// ══════════════════════════════════════════════════════════════════════════
//
// ⚠ **THE CASES ABOVE PROVE THE ROUTE RENDERS; THESE PROVE THE CONTROL REACHES
// IT.** DEF-730's mirror image is a CTA enabled onto a route that does not
// exist, and neither half can be seen from the other: a route with no caller is
// dead code, and a caller pointing at nothing is a dead button. These start on
// the Accounts page the PO was standing on, click the control they could not
// use, and look for the wizard at the far end.

describe("the Accounts header's Move-in / Move-out now go somewhere", () => {
  for (const flow of [
    {
      tab: "move-ins",
      // `CR-171-BRC10` P2.01 — image 01's `+ New move-in` on the Move-ins tab.
      label: "+ New move-in",
      url: `/${TEST_TENANT}/move-ins/new`,
      heading: "New move-in",
    },
    {
      tab: "move-outs",
      label: "Move-out",
      url: `/${TEST_TENANT}/move-outs/new`,
      heading: "Close an account and free the unit.",
    },
  ] as const) {
    it(`${flow.tab}: the tab's primary is clickable and lands on the wizard`, async () => {
      const user = userEvent.setup();
      const router = mount(`/accounts?tab=${flow.tab}`, (client) => {
        client.setQueryData(["move-in-unit-search", "", 1], searchRows([unit()]));
      });

      // ⚠ THE PAGE-HEADER PRIMARY, not the tab strip's own tab button of the
      // same name: `getAllByRole` would match both. B14 rule 4 / BR-SHL-044 —
      // exactly one primary — is what makes this query unambiguous.
      const actions = document.body.querySelector(".page-header-actions");
      const button = [...(actions?.querySelectorAll("button") ?? [])].find(
        (candidate) => candidate.textContent === flow.label,
      );
      expect(button).toBeDefined();
      // BR-SHL-025 read the other way: a control that CAN act is not disabled.
      expect(button).not.toBeDisabled();

      await user.click(button as HTMLButtonElement);

      expect(router.state.location.pathname + router.state.location.search).toBe(flow.url);
      // …and something is actually there. A navigation to a 404 passes the
      // line above and fails this one.
      expect(await screen.findByRole("heading", { level: 1 })).toHaveTextContent(flow.heading);
    });
  }
});

// ══════════════════════════════════════════════════════════════════════════
// 4b · `BR-CUS-1051` — THE CONTROL IS PRESSED AND THE DIALOG OPENS OVER THE
//      ACCOUNT (CR-094-BRC01 wave L)
// ══════════════════════════════════════════════════════════════════════════
//
// PO 2026-09-13, verbatim: *"Yes move the eight quick actions over the
// account"*. §4 above proves a control reaches a screen; this proves what the
// ruling actually asked for — that the account **is still there** when it does.
//
// ⚠ **IT STARTS ON THE ACCOUNT AND CLICKS, THROUGH THE REAL ROUTE TABLE.** A
// case that navigates straight to the child address proves the route and not
// the control, and a case that mounts the container over a stub proves the
// container and not the page. This one is the whole chain: the button on S21 →
// the URL → the route table → the dialog → the account still rendered behind
// it. It is the nearest this suite gets to hard-won law 6's *click it*.

describe("BR-CUS-1051 — pressing Move-out on the account opens it OVER the account", () => {
  it("navigates to the child address and leaves the account on screen", async () => {
    const user = userEvent.setup();
    const router = mount("/accounts/acc-10432", (client) => {
      client.setQueryData(
        accountDetailQueryKey("acc-10432"),
        detail({
          status: "active",
          status_name: "Active",
          status_behavior_class: "billable",
          closed_at: null,
        }),
      );
    });

    const actions = document.body.querySelector(".page-header-actions");
    const button = [...(actions?.querySelectorAll("button") ?? [])].find(
      (candidate) => candidate.textContent === "Move-out",
    );
    expect(button, "the account header offers Move-out").toBeDefined();
    expect(button).not.toBeDisabled();

    await user.click(button as HTMLButtonElement);

    // The ADDRESS is unchanged from what it was before this wave — a nesting,
    // not a re-addressing.
    expect(router.state.location.pathname).toBe(`/${TEST_TENANT}/accounts/acc-10432/move-out`);
    // The WIZARD is there…
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByRole("heading", { level: 1 })).toHaveTextContent(
      "Close an account and free the unit.",
    );
    // …and so is the account it was launched from, which is the ruling.
    expect(screen.getAllByText("1408 Elm St · A").length).toBeGreaterThan(1);
  });
});

// ══════════════════════════════════════════════════════════════════════════
// 5 · NOTHING THAT WORKED TODAY STOPPED WORKING
// ══════════════════════════════════════════════════════════════════════════

describe("the account-scoped roads are untouched", () => {
  // ⚠ **AMENDED 2026-09-13 — `BR-CUS-1051`, `CR-094-BRC01` wave L. THE
  // ASSERTIONS MOVED; WHAT THEY ASSERT DID NOT.**
  //
  // PO 2026-09-13, verbatim: *"Yes move the eight quick actions over the
  // account"*. `/accounts/:accountId/move-out` and `…/move-in` are now CHILD
  // routes of the account, so both addresses render `AccountDetailPage` with
  // the wizard in a dialog over it. **Both cases below then found `1408 Elm St
  // · A` TWICE** — once on the account behind, once in the wizard in front —
  // and `getByText` throws on two matches.
  //
  // **That is the ruling working, not a regression**, and the honest repair is
  // to ASK THE SAME QUESTION OF THE WIZARD rather than of the whole document.
  // Scoped to the dialog these cases are STRONGER than they were: before, a
  // premise rendered by anything at all on the page satisfied them.
  //
  // ⚠ The second half of each case — no finder, no unit picker — is unscoped on
  // purpose. *"Nowhere on this screen is there a second way to choose the
  // account"* is a claim about the whole document, and narrowing it to the
  // dialog would quietly stop checking the thing it was written for.
  function dialog(): HTMLElement {
    return screen.getByRole("dialog");
  }

  it("S20 at `/accounts/:accountId/move-out` still CONFIRMS the account and draws no finder", () => {
    mount("/accounts/acc-10432/move-out", (client) => {
      client.setQueryData(
        accountDetailQueryKey("acc-10432"),
        detail({ status: "active", status_name: "Active", status_behavior_class: "billable", closed_at: null }),
      );
    });
    expect(within(dialog()).getByText("1408 Elm St · A")).toBeInTheDocument();
    // ⛔ No second way to choose the same thing — the file header's departure 1,
    // which still holds on this road.
    expect(document.body.querySelector("[data-account-finder]")).toBeNull();
  });

  it("S19 at `/accounts/:accountId/move-in` still takes its unit from the URL's account, with no picker", () => {
    mount("/accounts/acc-10432/move-in", (client) => {
      client.setQueryData(accountDetailQueryKey("acc-10432"), detail());
      client.setQueryData(
        ["move-in-step-unit-facts", "u-10432a"],
        unitFacts("u-10432a", { account_no: "A-10432", name: "Miller, Sarah", closed_at: "2026-08-14" }),
      );
    });
    // `CR-171-BRC10` P2.18 — step 1's card, read for the URL account's unit.
    expect(within(dialog()).getByText("U-10432-A · A")).toBeInTheDocument();
    expect(screen.queryByLabelText(/Vacant unit/)).toBeNull();
  });

  it("BR-CUS-1051 — and the account is STILL THERE behind the wizard", () => {
    // The half the two cases above cannot see, and the half the ruling is
    // about: `ACC-S14` asks that a clerk act *"without losing sight of the
    // balance behind it"*. A dialog over a blank page would satisfy every
    // assertion in this file.
    mount("/accounts/acc-10432/move-out", (client) => {
      client.setQueryData(
        accountDetailQueryKey("acc-10432"),
        detail({ status: "active", status_name: "Active", status_behavior_class: "billable", closed_at: null }),
      );
    });
    expect(screen.getAllByText("1408 Elm St · A").length).toBeGreaterThan(1);
    expect(dialog()).toHaveAttribute("aria-modal", "true");
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: PO ruling 2026-08-26 ("-Enable Move in /move out") over the
//         justification recorded in `AccountsListPage.tabPrimary` and in
//         `App.tsx`'s S19/S20 route comment
// generated: 2026-08-26 by lane MOVEENTRY
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: tsc✔ eslint✔ vitest✔
// exceptions: E3 the two reads this change makes are BOTH already published —
//   `GET /units?f.occupancy=vacant` (the read `NewAccountWizard` makes) and
//   `GET /accounts?f.unit_id=` (`ACCOUNT_FILTERS`, served since W2). NO endpoint
//   is added, and the standalone S19 for a unit with no predecessor is STATED
//   as having none rather than given an invented one · E3 the client-side
//   predecessor tiebreak is `closed_at` then `id`, where the server's is
//   `closed_at` then `created_at` then `id`: `AccountRow` carries no
//   `created_at`. Two accounts closing the same day on one unit give the
//   IDENTICAL BR-CUS-056 boundary, and the chosen predecessor is rendered by
//   name and date so a wrong tiebreak is visible — REPORTED
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
