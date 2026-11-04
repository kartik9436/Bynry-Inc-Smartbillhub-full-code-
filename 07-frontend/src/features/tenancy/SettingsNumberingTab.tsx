// ── Trace ──────────────────────────────────────────────
// Story:    US-TEN-012 (EP-TEN-08 §Stories)  Screens: S8 (Settings → Configure → Numbering) / r10 SET-08
// Change:   CR-005 (PO 2026-08-16) — every system-generated number gets a defined format
// Rules:    BR-TEN-035 (format grammar: literals + {YYYY}/{YY}/{MM}/{DD} + EXACTLY ONE {0…0} pad token;
//           ≤24 chars; pad ≤8; restart period; overflow widens; duplicate prefixes WARN; a plain
//           prefix-free option in every category; format changes apply to FUTURE numbers only — issued
//           numbers are never renumbered; next-number edits are forward-only) · BR-TEN-033 (the
//           document-template panel is navigation only) · BR-TEN-024 (save + confirm/toast) ·
//           BR-TEN-016 (audit `settings.numbering.updated` / `.bulk_updated`, before/after) ·
//           BR-SHL-025 (a role that may not write sees the control disabled WITH ITS REASON) ·
//           BR-SHL-020 (plain-language failure) · BR-TEN-043 (the issue date is an input)
// Questions: OQ-250 (pad minimum) · OQ-251 (which entity list) · OQ-252 (restart without a date token)
// ───────────────────────────────────────────────────────
// S8 → Numbering: one row per series, grouped by what the number is FOR
// (Customers & premises · Billing & payments · Finance · Work · Assets &
// reads), each with a ready-made format or a custom one, a next counter, a
// restart policy, a live preview and a reset.
//
// THREE THINGS THIS SCREEN DELIBERATELY DOES NOT DO, each for a stated reason:
//
//   · It never composes the ready-made option list. `row.options` arrives from
//     the server's `SERIES_CATALOG`, which is also where the SEEDED default
//     comes from — so a dropdown can never offer a format the save would
//     refuse, and can never omit the one this tenant is already using.
//   · It never renumbers anything. BR-TEN-035 makes issued numbers immutable
//     (CLAUDE.md rule 4) and no such route exists at any layer. The sentence
//     saying so is ON the screen, because a rule the user cannot see is a rule
//     they will assume the opposite of.
//   · It never decides permission from a role NAME. `readOnly` arrives from the
//     server-computed access set (BR-SHL-025) and every control it disables
//     keeps its reason on it — a Billing Clerk READS this screen and cannot
//     change how bills are numbered (PO ruling 2026-08-16, CR-005/006/007).
//
// Two previews exist and they are deliberately different:
//   · the SERVER's `preview` field — what the next number will really look
//     like, rendered with the tenant's timezone and the stored counter. It is
//     the truth and it is what a row shows at rest.
//   · `previewFormat()` below — a LOCAL echo of an unsaved edit, so the user
//     sees the shape before saving. It is marked as unsaved, it allocates
//     nothing, and the moment a save lands the server's value takes over.
// The grammar validation is the same law in both halves: `formatProblem()`
// mirrors core.numbering.validate_format so a malformed format is refused with
// the specific problem instead of a generic "invalid".
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { getNumberSeries, saveNumberSeries, saveNumberSeriesBulk } from "@/api/endpoints";
import type { NumberSeriesRow, RestartPeriod } from "@/api/endpoints";
import { queryKeys } from "@/api/queryClient";
import { Button } from "@/components/Button";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { TextField } from "@/components/FormModal";
import { FailedWithRetry, FieldError, LoadingSkeleton, WorkingButton } from "@/components/StateFrame";
import { useToast } from "@/components/Toast";
import { Kicker, Note } from "@/components/TextBits";

import {
  Panel,
  RefusalNotice,
  SettingsDenied,
  apiErrorText,
  isPermissionDenied,
  refusalOf,
} from "./settingsShared";
import type { Refusal } from "./settingsShared";

// ── BR-TEN-035 grammar (mirrors core/numbering.py) ─────────────────────────

export const DATE_TOKENS: readonly string[] = ["YYYY", "YY", "MM", "DD"];
export const YEAR_TOKENS: readonly string[] = ["YYYY", "YY"];
/** CR-005: *"validated: max 1 counter, only allowed tokens, ≤ 24 chars"*. */
export const MAX_FORMAT_LENGTH = 24;
/** CR-005: *"pad length 4–8"* — the UPPER half only; the lower is OQ-250. */
export const MAX_PAD = 8;
export const RESTART_PERIODS: readonly RestartPeriod[] = ["never", "yearly", "monthly"];

