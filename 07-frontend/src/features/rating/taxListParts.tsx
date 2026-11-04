// ── Trace ──────────────────────────────────────────────
// Change:   CR-165-BRC10 round 2 task 5 — the Taxes & fees LIST's cells, built
//           from images 01–03 of 05-prototype/taxes-fees-2026-10-03 (B14 rule
//           42: the images are the specification, the mock-up's HTML is not).
// Defect:   DEF-RAT-9274 (P21–P28)
// Rules:    B14 rule 21 (Tailwind; on route-b-migrated.txt from its first
//           commit) · rule 31 (no database id on screen) · rule 33 (labels and
//           facts only — no sentence in a cell) · rule 37 (every drawn figure is
//           an illustration) · rule 43 (components, not code inside a page) ·
//           rule 44 (our kit decides spacing, sizes and type) · BR-RAT-087
//           (the server's display string, never the stored fraction) · NFR-3
// Tests:    src/features/rating/taxesFeesList.dom.test.tsx
// Impacts:  src/features/rating/TaxesFeesTab.tsx (the only caller)
// ───────────────────────────────────────────────────────
/**
 * THE PIECES OF ONE TAX ROW, AND THE TWO CONTROLS ABOVE THE TABLE.
 *
 * ⚠ **THE ROUND-2 FIELDS ARE OPTIONAL HERE ON PURPOSE.** `version`,
 * `premises_reached` and `premises_total` are the API contract round 2 builds
 * against (CR-165 §3, task 3), and the back end that serves them is being built
 * by a sibling lane at the same time as this screen. A row from a server that
 * predates them renders a dash in those cells and nothing breaks. They are
 * declared on a LOCAL type rather than on `TaxRow` so this lane edits no line
 * of the shared `endpoints.ts` the wizard and details lanes are also editing;
 * the day the back end lands, `TaxRow` gains them and this type is a no-op.
 *
 * ⚠ **THE BANNER'S NUMBER IS NEVER COUNTED HERE.** See `OverTwentyBanner`.
 */
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";

import type { Paginated, TaxRow } from "@/api/endpoints";
import { Chip } from "@/components/Chip";
import { DateCell } from "@/components/DateCell";
import type { RegionalDateFormat } from "@/components/DateCell";
import { formatRateNumber } from "@/components/MoneyCell";
import { StatusPill } from "@/components/StatusPill";
import type { StatusTone } from "@/components/StatusPill";
import { InlineLink, InlineLinkTo } from "@/components/Surfaces";
import { WarningBox } from "@/components/WarningBox";

/** A list row as the round-2 contract serves it. */
export type TaxListRow = TaxRow & {
  version?: number | null;
  premises_reached?: number | null;
  premises_total?: number | null;
};

/**
 * The list reply. `over_20_count` is NOT in the round-2 contract yet — it is
 * this lane's request to the back end (see `OverTwentyBanner`), so it is
 * optional and its absence draws no banner.
 */
export type TaxListResult = Paginated<TaxListRow> & { over_20_count?: number | null };

/** The `f.<name>` param `Show them` sets. Requested from the back end with
 *  `over_20_count`; sent only once the server has served the count. */
export const TAX_OVER_20_FILTER = "over_20";

/**
 * The Status filter's options — the round-2 contract's status words
 * (`draft|active|scheduled|ended|superseded`), in the order a clerk scans them.
 *
 * ⚠ **A FILTER, NOT BUTTONS (PO 2026-10-03, verbatim: *"on list view of Tax -
 * ensure you ahve filter and not button for filters- follow our toolkkit
 * standard"*).** Images 01–03 draw `All · Active · Draft · Ended` as buttons;
 * that ruling supersedes them, so Status is a `+ Filter` entry and a removable
 * chip like every other list (B14 rule 12). No status filter = all.
 */
export const TAX_LIST_STATUSES = ["active", "draft", "scheduled", "ended", "superseded"] as const;

/** A dash for a value the server has not served — never a zero, never blank. */
const DASH = "—";

/** The second line under a cell's main value. */
const UNDER = "text-sm text-neutral-700";

// ── Pure pieces ────────────────────────────────────────────────────────────

/**
 * Does this row charge more than twenty percent? A COMPARISON of the stored
 * fraction against `0.2`, which formats nothing and rounds nothing, so it is not
 * the client-side money arithmetic BR-RAT-087 keeps on the server.
 */
