// ── Trace ──────────────────────────────────────────────
// Change:  Finance blueprint `P5.9` (p067–p068) — **6·1 becomes a CLOSE, not a
//          board.** Reported verbatim by the Product Owner: *"as user i dont
//          understand this screen at all"*. `P5.10` — the amounts the checklist
//          builder was already computing and throwing away.
// Rules:   B14 rule 42 (the screen is built from the DRAWING as an image;
//          extracted text is an index) · rule 44 (the drawing says WHAT is on
//          the screen and how it is arranged; our token scale, spacing and
//          component kit say HOW it is built, and win) · rule 43 (a piece of UI
//          is a COMPONENT — this file exists so the two steps are not 120 lines
//          inline in a 1,096-line page) · rule 40 (the page-head title is 32px
//          on every screen) · rule 21 (Tailwind utilities; this file is on
//          `route-b-migrated.txt`) · rule 31 (no database id is ever a visible
//          value) · rules 32/33 (a description budget, and RATIONALE is ZERO
//          words on screen) · rule 36 (layout from the captured pack, style
//          from r10, the kit is how you comply) · BR-LED-006 (the checklist) ·
//          BR-LED-018 (WARN + CONFIRM — a reason always gets through) ·
//          BR-SHL-025 (a figure this deployment cannot state travels WITH its
//          reason) · CLAUDE.md hard rule 2 (money DISPLAYS to 2 decimals)
// Tests:   src/features/ledger/CloseView.dom.test.tsx
// Impacts: src/features/ledger/CloseExportPage.tsx (renders this in place of
//          the two panels it drew) · 10-scripts/po20260924_close_view_walkthrough.mjs
// ───────────────────────────────────────────────────────
//
// ╔══════════════════════════════════════════════════════════════════════════╗
// ║  WHAT WAS THERE, AND WHY A PERSON COULD NOT READ IT                      ║
// ╚══════════════════════════════════════════════════════════════════════════╝
//
// Photographed at 1440 before anything was changed
// (`p5-9-close-before.png`), and the blueprint's own TODAY line on p069 says
// the same thing in eleven words: *"Three system-side panels on one screen,
// headed Finance; no doors on any checklist row; no amounts."*
//
//   · the page head read **Finance** — not which month, not what was left;
//   · the first panel was headed *Before you close*, which is a BOARD: seven
//     facts with no act attached to any of them;
//   · nothing on a not-done row said where to go and fix it;
//   · no row said what it was worth, so *Accruals posted ○* could have meant
//     five minutes or a day;
//   · and one row rendered the raw string `unpaid_cost_accrual` to a clerk
//     (`DEF-LED-6600`, filed before this was written).
//
// **The redraw is two numbered steps.** A close is a job with an order — finish
// the month, then close it — and the drawing says so in its own bands: *STEP 1
// · FINISH SEPTEMBER* over the checklist, *STEP 2 · CLOSE IT* over the button.
// Every unfinished row then carries a door, which p068 item 4 calls *"the
// change that makes this usable"*.
//
// ╔══════════════════════════════════════════════════════════════════════════╗
// ║  WHERE THIS DELIBERATELY DIFFERS FROM THE DRAWING — B14 RULE 44          ║
// ╚══════════════════════════════════════════════════════════════════════════╝
//
// Rule 44, ratified 2026-09-24: *the drawing says WHAT is on the screen and how
// it is arranged; our token scale, spacing and component kit say HOW it is
// built and win every time.* Four differences, each one of those:
//
//   1 · **`PlainTable`, not `DataTable`.** p068's components table names
//       `DataTable ×2` and its own FILTER CRITERIA table says *"TABLE CONTROLS
//       — None needed, both lists are bounded"*. Those two cannot both be
//       honoured: `DataTable` brings a search box, a `+ Filter`, a column
//       chooser and a pager, none of which is drawn and all of which would be
//       controls the drawing does not show. `PlainTable` is the kit's bounded
//       table and is what `RevenueArPage`'s tie-outs already use.
//   2 · **The drawn FIGURES are not built to** (rule 37 — a figure in a
//       wireframe is an ILLUSTRATION). `$28,904.22` against *All bills issued*
//       is drawn; billing publishes no such read, so that row states its
//       absence instead of showing a number nobody computed.
//   3 · **The drawn ROW LABELS are not changed to match.** The drawing writes
//       *All bills issued*, *Tax filed*, *Supplier invoices matched*; ours are
//       `BR-LED-006`'s own names, already in eleven catalogues. p069's TASK
//       line scopes this work to *"P5.9 the steps and the doors · P5.10 the
//       amounts"* and says nothing about renaming, so nothing is renamed.
//   4 · **Spacing and type come from the scale**, not from the drawing's
//       pixels — which is rule 44's whole sentence.
//
// ⚠ **THE ONE THING NOT BUILT HERE, SAID PLAINLY: the `Close · Export` view
// switch at p068 item 1 and the `↺ reopen` row action at item 6 are `P4.12`
// and `P3.2`, sibling lanes' tasks in this same file.** This component draws
// neither and leaves no placeholder for either — a stub control onto an
// unbuilt view is hard-won law 2's dead UI, and a lane landing `P4.12`
// should add the switch here rather than find a disabled one waiting.
import { useTranslation } from "react-i18next";

