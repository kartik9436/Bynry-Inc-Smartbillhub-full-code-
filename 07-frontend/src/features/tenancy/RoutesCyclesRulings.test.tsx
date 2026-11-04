// ── Trace ──────────────────────────────────────────────
// Change:  CR-029 RC-W6b (PO 2026-08-23) — the two rulings that landed AFTER
//          the screens were built, asserted where a lane would otherwise
//          "fix" them back to the screenshot.
// Design:  04-docs/02-decisions/17-cr029-routes-cycles-design.md (B17) §3
// Rules:   OQ-343 CLOSED-RULED, PO verbatim *"B: no reader anywhere, correct
//          the screenshot and drop the stored name"* ·
//          OQ-338 CLOSED-RULED, PO verbatim *"A: geography only - option a"* ·
//          D6 (reader assignment is out of CR-029) · D5 (the RT-/CY- grammar)
// Screens: SET-04 (Areas & sub-areas) · SET-06D (route detail) ·
//          SET-07D (cycle detail) · SET-07.3 (cycle wizard, schedule)
// ───────────────────────────────────────────────────────
/**
 * ⚠ **BOTH RULINGS REVERSE SOMETHING THE PO THEMSELVES DREW OR IMPLIED**, which
 * is exactly the shape of change the next lane undoes in good faith:
 *
 * - **OQ-343.** The PO's own SET-06D.audit screenshot shows *"Aug 2026 · Aug 3
 *   · M. Chen · 196 · 196 · Complete"*. They ruled the column OUT anyway, and
 *   ruled the stored name out with it. So the screenshot is CORRECTED, not
 *   followed — and a test has to say so, because the drawing does not.
 * - **OQ-338.** r10's SET-04 "Areas & sub-areas" list duplicated the routes
 *   registry byte for byte. The ruling makes the routes registry the ONLY place
 *   a route is created or edited; SET-04 holds areas and nothing route-shaped.
 *
 * Neither is a behaviour this repo could have inferred. Each is asserted here
 * by its ruling, in the PO's own words, so a future "the screenshot says…"
 * lands on a red test instead of on a customer.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import type { LookupCard, LookupEntry, Paginated } from "@/api/endpoints";
import { queryKeys } from "@/api/queryClient";
import { ToastProvider } from "@/components/Toast";

import { REFERENCE_CARDS } from "./referenceDataConfig";
import { ReferenceDataTab } from "./SettingsReferenceData";

const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

// Node's own modules, reached exactly the way `src/components/buttonKit.test.ts`
// and `src/styles/routeBUtilities.test.ts` do — the string-split import keeps
// Vite from pre-bundling them and keeps `tsc` (which carries no @types/node for
// `src/`) out of it. A bare `import … from "node:fs"` passes vitest and FAILS
// the tsc gate.
const nodeFs = (await import(/* @vite-ignore */ ["node", "fs"].join(":"))) as {
  readFileSync(p: string, enc: string): string;
  readdirSync(p: string): string[];
  readdirSync(p: string, o: { withFileTypes: true }): { name: string; isDirectory(): boolean }[];
};
const nodePath = (await import(/* @vite-ignore */ ["node", "path"].join(":"))) as {
  join(...p: string[]): string;
  dirname(p: string): string;
  relative(from: string, to: string): string;
};
const nodeUrl = (await import(/* @vite-ignore */ ["node", "url"].join(":"))) as {
  fileURLToPath(url: URL | string): string;
};

const HERE = nodeUrl.fileURLToPath(import.meta.url);
const SRC = nodePath.dirname(nodePath.dirname(nodePath.dirname(HERE)));
const LOCALES = nodePath.join(SRC, "i18n", "locales");

/** The files PO 2026-10-24 (MQ-033) licenses to carry a reader field: the
 *  assign/reassign dialog on Reads → cycle → Routes, its test and its seam. */
