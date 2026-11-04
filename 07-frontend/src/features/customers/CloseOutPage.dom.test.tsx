// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:   DEF-724 — the CLOSE-OUT act (PO 2026-08-27). r11 step 2c: these
//           cases were declared by BR-CUS-430/431 before this code existed.
// Rules:    BR-CUS-430 (a SEPARATE act) · BR-CUS-431 (`closed_at` is the CUT
//           date, shown BEFORE it is written) · BR-CUS-082 (a surviving debt
//           restarts the ladder) · DEF-127/DEF-628 (an unreadable figure is
//           NEVER a zero) · OQ-680 (no clearance is performed and the screen
//           says so) · OQ-830 (the reason has no fixed list)
// ───────────────────────────────────────────────────────
//
// ⚠ **TWO CASES BELOW ASSERT AN ABSENCE AND EACH CAN ONLY TAKE THAT FORM.**
//
//   · **the balance** — `$0.00` must not appear anywhere when the reading
//     failed. A test asserting "the cell shows the reason" would still pass on
//     a screen that ALSO printed a fabricated zero somewhere else, and a
//     fabricated zero on an account in arrears looks exactly like a settled
//     account (DEF-127).
//   · **the date** — the close-out DATE THE CLERK PICKS must never appear as
//     the account's closing date. That is the whole of BR-CUS-431, and the
//     wrong answer is a plausible-looking date rather than a crash.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import "@/i18n";

import { createApiClient } from "@/api/client";
import { ToastProvider } from "@/components/Toast";

import { CloseOutPage } from "./CloseOutPage";
import type { CloseOutEligibility } from "./closeOutEndpoints";
import type { AccountDetail } from "@/api/endpoints";

afterEach(cleanup);

const TEST_TENANT = "brazosbend";

/** `A-11488` — the account BR-CUS-110, DEF-724 and OQ-386 were all put with:
 *  cut **2026-08-18** owing **$612.75**, its unit already re-let. */
function eligible(overrides: Partial<CloseOutEligibility> = {}): CloseOutEligibility {
  return {
    account_id: "acc-11488",
    account_no: "A-11488",
    eligible: true,
    blocked_by: null,
    closed_at_will_be: "2026-08-18",
    cut_on: "2026-08-18",
    case_no: "DSC-26-0004",
    balance: { stored: "612.7500", display: "612.75" },
    balance_unreadable: false,
    currency: "USD",
    dunning_if_closed: {
      chased: true,
      restarts_at_tier: 1,
      escalates_to_disconnection: false,
      will_restart: true,
      reason:
        "a debt survives this closure, so BR-CUS-082 restarts the ladder at TIER 1 as a COLLECTIONS sequence.",
      subject: "the closed account itself",
      subject_detail: "no residue was tied back to anyone.",
      detail: "the debt is still chased and the ladder restarts at TIER 1.",
    },
    absences: [
      {
        code: "close_out_clearance_not_performed",
        tracks: "OQ-680",
        detail:
          "this act does not look up an active payment plan, an open dispute or an unbilled cycle, and it is not telling you they are clear.",
      },
      {
        code: "close_out_reason_vocabulary_unruled",
        tracks: "OQ-830",
        detail: "the close-out reason is FREE TEXT and no fixed list exists.",
      },
    ],
    ...overrides,
  };
}

/**
 * The ACCOUNT behind `A-11488`, as `GET /accounts/{id}` serves it.
 *
 * ⚠ **A SEPARATE FIXTURE, AND A SEPARATE ROUTE IN THE STUB, BECAUSE THE SCREEN
 * MAKES TWO READS AND ONE STUB FOR BOTH CANNOT TELL THEM APART.** Until
 * 2026-09-13 `mount` answered EVERY request with the eligibility payload, which
 * was harmless while the screen made one call and would have rendered the whole
 * drawn account panel as `not on file` the moment it made two — green, and over
 * nine empty rows.
 *
 * `as unknown as AccountDetail` because `AccountDetail` is a wide contract and
 * this screen reads nine of its fields; a full literal here would be forty
 * lines of values no assertion looks at, and each of them a figure a later
 * reader could mistake for a rule.
 */