export function taxIsOverTwenty(row: TaxRow): boolean {
  if (row.kind !== "percent" || row.rate === null) return false;
  const fraction = Number(row.rate);
  return Number.isFinite(fraction) && fraction > 0.2;
}

/** Status meaning only (A12): live is success, waiting is info, over is muted. */
export function taxListStatusTone(status: string): StatusTone {
  if (status === "active") return "success";
  if (status === "scheduled") return "info";
  if (status === "ended" || status === "expired" || status === "superseded") return "muted";
  return "neutral";
}

/** The Rate cell's text: the figure alone, never *"… of the taxable amount"* (P23). */
export function taxListRate(row: TaxRow, t: (key: string, params?: Record<string, unknown>) => string): string {
  if (row.kind === "flat_per_bill") {
    if (row.flat_amount === null) return DASH;
    const amount = formatRateNumber(row.flat_amount);
    return row.flat_frequency === "per_fiscal_year"
      ? t("rating.taxes.list.rate.perYear", { amount })
      : t("rating.taxes.list.rate.perBill", { amount });
  }
  if (row.kind === "per_unit") {
    return row.per_unit_amount === null
      ? DASH
      : t("rating.taxes.list.rate.perUnit", {
          amount: formatRateNumber(row.per_unit_amount),
          unit: row.per_unit_uom ?? DASH,
        });
  }
  if (row.kind === "per_meter") {
    return row.per_meter_amount_display === null
      ? DASH
      : t("rating.taxes.list.rate.perMeter", { amount: row.per_meter_amount_display });
  }
  return row.rate_display ?? DASH;
}

// ── Cells ──────────────────────────────────────────────────────────────────

/** Tax or fee: the name (the door to details) and the authority's level under it (P22). */
export function TaxNameCell(props: { row: TaxListRow; to: string }): ReactNode {
  const { t } = useTranslation();
  const level = props.row.jurisdiction?.level ?? null;
  return (
    <div className="flex flex-col">
      <InlineLinkTo to={props.to} className="font-semibold">
        {props.row.name}
      </InlineLinkTo>
      {level !== null && level !== "" && (
        <span className={UNDER}>{t(`rating.taxes.level.${level}`, { defaultValue: level })}</span>
      )}
    </div>
  );
}

/** Version: `V3` in a small grey tag (P27). */
export function TaxVersionTag(props: { version: number | null | undefined }): ReactNode {
  const { t } = useTranslation();
  if (props.version === null || props.version === undefined) return <span>{DASH}</span>;
  return (
    <span className="inline-block bg-neutral-200 px-1.5 text-xs font-semibold text-neutral-700">
      {t("rating.taxes.list.version", { n: props.version })}
    </span>
  );
}

/** Applies to: service chips, the customer classes under them. */
export function TaxAppliesToCell(props: { row: TaxRow }): ReactNode {
  const { t } = useTranslation();
  const services = props.row.applies_to_services;
  const classes = props.row.applies_to_customer_classes;
  return (
    <div className="flex flex-col gap-1">
      <div className="flex flex-wrap gap-1">
        {services.length === 0 ? (
          <Chip className="font-semibold">{t("rating.taxes.allServices")}</Chip>
        ) : (
          services.map((code) => (
            <Chip key={code} className="font-semibold">
              {t(`rating.service.${code}`, { defaultValue: code })}
            </Chip>
          ))
        )}
      </div>
      <span className={UNDER}>
        {classes.length === 0
          ? t("rating.taxes.list.everyClass")
          : classes
              .map((code) => t(`rating.taxWiz.classes.${code}`, { defaultValue: code }))
              .join(", ")}
      </span>
    </div>
  );
}

/** Rate: the figure, bold, and `Over 20%` under a percentage above twenty (P23, P24). */
export function TaxRateCell(props: { row: TaxRow }): ReactNode {
  const { t } = useTranslation();
  return (
    <div className="flex flex-col items-end gap-1 whitespace-nowrap">
      <span className="font-semibold">{taxListRate(props.row, (key, params) => t(key, params))}</span>
      {taxIsOverTwenty(props.row) && (
        <StatusPill tone="warning">{t("rating.taxes.list.overTwenty")}</StatusPill>
      )}
    </div>
  );
}

