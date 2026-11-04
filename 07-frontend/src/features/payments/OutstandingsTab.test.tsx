// ── Trace ──────────────────────────────────────────────
// Story:    US-PAY-013 (S34 Outstandings — balance high→low, the ageing strip
//           that FOOTS to the rows, days late on BR-PAY-032's anchor, the bulk
//           toolbar) · US-PAY-012 (the write-off request that moves nothing and
//           the approval that posts it) · US-PAY-014 (the collections run over
//           an S34 selection)
//           Screens: S34 · S35
// Rules:    BR-PAY-029 · BR-PAY-032 · BR-PAY-021 · BR-PAY-015 (no autopay
//           retry ANYWHERE) · BR-PAY-018 · BR-PAY-020 (nothing money-bearing
//           until Finance approves) · BR-REP-011 (no DSO here) ·
//           BR-TEN-043 (`as_of` is asked for) · BR-SHL-023 (one money path) ·
//           BR-SHL-025 (a control this deployment cannot honour is DISABLED
//           with its reason) · CLAUDE.md rule 2 (no float touches money)
// ───────────────────────────────────────────────────────
// §4 test data is US-PAY-013's own, verbatim: A-11340 Northwind $8,240.00 (45
// days, 31–60), A-11024 Ridge Coffee $1,842.10 (30 days, 1–30), A-10802 Novak
// $948.20 (91 days, 90+) — and US-PAY-012 TC-1's write-off is A-10802's own
// 948.20.
//
// THE ASSERTIONS THAT MATTER MOST ARE THE NEGATIVE ONES. This screen must not
// print a DSO number nobody computed, a 0% share for an empty ledger, a "0
// days late" for a bill with no due date, an autopay RETRY that would charge a
// customer, or a write-off that reads as done before Finance has seen it.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import type {
  CollectionsRunResult,
  OutstandingRow,
  OutstandingsResponse,
  WriteOffRequested,
} from "@/api/endpoints";
import { ToastProvider } from "@/components/Toast";

import {
  CollectionsRunPanel,
  OutstandingsTab,
  WriteOffResultPanel,
  ageingTiles,
  outstandingsQueryKey,
} from "./OutstandingsTab";
import { sumDecimalStrings } from "./paymentsShared";

const TEST_TENANT = "brazosbend";
const AS_OF = "2026-08-15";

const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

function row(over: Partial<OutstandingRow> = {}): OutstandingRow {
  return {
    account_id: "acc-11340",
    account_no: "A-11340",
    customer_name: "Northwind Mfg.",
    balance: "8240.0000",
    days_late: 45,
    bucket: "31-60",
    open_bills: 2,
    last_payment_on: "2026-06-20",
    notice_summary: "1st + 2nd sent",
    collection_tier: "second_5_day",
    next_step_due: "2026-08-20",
    plan_status: null,
    autopay: false,
    bad_address: false,
    ...over,
  };
}

/** US-PAY-013 §4's three rows, in the order the SERVER sorts them. */
const ROWS: OutstandingRow[] = [
  row(),
  row({
    account_id: "acc-11024",
    account_no: "A-11024",
    customer_name: "Ridge Coffee Co.",
    balance: "1842.1000",
    days_late: 30,
    bucket: "1-30",
    open_bills: 1,
    last_payment_on: "2026-07-05",
    notice_summary: "friendly sent",
    collection_tier: "friendly",
  }),
  row({
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
  }),
];

const PROBLEMS = [
  {
    code: "dso_not_computed_here",
    br_ref: "BR-REP-011",
    detail: "reports own the read",
  },
  {
    code: "medical_hold_not_readable",
    br_ref: "BR-CUS-039",
    detail: "customers publishes no selector",
  },
];

