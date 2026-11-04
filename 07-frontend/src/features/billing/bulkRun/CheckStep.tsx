// ── Trace ──────────────────────────────────────────────
// Screen:   S31 · BIL-02 — the bill run, step 2 Check (full width, no aside)
// Drawing:  05-prototype/bulk-bill-run-2026-09-30/09…24-*.png · inventory.md §3, §4
// Story:    US-BIL-037 · US-BIL-038 (the Calculating panel)
// Plan:     15-bulk-bill-run-build-plan.md F7 · F8 · F13
// Rules:    changes rows 20–26, 36, 39, 41 · B14 rules 21, 33, 43, 44
// Defects:  DEF-BIL-8224 (n of N while checking — closed here) · DEF-BIL-8216
//           (the served grouped read — closed here) · DEF-BIL-8219
// ───────────────────────────────────────────────────────
/**
 * CHECK — THE TILES, THE PROBLEM LIST, ONE TAG'S PANE, AND THE STOPS.
 *
 * Four faces, in order of precedence:
 *
 *   1. **Calculating** (image 24) — once Price is pressed, the priced run's job
 *      progress, `n of N` from the job record.
 *   2. **Checking** (image 09) — while the Check JOB runs (`POST …/check`),
 *      `n of N` from its record (`GET …/check`'s `job.progress`, DEF-BIL-8224),
 *      or while the first summary read is in flight.
 *   3. **The stop** (image 10) — the read failed. It names what failed, says
 *      the run is kept, gives the support reference, and offers Try again.
 *   4. **Results** — the five tiles (each a filter), the list, the pane — all
 *      from the SERVER's grouped read (`GET …/check/findings`, DEF-BIL-8216).
 */
import { useEffect, useMemo, useState } from "react";

import type { CheckSummary, CheckTag } from "@/api/bulkRunEndpoints";
import { isApiError, supportRef } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { Button } from "@/components/Button";
import type { Translator } from "@/components/FormModal";
import { KPIStrip } from "@/components/KPIStrip";
import type { KpiTile } from "@/components/KPIStrip";
import { Panel } from "@/components/Panel";

import { Kicker, ProgressPanel, count } from "./bulkRunShared";
import {
  FixAccountPanel,
  ProblemTagList,
  ProblemTagPane,
  READY_TAG,
  ReadyToBillPane,
  firstShownTag,
  tagsByCode,
  visibleTags,
} from "./CheckPanes";
import type { CheckLinks, CheckPaneActions, TileFilter } from "./CheckPanes";
import { PricingCheck } from "./PricingCheck";

/** A utility-wide stop as the server records it on the run (B21): what, who, the reference. */
export interface CheckStopRecord {
  module?: unknown;
  who?: unknown;
  support_ref?: unknown;
}

/** DEF-BIL-8580 — the stop is read from the error envelope: what, who, the reference. */
export function checkStopLines(
  error: unknown,
  t: Translator,
  stop: CheckStopRecord | null = null,
): { what: string; who: string | null; ref: string | null } {
  // DEF-BIL-8510 — the stop names WHAT is down and WHO fixes it, and its
  // reference is the server's own (the one in the log), never a local one.
  if (stop !== null && typeof stop.module === "string") {
    return {
      what: t(`billing.bulkRun.check.down.${stop.module}`, { defaultValue: t("billing.bulkRun.check.stopGeneric") }),
      who: typeof stop.who === "string" ? t(`billing.bulkRun.check.who.${stop.who}`) : null,
      ref: typeof stop.support_ref === "string" ? stop.support_ref : null,
    };
  }
  if (!isApiError(error)) return { what: t("billing.bulkRun.check.stopGeneric"), who: null, ref: null };
  const params = error.params ?? {};
  const served = typeof params.ref === "string" ? params.ref : null;
  const ref = served ?? (error.traceId ? supportRef(error.traceId) : error.sentRef);
  const what = t(error.messageKey, { ...params, defaultValue: t("billing.bulkRun.check.stopGeneric") });
  const who = typeof params.who === "string" ? t(`billing.bulkRun.check.who.${params.who}`) : null;
  return { what, who, ref };
}

