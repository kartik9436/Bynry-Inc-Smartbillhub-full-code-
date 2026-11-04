// ── Trace ──────────────────────────────────────────────
// Defect:   DEF-PAY-10759 (L1-02 c/d) — the Cut result dropped what it skipped,
//           and the day picker printed the stored "10.000000 USD".
// Ruling:   decision log 2026-10-30 "Payments audit by level" — L1-02: "the cut
//           lists what it skipped; the day label formats money to 2 places".
// ───────────────────────────────────────────────────────
import { describe, expect, it } from "vitest";

import i18n from "@/i18n";
import { formatMoney } from "@/components/MoneyCell";

import { skippedLines } from "./DepositsPage";

const t = (key: string, params?: Record<string, unknown>) => i18n.t(key, params) as string;

describe("DEF-PAY-10759 — the cut says what it left out", () => {
  it("names the tester's six skipped store payments under one reason", () => {
    const skipped = ["0091", "0092", "0093", "0094", "0095", "0096"].map((n) => ({
      payment_no: `PY-${n}`,
      reason: "no_method",
    }));
    const lines = skippedLines(skipped, t);
    expect(lines).toHaveLength(1);
    expect(lines[0]).toContain("6 payments not banked");
    expect(lines[0]).toContain("no payment method");
    expect(lines[0]).toContain("PY-0091");
    expect(lines[0]).toContain("and 1 more");
    expect(lines[0]).not.toContain("PY-0096");
  });

  it("one line per reason; an unknown reason never shows its code", () => {
    const lines = skippedLines(
      [
        { payment_no: "PY-1", reason: "held_until_bankable" },
        { payment_no: "PY-2", reason: "something_new" },
      ],
      t,
    );
    expect(lines).toEqual([
      "1 payment not banked (held until its date): PY-1",
      "1 payment not banked (not bankable today): PY-2",
    ]);
  });

  it("nothing skipped says nothing", () => {
    expect(skippedLines([], t)).toEqual([]);
  });

  it("the day label's money is the 2-place formatter's, never the stored string", () => {
    expect(formatMoney("10.000000", "USD", "en-US")).toBe("$10.00");
    expect(formatMoney("832.800000", "USD", "en-US")).toBe("$832.80");
  });
});
