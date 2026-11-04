// @vitest-environment jsdom
// DEF-CUS-10093 (PO 2026-10-13, option B) — Complete drafts the final bill.
// The completion screen names the draft (number and amount) and links to the
// bill's own page; a refused draft is shown with the engine's own reason.
import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";
import { ApiError } from "@/api/client";
import { resolveScreen } from "@/routing/screenIds";

import { MoveOutFinalBillFact, moveOutRefusalText } from "./MoveOutWizard";

afterEach(cleanup);

const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

function mount(node: React.ReactNode) {
  return render(
    <MemoryRouter initialEntries={["/brazosbend/accounts/a1/move-out"]}>
      <Routes>
        <Route path="/:tenant/accounts/:accountId/move-out" element={node} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("DEF-CUS-10093 · the completion screen names the final draft", () => {
  it("shows the bill number, the amount and Draft, linked to the bill page", () => {
    mount(
      <MoveOutFinalBillFact
        finalBill={{
          outcome: "drafted",
          invoice_id: "4f1c2d8e-0000-4000-8000-000000000001",
          invoice_no: "BL-2610-000140",
          total: "186.3600",
          currency: "USD",
          period_start: "2026-10-01",
          period_end: "2026-10-12",
        }}
        t={t}
      />,
    );
    const link = screen.getByRole("link", { name: "BL-2610-000140" });
    const href = link.getAttribute("href") ?? "";
    expect(href).toBe("/brazosbend/billing/bills/4f1c2d8e-0000-4000-8000-000000000001");
    expect(resolveScreen(href).route?.path).toBe("/:tenant/billing/bills/:invoiceId");
    const text = document.body.textContent ?? "";
    expect(text).toContain("$186.36");
    expect(text).toContain("Draft");
    // B14 rule 31 — the id is the link's target, never its visible value.
    expect(text).not.toContain("4f1c2d8e");
  });

  it("says Already billed when an issued bill covered the move day", () => {
    mount(
      <MoveOutFinalBillFact
        finalBill={{ outcome: "nothing_to_bill", period_start: "2026-10-13", period_end: "2026-10-12" }}
        t={t}
      />,
    );
    expect(document.body.textContent).toBe("Already billed");
  });

  it("shows the refusal with billing's own reason after it", () => {
    const refused = new ApiError(409, {
      code: "BIZ-STATE",
      message_key: "customers.move_out.final_bill_not_drafted",
      br_ref: "BR-BIL-013 · DEF-CUS-10093",
      params: { cause_key: "billing.oneTime.err.noBillingCycle", reason: "no_billing_cycle" },
    });
    expect(moveOutRefusalText(refused, t)).toBe(
      "Final bill not created. Account still open. No billing cycle. Assign one on the account.",
    );
    const bare = new ApiError(409, {
      code: "BIZ-STATE",
      message_key: "customers.move_out.final_bill_not_drafted",
      params: { cause_key: "not.a.real.key" },
    });
    expect(moveOutRefusalText(bare, t)).toBe("Final bill not created. Account still open.");
  });
});
