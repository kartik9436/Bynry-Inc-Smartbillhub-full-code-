// ── Trace ──────────────────────────────────────────────
// Change:  DEF-CUS-5072 + DEF-CUS-5073 — three calls in the ending-service
//          screens built their path WITHOUT a leading slash, so `apiPath` welded
//          the tenant segment onto the first path segment and every one of them
//          404'd on every tenant. DEF-CUS-4010 (2026-09-05) was the same
//          character on the same route, fixed in a sibling function and nowhere
//          else.
// Rules:   CLAUDE.md hard rule 1 (tenant scoping) · hard-won law 7 (prove a
//          guard RED before trusting it green — proved on the three real lines,
//          output quoted below) · law 6 (nothing in this repo reads rendered
//          output; this reads SOURCE, which is the layer the bug lives in)
// Tests:   this file IS the guard.
// ───────────────────────────────────────────────────────
//
// ══════════════════════════════════════════════════════════════════════════
// WHY A ONE-CHARACTER BUG NEEDS ITS OWN CHECK
// ══════════════════════════════════════════════════════════════════════════
// `apiPath(tenant, path)` returns `${API_PREFIX}/${tenant}${path}`. The slash
// between the tenant and the rest of the path is supplied by the CALLER, not by
// `apiPath`. So:
//
//     "/accounts/x/close-out"  ->  /api/brazosbend/accounts/x/close-out   200
//     "accounts/x/close-out"   ->  /api/brazosbendaccounts/x/close-out    404
//
// **Every existing check passes over the second one.**
//
//   · `tsc` — both are `string`. There is nothing to type-check.
//   · eslint — no rule reads the shape of a URL.
//   · every unit test — the screens' suites inject a STUB client and assert on
//     the path string they themselves passed in, so the URL is never built.
//   · the walkthroughs — a 404 on a read whose failure path states an absence
//     honestly looks EXACTLY like a server with nothing to say. That is how
//     DEF-CUS-5073 left a clerk staring at `could not be read` for two weeks
//     while the server was answering with the rule, in plain English, on the
//     other spelling of the same URL.
//
// So this reads the SOURCE. Every literal handed as the path argument of a
// client call must begin with `/`, or begin with an interpolation of a constant
// that itself begins with `/`. That is the whole rule, and it is mechanical.
//
// ══════════════════════════════════════════════════════════════════════════
// PROVED RED FIRST — hard-won law 7, and in the harness that runs it
// ══════════════════════════════════════════════════════════════════════════
// Run against the three lines as they stood at `172373eac`, through `vitest`
// (the harness that runs it), NOT through a hand-written driver:
//
//   FAIL  src/api/apiPathLiteral.guard.test.ts > every client path literal
//         begins with a slash
//   AssertionError: expected '4 client path literals do not begin w…'
//     features/customers/MoveOutWizard.tsx:1166     accounts/${accountId}/close-impact
//     features/customers/MoveOutWizard.tsx:1187     accounts/${accountId}/settle-shortfall
//     features/customers/closeOutEndpoints.ts:137   path() builds "accounts/…"
//     features/customers/closeOutEndpoints.ts:145   path() builds "accounts/…"
//   ...over `checked 598 literal path arguments; 33 call sites build their path
//   elsewhere and are NOT covered by this guard`. Then GREEN on the fixed tree,
//   same command, same scope line with no findings above it.
//
// ⚠ **IT TOOK THREE ATTEMPTS TO GO RED ON ALL FOUR, AND THE TWO IT MISSED ARE
// THE LESSON.** Draft 1 resolved named CONSTANTS only and found two — it
// counted the close-out's arrow-built path in `unresolved` and reported success
// over the worst of the three defects. Draft 2 resolved BUILDERS too and still
// found two, because the name map was TREE-WIDE and `const path` exists in ten
// files: it answered with `work/workEndpoints.ts`'s `"/assets/…"`, which begins
// with a slash, and passed the defective line as clean. **A guard that resolves
// a shadowed name against the wrong file is law 7's *incapable of failing*
// shape wearing a scope bug.** Draft 3 resolves the file's own declarations
// first. Each draft was run before being believed; none was believed because it
// looked right.
//
// Then green on the fixed tree. The failure NAMES the file, the line and the
// literal, because law 7 habit 3 says a check's output must distinguish pass
// from fail TO A READER and "3 !== 0" does not.
//
// ⚠ WHAT WOULD MAKE THIS PASS WRONGLY (law 7 habit 2), stated rather than left
// to be discovered: a path assembled by a helper this file cannot see —
// `client.get(buildPath(id))` — is NOT covered, because the literal is not at
// the call site. That is a declared blind spot and it is COUNTED: the test
// prints how many call sites it could not resolve beside how many it checked,
// so an empty report and a blind one never look alike (the G32 lesson).
import { describe, expect, it } from "vitest";

