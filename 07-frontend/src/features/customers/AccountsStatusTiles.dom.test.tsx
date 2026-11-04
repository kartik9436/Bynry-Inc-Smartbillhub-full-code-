// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:  PO ruling 2026-09-28 — the Accounts register carries FOUR tiles,
//          **Active · Pending · Disconnecting · Suspended**, one word each with
//          a short line under it, and *"each tile SETS the list's filter when
//          pressed, through the same state the FilterBar reads, so the filter
//          bar shows it as applied afterwards"*.
// Defect:  DEF-CUS-7700 — two of the five tiles it replaces never counted
//          anything, and the suite asserted their placeholder text.
// Rules:   BR-CUS-055 (the seeded statuses and their behaviour classes;
//          tenant-EXTENSIBLE) · B14 rule 33 (a LABEL ≤ 3 words · a FACT ≤ 6 ·
//          RATIONALE zero) · rule 31 (no database id is a visible value) ·
//          rule 43 (a piece of UI is a COMPONENT — the strip is the shared
//          `KPIStrip`, not a second one) · BR-SHL-011 (the `f.<name>` URL
//          grammar the filter and the tile now share) · hard-won law 2 and its
//          MIRROR (built is not wired; a live screen behind a dead control)
// Screens: S17 — Accounts → Accounts
// Tests:   this file · src/features/customers/AccountsPage.test.tsx (the
//          rendered strip, statically) · 06-backend/tests/
//          test_def_cus_7700_account_status_tiles.py (the grouped count)
// ───────────────────────────────────────────────────────
//
// ══════════════════════════════════════════════════════════════════════════
// WHY THIS FILE EXISTS BESIDE `AccountsPage.test.tsx`
// ══════════════════════════════════════════════════════════════════════════
// That suite renders to STATIC MARKUP. It can prove the four tiles are drawn,
// with the right words and the right numbers, and it can NEVER prove that
// pressing one sends anything — which is the whole of the ruling, and the
// defect this screen's neighbour already shipped once: five worklists with a
// filter control that rendered and did nothing (`DEF-1702`). **This file
// CLICKS**, in jsdom, and reads the answer back out of the FILTER BAR rather
// than out of a prop.
//
// ⚠ **IT MOUNTS UNDER THE REAL PATH PATTERN, NOT A BARE `MemoryRouter`.**
// `AccountsListPage` builds every address through `useTenantPath()`, which
// reads `useParams().tenant`. Mounted with no `/:tenant/...` route that is
// `undefined` and every address comes out `//accounts/…` — a protocol-relative
// URL to another host, which reads as a perfectly good string to `toContain`.
// That is `DEF-CWP-3925`'s fixture hole, named in hard-won law 2.
//
// ⚠ **THE PROOF IS THE CHIP AND THE REQUEST, NOT THE PRESSED TILE.** A tile
// that merely turned itself on would satisfy `aria-pressed` and leave the list
// showing everything — two controls holding one answer, which is the defect
// just removed from the New Connects list. So every case here asserts at least
// one of: the chip the FilterBar drew, or the `f.status=` the server was asked
// for.
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import { createApiClient } from "@/api/client";
import { queryKeys } from "@/api/queryClient";
import { ToastProvider } from "@/components/Toast";
import type { AccountRow, AccountsPage } from "@/api/endpoints";

import { AccountsListPage } from "./AccountsListPage";
import { ACCOUNT_CATEGORIES_QUERY_KEY, ACCOUNTS_PERMISSION } from "./customersShared";

const TEST_TENANT = "brazosbend";

afterEach(cleanup);

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
    services: ["electric"],
    balance: "247.300000",
    balance_currency: "USD",
    balance_basis: "posting",
    balance_source: "ledger",
    balance_unavailable: [],
    balance_not_yet_billable: false,
    balance_cached: "0.000000",
    currency: "USD",
    status: "active",
    status_name: "Active",
    status_behavior_class: "billable",
    account_type: "residential",
    account_subtype: null,
    autopay: true,
    opened_at: "2024-02-14",
    closed_at: null,
    last_bill_at: null,
    aging: null,
    ...over,
  };
}

/**
 * ⚠ **THE FIGURES ARE ILLUSTRATIONS (B14 rule 37).** What these pin is which
 * tile reads which status CODE, never that a real utility has 71 active
 * accounts. They are the PO's own worked example all the same — 71 active out
 * of a tenant whose old `ACCOUNTS` tile read 79 — because the headline number
 * FALLING is the thing that will look like a bug on the day this ships.
 */