export type FormatProblem =
  | "empty"
  | "unbalanced_braces"
  | "no_sequence_token"
  | "multiple_sequence_tokens"
  | "unknown_token"
  | "too_long"
  | "pad_too_long"
  | null;

const TOKEN_RE = /\{([^{}]*)\}/g;
const SEQUENCE_TOKEN_RE = /^0+$/;

/**
 * The client half of BR-TEN-035, pure and provable without a network. It names
 * the SPECIFIC problem rather than "invalid". The server re-validates on save
 * and its refusal is what actually blocks the write.
 */
export function formatProblem(format: string): FormatProblem {
  if (format.trim() === "") {
    return "empty";
  }
  // A stray brace would silently swallow a token from the scan — name the typo
  // before diagnosing whatever tokens are left.
  const opens = format.split("{").length - 1;
  const closes = format.split("}").length - 1;
  if (opens !== closes) {
    return "unbalanced_braces";
  }
  let sequences = 0;
  for (const match of format.matchAll(TOKEN_RE)) {
    const token = match[1];
    if (SEQUENCE_TOKEN_RE.test(token)) {
      sequences += 1;
    } else if (!DATE_TOKENS.includes(token)) {
      return "unknown_token";
    }
  }
  if (sequences === 0) {
    return "no_sequence_token";
  }
  if (sequences > 1) {
    return "multiple_sequence_tokens";
  }
  // Length last, in the server's order: "too long" is a useless thing to be
  // told about a format whose real problem is a typo'd token.
  if (format.length > MAX_FORMAT_LENGTH) {
    return "too_long";
  }
  if (padLength(format) > MAX_PAD) {
    return "pad_too_long";
  }
  return null;
}

/** Digits in the counter token — the pad width; 0 when there is no counter. */
export function padLength(format: string): number {
  for (const match of format.matchAll(TOKEN_RE)) {
    if (SEQUENCE_TOKEN_RE.test(match[1])) {
      return match[1].length;
    }
  }
  return 0;
}

/**
 * The literal characters before the first token. An empty prefix is what the
 * mandatory plain option (`{00000}`) has, and empty prefixes are never
 * duplicates of one another — see `duplicatePrefixes`.
 */
export function literalPrefix(format: string): string {
  const brace = format.indexOf("{");
  return brace === -1 ? format : format.slice(0, brace);
}

/**
 * DEF-197: the format IS the bare counter and nothing else — `{00000}`.
 *
 * This is NOT `literalPrefix(f) === ""`, which is what shipped and which was
 * wrong: a format OPENING with a token has no literal prefix either, so
 * `{YYYY}{00000}` and `{YYYY}{MM}{DD}-{0000}` both announced themselves as the
 * plain option. The Account row then offered TWO options each claiming to be
 * the plain one, and picking the wrong one issued `202600001`.
 *
 * The label is the affordance, not decoration — the PO's rule requires a plain
 * no-prefix option *in every category* precisely so it is FINDABLE. A label
 * that points at two different formats defeats the rule it implements.
 */
export function isPlainCounter(format: string): boolean {
  return /^\{0+\}$/.test(format.trim());
}

/**
 * CR-005: *"duplicate prefixes across entities → warning (not blocking)"*.
 * Computed over the DRAFTS so the warning tracks what is being typed; the
 * server computes the same thing over what is saved (`duplicate_prefix`).
 */
export function duplicatePrefixes(formats: readonly string[]): Set<string> {
  const seen = new Map<string, number>();
  for (const format of formats) {
    const prefix = literalPrefix(format);
    if (prefix !== "") {
      seen.set(prefix, (seen.get(prefix) ?? 0) + 1);
    }
  }
  return new Set([...seen].filter(([, count]) => count > 1).map(([prefix]) => prefix));
}

/**
 * CR-005 edge case: *"counter overflow (counter exceeds pad length) → keep
 * issuing, widen number, surface a warning banner"*. True means the next number
 * will be one digit longer than the format shows. Nothing breaks and nothing
 * stops — this is a banner, never a refusal.
 */
export function willOverflow(format: string, nextNumber: number): boolean {
  const pad = padLength(format);
  return pad > 0 && nextNumber >= 10 ** pad;
}

