// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-LED-6723 — the Product Owner on v2.351.84: *"on this screen
//          user is unable to see detail screen of Journal entry - we cannot
//          click on eye."* The eye was correctly DISABLED: the path was
//          registered DELETE-only and there was no read to open.
// Story:   US-LED-013 · A1 S56 — `11b` §2.10 line 436 calls the screen
//          *"Journal list + detail"* with *"lines expand to dimensions"*.
// Drawing: 05-prototype/07 Finance Blueprint.pdf — **p020** draws 1·1 and its
//          item 7 names the control (*"Row actions as icons · 👁 view · ↺
//          reverse"*); **p079** carries the gap it never closed, G3, ⛔,
//          *"open an entry to its lines and dimensions — no read —
//          journal_api.py is DELETE-only"*. Read as IMAGES (B14 rule 42).
//          ⚠ **THE BLUEPRINT DRAWS THE DOOR AND NOT THE ROOM.** No wireframe
//          of the detail exists, so B14 rule 44 decides the whole of it: our
//          token scale, our spacing and the shared component kit, built the
//          way `RefundDetailPage` (the module's other detail) is built.
// Rules:   BR-LED-001 (the five dimensions on a line) · BR-LED-003 + CLAUDE.md
//          hard rule 4 (a posted entry is immutable — THERE IS NO EDIT HERE
//          AND THE SCREEN MUST NOT IMPLY ONE) · BR-LED-012 (the journal list
//          this opens from) · BR-LED-021 (a draft and an opening balance carry
//          NO number) · BR-SHL-023 · hard rule 2 (money to 2 places on screen,
//          never a float) · NFR-3 (the lines page) · B14 rule 2 (one page
//          header) · 21 (Tailwind only — this file is on
//          `styles/route-b-migrated.txt`) · 31 (no database id is ever a
//          visible value) · 32 (one sentence a section) · 33 (RATIONALE is
//          ZERO WORDS on screen) · 40 (32px title — `PageHeader`'s) · 43 · 44
// Tests:   07-frontend/src/features/ledger/journalEntryDoor.dom.test.tsx
// ───────────────────────────────────────────────────────
//
// S56 DETAIL — *"what are the two sides of this entry, and do they agree?"*
//
// ══════════════════════════════════════════════════════════════════════════
// ⚠ A COMPONENT, NOT MARKUP INSIDE A PAGE (B14 rule 43)
// ══════════════════════════════════════════════════════════════════════════
// Rule 43 was ratified on 2026-09-20 after *"use it"* turned out to mean 120
// lines inline in a 4,186-line page, importable by nothing. The page below is
// the route and the fetch; everything that DRAWS is here, and the two tables
// take their rows as props so a test can mount them without a server.
//
// ══════════════════════════════════════════════════════════════════════════
// ⚠ THE FOOTER IS THE ENTRY'S AND IS NEVER RE-SUMMED FROM THE PAGE
// ══════════════════════════════════════════════════════════════════════════
// `entry.debit`, `entry.credit` and `entry.balanced` come off the header the
// server computed over ALL the entry's lines, in SQL, before it cut a page.
// Adding up the fifty rows on screen would produce a footer that disagrees
// with the verdict printed beside it the moment an entry has fifty-one lines —
// and it would still look right on every fixture we have.
//
// ══════════════════════════════════════════════════════════════════════════
// ⚠ AN ENTRY WITH NO NUMBER SHOWS NO NUMBER (B14 rule 31 + hard rule 4)
// ══════════════════════════════════════════════════════════════════════════
// Most rows in the Journal show `—` under ENTRY NO. and `opening` as the
// source, because **an opening balance is not a document and has no document
// number**. A draft has none by BR-LED-021's ruling, and a posted entry whose
// tenant has no series row has none for ever. All three render the same stated
// absence — and the entry's UUID is in the URL and reaches NO cell, which is
// the sibling defect `DET-LED-6661` (a write-off's uuid printed in a memo).
// Hard rule 4 is what makes this load-bearing rather than tidy: a number
// invented on this screen could never be withdrawn.

import type { ReactNode } from "react";

import { useTranslation } from "react-i18next";

import { MoneyCell } from "@/components/MoneyCell";
import { Panel } from "@/components/Panel";
import { InlineLinkTo, PlainTable } from "@/components/Surfaces";
import { billDetailPath } from "@/features/billing/billingShared";
import { paymentDetailRoute } from "@/features/payments/paymentDetailShared";
import { StatusPill } from "@/components/StatusPill";
import { Dash, premisesDetailPath, unitDetailPath } from "@/features/metering/meteringShared";
import { accountDetailPath } from "@/features/customers/customersShared";
import { RecordLink } from "@/components/RecordLink";

import type { JournalDimension, JournalEntryLine, JournalEntryListRow } from "@/api/endpoints";

import { FactRow } from "./financeShared";
import { refundDetailPath } from "./RefundDetailPage";

