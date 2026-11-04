/**
 * CR-018 Phase 0 — the theme and `tokens.css` may not drift apart.
 *
 * WHY THIS FILE EXISTS
 * --------------------
 * For as long as both sheets exist, every value in `tailwind.css`'s `@theme`
 * block is a SECOND COPY of a value in `tokens.css`. Hard-won law 5 says one
 * source; this is a deliberate exception with an end date (Phase 3 deletes
 * `tokens.css` and `@theme` becomes the only declaration), so it is gated
 * rather than trusted. Retune a token in one file and this goes RED.
 *
 * It is a SOURCE check and it is not the whole proof. `tailwind-specimen/`
 * renders all 76 in a real browser and compares computed styles, which is the
 * thing that actually answers "did the value survive" (hard-won law 1: a
 * config claiming a value is not the value). This file is the half that runs
 * in `npm test`, with no browser and no build step.
 *
 * ⚠ It is deliberately NOT a `10-scripts/gates/` gate. The next free gate
 * number is contested — another lane is registering `g34_rls_policy_guard`
 * for DEF-333 — and editing the shared `run_gates.py` to claim a number is how
 * two lanes collide in one working tree (hard-won law 11). `npm test` already
 * runs, so the assertion lands where it will actually be executed.
 *
 * PROVED RED BEFORE TRUSTED GREEN (hard-won law 7): five sabotages —
 * a colour changed by one hex digit, `--text-btn` 14→15px, `--radius-2xl`
 * 0→2px, `--text-table` hard-coded instead of derived, and the `--font-*`
 * clear deleted — produced five distinct failures naming the exact drift.
 */
import { describe, expect, it } from "vitest";

// `../main.tsx?raw` is Vite's own source read, typed by `vite/client` — the
// convention the existing source-reading tests use (ShellWithSession.test.tsx,
// ChargesTaxes.test.tsx). It works for .tsx and NOT for .css: Vitest stubs CSS
// modules to the empty string by default, and the stub wins over `?raw`, so
// `./tokens.css?raw` imports as "" — measured, not assumed, and it fails
// silently rather than erroring, which is why it is written down here.
import mainSource from "../main.tsx?raw";

// So the two stylesheets are read at runtime instead. The app carries no
// `@types/node` on purpose (adding it would put Node's globals over 127
// components — `setTimeout` returning NodeJS.Timeout rather than number, and
// the rest), so a static `import { readFileSync } from "node:fs"` fails
// `tsc --noEmit` and breaks `npm run build`. A dynamic import of a
// non-literal specifier is resolved by the runtime and not by the compiler,
// which is exactly the split that is wanted here: real Node under Vitest, no
// Node types leaking into the app.
const nodeFs = (await import(/* @vite-ignore */ ["node", "fs"].join(":"))) as {
  readFileSync(path: string, encoding: string): string;
};
const nodeUrl = (await import(/* @vite-ignore */ ["node", "url"].join(":"))) as {
  fileURLToPath(url: URL): string;
};
const read = (name: string) => nodeFs.readFileSync(nodeUrl.fileURLToPath(new URL(name, import.meta.url)), "utf8");
const tokensCss = read("./tokens.css");
const themeCss = read("./tailwind.css");
const globalSource = read("./global.css");

