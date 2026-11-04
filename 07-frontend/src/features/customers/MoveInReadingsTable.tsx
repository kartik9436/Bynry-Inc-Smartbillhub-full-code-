// ── Trace ──────────────────────────────────────────────
// Defects:  DEF-CUS-6362 — move-in step 3 drew TWO tables: the grouped
//           *Meters on this unit* inventory and a separate reading form. The
//           PO asked for one; this is it. DEF-CUS-6361 — the sentences around
//           them are gone (B14 rule 33).
// Ruling:   PO 2026-09-23, verbatim, on the mock-up of exactly these columns:
//           *"this is correct fix it"* (decision log, *"THE MOVE-IN READING
//           TABLE (ACC-05 STEP 3), APPROVED AS MOCKED"*).
// Rules:    BR-CUS-021 (initial reads commit through metering's event door) ·
//           BR-MET-026/027/058 (an estimate from the register's own history) ·
//           hard rule 3 (a quantity travels with its unit) · B14 rules 21
//           (Tailwind; this file is on route-b-migrated.txt), 33, 43
// Tests:    MoveInReadingsTable.dom.test.tsx · MoveInWizard.test.tsx
// Hosts:    MoveInWizard.tsx (step 3)
// ───────────────────────────────────────────────────────
//
// ⚠ **THE MOVE-IN READING BOX OPENS EMPTY, AND THAT REVERSES A PREFILL FOR THE
// MOVE-IN ONLY.** `useReadsDraft` seeds every box with the register's last
// reading — `OQ-394`'s ruling, which was asked about a MOVE-OUT (*"the figure
// you leave is the one that closes the account"*). On a move-in a prefilled box
// nobody touched records a reading nobody took. The PO approved the empty box
// on 2026-09-23 with the last reading beside it in its own column, so the wizard
// holds a plain `ReadsDraft` and only what the clerk typed reaches the payload.
// The move-out keeps its prefill; nothing here touches it.
//
// ⚠ **WHAT "1 kgal" UNDER "2530 kgal" WAS.** The old panel printed the last
// read's `consumption` under its position — `(current − prior) × multiplier`,
// the usage that one reading recorded — with no label. The approved columns do
// not carry it, so it is gone rather than labelled.

import { DateCell } from "@/components/DateCell";
import type { RegionalDateFormat } from "@/components/DateCell";
import type { EditableColumn } from "@/components/EditableTable";
import { CheckboxField, DatePickerField, TextField } from "@/components/FormModal";
import { formatQuantity } from "@/components/UnitCell";
import { serviceLabel } from "@/features/assets/assetsShared";
import type { Translator } from "@/features/tenancy/settingsShared";

import { READABLE_ASSET_GROUPS, withReadDraft } from "./moveReadsCapture";
import type { ReadsDraft } from "./moveReadsCapture";
import { groupsInOrder } from "./UnitAssetsPanel";
import type { UnitAssetRow, UnitAssets } from "./UnitAssetsPanel";

/** The register a move-in reading is keyed against when the payload names
 *  none — `metering.services` defaults an event read's channel to `total`. */
const DEFAULT_REGISTER = "total";

export interface MoveInReadingRow {
  asset: UnitAssetRow;
  /** A meter or sub-meter with a number: it takes a reading. Anything else —
   *  a behind-the-meter device, an unclassified row — is listed with no input
   *  (`READABLE_ASSET_GROUPS` argues the boundary). */
  readable: boolean;
}

/**
 * One row per installed asset, in the register's group order, with no group
 * headings — a group with nothing in it simply contributes no rows.
 */
export function moveInReadingRows(assets: UnitAssets | undefined): MoveInReadingRow[] {
  if (assets === undefined || !Array.isArray(assets.groups)) {
    return [];
  }
  return groupsInOrder(assets.groups).flatMap((group) =>
    group.assets.map((asset) => ({
      asset,
      readable:
        (READABLE_ASSET_GROUPS as readonly string[]).includes(group.category) &&
        asset.asset_no !== null &&
        asset.asset_no !== "",
    })),
  );
}

/** *"2,530 kgal"* — the last position, grouped, with its unit when the server
 *  sent one and bare when it did not (a made-up unit is worse). `null` = never
 *  read, which the cell draws as a dash and never as a zero. */
export function lastReadingText(asset: UnitAssetRow): string | null {
  const read = asset.last_read;
  if (read === null || read.current_value === null) {
    return null;
  }
  const grouped = formatQuantity(read.current_value);
  return read.unit === null || read.unit === "" ? grouped : `${grouped} ${read.unit}`;
}

/**
 * **THE READING COLUMNS, AS ONE BUILDER — `DEF-CUS-10051`.** Exported so the
 * move-out's services table (`MoveOutServicesTable`) draws its METERED group
 * with exactly these nine columns rather than a copy of them (B14 rule 43).
 * The move-in passes no `unlinkedServiceText` and keeps its dash.
 */
export interface ReadingColumnOptions {
  draft: ReadsDraft;
  onChange: (draft: ReadsDraft) => void;
  /** The date every Read date opens on (ISO), or `""`. */
  moveInDate: string;
  t: Translator;
  timeZone: string;
  dateFormat: RegionalDateFormat;
  idPrefix: string;
  readingLabel?: string;
  /** What the Service cell says for an asset linked to no service. Default `—`. */
  unlinkedServiceText?: string;
  /**
   * `DEF-BIL-10129` — `false` when the host prints the SERVER's estimate
   * answer for a ticked row (the move-out's `MoveOutEstimateNote`). The
   * Estimate cell's own *no history* hint is inferred from "never read", and
   * printed beside the server's answer it said one fact twice — or, before
   * the server matched by meter, contradicted it. Default `true` (move-in).
   */
  noHistoryHint?: boolean;
}

