/**
 * Group A (F-01, F-09) — every text token and the field border, measured
 * against every background token, from the stylesheet itself.
 *
 * Decision log 2026-10-23, confirmed by the PO/QA (*"this is correct"*):
 *   grey-600  #7d7979 → #6b6767   5.58 on white · 5.00 on #f3f2f2
 *   field border (NEW) #8c8888    3.50 on white · 3.14 on #f3f2f2
 *   grey-500 (#9b9797) and the divider/card line (#d7d3d3) unchanged.
 *
 * Text fails below 4.5:1; the field border fails below 3:1 against the two
 * grounds a field sits on (its own white fill, and the page). A token edited
 * in `tokens.css` turns this red, naming the pair and the ratio.
 */
import { describe, expect, it } from "vitest";
import { AA_NON_TEXT, AA_TEXT, contrastRatio } from "../lib/contrast";

const nodeFs = (await import(/* @vite-ignore */ ["node", "fs"].join(":"))) as {
  readFileSync(path: string, encoding: string): string;
};
const nodeUrl = (await import(/* @vite-ignore */ ["node", "url"].join(":"))) as {
  fileURLToPath(url: URL): string;
};
const read = (name: string) => nodeFs.readFileSync(nodeUrl.fileURLToPath(new URL(name, import.meta.url)), "utf8");

