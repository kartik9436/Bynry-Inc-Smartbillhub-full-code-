// ── Trace ──────────────────────────────────────────────
// Change:   The TRANSFER RECORD screen (blueprint p132), approved by the PO
//           2026-09-20 — *"buildit - use drawing images. screens hosuld match
//           exactly to drawing"*. TWO doors and no action.
// Rules:    B14 rule 31 (no database id is ever a field's visible value) ·
//           rule 33 (rationale is ZERO words on screen) · `BR-CUS-085` (the
//           deposit is not refunded and re-collected) · hard-won law 2 and its
//           mirror · `DEF-127` (an absence and an empty cell are
//           indistinguishable once drawn)
// ───────────────────────────────────────────────────────
/**
 * What this file holds the SCREEN to — the things a browser walk cannot
 * re-check on every commit, and that no other check in the repo can see.
 *
 * **1 · A MONEY CLAIM WEARING A ZERO.** `Refunded to seller` and `Re-collected
 * from buyer` MUST read `$0.00` — that pair is `BR-CUS-085` and it is the
 * reason this screen exists. `Deposit interest`, `Fees charged` and `Taken on`
 * must NEVER read `$0.00` when nothing computed them. Both directions are
 * asserted, and the zero is COUNTED rather than searched for, because
 * `toContain("$0.00")` passes just as happily over four of them as over two.
 *
 * **2 · THE PAGE GROWING AN ACTION.** The blueprint's ruling — *"This record
 * has no actions"* — is the kind of thing a later lane "improves". Asserted as
 * a count of controls, not as a subset, because a subset assertion passes
 * while a third button is added.
 *
 * **3 · AN ABSENCE RENDERED AS A BLANK.** The server distinguishes *"no number
 * series has issued one"* from *"the seller was not kept"* from *"nothing
 * counts unbroken months"*. A screen that drew a dash for all three would
 * throw that away at the last step, and `tsc` cannot see it because every one
 * of them is a valid `TransferFact`. Asserted on the WORDS a person reads.
 *
 * **4 · RATIONALE LEAKING ONTO THE SCREEN.** The server's `detail` sentences
 * explain WHY a fact is missing; B14 rule 33 puts rationale at zero words on
 * screen. They ride in `title` — machine-reachable, not read aloud — so this
 * file borrows `MoveRecordPage.test.tsx`'s `visibleText` helper, which exists
 * because the naive `html.includes(...)` was wrong twice in exactly this way.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import {
  TransferRecordPage,
  TRANSFER_RECORD_ROUTE,
  TRANSFER_RECORD_SCREEN,
  transferRecordPath,
} from "./TransferRecordPage";
import type { TransferAbsence, TransferRecordDetail } from "./TransferRecordPage";
// ⚠ **THE ROUTE CONSTANTS AND THE PATH BUILDERS, IMPORTED RATHER THAN
// RETYPED.** The door assertions below check the built address against the
// SAME builder `App.tsx` mounts the account detail at, so a test cannot go on
// passing while the page and the router disagree about where an account lives
// — the shape that let a hold-expiry test assert one address while the router
// used another (hard-won law 7, *looking at the wrong thing*).
import { accountDetailPath } from "./customersShared";
import { CUSTOMERS_ROUTE } from "./CustomersListPage";
import { TRANSFER_WIZARD_ROUTE } from "./transferDisconnectShared";

/**
 * The rendered TEXT — every tag and attribute stripped, leaving only what a
 * person actually reads.
 *
 * ⚠ **THE ABSENCE SENTENCES RIDE IN `title=`**, so a raw `html.includes(...)`
 * finds the rationale inside the very attribute that keeps it off the screen —
 * and the assertion that rule 33 is obeyed would pass or fail for the wrong
 * reason. A test that cannot tell a string being SHOWN from a string being
 * carried as machine data is not testing the thing it names.
 */
function visibleText(html: string): string {
  // ⚠ **THE ENTITIES ARE DECODED, AND THAT IS NOT TIDINESS.**
  // `renderToStaticMarkup` writes an apostrophe as `&#x27;`, so *"Still the
  // seller's"* — a string this screen genuinely renders — is invisible to a
  // `toContain` over the raw markup. The first run of this file failed on
  // exactly that and the SCREEN was right: law 7's *looking at the wrong
  // thing*, caught by the assertion rather than by the code under it. A
  // helper that cannot read what a person reads is not reading the screen.
  return html
    .replace(/<[^>]*>/g, " ")
    .replace(/&#x27;|&#39;/g, "'")
    .replace(/&quot;/g, '"')
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&amp;/g, "&");
}

