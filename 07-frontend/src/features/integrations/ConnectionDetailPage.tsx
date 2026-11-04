// ── Trace ────────────────────────────────────────────────────────────────
// Story:    US-INT-020 (EP-INT-06) — S142, the connection detail: the
//           describe line, the operations, and *RECENT ACTIVITY* with the
//           counts written as a clerk reads them. US-INT-021 — *Unconfirmed*
//           is its own word, in amber, and never green.
//           Frames 44.1 (a connector is several things) · 25.2 (the mailbox
//           and its three run rows) · 51.1 (a partial send, opened) · 51.2
//           (the run nobody designs for) · 52.2 (their words underneath ours).
// Rules:    BR-INT-039 (the run record is the observability) · BR-INT-018
//           (`unconfirmed` is never reported as success) · BR-INT-040 (the
//           items are NAMED, never a batch boolean) · B14 rule 15 (the row
//           action is an ICON with an accessible name) · rule 20 (one table
//           type) · rule 21 (Tailwind only; this file is on
//           route-b-migrated.txt) · rule 31 (the ONLY identifier on this
//           screen is the trace id, labelled *Support reference*) · rule 32
//           (one sentence per section; a stated absence is closed by default)
//           · rule 33 (a label is three words or fewer) · rule 5 (two button
//           sizes) · rule 6 (no danger tier — nothing here commits anything)
// Tests:    src/features/integrations/ConnectionDetailPage.test.tsx ·
//           10-scripts/render-checks/cr069-c-run-record.mjs (rendered output)
// Impacts:  src/api/integrationsEndpoints.ts (the contract) · src/App.tsx
//           (the route) · src/routing/screenIds.ts (S142 · INT-02) ·
//           src/features/integrations/IntegrationsTab.tsx (the card's link) ·
//           the eleven locale catalogues (`integrations.runs.*`)
// ─────────────────────────────────────────────────────────────────────────
//
// ⚠ THE COUNTS ARE A SENTENCE HERE AND NUMBERS ON THE WIRE, AND THAT IS THE
// WHOLE REASON THIS FILE COMPOSES THEM. *93 of 93* · *86 of 93 · 7 bad
// addresses* · *Unconfirmed · 93 sent, provider did not say* are three
// different English sentences about four integers. A server that sent the
// sentence would send it in English to eleven catalogues; a server that sends
// the integers lets a translator write the Japanese one. So `runs.py` serves
// `attempted · succeeded · failed · skipped · changed · outcome` and this
// file writes the line.
//
// ⚠ *BAD ADDRESSES* IS THE MAILBOX'S WORD AND NOT A BRANCH ON A PROVIDER.
// `integrations.runs.failed.<operation>` is looked up with the generic
// `integrations.runs.failedGeneric` as its fallback, exactly as the provider
// name is. A new provider therefore gets an honest generic line the day it is
// registered and a specific one when somebody writes a catalogue row — and no
// `if (provider === …)` is ever added here (G77's rule, kept on this side).
//
// ⚠ A DASH IS NOT A ZERO, AND THE DIFFERENCE IS THE POINT (frame 51.2). On an
// unconfirmed run every count except *handed over* renders `—`: a zero would
// be a claim that nothing was sent, and we do not know that. `CountTile`
// takes the outcome, not a boolean, so a lane cannot pass `showDash={false}`
// on the one screen where it matters.

import { useState } from "react";
import { z } from "zod";
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useParams } from "react-router-dom";

import { api, formErrorEnvelope, isApiError } from "@/api/client";
import type { ApiClient } from "@/api/client";

import {
  addCustomApi,
  deleteCustomApi,
  disconnectIntegration,
  getConnectionRuns,
  getRun,
  issuePartnerKey,
  reconcileNow,
  rollbackCredential,
  rotateCredential,
  startOAuth,
  switchStandardApi,
  updateCustomApi,
} from "@/api/integrationsEndpoints";
import type {
  AddableKind,
  ConnectionRow,
  ConnectionRuns,
  DisplayState,
  CredentialVersion,
  DisconnectPreview,
  IssuedKey,
  OperationRow,
  ReconcileReport,
  RunDetail,
  RunOutcome,
  RunRow,
} from "@/api/integrationsEndpoints";
import { queryKeys } from "@/api/queryClient";
import { AccessLogPanel } from "@/features/integrations/AccessLogPanel";
// ⚠ ONE STATE WORD AND ONE TONE MAP FOR THE WHOLE MODULE. The card and this
// screen showing a different colour for one state is exactly the drift B14
// rule 36 exists to stop, so the component travels rather than the map.
import { StateWord } from "@/features/integrations/IntegrationsTab";
// ⚠ **S144's PANEL TRAVELS RATHER THAN BEING COPIED.** *Regenerate key* shows
// the new key exactly once, and a second implementation of *show it once and
// store it nowhere* is how the two doors onto that act would come to disagree.
import { IssuedKeyPanel } from "@/features/integrations/MachineKeysPage";
import { PlatformTextsPanel } from "@/features/integrations/PlatformTextsPanel";
import { refusalText } from "@/api/refusalText";
import { Button, ButtonLink } from "@/components/Button";
import { Chip } from "@/components/Chip";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { DataTable } from "@/components/DataTable";
import { DateCell, formatDate } from "@/components/DateCell";
import type { RegionalDateFormat } from "@/components/DateCell";
import { FilterBar } from "@/components/FilterBar";
import { KPIStrip } from "@/components/KPIStrip";
import type { KpiTile } from "@/components/KPIStrip";
import { Panel } from "@/components/Panel";
import { PlainTable } from "@/components/Surfaces";
import { PageHeader } from "@/components/PageHeader";
import { RowAction, RowActions } from "@/components/RowActions";
import { FieldStack, FormModal, PasswordField, SelectField, TextField } from "@/components/FormModal";
import type { FormSubmitOutcome } from "@/components/FormModal";
import { FailedWithRetry, LoadingSkeleton } from "@/components/StateFrame";
import { useToast } from "@/components/Toast";
import { Note } from "@/components/TextBits";
import { EyeIcon, PencilIcon, TrashIcon } from "@/components/icons";
import { Switch } from "@/components/Switch";
import { defaultRequestState } from "@/components/tableTypes";
import type { TableConfig, TableFilterConfig, TableRequestState } from "@/components/tableTypes";
import { WarningBox } from "@/components/WarningBox";
import { useTenantPath } from "@/routing/tenantPath";
import { useRegional } from "@/features/metering/meteringShared";

const INTEGRATIONS_ROUTE = "/settings/integrations";
/**
 * S147's address — the connector SET-UP form, which is where both *Connect* and
 * *Edit* go.
 *
 * ⚠ **`connectors`, NOT `integrations`, AND THE TWO WORDS COEXIST ON PURPOSE.**
 * `App.tsx` mounts S147 at `settings/connectors/:providerKey/configure` and
 * this screen at `settings/integrations/:key`; the 16 Sep route ruling kept the
 * shipped address and gave the new screen the ruled word. Getting it wrong here
 * opens the *not built yet* page, which is the miss `ConnectorSetupRoute.test.tsx`
 * exists for.
 *
 * ⚠ **NO PROVIDER IS NAMED AND NONE EVER MAY BE** (`BR-INT-037`, `G77`).
 */
const CONNECTORS_ROUTE = "/settings/connectors";

/**
 * THE *WHERE* SLOT — one segment, because B14 rule 33 caps a FACT at six words.
 *
 * The identity line printed the whole of `describe` and, on the six connectors
 * whose key we issue, the whole of the composed hint-plus-labels line:
 * `••••0a19 · Read bills, Read customers, Read the ledger, Read payments` —
 * eight words where the rule allows six. Measured across the demo tenant, the
 * first segment is the useful one every time: `billing@example.invalid` of
 * *billing@example.invalid · Custom SMTP*, `Site SITE-4417` of *Site SITE-4417 ·
 * Water meter cloud*, `••••0a19` of the key line.
 *
 * ⚠ **THE SERVER IS NOT CHANGED.** The whole line is still what the API serves
 * and what the grid's *Where* column reads; this is one screen's display
 * decision and not a narrowing of the contract.
 */
function whereWords(line: string): string {
  return (line.split("\u00b7")[0] ?? "").trim();
}

/**
 * The outcomes on which a count would be a CLAIM. On these the tiles read a
 * dash: the far end did not tell us, and a zero is an answer we do not have.
 */
const UNKNOWABLE: readonly (RunOutcome | null)[] = ["unconfirmed", "indeterminate"];

/** The word's colour. `unconfirmed` is amber — its own thing, never green. */
const OUTCOME_TONE: Record<string, string> = {
  succeeded: "text-success-700",
  partial: "text-danger-700",
  failed: "text-danger-700",
  unconfirmed: "text-warning-700",
  indeterminate: "text-warning-700",
  queued: "text-neutral-600",
  running: "text-neutral-600",
  //: CR-069 wave I. `skipped` is *we did not ask* — the third kind of
  //: not-knowing (BR-INT-024), and the outcome of a refused duplicate file.
  //: Neutral rather than amber: nothing went wrong, we declined to act.
  skipped: "text-neutral-600",
};

type Translate = (key: string, options?: Record<string, unknown>) => string;

function outcomeWord(t: Translate, outcome: RunOutcome | null): string {
  if (outcome === null) return t("integrations.runs.outcome.running");
  return t(`integrations.runs.outcome.${outcome}`, { defaultValue: outcome });
}

/**
 * THE RESULT CELL, and it is one string because frame 25.2 draws one column:
 *
 *   succeeded    *93 of 93*
 *   partial      *86 of 93 · 7 bad addresses*   (· *2 already had* · *6 revised*)
 *   unconfirmed  *Unconfirmed · 93 sent, provider did not say*
 *   failed       *Failed*  (· *93 refused* when there was more than one)
 *
 * The numbers speak for the first two, so no word is added to them; the last
 * two have a word BECAUSE the numbers cannot say what happened. The colour is
 * the same decision — amber for a run that could not tell us, and never green.
 */
function countLine(t: Translate, row: RunRow): string {
  const failureWord = () =>
    t(`integrations.runs.failed.${row.operation}`, {
      count: row.failed,
      defaultValue: t("integrations.runs.failedGeneric", { count: row.failed }),
    });
  if (UNKNOWABLE.includes(row.outcome)) {
    return `${outcomeWord(t, row.outcome)} · ${t("integrations.runs.count.unconfirmed", {
      attempted: row.attempted,
    })}`;
  }
  if (row.outcome === "failed") {
    return row.attempted > 1
      ? `${outcomeWord(t, row.outcome)} · ${failureWord()}`
      : outcomeWord(t, row.outcome);
  }
  if (row.outcome === "queued" || row.outcome === "running" || row.outcome === null) {
    return outcomeWord(t, row.outcome);
  }
  /*
   * ⚠ `skipped` JOINS THEM, AND IT WAS FALLING THROUGH TO *0 of 0* (CR-069
   * wave I). A run we declined to place has `attempted = 0`, so the count
   * branch below rendered a perfectly formatted lie: *0 of 0* reads as a run
   * that tried nothing and succeeded at it. Nothing WAS attempted, so the
   * only honest cell is the word — and the run's own summary underneath is
   * where the reason lives (*refused duplicate — the same file as Tuesday
   * 06:10*). Every refused duplicate file closes on this outcome, so wave I
   * turned a rare cell into a common one.
   */
  if (row.outcome === "skipped") {
    return outcomeWord(t, row.outcome);
  }
  const parts = [
    t("integrations.runs.count.of", { succeeded: row.succeeded, attempted: row.attempted }),
  ];
  if (row.failed > 0) parts.push(failureWord());
  if (row.skipped > 0) {
    parts.push(
      t(`integrations.runs.skipped.${row.operation}`, {
        count: row.skipped,
        defaultValue: t("integrations.runs.skippedGeneric", { count: row.skipped }),
      }),
    );
  }
  if (row.show_changed && row.changed > 0) {
    parts.push(t("integrations.runs.changed", { count: row.changed }));
  }
  return parts.join(" · ");
}

/** The result cell, coloured. `data-run-counts` is what the walkthrough reads. */
function ResultCell(props: { row: RunRow }) {
  const { t } = useTranslation();
  const outcome = props.row.outcome ?? "running";
  const tone = OUTCOME_TONE[outcome] ?? "text-neutral-600";
  return (
    <span
      className={`text-sm font-semibold ${tone}`}
      data-run-counts={props.row.trace_id}
      data-outcome={outcome}
    >
      {countLine(t as Translate, props.row)}
    </span>
  );
}

/**
 * One tile of frame 51.1's four. `outcome` and not a boolean, on purpose —
 * see the header: the dash is a rule about what we know, not a display option.
 */
function CountTile(props: { label: string; value: number; outcome: RunOutcome | null; always?: boolean }) {
  const dashed = props.always !== true && UNKNOWABLE.includes(props.outcome);
  return (
    <div
      className="flex flex-col gap-1 border border-neutral-200 bg-surface px-3 py-2"
      data-count-tile={props.label}
      data-dashed={dashed ? "true" : "false"}
    >
      <span className="text-lead font-semibold text-neutral-900">
        {dashed ? "—" : props.value.toLocaleString()}
      </span>
      <span className="font-heading text-table-header uppercase tracking-table-header text-neutral-600">{props.label}</span>
    </div>
  );
}

/** *Support reference **4C71A0E5*** — the one identifier on this screen. */
function SupportRef(props: { trace: string }) {
  const { t } = useTranslation();
  return (
    <p className="text-xs text-neutral-600" data-support-ref={props.trace}>
      {t("integrations.runs.supportRef")}{" "}
      <span className="font-mono font-semibold text-neutral-900">{props.trace}</span>
    </p>
  );
}

/** Frame 53.2 — what a run that is STILL GOING says about itself.
 *
 *  ⚠ **THE SENTENCE AND THE TWO FIGURES ARE THREE CATALOGUE KEYS, NOT ONE.**
 *  A single interpolated string would force every translator into English word
 *  order (B14 rule 35 — a catalogue is written in its own language), and the
 *  middle dots are ELEMENTS rather than characters inside a message so the
 *  three parts stay separable when the band is read aloud or copied.
 *
 *  ⚠ AND IT DRAWS NOTHING WHEN THERE IS NOTHING TO DRAW. `collecting` is
 *  `null` for a finished run and for one whose job record cannot be read; a
 *  band that guessed *window 1 of 105* would be a claim about a walk nobody
 *  can see. */
function CollectingBand({ collecting }: { collecting: RunDetail["collecting"] }) {
  const { t } = useTranslation();
  if (collecting === null) return null;
  const asking = collecting.asked !== undefined && collecting.asked !== null;
  const walking = collecting.window !== undefined && collecting.window !== null;
  if (!asking && !walking) return null;
  return (
    <div
      className="flex flex-wrap items-baseline gap-2 border border-neutral-300 bg-surface p-2 text-sm text-neutral-800"
      data-collecting={asking ? "poll" : "walk"}
    >
      {asking && <span>{t("integrations.runs.collecting.sentence")}</span>}
      {asking && <span aria-hidden="true" className="text-neutral-400">·</span>}
      {asking && (
        <span data-collecting-asked={String(collecting.asked)}>
          {t("integrations.runs.collecting.asked", { count: collecting.asked ?? 0 })}
        </span>
      )}
      {asking && collecting.next_in_s !== undefined && collecting.next_in_s !== null && (
        <span aria-hidden="true" className="text-neutral-400">·</span>
      )}
      {asking && collecting.next_in_s !== undefined && collecting.next_in_s !== null && (
        <span>
          {t("integrations.runs.collecting.nextIn", { seconds: collecting.next_in_s })}
        </span>
      )}
      {walking && (
        <span data-collecting-window={String(collecting.window)}>
          {t("integrations.runs.collecting.window", {
            done: collecting.window,
            total: collecting.of,
          })}
        </span>
      )}
    </div>
  );
}

