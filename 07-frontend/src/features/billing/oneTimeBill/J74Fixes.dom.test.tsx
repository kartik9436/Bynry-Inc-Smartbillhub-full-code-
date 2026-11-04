// @vitest-environment jsdom
/**
 * J74's fixes on the one-time bill page (2026-09-30):
 *  - DEF-BIL-8565 — the Review footer adds up: a first bill's deposit and
 *    connection charge sit on their own "One-time charges" line.
 *  - DEF-BIL-8561 — a catch-up's Review prints one group per month.
 *  - DEF-BIL-8562 — an interim meter with no reading can be ESTIMATED on
 *    step 2, and the request asks the server for the meter's own estimate.
 */
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import i18n from "i18next";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import type {
  OneTimeBillDocument,
  OneTimeBillPreview,
  OneTimeBillReadingRow,
} from "@/api/billingOpsEndpoints";

import { BillPreview } from "./ReviewStep";
import { ReadingsPanel } from "./ServicesStep";
import { emptyForm, readingsReady, requestBody } from "./oneTimeBillModel";
import type { OneTimeBillForm } from "./oneTimeBillModel";
import type { OtbFormat } from "./oneTimeBillShared";

afterEach(cleanup);

const t = (key: string, params?: Record<string, unknown>) => i18n.t(key, params) as string;
const fmt: OtbFormat = {
  t,
  currency: "USD",
  timeZone: "America/Chicago",
  dateFormat: "MM/DD/YYYY",
};

function renderBill(document: OneTimeBillDocument, kind: "first" | "backbill") {
  render(
    <BillPreview
      kind={kind}
      bill={document}
      customer="Maria Alvarez"
      accountLine="AC-2026-00056"
      billDate="2026-09-30"
      dueDate="2026-10-21"
      period={null}
      warnings={[]}
      t={t}
      fmt={fmt}
    />,
  );
}

const water = (amount: string) => ({
  service: "water",
  asset_label: "W-10442C",
  charge: "usage" as const,
  code: null,
  quantity: "8.6",
  unit: "kgal",
  rate: "tiered",
  amount,
  flags: [],
});

describe("DEF-BIL-8565 — the footer adds up", () => {
  it("prints One-time charges $195.00 between Tax and Total due on a first bill", () => {
    renderBill(
      {
        groups: [
          {
            label: "period",
            period_start: "2026-09-13",
            period_end: "2026-09-30",
            subtotal: "198.8400",
            lines: [water("198.8400")],
          },
          {
            label: "move_in_charges",
            period_start: null,
            period_end: null,
            subtotal: "195.0000",
            lines: [
              {
                service: "Security deposit",
                asset_label: null,
                charge: "deposit",
                code: null,
                quantity: null,
                unit: null,
                rate: null,
                amount: "150.0000",
                flags: [],
              },
              {
                service: "Connection fee",
                asset_label: null,
                charge: "fee",
                code: "CONN",
                quantity: "1",
                unit: null,
                rate: "45.0000",
                amount: "45.0000",
                flags: [],
              },
            ],
          },
        ],
        subtotal: "198.8400",
        tax: [{ label: "Tax Local", rate: "2.000000", amount: "3.9800" }],
        one_time_charges: "195.0000",
        total: "397.8200",
        currency: "USD",
      },
      "first",
    );
    const row = document.querySelector("[data-bill-one-time]");
    expect(row, "DEF-BIL-8565: no One-time charges footer line").not.toBeNull();
    expect(row).toHaveTextContent("One-time charges$195.00");
  });
});

describe("DEF-BIL-8561 — one group per month", () => {
  it("draws each month's own subtotal", () => {
    renderBill(
      {
        groups: [
          {
            label: "period",
            period_start: "2026-08-01",
            period_end: "2026-08-31",
            subtotal: "32.5000",
            lines: [water("32.5000")],
          },
          {
            label: "period",
            period_start: "2026-09-01",
            period_end: "2026-09-30",
            subtotal: "65.0000",
            lines: [water("65.0000")],
          },
        ],
        subtotal: "97.5000",
        tax: [],
        total: "97.5000",
        currency: "USD",
      },
      "backbill",
    );
    const groups = document.querySelectorAll("[data-bill-group]");
    expect(groups).toHaveLength(2);
    expect(groups[0]).toHaveTextContent("08/01/2026 – 08/31/2026$32.50");
    expect(groups[1]).toHaveTextContent("09/01/2026 – 09/30/2026$65.00");
  });
});

describe("DEF-BIL-8562 — an interim meter estimated on step 2", () => {
  const waiting: OneTimeBillReadingRow = {
    asset_id: "m-460",
    label: "W-10460",
    unit: "kgal",
    previous: { value: "312.4", read_at: "2026-08-31", on_file: true },
    current: { value: null, read_at: "2026-09-30", fixed_date: false },
    usage: null,
    status: "waiting",
    refusal_key: null,
    period_index: null,
  };
  const preview = {
    account: { moved_in_on: null },
    services: [
      { service: "water", assets: [{ asset_id: "m-460", label: "W-10460" }], status: "billed" },
    ],
    readings: { needed: "every_meter", rows: [waiting] },
  } as unknown as OneTimeBillPreview;

  it("asks the server for the meter's own estimate, and needs no reading typed", () => {
    const form: OneTimeBillForm = {
      ...emptyForm("interim", "2026-09-30"),
      estimates: { "m-460": "water" },
    };
    expect(requestBody(form, [waiting]).readings).toEqual([
      { asset_id: "m-460", read_at: "2026-09-30", value: "", role: "estimate", service: "water" },
    ]);
    expect(readingsReady(form, preview)).toBe(true);
    expect(readingsReady(emptyForm("interim", "2026-09-30"), preview)).toBe(false);
  });

  it("offers an Estimate button on the waiting row, and it asks for the estimate", () => {
    const asked: [string, string | null][] = [];
    render(
      <MemoryRouter>
        <ReadingsPanel
          preview={preview}
          form={emptyForm("interim", "2026-09-30")}
          onChange={() => undefined}
          onEstimate={(asset, service) => asked.push([asset, service])}
          readsHref="/reads"
          t={t}
          fmt={fmt}
        />
      </MemoryRouter>,
    );
    fireEvent.click(screen.getByRole("button", { name: "Estimate W-10460" }));
    expect(asked).toEqual([["m-460", "water"]]);
  });
});
