/**
 * The one-time bill's rules without a DOM — design §2 (step-1 fields by
 * kind), the contract's request body, the problems list and the aside's counts.
 * Every figure here is an illustration of a shape (B14 rule 37).
 */
import { describe, expect, it } from "vitest";

import type { OneTimeBillPreview, OneTimeBillReadingRow } from "@/api/billingOpsEndpoints";

import {
  accountProblems,
  addDays,
  chargeCodeRule,
  clientProblems,
  derivedDueDate,
  draftExtras,
  editableRoles,
  emptyForm,
  hasServiceSections,
  mergeProblems,
  parseDueDays,
  readingKey,
  readingsReady,
  requestBody,
  serviceCounts,
  summaryLine,
  takesPeriodList,
  takesWindow,
} from "./oneTimeBillModel";

const TODAY = "2026-09-30";

function row(overrides: Partial<OneTimeBillReadingRow> = {}): OneTimeBillReadingRow {
  return {
    asset_id: "a1",
    label: "W-10442",
    unit: "kgal",
    previous: { value: "482.3", read_at: "2026-08-31", on_file: true },
    current: { value: null, read_at: "2026-09-30", fixed_date: false },
    usage: null,
    status: "waiting",
    refusal_key: null,
    period_index: null,
    ...overrides,
  };
}

describe("design §2 — which fields each kind asks for", () => {
  it("gives interim, first and final one window, and catch-up and penalty a list", () => {
    expect(["interim", "first", "final"].every((k) => takesWindow(k as never))).toBe(true);
    expect(["backbill", "penalty"].every((k) => takesPeriodList(k as never))).toBe(true);
    expect(takesWindow("fee")).toBe(false);
    expect(takesPeriodList("fee")).toBe(false);
  });

  it("requires a charge code on a fee, offers one on a penalty, and nowhere else", () => {
    expect(chargeCodeRule("fee")).toBe("required");
    expect(chargeCodeRule("penalty")).toBe("optional");
    expect(chargeCodeRule("interim")).toBe("absent");
  });

  it("gives a fee no services, rates or readings", () => {
    expect(hasServiceSections("fee")).toBe(false);
    expect(hasServiceSections("backbill")).toBe(true);
  });
});

describe("dates — the due date is bill date + days to pay", () => {
  it("adds calendar days across a month end", () => {
    expect(addDays("2026-09-30", 21)).toBe("2026-10-21");
  });

  it("treats zero days as lawful and blank or fractional as no due date", () => {
    expect(parseDueDays("0")).toBe(0);
    expect(parseDueDays("")).toBeNull();
    expect(parseDueDays("2.5")).toBeNull();
    expect(derivedDueDate({ billDate: "2026-09-30", dueDays: "" })).toBeNull();
  });
});