function declarations(css: string): Map<string, string> {
  const out = new Map<string, string>();
  const re = /(--[a-z0-9-]+)\s*:\s*([^;]+);/g;
  const stripped = css.replace(/\/\*[\s\S]*?\*\//g, "");
  let m: RegExpExecArray | null;
  while ((m = re.exec(stripped)) !== null) out.set(m[1], m[2].trim());
  return out;
}

const tokens = declarations(read("./tokens.css"));
const value = (name: string): string => {
  const v = tokens.get(name);
  expect(v, `${name} is not declared in tokens.css`).toBeDefined();
  return v as string;
};

/** Every ground text is written on. `white` is the portal's surface
 *  (GuestFrame.tsx `PORTAL_SURFACE`) and every field's fill. */
const BACKGROUNDS: Record<string, string> = {
  white: "#ffffff",
  "--color-bg": value("--color-bg"),
  "--color-surface": value("--color-surface"),
  "--color-neutral-100": value("--color-neutral-100"),
  "--color-neutral-200": value("--color-neutral-200"),
};

/** The text tokens. grey-500 is NOT one: it stays for dividers, decoration
 *  and disabled controls, and every use of it as text moved to grey-600. */
const TEXT = ["--color-text", "--color-neutral-600", "--color-neutral-700", "--color-neutral-800", "--color-neutral-900"];

describe("Group A · token contrast (F-01, F-09)", () => {
  it("the confirmed values are the ones in the stylesheet", () => {
    expect(value("--color-neutral-600").toLowerCase()).toBe("#6b6767");
    expect(value("--color-field-border").toLowerCase()).toBe("#8c8888");
    expect(value("--color-neutral-500").toLowerCase()).toBe("#9b9797");
    expect(value("--color-neutral-300").toLowerCase()).toBe("#d7d3d3");
  });

  for (const text of TEXT) {
    for (const [bgName, bg] of Object.entries(BACKGROUNDS)) {
      it(`${text} reads at least 4.5:1 on ${bgName}`, () => {
        const ratio = contrastRatio(value(text), bg) as number;
        expect(ratio, `${text} ${value(text)} on ${bgName} ${bg} is ${ratio.toFixed(2)}:1`).toBeGreaterThanOrEqual(AA_TEXT);
      });
    }
  }

  for (const bgName of ["white", "--color-bg"]) {
    it(`--color-field-border reads at least 3:1 on ${bgName}`, () => {
      const ratio = contrastRatio(value("--color-field-border"), BACKGROUNDS[bgName]) as number;
      expect(ratio, `field border on ${bgName} is ${ratio.toFixed(2)}:1`).toBeGreaterThanOrEqual(AA_NON_TEXT);
    });
  }

  it("the worked figures the PO was shown", () => {
    const r = (a: string, b: string) => Math.round((contrastRatio(a, b) as number) * 100) / 100;
    expect(r("#6b6767", "#ffffff")).toBe(5.58);
    expect(r("#6b6767", "#f3f2f2")).toBe(5.0);
    expect(r("#6b6767", "#eae7e7")).toBe(4.54);
    expect(r("#8c8888", "#ffffff")).toBe(3.5);
    expect(r("#8c8888", "#f3f2f2")).toBe(3.14);
    expect(r("#7d7979", "#ffffff")).toBe(4.3);
  });
});

// ── grey-500 is never TEXT in the portal or the kit it mounts ──────────────
// Ruling (Group A, 2026-10-23): every use of grey-500 AS TEXT moves to the new
// grey-600; the token itself stays for dividers, decoration and disabled
// controls. The only text left on it is inside a DISABLED control
// (aria-disabled), which WCAG 1.4.3 exempts — named here one by one.
const SOURCES = import.meta.glob(
  [
    "../portal/**/*.tsx",
    "../portal/**/*.ts",
    "../components/**/*.tsx",
    "../components/**/*.ts",
    "../features/**/*.tsx",
    "../features/**/*.ts",
    "!../**/*.test.ts",
    "!../**/*.test.tsx",
  ],
  { query: "?raw", eager: true, import: "default" },
) as Record<string, string>;

/** file → how many disabled-control uses it may keep. */
const DISABLED_ONLY: Record<string, number> = {
  // ErrandCard's `unavailable` card (aria-disabled): its title and its line.
  // PhotoPicker (aria-disabled): the held photo box.
  "../portal/components/primitives.tsx": 3,
};

// ── Group A, the eight decisions (decision log 2026-10-23, PO/QA *"agreed to
// your recommondation"*, and "how they are built") ───────────────────────────
describe("Group A · the eight decisions, held on the stylesheet", () => {
  it("decision 7: a staff primary button's ink passes on every step of the stock accent", () => {
    // Was --color-bg #f3f2f2 on #ec3013 = 3.76. Now black 5.00, white 4.74 and 7.17.
    for (const [ink, fill] of [
      ["--color-on-accent", "--color-accent"],
      ["--color-on-accent-600", "--color-accent-600"],
      ["--color-on-accent-700", "--color-accent-700"],
    ] as const) {
      const ratio = contrastRatio(value(ink), value(fill)) as number;
      expect(ratio, `${ink} ${value(ink)} on ${fill} ${value(fill)} is ${ratio.toFixed(2)}:1`).toBeGreaterThanOrEqual(AA_TEXT);
    }
    expect(value("--color-on-accent").toLowerCase()).toBe("#000000");
  });

  it("decision 6: a staff field is filled white, so its border reads 3.50 (was 2.89 on #eae9e9)", () => {
    expect(value("--color-field-fill").toLowerCase()).toBe("#ffffff");
    const ratio = contrastRatio(value("--color-field-border"), value("--color-field-fill")) as number;
    expect(Math.round(ratio * 100) / 100).toBe(3.5);
    // Every shared field rule paints that fill, not --color-surface.
    for (const [file, selector] of [
      ["../components/FormModal.css", ".input {"],
      ["../components/FormModal.css", ".view textarea {"],
      ["../components/AppShell.css", "border: 1px solid var(--color-field-border)"],
      ["../components/DataTable.css", ".table-pager-size select {"],
    ] as const) {
      const css = read(file);
      const at = css.indexOf(selector);
      expect(at, `${selector} in ${file}`).toBeGreaterThan(-1);
      const block = css.slice(css.lastIndexOf("{", at + selector.length), css.indexOf("}", at));
      expect(block, `${file} ${selector}`).toContain("var(--color-field-fill)");
      expect(block, `${file} ${selector}`).not.toContain("var(--color-surface)");
    }
  });

  it("decision 2: outside the portal frame, brand text is the accent itself (staff unchanged)", () => {
    expect(value("--color-accent-text")).toBe("var(--color-accent)");
  });
});

/** The portal and the whole shared kit it renders from. The kit is scanned
 *  whole: outside the portal frame `--color-accent-text` IS the accent, so a
 *  staff screen does not move, and a kit piece the portal starts rendering
 *  later (the page-header kicker in `TextBits.tsx` was found this way, by the
 *  browser scan) is already right. */
const PORTAL_TEXT_SOURCES = Object.entries(SOURCES).filter(
  ([file]) => file.startsWith("../portal/") || file.startsWith("../components/"),
);

describe("Group A · brand-coloured text in the portal is the text shade (decision 2)", () => {
  const code = (text: string) =>
    text
      .split("\n")
      .filter((l) => !/^\s*(\*|\/\/|\/\*)/.test(l))
      .join("\n");

  it("scans the portal and says how much it scanned", () => {
    expect(PORTAL_TEXT_SOURCES.length).toBeGreaterThan(100);
  });

  it("no bare text-accent: brand text reads --color-accent-text", () => {
    const offenders = PORTAL_TEXT_SOURCES.filter(([, text]) => /(?<![\w-])text-accent(?![\w-])/.test(code(text))).map(
      ([file]) => file,
    );
    expect(offenders).toEqual([]);
  });

  it("the shared stylesheets' brand text (back link, active tab, failure link, kicker, required *) reads it too", () => {
    for (const [file, selector] of [
      ["../components/PageHeader.css", ".page-header-back {"],
      ["../components/PageHeader.css", ".page-header-tabs a.active {"],
      ["../components/StateFrame.css", ".state-failed-view {"],
      ["../components/FormModal.css", ".modal-kicker {"],
      ["../components/FormModal.css", ".field-required {"],
      ["../components/DataTable.css", ".table-columns-up {"],
      ["../components/DataTable.css", ".table-sort-arrow {"],
    ] as const) {
      const css = read(file);
      const at = css.indexOf(selector);
      expect(at, `${selector} in ${file}`).toBeGreaterThan(-1);
      const block = css.slice(at, css.indexOf("}", at));
      expect(block, `${file} ${selector}`).toMatch(/(?<![\w-])color:\s*var\(--color-accent-text\)/);
    }
  });

  it("decision 4: the future step's circle and last year's bar are the 3:1 grey, not #d7d3d3", () => {
    const primitives = code(SOURCES["../portal/components/primitives.tsx"]);
    expect(primitives).not.toMatch(/bg-neutral-300/);
    expect(primitives).toContain('future: "border-field-border text-field-border"');
    expect(primitives).toContain('"border-accent text-accent-text" : "border-field-border"');
    expect(primitives).toContain('className="h-3 min-w-0 bg-field-border"');
    expect(Math.round((contrastRatio(value("--color-field-border"), "#ffffff") as number) * 100) / 100).toBe(3.5);
  });
});

describe("Group A · grey-500 is not used as text (portal, kit and staff screens)", () => {
  it("scans the portal and the shared kit, and says how much it scanned", () => {
    expect(Object.keys(SOURCES).length).toBeGreaterThan(100);
  });

  it("no text-neutral-500 outside a disabled control", () => {
    const offenders: string[] = [];
    for (const [file, text] of Object.entries(SOURCES)) {
      const code = text
        .split("\n")
        .filter((l) => !/^\s*(\*|\/\/|\/\*)/.test(l))
        .join("\n");
      // `disabled:text-neutral-500` styles a disabled control, which is exempt.
      const n = (code.match(/(?<!disabled:)text-neutral-500/g) ?? []).length;
      if (n > (DISABLED_ONLY[file] ?? 0)) offenders.push(`${file}: ${n}`);
    }
    expect(offenders).toEqual([]);
  });
});