interface RunCardProps {
  run: RunDetail;
  timeZone: string;
  dateFormat: RegionalDateFormat;
  onClose: () => void;
}

/** Template I4 — a run, opened. Frames 51.1 and 51.2. */
function RunCard(props: RunCardProps) {
  const { t } = useTranslation();
  const run = props.run;
  const unknowable = UNKNOWABLE.includes(run.outcome);
  return (
    <section
      className="flex flex-col gap-3 border border-neutral-300 bg-bg p-4"
      data-run-card={run.trace_id}
      aria-label={t("integrations.runs.openTitle", { operation: run.operation_label })}
    >
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="text-base font-semibold text-neutral-900">
          {run.operation_label} ·{" "}
          <DateCell
            value={run.started_at}
            timeZone={props.timeZone}
            dateFormat={props.dateFormat}
            withTime
          />
        </h3>
        <ResultCell row={run} />
      </div>

      {/* rule 32: one sentence, and it is the runtime's own. */}
      {run.summary !== null && <p className="text-sm text-neutral-700">{run.summary}</p>}

      <CollectingBand collecting={run.collecting} />

      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        <CountTile
          label={t("integrations.runs.tile.attempted")}
          value={run.attempted}
          outcome={run.outcome}
          always
        />
        <CountTile
          label={t("integrations.runs.tile.succeeded")}
          value={run.succeeded}
          outcome={run.outcome}
        />
        <CountTile
          label={t("integrations.runs.tile.failed")}
          value={run.failed}
          outcome={run.outcome}
        />
        <CountTile
          label={
            run.show_changed
              ? t("integrations.runs.tile.changed")
              : t("integrations.runs.tile.skipped")
          }
          value={run.show_changed ? run.changed : run.skipped}
          outcome={run.outcome}
        />
      </div>

      {unknowable && <Note>{t("integrations.runs.dashesNote")}</Note>}

      {run.items.length > 0 && (
        <>
          <h4 className="font-heading text-table-header uppercase tracking-table-header text-neutral-600">
            {t("integrations.runs.itemsTitle", { count: run.items.length })}
          </h4>
          <ul className="flex flex-col gap-1" data-run-items={run.items.length}>
            {run.items.map((item, index) => (
              <li
                key={`${item.ref ?? "item"}-${index}`}
                className="flex flex-wrap items-baseline gap-2 border-b border-neutral-200 pb-1 text-sm"
                data-run-item={item.detail ?? item.ref ?? ""}
              >
                {/* Frame 51.1 draws *A-10432 · j.doe@… · No such mailbox*, and the
                    middle dots are ELEMENTS rather than part of any string: they
                    separate the three parts when the row is read aloud or copied,
                    which flexbox spacing alone does not do. */}
                {item.ref !== null && (
                  <span className="font-mono text-xs text-neutral-600">{item.ref}</span>
                )}
                {item.ref !== null && item.detail !== null && (
                  <span aria-hidden="true" className="text-neutral-400">·</span>
                )}
                {item.detail !== null && (
                  <span className="text-neutral-900">{item.detail}</span>
                )}
                {item.detail !== null && item.provider_text !== null && (
                  <span aria-hidden="true" className="text-neutral-400">·</span>
                )}
                {item.provider_text !== null && (
                  <span className="text-neutral-600">{item.provider_text}</span>
                )}
              </li>
            ))}
          </ul>
        </>
      )}

      {run.unnamed_items > 0 && (
        <Note>{t("integrations.runs.unnamed", { count: run.unnamed_items })}</Note>
      )}

      {/* Frame 52.2: our sentence first, THEIR words underneath — because one
          is actionable and the other is what support needs. This is the only
          screen in the product that renders `provider_error`, and only to the
          utility that owns the run. */}
      {run.provider_error !== null && (
        <div className="flex flex-col gap-1">
          <span className="font-heading text-table-header uppercase tracking-table-header text-neutral-600">
            {t("integrations.runs.providerSaid")}
          </span>
          <p
            className="border border-neutral-300 bg-surface p-2 font-mono text-xs text-neutral-800"
            data-provider-said=""
          >
            {run.provider_error}
          </p>
        </div>
      )}

      {/* Frame 83.1 — *what we ask them for*. `US-INT-035`/`C18`: four of one
          supplier's request parameters have an unsafe default and two of them
          are on the money path, so the ones we STATE are shown rather than
          left to be trusted. Absent entirely for an operation with none —
          B14 rule 32's stated-absence-closed-by-default. */}
      {run.asked_for.length > 0 && (
        <div className="flex flex-col gap-1" data-asked-for={run.asked_for.length}>
          <span className="font-heading text-table-header uppercase tracking-table-header text-neutral-600">
            {t("integrations.runs.askedForTitle")}
          </span>
          <ul className="flex flex-wrap gap-2">
            {run.asked_for.map((name) => (
              <li
                key={name}
                className="border border-neutral-300 bg-surface px-2 py-1 font-mono text-xs text-neutral-800"
              >
                {name}
              </li>
            ))}
          </ul>
          <Note>{t("integrations.runs.askedForNote")}</Note>
        </div>
      )}

      {/* The file the vendor built, once it is in hand. `BR-INT-046`: the run
          is not finished until it is, so a link here is the proof rather than
          a convenience. */}
      {run.artifact_link !== null && run.artifact_link !== "" && (
        <p className="text-sm">
          <a
            className="text-brand underline"
            href={run.artifact_link}
            data-run-artifact=""
            rel="noreferrer"
          >
            {t("integrations.runs.artifact")}
          </a>
        </p>
      )}

      {run.content_hash !== null && (
        <p className="font-mono text-xs text-neutral-600">
          {t("integrations.runs.contentHash", { hash: run.content_hash })}
        </p>
      )}

      <SupportRef trace={run.trace_id} />

      <div className="flex flex-wrap gap-2">
        <Button type="button" variant="secondary" size="sm" onClick={props.onClose}>
          {t("integrations.runs.close")}
        </Button>
      </div>
    </section>
  );
}

/** Cells for the SEED config only — `defaultRequestState` reads the sort and
 *  nothing else, and a config cannot be built without them. */
const EMPTY_CELLS = {
  when: () => null,
  what: () => null,
  result: () => null,
  open: () => null,
};

/** r10's own badge for this screen (`g29_allocated_badges.txt`, INT-02). */
export const CONNECTION_DETAIL_SCREEN = "INT-02";

/**
 * The drawn WHEN words, by trigger — the ENGLISH fallback for
 * `integrations.when.*`, written out rather than left to `t()`'s key-as-
 * fallback, which is exactly how `ACCOUNTING · OUT.THEM` once reached a clerk
 * (`DEF-INT-5491`).
 *
 * ⚠ **`partner` AND `webhook` SAY THE SAME FIVE WORDS BECAUSE THE DRAWING
 * DOES.** p064's sandbox row and p066's three Aclarian rows both read *They
 * call us*: the clerk's question is who places the call, and both triggers
 * answer *them*. `ConnectorSetupPage`'s `TRIGGER_WORDS` is the same list for
 * the same reason and the two files are asserted against each other.
 */
const WHEN_FALLBACK: Record<string, string> = {
  scheduled: "On a schedule",
  manual: "On demand",
  dispatcher: "By a bill run",
  webhook: "They call us",
  partner: "They call us",
  inline: "While you wait",
};

/**
 * S142's run table, DECLARED — `EP-INT-06`'s capability-matrix row made into
 * the one list assembly (`DataTable`), not a hand-rolled toolbar.
 *
 * ⚠ IT WAS HAND-ROLLED FIRST, AND B14 RULE 36 IS WHY IT IS NOT ANY MORE (PO
 * 2026-09-04: *"style guide should be from r10 agreement … also toolkit is not
 * align"*). A search box, a select and a table built here would have been a
 * fourth search box, a fourth filter control and a fourth pagination footer;
 * `r10` rules 12, 13, 15 and 16 are one assembly and the kit already is it.
 *
 * ⚠ AND THE PAGE SIZE MOVED WITH IT, WHICH IS A STAMPED DEVIATION. The
 * capability matrix says *"Twenty rows by default"*; this product has ONE
 * page-size vocabulary — 50 · 100 · 200 · 500 · 1000, PO ruling 2026-08-09 —
 * and a table defaulting to a size its own picker cannot express would be a
 * second way of paginating on one screen. The first page is fifty.
 */
export function runsTableConfig(
  t: Translate,
  cells: {
    when: (row: RunRow) => ReactNode;
    what: (row: RunRow) => ReactNode;
    result: (row: RunRow) => ReactNode;
    open: (row: RunRow) => ReactNode;
  },
  filters: TableFilterConfig[],
): TableConfig<RunRow> {
  return {
    screenId: CONNECTION_DETAIL_SCREEN,
    getRowId: (row) => row.id,
    // B14 rule 19 — what the search MATCHES, and it is one thing: the eight
    // characters a support agent is read down the telephone.
    searchFields: ["trace_id"],
    searchPlaceholder: "integrations.runs.search",
    filters,
    defaultSort: { sort: "started", dir: "desc" },
    columns: [
      { key: "when", label: t("integrations.runs.column.when"), sortable: true, identity: true, cell: cells.when },
      { key: "what", label: t("integrations.runs.column.what"), cell: cells.what },
      { key: "result", label: t("integrations.runs.column.result"), cell: cells.result },
      {
        key: "trace",
        label: t("integrations.runs.supportRef"),
        cell: (row) => <span className="tabular-nums">{row.trace_id}</span>,
      },
      { key: "open", label: t("integrations.runs.column.open"), cell: cells.open },
    ],
  };
}

// The client-side shape check. UX only — the SERVER is authoritative (B8),
// and it is the server that knows this manifest declares a `password` field at
// all. A blank password here would be refused by `validate_fields` anyway; the
// schema saves the round trip.
const credentialSchema = z.object({ password: z.string().min(1) });

// ── ManagePanel — template I3's ButtonRow, and the keys table of frame 54.2 ──
//
// ⚠ THE ORDER OF THE THREE CONTROLS IS THE ORDER OF THE RISK, and it is not
// alphabetical or accidental: *Replace password* (routine), *Roll back*
// (recovery), *Disconnect* (destructive, danger tier — B14 rule 6). Roll back
// is drawn ONLY where there is a previous version: a control whose whole
// purpose is to produce *Nothing to roll back to.* is a button wired to a
// refusal, which is hard-won law 2 wearing a nicer coat. The refusal still
// guards the endpoint, for the case where two people press at once.
//
// ⚠ THE HISTORY IS FOUR CHARACTERS AND A DATE, AND THAT IS ALL THERE IS.
// `CredentialVersion` has no field a password could travel in, so this
// component could not render one if a later lane wanted it to (BR-INT-003).
// The note under the table says so to the reader in as many words, because a
// person about to replace a password wants to know they cannot get the old
// one back by looking.

function CredentialHistory(props: {
  rows: CredentialVersion[];
  timeZone: string;
  dateFormat: RegionalDateFormat;
}) {
  const { t } = useTranslation();
  if (props.rows.length === 0) {
    return <Note>{t("integrations.credential.empty")}</Note>;
  }
  return (
    <ul className="divide-y divide-neutral-200" data-credentials={props.rows.length}>
      {props.rows.map((row) => (
        <li
          key={row.version}
          className="flex flex-wrap items-baseline justify-between gap-2 py-2"
          data-credential-version={row.version}
          data-credential-active={row.is_active ? "yes" : "no"}
        >
          <span className="font-mono text-sm text-neutral-900">{row.hint}</span>
          <span className="text-sm text-neutral-600">
            <DateCell
              value={row.created_at}
              timeZone={props.timeZone}
              dateFormat={props.dateFormat}
              withTime
            />
          </span>
          <span className="text-sm font-semibold text-neutral-900">
            {row.is_active
              ? t("integrations.credential.inUse")
              : t("integrations.credential.previous")}
          </span>
        </li>
      ))}
    </ul>
  );
}

/** The IS-6 consequence, in two labelled halves (template I7).
 *
 *  ⚠ `messages_waiting === null` DRAWS THE RECORDS LINE INSTEAD OF A ZERO, and
 *  that is deliberate: *nothing is waiting* and *we could not count* are
 *  different sentences and only one of them is reassuring. It is the rule
 *  `apps/billing/release.py` states about mandate coverage, kept on this side
 *  of the wire. */
function disconnectConsequence(t: Translate, preview: DisconnectPreview): string {
  const stops = t(`integrations.disconnect.stops.${preview.category}`, {
    defaultValue: t("integrations.disconnect.stops.default"),
  });
  const kept = [t("integrations.disconnect.keptRuns", { count: preview.runs_kept })];
  kept.push(
    preview.messages_waiting !== null && preview.messages_waiting > 0
      ? t("integrations.disconnect.keptWaiting", { count: preview.messages_waiting })
      : t("integrations.disconnect.keptRecords"),
  );
  return [
    `${t("integrations.disconnect.straightAway")}: ${stops} ${t("integrations.disconnect.secret")}`,
    `${t("integrations.disconnect.kept")}: ${kept.join(" ")}`,
  ].join("\n");
}

/**
 * ── KEYS WE ISSUE — the drawn panel, p062 and p066 ──────────────────────────
 *
 * `KEY · MAY CALL · ISSUED · STATE`, one row per key, newest first.
 *
 * ⚠ **WHY IT HAD TO EXIST, AND WHY ITS ABSENCE WAS WORSE THAN MISSING
 * (`DEF-INT-5533`).** A `they_hold_ours` connector is one we do not dial: the
 * partner holds a key WE issued. The screen drew *"Passwords on this
 * connection"* over those very keys and offered *Replace password*, so the one
 * panel a clerk needs was absent and the panel that was there named a thing
 * that does not exist. Both facts were on the wire the whole time — the card
 * has served `issued_keys` since wave R and the key's `scope` since the
 * key-scope wave — and no screen read either. That is hard-won law 2 with a
 * SERVED FIELD in place of a prop: nothing asks whether a field has a reader.
 *
 * ⚠ **`MAY CALL` IS OPERATION LABELS AND NOT THE CLERK'S OLD WORDS.** The
 * drawing's own summary line says *reads payments, bills* while its MAY CALL
 * cell says *Read payments, Read bills +1* — two vocabularies for one idea,
 * which is `DEF-INT-5504` exactly, and the `scopes` field that produced the
 * first set is retired in this same commit. One list of words, the operation
 * labels the table above already uses.
 *
 * ⚠ **THE DRAWN NOTE UNDER IT IS DELIBERATELY NOT BUILT** — *"May call is new.
 * Today one key opens every API on the connector — see CR-4."* Two reasons and
 * either is enough: it is no longer TRUE (CR-4's scoping is built — a key is
 * refused unless it names its operations), and it is RATIONALE, which B14 rule
 * 33 puts at zero words on screen. Recorded in `CR-110-BRC04` rather than
 * shipped as a sentence that would have to be believed.
 *
 * ⚠ **EVERY VERSION IS SHOWN, NOT ONLY THE LIVE ONE.** The frames draw one
 * row, which is an illustration under B14 rule 37; `STATE` is a drawn COLUMN,
 * and a column that can only ever say one thing is not a column. A revoked key
 * is the answer to *who could have read this last month*, and hiding it is the
 * one thing this panel exists to prevent.
 */
