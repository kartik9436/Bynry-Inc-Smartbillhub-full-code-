// ── Trace ──────────────────────────────────────────────
// Story:    US-BIL-006 (the pending-billing queue + catch-up sub-runs —
//           *"hold ≠ forget"*)
//           Screens: S30 (the queue reached from the Billing header)
// Rules:    BR-BIL-015 (a missing read is a CHOICE, and the hold is the record
//           of it) · BR-BIL-021 (the escalation threshold is a tenant setting
//           and is REPORTED as not-a-setting-yet, never invented) ·
//           BR-BIL-051 / BR-BIL-055 (a catch-up is an ordinary run) ·
//           BR-TEN-043 (an age is measured against a stated day, never a
//           browser clock) · BR-SHL-020 · BR-SHL-044 (one page header)
// ───────────────────────────────────────────────────────
// *"Hold ≠ forget."* This is the door back for every account a bill run did not
// bill — and until this commit there was no handle on it. `GET /billing/pending`
// has been SERVED since the queue landed and `pending.py`'s own trailer says
// what was missing: `E=deferred(no-frontend-half — S30's KPI chip and queue
// list are not built; REPORTED)`. So an account held out of a run was invisible:
// the run said "21 excluded" and nothing in the product could name them.
//
// ══════════════════════════════════════════════════════════════════════════
// THE TWO COLUMNS THIS SCREEN EXISTS FOR
// ══════════════════════════════════════════════════════════════════════════
// `origin` and `stage`. A clerk must read *"we never calculated this"*
// differently from *"we calculated it and it broke at measure-consumption"* —
// the first is fixed by entering a read, the second usually by fixing
// configuration (BR-BIL-055). A queue that showed only "held" would send every
// one of them to the same wrong place.
//
// ══════════════════════════════════════════════════════════════════════════
// AN AGE NEVER APPEARS WITHOUT THE DAY IT IS AN AGE AT
// ══════════════════════════════════════════════════════════════════════════
// `as_of` is a REQUIRED query parameter — the server reads no clock
// (BR-TEN-043) — and it comes back on the envelope beside the ages it produced.
// This screen prints it. A "held 14 days" with no anchor is a figure that
// silently changes meaning when somebody opens the queue from another timezone.
import { useState } from "react";

import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { getPendingQueue } from "@/api/billingOpsEndpoints";
import { DateCell } from "@/components/DateCell";
import type { RegionalDateFormat } from "@/components/DateCell";
import { PageHeader } from "@/components/PageHeader";
import { LoadingSkeleton, PermissionDenied } from "@/components/StateFrame";
import { StatusPill } from "@/components/StatusPill";
import { InlineLinkAnchor, PlainTable } from "@/components/Surfaces";
import { Panel } from "@/components/Panel";
import { accountDetailPath } from "@/features/customers/customersShared";
import { isDenied, useRegional, useAccessCell } from "@/features/metering/meteringShared";
import type { RegionalProps } from "@/features/metering/meteringShared";
import { ArrivesWith, apiErrorText, isPermissionDenied } from "@/features/tenancy/settingsShared";
import type { Translator } from "@/features/tenancy/settingsShared";
import { useTenantPath } from "@/routing/tenantPath";

import { BILLING_PERMISSION, BILLING_ROUTE, DASHBOARD_ROUTE } from "./billingShared";
import { GapNotes, todayIso } from "./billingOpsShared";

export const pendingQueueKey = (asOf: string, includeResolved: boolean) =>
  ["billing", "pending", asOf, includeResolved] as const;

export interface PendingQueuePageProps extends RegionalProps {
  client?: ApiClient; // test seam
}