/** The screen id, asserted BY NAME in the door test.
 *
 *  Hard-won law 2's mirror: a hold-expiry test that asserts only an ADDRESS
 *  passes when the router mounts a DIFFERENT screen there, and both screens
 *  open onto *"not built yet"*. So the door test asserts this string as well
 *  as the path. */
export const JOURNAL_ENTRY_DETAIL_SCREEN_ID = "S56-detail";

/** The address `👁 View entry` opens. One definition, imported by the route,
 *  by the row action and by the test, so the three cannot drift apart. */
export const JOURNAL_ENTRY_DETAIL_ROUTE = "/finance/journal-entries/:entryId";

export function journalEntryDetailPath(entryId: string): string {
  return `/finance/journal-entries/${encodeURIComponent(entryId)}`;
}

/**
 * Record links (PO 2026-10-19) — the page of the record an entry was posted
 * FROM, built off `journal_entries.source_type` + `source_id` (B2 §2's
 * polymorphic pair). Only the three kinds with a detail page open anything: a
 * bill, a payment and a refund. Every other source — a manual entry, a
 * write-off, an accrual — returns `null` and its word stays text.
 */
export function journalSourcePath(
  sourceType: string | null,
  sourceId: string | null | undefined,
): string | null {
  if (sourceId === null || sourceId === undefined || sourceId === "") {
    return null;
  }
  switch (sourceType) {
    case "invoice":
      return billDetailPath(sourceId);
    case "payment":
      return paymentDetailRoute(sourceId);
    case "refund":
      return refundDetailPath(sourceId);
    default:
      return null;
  }
}

/** One dimension cell — the LABEL, or a stated absence.
 *
 *  Three states and they are three different facts, which is why this is a
 *  component and not a ternary repeated five times:
 *    * the line does not carry this dimension → `—` (a cash line has no
 *      service, and BR-LED-001 requires each one only *where it applies*);
 *    * it carries one this product could not name → `—` with the reason, from
 *      the catalogues;
 *    * it carries one with a name → the name. **Never the id** (B14 rule 31).
 */
export function DimensionCell(props: {
  value: JournalDimension | null;
  /** Record links (DEF-LED-10303): the tenant address of the record this
   *  dimension names, built from its id. Absent → the label stays text. */
  hrefFor?: (id: string) => string;
}) {
  const { t } = useTranslation();
  if (props.value === null) {
    return <Dash />;
  }
  if (props.value.label === null || props.value.label === "") {
    return <Dash>{t("finance.entryDetail.unnamed")}</Dash>;
  }
  return (
    <RecordLink to={props.hrefFor === undefined ? null : props.hrefFor(props.value.id)}>
      {props.value.label}
    </RecordLink>
  );
}

export interface JournalEntryLinesProps {
  lines: JournalEntryLine[];
  entry: JournalEntryListRow;
  locale?: string;
  /** Record links (DEF-LED-10303): the page's `useTenantPath()`. Absent → the
   *  customer, premises and unit cells stay text. */
  tenantPath?: (path: string) => string;
}

/** The two sides, as one table, debits first.
 *
 *  ⚠ **DEBIT AND CREDIT ARE TWO COLUMNS AND NEVER ONE SIGNED AMOUNT.** That is
 *  `journal_lines.side` carried all the way to the screen: a reader never has
 *  to work out what a minus sign meant, which is the same discipline S59's
 *  account ledger keeps.
 */
export function JournalEntryLines(props: JournalEntryLinesProps) {
  const { t } = useTranslation();
  const tp = props.tenantPath;
  const link = (path: (id: string) => string) =>
    tp === undefined ? undefined : (id: string) => tp(path(id));
  return (
    <PlainTable data-testid="journal-entry-lines">
      <thead>
        <tr>
          <th scope="col">{t("finance.entryDetail.col.account")}</th>
          <th scope="col">{t("finance.entryDetail.col.service")}</th>
          <th scope="col">{t("finance.entryDetail.col.customer")}</th>
          <th scope="col">{t("finance.entryDetail.col.premises")}</th>
          <th scope="col">{t("finance.entryDetail.col.unit")}</th>
          <th scope="col" className="text-right">
            {t("finance.entryDetail.col.debit")}
          </th>
          <th scope="col" className="text-right">
            {t("finance.entryDetail.col.credit")}
          </th>
        </tr>
      </thead>
      <tbody>
        {props.lines.map((line) => (
          <tr key={line.line_id}>
            {/* B14 rule 31 — the chart CODE and its NAME. The account's row id
                is what the read was made with and reaches no cell. */}
            <td>
              <span className="font-mono text-sm">{line.account_code ?? ""}</span>
              {line.account_name !== null && (
                <span className="ml-2">{line.account_name}</span>
              )}
            </td>
            <td>
              <DimensionCell value={line.service} />
            </td>
            <td>
              <DimensionCell value={line.account} hrefFor={link(accountDetailPath)} />
            </td>
            <td>
              <DimensionCell value={line.premises} hrefFor={link(premisesDetailPath)} />
            </td>
            <td>
              <DimensionCell value={line.unit} hrefFor={link(unitDetailPath)} />
            </td>
            <td className="text-right">
              {line.debit === null ? (
                <Dash />
              ) : (
                <MoneyCell
                  amount={line.debit}
                  currency={props.entry.currency}
                  locale={props.locale}
                />
              )}
            </td>
            <td className="text-right">
              {line.credit === null ? (
                <Dash />
              ) : (
                <MoneyCell
                  amount={line.credit}
                  currency={props.entry.currency}
                  locale={props.locale}
                />
              )}
            </td>
          </tr>
        ))}
      </tbody>
      <tfoot>
        {/* ⚠ THE ENTRY'S OWN TOTALS, NOT THE PAGE'S — see the header comment.
            `data-testid` is on the footer so the door test can assert the two
            sides agree without re-adding the rows itself. */}
        <tr data-testid="journal-entry-foot">
          <th scope="row" colSpan={5}>
            {t("finance.entryDetail.bothSides")}
          </th>
          <td className="text-right">
            <MoneyCell
              amount={props.entry.debit}
              currency={props.entry.currency}
              locale={props.locale}
            />
          </td>
          <td className="text-right">
            <MoneyCell
              amount={props.entry.credit}
              currency={props.entry.currency}
              locale={props.locale}
            />
          </td>
        </tr>
      </tfoot>
    </PlainTable>
  );
}

