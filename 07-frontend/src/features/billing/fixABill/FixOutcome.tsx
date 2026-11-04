// ── Trace ──────────────────────────────────────────────
// Change:  CR-180-BRC10 — F5 (bulk per-bill table, going up / going down apart)
//          and F6 (*What changes on the page* for reprint rows)
// Drawing: 05-prototype/fix-a-bill-2026-10-12/09, 10, 12 (page changes) · 14, 15 (bulk)
// Rules:   hard rule 2 · NFR-3 (the bulk rows are a server page) · B14 rule 43
// ───────────────────────────────────────────────────────
/**
 * Two step-2 panels besides the table and the comparison.
 *
 * ⚠ **UP AND DOWN ARE NEVER ADDED TOGETHER** on the bulk tiles — the server's
 * `totals.up` and `totals.down` are shown apart, as drawn (image 14), because
 * a net of +$412 over 44 rises and 0 falls reads very differently from a net of
 * +$412 over 60 rises and 16 falls.
 */
import type { CorrectionPreview } from "@/api/billingOpsEndpoints";
import { ListPager } from "@/components/ListPager";
import type { PageSize } from "@/components/tableTypes";
import { PlainTable } from "@/components/Surfaces";
import { Note } from "@/components/TextBits";

import { OTB_TABLE, OtbPanel, PanelAside, TableScroll } from "../oneTimeBill/oneTimeBillShared";

import { signOf } from "./fixABillModel";
import type { Translate } from "./fixABillModel";
import { changeTone, money, signedMoney } from "./fixABillShared";
import type { FixFmt } from "./fixABillShared";

/** *What changes on the page* — field · was · becomes, for every reprint row. */
export function PageChangesPanel(props: {
  changes: CorrectionPreview["page_changes"];
  cls: string | null;
  t: Translate;
}) {
  const { t } = props;
  if (props.changes.length === 0) return null;
  return (
    <OtbPanel
      id="page-changes"
      title={t("billing.fixBill.page.title")}
      aside={
        <PanelAside>
          {t(props.cls === "document" ? "billing.fixBill.page.same" : "billing.fixBill.page.also")}
        </PanelAside>
      }
    >
      <TableScroll>
        <PlainTable className={OTB_TABLE} data-fix-page-changes="">
          <thead>
            <tr>
              <th scope="col">{t("billing.fixBill.page.field")}</th>
              <th scope="col">{t("billing.fixBill.page.was")}</th>
              <th scope="col">{t("billing.fixBill.page.becomes")}</th>
            </tr>
          </thead>
          <tbody>
            {props.changes.map((change) => (
              <tr key={change.field} className="bg-accent-100">
                <td>
                  {t(`billing.fixBill.reason.${change.field}`, { defaultValue: change.field })}
                </td>
                <td>{change.was ?? "—"}</td>
                <td className="font-semibold">{change.becomes}</td>
              </tr>
            ))}
          </tbody>
        </PlainTable>
      </TableScroll>
    </OtbPanel>
  );
}

function Tile(props: {
  kind: "up" | "down" | "flat";
  label: string;
  figure: string;
  caption: string;
}) {
  const tone =
    props.kind === "up"
      ? "text-accent-700"
      : props.kind === "down"
        ? "text-success-700"
        : "text-text";
  return (
    <div
      className="flex flex-col gap-1 border border-divider bg-surface px-4 py-3"
      data-fix-tile={props.kind}
    >
      <span className="font-heading text-xs font-semibold uppercase tracking-kicker text-neutral-700">
        {props.label}
      </span>
      <span className={`font-heading text-metric font-semibold tabular-nums ${tone}`}>
        {props.figure}
      </span>
      <span className="text-sm text-neutral-700">{props.caption}</span>
    </div>
  );
}

/** *Each bill, was and becomes* — the three tiles and the per-bill page. */
export function BulkBillsPanel(props: {
  preview: CorrectionPreview;
  t: Translate;
  fmt: FixFmt;
  page: number;
  per: PageSize;
  onPage: (page: number) => void;
  onPer: (per: PageSize) => void;
}) {
  const { preview, t, fmt } = props;
  const { up, down, unchanged } = preview.totals;
  return (
    <OtbPanel
      id="bulk-bills"
      title={t("billing.fixBill.bulk.title")}
      aside={<PanelAside>{t("billing.fixBill.bulk.aside", { count: preview.count })}</PanelAside>}
    >
      <div className="grid grid-cols-3 gap-3 max-md:grid-cols-1">
        <Tile
          kind="up"
          label={t("billing.fixBill.bulk.up")}
          figure={`${up.count} · ${signedMoney(up.amount, fmt)}`}
          caption={t("billing.fixBill.bulk.upCaption")}
        />
        <Tile
          kind="down"
          label={t("billing.fixBill.bulk.down")}
          figure={`${down.count} · ${signedMoney(down.amount, fmt)}`}
          caption={t("billing.fixBill.bulk.downCaption")}
        />
        <Tile
          kind="flat"
          label={t("billing.fixBill.bulk.flat")}
          figure={String(unchanged)}
          caption={t("billing.fixBill.bulk.flatCaption")}
        />
      </div>
      <Note as="p" className="mt-3 text-sm">
        {t("billing.fixBill.bulk.apart")}
      </Note>
      <TableScroll>
        <PlainTable className={OTB_TABLE} data-fix-bulk-bills="">
          <thead>
            <tr>
              <th scope="col">{t("billing.fixBill.col.account")}</th>
              <th scope="col">{t("billing.fixBill.col.customer")}</th>
              <th scope="col" data-num="">
                {t("billing.fixBill.col.was")}
              </th>
              <th scope="col" data-num="">
                {t("billing.fixBill.col.becomes")}
              </th>
              <th scope="col" data-num="">
                {t("billing.fixBill.col.change")}
              </th>
            </tr>
          </thead>
          <tbody>
            {preview.bills.map((bill) => (
              <tr
                key={bill.invoice_id}
                className={signOf(bill.delta) === "flat" ? undefined : "bg-accent-100"}
              >
                <td>{bill.account_no ?? "—"}</td>
                <td>{bill.customer_name ?? "—"}</td>
                <td data-num="">{money(bill.was_total, fmt)}</td>
                <td data-num="">{money(bill.becomes_total, fmt)}</td>
                <td data-num="" className={changeTone(bill.delta)}>
                  {signedMoney(bill.delta, fmt)}
                </td>
              </tr>
            ))}
          </tbody>
        </PlainTable>
      </TableScroll>
      <ListPager
        total={preview.count}
        page={props.page}
        per={props.per}
        onPage={props.onPage}
        onPer={props.onPer}
      />
    </OtbPanel>
  );
}
