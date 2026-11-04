// ── Trace ──────────────────────────────────────────────
// Story:    US-WRK-021 — the technician detail and the three-step skills
//           wizard.  Screen: Work-024 (+ the undrawn wizard sub-screen)
// Rules:    BR-WRK-028 · B14 rules 2 · 20 · 31 · 32 · BR-SHL-025 ·
//           CLAUDE.md hard-won law 2 (a tab onto a screen that does not exist
//           is a control onto nothing)
// ───────────────────────────────────────────────────────
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import { queryKeys } from "@/api/queryClient";

import {
  TechnicianDetailPage,
  WORK_TECHNICIAN_SCREEN,
  metaLine,
  technicianTabs,
} from "./TechnicianDetailPage";
import { initialChoice, skillsPayload } from "./SkillsWizard";
import type { TechnicianDetail } from "./workEndpoints";

const TENANT = "brazosbend";
const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

/** `US-WRK-021` §4's fixture — R. Patel, with the *Not held* row that is the
 *  whole point of the panel. */
function patel(over: Partial<TechnicianDetail> = {}): TechnicianDetail {
  return {
    id: "t-patel",
    slug: "r-patel",
    name: "R. Patel",
    role_label: "Senior technician",
    shift: "07:00–16:00",
    status: "on_shift",
    unavailable_reason: null,
    van: "Unit 12",
    crew: null,
    skills: [
      {
        skill_id: "s-w1",
        code: "WATER1",
        name: "Water I",
        proficiency: "certified",
        eligible_for: ["Leak investigation", "Service connection", "Disconnects"],
      },
      {
        skill_id: "s-rd",
        code: "READS",
        name: "Reads",
        proficiency: "trained",
        eligible_for: ["Read verification", "Final reads"],
      },
      // ⚠ THE ROW THAT MATTERS AS MUCH AS THE TWO HELD ONES — it tells a
      // supervisor exactly which jobs a training course would unlock.
      {
        skill_id: "s-w2",
        code: "WATER2",
        name: "Water II",
        proficiency: "not_held",
        eligible_for: ["Main repair", "Tap and service line"],
      },
    ],
    certifications: [
      { certification_type_id: "c-bf", name: "Backflow tester", expires_on: "2028-01-31" },
      { certification_type_id: "c-fa", name: "First aid / CPR", expires_on: "2027-09-30" },
    ],
    ...over,
  };
}

/** ⚠ MOUNTED UNDER THE REAL PATH PATTERN — law 2's fixture clause. Bare, the
 *  `:slug` param is undefined and every address the page builds is wrong in a
 *  way `toContain` reads as fine. */