// ⚠ **A BARE `import … from "node:fs"` PASSES VITEST AND FAILS `tsc --noEmit`**
// — `@types/node` is not in the app's tsconfig, so the module has no
// declarations. `components/buttonKit.test.ts` and `styles/routeBUtilities.test.ts`
// both reach Node through this string-split shim for exactly that reason, and it
// is copied rather than reinvented: the split keeps Vite from pre-bundling and
// keeps `tsc` out of it. Written the obvious way first, and `tsc` said
// `TS2307: Cannot find module 'node:fs'` on two lines — which is the whole
// reason the note above this exists in two other files already.
const nodeFs = (await import(/* @vite-ignore */ ["node", "fs"].join(":"))) as {
  readFileSync(p: string, enc: string): string;
  readdirSync(p: string): string[];
  statSync(p: string): { isDirectory(): boolean };
};
const nodePath = (await import(/* @vite-ignore */ ["node", "path"].join(":"))) as {
  join(...p: string[]): string;
  relative(from: string, to: string): string;
  dirname(p: string): string;
};
const nodeUrl = (await import(/* @vite-ignore */ ["node", "url"].join(":"))) as {
  fileURLToPath(url: URL | string): string;
};

const { readFileSync, readdirSync, statSync } = nodeFs;
const { join, relative } = nodePath;

/** `07-frontend/src` — derived from this file's own location, never a literal. */
const SRC = nodePath.dirname(nodePath.dirname(nodeUrl.fileURLToPath(import.meta.url)));

/** The verbs `ApiClient` publishes. `pollJob` takes a job id, not a path. */
const VERBS = ["request", "get", "post", "put", "patch", "del"];

function walk(dir: string, out: string[] = []): string[] {
  for (const entry of readdirSync(dir)) {
    if (entry === "node_modules" || entry === "__fixtures__") continue;
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) walk(full, out);
    else if (/\.tsx?$/.test(entry)) out.push(full);
  }
  return out;
}

/** Everything in the tree whose name can stand where a path literal stands,
 *  mapped to the first characters of the string it produces. Two shapes, and
 *  the SECOND one is the whole reason this guard exists in its present form:
 *
 *    const ACCOUNTS_PATH = "/accounts";                     — a constant
 *    const path = (id: string) => `/accounts/${id}/close-out`;  — a BUILDER
 *
 *  ⚠ **THE BUILDER SHAPE IS NOT A REFINEMENT, IT IS THE DEFECT.** The first
 *  draft of this guard resolved constants only, and it found two of
 *  `DEF-CUS-5072`'s three lines and **missed `DEF-CUS-5073` entirely** — the
 *  close-out screen, the worst of the three, because its path is assembled by a
 *  one-line arrow and handed over as `path(accountId)`. It counted that line
 *  honestly in its `unresolved` total and reported success over it, which is
 *  law 7's *reporting zero over a scope it silently excludes* with the register
 *  row for the excluded case open on the same screen. A guard written for three
 *  defects that cannot see one of them is not a weaker guard; it is no guard at
 *  all for that one.
 *
 *  Values only ever answer one question here — does it start with a slash — so
 *  a duplicate name across files cannot turn a fail into a pass. */
