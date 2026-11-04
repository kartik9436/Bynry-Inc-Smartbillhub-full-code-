// ── Trace ──────────────────────────────────────────────
// Change:   CR-150-BRC09 task 12 — the Audit tab. MOVED here from
//           `features/customers/BuildDetailTabs.tsx:1194` by `DEF-CUS-7618`,
//           unchanged in what it renders.
// Drawing:  `05-prototype/new-connect-detail-2026-09-28/07-audit.png`
// Rules:    B14 rule 20 · rule 31 · rule 43 · B14 rule 34 (one pair of words
//           for *held here* and *in the books*)
// Tests:    src/features/customers/BuildDetailTabs.dom.test.tsx
// ───────────────────────────────────────────────────────
//
// ══════════════════════════════════════════════════════════════════════════
// WHY NO SHARED PANEL SERVES THIS TAB
// ══════════════════════════════════════════════════════════════════════════
// There is no audit panel in `buildViews.tsx`, and that file's `BuildTab`
// docstring says why it is not there: *"AND THERE IS NO CHARGES PANEL AND NO
// HISTORY PANEL … the account's Bills, Adjustments and Audit tabs already
// hold both, and the premises has its own Audit log tab."* Those two audit
// tabs each read their OWN entity's trail — `GET /accounts/{id}/audit` and
// the premises' equivalent — and neither can be pointed at a connection.
// What this reads is `detail.history`, `_history`'s window on audit's
// `entity_trail` for THIS build, which arrives on the build's own read. New
// tab content with no shared panel, so it lives in the kit (`CR-151-BRC09`
// §3).
//
// ⚠ **NEWEST FIRST IS THE SERVER'S ORDER AND IS NOT RE-SORTED HERE.**
// `_history` reads audit's own `entity_trail`, which is the window every Audit
// tab in this product uses; a second ordering would be this screen deciding
// something audit already decided.
import { BUILD_AUDIT_ACTION, buildWord } from "@/features/customers/newConnectShared";
import { DateCell } from "@/components/DateCell";
import { PlainTable } from "@/components/Surfaces";

import { Section } from "./buildTabShell";
import type { BuildTabProps } from "./buildTabShell";

export function BuildAuditTab(props: BuildTabProps) {
  const { t, detail } = props;
  return (
    <Section id="audit" title={t("customers.build.audit.title", { defaultValue: "Audit" })}>
      {detail.history.length === 0 ? (
        <p className="text-sm text-neutral-700" data-build-empty="audit">
          {t("customers.build.audit.none", { defaultValue: "Nothing recorded yet." })}
        </p>
      ) : (
        <PlainTable data-table="build-audit">
          <thead>
            <tr>
              <th>{t("customers.build.audit.col.when", { defaultValue: "When" })}</th>
              <th>{t("customers.build.audit.col.who", { defaultValue: "Who" })}</th>
              <th>{t("customers.build.audit.col.what", { defaultValue: "What" })}</th>
            </tr>
          </thead>
          <tbody>
            {detail.history.map((row, index) => (
              <tr key={`${row.at}-${index}`} data-audit-row={index}>
                <td>
                  <DateCell
                    value={row.at}
                    timeZone={props.timeZone}
                    dateFormat={props.dateFormat}
                    withTime
                  />
                </td>
                <td>{row.who}</td>
                {/* ⚠ **`DEF-MET-7805` — THIS COLUMN PRINTED
                    `connection.committed` AND ITS NINE SIBLINGS.**
                    `customers.build.audit.action.*` resolves in none of the
                    eleven catalogues, so the `defaultValue` was the event
                    token. A history is the one place a clerk reads top to
                    bottom, so it is the worst place to put nine dotted
                    identifiers. The words are past tense, three at most
                    (B14 rule 33). */}
                <td>
                  {buildWord(BUILD_AUDIT_ACTION, row.what, "customers.build.audit.action", t)}
                </td>
              </tr>
            ))}
          </tbody>
        </PlainTable>
      )}
    </Section>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: DEF-CUS-7618 · CR-150-BRC09 task 12 · `07-audit.png` (rule 42)
// generated: 2026-09-28 by the DETAIL PAGE lane; MOVED into the kit the same
//   day by the DEF-CUS-7618 lane, with no change to what it renders
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO)
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
