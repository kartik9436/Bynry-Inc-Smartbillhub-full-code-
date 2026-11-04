// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Ruling:   PO 2026-10-17 — *"use same code components"* for *"meter
//           reading, date and fetch"*.
// Tests:    MeterReadingEntry.tsx — the reading box, its read date and Fetch
// ───────────────────────────────────────────────────────
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ApiClient } from "@/api/client";
import i18n from "@/i18n";

import { MeterReadingEntry, readDateProblem } from "./MeterReadingEntry";
import type { MeterReadingEntryProps, MeterReadingEntryValue } from "./MeterReadingEntry";

afterEach(cleanup);

const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

function client(answer: unknown): ApiClient {
  return {
    post: vi.fn(async () => ({ status: 200, etag: null, notModified: false, data: answer })),
  } as unknown as ApiClient;
}

function Host(props: Partial<MeterReadingEntryProps> & { api: ApiClient; seen?: MeterReadingEntryValue[] }) {
  const [entry, setEntry] = useState<MeterReadingEntryValue>({
    value: "",
    readDate: "2026-10-10",
    estimate: false,
    fetched: false,
  });
  return (
    <MeterReadingEntry
      meterNo="W-5023"
      unit="kgal"
      lastReading={{ value: "2990.000000", readAt: "2026-09-30" }}
      defaultReadDate="2026-10-10"
      maxDate="2026-10-17"
      showFetch
      showDateError
      client={props.api}
      t={t}
      timeZone="America/Chicago"
      dateFormat="YYYY-MM-DD"
      {...props}
      value={entry.value}
      readDate={entry.readDate}
      estimate={entry.estimate}
      fetched={entry.fetched}
      onChange={(next) => {
        props.seen?.push(next);
        setEntry(next);
      }}
    />
  );
}

describe("readDateProblem", () => {
  it("refuses empty, after today, and before the last reading; the same day is lawful", () => {
    const bounds = { minDate: "2026-09-30", maxDate: "2026-10-17" };
    expect(readDateProblem("", bounds)).toBe("required");
    expect(readDateProblem("2026-10-18", bounds)).toBe("future");
    expect(readDateProblem("2026-09-29", bounds)).toBe("before_last");
    expect(readDateProblem("2026-09-30", bounds)).toBeNull();
    expect(readDateProblem("2026-10-17", bounds)).toBeNull();
  });
});

describe("MeterReadingEntry", () => {
  it("draws the reading, its unit and the read date with real bounds", () => {
    render(<Host api={client(null)} />);
    expect(screen.getByLabelText("Reading for W-5023")).toBeInTheDocument();
    const box = document.querySelector('[data-meter-reading-date="W-5023"]');
    expect(box?.getAttribute("data-read-date-problem")).toBe("");
    const date = document.getElementById("reading-W-5023-date") as HTMLInputElement | null;
    expect(date).not.toBeNull();
  });

  it("a fetched reading keeps the meter's date and locks it; typing over it returns the default", async () => {
    const user = userEvent.setup();
    const seen: MeterReadingEntryValue[] = [];
    render(
      <Host
        api={client({
          result: "fetched",
          reading: { meter_no: "W-5023", value: "3004", unit: "kgal", read_on: "2026-10-08" },
          message_key: null,
        })}
        seen={seen}
      />,
    );
    await user.click(screen.getByRole("button", { name: "Fetch reading for W-5023" }));
    await waitFor(() => expect(seen.at(-1)).toEqual({ value: "3004", readDate: "2026-10-08", estimate: false, fetched: true }));
    expect(screen.getByText("Date from the meter.")).toBeInTheDocument();
    await user.type(screen.getByLabelText("Reading for W-5023"), "1");
    expect(seen.at(-1)).toEqual({ value: "30041", readDate: "2026-10-10", estimate: false, fetched: false });
  });

  it("names a date before the last reading and a date after today", () => {
    render(
      <MeterReadingEntry
        meterNo="E-1"
        unit="kWh"
        lastReading={{ value: "10", readAt: "2026-09-30" }}
        value="12"
        readDate="2026-09-01"
        maxDate="2026-10-17"
        showDateError
        onChange={() => undefined}
        client={client(null)}
        t={t}
        timeZone="UTC"
        dateFormat="YYYY-MM-DD"
      />,
    );
    expect(screen.getByText("Earlier than the last reading.")).toBeInTheDocument();
    cleanup();
    render(
      <MeterReadingEntry
        meterNo="E-1"
        unit="kWh"
        value="12"
        readDate="2026-10-18"
        maxDate="2026-10-17"
        showDateError
        onChange={() => undefined}
        client={client(null)}
        t={t}
        timeZone="UTC"
        dateFormat="YYYY-MM-DD"
      />,
    );
    expect(screen.getByText("Read date is after today.")).toBeInTheDocument();
  });

  it("offers no Fetch and no Estimate unless the host asks", () => {
    render(
      <MeterReadingEntry
        meterNo="E-1"
        unit={null}
        value=""
        readDate="2026-10-01"
        onChange={() => undefined}
        client={client(null)}
        t={t}
        timeZone="UTC"
        dateFormat="YYYY-MM-DD"
      />,
    );
    expect(screen.queryByRole("button", { name: /Fetch reading/ })).toBeNull();
    expect(screen.queryByLabelText("Estimate")).toBeNull();
  });
});