function KeysWeIssuePanel(props: {
  keys: IssuedKey[];
  operations: OperationRow[];
  providerKey: string;
  timeZone: string;
  dateFormat: RegionalDateFormat;
}) {
  const { t } = useTranslation();
  /** An operation NAME in the clerk's words. ⚠ Never the raw name — that is a
   *  code on a clerk's screen (B14 rule 31), and `serve_ledger` was on one:
   *  the run list showed it the day the fourth operation landed. */
  const label = (name: string): string => {
    const found = props.operations.find((one) => one.name === name);
    return found === undefined
      ? name
      : t(`integrations.provider.${props.providerKey}.operation.${name}`, {
          defaultValue: found.label,
        });
  };
  /** The drawn cell — two names then `+n`. A key on a sixteen-operation
   *  connector would otherwise be a paragraph inside a table cell. */
  const mayCall = (key: IssuedKey): string => {
    const names = key.scope ?? [];
    if (names.length === 0) {
      return t("integrations.keys.mayCallUnknown", { defaultValue: "Not recorded" });
    }
    const first = names.slice(0, 2).map(label).join(", ");
    return names.length > 2 ? `${first} +${names.length - 2}` : first;
  };
  return (
    <Panel as="section" title={t("integrations.keys.title")}>
      <PlainTable data-keys-table="">
        <thead>
          <tr>
            <th scope="col">{t("integrations.keys.column.key")}</th>
            <th scope="col">
              {t("integrations.keys.column.mayCall", { defaultValue: "May call" })}
            </th>
            <th scope="col">{t("integrations.keys.column.issued")}</th>
            <th scope="col">{t("integrations.keys.column.state")}</th>
          </tr>
        </thead>
        <tbody>
          {props.keys.map((one) => (
            <tr key={one.version} data-key-version={one.version}>
              <td>
                {/* The drawn cell is the hint in a bordered box — the mask and
                    four characters, which is the whole of what any screen ever
                    gets. There is no field on `IssuedKey` that could hold a
                    key, by design (`BR-INT-053`). */}
                <Chip data-key-hint="">{one.hint}</Chip>
              </td>
              <td data-may-call="">{mayCall(one)}</td>
              <td>{formatDate(one.issued_at, props.timeZone, props.dateFormat)}</td>
              <td data-key-state={one.state}>{t(`integrations.keys.state.${one.state}`)}</td>
            </tr>
          ))}
        </tbody>
      </PlainTable>
      {props.keys.length === 0 && (
        <Note>{t("integrations.keys.empty.helper")}</Note>
      )}
    </Panel>
  );
}

/**
 * ── CredentialPanel — what we hold, drawn where VIEW-10 draws it ────────────
 *
 * ⚠ **THIS IS HALF OF WHAT `ManagePanel` USED TO BE, AND THE SPLIT IS THE
 * DRAWING'S (`DEF-INT-5560`).** `VIEW-10` (p047–p048) puts the credential
 * panel — *Token we hold*, *••••7Q2F generated 12 Aug 2026 · In use* — under
 * the API table and ABOVE *Recent activity*, and puts the BUTTONS at the very
 * bottom of the page under the activity table. One component could not be in
 * both places, so it is two: the facts here, the controls in
 * `ConnectionFooter`. The PO read the difference off the running product —
 * *"this screen does not match with images in document - why?"*.
 *
 * ⚠ **A `<Panel>`, NOT A HAND-WRITTEN `<h2>` IN SMALL GREY CAPITALS.** p047
 * draws this heading exactly as it draws *Keys we issue* and *N APIs on this
 * connector*: sentence case, dark, the weight of the panels either side of it.
 * The kit already owns that heading (B14 rule 36), so the screen stops writing
 * its own.
 */
function CredentialPanel(props: {
  signInOnly: boolean;
  weIssueTheKey: boolean;
  operationCount: number;
  credentials: CredentialVersion[];
  timeZone: string;
  dateFormat: RegionalDateFormat;
}) {
  const { t } = useTranslation();
  // Nothing to draw where the key is OURS: `KeysWeIssuePanel` is this slot's
  // panel for those six connectors, and an empty second box would be hard-won
  // law 2 wearing a layout.
  if (props.weIssueTheKey) return null;
  return (
    <Panel
      as="section"
      data-credential-panel=""
      title={t(props.signInOnly ? "integrations.credential.titleSignIn" : "integrations.credential.title")}
    >
      <CredentialHistory
        rows={props.credentials}
        timeZone={props.timeZone}
        dateFormat={props.dateFormat}
      />
      <Note>
        {t(props.signInOnly ? "integrations.credential.noteSignIn" : "integrations.credential.note")}
      </Note>
      {/* ── CR-110-BRC04 wave B · *One key. All N APIs use it.* ─────────────
          Drawn under the credential panel on every `VIEW-` frame, and it is
          the sentence the PO's ruling of 2026-09-16 turns on — verbatim,
          *"i only want to issue a key per conenction … i dont understand the
          differnt between key and token"*.

          ⚠ **IT SAYS *KEY*, AND THE WORD *TOKEN* IS NOWHERE ON THIS SCREEN.**
          The drawing reads *One token. All 1 API use it.* and the ruling
          retires that vocabulary from the product.

          ⚠ **NOT SHOWN WHERE WE ISSUE THE KEY** — CR-4's scoping ended
          "one key opens every API", and the `Keys we issue` panel answers the
          same question honestly and per key, in its MAY CALL column. The
          whole component returns null there, so the guard is the `if` above. */}
      {props.operationCount > 0 && (
        <Note>
          {t("integrations.credential.oneKeyForAll", {
            count: props.operationCount,
            defaultValue_one: "One key. The {{count}} API uses it.",
            defaultValue_other: "One key. All {{count}} APIs use it.",
          })}
        </Note>
      )}
    </Panel>
  );
}

/**
 * ── ConnectionHeader — the page head, its actions and their dialogs ─────────
 *
 * ⚠ **THE ACTIONS ARE AT THE TOP, AND THAT OVERRIDES THE DRAWING (PO ruling
 * 2026-09-17, `DEF-INT-5579`).** Verbatim: *"actions on this screens - should
 * be on top - like we follow as per our ui guideline"*. `VIEW-17` draws them in
 * a footer at the very bottom of p067 and `DEF-INT-5560` put them there on that
 * evidence, correctly. **B14 rule 38 is what settles it**: where a drawing and
 * our UI rules disagree about how a thing is BUILT, the UI rules win, because
 * construction would otherwise change on one screen's authority — and where a
 * detail screen's actions live is construction of exactly that kind. What the
 * drawing still decides is WHICH actions exist and what they do.
 *
 * ⚠ **THE HEADER AND ITS DIALOGS ARE ONE COMPONENT ON PURPOSE.** `PageHeader`
 * takes nodes for its slots, so a button that opens a confirm needs its state
 * SOMEWHERE — and putting it in the page body would leave the opener and the
 * thing it opens in two files that can drift. The issued-key panel renders
 * UNDER the head rather than inside the action row, because it is a secret to
 * be read and copied, not a control.
 *
 * ⚠ **THE ACTION SET IS READ OFF THE MANIFEST AND NEVER OFF A PROVIDER KEY**
 * (`BR-INT-037`; `G77` fails a provider-key branch). `auth.mode ===
 * "they_hold_ours"` is *we issue their key* — the five ERPs and the kiosk, six
 * of twenty-eight — and `auth.placement === "redirect"` is *they sign in*. A
 * twenty-ninth connector needs no line here.
 */
function ConnectionHeader(props: {
  providerKey: string;
  providerName: string;
  /** `ERP`, already resolved to the clerk's word by the caller. */
  categoryWord: string;
  /** *They read* · *We collect* — the UNION over the operations, in the drawn
   *  order and de-duplicated. Composed by the caller, which already does it. */
  directionWords: readonly string[];
  displayState: DisplayState;
  connection: ConnectionRow | null;
  /** The one-segment *where* — see `whereWords` in the page below. */
  where: string;
  weIssueTheKey: boolean;
  signInOnly: boolean;
  comingSoon: boolean;
  /** What a regenerated key would reach. The LIVE key's own scope when there is
   *  one, so a regenerate can neither widen nor narrow it by accident — the
   *  reasoning `ConnectorSetupPage` already records for the same act. */
  scope: readonly string[];
  keysPath: string | null;
  /** `CR-174-BRC10` — S143's address when the connector ships a vocabulary
   *  of their words, else null (no door onto an empty room). */
  mappingsPath?: string | null;
  setupPath: string;
  backTo: string;
  credentials: CredentialVersion[];
  preview: DisconnectPreview | null;
  client: ApiClient;
  onChanged: () => void;
}) {
  const { t } = useTranslation();
  const toast = useToast();
  const [replacing, setReplacing] = useState(false);
  const [password, setPassword] = useState("");
  const [confirmingDisconnect, setConfirmingDisconnect] = useState(false);
  const [confirmingRegenerate, setConfirmingRegenerate] = useState(false);
  /** The one copy of a regenerated key, for as long as the panel is open.
   *  ⚠ **NEVER CACHED**, for the reason `issuePartnerKey`'s own docstring
   *  gives: a cached secret sits in browser memory for the life of the tab.
   *  S144 holds it exactly this way and this screen does not invent a second
   *  rule for the same act. */
  const [justIssued, setJustIssued] = useState<string | null>(null);
  const [refusal, setRefusal] = useState<string | null>(null);

  const rollback = useMutation({
    mutationFn: () => rollbackCredential(props.client, props.providerKey),
    onSuccess: () => {
      toast(t("integrations.credential.rolledBack"));
      props.onChanged();
    },
  });
  const disconnect = useMutation({
    mutationFn: () => disconnectIntegration(props.client, props.providerKey),
    onSuccess: () => {
      setConfirmingDisconnect(false);
      toast(t("integrations.disconnect.toast"));
      props.onChanged();
    },
  });
  const reauthorise = useMutation({
    mutationFn: async () => {
      const started = await startOAuth(
        props.client,
        props.providerKey,
        `${window.location.origin}${window.location.pathname}`,
      );
      window.location.assign(started.authorize_url);
    },
  });
  /**
   * ⚠ **THE SAME MUTATION `MachineKeysPage` CALLS, AND NOT A SECOND ENDPOINT.**
   * `issuePartnerKey` retires the live key and mints its replacement in one
   * request; S144 labels that act *Replace key* and this screen labels it
   * *Regenerate key*, which is the PO's word — *"you did not inlcude
   * rEgenerate Keys button"*. Two doors onto ONE act, with one implementation,
   * because a second copy of *issue · hold · show once · drop* is how the two
   * would come to disagree about the rule that matters.
   */
  const regenerate = useMutation({
    mutationFn: () => issuePartnerKey(props.client, props.providerKey, props.scope),
    onSuccess: (result) => {
      setRefusal(null);
      setConfirmingRegenerate(false);
      setJustIssued(result.key); // the only copy — component state, never cache
      toast(t("integrations.keys.issued"));
      props.onChanged();
    },
    onError: (error) => {
      setConfirmingRegenerate(false);
      setRefusal(refusalText(t, error));
    },
  });

  const connected = props.connection !== null;
  const hasPrevious = props.credentials.length > 1;

  /**
   * THE ACTION ROW, BY STATE — the ratified table, in one expression so a
   * reader can see all five cases at once rather than hunting five `&&`s.
   *
   * ⚠ **`Keys` APPEARS ONLY WHERE WE ISSUE ONE — six manifests of twenty-eight.**
   * Elsewhere it opens a screen with nothing on it, which is hard-won law 2's
   * mirror: a live door onto an empty room.
   *
   * ⚠ **A *coming soon* CONNECTOR GETS NOTHING AT ALL.** The server refuses the
   * connect (`BR-INT-001`), so every control here would lead to a refusal — and
   * the page already says *Coming soon* in its own words.
   */
  const secondaries: ReactNode[] = [];
  // `CR-174-BRC10` — the door to S143, in BOTH states: a connector whose
  // fallback word is unmapped cannot be switched on, so the mapping has to be
  // reachable BEFORE it is connected as well as after.
  if (!props.comingSoon && props.mappingsPath) {
    secondaries.push(
      <ButtonLink key="mappings" to={props.mappingsPath} variant="secondary" data-mappings-door="">
        {t("integrations.setup.mapWords")}
      </ButtonLink>,
    );
  }
  const primary: ReactNode = (() => {
    if (props.comingSoon) return null;
    if (!connected) {
      // Not set up: ONE door, and it is the set-up screen rather than a modal
      // (`DEF-INT-5513` moved the grid's own Connect there for the same reason).
      return (
        <ButtonLink to={props.setupPath} variant="primary" data-connect="">
          {t("integrations.actions.connect")}
        </ButtonLink>
      );
    }
    secondaries.push(
      <ButtonLink key="edit" to={props.setupPath} variant="secondary" data-edit="">
        {t("integrations.actions.edit")}
      </ButtonLink>,
    );
    if (props.weIssueTheKey && props.keysPath !== null) {
      // A LINK because it NAVIGATES — middle-click and *open in new tab* work,
      // which is the reasoning the grid's own row links already carry.
      secondaries.push(
        <ButtonLink key="keys" to={props.keysPath} variant="secondary" data-keys-link="">
          {t("integrations.actions.keys")}
        </ButtonLink>,
      );
    }
    if (hasPrevious && !props.weIssueTheKey) {
      // ⚠ KEPT RATHER THAN DROPPED. The ratified table names five actions and
      // not this one, and the ruling was about WHERE the actions live. Deleting
      // a working control nobody asked to remove would be a product change
      // smuggled in as a layout change, so it moves up with the rest.
      secondaries.push(
        <Button
          key="rollback"
          variant="secondary"
          disabled={rollback.isPending}
          onClick={() => rollback.mutate()}
        >
          {t("integrations.credential.rollback")}
        </Button>,
      );
    }
    if (props.preview !== null) {
      secondaries.push(
        <Button
          key="disconnect"
          variant="danger"
          data-disconnect=""
          onClick={() => setConfirmingDisconnect(true)}
        >
          {t("integrations.disconnect.action")}
        </Button>,
      );
    }
    /*
     * ⚠ **REGENERATE KEY IS THE *PRIMARY* BUTTON AND OPENS A *RED* CONFIRM, AND
     * THAT IS B14 RULE 6 READ EXACTLY.** The danger tier belongs on the
     * destructive COMMIT — the dialog's confirm — and not on the opener. It is
     * the act a clerk comes to this screen to perform, so it is the loud one;
     * it breaks the partner's live integration the moment it lands, so the
     * consequence is read before it is taken.
     */
    if (props.weIssueTheKey) {
      return (
        <Button
          variant="primary"
          data-regenerate-key=""
          disabled={regenerate.isPending}
          onClick={() => setConfirmingRegenerate(true)}
        >
          {t("integrations.regenerate.action")}
        </Button>
      );
    }
    if (props.signInOnly) {
      // ⚠ *Replace password* ON A SIGN-IN CONNECTION OPENED A FORM THE SERVER
      // WOULD REFUSE (`DEF-INT-4237`): `email_microsoft` declares no field of
      // kind `secret`, so the password it collected arrives as an unknown field.
      // The round trip is the thing a clerk actually needs here.
      return (
        <Button
          variant="primary"
          disabled={reauthorise.isPending}
          onClick={() => reauthorise.mutate()}
          data-reauthorise="head"
        >
          {t("integrations.expiry.reauthorise")}
        </Button>
      );
    }
    return (
      <Button variant="primary" data-replace-password="" onClick={() => setReplacing(true)}>
        {t("integrations.credential.replace")}
      </Button>
    );
  })();

  return (
    <>
      <PageHeader
        title={props.providerName}
        /* ⚠ THE KICKER IS *ERP · THEY READ*, WHICH IS WHAT p067 DRAWS ON THE
           SET-UP FRAME AND WHAT THE PO ASKED THIS SCREEN TO CARRY — *"can you
           include some of the missing data from this into header"*. It read
           the literal word *Connector* until 2026-09-17, which told a reader
           what kind of PAGE they were on and nothing about the connector. */
        kicker={[props.categoryWord, ...props.directionWords].join(" · ")}
        /* The state sits WITH THE IDENTITY and not in the action row — the
           shared header's own rule (`DEF-966`), so ~20 detail screens agree. */
        status={
          <span
            className="text-sm font-semibold text-neutral-900"
            data-display-state={props.displayState}
          >
            <StateWord state={props.displayState} dot />
          </span>
        }
        rollup={
          props.connection === null ? undefined : (
            <span data-meta="">
              {[
                t(`integrations.environment.${props.connection.environment}`),
                props.where,
                ...(props.connection.connected_by !== null
                  ? [t("integrations.runs.connectedBy", { name: props.connection.connected_by })]
                  : []),
              ]
                .filter((one) => one !== "")
                .join(" · ")}
            </span>
          )
        }
        backTo={{ to: props.backTo, label: t("integrations.runs.backTo") }}
        secondaryActions={secondaries.length > 0 ? <>{secondaries}</> : undefined}
        primaryAction={primary ?? undefined}
      />

      {refusal !== null && (
        <p className="text-sm text-danger-700" data-key-refusal="" role="alert">
          {refusal}
        </p>
      )}
      {rollback.isError && <Note>{refusalText(t, rollback.error)}</Note>}

      {/* THE KEY, ONCE. `IssuedKeyPanel` is S144's component and it travels
          rather than being copied — one panel, one *Copy it now* sentence, one
          rule about a secret that is shown once and stored nowhere. */}
      {justIssued !== null && (
        <IssuedKeyPanel value={justIssued} onDone={() => setJustIssued(null)} />
      )}

      {confirmingRegenerate && (
        <ConfirmDialog
          title={t("integrations.regenerate.title")}
          /* B14 rule 33: a CONSEQUENCE before an irreversible act is at most
             two sentences of six words. Two of five. */
          consequence={t("integrations.regenerate.consequence")}
          confirmLabel={t("integrations.regenerate.action")}
          confirmVariant="danger" // rule 6 — the tier is on the COMMIT
          working={regenerate.isPending}
          onConfirm={() => regenerate.mutate()}
          onCancel={() => setConfirmingRegenerate(false)}
        />
      )}

      {replacing && (
        <FormModal
          title={t("integrations.credential.replaceTitle")}
          schema={credentialSchema}
          values={{ password }}
          submitLabel={t("integrations.credential.save")}
          onClose={() => {
            setReplacing(false);
            setPassword("");
          }}
          onSubmit={async () => {
            const outcome = await rotateCredential(props.client, props.providerKey, { password });
            setReplacing(false);
            setPassword("");
            toast(t("integrations.credential.saved"));
            props.onChanged();
            return { ok: true, value: outcome };
          }}
        >
          <PasswordField
            id="integration-credential"
            label={t("integrations.credential.field")}
            value={password}
            onChange={setPassword}
            required
            autoComplete="new-password"
          />
        </FormModal>
      )}

      {confirmingDisconnect && props.preview !== null && (
        <ConfirmDialog
          title={t("integrations.disconnect.title", { name: props.providerName })}
          consequence={disconnectConsequence(t as Translate, props.preview)}
          confirmLabel={t("integrations.disconnect.action")}
          confirmVariant="danger"
          typeToConfirm={props.providerName}
          working={disconnect.isPending}
          onConfirm={() => disconnect.mutate()}
          onCancel={() => setConfirmingDisconnect(false)}
        />
      )}
    </>
  );
}

