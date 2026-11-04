// CR-169-BRC10 §2 row 1 — `src/analytics/` is the ONLY importer of posthog-js.
// A screen calls `track()`; it never reaches PostHog itself, so the allow-list
// in `events.ts` cannot be stepped around. Written red-first: it was proved red
// by adding `import posthog from "posthog-js"` to a screen file.
import { describe, expect, it } from "vitest";

// `src/`'s tsconfig carries no @types/node, so a bare `node:fs` import fails
// `tsc` — the repo's pattern (`runbookKitClasses.test.ts`) is a typed dynamic one.
const { readFileSync, readdirSync, statSync } = (await import(/* @vite-ignore */ ["node", "fs"].join(":"))) as {
  readFileSync(p: string, enc: string): string;
  readdirSync(p: string): string[];
  statSync(p: string): { isDirectory(): boolean };
};
const { join, relative } = (await import(/* @vite-ignore */ ["node", "path"].join(":"))) as {
  join(...p: string[]): string;
  relative(from: string, to: string): string;
};
const { fileURLToPath } = (await import(/* @vite-ignore */ ["node", "url"].join(":"))) as {
  fileURLToPath(url: URL | string): string;
};

const SRC = fileURLToPath(new URL("..", import.meta.url));
const IMPORT = /(?:from\s*|import\s*\(\s*|import\s+|require\s*\(\s*)["']posthog-js(?:\/[^"']*)?["']/;

function walk(dir: string, out: string[]): string[] {
  for (const name of readdirSync(dir)) {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) {
      walk(path, out);
    } else if (/\.(?:ts|tsx|js|jsx|mjs)$/.test(name)) {
      out.push(path);
    }
  }
  return out;
}

function offenders(root: string): string[] {
  return walk(root, [])
    .map((path) => relative(root, path))
    .filter((path) => !path.startsWith("analytics/"))
    .filter((path) => IMPORT.test(readFileSync(join(root, path), "utf8")));
}

describe("posthog-js import gate (CR-169-BRC10)", () => {
  it("scans a real number of files, not zero (law 7)", () => {
    expect(walk(SRC, []).length).toBeGreaterThan(500);
  });

  it("finds no file outside src/analytics/ importing posthog-js", () => {
    expect(offenders(SRC)).toEqual([]);
  });

  it("the pattern catches the three spellings of an import", () => {
    expect(IMPORT.test(`import posthog from "posthog-js";`)).toBe(true);
    expect(IMPORT.test(`const m = await import("posthog-js/dist/module.full.no-external");`)).toBe(true);
    expect(IMPORT.test(`import "posthog-js/rrweb";`)).toBe(true);
    expect(IMPORT.test(`import { track } from "@/analytics";`)).toBe(false);
  });
});
