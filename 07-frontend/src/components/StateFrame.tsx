// ── Trace ──────────────────────────────────────────────
// Story:    US-SHL-011 (EP-SHL-04 §Stories)  Screens: S17, S25, S28, S33, S36, S38 (composes into all)
// Rules:    BR-SHL-020 (six-patterns-once)
// ───────────────────────────────────────────────────────
// FE-07 StateFrame (B13 §1): the six A18 shared state patterns, each existing
// exactly ONCE. Screens compose these and supply only slot content — titles,
// helpers, CTAs, reasons (BR-SHL-020). Pattern (5), inline validation, is the
// presentation kit shared with EP-SHL-03/US-SHL-009: the pieces live here, the
// form field kit composes them.
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";

import "./StateFrame.css";
import { Button } from "./Button";
import type { ButtonVariant } from "./buttonKit";
import { ErrorReportButton } from "./ErrorReportButton";
import { useSectionHeadingLevel } from "./HeadingLevel";

// ── A18 §1 — Empty list (nothing created yet) ──────────────────────────────
// Centered h4 title + muted helper + primary create action. Replaces the WHOLE
// table region — consuming screens render EmptyList INSTEAD of their table.
export function EmptyList(props: {
  title: string; // per-screen copy, e.g. "No accounts yet."
  helper: string; // e.g. "Create your first account to start billing."
  /**
   * The one way into an empty list — e.g. `+ New account`.
   *
   * ⚠ **OPTIONAL SINCE 2026-09-10, AND ABSENT IS BYTE-FOR-BYTE WHAT EVERY
   * EXISTING CALLER ALREADY DREW** — the same additive shape `ctaVariant` and
   * `secondaryCtaLabel` took before it, and for the same reason: a shared
   * component may not move 27 screens to correct one.
   *
   * It exists because **an empty state is not always a list somebody can
   * fill.** A record's audit history is the worked case (`DEF-MET-4764`): a
   * clerk cannot create an audit row, so the block had nothing honest to
   * offer and passed `onCta: () => undefined` to satisfy a required prop —
   * which `EmptyList` then wired to a LIVE `<Button>`. The result was a
   * control that looked pressable, was pressable, and did nothing, sitting
   * a few pixels above a `ButtonLink` carrying the same words that worked.
   * Hard-won law 2's mirror, and nothing could see it: the prop HAS a caller,
   * so G13 passes; the label IS in the DOM, so every `toContain` passes.
   *
   * **A block with no `ctaLabel` draws no button at all** — which is the whole
   * of the fix, and is why the pair is checked rather than the label alone.
   */
  ctaLabel?: string;
  // BR-SHL-025's shape, in the empty state: a CTA the user cannot act on
  // renders DISABLED WITH ITS REASON rather than as a live button onto
  // nothing. Added 2026-08-10 with S17, whose create flow (the S18 guided
  // page) is a later story — an empty accounts list would otherwise have
  // offered "+ New account" and done nothing when clicked, which is exactly
  // the dead-UI class G13 exists for. Null/absent = the CTA is live.
  //
  // ⚠ **THE REASON IS RENDERED. IT WAS A `title` ALONE UNTIL 2026-09-05 AND
  // THE SENTENCE ABOVE WAS THEREFORE FALSE FOR FOUR WEEKS (`DEF-SHL-4043`).**
  // The line under this one said *disabled WITH ITS REASON* and the code said
  // `title={props.ctaReason}` — a browser tooltip, which opens on hover, after
  // a delay, and NEVER on a touch screen. So twenty screens drew a grey button
  // that said nothing, and the docstring was the only place the promise
  // existed: hard-won law 1, in this file's own amendment note.
  //
  // **NOTHING COULD HAVE SEEN IT, AND THAT IS THE POINT RATHER THAN AN
  // ACCIDENT.** A `title` attribute IS the sentence, so `toContain(reason)`
  // passes on the broken version, `tsc` passes, eslint passes, and G13 passes
  // — the prop HAS a caller, so by G13's question it is wired. Law 6: no gate
  // in this repo reads rendered output, and a tooltip and a line of text are
  // the same string to every check we own.
  //
  // It is the SECOND time in this product. `SegmentedControl.tsx` shipped the
  // identical bug and `DEF-WRK-3646` fixed it there; the fix did not travel to
  // the other component holding the same prop, because nothing looks for a
  // PATTERN, only for an instance. `G109` is what looks for the pattern now.
  ctaReason?: string | null;
  /**
   * B14 rule 4 / BR-SHL-044 — EXACTLY ONE PRIMARY ACTION ON A SCREEN, and an
   * empty list is where that is easiest to break: the page header already
   * carries the create action, and this block draws the same words again in
   * the same tier a few hundred pixels below it. Work > Parts shipped exactly
   * that and the PO reported it on 2026-09-04 as *"two + Add part buttons"*.
   *
   * ⚠ THE DEFAULT IS `primary`, SO ALL 27 EXISTING CALL SITES ARE
   * BYTE-FOR-BYTE UNCHANGED. It is the same shape `WorkingButton` used when it
   * grew its tier prop on 2026-08-25, and for the same reason: a shared
   * component may not move 27 screens to correct one. A screen whose header
   * carries the same action passes `secondary`; r10 rule 17 still gets *the
   * action that fills it*, and rule 4 gets its one primary.
   */
  ctaVariant?: "primary" | "secondary";
  /** Absent WITH `ctaLabel` absent = this empty state offers nothing, and
   *  draws nothing. Never a no-op handler — see `ctaLabel` above. */
  onCta?: () => void;
  /**
   * A SECOND way to fill the list, drawn beside the first in the ghost tier.
   *
   * ⚠ **OPTIONAL, AND ABSENT IS BYTE-FOR-BYTE WHAT THIS BLOCK ALREADY DREW** —
   * the same shape `ctaVariant` took when it landed, and for the same reason: a
   * shared component may not move 27 screens to correct one.
   *
   * It exists because a list can have two honest ways in and the empty state
   * that offers one is a door a clerk has to already know about. The premises
   * blueprint draws exactly that — *"the empty state names what is missing and
   * offers the two ways to fill it — add one, **or import a list**"* — and a
   * utility's first act on this product is almost always the import, which was
   * the option the block did not mention.
   *
   * The tier is GHOST rather than a second `secondary`: B14 rule 4 gives a
   * screen one primary, and two outlined buttons side by side ask a reader to
   * choose between equals when one of them is the ordinary answer.
   */
  secondaryCtaLabel?: string;
  onSecondaryCta?: () => void;
}) {
  // BR-SHL-020: an empty table header with zero rows must never render — this
  // block is the entire content area when a list has nothing yet.
  const blocked = props.ctaReason !== undefined && props.ctaReason !== null;
  return (
    <div className="state-frame state-empty">
      <h4>{props.title}</h4>
      <p className="state-helper">{props.helper}</p>
      {/* ⚠ **NO LABEL ⇒ NO BUTTON.** An empty state whose list nobody can fill
          offers nothing rather than a control that cannot act — the pair G13
          exists to catch, in the direction G13 cannot see (`DEF-MET-4764`). */}
      {props.ctaLabel === undefined ? null : blocked ? (
        <>
          {/* The `title` STAYS. It costs nothing, a pointer user keeps the
              hover, and removing it would be a second change to defend. What
              it may not be is the ONLY place the sentence lives. */}
          <Button variant={props.ctaVariant ?? "primary"} disabled title={props.ctaReason ?? ""}>
            {props.ctaLabel}
          </Button>
          {/* ⚠ `state-helper` IS REUSED RATHER THAN A NEW CLASS ADDED, AND A
              TAILWIND UTILITY WOULD HAVE RENDERED AS NOTHING AT ALL. B14 rule
              21's migration clause is PER FILE: a utility is emitted only for a
              file listed in `src/styles/route-b-migrated.txt`, and
              `components/StateFrame.tsx` is NOT on that list. `mt-1 text-base`
              here would be three classes no stylesheet declares — invisible,
              with `tsc`, eslint and every `toContain("mt-1")` green over it.
              The stylesheet already declares this one and it is the muted ink
              A18 §1 asks for, so reuse adds no class, which is what rule 21 is
              actually asking for.

              `data-cta-reason` is the machine handle, and it exists because
              neither reader can be satisfied by an attribute: the test strips
              tags and a walkthrough reads innerText. Same shape
              `SegmentedControl` settled on for `data-segment-reason` — the two
              components in this kit that hold a refusal now answer for it the
              same way, deliberately, so the next one can be copied from
              either. */}
          <p className="state-helper" data-cta-reason="">
            {props.ctaReason}
          </p>
        </>
      ) : (
        <Button variant={props.ctaVariant ?? "primary"} onClick={props.onCta}>
          {props.ctaLabel}
        </Button>
      )}
      {/* ⚠ NO WRAPPER AND NO NEW CLASS. `.state-frame` is already a centred
          column with the spacing scale's gap, so the second way in sits under
          the first with the rhythm the block already has — and this file is NOT
          on `src/styles/route-b-migrated.txt`, so a `flex gap-2` row here would
          be two classes no stylesheet declares: invisible in a browser, green
          in `tsc`, eslint and every `toContain` (B14 rule 21's per-file clause,
          DEF-974).
          Drawn only when BOTH halves are present — a label with no handler is
          a dead control and a handler with no label is nothing at all, which is
          the pair G13 exists to catch. */}
      {props.secondaryCtaLabel !== undefined && props.onSecondaryCta !== undefined && (
        <Button variant="ghost" onClick={props.onSecondaryCta}>
          {props.secondaryCtaLabel}
        </Button>
      )}
    </div>
  );
}

