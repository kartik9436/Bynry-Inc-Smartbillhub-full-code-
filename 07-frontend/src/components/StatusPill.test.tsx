// ── Trace ──────────────────────────────────────────────
// Story:    US-SHL-013 (EP-SHL-05 §Stories — display kit)  Screens: every status chip (S17, S25, S30, S33, S49, …)
// Rules:    BR-SHL-023 (labels from the consumer's catalog) · A12 §Semantic tokens
// ───────────────────────────────────────────────────────
// TC tests for FE-10 StatusPill: four semantic tones, bound to the A12
// design-system pill classes — status meaning only, never decoration.
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { StatusPill } from "./StatusPill";

describe("US-SHL-013 — StatusPill (FE-10): semantic tones on the A12 pill classes", () => {
  // CR-018 Route B: StatusPill.css is deleted; three tones render their exact
  // former declarations as utilities, and danger still composes StateFrame's
  // `.pill.past` class (that stylesheet is not migrated yet).
  it("A12 §Semantic tokens: each tone maps to its design-system styling (utilities / past)", () => {
    expect(renderToStaticMarkup(<StatusPill tone="success">Paid</StatusPill>)).toBe(
      '<span class="pill bg-success-100 text-success-700">Paid</span>',
    );
    expect(renderToStaticMarkup(<StatusPill tone="warning">Estimated</StatusPill>)).toBe(
      '<span class="pill bg-warning-100 text-warning-700">Estimated</span>',
    );
    expect(renderToStaticMarkup(<StatusPill tone="danger">Overdue</StatusPill>)).toBe(
      '<span class="pill past">Overdue</span>',
    );
    expect(renderToStaticMarkup(<StatusPill tone="neutral">Draft</StatusPill>)).toBe(
      '<span class="pill bg-neutral-200 text-neutral-700">Draft</span>',
    );
  });

  // ── DEF-722 · THE FIFTH AND SIXTH TONES (PO ruling 2026-08-26) ───────────
  // *"have differnt color for diff pill - you can define colors -
  // recommendation: A"*. Asserted here, on RENDERED markup, because the whole
  // failure mode of a new tone is that the union accepts it, `tsc` is happy,
  // `toHaveClass` is happy, and the browser paints nothing — which is the
  // DEF-327 / G31 shape this repo has met seven times.
  it("A12 §Semantic tokens: `info` and `muted` render their own utilities, and neither reuses another tone's", () => {
    expect(renderToStaticMarkup(<StatusPill tone="info">Vacation hold</StatusPill>)).toBe(
      '<span class="pill bg-info-100 text-info-700">Vacation hold</span>',
    );
    // ⚠ `muted` adds NO token — it is the neutral ramp one step solid, so the
    // two quiet statuses differ by WEIGHT and not by hue.
    expect(renderToStaticMarkup(<StatusPill tone="muted">Closed</StatusPill>)).toBe(
      '<span class="pill bg-neutral-400 text-neutral-900">Closed</span>',
    );
    // …and the six are six. A tone that quietly duplicates another is the
    // collapse DEF-722 was filed about, reappearing one layer down.
    const tones = ["success", "warning", "danger", "info", "neutral", "muted"] as const;
    const rendered = tones.map((tone) =>
      renderToStaticMarkup(<StatusPill tone={tone}>x</StatusPill>),
    );
    expect(new Set(rendered).size, "two tones render the same markup").toBe(tones.length);
  });

  it("BR-SHL-023: the label is the consumer's pre-translated copy — the pill invents no strings and carries no inline styles", () => {
    const html = renderToStaticMarkup(<StatusPill tone="success">Conciliado</StatusPill>);
    expect(html).toContain("Conciliado"); // whatever the consumer's catalog says
    expect(html).not.toContain("style="); // tokens-only styling (B8)
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-SHL-013@1e89ecb (story+rules snapshot hash)
// generated: 2026-08-09 by story-coder v1
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-08)
// gates: trace_lint✔ run_gates✔ (10 PASS · 0 FAIL · 2 SKIP) tsc✔ eslint✔ vitest 94/94✔ (12 todo this packet — browser/server/consumer scope)
// exceptions: none
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