const ABSENT = (code: string, detail: string): TransferAbsence => ({ code, detail });

const NO_SERIES: TransferAbsence = {
  code: "numbering_series_missing",
  series: "transfer",
  open_question: "OQ-426",
  detail:
    "This transfer has no reference number yet. A number series for transfers has not " +
    "been set up, so nothing has been issued — the job is complete and only its " +
    "reference is missing.",
};

const SELLER_GONE = ABSENT(
  "seller_not_kept_after_reassignment",
  "reassign_account removes the seller's customer_accounts link, so the seller survives " +
    "only in audit_log, which is pruned on a retention schedule.",
);

const INTEREST_AT_SETTLEMENT = ABSENT(
  "deposit_interest_not_computed",
  "Deposit interest is computed at settlement (PO ruling 2026-09-19); nothing accrues it " +
    "on the day of a sale.",
);

const LEDGER_NOT_COUNTED = ABSENT(
  "unbroken_ledger_months_not_counted",
  "Nothing in this product counts how many unbroken months an account's ledger runs.",
);

function sold(over: Partial<TransferRecordDetail> = {}): TransferRecordDetail {
  return {
    state: "completed",
    reference: { value: "TRF-26-0001", unavailable: null },
    // ⚠ Rule 37 — every figure and every name here is an ILLUSTRATION taken
    // from p132's drawing, never a tenant's data.
    seller_name: { value: "Tan, Wei", unavailable: null },
    buyer_name: { value: "Ferraro, L.", unavailable: null },
    what_happened: {
      account: { value: "A-11455", unavailable: null },
      unit: { value: "1408 Elm Street · Unit B", unavailable: null },
      service_address: { value: "1408 Elm Street, Silver Creek, TX 78611", unavailable: null },
      sold_on: { value: "2026-05-07", unavailable: null },
      sold_by: { value: "Tan, Wei · C-00344", unavailable: null },
      sold_to: { value: "Ferraro, L. · C-00877", unavailable: null },
      buyer_kind: { value: "person", unavailable: null },
      identifier_given: { value: "driving_licence", unavailable: null },
      buyer_matched: { value: "matched", unavailable: null },
      changeover_read: { value: { raised: 2, completed: 2, on: "2026-05-07" }, unavailable: null },
      committed_by: { value: { name: "S. Ortiz", at: "2026-05-07T14:06:00Z" }, unavailable: null },
    },
    unchanged: {
      account_no: { value: "A-11455", unavailable: null },
      status: { value: "active", unavailable: null },
      ledger_months: { value: null, unavailable: LEDGER_NOT_COUNTED },
    },
    money: {
      currency: "USD",
      balance: { value: "64.2000", unavailable: null },
      deposit: { value: "150.0000", unavailable: null },
      deposit_interest: { value: null, unavailable: INTEREST_AT_SETTLEMENT },
      taken_on: { value: "64.2000", unavailable: null },
    },
    doors: {
      account: { value: { account_id: "acc-uuid-1", account_no: "A-11455" }, unavailable: null },
      customer: { value: { customer_id: "cus-uuid-1", name: "Ferraro, L." }, unavailable: null },
    },
    ...over,
  };
}

/**
 * Render the page at its REAL address pattern.
 *
 * ⚠ **MOUNTED UNDER `/:tenant/transfers/:ref`, NOT BARE** — hard-won law 2's
 * fixture clause, which cost the customer portal a whole front page of broken
 * links. A component mounted inside a `MemoryRouter` with no matching route
 * gets `undefined` for every param, so every address it builds comes out
 * `//transfers/…` — a protocol-relative URL to another host that reads as a
 * perfectly good string to `toContain`. Mounting under the real pattern is the
 * only way the link assertions below mean anything.
 *
 * ⚠ **THE CACHE IS SEEDED, BECAUSE `renderToStaticMarkup` IS SYNCHRONOUS.** A
 * `useQuery` cannot resolve inside one pass, so an unseeded helper renders the
 * LOADING SKELETON and every assertion fails against it — or worse, passes,
 * if the assertions are loose enough to hold over a skeleton. Seeding the
 * exact key the page reads is what makes the rendered markup the thing under
 * test.
 */
