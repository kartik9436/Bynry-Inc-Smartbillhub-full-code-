// ── Trace ──────────────────────────────────────────────
// Story:   US-RBS-016 · US-RBS-001 · CR-075 wave C task C2.
// Screens: RBS-006 (`S152`), built region by region against
//          `04-docs/05-modules/17-runbooks/wireframes/RBS-006-R1.md` + `.png`.
// Rules:   `BR-RBS-020` (composed at close and FROZEN) · `BR-RBS-021` (the
//          twelve are closed) · `NFR-3` · B14 rules 2, 4, 12, 16, 20, 31, 32.
// Tests:   RunResult.dom.test.tsx · blocks/reportConformance.test.tsx
// Defects: DEF-RBS-4284.
// ───────────────────────────────────────────────────────
// THE RESULT RENDERER. THIRTY-FOUR RUNBOOKS, ONE SCREEN.
//
// It draws a frozen report and knows nothing about any particular runbook.
// `RB-020`'s claim — adding runbook 23 is one Python module and no frontend
// code — is only true while this file stays that way, so **nothing here may
// branch on a runbook key.** If a runbook needs something this cannot draw, the
// answer is to compose the twelve differently, not to special-case it here
// (`BR-RBS-021`: a thirteenth block needs THREE runbooks that cannot be drawn
// without it).
//
// ══════════════════════════════════════════════════════════════════════════
// THE COMPOSITION RULE, WHICH IS THE ONE THING THIS FILE DECIDES
// ══════════════════════════════════════════════════════════════════════════
// `RBS-006-R1` draws SIX regions — page head, KPI strip, chain, toolbar, table,
// pagination footer — while runbook 1's report carries SIX BLOCKS: verdict,
// kpis, chain, breakdown, records, downloads. Those two lists are not the same
// list, and reading the frame beside the report is what settles how:
//
//   * the head's SUBTITLE on the frame is *"3 things stop billing."*, which is
//     the `verdict` block's `count` word for word. So a LEADING verdict block
//     becomes the page head's subtitle and is not drawn again below it —
//     drawing both would print one sentence twice, which is exactly the
//     description budget B14 rule 32 exists to protect (*"too much content -
//     desctiption is too much for clark to read"*, said four times in twenty
//     minutes).
//   * the head's `↓ Findings` ACTION is the `downloads` block. So downloads
//     lift into the header rather than drawing a row of their own.
//   * everything else draws in the body, in the report's own order.
//
// ⚠ **NOTHING IS DROPPED, AND THAT IS THE TEST.** `breakdown` is absent from
// R1's frame — the blockers fixture sells one service, so its per-service table
// is one row — but it is NOT suppressed here: §8.1's whole reason is that a
// service with nothing wrong is still LISTED, so a two-service utility that
// fixes water watches Sewer stay red while Water goes green. A sheet is a
// region list, not the whole screen (39 of the 75 are fragments), so an absent
// region is not an instruction to drop a block. `RunResult.dom.test.tsx`
// asserts every block of the fixture reaches the DOM.
import { useTranslation } from "react-i18next";

import { PageHeader } from "@/components/PageHeader";
import { StatusPill } from "@/components/StatusPill";
import { Button } from "@/components/Button";
import type { PageSize, TableRequestState } from "@/components/tableTypes";

import {
  ActionBlock,
  BreakdownBlock,
  ChainBlock,
  DownloadsBlock,
  FactsBlock,
  KpisBlock,
  RankedBlock,
  ReconciledBlock,
  RecordsBlock,
  RowDecisionsBlock,
  SentenceBlock,
  VerdictBlock,
} from "./blocks";
import type { BlockContext, KpisPayload, ReportBlock, VerdictPayload } from "./blocks/types";
import type { RunResultView } from "./resultTypes";

export interface RunResultProps {
  view: RunResultView;
  ctx: BlockContext;
  /** The `records` block's query. Owned HERE and handed down, because a block
   *  holding its own paging would page a list the screen does not know it is
   *  paging — `09-component-inventory.md`, and the reason `records` waited for
   *  this task. */
  onRecordsQuery: (next: { page: number; per: PageSize; chip: string }) => void;
  /** Re-run. REQUIRED — an optional handler nothing passes is dead UI (law 2,
   *  `G13`'s whole question), and the header's own `rerun` field carries
   *  whether it may fire and why not. */
  onRerun: () => void;
  /** A result file. REQUIRED for the same reason. */
  onDownload: (fileId: string, format: "csv" | "pdf") => void;
  /** A row decision, and an action block's button. Both REQUIRED: no runbook 1
   *  report contains either, and a report that does must not meet a hole. */
  onDecide: (rowId: string, choiceId: string) => void;
  onAct: () => void;
  loading: boolean;
}

