// ── Trace ──────────────────────────────────────────────
// Story:    US-WRK-051 (labour rates — per hour, overtime, dated, per ROLE and
//           never per person; a closed job keeps the rate it closed at).
//           Screen: Work-030 (`wireframes/Work-030.png`)
// Rules:    BR-WRK-020 (per role; hourly, overtime, threshold, effective-from;
//           a contractor one rate and a dash) · BR-WRK-004 (posted nowhere) ·
//           CLAUDE.md hard rule 2 (4 stored, 2 displayed — and the ONE
//           exception, below) · B14 rule 2 (one page header) · rule 11 (the
//           consequence box) · rule 20 (one table type) · rule 21 (Tailwind;
//           on route-b-migrated.txt) · rule 31 (no database id is a visible
//           value) · rule 32 (one sentence per section) · rule 36 (the kit)
// Tests:    src/features/work/LabourRatesPage.test.tsx
// Impacts:  src/features/work/workEndpoints.ts · src/routing/screenIds.ts
//           (WRK-17)
// ───────────────────────────────────────────────────────
//
// ⚠⚠ **THIS IS THE ONE SCREEN IN THE PRODUCT THAT SHOWS MONEY AT FOUR
// DECIMALS, AND IT IS AN EXCEPTION WITH A REASON RATHER THAN A LAPSE.**
//
// Hard rule 2 stores money to four places and DISPLAYS two, everywhere. Here
// the stored value is the thing being EDITED: a supervisor who types `48.5000`
// must see `48.5000` back, or the screen and the column disagree about what
// was saved. The same rate renders as `$48.50` on the report a customer reads
// (`Work-032`) — two audiences, two precisions, one stored number.
//
// ⚠ **A RATE IS PER ROLE AND NEVER PER PERSON.** `WM-45` is explicit about
// why: *"a per-person rate is a salary, it belongs in payroll, and putting it
// on the crews screen would make `WS-23` a page a billing clerk must not
// open."* So there is no technician column here and no way to reach one; the
// server refuses a `technician_id` in the body as an unknown field.
//
// ⚠ **AND A CONTRACTOR'S OVERTIME IS A DASH.** *"An agency invoices its own
// overtime… The dash is the honest value."* `null` renders as `<Dash />` and
// never as `0.0000`, which would say their overtime is free.
import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { DataTable } from "@/components/DataTable";
import { ConsequenceBox } from "@/components/ConsequenceBox";
import { DateCell } from "@/components/DateCell";
import { PageHeader } from "@/components/PageHeader";
import { StatusPill } from "@/components/StatusPill";
import { defaultRequestState } from "@/components/tableTypes";
import type { TableConfig, TableRequestState } from "@/components/tableTypes";
import { Dash } from "@/features/customers/customersShared";
import { useRegional } from "@/features/metering/meteringShared";
import type { RegionalProps } from "@/features/metering/meteringShared";

import { listLabourRates } from "./workEndpoints";
import type { LabourRateRow } from "./workEndpoints";

/** r10's own badge for the labour-rates screen — Work-030 ↔ WRK-17. */
export const WORK_LABOUR_RATES_SCREEN = "WRK-17";

/** `Work-030`'s address — a Settings reference-data card, not a Work tab,
 *  because a rate is configuration a supervisor sets once and not a list a
 *  dispatcher works from.
 *
 *  ⚠ **NO `:tenant` SEGMENT.** `App.tsx` mounts this under a `:tenant` route
 *  and registers it as `ROUTE.slice(1)`; a constant carrying the tenant would
 *  come out `:tenant/:tenant/settings/...`, match nothing, and fall through to
 *  *"This screen is not built yet"* with `tsc`, every test, the build and
 *  `G13` all green over it — `DEF-WRK-4051`, which made both of wave H's
 *  screens unreachable from the day they shipped. `screenIds.ts` spells the
 *  SAME address WITH the segment, and that difference is deliberate: one is a
 *  child path and the other is the absolute address a person opens. */
export const WORK_LABOUR_RATES_ROUTE = "/settings/reference-data/work-labour-rates";

type Translate = (key: string, params?: Record<string, unknown>) => string;

/**
 * `Work-030`'s five columns, in the drawing's order.
 *
 * Exported so a test can read the column set with no DOM — and assert that
 * `role` (a code) is never a visible value and that no technician column
 * exists.
 */
