// @vitest-environment jsdom
/**
 * DEF-BIL-8328 — a catch-up period whose meter still waits for its reading
 * says Waiting, never Actual (PO walk on 2.412.4, `6a-catch-up-waiting.png`).
 * The status itself is the server's (`one_time_answer._periods`); this proves
 * the table can print the fourth word the server now sends.
 */
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { cleanup, render, screen } from "@testing-library/react";
import i18n from "i18next";
import { afterEach, describe, expect, it } from "vitest";

import { PeriodsTable } from "./ServicesStep";
import type { OtbFormat } from "./oneTimeBillShared";

afterEach(cleanup);

const t = (key: string, params?: Record<string, unknown>) => i18n.t(key, params) as string;
const fmt: OtbFormat = { t, currency: "USD", timeZone: "America/Chicago", dateFormat: "MM/DD/YYYY" };

describe("DEF-BIL-8328 — the Periods table says what each period is priced on", () => {
  it("prints Waiting for a period with no reading yet, and Estimated for a shared one", () => {
    render(
      <PeriodsTable
        periods={[
          { period_start: "2026-07-01", period_end: "2026-07-15", days: 15, versions: [], reading: "estimated", split_on: null },
          { period_start: "2026-07-16", period_end: "2026-07-31", days: 16, versions: [], reading: "waiting", split_on: null },
        ]}
        t={t}
        fmt={fmt}
      />,
    );
    expect(screen.getByText("Waiting")).toBeInTheDocument();
    expect(screen.getByText("Estimated")).toBeInTheDocument();
    expect(screen.queryByText("Actual")).not.toBeInTheDocument();
  });
});
