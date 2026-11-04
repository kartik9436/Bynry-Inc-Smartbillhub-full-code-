// ── Trace ──────────────────────────────────────────────
// Story:    US-CUS-019 (bulk account upload) · US-CUS-020 (the value-mapping
//           step) · US-CUS-021/022 (aged opening balances and their journal
//           entries) · US-CUS-023 (deposits with original receipt dates)
//           Screens: S68 (the import wizard, finally as A1 specified it)
// Change:   CR-030 W1 — the account import moves onto the ONE ETL runner
//           (BR-MET-096), the sixth target beside premises, units and the
//           three assets kinds.
// Rules:    BR-MET-096 (one runner, `target` parameterised — a new import is a
//           TARGET, never a new pipeline) · BR-CUS-046 (the published template
//           and its auto-numbered account column) · BR-CUS-047 (migration
//           order: a row naming a missing unit ERRORS) · BR-CUS-052 (the
//           source→target value-mapping step) · BR-SHL-025 (a thing this
//           deployment cannot honour renders WITH its reason)
// Impacts:  App.tsx (the /accounts/import route this replaces) ·
//           components/workflow/kinds.ts (the `accounts` kind) ·
//           ImportAccountsWizard.tsx (the three-step modal this supersedes)
// ───────────────────────────────────────────────────────
// WHY THIS FILE REPLACES A WORKING SCREEN.
//
// ⚠ **S68 HAS SPECIFIED FIVE STEPS SINCE 2026-08-08 AND THE PRODUCT SHIPPED
// THREE (DEF-611).** A1's own row reads *"Account onboarding import wizard
// (upload → stage → VALUE-MAP → review → commit)"* and BR-CUS-052 requires the
// mapping step. `ImportAccountsWizard.tsx` implemented `upload → review →
// confirm`: no column mapping and no value mapping, so a utility whose CSV did
// not already use OUR header names could not import accounts at all. Every
// gate was green over it for sixteen days, because no gate compares a shipped
// wizard's step count to the step list A1 writes for it.
//
// So this is not new scope. It is the runner that already does all five stages
// for five other targets being pointed at the sixth.
import { useTranslation } from "react-i18next";

import { WORKFLOW_KINDS } from "@/components/workflow";
import { ImportWorkflowPage } from "@/features/metering/ImportWorkflowPage";
import { PageHeader } from "@/components/PageHeader";
import { ButtonLink } from "@/components/Button";
import type { ImportTarget } from "@/api/endpoints";
import { useTenantPath } from "@/routing/tenantPath";

import { ACCOUNTS_ROUTE } from "./customersShared";

/** The runner target an account import runs as. One value, named once, so the
 *  route, the button and the kind cannot drift apart. */
export const ACCOUNT_IMPORT_TARGET = "accounts";

export function AccountImportWorkflowPage() {
  const { t } = useTranslation();
  const tenantPath = useTenantPath();

  // A REGISTERED target mounts the real five-stage runner — one runner, one
  // implementation, the target the only difference (BR-MET-096).
  if (ACCOUNT_IMPORT_TARGET in WORKFLOW_KINDS) {
    return <ImportWorkflowPage target={ACCOUNT_IMPORT_TARGET as ImportTarget} />;
  }

  // Unreachable while the kind is registered, and kept rather than deleted: it
  // is what a half-deployed build should show instead of a blank page
  // (BR-SHL-025 — state the absence with its reason, in plain words).
  return (
    <div className="px-4 pt-6 pb-8">
      <PageHeader title={t("customers.import.unavailable.title")} />
      <div
        className="max-w-xl border border-divider bg-surface px-4 py-4"
        role="note"
        data-tracks="BR-MET-096"
      >
        <p className="m-0 mb-4 text-base">{t("customers.import.unavailable.body")}</p>
        <ButtonLink variant="secondary" to={tenantPath(ACCOUNTS_ROUTE)}>
          {t("customers.import.unavailable.back")}
        </ButtonLink>
      </div>
    </div>
  );
}
