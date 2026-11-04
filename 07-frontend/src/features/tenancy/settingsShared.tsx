// ── Trace ──────────────────────────────────────────────
// Story:    US-TEN-005 · US-TEN-006 · US-TEN-007 · US-TEN-009 · US-TEN-012 · US-IDN-010 (S8 shared frame)
//           Screens: S8 (every tab), S63–S71 (Reference-data rule cards)
// Rules:    BR-SHL-035 (ONE Reference-data shell — same header block, same "← Reference data" return,
//           same save/confirm/toast, same audit line, whether the management view is a LIST or a FORM) ·
//           BR-TEN-024 (sticky Save/Discard; the whole tab commits atomically) ·
//           BR-SHL-020 (plain-language failure; the six A18 states exist once) ·
//           BR-SHL-025 (a forbidden control renders disabled WITH ITS REASON, never silently missing) ·
//           BR-TEN-016 (every save is audited server-side — the audit line says so, it never claims to write one)
// ───────────────────────────────────────────────────────
// The pieces every S8 surface composes. They live here rather than in
// SettingsPage.tsx so the tab bodies can import them without an import cycle
// back through the frame that renders them.
//
// BR-SHL-035 is the reason SettingsFrame exists at all: the PO's ruling is that
// every Reference-data item — simple lookup list AND rule page — uses the SAME
// shell. One component renders that shell, so a rule page CANNOT drift into a
// differently-shaped screen: it gets the same back-link, header block, save row
// and audit line by construction.
import type { CSSProperties, ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";

import { isApiError } from "@/api/client";
import { refusalText } from "@/api/refusalText";
import { PermissionDenied, WorkingButton } from "@/components/StateFrame";
import { RefusalStrip } from "@/components/Surfaces";
import { Kicker, Note } from "@/components/TextBits";
import { useTenantPath } from "@/routing/tenantPath";
import { Button } from "@/components/Button";

/** Tenant-RELATIVE, like every route constant since path tenancy landed. */
export const DASHBOARD_ROUTE = "/dashboard";

// ── Plain-language failure (BR-SHL-020) ────────────────────────────────────

export type Translator = (key: string, params?: Record<string, unknown>) => string;

/**
 * The server's `message_key` renders through the catalog. A raw code never
 * reaches a user and no sentence is assembled client-side (TD-16/B8).
 *
 * BR-SHL-020 r2 (DEF-322): the params go through `refusalParams`, so
 * `params.detail` — the service's own engineering prose — is dropped and the
 * `{{ref}}` a system-error sentence quotes is supplied. One implementation,
 * shared, because six screens each had their own before.
 */
export function apiErrorText(error: unknown, t: Translator): string {
  return refusalText(t, error);
}

/**
 * True when the failure is the server refusing this ROLE → A18 §6. **403 only.**
 *
 * ⛔ **`DEF-SHL-6378` — THIS RETURNED TRUE FOR 401 AS WELL, FROM 2026-08-09 TO
 * 2026-09-23, AND 78 SCREENS INHERITED IT.** A 401 is not a refusal of the role:
 * it means there is no session at all (`core/errors.py` answers `AUTH-001`), so
 * a System Admin whose session had run out opened Payments and was told *"Your
 * role can't open Payments. Ask a System Admin if you need it."* — advice to ask
 * themselves. The PO found it on production. A 401 is now said ONCE, by the
 * shell, for every screen (`components/SessionExpired.tsx`), and never reaches a
 * screen's denial branch as a permission fact.
 */
export function isPermissionDenied(error: unknown): boolean {
  return isApiError(error) && error.status === 403;
}

/**
 * The refusal envelopes these screens must SHOW rather than swallow — currency
 * lock, guarded disable, audit-locked delete, last-admin guard, self-lockout.
 * Returns the rendered line plus the `br_ref` the server cited, so the reason
 * on screen is traceable to the rule that produced it.
 */
export interface Refusal {
  message: string;
  brRef: string | null;
}

export function refusalOf(error: unknown, t: Translator): Refusal {
  return {
    message: apiErrorText(error, t),
    brRef: isApiError(error) ? error.brRef : null,
  };
}

/**
 * One place that renders a server refusal, so every tab shows it the same.
 *
 * ── DEF-332 · THE `br_ref` IS CARRIED, NOT PRINTED (2026-08-21) ────────────
 * This used to append `<span class="settings-refusal-ref"> (BR-IDN-013)</span>`
 * after the sentence, so a billing clerk at a 1–2 staff utility read *"A
 * utility needs one active System Admin. You can't deactivate this one.
 * (BR-IDN-013)"*. The PO's standing ruling of 2026-08-19 is *"all these
 * messages should not be on screen for user"*; the same day they added *"for
 * time being okay"* about this particular span, which the decision log records
 * as a DEFERRAL and not a reversal. This takes the deferral up.
 *
 * ⚠ THE ID IS NOT DROPPED, IT MOVES. `br_ref` is mandatory on every BIZ refusal
 * (hard rule B8) and both the audit trail and support read it, so:
 *   · the SERVER still sends it and the envelope still carries it — unchanged;
 *   · it lands on `data-br-ref` on the strip, which is what support and the
 *     browser inspector read, and what the DEF-322 e2e spec now pins;
 *   · it stops being part of the SENTENCE, which is the whole of the ruling.
 *
 * A `data-` attribute rather than a `console.log`: a console line is written
 * once at render and gone the moment the user scrolls or the app re-renders,
 * and cannot be read from a screenshot, an accessibility tree or a Playwright
 * assertion. The attribute is on the element the refusal IS, so it survives for
 * exactly as long as the refusal is on screen and no longer.
 *
 * ⚠ It is NOT rendered into the accessible name either — `data-*` is invisible
 * to a screen reader by design. A clerk using one hears the sentence, which is
 * what a sighted clerk now reads.
 */
export function RefusalNotice(props: { refusal: Refusal | null }) {
  if (props.refusal === null) {
    return null;
  }
  return (
    <RefusalStrip
      role="alert"
      {...(props.refusal.brRef !== null ? { "data-br-ref": props.refusal.brRef } : {})}
    >
      {props.refusal.message}
    </RefusalStrip>
  );
}

// ── Layout primitives (A12 `.panel`, ported from the signed prototype) ─────

export function Panel(props: {
  /** Usually a plain string; S64's per-service panels pass the service badge
   *  beside the name (CR-038 A1), so the type is the h3's own. */
  title: ReactNode;
  hint?: string;
  accent?: boolean;
  children: ReactNode;
}) {
  return (
    <section className={`panel${props.accent === true ? " hi" : ""}`}>
      <h3>{props.title}</h3>
      {props.hint !== undefined && <p className="panel-hint">{props.hint}</p>}
      {props.children}
    </section>
  );
}

/**
 * ⚠ **`min` IS AN OPT-IN AND ABSENT IT RENDERS EXACTLY WHAT IT ALWAYS DID
 * (`CR-155-BRC09`, B14 rule 36's "add it to the kit" shape).** `.settings-grid`
 * reads `--panel-min` with a 320px default, so the fifteen other Settings
 * surfaces composing this grid are byte-identical.
 *
 * ⚠ **AND IT IS A CUSTOM PROPERTY RATHER THAN A SECOND CLASS, ON PURPOSE.**
 * B14 rule 21 forbids adding a class to a stylesheet; writing the whole
 * `grid-template-columns` as a Tailwind utility here would put a class no
 * stylesheet declares into a file that is NOT on `route-b-migrated.txt`,
 * which G31 refuses — and listing this file hands fifteen screens' bespoke
 * classes to the stricter compiler check in the same commit, for one number.
 *
 * The one caller today is the redesigned Security tab, at `288px`, because
 * three 320px columns need 1008px and the real frame leaves 992px at 1280 —
 * the arithmetic is written out in `SettingsPage.css` beside the rule.
 */
export function PanelGrid(props: { children: ReactNode; min?: string }) {
  return (
    <div
      className="settings-grid"
      {...(props.min === undefined
        ? {}
        : { style: { "--panel-min": props.min } as CSSProperties })}
    >
      {props.children}
    </div>
  );
}

/**
 * BR-TEN-024: the sticky Save/Discard footer. Save commits the WHOLE tab in one
 * call; Discard reverts to the server's values. The trailing note is the tab's
 * own (US-TEN-005 "Last edited by …", US-TEN-006 "does not restate historical
 * bills") — this component never invents one.
 */
export function SaveBar(props: {
  saveLabel: string;
  working: boolean;
  dirty: boolean;
  readOnly: boolean;
  readOnlyReason: string;
  onSave: () => void;
  onDiscard: () => void;
  note?: ReactNode;
}) {
  const { t } = useTranslation();
  return (
    <div className="settings-savebar">
      {props.readOnly ? (
        // BR-SHL-025: disabled WITH the reason, focusable, never a vanished
        // control that leaves the user guessing.
        <Button variant="primary" disabled title={props.readOnlyReason}>
          {props.saveLabel}
        </Button>
      ) : (
        <WorkingButton working={props.working} onClick={props.onSave}>
          {props.saveLabel}
        </WorkingButton>
      )}
      <Button
        variant="ghost"
        disabled={props.readOnly || !props.dirty || props.working}
        onClick={props.onDiscard}
      >
        {t("settings.discard")}
      </Button>
      {props.readOnly && <span className="settings-readonly">{props.readOnlyReason}</span>}
      {props.note !== undefined && <Note as="span">{props.note}</Note>}
    </div>
  );
}

/**
 * BR-SHL-035: the ONE management-view shell. Every Reference-data item renders
 * inside it — the lookup lists, the holiday calendar, and each rule page —
 * so the back-link, header block and audit line are identical by construction.
 * `children` is the only thing that differs: a table for a list, fields for a
 * rule page.
 */
export function SettingsFrame(props: {
  backLabel?: string;
  onBack?: () => void;
  kicker: string;
  title: string;
  description?: string;
  actions?: ReactNode;
  children: ReactNode;
}) {
  const { t } = useTranslation();
  return (
    <div className="settings-frame">
      {props.onBack !== undefined && (
        <Button variant="ghost" className="settings-back" onClick={props.onBack}>
          {props.backLabel ?? t("settings.reference.back")}
        </Button>
      )}
      <div className="settings-frame-head">
        <div>
          <Kicker>{props.kicker}</Kicker>
          <h2 className="settings-frame-title">{props.title}</h2>
          {props.description !== undefined && (
            <p className="settings-frame-desc">{props.description}</p>
          )}
        </div>
        {props.actions !== undefined && (
          <div className="settings-frame-actions">{props.actions}</div>
        )}
      </div>
      {props.children}
      {/* BR-TEN-016 / CLAUDE.md #7: the write is audited SERVER-side. This line
          states the fact for the user; it never claims to have written a row. */}
      <p className="settings-audit-line">{t("settings.auditLine")}</p>
    </div>
  );
}

/**
 * The honest state for a surface whose backend does not exist yet. It names
 * what it is waiting for and renders NO fields — nothing can be typed into a
 * form that posts nowhere.
 *
 * ── `tracks` · WHY A STATED ABSENCE NEEDS AN ID (DEF-445, 2026-08-21) ──────
 * DEF-445: the plan wizard's Deposits panel said *"the category list is set up
 * in the Accounts module, which is not built yet"* — for WEEKS after that
 * module was built, and after that very wizard began receiving the list. It was
 * found by the PO walking the screen, and by nothing else. DEF-421 was the same
 * shape one screen earlier.
 *
 * **A sentence is invisible to every gate we own.** `tsc` cannot type-check a
 * claim, the component's tests assert the panel RENDERS (it does), and a grep
 * for the last false string never reaches the next one, because the next one
 * phrases the same false premise differently. So the note outlives its reason
 * and nothing notices.
 *
 * `tracks` is the expiry date: the OQ or DEF that keeps this absence open. When
 * that row closes, `10-scripts/defect_report.py` and the open-questions
 * register point at every screen still claiming it, and `G38` counts the notes
 * that cite nothing at all — ratcheted, so the number can only fall.
 *
 * ⚠ IT IS A `data-` ATTRIBUTE AND NOT PART OF THE SENTENCE. The PO ruled on
 * 2026-08-19 that our internal ids do not belong on a customer's screen (see
 * `RefusalNotice`, DEF-332), and a clerk at a 1–2 staff utility can do nothing
 * with `DEF-445`. The id is for US; the sentence is for them.
 *
 * ⚠ AND IT IS OPTIONAL IN THE TYPE ON PURPOSE. Making it required would break
 * 90-odd call sites in one commit, most of which need an id nobody has minted
 * yet — a change that big gets a blanket value typed into it and the mechanism
 * dies on arrival. G38 holds the count instead: new notes must carry one.
 */
export function ArrivesWith(props: { title: string; message: string; tracks?: string }) {
  return (
    <div
      className="settings-arrives"
      role="note"
      {...(props.tracks !== undefined ? { "data-tracks": props.tracks } : {})}
    >
      <h3>{props.title}</h3>
      <p>{props.message}</p>
    </div>
  );
}

/**
 * A day-of-month as an ORDINAL in the active language (`DEF-224`).
 *
 * r10's schedule preview reads *"bills out 5th · due 26th"*; the screen
 * rendered *"bills out the 5 · due the 26"*. A number where a reader expects an
 * ordinal reads as unfinished rather than as a bug.
 *
 * ⚠ NOT `${n}th` WITH SPECIAL CASES FOR 1/2/3. That is English spelled out in
 * code, and this product ships eleven languages. `Intl.PluralRules` with
 * `type: "ordinal"` gives the language's own category — English returns
 * one/two/few/other for 1st/2nd/3rd/4th, and a language with no ordinal
 * suffixes returns "other" for everything. The suffix strings live in the
 * catalogues, so a language whose "other" suffix is empty simply gets the bare
 * number, which is the correct rendering for it.
 *
 * ⚠ **IT MOVED HERE FROM `RoutesCyclesWizards` ON 2026-09-09 AND WAS NOT
 * COPIED (`DEF-MET-4733`).** `CR-089`'s property header writes *"bills on the
 * 12th"* and needs the same rendering. A second `ordinalDay` in metering would
 * be `DEF-348`'s shape — one vocabulary with two implementations, correct on
 * the day it is written and drifting after — so the one definition moved to the
 * module both screens already import, and the wizard imports it from here.
 */
export function ordinalDay(day: number, language: string, t: (k: string) => string): string {
  let category = "other";
  try {
    category = new Intl.PluralRules(language, { type: "ordinal" }).select(day);
  } catch {
    // An unknown or malformed locale must not break a settings screen; the
    // bare number is always readable.
    return String(day);
  }
  return `${day}${t(`ordinal.suffix.${category}`)}`;
}

/** A18 §6, identically in every tab whose own GET answered 403. */
export function SettingsDenied(props: { helper: string }) {
  const navigate = useNavigate();
  const tenantPath = useTenantPath();
  return (
    <PermissionDenied helper={props.helper} onBack={() => navigate(tenantPath(DASHBOARD_ROUTE))} />
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-TEN-009@178c282 (story+rules snapshot hash — EP-TEN-07; co-packets EP-TEN-05@0733260 · EP-TEN-06@53479d6 · EP-TEN-08@80cdedf · EP-IDN-04@493ea2f)
// generated: 2026-08-09 by story-coder v1 (W0 Settings screens lane) · AMENDED 2026-08-10 by story-coder v1 (path-tenancy lane — PO ruling 2026-08-10: SPA `/{tenant}/…`, API `/api/{tenant}/…`)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: trace_lint✔ run_gates✔ (11 PASS · 0 FAIL · 1 SKIP) tsc✔ eslint✔ vitest 228 passed / 71 todo across 28 files✔ (144+40 baseline unchanged; this packet adds 84 passing + 31 todo — the todos are browser/journey, server-enforcement and unwired-endpoint scope) · 2026-08-10 path-tenancy re-run: tsc✔ eslint✔ vitest 529 passed / 134 todo across 44 files✔ (509 passed / 132 todo was the pre-lane baseline — the suite grew, nothing was dropped) · vite build✔ · run_gates 11 PASS · 0 FAIL · 1 SKIP · trace_lint✔
// exceptions: none
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