import { AbsentFigure } from "@/components/AbsentFigure";
import { BandHeading } from "@/components/BandHeading";
import { Button } from "@/components/Button";
import { MoneyCell } from "@/components/MoneyCell";
import { Panel } from "@/components/Panel";
import { StatusPill } from "@/components/StatusPill";
import { InlineLinkTo, PlainTable } from "@/components/Surfaces";
import { BILLING_ROUTE } from "@/features/billing/billingShared";
import { useTenantPath } from "@/routing/tenantPath";

import type { ReactNode } from "react";

import type {
  CloseChecklistItem,
  CloseChecklistResponse,
  ClosedPeriodRow,
} from "@/api/endpoints";
import { FINANCE_ROUTE } from "./financeShared";

/**
 * WHERE EACH UNFINISHED ROW SENDS A CLOSER — p068 item 4, *"every unfinished
 * item links to the screen that clears it"*.
 *
 * ⚠ **A DOOR IS AN ADDRESS AND A SCREEN ID, NEVER A CODE ON SCREEN** (B14 rule
 * 31). The key is the server's item code and it is used to LOOK UP a
 * destination; it is never rendered. The `label` is a catalogue key, so the
 * words are the catalogue's and the grammar is B14 rule 4's `Verb →`.
 *
 * ⚠ **ONE MAP, NOT A CONDITIONAL PER ROW.** CLAUDE.md's hard-won law on
 * hand-typed lists is why: the service list is typed out in two places and an
 * eleventh service silently never appears. An item with no entry here draws NO
 * door rather than a dead one — which is the honest answer for a row whose
 * fixing screen does not exist, and it is what `runs_issued` gets until
 * billing has a runs list to point at.
 */
const FIX_IT: Record<string, { to: string; label: string }> = {
  runs_issued: { to: BILLING_ROUTE, label: "finance.close.fix.runs_issued" },
  batches_reconciled: {
    to: `${FINANCE_ROUTE}/deposits`,
    label: "finance.close.fix.batches_reconciled",
  },
  bank_rec_current: {
    to: `${FINANCE_ROUTE}/deposits`,
    label: "finance.close.fix.bank_rec_current",
  },
  accruals_posted: {
    to: `${FINANCE_ROUTE}?view=accruals`,
    label: "finance.close.fix.accruals_posted",
  },
  unbilled_accrual: {
    to: `${FINANCE_ROUTE}?view=accruals`,
    label: "finance.close.fix.unbilled_accrual",
  },
  unpaid_cost_accrual: {
    to: `${FINANCE_ROUTE}/cost-of-service`,
    label: "finance.close.fix.unpaid_cost_accrual",
  },
  remittance_recorded: { to: `${FINANCE_ROUTE}/taxes`, label: "finance.close.fix.remittance_recorded" },
};

/**
 * The tone a checklist item renders in. THREE states, deliberately: `unknown`
 * is neutral, not a red ✗ and never a green ✓ — the register that would answer
 * lives in another module and no read is published.
 */
export function checklistTone(state: string): "success" | "warning" | "neutral" {
  if (state === "complete") {
    return "success";
  }
  return state === "unknown" ? "neutral" : "warning";
}

