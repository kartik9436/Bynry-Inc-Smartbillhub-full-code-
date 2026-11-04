/**
 * DEF-BIL-10201 (PO 2026-10-17: a late fee is flat OR a percentage with an
 * optional minimum) — a percent penalty at 0% with no minimum charges $0.00 on
 * every bill, so the charge-code form refuses it before the server does.
 */
import { describe, expect, it } from "vitest";

import { penaltyChargesNothing } from "./chargeCodeModel";

describe("DEF-BIL-10201 · a 0% penalty with no minimum means nothing", () => {
  it.each([
    ["0", "", true],
    ["0.00", "0", true],
    ["0", "5.00", false],
    ["1.5", "", false],
    ["1.50", "5.00", false],
    ["", "", false],
  ])("percent %j, minimum %j → refused %s", (percent, minimum, refused) => {
    expect(penaltyChargesNothing({ percent, minimum })).toBe(refused);
  });
});
