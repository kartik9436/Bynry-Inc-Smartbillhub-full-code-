// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Story:   US-MET-002 (S15 unit detail — the Account tab) · CR-089 wave I
//          Screens: S15 (PRM-03, Account)
// Spec:    04-docs/05-modules/04-metering/conformance/CR-089-p077-unit-account.md
//          — rows 1 (no group heading), 3 (`Last bill`), 5 (`BEFORE THIS`),
//          8 (a private note says nothing), 12 (`nothing booked`), 17/18
//          (order), 19–25 (labels), 29–32 (tier, pill and note shape)
// Defect:  DEF-MET-4766 — the tab leaves out facts the payload it already reads
//          is serving
// Rules:   B14 rule 4 (one primary) · the frame's RULES line ("the danger tier
//          for anything that ends service") · B14 rule 34 (one pair of words
//          per concept) · B14 rule 37 (a drawn figure is an illustration) ·
//          BR-MET-1161 (an address is walked from the premises) · DEF-127
// ───────────────────────────────────────────────────────
// ⚠ **NO DRAWN FIGURE IS ASSERTED HERE** (B14 rule 37, ratified 2026-09-10).
// The frame inks an account number, an address and a balance into this page and
// inks a DIFFERENT account and year for the same previous tenancy two pages
// later — illustrations of a shape, not facts. Every value below is the shared
// fixture's own.
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import type { AccountRow, UnitAccountResponse } from "@/api/endpoints";
import { ToastProvider } from "@/components/Toast";
import i18n from "@/i18n";

import {
  UnitDetailPage,
  previousTenancy,
  unitAccountQueryKey,
  unitAccountsQueryKey,
  unitDetailQueryKey,
} from "./UnitDetailPage";
import { premisesAssetsQueryKey } from "./PremisesDetailPage";
import { ACCOUNT, UNIT, UNIT_ID, quietAnswer } from "./unitAccountFixture";

const TEST_TENANT = "brazosbend";
const t = (key: string, params?: Record<string, unknown>) => i18n.t(key, params) as string;

/** The tenancy that held this unit before the current one, and its gap. */
const EARLIER: AccountRow = {
  ...ACCOUNT,
  id: "acc-earlier",
  account_no: "AC-EARLIER",
  name: "An Earlier Tenant",
  status_name: "Closed",
  opened_at: "2022-02-03",
  closed_at: "2024-03-05",
} as AccountRow;

