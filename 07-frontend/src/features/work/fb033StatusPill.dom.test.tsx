// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:   FB-033 — availability from the phone reaches the office (decision
//           log 2026-10-31, D1–D4) · DEF-FLD-10799
// Code:     TechnicianStatusPill.tsx · CrewsPage.tsx (STATUS column) ·
//           candidateAdvice.ts (availabilityAlert) · CandidatePicker.tsx ·
//           performance/ScheduleBoard.tsx (holderLoad)
// ───────────────────────────────────────────────────────
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import { adviceText, availabilityAlert } from "./candidateAdvice";
import { technicianListConfig } from "./CrewsPage";
import type { TechnicianListRow } from "./crewsEndpoints";
import { holderLoad } from "./performance/ScheduleBoard";
import { statusPillText, TechnicianStatusPill } from "./TechnicianStatusPill";
import type { Candidate } from "./workEndpoints";

const t = (key: string, params?: Record<string, unknown>) => i18n.t(key, params as never) as unknown as string;

afterEach(cleanup);

describe("FB-033 — the status pill carries its time (D4 = B: two separate facts)", () => {
  it("Off duty · since 15:30, On break · since 10:42, Shift ended · 17:02", () => {
    expect(statusPillText("off_duty", "2026-10-28T15:30:00-05:00", false, t)).toBe("Off duty · since 15:30");
    expect(statusPillText("on_break", "2026-10-28T10:42:00-05:00", false, t)).toBe("On break · since 10:42");
    expect(statusPillText("off_today", "2026-10-28T17:02:00-05:00", true, t)).toBe("Shift ended · 17:02");
    // The office set Off today by hand: no End shift, so no "Shift ended".
    expect(statusPillText("off_today", "2026-10-28T11:00:00-05:00", false, t)).toBe("Off today");
    // A time the server does not know is never made up.
    expect(statusPillText("off_duty", null, false, t)).toBe("Off duty");
    expect(statusPillText("on_shift", "2026-10-28T07:00:00-05:00", false, t)).toBe("On shift");
  });

  it("the Crews STATUS column renders the pill with the time", () => {
    const row = {
      id: "t1",
      kind: "person",
      name: "Dana Field",
      slug: "dana-field",
      role_label: null,
      crew: null,
      skills: [],
      certifications: [],
      shift: null,
      status: "off_duty",
      status_since: "2026-10-28T15:30:00-05:00",
      shift_ended: false,
      unavailable_reason: null,
      phone: null,
      email: null,
    } as TechnicianListRow;
    const config = technicianListConfig(t, { technician: (r) => r.name });
    const status = config.columns.find((column) => column.key === "status");
    render(<>{status?.cell?.(row)}</>);
    expect(screen.getByText("Off duty · since 15:30")).toBeTruthy();
  });

  it("renders as a pill", () => {
    render(<TechnicianStatusPill status="on_break" since="2026-10-28T10:42:00-05:00" />);
    expect(screen.getByText("On break · since 10:42")).toBeTruthy();
  });
});

const candidate = (availability: Candidate["advice"]["availability"], patch: Partial<Candidate["advice"]> = {}): Candidate => ({
  kind: "person",
  id: "t1",
  name: "Dana Field",
  best_fit: false,
  advice: {
    skill: null,
    has_skill: true,
    area_match: false,
    off_that_day: false,
    jobs_that_day: 1,
    certifications_lapsed: [],
    availability,
    ...patch,
  },
});

describe("FB-033 — the assign picker warns and still offers (D1 = A, D2 = A)", () => {
  it("Off duty is a RED warning with its time; On break a plain warning", () => {
    expect(availabilityAlert(candidate({ status: "off_duty", since: "2026-10-31T16:10:00-05:00" }), t)).toEqual({
      text: "Off duty since 16:10",
      tone: "danger",
    });
    expect(availabilityAlert(candidate({ status: "on_break", since: "2026-10-31T10:42:00-05:00" }), t)).toEqual({
      text: "On break since 10:42",
      tone: "warning",
    });
    expect(availabilityAlert(candidate(null), t)).toBeNull();
  });

  it("the advice line says it once — never 'Off that day' beside 'Off duty'", () => {
    const off = candidate({ status: "off_duty", since: "2026-10-31T16:10:00-05:00" }, { off_that_day: true });
    expect(adviceText(off, t, (iso) => iso)).toBe("Off duty since 16:10 · 1 job that day");
    expect(adviceText(off, t, (iso) => iso, { availabilityShownApart: true })).toBe("1 job that day");
  });

  it("D3 — the board marks an Off-duty technician still holding jobs: Assignee off duty", () => {
    expect(holderLoad(candidate({ status: "off_duty", since: null }, { jobs_that_day: 2 }))).toBe("offDutyHolding");
    expect(holderLoad(candidate({ status: "off_duty", since: null }, { jobs_that_day: 0, off_that_day: true }))).toBe("off");
    expect(holderLoad(candidate({ status: "on_break", since: null }, { jobs_that_day: 2 }))).toBe("busy");
    expect(t("work.schedule.load.assigneeOffDuty")).toBe("Assignee off duty");
  });
});