export function PendingQueuePage(props: PendingQueuePageProps) {
  const { t } = useTranslation();
  const translate: Translator = (key, params) => t(key, params);
  const client = props.client ?? api;
  const navigate = useNavigate();
  const tenantPath = useTenantPath();
  const cell = useAccessCell(BILLING_PERMISSION, client);
  const { timeZone, dateFormat } = useRegional(props);

  const [includeResolved, setIncludeResolved] = useState(false);
  // THE BUSINESS DAY IS STATED, not read server-side (BR-TEN-043, gate G6).
  const [asOf] = useState(() => todayIso());

  const queueQuery = useQuery({
    queryKey: pendingQueueKey(asOf, includeResolved),
    queryFn: () => getPendingQueue({ as_of: asOf, include_resolved: includeResolved }, client),
    retry: false,
  });

  if (isDenied(cell)) {
    return (
      <PermissionDenied
        helper={t("billing.denied")}
        onBack={() => navigate(tenantPath(DASHBOARD_ROUTE))}
      />
    );
  }
  if (queueQuery.isError && isPermissionDenied(queueQuery.error)) {
    return (
      <PermissionDenied
        helper={t("billing.denied")}
        onBack={() => navigate(tenantPath(DASHBOARD_ROUTE))}
      />
    );
  }

  const data = queueQuery.data;
  return (
    <div className="px-4 pt-6 pb-8">
      <PageHeader
        title={t("billing.pending.title")}
        backTo={{ to: tenantPath(BILLING_ROUTE), label: t("billing.title") }}
        rollup={
          data === undefined ? null : (
            <span>
              {/* The counts are the SERVER's and the day they were measured
                  against travels with them. Never a browser-side sum. */}
              {t("billing.pending.rollup", {
                open: data.counts.open ?? 0,
                escalated: data.counts.escalated ?? 0,
                asOf: data.as_of,
              })}
            </span>
          )
        }
      />

      <p className="m-0 mb-4 max-w-measure text-base leading-prose text-[color-mix(in_srgb,var(--color-text)_70%,transparent)]">
        {t("billing.pending.explainer")}
      </p>

      <div className="seg" role="group" aria-label={t("billing.pending.filterLabel")}>
        {[false, true].map((value) => (
          <button
            key={String(value)}
            type="button"
            className={value === includeResolved ? "seg-opt active" : "seg-opt"}
            aria-pressed={value === includeResolved}
            onClick={() => setIncludeResolved(value)}
          >
            {t(value ? "billing.pending.filter.all" : "billing.pending.filter.open")}
          </button>
        ))}
      </div>

      {queueQuery.isError ? (
        <Panel role="alert">
          <h3>{t("billing.pending.errorTitle")}</h3>
          <p className="font-body text-base leading-normal font-normal tracking-normal text-[color-mix(in_srgb,var(--color-text)_62%,transparent)] [&[role=alert]]:text-accent-700">
            {apiErrorText(queueQuery.error, translate)}
          </p>
        </Panel>
      ) : data === undefined ? (
        <LoadingSkeleton variant="table" />
      ) : data.items.length === 0 ? (
        <p
          className="font-body text-base leading-normal font-normal tracking-normal text-[color-mix(in_srgb,var(--color-text)_62%,transparent)] [&[role=alert]]:text-accent-700"
          role="note"
        >
          {t("billing.pending.empty")}
        </p>
      ) : (
        <div className="overflow-x-auto">
          <PlainTable>
            <thead>
              <tr>
                <th scope="col">{t("billing.pending.col.account")}</th>
                <th scope="col">{t("billing.pending.col.period")}</th>
                <th scope="col">{t("billing.pending.col.origin")}</th>
                <th scope="col">{t("billing.pending.col.stage")}</th>
                <th scope="col">{t("billing.pending.col.reason")}</th>
                <th scope="col">{t("billing.pending.col.held")}</th>
                <th scope="col">{t("billing.pending.col.age")}</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((row) => (
                <tr key={row.id}>
                  <td>
                    {/* ⛔ DEF-3158 — was `row.account_no ?? row.account_id.slice(0, 8)`.
                        B14 rule 31: the account HAS a human-facing number and
                        that is what is shown; where it has none the field says
                        so in words and the id rides on `title`. The link is
                        unchanged — it navigates by id, which is a href. */}
                    <InlineLinkAnchor href={tenantPath(accountDetailPath(row.account_id))}>
                      {row.account_no ?? (
                        <span title={row.account_id}>{t("billing.pending.noAccountNo")}</span>
                      )}
                    </InlineLinkAnchor>
                  </td>
                  <td>
                    {row.period_start} – {row.period_end}
                  </td>
                  <td>
                    {/* THE TWO COLUMNS THE STORY EXISTS FOR. A phase-1 hold was
                        never calculated; a phase-3 mark-for-later was, and broke
                        at a named stage. Different fixes. */}
                    <StatusPill tone={row.origin === "hold" ? "warning" : "danger"}>
                      {t(`billing.pending.origin.${row.origin}`, { defaultValue: row.origin })}
                    </StatusPill>
                  </td>
                  <td>
                    {row.stage ?? (
                      <span className="font-body text-base leading-normal font-normal tracking-normal text-[color-mix(in_srgb,var(--color-text)_62%,transparent)] [&[role=alert]]:text-accent-700">
                        {t("billing.pending.noStage")}
                      </span>
                    )}
                  </td>
                  <td>
                    {t(`billing.pending.reason.${row.reason_code}`, {
                      defaultValue: row.detail ?? row.reason_code,
                    })}
                  </td>
                  <td>
                    <DateCell
                      value={row.held_on}
                      timeZone={timeZone}
                      dateFormat={dateFormat as RegionalDateFormat}
                    />
                  </td>
                  <td>
                    {t("billing.pending.ageDays", { days: row.age_days })}
                    {row.escalated && (
                      <span className="block text-xs text-[color-mix(in_srgb,var(--color-text)_60%,transparent)]">
                        {t("billing.pending.escalated")}
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </PlainTable>
        </div>
      )}

      {/* Hard-won law 2, stated rather than hidden: the catch-up sub-run is
          SERVED (`POST /billing/runs/{id}/catch-up`) and needs a parent run to
          hang off, which this list does not choose between — the S31 wizard
          does. Naming it beats a button that would guess which run. */}
      <ArrivesWith title={t("billing.pending.awaitsTitle")} message={t("billing.pending.awaits")} />
      <GapNotes gaps={data?.unavailable ?? []} t={translate} />
    </div>
  );
}

export default PendingQueuePage;

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-BIL-006@c81a5f3 (sources: 04-docs/05-modules/07-billing/06-epics/EP-BIL-01-bill-run.md US-BIL-006 §1/§4/§5 · 07-billing/02-business-rules.md BR-BIL-015/021/051/055 · 06-backend/apps/billing/pending.py + its PENDING_UNAVAILABLE)
// generated: 2026-08-16 by story-coder (billing SURFACE lane — the screen pending.py's own trailer recorded as missing)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: RED PROVED FIRST — the browser check for the queue route failed against the W0 placeholder before this screen existed. Verbatim in the lane report. tsc✔ · eslint --max-warnings 0✔ · vitest✔ · vite build✔ · run_gates✔
// exceptions: E3 the queue is a ROUTE off the Billing header, not a seventh S30 tab: the prototype's strip has six labels and G14 compares the shipped ones against it · E3 an AGE never renders without the day it was measured against — `as_of` is on the envelope and on the screen · E3 no money member is drawn and none is served: a queue row is an account that has NOT been billed, so a zero would be a claim · E3 no catch-up BUTTON: `POST /billing/runs/{id}/catch-up` needs a parent run and this list does not choose between them — named rather than guessed
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