/**
 * ⚠ **ENGLISH FOR A ROW WHOSE CATALOGUE KEY HAS NOT LANDED — AND IT IS THE
 * DEFECT THIS SCREEN SHIPPED WITH (`DEF-LED-6600`).**
 *
 * The row label is a DYNAMIC key (`finance.close.item.<code>`), so i18next has
 * nothing to fall back to and renders **the key itself**. A clerk read
 * `unpaid_cost_accrual` on the live month-close screen from 2026-09-02 until
 * today, because the seventh checklist item was added to `apps/ledger/close.py`
 * and neither the eleven catalogues nor this map moved with it. `tsc`, every
 * test and every gate were green over it — a missing entry here is not a
 * missing-key failure, it is a key rendered as a word.
 *
 * All seven codes are listed, not just the one that was missing, so the map
 * answers for the whole set rather than for whichever row happens to be new.
 * The catalogue still wins wherever it has the key, and
 * `CloseView.dom.test.tsx` asserts this map covers the server's own tuple.
 */
export const CHECKLIST_LABEL_FALLBACK: Record<string, string> = {
  runs_issued: "Bill runs issued",
  batches_reconciled: "Deposit batches reconciled",
  bank_rec_current: "Bank reconciliation up to date",
  accruals_posted: "Accruals reversed",
  unbilled_accrual: "Unbilled revenue accrued",
  unpaid_cost_accrual: "Supplier costs accrued",
  remittance_recorded: "Tax remittance recorded",
};

/**
 * WHAT A ROW IS WORTH — `P5.10`, and the four answers are four different facts.
 *
 * ⚠ **`null`, `0.00` AND *we cannot tell* ARE NOT THE SAME THING** (DEF-127,
 * BR-SHL-025). In order:
 *
 *   1 · the item could not be measured → `AbsentFigure`, which states the
 *       absence in words rather than drawing a blank a reader cannot tell from
 *       a figure nobody looked at;
 *   2 · a MONEY figure → `MoneyCell`, which displays two decimals off four
 *       stored (hard rule 2);
 *   3 · a COUNT → the item's own plural sentence from the catalogue;
 *   4 · nothing outstanding → **empty**, deliberately. The STATE column has
 *       already said *Done*, and a `$0.00` beside a tick reads as a
 *       measurement somebody took rather than as nothing to measure.
 */
function Worth(props: { item: CloseChecklistItem; currency: string }) {
  const { t } = useTranslation();
  const { item } = props;
  if (item.state === "unknown") {
    return (
      <AbsentFigure
        label={t("finance.close.notMeasured")}
        reason={t("finance.close.itemUnknown")}
      />
    );
  }
  if (item.amount !== null && item.amount !== undefined) {
    return <MoneyCell amount={item.amount} currency={props.currency} />;
  }
  if (item.outstanding !== null && item.outstanding > 0) {
    return <>{t(`finance.close.outstanding.${item.code}`, { count: item.outstanding })}</>;
  }
  return null;
}

/**
 * **6·1 Close** — the month, what is left of it, and the two steps that finish
 * it.
 *
 * The caller owns the data and the act; this owns the shape. `onClose` opens
 * the confirm dialog that `BR-LED-018` requires — a close is never silent and
 * never a lockout, and the reason always gets through.
 */