function render(detail: TechnicianDetail | null): string {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, enabled: false } },
  });
  if (detail !== null) {
    queryClient.setQueryData(queryKeys.workTechnician("r-patel"), detail);
  }
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[`/${TENANT}/work/crews/r-patel`]}>
        <Routes>
          <Route path="/:tenant/work/crews/:slug" element={<TechnicianDetailPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("US-WRK-021 — the technician detail (Work-024, template W5)", () => {
  it("draws the head, the badge and the back link to Crews", () => {
    const html = render(patel());
    expect(html).toContain(WORK_TECHNICIAN_SCREEN);
    expect(html).toContain("R. Patel");
    expect(html).toContain("Senior technician");
    expect(html).toContain(`/${TENANT}/work/crews`);
    expect(html).not.toContain('href="//work/');
  });

  it("the SKILLS panel lists the tenant's WHOLE catalogue — held and NOT HELD", () => {
    // ⚠ THE POINT OF THIS SCREEN. The *Not held* row is DERIVED (the catalogue
    // minus what she holds), never stored: a stored absence goes stale the
    // moment a skill is added in Settings.
    const html = render(patel());
    expect(html).toContain("Water I");
    expect(html).toContain("Certified");
    expect(html).toContain("Reads");
    expect(html).toContain("Trained");
    expect(html).toContain("Water II");
    expect(html).toContain("Not held");
    // And what each one unlocks, which is why the row is worth drawing.
    expect(html).toContain("Main repair");
  });

  it("draws the certifications with their expiry", () => {
    const html = render(patel());
    expect(html).toContain("Backflow tester");
    expect(html).toContain("exp 2028-01-31");
    expect(html).toContain("First aid / CPR");
  });

  it("draws *This month* only from the server's figures — none served, none drawn (ruling 27)", () => {
    // ⚠ CHANGED 2026-10-04 (CR-168-BRC10 round 4, lane CREWS). This case read
    // *"does NOT draw the this month figures — nothing can compute them until
    // wave G"*; ruling 27 draws the panel and SRV-3 serves `this_month`. What
    // stands is the honest half: a person with no served figures gets no
    // invented ones. The served case is `crewsLane.dom.test.tsx`, on the
    // recorded answer.
    const html = render(patel());
    for (const forbidden of ["Jobs closed", "88", "92%", "−4 min"]) {
      expect(html).not.toContain(forbidden);
    }
  });

  it("draws images 31–34's four tabs, in order — and still no Audit (ruling 27, 28)", () => {
    // ⚠ CHANGED 2026-10-04: this case asserted Jobs ABSENT (wave G's assignee
    // column had not landed). Rulings 27 and 28 draw Jobs and Performance and
    // the server serves both; Audit is drawn on none of images 31–34.
    const ids = technicianTabs(t).map((tab) => tab.id);
    // CR-193-BRC10 (MQ-040 step 1, PO 2026-10-26) appends *Timesheets* — the
    // days the phone submitted; images 31–34's four stay first, in their order.
    expect(ids).toEqual(["overview", "jobs", "certifications", "performance", "timesheets"]);
    const html = render(patel());
    expect(html).not.toContain(">Audit<");
  });

  it("*Set unavailable* is offered and DELETE is not (US-WRK-020 TC-5)", () => {
    // A technician with jobs against their name is never removed: a deleted
    // row leaves a job assigned to nobody with no way to see it happened.
    const html = render(patel());
    expect(html).toContain("Set unavailable");
    expect(html).not.toContain("Delete");
    // The reverse control appears on somebody already unavailable.
    expect(render(patel({ status: "unavailable" }))).toContain("Set available");
  });

  it("the meta line carries the skills and the shift and NOT an invented job count", () => {
    const line = metaLine(patel(), t);
    expect(line).toContain("Water I");
    expect(line).toContain("shift 07:00–16:00");
    // `WS-24` draws *5 jobs today* — see above; it is not composed here.
    expect(line).not.toContain("jobs today");
    // A *Not held* skill is not in the meta line: she does not hold it.
    expect(line).not.toContain("Water II");
  });

  it("B14 rule 31 / 32: no database id and no rule id in clerk-facing copy", () => {
    const html = render(patel());
    for (const forbidden of ["t-patel", "s-w1", "c-bf", "BR-WRK", "OQ-WRK", "US-WRK"]) {
      expect(html).not.toContain(forbidden);
    }
  });
});

describe("the skills wizard — a sub-screen of Work-024, and it takes no screen id", () => {
  it("opens holding exactly what the person holds today", () => {
    expect(initialChoice(patel())).toEqual({ "s-w1": "certified", "s-rd": "trained" });
  });

  it("never sends *not held* — it is an ABSENCE, not a third proficiency", () => {
    const payload = skillsPayload(patel(), initialChoice(patel()));
    expect(payload.map((row) => row.skill_id)).toEqual(["s-w1", "s-rd"]);
    expect(payload.some((row) => (row.proficiency as string) === "not_held")).toBe(false);
  });

  it("a REPLACE, not a merge: unticking a skill removes it from the body", () => {
    // Step 2 shows the whole set, so a supervisor who unticks Water I means
    // it — and the server's `PUT …/skills` replaces for the same reason.
    const payload = skillsPayload(patel(), { "s-rd": "trained" });
    expect(payload).toEqual([{ skill_id: "s-rd", proficiency: "trained" }]);
  });

  it("adding Water II at *trained* is what the demo does, and it lands in the body", () => {
    const payload = skillsPayload(patel(), {
      "s-w1": "certified",
      "s-rd": "trained",
      "s-w2": "trained",
    });
    expect(payload).toContainEqual({ skill_id: "s-w2", proficiency: "trained" });
  });
});