export function CheckStop(props: { error: unknown; stop?: CheckStopRecord | null; onRetry: () => void; t: Translator }) {
  const { t } = props;
  const { what, who, ref } = checkStopLines(props.error, t, props.stop ?? null);
  return (
    <Panel as="section" aria-label={t("billing.bulkRun.check.title")} data-check-stop="">
      <div className="bg-danger-100 px-3 py-3 text-base text-danger-700" role="alert">
        <p className="m-0 font-heading font-semibold">
          {what} {t("billing.bulkRun.check.noneChecked")}
        </p>
        <p className="m-0 mt-1">
          {who !== null && `${who} `}
          {t("billing.bulkRun.check.tryLater")}
          {ref !== null && ` ${t("billing.bulkRun.ref", { ref })}`}
        </p>
      </div>
      <div className="mt-4 flex justify-end border-t border-divider pt-4">
        <Button onClick={props.onRetry}>{t("billing.bulkRun.tryAgain")}</Button>
      </div>
    </Panel>
  );
}

export function CheckStep(props: {
  runId: string;
  client: ApiClient;
  summary: CheckSummary | null;
  loading: boolean;
  error: unknown;
  onRetry: () => void;
  /** The Check job while it runs — `n of N` from its record (DEF-BIL-8224). */
  checking: { progress: { done: number; total: number } | null } | null;
  /** *Check again*: the whole run, as a job. */
  onCheckAgain: () => void;
  /** A utility-wide stop recorded on the run (the Check never started). */
  stop?: CheckStopRecord | null;
  /** The Check job stopped part-way (its worker lost, a time limit) — DEF-BIL-8511. */
  stopped?: { progress: { done: number; total: number } | null } | null;
  onResume?: () => void;
  calculating: { progress: { done: number; total: number; stage?: string } | null } | null;
  working: boolean;
  refusal: string | null;
  actions: CheckPaneActions;
  links: CheckLinks;
  /** The tag Sign off's *Fix in Check* or a warning's *See* asked for. */
  focus: { tag: string | null; account: string | null } | null;
  t: Translator;
}) {
  const { summary, t } = props;
  const [filter, setFilter] = useState<TileFilter>("all");
  const [query, setQuery] = useState("");
  const [showPassed, setShowPassed] = useState(false);
  const [selected, setSelected] = useState<string>(READY_TAG);
  const [fixing, setFixing] = useState<string | null>(null);

  // Open on the first problem, not on Ready, when there are problems (image 11).
  const firstProblem = useMemo(
    () => (summary === null ? null : firstShownTag(summary, "all", "", false, t)),
    [summary, t],
  );
  const tags = useMemo(() => (summary === null ? new Map<string, CheckTag>() : tagsByCode(summary)), [summary]);
  useEffect(() => {
    if (props.focus !== null) {
      if (props.focus.tag !== null) setSelected(props.focus.tag);
      if (props.focus.account !== null) setFixing(props.focus.account);
      return;
    }
    if (firstProblem !== null) setSelected((was) => (was === READY_TAG ? firstProblem : was));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [firstProblem, props.focus]);

  if (props.calculating !== null) {
    return (
      <ProgressPanel
        name="calculating"
        // DEF-BIL-9010 — Calculate's first pass reads every account before it
        // drafts one; it is counted, under its own title.
        title={t(
          props.calculating.progress?.stage === "preparing"
            ? "billing.bulkRun.calculating.preparing"
            : "billing.bulkRun.calculating.title",
        )}
        progress={props.calculating.progress}
        note={t("billing.bulkRun.calculating.note")}
        t={t}
      />
    );
  }
  if (props.checking !== null || (props.loading && summary === null)) {
    return (
      <ProgressPanel
        name="checking"
        title={t("billing.bulkRun.check.checking")}
        progress={props.checking?.progress ?? null}
        note={t("billing.bulkRun.check.checkingNote")}
        t={t}
      />
    );
  }
  if (summary === null) {
    return <CheckStop error={props.error} onRetry={props.onRetry} t={t} />;
  }
  if (props.stop != null) {
    // The latest pass stopped utility-wide (B21): the run is kept and Try
    // again runs the Check again — a re-read would only find the same stop.
    return <CheckStop error={null} stop={props.stop} onRetry={props.onCheckAgain} t={t} />;
  }

  const tiles = summary.tiles;
  const tagShownNow =
    selected === READY_TAG
      ? filter === "all" || filter === "ready"
      : summary.categories.some((category) => visibleTags(category, filter, query, true, t).some((tag) => tag.code === selected));
  const effective = tagShownNow ? selected : (firstShownTag(summary, filter, query, showPassed, t) ?? READY_TAG);
  const openTag = tags.get(effective) ?? null;
  const checkedAt = tiles.checked_at === null ? null : new Date(tiles.checked_at);

  const pressFilter = (next: TileFilter) => {
    setFilter(next);
    if (next === "ready") setSelected(READY_TAG);
  };
  const tone = (text: string, className: string) => <span className={className}>{text}</span>;
  const kpis: KpiTile[] = [
    {
      id: "types",
      label: t("billing.bulkRun.check.tile.types"),
      value: count(tiles.problem_types),
      press: { pressed: filter === "all", onPress: () => pressFilter("all") },
    },
    {
      id: "blocked",
      label: t("billing.bulkRun.check.tile.blocked"),
      value: tone(count(tiles.blocked), "text-danger-700"),
      press: { pressed: filter === "blocks", onPress: () => pressFilter("blocks") },
    },
    {
      id: "decision",
      label: t("billing.bulkRun.check.tile.decision"),
      value: tone(count(tiles.decisions), "text-warning-700"),
      press: { pressed: filter === "decision", onPress: () => pressFilter("decision") },
    },
    {
      id: "warnings",
      label: t("billing.bulkRun.check.tile.warnings"),
      value: tone(count(tiles.warnings), "text-info-700"),
      press: { pressed: filter === "warning", onPress: () => pressFilter("warning") },
    },
    {
      id: "ready",
      label: t("billing.bulkRun.check.tile.ready"),
      value: tone(count(tiles.ready), "text-success-700"),
      press: { pressed: filter === "ready", onPress: () => pressFilter("ready") },
    },
  ];

  return (
    <Panel
      as="section"
      title={t("billing.bulkRun.check.title")}
      aria-label={t("billing.bulkRun.check.title")}
      trailing={
        <span className="flex items-center gap-3">
          <Kicker as="div">
            {checkedAt === null
              ? t("billing.bulkRun.check.checked", { count: tiles.accounts })
              : t("billing.bulkRun.check.checkedAt", {
                  count: tiles.accounts,
                  time: checkedAt.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit" }),
                })}
          </Kicker>
          <Button size="sm" disabled={props.working || props.loading} onClick={props.onCheckAgain} data-check-again="">
            {t("billing.bulkRun.check.checkAgain")}
          </Button>
        </span>
      }
      data-check-results=""
    >
      {props.stopped != null && (
        <div className="mt-3 flex items-center justify-between gap-3 bg-warning-100 px-3 py-2 text-base text-warning-700" role="status" data-check-stopped="">
          <span className="font-heading font-semibold">
            {props.stopped.progress === null
              ? t("billing.bulkRun.check.stoppedPart")
              : t("billing.bulkRun.check.stoppedAt", {
                  done: count(props.stopped.progress.done),
                  total: count(props.stopped.progress.total),
                })}
          </span>
          {props.onResume !== undefined && (
            <Button size="sm" disabled={props.working} onClick={props.onResume} data-check-resume="">
              {t("billing.bulkRun.check.resume")}
            </Button>
          )}
        </div>
      )}
      <div className="mt-3 [&_.kpi-grid]:grid-cols-5">
        <KPIStrip kpis={kpis} label={t("billing.bulkRun.check.tilesLabel")} />
      </div>
      {/* OQ-BIL-12791 → A (DEF-BIL-10121): the pricing check, back on the run. */}
      <div className="mt-3">
        <PricingCheck
          runId={props.runId}
          client={props.client}
          checkedAt={tiles.checked_at}
          t={t}
          accountHref={(accountId) => props.links.fix("accounts", accountId)}
        />
      </div>
      <div className="mt-4 grid grid-cols-4 items-start gap-4">
        <div className="col-span-1 max-h-screen overflow-y-auto">
          <ProblemTagList
            summary={summary}
            filter={filter}
            selected={effective}
            onSelect={setSelected}
            query={query}
            onQuery={setQuery}
            showPassed={showPassed}
            onShowPassed={setShowPassed}
            t={t}
          />
        </div>
        <div className="col-span-3">
          {effective === READY_TAG || openTag === null ? (
            <ReadyToBillPane runId={props.runId} client={props.client} working={props.working} actions={props.actions} links={props.links} t={t} />
          ) : (
            <ProblemTagPane
              key={openTag.code}
              runId={props.runId}
              tag={openTag}
              tags={tags}
              client={props.client}
              working={props.working}
              refusal={props.refusal}
              actions={props.actions}
              onOpenAccount={setFixing}
              onOpenTag={(code) => {
                setFilter("all");
                setQuery("");
                setSelected(code);
              }}
              links={props.links}
              t={t}
            />
          )}
        </div>
      </div>
      {fixing !== null && (
        <FixAccountPanel
          runId={props.runId}
          accountId={fixing}
          tags={tags}
          client={props.client}
          working={props.working}
          actions={props.actions}
          onClose={() => setFixing(null)}
          links={props.links}
          t={t}
        />
      )}
    </Panel>
  );
}