export function CloseView(props: {
  checklist: CloseChecklistResponse;
  currency: string;
  /**
   * ⚠ **THE `↺ reopen` ACTION IS `P3.2`'s AND IT IS A RENDER PROP FOR THAT
   * REASON.** p068 item 6 draws an ACTIONS column on the closed-month table,
   * and a sibling lane built the act — the dialog, the role gate, the
   * handed-over check — while this component was being written. Taking it over
   * would have been this lane re-implementing another's work; leaving the
   * column out would have dropped it. So the drawn COLUMN is here and what
   * goes in a cell is the page's, which is also where the reopen state has to
   * live.
   *
   * Absent draws no column at all, so a caller with no action does not get an
   * empty one.
   */
  rowActions?: (row: ClosedPeriodRow) => ReactNode;
  /**
   * The month the head names, so step 2's button can name it too — the drawing
   * puts `Close September ✓` on it, which is B14 rule 4's commit grammar
   * (`Verb ✓`). `null` when the month cannot be read, and the button then falls
   * back to `Close this month`, which is what it has always said.
   */
  month: string | null;
  /**
   * ⚠ **A PERMISSION AND NOTHING ELSE — `DEF-LED-6668`.** `CloseExportPage`
   * used to pass `!checklist.closed` into this, so a System Admin who had just
   * closed September read *"Your role cannot close an accounting period."* on
   * the button they had pressed a second earlier. The two conditions were ORed
   * into one disabled state, so the button was correctly disabled in both
   * cases and only the SENTENCE was wrong — which no gate in this repo can
   * see, because none reads a rendered `title`. The PERIOD's state arrives on
   * `checklist.closed`, which this component already has.
   */
  canClose: boolean;
  onClose: () => void;
}) {
  const { t } = useTranslation();
  const tenantPath = useTenantPath();
  const { checklist } = props;
  const left = checklist.incomplete.length;

  return (
    <>
      {/* ── STEP 1 · FINISH ─────────────────────────────────────────────── */}
      <Panel>
        <BandHeading as="h3">{t("finance.close.step1")}</BandHeading>
        {/* ⚠ **`[&_[data-amount]]:text-right` RATHER THAN `text-right` ON THE
            CELL, AND IT IS NOT A STYLE PREFERENCE — MEASURED IN A BROWSER.**
            `PlainTable` declares `[&_td]:text-left` and `[&_th]:text-left`,
            which is specificity (0,1,1); a bare `text-right` on the cell is
            (0,1,0) and LOSES. The class is genuinely in the DOM, so
            `toContain("text-right")` passes and `getComputedStyle` answers
            `left` — the silent-class trap in its most deceptive form.
            Measured on the running product at 1440: `$13,310.39` came back
            `textAlign: "left"`. An attribute selector is (0,2,0) and wins on
            specificity rather than on source order, which is the part a
            utility framework does not guarantee. `!important` is forbidden. */}
        <PlainTable className="fin-table [&_[data-amount]]:text-right">
          <thead>
            <tr>
              <th scope="col">{t("finance.close.col.what")}</th>
              <th scope="col">{t("finance.close.col.state")}</th>
              <th scope="col" data-amount="">
                {t("finance.close.col.amount")}
              </th>
              <th scope="col">{t("finance.close.col.fixIt")}</th>
            </tr>
          </thead>
          <tbody>
            {checklist.items.map((item: CloseChecklistItem) => {
              const door = item.complete ? undefined : FIX_IT[item.code];
              return (
                <tr key={item.code}>
                  <th scope="row" className="font-body font-normal">
                    {t(`finance.close.item.${item.code}`, {
                      defaultValue: CHECKLIST_LABEL_FALLBACK[item.code] ?? item.code,
                    })}
                  </th>
                  <td>
                    <StatusPill tone={checklistTone(item.state)}>
                      {t(`finance.close.state.${item.state}`)}
                    </StatusPill>
                  </td>
                  <td data-amount="" className="tabular-nums">
                    <Worth item={item} currency={props.currency} />
                  </td>
                  <td>
                    {door !== undefined && (
                      <InlineLinkTo to={tenantPath(door.to)}>{t(door.label)}</InlineLinkTo>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </PlainTable>
      </Panel>

      {/* ── STEP 2 · CLOSE IT ───────────────────────────────────────────── */}
      <Panel>
        <BandHeading as="h3">{t("finance.close.step2")}</BandHeading>
        {/* BR-LED-018's WARN, said before the button rather than after it: the
            close is NOT blocked, it demands a typed reason that is audited.
            Two short sentences rather than one long one — B14 rule 33, *"two
            sentences of six beat one sentence of twelve"*. */}
        {/* ⚠ **A CLOSED MONTH STATES THE CLOSE, NOT WHAT IS STILL UNDONE**
            (`DEF-LED-6668`). This read `warn` over a closed September —
            *"3 items are not done. You can still close…"* — which is an
            instruction for an act that has already happened. */}
        <p className="fin-absent-reason" role="note">
          {checklist.closed
            ? t("finance.close.done")
            : left === 0
              ? t("finance.close.ready")
              : t("finance.close.warn", { count: left })}
        </p>
        <Button
          variant="primary"
          disabled={checklist.closed || !props.canClose}
          /* ⚠ **TWO REASONS, ASKED IN THE ORDER A CLERK MEETS THEM.** The
             month being closed is the commoner one and is about the BOOKS;
             the role is about the PERSON. One sentence for both is how
             `DEF-LED-6668` told a System Admin their role was at fault for a
             month they had just closed themselves. */
          title={
            checklist.closed
              ? t("finance.close.done")
              : props.canClose
                ? undefined
                : t("finance.close.roleReason")
          }
          onClick={props.onClose}
        >
          {/* p068's PRIMARY ACTION row: `Close September ✓, in step 2`. B14
              rule 4 — `Verb ✓` COMMITS, and this is the irreversible one on
              the screen. Naming the month on the button as well as in the head
              is the drawing's, and it is what a clerk reads last before they
              press it. */}
          {props.month === null
            ? t("finance.close.action")
            : t("finance.close.actionMonth", { month: props.month })}
        </Button>
        {/* ⚠ THE GENERAL CHANNEL FOR A FIGURE THE BOOKS WILL NOT STATE. It is
            EMPTY on a close today — the role-gate marker that used to render
            here was retired when the PO ruled the gate on 2026-09-24 — and the
            `.map` stays because the next gap belongs in it. */}
        {checklist.unavailable.map((gap) => (
          <AbsentFigure key={gap.code} label={t("finance.close.notMeasured")} reason={gap.detail} />
        ))}
      </Panel>

      {/* ── CLOSED MONTHS ───────────────────────────────────────────────── */}
      {checklist.closed_periods.length > 0 && (
        <Panel>
          <BandHeading as="h3">{t("finance.close.historyTitle")}</BandHeading>
          <PlainTable className="fin-table">
            <thead>
              <tr>
                <th scope="col">{t("finance.close.col.month")}</th>
                <th scope="col">{t("finance.close.col.closedOn")}</th>
                <th scope="col">{t("finance.close.col.closedShort")}</th>
                {props.rowActions !== undefined && (
                  <th scope="col">{t("finance.close.col.actions")}</th>
                )}
              </tr>
            </thead>
            <tbody>
              {checklist.closed_periods.map((row) => (
                <tr key={`${row.period.start}|${row.period.end}`}>
                  <th scope="row" className="font-body font-normal">
                    {t("reports.rollup", { from: row.period.start, to: row.period.end })}
                  </th>
                  <td>
                    <StatusPill tone={row.status === "closed" ? "success" : "neutral"}>
                      {t(`finance.close.periodState.${row.status}`, { defaultValue: row.status })}
                    </StatusPill>
                  </td>
                  <td>
                    {/* J19 step 1: the reason AND the incomplete-item snapshot
                        are recorded ON the close and shown here — recomputing
                        them later answers a different question. */}
                    {row.incomplete_items.length > 0
                      ? t("finance.close.snapshot", { count: row.incomplete_items.length })
                      : null}
                  </td>
                  {props.rowActions !== undefined && <td>{props.rowActions(row)}</td>}
                </tr>
              ))}
            </tbody>
          </PlainTable>
        </Panel>
      )}
    </>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: Finance blueprint `05-prototype/07 Finance Blueprint.pdf` p067–p069 (6·1 Close, rendered at scale 3 and READ AS AN IMAGE per B14 rule 42) · `P5.9` · `P5.10` · DEF-LED-6600
// generated: 2026-09-24 by lane FIN-P5
// checklist: A✔ B✔ C✔ D=n/a E✔ F✔ G✔ H=n/a (no money math — `amount` is the server's own figure and is only FORMATTED here, 4 stored to 2 displayed)
// gates: vitest src/features/ledger/CloseView.dom.test.tsx · tsc · walked in a browser at 1440 and 1280 against p067, before and after (`p5-9-close-before.png` / `p5-9-close-after.png`)
// exceptions: (1) `PlainTable` rather than the drawn `DataTable` — p068's own TABLE CONTROLS row says none are needed and `DataTable` brings four; B14 rule 44 gives the kit the HOW · (2) the drawn figures and the drawn row labels are NOT built to — rule 37 makes a drawn figure an illustration, and p069's TASK line scopes this to the steps, the doors and the amounts · (3) the `Close · Export` switch and the `↺ reopen` action are drawn on p068 and are NOT built here — they are `P4.12` and `P3.2`, and a placeholder onto an unbuilt view is dead UI
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
