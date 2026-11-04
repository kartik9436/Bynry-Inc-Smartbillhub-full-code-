// ── Trace ──────────────────────────────────────────────
// Story:    US-PAY-005 (S32 Payments summary — today, method mix MTD, failed,
//           collections, the two needs-attention chips)
//           Screens: S32
// Rules:    BR-PAY-027 (figures tie to the lists exactly) · BR-PAY-021 (Today
//           is POSTED money; the mix is CLEARED money) · BR-PAY-015 (no retry
//           and no charging path anywhere) · BR-PAY-018 · BR-PAY-020 ·
//           BR-REP-011 (no DSO here) · BR-SHL-023 (one money path)
// ───────────────────────────────────────────────────────
// §4 test data is US-PAY-005's own PE-10 receipt set: checks 292.87 + 142.30 +
// 36.22 and cash 105.36 + 16.42 — five payments, 593.17 taken, an average of
// 118.634, and a method mix that adds to 100.0%.
//
// THE ASSERTION THIS FILE EXISTS FOR IS THE NULL ONE. A day with no payments
// has NO average, and a screen that renders $0.00 there states something false
// about a division that never happened.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import type { PaymentsSummaryResponse } from "@/api/endpoints";
import { ToastProvider } from "@/components/Toast";

import { methodMixShareTotal, summaryQueryKey } from "./SummaryTab";
import { SummaryTab } from "./SummaryTab";

const TEST_TENANT = "brazosbend";
const AS_OF = "2026-08-08";

const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

/** PE-10, exactly: 292.87 + 142.30 + 36.22 + 105.36 + 16.42 = 593.17 over 5. */
function summary(over: Partial<PaymentsSummaryResponse> = {}): PaymentsSummaryResponse {
  return {
    as_of: AS_OF,
    today: { amount: "593.1700", count: 5, average: "118.6340" },
    method_mix: [
      { method: "check", method_name: "Check", amount: "471.3900", count: 3, share: "79.5" },
      { method: "cash", method_name: "Cash", amount: "121.7800", count: 2, share: "20.5" },
    ],
    failed: [
      {
        payment_id: "pay-9001",
        payment_no: "PMT-2608-000901",
        account_id: "acc-11025",
        amount: "328.6000",
        status: "failed",
        reason: "nsf",
        posted_at: "2026-08-05T22:14:00Z",
      },
    ],
    collections: {
      accounts_owing: 3,
      total_owed: "11030.3000",
      write_offs_ytd: "6420.0000",
    },
    chips: { autopay_scheduled: 2, returned_mail: 1 },
    problems: [
      { code: "dso_not_computed_here", br_ref: "BR-REP-011", detail: "reports own the read" },
    ],
    ...over,
  };
}

