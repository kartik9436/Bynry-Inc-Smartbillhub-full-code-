// ── Trace ────────────────────────────────────────────────────────────────
// Defects:  DEF-CWP-10548 (F-03) · DEF-CWP-10551 (F-22)
// The two SOURCE guards of lane A11Y-BC, in a node test because they read
// files (the rendered half is in `a11y.dom.test.tsx`):
//   * required is never an asterisk only — the asterisk is drawn by
//     `FormField`, which marks its box; any other file drawing one must mark
//     its own box `aria-required`;
//   * a disabled button's reason is never a `title` tooltip only — every
//     hand-built `disabled … title=` also names a reason line.
// ─────────────────────────────────────────────────────────────────────────
import { describe, expect, it } from "vitest";

// Node's own modules, reached the way `pageHeadCensus.test.ts` does:
// `@types/node` is deliberately not installed, so a plain `import … from
// "node:fs"` fails `tsc`.
const nodeFs = (await import(/* @vite-ignore */ ["node", "fs"].join(":"))) as {
  readFileSync(p: string, enc: string): string;
  readdirSync(p: string): string[];
  statSync(p: string): { isDirectory(): boolean };
};
const nodePath = (await import(/* @vite-ignore */ ["node", "path"].join(":"))) as {
  join(...p: string[]): string;
};
const { readFileSync, readdirSync, statSync } = nodeFs;
const { join } = nodePath;

function portalSources(dir: string): string[] {
  const out: string[] = [];
  for (const name of readdirSync(dir)) {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) out.push(...portalSources(path));
    else if (name.endsWith(".tsx") && !name.includes(".test.")) out.push(path);
  }
  return out;
}

const PORTAL = new URL("..", import.meta.url).pathname.replace(/\/$/, "");


describe("guard: required is never an asterisk only (F-03)", () => {
  /**
   * The asterisk is drawn in exactly ONE place — `FormField` — and that same
   * component now publishes `required` to its box. A second place that draws
   * `*` beside a label would be required to the eye and silent to a screen
   * reader, which is the finding. `ApplicationCustomFields` draws its own
   * label and is checked to set `aria-required` itself.
   */
  it("no portal file draws a required asterisk except FormField (or marks its box itself)", () => {
    const offenders: string[] = [];
    for (const file of portalSources(PORTAL)) {
      const text = readFileSync(file, "utf8");
      const draws = /aria-hidden="true">\s*\{?\s*["']?\s*\*/.test(text) || /\{" \*"\}/.test(text);
      if (!draws) continue;
      if (file.endsWith(join("components", "primitives.tsx"))) continue;
      if (/aria-required=\{/.test(text)) continue;
      offenders.push(file.slice(PORTAL.length + 1));
    }
    expect(offenders).toEqual([]);
  });

});

describe("guard: a disabled button's reason is never a tooltip only (F-22)", () => {
  it("every hand-built `disabled … title=` in the portal also names a reason line", () => {
    const offenders: string[] = [];
    for (const file of portalSources(PORTAL)) {
      const text = readFileSync(file, "utf8");
      // Each JSX opening tag of a Button/button that is disabled AND titled.
      for (const tag of text.match(/<(?:Button|button)\b[^>]*?>/gs) ?? []) {
        if (!/\bdisabled\b/.test(tag) || !/\btitle=/.test(tag)) continue;
        if (/aria-describedby=/.test(tag)) continue;
        offenders.push(`${file.slice(PORTAL.length + 1)}: ${tag.replace(/\s+/g, " ").slice(0, 80)}`);
      }
    }
    expect(offenders).toEqual([]);
  });
});
