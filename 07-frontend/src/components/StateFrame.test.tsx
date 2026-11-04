// ── Trace ──────────────────────────────────────────────
// Story:    US-SHL-011 (EP-SHL-04 §Stories)  Screens: S17, S25, S28, S33, S36, S38
// Rules:    BR-SHL-020 (six-patterns-once)
// ───────────────────────────────────────────────────────
// TC tests for the six A18 state patterns. No DOM library is in package.json,
// so these assert on react-dom/server static markup — real render output, no
// new dependencies (stdlib-of-react approach). Interactive behavior that needs
// a browser is marked it.todo and lands with the Playwright journeys.
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import "@/i18n"; // initializes the i18next singleton with the five catalogs

import {
  EmptyList,
  FailedWithRetry,
  FieldError,
  FormErrorSummary,
  LoadingSkeleton,
  PermissionDenied,
  WorkingButton,
  ZeroResults,
} from "./StateFrame";
import { buttonClasses } from "./buttonKit";

const noop = () => undefined;

describe("US-SHL-011 — the six A18 states as reusable components", () => {
  it("US-SHL-011 TC-1: empty list (S17, zero accounts) renders title + helper + primary create action, never an empty table header", () => {
    // §4 test data: fresh tenant "Maple Court Utilities", zero accounts.
    const html = renderToStaticMarkup(
      <EmptyList
        title="No accounts yet."
        helper="Create your first account to start billing."
        ctaLabel="+ New account"
        onCta={noop}
      />,
    );
    expect(html).toContain("<h4");
    expect(html).toContain("No accounts yet.");
    expect(html).toContain("Create your first account to start billing.");
    expect(html).toContain("+ New account");
    expect(html).toContain('data-variant="primary"');
    // BR-SHL-020: the block replaces the WHOLE table — no header markup anywhere.
    expect(html).not.toContain("<table");
    expect(html).not.toContain("<th");
  });

  it("DEF-SHL-4043: a held create action says why ON THE SCREEN, not only in a tooltip", () => {
    const html = renderToStaticMarkup(
      <EmptyList
        title="No crews yet"
        helper="Technicians are invited in Settings → Team."
        ctaLabel="Add a technician"
        ctaReason="Invite them in Settings first."
        onCta={noop}
      />,
    );
    // ⚠ READ THE TEXT WITH THE TAGS STRIPPED. THAT IS THE WHOLE CASE.
    // Asserting `html` contains the sentence is TRUE of
    // `title="Invite them in Settings first."` and equally true of a rendered
    // line, so an assertion written that way is green while the reason is a
    // tooltip and cannot fail on the thing this case is named for. It is
    // exactly how `PartsPage.test.tsx:151` records the same mistake in
    // `SegmentedControl` (`DEF-WRK-3646`). A tooltip does not exist on a touch
    // screen; stripping the tags is what makes a return to one go RED.
    const visible = html.replace(/<[^>]*>/g, " ");
    expect(visible).toContain("Invite them in Settings first.");
    expect(html).toContain('data-cta-reason=""');
    // The button is still disabled, and the tooltip is still there for a
    // pointer — the fix ADDS the visible line, it does not trade one for it.
    expect(html).toContain("disabled");
    expect(html).toContain('title="Invite them in Settings first."');
  });

  it("DEF-SHL-4043: a CTA with NO reason is unchanged — no stray reason line, no disabled button", () => {
    const html = renderToStaticMarkup(
      <EmptyList title="No accounts yet." helper="h" ctaLabel="+ New account" onCta={noop} />,
    );
    expect(html).not.toContain("data-cta-reason");
    // ⚠ `disabled=` WITH THE EQUALS SIGN. A bare `not.toContain("disabled")`
    // fails on the LIVE button, because the kit's own classes spell
    // `disabled:opacity-45` — the word is in every button's class list either
    // way, so the assertion would have been red for the wrong reason and then
    // "fixed" by deleting it. The attribute is what this case is about.
    expect(html).not.toContain("disabled=");
  });

  it("DEF-BIL-5340: zero results under a filter with NO term names the filters — never \"No results for ''\"", () => {
    const html = renderToStaticMarkup(<ZeroResults query="" onClearFilters={noop} />);
    // A default status chip empties a list with nothing typed; the echo form
    // read "No results for ''." on the Budget Bills tab (PO, 2026-09-15).
    expect(html).not.toContain("''");
    expect(html).toContain("No results match these filters.");
    expect(html).toContain("Clear filters");
    expect(html).not.toContain('data-variant="primary"');
  });

  it("US-SHL-011 TC-2: zero results for 'zzzz' shows the query echo + ghost Clear filters, and NO create action (A18 §2)", () => {
    const html = renderToStaticMarkup(<ZeroResults query="zzzz" onClearFilters={noop} />);
    expect(html).toContain("No results for");
    expect(html).toContain("zzzz");
    expect(html).toContain("Clear filters");
    expect(html).toContain('data-variant="ghost"');
    // A18 §2: do not offer "create" here — the data may exist, just filtered out.
    expect(html).not.toContain('data-variant="primary"');
    // The component replaces only the rows region; it renders no toolbar of its
    // own (the consuming screen keeps its toolbar/filters visible).
    expect(html).not.toContain("toolbar");
  });

  it("US-SHL-011 TC-3: loading skeleton (S33, slow connection) renders 6-10 rows in the real layout, never a bare spinner", () => {
    const html = renderToStaticMarkup(<LoadingSkeleton variant="table" />);
    const rowCount = (html.match(/skeleton-row/g) ?? []).length;
    expect(rowCount).toBeGreaterThanOrEqual(6);
    expect(rowCount).toBeLessThanOrEqual(10);
    expect(html).not.toContain("spinner");
    expect(html).toContain('aria-busy="true"');

    // Out-of-band row requests clamp into the A18 §3 band instead of degrading.
    const tooFew = renderToStaticMarkup(<LoadingSkeleton variant="table" rows={2} />);
    expect((tooFew.match(/skeleton-row/g) ?? []).length).toBe(6);
    const tooMany = renderToStaticMarkup(<LoadingSkeleton variant="table" rows={50} />);
    expect((tooMany.match(/skeleton-row/g) ?? []).length).toBe(10);

    // KPI and card variants render their real-layout shapes.
    const kpi = renderToStaticMarkup(<LoadingSkeleton variant="kpi" />);
    expect((kpi.match(/skeleton-kpi-block/g) ?? []).length).toBe(4);
    const card = renderToStaticMarkup(<LoadingSkeleton variant="card" />);
    expect(card).toContain("skeleton-title");
  });

  it("US-SHL-011 TC-4: failed bank import (S38, row 42) renders the danger card with Failed pill, plain-language reason, and Retry/Download/Cancel", () => {
    // §4 test data: firstnational-2026-08-06.csv, row 42 missing its amount.
    const html = renderToStaticMarkup(
      <FailedWithRetry
        title="Bank statement import failed."
        reason="We couldn't read row 42 (missing amount)."
        onRetry={noop}
        onDownloadReport={noop}
        onCancel={noop}
      />,
    );
    expect(html).toContain("card state-failed"); // danger top border via .state-failed
    expect(html).toContain("pill past");
    expect(html).toContain(">Failed<");
    expect(html).toContain("Bank statement import failed.");
    // BR-SHL-020: plain language — the human reason renders, no raw error code alone.
    expect(html).toContain("read row 42 (missing amount).");
    expect(html).toContain("Retry");
    expect(html).toContain("Download error report");
    expect(html).toContain("Cancel");
  });

  it("DEF-INT-5562: a failure panel with nothing to cancel draws no Cancel button", () => {
    // ⚠ **THE OTHER HALF OF THE CASE ABOVE, AND IT IS THE ONE THAT WAS
    // MISSING.** `onCancel` was REQUIRED, so 44 call sites passed
    // `() => undefined` and shipped a live, pressable *Cancel* over a
    // whole-page QUERY failure — where there is nothing to abandon and
    // *Retry* is the only act. Every check passed over it: the prop WAS
    // passed, so `G13` is satisfied; the label WAS in the DOM, so the case
    // above passed; and no gate in this repo reads rendered output (law 6).
    //
    // RED-FIRST: with `onCancel` required again and the button drawn
    // unconditionally, this fails on `expect(html).not.toContain("Cancel")`.
    const html = renderToStaticMarkup(
      <FailedWithRetry
        title="We could not load this page."
        reason="The server did not answer."
        onRetry={noop}
      />,
    );
    // Retry and the report stay — they are what this panel is FOR.
    expect(html).toContain("Retry");
    expect(html).toContain("Download error report");
    expect(html).not.toContain("Cancel");
  });

  it("US-SHL-011 TC-5: partial success (S28 read import) renders '84 imported · 6 need review · 2 failed' with a link to the failing rows", () => {
    // §4 test data: 92-row read file — 84 clean, 6 flagged, 2 malformed.
    const html = renderToStaticMarkup(
      <FailedWithRetry
        title="Read import finished with problems."
        reason="2 rows could not be read."
        onRetry={noop}
        onDownloadReport={noop}
        onCancel={noop}
        partial={{ imported: 84, needReview: 6, failed: 2, onViewFailing: noop }}
      />,
    );
    expect(html).toContain("84 imported · 6 need review · 2 failed");
    // The failing-rows link renders as a real interactive element.
    expect(html).toContain("state-failed-view");
    expect(html).toContain("View failing rows");
  });

  it.todo(
    "US-SHL-011 TC-6 (negative): Retry succeeding replaces the failed card with the normal flow, no duplicate import of the 84 rows — needs the consuming module's commit + idempotency; covered by the S28/S38 Playwright journeys",
  );

  it("US-SHL-011 TC-7: permission denied (Jordan deep-links /finance) renders title + helper + Back to Dashboard, with no data behind", () => {
    const helper = "Billing Clerks can't open Finance. Ask a System Admin if you need it.";
    const html = renderToStaticMarkup(<PermissionDenied helper={helper} onBack={noop} />);
    expect(html).toContain("have access to this."); // "You don't have access to this."
    expect(html).toContain("Ask a System Admin if you need it.");
    expect(html).toContain("Back to Dashboard");
    expect(html).toContain('data-variant="secondary"');
    // A18 §6: no data rendered behind — the component takes no children and its
    // markup is exactly the one centered block.
    expect(html.startsWith('<div class="state-frame state-denied"')).toBe(true);
    expect(html).not.toContain("<table");
  });

  // ── Supplementary (non-TC) coverage for patterns shared with EP-SHL-03 ──
  it("US-SHL-011 (A18 §3): WorkingButton disables and shows 'Working…' while in flight", () => {
    const idle = renderToStaticMarkup(<WorkingButton working={false}>Retry</WorkingButton>);
    expect(idle).toContain("Retry");
    // ⚠ NOT `not.toContain("disabled")` (CR-018 Phase 3). Under Route B the class
    // attribute SPELLS the state variants — `disabled:opacity-45
    // disabled:cursor-not-allowed` — so the substring is present on every button
    // in the product, enabled or not, and the old assertion passes nothing. It
    // is the ATTRIBUTE that has to be asked for.
    expect(idle).not.toMatch(/<button[^>]*\sdisabled=/);
    const busy = renderToStaticMarkup(<WorkingButton working={true}>Retry</WorkingButton>);
    expect(busy).toContain("disabled");
    expect(busy).toContain("Working…");
  });

  /**
   * ── B14 RULE 6, ASKED OF RENDERED OUTPUT — DEF-712 ──────────────────────
   *
   * Rule 6: *"Destructive commits (disconnect, retire, reverse, write-off) use
   * the danger button — outlined accent, filled on hover — never the standard
   * primary."* Until 2026-08-25 `WorkingButton` hard-coded `primary`, so the
   * danger tier sat in `buttonKit` UNREACHABLE from any wizard commit and a
   * disconnection committed through a button styled exactly like Save.
   *
   * ⚠ **THE ASSERTION IS THE RENDERED `class` ATTRIBUTE, NOT THE PROP.** The
   * defect's own escape reason is that nothing in this repo reads rendered
   * output; a case that checked the prop travelled would have passed on the
   * day the tier could not be reached at all. `buttonClasses("danger")` is the
   * same string the browser is given, so a change to the tier fails HERE
   * rather than on a screenshot.
   */
  it("B14 rule 6 (DEF-712): WorkingButton renders the DANGER tier when a commit declares itself destructive", () => {
    const html = renderToStaticMarkup(
      <WorkingButton working={false} variant="danger">
        Schedule the disconnection ✓
      </WorkingButton>,
    );
    expect(html).toContain('data-variant="danger"');
    expect(html).toContain(`class="${buttonClasses("danger")}"`);
    // Outlined at rest and FILLED on hover is the tier's own definition —
    // asserted so a future "simplification" to a flat fill goes red here.
    expect(html).toContain("bg-transparent");
    expect(html).toContain("hover:not-disabled:bg-danger-700");
  });

  it("B14 rule 6 (DEF-712, negative): a commit that does NOT declare itself destructive is unchanged — the primary tier", () => {
    const html = renderToStaticMarkup(<WorkingButton working={false}>Save ✓</WorkingButton>);
    expect(html).toContain('data-variant="primary"');
    expect(html).toContain(`class="${buttonClasses("primary")}"`);
    // The point of the negative half: threading the tier must not repaint the
    // other thirteen call sites. `bg-accent` is the primary fill; a danger
    // button has neither it nor the danger border.
    expect(html).toContain("bg-accent");
    expect(html).not.toContain("border-danger-500");
  });

  it("B14 rule 6 (DEF-712): the danger tier does NOT cost the A18 §3 working state", () => {
    // The tier is a colour. Single-flight lives on the wizard controller; the
    // DISABLED-while-in-flight half lives here, and it must survive the tier.
    const busy = renderToStaticMarkup(
      <WorkingButton working={true} variant="danger">
        Schedule the disconnection ✓
      </WorkingButton>,
    );
    expect(busy).toMatch(/<button[^>]*\sdisabled=/);
    expect(busy).toContain("Working…");
    expect(busy).toContain('data-variant="danger"');
  });

  it("US-SHL-011 (A18 §5 presentation kit): FieldError renders under-field copy; FormErrorSummary only appears for >3 errors", () => {
    const err = renderToStaticMarkup(
      <FieldError message="Amount must be greater than 0." id="amount-error" />,
    );
    expect(err).toContain("Amount must be greater than 0.");
    expect(err).toContain('id="amount-error"'); // aria-describedby hook for US-SHL-009
    // A18 §5: summary line only when MORE than 3 fields are invalid.
    expect(renderToStaticMarkup(<FormErrorSummary count={3} />)).toBe("");
    const summary = renderToStaticMarkup(<FormErrorSummary count={4} />);
    expect(summary).toContain("Fix 4 fields to continue.");
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-SHL-011@41aa2ae (story+rules snapshot hash)
// generated: 2026-08-09 by story-coder v1
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-08)
// gates: trace_lint✔ run_gates✔ tsc✔ eslint✔ vitest 14/14✔ (1 TC todo — browser/journey scope)
// exceptions: none
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
