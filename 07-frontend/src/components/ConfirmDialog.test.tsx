// ── Trace ──────────────────────────────────────────────
// Story:    US-SHL-009 (EP-SHL-03 §Stories)  Screens: S8, S22, S31.3, S35, S54, S63
// Rules:    IS-6 (consequence confirm) · IS-10 (dialog a11y) — B9 conformance
// ───────────────────────────────────────────────────────
// Tests for FE-04 ConfirmDialog — the IS-6 confirm step of every destructive/
// money action. Markup asserts on react-dom/server static output (prior-run
// convention); the toast-after-commit and audit_log halves of IS-6 belong to
// the consuming modules + backend, so they are honest it.todos here.
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import "@/i18n"; // initializes the i18next singleton with the five catalogs

import { ConfirmDialog } from "./ConfirmDialog";
import { buttonClasses } from "./buttonKit";

const noop = () => undefined;

/**
 * ⚠ **ONE BUTTON'S OWN OPENING TAG, NOT THE WHOLE DOCUMENT.**
 *
 * This dialog renders THREE buttons — ✕ close, Cancel and the confirm — and the
 * B14 rule 6 cases below ask a question about exactly one of them. Asserting a
 * class token against the whole markup answers "does ANY button on screen carry
 * this", which is a different and much weaker question: the ghost Cancel would
 * happily answer for the confirm. So the confirm is located by the copy it
 * renders, and only its opening tag is examined (DEF-712's helper, DEF-718's
 * surface).
 */
function buttonTagLabelled(html: string, label: string): string {
  for (const match of html.matchAll(/<button\b[^>]*>([\s\S]*?)<\/button>/g)) {
    if (match[1].includes(label)) {
      return match[0].slice(0, match[0].indexOf(">") + 1);
    }
  }
  throw new Error(`no <button> labelled ${label} in the rendered output`);
}