function view(over: Partial<OutstandingsResponse> = {}): OutstandingsResponse {
  return {
    as_of: AS_OF,
    rows: ROWS,
    // Σ 8240.00 + 1842.10 + 948.20 — the server folds the SAME rows into the
    // tiles, which is what makes TC-1's tie-out true rather than hoped for.
    totals: { accounts: 3, owed: "11030.3000", dso_days: null },
    ageing: [
      { bucket: "current", amount: "0.0000", accounts: 0, share: "0.0" },
      { bucket: "1-30", amount: "1842.1000", accounts: 1, share: "16.7" },
      { bucket: "31-60", amount: "8240.0000", accounts: 1, share: "74.7" },
      { bucket: "61-90", amount: "0.0000", accounts: 0, share: "0.0" },
      { bucket: "90+", amount: "948.2000", accounts: 1, share: "8.6" },
    ],
    problems: PROBLEMS,
    // `CR-138-BRC07` `P4.1` — the body carries its page state now. `per` is
    // `null` because this screen does not ask for a page yet: the read can
    // cut one in SQL and the toolbar declares ten sorts and a search it
    // cannot honour, so switching it on would be a search box that searches
    // fifty rows (`DEF-PAY-6270`). `count` is the whole filtered list and is
    // not `rows.length` — the two are the same only while the fixture fits
    // on one page.
    debtors_window: { page: 1, per: null, count: 3, pages: 1 },
    ...over,
  };
}

function render(
  seed: OutstandingsResponse | undefined,
  props: { currency?: string | null } = {},
): string {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  if (seed !== undefined) {
    queryClient.setQueryData(outstandingsQueryKey(AS_OF, "", false), seed);
  }
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TEST_TENANT}/payments/outstandings`]}>
          <Routes>
            <Route
              path="/:tenant/payments/:tab"
              element={
                <OutstandingsTab
                  asOf={AS_OF}
                  onAsOfChange={() => undefined}
                  currency={props.currency === undefined ? "USD" : props.currency}
                  writeBlockedReason={null}
                />
              }
            />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

/** Copy as `renderToStaticMarkup` writes it — an apostrophe in real English
 *  prose comes out as `&#x27;`, and a test comparing the raw string would fail
 *  on the copy being written well rather than on the screen being wrong. */
function escaped(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#x27;");
}

