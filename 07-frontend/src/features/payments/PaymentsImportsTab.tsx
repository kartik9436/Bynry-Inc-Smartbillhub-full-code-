// ── Trace ──────────────────────────────────────────────
// Change:   `P1.5` of `05-prototype/06 Payments Page Blueprint.pdf` — §03 frame
//           4·1 *Batches*, read at 2.0 (p061–p062). Task row: *"Mount the
//           existing imports list · With `target=payments`. Three copies already
//           exist for premises, assets and accounts."* Outcome: **"A fourth
//           caller, not a fourth implementation."**
// Screens:  S35 · PAY-F (the §05 register's own row: *"Reuse — the existing
//           imports list, target=payments"*)
// Rules:    BR-MET-096 (ONE ETL runner, `target` parameterised) · B14 rule 4
//           (ONE primary per page, and the drawing's *Doors: The Imports tab.
//           1 door.*) · rules 12–17 · rule 21 (utilities, no stylesheet class —
//           listed in the same commit) · rule 36 · rule 43
// Tests:    src/features/payments/paymentsImportsTab.dom.test.tsx
// ───────────────────────────────────────────────────────
// S35 — the Imports tab of the Payments page, and the door that releases every
// other piece of phase 1's import work.
//
// ⚠ **THIS FILE IS DELIBERATELY THIS SHORT.** `P1.17` proved, before this lane
// started, that the ONE runner already renders correctly for `target="payments"`
// — seven cases in `paymentsRunnerIsReady.dom.test.tsx` — and `P1.5`'s outcome
// asks for a fourth CALLER. Everything a run list does now lives in
// `components/workflow/ImportRunsList.tsx`; what belongs to payments is the
// four sentences below.
//
// ⚠ **NO ROLLBACK CONTROL, AND IT IS A CLAIM ABOUT THE SERVER RATHER THAN A
// SCOPE CUT.** `import_runs.rollback` refuses the payments target BY NAME and
// `_load_payments_rows` creates no rollback point to spend, because a posted
// payment cannot be unwritten (CLAUDE.md hard rule 4). So this list passes
// `rollbackConsequence={null}` and the kit's own per-target rule
// (`rollbackControlIsOffered`) refuses the row action a second time. The way
// to throw a payments batch away is *Discard this batch* BEFORE the commit,
// which is stage 4's control and is drawn on 4·2.
//
// ⚠ **AND NO KPI STRIP, WHICH IS THE ONE PLACE THIS SCREEN DOES NOT FOLLOW ITS
// OWN WIREFRAME.** 4·1 draws four tiles — *Waiting · Applied today · Needs a
// person · Refused* — over figures `GET /imports` does not serve: there is no
// money on `ImportRunRow`, no *applied today*, and no count of rejects still
// open. B14 rule 37 makes a figure in a wireframe an illustration rather than a
// fact to build to, and the §05 register row for this very screen says *"Reuse
// — the existing imports list"*. Four tiles reading `—` would be worse than
// four tiles that are not there. **The gap is FILED, with the endpoint each
// tile would need.**
import { useTranslation } from "react-i18next";

import type { ApiClient } from "@/api/client";
import { ImportRunsList } from "@/components/workflow";

/** The ONE target this tab lists — the eighth `ImportTarget`, `P1.1`. A
 *  one-option Target filter would change nothing (B14 rule 9's own objection),
 *  so the scope is SENT to the server instead of drawn as a choice. */
export const PAYMENTS_IMPORT_TARGET = "payments";

/** Where the `↑ Import →` door goes — TENANT-RELATIVE, so the caller prefixes
 *  it exactly as every other payments address is prefixed.
 *
 *  ⚠ **IT IS AN ADDRESS AND NOT A CLICK HANDLER, DELIBERATELY.** The blueprint
 *  gives this screen exactly one door and `DEF-CWP-3925` is what a door with no
 *  address costs: a handler carries nothing a test can assert, so the one
 *  assertion that catches the door breaking cannot be written. */
export const PAYMENTS_IMPORT_NEW_ROUTE = "/payments/imports/new";

export interface PaymentsImportsTabProps {
  /** BR-SHL-025: null = allowed; a string disables the controls WITH it. */
  writeBlockedReason: string | null;
  /** Open the runner at Extract — the ONE entry, owned by the page header. */
  onImport: () => void;
  client?: ApiClient;
}

export function PaymentsImportsTab(props: PaymentsImportsTabProps) {
  const { t } = useTranslation();

  return (
    <ImportRunsList
      targets={[PAYMENTS_IMPORT_TARGET]}
      // S35 is A1's own id for this screen, and the §05 register's.
      screenId="S35"
      cacheScope="payments"
      empty={{
        title: t("payments.imports.empty.title"),
        helper: t("payments.imports.empty.helper"),
        ctaLabel: t("payments.imports.action.import"),
      }}
      // See the file header: the server refuses this target's rollback, so
      // there is no sentence to state and no control to state it on.
      rollbackConsequence={null}
      writeBlockedReason={props.writeBlockedReason}
      onImport={props.onImport}
      client={props.client}
    />
  );
}

export default PaymentsImportsTab;

// ── Lifecycle ─────────────────────────────────────────────
// packet: payments blueprint p14 `P1.5` · §03 frame 4·1 (p061–p062) · §05 register row S35 · PAY-F
// generated: 2026-09-22 by LANE P1-C
// checklist: A✔ B=n/a(no new endpoint — `GET /imports?f.target=payments`) C✔ D=n/a E✔(PaymentsPage mounts it on the Imports tab, and the hold that stood there is gone) F✔ G✔ H=n/a
// gates: tsc --noEmit · vitest src/features/payments/paymentsImportsTab.dom.test.tsx · vitest src/features/payments/sevenTabs.dom.test.tsx (the hold-expiry case, flipped in this commit) · G31 (listed on src/styles/route-b-migrated.txt) · routeBUtilities.test.ts
// exceptions: E3 4·1's four KPI tiles and its SOURCE, LABEL and AMOUNT columns are NOT drawn — `ImportRunRow` serves none of those fields and the register says *Reuse*; filed rather than invented · E3 no rollback row action: the server refuses this target by name
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