describe("contract §2 — the request body", () => {
  it("sends the window for interim and a sub-period list for catch-up", () => {
    const interim = { ...emptyForm("interim", TODAY), accountId: "acc", periodStart: "2026-09-01", periodEnd: "2026-09-30", dueDays: "21" };
    const body = requestBody(interim);
    expect(body).toMatchObject({ kind: "interim", period_start: "2026-09-01", period_end: "2026-09-30", bill_date: TODAY, due_days: 21 });
    expect(body.sub_periods).toBeUndefined();

    const catchUp = {
      ...emptyForm("backbill", TODAY),
      accountId: "acc",
      periods: [{ start: "2026-06-01", end: "2026-06-30" }],
      reasonCode: "MISSED",
    };
    const body2 = requestBody(catchUp);
    expect(body2.sub_periods).toEqual([{ period_start: "2026-06-01", period_end: "2026-06-30" }]);
    expect(body2.reason_code).toBe("MISSED");
    expect(body2.period_start).toBeUndefined();
  });

  it("puts the three clerk words on the DRAFT only for their own kind (contract §6)", () => {
    const choices = { settlementPath: "payment_plan", evidence: " Bypass pipe found ", note: "Reset meter" };
    expect(draftExtras("final", choices, ["collect", "payment_plan"])).toEqual({ settlement_path: "payment_plan" });
    // A path the server did not offer for this remainder is never sent.
    expect(draftExtras("final", choices, ["collect"])).toEqual({});
    expect(draftExtras("penalty", choices)).toEqual({ evidence: "Bypass pipe found" });
    expect(draftExtras("fee", choices)).toEqual({ note: "Reset meter" });
    expect(draftExtras("interim", choices, ["payment_plan"])).toEqual({});
    // …and never on the preview body, which prices nothing from them.
    const fee = { ...emptyForm("fee", TODAY), accountId: "acc", chargeCode: "RECON", dueDays: "21" };
    expect(requestBody(fee)).not.toHaveProperty("note");
  });

  it("DEF-RAT-8753 — a code priced 'entered when used' sends the clerk's amount, and only that code", () => {
    const fee = { ...emptyForm("fee", TODAY), accountId: "acc", chargeCode: "TAP", dueDays: "21" };
    const entered = { ...fee, chargeEntered: true, enteredAmount: " 1250.00 " };
    expect(requestBody(entered).entered_amount).toBe("1250.00");
    // A code that states its own price never carries a typed figure (BR-BIL-020).
    expect(requestBody({ ...fee, enteredAmount: "1250.00" })).not.toHaveProperty("entered_amount");
    // An entered-when-used code with no amount is a step-1 problem, named.
    expect(clientProblems({ ...fee, chargeEntered: true, enteredAmount: "" }).map((p) => p.field)).toContain(
      "entered_amount",
    );
    expect(clientProblems(fee).map((p) => p.field)).not.toContain("entered_amount");
  });

  it("sends an empty days-to-pay as null so the server names it in the same pass", () => {
    expect(requestBody(emptyForm("fee", TODAY)).due_days).toBeNull();
  });

  it("sends typed readings with their role, and none that were left blank", () => {
    const r = row();
    const form = {
      ...emptyForm("interim", TODAY),
      readings: { [readingKey(r, "current")]: { value: "488.4", readAt: "" } },
    };
    expect(requestBody(form, [r]).readings).toEqual([
      { asset_id: "a1", read_at: "2026-09-30", value: "488.4", role: "current" },
    ]);
    expect(requestBody(emptyForm("interim", TODAY), [r]).readings).toBeUndefined();
  });
});

describe("problems — all at once, each on its field", () => {
  it("names every missing field on an empty catch-up in one pass", () => {
    const fields = clientProblems({ ...emptyForm("backbill", TODAY), billDate: "" }).map((p) => p.field);
    expect(fields).toEqual([
      "account_id",
      "sub_periods[0].period_start",
      "sub_periods[0].period_end",
      "reason_code",
      "bill_date",
      "due_days",
    ]);
  });

  it("says which period ends before it starts, in the summary as drawn", () => {
    const form = {
      ...emptyForm("backbill", TODAY),
      accountId: "acc",
      reasonCode: "MISSED",
      dueDays: "21",
      periods: [
        { start: "2026-06-01", end: "2026-06-30" },
        { start: "2026-07-01", end: "2026-06-15" },
      ],
    };
    const [problem] = clientProblems(form);
    expect(problem).toEqual({
      field: "sub_periods[1].period_end",
      messageKey: "billing.oneTime.err.periodEndsBeforeStart",
    });
    expect(summaryLine(problem)).toEqual({
      key: "billing.oneTimeBill.problem.subPeriodEndsBeforeStart",
      params: { n: 2 },
    });
  });

  it("keeps one sentence per field when the server names a field the screen already did", () => {
    const merged = mergeProblems(
      [{ field: "due_days", messageKey: "billing.oneTime.err.dueDaysRequired" }],
      [
        { field: "due_days", messageKey: "billing.oneTime.err.dueDaysInvalid" },
        { field: "reason_code", messageKey: "billing.oneTime.err.reasonUnknown" },
      ],
    );
    expect(merged.map((p) => p.messageKey)).toEqual([
      "billing.oneTime.err.dueDaysRequired",
      "billing.oneTime.err.reasonUnknown",
    ]);
  });
});