/**
 * ── ConnectionFooter — the drawn footer row, now the footnote alone ─────────
 *
 * ⚠ **IT LOST ITS BUTTONS ON 2026-09-17 AND KEPT ITS NOTE, AND BOTH HALVES ARE
 * THE RULING.** The PO moved the controls to the page head — *"actions on this
 * screens - should be on top"* — and said nothing about the append-only
 * footnote, which p067 draws right-aligned on that same row. A drawing is still
 * the authority for everything the ruling did not move (B14 rule 41), so the
 * row stays where it is drawn with one child instead of two.
 *
 * ⚠ **`ml-auto` AND NOT `justify-end`, UNCHANGED FROM `DEF-INT-5560`.** With
 * the buttons gone this is now the only child, and `ml-auto` is what keeps it
 * at the far edge; `justify-between` alone would leave a lone child on the left.
 *
 * ⚠ **NOTHING ELSE MOUNTS THIS.** Grepped before the shape changed, which is
 * hard-won law 2's mirror read as blast radius: `ConnectionDetailPage.tsx` is
 * the only caller, and `[data-connection-footer]` is read by
 * `ConnectionDetailPage.test.tsx` and by
 * `10-scripts/cr110_wave_b_connection_view_walkthrough.mjs`, both of which ask
 * about the NOTE and neither about a button.
 */
function ConnectionFooter() {
  const { t } = useTranslation();
  return (
    <section
      className="mt-2 flex flex-wrap items-center justify-between gap-3 border-t border-divider pt-4"
      data-manage=""
      data-connection-footer=""
    >
      <Note className="ml-auto text-right" data-runs-foot="">
        {t("integrations.runs.foot")}
      </Note>
    </section>
  );
}

/**
 * The dated warning, and the button that ends it (frame `54.1`).
 *
 * ⚠ **THE DATE IS RENDERED THROUGH `formatDate`, IN THE TENANT'S OWN FORMAT.**
 * Frame 54.1 draws *"by 12 September"*, and every wave walked in a browser on
 * 2026-09-05 turned up clerk-facing dates written the way a computer writes
 * them — `2026-09-06` where the tenant had asked for `09/06/2026`. A month name
 * typed here would be a SECOND formatting path (BR-SHL-023 keeps one) and would
 * read as English in all eleven catalogues. So the sentence takes the date as a
 * parameter and the tenant's Regional setting decides how it reads; the
 * deviation from the frame's exact wording is stamped in `08-screen-layouts.md`.
 */
function ExpiryWarning(props: {
  connection: ConnectionRow;
  providerKey: string;
  client: ApiClient;
}) {
  const { t } = useTranslation();
  const { timeZone, dateFormat } = useRegional({});
  const expiry = props.connection.expiry;

  // ⚠ THE BUTTON IS THE TRIP, NOT A LINK TO A PAGE THAT WOULD HOST IT. Frame
  // 54.1 draws *Re-authorise now*, and the execution plan says in as many words
  // that it "is the return trip". Pointing it at a route would mean inventing a
  // screen whose only job is to redirect — and a control aimed at an address
  // nothing serves is exactly the dead door of DEF-CWP-3925.
  const reauthorise = useMutation({
    mutationFn: async () => {
      const started = await startOAuth(
        props.client,
        props.providerKey,
        `${window.location.origin}${window.location.pathname}`,
      );
      // The provider owns the next screen. `assign` rather than `replace`, so
      // the browser's Back button still returns a person who changed their mind
      // to the connection they were looking at.
      window.location.assign(started.authorize_url);
    },
  });

  // `ok` and `unknown` draw nothing at all. A box that is sometimes merely
  // interesting is a box people stop reading (B14 rule 32 — a stated absence is
  // CLOSED by default), and `unknown` means there is no credential to have an
  // opinion about, which the card's own state word already says.
  if (expiry.state !== "warning" && expiry.state !== "lapsed") {
    return null;
  }
  const lapsed = expiry.state === "lapsed";
  const when =
    expiry.expires_at === null ? null : formatDate(expiry.expires_at, timeZone, dateFormat);

  return (
    <WarningBox
      tone={lapsed ? "now" : "soon"}
      data-warning={lapsed ? "lapsed" : "expiring"}
      sentence={
        lapsed || when === null
          ? t("integrations.expiry.lapsedBox")
          : t("integrations.expiry.warning", { date: when })
      }
      note={t("integrations.expiry.reassure")}
      action={
        <Button
          variant="primary"
          onClick={() => reauthorise.mutate()}
          disabled={reauthorise.isPending}
          data-reauthorise=""
        >
          {t("integrations.expiry.reauthorise")}
        </Button>
      }
    />
  );
}



/**
 * ── `CR-115-BRC05` §7 · CUSTOM APIs ON A CONNECTOR ──────────────────────────
 *
 * **THE KIND IS OURS. THE NAME IS THEIRS** (§7.2, PO ruling 2026-09-17). A
 * clerk picks what SORT of call this is from a closed list WE ship, and gives
 * it their own name and their own address. The reasoning, the five rules and
 * the two deliberate absences live in `apps/integrations/custom_apis.py`'s own
 * docstring rather than being paraphrased here; this is what a clerk touches.
 *
 * ⚠ **THE CLOSED LIST IS THE SERVER'S AND IS NEVER TYPED HERE.** `kinds` comes
 * off the card. A React array of three would be the front end deciding what the
 * product can do — the shape `BR-INT-037` forbids, and the shape that let a
 * set-up screen answer differently from a view screen on 9 of 91 operations
 * (`DEF-INT-5613`).
 *
 * ⚠ **NO FIELD MAPPING, AND IT IS AN ABSENCE RATHER THAN AN OVERSIGHT.** PO
 * R35, verbatim: *"DOnt add field Mapping here - remove it"* — removed BY NAME.
 * Not reintroduced, not in a smaller form, not as a link. The product has a
 * mappings screen, per connector, and whether a per-API mapping should exist is
 * a separate decision that is not this screen's to take.
 *
 * ⚠ **NO KEY FIELD, AND NO KEY COLUMN — A DEFERRAL WE WROTE DOWN**
 * (`DEF-INT-5680`). §7.6: *"A key is a CREDENTIAL, not config … If per-API keys
 * need that changed, ship Name / Kind / URL / Enabled WITHOUT them and say
 * so."* A connection holds ONE credential today: encrypted, versioned, one
 * active row enforced by the database, shown once. Several per connection
 * touches that store, the *Keys in use* tile, rotation and expiry. The
 * blueprint's own `VIEW-25` frame says the same thing under this very table, in
 * as many words — **"One key. All 3 APIs use it."** — so a custom row sends the
 * connection's key exactly as the standard rows do, and the fact is stated once
 * in the key panel below rather than repeated down a column.
 *
 * ⚠ **BUILT FROM THE KIT, NOT HAND-ROLLED** (B14 rules 36 and 38). Rule 38:
 * *"where a drawing and our UI rules disagree about how a FORM IS BUILT, the UI
 * rules win"*. So the field anatomy (label → input → helper, rule 39), the
 * footer's button order and the commit tier all come from `FormModal`, and what
 * the form CONTAINS is still the ruling's to decide.
 */