export function labourRatesTableConfig(
  t: Translate,
  cells: {
    overtime: (row: LabourRateRow) => React.ReactNode;
    threshold: (row: LabourRateRow) => React.ReactNode;
    status: (row: LabourRateRow) => React.ReactNode;
    // ⚠ A DATE IS RENDERED IN THE TENANT'S OWN ZONE AND FORMAT (IS-8), which
    // is why `DateCell` REQUIRES both and this config takes the cell rather
    // than building one: a rate effective "01 Jan 2026" in Boise is not the
    // same instant as in Jakarta, and a hard-coded format would show a US
    // utility's date to an Indonesian one backwards.
    effectiveFrom: (row: LabourRateRow) => React.ReactNode;
  },
): TableConfig<LabourRateRow> {
  return {
    screenId: WORK_LABOUR_RATES_SCREEN,
    getRowId: (row) => row.id,
    searchFields: ["role_label"],
    searchPlaceholder: "work.labourRates.search",
    defaultSort: { sort: "effective_from", dir: "desc" },
    columns: [
      {
        key: "role_label",
        label: t("work.labourRates.col.role"),
        identity: true,
        // ⚠ B14 rule 31 — the CODE (`field_technician`) is a database value and
        // is never what a person reads. The typed label is, and it falls back
        // to nothing rather than to the code.
        cell: (row) => <span>{row.role_label}</span>,
      },
      {
        key: "hourly",
        label: t("work.labourRates.col.perHour"),
        numeric: true,
        // FOUR decimals, deliberately — see the file header. The server sends
        // `"48.5000"` and it is rendered verbatim; parsing it into a number
        // would make it a float, which hard rule 2 forbids outright.
        cell: (row) => <span className="tabular-nums">{row.hourly}</span>,
      },
      {
        key: "overtime_hourly",
        label: t("work.labourRates.col.overtimePerHour"),
        numeric: true,
        cell: cells.overtime,
      },
      {
        key: "overtime_after_hours",
        label: t("work.labourRates.col.overtimeAfter"),
        numeric: true,
        cell: cells.threshold,
      },
      {
        key: "effective_from",
        label: t("work.labourRates.col.effectiveFrom"),
        cell: cells.effectiveFrom,
      },
      { key: "current", label: t("work.labourRates.col.status"), cell: cells.status },
    ],
  };
}

export interface LabourRatesPageProps extends RegionalProps {
  client?: ApiClient; // test seam — screens never build their own transport
}

/** `Work-030` at `…/settings/configure/reference-data/work-labour-rates`. */
export function LabourRatesPage(props: LabourRatesPageProps) {
  const { t } = useTranslation();
  const client = props.client ?? api;
  const translate: Translate = (key, params) => t(key, params);

  const { timeZone, dateFormat } = useRegional(props);
  const config = useMemo(
    () =>
      labourRatesTableConfig(translate, {
        effectiveFrom: (row) => (
          <DateCell value={row.effective_from} timeZone={timeZone} dateFormat={dateFormat} />
        ),
        // ⚠ A DASH, NEVER A ZERO. See the file header.
        overtime: (row) =>
          row.overtime_hourly === null ? (
            <Dash />
          ) : (
            <span className="tabular-nums">{row.overtime_hourly}</span>
          ),
        threshold: (row) =>
          row.overtime_after_hours === null ? (
            <Dash />
          ) : (
            <span className="tabular-nums">
              {t("work.labourRates.hoursPerDay", { hours: row.overtime_after_hours })}
            </span>
          ),
        // A superseded row is history and is drawn as history — it is still
        // the rate every job closed before the change is priced at, so it is
        // never hidden.
        status: (row) => (
          <StatusPill tone={row.current ? "success" : "muted"}>
            {translate(
              row.current ? "work.labourRates.status.current" : "work.labourRates.status.superseded",
            )}
          </StatusPill>
        ),
      }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [t, timeZone, dateFormat],
  );

  const [state, setState] = useState<TableRequestState>(() => defaultRequestState(config));
  const query = useQuery({
    queryKey: ["work", "labour-rates", state.page, state.per],
    queryFn: () => listLabourRates({ page: state.page, per: state.per }, client),
  });

  return (
    <section aria-label={t("work.labourRates.title")}>
      <PageHeader
        // B14 rule 2 — ONE page header. This screen is a Settings
        // reference-data card rather than a Work tab, so it carries no strip;
        // its one sentence (rule 32) rides in the roll-up slot, which is where
        // every other reference-data card puts it.
        kicker={t("work.labourRates.kicker")}
        title={t("work.labourRates.title")}
        rollup={t("work.labourRates.description")}
      />

      <DataTable<LabourRateRow>
        config={config}
        state={state}
        onStateChange={setState}
        rows={query.data?.rows ?? []}
        totalRows={query.data?.total ?? null}
        loading={query.isPending}
        error={
          query.isError
            ? { reason: t("work.labourRates.loadFailed"), onRetry: () => void query.refetch() }
            : null
        }
        empty={{
          title: t("work.labourRates.empty.title"),
          helper: t("work.labourRates.empty.helper"),
          ctaLabel: t("work.labourRates.empty.cta"),
          onCta: () => undefined,
          // The Add flow is `US-WRK-051`'s form and is not on this wave's
          // screen list — disabled WITH its reason rather than a live button
          // onto nothing (`BR-SHL-025`).
          ctaReason: t("work.labourRates.empty.ctaReason"),
        }}
      />

      {/* B14 rule 11 — the box `Work-030` draws. It says the one thing a
          supervisor about to change a price needs to know, and it is true:
          a rate is dated, and a job keeps the rate it was closed at. */}
      <ConsequenceBox
        tone="check"
        title={t("work.labourRates.consequence.title")}
        body={t("work.labourRates.consequence.body")}
      />

      {/* `Work-030`'s footnote — the four-decimal exception, said once, in a
          clerk's words rather than as a rule id (B14 rule 32). */}
      <p className="mt-3 text-sm text-neutral-600">{t("work.labourRates.footnote")}</p>
    </section>
  );
}