const stripComments = (css: string) => css.replace(/\/\*[\s\S]*?\*\//g, "");
const norm = (v: string) => v.trim().replace(/\s+/g, " ");

/** every `--name: value;` in a chunk of CSS, comments removed */
function declarations(css: string): Map<string, string> {
  const out = new Map<string, string>();
  const re = /(--[a-z0-9-]+)\s*:\s*([^;]+);/g;
  let m: RegExpExecArray | null;
  while ((m = re.exec(stripComments(css))) !== null) out.set(m[1], norm(m[2]));
  return out;
}

const tokens = declarations(tokensCss);

const themeSource = (() => {
  const css = stripComments(themeCss);
  const start = css.indexOf("@theme");
  expect(start, "tailwind.css must declare an @theme block").toBeGreaterThan(-1);
  let depth = 0;
  let i = css.indexOf("{", start);
  const from = i + 1;
  for (; i < css.length; i++) {
    if (css[i] === "{") depth++;
    if (css[i] === "}") {
      depth--;
      if (depth === 0) break;
    }
  }
  return css.slice(from, i);
})();
const theme = declarations(themeSource);

describe("CR-018 · the Tailwind theme against tokens.css", () => {
  it("tokens.css declares exactly the tokens this theme was derived from", () => {
    // A token added without crossing it is a screen that drifts in Phase 3.
    // 76 at Phase 0. 82 since the type scale was ruled (decision log
    // 2026-08-19, OQ-275/276, commit 4b6baa6): `--text-display` is new,
    // `--text-xs/sm/base/md` are the four small steps the ruling names,
    // `--text-h6` is gone — it was a second name for `--text-base`'s 13px —
    // and `--text-btn` / `--text-btn-sm`, which the `@theme` block has carried
    // since Phase 0, are declared in tokens.css too so a STYLESHEET can write
    // B14 rule 5's ratified figures by name instead of as the literal rule 5
    // itself forbids.
    // 87 since OQ-278 was ruled (decision log 2026-08-19, commit 6a13828):
    // `--text-metric-sm` / `--text-metric` / `--text-metric-lg` are the three
    // ruled metric steps and `--line-height-metric-sm` / `--line-height-metric`
    // are their leadings, which live here rather than only in @theme because a
    // STYLESHEET has to be able to write them by name.
    // 91 since OQ-273 was ruled (decision log 2026-08-20, commit 4e78da4):
    // `--color-service-storm-water`, `--color-service-solar`,
    // `--color-service-thermal-heat` and `--color-service-battery` are the four
    // of our TEN services that had no colour. A ten-service platform declaring
    // six colours meant four dots rendered as the SAME neutral grey.
    // 93 since DEF-722 was ruled (decision log 2026-08-26, PO verbatim: *"have
    // differnt color for diff pill - you can define colors - recommendation:
    // A"*): `--color-info-100` / `--color-info-700` are the FIFTH semantic
    // status tone. BR-CUS-055 seeds six account statuses and StatusPill had
    // four tones, so two statuses shared a colour; five of the six are servable
    // from tokens that already existed and `Vacation hold` — a pause the
    // customer asked for — is not, because every other non-green ramp here is a
    // red-orange. There is no `--color-info-500`: nothing renders one, and the
    // count above is exactly why a decorative third step would have to be
    // justified on this line.
    // 94 since CR-063 (2026-09-02): `--color-service-fire` is the ELEVENTH
    // service's colour. Fire's obvious hue — red — was taken twice over
    // (#ec3013 is electric's dot AND the brand accent), so it takes a deep
    // oxide red separated by VALUE and, because value is what a 6px dot loses
    // first, the HOLLOW dot as well. That is OQ-273's answer applied as the
    // GENERAL rule it was ratified as, and storm water is the precedent.
    // 95 since B14 rule 39 was ratified (2026-09-11, CR-085): `--space-5: 20px`
    // is the ONE step of the rule's seven that this scale did not declare —
    // the rule's *step side padding, KPI cell side padding*. The amendment
    // ruled the same day is what decides it is `--space-5` and not a new
    // `--sp-5`: the family that exists gets the missing step, because two
    // spacing scales in one product is the second copy hard-won law 5 exists
    // to prevent. ⚠ THIS NUMBER MOVED BECAUSE A TOKEN WAS ADDED, not to make
    // a check pass — the seven steps are asserted by name in
    // `portal/components/spacingAnchors.test.ts`, so a lane deleting the token
    // and decrementing this line goes red there instead.
    // 99 since portal a11y Group A (decision log 2026-10-23, F-09 and ruling
    // 3(a)): `--color-field-border` is the NEW border of an input, select or
    // textarea (#8c8888, confirmed by the PO/QA), and `--color-on-accent`,
    // `-600`, `-700` are the text on an accent fill at rest, hover and press —
    // `--color-bg` on staff screens, chosen by contrast inside the portal frame.
    // `tokenContrast.test.ts` measures them; this line only counts them.
    // 101 since Group A's eight decisions (decision log 2026-10-23, "how they
    // are built"): `--color-field-fill` (#ffffff, a staff field's fill,
    // decision 6) and `--color-accent-text` (brand-coloured text, set by the
    // portal frame, decision 2).
    expect(tokens.size).toBe(101);
  });

  it("all ELEVEN services have a colour, and no service has two", () => {
    // BR-RAT-024 CONFIRMED-AS-AMENDED (2026-09-02) — the canonical ELEVEN and
    // their SEED ORDER live in `06-backend/apps/tenancy/migrations/` :
    // `0001_initial.py` (SERVICE_SEED, the first ten) and
    // `0033_cr063_fire_service.py` (FIRE_SEED, the eleventh).
    // OQ-273 RULED 2026-08-20 (decision log, commit 4e78da4). Written as a
    // literal map rather than a loop so that a retune, a rename or a fifth
    // "bundle" colour is a visible diff on THESE lines — the proposal this
    // ruling answered tried to rename broadband and mint a second one.
    const services = Object.fromEntries(
      [...tokens].filter(([k]) => k.startsWith("--color-service-")),
    );
    expect(services).toEqual({
      "--color-service-electric": "#ec3013",
      "--color-service-water": "#1e6b8f",
      "--color-service-gas": "#c47a1d",
      "--color-service-sewer": "#5a5555",
      "--color-service-trash": "#3a6b3d",
      "--color-service-storm-water": "#2f4a7a",
      "--color-service-solar": "#7a9a2a",
      "--color-service-broadband": "#6b3d8a",
      "--color-service-thermal-heat": "#a8256b",
      "--color-service-battery": "#3aa39b",
      // CR-063 — fire. NOT a second bright red: #ec3013 is electric's dot and
      // the brand accent, so this one separates by VALUE and takes the hollow
      // dot for the separation a 6px disc cannot carry.
      "--color-service-fire": "#8f1f14",
    });
    // No service wears two colours, and none of the eleven is the brand accent
    // twice over: electric IS #ec3013 by design (r9), and nothing else may be.
    const hexes = Object.values(services);
    expect(new Set(hexes).size, "two services share one colour").toBe(11);
    expect(hexes.filter((h) => h === "#ec3013"), "only electric is the accent").toEqual([
      "#ec3013",
    ]);
  });

  it("the ruled type scale is exactly what tokens.css declares — every step, no strays", () => {
    // The whole value of a scale is that a size can only be one of these. A
    // sixth small step or a retuned h2 has to be a visible diff on THIS line,
    // never a number that appeared in a stylesheet and was never ruled.
    // Decision log 2026-08-19, "THE TYPE SCALE IS RULED — OQ-275/276 CLOSED".
    const scale = Object.fromEntries(
      [...tokens].filter(([k]) => /^--text-(display|h[1-6]|xs|sm|base|md|body)$/.test(k)),
    );
    expect(scale).toEqual({
      "--text-display": "56px",
      "--text-h1": "40px",
      "--text-h2": "32px",
      "--text-h3": "25px",
      "--text-h4": "20px",
      "--text-h5": "16px",
      "--text-xs": "11px",
      "--text-sm": "12px",
      "--text-base": "13px",
      "--text-md": "14px",
      "--text-body": "15px",
    });
  });

  it("the METRIC tier is exactly three steps, and a metric is not a heading", () => {
    // Decision log 2026-08-19, "OQ-278 RULED — three metric tokens, and a
    // metric is not a heading" (commit 6a13828). A fourth metric step, or one
    // of these retuned, has to be a visible diff on THIS line.
    const metric = Object.fromEntries([...tokens].filter(([k]) => /^--text-metric/.test(k)));
    expect(metric).toEqual({
      "--text-metric-sm": "22px",
      "--text-metric": "26px",
      "--text-metric-lg": "32px",
    });

    // ⚠ THE ASYMMETRY IS THE RULING, SO IT IS ASSERTED. Heading steps carry a
    // weight and a tracking modifier; metric steps carry a LEADING ONLY,
    // because every metric site sets its own weight (800 on the KPI value and
    // the "Today" total, 600 on a net-pair figure) and a modifier here would
    // overwrite it the moment Phase 3 turns the site into a utility.
    for (const step of ["--text-metric-sm", "--text-metric", "--text-metric-lg"]) {
      expect(theme.has(`${step}--line-height`)).toBe(true);
      expect(theme.has(`${step}--font-weight`)).toBe(false);
      expect(theme.has(`${step}--letter-spacing`)).toBe(false);
    }
    // …and the KPI role's default really is 26px, which is the figure the PO
    // ruled and the pixel the dashboard moved to from 30px.
    expect(theme.get("--text-metric")).toBe("26px");
  });

  it("every token in tokens.css crosses into @theme with an identical value", () => {
    const missing: string[] = [];
    const drifted: string[] = [];
    for (const [name, value] of tokens) {
      if (!theme.has(name)) missing.push(name);
      else if (theme.get(name) !== value) drifted.push(`${name}: tokens=${value} theme=${theme.get(name)}`);
    }
    expect({ missing, drifted }).toEqual({ missing: [], drifted: [] });
  });

  it("the six namespace-renamed tokens DERIVE from ours rather than repeating the literal", () => {
    // One literal per number — hard-won law 5. If any of these ever hard-codes
    // a value, the drift test above can no longer see it.
    expect(theme.get("--leading-body")).toBe("var(--line-height-body)");
    expect(theme.get("--leading-heading")).toBe("var(--line-height-heading)");
    expect(theme.get("--tracking-heading")).toBe("var(--letter-spacing-heading)");
    expect(theme.get("--text-table")).toBe("var(--table-font-size)");
    expect(theme.get("--text-table-header")).toBe("var(--table-header-font-size)");
    expect(theme.get("--container-measure")).toBe("var(--desc-measure)");
    expect(theme.get("--leading-metric-sm")).toBe("var(--line-height-metric-sm)");
    expect(theme.get("--leading-metric")).toBe("var(--line-height-metric)");
  });

  it("B14's ratified figures are the ones in the theme", () => {
    // rule 5 — two button sizes only, default and small (12px). CR-016's
    // conformance register locks the pair at ["12px","14px"].
    expect(theme.get("--text-btn")).toBe("14px");
    expect(theme.get("--text-btn-sm")).toBe("12px");
    // rule 20 — one table type size, and its header at rule 5's small tier.
    expect(theme.get("--table-font-size")).toBe("13.5px");
    expect(theme.get("--table-header-font-size")).toBe("12px");
    // rule 18 as amended — PO 2026-08-16, "make it 80%", "across the app".
    expect(theme.get("--desc-measure")).toBe("80%");
    // The heading weight has no utility of its own (font-heading is taken by
    // the family), so it must equal Tailwind's own --font-weight-extrabold,
    // which is what Phase 3's markup will actually write.
    expect(theme.get("--font-heading-weight")).toBe("800");
  });

  it("Modernist is square — every radius key is 0, and there are no gaps", () => {
    const keys = [...theme.keys()].filter((k) => /^--radius-/.test(k)).sort();
    expect(keys).toEqual([
      "--radius-2xl",
      "--radius-3xl",
      "--radius-4xl",
      "--radius-lg",
      "--radius-md",
      "--radius-none",
      "--radius-sm",
      "--radius-xl",
      "--radius-xs",
    ]);
    for (const k of keys) expect(theme.get(k), k).toBe("0px");
  });

  it("Tailwind's own defaults are cleared before ours are declared", () => {
    // Route B was bought to make a wrong style unwritable. That only holds if
    // bg-red-500 / text-lg / shadow-2xl / font-sans do not exist at all.
    for (const ns of ["--color-*", "--text-*", "--radius-*", "--shadow-*", "--font-*"]) {
      expect(themeSource, `${ns} must be cleared`).toContain(`${ns}: initial;`);
    }
  });

  // ── CR-018 PHASE 1 REPLACED THE PHASE 0 ASSERTION HERE ──────────────────
  // Phase 0 asserted `mainSource` does NOT contain "tailwind" — "the theme
  // reaches no screen". Phase 1's whole job is to break that, so the assertion
  // is REPLACED rather than deleted: an assertion whose premise expired is
  // removed and its successor written in the same commit, or the guard silently
  // stops guarding (the failure G26/G27/DEF-323 are the record of).
  //
  // The three facts that replace it are the three ways Phase 1's import can be
  // wrong, and every one of them is invisible to tsc, eslint and every existing
  // gate — they are only visible in a browser, which is hard-won law 6.

  it("Phase 1 imports the theme into the app, and does it from main.tsx", () => {
    expect(mainSource).toContain('import "@/styles/tailwind.css";');
  });

  it("PREFLIGHT IS IMPORTED, INTO layer(base) — and the layer is the whole point", () => {
    // ⚠ THIS ASSERTION IS THE INVERSE OF THE ONE IT REPLACES, and the swap was
    // made in the same commit as the change (CR-018 Phase 5, 2026-08-20). Until
    // then it asserted Preflight was NOT imported, because it was a
    // whole-product change nobody had measured. It is measured now — 7,413
    // elements on 20 screens, before and after — and the PO ruled on the result:
    // "Im okay with this one also ; so we dont hav eto worry pixel perfect".
    //
    // An assertion whose premise has expired is REPLACED, never deleted, or the
    // guard silently stops guarding. What it guards now is the three things
    // that make Preflight survivable here.
    const importLines = stripComments(themeCss)
      .split("\n")
      .filter((line) => line.trim().startsWith("@import"))
      .join("\n");

    // 1 · it is imported at all
    expect(importLines).toContain("preflight");

    // 2 · ⚠ INTO layer(base), WHICH IS WHAT KEEPS 40 LEGACY STYLESHEETS WINNING.
    //     The cascade puts unlayered author CSS above every layer, so the order
    //     is: UA styles < layer(base) = Preflight < the legacy sheets. Import it
    //     unlayered and Preflight would beat every one of them — the same
    //     mechanism, pointed the other way, that the utilities import below
    //     depends on. This is one word in one line and it decides the product.
    expect(importLines).toMatch(/@import\s+"tailwindcss\/preflight\.css"\s+layer\(base\);/);

    // 3 · not the bundled shorthand, which would bring Preflight in UNLAYERED
    expect(importLines).not.toMatch(/@import\s+"tailwindcss"\s*;/);
    expect(importLines).toContain('@import "tailwindcss/theme.css" layer(theme);');
  });

  it("global.css puts back the two things Preflight took that would read as BROKEN", () => {
    // Measured before/after, 7,413 elements: four things moved that a person
    // could see. Two are differences and are accepted; two are defects.
    //
    //   h1 30px -> 15px   a heading at body size is not a heading
    //   p  margin -> 0    84 paragraphs running their text together
    //
    // ⚠ AND THE HEADINGS TAKE THE RULED SCALE RATHER THAN THE BROWSER'S 2em.
    // OQ-275 ruled h1 40 / h2 32 / h3 25 / h4 20 / h5 16 on 2026-08-19 and those
    // tokens had never been rendered by anything. If this assertion fails, the
    // headings have gone back to whatever the browser felt like.
    const css = stripComments(globalSource);
    for (const [tag, token] of [["h1", "--text-h1"], ["h2", "--text-h2"], ["h3", "--text-h3"],
                                ["h4", "--text-h4"], ["h5", "--text-h5"]] as const) {
      const rule = new RegExp(`(^|\\})\\s*${tag}\\s*\\{[^}]*font-size:\\s*var\\(${token}\\)`, "m");
      expect(rule.test(css), `global.css no longer sizes ${tag} from ${token}`).toBe(true);
    }
    expect(/(^|\})\s*p\s*\{[^}]*margin-block:\s*1em/m.test(css),
      "global.css no longer restores the paragraph rhythm Preflight removes").toBe(true);
  });

  it("the utilities are imported UNLAYERED, and main.tsx imports them LAST", () => {
    // A cascade layer always loses to unlayered CSS whatever the specificity,
    // and 40 unlayered legacy stylesheets are still in the bundle — so a
    // layered `p-4` loses to `.card { padding: 28px }` and the migrated card
    // silently grows 12px on every side. Unlayered, both are 0,1,0 and source
    // order decides, which is why the import sits BELOW `import App`.
    expect(themeCss).toMatch(/@import "tailwindcss\/utilities\.css"(?: source\(none\))?;/);
    expect(stripComments(themeCss)).not.toContain('utilities.css" layer(utilities)');
    const app = mainSource.indexOf('from "@/App"');
    const twind = mainSource.indexOf('"@/styles/tailwind.css"');
    expect(app, "main.tsx no longer imports App by that name").toBeGreaterThan(-1);
    expect(twind, "main.tsx no longer imports the theme").toBeGreaterThan(-1);
    expect(twind, "the theme import must come AFTER @/App or it loses the cascade").toBeGreaterThan(
      app,
    );
  });
});