/**
 * OQ-252 / BR-TEN-035 clause (b): a restart is only safe when the date token
 * that distinguishes the periods is IN the number. Yearly needs a year token;
 * monthly needs a month token AND a year token, or every January repeats.
 */
export function restartProblem(
  format: string,
  restart: RestartPeriod,
): "needs_year_token" | "needs_year_and_month_tokens" | null {
  if (restart === "never") {
    return null;
  }
  const tokens = new Set([...format.matchAll(TOKEN_RE)].map((match) => match[1]));
  const hasYear = YEAR_TOKENS.some((token) => tokens.has(token));
  if (restart === "yearly") {
    return hasYear ? null : "needs_year_token";
  }
  return tokens.has("MM") && hasYear ? null : "needs_year_and_month_tokens";
}

/**
 * The local echo of an UNSAVED format. Date tokens fill from the supplied
 * issue date (BR-TEN-043: the date is always an argument, never the wall
 * clock) and the pad token from the next number. Returns null when the format
 * is not yet legal — a preview that renders garbage teaches the wrong shape.
 */
export function previewFormat(format: string, nextNumber: number, issueDate: string): string | null {
  if (formatProblem(format) !== null) {
    return null;
  }
  const [year, month, day] = issueDate.split("-");
  return format.replace(TOKEN_RE, (_whole, token: string) => {
    if (SEQUENCE_TOKEN_RE.test(token)) {
      return String(nextNumber).padStart(token.length, "0");
    }
    switch (token) {
      case "YYYY":
        return year;
      case "YY":
        return year.slice(2);
      case "MM":
        return month;
      case "DD":
        return day;
      default:
        return "";
    }
  });
}

/** BR-TEN-035: the counter may only move FORWARD — collisions are impossible. */
export function nextNumberProblem(current: number, proposed: string): "not_int" | "backward" | null {
  if (!/^\d+$/.test(proposed.trim())) {
    return "not_int";
  }
  return Number.parseInt(proposed, 10) < current ? "backward" : null;
}

export interface SeriesDraft {
  format: string;
  next_number: string;
  restart_period: RestartPeriod;
}

export function seriesDraftFrom(row: NumberSeriesRow): SeriesDraft {
  return {
    format: row.format,
    next_number: String(row.next_number),
    restart_period: row.restart_period,
  };
}

export function seriesChanges(
  draft: SeriesDraft,
  row: NumberSeriesRow,
): { format?: string; next_number?: number; restart_period?: RestartPeriod } {
  const changes: { format?: string; next_number?: number; restart_period?: RestartPeriod } = {};
  if (draft.format !== row.format) {
    changes.format = draft.format;
  }
  if (draft.next_number !== String(row.next_number)) {
    changes.next_number = Number.parseInt(draft.next_number, 10);
  }
  if (draft.restart_period !== row.restart_period) {
    changes.restart_period = draft.restart_period;
  }
  return changes;
}

export function draftIsDirty(draft: SeriesDraft, row: NumberSeriesRow): boolean {
  return Object.keys(seriesChanges(draft, row)).length > 0;
}

/** Every problem on one row, or null when the row is saveable. */
export function draftProblem(
  draft: SeriesDraft,
  row: NumberSeriesRow,
): FormatProblem | "not_int" | "backward" | "needs_year_token" | "needs_year_and_month_tokens" {
  return (
    formatProblem(draft.format) ??
    nextNumberProblem(row.next_number, draft.next_number) ??
    restartProblem(draft.format, draft.restart_period)
  );
}

// ── The right rail: "How they appear together" ─────────────────────────────

/**
 * CR-005: *"Live sample showing formats in context … re-renders as formats
 * change so the admin sees the downstream effect before saving."*
 *
 * The sample is built from the SAME drafts the table is editing, so it is the
 * one place an admin sees an account number and a bill number side by side —
 * which is where "AC-2026-01248 / AC-2026-020419" reads as an obvious mistake
 * and neither row does on its own. A series this tenant does not have simply
 * leaves its line out rather than inventing a number for it.
 */
export function sampleNumber(
  series: string,
  rows: readonly NumberSeriesRow[],
  edits: Record<string, SeriesDraft>,
  today: string,
): string | null {
  const row = rows.find((candidate) => candidate.series === series);
  if (row === undefined) {
    return null;
  }
  const draft = edits[series] ?? seriesDraftFrom(row);
  const counter = /^\d+$/.test(draft.next_number.trim())
    ? Number.parseInt(draft.next_number, 10)
    : row.next_number;
  return previewFormat(draft.format, counter, today) ?? row.preview;
}