function constantPrefixes(text: string): Map<string, string> {
  const found = new Map<string, string>();
  //  const NAME [: T] = "…" | `…`
  const literal = /\b(?:const|let)\s+([A-Za-z_$][\w$]*)\s*(?::[^=]+)?=\s*(["'`])([^"'`\n]*)/g;
  //  const NAME = (args) => "…" | `…`      — the path BUILDER
  const builder =
    /\b(?:const|let)\s+([A-Za-z_$][\w$]*)\s*(?::[^=]+)?=\s*\([^)]*\)\s*(?::[^=]+)?=>\s*(["'`])([^"'`\n]*)/g;
  for (const re of [literal, builder]) {
    re.lastIndex = 0;
    let m: RegExpExecArray | null;
    while ((m = re.exec(text)) !== null) found.set(m[1], m[3]);
  }
  return found;
}

/** The index just past the call's opening `(`, skipping a generic argument
 *  list of any nesting depth. `-1` when this is not a call. */
function openParenAfter(text: string, from: number): number {
  let i = from;
  while (i < text.length && /\s/.test(text[i])) i += 1;
  if (text[i] === "<") {
    let depth = 0;
    while (i < text.length) {
      if (text[i] === "<") depth += 1;
      else if (text[i] === ">") {
        depth -= 1;
        if (depth === 0) {
          i += 1;
          break;
        }
      } else if (text[i] === "(" || text[i] === ";" || text[i] === "\n") {
        return -1; // not a generic list after all
      }
      i += 1;
    }
    while (i < text.length && /\s/.test(text[i])) i += 1;
  }
  return text[i] === "(" ? i + 1 : -1;
}

interface Site {
  where: string;
  literal: string;
}

function scan(files: string[]): { bad: Site[]; checked: number; unresolved: number } {
  // ⚠ **RESOLVED FILE-LOCALLY FIRST, AND THAT ORDER IS LOAD-BEARING.** A
  // tree-wide name map answered `path` with `work/workEndpoints.ts`'s
  // `"/assets/…"` — which begins with a slash — and passed
  // `closeOutEndpoints.ts`'s own `path`, the DEFECT this guard was written for,
  // as clean. `const path = …` occurs in ten files here. A shadowed name is the
  // ordinary case in this tree, not an edge one, so the file's own declarations
  // win and the tree-wide map is only a fallback for an imported constant.
  const shared = new Map<string, string>();
  for (const file of files) {
    for (const [name, value] of constantPrefixes(readFileSync(file, "utf8"))) {
      if (!shared.has(name)) shared.set(name, value);
    }
  }
  const bad: Site[] = [];
  let checked = 0;
  let unresolved = 0;
  const call = new RegExp(`\\b(?:client|api|apiClient)\\s*\\.\\s*(${VERBS.join("|")})\\b`, "g");

  for (const file of files) {
    if (/\.test\.tsx?$/.test(file) || file.endsWith("apiPathLiteral.guard.test.ts")) continue;
    const text = readFileSync(file, "utf8");
    const local = constantPrefixes(text);
    const consts = { get: (n: string) => local.get(n) ?? shared.get(n) };
    let m: RegExpExecArray | null;
    call.lastIndex = 0;
    while ((m = call.exec(text)) !== null) {
      const open = openParenAfter(text, m.index + m[0].length);
      if (open === -1) continue;
      let i = open;
      while (i < text.length && /\s/.test(text[i])) i += 1;
      const quote = text[i];
      if (quote !== "`" && quote !== '"' && quote !== "'") {
        // Not a literal at the call site. A NAMED builder — `path(accountId)`,
        // `accountPath(id)` — is still resolvable, and resolving it is what
        // catches DEF-CUS-5073. Anything else is genuinely out of reach and is
        // COUNTED rather than passed over in silence.
        const named = text.slice(i).match(/^([A-Za-z_$][\w$]*)\s*\(/);
        const built = named === null ? undefined : consts.get(named[1]);
        const line = text.slice(0, i).split("\n").length;
        if (built === undefined) unresolved += 1;
        else {
          checked += 1;
          if (!built.startsWith("/")) {
            bad.push({
              where: `${relative(SRC, file)}:${line}`,
              literal: `${named?.[1]}() builds "${built}…"`,
            });
          }
        }
        continue;
      }
      checked += 1;
      const rest = text.slice(i + 1);
      const line = text.slice(0, i).split("\n").length;
      const where = `${relative(SRC, file)}:${line}`;
      const literal = rest.slice(0, Math.min(rest.indexOf(quote === "`" ? "`" : quote), 60));
      if (rest.startsWith("/")) continue;
      if (rest.startsWith("${")) {
        const name = rest.slice(2).match(/^\s*([A-Za-z_$][\w$]*)\s*\}/)?.[1];
        const value = name === undefined ? undefined : consts.get(name);
        if (value === undefined) unresolved += 1;
        else if (!value.startsWith("/")) bad.push({ where, literal: `\${${name}} = ${value}` });
        continue;
      }
      bad.push({ where, literal });
    }
  }
  return { bad, checked, unresolved };
}

describe("every client path literal begins with a slash", () => {
  it("refuses a path that apiPath would weld onto the tenant segment", () => {
    const { bad, checked, unresolved } = scan(walk(SRC));
    // Law 7 habit 3 + the G32 lesson: print the SCOPE beside the verdict, so a
    // zero over a narrow scope cannot be mistaken for a zero over a wide one.
    const scope = `checked ${checked} literal path arguments; ${unresolved} call sites build their path elsewhere and are NOT covered by this guard`;
    expect(
      bad.length === 0
        ? scope
        : `${bad.length} client path literals do not begin with "/" (${scope}):\n` +
          bad.map((b) => `  ${b.where}  ${b.literal}`).join("\n"),
    ).toBe(scope);
  });
});
