// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defect:   DEF-CUS-10050 (Move-in) · DEF-CUS-10051 (Move-out reuses it)
// Tests:    FetchMeterReading.tsx — the ONE component both flows mount
// ───────────────────────────────────────────────────────
// The host-level cases (metered rows only, the box filled, typing over it)
// are in customers/moveInWizard/StepUnit.dom.test.tsx. These are the ones
// the component owns: `asOf` reaching the request, the tenant's date format,
// a reading in another unit refused, and a transport failure said in words.
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ApiClient } from "@/api/client";
import i18n from "@/i18n";

import { FETCH_METER_READING_PATH, FetchMeterReading } from "./FetchMeterReading";
import type { FetchedMeterReading } from "./FetchMeterReading";

afterEach(cleanup);

const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

function client(answer: unknown, fail = false): ApiClient {
  return {
    post: vi.fn(async () => {
      if (fail) throw new Error("network");
      return { status: 200, etag: null, notModified: false, data: answer };
    }),
  } as unknown as ApiClient;
}

const FETCHED = {
  result: "fetched",
  reading: { meter_no: "W-5023", value: "3004", unit: "kgal", read_on: "2026-10-11" },
  message_key: null,
};

describe("FetchMeterReading", () => {
  it("asks for the latest by default, and the date reads in the tenant's format", async () => {
    const user = userEvent.setup();
    const api = client(FETCHED);
    const got: FetchedMeterReading[] = [];
    render(
      <FetchMeterReading
        meterNo="W-5023"
        client={api}
        t={t}
        timeZone="America/Chicago"
        dateFormat="DD-MMM-YY"
        expectedUnit="kgal"
        onFetched={(reading) => got.push(reading)}
      />,
    );
    await user.click(screen.getByRole("button", { name: "Fetch reading for W-5023" }));
    await waitFor(() => expect(screen.getByText("Read on 11-Oct-26")).toBeInTheDocument());
    expect(api.post).toHaveBeenCalledWith(FETCH_METER_READING_PATH, { meter_no: "W-5023" });
    expect(got).toEqual([FETCHED.reading]);
  });

  it("asOf rides the request — the move-out's reading on or before its date", async () => {
    const user = userEvent.setup();
    const api = client(FETCHED);
    render(
      <FetchMeterReading
        meterNo="W-5023"
        asOf="2026-10-20"
        client={api}
        t={t}
        timeZone="America/Chicago"
        dateFormat="MM/DD/YYYY"
        onFetched={() => undefined}
      />,
    );
    await user.click(screen.getByRole("button", { name: "Fetch reading for W-5023" }));
    await waitFor(() =>
      expect(api.post).toHaveBeenCalledWith(FETCH_METER_READING_PATH, { meter_no: "W-5023", as_of: "2026-10-20" }),
    );
  });

  it("a reading in another unit is not handed back (hard rule 3)", async () => {
    const user = userEvent.setup();
    const onFetched = vi.fn();
    render(
      <FetchMeterReading
        meterNo="W-5023"
        client={client(FETCHED)}
        t={t}
        timeZone="America/Chicago"
        dateFormat="MM/DD/YYYY"
        expectedUnit="gal"
        onFetched={onFetched}
      />,
    );
    await user.click(screen.getByRole("button", { name: "Fetch reading for W-5023" }));
    await waitFor(() => expect(screen.getByText("Reading unit does not match.")).toBeInTheDocument());
    expect(onFetched).not.toHaveBeenCalled();
  });

  it("a request that fails says so in one line and fills nothing", async () => {
    const user = userEvent.setup();
    const onFetched = vi.fn();
    render(
      <FetchMeterReading
        meterNo="W-5023"
        client={client(null, true)}
        t={t}
        timeZone="America/Chicago"
        dateFormat="MM/DD/YYYY"
        onFetched={onFetched}
      />,
    );
    await user.click(screen.getByRole("button", { name: "Fetch reading for W-5023" }));
    await waitFor(() => expect(screen.getByText("Could not ask the provider.")).toBeInTheDocument());
    expect(onFetched).not.toHaveBeenCalled();
  });

  // PO 2026-10-11 — a head-end switched on that cannot be read is NAMED.
  it("a connector switched on but unable to read names the provider", async () => {
    const user = userEvent.setup();
    const onFetched = vi.fn();
    render(
      <FetchMeterReading
        meterNo="W-5023"
        client={client({
          result: "unavailable",
          reading: null,
          message_key: "integrations.meterReading.connected_no_read",
          params: { provider: "Neptune 360" },
        })}
        t={t}
        timeZone="America/Chicago"
        dateFormat="MM/DD/YYYY"
        onFetched={onFetched}
      />,
    );
    await user.click(screen.getByRole("button", { name: "Fetch reading for W-5023" }));
    await waitFor(() =>
      expect(screen.getByText("Neptune 360 connected. No reading fetched.")).toBeInTheDocument(),
    );
    expect(onFetched).not.toHaveBeenCalled();
  });
});
