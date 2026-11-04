// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defect:  `DEF-PAY-10734` (tester payments audit L2-03, 2026-10-30, imgs
//          25-27) — a counter payment read "Counter · Nobody named"; a Hy-Vee
//          store file payment read Source "Mail".
// ───────────────────────────────────────────────────────
// RED FIRST: against the tip the counter case drew "Nobody named" (the server
// sent `taken_by: null`, and this strip had no till code to draw) and the
// import case drew "Mail".
import "@/i18n";

import { cleanup, render } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import type { PaymentSource } from "@/api/paymentDetailEndpoints";
import i18n from "@/i18n";

import { PaymentHeaderStrip } from "./paymentDetailShared";

const t = (key: string): string => i18n.t(key);

afterEach(cleanup);

function strip(source: Partial<PaymentSource>) {
  cleanup();
  const full: PaymentSource = {
    origin: "entry",
    origin_is_derived: false,
    taken_by: null,
    counter_session_ref: null,
    import_kind: null,
    ...source,
  };
  const { getByTestId } = render(
    <PaymentHeaderStrip source={full} batchRef={null} reconciled={null} status="posted" />,
  );
  return getByTestId("payment-header-strip").textContent ?? "";
}

describe("DEF-PAY-10734 — the Source cell says where the money came from and who took it", () => {
  it("a counter payment names the clerk and the till", () => {
    const text = strip({ taken_by: "Dana Whitfield", counter_session_ref: "CTR-261021-BS-4" });
    expect(text).toContain("Dana Whitfield · CTR-261021-BS-4");
    expect(text).not.toContain(t("payments.detail.noTakenBy"));
  });

  it("a lockbox import reads Lockbox and a file import reads File — never Mail", () => {
    expect(strip({ origin: "import", import_kind: "lockbox" })).toContain(
      t("payments.source.importKind.lockbox"),
    );
    const file = strip({ origin: "import", import_kind: "file" });
    expect(file).toContain(t("payments.source.importKind.file"));
    expect(file).not.toContain("Mail");
  });

  // DEF-PAY-10759 (L1-02 b) — the LIST's Source cell and filter read the same
  // word as this page; it said "Mail" for every imported payment.
  it("the list's word for an import is the page's word, not Mail", () => {
    expect(t("payments.source.import")).toBe(t("payments.source.importKind.file"));
    expect(t("payments.source.import")).not.toBe("Mail");
  });

  // PO 2026-10-30 Q6 — the network name from the file's Network column.
  it("a Hy-Vee row reads Store · Hy-Vee on the payment page, not File", () => {
    const text = strip({ origin: "import", import_kind: "file", store_network: "Hy-Vee" });
    expect(text).toContain("Store · Hy-Vee");
    expect(text).not.toContain(t("payments.source.importKind.file"));
  });

  it("a payment nobody is named on still says so (law 7, habit 2)", () => {
    expect(strip({})).toContain(t("payments.detail.noTakenBy"));
  });
});