// ── A18 §2 — Zero results after a filter/search ────────────────────────────
// The toolbar/filters stay visible (the consuming screen keeps them); only the
// rows region is replaced by this block.
export function ZeroResults(props: { query: string; onClearFilters: () => void }) {
  const { t } = useTranslation();
  return (
    <div className="state-zero">
      {/* ⚠ TWO SENTENCES, BY WHETHER A TERM WAS TYPED (`DEF-BIL-5340`,
          2026-09-15). A list can be empty under a FILTER with no search term
          at all — a default status chip is one — and the echo form then read
          "No results for ''." on a live screen, which a clerk reads as a
          broken search. With a term the echo tells them what was searched;
          without one there is nothing to echo, so the sentence names the
          filters instead. Both keep the ghost Clear filters beneath. */}
      <p className="state-helper">
        {props.query === ""
          ? t("states.zeroResults.filtered")
          : t("states.zeroResults.message", { query: props.query })}
      </p>
      {/* BR-SHL-020 / A18 §2: no create action here — the data may exist, just filtered out */}
      <Button variant="ghost" onClick={props.onClearFilters}>
        {t("states.zeroResults.clearFilters")}
      </Button>
    </div>
  );
}

// ── A18 §3 — Loading skeleton ──────────────────────────────────────────────
// Real layout with shimmer bars — never a bare spinner for a content area.
// Tables show 6–10 rows; KPI strips show KPI-sized blocks; cards show a title
// bar + 3 line bars.
const SKELETON_ROWS_MIN = 6;
const SKELETON_ROWS_MAX = 10;
const SKELETON_ROWS_DEFAULT = 8;
// Varying bar widths per A18 §3 ("grey bars, varying widths") — cycled by row.
const SKELETON_WIDTHS = ["w-long", "w-mid", "w-short", "w-mid"] as const;

