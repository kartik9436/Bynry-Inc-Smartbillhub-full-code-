// ── Trace ──────────────────────────────────────────────
// Story:    CR-043 findings 5, 6, 7, 10 (the bills list and the shared header)
//           Screens: BIL-01 (S30 All bills) · every screen using PageHeader
// Rules:    BR-SHL-044 / B14 rule 2 (ONE page header, right-aligned actions) ·
//           B14 rule 21 (a new piece of UI adds NO class to a stylesheet) ·
//           BR-SHL-010 (an undeclared capability is not rendered) ·
//           IS-3 (server-side search from two characters)
// Tests:    this file
// ───────────────────────────────────────────────────────
/**
 * The CR-043 findings that no rendered-output check can see.
 *
 * ⚠ **HARD-WON LAW 6 IS WHY THESE ARE WRITTEN AS SOURCE ASSERTIONS.** Nothing
 * in this repo reads rendered output, and `jsdom` computes no layout — it will
 * happily report `justify-content: space-between` as "right-aligned" because it
 * never lays a single box out. DEF-966 was found in a browser and could not be
 * found any other way. So the guard reads the DECLARATION that fixes it, which
 * is the next best thing and is the same trade `tailwindTheme.test.ts` makes.
 */
import { describe, expect, it } from "vitest";

import { BILLS_SEARCH_PLACEHOLDER_KEY, billsTableConfig, billsCells } from "./BillsListPage";
import en from "@/i18n/locales/en.json";

// Read at runtime through a non-literal dynamic import — the app carries no
// `@types/node` on purpose, so a static `import { readFileSync }` would fail
// `tsc --noEmit` and break `npm run build` (the idiom
// `OwnerMatching.dom.test.tsx` documents).
const nodeFs = (await import(/* @vite-ignore */ ["node", "fs"].join(":"))) as {
  readFileSync(path: string, encoding: string): string;
};
const nodePath = (await import(/* @vite-ignore */ ["node", "path"].join(":"))) as {
  join(...parts: string[]): string;
};
const nodeUrl = (await import(/* @vite-ignore */ ["node", "url"].join(":"))) as {
  fileURLToPath(url: URL): string;
};
// `import.meta.url`, not `process.cwd()` — the app carries no `@types/node`, so
// `process` is a `tsc --noEmit` error and `npm run build` would fail. This is
// the idiom `src/styles/tailwindTheme.test.ts` established for the same reason.
const HERE = nodeUrl.fileURLToPath(new URL(".", import.meta.url));
const SRC = nodePath.join(HERE, "..", "..");
const REPO = nodePath.join(SRC, "..", "..");

const catalog = en as Record<string, string>;
const t = (key: string) => catalog[key] ?? key;

describe("DEF-966 — the shared page header's actions stay right-aligned when they wrap", () => {
  it("`.page-header-actions` declares `margin-left: auto`", () => {
    const css = nodeFs.readFileSync(
      nodePath.join(SRC, "components", "PageHeader.css"),
      "utf8",
    );
    const rule = css.slice(css.indexOf(".page-header-actions {"));
    const body = rule.slice(0, rule.indexOf("}"));

    // ⚠ THE MECHANISM, so a later reader does not "simplify" this away:
    // `.page-header-top` is `display:flex` + `justify-content:space-between` +
    // `flex-wrap:wrap`. Those three right-align the SECOND child only while both
    // children share one line; a wrapped line holding one item sits hard LEFT,
    // which is what the PO photographed on BIL-02 (*"buttons position is not as
    // per UI rule it should be top right corner"*). `margin-left:auto` pushes
    // this child right on whatever line it lands on.
    expect(body).toContain("margin-left: auto");

    // The parent must KEEP `space-between` — that is what holds the title hard
    // left, which is the other half of B14 rule 2.
    const top = css.slice(css.indexOf(".page-header-top {"));
    expect(top.slice(0, top.indexOf("}"))).toContain("justify-content: space-between");
  });

  it("no other stylesheet re-declares the header's alignment (the sweep CR-043 asked for)", () => {
    // `PageHeader.css`'s own header names eight suites that SELECT `.page-header`;
    // the question this answers is different — does any OTHER stylesheet
    // override the alignment and undo the fix on one screen? Swept 2026-08-27:
    // no `.page-header*` rule exists outside `components/PageHeader.css`.
    const stylesheets: string[] = [];
    const walk = (dir: string) => {
      const fs = nodeFs as unknown as {
        readdirSync(p: string, o: { withFileTypes: true }): {
          name: string;
          isDirectory(): boolean;
        }[];
      };
      for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
        const full = nodePath.join(dir, entry.name);
        if (entry.isDirectory()) walk(full);
        else if (entry.name.endsWith(".css") && full !== nodePath.join(SRC, "components", "PageHeader.css"))
          stylesheets.push(full);
      }
    };
    walk(SRC);
    const offenders = stylesheets.filter((file) =>
      /\.page-header[a-z-]*\s*[,{]/.test(nodeFs.readFileSync(file, "utf8")),
    );
    expect(offenders).toEqual([]);
  });
});

