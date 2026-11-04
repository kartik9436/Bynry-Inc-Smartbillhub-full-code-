// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Tests:   the move-out record's ratified ACTION GRID, MOUNTED — PO 2026-09-20
//          (decision log §7). One case per row of the grid, asserting which
//          controls are on screen, their TIER, and each destination BY ADDRESS.
// Rules:   hard-won law 2's fixture clause (mount under the REAL
//          `/:tenant/...` pattern, or every address comes out
//          protocol-relative and `toContain` is satisfied by a link to another
//          host) · law 7 (proved RED first, under `vitest run`) · B14 rules 4,
//          6 and 11
// ───────────────────────────────────────────────────────
//
// ⚠ **WHY THIS EXISTS BESIDE `moveRecordActions.test.ts`, WHICH ALREADY TESTS
// THE GRID.** That file asks *"which controls does the RULE say exist"*; this
// one asks *"which controls are on the SCREEN, and where do they go"*. They
// are different questions and the second is the one the PO can see. A pure
// grid can be perfect while the page renders none of it — which is hard-won
// law 2's *built is not wired*, and it is exactly what happened to the
// customer portal's front page.
//
// ⚠ **WHAT WOULD MAKE THIS PASS WRONGLY**, asked before it was trusted:
//   * **A page that renders nothing.** Every case asserts the EXACT SET of
//     `data-action` values present, so an empty header fails rather than
//     satisfying a string of absence checks.
//   * **A href that lost its tenant.** `//accounts/...` contains
//     `/accounts/...`, so `toContain` passes on a link to another host. Every
//     address here is asserted with `toBe` against the full path, tenant
//     included.
//   * **A tier nobody reads.** The tier is asserted off `data-tier`, which the
//     renderer sets from the grid — and separately off the rendered `class`
//     for the danger control, because rule 6 is about what the button LOOKS
//     like and `data-tier` could be right while the class was wrong.
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { MoveRecordPage } from "./MoveRecordPage";
import type { MoveRecordDetail } from "./MoveRecordPage";
import { buttonClasses } from "@/components/Button";

afterEach(cleanup);

const TENANT = "brazosbend";
const ACCOUNT_ID = "acc-10432";
const MVO = "MVO-26-0088";

const NO_ACCOUNT = {
  code: "move_has_not_opened_an_account_yet",
  br_ref: "—",
  detail: "an account is what completing a move produces",
};

/** A COMPLETED move-out with both doors resolvable. */
function completedRecord(over: Partial<MoveRecordDetail> = {}): MoveRecordDetail {
  return {
    move_no: MVO,
    kind: "move_out",
    state: "completed",
    title: "Okafor, D.",
    address_line: "1408 Elm Street · Unit A",
    park_id: null,
    what_happened: {
      account_opened: { value: "A-10432", unavailable: null },
      from_account: { value: null, unavailable: NO_ACCOUNT },
      unit: { value: "1408 Elm Street · Unit A", unavailable: null },
      moved_in_on: { value: "2026-01-28", unavailable: null },
      earliest_legal_start: { value: null, unavailable: NO_ACCOUNT },
      close_reason: { value: null, unavailable: { ...NO_ACCOUNT, code: "close_reason_not_given" } },
      committed_by: { value: { name: "S. Ortiz", at: "2026-01-28" }, unavailable: null },
    },
    opening_reads: { unavailable: NO_ACCOUNT, rows: [] },
    money_taken: {
      required: { value: null, unavailable: NO_ACCOUNT },
      taken: { value: null, unavailable: NO_ACCOUNT },
      taken_on: null,
      tender: { value: null, unavailable: NO_ACCOUNT },
      still_to_collect: { value: null, unavailable: NO_ACCOUNT },
    },
    still_owed: {
      demand_register: { value: null, unavailable: NO_ACCOUNT },
      visit: { value: null, unavailable: NO_ACCOUNT },
      carry_forward: { value: null, unavailable: NO_ACCOUNT },
    },
    doors: {
      account: { value: { account_id: ACCOUNT_ID, account_no: "A-10432" }, unavailable: null },
      customer: { value: { customer_id: "cus-1", name: "Okafor, D." }, unavailable: null },
    },
    chips: { unread_registers: 0, reads_committed: 3 },
    ...over,
  } as MoveRecordDetail;
}