export function LoadingSkeleton(props: { variant: "table" | "kpi" | "card"; rows?: number }) {
  const { t } = useTranslation();
  // BR-SHL-020 / A18 §3: table skeletons render 6–10 rows — requests outside
  // that band clamp to it rather than degrading into a sparse or endless list.
  const rows = Math.min(
    SKELETON_ROWS_MAX,
    Math.max(SKELETON_ROWS_MIN, props.rows ?? SKELETON_ROWS_DEFAULT),
  );

  return (
    <div
      className={`skeleton skeleton-${props.variant}`}
      // ⚠ `role="status"` (`DEF-CWP-10565`, tester F-14): an `aria-label` on a
      // role-less `<div>` is PROHIBITED and is dropped by the browser, so the
      // name "Loading…" reached nobody. A status region may carry a name, and
      // it is what a placeholder for content still coming IS.
      role="status"
      aria-busy="true"
      aria-label={t("states.loading")}
    >
      {props.variant === "table" &&
        Array.from({ length: rows }, (_, i) => (
          <div key={i} className="skeleton-row">
            <div className={`skeleton-bar ${SKELETON_WIDTHS[i % SKELETON_WIDTHS.length]}`} />
          </div>
        ))}
      {props.variant === "kpi" &&
        Array.from({ length: 4 }, (_, i) => (
          <div key={i} className="skeleton-kpi-block skeleton-bar" />
        ))}
      {props.variant === "card" && (
        <>
          <div className="skeleton-bar skeleton-title w-mid" />
          <div className="skeleton-bar w-long" />
          <div className="skeleton-bar w-mid" />
          <div className="skeleton-bar w-short" />
        </>
      )}
    </div>
  );
}