const BY_STATUS = [
  { code: "active", name: "Active", accounts: 71 },
  { code: "closed", name: "Closed", accounts: 5 },
  { code: "disconnected", name: "Disconnected", accounts: 0 },
  { code: "marked_disconnect", name: "Marked disconnect", accounts: 2 },
  { code: "pending_activation", name: "Pending activation", accounts: 1 },
  { code: "vacation_hold", name: "Vacation hold/Suspended", accounts: 0 },
];

function envelope(over: Partial<AccountsPage["rollup"]> = {}): AccountsPage {
  return {
    count: 1,
    next: null,
    previous: null,
    results: [row()],
    rollup: {
      accounts: 79,
      outstanding: "19461.870000",
      currency: "USD",
      outstanding_basis: "posting",
      outstanding_unavailable: [],
      past_due_60_plus: null,
      by_status: BY_STATUS,
      ...over,
    },
  };
}

/**
 * Mount the register AT ITS REAL ADDRESS, with the accounts read going through
 * a real client so the REQUEST is observable.
 *
 * Permissions and the category catalogue are seeded into the cache rather than
 * answered by `fetchImpl`: they are not what this file is about, and a fixture
 * that has to fake three endpoints to test one is a fixture nobody maintains.
 */
function mount(initial = "/accounts", rollupOver: Partial<AccountsPage["rollup"]> = {}) {
  const urls: string[] = [];
  const client = createApiClient({
    tenant: TEST_TENANT,
    // ⚠ **ROUTED BY URL, NOT ANSWERED BLIND.** The page fires three reads and
    // only one of them is this file's subject; a fixture that hands the same
    // body to all three is a fixture that cannot tell which one it just
    // asserted about. `urls` therefore holds ONLY the accounts reads, so
    // `urls[urls.length - 1]` means what the cases below say it means.
    fetchImpl: async (input) => {
      const url = String(input);
      const body = url.includes("/accounts")
        ? (urls.push(url), envelope(rollupOver))
        : { selectable: [], legacy: [] };
      return new Response(JSON.stringify(body), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    },
  });
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  queryClient.setQueryData(queryKeys.myPermissions, {
    role: "billing_clerk",
    role_name: "Billing Clerk",
    permissions: [{ code: ACCOUNTS_PERMISSION, label: "Premises / Accounts", access: "Full" }],
  });
  queryClient.setQueryData(ACCOUNT_CATEGORIES_QUERY_KEY, { selectable: [], legacy: [] });
  render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TEST_TENANT}${initial}`]}>
          <Routes>
            {/* ⚠ **THE `client` PROP IS LOAD-BEARING AND ITS ABSENCE IS
                SILENT.** `AccountsListPage` falls back to the real `api`
                singleton, which in jsdom fails every request with `HTTP 0` —
                so the first draft of this file mounted, fetched nothing, drew
                four dashes and failed ten cases on *"Unable to find
                role=table"*, which names neither the cause nor the fix. */}
            <Route path="/:tenant/accounts" element={<AccountsListPage client={client} />} />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
  return { urls };
}

/**
 * The four tiles as a clerk reads them: the word, then the number.
 *
 * ⚠ **READ OFF THE STRIP'S CHILDREN, NOT OFF `[data-kpi]`.** A tile that
 * cannot be pressed carries no `data-kpi`, so a `[data-kpi]` selector silently
 * returns THREE on the very tenant the absence case exists to check — and
 * `expect(undefined).toBe("—")` names nothing. Found by writing the case.
 */
function tiles(): { label: string; value: string; pressed: boolean; presses: boolean }[] {
  return Array.from(document.querySelectorAll(".kpi-grid > *")).map((node) => ({
    label: String(node.querySelector("span.k")?.textContent ?? "").trim(),
    value: String(node.querySelector("span.v")?.textContent ?? "").trim(),
    pressed: node.getAttribute("aria-pressed") === "true",
    presses: node.hasAttribute("data-kpi"),
  }));
}

/**
 * Every chip the FILTER BAR is drawing, by its text.
 *
 * ⚠ **THE `✕` IS PART OF THE CHIP'S `textContent`** — `Chip` renders the
 * remove control inside the chip, so the bar reads `Status: Active×`. Trimmed
 * here rather than in every assertion, so a case says what it means.
 */
function chips(): string[] {
  return Array.from(document.querySelectorAll("[data-chip]")).map((node) =>
    String(node.textContent ?? "")
      .replace(/[×✕]\s*$/, "")
      .trim(),
  );
}

describe("PO 2026-09-28 · the Accounts register's four status tiles", () => {
  it("draws the four the PO ruled, in the PO's order, each with its served count", async () => {
    mount();
    await screen.findByRole("table");

    expect(tiles().map((tile) => tile.label)).toEqual([
      "Active",
      "Pending",
      "Disconnecting",
      "Suspended",
    ]);
    // Each reads the count the ONE grouped query sent for ITS status code.
    expect(tiles().map((tile) => tile.value)).toEqual(["71", "1", "2", "0"]);
  });

  /**
   * ⚠ **THE HEADLINE FALLS FROM 79 TO 71 AND THAT IS THE RULING, NOT A BUG.**
   * The tile it replaces counted live AND closed; `Active` counts only the
   * accounts billing normally. The envelope still carries `accounts: 79`, and
   * this asserts the screen no longer prints it — because the two numbers side
   * by side on one screen are what a clerk would read as a defect.
   */
  it("prints no tenant-wide total and no money: the five dropped figures are gone from the page", async () => {
    mount();
    await screen.findByRole("table");

    const page = document.body.textContent ?? "";
    expect(page).not.toContain("79");
    expect(page).not.toContain("$19,461.87");
    for (const dropped of ["Outstanding", "Past-due 60+", "Closed this year", "Not counted yet"]) {
      expect(page).not.toContain(dropped);
    }
  });

  /**
   * THE RULING'S OWN SENTENCE, ASSERTED THE WAY IT IS WRITTEN: press the tile,
   * read the chip back out of the filter bar.
   */
  it("pressing a tile applies the status filter, and the FILTER BAR shows it as applied", async () => {
    const { urls } = mount();
    await screen.findByRole("table");
    expect(chips()).toEqual(["All"]);

    await userEvent.click(screen.getByRole("button", { name: /Active/ }));

    // (1) THE CHIP. `table.filters.chip` is `{{label}}: {{value}}`, so the bar
    // reads the filter's own label and the STATUS OPTION's label — which is
    // the proof that the tile wrote the state the bar reads, and not a copy of
    // its own.
    await waitFor(() => expect(chips()).toContain("Status: Active"));
    // …and the `All` chip is no longer the selected one.
    expect(
      document.querySelector('[data-chip="selected"]')?.textContent?.trim(),
    ).not.toBe("All");
    // (2) THE SERVER WAS REALLY ASKED. A tile that only lit itself up would
    // pass (1) on a page still showing every account.
    await waitFor(() => expect(urls.some((url) => url.includes("f.status=active"))).toBe(true));
    // (3) The tile itself says it is on, for a screen reader as well as a mouse.
    expect(tiles().find((tile) => tile.label === "Active")?.pressed).toBe(true);
    expect(tiles().filter((tile) => tile.pressed)).toHaveLength(1);
  });

  it("pressing the same tile again clears the filter and the chip goes with it", async () => {
    const { urls } = mount();
    await screen.findByRole("table");

    await userEvent.click(screen.getByRole("button", { name: /Suspended/ }));
    await waitFor(() => expect(chips()).toContain("Status: Vacation hold/Suspended"));

    await userEvent.click(screen.getByRole("button", { name: /Suspended/ }));

    await waitFor(() => expect(chips()).toEqual(["All"]));
    expect(tiles().filter((tile) => tile.pressed)).toHaveLength(0);
    // The LAST request carries no status at all — the key is deleted rather
    // than sent empty, so `f.status=` never reaches the server as a filter
    // nobody can see.
    expect(urls[urls.length - 1]).not.toContain("f.status");
  });

  /**
   * ⚠ **A NARROWER LIST HAS FEWER PAGES.** Pressing a tile on page 3 and
   * staying on page 3 is the blank table `BR-SHL-011`'s clamp exists to
   * prevent, and it is the half of the ruling a `toContain` on the chip would
   * never notice.
   */
  it("a tile pressed on page 3 puts the list back on page 1", async () => {
    const { urls } = mount("/accounts?page=3");
    await screen.findByRole("table");
    expect(urls.some((url) => url.includes("page=3"))).toBe(true);

    await userEvent.click(screen.getByRole("button", { name: /Pending/ }));

    await waitFor(() =>
      expect(urls.some((url) => url.includes("f.status=pending_activation"))).toBe(true),
    );
    const narrowed = urls.filter((url) => url.includes("f.status=pending_activation"));
    for (const url of narrowed) {
      expect(url).not.toContain("page=3");
    }
  });

  /**
   * ⚠ **SWITCHING TILES REPLACES THE FILTER, IT DOES NOT ADD ONE.** `f.status`
   * takes one value, so a second press must move the chip rather than draw a
   * second one — and a strip that let two tiles look pressed at once would be
   * claiming a list narrowed two ways.
   */
  it("pressing a second tile moves the filter rather than adding one", async () => {
    mount();
    await screen.findByRole("table");

    await userEvent.click(screen.getByRole("button", { name: /Active/ }));
    await waitFor(() => expect(chips()).toContain("Status: Active"));

    await userEvent.click(screen.getByRole("button", { name: /Disconnecting/ }));

    await waitFor(() => expect(chips()).toContain("Status: Marked disconnect"));
    expect(chips()).not.toContain("Status: Active");
    expect(tiles().filter((tile) => tile.pressed).map((tile) => tile.label)).toEqual([
      "Disconnecting",
    ]);
  });

  /**
   * BR-CUS-055 — the status list is TENANT-EXTENSIBLE, in both directions.
   */
  it("a tenant whose status set is missing one of the four gets a dash there, not a zero", async () => {
    mount("/accounts", {
      by_status: [
        { code: "active", name: "Active", accounts: 6 },
        { code: "pending_activation", name: "Pending activation", accounts: 0 },
        { code: "marked_disconnect", name: "Marked disconnect", accounts: 0 },
        // `vacation_hold` is simply not this utility's.
      ],
    });
    await screen.findByRole("table");

    // Still four tiles: the ruling is four, and a strip that silently shrinks
    // to three for some tenants is a screen nobody can describe.
    expect(tiles()).toHaveLength(4);
    const suspended = tiles().find((tile) => tile.label === "Suspended");
    expect(suspended?.value).toBe("—");
    // A tile whose status the tenant does not have is NOT a control: a filter
    // on it would return an empty list for ever.
    expect(suspended?.presses).toBe(false);
    expect(document.querySelector('[data-kpi="suspended"]')).toBeNull();
    // The two at a REAL zero are still controls — a zero is an answer.
    expect(tiles().find((tile) => tile.label === "Pending")?.value).toBe("0");
    expect(document.querySelector('[data-kpi="pending"]')).not.toBeNull();
  });

  it("a renamed status is still counted, and the tile still reads the ruled word", async () => {
    mount("/accounts", {
      by_status: [
        { code: "active", name: "Active", accounts: 1 },
        { code: "pending_activation", name: "Pending activation", accounts: 0 },
        { code: "marked_disconnect", name: "Marked disconnect", accounts: 0 },
        // The utility calls it *Snowbird hold*. The COUNT follows the code.
        { code: "vacation_hold", name: "Snowbird hold", accounts: 9 },
      ],
    });
    await screen.findByRole("table");

    const suspended = tiles().find((tile) => tile.label === "Suspended");
    expect(suspended?.value).toBe("9");
    // The tile keeps the PO's one ruled word — the tenant's own name would
    // break the one-word ruling the first time a utility wrote a sentence into
    // a lookup row.
    expect(document.body.textContent).not.toContain("Snowbird");
  });

  /**
   * B14 rule 31 — nothing internal is ever a visible value, and a status
   * lookup row has a uuid. Read as TEXT, never as markup: the rule's own
   * sentence permits an internal value on `title`, so a check over the DOM
   * string would go red on a correct fix.
   */
  it("B14 rule 31 · rule 33: no code, no id, and no rationale on the strip", async () => {
    mount();
    await screen.findByRole("table");

    const strip = document.querySelector(".kpi-grid")?.textContent ?? "";
    expect(strip).not.toMatch(/[0-9a-f]{8}-[0-9a-f]{4}/);
    // The wire's own spellings are internal codes, not clerk-facing words.
    for (const code of ["vacation_hold", "marked_disconnect", "pending_activation"]) {
      expect(strip).not.toContain(code);
    }
    // RATIONALE is ZERO WORDS ON SCREEN: the strip never explains why a status
    // bills the way it does, or why a tile cannot be pressed.
    for (const why of ["because", "BR-", "DEF-", "OQ-"]) {
      expect(strip).not.toContain(why);
    }
  });

  /**
   * ⚠ **THE GROUP HAS A NAME.** Four unlabelled buttons in a row are unusable
   * without a mouse — the same finding B14 records against unlabelled row
   * actions, and the reason `AgeingCards` carries one too.
   */
  it("the strip announces itself as a named group of toggles", async () => {
    mount();
    await screen.findByRole("table");

    const group = screen.getByRole("group", { name: "Filter by status" });
    // `aria-pressed`, never `aria-selected`: these are toggles, not tabs, and a
    // screen reader announcing "tab" says the list will be REPLACED.
    expect(group.querySelectorAll("[aria-pressed]")).toHaveLength(4);
    expect(group.querySelectorAll("[aria-selected]")).toHaveLength(0);
  });
});