function account(overrides: Partial<AccountDetail> = {}): AccountDetail {
  return {
    id: "acc-11488",
    account_no: "A-11488",
    customer_no: "C-00318",
    name: "Okafor, D.",
    unit_label: "Unit 2",
    premise: "77 Rio Grande",
    premise_locality: { city: "Silver Creek", state: "TX", postal_code: "78611" },
    services: ["electric", "water"],
    status: "disconnected",
    status_name: "Disconnected",
    status_behavior_class: "non_billable",
    account_type: "residential",
    account_subtype_name: "Standard",
    opened_at: "2021-06-03",
    currency: "USD",
    ...overrides,
  } as unknown as AccountDetail;
}

function mount(payload: CloseOutEligibility, detail: AccountDetail = account()): void {
  const client = createApiClient({
    tenant: TEST_TENANT,
    fetchImpl: async (input: RequestInfo | URL) => {
      const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
      // The close-out preview and the account read live one path segment
      // apart, so the stub routes on the SUFFIX rather than on call order —
      // react-query is free to fire them in either order and a stub that
      // counted calls would be a test that passes for the wrong reason.
      // THREE reads, not two: the screen also asks the platform category
      // catalogue, because B14 rule 31 forbids printing `residential` and the
      // NAME only exists there. A stub that answered it with an account made
      // the Category row silently empty — the row present, the value gone,
      // every assertion about the panel still green.
      const body = url.includes("categor")
        ? { selectable: [{ code: "residential", name: "Residential" }], legacy: [] }
        : url.endsWith("/close-out")
          ? payload
          : detail;
      return new Response(JSON.stringify(body), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    },
  });
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TEST_TENANT}/accounts/acc-11488/close-out`]}>
          <Routes>
            <Route
              path="/:tenant/accounts/:accountId/close-out"
              element={<CloseOutPage client={client} />}
            />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

describe("DEF-724 · the close-out screen", () => {
  it("shows the CUT date as the closing date, before anything is written", async () => {
    mount(eligible());
    // ⚠ **`08/18/2026`, NOT `2026-08-18` — the date goes through `DateCell`
    // since 2026-09-13.** This screen printed `closed_at_will_be` as the raw
    // ISO string the wire carries, so on a tenant whose Regional setting is
    // `DD/MM/YYYY` the one date no correction can un-say was the only date in
    // the product rendered in a format that tenant never chose (BR-SHL-034 —
    // one date formatter). The assertion moved with the screen; asserting the
    // ISO string was asserting the defect.
    // THREE times over, and that is the drawing: the roll-up says when service
    // was cut, the *What was cut* panel dates it, and *What pressing this
    // writes* names it as the date that will be written. `getAllByText` rather
    // than `getByText` — a screen that stopped showing two of the three would
    // still be telling the truth, and pinning the count here would go red on a
    // layout change instead of on a wrong date.
    await waitFor(() => expect(screen.getAllByText("08/18/2026").length).toBeGreaterThan(0));
    // BR-CUS-431 — the act's own date is a separate field the clerk fills in;
    // it must never be presented as the date the account closed.
    expect(document.body.textContent).not.toContain("2026-09-30");
    expect(document.body.textContent).not.toContain("09/30/2026");
  });

  it("renders the surviving balance WITH its currency, and the consequence in our words", async () => {
    mount(eligible());
    // ⚠ **`$612.75`, NOT `612.75` — `DEF-CUS-5087`.** This row printed the
    // server's `display` string bare, so a clerk read a number with no currency
    // on it while `currency` sat unused in the same payload. It goes through
    // `MoneyCell` now, which is the kit's one formatter and reads the 4 dp
    // `stored` figure and shows 2 (hard rule 2).
    await waitFor(() => expect(document.body.textContent).toContain("$612.75"));
    // ⚠ **THIS CASE ASSERTED `TIER 1` AND THAT WAS ASSERTING THE DEFECT.** The
    // screen printed `dunning_if_closed.reason` — a four-sentence paragraph
    // naming BR-CUS-082 and quoting the PO — and a passing test held it there.
    // The consequence is now DERIVED from `will_restart`, in two short
    // sentences, and the server's paragraph is evidence on `title`.
    expect(document.body.textContent).toContain("Chasing starts again");
    expect(document.body.textContent).not.toContain("BR-CUS-082");
  });

  it("NEVER prints $0.00 when the balance could not be read", async () => {
    mount(
      eligible({
        balance: null,
        balance_unreadable: true,
        dunning_if_closed: {
          ...eligible().dunning_if_closed,
          will_restart: null,
          reason: "the balance could not be read, so whether a ladder restarts cannot be answered.",
        },
      }),
    );
    await waitFor(() => expect(document.body.textContent).toContain("could not be read"));
    // DEF-127 — asserted over the WHOLE render, not over one cell.
    expect(document.body.textContent).not.toContain("0.00");
  });

  it("renders the refusal in the rule's own words and disables the commit", async () => {
    mount(
      eligible({
        eligible: false,
        blocked_by: {
          code: "still_occupying",
          message_key: "customers.account.close_out_still_occupying",
          br_ref: "BR-CUS-430 · BR-CUS-030",
          detail:
            "this account still occupies its unit, so its departure is a MOVE-OUT and must be filed as one.",
        },
      }),
    );
    // ⚠ **THE OLD ASSERTION WAS `toContain("must be filed as one")`** — the
    // server's own clause, so the test passed precisely BECAUSE the screen
    // piped engineering prose to the DOM. What a clerk must read is this
    // product's sentence; the server's stays available as `title` evidence.
    //
    // ⚠⚠ **AND IT IS ASSERTED ON THE STRIP, NOT ON `document.body` —
    // 2026-09-13, and this one nearly became a check that does not check.**
    // The screen now also draws the drawn *When it refuses* reference table,
    // which lists all six sentences whatever the server says. A `body`
    // assertion for *"This customer still holds the unit"* therefore passes
    // BEFORE the read resolves and would go on passing if the live refusal
    // stopped rendering altogether. `[data-refusal]` is the strip's own marker
    // and only the LIVE refusal carries it.
    await waitFor(() =>
      expect(document.querySelector("[data-refusal]")?.textContent).toContain(
        "This customer still holds the unit",
      ),
    );
    expect(document.body.textContent).not.toContain("MOVE-OUT and must be filed");
    expect(document.querySelector('[title*="must be filed as one"]')).toBeTruthy();
    const commit = screen.getByRole("button", { name: /close out this account/i });
    expect(commit.hasAttribute("disabled")).toBe(true);
  });

  it("states what it did NOT check, and cites the row that will close each sentence", async () => {
    mount(eligible());
    await waitFor(() =>
      expect(document.body.textContent).toContain("Nothing was checked for you"),
    );
    // G38's discipline pointed at a server payload: an absence names the
    // register row whose closure kills it, so it expires by itself. ⚠ It was
    // the ATTRIBUTE that mattered all along — `tracks` was ALSO being printed
    // as visible text, which is what rule 31 forbids, and this assertion was
    // green either way.
    expect(document.querySelector('[data-tracks="OQ-680"]')).toBeTruthy();
    expect(document.querySelector('[data-tracks="OQ-830"]')).toBeTruthy();
  });

  // ══════════════════════════════════════════════════════════════════════
  // THE CHECK THAT WOULD HAVE CAUGHT `DEF-CUS-5087`, AND WHY NONE EXISTED
  // ══════════════════════════════════════════════════════════════════════
  // Three of the cases above asserted the server's own prose was PRESENT, so
  // the suite was holding the defect in place rather than missing it. `G28`
  // enforces B14 rule 31, and it reads the eleven catalogues and the backend's
  // strings — it cannot see a component handing a payload field to the DOM.
  // `screenVoice.guard.test.tsx` does read rendered output and does exactly
  // this, for three OTHER screens; this screen was not among them, and its
  // absence is what let four paragraphs of rationale and nine internal ids onto
  // a clerk's screen the moment the transport was fixed.
  //
  // ⚠ READ AS `textContent`, NEVER AS MARKUP. Rule 31's own sentence puts the
  // internal value on `title` as evidence, so a check over `innerHTML` would go
  // RED on the correct fix and GREEN on the breach — which is the note B14
  // attaches to this rule, and it is easy to get backwards.
  it("puts no rule, question or defect id — and no engineering prose — in front of a clerk", async () => {
    mount(
      eligible({
        eligible: false,
        blocked_by: {
          code: "still_occupying",
          message_key: "customers.account.close_out_still_occupying",
          br_ref: "BR-CUS-430 · BR-CUS-030",
          detail:
            "this account still occupies its unit, so its departure is a MOVE-OUT and " +
            "must be filed as one, which is the same falsification BR-CUS-430 forbids.",
        },
      }),
    );
    // ⚠ **THE ANCHOR IS LOAD-BEARING AND THE FIRST DRAFT GOT IT WRONG.** It
    // waited for `"Close out account"` — the STATIC page title, present before
    // any request resolves — so the leak scan read an empty frame and passed.
    // Proved: reverting the blocker strip to the defective `{blocker.detail}`
    // left this case GREEN over a DOM carrying `BR-CUS-430`. Anchor on
    // something only the PAYLOAD can put on screen: the formatted balance.
    await waitFor(() => expect(document.body.textContent).toContain("$612.75"));
    // And the refusal strip is on screen — asserted by its own ATTRIBUTE, not
    // by any wording, so this anchor holds for the defective render and the
    // fixed one alike. Anchoring on our sentence would make THAT assertion the
    // one that fires and would leave the leak scan unproven.
    await waitFor(() => expect(document.querySelector("[data-refusal]")).toBeTruthy());
    const read = document.body.textContent ?? "";
    const leaks = [
      /\bBR-[A-Z]{3}-\d+/,      // a business-rule number
      /\bOQ-(?:[A-Z]{3}-)?\d+/,  // an open question
      /\bDEF-(?:[A-Z]{3}-)?\d+/, // a defect
      /\bUS-[A-Z]{3}-\d+/,      // a story
      /\bGT-\d+/,              // a golden test
      /\bACC-S\d+/,            // a blueprint specification
      /\bDSC-\d\d\.\d/,         // a screen-spec section
      /accounts\.[a-z_]+/,      // a database column
      /\bPROPOSED-SCHEMA\b/,
    ];
    const found = leaks.filter((re) => re.test(read)).map((re) => String(re));
    expect(found).toEqual([]);
  });

  // ══════════════════════════════════════════════════════════════════════════
  // THE DRAWING — `blueprint/10-close-out.md` → `09-…-standalone.md`, pp 107–111
  // ══════════════════════════════════════════════════════════════════════════
  // ⚠ **NOT ONE OF THESE CASES ASSERTS A FIGURE FROM THE DRAWING** (B14 rule
  // 37 — a number in a wireframe is an ILLUSTRATION). Every value checked below
  // comes from THIS FILE'S fixture, which is the test's own and not the
  // blueprint's. What IS asserted from the drawing is its LABELS and their
  // ORDER, because that is what rule 41 makes binding.

  it("draws the nine rows of `The account you are closing`, in the drawn order", async () => {
    mount(eligible());
    await waitFor(() => expect(screen.getByText("Okafor, D.")).toBeTruthy());
    const labels = [
      "Account number",
      "Customer number",
      "Category",
      "Status now",
      "Service address",
      "Opened",
    ];
    const read = document.body.textContent ?? "";
    for (const label of labels) expect(read).toContain(label);
    // ORDER is part of the design, not a detail — a panel with every drawn row
    // in the wrong sequence is a different panel.
    const at = labels.map((label) => read.indexOf(label));
    expect(at).toEqual([...at].sort((a, b) => a - b));
    // The account's own values, wired from `GET /accounts/{id}` — the read that
    // existed all along and that this screen never made (hard-won law 2).
    expect(read).toContain("C-00318");
    expect(read).toContain("Residential · Standard");
    expect(read).toContain("Disconnected");
    expect(read).toContain("77 Rio Grande, Silver Creek, TX, 78611");
  });

  it("shows the services as this product's badges and never as their codes", async () => {
    mount(eligible({ services_cut: ["electric", "water"] }));
    await waitFor(() => expect(screen.getByText("Services cut")).toBeTruthy());
    // B14 rule 31 — a service CODE is an internal value. `electric` on screen
    // is the same class of leak as a database id, and it is what the wire
    // carries in both `services` and `services_cut`.
    const read = document.body.textContent ?? "";
    expect(read).not.toContain("electric");
    expect(read).not.toContain("water");
  });

  it("states the two figures billing cannot give, and never prints a zero for them", async () => {
    mount(eligible());
    await waitFor(() => expect(screen.getByText("Final metered bill")).toBeTruthy());
    const read = document.body.textContent ?? "";
    // Billing has no invoices table. A dash reads as "nothing"; `$0.00` on a
    // final bill nobody raised is invented money (CLAUDE.md hard rule 2).
    expect(read).toContain("Final metered bill");
    expect(read).toContain("not served");
    expect(read).not.toContain("$0.00");
    expect(read).toContain("Base charges since");
  });

  it("says what one press writes, and dates it from the CUT and not from today", async () => {
    mount(eligible());
    await waitFor(() => expect(screen.getByText("What pressing this writes")).toBeTruthy());
    const read = document.body.textContent ?? "";
    for (const row of [
      "The date the account closed",
      "The account's status",
      "Every open service agreement",
      "The disconnection case",
      "The record of the act",
    ]) {
      expect(read).toContain(row);
    }
    // BR-CUS-431 in one assertion: the value beside the drawn row is the cut
    // date the server sent, and the clerk's own date is nowhere near it.
    expect(read).toContain("The cut date, not today");
  });

  it("lists the six ways it refuses, whether or not one of them is live", async () => {
    // The eligible payload — nothing is refusing, and the reference table is
    // still drawn, because the drawing draws it as a reference rather than as
    // a state. `[data-refusal]` proves the LIVE strip is absent here, which is
    // the distinction the sibling case above turns on.
    mount(eligible());
    await waitFor(() => expect(screen.getByText("When it refuses")).toBeTruthy());
    const read = document.body.textContent ?? "";
    for (const cause of [
      "The account is already closed",
      "They still live there",
      "The supply was never cut",
      "Your date is before the cut",
      "You left the date empty",
      "You left the reason empty",
    ]) {
      expect(read).toContain(cause);
    }
    expect(document.querySelector("[data-refusal]")).toBeNull();
  });

  it("keeps every on-screen sentence inside B14 rule 33's caps", () => {
    // ⚠ **THIS IS THE ONE CHECK THAT COULD NOT BE WRITTEN OVER THE OLD SCREEN
    // AND IS THE REASON THE DRAWN SENTENCES WERE NOT COPIED.** Four of the six
    // refusal sentences the blueprint draws run past six words a sentence —
    // *"Enter the date you are closing this account out."* is nine. A screen
    // built to the drawing character for character would breach a signed rule,
    // so the drawing's `IF` column is used verbatim and the answer column is
    // this product's own wording. This case is what stops a later lane
    // "restoring" the drawn sentences without noticing which rule they break.
    mount(eligible());
    const read = document.body.textContent ?? "";
    const facts = [
      "No. It was read at the cut.",
      "No. That is the payments side.",
      "No. Not on this screen.",
      "No. This was not a move.",
      "No. The balance survives it.",
      "Not earlier than the cut date.",
      "Enter the date you are closing.",
      "Say why it is being closed.",
      "A cut account is still open. It still owes money.",
      "Today, or the day you decided.",
      "A sentence, in your own words.",
    ];
    for (const sentence of facts) {
      // ⚠ **PRESENCE FIRST, THEN THE CAP — and the order is the whole point.**
      // A cap asserted over a literal list is a check that cannot fail: delete
      // every one of these sentences from the screen and it still passes. This
      // way the case goes red both when a sentence LEAVES and when one grows
      // past the cap, which are the two ways rule 33 is actually broken.
      expect({ sentence, onScreen: read.includes(sentence) }).toEqual({ sentence, onScreen: true });
      for (const part of sentence.split(/(?<=\.)\s+/)) {
        const words = part.trim().split(/\s+/).filter(Boolean);
        expect({ sentence, part, words: words.length }).toEqual({
          sentence,
          part,
          words: Math.min(words.length, 6),
        });
      }
    }
  });
});