// A18 §3, second half: buttons that trigger work show disabled + "Working…"
// (billing run, import, reconcile). The wizard framework (US-SHL-010) and any
// commit button compose this instead of re-implementing the state.

/**
 * THE TWO TIERS A COMMIT MAY WEAR — B14 rule 6, and nothing wider.
 *
 * ⚠ **IT IS A NARROWED UNION AND NOT `ButtonVariant`, DELIBERATELY.** Rule 6
 * says a destructive commit (disconnect, retire, reverse, write-off) uses the
 * danger tier and *"never the standard primary"*; every other commit is the
 * primary. Those are the only two answers the rule has, so a `ghost` or `link`
 * commit button does not compile rather than being caught by a reviewer's eye.
 * `Extract<>` keeps the two names tied to `buttonKit` — rename a variant there
 * and this stops compiling instead of silently drifting.
 */
export type CommitTier = Extract<ButtonVariant, "primary" | "danger">;

export function WorkingButton(props: {
  working: boolean;
  children: ReactNode; // the idle label, per-screen copy (e.g. "Create account ✓")
  onClick?: () => void;
  type?: "button" | "submit";
  /**
   * B14 rule 6's danger tier, for a DESTRUCTIVE commit — DEF-712.
   *
   * ⚠ **THE RULE WAS UNOBEYABLE UNTIL THIS PROP EXISTED, AND THAT LOOKED
   * EXACTLY LIKE A RULE NOBODY HAD GOT TO YET.** `danger` has been in
   * `buttonKit` since CR-018 Phase 3 with no way through: this component hard
   * coded `primary`, so a disconnection — cutting off a household's water —
   * committed through a button styled identically to Save, and no gate in this
   * repo reads rendered output to say so.
   *
   * It is OPTIONAL and absent means `primary`, so all fourteen existing call
   * sites render exactly as before; only a screen that DECLARES its commit
   * destructive changes tier. The alternative — a second commit button drawn
   * beside this one — was rejected by the W7 lane and the reasoning is binding:
   * it would lose the single-flight guard, the A18 §3 working state and the
   * A18 §4 failure-with-state-preserved, which is a worse product than a
   * wrongly-styled button.
   */
  variant?: CommitTier;
  /**
   * A18 §3 already disables this button WHILE THE COMMIT IS IN FLIGHT. This is
   * the other reason a commit can be unavailable: the form in front of it is
   * not finished — CR-069 wave E's type-the-name confirm (`US-INT-025`).
   *
   * ⚠ OPTIONAL, AND ABSENT MEANS EXACTLY WHAT IT MEANT BEFORE. It is OR-ed
   * with `working`, never substituted for it, so no caller can accidentally
   * re-enable a button mid-commit by passing `disabled={false}`.
   */
  disabled?: boolean;
}) {
  const { t } = useTranslation();
  return (
    <Button
      variant={props.variant ?? "primary"}
      type={props.type ?? "button"}
      // A18 §3: disabled while in flight — double-clicks are harmless. OR-ed
      // with the caller's own reason, never replaced by it.
      disabled={props.working || props.disabled === true}
      onClick={props.onClick}
    >
      {props.working ? t("states.working") : props.children}
    </Button>
  );
}