// ── The tab ────────────────────────────────────────────────────────────────

export interface NumberingTabProps {
  readOnly: boolean;
  client?: ApiClient;
  // BR-TEN-043: the issue date the local preview echoes. The SERVER's preview
  // uses the tenant timezone; this prop keeps the client echo deterministic
  // instead of reading a wall clock inside the render.
  today?: string;
}

function isoToday(): string {
  return new Date().toISOString().slice(0, 10);
}

const GROUP_ORDER = [
  "customers_premises",
  "billing_payments",
  "finance",
  "work",
  "assets_reads",
] as const;

export function NumberingTab(props: NumberingTabProps) {
  const { t } = useTranslation();
  const client = props.client ?? api;
  const fireToast = useToast();
  const queryClient = useQueryClient();
  const today = props.today ?? isoToday();

  const seriesQuery = useQuery({
    queryKey: queryKeys.numberSeries,
    queryFn: () => getNumberSeries(client),
  });

  const [edits, setEdits] = useState<Record<string, SeriesDraft>>({});
  const [custom, setCustom] = useState<Record<string, boolean>>({});
  const [resetting, setResetting] = useState<string | null>(null);
  const [refusal, setRefusal] = useState<Refusal | null>(null);

  const invalidate = () => {
    void queryClient.invalidateQueries({ queryKey: queryKeys.numberSeries });
    void queryClient.invalidateQueries({ queryKey: queryKeys.checklist });
  };

  // The whole tab, one call, one transaction (CR-005 "Save").
  const saveAll = useMutation({
    mutationFn: (rows: ({ series: string } & ReturnType<typeof seriesChanges>)[]) =>
      saveNumberSeriesBulk(rows, client),
    onSuccess: () => {
      invalidate();
      setEdits({});
      setCustom({});
      setRefusal(null);
      fireToast(t("settings.numbering.savedAll"));
    },
    onError: (error: unknown) => setRefusal(refusalOf(error, t)),
  });

  // The reset dialog changes ONE row and posts only that row — a confirm about
  // the bill counter has no business saving twenty-one other formats.
  const resetCounter = useMutation({
    mutationFn: (input: { series: string; next_number: number }) =>
      saveNumberSeries(input.series, { next_number: input.next_number }, client),
    onSuccess: (saved: NumberSeriesRow) => {
      invalidate();
      setEdits((current) => {
        const next = { ...current };
        delete next[saved.series];
        return next;
      });
      setResetting(null);
      setRefusal(null);
      fireToast(
        t("settings.numbering.saved", {
          series: t(`settings.numbering.series.${saved.series}`),
        }),
      );
    },
    onError: (error: unknown) => {
      setResetting(null);
      setRefusal(refusalOf(error, t));
    },
  });

  if (seriesQuery.isPending) {
    return <LoadingSkeleton variant="card" />;
  }
  if (seriesQuery.data === undefined) {
    if (isPermissionDenied(seriesQuery.error)) {
      return <SettingsDenied helper={t("settings.denied.tab")} />;
    }
    return (
      <FailedWithRetry
        title={t("settings.numbering.failedTitle")}
        reason={apiErrorText(seriesQuery.error, t)}
        onRetry={() => void seriesQuery.refetch()}
        onDownloadReport={() => undefined}
        onCancel={() => void seriesQuery.refetch()}
      />
    );
  }

  const rows = seriesQuery.data;
  const draftOf = (row: NumberSeriesRow): SeriesDraft => edits[row.series] ?? seriesDraftFrom(row);
  const setDraft = (row: NumberSeriesRow, patch: Partial<SeriesDraft>) =>
    setEdits({ ...edits, [row.series]: { ...draftOf(row), ...patch } });

  const duplicates = duplicatePrefixes(rows.map((row) => draftOf(row).format));
  const overflowing = rows.filter((row) => {
    const draft = draftOf(row);
    const counter = /^\d+$/.test(draft.next_number.trim())
      ? Number.parseInt(draft.next_number, 10)
      : row.next_number;
    return willOverflow(draft.format, counter);
  });
  const dirtyRows = rows.filter((row) => draftIsDirty(draftOf(row), row));
  // DEF-199: the ROW, not a boolean. `blocked` could only ever produce a silent
  // refusal, because by the time Save ran nothing knew which row was at fault.
  const blockedRow = dirtyRows.find((row) => draftProblem(draftOf(row), row) !== null) ?? null;
  const resettingRow = rows.find((row) => row.series === resetting);

  const groups = [...GROUP_ORDER, "other"].map((group) => ({
    group,
    rows: rows.filter((row) => (GROUP_ORDER.includes(row.group as never) ? row.group : "other") === group),
  }));

  return (
    <div className="settings-tab">
      <Kicker>{t("settings.numbering.kicker")}</Kicker>
      {/* r10 SET-08's own lead sentence — what a format IS, before the table. */}
      <p className="settings-lede">{t("settings.numbering.description")}</p>
      <p className="settings-lede">{t("settings.numbering.lede")}</p>

      <RefusalNotice refusal={refusal} />

      {/* CR-005 edge case: overflow keeps issuing and SAYS SO. A banner, not a
          block — a utility mid-bill-run must not be stopped by cosmetics. */}
      {overflowing.length > 0 && (
        <p className="settings-warning" role="status">
          {t("settings.numbering.overflowBanner", {
            entities: overflowing
              .map((row) => t(`settings.numbering.series.${row.series}`))
              .join(", "),
          })}
        </p>
      )}

      <div className="numbering-layout">
        {/* The table keeps the panel it has always had — "Number formats", with
            the grammar as its hint. G18 named both strings DEAD when the rewrite
            dropped the old panel, which is the check doing its job: a heading
            that stops being rendered is a heading somebody decided to remove,
            and nobody had. */}
        <Panel title={t("settings.numbering.series")} hint={t("settings.numbering.seriesHint")} accent>
          <div className="numbering-scroll">
            <table className="numbering-table">
              <thead>
                <tr>
                  <th scope="col">{t("settings.numbering.col.entity")}</th>
                  <th scope="col">{t("settings.numbering.col.format")}</th>
                  <th scope="col" className="numbering-num">
                    {t("settings.numbering.col.next")}
                  </th>
                  <th scope="col">{t("settings.numbering.col.restart")}</th>
                  <th scope="col">{t("settings.numbering.col.preview")}</th>
                  <th scope="col">
                    <span className="numbering-sr">{t("settings.numbering.col.reset")}</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {rows.length === 0 && (
                  <tr>
                    <td colSpan={6}>{t("settings.numbering.none")}</td>
                  </tr>
                )}
                {groups.map(({ group, rows: groupRows }) =>
                  groupRows.length === 0 ? null : (
                    <NumberingGroup
                      key={group}
                      group={group}
                      rows={groupRows}
                      draftOf={draftOf}
                      setDraft={setDraft}
                      custom={custom}
                      setCustom={setCustom}
                      duplicates={duplicates}
                      readOnly={props.readOnly}
                      today={today}
                      onReset={setResetting}
                    />
                  ),
                )}
              </tbody>
            </table>
          </div>

          {/* CR-005 Actions: Save is primary and bottom-left, and it saves the
              WHOLE table in one transaction. */}
          <div className="numbering-actions">
            {props.readOnly ? (
              // BR-SHL-025: disabled WITH the reason on the control, never a
              // control that quietly disappeared.
              <Button
                variant="primary"
                disabled
                title={t("settings.readOnlyReason")}
              >
                {t("settings.numbering.saveAll")}
              </Button>
            ) : (
              <WorkingButton
                working={saveAll.isPending}
                onClick={() => {
                  // DEF-199: a press must ANSWER where the press happened.
                  // This used to be a bare `return` — the button stayed enabled,
                  // the field error sat on a row the admin had scrolled past,
                  // and pressing Save produced nothing at all. Same class as
                  // DEF-178, whose whole lesson was exactly this.
                  //
                  // Deliberately NOT solved by disabling the button: BR-SHL-025
                  // treats a grey control with no reason as the other half of
                  // the same failure. So it stays pressable and it explains.
                  const offender = blockedRow;
                  if (offender) {
                    setRefusal({
                      message: t("settings.numbering.blockedSave", {
                        entity: t(`settings.numbering.series.${offender.series}`),
                      }),
                      brRef: null,
                    });
                    // Take the admin TO the row, not merely tell them it
                    // exists. Scroll by the ROW (always present) and focus the
                    // custom-format field when that is what is at fault.
                    document
                      .getElementById(`series-row-${offender.series}`)
                      ?.scrollIntoView({ block: "center" });
                    const field = document.getElementById(
                      `series-format-${offender.series}`,
                    ) as HTMLInputElement | null;
                    field?.focus();
                    return;
                  }
                  if (dirtyRows.length === 0) {
                    setRefusal({
                      message: t("settings.numbering.nothingToSave"),
                      brRef: null,
                    });
                    return;
                  }
                  setRefusal(null);
                  saveAll.mutate(
                    dirtyRows.map((row) => ({
                      series: row.series,
                      ...seriesChanges(draftOf(row), row),
                    })),
                  );
                }}
              >
                {t("settings.numbering.saveAll")}
              </WorkingButton>
            )}
            {props.readOnly && (
              <span className="settings-readonly">{t("settings.readOnlyReason")}</span>
            )}
            {/* BR-TEN-035, in the user's words — the reason there is no
                renumber control anywhere on this screen. */}
            <Note as="span">{t("settings.numbering.futureOnly")}</Note>
          </div>
        </Panel>

        <aside className="numbering-rail">
          <Panel title={t("settings.numbering.sample")} accent>
            <SampleCard
              title={t("settings.numbering.sample.bill")}
              lines={[
                [t("settings.numbering.sample.account"), sampleNumber("account", rows, edits, today)],
                [t("settings.numbering.sample.billNo"), sampleNumber("bill", rows, edits, today)],
                [t("settings.numbering.sample.paidBy"), sampleNumber("payment", rows, edits, today)],
                [t("settings.numbering.sample.receipt"), sampleNumber("receipt", rows, edits, today)],
              ]}
            />
            <SampleCard
              title={t("settings.numbering.sample.work")}
              lines={[
                [t("settings.numbering.sample.workOrder"), sampleNumber("work_order", rows, edits, today)],
                [t("settings.numbering.sample.asset"), sampleNumber("asset", rows, edits, today)],
                [t("settings.numbering.sample.premises"), sampleNumber("premises", rows, edits, today)],
              ]}
            />
            <SampleCard
              title={t("settings.numbering.sample.finance")}
              lines={[
                [t("settings.numbering.sample.deposit"), sampleNumber("deposit_batch", rows, edits, today)],
                [t("settings.numbering.sample.journal"), sampleNumber("journal_entry", rows, edits, today)],
                [t("settings.numbering.sample.loadedBy"), sampleNumber("import_run", rows, edits, today)],
              ]}
            />
            <Note>{t("settings.numbering.sample.note")}</Note>
          </Panel>

          <Panel
            title={t("settings.numbering.templates")}
            hint={t("settings.numbering.templatesHint")}
          >
            {/* BR-TEN-033: navigation only. Tenancy stores nothing for
                templates, so this panel states the pointer instead of listing
                rows it would have to invent. */}
            <FieldError message={t("settings.numbering.templatesPending")} />
          </Panel>
        </aside>
      </div>

      {resettingRow !== undefined && (
        <ConfirmDialog
          title={t("settings.numbering.resetTitle", {
            series: t(`settings.numbering.series.${resettingRow.series}`),
          })}
          consequence={t("settings.numbering.resetConsequence", {
            value:
              previewFormat(
                draftOf(resettingRow).format,
                /^\d+$/.test(draftOf(resettingRow).next_number.trim())
                  ? Number.parseInt(draftOf(resettingRow).next_number, 10)
                  : resettingRow.next_number,
                today,
              ) ?? t("settings.numbering.previewNone"),
          })}
          confirmLabel={t("settings.numbering.resetConfirm")}
          working={resetCounter.isPending}
          onConfirm={() => {
            const draft = draftOf(resettingRow);
            if (nextNumberProblem(resettingRow.next_number, draft.next_number) !== null) {
              return; // forward-only; the field already names the minimum
            }
            resetCounter.mutate({
              series: resettingRow.series,
              next_number: Number.parseInt(draft.next_number, 10),
            });
          }}
          onCancel={() => setResetting(null)}
        />
      )}
    </div>
  );
}