/**
 * The SHORT settlement of p118, **in `close-impact`'s OWN WIRE SHAPE** —
 * `everything_outstanding.total`, `what_is_applied.total`, `verdict.shortfall`,
 * each a `{stored, display}` money cell.
 *
 * ⚠ **THE RAW SHAPE AND NOT THE MAPPED ONE, DELIBERATELY.** Seeding the cache
 * with an already-mapped object would make this suite pass over a broken
 * `readMoveOutSettlement` — and that mapper is where `DEF-669` records that an
 * unmapped field arrives `undefined` and renders as a figure nobody measured.
 * Handing the reader the server's own shape keeps the mapping under test.
 */
function shortImpact() {
  const cell = (display: string) => ({ stored: `${display}00`, display });
  return {
    currency: "USD",
    landing: "short",
    complete: true,
    gaps: [],
    everything_outstanding: { total: cell("336.40") },
    what_is_applied: { total: cell("150.00") },
    verdict: { shortfall: cell("186.40") },
    shortfall_paths: [
      { path: "collect", enabled: true, reason: null },
      { path: "payment_plan", enabled: true, reason: null },
      { path: "transfer", enabled: true, reason: null },
    ],
    unit_falls_to: { available: true, account_no: "A-10001", reason: null },
  };
}

/** A settlement that landed SETTLED — nothing to place. */
function settledImpact() {
  return { ...shortImpact(), landing: "settled", verdict: { shortfall: null } };
}

/**
 * Mount at the REAL address pattern, with both queries seeded.
 *
 * ⚠ **`/:tenant/moves/:ref` AND NOT A BARE ROUTER.** A bare `MemoryRouter`
 * leaves `useParams().tenant` undefined, so `tenantPath` builds `//accounts/…`
 * — a protocol-relative URL to ANOTHER HOST that still contains
 * `/accounts/…` and satisfies every `toContain`. That fixture flaw hid two
 * working doors out of eight on the customer portal's front page for days.
 */
function mount(detail: MoveRecordDetail, impact: unknown | null, post = vi.fn()) {
  // ⚠ **URL-AWARE, BECAUSE A COMMIT INVALIDATES AND THE PAGE REFETCHES.** The
  // first draft answered `{}` to every GET; the settle mutation invalidated,
  // React Query re-ran the REAL `queryFn`, and the page crashed on
  // `record.chips` — which is the suite finding a real behaviour rather than a
  // fixture bug, so the fixture now answers what the server would.
  const client = {
    get: vi.fn(async (url: string) => {
      if (url.includes("/close-impact")) return { status: 200, data: impact ?? {} };
      return { status: 200, data: detail };
    }),
    post,
    delete: vi.fn(async () => ({ status: 204, data: null })),
  } as never;
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  qc.setQueryData(["move-record", detail.move_no ?? ""], detail);
  render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[`/${TENANT}/moves/${detail.move_no}`]}>
        <Routes>
          <Route
            path="/:tenant/moves/:ref"
            element={<MoveRecordPage client={client} timeZone="UTC" dateFormat="MM/DD/YYYY" />}
          />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return { post };
}

/**
 * Wait until the control this case is about is on screen.
 *
 * ⚠ **WAITING ON THE TITLE WAS NOT ENOUGH, AND THAT IS LAW 7's `LOOKING AT THE
 * WRONG THING`.** The record and the settlement are TWO queries; the title
 * arrives with the first and every money control with the second. A
 * `waitFor(title)` therefore passed while the options were still absent, and
 * four cases failed for a reason that had nothing to do with the grid. Each
 * case now waits for its own subject.
 */
