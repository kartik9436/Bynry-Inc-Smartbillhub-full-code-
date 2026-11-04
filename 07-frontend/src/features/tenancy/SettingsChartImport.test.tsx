// ── Trace ──────────────────────────────────────────────
// Change:   CR-008 Tab 1 (SET-11.coa) — *"Import CSV: ETL-style flow (upload →
//           map columns code/name/type → validate → load) with dedupe on code"*
//           Screens: SET-11 → Chart of accounts
// Rules:    BR-LED-015 · BR-SHL-020 · BR-SHL-025 · US-LED-005
// ───────────────────────────────────────────────────────
// §3 test cases for the import, written from the CR's own sentence rather than
// from the code: a file is PARSED the way a spreadsheet writes one, the columns
// are MAPPED by a person, and nothing is loaded until the server has looked.
//
// The judgments — is this type real, is this code taken, is it in the file
// twice — are asserted on the SERVER (tests/test_cr008_chart_import.py). What
// is asserted here is only what this half owns: the parsing, the mapping, and
// which control is available when.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import { ToastProvider } from "@/components/Toast";

import {
  ChartImportModal,
  guessMapping,
  mappingIsComplete,
  parseDelimited,
  rowsFromMapping,
} from "./SettingsChartImport";

const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

describe("CR-008 — a chart file is parsed the way a spreadsheet writes one", () => {
  it("splits a plain file into a header row and its accounts", () => {
    const parsed = parseDelimited("code,name,type\n1200,Accounts receivable,asset\n4110,Water usage revenue,revenue\n");
    expect(parsed.headers).toEqual(["code", "name", "type"]);
    expect(parsed.rows).toHaveLength(2);
    expect(parsed.rows[1]).toEqual(["4110", "Water usage revenue", "revenue"]);
  });

  it("a quoted field keeps its comma — an account name is not two columns", () => {
    const parsed = parseDelimited('code,name,type\n4115,"Water revenue, base",revenue\n');
    expect(parsed.rows[0][1]).toBe("Water revenue, base");
  });

  it('a doubled quote inside a quoted field is one literal quote', () => {
    const parsed = parseDelimited('code,name,type\n1500,"The ""old"" meter fund",asset\n');
    expect(parsed.rows[0][1]).toBe('The "old" meter fund');
  });

  it("a Windows export gains no blank rows AND no stray carriage returns", () => {
    const parsed = parseDelimited("code,name,type\r\n1200,AR,asset\r\n4110,Water,revenue\r\n");
    expect(parsed.rows).toHaveLength(2);
    // The last field of every line is the one that carries the \r, and a type
    // of "asset\r" is refused by the server as an unknown type — a whole
    // import failing on an invisible character.
    expect(parsed.rows[0][2]).toBe("asset");
    expect(parsed.headers[2]).toBe("type");
  });

  it("an empty file is empty rather than one row of nothing", () => {
    expect(parseDelimited("")).toEqual({ headers: [], rows: [] });
    expect(parseDelimited("\n\n")).toEqual({ headers: [], rows: [] });
  });
});

describe("CR-008 — the column mapping is the PERSON's, and guessing stays timid", () => {
  it("headers that ARE the field names are pre-selected, whatever their case", () => {
    expect(guessMapping(["Code", "NAME", "type"])).toEqual({
      code: "Code",
      name: "NAME",
      type: "type",
    });
  });

  it("a header that merely LOOKS like the field is left for the user to choose", () => {
    // "Account Code" is almost certainly the code. Almost is the problem: a
    // fuzzy match that is right four times in five loads the fifth utility's
    // chart under the wrong column, silently.
    expect(guessMapping(["Account Code", "Account Name", "Class"])).toEqual({
      code: "",
      name: "",
      type: "",
    });
  });

  it("mapping is INCOMPLETE until all three fields point somewhere", () => {
    expect(mappingIsComplete({ code: "A", name: "B", type: "C" })).toBe(true);
    expect(mappingIsComplete({ code: "A", name: "", type: "C" })).toBe(false);
  });

  it("rows come out in the server's shape, trimmed, with the type lower-cased", () => {
    const parsed = parseDelimited("Class,Number,Title\nASSET, 1200 , Accounts receivable \n");
    const rows = rowsFromMapping(parsed, { code: "Number", name: "Title", type: "Class" });
    expect(rows).toEqual([{ code: "1200", name: "Accounts receivable", type: "asset" }]);
  });

  it("a column the user has not mapped yields an EMPTY value, never a wrong one", () => {
    const parsed = parseDelimited("code,name\n1200,AR\n");
    const rows = rowsFromMapping(parsed, { code: "code", name: "name", type: "" });
    // The server then refuses it by name (`type_unknown`) — this half does not
    // invent "asset" to make the row go through.
    expect(rows[0].type).toBe("");
  });
});

describe("CR-008 — nothing is loaded before the file has been looked at", () => {
  function render(): string {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    return renderToStaticMarkup(
      <QueryClientProvider client={queryClient}>
        <ToastProvider>
          <ChartImportModal onClose={() => undefined} onImported={() => undefined} />
        </ToastProvider>
      </QueryClientProvider>,
    );
  }

  it("with no file chosen, both Check and Add are disabled and SAY WHY", () => {
    const html = render();
    expect(html).toContain(t("settings.accounting.import.validate"));
    expect(html).toContain(t("settings.accounting.import.load", { count: 0 }));
    // BR-SHL-025: the reason travels on the control, never as a vanished one.
    expect(html).toContain(t("settings.accounting.import.needFile"));
    expect(html).toContain(t("settings.accounting.import.needValidate"));
    expect(html).toContain("disabled");
  });

  it("the modal states the dedupe rule before anybody clicks anything", () => {
    // *"Accounts you already have are left exactly as they are"* — the CR's
    // dedupe, said where the decision is made rather than in a report after.
    expect(t("settings.accounting.import.lede")).toContain("already have");
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-008@11-change-requests.md §CR-008 + PO RULINGS 2026-08-17 (ruling 3 — file only, no live integration)
// generated: 2026-08-17 by story-coder (CR-008 SET-11 lane)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: PROVED RED FIRST (law 7), measured and quoted rather than claimed — the parser was replaced with the naive `line.split(",")` an import would otherwise have shipped with, and THREE of these went red: the quoted comma (`expected '"Water revenue' to be 'Water revenue, base'`), the doubled quote (`expected '"The ""old"" meter fund"' to be 'The "old" meter fund'`) and the Windows export (`expected 'asset\r' to be 'asset'`). The other nine stayed green under the same mutation, which is the honest reading: they cover the MAPPING, and the mapping does not care how the file was split. tsc✔ · eslint --max-warnings 0✔ · vitest 12 passed✔
// exceptions: E4 the modal is rendered to STATIC markup, so the file-choosing and the two server round trips are not exercised here — those are the browser walkthrough's, and the server's own refusals have their own tests
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
