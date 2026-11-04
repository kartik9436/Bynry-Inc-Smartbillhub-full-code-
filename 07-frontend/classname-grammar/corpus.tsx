/* ══════════════════════════════════════════════════════════════════════════
 * THE GOLDEN CORPUS FOR THE className GRAMMAR (OQ-277, 2026-08-20)
 * ══════════════════════════════════════════════════════════════════════════
 *
 * This file is NOT part of the application. It is never imported, never built,
 * never rendered. It is the FIXTURE that two independent readers of the same
 * grammar are measured against:
 *
 *   · Python — `10-scripts/gates/g31_declared_classes.py`, `class_tokens()`,
 *     asserted by `grammar_corpus_selftest()` inside G31's own `run()`, which
 *     `.github/workflows/gates.yml` runs on every push.
 *   · TypeScript — `07-frontend/src/styles/routeBUtilities.test.ts`,
 *     `classTokens()`, asserted by vitest, which `.github/workflows/
 *     ci-frontend.yml` runs on every change under `07-frontend/**` (this file
 *     included — which is WHY it lives under 07-frontend and not in 10-scripts).
 *
 * Sharing the regex sources (`patterns.json`) stops the two from spelling the
 * grammar differently. It does NOT stop them from USING it differently — the
 * bugs this corpus is built from were all in the surrounding code, not in a
 * character of regex. Only measuring both readers against the same expected
 * output catches that, and that is what this file is for.
 *
 * ⚠ IT DELIBERATELY LIVES OUTSIDE `07-frontend/src/`. G31 scans `src/**\/*.tsx`
 * for referenced classes and its ratchet is ZERO; a fixture inside src/ would
 * add ten undeclared class names to the product's own count and turn the gate
 * red on a file that is not part of the product. `tsconfig.json` includes only
 * `src`, `npm run lint` lints only `src`, and vitest collects only
 * `src/**\/*.test.{ts,tsx}` — so nothing here reaches tsc, ESLint or the test
 * collector either. That is four separate reasons for the location; none of
 * them is cosmetic.
 *
 * EVERY CASE BELOW IS A BUG THAT HAS ALREADY HAPPENED. The mapping from case to
 * defect is in `corpus.expected.json`'s `cases` array, which is the readable
 * half of this pair. Add a case by adding it in BOTH files; both readers assert
 * SET EQUALITY, so a name added here and not there fails immediately, in both
 * languages — which is the point.
 * ══════════════════════════════════════════════════════════════════════════ */

/** C1 — the ordinary case: a plain string attribute, every token a class. */
export function C1Plain() {
  return <div className="cg-plain-alpha cg-plain-beta" />;
}

/** C2 — A COMPARISON OPERAND IS A VALUE, NOT A CLASS.
 *  `"auto"` is a state name that happens to sit inside the same braces. G31's
 *  first draft counted it and reported 130 undeclared classes where 125 were
 *  real — a false positive, which is the one failure this family of gates
 *  cannot survive (DEF-323: a gate that cries wolf gets switched off). */
export function C2Comparison({ row }: { row: { state: string } }) {
  return <div className={row.state === "auto" ? undefined : "cg-comparison-kept"} />;
}

/** C3 — AN INTERPOLATED TEMPLATE MUST YIELD ALL THREE NAMES.
 *  This is the case that has been read wrong TWICE, in opposite directions:
 *  the narrow first reader accepted only a backtick string with no `${`, so it
 *  found the two state classes and LOST the base class that draws the element;
 *  the first widening used one alternation, so the backtick branch consumed the
 *  template whole and it found the base class and SILENTLY LOST both state
 *  classes. The referenced count went 871 -> 870 and looked like an improvement.
 *  Two separate passes over the same expression are the only reading that gets
 *  all three, and this case is what says so. */
export function C3Interpolated({ sel }: { sel: boolean }) {
  return <div className={`cg-tpl-base ${sel ? "cg-tpl-selected" : "cg-tpl-blocked"}`} />;
}

/** C4 — A CLASS NAME MENTIONED IN A COMMENT IS NOT A REFERENCE.
 *  Neither reader parses TSX; both scan for `className=`. So prose naming a
 *  class must not be picked up, and this asserts it. See C9 for the honest
 *  limit of that claim. */
export function C4Comment() {
  // cg-comment-line is named here in prose and is never asked for.
  /* cg-comment-block is named in a block comment and is never asked for. */
  return <div className="cg-comment-real" />;
}

/** C5 — a template literal with NO interpolation is just a string. */
export function C5FlatTemplate() {
  return <div className={`cg-flat-one cg-flat-two`} />;
}