async function waitForAction(id: string) {
  await waitFor(() =>
    expect(document.querySelector(`[data-action="${id}"]`)).toBeInTheDocument(),
  );
}

/**
 * Press the confirm button INSIDE the open dialog.
 *
 * ⚠ **SCOPED TO THE DIALOG BECAUSE THE TWO BUTTONS SHARE ONE NAME, AND THAT
 * IS THE FEATURE RATHER THAN A CLASH.** PO 2026-09-20 §7 finding (a) is that
 * one act had four spellings; the fix points the trigger and the confirm at
 * ONE catalogue key, so `getByRole("button", {name: /Tie to master/})` now
 * finds two elements and refuses — which is the rule holding, proved by a
 * selector that could not have failed before it landed.
 */
async function confirmInDialog(name: RegExp) {
  const dialog = await screen.findByRole("alertdialog");
  await userEvent.click(within(dialog).getByRole("button", { name }));
}

/** Every control the header is showing, in DOM order, as `data-action` ids. */
function actionsOnScreen(): string[] {
  return Array.from(document.querySelectorAll("[data-action]")).map(
    (el) => el.getAttribute("data-action") ?? "",
  );
}

function tierOf(action: string): string | null {
  return document.querySelector(`[data-action="${action}"]`)?.getAttribute("data-tier") ?? null;
}

function hrefOf(action: string): string | null {
  return document.querySelector(`[data-action="${action}"]`)?.getAttribute("href") ?? null;
}

// ════════════════════════════════════════════════════════════════════════════
// THE GRID, ON SCREEN, ROW BY RATIFIED ROW
// ════════════════════════════════════════════════════════════════════════════
describe("Completed · settled — the three doors and nothing else", () => {
  it("shows exactly the doors, at the ratified tiers", async () => {
    mount(completedRecord(), settledImpact());
    await waitForAction("openAccount");
    // `Open the request →` is ABSENT because this move-out came from no
    // request — the ratified exception to BR-SHL-025, and today it is absent
    // on every record (`DEF-CUS-6001`).
    // The head draws `leadingAction`, then `secondaryActions`, then
    // `primaryAction`; neither door is primary here, so both sit in the
    // secondary slot IN THE RATIFIED GRID ORDER.
    expect(actionsOnScreen()).toEqual(["openAccount", "openCustomer"]);
    expect(tierOf("openAccount")).toBe("secondary");
    expect(tierOf("openCustomer")).toBe("ghost");
  });

  it("points the account door at the REAL address, tenant included", async () => {
    mount(completedRecord(), settledImpact());
    await waitForAction("openAccount");
    // ⚠ `toBe`, never `toContain`: `//accounts/acc-10432` CONTAINS
    // `/accounts/acc-10432` and points at another host.
    expect(hrefOf("openAccount")).toBe(`/${TENANT}/accounts/${ACCOUNT_ID}`);
  });

  it("offers NO money control when nothing is short", async () => {
    mount(completedRecord(), settledImpact());
    await waitForAction("openAccount");
    for (const id of ["tieBack", "collect", "paymentPlan"]) {
      expect(actionsOnScreen()).not.toContain(id);
    }
  });
});

