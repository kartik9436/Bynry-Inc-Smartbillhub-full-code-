// ── Trace ──────────────────────────────────────────────
// Change:   CR-030 W4 task 4.13, the FOURTH unnumbered screen — **Form
//           definitions (Settings → Configure)**, which BR-CUS-095 makes
//           concrete as *"a checklist — for each request type, tick which
//           documents are required"*. Screens: none — decision **D1** (A1's
//           reserved band is exhausted and allocation is the PO's); the route
//           row in `routing/screenIds.ts` carries that finding rather than
//           minting an id.
// Rules:    BR-CUS-095 (PO 2026-08-24, closing OQ-351) — *"We ship with nothing
//           ticked, and a utility that configures nothing blocks nothing."* ·
//           BR-SHL-025 · B14 rules 20 · 21 · CLAUDE.md hard rule 1 (tenancy)
// Tests:    ServiceRequestDocumentSettingsPage.test.tsx
// Impacts:  `GET|PUT /api/{tenant}/service-request-settings/document-requirements`
//           (live, System Admin only)
// ───────────────────────────────────────────────────────
//
// ⚠ **THE ONE THING THIS SCREEN MUST NOT DO IS BE HELPFUL.** BR-CUS-095's
// sharpest clause, verbatim: *"THE DEFAULT IS THE RULING'S SHARPEST CLAUSE AND
// MUST NOT BE SOFTENED: nothing is ticked, so a utility that never opens the
// screen never has a request blocked. No helpful pre-tick of proof of identity,
// however reasonable it looks — a product that blocks approvals out of the box
// for a rule its customer never chose is worse than one that blocks none."*
//
// So: no default ticks, no "recommended" marker, no pre-selected request type
// with a suggested set. The grid renders exactly what the server serves, and
// the server serves an EMPTY table until a human ticks a box.
//
// ⚠ **AND `configured` IS NOT `required`.** The GET returns the whole 5 × 8
// grid whether or not a row exists, because a checklist that listed only what
// somebody had already touched could never be ticked for the first time. An
// untouched cell is `required:false, configured:false` — *"nobody has looked"* —
// and a cell somebody ticked and then un-ticked is `required:false,
// configured:true` — *"we said no"*. They are two different facts about a
// tenant's law and this screen shows them as two.
//
// ⚠ **TWO GATES, JOINED NOT REPLACED (B19 §5).** Ticking a box here NEVER
// blocks CREATION; it blocks APPROVAL, and only once the document is both
// attached AND verified. The sentence saying so is on this screen because this
// is where somebody decides to tick.
import { useMutation, useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { PageHeader } from "@/components/PageHeader";
import { Panel } from "@/components/Panel";
import { LoadingSkeleton } from "@/components/StateFrame";
import { StatusPill } from "@/components/StatusPill";
import { useTenantPath } from "@/routing/tenantPath";

import { DASHBOARD_ROUTE } from "./customersShared";
import {
  DESIGNED_DOC_TYPES,
  SERVICE_REQUEST_OUTCOMES,
  getDocumentRequirements,
  setDocumentRequirement,
} from "./serviceRequestEndpoints";
import type { DocumentRequirementCell } from "./serviceRequestEndpoints";

export function documentRequirementsKey(): readonly unknown[] {
  return ["service-request-document-requirements"];
}

/** `(request_type, doc_type)` → the served cell. Built once per render so the
 *  grid is a lookup rather than a scan per checkbox. */
export function cellIndex(
  rows: readonly DocumentRequirementCell[],
): Map<string, DocumentRequirementCell> {
  return new Map(rows.map((row) => [`${row.request_type}::${row.doc_type}`, row]));
}

export interface ServiceRequestDocumentSettingsPageProps {
  client?: ApiClient;
}

export function ServiceRequestDocumentSettingsPage(
  props: ServiceRequestDocumentSettingsPageProps,
) {
  const { t } = useTranslation();
  const tenantPath = useTenantPath();
  const client = props.client ?? api;

  const gridQuery = useQuery({
    queryKey: documentRequirementsKey(),
    queryFn: () => getDocumentRequirements(undefined, client),
  });

  const save = useMutation({
    mutationFn: (body: { request_type: string; doc_type: string; required: boolean }) =>
      setDocumentRequirement(body, client),
    onSuccess: () => void gridQuery.refetch(),
  });

  if (gridQuery.isLoading) {
    return <LoadingSkeleton variant="table" />;
  }

  // A 403 here is the RULE, not a failure: this is a tenant SETTING and it is
  // System Admin only, because ticking `proof_of_identity` for `move_in`
  // changes what every future approval of that job type demands.
  if (gridQuery.isError) {
    return (
      <p role="alert" className="text-sm text-danger-500">
        {t("customers.serviceRequest.docSettings.loadFailed")}
      </p>
    );
  }

  const rows = gridQuery.data?.requirements ?? [];
  const index = cellIndex(rows);
  const tickedCount = rows.filter((row) => row.required).length;

  return (
    <div>
      <PageHeader
        kicker={t("customers.serviceRequest.docSettings.kicker")}
        title={t("customers.serviceRequest.docSettings.title")}
        backTo={{
          to: tenantPath(DASHBOARD_ROUTE),
          label: t("customers.serviceRequest.docSettings.back"),
        }}
        status={
          <StatusPill tone="neutral">
            {t("customers.serviceRequest.docSettings.tickedCount", { count: tickedCount })}
          </StatusPill>
        }
      />

      <Panel as="section">
        {/* The ruling's own sentence, on the screen it is about. */}
        <p className="max-w-prose text-sm text-neutral-700">
          {t("customers.serviceRequest.docSettings.shipsUnticked")}
        </p>
        <p className="max-w-prose text-sm text-neutral-700">
          {t("customers.serviceRequest.docSettings.twoGates")}
        </p>
      </Panel>

      {/* ONE table type (B14 rule 20) — the shared `.data-table`, not a bespoke
          grid. Wide content scrolls inside its own container rather than making
          the page scroll sideways. */}
      <div className="overflow-x-auto">
        <table className="data-table">
          <thead>
            <tr>
              <th>{t("customers.serviceRequest.docSettings.col.document")}</th>
              {SERVICE_REQUEST_OUTCOMES.map((outcome) => (
                <th key={outcome} scope="col">
                  {t(`customers.serviceRequest.type.${outcome}`)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {DESIGNED_DOC_TYPES.map((docType) => (
              <tr key={docType}>
                <th scope="row">{t(`customers.serviceRequest.docType.${docType}`)}</th>
                {SERVICE_REQUEST_OUTCOMES.map((outcome) => {
                  const cell = index.get(`${outcome}::${docType}`);
                  const required = cell?.required ?? false;
                  const configured = cell?.configured ?? false;
                  return (
                    <td key={outcome}>
                      <label className="inline-flex items-center gap-2 text-sm">
                        <input
                          type="checkbox"
                          checked={required}
                          disabled={save.isPending}
                          data-requirement={`${outcome}::${docType}`}
                          data-configured={String(configured)}
                          onChange={() =>
                            save.mutate({
                              request_type: outcome,
                              doc_type: docType,
                              required: !required,
                            })
                          }
                        />
                        {/* ⚠ THE TWO ABSENCES ARE SPELLED DIFFERENTLY. An
                            untouched cell says *nobody has looked*; a cell
                            ticked and un-ticked says *we said no*. Rendering
                            both as a bare empty box would lose a fact the
                            server went out of its way to serve. */}
                        <span className="text-neutral-700">
                          {required
                            ? t("customers.serviceRequest.docSettings.required")
                            : configured
                              ? t("customers.serviceRequest.docSettings.notRequired")
                              : t("customers.serviceRequest.docSettings.neverConfigured")}
                        </span>
                      </label>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* ⚠ **THE NINTH VALUE IS NOT IN THIS GRID AND MUST NOT BE.** `other` —
          REQ-03.4's `Anything else` — is ATTACHABLE AND NEVER TICKABLE. Keeping
          the two vocabularies apart is what stops a tenant ticking a box that
          no attachment can ever satisfy. */}
      <p className="mt-2 max-w-prose text-sm text-neutral-700">
        {t("customers.serviceRequest.docSettings.otherIsNotTickable")}
      </p>
    </div>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-030 W4 task 4.13 (the fourth unnumbered screen) · BR-CUS-095
// generated: 2026-08-24 by the CR-031 W4 FRONTEND lane (M3)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-08)
// gates: tsc✔ eslint✔ vitest✔ · G13✔ G31✔ G40✔
// exceptions: E3 the screen has NO id from either authority — A1's reserved
//   band is exhausted (decision **D1**) and r10 draws no such screen; the route
//   row in `routing/screenIds.ts` carries the reason rather than minting one ·
//   E3 it is a ROUTE of its own rather than a tab body inside `SettingsPage
//   .tsx`, which owns the Configure strip and is not this lane's file — the
//   SET-06D/SET-07D precedent. Folding it into the strip is one line, OWED
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
