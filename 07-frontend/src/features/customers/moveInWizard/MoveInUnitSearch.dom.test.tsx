// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defect:   DEF-CUS-10190 — Move-in step 1 listed only vacant units.
// Ruling:   PO 2026-10-17, decision log *"MOVE-IN SEARCHES ALL UNITS, NOT ONLY
//           VACANT ONES"* + *"Same day"*.
// ───────────────────────────────────────────────────────
// RED FIRST (law 7): the routed cases in `MoveEntryPoints.dom.test.tsx` were
// re-pointed at the search before the wizard wired it, and failed with
// `no Use button for U-10432-A` (the vacant-only select still drew). This file
// pins the component's own states, rendered — never props.
import "@testing-library/jest-dom/vitest";
import { QueryClient } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import { whatHappenedRows } from "./MoveInCompleted";
import type { MoveInCompletedResult } from "./MoveInCompleted";
import { MoveInUnitSearch } from "./MoveInUnitSearch";
import type { MoveInUnitSearchProps } from "./MoveInUnitSearch";
import { carriedReads, forgetTenancyAfterMoveOut, moveInResumePath } from "./moveInUnitSearch";
import type { MoveInUnitRow } from "./moveInUnitSearch";

const t = (key: string, params?: Record<string, unknown>) => i18n.t(key, params);

afterEach(cleanup);

function row(over: Partial<MoveInUnitRow> = {}): MoveInUnitRow {
  return {
    id: "u-1",
    unit_no: "U-00104",
    label: "Apt 104",
    premise_no: "P-00012",
    premise_name: "Mill Pond",
    address: { line1: "12 Mill Pond Rd", city: "Ottumwa", state: "IA", postal_code: "52501" },
    meters: ["E-7781"],
    state: "vacant",
    occupant: null,
    selectable: true,
    path: "move_in",
    reason_key: null,
    ...over,
  };
}

const ACTIVE = row({
  id: "u-2",
  unit_no: "U-00105",
  label: "Apt 105",
  state: "active",
  path: "move_out_first",
  occupant: { account_id: "a-2", account_no: "AC-2026-00105", name: "Rosa Diaz", status_name: "Active", closed_at: null },
});
const IN_PROGRESS = row({
  id: "u-3",
  unit_no: "U-00106",
  state: "move_out_in_progress",
  selectable: false,
  path: null,
  reason_key: "customers.moveIn.unitSearch.blocked.moveOutInProgress",
  occupant: { account_id: "a-3", account_no: "AC-2026-00106", name: "Ian Chu", status_name: "Active", closed_at: null },
});
const PENDING = row({
  id: "u-4",
  unit_no: "U-00107",
  state: "pending_activation",
  selectable: false,
  path: null,
  reason_key: "customers.moveIn.unitSearch.blocked.pendingActivation",
});
const CUT = row({
  id: "u-5",
  unit_no: "U-00108",
  state: "disconnected",
  path: "close_out_first",
  occupant: { account_id: "a-5", account_no: "AC-2026-00108", name: "Dora Cut", status_name: "Disconnected", closed_at: null },
});

function mount(over: Partial<MoveInUnitSearchProps> = {}) {
  const props: MoveInUnitSearchProps = {
    term: "",
    onTermChange: vi.fn(),
    page: 1,
    onPage: vi.fn(),
    search: { rows: [row(), ACTIVE, IN_PROGRESS, PENDING, CUT], total: 5, loading: false, failed: false },
    chosen: null,
    onChoose: vi.fn(),
    onChange: vi.fn(),
    onSettleFirst: vi.fn(),
    settleBlockedReason: null,
    settling: false,
    settleRefusal: null,
    t,
    ...over,
  };
  render(
    <MemoryRouter initialEntries={["/silvercreek/move-ins/new"]}>
      <Routes>
        <Route path="/:tenant/move-ins/new" element={<MoveInUnitSearch {...props} />} />
      </Routes>
    </MemoryRouter>,
  );
  return props;
}

