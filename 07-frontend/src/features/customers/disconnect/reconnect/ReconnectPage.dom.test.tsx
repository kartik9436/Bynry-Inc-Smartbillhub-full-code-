/**
 * `S148` — the drawn rows, the master split, and the door lane CUTPATH owes.
 *
 * ⚠ **MOUNTED UNDER THE REAL `/:tenant/…` PATTERN.** A bare `MemoryRouter`
 * leaves `useParams().tenant` undefined and every address the page builds comes
 * out `//disconnects/…` — a protocol-relative URL to another host, which
 * `toContain` reads as a perfectly good string. That is how a portal front page
 * shipped with two working doors out of eight.
 *
 * ⚠ **WHAT A FALSE PASS WOULD LOOK LIKE**, asked before trusting any of this
 * (hard-won law 7, habit 2): these render to static markup, so they can tell
 * you a string IS on the page and can never tell you it is in the right place,
 * the right size or the right order. **That is what the browser walk is for**
 * (`10-scripts/po20260925_reconnect_walk.mjs`), and the two are not
 * substitutes. A green file here over a screen that does not match its drawing
 * is the 10.8% this repo fails in.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { ReconnectPage } from "./ReconnectPage";
import { RECONNECT_ROUTE, RECONNECT_SCREEN, reconnectKey, reconnectPath } from "./reconnectEndpoints";
import type { ReconnectDetail } from "./reconnectEndpoints";

const CASE_NO = "DSC-26-0005";
const ACCOUNT_ID = "6f2a0d7e-0000-4000-8000-000000000001";

function money(display: string) {
  return { stored: `${display}0000`, display, currency: "USD", unavailable: null };
}

function detail(over: Partial<ReconnectDetail> = {}): ReconnectDetail {
  return {
    case_no: CASE_NO,
    account: {
      account_no: "A-11996",
      customer_name: "Thompson, R.",
      address: "88 Pine Vista · Unit 1 · Silver Creek, TX 78611",
      account_kind: "regular",
      account_class: "Residential",
      cut_on: "2026-09-20",
      balance: money("139.80"),
    },
    master: { is_master: false, units: null, unit_accounts: null },
    services: {
      rows: [
        {
          service: "water",
          scope: null,
          service_point: "88 Pine Vista · Unit 1",
          point_known: true,
          meter: null,
          meter_absence: { code: "meter_not_recorded", detail: "no meter is recorded." },
          how_options: ["work_order", "remote", "no_visit"],
          how_default: "work_order",
          instruction: null,
          work_order: null,
          reaches: null,
        },
      ],
      unavailable: null,
      addable: [],
    },
    owed: {
      lines: [
        {
          code: "arrears_at_the_cut",
          from_code: "the_account",
          amount: money("64.80"),
          when: "2026-09-20",
          negative: false,
        },
        {
          code: "reconnection_fee",
          from_code: "the_tenants_charge_code",
          amount: money("75.00"),
          when: "at_the_cut",
          negative: false,
        },
        {
          code: "paid_since",
          from_code: "payments",
          amount: money("0.00"),
          when: null,
          negative: true,
        },
      ],
      still_owed: money("139.80"),
      total_is_the_ledger: { code: "fee_is_already_in_the_balance", detail: "read once." },
      plan_label: "Residential",
    },
    deposit: { held_before_the_cut: null, disposition: "held", new_deposit_required: false },
    consequences: [{ code: "supply_back_on" }, { code: "the_case_closes" }],
    warning: { code: "still_owed_you_may_continue", amount: money("139.80") },
    commit_refused_by: { code: "not_settled", br_ref: "`DSC-02.4`" },
    step: "mark_reconnecting",
    restore_on: "2026-09-26",
    ...over,
  };
}

/**
 * ⚠ **`step` IS A REAL QUERY PARAMETER AND NOT A TEST SEAM.** `WizardFrame`
 * renders only the ACTIVE step's content, so step 2 cannot be asserted from a
 * step-1 render — which is the frame working correctly and my first draft of
 * this file being wrong. The screen serialises `?step=` because that is the
 * frame's own documented contract (A9, `BR-SHL-018`) and because a screen whose
 * point is having a sendable address must have a sendable step. So these
 * render the address a clerk would actually paste.
 */