/** From / To: one date each, the tenant's format; an open end reads `No end` (P27). */
export function TaxDateCell(props: {
  value: string | null;
  openEnd?: boolean;
  timeZone: string;
  dateFormat: RegionalDateFormat;
}): ReactNode {
  const { t } = useTranslation();
  if (props.value === null) {
    return <span>{props.openEnd === true ? t("rating.taxes.list.noEnd") : DASH}</span>;
  }
  return <DateCell value={props.value} timeZone={props.timeZone} dateFormat={props.dateFormat} />;
}

/**
 * GL account: the code bold, the name small under it (P26). Unmapped renders
 * nothing (PO 2026-09-17: *"if GL code is not map then dont show it"*), and the
 * account's id is never shown (B14 rule 31).
 */
export function TaxGlCell(props: { row: TaxRow }): ReactNode {
  const code = props.row.gl_account_code ?? null;
  if (code === null) return null;
  return (
    <div className="flex flex-col">
      <span className="font-semibold">{code}</span>
      {props.row.gl_account_name !== null && props.row.gl_account_name !== undefined && (
        // P26 — *"Long GL account text wraps"*: one line, cut with an ellipsis
        // and whole on hover. Measured at 1440: unwrapped, a long name pushed
        // Premises and Status out of the visible table.
        <span
          className="block max-w-32 truncate text-sm text-neutral-700"
          title={props.row.gl_account_name}
        >
          {props.row.gl_account_name}
        </span>
      )}
    </div>
  );
}

/** Premises: how many it reaches, of how many the utility has (P25). */
export function TaxPremisesCell(props: { row: TaxListRow }): ReactNode {
  const { t } = useTranslation();
  const reached = props.row.premises_reached;
  const total = props.row.premises_total;
  if (reached === null || reached === undefined || total === null || total === undefined) {
    return <span>{DASH}</span>;
  }
  return <span>{t("rating.taxes.list.premisesOf", { reached, total })}</span>;
}

export function TaxStatusCell(props: { status: string }): ReactNode {
  const { t } = useTranslation();
  return (
    <StatusPill tone={taxListStatusTone(props.status)}>
      {t(`rating.status.${props.status}`, { defaultValue: props.status })}
    </StatusPill>
  );
}

// ── Above the table ─────────────────────────────────────────────────────────

/**
 * `N taxes charge over 20%.` with `Show them` (P24).
 *
 * ⚠ **THE COUNT IS THE SERVER'S, AND WITHOUT IT THERE IS NO BANNER.** The
 * drawing shows the SAME number over All (image 01), Active (02) and a search
 * that matches nothing (03), so it describes the utility's taxes, not the page.
 * A page is at most a few hundred rows of a list that may hold more (NFR-3), so
 * counting the rows on screen would print a confident wrong number on page two.
 * The round-2 contract serves no such count; this lane asked for one
 * (`over_20_count` on the list reply, and `f.over_20=1` for `Show them`) rather
 * than adding it to a back end it does not own. Until it lands this renders
 * nothing — the per-row pill still marks every such tax on the page.
 */
export function OverTwentyBanner(props: {
  count: number | null | undefined;
  showing: boolean;
  onShow: () => void;
  onShowAll: () => void;
}): ReactNode {
  const { t } = useTranslation();
  if (props.count === null || props.count === undefined || props.count < 1) return null;
  return (
    <WarningBox
      tone="soon"
      data-warning="over-20"
      sentence={
        <>
          <strong>{t("rating.taxes.list.overTwentyBanner", { count: props.count })}</strong>{" "}
          {props.showing ? (
            <InlineLink onClick={props.onShowAll}>{t("rating.taxes.list.showAll")}</InlineLink>
          ) : (
            <InlineLink onClick={props.onShow}>{t("rating.taxes.list.showThem")}</InlineLink>
          )}
        </>
      }
    />
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-165-BRC10 round 2 task 5 · DEF-RAT-9274
// generated: 2026-10-03 by the round-2 list lane
// checklist: A✔ B✔ C✔ D=n/a(no API half) E✔ F✔ G✔ H=deferred
// exceptions: E3 `over_20_count` / `f.over_20` are requested of the back end, not served — the banner renders nothing until they are
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
