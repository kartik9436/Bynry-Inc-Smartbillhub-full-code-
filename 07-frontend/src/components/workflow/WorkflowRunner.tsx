// ── Trace ──────────────────────────────────────────────
// Change:   CR-023 — the ETL runner shell, ONE implementation with `target`
//           parameterised (design B15 §11 WFL-01.*)
// Rules:    BR-SHL-044 (ONE page header for every screen, workflows included) ·
//           BR-SHL-018 (rail semantics) · B14 rule 1 (the header's `←` names
//           where it EXITS; the footer's `← Back` means previous step) ·
//           B14 rule 2 (one page header) · B14 rule 3 (numbered rail +
//           wizard-actions footer) · B14 rule 4 (`Verb →` advances,
//           `Verb ✓` commits) · B14 rule 5/6 (two sizes; the danger tier on the
//           commit that writes) · B14 rule 21 (Tailwind)
// Impacts:  components/workflow/** — the screens that mount this are the
//           metering lane's (PRM-01/PRM-01U/PRM-04) and are NOT built here.
// ───────────────────────────────────────────────────────
import { useEffect } from "react";
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";

import { useTenantPath } from "@/routing/tenantPath";

import { Button } from "@/components/Button";
import { useLeaveGuard } from "@/components/LeaveGuard";
import { PageHeader } from "@/components/PageHeader";
import { Kicker } from "@/components/TextBits";

import { StageBar } from "./StageBar";
import { WORKFLOW_STAGES, type WorkflowKind } from "./kinds";
import * as WF from "./workflowKit";

/**
 * The shell that composes the kit: back link, kicker, title, sub-line, the
 * stage bar, the stage body, and the two-action footer.
 *
 * ⚠ ONE IMPLEMENTATION, `kind` PARAMETERISED — that is the whole deliverable.
 * r10 opens this same runner for premises, units, accounts, reads, lockbox
 * payments, bank statements, cost inputs, meters, sub-meters, devices and
 * parts, and this product's two existing import wizards had already diverged
 * before the third arrived. Everything that differs between a premises run and
 * a units run is a catalogue key or a route; the stages, the mapping table, the
 * rules table, the dry run and the receipt are identical. So the tenth workflow
 * costs a `WorkflowKind` object.
 *
 * ⚠ THE PRIMARY NAMES ITS DESTINATION AND THE DESTINATION IS THE STAGE'S, NOT
 * THE CALLER'S. `Transform →`, `Validate →`, `Load →`, `Commit load ✓` come
 * from `WORKFLOW_STAGES` so a runner cannot be mounted with a button that lies
 * about where it goes. B14 rule 4's grammar is the reason the fourth one is a
 * `✓` and the first three are `→`: three navigate and one WRITES.
 *
 * ⚠ AND THE COMMIT TAKES THE DANGER TIER. r10 draws `Commit load ✓` as its
 * ordinary primary. B15 §9 note 4 rules otherwise — *"`Commit load ✓` writes;
 * `Roll back this run` reverses. Both qualify"* for B14 rule 6 — and where r10
 * and a ratified B14 rule disagree, B14 wins with the divergence stamped (the
 * precedent rule 18's 66% → 80% set). An outlined button that fills on hover is
 * not reachable without the colour having changed first, which is the property
 * rule 6 exists for on the one stage that writes.
 *
 * ⚠ THE HEADER IS THE SHARED `PageHeader`, NOT A WORKFLOW HEADER. BR-SHL-044 is
 * explicit that it covers *"every screen, including task pages and workflows"*,
 * and DEF-021 is what eight screens each solving this separately cost.
 *
 * ⚠ STAGE 5 HAS NO FOOTER, AND THAT IS r10's OWN SHAPE. The Result stage's
 * actions — `Go to Premises →`, the two downloads and `Roll back this run` —
 * live inside its body beside the receipt they act on, because three of the
 * four are about the RUN and not about the flow. `WORKFLOW_STAGES[4]` carries
 * `advanceKey: null`, so the absence is declared rather than special-cased.
 */
