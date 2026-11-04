// @vitest-environment jsdom
/**
 * DEF-BIL-10067 / 10068 / 10069 — the one-time bill's screen half of the PO's
 * rulings of 2026-10-12.
 *
 *   * OTB-1 — the usage recalculates as the reading is typed: 4.6 − 2.9 = 1.7.
 *   * OTB-2/3/4 — the Rates table shows two lines per CHANGED service, each
 *     with its dates, usage share, rate and amount.
 *   * OTB-10/17 — a DRAFT for the period reads *Draft already exists for this
 *     period.* with Open draft and Discard draft; an issued one keeps *Already
 *     billed for this period.*
 *   * OTB-18 — *August is closed. Posts to October.*
 *   * OTB-6 — a one-time draft's page carries Approve and Cancel draft, and
 *     Cancel goes through the existing discard after a confirm.
 */
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import i18n from "i18next";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ApiClient } from "@/api/client";
import type { OneTimeBillDuplicate, OneTimeBillRateRow } from "@/api/billingOpsEndpoints";

import { DraftDecision } from "./DraftDecision";
import { AlreadyBilledBanner, ClosedMonthNote } from "./OneTimeSummary";
import { RatesTable, liveUsage } from "./ServicesStep";
import type { OtbFormat } from "./oneTimeBillShared";

afterEach(cleanup);

const t = (key: string, params?: Record<string, unknown>) => i18n.t(key, params) as string;
const fmt: OtbFormat = { t, currency: "USD", timeZone: "America/Chicago", dateFormat: "MM/DD/YYYY" };

describe("OTB-1 — usage recalculates from the typed reading", () => {
  it("4.6 typed over 2.9 is 1.7, exactly", () => {
    expect(liveUsage("2.9", "4.6")).toBe("1.7000");
  });
  it("an empty box, a non-number or no previous reading leaves the server's figure", () => {
    expect(liveUsage("2.9", "")).toBeNull();
    expect(liveUsage("2.9", "4.6x")).toBeNull();
    expect(liveUsage(null, "4.6")).toBeNull();
  });
});

const water: OneTimeBillRateRow = {
  service: "water",
  asset_id: null,
  asset_label: "W-9011",
  rate_type: "tiered",
  usage_rate: { tiers: [{ up_to: null, unit: "kgal", price: "4.4000" }] },
  base_charge: { amount: "8.0000", code: "BASE-W", set: true, per_asset: false, prorated: null },
  minimum: null,
  versions: [
    { label: "Water", from: "2026-01-01" },
    { label: "Water", from: "2026-09-15" },
  ],
  amount: "15.1600",
  parts: [
    {
      period_start: "2026-09-01",
      period_end: "2026-09-14",
      days: 14,
      usage_rate: { tiers: [{ up_to: null, unit: "kgal", price: "4.0000" }] },
      quantity: "0.793333",
      unit: "kgal",
      amount: "3.1700",
      version_label: "Water",
      version_from: "2026-01-01",
    },
    {
      period_start: "2026-09-15",
      period_end: "2026-09-30",
      days: 16,
      usage_rate: { tiers: [{ up_to: null, unit: "kgal", price: "4.4000" }] },
      quantity: "0.906667",
      unit: "kgal",
      amount: "3.9900",
      version_label: "Water",
      version_from: "2026-09-15",
    },
  ],
};

const trash: OneTimeBillRateRow = {
  service: "trash",
  asset_id: null,
  asset_label: null,
  rate_type: "per_asset",
  usage_rate: { price: "15.0000", unit: "cart" },
  base_charge: null,
  minimum: null,
  versions: [{ label: "Trash", from: "2026-01-01" }],
  amount: "15.0000",
};

describe("OTB-2/3/4 — two lines per changed service, none for an unchanged one", () => {
  it("water shows its two parts with dates, usage share and amount; trash shows none", () => {
    render(<RatesTable rates={[water, trash]} plan="Residential" perPeriod={false} t={t} fmt={fmt} />);
    const parts = Array.from(document.querySelectorAll("[data-rate-part]"));
    expect(parts.map((row) => row.getAttribute("data-rate-part"))).toEqual([
      "water:2026-09-01",
      "water:2026-09-15",
    ]);
    expect(parts[0]).toHaveTextContent("09/01/2026");
    expect(parts[0]).toHaveTextContent("09/14/2026");
    expect(parts[0]).toHaveTextContent("0.79 kgal");
    expect(parts[0]).toHaveTextContent("$3.17");
    expect(parts[1]).toHaveTextContent("0.91 kgal");
    expect(parts[1]).toHaveTextContent("$3.99");
    expect(document.querySelector('[data-rate-part^="trash"]')).toBeNull();
  });
});

