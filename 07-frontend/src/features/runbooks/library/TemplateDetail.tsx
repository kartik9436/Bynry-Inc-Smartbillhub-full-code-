// ── Trace ──────────────────────────────────────────────
// Story:   US-RBS-018 (EP-RBS-01) — CR-075 wave D task D3.
// Screens: RBS-002.2 (`S148.2`) — one template, before adding, at
//          `/{tenant}/runbooks/templates/{key}`.
// Rules:   `BR-RBS-002` (a Check is CONSTRUCTED with no ports — the capability
//          is ABSENT, not withheld) · `US-RBS-002` (*What it can touch* is
//          derived from `ports[]` and from nothing else) · B14 rule 2 (page
//          head) · rule 4 (one primary action) · rule 31 · rule 32 · rule 33.
// Tests:   TemplateDetail.dom.test.tsx ·
//          10-scripts/render-checks/rbs-d-the-library.mjs
// Defects: DEF-RBS-4309 (the step labels, *Reads* and *Runs for* are on no
//          payload) · DEF-CWP-3925 (a fixture that cannot tell a working link
//          from a broken one).
// ───────────────────────────────────────────────────────
// *WHAT IT CAN TOUCH* IS THE SCREEN. EVERYTHING ELSE IS CONTEXT.
//
// The frame says so in its own design note: *"'What it can touch' is the first
// thing on this screen after the name, and for a Check it always reads Nothing.
// That single table is what a clerk needs before adding anything."*
//
// ══════════════════════════════════════════════════════════════════════════
// THE DERIVATION, AND THE EXACT LINE THIS FILE WILL NOT CROSS
// ══════════════════════════════════════════════════════════════════════════
// `08-screen-layouts.md`: *"That is the ports allow-list rendered, and it is why
// a Check can be trusted: the screen states capability, not intention."*
//
// **What is derivable here with no map at all:** a Check holds ZERO ports
// (`BR-RBS-002`, enforced at CONSTRUCTION), so it writes nothing and sends
// nothing, and `writes_nothing` carries that one fact from the server. Two rows,
// both *Nothing*, and the emptiness is the safety promise rather than an
// omission.
//
// **What is NOT derivable, and is therefore not invented:** WHICH of the
// thirteen ports counts as a *send*, a *charge* or a *change*. The port →
// capability map is written down nowhere in the pack — the wave C lane measured
// it (`12-the-contract.md` §8 names thirteen ports; `RBS-004.1` draws three
// rows; one of the three, *Change bills*, maps to no port at all) and refused to
// invent it for the same two reasons that apply here: it would resolve an
// unstated design question by choosing a value, and it would break `RB-020`,
// because a fourteenth port would then need a frontend change.
//
// ⚠ **SO AN ACTION'S TABLE IS NOT DRAWN AND THE SCREEN SAYS SO IN SIX WORDS.**
// It is not a blank table and it is not a guess. **No Action ships today** — the
// registry holds one runbook, *Can we bill?*, a Check — so this branch is
// reachable only by the wave that binds a port, which is the wave that will also
// have the map. The alternative, a table of *Yes* pills with no nouns, would be
// the most dangerous shape this product has: a safety statement that says
// nothing while looking like one that says something.
//
// ══════════════════════════════════════════════════════════════════════════
// TWO REGIONS THE SHEET DRAWS AND THIS SCREEN DOES NOT (`DEF-RBS-4309`)
// ══════════════════════════════════════════════════════════════════════════
//   * **What it does** — a three-step progress list. `templates_page` serves
//     `steps` as an integer COUNT; the LABELS are on `Step` and are not on this
//     payload. The heading is drawn only when the labels arrive, because a
//     heading over nothing is furniture and B14 rule 33 puts rationale at zero
//     words on screen.
//   * **Reads** and **Runs for** — no `reads[]` declaration and no duration
//     estimate exist anywhere in the contract.
//
// Each row is rendered from an OPTIONAL field, so the day the server serves one
// it appears with no change here — and until then it draws nothing at all, never
// a dash and never a placeholder. That is the wave C lane's rule for `Step.why`,
// and the reason is that a placeholder is indistinguishable from a real empty
// value.
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";