describe("US-PAY-013 · S34 Outstandings — the rows", () => {
  it("TC-1: renders the three worked balances THROUGH MoneyCell, balance high→low", () => {
    const html = render(view());
    // BR-SHL-023 / BR-TEN-080: 4dp on the wire, 2dp on screen, one formatter.
    expect(html).toContain('<span class="cell-money-amount">$8,240.00</span>');
    expect(html).toContain('<span class="cell-money-amount">$1,842.10</span>');
    expect(html).toContain('<span class="cell-money-amount">$948.20</span>');
    // BR-PAY-029's order, as the SERVER sorted it — the screen re-sorts nothing.
    // Read inside the TABLE: the ageing strip above it is in BUCKET order
    // (1–30 before 31–60), which is a different and equally correct order.
    const table = html.slice(html.indexOf("<table"));
    const first = table.indexOf("$8,240.00");
    const second = table.indexOf("$1,842.10");
    const third = table.indexOf("$948.20");
    expect(first).toBeGreaterThan(-1);
    expect(first).toBeLessThan(second);
    expect(second).toBeLessThan(third);
    // Never the raw 4dp wire figure (DEF-088's own shape).
    expect(html).not.toContain("8240.0000");
    expect(html).not.toContain("$948.2000");
  });

  it("TC-1: days late are 45 · 30 · 91 and each row carries A2's band", () => {
    const html = render(view());
    expect(html).toContain(">45</td>");
    expect(html).toContain(">30</td>");
    expect(html).toContain(">91</td>");
    expect(html).toContain(escaped(t("payments.bucket.d31_60")));
    expect(html).toContain(escaped(t("payments.bucket.d1_30")));
    expect(html).toContain(escaped(t("payments.bucket.d90_plus")));
  });

  it("TC-1: the header states the account count and the served total, not a browser sum", () => {
    const html = render(view());
    // ⚠ **THE ROLL-UP LINE BECAME THE FOUR TILES — `CR-138-BRC07` `P4.7`.**
    // *Accounts owing · Total owed · Sorted by* was a sentence above the table;
    // the drawing's annotation ① is *"Four tiles, not nine"*, and the account
    // count is now the **OWED** tile's own detail line. The FIGURE is asserted
    // below exactly as it was — what moved is where it is drawn, not whether
    // it is served, and TC-1's control is that it is the SERVER's number.
    expect(html).toContain(escaped(t("payments.outstandings.kpi.owed")));
    expect(html).toContain(
      escaped(t("payments.outstandings.kpi.owedDetail", { accounts: view().totals.accounts })),
    );
    // The COUNT is the OWED tile's detail line now, asserted above from the
    // server's own `totals.accounts`; the `pay-rollup-value` span it used to
    // sit in went with the sentence `P4.7` replaced.
    expect(html).toContain('<span class="cell-money-amount">$11,030.30</span>');
  });

  it("BR-PAY-032: a null days-late renders its REASON, never a 0", () => {
    const html = render(
      view({ rows: [row({ days_late: null, bucket: "current", balance: "120.0000" })] }),
    );
    expect(html).toContain(escaped(t("payments.outstandings.noDueDate")));
    // The row must not read as "due today" — that is a different claim.
    expect(html).not.toContain(">0</td>");
  });

  it("BR-PAY-015: there is no autopay RETRY anywhere on this screen", () => {
    const html = render(view({ rows: [row({ autopay: true })] })).toLowerCase();
    // ⚠ **THE AUTOPAY COLUMN IS OFF BY DEFAULT SINCE `P4.7` AND THE RULE IS
    // UNAFFECTED.** The drawing's 7·1 draws eight columns and autopay is not
    // among them, so it moved into the `▦` chooser (B14 rule 14) — it is NOT
    // deleted, and `debtorScreens.dom.test.tsx` asserts it is still offered.
    //
    // **What BR-PAY-015 actually forbids is an ACT**, and that is what this
    // case checks: v1 is capture-only, no charging path exists anywhere, and
    // the prototype's *Retry autopay* row option is superseded. The two
    // negatives below are the rule; the enrolment WORD was only ever the
    // occasion for reading them.
    expect(html).not.toContain("retry");
    expect(html).not.toContain("charge autopay");
  });

  it("BR-PAY-018: a returned-mail row is badged", () => {
    const html = render(view({ rows: [row({ bad_address: true })] }));
    expect(html).toContain(escaped(t("payments.outstandings.badAddressFlag")));
  });

  it("BR-TEN-043: the as-of day is ASKED FOR on screen, never implied", () => {
    const html = render(view());
    expect(html).toContain('id="as_of"');
    expect(html).toContain(escaped(t("payments.outstandings.asOf")));
    expect(html).toContain(AS_OF);
  });

  it("A18: an empty list says nobody owes anything rather than rendering a bare header", () => {
    const html = render(
      view({ rows: [], totals: { accounts: 0, owed: "0.0000", dso_days: null } }),
    );
    expect(html).toContain(escaped(t("payments.outstandings.emptyTitle")));
    expect(html).not.toContain("<tbody></tbody>");
  });
});