function render(detail: TransferRecordDetail, ref = "TRF-26-0001"): string {
  const client = { get: async () => ({ status: 200, data: detail }) } as never;
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  qc.setQueryData(["transfer-record", ref], detail);
  return renderToStaticMarkup(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[`/brazosbend${transferRecordPath(ref)}`]}>
        <Routes>
          <Route
            path={`/:tenant${TRANSFER_RECORD_ROUTE}`}
            element={<TransferRecordPage client={client} timeZone="UTC" dateFormat="MM/DD/YYYY" />}
          />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("the transfer record's address", () => {
  it("is a reference and never a uuid", () => {
    // B14 rule 31 — the URL a clerk copies is the NUMBER, and `OQ-426` closed
    // on 2026-08-27 so there IS one: `TRF-26-0001`.
    expect(transferRecordPath("TRF-26-0001")).toBe("/transfers/TRF-26-0001");
    expect(transferRecordPath("TRF-26-0001")).not.toContain("uuid");
  });

  it("sits beside the wizard and never under /accounts", () => {
    expect(TRANSFER_RECORD_ROUTE).toBe("/transfers/:ref");
    expect(transferRecordPath("TRF-26-0001")).not.toContain("/accounts/");
  });

  it("cannot swallow `/transfers/new`", () => {
    // The wizard's address is a STATIC segment; React Router ranks it above
    // `:ref` and `App.tsx` declares it first as well. This asserts the two are
    // different addresses rather than one pattern eating the other — the trap
    // `App.tsx` carries a comment about, and DEF-520 is a sibling meeting it.
    expect(TRANSFER_WIZARD_ROUTE).toBe("/transfers/new");
    expect(TRANSFER_WIZARD_ROUTE).not.toContain(":");
    expect(transferRecordPath("new")).toBe(TRANSFER_WIZARD_ROUTE);
  });

  // ⛔ **THE BREADCRUMB LEAF IS NOT ASSERTED HERE, AND THAT IS DELIBERATE.**
  // `useCrumbLeaf` publishes from an EFFECT, and `renderToStaticMarkup` runs no
  // effects — so a unit case here could only assert the fixture it was handed,
  // which is law 7's *check that cannot fail* wearing a test's name. The first
  // draft of this file had exactly that case and it is deleted rather than
  // kept. The leaf is asserted where it can actually be read: the browser walk
  // checks the top bar and the document title for the reference
  // (`10-scripts/po20260920_transfer_record_walkthrough.mjs`, walk 2).

  it("names the screen it opens", () => {
    // Law 2's mirror asks a door to be asserted BY ADDRESS and BY THE SCREEN
    // ID IT OPENS. This is the second half, so the day a list links here the
    // two assertions are already written.
    expect(TRANSFER_RECORD_SCREEN).toBe("S89.transferRecord");
  });
});

describe("the two doors, and nothing else", () => {
  it("carries exactly TWO controls", () => {
    // The blueprint: *"This record has no actions, and that is the answer
    // rather than a gap."* Counted, not sampled — a subset assertion passes
    // while somebody adds a third control.
    const html = render(sold());
    const testIds = [...html.matchAll(/data-testid="(transfer-record-[^"]+)"/g)].map((m) => m[1]);
    expect(new Set(testIds)).toEqual(
      new Set([
        "transfer-record-open-customer",
        "transfer-record-open-account",
        "transfer-record-banner",
        "transfer-record-money",
      ]),
    );
    // …and nothing on this page is pressable. Every control here is a DOOR.
    expect(html).not.toContain("<button");
  });

  it("opens the customer and the account under the tenant, never against another host", () => {
    const html = render(sold());
    const hrefs = [...html.matchAll(/href="([^"]*)"/g)].map((m) => m[1]);
    // The account door lands on the account DETAIL screen, at the address the
    // router mounts it at — the builder is imported, never retyped.
    expect(hrefs).toContain(`/brazosbend${accountDetailPath("acc-uuid-1")}`);
    // The customer door lands on the customers REGISTER filtered to that
    // person, because this product has no customer detail screen (the
    // divergence `MoveRecordPage` measured and recorded).
    expect(hrefs).toContain(`/brazosbend${CUSTOMERS_ROUTE}?q=${encodeURIComponent("Ferraro, L.")}`);
    // ⚠ the protocol-relative trap: an unrouted mount builds `//transfers/…`,
    // which reads as a perfectly good string to every other assertion here.
    for (const href of hrefs) {
      expect(href.startsWith("//")).toBe(false);
    }
  });

  it("states the absence rather than drawing a door onto nothing", () => {
    const html = render(
      sold({
        doors: {
          account: { value: null, unavailable: ABSENT("no_account", "the sale has no account.") },
          customer: { value: null, unavailable: ABSENT("no_customer", "no buyer is linked.") },
        },
      }),
    );
    const text = visibleText(html);
    expect(html).toContain("transfer-record-no-customer");
    expect(html).toContain("transfer-record-no-account");
    expect(text).toContain("No customer linked");
    expect(text).toContain("No account linked");
    // no door, and no invitation to make one
    expect(html).not.toContain("transfer-record-open-account");
    expect(html).not.toContain("transfer-record-open-customer");
  });
});

describe("the money box — `BR-CUS-085` in two rows", () => {
  it("reads $0.00 for the refund and the re-collection EVEN WHEN THE SERVER SENDS NEITHER", () => {
    // *"This customer is not leaving. Their deposit, their discounts and their
    // history move with them — nothing is refunded and re-collected."* The
    // rule guarantees it (`refund_raised: False`), so the figure is the rule's
    // and rendering an absence here would say *"we did not check"* about the
    // one fact this screen exists to prove.
    const text = visibleText(render(sold()));
    expect(text).toContain("Refunded to seller");
    expect(text).toContain("Re-collected from buyer");
    const zeros = [...text.matchAll(/\$0\.00/g)].length;
    // EXACTLY two. Counted rather than searched for: `toContain("$0.00")`
    // passes just as happily over four zeros as over two, and the other four
    // money rows going to zero is the defect this whole file is about.
    expect(zeros).toBe(2);
  });

  it("never draws a zero where nothing computed a figure", () => {
    const text = visibleText(render(sold()));
    // deposit interest — the PO ruled it is computed AT SETTLEMENT, so on the
    // day of a sale there is nothing to show. A zero here is wrong by $3.50 on
    // a $150.00 deposit held fourteen months, AGAINST the customer.
    expect(text).toContain("Counted at settlement");
    // fees — a WORD, not a zero: "no fee was charged" and "a fee of nothing
    // was charged" are different sentences.
    expect(text).toContain("Fees charged");
    expect(text).toContain("None");
  });

  it("states an absence for the total rather than adding the rows up", () => {
    // ⛔ The screen does no arithmetic on money (CLAUDE.md hard rule 2). With
    // no served total there is no total, and $64.20 must NOT appear from the
    // balance being re-used as the answer.
    const detail = sold();
    const text = visibleText(
      render({
        ...detail,
        money: {
          ...detail.money,
          taken_on: { value: null, unavailable: ABSENT("no_total", "nothing totals this.") },
        },
      }),
    );
    expect(text).toContain("Taken on");
    expect(text).toContain("Not recorded");
    // the balance is still drawn; the TOTAL is not invented from it
    expect(text).toContain("$64.20");
    expect([...text.matchAll(/\$64\.20/g)].length).toBe(1);
  });

  it("prints money to two decimals however many it is stored to", () => {
    // CLAUDE.md hard rule 2 — stored to 4, displayed to 2.
    const text = visibleText(render(sold()));
    expect(text).toContain("$150.00");
    expect(text).not.toContain("150.0000");
  });
});

describe("what the product cannot say yet", () => {
  it("renders the buyer alone when the seller was not kept, and never an arrow onto a dash", () => {
    // `reassign_account` removes the seller's link and `audit_log` is pruned;
    // the PO ruled on 2026-09-20 that this must stop, and the shape that
    // follows is not built. Until it is, the title degrades honestly.
    const detail = sold();
    const html = render({
      ...detail,
      seller_name: { value: null, unavailable: SELLER_GONE },
      what_happened: { ...detail.what_happened, sold_by: { value: null, unavailable: SELLER_GONE } },
    });
    const text = visibleText(html);
    expect(text).toContain("Ferraro, L.");
    expect(text).not.toContain("→ Ferraro, L.");
    expect(text).toContain("Seller not kept");
    // and the reason is reachable without being read aloud (rule 33)
    expect(html).toContain("pruned on a retention schedule");
    expect(text).not.toContain("pruned on a retention schedule");
  });

  it("says the reference has not been issued rather than printing an empty kicker", () => {
    const html = render(sold({ reference: { value: null, unavailable: NO_SERIES } }), "TRF-26-0001");
    const text = visibleText(html);
    expect(text).toContain("No reference yet");
    // the server's forty-five-word explanation is machine-reachable and off
    // the screen — p132 draws it as a dashed panel and B14 rule 33 does not
    expect(html).toContain("A number series for transfers has not been set up");
    expect(text).not.toContain("A number series for transfers has not been set up");
  });

  it("says the ledger's length was never counted rather than drawing the drawn 38", () => {
    // B14 rule 37: a figure drawn in a wireframe is an ILLUSTRATION. p132
    // draws `One continuous history, 38 months` and nothing in this product
    // counts unbroken months.
    const text = visibleText(render(sold()));
    expect(text).toContain("Length not counted");
    expect(text).not.toContain("38 months");
  });

  it("never calls a COMPLETED sale's missing committer 'not committed yet' (DEF-CUS-6429)", () => {
    // Lane TRANSFER's own walk, TRF-26-0001: a done sale read *Committed by:
    // Not committed yet*. `transfers` keeps no committer, so a completed
    // record's absence is *Not recorded*; only an unfinished one's is *Not
    // committed yet*. The server sends the two different absences, and the
    // label follows the record's state.
    const NOT_STORED = ABSENT(
      "committed_by_not_stored",
      "`transfers` has no column for who committed the sale.",
    );
    const NOT_YET = ABSENT(
      "transfer_not_committed",
      "this sale has not been committed, so the facts it would record do not exist yet.",
    );
    const committedBy = (state: TransferRecordDetail["state"], absence: TransferAbsence) => {
      const detail = sold({ state });
      const text = visibleText(
        render({
          ...detail,
          what_happened: {
            ...detail.what_happened,
            committed_by: { value: null, unavailable: absence },
          },
        }),
      );
      const at = text.indexOf("Committed by");
      expect(at).toBeGreaterThan(-1);
      return text.slice(at, at + 60);
    };
    const done = committedBy("completed", NOT_STORED);
    expect(done).toContain("Not recorded");
    expect(done).not.toContain("Not committed yet");
    expect(committedBy("in_flight", NOT_YET)).toContain("Not committed yet");
  });

  it("counts the months when something finally does count them", () => {
    // The other arm, so the day a reader serves this the screen is already
    // right — and so the plural is exercised rather than assumed.
    const detail = sold();
    const text = visibleText(
      render({
        ...detail,
        unchanged: { ...detail.unchanged, ledger_months: { value: 38, unavailable: null } },
      }),
    );
    expect(text).toContain("38 months, unbroken");
    expect(text).not.toContain("Length not counted");
  });
});

describe("the sections p132 draws", () => {
  it("draws the banner's FACT and not its 24-word second sentence", () => {
    const text = visibleText(render(sold()));
    expect(text).toContain("One account, never closed.");
    // RATIONALE is zero words on screen (rule 33) — every clause of the cut
    // sentence is a ROW of *Nothing changed* instead.
    expect(text).not.toContain("with the same meters and the same unbroken ledger");
    expect(text).toContain("Nothing changed");
    expect(text).toContain("Unchanged");
  });

  it("names what the record does not say — one row since 2026-09-23", () => {
    const text = visibleText(render(sold()));
    expect(text).toContain("Not said here");
    expect(text).toContain("Buyer told");
    expect(text).toContain("Not decided");
    // ⛔ `DEF-CUS-6393` / `DEF-CUS-6394` — a sale now removes the seller's
    // contact details (T3) and moves a master account's premises owner (T2),
    // so the two rows that said otherwise are gone rather than false.
    expect(text).not.toContain("Still names the seller");
    expect(text).not.toContain("Still the seller's");
  });

  it("translates every stored code and prints none of them", () => {
    // B14 rule 31 — `person`, `driving_licence`, `matched` and `active` are
    // stored values; what a clerk reads is the catalogue's own word.
    const text = visibleText(render(sold()));
    expect(text).toContain("Person");
    expect(text).toContain("Driver's license");
    expect(text).toContain("Already on file");
    expect(text).toContain("Active");
    expect(text).not.toContain("driving_licence");
    expect(text).not.toContain("person");
  });

  it("counts the changeover jobs the server raised", () => {
    const text = visibleText(render(sold()));
    expect(text).toContain("Changeover read");
    expect(text).toContain("2 raised");
    expect(text).toContain("2 done");
  });

  it("gives the commit its TIME, because p132 draws one", () => {
    // `S. Ortiz · 05/07/2026 14:06` — the one timestamp on this page. It goes
    // through `DateCell`'s own `withTime` in the tenant's zone, never a second
    // formatting path (`BR-SHL-023`).
    const text = visibleText(render(sold()));
    expect(text).toContain("S. Ortiz");
    expect(text).toContain("05/07/2026 14:06");
    // …and the DATES around it stay dates — a time on `Sold on` would be a
    // precision the product never recorded.
    expect(text).toContain("Sold on");
    expect(text).not.toContain("05/07/2026 00:00");
  });
});

describe("the head's chips", () => {
  it("says the account was reassigned only on a completed sale", () => {
    // `Account reassigned` is `BR-CUS-1030` having HAPPENED. An unfinished
    // transfer has reassigned nothing and a cancelled one never will, so the
    // chip on either would state an act nobody performed.
    expect(visibleText(render(sold()))).toContain("Account reassigned");
    expect(visibleText(render(sold({ state: "in_flight" })))).not.toContain("Account reassigned");
    expect(visibleText(render(sold({ state: "cancelled" })))).not.toContain("Account reassigned");
  });

  it("names each state in the clerk's own words", () => {
    expect(visibleText(render(sold()))).toContain("Completed");
    expect(visibleText(render(sold({ state: "in_flight" })))).toContain("In progress");
    expect(visibleText(render(sold({ state: "cancelled" })))).toContain("Canceled");
  });

  it("offers NO resume door on an unfinished transfer", () => {
    // The move record gained one by a PO ruling of 2026-09-19 about a MOVE.
    // No such ruling exists for a transfer, and p132 draws two doors.
    const html = render(sold({ state: "in_flight" }));
    expect(html).not.toContain("transfer-record-resume");
    expect(visibleText(html)).not.toContain("Resume");
  });
});

describe("rule 33 and rule 31 — what never reaches the screen", () => {
  it("keeps every absence SENTENCE in the title and out of the copy", () => {
    const detail = sold();
    const html = render({
      ...detail,
      what_happened: { ...detail.what_happened, sold_by: { value: null, unavailable: SELLER_GONE } },
    });
    const text = visibleText(html);
    expect(html).toContain("customer_accounts link");
    expect(text).not.toContain("customer_accounts link");
    expect(text).not.toContain("Nothing in this product counts how many unbroken months");
  });

  it("never prints a rule id, an open question or a stored code in clerk-facing copy", () => {
    const text = visibleText(render(sold({ reference: { value: null, unavailable: NO_SERIES } })));
    expect(text).not.toMatch(/BR-CUS-\d/);
    expect(text).not.toMatch(/OQ-\d/);
    expect(text).not.toContain("numbering_series_missing");
    expect(text).not.toContain("seller_not_kept_after_reassignment");
  });

  it("never prints a database id, even though the doors are built from two", () => {
    // B14 rule 31. The uuids are in `href`s — an address is not a field's
    // visible value — and nowhere a person reads.
    const text = visibleText(render(sold()));
    expect(text).not.toContain("acc-uuid-1");
    expect(text).not.toContain("cus-uuid-1");
  });
});

describe("the payload the endpoint has not shipped yet", () => {
  it("renders the whole page when the server sends only what it has", () => {
    // ⚠ `GET /transfers/{ref}` does not exist at this commit and the sibling
    // building it may land it in pieces. A field that is simply ABSENT from
    // the payload must read as the same short label the server's own absence
    // would carry — never `undefined`, never a crash, never a zero.
    const bare = {
      state: "completed",
      reference: { value: "TRF-26-0002", unavailable: null },
      seller_name: { value: null, unavailable: null },
      buyer_name: { value: "Okafor, D.", unavailable: null },
      what_happened: {},
      unchanged: {},
      money: { currency: "USD" },
      doors: {},
    } as unknown as TransferRecordDetail;
    const text = visibleText(render(bare, "TRF-26-0002"));
    expect(text).toContain("Okafor, D.");
    expect(text).toContain("Not recorded");
    expect(text).not.toContain("undefined");
    expect(text).not.toContain("NaN");
    // `BR-CUS-085`'s pair still holds, because the RULE is what guarantees it
    expect([...text.matchAll(/\$0\.00/g)].length).toBe(2);
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: blueprint p132 read AS AN IMAGE (B14 rule 42) + the conformance
//         file's §7 + `TransferRecordPage.tsx`'s §§1–4
// generated: 2026-09-20, the transfer-record lane
// exceptions: none
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