describe("design §4 — which readings the clerk types", () => {
  it("asks a first bill for a move-in reading only where none is on file", () => {
    expect(editableRoles("first", row(), null)).toEqual(["current"]);
    expect(
      editableRoles("first", row({ previous: { value: null, read_at: null, on_file: false } }), null),
    ).toEqual(["move_in", "current"]);
  });

  it("asks catch-up for the last period only, and penalty for nothing", () => {
    expect(editableRoles("backbill", row({ period_index: 2 }), 2)).toEqual(["last_period"]);
    expect(editableRoles("backbill", row({ period_index: 1 }), 2)).toEqual([]);
    expect(editableRoles("penalty", row({ period_index: 2 }), 2)).toEqual([]);
  });

  it("holds step 2 until every needed reading is typed, and never over a refusal", () => {
    const r = row();
    const preview = { readings: { needed: "every_meter", rows: [r] } } as unknown as OneTimeBillPreview;
    const empty = emptyForm("interim", TODAY);
    expect(readingsReady(empty, preview)).toBe(false);
    const typed = { ...empty, readings: { [readingKey(r, "current")]: { value: "488.4", readAt: "" } } };
    expect(readingsReady(typed, preview)).toBe(true);
    const refused = { readings: { needed: "every_meter", rows: [{ ...r, status: "refused" }] } } as unknown as OneTimeBillPreview;
    expect(readingsReady(typed, refused)).toBe(false);
  });
});

describe("the aside's service counts", () => {
  it("counts follows-basis and base-zero as billed, and the two absences apart", () => {
    const base = { assets: [], basis_service: null, count: 1, on_bill: "" };
    expect(
      serviceCounts([
        { ...base, service: "water", status: "billed" },
        { ...base, service: "electric", status: "billed_base_zero" },
        { ...base, service: "sewer", status: "follows_basis" },
        { ...base, service: "gas", status: "not_in_service" },
        { ...base, service: "fire", status: "not_in_service" },
        { ...base, service: "broadband", status: "not_taken" },
      ]),
    ).toEqual({ billed: 3, notInService: 2, notTaken: 1 });
  });
});

describe("DEF-BIL-8322 / PO report 2.411.4 — periods against each other, and the move-in date", () => {
  it("names the overlapping row (the PO's Sep 30–Sep 30 beside Aug 30–Sep 30) and not the order", () => {
    const form = {
      ...emptyForm("penalty", TODAY),
      accountId: "a",
      reasonCode: "MISSED",
      dueDays: "2",
      periods: [
        { start: "2026-09-30", end: "2026-09-30" },
        { start: "2026-08-30", end: "2026-09-30" },
      ],
    };
    const overlaps = clientProblems(form).filter((p) => p.messageKey === "billing.oneTime.err.periodOverlaps");
    expect(overlaps.map((p) => p.field)).toEqual(["sub_periods[0].period_start"]);
    const reordered = {
      ...form,
      periods: [
        { start: "2026-09-01", end: "2026-09-30" },
        { start: "2026-08-01", end: "2026-08-31" },
      ],
    };
    expect(clientProblems(reordered).some((p) => p.messageKey === "billing.oneTime.err.periodOverlaps")).toBe(false);
  });

  it("a first bill's missing start is the MOVE-IN date, on its field", () => {
    const form = { ...emptyForm("first", TODAY), accountId: "a", periodEnd: "2026-09-30", dueDays: "21" };
    expect(clientProblems(form)).toContainEqual({
      field: "period_start",
      messageKey: "billing.oneTime.err.moveInRequired",
    });
  });
});

describe("BR-BIL-1066 / PO 2026-10-01 — an interim bill needs a cycle too", () => {
  const noCycle = { cycle_name: null };
  const onACycle = { cycle_name: "Monthly" };
  it("refuses first, final and interim on an account with no cycle", () => {
    for (const kind of ["first", "final", "interim"] as const) {
      expect(accountProblems(kind, noCycle)).toEqual([
        { field: "account_id", messageKey: "billing.oneTime.err.noBillingCycle" },
      ]);
      expect(accountProblems(kind, onACycle)).toEqual([]);
    }
  });
  it("leaves catch-up, penalty and fee alone", () => {
    for (const kind of ["backbill", "penalty", "fee"] as const) {
      expect(accountProblems(kind, noCycle)).toEqual([]);
    }
  });
});