describe("US-SHL-009 — FE-04 ConfirmDialog (IS-6 destructive/money confirm)", () => {
  it("US-SHL-009 / IS-6: renders consequence messaging with an explicit verb confirm — never a bare OK", () => {
    // Consequence copy names what changes, to what, and how much (IS-6);
    // corrections-are-new-rows is CLAUDE.md rule 4 speaking in plain language.
    const html = renderToStaticMarkup(
      <ConfirmDialog
        title="Write off 3 balances?"
        consequence="This writes off $412.55 across 3 accounts. Corrections are new rows — this can't be edited away later."
        confirmLabel="Write off 3 balances"
        working={false}
        onConfirm={noop}
        onCancel={noop}
      />,
    );
    expect(html).toContain('role="alertdialog"'); // interrupts, and says so to AT
    expect(html).toContain('aria-modal="true"');
    expect(html).toContain("Write off 3 balances?");
    expect(html).toContain("This writes off $412.55 across 3 accounts.");
    expect(html).toContain(">Write off 3 balances</button>"); // explicit verb, not OK
    expect(html).toContain('data-variant="primary"'); // Modernist: accent doubles as the alert color (A12)
    expect(html).toContain(">Cancel</button>");
    // ⚠ CLASS NAME -> `data-variant` (CR-018 Phase 4a, 2026-08-20). Route B
    // deletes the name; `buttonKit` stamps `data-variant`/`data-size` on every
    // kit button precisely so a check has something stable to read.
    expect(html).toContain('data-variant="ghost"');
    expect(html).not.toContain(">OK<");
  });

  it("US-SHL-009 / A18 §3: while the commit is in flight the confirm shows disabled + 'Working…' — double-clicks harmless", () => {
    const html = renderToStaticMarkup(
      <ConfirmDialog
        title="Write off 3 balances?"
        consequence="This writes off $412.55 across 3 accounts."
        confirmLabel="Write off 3 balances"
        working={true}
        onConfirm={noop}
        onCancel={noop}
      />,
    );
    expect(html).toContain("Working…"); // WorkingButton, composed not rebuilt
    // ⚠ NOT `toContain("disabled")` — that assertion CANNOT FAIL and was green
    // through a mutation that removed `disabled={props.working}` outright
    // (DEF-712's mutant 5). Under Route B the kit spells the state variants
    // into every button's class attribute — `disabled:opacity-45
    // disabled:cursor-not-allowed` — so the substring is present on a button
    // that is not disabled at all. It is the ATTRIBUTE that has to be asked
    // for, on the confirm's own tag.
    expect(buttonTagLabelled(html, "Working…")).toMatch(/<button[^>]*\sdisabled=/);
    expect(html).not.toContain(">Write off 3 balances</button>");
  });

  it("US-SHL-009 / IS-10: the shell provides a labelled ✕ close and title association", () => {
    const html = renderToStaticMarkup(
      <ConfirmDialog
        title="Retire meter M-2201?"
        consequence="The meter stops accepting reads. Its history stays."
        confirmLabel="Retire meter"
        working={false}
        onConfirm={noop}
        onCancel={noop}
      />,
    );
    expect(html).toContain('aria-label="Close"');
    expect(html).toContain("aria-labelledby");
    expect(html).toContain("modal-head"); // the ONE shell from FormModal.tsx
  });

  /**
   * ── B14 RULE 6, ASKED OF RENDERED OUTPUT — DEF-718 ────────────────────────
   *
   * Rule 6: *"Destructive commits (disconnect, retire, reverse, write-off) use
   * the danger button — outlined accent, filled on hover — never the standard
   * primary."* This dialog is the rule's LARGEST surface — thirty non-test call
   * sites that delete, retire, archive, deactivate and roll back — and until
   * 2026-08-26 it composed `WorkingButton` and passed no tier, so every one of
   * them committed through a button styled exactly like Save. DEF-712 landed
   * the tier on `WorkingButton`; `confirmVariant` is the half that reaches
   * here.
   *
   * ⚠ **THE ASSERTION IS THE RENDERED `class` ATTRIBUTE, NOT THE PROP**, and it
   * is pinned at BOTH quotes so an appended class cannot slip past a substring
   * match (DEF-182's shape). DEF-718's escape reason is that no gate in this
   * repo reads rendered output: a case checking that `confirmVariant` travelled
   * would have been green on the broken day, when there was nothing to travel.
   */
  it("B14 rule 6 (DEF-718): a destructive confirm renders the DANGER tier", () => {
    const html = renderToStaticMarkup(
      <ConfirmDialog
        title="Write off 3 balances?"
        consequence="This writes off $412.55 across 3 accounts."
        confirmLabel="Write off 3 balances"
        confirmVariant="danger"
        working={false}
        onConfirm={noop}
        onCancel={noop}
      />,
    );
    const confirm = buttonTagLabelled(html, "Write off 3 balances");
    expect(confirm).toContain('data-variant="danger"');
    // Both quotes — the whole attribute, so an extra token appended to the end
    // of the class list fails here instead of passing a substring match.
    expect(confirm).toContain(`class="${buttonClasses("danger")}"`);
    // Outlined at rest and FILLED on hover — rule 6's own words, both halves.
    expect(confirm).toContain("bg-transparent");
    expect(confirm).toContain("border-danger-500");
    expect(confirm).toContain("hover:not-disabled:bg-danger-700");
    // …and never the standard primary.
    expect(confirm).not.toContain('data-variant="primary"');
    expect(confirm).not.toContain("bg-accent");
    // The tier belongs to the CONFIRM alone: Cancel is still the ghost.
    expect(buttonTagLabelled(html, "Cancel")).toContain('data-variant="ghost"');
  });

  it("B14 rule 6 (DEF-718, negative): a confirm in front of a NON-destructive act is byte-for-byte the primary", () => {
    // ⚠ THIS HALF IS THE POINT OF THE SWEEP, NOT A FORMALITY. A tier that
    // appears on every dialog carries no information, so a confirm before a
    // creation, a publish or a send must NOT wear it — and the prop being
    // optional is what keeps those call sites unchanged.
    const html = renderToStaticMarkup(
      <ConfirmDialog
        title="Send the close export?"
        consequence="This sends 412 entries to QuickBooks."
        confirmLabel="Send export"
        working={false}
        onConfirm={noop}
        onCancel={noop}
      />,
    );
    const confirm = buttonTagLabelled(html, "Send export");
    expect(confirm).toContain('data-variant="primary"');
    expect(confirm).toContain(`class="${buttonClasses("primary")}"`);
    expect(confirm).toContain("bg-accent");
    expect(confirm).not.toContain("border-danger-500");
  });

  it("B14 rule 6 (DEF-718): the danger tier does NOT cost the A18 §3 working state", () => {
    // The tier is a colour. Disabled-while-in-flight is the guarantee, and a
    // restyle must not buy the colour with it.
    const html = renderToStaticMarkup(
      <ConfirmDialog
        title="Retire meter M-2201?"
        consequence="The meter stops accepting reads. Its history stays."
        confirmLabel="Retire meter"
        confirmVariant="danger"
        working={true}
        onConfirm={noop}
        onCancel={noop}
      />,
    );
    const confirm = buttonTagLabelled(html, "Working…");
    expect(confirm).toMatch(/<button[^>]*\sdisabled=/);
    expect(confirm).toContain('data-variant="danger"');
    // A18 §3's other half: Cancel is unavailable while the commit is in flight.
    expect(buttonTagLabelled(html, "Cancel")).toMatch(/<button[^>]*\sdisabled=/);
  });

  it.todo(
    "IS-6 (journey scope): confirm → consumer commit → A13 toast → audit_log row — needs the consuming module's packet + backend",
  );

  it.todo(
    "IS-10 (browser scope): Esc / backdrop / ✕ cancel the dialog and focus stays trapped inside — Playwright journey",
  );
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-SHL-009@b9eb83e (story+rules snapshot hash)
// generated: 2026-08-09 by story-coder v1
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-08)
// gates: trace_lint✔ run_gates✔ (10 PASS · 0 FAIL · 2 SKIP) tsc✔ eslint✔ vitest 54/54✔ (7 todo this packet — browser/journey/consumer scope)
// exceptions: none
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