export interface WorkflowRunnerProps {
  kind: WorkflowKind;
  /** 1-based. */
  stage: number;
  /** The furthest stage advanced into — BR-SHL-018's forward fence. */
  reached: number;
  onStageChange: (stage: number) => void;
  /** The stage body — built by the screen from its own state. */
  children: ReactNode;
  /** Header action, e.g. `Save mapping as template`. */
  headerAction: ReactNode;
  onBack: () => void;
  onAdvance: () => void;
  /** True while the stage cannot be left — a file not yet chosen, errors open. */
  advanceDisabled: boolean;
  /**
   * ⛔ **CR-054 task 15 — AN IRREVERSIBLE CLICK STATES ITS SCOPE.** The PO's
   * ruling made posting PARTIAL (*"we accept what is correct and rejct what i
   * not correct"*), so *"Commit load ✓"* no longer describes what the button
   * does: it files SOME of the rows, and the clerk cannot see how many from the
   * label. Reads passes *"Commit 1,178 rows ✓"*.
   *
   * ⚠ **AN OVERRIDE, NOT A REPLACEMENT OF THE GRAMMAR.** `WORKFLOW_STAGES`
   * still owns the DANGER tier, the `✓` and which stage writes (B14 rules 4 and
   * 6); this replaces only the words, and only when a flow has a figure worth
   * naming. `null`/omitted keeps `advanceKey` exactly as it was, which is what
   * the other six targets do — so this is not an unwired prop (hard-won law 2,
   * G13): reads is its caller and the default is the shipped behaviour.
   */
  advanceLabel?: string | null;
  /**
   * A second footer control beside `← Back` — `Discard this batch` on the reads
   * target, which its blueprint draws on the footer line. Optional; absent
   * leaves every other target's footer exactly as it was.
   */
  footerSecondary?: ReactNode;
  /**
   * A FACT on the footer line, to the left of the primary — "1 reading will
   * post". The blueprint takes the count OFF the commit label and puts it here,
   * for a reason worth keeping: a label is ≤ 3 words and carries no sentence
   * (B14 rule 33), and a count inside the label is what broke the grammar of
   * "Commit 1 rows ✓". Beside the button it can be a sentence.
   */
  footerAside?: ReactNode;
  /**
   * The REASON the primary is disabled, rendered UNDER the footer row.
   * ⚠ **It exists so a refusal arrives BEFORE the click rather than after it.**
   * The reads commit was enabled with the certification unticked, accepted the
   * press, and then answered "Tick the certification before posting the batch."
   * BR-SHL-025: a disabled control owes the reader its reason, where they are
   * looking.
   */
  footerNote?: ReactNode;
}

