// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defects: DEF-TEN-5706 (SET-06.1/SET-07.1 step 2 hand-rolled their list — no
//          column selector at all, a bare search box, a hand-made `+ Filter`
//          and their own pager) · DEF-TEN-5707 (47 strings on those two
//          wizards over B14 rule 33's caps; most of them RATIONALE)
// Rules:   B14 rule 33 (on-screen text is capped by what it is FOR; rationale
//          is zero words) · rule 36 (the shared component kit is how you
//          comply) · rule 16 (a pagination footer on every list table; wizard
//          SUMMARY tables exempt — a 79-row picker is not a summary) ·
//          rule 12 (the toolbar's grammar) · BR-MET-072 (the area filter is
//          MULTI-SELECT, never single-select)
// ───────────────────────────────────────────────────────
/**
 * THE TWO GUARDS THE PRODUCT OWNER'S REPORT OF 2026-09-17 IS OWED.
 *
 * Both faults were reported from the DEPLOYED BUILD with screenshots, and
 * neither was visible to any check in this repo: no gate reads rendered output
 * (hard-won law 6), `tsc` and every suite were green, and the wizards' own
 * tests asserted the CONTENT of the long sentences rather than their LENGTH —
 * so the copy could only ever grow.
 *
 * ⚠ **THE COPY GUARD READS THE CATALOGUE, NOT THE SCREEN, AND THAT IS ON
 * PURPOSE.** A rendered-output assertion would cover the strings this lane
 * happened to leave on the page; the catalogue is where the next lane ADDS one.
 * A 40-word lede introduced tomorrow fails here before it is ever wired.
 *
 * ⚠ **AND IT IS A PER-SENTENCE CAP, NOT A PER-STRING ONE, BECAUSE THAT IS WHAT
 * RULE 33 SAYS.** *"Two sentences of six beat one sentence of twelve"* — the
 * rule's own words. A total-word check would have failed eleven strings that
 * are perfectly lawful and would have pushed the next author toward ONE long
 * sentence, which is the thing the rule exists to prevent.
 */
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import i18n from "@/i18n";
import type { RouteRow } from "@/api/endpoints";
import type { ApiClient } from "@/api/client";
import { ToastProvider } from "@/components/Toast";

import { CycleWizard } from "./RoutesCyclesWizards";

afterEach(cleanup);

const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

// Node's own modules, by the string-split import this repo already uses — a
// bare `import … from "node:fs"` passes vitest and FAILS the tsc gate.
const nodeFs = (await import(/* @vite-ignore */ ["node", "fs"].join(":"))) as {
  readFileSync(p: string, enc: string): string;
  readdirSync(p: string): string[];
};
const nodePath = (await import(/* @vite-ignore */ ["node", "path"].join(":"))) as {
  join(...p: string[]): string;
  dirname(p: string): string;
};
const nodeUrl = (await import(/* @vite-ignore */ ["node", "url"].join(":"))) as {
  fileURLToPath(url: URL | string): string;
};
const HERE = nodeUrl.fileURLToPath(import.meta.url);
const SRC = nodePath.dirname(nodePath.dirname(nodePath.dirname(HERE)));
const LOCALES = nodePath.join(SRC, "i18n", "locales");

const PREFIXES = ["settings.routes.wizard.", "settings.cycles.wizard."];

/**
 * A string's SENTENCES, or none where it is not prose at all.
 *
 * A value strip — `Read 1–3 · bills out 5th · due 26th` — is a row of VALUES
 * separated by `·`, not a sentence, and counting its words as prose would be
 * measuring the wrong thing. It is recognised by having two or more `·` and no
 * sentence-ending punctuation.
 */
function sentencesOf(value: string): string[] {
  const separators = (value.match(/·/g) ?? []).length;
  if (separators >= 2 && !/[.!?]/.test(value)) {
    return [];
  }
  return value
    .split(/(?<=[.!?])\s+/)
    .map((part) => part.trim())
    .filter((part) => part !== "");
}

/** Words, counting an interpolation as the one value it renders as. */
function wordsOf(sentence: string): number {
  return sentence
    .replace(/\{\{\w+\}\}/g, "X")
    .replace(/[.!?]+$/, "")
    .split(/\s+/)
    .filter((word) => word !== "" && word !== "·").length;
}

function englishCatalogue(): Record<string, string> {
  return JSON.parse(nodeFs.readFileSync(nodePath.join(LOCALES, "en.json"), "utf8")) as Record<
    string,
    string
  >;
}