import { Button, ButtonLink } from "@/components/Button";
import { PageHeader } from "@/components/PageHeader";
import { StatusPill } from "@/components/StatusPill";
import { PlainTable } from "@/components/Surfaces";
import { tenantPathFrom, useTenant } from "@/routing/tenantPath";

import { categoryLabel } from "./libraryLabels";
import type { TemplateRow } from "./libraryTypes";

export interface TemplateDetailProps {
  template: TemplateRow;
  /** **+ Add to my runbooks** — `POST /runbooks` is task `E1`. REQUIRED, so a
   *  caller that forgets it does not compile (law 2 / `G13`). */
  onAdd: () => void;
}

export function TemplateDetail(props: TemplateDetailProps) {
  const { t } = useTranslation();
  const { template } = props;
  const tenant = useTenant();
  const added = template.state === "added";
  const unavailable = template.state === "unavailable";

  return (
    <main data-screen="RBS-002" data-state="detail" data-template={template.template_key}>
      <PageHeader
        backTo={{
          to: tenantPathFrom(tenant, "runbooks/templates"),
          label: t("runbooks.library.detail.back"),
        }}
        title={template.name}
        rollup={
          // ⚠ ONE SENTENCE AND A CHIP is what `RBS-004.1` does with the same
          // material, and the sentence is the template's purpose — which no
          // payload carries (`DEF-RBS-4309`). So the category travels alone
          // rather than under an invented sentence, and the day the purpose is
          // served it joins it here.
          <span className="flex flex-wrap items-center gap-2">
            {template.description !== undefined &&
              template.description !== null &&
              template.description !== "" && <span>{template.description}</span>}
            <StatusPill tone={template.kind === "check" ? "info" : "danger"}>
              {t(`runbooks.library.kind.${template.kind}`)}
            </StatusPill>
            <span className="text-neutral-600">{categoryLabel(t, template.category)}</span>
          </span>
        }
        primaryAction={
          // ⚠ **ONE PRIMARY, AND WHICH ONE DEPENDS ON THE STATE** (B14 rule 4).
          // The sheet draws `+ Add to my runbooks` because it draws a template
          // that is NOT added. Offering it over one that already is would be a
          // button onto a duplicate; an added template's one useful action is
          // its setup screen, which is `RBS-004` and is live. Stamped in
          // `08-screen-layouts.md`.
          added ? (
            <ButtonLink
              variant="primary"
              to={tenantPathFrom(tenant, `runbooks/${template.template_key}`)}
              data-detail-open=""
            >
              {t("runbooks.library.detail.open")}
            </ButtonLink>
          ) : (
            <Button
              variant="primary"
              disabled={unavailable}
              title={unavailable ? (template.unavailable_reason ?? undefined) : undefined}
              onClick={props.onAdd}
              data-detail-add=""
            >
              {t("runbooks.library.detail.add")}
            </Button>
          )
        }
      />

      <div className="mt-4 grid gap-3.5 [grid-template-columns:repeat(auto-fit,minmax(228px,1fr))]">
        {/* ── Regions 3–4 · What it does ────────────────────────────────────
            Drawn only when the labels are served (`DEF-RBS-4309`). */}
        {template.step_labels !== undefined && template.step_labels.length > 0 && (
          <section data-region="what-it-does">
            <h5 className="m-0 mb-2 text-sm font-extrabold tracking-wider text-neutral-600 uppercase">
              {t("runbooks.library.detail.whatItDoes")}
            </h5>
            <ol className="m-0 list-none border border-divider bg-[white] p-0">
              {template.step_labels.map((label, index) => (
                <li
                  key={label}
                  className="flex items-start gap-3 border-b border-b-divider px-4 py-3 last:border-b-0"
                >
                  <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full border border-neutral-400 text-xs text-neutral-600">
                    {index + 1}
                  </span>
                  <span className="min-w-0 flex-1 text-table text-neutral-700">{label}</span>
                </li>
              ))}
            </ol>
          </section>
        )}

        {/* ── Regions 5–6 · What it can touch ───────────────────────────────
            The first thing on the screen after the name, and for a Check it
            always reads *Nothing*. */}
        <section data-region="what-it-can-touch">
          <h5 className="m-0 mb-2 text-sm font-extrabold tracking-wider text-neutral-600 uppercase">
            {t("runbooks.library.detail.whatItCanTouch")}
          </h5>
          {template.writes_nothing ? (
            <PlainTable>
              <tbody>
                <TouchRow
                  label={t("runbooks.library.detail.writes")}
                  value={
                    <StatusPill tone="success">{t("runbooks.library.detail.nothing")}</StatusPill>
                  }
                />
                <TouchRow
                  label={t("runbooks.library.detail.sends")}
                  value={
                    <StatusPill tone="success">{t("runbooks.library.detail.nothing")}</StatusPill>
                  }
                />
                {/* `Reads` and `Runs for` — served by nothing today. */}
                {template.reads !== undefined && template.reads !== null && (
                  <TouchRow label={t("runbooks.library.detail.reads")} value={template.reads} />
                )}
                {template.runs_for !== undefined && template.runs_for !== null && (
                  <TouchRow
                    label={t("runbooks.library.detail.runsFor")}
                    value={template.runs_for}
                  />
                )}
              </tbody>
            </PlainTable>
          ) : (
            // Six words, a FACT rather than a rationale (B14 rule 33). The
            // reason lives in this file's header and in `DEF-RBS-4309`, which
            // is where rationale belongs.
            <p className="m-0 text-base text-neutral-600" data-touch-absent="">
              {t("runbooks.library.detail.touchUnknown")}
            </p>
          )}
        </section>
      </div>
    </main>
  );
}