describe("DEF-CUS-10190 — Move-in step 1 searches every unit", () => {
  it("lists every state with its chip; a blocked row is greyed, says why, and has no Use", () => {
    mount();
    const rows = Array.from(document.querySelectorAll<HTMLElement>("[data-move-in-unit-row]"));
    expect(rows.map((r) => r.dataset.moveInUnitRow)).toEqual([
      "vacant",
      "active",
      "move_out_in_progress",
      "pending_activation",
      "disconnected",
    ]);
    expect(rows[1]).toHaveTextContent("Rosa Diaz");
    expect(rows[1]).toHaveTextContent("Active");
    expect(rows[2]).toHaveTextContent("Move-out in progress");
    expect(rows[2]).toHaveTextContent("Finish the move-out first.");
    expect(rows[2].querySelector("[data-move-in-unit-use]")).toBeNull();
    expect(rows[3]).toHaveTextContent("Waiting for activation.");
    expect(rows[3].querySelector("[data-move-in-unit-use]")).toBeNull();
    expect(rows[0].querySelector("[data-move-in-unit-use]")).not.toBeNull();
    expect(rows[0]).toHaveTextContent("12 Mill Pond Rd, Ottumwa, IA 52501");
    expect(rows[0]).toHaveTextContent("E-7781");
  });

  it("Use chooses the row", () => {
    const props = mount();
    fireEvent.click(document.querySelector('[data-move-in-unit-use="U-00105"]') as HTMLElement);
    expect(props.onChoose).toHaveBeenCalledWith(ACTIVE);
  });

  it("an occupied unit warns by name and offers Start move-out", () => {
    const props = mount({ chosen: ACTIVE });
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Rosa Diaz is still on this unit. Start a move-out for them first.",
    );
    fireEvent.click(screen.getByRole("button", { name: "Start move-out" }));
    expect(props.onSettleFirst).toHaveBeenCalledWith(ACTIVE);
  });

  it("Start move-out waits for the move-in date, and says so", () => {
    mount({ chosen: ACTIVE, settleBlockedReason: t("customers.moveIn.unitSearch.dateFirst") });
    expect(screen.getByRole("button", { name: "Start move-out" })).toBeDisabled();
    expect(document.querySelector("[data-move-in-settle-why]")).toHaveTextContent("Enter the move-in date first.");
  });

  it("a disconnected unit settles by close-out, not move-out", () => {
    mount({ chosen: CUT });
    expect(screen.getByRole("alert")).toHaveTextContent("Dora Cut was disconnected here.");
    expect(screen.getByRole("button", { name: "Start close-out" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Start move-out" })).toBeNull();
  });

  it("a vacant unit chosen shows no warning", () => {
    mount({ chosen: row() });
    expect(screen.queryByRole("alert")).toBeNull();
    expect(screen.getByRole("button", { name: "Change" })).toBeInTheDocument();
  });
});

describe("DEF-CUS-10190 — back from the move-out, the opening reads carry the closing reads", () => {
  it("fills each empty box with the last reading and its date, and keeps what was typed", () => {
    const read = {
      services: [
        {
          meters: [
            // The server's storage form — six decimals (`DEF-CUS-10191`).
            { asset_no: "E-1", last_read: { value: "42864.000000", read_at: "2026-10-16T00:00:00Z" }, needs_opening_read: true },
            { asset_no: "W-1", last_read: { value: "1203", read_at: "2026-10-16" }, needs_opening_read: true },
          ],
        },
      ],
    };
    const next = carriedReads(read, { "W-1": { meterNo: "W-1", value: "1210", estimate: false, readAt: "" } });
    // `DEF-CUS-10191` (found on the walk): the value as a clerk reads it, and
    // the date DEFERRED to the move-in day — the closing read's own date is
    // the same reading, which the read door files as already recorded
    // (BR-MET-1189), so the new account got no opening read at all.
    expect(next?.["E-1"]).toEqual({ meterNo: "E-1", value: "42864", estimate: false, readAt: "" });
    expect(next?.["W-1"].value).toBe("1210");
  });

  it("a finished move-out forgets what the browser held about the old tenancy (DEF-CUS-10193)", async () => {
    const client = new QueryClient();
    const keys = [
      ["accounts", "detail", "acc-1"],
      ["move-in-unit-accounts", "u-1"],
      ["move-in-step-unit-meters", "u-1"],
      ["move-in-step-unit-facts", "u-1"],
      ["move-in-unit-search", "Rosa", 1],
      ["move-in-unit-row", "u-1"],
    ];
    for (const key of keys) client.setQueryData(key, { stale: true });
    client.setQueryData(["unrelated"], { kept: true });
    await forgetTenancyAfterMoveOut(client, { accountId: "acc-1", unitId: "u-1" });
    for (const key of keys) expect(client.getQueryState(key)?.isInvalidated, JSON.stringify(key)).toBe(true);
    expect(client.getQueryState(["unrelated"])?.isInvalidated).toBe(false);
  });

  it("the parked move-in's cached draft is dropped, so the way back reads it fresh (DEF-CUS-10195)", async () => {
    // The walk's W7: the draft cached as first read (empty) was hydrated on
    // the way back and autosaved over the real one — unit and date lost.
    const client = new QueryClient();
    client.setQueryData(["wizard-park", "park-mi"], { values: { unit_id: "" } });
    client.setQueryData(["wizard-park", "other"], { values: { unit_id: "u-9" } });
    await forgetTenancyAfterMoveOut(client, { accountId: "acc-1", unitId: "u-1", moveInParkId: "park-mi" });
    expect(client.getQueryData(["wizard-park", "park-mi"])).toBeUndefined();
    expect(client.getQueryData(["wizard-park", "other"])).toEqual({ values: { unit_id: "u-9" } });
  });

  it("the way back names the parked move-in and asks for the carry", () => {
    expect(moveInResumePath("park-1")).toBe("/move-ins/new?parked=park-1&carry=reads");
  });
});

describe("DEF-CUS-10196 — the done screen after a reopen names each service once", () => {
  it("counts only the agreements this move-in opened, not the earlier tenancy's ended ones", () => {
    const result = {
      service_agreements: [
        { id: "old-w", service_point_id: "sp-w", service: "water", started_on: "2026-08-01", ended_on: "2026-10-15" },
        { id: "old-e", service_point_id: "sp-e", service: "electric", started_on: "2026-08-01", ended_on: "2026-10-15" },
        { id: "new-w", service_point_id: "sp-w", service: "water", started_on: "2026-10-17", ended_on: null },
        { id: "new-e", service_point_id: "sp-e", service: "electric", started_on: "2026-10-17", ended_on: null },
      ],
      what_happened: { items: [{ key: "services", count: 2, starts_on: "2026-10-17" }] },
    } as unknown as MoveInCompletedResult;
    const row = whatHappenedRows(result, t, { timeZone: "America/Chicago", dateFormat: "MM/DD/YYYY" }).find(
      (r) => r.id === "services",
    );
    expect(row?.fact).toContain("Water · Electric");
    expect(row?.fact).not.toContain("Water · Electric · Water");
  });
});