function ApiFormModal(props: {
  providerKey: string;
  client: ApiClient;
  kinds: AddableKind[];
  /** Absent = ADD. Present = EDIT that row — R36's *"in table also give edit
   *  button"*. The Kind cannot move on an edit: see the field's own note. */
  editing?: OperationRow | null;
  onSaved: () => void;
  onClose: () => void;
}) {
  const { t } = useTranslation();
  const editing = props.editing ?? null;
  const [kind, setKind] = useState<string>(editing?.api_kind ?? "");
  const [name, setName] = useState<string>(editing?.custom_name ?? "");
  const [url, setUrl] = useState<string>(editing?.endpoint ?? "");

  /**
   * The refusal the SERVER would give for this Kind, served beside it.
   *
   * ⚠ **THE FORM AND THE SERVER SAY THE SAME SENTENCE BECAUSE IT IS THE SAME
   * KEY.** §7.5 rule 1 asks for the refusal *"at the form AND on the server"*,
   * and a form that invented its own wording would be two rules the day one of
   * them changed. `custom_apis.add` raises this exact catalogue key, and a
   * backend test asserts the two are equal.
   */
  const refusedKind =
    kind === "" ? null : (props.kinds.find((one) => one.kind === kind)?.refusal ?? null);

  async function submit(): Promise<FormSubmitOutcome> {
    try {
      if (editing !== null && editing.api_id != null) {
        await updateCustomApi(props.client, props.providerKey, editing.api_id, { name, url });
      } else {
        await addCustomApi(props.client, props.providerKey, { kind, name, url });
      }
      props.onSaved();
      return { ok: true };
    } catch (error) {
      // ⚠ **CAUGHT, NOT LET THROUGH.** `FormModal.handleSubmit` has only a
      // `finally`, so a thrown refusal escapes the frame and the clerk sees
      // nothing at all — the *silence* shape `G32` exists for. Mapped to the
      // envelope, the server's own sentence lands in the form's message slot.
      if (isApiError(error)) {
        return { ok: false, error: formErrorEnvelope(error) };
      }
      return { ok: false, error: { code: "", message_key: "api.error.unexpected" } };
    }
  }

  return (
    <FormModal
      title={t(
        editing !== null
          ? "integrations.customApi.editTitle"
          : "integrations.customApi.formTitle",
      )}
      schema={z.object({
        // Mirrors the server's own VAL codes (B8). These stop a pointless round
        // trip; the sentence a clerk reads for a REFUSAL is still the server's.
        kind: editing !== null ? z.string() : z.string().min(1),
        name: z.string().min(1),
        url: z.string().regex(/^https?:\/\//i),
      })}
      values={{ kind, name, url }}
      submitLabel={t(
        editing !== null
          ? "integrations.customApi.saveEdit"
          : "integrations.customApi.submit",
      )}
      /* §7.5 rule 1, AT THE FORM. `BR-SHL-025`'s shape: the control stays
         visible and carries its reason, rather than vanishing. */
      commitBlocked={refusedKind === null ? undefined : t(refusedKind)}
      onSubmit={submit}
      onClose={props.onClose}
    >
      <FieldStack>
        {/* ⚠ **KIND FIRST, AND IT IS THE ONLY OPTION ON AN EDIT.** *The kind is
            ours*: a clerk may rename their layer and re-point it, but changing
            what KIND of call it is would change which of OUR code runs it —
            that is a different API, not an edit of this one. Drawn as a select
            holding exactly its own value rather than as a disabled control,
            because the value is worth reading and there is nothing to choose. */}
        <SelectField
          id="custom-api-kind"
          label={t("integrations.customApi.kindLabel")}
          value={kind}
          onChange={setKind}
          required
          placeholder={
            editing !== null ? undefined : t("integrations.customApi.chooseKind")
          }
          options={
            editing !== null && editing.api_kind != null
              ? [
                  {
                    value: editing.api_kind,
                    label: t(`integrations.customApi.kind.${editing.api_kind}`),
                  },
                ]
              : props.kinds.map((one) => ({
                  value: one.kind,
                  label: t(`integrations.customApi.kind.${one.kind}`),
                }))
          }
        />
        <TextField
          id="custom-api-name"
          label={t("integrations.customApi.nameLabel")}
          value={name}
          onChange={setName}
          required
        />
        <TextField
          id="custom-api-url"
          label={t("integrations.customApi.urlLabel")}
          value={url}
          onChange={setUrl}
          required
        />
      </FieldStack>
    </FormModal>
  );
}

/**
 * The ENABLED switch on one API row — ours or theirs (`CR-115-BRC05` §7.4:
 * *"Enable / disable: yes"* on both).
 *
 * ⚠ **TWO ROUTES BEHIND ONE CONTROL, AND THE SPLIT IS NOT COSMETIC.** A custom
 * row has an id to address. A STANDARD one has no row at all until now —
 * absence means ON, so there is nothing to address until somebody first
 * disagrees with that default, and the server creates the row on the first
 * switch. Inventing an id so the two could share a URL would have meant writing
 * one row per operation per connection at migration time.
 *
 * ⚠ **THE REFUSAL IS RENDERED.** Turning the shipped sync back on beside a
 * custom one is rule 1 through the other door, and the server refuses it. A
 * switch that silently snapped back would be the worst of both.
 */
function ApiSwitch(props: {
  providerKey: string;
  client: ApiClient;
  row: OperationRow;
  displayName: string;
  onDone: () => void;
  onRefused: (sentence: string) => void;
}) {
  const { t } = useTranslation();
  const on = props.row.enabled !== false;
  const flip = useMutation({
    mutationFn: (next: boolean) =>
      props.row.api_id != null
        ? updateCustomApi(props.client, props.providerKey, props.row.api_id, {
            enabled: next,
          })
        : switchStandardApi(props.client, props.providerKey, props.row.name, next),
    onSuccess: () => props.onDone(),
    onError: (error) => props.onRefused(refusalText(t, error)),
  });
  return (
    <Switch
      on={on}
      label={t("integrations.customApi.switchLabel", { name: props.displayName })}
      onLabel={t("integrations.customApi.on")}
      offLabel={t("integrations.customApi.off")}
      disabled={flip.isPending}
      testKey={props.row.api_id ?? props.row.name}
      onChange={(next) => flip.mutate(next)}
    />
  );
}


/**
 * ── CR-115-BRC05 R31 · RUN NOW ──────────────────────────────────────────────
 *
 * PO, verbatim: *"i dont have Run button here"*.
 *
 * ⚠ **IT LIVES IN THE OPERATION'S OWN ROW AND NOT IN THE PAGE HEADER, AND THAT
 * IS AN ARGUMENT RATHER THAN A PREFERENCE.** Three reasons, in the order they
 * decide it:
 *
 *   1. **The header set is RATIFIED at four** — Edit · Keys · Disconnect ·
 *      Regenerate, 2026-09-17 — and a fifth arriving without a ruling is the
 *      drift B14 rule 2 exists to stop. *Run now* would be that fifth.
 *   2. **A run is an act on ONE OPERATION.** A connector may declare several,
 *      and a header button would have to pick one silently. That is exactly
 *      the fault `DEF-INT-5489` already recorded on THIS table: a per-row
 *      *Test* button was refused because `POST …/test` takes no operation, so
 *      it would have run the connector's test and reported it against one row.
 *   3. **The same fact decides it the other way here.** `POST …/reconcile`
 *      names its operation, so a per-row control CAN call the thing its row
 *      names — which is the precise distinction that defect drew, applied.
 *
 * ⚠ **TWO BUTTONS AND NEVER ONE.** *Run now* as a single control is a control
 * that does the dangerous thing: the only way to find out what a
 * reconciliation would change would be to let it change it. *Preview* is the
 * plain button, *Apply* is behind a confirm, and the confirm carries the
 * danger tier rather than the opener (B14 rule 6 — the tier is on the COMMIT).
 *
 * ⚠ **THE ROW IS DRAWN ONLY WHERE THE SERVER SAYS THERE IS A DOOR**
 * (`can_run_now`). Five shipped connectors declare an inbound scheduled fetch
 * and have no service behind it; deciding from the manifest shape on this side
 * would have put a live button over a 404, which is hard-won law 2's mirror —
 * and that is the failure that cost the customer portal six working doors.
 */
function RunNowCell(props: {
  providerKey: string;
  operationName: string;
  client: ApiClient;
  onDone: (report: ReconcileReport) => void;
}) {
  const { t } = useTranslation();
  const [confirming, setConfirming] = useState(false);
  const [refusal, setRefusal] = useState<string | null>(null);

  const run = useMutation({
    mutationFn: (mode: "preview" | "apply") =>
      reconcileNow(props.client, props.providerKey, mode),
    onSuccess: (report) => {
      setRefusal(null);
      setConfirming(false);
      props.onDone(report);
    },
    onError: (error) => {
      setConfirming(false);
      setRefusal(refusalText(t, error));
    },
  });

  return (
    <>
      <div className="flex flex-wrap items-center gap-2" data-run-now={props.operationName}>
        <Button
          variant="secondary"
          size="sm"
          data-run-preview=""
          disabled={run.isPending}
          onClick={() => run.mutate("preview")}
        >
          {t("integrations.reconcile.preview")}
        </Button>
        <Button
          variant="secondary"
          size="sm"
          data-run-apply=""
          disabled={run.isPending}
          onClick={() => setConfirming(true)}
        >
          {t("integrations.reconcile.apply")}
        </Button>
      </div>
      {run.isPending && <Note data-run-running="">{t("integrations.reconcile.running")}</Note>}
      {refusal !== null && (
        <WarningBox tone="now" sentence={refusal} data-warning="run-refusal" />
      )}
      {confirming && (
        <ConfirmDialog
          title={t("integrations.reconcile.confirmTitle")}
          /* B14 rule 33 — a CONSEQUENCE before an irreversible act: at most two
             sentences of six words. Two of five and three. */
          consequence={t("integrations.reconcile.confirmBody")}
          confirmLabel={t("integrations.reconcile.apply")}
          confirmVariant="danger" // rule 6 — the tier is on the COMMIT
          working={run.isPending}
          onConfirm={() => run.mutate("apply")}
          onCancel={() => setConfirming(false)}
        />
      )}
    </>
  );
}

/**
 * What the run found, in a clerk's words.
 *
 * ⚠ **THE SENTENCE IS COMPOSED HERE AND THE SERVER'S OWN `headline` IS NOT
 * RENDERED**, which is this file's established rule stated at the top: the
 * server serves integers and this file writes the line, so a translator can
 * write the Japanese one. The server's sentence is still real — it is the
 * `summary` stored on the run row, which is where support reads it.
 *
 * ⚠ **`0 applied` CARRIES ITS REASON OR IT READS AS BROKEN (PO ruling R28,
 * *"(c) never touch by default"*).** On every tenant today no address field is
 * turned on, so a correct run reports differences and applies none of them. A
 * report showing two numbers and no reason is a screen a clerk files a defect
 * against — so the reason is part of the report, not a tooltip.
 *
 * ⚠ **AND `0 applied` IS NOT `nothing happened`.** R28 governs ADDRESS fields.
 * The two City keys and the verified stamp are written on every apply, and
 * they are the whole of what the going-live customer asked for (R29, *"our job
 * is the keep parcel ID updated"*). *Keys stored* is therefore its own figure.
 */
export function ReconcileResult(props: { report: ReconcileReport; queuePath: string | null }) {
  const { t } = useTranslation();
  const counts = props.report.counts ?? {};
  const applied = props.report.applied ?? {};
  const appliedTotal =
    (applied.keys_taken ?? 0) + (applied.keys_replaced ?? 0) + (applied.fields_applied ?? 0);
  const queued = counts.queued ?? 0;

  if (props.report.stopped) {
    return (
      <Panel as="section" title={t("integrations.reconcile.resultTitle")} data-reconcile-result="">
        <WarningBox
          tone="now"
          sentence={
            // `DEF-INT-9846` — the City's refusal, said by which way, ahead of
            // the general sentence; a stop with no reason keeps the general one.
            props.report.stop_reason_key
              ? `${t(props.report.stop_reason_key)} ${t("integrations.reconcile.stopped")}`
              : t("integrations.reconcile.stopped")
          }
          data-warning="reconcile-stopped"
        />
      </Panel>
    );
  }

  return (
    <Panel as="section" title={t("integrations.reconcile.resultTitle")} data-reconcile-result="">
      <p className="text-sm text-neutral-900" data-reconcile-headline="">
        {t("integrations.reconcile.differences", { count: counts.differences_found ?? 0 })}
        {" · "}
        {t("integrations.reconcile.appliedCount", { count: appliedTotal })}
      </p>
      {/* The reason, and it is only shown when it is the reason. A run that
          applied something needs no explanation of why it did not. */}
      {appliedTotal === 0 && (counts.fields_set_to_never_touch ?? 0) > 0 && (
        <Note data-reconcile-never-touch="">{t("integrations.reconcile.neverTouch")}</Note>
      )}
      {/* `DEF-INT-9849` — a Preview reads the first few pages of the City's
          register so it answers inside the worker's 60 seconds. When it did
          not read the whole of it, the report SAYS so, first among the notes,
          so the counts below are never read as the register. */}
      {props.report.complete === false && (
        <Note data-reconcile-partial="">
          {counts.city_pages_total != null
            ? t("integrations.reconcile.stoppedAfterOf", {
                read: counts.city_pages ?? 0,
                total: counts.city_pages_total,
              })
            : t("integrations.reconcile.stoppedAfter", { read: counts.city_pages ?? 0 })}
        </Note>
      )}
      {props.report.mode === "preview" && (
        <Note data-reconcile-preview-only="">{t("integrations.reconcile.previewOnly")}</Note>
      )}
      <PlainTable>
        <tbody className="divide-y divide-neutral-200">
          {[
            ["cityRows", t("integrations.reconcile.cityRows"), counts.city_rows ?? 0],
            [
              "examined",
              t("integrations.reconcile.examined"),
              (counts.premises_examined ?? 0) + (counts.units_examined ?? 0),
            ],
            ["keysTaken", t("integrations.reconcile.keysTaken"), applied.keys_taken ?? 0],
            ["needsAPerson", t("integrations.reconcile.needsAPerson"), queued],
          ].map(([key, label, value]) => (
            <tr key={String(key)}>
              <th scope="row" className="py-2 pr-4 text-left font-normal text-neutral-600">
                {label}
              </th>
              <td className="py-2 font-mono text-neutral-900" data-reconcile-count={String(key)}>
                {String(value)}
              </td>
            </tr>
          ))}
        </tbody>
      </PlainTable>
      {/* ⚠ **THE LINK IS DRAWN ONLY WHERE THERE IS SOMETHING TO OPEN**, and its
          address is built from the runbook KEY the server sent rather than
          composed here — a screen that spelled the runbook's own address would
          be a second source for it (`DEF-CWP-3925`'s shape: a door that stops
          pointing at the thing it names, with nothing to notice). */}
      {queued > 0 && props.queuePath !== null && (
        <ButtonLink to={props.queuePath} variant="secondary" data-reconcile-queue="">
          {t("integrations.reconcile.openQueue")}
        </ButtonLink>
      )}
    </Panel>
  );
}

export interface ConnectionDetailPageProps {
  /** Test seam, and the same shape every other Settings screen takes. */
  client?: ApiClient;
}

export function ConnectionDetailPage(props: ConnectionDetailPageProps = {}) {
  const { t } = useTranslation();
  const params = useParams<{ key: string }>();
  const providerKey = params.key ?? "";
  const client = props.client ?? api;
  const tenantPath = useTenantPath();

  const [openRun, setOpenRun] = useState<string | null>(null);
  /** `CR-115-BRC05` R31 — the last Preview or Apply on this screen.
   *  ⚠ **COMPONENT STATE AND NEVER A CACHE.** A report is what THIS person just
   *  did; caching it would show the next visitor somebody else's run as though
   *  it were theirs, and RECENT ACTIVITY below is where a run becomes history. */
  const [reconcileReport, setReconcileReport] = useState<ReconcileReport | null>(null);

  /** ── `CR-115-BRC05` §7 · the per-API form, the row being edited, the row
   *  being deleted, and the one refusal a switch can raise.
   *
   *  ⚠ **FOUR PIECES OF STATE AND NOT ONE MODE ENUM.** They are genuinely
   *  independent: a clerk can be shown a switch's refusal while a delete
   *  confirmation is open, and collapsing them would make one cancel the
   *  other for no reason a reader could find. */
  const [addingApi, setAddingApi] = useState(false);
  const [editingApi, setEditingApi] = useState<OperationRow | null>(null);
  const [deletingApi, setDeletingApi] = useState<OperationRow | null>(null);
  const [apiRefusal, setApiRefusal] = useState<string | null>(null);

  /** Removing a custom API. ⚠ **ONLY EVER A CUSTOM ONE** — the server refuses a
   *  standard row by name (§7.4, *"Delete: NO"*), and the Edit cell draws no
   *  control on one, so the two agree rather than one policing the other. */
  const removeApi = useMutation({
    mutationFn: (apiId: string) => deleteCustomApi(client, providerKey, apiId),
    onSuccess: () => {
      setDeletingApi(null);
      setApiRefusal(null);
      void runsQuery.refetch();
    },
    onError: (error) => {
      setDeletingApi(null);
      setApiRefusal(refusalText(t, error));
    },
  });

  // DEF-SHL-3964 — was this screen's own copy of the shell's regional query
  // plus its own `?? "MM/DD/YYYY"` / `?? "UTC"`. The shell publishes it and
  // holds every screen until it has answered.
  const { timeZone, dateFormat } = useRegional({});

  // The table state is THIS SCREEN'S, seeded from the declaration — the same
  // shape every other list in the product holds (BR-SHL-011's grammar).
  const [state, setState] = useState<TableRequestState>(() =>
    defaultRequestState(runsTableConfig((key) => key, EMPTY_CELLS, [])),
  );

  const runsQuery = useQuery<ConnectionRuns>({
    // ONE key from the WHOLE request (BR-SHL-011's six params). A search and a
    // filter are different questions and must never answer each other from
    // cache; `serializeTableParams`' own vocabulary would do, and a stable
    // JSON of the state is the same fact with no extra import.
    queryKey: queryKeys.integrationRuns(
      providerKey,
      JSON.stringify([state.q, state.filters, state.page, state.per, state.sort, state.dir]),
    ),
    queryFn: () =>
      getConnectionRuns(client, providerKey, {
        q: state.q,
        operation: state.filters.operation ?? "",
        outcome: state.filters.outcome ?? "",
        trigger: state.filters.trigger ?? "",
        page: state.page,
        per: state.per,
      }),
    enabled: providerKey !== "",
  });

  const runQuery = useQuery<RunDetail>({
    queryKey: queryKeys.integrationRun(providerKey, openRun ?? ""),
    queryFn: () => getRun(client, providerKey, openRun ?? ""),
    enabled: openRun !== null,
  });

  const payload = runsQuery.data;

  if (runsQuery.isPending) {
    return <LoadingSkeleton variant="table" />;
  }

  // The HEAD of this screen — the describe line, the operations — has no data
  // without the payload, so a failure is the whole screen's rather than the
  // table's. `DataTable`'s own `error` slot covers a failure that happens once
  // the head is already drawn (a filter change, a page turn).
  if (payload === undefined) {
    return (
      <FailedWithRetry
        title={t("integrations.runs.failedTitle")}
        reason={refusalText(t, runsQuery.error)}
        onRetry={() => void runsQuery.refetch()}
        onDownloadReport={() => undefined}
      />
    );
  }

  const providerName = t(`integrations.provider.${payload.provider.key}.name`, {
    defaultValue: payload.provider.display_name,
  });
  // ⚠ `stateWord` IS GONE, AND ITS `defaultValue` IS WHY IT IS WORTH A NOTE.
  // It read `defaultValue: payload.display_state` — so a state with no
  // catalogue row rendered its own internal code as though it were English,
  // which is B14 rule 31's failure wearing a plausible word rather than the
  // silence a missing key usually gives you. `StateWord` takes the state and
  // resolves it through the one tone map the card also uses, with no default,
  // so a missing row goes back to being visible. (The same shape survives in
  // the run FILTER's trigger list and is filed as `DEF-INT-5502` rather than
  // fixed in passing.)

  // The declaration, built from the SERVER's own filter vocabulary — the
  // manifest's operations, the model's outcomes, the model's triggers. No
  // provider and no enum value is typed here (BR-INT-037's rule, kept on this
  // side of the wire).
  const config = runsTableConfig(
    t as Translate,
    {
      // ⚠ THE ROW'S IDENTITY HOOKS LIVE IN THIS CELL AND NOT ON THE `<tr>`.
      // `DataTable` owns the row element and puts nothing of a consumer's on
      // it — deliberately (its own comment: a class on a row is what the
      // shipped suite counts). So the identity column carries them, which is
      // also where a reader would look for the row's identity.
      when: (row) => (
        <span data-run-row={row.trace_id} data-run-outcome={row.outcome ?? "running"}>
          <DateCell value={row.started_at} timeZone={timeZone} dateFormat={dateFormat} withTime />
        </span>
      ),
      what: (row) => (
        <span>
          {row.operation_label}
          {row.provider_key !== payload.provider.key && (
            <span className="block text-xs text-neutral-600" data-run-elsewhere={row.provider_key}>
              {t("integrations.runs.onConnection", { name: row.connection_label })}
            </span>
          )}
        </span>
      ),
      result: (row) => <ResultCell row={row} />,
      open: (row) => (
        <RowActions>
          <RowAction
            label={t("integrations.runs.open")}
            icon={<EyeIcon />}
            pressed={openRun === row.id}
            onClick={() => setOpenRun(openRun === row.id ? null : row.id)}
          />
        </RowActions>
      ),
    },
    [
      {
        name: "operation",
        label: t("integrations.runs.column.what"),
        options: payload.filters.operations.map((one) => ({
          value: one.name,
          label: t(`integrations.provider.${payload.provider.key}.operation.${one.name}`, {
            defaultValue: one.label,
          }),
        })),
      },
      {
        name: "outcome",
        label: t("integrations.runs.filterOutcome"),
        options: payload.filters.outcomes.map((one) => ({
          value: one,
          label: t(`integrations.runs.outcome.${one}`, { defaultValue: one }),
        })),
      },
      {
        name: "trigger",
        label: t("integrations.runs.filterTrigger"),
        options: payload.filters.triggers.map((one) => ({
          value: one,
          label: t(`integrations.runs.trigger.${one}`, { defaultValue: one }),
        })),
      },
    ],
  );

  /** ⚠ **TRUE FOR THE SIX CONNECTORS WHOSE KEY WE ISSUE, READ OFF THE
   *  MANIFEST.** Never a provider key — `BR-INT-037`, and `G77` fails one. */
  const weIssueTheKey = payload.provider.auth.mode === "they_hold_ours";
  const issuedKeys = payload.issued_keys ?? [];
  const liveKey = issuedKeys.find((one) => one.state === "active") ?? null;

  /**
   * THE SUMMARY LINE — `••••7Q2F · Read payments, Read bills` (`DEF-INT-5532`).
   *
   * ⚠ **IT RENDERED THE CONNECTOR'S NAME, DIRECTLY UNDER THE HEADING THAT
   * ALREADY SAYS IT.** `describe_line` falls back to `display_name` when no
   * adapter is bound, which is right for the twelve connectors we DIAL — there
   * it is their masked host — and a connector that dials US has no host and no
   * adapter, so all six got the name twice. p066 uses this line for the two
   * facts available nowhere else on the screen: WHICH KEY is live, and WHAT IT
   * MAY CALL.
   *
   * ⚠ **THE DRAWING'S OWN WORDS ARE `reads payments, bills` AND THESE ARE THE
   * OPERATION LABELS INSTEAD — a stated divergence, not an oversight.** Those
   * lower-case nouns are the retired `scopes` field's options, and reviving
   * them here would re-create the two vocabularies `DEF-INT-5504` is about and
   * the PO's own ruling retires. Same list of words as the MAY CALL cell below
   * and as the API table above, so no two places on this screen can disagree.
   */
  const describeLine: string = ((): string => {
    if (!weIssueTheKey || liveKey === null) {
      return payload.describe ?? providerName;
    }
    const names = liveKey.scope ?? [];
    const words = names
      .map((name) => {
        const found = payload.operations.find((one) => one.name === name);
        return found === undefined
          ? name
          : t(`integrations.provider.${payload.provider.key}.operation.${name}`, {
              defaultValue: found.label,
            });
      })
      .join(", ");
    return words === "" ? liveKey.hint : `${liveKey.hint} \u00b7 ${words}`;
  })();

  /**
   * THE FOUR FACTS THE HEADER AND THE STRIP SHARE, computed ONCE.
   *
   * ⚠ **THE DIRECTION HALF IS THE UNION OVER THE OPERATIONS, NEVER THE FIRST
   * ONE.** `Manifest.kicker` returns the first operation's pair only, so a
   * two-door connector reading it shows one word and silently hides the other
   * door (measured at `registry.py:637`). A connector that both sends and
   * collects says both, in the drawn order, de-duplicated.
   */
  const directionWords = Array.from(
    new Set(
      payload.operations.map((one) =>
        t(`integrations.kicker.${one.initiative}.${one.direction}`),
      ),
    ),
  );
  /**
   * ── `CR-115-BRC05` §7.5 RULE 4 · THE COUNT SEES ONLY ENABLED APIs ─────────
   *
   * *"a switched-off API must not drag the count, and a connector is not Not
   * working because of one you turned off"*.
   *
   * ⚠ **BOTH HALVES OF THE FRACTION MOVE, AND MOVING ONLY THE NUMERATOR WAS
   * THE FIRST DRAFT.** Counting working rows among the enabled ones while
   * dividing by every row gives *0 of 3* on a connector with one API switched
   * off and two working — a number that is wrong in the alarming direction and
   * reads exactly like a broken connector.
   *
   * ⚠ **`enabled !== false` AND NOT `enabled === true`.** The field is optional
   * on the wire: a payload cached from before this wave carries none, and
   * `undefined` there means *nobody has touched the switch*, which is ON. The
   * strict form would show *0 of 0* on every connector for as long as one stale
   * payload lived in a cache — the `skipped`-missing-from-the-union shape this
   * file already records once.
   */
  const live = payload.operations.filter((one) => one.enabled !== false);
  const working = live.filter((one) => one.state === "working").length;
  /** §7.3's closed list, as the SERVER serves it. `[]` — and no form — on a
   *  connector that offers none. Never an array typed in React. */
  const addable: AddableKind[] = payload.custom_api_kinds ?? [];
  /** The newest `last_run_at` across the operations, or `null` where none has
   *  ever run. ⚠ **COMPARED AS ISO-8601 STRINGS, WHICH IS SOUND** — the wire
   *  serves UTC with a `Z`, so lexical order IS chronological order, and
   *  building `Date`s here would be a second place a time zone could enter.
   *  The VALUE is still rendered through `formatDate` (`BR-SHL-023`). */
  const lastRunAt = payload.operations.reduce<string | null>(
    (newest, one) =>
      one.last_run_at !== null && (newest === null || one.last_run_at > newest)
        ? one.last_run_at
        : newest,
    null,
  );
  const activeKeys = (payload.issued_keys ?? []).filter((one) => one.state === "active").length;

  /**
   * ── THE KPI LINE (PO ruling 2026-09-17) ───────────────────────────────────
   *
   * ⚠ **`VIEW-17` DRAWS NO KPI LINE AT ALL, AND THIS OVERRIDES IT.** The PO
   * asked for one by name — *"we did not include any KPIs line"* — and
   * approved these four: *"this is good"*. Where a drawing is SILENT the signed
   * rules decide (B14 rule 41); here it is not silent but contrary, so this is
   * a ruled ADDITION on top of it and is recorded as an override in
   * `12-governance/02-decision-log.md` rather than read out of p066.
   *
   * ⚠ **NO BACKEND CHANGE AND NO NEW FIELD.** All four come off the payload
   * this screen already fetches, checked against `integrationsEndpoints.ts`.
   *
   * ⚠ **A TILE WITH NOTHING TO SHOW IS AN EM-DASH AND NEVER A ZERO.** That is
   * `CountTile`'s existing rule on this very screen and `RBS-1`'s finding in
   * this same blueprint: a zero is a CLAIM, and *nothing has run yet* is a
   * different fact from *something ran and found nothing*.
   *
   * ⚠ **THE `4 APIs` CHIP LEFT THE IDENTITY LINE IN THE SAME COMMIT**, because
   * it is tile 1 now and one fact in two places is what drifts.
   */
  const kpis: KpiTile[] = [
    {
      id: "apis",
      label: t("integrations.kpi.apis"),
      value: (
        <span data-kpi="apis" data-operation-count={payload.operations.length}>
          {payload.operations.length}
        </span>
      ),
    },
    {
      id: "working",
      label: t("integrations.kpi.working"),
      value: (
        <span data-kpi="working">
          {live.length === 0
            ? "—"
            : t("integrations.kpi.workingValue", {
                working,
                total: live.length,
              })}
        </span>
      ),
    },
    {
      id: "lastRun",
      label: t("integrations.kpi.lastRun"),
      value: (
        <span data-kpi="lastRun">
          {lastRunAt === null ? "—" : formatDate(lastRunAt, timeZone, dateFormat, true)}
        </span>
      ),
    },
    {
      id: "keys",
      label: t("integrations.kpi.keysInUse"),
      // ⚠ THE DASH HERE MEANS *WE ISSUE NO KEY ON THIS CONNECTOR*, which is
      // twenty-two of twenty-eight. A `0` would read as *we issue keys and none
      // is live*, which is a different and alarming fact.
      value: <span data-kpi="keys">{weIssueTheKey ? activeKeys : "—"}</span>,
    },
  ];

  return (
    <section className="flex flex-col gap-4" data-screen="S142" data-provider={payload.provider.key}>
      {/* ── The page head, its actions and their dialogs ──────────────────
          Everything a clerk can DO on this screen is in the shared header now
          (PO 2026-09-17, `DEF-INT-5579`), which is B14 rule 2 and the reason
          the component below carries its own confirms. */}
      <ConnectionHeader
        providerKey={payload.provider.key}
        providerName={providerName}
        categoryWord={t(`integrations.category.${payload.provider.category}`, {
          defaultValue: payload.provider.category,
        })}
        directionWords={directionWords}
        displayState={payload.display_state}
        connection={payload.connection}
        where={whereWords(describeLine)}
        weIssueTheKey={weIssueTheKey}
        signInOnly={payload.provider.auth.placement === "redirect"}
        /* `CR-198-BRC10` — a provider the PLATFORM holds has nothing to
           connect or edit either (the server refuses a connect by name), so
           the head offers no action for it, exactly as for a coming-soon one.
           Found on the walk: the head drew *Connect* over the platform panel. */
        comingSoon={
          payload.provider.disposition?.kind === "coming_soon" ||
          payload.provider.auth.mode === "platform_holds_ours"
        }
        /* What a regenerated key reaches: the LIVE key's own scope when there
           is one, so the act can neither widen nor narrow it by accident, and
           EVERY READ when there is none — the PO's *all 4*, which is also what
           `machine_auth._validated_scope` requires to be non-empty.

           ⚠⚠ **THIS READ `payload.operations.map(…)` — EVERY OPERATION —
           UNTIL 2026-09-24, AND ON THAT DAY IT STARTED GRANTING THE POWER TO
           TAKE MONEY BY DEFAULT (`DEF-INT-6488`).** The comment above said
           *the PO's all 4* and it was written when all four were READS;
           `pay_invoicecloud_partner` now declares `record_payment`, an inbound
           door, so the FIRST key a clerk issued reached it **without anybody
           ticking it and with nothing on the screen saying so** — which is
           hard-won law 3 exactly (the unsafe option must be the one you type)
           and is the opposite of what `BR-INT-083` and the manifest's own row
           both promise.

           **Nothing here is invented: the filter restores the comment's own
           stated intent.** `direction === "in"` is *a door THEY send things
           to*, the same property `serve.record_write` files the run row under
           and the same one the published specification reads to say `post`.
           A write is granted by ticking its row, which is what the row is for.
        */
        scope={
          liveKey?.scope ??
          payload.operations
            .filter((one) => one.direction !== "in")
            .map((one) => one.name)
        }
        keysPath={
          weIssueTheKey
            ? tenantPath(`${INTEGRATIONS_ROUTE}/${payload.provider.key}/access`)
            : null
        }
        mappingsPath={
          (payload.provider.vocabularies ?? []).length > 0
            ? tenantPath(`${INTEGRATIONS_ROUTE}/${payload.provider.key}/mappings`)
            : null
        }
        setupPath={tenantPath(`${CONNECTORS_ROUTE}/${payload.provider.key}/configure`)}
        backTo={tenantPath(INTEGRATIONS_ROUTE)}
        credentials={payload.credentials}
        preview={payload.disconnect}
        client={client}
        onChanged={() => void runsQuery.refetch()}
      />

      {/* The KPI line, directly under the head and above the first panel. */}
      <KPIStrip kpis={kpis} />

      {/* ⚠ **WHY IT IS NOT WORKING — A RED LINE UNDER THE STRIP, AND ONLY WHEN
          IT IS NOT WORKING.** `last_test_text` has been served since wave B and
          `DEF-INT-4025` is the defect that no screen read it. It is deliberately
          NOT a KPI tile: a tile whose value is a sentence is not a tile.

          ⚠ **THIS LINE IS THE ONE STRUCTURALLY AT RISK OF NEVER RENDERING
          ANYTHING** (hard-won law 7's third shape, one layer over — a view
          incapable of drawing rather than a check incapable of failing). The
          field is `null` on every connector but the failing ones, so a demo
          tenant with none would let it pass every check. It was proved by
          opening `meters_neptune360` (*Not working · No connection to the meter
          cloud.*) and `bank_lockbox_file` (*No folder client is installed.*) in
          a browser on 2026-09-17 and READING the sentence, not by inferring it
          from the type.

          ⚠ **THE GUARD IS THE STATE AND NOT MERELY THE FIELD'S PRESENCE.** It
          rendered whenever the text existed, so a connector that had failed and
          then been fixed carried yesterday's reason under today's green word. */}
      {payload.display_state === "not_working" && payload.connection?.last_test_text != null && (
        <p className="text-sm text-danger-700" data-state-reason="" role="status">
          {payload.connection.last_test_text}
        </p>
      )}

      {/* WarningBox — frame `54.1`, template I3's slot, FILLED at last.
          This screen's own trailer has carried the absence in writing since
          wave C: *"the WarningBox (wave H) and BudgetLine (wave G) slots of
          template I3 are NOT rendered — a stated absence closed by default."*
          Wave H is that wave, so the note comes off the trailer in the same
          commit the box appears. A stated absence that outlives the thing it
          was waiting for is hard-won law 2's mirror.

          ⚠ THE SERVER DECIDES *warning* vs *lapsed*, NOT THIS SCREEN. The
          `expiry` block arrives already settled (`apps/integrations/expiry.py`)
          so that this page and the S7 attention strip cannot drift apart on
          which side of a boundary a date falls. Nothing here subtracts dates. */}
      {payload.connection !== null && (
        <ExpiryWarning
          connection={payload.connection}
          providerKey={payload.provider.key}
          client={client}
        />
      )}

      {/* ── The placeholder line (CR-110-BRC04 wave B) ──────────────────────
          PO 2026-09-16 on the two unnamed vendors: *"keep it as it is right
          now - we will replace them - theya re dummay right now we will
          replace them later"*. The CR extends it to anything declaring
          `Disposition(kind="coming_soon")` — the card says *coming soon* and
          the server refuses the connect.

          ⚠ **THE GRID CARRIED THIS AND THIS PAGE DID NOT.** A clerk who opened
          the print vendor's own page got a full API table and *Not set up*,
          with nothing saying it can never be connected — a screen reading as
          ready over a refusal, which is hard-won law 2's mirror.

          The wave is shown when the manifest declares one and omitted when it
          does not, rather than invented: *Coming soon · v1.1* is a promise and
          `null` means we have not made it. Rule 33 — a FACT, four words. */}
      {payload.provider.disposition?.kind === "coming_soon" && (
        <Note data-disposition="coming_soon">
          {payload.provider.disposition.wave === null
            ? t("integrations.comingSoon")
            : t("integrations.comingSoonWave", { wave: payload.provider.disposition.wave })}
        </Note>
      )}

      {/* `CR-198-BRC10` — a provider the PLATFORM holds (texts through one
          shared Twilio account) is never connected by a utility: its status,
          last error and a Test send, read off `auth.mode` (data, never a key).
          The server refuses a non-admin's Test, and the refusal is shown. */}
      {payload.provider.auth.mode === "platform_holds_ours" && (
        <PlatformTextsPanel providerKey={payload.provider.key} client={client} readOnly={false} />
      )}

      {/* ── OperationsPanel — the drawn API table (CR-110-BRC04 wave B) ──────
          `VIEW-01`…`VIEW-28` of the Integration Blueprint all draw the SAME
          table under an accented panel: seven columns, one row per operation,
          rendered from the manifest so a 29th connector costs no screen code
          (`BR-INT-037`). Built from the pages AS IMAGES (B14 rule 42) —
          p022–p023, p047–p048, p081, p092.

          ⚠ **STILL NO AGGREGATE WORD OVER THE TABLE (`BR-INT-028`).** The
          heading counts the operations; it does not average their states.
          Averaging three into one hides a broken one, and
          `IntegrationsTab.test.tsx` TC-3 already asserts the absence.

          ⚠ **THE DRAWING IS CLIPPED AND THE LAST COLUMN IS STILL BUILT
          (`DEF-INT-5487`).** The right-hand edge of all 56 connector frames is
          absent from the PDF's own content stream — page 22's header
          text-extracts as `… RATE LIMIT T`, the TEST column truncated to one
          letter. A lane building from the renders alone builds this table one
          column short and never knows, which is why the column is named here
          rather than left to the picture. */}
      <Panel
        as="section"
        accent
        title={t("integrations.runs.operationsPanel", {
          count: payload.operations.length,
          // ⚠ **`defaultValue` ALONE DOES NOT PLURALISE, AND IT RENDERED
          // *1 APIs on this connector* ON A REAL SCREEN** — caught in a
          // browser, not by a test, which is hard-won law 6 exactly. i18next
          // picks a plural SUFFIX when `count` is present, so the default has
          // to be given per form or the singular never has a spelling.
          defaultValue_one: "{{count}} API on this connector",
          defaultValue_other: "{{count}} APIs on this connector",
        })}
        /* ── `CR-115-BRC05` §7.3 · THE ADD CONTROL ──────────────────────────
           PO R32: *"here Customer is giving custom URLs … hence we need a form
           to add them"*.

           ⚠ **THIS IS THE CONTROL THE BLUEPRINT REMOVED, PUT BACK BY A LATER
           RULING.** `CR-3` (p15, p164, 14 September) ruled *"a clerk does not
           name an API and does not add one … the disabled + Add an API button
           is gone: a control nobody may use is not a control, it is a
           promise."* The PO ruled that too broad on 17 September, and §7.2
           records the correction: the distinction is the CONNECTOR, not the
           customer. This button is live or it is not drawn — the blueprint's
           objection was to a DISABLED one, and it still stands.

           ⚠ **NOT DRAWN AT ALL WHERE THE CONNECTOR OFFERS NO KINDS**, which is
           twenty-seven of twenty-eight. That is the half of the earlier ruling
           §7.2 keeps, and it is `BR-SHL-025`'s own limit: a control that could
           never act for anyone, on any connection, is not a blocked action —
           it is an action that does not exist.

           ⚠ **B14 rule 4: `+ Noun` OPENS A CREATOR.** Not `Add API →`, which
           would promise navigation. */
        trailing={
          addable.length > 0 ? (
            <Button
              variant="secondary"
              size="sm"
              data-add-api=""
              onClick={() => {
                setApiRefusal(null);
                setAddingApi(true);
              }}
            >
              {t("integrations.customApi.addButton")}
            </Button>
          ) : undefined
        }
      >
        <table
          className="w-full border-collapse text-table"
          data-operations={payload.operations.length}
        >
          <thead>
            <tr className="border-b border-divider text-left align-bottom">
              {[
                ["api", "API · Endpoint"],
                // ── CR-115-BRC05 §7.4 — *"Name · Kind · URL · Key · Enabled ·
                // Edit"*. Three of those six were already drawn: the NAME and
                // the URL are the first cell, stacked as `VIEW-25` draws them.
                // KIND, ENABLED and EDIT are new columns, and the KEY is
                // deliberately NOT one — see `ApiFormModal`'s docstring, and
                // the blueprint's own line under this table, *"One key. All 3
                // APIs use it."*
                ["kind", "Kind"],
                ["direction", "Direction"],
                ["when", "When"],
                ["rate", "Rate limit"],
                ["lastRun", "Last run"],
                ["result", "Result"],
                ["test", "Test"],
                // ── CR-115-BRC05 R31 — *"i dont have Run button here"* ─────
                // ⚠ **AN EIGHTH COLUMN ON A SEVEN-COLUMN DRAWING, AND THE
                // OVERRIDE IS RECORDED RATHER THAN SLIPPED IN.** `VIEW-01`…
                // `VIEW-28` draw seven; the PO asked for this control on this
                // screen on 2026-09-17, which is the same authority that moved
                // the action row to the top (B14 rule 41 — the only thing that
                // reaches the PO is a drawing that contradicts a signed rule).
                // ⚠ And the column is EMPTY on every row the server does not
                // give a door to, rather than absent — a table whose column
                // count changes with its contents is harder to read than one
                // with a blank cell.
                ["run", "Run"],
                // §7.4, PO R36: *"in table also give edit button + remember if
                // we have existing Apis , standard APis those will be availabel
                // for enable diable but those will not be editable"*. Two
                // columns because they answer two questions — *is this on* and
                // *whose is it* — and the second cell is EMPTY on a standard
                // row rather than absent, for the reason the Run column already
                // gives: a table whose column count changes with its contents
                // is harder to read than one with a blank cell.
                ["enabled", "Enabled"],
                ["edit", "Edit"],
              ].map(([key, fallback]) => (
                <th
                  key={key}
                  scope="col"
                  className="py-2 pr-4 font-heading text-table-header font-semibold uppercase tracking-table-header text-neutral-600"
                >
                  {t(`integrations.runs.column.${key}`, { defaultValue: fallback })}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-neutral-200">
            {payload.operations.map((operation) => (
              // ⚠ **KEYED ON THE API ROW WHERE THERE IS ONE** (`CR-115-BRC05`
              // §7.4). Ours and theirs share one list and a custom row borrows
              // its operation's NAME, so keying on the name alone would give
              // two siblings one key: React reuses the wrong node, and the
              // switch a clerk just pressed appears on the other row.
              <tr
                key={operation.api_id ?? operation.name}
                data-operation={operation.name}
                data-api-id={operation.api_id ?? undefined}
                data-api-standard={operation.is_standard === false ? "no" : "yes"}
                className="align-top"
              >
                {/* API · ENDPOINT — the label over the host, exactly as drawn.
                    The host is the connection's own non-secret setting for the
                    field THIS operation declares, so a connector holding two
                    addresses shows each row its own (`DEF-INT-4259`). */}
                <td className="py-2 pr-4">
                  {/* ⚠ **THEIR NAME WINS WHERE THEY GAVE ONE** — *"THE KIND IS
                      OURS. THE NAME IS THEIRS"* (§7.2). A custom row's name is
                      never sent through `t()`: it is the clerk's own words and
                      translating it would be nonsense. */}
                  <span className="block text-neutral-900" data-api-name="">
                    {operation.custom_name ??
                      t(
                        `integrations.provider.${payload.provider.key}.operation.${operation.name}`,
                        { defaultValue: operation.label },
                      )}
                  </span>
                  {/* ⚠ **`data-endpoint-source` IS READ OFF THE WIRE AND NEVER
                      WORKED OUT HERE** (§7.7). The server's one resolver says
                      which rung answered — the API row's own address, the
                      operation's field, the connector's, or the path we
                      publish — and *"a screen that re-derives it is a second
                      source by another name"*, which is exactly what
                      `DEF-INT-5613` was. */}
                  {operation.endpoint !== null && (
                    <span
                      className="block font-mono text-xs text-neutral-600"
                      data-endpoint=""
                      data-endpoint-source={operation.endpoint_source ?? undefined}
                    >
                      {operation.endpoint}
                    </span>
                  )}
                  {/* `BR-INT-048` / `C14` — who places the call. Kept from the
                      list this table replaces rather than dropped with it. */}
                  {operation.executor !== "server" && (
                    <span
                      className="block text-xs text-neutral-600"
                      data-operation-executor={operation.executor}
                    >
                      {t("integrations.operation.browserExecuted")}
                    </span>
                  )}
                </td>
                {/* KIND — what SORT of call this is, from the closed list WE
                    ship (§7.3), and *"ours marked as standard"* (§7.4).

                    ⚠ **THE MARKER IS ON OURS AND NOT ON THEIRS**, which is the
                    ruling's own direction and is also the useful one: a clerk
                    scanning for the rows they may edit finds them by the
                    ABSENCE of a word they have stopped reading.
                    ⚠ **AN EM-DASH WHERE THE CONNECTOR OFFERS NO KINDS**, which
                    is twenty-seven of twenty-eight. Blank would read as *we do
                    not know*; there is simply nothing to say. */}
                <td className="py-2 pr-4 text-neutral-700" data-api-kind={operation.api_kind ?? ""}>
                  {operation.api_kind == null ? (
                    "—"
                  ) : (
                    <span className="flex flex-wrap items-center gap-1">
                      {operation.is_standard !== false && (
                        <Chip data-api-standard-mark="">
                          {t("integrations.customApi.standard")}
                        </Chip>
                      )}
                      <span>{t(`integrations.customApi.kind.${operation.api_kind}`)}</span>
                    </span>
                  )}
                </td>
                {/* DIRECTION — *We send* · *We collect* · *They send*, from the
                    catalogue keys the card's kicker already uses, so the two
                    screens cannot drift into two vocabularies for one fact. */}
                <td className="py-2 pr-4 text-neutral-700" data-direction="">
                  {t(`integrations.kicker.${operation.initiative}.${operation.direction}`)}
                </td>
                {/* WHEN — the manifest's trigger in a clerk's words.
                    ⚠ **`integrations.when.*`, NOT `integrations.runs.trigger.*`
                    (`DEF-INT-5493`).** The run history's words answer *what
                    started this run that already happened* — *A partner*,
                    *They called us* — and this column answers *when does this
                    API run*. Reading the history's family here put **"Read
                    payments · A partner"** on the screen: an answer to WHO in
                    the WHEN column. p066 draws *They call us* on all three
                    Aclarian rows and p064 draws it on the sandbox's webhook
                    row, so the two partner-initiated triggers share one
                    sentence, and the SET-UP screen now reads the same family —
                    one vocabulary for one question on both screens. */}
                <td className="py-2 pr-4 text-neutral-700" data-when="">
                  {/* ⚠ `trigger` IS OPTIONAL ON THE WIRE and the type says so:
                      a payload cached from before wave A carries none. `t()`
                      would happily key off `undefined` and render the literal
                      word, which is the enum-on-a-clerk's-screen shape all
                      over again (`DEF-INT-5491`). */}
                  {operation.trigger === undefined
                    ? "—"
                    : t(`integrations.when.${operation.trigger}`, {
                        defaultValue: WHEN_FALLBACK[operation.trigger] ?? "On demand",
                      })}
                </td>
                {/* RATE LIMIT — DISPLAY ONLY. PO 2026-09-16: *"we cant allow
                    clark to reset it … keep the check in code - thats it"*.
                    There is no input, no Save and no editor on this screen.

                    ⚠ **A DASH IS NOT A ZERO, AND HERE IT IS NOT A BLANK
                    EITHER.** A number appears only where one is really
                    enforced — a partner calling US. Nothing throttles the
                    calls we place at a vendor, so printing the inbound ceiling
                    beside an outbound call would be hard-won law 1: a figure
                    claiming a guarantee nothing keeps. */}
                <td className="py-2 pr-4 font-mono text-xs text-neutral-700" data-rate-limit="">
                  {operation.rate_limit_per_minute !== null
                    ? t("integrations.runs.ratePerMinute", {
                        count: operation.rate_limit_per_minute,
                        defaultValue: "{{count}} / min",
                      })
                    : "—"}
                </td>
                {/* LAST RUN */}
                <td className="py-2 pr-4 text-neutral-700" data-last-run="">
                  {operation.last_run_at !== null ? (
                    <DateCell
                      value={operation.last_run_at}
                      timeZone={timeZone}
                      dateFormat={dateFormat}
                      withTime
                    />
                  ) : (
                    "—"
                  )}
                </td>
                {/* RESULT — each operation's OWN state, with the drawn dot. */}
                <td className="py-2 pr-4" data-operation-state={operation.state}>
                  <StateWord state={operation.state} dot />
                </td>
                {/* TEST — the column the clipped edge hid, and it carries the
                    manifest's own sentence for the smallest real instance of
                    this operation (`BR-INT-019`), or says it cannot be tested.

                    ⚠ **A SENTENCE AND NOT A BUTTON, ON PURPOSE
                    (`DEF-INT-5489`).** `POST /integrations/{key}/test` takes a
                    recipient and NO operation, so a test is a fact about a
                    CONNECTOR while `test_action` is a fact about an OPERATION.
                    A per-row button here could not call the thing its row
                    names — it would run the connector's test and report it
                    against one row. The PO's own rule decides it: *"a box that
                    does nothing is worse than no box"*. The column is drawn,
                    the information is real, and no dead control ships. */}
                {/* ⚠ **THE CELL IS EMPTY WHERE THERE IS NO TEST, AND THE
                    SENTENCE MOVED TO ONE LINE UNDER THE TABLE (PO 2026-09-17,
                    B14 rules 32 and 33).** It printed *Cannot be tested until
                    first use.* on EVERY row — four identical sentences stacked
                    down one column on Aclarian, sixteen on Neptune — which
                    spends rule 32's one-sentence budget for the whole section
                    four times over on a single fact. An em-dash would be
                    wrong too: this column's absence is not *we do not know*,
                    it is *there is nothing to say yet*, and the line under the
                    table says it once. */}
                <td className="py-2 pr-4 text-neutral-700" data-test-action="">
                  {operation.test_action ?? ""}
                </td>
                {/* RUN — `CR-115-BRC05` R31. See `RunNowCell`'s own docstring
                    for why this lives in the row rather than the page header,
                    and why there are two buttons rather than one. */}
                <td className="py-2" data-run-cell={operation.name}>
                  {operation.can_run_now === true && (
                    <RunNowCell
                      providerKey={payload.provider.key}
                      operationName={operation.name}
                      client={client}
                      onDone={(report) => {
                        setReconcileReport(report);
                        // ⚠ **ONE REFETCH AND NOT TWO — `runsQuery` SERVES
                        // BOTH.** This screen's whole payload, the operations
                        // among them, comes off `GET …/runs`, so the new run
                        // reaches RECENT ACTIVITY and the row's *Last run* and
                        // *Result* move with it in the same round trip.
                        void runsQuery.refetch();
                      }}
                    />
                  )}
                </td>
                {/* ── ENABLED — `CR-115-BRC05` §7.4, on OURS and THEIRS alike ──
                    ⚠ **THE RUNNERS OBEY THIS, WHICH IS WHY IT IS NOT
                    DECORATION** (§7.5 rule 3). `gis.search` drops a switched-off
                    lookup and never dials it; `gis.reconcile` refuses a
                    switched-off sync before it writes a run row. A switch that
                    rendered and changed nothing would look identical to this
                    one — hard-won law 2's mirror, and the failure that cost the
                    customer portal six working doors. */}
                <td className="py-2 pr-4" data-enabled-cell={operation.api_id ?? operation.name}>
                  <ApiSwitch
                    providerKey={payload.provider.key}
                    client={client}
                    row={operation}
                    displayName={
                      operation.custom_name ??
                      t(
                        `integrations.provider.${payload.provider.key}.operation.${operation.name}`,
                        { defaultValue: operation.label },
                      )
                    }
                    onDone={() => void runsQuery.refetch()}
                    onRefused={setApiRefusal}
                  />
                </td>
                {/* ── EDIT · DELETE — R36: *"standard APis those will be
                    availabel for enable diable but those will not be
                    editable"*.
                    ⚠ **THE CELL IS EMPTY ON A STANDARD ROW RATHER THAN
                    CARRYING A DISABLED CONTROL.** `BR-SHL-025` asks a control
                    that CANNOT ACT to render disabled with its reason — but a
                    standard API has no edit anybody could ever perform, on any
                    connector, for any clerk. That is not a blocked action, it
                    is an action that does not exist, and drawing two greyed
                    icons on every standard row of every connector would spend
                    B14 rule 32's whole description budget on saying nothing.
                    The Kind column already says which rows are ours. */}
                <td className="py-2" data-edit-cell={operation.api_id ?? operation.name}>
                  {operation.is_standard === false && operation.api_id != null && (
                    <RowActions>
                      <RowAction
                        label={t("integrations.customApi.editTitle")}
                        icon={<PencilIcon />}
                        onClick={() => setEditingApi(operation)}
                      />
                      <RowAction
                        label={t("integrations.customApi.deleteTitle")}
                        icon={<TrashIcon />}
                        danger
                        onClick={() => setDeletingApi(operation)}
                      />
                    </RowActions>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {/* ONE line for the whole column, and only when a row actually wants
            it. `some` rather than `every`: a connector with a mix — one
            testable API and three not — still owes the reader the sentence. */}
        {payload.operations.some((one) => one.test_action === null) && (
          <Note data-test-note="">{t("integrations.refusal.no_test_action")}</Note>
        )}
        {/* ── `CR-115-BRC05` §7.5 rule 1, through the SWITCH's door ──────────
            Turning the shipped sync back on beside a custom one is the same
            rule reached another way, and the server refuses it. Rendered as
            TEXT and never as a `title` tooltip: a tooltip is unreachable by
            keyboard, invisible on touch and unread by a clerk on the phone —
            the exact reader B14 rule 33 writes its caps for. */}
        {apiRefusal !== null && (
          <WarningBox tone="now" sentence={apiRefusal} data-warning="api-refusal" />
        )}
      </Panel>

      {/* ── `CR-115-BRC05` §7.3 · the Add / Edit form ────────────────────────
          One component for both, because they are the same three fields and the
          only difference is which of them a clerk may move. Two components
          would be two places the *no field mapping* ruling has to hold. */}
      {(addingApi || editingApi !== null) && (
        <ApiFormModal
          providerKey={payload.provider.key}
          client={client}
          kinds={addable}
          editing={editingApi}
          onSaved={() => {
            setAddingApi(false);
            setEditingApi(null);
            setApiRefusal(null);
            void runsQuery.refetch();
          }}
          onClose={() => {
            setAddingApi(false);
            setEditingApi(null);
          }}
        />
      )}

      {/* ── Deleting a custom API ────────────────────────────────────────────
          ⚠ **A CONSEQUENCE, NOT A *are you sure*** (B14 rule 33): at most two
          sentences of six words, saying what will actually happen. *This API
          stops being called* is the fact a clerk needs; *are you sure* is a
          question nobody can answer. Rule 6 puts the danger tier on the COMMIT. */}
      {deletingApi !== null && deletingApi.api_id != null && (
        <ConfirmDialog
          title={t("integrations.customApi.deleteTitle")}
          consequence={t("integrations.customApi.deleteConsequence")}
          confirmLabel={t("integrations.customApi.deleteAction")}
          confirmVariant="danger"
          working={removeApi.isPending}
          onConfirm={() => removeApi.mutate(deletingApi.api_id as string)}
          onCancel={() => setDeletingApi(null)}
        />
      )}

      {/* ── What the last Preview or Apply found (`CR-115-BRC05` R31) ────────
          Under the table the button is in, because it is that button's answer.
          Absent until somebody presses one — an empty result panel would be a
          section claiming a run that never happened. */}
      {reconcileReport !== null && (
        <ReconcileResult
          report={reconcileReport}
          queuePath={
            reconcileReport.queue_runbook_key
              ? tenantPath(`/runbooks/${reconcileReport.queue_runbook_key}`)
              : null
          }
        />
      )}

      {/* ManagePanel — template I3's ButtonRow and frame 54.2's keys table.
          Drawn only where there IS a connection: on a card that is *Not set
          up* there is no password to replace and nothing to disconnect, and a
          panel of controls that all refuse is law 2 wearing a layout. */}
      {/* ── Keys we issue (p062, p066) ──────────────────────────────────────
          ABOVE the manage row and below the API table, where both frames draw
          it. Only where the manifest says we issue a key, so the twelve
          connectors we dial are unchanged — not an empty table, an absent one. */}
      {payload.connection !== null && weIssueTheKey && (
        <KeysWeIssuePanel
          keys={issuedKeys}
          operations={payload.operations}
          providerKey={payload.provider.key}
          timeZone={timeZone}
          dateFormat={dateFormat}
        />
      )}

      {/* CredentialPanel — what we hold, in the slot p047 draws it in: under
          the API table, above *Recent activity*. It draws nothing at all on
          the six connectors whose key we issue, where `KeysWeIssuePanel` above
          is this slot's panel. */}
      {payload.connection !== null && (
        <CredentialPanel
          signInOnly={payload.provider.auth.placement === "redirect"}
          weIssueTheKey={weIssueTheKey}
          operationCount={payload.operations.length}
          credentials={payload.credentials}
          timeZone={timeZone}
          dateFormat={dateFormat}
        />
      )}

      {/* ── Recent activity (p067) ─────────────────────────────────────────
          A `<Panel>`, and it is the product's ONE list assembly inside it:
          r10 rule 12's toolbar (the search and the filter chips), rule 13's
          sortable header, rule 15's icon row action and rule 16's pagination
          footer, all from `DataTable`. B14 rule 36.

          ⚠ **THE HEADING WAS A HAND-WRITTEN `<h2>` IN SMALL GREY CAPITALS AND
          THE DRAWING HAS NEVER SHOWN ONE (`DEF-INT-5560`).** p067 draws
          *Recent activity* exactly as p066 draws *Keys we issue* — sentence
          case, dark, 16px — because a reader meets the three sections as
          equals. The catalogue value was ALREADY sentence case; `uppercase`
          in this screen's own class string was doing it, which is why no
          `toContain` in 27 cases could see it and the PO read it off the
          running product instead.

          ⚠ **THE PANEL IS ALSO WHAT PUTS THE TOOLBAR INSIDE THE SECTION.**
          The drawn box contains the search, the filter chips, the column
          chooser, the table and the *1–3 of 3 · Rows per page 50* footer; on
          the flat layout they were four siblings of a heading and a reader had
          nothing telling them where the section ended.

          ⚠ **AND NO DESCRIPTION LINE — B14 rule 32, and the drawing agrees.**
          *"Every attempt, newest first."* was one of three sentences this one
          section carried; the sort arrow on WHEN already says it, which makes
          it rationale, and rule 33 puts rationale at ZERO WORDS ON SCREEN. */}
      <Panel as="section" data-runs-panel="" title={t("integrations.runs.recentTitle")}>
      {payload.elsewhere > 0 && (
        <Note>{t("integrations.runs.elsewhere", { count: payload.elsewhere })}</Note>
      )}

      <DataTable<RunRow>
        config={config}
        state={state}
        onStateChange={(next) => {
          setOpenRun(null);
          setState(next);
        }}
        rows={payload.rows}
        totalRows={payload.page.count}
        // `isPending`, not `isFetching`: a background refetch must not blank
        // rows that are already on the screen — the page turn would flicker and
        // a reader would lose their place.
        loading={runsQuery.isPending}
        error={
          runsQuery.isError
            ? {
                reason: refusalText(t, runsQuery.error),
                onRetry: () => void runsQuery.refetch(),
              }
            : null
        }
        filterBarSlot={
          <FilterBar filters={config.filters ?? []} state={state} onStateChange={setState} />
        }
        // ⚠ **NO `ctaLabel`, SO NO BUTTON — AND THAT IS THE FIX RATHER THAN A
        // TIDIER LABEL (`DEF-INT-5560`).** This block shipped a *Test it now*
        // button wired to `onCta: () => undefined`: a control that looked
        // pressable, WAS pressable, and did nothing, with *"Test it from the
        // card"* underneath it explaining why — the exact pair `DEF-MET-4764`
        // added `EmptyList`'s optional `ctaLabel` for, and hard-won law 2's
        // mirror. Nothing could see it: the prop HAD a caller, so G13 passes,
        // and the words WERE in the DOM, so every `toContain` passes.
        //
        // ⚠ **THE TWO SENTENCES WENT WITH IT (B14 rules 32 and 33).** This one
        // section carried three — *Every attempt, newest first.*, this
        // helper, and *Test it from the card* — where the budget is one, and
        // the third was rationale, which rule 33 puts at zero words on screen.
        //
        // ⚠ **THE EMPTY BLOCK ITSELF STAYS, AND THAT IS A JUDGMENT, NOT AN
        // OVERSIGHT.** VIEW-17 draws no empty state at all — every frame is
        // populated — so the drawing does not contradict `BR-SHL-012`, which
        // is CONFIRMED and says the empty block replaces the WHOLE table
        // region with *no toolbar and never an empty header*. Where the
        // drawing is silent the signed rule decides (B14 rule 41), and
        // reaching past `DataTable` to draw a header over nothing would make
        // this the only screen in the product that does.
        empty={{
          title: t("integrations.runs.empty.title"),
          helper: t("integrations.runs.empty.helper"),
        }}
      />

      {openRun !== null && runQuery.data !== undefined && (
        <RunCard
          run={runQuery.data}
          timeZone={timeZone}
          dateFormat={dateFormat}
          onClose={() => setOpenRun(null)}
        />
      )}
      </Panel>

      {/* CR-069 wave S (US-INT-041) — *Who has been reading*, frame 46.2. It
          draws itself only for a connection something reads FROM (the SERVE
          quadrant, read off `operations` and never off the provider's name),
          and returns null otherwise, so no empty box appears on the sixteen
          connectors nobody reads from. */}
      <AccessLogPanel
        providerKey={payload.provider.key}
        operations={payload.operations}
        timeZone={timeZone}
        dateFormat={dateFormat}
      />

      {/* ── The footer, LAST (p047–p048, p066–p067) ─────────────────────────
          A divider, then one row: the controls on the left and the append-only
          footnote right-aligned beside them. It sits under the access log
          because the drawing puts it under everything — the blueprint records
          the access log as *"a panel inside the connection view"*, and a
          footer with a panel after it is not a footer.

          ⚠ **DRAWN ONLY WHERE THERE IS A CONNECTION.** On a card that is *Not
          set up* there is no password to replace and nothing to disconnect,
          and a row of controls that all refuse is law 2 wearing a layout. The
          footnote is then absent too, because a run record nobody has is not a
          record we can promise to keep. */}
      {/* ── The footer, LAST (p047–p048, p066–p067) ─────────────────────────
          A divider and ONE right-aligned line: *Runs are kept exactly as they
          happened*. Its buttons moved to the page head on 2026-09-17 (PO:
          *"actions on this screens - should be on top"*) and the note did not,
          because the ruling moved the CONTROLS and p067 still draws the
          footnote here. A drawing remains the authority for everything a
          ruling did not move (B14 rule 41).

          ⚠ **DRAWN ONLY WHERE THERE IS A CONNECTION.** A run record nobody has
          is not a record we can promise to keep. */}
      {payload.connection !== null && <ConnectionFooter />}
    </section>
  );
}

// ── Lifecycle ────────────────────────────────────────────────────────────
// packet: US-INT-020 (EP-INT-06) · US-INT-021 · frames 44.1 · 25.2 · 51.1 · 51.2 · 52.2 · 08-screen-layouts.md S142
// generated: 2026-09-04 by the CR-069 wave C build lane
// checklist: A✔ B✔ C✔ D✔(GET /integrations/{key}/runs · /runs/{run_id}) E✔(routed at settings/integrations/:key; linked from the card) F✔ G✔ H=n/a
// gates: tsc · vitest · G13 (the one optional prop is the client seam) · G31 (Tailwind only; on route-b-migrated.txt) · G37 (the row action is a <RowAction>) · G40 (mounted from App.tsx) · G69 (no id is a visible value — the trace id is the only identifier and it is not a truncated uuid)
// exceptions: the BudgetLine (wave G) slot of template I3 is NOT rendered — a stated absence closed by default. ⚠ THE WarningBox SLOT IS NOW FILLED (wave H, 2026-09-06): this line said BOTH were absent, and a stated absence that outlives the thing it was waiting for is hard-won law 2's mirror, so the note comes off in the commit that fills the slot rather than later · frame 51.1 masks the seven addresses (`j.doe@•••`); this screen shows them whole, stamped as a deviation in 08-screen-layouts.md
// amended: 2026-09-16 by the DEF-INT-5560 rebuild lane (2.287.4) — VIEW-17 (p066–p067) and VIEW-10 (p047–p048) read AS IMAGES under B14 rule 42: `ManagePanel` split into `CredentialPanel` (the facts, in p047's slot) and `ConnectionFooter` (the controls, LAST on the page with the append-only footnote right-aligned beside them); *Recent activity* moved from a hand-written <h2> in small grey capitals to `<Panel>`'s own <h3>, which also puts the toolbar, the table and the pagination footer inside the drawn box; `integrations.runs.intro` and the empty block's dead *Test it now* CTA removed (B14 rules 32/33, and `EmptyList`'s optional `ctaLabel` — `DEF-MET-4764`'s shape)
// exceptions: the EMPTY run history keeps `DataTable`'s block with NO toolbar and NO column headers — `BR-SHL-012` is CONFIRMED and every VIEW- frame is drawn populated, so the drawing is silent rather than contradictory and the signed rule decides (B14 rule 41; reasoned out in `12-governance/02-decision-log.md`, 2026-09-16) · the second column reads *What ran* where the drawing reads *Which API* — `DEF-INT-5565`, not fixed here because the value is shared across eleven catalogues a sibling lane is holding · `integrations.runs.intro` and the two `empty.cta*` keys are now dead in all eleven catalogues — `DEF-INT-5561`, for the same reason
// status: VERIFIED-UNRATIFIED
// ─────────────────────────────────────────────────────────────────────────