describe("US-PAY-013 · S34 — the ageing strip", () => {
  it("TC-1: the five tiles carry the served amounts and FOOT to the rows exactly", () => {
    const html = render(view());
    expect(html).toContain('<span class="cell-money-amount">$8,240.00</span>');
    expect(html).toContain('<span class="cell-money-amount">$1,842.10</span>');
    expect(html).toContain('<span class="cell-money-amount">$948.20</span>');
    // The tie-out itself, computed here from the SERVED tile amounts: the four
    // bands plus `current` must add up to the header total, exactly.
    const tiles = view().ageing.map((tile) => tile.amount);
    expect(sumDecimalStrings(tiles)).toBe("11030.300000");
    expect(sumDecimalStrings([...ROWS.map((r) => r.balance)])).toBe("11030.300000");
  });

  it("BR-REP-011: no DSO number is invented, and the reason is not explained on screen", () => {
    const html = render(view());
    // ⚠ **THIS CASE ASSERTED THE OPPOSITE UNTIL 2026-09-23 (`DEF-PAY-6327`),
    // AND IT WAS RIGHT UNTIL THE PRODUCT OWNER READ THE PANEL.** It required
    // `dso_not_computed_here` — *"Finance owns this formula. It is not worked
    // out here."* — to be ON the screen. The PO quoted that exact bullet back
    // at us asking why we were showing it, and ruled: keep the facts, shorten
    // them to six words, **delete the reasons**. B14 rule 33 puts RATIONALE at
    // ZERO WORDS ON SCREEN, and an explanation of which module owns a formula
    // is rationale however short it is made. The code is still sent by
    // `OUTSTANDINGS_UNAVAILABLE`; it simply has no words any more.
    //
    // **What must never appear is a NUMBER**, and that half is unchanged —
    // it is the reason this case exists at all.
    expect(view().totals.dso_days).toBeNull();
    // ⚠ AND THE NEW HALF: deleting a catalogue key must not turn into a DOTTED
    // KEY on screen. `t()` returns the key when none is found (`keySeparator:
    // false`), so the failure mode of this very commit is a clerk reading
    // `payments.problem.dso_not_computed_here`. `ProblemList` drops a wordless
    // code instead (`DEF-PAY-6328`), and this is that guarantee at the screen.
    expect(html).not.toContain("payments.problem.");
    // ⚠ **THE NEGATIVE READS THE TEXT, NOT THE MARKUP — AND IT HAD TO.** As
    // written it was `expect(html).not.toContain("18.4")` over the raw string,
    // and `P4.7` added the `👁` row action, whose SVG path data contains
    // `… 22.2 12 18.4 18.5 12 …`. The case went red on a COORDINATE IN A
    // VECTOR PATH — a check looking at the wrong thing, which would just as
    // easily have gone the other way and passed over a real 18.4 hidden in an
    // attribute. Tags are stripped first, so what is asserted is what a person
    // can read.
    const text = html.replace(/<[^>]*>/g, " ");
    expect(text).not.toContain("18.4");
  });

  it("a null share renders the absence, never 0%", () => {
    const tiles = ageingTiles(
      view({
        ageing: [{ bucket: "1-30", amount: "0.0000", accounts: 0, share: null }],
      }),
      "USD",
      t,
    );
    expect(tiles[0].detail).toBe(t("payments.outstandings.tileNoShare", { accounts: 0 }));
    expect(String(tiles[0].detail)).not.toContain("0%");
  });

  it("with no currency code served, a tile states the absence rather than guessing USD", () => {
    const tiles = ageingTiles(view(), null, t);
    const first = tiles[0];
    expect("money" in first).toBe(false);
    const html = render(view(), { currency: null });
    expect(html).toContain(escaped(t("payments.money.currencyUnavailable")));
    expect(html).not.toContain("$8,240.00");
  });
});