describe("Completed · short, UNDECIDED — the three doors plus the three options", () => {
  it("shows the doors and every option, at the ratified tiers", async () => {
    mount(completedRecord(), shortImpact());
    await waitForAction("tieBack");
    expect([...actionsOnScreen()].sort()).toEqual(
      ["collect", "openAccount", "openCustomer", "paymentPlan", "tieBack"].sort(),
    );
    expect(tierOf("tieBack")).toBe("primary");
    expect(tierOf("collect")).toBe("secondary");
    expect(tierOf("paymentPlan")).toBe("secondary");
  });

  it("PO 2026-10-12 — offers NO write-off and no danger control on a completed record", async () => {
    // *"we will not write off at the time of move out; these charges remain
    // outstanding on the account and followup is done as per outstanding
    // rules"*. The server refuses `write_off` by name, so a `Write it off ✓`
    // here would be a live control over a refusing door.
    mount(completedRecord(), shortImpact());
    await waitForAction("tieBack");
    expect(document.querySelector('[data-action="writeOff"]')).toBeNull();
    expect(document.querySelector(`[class="${buttonClasses("danger")}"]`)).toBeNull();
    expect(screen.queryByText(/Write it off/)).toBeNull();
  });

  it("sends `+ Payment plan` to S24's creator, BY ADDRESS", async () => {
    mount(completedRecord(), shortImpact());
    await waitForAction("tieBack");
    expect(hrefOf("paymentPlan")).toBe(`/${TENANT}/accounts/${ACCOUNT_ID}/payment-plan`);
  });

  it("marks the grammar B14 rule 4 asks for, on the label a clerk reads", async () => {
    mount(completedRecord(), shortImpact());
    await waitForAction("tieBack");
    const text = (id: string) =>
      document.querySelector(`[data-action="${id}"]`)?.textContent ?? "";
    expect(text("openAccount")).toMatch(/→$/); // navigates
    expect(text("tieBack")).toMatch(/✓$/); // commits
    expect(text("collect")).toMatch(/✓$/); // commits
    expect(text("paymentPlan")).toMatch(/^\+ /); // creates
  });
});

// ════════════════════════════════════════════════════════════════════════════
// B14 RULE 11 — THE CONSEQUENCE PREVIEW, AND WHAT IT IS ALLOWED TO PROMISE
// ════════════════════════════════════════════════════════════════════════════
describe("a money commit shows what it will do, before it does it", () => {
  it("opens a consequence box that says the amount moves to the owner's account", async () => {
    mount(completedRecord(), shortImpact());
    await waitForAction("tieBack");
    await userEvent.click(document.querySelector('[data-action="tieBack"]')!);
    // p118 draws `$186.40 moves to A-10001 and A-10432 settles at zero`.
    // 🔒 `OQ-1250` CLOSED 2026-10-14 → (a), PO D5: the tie-back POSTS one
    // AR→AR entry, so *moves to* is now a fact the product keeps (this case
    // asserted *"The books do not move yet"* until then). *Settles at zero* is
    // still not promised — it depends on what else the account owes.
    const dialog = await screen.findByRole("alertdialog");
    expect(dialog).toHaveTextContent(/\$186\.40 moves to A-10001 now\./);
    expect(screen.queryByText(/do not move/)).toBeNull();
    expect(screen.queryByText(/settles at zero/)).toBeNull();
  });

  it("shows the shortfall WITH ITS CURRENCY, not a bare number", async () => {
    // ⚠ **THIS CASE EXISTS BECAUSE A BROWSER FOUND THE DEFECT AND NOTHING
    // ELSE DID.** Every other figure on this screen goes through `MoneyCell`,
    // which adds the symbol; a dialog TITLE is a plain string, so the server's
    // `display` — `186.40`, symbol-less by design — went straight into it and
    // the live page read `Tie 186.40 back?` on a money commit. `tsc` cannot
    // see it, no gate reads rendered output, and the assertions that existed
    // matched on the number. Hard-won law 6.
    mount(completedRecord(), shortImpact());
    await waitForAction("tieBack");
    await userEvent.click(document.querySelector('[data-action="tieBack"]')!);
    const dialog = await screen.findByRole("alertdialog");
    expect(dialog).toHaveTextContent("$186.40");
  });

  it("names the account that starts being chased", async () => {
    mount(completedRecord(), shortImpact());
    await waitForAction("tieBack");
    await userEvent.click(document.querySelector('[data-action="tieBack"]')!);
    // `A-10001` is `unit_falls_to.account_no` — a user-facing reference, never
    // a uuid (B14 rule 31).
    expect(await screen.findByText(/A-10001 is chased from now/)).toBeInTheDocument();
  });

  it("posts ONE settle-shortfall for the disposition the clerk chose", async () => {
    // ⚠ **THE ARGUMENT TYPES ARE DECLARED, AND THAT IS NOT TIDINESS.** A bare
    // `vi.fn()` gives `mock.calls` the tuple type `[]`, so `calls[0][0]` is a
    // TYPE ERROR — which `vitest` never sees, because it does not type-check.
    // The first draft was green under the harness and red under `tsc`: a case
    // that passes while the file it lives in cannot compile.
    const post = vi.fn<(url: string, body: unknown) => Promise<{ status: number; data: object }>>(
      async () => ({ status: 200, data: {} }),
    );
    mount(completedRecord(), shortImpact(), post);
    await waitForAction("tieBack");
    await userEvent.click(document.querySelector('[data-action="tieBack"]')!);
    await confirmInDialog(/Tie to master/);
    await waitFor(() => expect(post).toHaveBeenCalledTimes(1));
    // ⚠ The ONE settlement path — `move_out_settlement.shortfall_decision`,
    // through the caller `MoveOutWizard.tsx` already publishes. A second one
    // would be two code paths deciding one customer's closing money.
    expect(post.mock.calls[0][0]).toBe(`/accounts/${ACCOUNT_ID}/settle-shortfall`);
    expect(post.mock.calls[0][1]).toEqual({ path: "transfer" });
  });

  it("turns the three options into a SENTENCE once one is chosen", async () => {
    const post = vi.fn(async () => ({ status: 200, data: {} }));
    mount(completedRecord(), shortImpact(), post);
    await waitForAction("tieBack");
    await userEvent.click(document.querySelector('[data-action="collect"]')!);
    await confirmInDialog(/Follow the customer/);
    // PO §7: *"once decided they become a sentence"*.
    expect(await screen.findByTestId("move-record-decided")).toHaveTextContent(
      "The customer still owes it.",
    );
    // …and the screen says, in five words, that a reload forgets it
    // (`OQ-CUS-12516`) rather than claiming a settlement it cannot produce.
    expect(screen.getByTestId("move-record-decided-not-kept")).toHaveTextContent(
      "Reopens if you leave.",
    );
    await waitFor(() => expect(actionsOnScreen()).not.toContain("collect"));
  });
});

