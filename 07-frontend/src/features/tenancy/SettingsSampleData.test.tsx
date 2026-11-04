// ── Trace ──────────────────────────────────────────────
// Story:    US-TEN-019 (EP-TEN-03 — tenant sample data: seed it, tag it, report
//           it, remove it)   Screens: S8 (Settings → Company profile)
// Rules:    BR-TEN-060 (an unwired seam is a NAMED line, not a skip) ·
//           BR-TEN-056 (a run with any skip does not report success) ·
//           BR-TEN-066 (removal is partial-and-named) · BR-TEN-069 (both
//           actions on Company profile) · BR-SHL-020 (plain-language states)
// ───────────────────────────────────────────────────────
// EVERY ASSERTION HERE IS A NEGATIVE ONE, and that is the point of the file.
//
// The sample-data engine seeds nothing today and says so. The failure modes are
// all on this side of the wire — a screen that renders that truthful report as
// a success, as a bare zero, or as an empty "no sample data" state. Each of
// those has a defect number already: DEF-016 (a skip inside a summary nobody
// read, found by the PO on a live deployment) and DEF-127 (a zero standing in
// for "I don't know").
//
// So this suite asserts:
//   1. never-asked and asked-and-loaded-nothing render DIFFERENTLY;
//   2. a run that loaded nothing never renders the success line;
//   3. every not-loaded module's REASON reaches the DOM, not just its name.
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import type { SampleDataReport } from "@/api/endpoints";

import { SampleDataReportBody } from "./SettingsSampleData";

const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

/** A tenant that has never pressed the button. */
const NEVER_RUN: SampleDataReport = {
  modules: [],
  seeded_total: 0,
  not_loaded: [],
  succeeded: false,
  counts_toward_progress: false,
  has_run: false,
  // CR-039 wave B: this fixture keeps `blocks: []` deliberately — it is the
  // LEGACY shape (a run recorded before block-level reporting), so these cases
  // go on pinning the module-line fallback that shape still has to render.
  blocks: [],
  blocks_recorded: false,
  removal: { order: [], removable: 0, retained: [], blocked: [] },
};

const SEAM_DETAIL =
  "apps.metering.services.seed_sample_records is not published, so nothing can write this block.";

/** The REAL shape of a run today: it ran, and every module is named. */
const RAN_AND_LOADED_NOTHING: SampleDataReport = {
  modules: [
    {
      module: "metering",
      label: "Premises, units & service points",
      outcome: "skipped",
      reason_code: "seam_not_wired",
      detail: SEAM_DETAIL,
      count: 0,
    },
    {
      module: "rating",
      label: "Plans & rates",
      outcome: "skipped",
      reason_code: "seam_not_wired",
      detail: "apps.rating.services.seed_sample_records is not published",
      count: 0,
    },
  ],
  seeded_total: 0,
  not_loaded: [
    {
      module: "metering",
      label: "Premises, units & service points",
      reason_code: "seam_not_wired",
      detail: SEAM_DETAIL,
    },
  ],
  succeeded: false,
  counts_toward_progress: false,
  has_run: true,
  blocks: [],
  blocks_recorded: false,
  removal: { order: ["meter_reads", "premises"], removable: 0, retained: [], blocked: [] },
};

function render(report: SampleDataReport): string {
  return renderToStaticMarkup(<SampleDataReportBody report={report} t={t} />);
}

/**
 * The real server labels contain `&` ("Premises, units & service points"), and
 * React escapes it into the markup. Asserting on the escaped form rather than
 * renaming the fixture keeps the test measuring the label the server actually
 * sends — a fixture bent to fit an assertion stops covering the real string.
 */
function escaped(value: string): string {
  return value.replace(/&/g, "&amp;");
}

describe("US-TEN-019 — the sample-data report never flatters itself", () => {
  it("TC-13 · never-asked and loaded-nothing are DIFFERENT screens, not one zero", () => {
    const never = render(NEVER_RUN);
    const ran = render(RAN_AND_LOADED_NOTHING);

    // The never-asked state says so in words and shows no per-module verdicts:
    // an operator who has not pressed the button has not been told anything.
    expect(never).toContain(t("settings.sampleData.neverRun"));
    expect(never).not.toContain(t("settings.sampleData.nothingLoaded"));
    expect(never).not.toContain("Premises, units");

    // The after-a-run state is the opposite of that in every respect.
    expect(ran).not.toContain(t("settings.sampleData.neverRun"));
    expect(ran).toContain(t("settings.sampleData.nothingLoaded"));
    expect(never).not.toBe(ran);
  });

  it("TC-5 · a run that loaded nothing NEVER renders the success line", () => {
    const html = render(RAN_AND_LOADED_NOTHING);
    // BR-TEN-056 clause 3 — this is DEF-016's exact shape and the one string
    // that must never appear over a zero-row run.
    expect(html).not.toContain(t("settings.sampleData.loaded", { count: 0 }));
    expect(html).toContain(t("settings.sampleData.nothingLoaded"));
  });

  it("TC-5 · every not-loaded module reaches the DOM WITH its reason, not just its name", () => {
    const html = render(RAN_AND_LOADED_NOTHING);
    for (const row of RAN_AND_LOADED_NOTHING.modules) {
      expect(html).toContain(escaped(row.label));
      expect(html).toContain(t("settings.sampleData.outcome.skipped"));
      // BR-TEN-060: NAMED, with a sentence an operator can act on. A label
      // beside "Not loaded" and no reason is a skip in a smaller font.
      expect(html).toContain(row.detail ?? "");
    }
  });

  it("BR-TEN-060 · the advisory note is on screen, so red lines do not read as a broken setup", () => {
    expect(render(RAN_AND_LOADED_NOTHING)).toContain(t("settings.sampleData.advisory"));
  });

  it("a genuinely seeded run DOES get its count — the rule is not 'never show a number'", () => {
    const seeded: SampleDataReport = {
      ...RAN_AND_LOADED_NOTHING,
      modules: RAN_AND_LOADED_NOTHING.modules.map((row) => ({
        ...row,
        outcome: "seeded" as const,
        reason_code: null,
        detail: null,
        count: 19,
      })),
      not_loaded: [],
      seeded_total: 38,
      succeeded: true,
    };
    const html = render(seeded);
    expect(html).toContain(t("settings.sampleData.loaded", { count: 38 }));
    expect(html).not.toContain(t("settings.sampleData.nothingLoaded"));
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-TEN-019@c3b7d18 (EP-TEN-03 — the S8 surface half; ships with features/tenancy/SettingsSampleData.tsx)
// generated: 2026-08-16 by story-coder (unreachable-screens lane)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09 — not a 🔒 path: no money figure, threshold or key is asserted here)
// gates: vitest 5 passed✔ · tsc✔ · eslint --max-warnings 0✔ · G15 11 catalogues × 4308 keys✔ · G13 unwired-props✔ · RED-PROVED: forcing the success branch in SettingsSampleData.tsx renders "0 sample records loaded." over a zero-row run and two of these five TCs go red
// exceptions: the fixtures carry the SERVER's real diagnostic sentences verbatim rather than short stand-ins, because the assertion under test is that the reason reaches the DOM — a fixture trimmed to fit the assertion would stop covering the string a user actually sees
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