const ROUTES_TAB_READER_FILES: readonly string[] = [
  "features/metering/AssignReaderModal.dom.test.tsx",
  "features/metering/AssignReaderModal.tsx",
  "features/metering/routeReaderEndpoints.ts",
];

/** Every `.ts`/`.tsx` under `src/`, so a reader that creeps back in ANYWHERE
 *  is caught — not only in the two files this lane happened to edit. */
function everySource(): { file: string; text: string }[] {
  const out: { file: string; text: string }[] = [];
  const walk = (dir: string): void => {
    for (const entry of nodeFs.readdirSync(dir, { withFileTypes: true })) {
      const full = nodePath.join(dir, entry.name);
      if (entry.isDirectory()) {
        walk(full);
      } else if (/\.tsx?$/.test(entry.name)) {
        out.push({ file: nodePath.relative(SRC, full), text: nodeFs.readFileSync(full, "utf8") });
      }
    }
  };
  walk(SRC);
  return out;
}

// ═══════════════════════════════════════════════════════════════════════════
// OQ-343 — *"B: no reader anywhere, correct the screenshot and drop the
// stored name"*
// ═══════════════════════════════════════════════════════════════════════════
describe("OQ-343 · no reader on the Routes & Cycles screens (superseded for the cycle Routes tab, PO 2026-10-24)", () => {
  it("the read-window contract declares NO reader field — the stored name is dropped", () => {
    const endpoints = nodeFs.readFileSync(nodePath.join(SRC, "api", "endpoints.ts"), "utf8");
    const start = endpoints.indexOf("export interface RouteReadWindowRow");
    expect(start).toBeGreaterThan(-1);
    const block = endpoints.slice(start, endpoints.indexOf("}", start));
    expect(block).not.toContain("reader_id");
    expect(block).not.toContain("reader_name");
  });

  /**
   * ⚠ **THIS MATCHES A FIELD, NOT A WORD, AND THE DIFFERENCE IS DELIBERATE.**
   * The first version of this check forbade the STRING `reader_name` anywhere
   * under `src/`, and it went red on three files whose only mention was the
   * comment explaining the ruling — i.e. it would have driven the write-back
   * out of the code to make itself green. So it looks for a property being
   * DECLARED (`reader_name:`), READ (`.reader_name`) or INDEXED
   * (`["reader_name"]`); prose naming the dropped column stays legal, and must,
   * because a lane that cannot find the reasoning restores the column.
   */
  it("no frontend source DECLARES, READS or INDEXES a reader field — outside the cycle's Routes tab", () => {
    const asAField = /(?:\.|\["|\['")\s*reader_(?:name|id)|reader_(?:name|id)\s*:|readerName/;
    const offenders = everySource()
      .filter(({ file }) => file !== nodePath.relative(SRC, HERE))
      .filter(({ file }) => !ROUTES_TAB_READER_FILES.includes(file))
      .filter(({ text }) => asAField.test(text))
      .map(({ file }) => file);
    expect(offenders).toEqual([]);
  });

  /**
   * ⚠ **SUPERSEDED FOR READS → CYCLE → ROUTES ONLY — PO 2026-10-24 (decision
   * log, the MQ-033 reader-assignment ruling):** *"i have given you a screen
   * from where assign/reassign should be done"*, pointing at the cycle's
   * Routes tab. A route's reader is assigned there, so the three files that
   * build that dialog may name the field. The list is EXACT: a fourth file
   * goes red above, and every surface the ruling left reader-free is held
   * below by name.
   */
  it("the allowed reader files are exactly the cycle Routes tab's dialog", () => {
    const asAField = /(?:\.|\["|\['")\s*reader_(?:name|id)|reader_(?:name|id)\s*:|readerName/;
    const present = everySource()
      .filter(({ file }) => ROUTES_TAB_READER_FILES.includes(file))
      .filter(({ text }) => asAField.test(text))
      .map(({ file }) => file)
      .sort();
    expect(present).toEqual([...ROUTES_TAB_READER_FILES].sort());
  });

  it("Settings → Routes, the route reads page and the cycle Overview stay reader-free", () => {
    const readerFree = [
      "features/tenancy/SettingsRoutesCyclesTab.tsx",
      "features/tenancy/RouteDetailPage.tsx",
      "features/tenancy/CycleDetailPage.tsx",
      "features/tenancy/RoutesCyclesWizards.tsx",
      "features/metering/RoutesCyclesPage.tsx",
      "features/metering/RouteReadsPage.tsx",
    ];
    const usesReader = /from "\.\/(?:AssignReaderModal|routeReaderEndpoints)"|metering\.routeReader\./;
    for (const file of readerFree) {
      const text = nodeFs.readFileSync(nodePath.join(SRC, file), "utf8");
      expect({ file, reader: usesReader.test(text) }).toEqual({ file, reader: false });
    }
    // The cycle's Overview panel mounts the same table in its "overview"
    // column set; the Reader column and the dialog live behind "full" only.
    const cycle = nodeFs.readFileSync(
      nodePath.join(SRC, "features", "metering", "ReadCycleDetailPage.tsx"),
      "utf8",
    );
    const overview = cycle.slice(cycle.indexOf("function OverviewTab("), cycle.indexOf("export function Figure("));
    expect(overview.length).toBeGreaterThan(0);
    expect(overview).toContain('columns="overview"');
    expect(usesReader.test(overview)).toBe(false);
  });
});

// ═══════════════════════════════════════════════════════════════════════════
// OQ-338 — *"A: geography only - option a"*
// ═══════════════════════════════════════════════════════════════════════════
const AREA_ROWS: LookupEntry[] = [
  { id: "a1", code: "NORTH", name: "North district", active: true, is_system: false, used_by: 0 },
  {
    id: "a2",
    code: "NE",
    name: "North · East",
    active: true,
    is_system: false,
    used_by: 0,
    parent_code: "NORTH",
    parent_name: "North district",
  } as LookupEntry,
];

const SERVER_CARDS: LookupCard[] = [{ list: "areas", owner: "metering", count: 4, state: "seeded" }];

function page<T>(results: T[]): Paginated<T> {
  return { count: results.length, next: null, previous: null, results };
}

function renderAreas(): string {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  queryClient.setQueryData(queryKeys.lookupCards, SERVER_CARDS);
  queryClient.setQueryData(queryKeys.lookupEntries("areas", "", 1, 50), page(AREA_ROWS));
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={["/settings/reference-data?list=areas"]}>
          <ReferenceDataTab readOnly={false} />
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

describe("OQ-338 · areas are geography, and routes are edited in ONE place", () => {
  it("Settings' reference data declares NO route- and NO cycle-shaped card", () => {
    const routeShaped = REFERENCE_CARDS.filter((card) => /route|cycle/i.test(card.code));
    expect(routeShaped.map((card) => card.code)).toEqual([]);
  });

  it("the Areas card's own sample line names geography, never routes", () => {
    expect(t("settings.reference.sample.areas")).not.toMatch(/route/i);
  });

  it("SET-04's Areas list renders areas and nothing route-shaped", () => {
    const html = renderAreas().toLowerCase();
    expect(html).toContain("areas &amp; sub-areas");
    expect(html).toContain("north district");
    // The one editing surface for a route is the routes registry (SET-05).
    // A route word here — a column, a count, an action — is the r10
    // duplication the ruling closed.
    for (const banned of ["route", "cycle", "walk order", "reading order"]) {
      expect(html).not.toContain(banned);
    }
  });
});

// ═══════════════════════════════════════════════════════════════════════════
// DEF-606 / DEF-607 — the field says one thing and the copy beneath it said
// another. Both are `ui-copy`, and both needed eleven catalogues, which is why
// they sat open.
// ═══════════════════════════════════════════════════════════════════════════
const LOCALE_FILES: string[] = nodeFs
  .readdirSync(LOCALES)
  .filter((f: string) => f.endsWith(".json"));

function catalogue(file: string): Record<string, string> {
  return JSON.parse(nodeFs.readFileSync(nodePath.join(LOCALES, file), "utf8")) as Record<
    string,
    string
  >;
}

describe("DEF-606 · SET-07D's footnote calls the field by its real name", () => {
  it("the footnote says DUE DAYS — the label above it is `billing.run.field.dueDays`", () => {
    const footnote = t("settings.cycles.detail.defaultsFootnote");
    expect(footnote).toContain("due days");
    expect(footnote).not.toMatch(/due day\b(?!s)/);
    // The D9 clause it exists to carry is untouched.
    expect(footnote).toContain("without changing what is saved here");
  });
});

describe("DEF-607 · the cycle wizard separates day-of-month fields from counts", () => {
  /**
   * ⚠ **DEF-607's FACT MOVED FROM THE LEDE TO THE FIELDS, AND THE ASSERTION
   * MOVED WITH IT (DEF-TEN-5707).** The repair of 2026-08-xx made the step-3
   * lede say, in prose, that `Start day` and `Bill day` are days of the month
   * while `Days to complete` and `Due days` are counts. It was correct and it
   * was 44 words, which the Product Owner reported on 2026-09-17 — *"too much
   * text - please reduce it"*.
   *
   * **The reason the paragraph was needed at all is the defect underneath it:
   * `Days to complete` had NO HINT.** Three of the four boxes explained
   * themselves and the fourth did not, so the difference had to be narrated
   * above them. It has its own hint now, which is where B14 rule 32 puts a
   * control's own fact, and the lede is six words.
   *
   * So this asserts the SAME distinction in its new home. It is strictly
   * harder to break by accident than the old one: a lane rewording a lede
   * cannot silently take a field's hint with it.
   */
  it("the two day-of-month fields say so, and the two counts say so", () => {
    // The days of the month.
    expect(t("settings.cycles.wizard.dayHint")).toContain("Day of the month");
    // The counts. `countHint` is new and exists precisely because this box had
    // nothing; `dueDaysHelp` already named itself in days.
    expect(t("settings.cycles.wizard.countHint")).toContain("days");
    expect(t("settings.cycles.wizard.countHint").toLowerCase()).not.toContain("day of the month");
    expect(t("billing.run.field.dueDaysHelp").toLowerCase()).toContain("days");
  });

  it("the lede no longer argues, and ruling 3 still reaches the user", () => {
    const lede = t("settings.cycles.wizard.step3Lede");
    expect(lede).not.toContain("These are the days of the month this cycle usually runs on");
    expect(lede).toContain("Defaults only");
    expect(lede).toContain("Each run can change them");
    // B14 rule 33 — six words a sentence, and this is the check that keeps it.
    for (const sentence of lede.split(".").filter((part) => part.trim() !== "")) {
      expect(sentence.trim().split(/\s+/).length).toBeLessThanOrEqual(6);
    }
  });
});

describe("DEF-606 · DEF-607 — eleven catalogues, TRANSLATED", () => {
  const keys = [
    "settings.cycles.detail.defaultsFootnote",
    "settings.cycles.wizard.step3Lede",
    "settings.reference.sample.areas",
  ];

  it("every locale carries every key", () => {
    expect(LOCALE_FILES).toHaveLength(11);
    for (const file of LOCALE_FILES) {
      const data = catalogue(file);
      for (const key of keys) {
        expect(typeof data[key], `${file} ${key}`).toBe("string");
      }
    }
  });

  it("no locale falls back to the English sentence", () => {
    const en = catalogue("en.json");
    for (const file of LOCALE_FILES.filter((f: string) => f !== "en.json")) {
      const data = catalogue(file);
      for (const key of keys) {
        expect(data[key], `${file} ${key} is still English`).not.toBe(en[key]);
      }
    }
  });
});
