// ── Trace ──────────────────────────────────────────────
// Story:    US-WRK-020 · US-WRK-021 — rebuilt for CR-168-BRC10 round 4 (lane
//           CREWS): the Crews page is THREE lists (ruling 30), from images
//           25, 27 and 28.
// Rules:    ruling 30 (supersedes `BR-WRK-028`'s last sentence) · PO answer 2
//           of 2026-10-04 (`BR-WRK-030` superseded — a lapsed certification
//           WARNS; `DEF-WRK-9634`) · B14 rules 19 · 31 · 32 · 33
// ───────────────────────────────────────────────────────
//
// ⚠ **THIS FILE ASSERTED THE ONE-TABLE SCREEN UNTIL 2026-10-04, AND FOUR OF ITS
// CASES WERE REMOVED BECAUSE THE RULINGS THEY HELD WERE SUPERSEDED, NOT
// BECAUSE THEY WENT RED:** *"TC-3: a crew and a contractor are ROWS IN THE SAME
// TABLE as a person"* and *"the footer counts the whole list"* (ruling 30 —
// three lists, three badges); *"TC-4, the other direction: a utility with
// BLOCKING on reads the sentence"* (PO answer 2 — warn only, every tenant);
// *"draws NO today and NO utilisation column"* (images 25–28 draw neither, and
// the lists' own columns are asserted below instead). The DOM cases live in
// `crewsLane.dom.test.tsx`, on the server's RECORDED answers. These are the
// column sets and the pure helpers, read without a DOM.
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import {
  CERT_PILL,
  certificationState,
  contractorListConfig,
  crewListConfig,
  crewsViewFrom,
  expiringSoon,
  technicianListConfig,
} from "./CrewsPage";
import { WORK_TABS } from "./WorkShell";
import TECHNICIANS from "./__fixtures__/server/work.crews.technicians.json";
import CERT_WATCH from "./__fixtures__/server/work.certification-watch.json";

const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);
const labels = (config: { columns: { label: string }[] }) => config.columns.map((c) => c.label);

describe("ruling 30 — three lists, each with the drawn columns in the drawn order", () => {
  it("Technicians (image 25)", () => {
    expect(labels(technicianListConfig(t, { technician: () => null }))).toEqual([
      "Technician",
      "Crew",
      "Job title",
      "Skills",
      "Certifications",
      "Shift",
      "Status",
    ]);
  });

  it("Crews (image 27)", () => {
    expect(labels(crewListConfig(t))).toEqual(["Crew", "Members", "Does", "Skills", "Shift", "Status"]);
  });

  it("Contractors (image 28)", () => {
    expect(labels(contractorListConfig(t))).toEqual(["Contractor", "Skills", "Hours", "Status"]);
  });

  it("each list has its own search prompt (B14 rule 19), and every label is three words or fewer (rule 33)", () => {
    const configs = [technicianListConfig(t, { technician: () => null }), crewListConfig(t), contractorListConfig(t)];
    expect(configs.map((c) => t(c.searchPlaceholder ?? ""))).toEqual([
      "Search name or skill…",
      "Search crew or member…",
      "Search contractor…",
    ]);
    for (const config of configs) {
      for (const label of labels(config)) expect(label.split(/\s+/).length).toBeLessThanOrEqual(3);
    }
  });

  it("only the columns the server can sort are sortable (name; crew; members)", () => {
    const sortable = (config: { columns: { key: string; sortable?: boolean }[] }) =>
      config.columns.filter((c) => c.sortable === true).map((c) => c.key);
    expect(sortable(technicianListConfig(t, { technician: () => null }))).toEqual(["name", "crew"]);
    expect(sortable(crewListConfig(t))).toEqual(["name", "members"]);
    expect(sortable(contractorListConfig(t))).toEqual(["name"]);
  });

  it("the address names the list; anything else is Technicians", () => {
    expect(crewsViewFrom(null)).toBe("technicians");
    expect(crewsViewFrom("crews")).toBe("crews");
    expect(crewsViewFrom("contractors")).toBe("contractors");
    expect(crewsViewFrom("everyone")).toBe("technicians");
  });

  it("the Crews tab is on the module strip, before Parts", () => {
    const ids = WORK_TABS.map((tab) => tab.id);
    expect(ids.indexOf("crews")).toBeGreaterThan(-1);
    expect(ids.indexOf("crews")).toBeLessThan(ids.indexOf("parts"));
  });
});

describe("the certification pill, against the SERVER's day", () => {
  it("a recorded person whose certificate runs out within 30 days carries it; one far off does not", () => {
    const today = CERT_WATCH.today;
    const flagged = new Set(CERT_WATCH.windows.flatMap((w) => w.entries.map((e) => e.technician_slug)));
    for (const row of TECHNICIANS.results) {
      const soon = row.certifications.some(
        (c) => c.expires_on !== null && Date.parse(c.expires_on) - Date.parse(today) <= 30 * 86_400_000,
      );
      expect(expiringSoon(row, today)).toBe(soon);
      if (flagged.has(row.slug)) expect(expiringSoon(row, today)).toBe(true);
    }
  });
});

// ── CR-168-BRC10 lane FLOW-FIX · DEF-WRK-9639 ─────────────────────────────
// J. Okoro's First aid / CPR expired 2026-09-22 and the row read *cert
// expiring* while the watch below it said *expired*.
describe("DEF-WRK-9639 — an EXPIRED certificate is badged expired, never expiring", () => {
  const person = (expires_on: string | null) => ({
    certifications: [{ name: "First aid / CPR", expires_on } as never],
  });
  it("past → expired · within 30 days → expiring · far off or none → no pill", () => {
    const today = "2026-10-04";
    expect(certificationState(person("2026-09-22"), today)).toBe("expired");
    expect(certificationState(person("2026-10-20"), today)).toBe("expiring");
    expect(certificationState(person("2027-06-01"), today)).toBeNull();
    expect(certificationState(person(null), today)).toBeNull();
  });
  it("the two pills read two different words, and the expired one is the danger tier", () => {
    expect(CERT_PILL.expired.tone).toBe("danger");
    expect(t(CERT_PILL.expired.key)).toBe("cert expired");
    expect(t(CERT_PILL.expiring.key)).toBe("cert expiring");
  });
});