export function readingColumns(opts: ReadingColumnOptions): EditableColumn<MoveInReadingRow>[] {
  const { t, idPrefix } = opts;
  const draftRow = (asset: UnitAssetRow) =>
    opts.draft[asset.id] ?? { meterNo: asset.asset_no ?? "", value: "", estimate: false, readAt: "" };

  return [
    {
      key: "asset",
      label: t("customers.moveIn.reads.col.assetNo"),
      cell: ({ asset }) => (
        <span className="flex flex-wrap items-baseline gap-2" data-move-in-reading-asset={asset.asset_no ?? ""}>
          <span className="tabular-nums">{asset.asset_no ?? "—"}</span>
          {asset.qualifier === null || asset.qualifier === "" ? null : (
            <span className="font-mono text-xs uppercase tracking-tag text-neutral-700">
              {t(`customers.moveIn.reads.tag.${asset.qualifier}`, { defaultValue: asset.qualifier })}
            </span>
          )}
        </span>
      ),
    },
    {
      key: "type",
      label: t("customers.moveIn.reads.col.type"),
      cell: ({ asset }) => asset.type_name ?? asset.type ?? "—",
    },
    {
      key: "service",
      label: t("customers.moveIn.reads.col.service"),
      cell: ({ asset }) =>
        asset.service === null ? (opts.unlinkedServiceText ?? "—") : serviceLabel(asset.service, t),
    },
    {
      key: "register",
      label: t("customers.moveIn.reads.col.register"),
      cell: ({ asset, readable }) => {
        const channel = asset.last_read?.channel ?? (readable ? DEFAULT_REGISTER : null);
        return channel === null
          ? "—"
          : t(`customers.moveIn.reads.register.${channel}`, {
              defaultValue: t(`metering.reads.channel.${channel}`, { defaultValue: channel }),
            });
      },
    },
    {
      key: "lastReading",
      label: t("customers.moveIn.reads.col.lastReading"),
      numeric: true,
      cell: ({ asset }) => lastReadingText(asset) ?? "—",
    },
    {
      key: "lastReadOn",
      label: t("customers.moveIn.reads.col.lastReadOn"),
      cell: ({ asset }) =>
        asset.last_read === null || asset.last_read.read_at === null ? (
          "—"
        ) : (
          <DateCell value={asset.last_read.read_at} timeZone={opts.timeZone} dateFormat={opts.dateFormat} />
        ),
    },
    {
      key: "reading",
      label: opts.readingLabel ?? t("customers.moveIn.reads.col.reading"),
      cell: ({ asset, readable }) => {
        if (!readable) return null;
        const row = draftRow(asset);
        return (
          <TextField
            id={`${idPrefix}-read-${asset.id}`}
            // ⚠ **THE HIDDEN LABEL TAKES THE OVERRIDE TOO, AND FORGETTING IT IS
            // THE SUBTLE HALF.** The column heading and this label are the same
            // words for the same box; changing only the heading leaves a screen
            // reader announcing *Move-in reading* on a move-out, which is the
            // one version of this defect nobody looking at the screen can see.
            label={opts.readingLabel ?? t("customers.moveIn.reads.col.reading")}
            labelHidden
            numeric
            value={row.value}
            // A value and an estimate never travel together (the door refuses
            // the pair); ticking Estimate clears and locks the box.
            readOnly={row.estimate}
            onChange={(value) =>
              opts.onChange(withReadDraft(opts.draft, asset.id, row.meterNo, { value }))
            }
          />
        );
      },
    },
    {
      key: "readDate",
      label: t("customers.moveIn.reads.col.readDate"),
      cell: ({ asset, readable }) => {
        if (!readable) return null;
        const row = draftRow(asset);
        // Shows the move-in date and SENDS nothing until changed, so a later
        // change of the move-in date still carries every untouched row with it.
        return (
          <DatePickerField
            id={`${idPrefix}-read-date-${asset.id}`}
            label={t("customers.moveIn.reads.col.readDate")}
            labelHidden
            regional
            value={row.readAt === "" ? opts.moveInDate : row.readAt}
            dateFormat={opts.dateFormat}
            onChange={(readAt) =>
              opts.onChange(withReadDraft(opts.draft, asset.id, row.meterNo, { readAt }))
            }
          />
        );
      },
    },
    {
      key: "estimate",
      label: t("customers.moveIn.reads.col.estimate"),
      cell: ({ asset, readable }) => {
        if (!readable) return null;
        const row = draftRow(asset);
        return (
          <span className="flex flex-col gap-1">
            <CheckboxField
              id={`${idPrefix}-estimate-${asset.id}`}
              label={t("customers.moveIn.reads.col.estimate")}
              labelHidden
              checked={row.estimate}
              onChange={(estimate) =>
                opts.onChange(withReadDraft(opts.draft, asset.id, row.meterNo, { estimate }))
              }
            />
            {/* The one outcome knowable before the save: a register never read
                has no history to estimate from (`no_history`). Any other
                refusal comes back per meter on the done screen. */}
            {opts.noHistoryHint !== false && row.estimate && asset.last_read === null ? (
              <span className="text-sm text-warning-700" data-move-in-estimate="no-history">
                {t("customers.moveIn.reads.noHistory")}
              </span>
            ) : null}
          </span>
        );
      },
    },
  ];
}