describe("DEF-TEN-5707 · B14 rule 33 on the two Routes & Cycles wizards", () => {
  it("no sentence on either wizard runs past six words", () => {
    const en = englishCatalogue();
    const over: string[] = [];
    for (const [key, value] of Object.entries(en)) {
      if (!PREFIXES.some((prefix) => key.startsWith(prefix))) {
        continue;
      }
      for (const sentence of sentencesOf(value)) {
        const words = wordsOf(sentence);
        if (words > 6) {
          over.push(`${key} — ${words} words: "${sentence}"`);
        }
      }
    }
    // The Product Owner's own words, 2026-09-17: *"too much text - please
    // reduce it"*. 47 strings were over when that was said.
    expect(over, `B14 rule 33 caps a sentence at six words:\n${over.join("\n")}`).toEqual([]);
  });

  it("the deleted RATIONALE stays deleted — these keys are gone from all eleven", () => {
    // ⚠ Rule 33's hardest clause: rationale is ZERO words on screen, so the
    // repair for these was DELETE and not shorten. A lane that re-adds one has
    // re-opened the defect, and a catalogue key is where that would start.
    const retired = [
      "settings.routes.wizard.step1Lede", // "A route is a meter-reading group…"
      "settings.routes.wizard.serviceHint", // "A premises can be on one route per service…"
      "settings.routes.wizard.areaHint", // "A label for the route. Which premises…"
      "settings.routes.wizard.auditNote", // "Every save here is recorded in the audit log…"
      "settings.cycles.wizard.step1Lede", // "A cycle is a group of routes…"
      "settings.cycles.wizard.auditNote",
    ];
    const files = nodeFs.readdirSync(LOCALES).filter((name) => name.endsWith(".json"));
    expect(files).toHaveLength(11);
    for (const file of files) {
      const data = JSON.parse(nodeFs.readFileSync(nodePath.join(LOCALES, file), "utf8")) as Record<
        string,
        string
      >;
      for (const key of retired) {
        expect(data[key], `${file} still carries the retired ${key}`).toBeUndefined();
      }
    }
  });
});

// ═══════════════════════════════════════════════════════════════════════════
// DEF-TEN-5706 — STEP 2 IS THE SHARED TABLE
// ═══════════════════════════════════════════════════════════════════════════

const CYCLE_QUERY = new QueryClient({
  defaultOptions: { queries: { retry: false, gcTime: 0 } },
});

function route(id: string, code: string, cycleCode: string | null = null): RouteRow {
  return {
    id,
    code,
    name: `${code} walk`,
    route_type: "walk",
    feeder_ref: null,
    assigned_to: null,
    cycle_id: cycleCode === null ? null : "c1",
    cycle_code: cycleCode,
    status: "active",
    members: 4,
    meters: 6,
    collected: null,
    last_completion: null,
    progress: null,
    service_id: null,
    service_code: null,
    services: [],
    area_code: null,
    area_name: null,
  } as unknown as RouteRow;
}

/**
 * ⚠ **MOUNTED UNDER THE REAL PATH PATTERN (`DEF-CWP-3925`).** A routed
 * component rendered bare inside a `MemoryRouter` has `useParams().tenant`
 * undefined, so every address it builds comes out `//…` — a protocol-relative
 * URL to another host, which reads as a perfectly good string to `toContain`.
 */

/**
 * ⚠ **THE WIZARD FETCHES ITS OWN PAGE OF ROUTES SINCE `DEF-MET-5743`**, so the
 * fixture hands it a CLIENT rather than an array. That is not ceremony: the
 * whole point of the change is that step 2 makes a request, and a fixture that
 * went on passing rows in memory could not tell the fixed screen from the
 * broken one.
 */
function routesClient(routes: RouteRow[]): ApiClient {
  return {
    get: async (path: string, options?: { query?: Record<string, unknown> }) => {
      if (path === "/routes") {
        // ⚠ **THE STUB CLAMPS `per` BECAUSE THE SERVER DOES** (`DEF-TEN-5840`).
        // `core.pagination.clamp_page_size` caps any `per` at the top of
        // `PAGE_SIZES` — 1,000 — silently, never as an error. A stub that
        // honoured `per: 40000` would answer a naive one-request select-all
        // with every row and report success, which is a fixture that cannot
        // tell a working walk from a broken one (`DEF-CWP-3925`).
        const per = Math.min(Number(options?.query?.per ?? 50), 1000);
        const page = Number(options?.query?.page ?? 1);
        const q = String(options?.query?.q ?? "");
        const onCycle = options?.query?.["f.on_cycle"];
        // The stub does the SERVER's job, because the screen no longer does it:
        // match, then window. A stub that returned everything would hide a
        // screen that had gone back to slicing in the browser.
        const matched = routes.filter((row) => {
          if (onCycle === "1" && row.cycle_code === null) {
            return false;
          }
          return (
            q.length < 2 ||
            row.code.toLowerCase().includes(q.toLowerCase()) ||
            (row.name ?? "").toLowerCase().includes(q.toLowerCase())
          );
        });
        return {
          data: {
            count: matched.length,
            next: null,
            previous: null,
            results: matched.slice((page - 1) * per, page * per),
          },
          status: 200,
          headers: new Headers(),
        };
      }
      return { data: { count: 0, next: null, previous: null, results: [] }, status: 200, headers: new Headers() };
    },
  } as unknown as ApiClient;
}