/** The leading `verdict` block, which becomes the page head's subtitle. */
function leadingVerdict(report: ReportBlock[]): VerdictPayload | null {
  const first = report[0];
  return first !== undefined && first.block === "verdict" ? first.payload : null;
}

/**
 * The run's DURATION, added to the first KPI strip as its last tile.
 *
 * ⚠ **THE FOURTH TILE `RBS-006-R1` ASKS FOR, AND `DEF-RBS-4336` IS WHAT IT COST
 * TO LEAVE IT OUT.** Region 2 of that wireframe is four tiles — *3 Blockers · 6
 * Warnings · 7 of 10 Steps clear · **12s Took*** — and the engine composes only
 * the first three. It is right not to compose the fourth: a duration is a fact
 * about the RUN (`runbook_runs.started_at` / `finished_at`), not about the
 * result, and `BR-RBS-020` freezes the report at close. So the run fact is
 * added HERE, at render time, where the run row is already in hand.
 *
 * The report itself is never mutated — this returns a new payload — because a
 * past run reopened must draw exactly what it drew that day.
 *
 * It was declared, typed, mapped by the page and documented down to the
 * wireframe region, and read by nothing: hard-won law 2 with the arrow
 * reversed, which is the direction `G13` does not look and `tsc` cannot.
 */
function withTook(payload: KpisPayload, took: string | undefined): KpisPayload {
  if (took === undefined) {
    // Absent while a run is still going. A stated absence is CLOSED by default
    // (B14 rule 32) — no tile rather than a `—` that reads as a measurement.
    return payload;
  }
  return {
    ...payload,
    tiles: [
      ...payload.tiles,
      { id: "took", label: "Took", value: { kind: "text", text: took } },
    ],
  };
}