export function WorkflowRunner({
  kind,
  stage,
  reached,
  onStageChange,
  children,
  headerAction,
  onBack,
  onAdvance,
  advanceDisabled,
  advanceLabel = null,
  footerSecondary = null,
  footerAside = null,
  footerNote = null,
}: WorkflowRunnerProps) {
  const { t } = useTranslation();
  // ⚠ **THE BACK LINK MUST CARRY THE TENANT, AND WHEN IT DID NOT IT BROKE THE
  // WHOLE APPLICATION (`DEF-532`, critical).** `kind.returnTo` is a bare
  // `/premises`; passed straight to `backTo`, clicking the arrow navigated
  // there, the shell read **"premises" as the tenant slug** (PO ruling
  // 2026-08-10: the tenant is the FIRST url segment), and from that moment
  // every request went to `/api/premises/...` and returned not-found — so
  // Settings, Accounts and every other screen rendered a failure. The PO found
  // it on the deployed build at `/premises/settings/security`.
  //
  // Every other page in the product already does this (`tenantPath(ROUTE)` in
  // `PremisesDetailPage`, `UnitDetailPage`, `AssetDetailPage` …). The kit was
  // the one place that did not, because it was written before it had a mount.
  const tenantPath = useTenantPath();
  const current = WORKFLOW_STAGES[stage - 1];
  // ⚠ NOT named `count`: i18next treats a `count` interpolation as a PLURAL
  // selector and starts hunting for `_one` / `_other` variants of the key.
  const total = WORKFLOW_STAGES.length;
  // Stage 1's sub-line is the KIND's; every other stage's is the stage's own.
  //
  // ⛔ DEF-624 — `current?.blurbKey ?? kind.extractBlurbKey` WAS WRITTEN FOR
  // THE FIRST `null` AND THERE ARE TWO. `WORKFLOW_STAGES` declares
  // `blurbKey: null` at index 0 (stage 1, which borrows the kind's) AND at
  // index 4 (stage 5, the receipt, which has none). The coalesce could not
  // tell them apart, so under *"Loaded. Here's the receipt."* the runner
  // printed the EXTRACT blurb — *"Upload the account file. Nothing is written
  // until you commit at stage four."* — after the write, on every target.
  //
  // It survived because every check it could have failed passes on it:
  // `WorkflowRunner.test.tsx` asserts the keys EXIST, which a fallback between
  // two existing keys satisfies by construction, and CR-023's walkthrough
  // stopped at stage 4 and never saw stage 5. A browser reaching the receipt
  // is what found it.
  //
  // So the fallback is now asked the question it was always meant to ask —
  // *"is this stage 1?"* — and a stage that declares no sub-line renders none.
  // No new copy: the receipt's own heading already says where the operator is.
  const blurbKey = stage === 1 ? kind.extractBlurbKey : (current?.blurbKey ?? null);
  // ⛔ **CR-054 task 19 — THE TWO STAGE STRINGS THAT ARE A CLAIM ABOUT THE
  // TARGET, RESOLVED PER KIND.** Stage 2's sub-line promised a saved mapping
  // template and stage 4's heading promised a dry run; reads keeps no mapping
  // (BR-MET-032) and runs no dry run, so on that target both were false — the
  // second of them directly above the danger-tier control that writes. Same
  // shape as `rollbackBody` (DEF-623), for the same reason: in a kit
  // parameterised by target, an UNparameterised string is a claim about one
  // target that every other target repeats.
  //
  // ⚠ KEYED OFF THE STAGE'S OWN `id`, NEVER OFF `stage === 2`. The rail's
  // numbering is data (`WORKFLOW_STAGES`) and a magic index would silently
  // point at the wrong stage the day a sixth is declared.
  const titleCopy = current?.id === "load" ? kind.loadTitle : null;
  const blurbCopy = current?.id === "transform" ? kind.transformBlurb : null;
  // ⚖️ **`CR-096-BRC02` — THE TARGET'S OWN HEADS, WHERE IT DECLARES THEM.**
  // `kind.own` is optional and every field inside it is optional, so a kind
  // that declares none resolves to exactly the expressions above and renders
  // byte-for-byte what it renders today. See `WorkflowOwnCopy`.
  const own = current === undefined ? undefined : kind.own?.stages?.[current.id];
  // `undefined` = not declared, fall through. `null` = declared as ABSENT, draw
  // nothing — the two answers a coalesce cannot tell apart, which is the exact
  // shape of DEF-624 recorded above, so they are asked separately.
  const ownBlurbDeclared = own !== undefined && "blurb" in own;

  // ⚠ **`DEF-SHL-10001` — THE LEAVE-PAGE GUARD, AND A RUN KEEPS NO DRAFT.**
  // Every stage before the result lives in the page's own state, so leaving
  // loses it: the popup says so and offers no save (PO 2026-10-07). It arms on
  // a touch or once a stage has been passed, and lets go on the result stage —
  // the one stage with no footer, because the load has been written by then.
  const finished = current !== undefined && current.advanceKey === null;
  const guard = useLeaveGuard({ dirty: reached > 1, draft: null });
  useEffect(() => {
    if (finished) guard.release();
  }, [finished]);

  return (
    <div
      className={WF.FRAME}
      data-workflow="runner"
      data-kind={kind.id}
      data-stage={stage}
      {...guard.touch}
    >
      {guard.element}
      <PageHeader
        kicker={t(kind.kickerKey)}
        title={
          kind.own?.pageTitle === undefined
            ? t("workflow.title")
            : t(kind.own.pageTitle.key, { defaultValue: kind.own.pageTitle.en })
        }
        backTo={{ to: tenantPath(kind.returnTo), label: t(kind.returnLabelKey) }}
        secondaryActions={headerAction}
      />

      <StageBar
        stages={WORKFLOW_STAGES}
        current={stage}
        reached={reached}
        onSelect={onStageChange}
        promise={kind.own?.railPromise}
      />

      <div className={WF.STAGE_HEAD} data-workflow="stage-head">
        <Kicker as="div">
          {t("workflow.stageOf", {
            n: stage,
            total,
            name: current === undefined ? "" : t(current.labelKey),
          })}
        </Kicker>
        <h2 className={WF.STAGE_TITLE}>
          {current === undefined
            ? ""
            : own?.title !== undefined
              ? t(own.title.key, { defaultValue: own.title.en })
              : titleCopy === null
                ? t(current.titleKey)
                : t(titleCopy.key, { defaultValue: titleCopy.en })}
        </h2>
        {ownBlurbDeclared ? (
          own?.blurb != null && (
            <p className={WF.STAGE_BLURB}>{t(own.blurb.key, { defaultValue: own.blurb.en })}</p>
          )
        ) : blurbCopy !== null ? (
          <p className={WF.STAGE_BLURB}>{t(blurbCopy.key, { defaultValue: blurbCopy.en })}</p>
        ) : (
          blurbKey !== null && <p className={WF.STAGE_BLURB}>{t(blurbKey)}</p>
        )}
      </div>

      <div data-workflow="stage-body">{children}</div>

      {current !== undefined && current.advanceKey !== null && (
        <div
          className={WF.FOOTER}
          data-workflow="footer"
          // The footer's own acts — Cancel on stage 1, a stage's commit — are
          // deliberate; only leaving through the app frame is asked about.
          onClickCapture={() => guard.deliberately(() => undefined)}
          data-writes={current.writes ? "true" : "false"}
        >
          <Button variant="secondary" onClick={onBack}>
            {stage === 1 ? t("workflow.cancel") : t("workflow.back")}
          </Button>
          {/* ⚖️ **`CR-096-BRC02` — A SECOND, NON-ADVANCING FOOTER CONTROL.**
              The Meter Reads blueprint draws `Discard this batch` on the footer
              line beside `← Back` at stages 3 and 4, where a clerk deciding
              whether to go on is looking. It was rendered BELOW the runner
              entirely, outside the frame. Optional, so every other target's
              footer is unchanged. */}
          {footerSecondary}
          {footerAside !== null && (
            <span className="ml-auto self-center text-sm text-text" data-workflow="footer-aside">
              {footerAside}
            </span>
          )}
          <Button
            variant={current.writes ? "danger" : "primary"}
            disabled={advanceDisabled}
            onClick={onAdvance}
          >
            {advanceLabel ?? t(current.advanceKey)}
          </Button>
        </div>
      )}
      {current !== undefined && current.advanceKey !== null && footerNote !== null && (
        <p className={`${WF.STAGE_BLURB} text-right`} data-workflow="footer-note" role="status">
          {footerNote}
        </p>
      )}
    </div>
  );
}