function renderCycleWizard(routes: RouteRow[]): void {
  render(
    <QueryClientProvider client={CYCLE_QUERY}>
      <ToastProvider>
        <MemoryRouter initialEntries={["/brazosbend/settings/reference-data/routes-cycles/cycles/new"]}>
          <Routes>
            <Route
              path="/:tenant/settings/reference-data/routes-cycles/cycles/new"
              element={
                <CycleWizard
                  cycle={null}
                  client={routesClient(routes)}
                  readOnly={false}
                  onDone={() => undefined}
                  onCancel={() => undefined}
                />
              }
            />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

async function toStepTwo(user: ReturnType<typeof userEvent.setup>): Promise<void> {
  await user.type(screen.getByLabelText(/Name/), "Quarterly — irrigation");
  await user.click(screen.getByRole("button", { name: t("wizard.continue") }));
}

describe("DEF-TEN-5706 · the picker is the shared table, with its three controls", () => {
  it("rule 36: the COLUMN SELECTOR exists — the control this screen never had", async () => {
    const user = userEvent.setup();
    renderCycleWizard([route("r1", "RT-001"), route("r2", "RT-002", "CY-001")]);
    await toStepTwo(user);
    // The PO named this one exactly: *"we are not using table component
    // toolkit - search, filter, colume selector"*. It is `ColumnChooser`'s
    // `<summary>` inside a `<details>` — the Meter Reads blueprint records a
    // probe that searched for a `button`, found none, and nearly reported the
    // control missing when it was there.
    expect(screen.getByText(t("table.columns.title"))).toBeInTheDocument();
  });

  it("rule 12 + 16: search and a pagination footer come from the kit", async () => {
    const user = userEvent.setup();
    renderCycleWizard([route("r1", "RT-001")]);
    await toStepTwo(user);
    expect(screen.getByLabelText(t("settings.routes.searchPlaceholder"))).toBeInTheDocument();
    expect(screen.getByText(t("table.pager.pageSize"))).toBeInTheDocument();
    expect(screen.getByLabelText(t("table.pager.next"))).toBeInTheDocument();

    // ⚠ **THE THREE ASSERTIONS ABOVE PASS ON THE BROKEN SCREEN TOO, AND THAT
    //    IS WHY THE TWO BELOW EXIST.** Proved, not assumed: run against the
    //    pre-fix code this case was GREEN, because the hand-rolled step 2 also
    //    had a search box with this very label and also rendered `ListPager`.
    //    A check whose name says *from the kit* and which cannot tell the kit
    //    from a hand-rolled copy is hard-won law 7's "looks at the wrong
    //    thing" — true, and useless for the defect it is named after.
    //
    //    `data-table-frame` is `DataTable`'s own root; `data-rcw="table"` was
    //    the marker on the `<table>` this screen used to draw itself. One must
    //    be present and the other must be gone.
    expect(document.querySelector(".data-table-frame")).not.toBeNull();
    expect(document.querySelector('[data-rcw="table"]')).toBeNull();
  });

  it("the FILTER is a real dimension, and it narrows the list", async () => {
    const user = userEvent.setup();
    renderCycleWizard([route("r1", "RT-001"), route("r2", "RT-002", "CY-001")]);
    await toStepTwo(user);
    // BR-MET-034 — a route already on a cycle is the row whose selection MOVES
    // it, so "show me only those" is the question this step asks.
    await user.selectOptions(
      screen.getByLabelText(t("settings.routes.wizard.addFilter")),
      "__unassigned",
    );
    await waitFor(() => {
      expect(screen.queryByText("RT-001")).not.toBeInTheDocument();
    });
    expect(screen.getByText("RT-002")).toBeInTheDocument();
    // …and the chip that says so carries its own labelled ✕ (B14 rule 12).
    expect(
      screen.getByLabelText(t("settings.cycles.wizard.removeOnCycleFilter")),
    ).toBeInTheDocument();
  });

  it("the running count survives the move to the kit", async () => {
    const user = userEvent.setup();
    renderCycleWizard([route("r1", "RT-001")]);
    await toStepTwo(user);
    // `DataTable` owns ROWS; what a wizard has CHOSEN from them is the
    // wizard's, and it is the number a clerk builds the cycle by.
    await user.click(screen.getByLabelText(t("settings.cycles.wizard.selectRoute", { route: "RT-001" })));
    expect(
      screen.getByText(t("settings.cycles.wizard.routesSelected.one", { count: 1 })),
    ).toBeInTheDocument();
  });
});

// ── `DEF-TEN-5840` · SELECT ALL, ON THE CYCLE WIZARD ─────────────────────────
/**
 * **THE CYCLE WIZARD'S STEP 2 HAD NO SELECT-ALL AT ALL**, while the route
 * wizard's — the same shape of picker over the same kind of list — has had one
 * since CR-006. PO, 2026-09-19: *"this is in premises/unit, route and cycle
 * creation context"*. Building a monthly cycle out of eighty routes meant
 * eighty clicks across two pages.
 *
 * ⚠ **WHAT WOULD MAKE THESE PASS WRONGLY, WHICH IS THE QUESTION LAW 7 ASKS.**
 * A case asserting *"some routes are selected"* passes on the page-only bug
 * this control exists to prevent — tick the fifty on screen under a filter
 * matching 1,200 and the clerk believes they have 1,200. So both cases assert
 * a **COUNT**, and the fixture is built at **1,200 routes** precisely because
 * that is larger than the server's `per` ceiling: a one-request implementation
 * gets 1,000 back and stops, and the count then reads 1,000 rather than 1,200.
 * That is the difference the walk exists for and it is the difference these
 * assert.
 */
describe("DEF-TEN-5840 · `Select all` on the cycle wizard means every MATCHING route", () => {
  const MANY = Array.from({ length: 1200 }, (_, i) =>
    route(`r${i}`, `RT-${String(i).padStart(4, "0")}`),
  );

  it("the label states the SERVER's total, never the rows on this page", async () => {
    const user = userEvent.setup();
    renderCycleWizard(MANY);
    await toStepTwo(user);
    await waitFor(() => {
      expect(
        screen.getByRole("button", {
          name: t("settings.routes.wizard.selectAllMatching", { count: 1200 }),
        }),
      ).toBeInTheDocument();
    });
    // The page holds fifty. A button reading "Select all 50" is exactly the
    // bug, so this is the assertion that can tell the two apart.
    expect(
      screen.queryByRole("button", {
        name: t("settings.routes.wizard.selectAllMatching", { count: 50 }),
      }),
    ).toBeNull();
  });

  it("pressing it selects all 1,200 — past the server's 1,000-row `per` ceiling", async () => {
    const user = userEvent.setup();
    renderCycleWizard(MANY);
    await toStepTwo(user);
    await user.click(
      await screen.findByRole("button", {
        name: t("settings.routes.wizard.selectAllMatching", { count: 1200 }),
      }),
    );
    // ⚠ **1,200 AND NOT 1,000.** The stub clamps `per` the way the real
    // endpoint does, so a single request — however large a `per` it asks for —
    // can only ever come back with 1,000 rows. The count below is what proves
    // the walk ran and what would have read `1000` if somebody "simplified" it
    // into one call.
    await waitFor(() => {
      expect(
        screen.getByText(
          t("settings.cycles.wizard.routesSelected.other", { count: 1200 }),
        ),
      ).toBeInTheDocument();
    });
  });

  it("`Clear selection` empties it again", async () => {
    const user = userEvent.setup();
    renderCycleWizard(MANY);
    await toStepTwo(user);
    await user.click(
      await screen.findByRole("button", {
        name: t("settings.routes.wizard.selectAllMatching", { count: 1200 }),
      }),
    );
    await waitFor(() => {
      expect(
        screen.getByText(t("settings.cycles.wizard.routesSelected.other", { count: 1200 })),
      ).toBeInTheDocument();
    });
    await user.click(
      screen.getByRole("button", { name: t("settings.routes.wizard.clearSelection") }),
    );
    expect(
      screen.getByText(t("settings.cycles.wizard.routesSelected.other", { count: 0 })),
    ).toBeInTheDocument();
  });
});
