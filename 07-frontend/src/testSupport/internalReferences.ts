// ── Trace ──────────────────────────────────────────────
// Defect:   DEF-BIL-5339 (rule ids, open-question ids and Python identifiers
//           reached a clerk on the Budget Bills tab through two sites that
//           printed the server's own sentences unchanged)
// Rules:    B14 rule 31 (no database id on screen) · rule 32 (no rule id or
//           internal code in clerk-facing copy) · rule 33 (rationale is ZERO
//           words on screen) · CLAUDE.md hard-won law 6 (no gate reads
//           rendered output — the running screen has to be looked at)
// ───────────────────────────────────────────────────────
/**
 * WHAT A CLERK CAN SEE, READ FOR INTERNAL REFERENCES.
 *
 * ══════════════════════════════════════════════════════════════════════════
 * WHY THIS READS RENDERED OUTPUT AND NOT SOURCE
 * ══════════════════════════════════════════════════════════════════════════
 * Every check this repo already has for internal ids reads a FILE: G28 walks
 * the catalogues and the API modules' served dicts, the backend asks test
 * regexes `unavailable[].detail` off the response, and an August fix stopped
 * `GapNotes` printing the `br_ref` FIELD. Each one is truthful over what it
 * looks at, and none of them can see an id that arrives INSIDE a sentence a
 * component prints verbatim — which is how `BR-RAT-043`, `OQ-237`, `OQ-142`,
 * `budget_service.enroll` and `budget.settle_up_gl_account` stood on a live
 * screen for four weeks with every suite green (`DEF-BIL-5339`).
 *
 * So this helper looks at the thing a clerk looks at: the DOM a screen
 * produced. Text nodes, and the two attributes a browser SHOWS on hover or
 * reads aloud (`title`, `aria-label`). It deliberately does NOT read `data-*`
 * attributes, because the 2026-08-19 ruling put the reference THERE on
 * purpose — `data-br-ref` is where support finds the rule, and a check that
 * flagged it would be refusing that ruling.
 *
 * ══════════════════════════════════════════════════════════════════════════
 * WHAT COUNTS AS INTERNAL
 * ══════════════════════════════════════════════════════════════════════════
 *   1. The id grammar `CLAUDE.md` defines — `US-`, `EP-`, `BR-`, `OQ-`, `DEF-`,
 *      `GT-`, `TC-`, `IS-`, `ADR-`, `CR-`, with the optional module segment
 *      (`OQ-BIL-12359`) and three to five digits. ⚠ THE LOOKAHEAD IS
 *      LOAD-BEARING: without `(?!\d)` a six-digit tail reads as a five-digit id
 *      (`DEF-2804`'s shape one order up).
 *   2. A dotted Python identifier — `budget_service.enroll`,
 *      `budget.settle_up_gl_account`, `apps.tenancy.selectors.read_settings`,
 *      `bill_run_decisions.case`. A dotted run only counts when a segment
 *      carries an underscore or the run has three or more segments, so `e.g.`
 *      and a domain name are not false positives.
 *
 * ══════════════════════════════════════════════════════════════════════════
 * HOW TO USE IT
 * ══════════════════════════════════════════════════════════════════════════
 *     const { container } = render(<Screen />);
 *     expect(internalReferencesIn(container)).toEqual([]);
 *
 * The array is what a failure prints, so the test names the exact string the
 * clerk would have read rather than a count. It is shared so any screen's
 * test can ask the same question; a screen that has never been asked it is a
 * screen nobody has checked.
 */

/** `CLAUDE.md`'s id grammar, verbatim, with the load-bearing lookahead. */
export const INTERNAL_ID_PATTERN =
  /\b(?:US|EP|BR|OQ|DEF|GT|TC|IS|ADR|CR)-(?:[A-Z]{3}-)?\d{3,5}(?!\d)/g;

/** A dotted run of snake-case names — a Python identifier, a column, a path. */
const DOTTED_RUN = /\b[a-z_][a-z0-9_]*(?:\.[a-z_][a-z0-9_]*)+\b/g;

function isPythonIdentifier(run: string): boolean {
  return run.includes("_") || run.split(".").length >= 3;
}

/** Every internal reference inside ONE string, in order of appearance. */
export function internalReferencesInText(text: string): string[] {
  const ids = text.match(INTERNAL_ID_PATTERN) ?? [];
  const dotted = (text.match(DOTTED_RUN) ?? []).filter(isPythonIdentifier);
  return [...ids, ...dotted];
}

/**
 * The same question asked of STATIC MARKUP — for a test that renders with
 * `renderToStaticMarkup` in node and has no DOM to walk (`routing/
 * renderedCopy.test.tsx` is one). Text between tags is read tag by tag, so an
 * id at the start of an element keeps its word boundary; `title` and
 * `aria-label` values are read; every other attribute — `data-br-ref` and its
 * siblings, which the 2026-08-19 ruling put there on purpose — is dropped.
 */
export function internalReferencesInMarkup(html: string): string[] {
  const found: string[] = [];
  for (const match of html.matchAll(/\s(?:title|aria-label)="([^"]*)"/g)) {
    found.push(...internalReferencesInText(decodeEntities(match[1] ?? "")));
  }
  for (const text of html.replace(/<script[\s\S]*?<\/script>/g, "").split(/<[^>]*>/)) {
    if (text.trim() !== "") {
      found.push(...internalReferencesInText(decodeEntities(text)));
    }
  }
  return found;
}

function decodeEntities(text: string): string {
  return text
    .replace(/&quot;/g, '"')
    .replace(/&#x27;/g, "'")
    .replace(/&#39;/g, "'")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&amp;/g, "&");
}

/**
 * Every internal reference a clerk could read or hover on inside `root`:
 * every text node in the subtree, ONE AT A TIME, plus every `title` and
 * `aria-label` attribute on every element in it.
 *
 * ⚠ NOT `root.textContent`. The first draft of this helper read that, and the
 * red proof it was written for CAUGHT FOUR IDS AND MISSED THE FIFTH:
 * `textContent` glues adjacent elements together with no separator, so a
 * `<summary>` ending in "yet" followed by an `<li>` starting "BR-RAT-043"
 * reads as `yetBR-RAT-043`, and the word boundary the pattern needs is gone.
 * Same for `billingapps.tenancy.selectors…` — a heading glued to a paragraph.
 * A clerk sees two lines; the check saw one word. Text nodes are what the
 * browser lays out, so they are what this reads.
 */
export function internalReferencesIn(root: Element | DocumentFragment): string[] {
  const found: string[] = [];
  const walker = root.ownerDocument?.createTreeWalker(root, 4 /* NodeFilter.SHOW_TEXT */);
  for (let node = walker?.nextNode(); node; node = walker?.nextNode()) {
    found.push(...internalReferencesInText(node.textContent ?? ""));
  }
  for (const element of root.querySelectorAll("[title], [aria-label]")) {
    for (const attribute of ["title", "aria-label"] as const) {
      const value = element.getAttribute(attribute);
      if (value !== null) {
        found.push(...internalReferencesInText(value));
      }
    }
  }
  return found;
}