function SampleCard(props: { title: string; lines: [string, string | null][] }) {
  const shown = props.lines.filter(([, value]) => value !== null);
  if (shown.length === 0) {
    return null; // a card with nothing in it teaches nothing
  }
  return (
    <div className="numbering-sample">
      <Kicker>{props.title}</Kicker>
      {shown.map(([label, value]) => (
        <div key={label} className="numbering-sample-line">
          <span>{label}</span> <b>{value}</b>
        </div>
      ))}
    </div>
  );
}

function NumberingGroup(props: {
  group: string;
  rows: NumberSeriesRow[];
  draftOf: (row: NumberSeriesRow) => SeriesDraft;
  setDraft: (row: NumberSeriesRow, patch: Partial<SeriesDraft>) => void;
  custom: Record<string, boolean>;
  setCustom: (next: Record<string, boolean>) => void;
  duplicates: Set<string>;
  readOnly: boolean;
  today: string;
  onReset: (series: string) => void;
}) {
  const { t } = useTranslation();
  return (
    <>
      {/* CR-005 UX rule: "Section kickers per group". */}
      <tr className="numbering-group">
        <th colSpan={6} scope="colgroup">
          <Kicker>{t(`settings.numbering.group.${props.group}`)}</Kicker>
        </th>
      </tr>
      {props.rows.map((row) => {
        const draft = props.draftOf(row);
        const dirty = draftIsDirty(draft, row);
        const problem = formatProblem(draft.format);
        const counter = nextNumberProblem(row.next_number, draft.next_number);
        const restart = restartProblem(draft.format, draft.restart_period);
        const isCustom = props.custom[row.series] === true || !row.options.includes(draft.format);
        const localPreview =
          dirty && problem === null && counter === null
            ? previewFormat(draft.format, Number.parseInt(draft.next_number, 10), props.today)
            : null;
        return (
          // DEF-199: the row needs a handle so a blocked Save can take the
          // admin TO it. The format field only exists in custom mode, so it
          // cannot be the anchor for every row.
          <tr key={row.series} id={`series-row-${row.series}`}>
            <th scope="row">{t(`settings.numbering.series.${row.series}`)}</th>
            <td>
              <select
                className="input numbering-format"
                aria-label={t("settings.numbering.col.format")}
                value={isCustom ? "__custom__" : draft.format}
                disabled={props.readOnly}
                title={props.readOnly ? t("settings.readOnlyReason") : undefined}
                onChange={(event) => {
                  if (event.target.value === "__custom__") {
                    props.setCustom({ ...props.custom, [row.series]: true });
                    return;
                  }
                  props.setCustom({ ...props.custom, [row.series]: false });
                  props.setDraft(row, { format: event.target.value });
                }}
              >
                {row.options.map((option) => (
                  <option key={option} value={option}>
                    {/* CR-005 user rule: the prefix-free option is labelled as
                        what it is, so "plain sequential number" is findable.
                        DEF-197: the test is isPlainCounter, NOT an empty
                        literal prefix — a format starting with a token has no
                        prefix either and is not the plain option. */}
                    {isPlainCounter(option)
                      ? t("settings.numbering.plainOption", { format: option })
                      : option}
                  </option>
                ))}
                <option value="__custom__">{t("settings.numbering.custom")}</option>
              </select>
              {isCustom && (
                <TextField
                  id={`series-format-${row.series}`}
                  label={t("settings.numbering.customLabel")}
                  value={draft.format}
                  // BR-SHL-025's own shape for "may read, may not set": the
                  // field stays focusable and selectable and the help line
                  // carries the reason, rather than a control going grey with
                  // no explanation.
                  readOnly={props.readOnly}
                  onChange={(value) => props.setDraft(row, { format: value })}
                  help={
                    props.readOnly
                      ? t("settings.readOnlyReason")
                      : t("settings.numbering.formatHelp")
                  }
                  error={problem === null ? undefined : t(`settings.numbering.problem.${problem}`)}
                />
              )}
              {!isCustom && problem !== null && (
                <FieldError message={t(`settings.numbering.problem.${problem}`)} />
              )}
              {/* CR-005: duplicate prefixes WARN — the save goes through. */}
              {props.duplicates.has(literalPrefix(draft.format)) && (
                <Note>
                  {t("settings.numbering.duplicatePrefix", {
                    prefix: literalPrefix(draft.format),
                  })}
                </Note>
              )}
            </td>
            <td className="numbering-num">
              {/* ⚠ NO VISIBLE LABEL, AND THAT IS THE ALIGNMENT FIX (PO, on the
                  running product at v2.123.0: *"can you ensure inputs boxes on
                  this screen are aling, theya re in same line"*).
                  This cell used the shared `TextField`, which paints a label
                  ABOVE its input. Its two neighbours — Format and Restart — are
                  bare controls carrying an `aria-label`, so they start at the
                  top of the row while this one started a label's height lower,
                  and the three columns never lined up on any row.
                  The label was also REDUNDANT: the column header already reads
                  "Next counter", and B14 rule 32 says a row never repeats what
                  its own control offers.
                  The accessible name now comes from the SAME key the column
                  header renders, which is exactly what the Format cell beside
                  it already does — so a screen reader loses nothing and the
                  paint loses a line. */}
              <input
                id={`series-next-${row.series}`}
                className="input"
                type="text"
                inputMode="decimal"
                aria-label={t("settings.numbering.col.next")}
                value={draft.next_number}
                readOnly={props.readOnly}
                title={props.readOnly ? t("settings.readOnlyReason") : undefined}
                aria-invalid={counter === null ? undefined : true}
                aria-describedby={
                  counter === null ? undefined : `series-next-${row.series}-error`
                }
                onChange={(event) => props.setDraft(row, { next_number: event.target.value })}
              />
              {counter !== null && (
                <FieldError
                  id={`series-next-${row.series}-error`}
                  message={t(`settings.numbering.counter.${counter}`, { min: row.next_number })}
                />
              )}
            </td>
            <td>
              <select
                className="input"
                aria-label={t("settings.numbering.col.restart")}
                value={draft.restart_period}
                disabled={props.readOnly}
                title={props.readOnly ? t("settings.readOnlyReason") : undefined}
                onChange={(event) =>
                  props.setDraft(row, { restart_period: event.target.value as RestartPeriod })
                }
              >
                {RESTART_PERIODS.map((period) => (
                  <option key={period} value={period}>
                    {t(`settings.numbering.restart.${period}`)}
                  </option>
                ))}
              </select>
              {restart !== null && (
                <FieldError message={t(`settings.numbering.restart.${restart}`)} />
              )}
            </td>
            <td className="numbering-preview">
              {/* At rest the SERVER's preview; while editing, the clearly
                  labelled local echo (BR-TEN-035 — neither allocates). */}
              {dirty
                ? t("settings.numbering.previewUnsaved", {
                    value: localPreview ?? t("settings.numbering.previewNone"),
                  })
                : t("settings.numbering.preview", {
                    value: row.preview ?? t("settings.numbering.previewNone"),
                  })}
              {row.overflow && (
                <Note as="span">{t("settings.numbering.overflowRow")}</Note>
              )}
            </td>
            <td>
              <button
                type="button"
                // DEF-198, decided by the PO 2026-08-17: *"Button size decide
                // for me as per rule"*. B14 rule 5 ratifies TWO sizes, default
                // and small at 12px, and `settings-icon-btn` (32×32) is that
                // small tier — already worn by every icon action on the
                // reference-data screens one click away.
                //
                // `btn btn-icon-sm` was the ONLY occurrence of `btn-icon-sm` in
                // the frontend and NO stylesheet declared it, so the button fell
                // through to the default tier and measured 34.8px at 14px type —
                // neither of the two sizes the rule allows.
                //
                // ⚠ THE 44px IN CR-005's PROSE IS NOT B14 AND DOES NOT WIN. It
                // is the WCAG target-size guidance and it is a real argument;
                // the PO said "as per rule", and the rule is B14. Recorded as
                // OQ-259 rather than dropped, because raising B14's small tier
                // to 44px is a product-wide accessibility decision and will be
                // raised again by anyone who audits this for accessibility.
                className="btn settings-icon-btn"
                // CR-005: *"Counter reset: … confirmation required,
                // audit-logged"*. Read-only roles keep the control and the
                // reason (BR-SHL-025) instead of losing it.
                disabled={props.readOnly}
                title={
                  props.readOnly
                    ? t("settings.readOnlyReason")
                    : t("settings.numbering.resetLabel")
                }
                aria-label={t("settings.numbering.resetLabel")}
                onClick={() => props.onReset(row.series)}
              >
                ↺
              </button>
            </td>
          </tr>
        );
      })}
    </>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-TEN-012@80cdedf (the story this extends; the CHANGE is CR-005 — 12-governance/11-change-requests.md, PO 2026-08-16)
// generated: 2026-08-17 by the CR-005 SET-08 lane (US-TEN-012@80cdedf lineage)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: tsc✔ vitest src/features/tenancy✔
// exceptions: the format picker is a NATIVE select, as r10 SET-08 draws it — CR-005's prose asks for a "searchable dropdown" and the design it points at draws `<select class="input">`; with at most seven options per entity a filter box would be furniture. Reported, not resolved · OQ-250/251/252 are OPEN and each is answered in the direction that refuses nothing already stored
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
