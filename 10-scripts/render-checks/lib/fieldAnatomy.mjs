/**
 * THE FIELD-ANATOMY PROBE — B14 rule 39, measured in a real browser.
 *
 * ⚠ **IT LIVES HERE BECAUSE TWO CHECKS NEED IT AND A SECOND COPY WOULD DRIFT**
 * (PO 2026-09-12: *"Do all changes bsed on actual code - also dont create
 * duplcate code"*, and hard-won law 5 — one source, derive the rest). It was a
 * `const` inside `cr092-lane3-field-anatomy.mjs` until `CR-094-BRC01` step 2
 * wave E needed the same measurement on the five starting-service wizards. The
 * corrections that made it trustworthy — measuring to the VISIBLE control box
 * rather than to a radio inside a `.seg`, and refusing to call a distance
 * across an intervening row a field-to-field gap — were each paid for once, in
 * a wrong number in a published table, and a copy would have to pay for them
 * again.
 *
 * `render-checks/lib/` is where this directory already keeps shared probe code
 * (`knownGaps.mjs`, `timings.mjs`); nothing new is invented by putting it here.
 *
 * ⚠ **IT RUNS IN THE PAGE.** Everything it returns is rendered truth read with
 * `getBoundingClientRect` and `getComputedStyle` — never source, and never a
 * class name. A Tailwind utility in a file absent from `route-b-migrated.txt`
 * is in the DOM and styles nothing, which is exactly why no source-level check
 * can answer these questions.
 */

/** Rule 39's ratified figures: label -> input 5px, input -> helper 6px,
 *  field -> field 20px (amended 2026-09-12, *"a) 20 everywhere — the anatomy
 *  wins"*), a ratio of ~1 : 1 : 4. */
export const RULE = { labelToInput: 5, inputToHelp: 6, fieldToField: 20 };

/**
 * Read every `.field` inside `scope` and report its anatomy.
 * Runs IN THE PAGE — everything here is rendered truth, not source.
 */
export const PROBE = (scopeSelector) => {
  const round = (n) => Math.round(n * 100) / 100;
  const scope = document.querySelector(scopeSelector);
  if (scope === null) return { error: `no element matches ${scopeSelector}` };
  const all = Array.from(scope.querySelectorAll(".field"));
  const hidden = [];
  const fields = [];
  for (const el of all) {
    const box = el.getBoundingClientRect();
    if (box.height === 0 || box.width === 0) {
      hidden.push(el.querySelector("label")?.textContent?.trim() ?? "(no label)");
      continue;
    }
    const label = el.querySelector(":scope > label");
    const help = el.querySelector(":scope > .field-help");
    // ⚠ THE CONTROL IS THE VISIBLE BOX, NOT THE FIRST `<input>` IN THE TREE.
    // A `SegmentedField` wraps its radios in `<div class="seg">` and each radio
    // sits inside a `.seg-opt` label, inset by the seg's own padding — so
    // `querySelector("input")` measures to a radio the eye never sees and
    // reports a label-to-input gap that is nobody's design decision. The first
    // pass of this script did exactly that and put 22.3px in the table for
    // three fields; this is the correction, kept visible because a wrong number
    // in a measured table is the one thing this lane exists not to produce.
    const control =
      el.querySelector(":scope > .seg, :scope > .radio-group") ??
      el.querySelector("input, select, textarea");
    const parts = [];
    if (label !== null) parts.push(["LABEL", label.getBoundingClientRect()]);
    if (help !== null) parts.push(["HELP", help.getBoundingClientRect()]);
    if (control !== null) parts.push(["INPUT", control.getBoundingClientRect()]);
    const domOrder = Array.from(el.children)
      .map((c) =>
        c.matches("label")
          ? "LABEL"
          : c.matches(".field-help")
            ? "HELP"
            : c.querySelector("input, select, textarea") !== null ||
                c.matches("input, select, textarea")
              ? "INPUT"
              : c.matches(".field-error, [role='alert']")
                ? "ERROR"
                : "other",
      )
      .filter((n) => n !== "other");
    const paintedOrder = parts
      .slice()
      .sort((a, b) => a[1].top - b[1].top)
      .map((p) => p[0]);
    const rect = (name) => parts.find((p) => p[0] === name)?.[1] ?? null;
    const gap = (from, to) => {
      const a = rect(from);
      const b = rect(to);
      return a === null || b === null ? null : round(b.top - a.bottom);
    };
    fields.push({
      el,
      label: label?.textContent?.replace(/\*$/, "").trim() ?? "(no label)",
      id: control?.id ?? null,
      tag:
        control === null
          ? "NONE"
          : control.classList.contains("seg")
            ? "seg"
            : control.tagName.toLowerCase(),
      hasHelp: help !== null,
      helpText: help?.textContent?.trim() ?? null,
      domOrder: domOrder.join(" > "),
      paintedOrder: paintedOrder.join(" > "),
      labelToInput: gap("LABEL", "INPUT"),
      labelToHelp: gap("LABEL", "HELP"),
      helpToInput: gap("HELP", "INPUT"),
      inputToHelp: gap("INPUT", "HELP"),
      labelMarginBottom: label === null ? null : getComputedStyle(label).marginBottom,
      helpMargin: help === null ? null : getComputedStyle(help).margin,
      top: round(box.top),
      bottom: round(box.bottom),
      left: round(box.left),
      parentGap: getComputedStyle(el.parentElement).gap,
      parentDisplay: getComputedStyle(el.parentElement).display,
    });
  }
  // ── Field-to-field ────────────────────────────────────────────────────
  // ⚠ ONLY BETWEEN TWO `.field`s THAT ARE IMMEDIATE SIBLINGS IN ONE CONTAINER
  // AND SHARE A LEFT EDGE. Anything else is not a field-to-field gap at all:
  // the first pass of this script reported 53.69px and 120.22px, which were the
  // distance across an intervening checkbox row and across a nested grid — real
  // distances between real fields, and nobody's spacing decision. A measured
  // table that carries them is worse than one that says "not adjacent".
  const visible = new Map(all.map((el) => [el, null]));
  for (let i = 0; i < fields.length; i += 1) {
    const el = fields[i].el;
    let sib = el.nextElementSibling;
    while (sib !== null && !sib.classList.contains("field") && sib.getBoundingClientRect().height === 0)
      sib = sib.nextElementSibling;
    if (sib === null || !sib.classList.contains("field")) {
      fields[i].fieldToField = null;
      fields[i].fieldToFieldWhy = "not adjacent (no sibling .field)";
      continue;
    }
    const b = sib.getBoundingClientRect();
    if (Math.abs(b.left - fields[i].left) > 1) {
      fields[i].fieldToField = null;
      fields[i].fieldToFieldWhy = "side by side (same row, different column)";
      continue;
    }
    fields[i].fieldToField = round(b.top - fields[i].bottom);
    fields[i].fieldToFieldWhy = null;
  }
  for (const f of fields) delete f.el;
  void visible;
  return { fields, hidden, total: all.length };
};