// ── A18 §4 — Failed import / sync (with retry) ─────────────────────────────
// A card with a danger top border and a "Failed" pill; bold what-failed line,
// muted plain-language reason; Retry / Download error report / Cancel.
export function FailedWithRetry(props: {
  title: string; // bold what-failed line, e.g. "Bank statement import failed."
  // BR-SHL-020: plain language, never a raw error code alone —
  // e.g. "We couldn't read row 42 (missing amount)."
  reason: string;
  onRetry: () => void; // surface only re-invokes; idempotency is the consuming module's (§1 TC-6)
  /**
   * ⛔ **OPTIONAL SINCE 2026-09-23, AND THE BUTTON NO LONGER NEEDS IT
   * (`DEF-SHL-6377`).** The Product Owner pressed *Download error report* on a
   * failed property sale and nothing happened: 99 of this panel's 101 call
   * sites passed `() => undefined` to satisfy a required prop, the wizard
   * frame passed `noop`, and there was never a report behind any of them.
   *
   * **The button now builds and downloads its own report** —
   * `ErrorReportButton`: screen, page, time in the utility's zone, version,
   * the two sentences below, the diagnostic, and the refused request's
   * method/path/status/code. A handler passed here still runs, AFTER the
   * download. The 99 `() => undefined` are dead and harmless; they are left
   * for the lanes that own those files rather than swept here (CLAUDE.md law
   * 11). A new caller passes nothing.
   */
  onDownloadReport?: () => void;
  /**
   * ⛔ **OPTIONAL SINCE 2026-09-24, AND THE BUTTON IS NOT DRAWN WITHOUT IT
   * (`DEF-INT-5562`).** This prop was REQUIRED, and 44 of this panel's call
   * sites passed `() => undefined` to satisfy it — a live, pressable *Cancel*
   * on a failure panel that cancels nothing. That is hard-won law 2's mirror:
   * `G13` asks whether a prop is PASSED and a no-op handler IS a caller, the
   * label IS in the DOM so every `toContain` passes, and no gate in this repo
   * reads rendered output (law 6).
   *
   * **Absent ⇒ no button.** The component was written for a whole-PAGE import
   * or sync failure (A18 §4), where *Cancel* means abandon the job; every
   * later caller is a whole-page QUERY failure, where there is nothing to
   * abandon and *Retry* is the only act. The 44 no-ops are removed in the same
   * commit, so the control disappears from those screens rather than being
   * left live over a rule nobody can see.
   */
  onCancel?: () => void;
  // A18 §4 partial success: "84 imported · 6 need review · 2 failed" + a link
  // to the failing rows. Counts come from the job result payload.
  partial?: { imported: number; needReview: number; failed: number; onViewFailing: () => void };
  // The short technical line — `diagnosticOf(error)` from api/client. ADDED
  // 2026-08-10 on the PO's report from the first live deployment: the screen
  // said "Something went wrong" while the actual event was a 502 from the API
  // pass-through, and nothing on the page let a user tell those apart. Codes and
  // identifiers only, never server prose, so TD-16/G14 are untouched. Rendered
  // beside the reason rather than hidden behind Download error report, because a
  // user who cannot load the page often cannot download a report either.
  diagnostic?: string | null;
}) {
  const { t } = useTranslation();
  // ⚠ **IN THE PORTAL THIS CARD IS THE WHOLE PAGE, SO ITS TITLE IS THE PAGE'S
  // h1 (`DEF-CWP-10563`).** All 27 portal call sites draw it IN PLACE OF the
  // frame — a signed-out visit to any of 36 signed-in addresses lands here —
  // and the page then had no heading at all. Where an outline is kept (only
  // under the portal's `HeadingLevelProvider`) the line is announced as a level-1
  // heading; it stays the same `<p>` with the same class, so it looks exactly
  // as it did. The staff app keeps no outline and gets the plain `<p>`.
  const outline = useSectionHeadingLevel();
  return (
    <div className="card state-failed" role="alert">
      <span className="pill past">{t("states.failed.pill")}</span>
      <p
        className="state-failed-title"
        role={outline === null ? undefined : "heading"}
        aria-level={outline === null ? undefined : 1}
      >
        {props.title}
      </p>
      <p className="state-failed-reason">{props.reason}</p>
      {props.diagnostic ? (
        <p className="state-failed-diagnostic">
          <code>{props.diagnostic}</code>
        </p>
      ) : null}
      {props.partial && (
        <p className="state-failed-counts">
          {t("states.failed.counts", {
            imported: props.partial.imported,
            needReview: props.partial.needReview,
            failed: props.partial.failed,
          })}{" "}
          <Button
            variant="ghost"
            className="state-failed-view"
            onClick={props.partial.onViewFailing}
          >
            {t("states.failed.viewFailing")}
          </Button>
        </p>
      )}
      <div className="state-failed-actions">
        <Button variant="primary" onClick={props.onRetry}>
          {t("states.failed.retry")}
        </Button>
        {/* `DEF-SHL-6377` — the button downloads its OWN report; the caller's
            handler, if any, runs after it. Same tier, same label, same place. */}
        <ErrorReportButton
          title={props.title}
          reason={props.reason}
          diagnostic={props.diagnostic}
          onAfterDownload={props.onDownloadReport}
        />
        {/* `DEF-INT-5562` — drawn ONLY where there is something to cancel. */}
        {props.onCancel ? (
          <Button variant="ghost" onClick={props.onCancel}>
            {t("states.failed.cancel")}
          </Button>
        ) : null}
      </div>
    </div>
  );
}

