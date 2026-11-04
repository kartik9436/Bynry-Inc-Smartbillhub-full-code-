// @vitest-environment jsdom
// DEF-BIL-10052 (PO 2026-10-11) — when the draft bill cannot be priced, step 3
// says it is not generated and lists EVERY missing value, with a way back.
import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import { DraftBill } from "./moveOutTables";
import type { FinalBillPreview } from "./moveShared";

afterEach(cleanup);

const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

function preview(over: Partial<FinalBillPreview>): FinalBillPreview {
  return {
    priced: false,
    lines: [],
    total: null,
    subtotal: null,
    taxTotal: null,
    currency: "USD",
    periodStart: "2026-08-01",
    periodEnd: "2026-10-14",
    fromUncommittedReads: false,
    unavailable: null,
    unavailableDetail: null,
    ...over,
  } as FinalBillPreview;
}

describe("DEF-BIL-10052 · the draft bill names every missing value", () => {
  it("lists all of them by service and meter, never the engine's sentence, and goes back to readings", () => {
    const back: string[] = [];
    render(
      <DraftBill
        preview={preview({
          unavailable: "values_missing",
          unavailableDetail: "account AC-2026-00043: water still has no usable read and no decision. BR-BIL-015",
          missing: [
            { service: "water", meters: ["AST-04412"], what: "reading" },
            { service: "electric", meters: ["E-1001"], what: "estimate_no_history" },
          ],
        })}
        timeZone="America/Chicago"
        dateFormat="MM/DD/YYYY"
        t={t}
        onBackToReadings={() => back.push("back")}
      />,
    );
    expect(screen.getByText(t("customers.moveOut.draftBill.notGenerated"))).toBeInTheDocument();
    const items = document.querySelectorAll("[data-final-bill-missing] li");
    expect(items).toHaveLength(2);
    expect(items[0].textContent).toContain("AST-04412");
    expect(items[1].textContent).toContain("E-1001");
    expect(document.body.textContent).not.toContain("BR-BIL-015");
    fireEvent.click(document.querySelector("[data-back-to-readings]") as HTMLButtonElement);
    expect(back).toEqual(["back"]);
  });
});