describe("US-PAY-013 · S34 — the bulk toolbar's four absent actions", () => {
  it("BR-SHL-025: reminder, notice, plan and field visit each name why they are off", () => {
    // The toolbar renders only over a selection, which a static render cannot
    // make — so the REASONS are asserted where they are declared, and the
    // selection path is exercised by the panels below.
    expect(t("payments.outstandings.action.noticesUnavailable")).toContain("no route accepts one");
    expect(t("payments.outstandings.action.planUnavailable")).toContain("not built");
    expect(t("payments.outstandings.action.fieldVisitUnavailable")).toContain("no agreed rule");
  });

  it("CLAUDE.md rule 2: the selected total is summed EXACTLY, with no float in the path", () => {
    // The prototype's own selection: four accounts, $11,642.90 owed.
    expect(sumDecimalStrings(["8240.0000", "1842.1000", "948.2000", "612.6000"])).toBe(
      "11642.900000",
    );
    // The float detector. 0.1 + 0.2 is 0.30000000000000004 as an IEEE-754
    // double; an exact decimal sum is 0.3 and nothing else.
    expect(sumDecimalStrings(["0.1", "0.2"])).toBe("0.300000");
    expect(sumDecimalStrings(["8.005", "0"])).toBe("8.005000");
    // A value that is not a decimal string returns null rather than being
    // skipped — a total that dropped one account would be a smaller number
    // wearing the right label.
    expect(sumDecimalStrings(["8240.0000", "n/a"])).toBeNull();
  });
});

describe("US-PAY-012 · the write-off that moves nothing until Finance approves", () => {
  const requested: WriteOffRequested = {
    id: "wo-1",
    status: "requested",
    account_id: "acc-10802",
    amount: "948.2000",
    posted_to_ledger: false,
    problems: [
      {
        code: "awaiting_finance_approval",
        br_ref: "BR-PAY-020",
        detail: "nothing money-bearing has happened",
      },
    ],
  };

  function panel(): string {
    return renderToStaticMarkup(
      <ToastProvider>
        <WriteOffResultPanel
          requested={[requested]}
          currency="USD"
          // ⚠ **THIS VALUE WAS `/t/brazosbend/finance` UNTIL `DEF-PAY-6329`,
          // AND IT WAS WRONG TWICE OVER** — the wrong destination (the bare
          // `/finance` is the TRIAL BALANCE since `CR-060` T10, not the
          // write-off queue) and not even the shape this app builds
          // (`tenantPath` writes `/{tenant}/…`, never `/t/{tenant}/…`). The
          // case below hands the href IN and then asserts it, so it was green
          // on any value at all; left as it was, it went on teaching the next
          // reader that this is the queue's address.
          // **The destination itself is asserted by `writeOffQueueDoor.dom.test.tsx`**,
          // which drives the real `OutstandingsTab` and reads the href off the
          // anchor instead of supplying it.
          financeQueueHref="/brazosbend/finance/revenue"
          onDismiss={() => undefined}
        />
      </ToastProvider>,
    );
  }

  it("TC-1: a 948.20 request shows the amount and says nothing moved", () => {
    const html = panel();
    expect(html).toContain('<span class="cell-money-amount">$948.20</span>');
    expect(html).toContain(escaped(t("payments.writeOff.nothingMoved")));
    expect(html).toContain(escaped(t("payments.writeOff.status.requested")));
    // The server's own reason, rendered — not swallowed (README rule 4).
    expect(html).toContain(escaped(t("payments.problem.awaiting_finance_approval")));
    // It must NOT read as approved.
    expect(html).not.toContain(escaped(t("payments.writeOff.posted")));
  });

  it("DEF-100: the requester's screen offers NO Approve control and points at Finance", () => {
    // ⚠ THE DEFECT, STATED AS A TEST. While `/write-offs` was POST-only this
    // panel held the only write-off id in the product, so the Approve button
    // had to live here — beside the request, in the requester's hand, in the
    // same breath. BR-PAY-020 puts the approval in FINANCE and now it is there.
    //
    // This asserts the SCREEN, not an authorisation: BR-PAY-037 still permits
    // the same admin to do both acts, and the server's role gate is unchanged.
    const html = panel();
    expect(html).not.toContain(escaped(t("payments.writeOff.approve")));
    expect(html).toContain(escaped(t("payments.writeOff.approveInFinance")));
    expect(html).toContain(escaped(t("payments.writeOff.openFinanceQueue")));
    // The LABEL and the absence of Approve are what this case is for; the
    // address here is only the fixture's own value echoed back.
    expect(html).toContain('href="/brazosbend/finance/revenue"');
  });
});