// ── A18 §5 — Inline form validation (presentation kit) ─────────────────────
// Shared with EP-SHL-03/US-SHL-009: the field kit applies INVALID_INPUT_CLASS
// to the offending input and renders FieldError directly under it (wired to
// the input via aria-describedby using `id`). Orchestration — when to validate,
// scroll-to-first-error — belongs to US-SHL-009, not here.
export const INVALID_INPUT_CLASS = "input-invalid"; // border-color: danger-500 (A18 §5)

export function FieldError(props: { message: string; id?: string }) {
  // 12px danger-700 message directly under the field, e.g. "Amount must be greater than 0."
  return (
    <p className="field-error" id={props.id}>
      {props.message}
    </p>
  );
}

export function FormErrorSummary(props: { count: number }) {
  const { t } = useTranslation();
  // A18 §5: the summary line renders only when MORE than 3 fields are invalid.
  if (props.count <= 3) {
    return null;
  }
  return (
    <p className="form-error-summary" role="alert">
      {t("states.validation.summary", { count: props.count })}
    </p>
  );
}

// ── A18 §6 — Permission denied ─────────────────────────────────────────────
// Centered title/helper/"Back to Dashboard". The component takes no children,
// so no data can render behind it — a gated route renders PermissionDenied
// INSTEAD of its screen (route gating itself is EP-SHL-06).
export function PermissionDenied(props: {
  helper: string; // per-screen copy naming role + module, e.g. "Billing Clerks can't open Finance. Ask a System Admin if you need it."
  onBack: () => void;
}) {
  const { t } = useTranslation();
  return (
    <div className="state-frame state-denied">
      <h4>{t("states.denied.title")}</h4>
      <p className="state-helper">{props.helper}</p>
      <Button variant="secondary" onClick={props.onBack}>
        {t("states.denied.back")}
      </Button>
    </div>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-SHL-011@41aa2ae (story+rules snapshot hash)
// generated: 2026-08-09 by story-coder v1 · AMENDED 2026-09-23 by lane ERROR-REPORT (DEF-SHL-6377 — `FailedWithRetry`'s *Download error report* is `ErrorReportButton`, which downloads its own report on every one of the 101 call sites; `onDownloadReport` became OPTIONAL and runs after the download, so every caller is unchanged and compiles) · AMENDED 2026-08-10 by story-coder (W2 customers lane — `EmptyList` grew an OPTIONAL `ctaReason`: a create CTA whose flow is a later story now renders disabled WITH its reason instead of a live button onto nothing) · AMENDED 2026-08-25 by lane DANGERTIER (DEF-712 — `WorkingButton` grew an OPTIONAL `variant?: CommitTier`: B14 rule 6's danger tier existed in `buttonKit` with NO way to reach a commit button, so a disconnection committed through a button styled exactly like Save. Absent = `primary`, so all fourteen existing call sites are byte-for-byte unchanged)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-08)
// gates: trace_lint✔ run_gates✔ tsc✔ eslint✔ vitest 14/14✔ (1 TC todo — browser/journey scope) · [W2 customers lane 2026-08-10] tsc✔ eslint --max-warnings 0✔ vitest 622 passed / 148 todo across 47 files✔ · vite build✔ · run_gates 14 PASS · 0 FAIL · 1 SKIP✔ · [DANGERTIER 2026-08-25] tsc✔ eslint 0✔ vitest 2624 passed / 1 skipped / 198 todo across 150 files✔ · G13✔ G31✔ G37✔ G40✔ · the three new rule-6 cases proved RED first, in a scratchpad copy, against a hard-coded `primary` and against a removed `disabled={props.working}`
// exceptions: E4 [2026-08-25] the tier is a NARROWED union (`"primary" | "danger"`) rather than `ButtonVariant` — rule 6 has exactly two answers, so a `ghost` commit does not compile · E4 [2026-08-10] `ctaReason` is OPTIONAL and absent means the CTA stays live, so every existing caller is unchanged; DataTable passes it through field by field rather than by spread, which is also what keeps G13 able to see that the prop has a caller
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