const draftDup: OneTimeBillDuplicate = {
  invoice_no: "BL-2609-000101",
  run_id: "run-1",
  invoice_id: "inv-1",
  ran_by_name: "Dana Whitfield",
  ran_at: "2026-10-12T10:00:00-05:00",
  status: "draft",
};

describe("OTB-10/17 — a draft is not 'Already billed'", () => {
  it("a draft reads its own sentence and offers Open draft and Discard draft", () => {
    const onDiscard = vi.fn();
    render(
      <MemoryRouter>
        <AlreadyBilledBanner duplicate={draftDup} billHref="/acme/billing/bills/inv-1" onDiscard={onDiscard} t={t} fmt={fmt} />
      </MemoryRouter>,
    );
    const banner = screen.getByRole("alert");
    expect(banner).toHaveTextContent("Draft already exists for this period.");
    expect(banner).not.toHaveTextContent("Already billed");
    expect(within(banner).getByRole("link", { name: "Open draft" })).toHaveAttribute(
      "href",
      "/acme/billing/bills/inv-1",
    );
    fireEvent.click(within(banner).getByRole("button", { name: "Discard draft" }));
    expect(onDiscard).toHaveBeenCalledTimes(1);
  });

  it("an issued bill still reads 'Already billed for this period.' with no discard", () => {
    render(
      <MemoryRouter>
        <AlreadyBilledBanner
          duplicate={{ ...draftDup, status: "issued" }}
          billHref="/acme/billing/bills/inv-1"
          onDiscard={() => undefined}
          t={t}
          fmt={fmt}
        />
      </MemoryRouter>,
    );
    const banner = screen.getByRole("alert");
    expect(banner).toHaveTextContent("Already billed for this period.");
    expect(within(banner).queryByRole("button", { name: "Discard draft" })).toBeNull();
  });
});

describe("OTB-18 — a closed month is said on step 1", () => {
  it("reads 'August is closed. Posts to October.'", () => {
    render(
      <ClosedMonthNote
        closed={{ requested_period: ["2026-08-01", "2026-08-31"], posted_period: ["2026-10-01", "2026-10-31"] }}
        t={t}
        language="en"
      />,
    );
    expect(screen.getByRole("status")).toHaveTextContent("August is closed. Posts to October.");
  });
});

describe("OTB-6 — Approve and Cancel on a one-time draft", () => {
  it("Cancel draft asks first, then discards the run and reports it", async () => {
    const post = vi.fn(async () => ({ data: { id: "run-1", status: "abandoned", drafts_removed: 1 } }));
    const client = { post } as unknown as ApiClient;
    const onDone = vi.fn();
    const onMessage = vi.fn();
    render(
      <DraftDecision
        runId="run-1"
        blockedReason={null}
        client={client}
        onMessage={onMessage}
        onDone={onDone}
        refusalOf={() => "refused"}
        t={t}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Cancel draft" }));
    const dialog = screen.getByRole("alertdialog");
    expect(dialog).toHaveTextContent("The draft is deleted. Its number is not reused.");
    expect(post).not.toHaveBeenCalled();
    fireEvent.click(within(dialog).getByRole("button", { name: "Cancel draft" }));
    await waitFor(() => expect(onDone).toHaveBeenCalledWith("cancelled"));
    expect(post).toHaveBeenCalledWith("/billing/runs/run-1/discard", {});
    expect(onMessage).toHaveBeenCalledWith("Draft canceled.");
  });

  it("Approve stays shut until all five confirmations are ticked, then sends through the one-time Send", async () => {
    const post = vi.fn(async () => ({
      data: { invoice_no: "BL-1", total: "1.0000", currency: "USD", due_date: null, delivery: "queued", reads: "locked" },
    }));
    const client = { post } as unknown as ApiClient;
    const onDone = vi.fn();
    render(
      <DraftDecision
        runId="run-1"
        blockedReason={null}
        client={client}
        onMessage={() => undefined}
        onDone={onDone}
        refusalOf={() => "refused"}
        t={t}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Approve" }));
    const dialog = screen.getByRole("dialog");
    const go = within(dialog).getByRole("button", { name: "Approve and send" });
    expect(go).toBeDisabled();
    for (const box of within(dialog).getAllByRole("checkbox")) fireEvent.click(box);
    expect(go).toBeEnabled();
    fireEvent.click(go);
    await waitFor(() => expect(onDone).toHaveBeenCalledWith("approved"));
    expect(post).toHaveBeenCalledWith("/billing/one-time/run-1/send", expect.anything());
  });
});