describe("US-PAY-014 · the collections run over an S34 selection", () => {
  it("renders every step AND every skip — a silent exclusion is what J4 forbids", () => {
    const run: CollectionsRunResult = {
      as_of: AS_OF,
      stepped: [{ account_id: "acc-11024", rung: "friendly", detail: "due+3" }],
      skipped: [
        { account_id: "acc-10802", reason: "medical_hold", detail: "A15 exclusion" },
        { account_id: "acc-11340", reason: "below_ladder_floor", detail: "$2.40" },
      ],
      problems: [
        {
          code: "no_scheduled_caller",
          br_ref: "BR-PAY-017",
          detail: "no nightly job runs this",
        },
      ],
    };
    const html = renderToStaticMarkup(
      <CollectionsRunPanel
        run={run}
        rowsByAccount={{ "acc-11024": ROWS[1], "acc-10802": ROWS[2], "acc-11340": ROWS[0] }}
        onDismiss={() => undefined}
      />,
    );
    expect(html).toContain("A-11024");
    expect(html).toContain(escaped(t("payments.tier.friendly")));
    expect(html).toContain(escaped(t("payments.skip.medical_hold")));
    expect(html).toContain(escaped(t("payments.skip.below_ladder_floor")));
    // BR-PAY-017: nothing runs this overnight, and the screen says so.
    expect(html).toContain(escaped(t("payments.problem.no_scheduled_caller")));
  });
});

describe("US-PAY-013 · problems[] are rendered, never dropped", () => {
  it("the panel carries the absence a clerk can act on, and no dotted key", () => {
    // ⚠ **THIS CASE NAMED TWO ABSENCES AND NOW NAMES ONE (`DEF-PAY-6327`).**
    // `dso_not_computed_here` was deleted as rationale on the PO's ruling of
    // 2026-09-23.
    //
    // ⚠ **THE HOLD ON `medical_hold_not_readable` EXPIRED 2026-09-24 —
    // `OQ-PAY-12612`, and this is the line that was promised would feel it.**
    // It was the PO's other quoted bullet and was HELD unchanged pending a
    // ruling of its own, because it is the only one of the four with a safety
    // argument. The ruling landed as (b), NOT as a deletion — PO, verbatim:
    // *"p6 b) Keep a short version: "Medical protections apply. Not shown
    // here.""*. So the words are asserted LITERALLY here and not only through
    // `t()`: a `t()` assertion passes whatever the catalogue says, which is
    // exactly the shape hard-won law 7 calls a check incapable of failing.
    const html = render(view());
    expect(html).toContain(escaped(t("payments.problems.title")));
    expect(html).toContain(escaped(t("payments.problem.medical_hold_not_readable")));
    expect(html).toContain(escaped("Medical protections apply. Not shown here."));
    // The sentence the ruling replaced. It explained WHY the screen cannot show
    // the hold, which B14 rule 33 puts at zero words on screen.
    expect(html).not.toContain("Medical protections cannot be shown here");
    expect(html).not.toContain("payments.problem.");
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-PAY-013@3c9f5a1 (story+rules snapshot — EP-PAY-04 US-PAY-013; co-packets US-PAY-012, US-PAY-014)
// generated: 2026-08-15 by story-coder (payments FRONTEND visible-half lane)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: RED PROVED FIRST — with the S34 tab still rendering the *awaiting* panel these assertions failed on the rendered output; the verbatim failure text is in the lane report
// exceptions: (1) NO CLICK-DRIVEN ASSERTIONS — `vitest.config.ts` registers no jsdom environment, so every test here renders STATIC markup; the selection toolbar's own reasons are asserted where they are declared and its result panels are rendered directly with their props
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