/** The header facts. B14 rule 32: one section, and the facts ARE the sentence.
 *
 *  ⚠ **NOTHING HERE IS A FIELD.** No input, no save, no version marker — hard
 *  rule 4 makes a posted entry immutable for ever and the only correction is
 *  reverse + repost. B14 rule 33 then decides how that is said on screen:
 *  RATIONALE IS ZERO WORDS, so the screen does not EXPLAIN that it cannot be
 *  edited. It simply offers nothing that could be. */
export function JournalEntryFacts(props: {
  entry: JournalEntryListRow;
  lineCount: number;
  /** Record links: the tenant address of the source record, or null. */
  sourceHref?: string | null;
}) {
  const { t } = useTranslation();
  const entry = props.entry;
  return (
    <>
      <FactRow
        label={t("finance.entryDetail.number")}
        value={
          entry.je_number === null || entry.je_number === "" ? (
            // ⚠ THE ABSENCE, SHOWN — never a composed number, never the uuid.
            <Dash />
          ) : (
            entry.je_number
          )
        }
      />
      <FactRow label={t("finance.entryDetail.date")} value={entry.entry_date ?? <Dash />} />
      <FactRow
        label={t("finance.entryDetail.source")}
        value={
          entry.source_mapped && entry.source_label !== null ? (
            props.sourceHref !== undefined && props.sourceHref !== null ? (
              <InlineLinkTo to={props.sourceHref}>
                {t(`finance.journal.source.${entry.source_label}`, {
                  defaultValue: entry.source_label,
                })}
              </InlineLinkTo>
            ) : (
              t(`finance.journal.source.${entry.source_label}`, {
                defaultValue: entry.source_label,
              })
            )
          ) : (
            <Dash />
          )
        }
      />
      <FactRow label={t("finance.entryDetail.memo")} value={entry.memo ?? <Dash />} />
      <FactRow
        label={t("finance.entryDetail.lines")}
        value={String(props.lineCount)}
      />
    </>
  );
}

/** The one-line verdict beside the figures. Six words at most (B14 rule 33 —
 *  a FACT). */
export function BalanceVerdict(props: { balanced: boolean }) {
  const { t } = useTranslation();
  return (
    <StatusPill tone={props.balanced ? "success" : "danger"}>
      {props.balanced
        ? t("finance.entryDetail.balanced")
        : t("finance.entryDetail.notBalanced")}
    </StatusPill>
  );
}

/** The whole body, so the page is a route and a fetch and nothing else. */
export function JournalEntryDetailBody(props: {
  entry: JournalEntryListRow;
  lines: JournalEntryLine[];
  lineCount: number;
  locale?: string;
  pager?: ReactNode;
  /** Record links: the tenant address of the entry's source record, or null. */
  sourceHref?: string | null;
  /** Record links (DEF-LED-10303): passed to the lines table. */
  tenantPath?: (path: string) => string;
}) {
  const { t } = useTranslation();
  return (
    <>
      <Panel data-testid="journal-entry-facts">
        <div className="mb-4">
          <h3 className="m-0 font-heading text-h5 leading-heading">
            {t("finance.entryDetail.theEntry")}
          </h3>
        </div>
        <JournalEntryFacts
          entry={props.entry}
          lineCount={props.lineCount}
          sourceHref={props.sourceHref}
        />
      </Panel>
      <Panel>
        <div className="mb-4 flex items-center justify-between gap-4">
          <h3 className="m-0 font-heading text-h5 leading-heading">
            {t("finance.entryDetail.theLines")}
          </h3>
          <BalanceVerdict balanced={props.entry.balanced} />
        </div>
        <JournalEntryLines
          entry={props.entry}
          lines={props.lines}
          locale={props.locale}
          tenantPath={props.tenantPath}
        />
        {props.pager}
      </Panel>
    </>
  );
}
