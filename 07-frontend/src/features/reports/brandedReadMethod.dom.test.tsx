// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:  DEF-REP-6931 — a brand name inside a translated value.
// Rules:   BR-REP-045 (a manufacturer is DATA, never vocabulary — PO ruling
//          2026-09-27, option (a) of two, answered *"a"*) · B14 rule 33
// Impacts: features/reports/ReportViewerPage.tsx · the eleven catalogues
// ───────────────────────────────────────────────────────
//
// ╔══════════════════════════════════════════════════════════════════════════╗
// ║      THE WORDS ARE TRANSLATED · THE COMPANY'S NAME IS PRINTED AS DATA     ║
// ╚══════════════════════════════════════════════════════════════════════════╝
//
// ⚠ **THE RED THIS WAS PROVED ON.** Before this change the catalogues held
// `reports.value.source_detail.ami_itron` = `AMI · Itron` — the same eleven
// times, correctly, because *Itron* is a company. `G15` counted both values as
// untranslated. The first two cases below FAIL on the shipped code with
// `AMI · Itron` where `AMI feed · Itron` is expected, and the French case fails
// with `AMI · Itron` where `Flux AMI · Itron` is expected.
//
// ⚠ **WHAT WOULD MAKE THIS PASS WRONGLY** (hard-won law 7, habit 2):
//
//   · **Asserting only that `Itron` is on screen.** It was on screen before —
//     inside the translated value, which is the whole defect. Every case
//     asserts the WHOLE cell text, so the method half is pinned too.
//   · **Asserting only English.** The point of the ruling is that the words
//     move between languages and the name does not; a single-language
//     assertion cannot see that, so French is asserted beside English.
//   · **Asserting only the two manufacturers that exist today.** The PO
//     refused a hand-curated list precisely because a third manufacturer would
//     arrive and nobody would remember it. `ami_badger` is asserted although
//     no tenant holds one — if it ever needs adding to a list, this case goes
//     red and names it.
//   · **Splitting every vocabulary column.** `source_kind` stores
//     `ami_replay`, whose second half is a word and not a company. Asserted to
//     be LEFT ALONE, so a generic split cannot pass both cases.
import { cleanup, render } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import { ReportCell } from "./ReportViewerPage";

afterEach(cleanup);

function cell(column: string, value: string, lang = "en"): string {
  const { container } = render(
    <ReportCell
      reportKey="read_import_log"
      column={column}
      value={value}
      currency="USD"
      t={i18n.getFixedT(lang)}
      locale={lang}
      // ⚠ **REQUIRED SINCE `P6.11`, AND THIS FIXTURE WAS WRITTEN WITHOUT THEM**
      // — `2.383.4` added this file against `ReportCell`'s older signature, so
      // `tsc` went red for every lane on a file whose own cases all pass.
      // `ReportCell` requires both on purpose: the compiler then names every
      // call site that has to decide, rather than one of them silently
      // printing a UTC instant in a tenant that keeps its books in Boise.
      // This test reads no timestamp column, so the values only have to be
      // lawful.
      timeZone="America/Chicago"
      dateFormat="MM/DD/YYYY"
    />,
  );
  return container.textContent ?? "";
}

describe("BR-REP-045 · a manufacturer is data, never vocabulary", () => {
  it("renders the reading method as words and the maker beside it", () => {
    expect(cell("source_detail", "ami_itron")).toBe("AMI feed · Itron");
    expect(cell("source_detail", "ami_sensus")).toBe("AMI feed · Sensus");
  });

  it("translates the words and leaves the company's name exactly as stored", () => {
    expect(cell("source_detail", "ami_itron", "fr-FR")).toBe("Flux AMI · Itron");
    expect(cell("source_detail", "ami_sensus", "de")).toBe("AMI-Datenstrom · Sensus");
  });

  it("a manufacturer nobody has bought yet needs no edit anywhere", () => {
    expect(cell("source_detail", "ami_badger")).toBe("AMI feed · Badger");
  });

  it("a method with no maker after it is untouched", () => {
    expect(cell("source_detail", "walk_by")).toBe("Walk-by");
  });

  it("`source_kind`'s `ami_replay` is NOT split — `replay` is a word, not a maker", () => {
    expect(cell("source_kind", "ami_replay")).toBe("AMI");
  });
});