/**
 * One key–value row: label left, value hard right.
 *
 * ⚠ **JUSTIFIED, NOT TEXT-ALIGNED, AND THE BROWSER IS WHAT SETTLED THAT**
 * (`CR-075` wave C, `rbs-c-setup-renderer.mjs`). `className="text-right"` on the
 * `<td>` does nothing here: `PlainTable` sets `[&_td]:text-left` on the TABLE,
 * which compiles to `.plain td` at specificity (0,1,1) and outranks a plain
 * `.text-right` at (0,1,0). The class IS in the DOM, so `tsc`, eslint and
 * `toContain("text-right")` were all green over a wrong screen — `DEF-974`'s
 * shape with the cascade in place of the compiler. A flex row justified to the
 * end is not text alignment and nothing on the table competes with it.
 */
function TouchRow(props: { label: string; value: ReactNode }) {
  return (
    <tr>
      <th scope="row" className="text-table font-normal text-neutral-700">
        {props.label}
      </th>
      <td className="text-table">
        <span className="flex justify-end">{props.value}</span>
      </td>
    </tr>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-RBS-018 (EP-RBS-01; CR-075 wave D task D3) · BR-RBS-002 · US-RBS-002 · wireframes/RBS-002.2 (sheet + frame) · 08-screen-layouts.md §RBS-002
// generated: 2026-09-06 by the CR-075 wave D D3/D4 build lane
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=n/a(no 🔒 path)
// gates: tsc --noEmit (the LOCAL compiler, never npx) · vitest · routeBUtilities (every utility compiles against the real theme)
// exceptions: the What it does list and the Reads / Runs for rows are ABSENT rather than invented (DEF-RBS-4309); an Action's capability table states its absence in six words rather than drawing a map nobody has written
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