export function RunResult(props: RunResultProps) {
  const { t } = useTranslation();
  const { view, ctx } = props;
  const { header } = view;

  const verdict = leadingVerdict(view.report);
  const downloads = view.report.filter((b) => b.block === "downloads");
  // Drawn in the body: everything except the two the head consumes.
  const body = view.report.filter(
    (block, index) => block.block !== "downloads" && !(index === 0 && block.block === "verdict"),
  );

  // The records block's request state. `NFR-3` — the page travels to the server
  // and this screen never slices an array.
  const recordsState: TableRequestState = {
    q: "",
    sort: "",
    dir: "asc",
    page: view.records.page,
    per: view.records.per as PageSize,
    filters: {},
  };

  return (
    // ⚠ **A ROOT ELEMENT CARRYING `data-screen`, NOT A BARE FRAGMENT —
    // `DEF-RBS-4332`.** `RunbookSetup.tsx` calls this *"the convention every
    // screen in this product follows and the handle a hold-expiry test or a
    // walkthrough holds on to"*, and this screen — written by the same wave —
    // returned a fragment with nothing to stamp. So `RBS-006` was the one
    // screen every other runbooks screen links TO and the one that could not be
    // recognised from the DOM: a sibling's walkthrough clicked `Watch` on
    // `RBS-001`'s in-flight banner and had nothing to wait for, and weakened
    // itself to an address assertion instead. Nothing went red, because no gate
    // in this repo reads rendered output (hard-won law 6) and every unit test
    // here mounts the component and asserts its own blocks — law 7's shape
    // exactly: each wave checking its own screen at its own address, so *can
    // this screen be named from outside itself* belonged to nobody.
    //
    // `data-runbook` rides along for the same reason it does on `RBS-004`: a
    // check that has found the screen usually needs to know WHICH runbook's
    // result it is looking at.
    <main data-screen="RBS-006" data-runbook={header.runbookName}>
      <PageHeader
        backTo={{ to: header.runbookTo, label: header.runbookName }}
        kicker={header.runbookName}
        title={header.title}
        // ⚠ **THE VERDICT'S WORD GOES IN `status`, AND DROPPING IT WAS
        // `DEF-RBS-4313`.** This composition took `verdict.count` alone and
        // threw away `word`, `tone` and `detail`. On runbook 1 that looked
        // harmless because its count — *"3 things stop billing"* — happens to
        // carry the meaning. On the month-end journal file it does not: the
        // count reads *"1 to fix · 3 months open."* while the WORD is **Ready
        // to import** or **No file**, which are the two states that runbook
        // exists to tell apart. A clerk read the arithmetic and never the
        // answer, on every runbook.
        //
        // `PageHeader.status` is the slot for exactly this — its own docstring:
        // *"The record's state … it renders with the IDENTITY, not in the
        // action row (DEF-966) … r10 puts state in the kicker or the sub-line
        // on every screen it draws."* The verdict IS the run's state.
        status={
          verdict === null ? undefined : (
            <StatusPill tone={verdict.tone}>{verdict.word}</StatusPill>
          )
        }
        // The sub-line stays the count, and now carries the detail when the
        // runbook supplies one — `VerdictPayload.detail` was being dropped too.
        rollup={
          verdict === null
            ? undefined
            : verdict.detail === undefined
              ? verdict.count
              : `${verdict.count} · ${verdict.detail}`
        }
        // Downloads lift into the header, per the composition rule above:
        // `↓ Findings` on `RBS-006-R1` IS the downloads block.
        secondaryActions={downloads.map((block, index) => (
          <DownloadsBlock
            key={`downloads-${index}`}
            payload={block.payload}
            onDownload={props.onDownload}
          />
        ))}
        // B14 rule 4 — ONE primary action on a screen, and here it is Run
        // again. A control the user may not use is drawn DISABLED WITH ITS
        // REASON, never hidden.
        primaryAction={
          header.rerun.enabled ? (
            <Button variant="primary" onClick={props.onRerun}>
              {t("runbooks.result.rerun")}
            </Button>
          ) : (
            <Button variant="primary" disabled title={header.rerun.reason}>
              {t("runbooks.result.rerun")}
            </Button>
          )
        }
      />
      {header.rerun.enabled === false && (
        // ⚠ THE REASON IS RENDERED, NOT ONLY A `title` (`DEF-SHL-4043`). A
        // tooltip opens on hover, after a delay, and NEVER on a touch screen —
        // so for four weeks twenty screens drew a grey button that said nothing
        // while the docstring promised otherwise.
        <p className="state-helper" data-rerun-reason="">
          {header.rerun.reason}
        </p>
      )}

      <div className="flex flex-col gap-6" data-run-result="">
        {body.map((block, index) => {
          const key = `${block.block}-${index}`;
          switch (block.block) {
            case "verdict":
              return <VerdictBlock key={key} payload={block.payload} />;
            case "kpis":
              return <KpisBlock key={key} payload={withTook(block.payload, header.took)} ctx={ctx} />;
            case "chain":
              return <ChainBlock key={key} payload={block.payload} />;
            case "records":
              return (
                <RecordsBlock
                  key={key}
                  payload={block.payload}
                  ctx={ctx}
                  state={recordsState}
                  loading={props.loading}
                  screenId={`RBS-006.${header.runbookName}`}
                  chip={{
                    selected: view.records.chip,
                    onSelect: (chip) =>
                      props.onRecordsQuery({ page: 1, per: recordsState.per, chip }),
                  }}
                  onStateChange={(next) =>
                    props.onRecordsQuery({
                      page: next.page,
                      per: next.per,
                      chip: view.records.chip,
                    })
                  }
                />
              );
            case "breakdown":
              return <BreakdownBlock key={key} payload={block.payload} ctx={ctx} />;
            case "reconciled":
              return <ReconciledBlock key={key} payload={block.payload} ctx={ctx} />;
            case "ranked":
              return <RankedBlock key={key} payload={block.payload} ctx={ctx} />;
            case "sentence":
              return <SentenceBlock key={key} payload={block.payload} />;
            case "facts":
              return <FactsBlock key={key} payload={block.payload} ctx={ctx} />;
            case "action":
              return <ActionBlock key={key} payload={block.payload} onAct={props.onAct} />;
            case "row_decisions":
              return (
                <RowDecisionsBlock
                  key={key}
                  payload={block.payload}
                  ctx={ctx}
                  onDecide={props.onDecide}
                />
              );
            case "downloads":
              // Consumed by the page head above. Unreachable — `body` filters
              // it — and listed so the switch stays EXHAUSTIVE: `tsc` refuses a
              // thirteenth block name here, which is `BR-RBS-021` enforced by
              // the compiler rather than by a reviewer noticing.
              return null;
          }
        })}
      </div>
    </main>
  );
}