describe("DEF-979 — the bills search box names the fields it really matches", () => {
  it("names the four `searchFields` and no fifth", () => {
    const config = billsTableConfig(t, billsCells(t, (p) => p, "UTC", "MM/DD/YYYY"), "all");
    expect(config.searchPlaceholder).toBe(BILLS_SEARCH_PLACEHOLDER_KEY);
    // ⚠ **`address` JOINED THE CONTRACT ON 2026-09-09 (`CR-089` wave K,
    // `PUJ-53`), AND THIS CASE IS WHAT CAUGHT THE COPY MOVING.** The wave
    // reworded the prompt in eleven catalogues and this assertion went RED in
    // the same run, naming the exact file whose declaration had not moved with
    // it. That is the check doing its job, so it is AMENDED rather than
    // loosened: the list below is still the whole promise, and a fifth word
    // still fails.
    expect(config.searchFields).toEqual([
      "invoice_no",
      "account_no",
      "customer_name",
      "address",
    ]);

    const prompt = t(BILLS_SEARCH_PLACEHOLDER_KEY);
    // The key must exist in the catalogue — `DataTable` calls `t()` with no
    // `defaultValue`, so a missing key renders its own NAME into the box, in
    // front of the user, in every locale at once.
    expect(prompt).not.toBe(BILLS_SEARCH_PLACEHOLDER_KEY);
    expect(prompt).not.toBe(t("table.search.placeholder"));
    // …and it must NAME the address, because the query really searches one now.
    // Withholding the word is the mirror of DEF-950 and costs more: a live leg
    // nobody is told about is a leg nobody uses.
    expect(prompt.toLowerCase()).toContain("address");

    // ⚠ **AND IT MUST NOT PROMISE A FIFTH FIELD.** DEF-950 is the sibling
    // failure on the reads list: a prompt named an address the query could not
    // search, which sends a clerk to type something that will never match and
    // then to conclude the bill is not there — worse than the generic prompt it
    // replaced. `address` has left this list because the predicate now performs
    // it; every remaining word is still one the box may not offer.
    for (const forbidden of ["meter", "premise", "unit", "email", "phone"]) {
      expect(prompt.toLowerCase()).not.toContain(forbidden);
    }
  });
});

describe("CR-043 finding 10 — the two 'arrives later' panels are gone and their absences are filed", () => {
  it("their eleven-catalogue copy is retired, so nothing can render it again", () => {
    // A catalogue entry BEATS a code `defaultValue`, so a key left behind is a
    // sentence one careless call site can put back on the screen.
    for (const key of [
      "billing.bills.awaits.filters",
      "billing.bills.awaits.filtersTitle",
      "billing.bills.awaits.export",
      "billing.bills.awaits.exportTitle",
    ]) {
      expect(catalog[key]).toBeUndefined();
    }
  });

  it("the register carries what the screen no longer says (G38's baseline drop is a MOVE)", () => {
    // ⚠ G38 CANNOT TELL A PAID DEBT FROM A DELETED NOTICE — its baseline fell
    // 71 → 69 and would have scored building the two features identically. The
    // two defect rows ARE the fact now, so this test fails if either is dropped.
    const register = nodeFs.readFileSync(
      nodePath.join(REPO, "12-governance", "10-defect-log.csv"),
      "utf8",
    );
    expect(register).toContain("DEF-1062");
    expect(register).toContain("DEF-1063");
  });
});