/** Render the Account tab with an optional accounts read behind it. */
function renderAccount(
  answer: UnitAccountResponse,
  accounts: readonly AccountRow[] | undefined = undefined,
): string {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  client.setQueryData(unitDetailQueryKey(UNIT_ID), UNIT);
  client.setQueryData(unitAccountQueryKey(UNIT_ID), answer);
  if (accounts !== undefined) {
    client.setQueryData(unitAccountsQueryKey(UNIT_ID), {
      count: accounts.length,
      results: accounts,
    });
  }
  client.setQueryData(premisesAssetsQueryKey(UNIT.premises_id), {
    count: 0,
    next: null,
    previous: null,
    results: [],
  });
  // Mounted under the REAL path pattern (hard-won law 2's fixture clause).
  return renderToStaticMarkup(
    <QueryClientProvider client={client}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TEST_TENANT}/premises/units/${UNIT_ID}?tab=account`]}>
          <Routes>
            <Route path="/:tenant/premises/units/:unitId" element={<UnitDetailPage />} />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

/** What a reader sees: `renderToStaticMarkup` escapes apostrophes. */
function asRead(html: string): string {
  return html.replace(/&#x27;/g, "'").replace(/&quot;/g, '"').replace(/&amp;/g, "&");
}

/** The `<h4>` group headings of the tab, in the order they render. */
function groups(html: string): string[] {
  return [...html.matchAll(/<h4[^>]*>(.*?)<\/h4>/g)].map((m) => m[1].replace(/<[^>]*>/g, "").trim());
}

/** The `<dt>` labels of the tab, in the order they render. */
function labels(html: string): string[] {
  return [...html.matchAll(/<dt[^>]*>(.*?)<\/dt>/g)].map((m) => m[1].replace(/<[^>]*>/g, "").trim());
}

describe("U7 · the three drawn groups, each with its heading", () => {
  it("heads the FIRST group, whose key was ratified in eleven catalogues and rendered nowhere", () => {
    const html = renderAccount(quietAnswer(), [ACCOUNT]);
    expect(groups(html).slice(0, 3)).toEqual([
      t("metering.units.account.sectionAccount"),
      t("metering.units.account.sectionStanding"),
      t("metering.units.account.sectionBefore"),
    ]);
  });

  it("no longer draws a fourth group for how we reach them — the frame has ONE row", () => {
    const html = renderAccount(quietAnswer(), [ACCOUNT]);
    expect(asRead(html)).not.toContain(t("metering.units.account.sectionReach"));
    expect(labels(html)).toContain(t("metering.units.account.reach"));
  });

  it("names all three absences in that one row when nothing has been elected", () => {
    // Three rows to say "we have not been told anything" is three times the
    // reading for one fact. The stated absence is the answer.
    expect(asRead(renderAccount(quietAnswer(), [ACCOUNT]))).toContain(
      t("metering.units.account.reachNothing"),
    );
  });
});

describe("U7 · the rows the payload was already serving", () => {
  it("draws Last bill from the date this tab's own payload carries", () => {
    const answer = quietAnswer();
    answer.account = { ...ACCOUNT, last_bill_at: "2026-08-28" } as AccountRow;
    const html = renderAccount(answer, [ACCOUNT]);
    expect(labels(html)).toContain(t("metering.units.account.lastBill"));
  });

  it("says NEVER BILLED rather than dashing, because that is a real answer", () => {
    const answer = quietAnswer();
    answer.account = { ...ACCOUNT, last_bill_at: null } as AccountRow;
    expect(asRead(renderAccount(answer, [ACCOUNT]))).toContain(
      t("metering.units.account.lastBillNever"),
    );
  });

  it("names the previous tenancy and the gap after it, from the accounts read", () => {
    const html = renderAccount(quietAnswer(), [EARLIER, ACCOUNT]);
    expect(labels(html)).toContain(t("metering.units.account.previousAccount"));
    expect(labels(html)).toContain(t("metering.units.account.vacantBetween"));
    expect(html).toContain("An Earlier Tenant");
    // The gap says who the base charge reached, which is the whole point of
    // drawing it: it is the commonest opening-balance dispute there is.
    expect(asRead(html)).toContain(t("metering.units.account.vacantOwnerBilled"));
  });

  it("states a NONE for both rows when this is the first tenancy, never omitting them", () => {
    const html = renderAccount(quietAnswer(), [ACCOUNT]);
    expect(asRead(html)).toContain(t("metering.units.account.previousNone"));
  });

  it("walks the address to the building and says which address it is showing", () => {
    // CLAUDE.md hard rule 8: an address lives on `premises` and nowhere else,
    // and every other entity derives it by walking.
    const html = renderAccount(quietAnswer(), [ACCOUNT]);
    expect(labels(html)).toContain(t("metering.units.account.post"));
    expect(asRead(html)).toContain(UNIT.premise_address as string);
    expect(asRead(html)).toContain(t("metering.units.account.postFromBuilding"));
  });

  it("keeps the bad-address warning, on the row it is about", () => {
    // The frame draws no bad-address row; deleting a live signal because a
    // drawing omits it is a loss the drawing did not ask for, so it rides the
    // address it is a fact about.
    const answer = quietAnswer();
    answer.facts = { ...answer.facts!, reach: { ...answer.facts!.reach, bad_address: true } };
    const html = renderAccount(answer, [ACCOUNT]);
    expect(html).toContain('data-bad-address=""');
    expect(asRead(html)).toContain(t("metering.units.account.postCameBack"));
  });
});

describe("U7 · order, tier and the words", () => {
  it("opens THE MONEY on Owed and puts Deposit held before Autopay", () => {
    const html = renderAccount(quietAnswer(), [ACCOUNT]);
    // ⚠ **`<dt>` AND NOT `>Owed<`.** The KPI tile above the tab is ALSO
    // labelled `Owed` (they are the same fact, which is the point), so a bare
    // string search finds the tile and reports the row as being above its own
    // heading — a false RED that reads exactly like a broken order.
    const owed = html.indexOf(`<dt>${t("metering.units.account.balance")}</dt>`);
    const deposit = html.indexOf(`<dt>${t("metering.units.account.deposit")}</dt>`);
    const autopay = html.indexOf(`<dt>${t("metering.units.account.autopay")}</dt>`);
    const money = html.indexOf(t("metering.units.account.sectionStanding"));
    expect(owed).toBeGreaterThan(money);
    expect(deposit).toBeGreaterThan(owed);
    expect(autopay).toBeGreaterThan(deposit);
  });

  it("draws no Start date row of its own — the open date is the Status row's qualifier", () => {
    const html = renderAccount(quietAnswer(), [ACCOUNT]);
    expect(labels(html)).not.toContain(t("metering.units.account.start"));
    expect(asRead(html)).toContain(
      t("metering.units.account.sinceDate", { date: "03/12/2024" }),
    );
  });

  it("renders the account status as a pill, so colour is never the only signal", () => {
    const html = renderAccount(quietAnswer(), [ACCOUNT]);
    expect(html).toMatch(/<span class="pill[^"]*">Active</);
  });

  it("puts Move-out in the DANGER tier, because it ends service", () => {
    const html = renderAccount(quietAnswer(), [ACCOUNT]);
    const moveOut = html.slice(0, html.indexOf(t("metering.units.account.moveOut")));
    const button = moveOut.lastIndexOf("<button");
    expect(moveOut.slice(button)).toContain('data-variant="danger"');
  });

  it("puts Change status in the DANGER tier too", () => {
    const html = renderAccount(quietAnswer(), [ACCOUNT]);
    const upTo = html.slice(0, html.indexOf(t("metering.status.action")));
    expect(upTo.slice(upTo.lastIndexOf("<button"))).toContain('data-variant="danger"');
  });

  it("uses the drawn words for the four labels that were reworded", () => {
    expect(t("metering.units.account.balance")).toBe("Owed");
    expect(t("metering.units.account.legacyRef")).toBe("In the old system");
    expect(t("metering.units.account.open")).toBe("Open the account →");
    expect(t("metering.units.account.sectionStanding")).toBe("The money");
  });
});

describe("U7 · the notes read as rows, and both visibility states are words", () => {
  const withNotes = (): UnitAccountResponse => {
    const answer = quietAnswer();
    answer.facts = {
      ...answer.facts!,
      notes: [
        {
          id: "n1",
          title: "Medical protection",
          body: "Certificate received.",
          pinned: true,
          customer_visible: false,
          author_id: "u1",
          author_name: null,
          created_at: "2026-08-04",
        },
        {
          id: "n2",
          title: "Meter access",
          body: "Ring first.",
          pinned: false,
          customer_visible: true,
          author_id: "u2",
          author_name: null,
          created_at: "2026-06-12",
        },
      ],
    } as UnitAccountResponse["facts"];
    return answer;
  };

  it("carries a count chip beside the heading", () => {
    const html = renderAccount(withNotes(), [ACCOUNT]);
    expect(html).toMatch(/data-chip="resting"[^>]*>[\s\S]{0,80}2</);
  });

  it("says a PRIVATE note is private, which is the state that used to say nothing", () => {
    const html = renderAccount(withNotes(), [ACCOUNT]);
    expect(asRead(html)).toContain(t("metering.units.account.notePrivate"));
    expect(asRead(html)).toContain(t("customers.account.note.customerVisiblePill"));
  });

  it("draws them as label/value rows rather than a bullet list", () => {
    const html = renderAccount(withNotes(), [ACCOUNT]);
    expect(html).not.toContain('data-testid="unit-account-notes"');
    expect(labels(html).some((label) => label.includes("Meter access"))).toBe(true);
  });
});

describe("U7 · previousTenancy is one derivation, shared with the Occupancy tab", () => {
  it("reads the entry before the current one off the shared timeline", () => {
    const answer = previousTenancy([EARLIER, ACCOUNT], ACCOUNT.id, "2026-09-10");
    expect(answer.previous?.id).toBe(EARLIER.id);
    // EARLIER closed 2024-03-05, ACCOUNT opened 2024-03-12 — the gap is the
    // days BETWEEN, which is the Occupancy tab's own convention.
    expect(answer.gap?.days).toBe(6);
    expect(answer.gap?.from).toBe("2024-03-06");
    expect(answer.gap?.to).toBe("2024-03-11");
  });

  it("answers nothing for the first tenancy a unit ever had", () => {
    expect(previousTenancy([ACCOUNT], ACCOUNT.id, "2026-09-10")).toEqual({
      previous: null,
      gap: null,
    });
  });

  it("reports the previous tenancy with NO gap when they were back to back", () => {
    const backToBack = { ...EARLIER, closed_at: "2024-03-11" } as AccountRow;
    const answer = previousTenancy([backToBack, ACCOUNT], ACCOUNT.id, "2026-09-10");
    expect(answer.previous?.id).toBe(backToBack.id);
    expect(answer.gap).toBeNull();
  });
});

describe("U7 · the tiles the whole page carries", () => {
  it("no longer renders '2 bill' — the ASSETS tile uses the drawn wording", () => {
    expect(t("metering.units.kpi.assetsSplit", { metered: 2, behind: 3 })).toBe(
      "2 metered · 3 behind the meter",
    );
    // The premises tile one screen away says the same sentence for the same
    // concept, so the two cannot drift (B14 rule 34).
    expect(t("metering.units.kpi.assetsSplit", { metered: 2, behind: 3 })).toBe(
      t("metering.premises.kpi.assetsSplit", { metered: 2, behind: 3 }),
    );
  });
});