// ════════════════════════════════════════════════════════════════════════════
// IN FLIGHT
// ════════════════════════════════════════════════════════════════════════════
describe("In flight — Resume and Discard, and no account door", () => {
  const parked = () =>
    completedRecord({
      state: "in_flight",
      park_id: "park-7",
      doors: {
        account: { value: null, unavailable: NO_ACCOUNT },
        customer: { value: null, unavailable: NO_ACCOUNT },
      },
    } as Partial<MoveRecordDetail>);

  it("shows exactly Resume and Discard draft, at the ratified tiers", async () => {
    mount(parked(), null);
    await waitForAction("resume");
    expect([...actionsOnScreen()].sort()).toEqual(["discardDraft", "resume"]);
    expect(tierOf("resume")).toBe("primary");
    expect(tierOf("discardDraft")).toBe("danger");
  });

  it("carries the clerk back into the wizard at the parked draft, BY ADDRESS", async () => {
    mount(parked(), null);
    await waitForAction("resume");
    // ⚠ The address is `resumePath`'s, the ONE builder for `?parked=<id>`,
    // and it is asserted with `toBe` so a tenant-less `//move-outs/new?...`
    // — which points at another host and still satisfies `toContain` — fails.
    expect(hrefOf("resume")).toBe(`/${TENANT}/move-outs/new?parked=park-7`);
  });

  it("asks before discarding, and says what is lost", async () => {
    mount(parked(), null);
    await waitForAction("resume");
    await userEvent.click(document.querySelector('[data-action="discardDraft"]')!);
    expect(await screen.findByText(/The parked move-out is deleted/)).toBeInTheDocument();
  });
});