function render(data: ReconnectDetail, step = 1): string {
  const client = { get: async () => ({ status: 200, data }) } as never;
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  qc.setQueryData(reconnectKey(CASE_NO), data);
  return renderToStaticMarkup(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[`/brazosbend${reconnectPath(CASE_NO)}?step=${step}`]}>
        <Routes>
          <Route path={`/:tenant${RECONNECT_ROUTE}`} element={<ReconnectPage client={client} />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("the reconnect screen's address — 4.8", () => {
  it("is the case record's plus one segment, and is a CASE NUMBER", () => {
    // B14 rule 31 — the URL a clerk copies is the number, never an id.
    expect(reconnectPath(CASE_NO)).toBe(`/disconnects/${CASE_NO}/reconnect`);
    expect(reconnectPath(CASE_NO)).not.toContain(ACCOUNT_ID);
    expect(RECONNECT_ROUTE).toBe("/disconnects/:ref/reconnect");
  });

  it("opens S148, asserted by ADDRESS and by the screen id — the door lane CUTPATH owes", () => {
    // ⚠ **THIS IS THE HOLD-EXPIRY TEST** (hard-won law 2's mirror). The case
    // record still opens the DIALOG; the day that control becomes a link, this
    // already names the address it must point at and the screen it must open.
    // A hold with no such test is a promise nobody is keeping.
    const html = render(detail());
    expect(html).toContain(`data-screen="${RECONNECT_SCREEN}"`);
    expect(html).toContain(`href="/brazosbend/disconnects/${CASE_NO}"`);
    // Not a protocol-relative URL to another host — the trap this file's
    // docstring names.
    expect(html).not.toContain('href="//disconnects');
  });
});

describe("what is still owed — 4.7", () => {
  it("is a table with every drawn line, not four lines in a box", () => {
    const html = render(detail(), 2);
    for (const code of ["arrears_at_the_cut", "reconnection_fee", "paid_since", "still_owed"]) {
      expect(html).toContain(`data-owed-line="${code}"`);
    }
  });

  it("draws transferred-up residue as its OWN line on a master — BR-CUS-1098", () => {
    const html = render(
      detail({
        account: { ...detail().account, account_kind: "master", account_class: "Commercial" },
        master: { is_master: true, units: 25, unit_accounts: 25 },
        owed: {
          ...detail().owed,
          lines: [
            {
              code: "own_debt_at_the_cut",
              from_code: "the_owners_account",
              amount: money("11940.00"),
              when: "2026-10-02",
              negative: false,
            },
            {
              code: "transferred_up_from_units",
              from_code: "occupying_accounts",
              amount: money("2450.00"),
              when: "2026-10-02",
              negative: false,
            },
          ],
        },
      }),
      2,
    );
    expect(html).toContain('data-owed-line="transferred_up_from_units"');
    expect(html).toContain('data-owed-line="own_debt_at_the_cut"');
  });

  it("draws neither of those on a regular account", () => {
    const html = render(detail(), 2);
    expect(html).not.toContain('data-owed-line="transferred_up_from_units"');
    expect(html).not.toContain('data-testid="reconnect-master"');
  });
});

describe("the balance warns and does not block — 4.2, BR-CUS-1097", () => {
  it("states the figure and gets out of the way", () => {
    const html = render(detail(), 2);
    expect(html).toContain('data-testid="reconnect-warning"');
    expect(html).toContain("139.80");
  });

  it("explains NOTHING — rationale is zero words on screen (B14 rule 33)", () => {
    // Rule 33: RATIONALE is REMOVED, never shortened. A Confirm screen that
    // explains the rule, the retention or what the product used to do breaks
    // rule 33 while trying to obey BR-CUS-1097.
    const html = render(detail(), 2);
    for (const word of ["BR-CUS", "retention", "audit log", "superseded", "DSC-02.4"]) {
      expect(html).not.toContain(word);
    }
  });

  it("draws no warning at all on a settled account", () => {
    const html = render(detail({ warning: null }), 2);
    expect(html).not.toContain('data-testid="reconnect-warning"');
  });
});

describe("the live refusal is reported rather than hidden — DEF-CUS-6742", () => {
  it("renders the reason as VISIBLE TEXT while the server would refuse", () => {
    // BR-SHL-025 — visible text, never a hover title, because a touch or
    // keyboard user never sees a tooltip.
    const html = render(detail());
    expect(html).toContain('data-testid="reconnect-refused"');
  });

  it("renders nothing when the server says it would accept", () => {
    const html = render(detail({ commit_refused_by: null }));
    expect(html).not.toContain('data-testid="reconnect-refused"');
  });
});

describe("the services table — 4.4 and 4.5", () => {
  it("offers + Add and a remove per row, from the kit's own table", () => {
    const html = render(detail());
    expect(html).toContain('data-testid="reconnect-add"');
    // The kit spells it `data-editable-table`; asserting the string this
    // screen PASSES rather than the one the DOM carries is a test that checks
    // my own source, not the product.
    expect(html).toContain('data-editable-table="reconnect-services"');
  });

  it("carries the act on the row, not merely a word", () => {
    const html = render(detail());
    expect(html).toContain("reconnect-raise-");
  });

  it("shows a raised order's reference and who it is with", () => {
    const html = render(
      detail({
        services: {
          ...detail().services,
          rows: [
            {
              ...detail().services.rows[0],
              work_order: { reference: "WO-26-0412", assignee: "Wilkes crew" },
            },
          ],
        },
      }),
    );
    expect(html).toContain("WO-26-0412");
    expect(html).toContain("Wilkes crew");
  });

  it("shows an em dash and never an invented meter", () => {
    const html = render(detail());
    expect(html).not.toContain("MTR-");
  });
});

describe("a master account — 4.3 and 4.6", () => {
  it("says the units come back together and offers no per-unit choice", () => {
    const html = render(
      detail({
        account: { ...detail().account, account_kind: "master", account_class: "Commercial" },
        master: { is_master: true, units: 25, unit_accounts: 25 },
      }),
    );
    expect(html).toContain('data-testid="reconnect-master"');
    expect(html).toContain("25");
  });

  it("names the account TYPE on both steps — the fact no reconnect surface had", () => {
    expect(render(detail())).toContain('data-testid="reconnect-account-facts"');
    expect(render(detail(), 2)).toContain('data-testid="reconnect-confirm-facts"');
  });
});

// ── CR-168-BRC10 lane FLOW-FIX · DEF-CUS-9630 ─────────────────────────────
describe("DEF-CUS-9630 — a raised reconnect job is counted and its state shown", () => {
  it("a row the server says carries an ACCEPTED job reads Accepted, and the count says 1 raised", () => {
    const html = render(
      detail({
        services: {
          ...detail().services,
          rows: [
            {
              ...detail().services.rows[0],
              work_order: { reference: "WO-0056", assignee: "R. Patel", done: true, accepted: true },
            },
          ],
        },
      }),
    );
    expect(html).toContain("WO-0056");
    expect(html).toContain("Accepted");
    expect(html).toContain("1 raised · 0 to raise");
  });

});