function render(seed: PaymentsSummaryResponse | undefined): string {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  if (seed !== undefined) {
    queryClient.setQueryData(summaryQueryKey(AS_OF), seed);
  }
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TEST_TENANT}/payments`]}>
          <Routes>
            <Route
              path="/:tenant/payments"
              element={
                <SummaryTab
                  asOf={AS_OF}
                  onAsOfChange={() => undefined}
                  currency="USD"
                  onOpenOutstandings={() => undefined}
                  onRecordPayment={() => undefined}
                />
              }
            />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

function escaped(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#x27;");
}

describe("US-PAY-005 · S32 — the Today panel", () => {
  it("TC-1: 292.87 + 142.30 + 36.22 + 105.36 + 16.42 renders as $593.17 over 5 payments", () => {
    const html = render(summary());
    expect(html).toContain('<span class="cell-money-amount">$593.17</span>');
    expect(html).toContain("<dd>5</dd>");
    // 593.17 ÷ 5 = 118.634 on the wire, $118.63 on screen — the ONE formatter
    // trims to 2dp (BR-TEN-080) and nothing here re-rounds.
    expect(html).toContain('<span class="cell-money-amount">$118.63</span>');
    expect(html).not.toContain("118.6340");
  });

  it("TC-5 / A18: a day with no payments has NO average — never $0.00", () => {
    const html = render(
      summary({
        today: { amount: "0.0000", count: 0, average: null },
        method_mix: [],
        failed: [],
      }),
    );
    expect(html).toContain(escaped(t("payments.summary.noAverage")));
    // The takings themselves ARE zero and say so; the AVERAGE must not.
    const average = html.slice(html.indexOf(escaped(t("payments.summary.todayAverage"))));
    expect(average).not.toContain("$0.00");
  });
});

describe("US-PAY-005 · S32 — the method mix", () => {
  it("TC-2: each method's share renders and the shares add to 100.0%", () => {
    const html = render(summary());
    // Hard rule 2 — a percentage DISPLAYS two decimals (`DEF-PAY-9644`): the
    // rows read 79.50 and 20.50, the total 100.00, never the stored 6 places.
    expect(html).toContain(escaped(t("payments.summary.share", { share: "79.50" })));
    expect(html).toContain(escaped(t("payments.summary.share", { share: "20.50" })));
    // The tie-out itself, on screen: US-PAY-005 TC-2's "Σ = 100%". The SUM is
    // exact and unrounded; only what is printed is cut to two places.
    expect(methodMixShareTotal(summary().method_mix)).toBe("100.000000");
    expect(html).toContain(escaped(t("payments.summary.share", { share: "100.00" })));
    expect(html).not.toContain("100.000000");
    // …and the money behind the shares.
    expect(html).toContain('<span class="cell-money-amount">$471.39</span>');
    expect(html).toContain('<span class="cell-money-amount">$121.78</span>');
  });

  it("BR-PAY-021: the mix is labelled as CLEARED money, a different date from the takings", () => {
    const html = render(summary());
    expect(html).toContain(escaped(t("payments.summary.mixBasis")));
  });

  it("DEF-PAY-9644: a total of 99.9 reads 99.90%, never 99.900000%", () => {
    const html = render(
      summary({
        method_mix: [
          { method: "check", method_name: "Check", amount: "100.0000", count: 1, share: "35.2" },
          { method: "cash", method_name: "Cash", amount: "183.0000", count: 2, share: "64.7" },
        ],
      }),
    );
    expect(html).toContain(escaped(t("payments.summary.share", { share: "99.90" })));
    expect(html).toContain(escaped(t("payments.summary.share", { share: "35.20" })));
    expect(html).not.toContain("99.900000");
  });

  it("a null share is an absence, never 0% — and the total then states no share at all", () => {
    const mix = [
      { method: "check", method_name: "Check", amount: "0.0000", count: 0, share: null },
    ];
    expect(methodMixShareTotal(mix)).toBeNull();
    const html = render(summary({ method_mix: mix }));
    expect(html).toContain(escaped(t("payments.summary.noShare")));
    expect(html).not.toContain("0.0%");
  });

  it("a payment with no instrument is its OWN row, never folded into another method", () => {
    const html = render(
      summary({
        method_mix: [
          { method: null, method_name: null, amount: "42.2000", count: 1, share: "100.0" },
        ],
      }),
    );
    expect(html).toContain(escaped(t("payments.row.noMethod")));
  });
});

describe("US-PAY-005 · S32 — the Failed panel", () => {
  it("TC-3: a failed payment shows its amount and its reason", () => {
    const html = render(summary());
    expect(html).toContain('<span class="cell-money-amount">$328.60</span>');
    expect(html).toContain("PMT-2608-000901");
    expect(html).toContain(escaped(t("payments.reversalReason.nsf")));
  });

  it("BR-PAY-015: there is NO retry and no charging path — the panel routes to a NEW recording", () => {
    const html = render(summary());
    expect(html).toContain(escaped(t("payments.summary.noRetry")));
    expect(html).toContain(escaped(t("payments.action.record")));
    expect(html.toLowerCase()).not.toContain(">retry<");
  });

  it("no failures says so rather than rendering an empty list", () => {
    const html = render(summary({ failed: [] }));
    expect(html).toContain(escaped(t("payments.summary.noFailures")));
  });
});

describe("US-PAY-005 · S32 — collections and the chips", () => {
  it("TC-4: the collections panel ties to the S34 read-model and shows write-offs YTD", () => {
    const html = render(summary());
    expect(html).toContain("<dd>3</dd>");
    expect(html).toContain('<span class="cell-money-amount">$11,030.30</span>');
    expect(html).toContain('<span class="cell-money-amount">$6,420.00</span>');
    expect(html).toContain(escaped(t("payments.summary.openOutstandings")));
  });

  it("BR-REP-011: DSO renders its reason in the collections panel, never 18.4", () => {
    const html = render(summary());
    expect(html).toContain(escaped(t("payments.outstandings.dsoUnavailable")));
    expect(html).not.toContain("18.4");
  });

  it("TC-4: both needs-attention counters carry their counts", () => {
    // ⚠ ASSERTED AGAINST THE COUNTER'S OWN HOOK, NOT ITS CLASS LIST
    // (`DEF-PAY-6335`). The band moved into `summaryFiguresBar.tsx` and is
    // written in Tailwind utilities, so `class="pay-chip-value"` — what this
    // case used to match on — is a string that will never appear again. A test
    // pinned to a class name re-breaks on every legitimate restyle and says
    // nothing about the fact it exists to protect, which is that each counter
    // reaches the screen carrying its figure.
    const html = render(summary());
    expect(html).toContain(escaped(t("payments.summary.chip.autopay")));
    expect(html).toMatch(/data-counter="autopay"[\s\S]*?data-counter-value="[^"]*"[^>]*>2</);
    expect(html).toContain(escaped(t("payments.summary.chip.returnedMail")));
    expect(html).toMatch(/data-counter="returned-mail"[\s\S]*?data-counter-value="[^"]*"[^>]*>1</);
  });

  it("US-PAY-016: the returned-mail chip carries the action that clears it", () => {
    // Hard-won law 2, and this chip was a live example of it: it counted a
    // needs-attention queue for five days while `returned_mail.py`, the
    // bad-address flag and `POST /deliveries/returned` all existed and a clerk
    // holding a stack of envelopes had nowhere to type them. A count with no
    // action beside it is a screen that reports a chore nobody can do.
    const html = render(summary());
    expect(html).toContain(escaped(t("payments.returnedMail.bulk.open")));
    // The AUTOPAY chip has no action, and that is deliberate rather than an
    // oversight (BR-PAY-015: v1 captures no money and offers no retry). If a
    // later lane adds one, this line is where the decision gets re-read.
    const buttons = html.match(/<button[^>]*>[^<]*<\/button>/g) ?? [];
    expect(buttons.filter((b) => b.includes("utopay")).length).toBe(0);
  });

  it("problems[] are rendered here too — the summary borrows S34's read-model", () => {
    // ⚠ **THIS ASSERTED `dso_not_computed_here` UNTIL 2026-09-23
    // (`DEF-PAY-6327`).** That bullet — *"Finance owns this formula. It is not
    // worked out here."* — is one of the two the Product Owner read on THIS
    // screen and asked why we were showing. It is deleted as rationale (B14
    // rule 33: rationale is zero words on screen). The read-model still
    // carries the code; the panel still renders every absence a clerk can ACT
    // on, which is what this case is really for, so it now asserts the one
    // that survived rather than the one that did not.
    // The seed carries `dso_not_computed_here` and nothing else, so the panel
    // now draws NOTHING AT ALL — which is the deletion reaching the screen,
    // and is asserted rather than assumed. An empty `<details>` inviting a
    // clerk to open nothing would be hard-won law 2's dead UI one click in.
    const html = render(summary());
    expect(html).not.toContain(escaped(t("payments.problems.title")));
    expect(html).not.toContain("Finance owns this formula");
    // Deleting a key must not print the key — `DEF-PAY-6328`.
    expect(html).not.toContain("payments.problem.");
    // …and the panel still WORKS, which is the guarantee this case was
    // written for and the half a deletion could silently have taken with it.
    const withLive = render(
      summary({
        problems: [
          { code: "medical_hold_not_readable", br_ref: "BR-CUS-043", detail: "holds are not readable here" },
        ],
      }),
    );
    expect(withLive).toContain(escaped(t("payments.problems.title")));
    expect(withLive).toContain(escaped(t("payments.problem.medical_hold_not_readable")));
    // ⚠ **THE HOLD EXPIRED 2026-09-24 — `OQ-PAY-12612` ruled (b), not (a).**
    // PO, verbatim: *"p6 b) Keep a short version: "Medical protections apply.
    // Not shown here.""*. Asserted LITERALLY, because the `t()` line above
    // passes whatever the catalogue happens to say and so could never have
    // gone red on the day the ruling landed.
    expect(withLive).toContain(escaped("Medical protections apply. Not shown here."));
    expect(withLive).not.toContain("Medical protections cannot be shown here");
    expect(withLive).not.toContain("payments.problem.");
  });
});

describe("US-PAY-005 · S32 — the business day", () => {
  it("BR-TEN-043: the day is asked for on screen and is not implied by a clock", () => {
    const html = render(summary());
    expect(html).toContain('id="summary_as_of"');
    expect(html).toContain(AS_OF);
    expect(html).toContain(escaped(t("payments.summary.asOfHelp")));
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-PAY-005@3c9f5a1 (story+rules snapshot — EP-PAY-01 US-PAY-005)
// generated: 2026-08-15 by story-coder (payments FRONTEND visible-half lane)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: RED PROVED FIRST — with the zero-count average rendered through MoneyCell the A18 assertion failed on the rendered output (`$0.00` in the average slot); the verbatim failure text is in the lane report
// exceptions: (1) NO CLICK-DRIVEN ASSERTIONS — `vitest.config.ts` registers no jsdom environment, so every test here renders STATIC markup
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