/** C6 — A TOKEN ENDING IN `-` IS A PREFIX, NOT A CLASS.
 *  `svc-${service}` is completed at runtime; the compiler and the stylesheet
 *  both know `.svc-electric`, and nobody declares `.svc-`. Six such prefixes
 *  exist in the app and counting them would be six false positives. */
export function C6Prefix({ service }: { service: string }) {
  return <div className={`cg-prefix-${service} cg-prefix-kept`} />;
}

/** C7 — THE EXPRESSION SPANS NEWLINES.
 *  The generalised shape of the G34 bug, where `^\s*` matched across a newline
 *  and the gate reported the wrong line. Anchors and whitespace classes are
 *  exactly where Python `re` and JS `RegExp` are most likely to disagree, so
 *  the grammar uses NO anchors at all (`patterns.json` refuses them) and this
 *  case proves `\s*` and the negated classes cross a newline identically in
 *  both engines. It is also verbatim the shape the app really writes. */
export function C7Multiline({ hot }: { hot: boolean }) {
  return (
    <div
      className={`cg-multiline-base ${
        hot ? "cg-multiline-hot" : "cg-multiline-cool"
      }`}
    />
  );
}

/** C8 — a comparison SPLIT ACROSS A NEWLINE is still a comparison.
 *  C2 and C7 crossed: if `\s*` stopped spanning newlines in either engine,
 *  `"compact"` would be reported as a class and the gate would cry wolf. */
export function C8NewlineComparison({ mode }: { mode: string }) {
  return (
    <div
      className={
        mode !==
        "compact"
          ? "cg-newline-cmp-yes"
          : "cg-newline-cmp-no"
      }
    />
  );
}

/** C9 — THE HONEST LIMIT OF C4, ASSERTED RATHER THAN ADMITTED.
 *  A commented-out `className=` attribute IS still read, by both readers,
 *  because neither strips comments before scanning. That is today's shared
 *  behaviour and it is harmless (the name is still a real class somebody
 *  declared). It is pinned here so that if a future lane teaches ONE reader to
 *  strip comments, the other one goes red on the same commit instead of
 *  quietly reading the codebase by different rules — which is the whole of
 *  OQ-277. */
export function C9CommentedAttribute() {
  // className="cg-commented-attribute-still-read"
  return <div className="cg-commented-real" />;
}

/** C10 — THE ONE PLACE THE TWO READERS ARE ALLOWED TO DIFFER, PINNED.
 *  `patterns.json` shares five patterns and deliberately does NOT share the
 *  sixth, `TOKEN`, because the two readers ask different questions: G31 asks
 *  "is this a name a stylesheet could declare", the vitest check asks "is this
 *  a candidate Tailwind could compile", and a variant like `sm:...` is a valid
 *  answer to the second and never to the first. Unshared is not unwatched: the
 *  divergence has an exact expected size here (one token), so a reader that
 *  drifts by one more fails. */
export function C10VariantUtility() {
  return <div className="cg-variant-plain sm:cg-variant-utility" />;
}

/* ── C11-C14 · OQ-280 · a component KIT holds its utilities in constants, not
 * in className=. These four cases are the shapes buttonKit.ts actually uses —
 * derived from that file, not invented. */
const CG_STRUCTURE =
  "inline-flex cg-kit-items-center " +
  "cg-kit-rounded";
const CG_SIZE = {
  default: "cg-kit-text-btn",
  sm: "cg-kit-text-btn-sm",
} as const;
const CG_ARBITRARY = "cg-kit-px-[14.4px]";
/* the NEGATIVE: prose in a kit file must contribute NOTHING, not its
 * lowercase words. `Save` is not utility-shaped, so the whole string is
 * rejected and `changes` never leaks in as a class name. */
const CG_LABEL = "Save changes";
const CG_URL = "https://example.invalid/docs";
/* C15 · a quoted OBJECT KEY is not a utility. `cg-kit-keyname` is perfectly
 * utility-shaped, so only its POSITION distinguishes it. Found on the real
 * buttonKit.ts, which named settings-row, link and ghost. */
const CG_KEYED = {
  "cg-kit-keyname": "cg-kit-keyed-value",
} as const;
/* C16 · a COMPARISON OPERAND inside a kit constant is a value, not a utility.
 * This is historical bug 1 in a second reader — it contributed `link` and
 * `ghost` from the real buttonKit.ts until the strip was added. */
const CG_PICK = variant === "cg-kit-notautility" ? "cg-kit-picked" : "cg-kit-other";
