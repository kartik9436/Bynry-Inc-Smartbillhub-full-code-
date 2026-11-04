// ── Trace ──────────────────────────────────────────────
// Change:   REQ-03, the New Request redesign — six steps into four, approved by
//           the PO on 2026-09-29. Tasks 8, 9 and 10: the Services table array,
//           the Application-fees table array, and the Review's communication
//           card. Drawn in `05-prototype/new-request-four-steps-2026-09-29/`
//           (`03-service-1440.png`, `04-review-1440.png`), read AS IMAGES —
//           B14 rule 42, and the README in that folder is an index, not the
//           screen.
// Rules:    B14 rule 43 (a piece of UI is a COMPONENT; standalone code inside a
//           page is not reuse — the host page is 5,282 lines) · rule 44 (our UI
//           standard and the shared kit win over the drawing) · rule 20 (ONE
//           table type — every table here is the kit's `EditableTable`) ·
//           rule 21 (Tailwind utilities only; this file is on
//           `src/styles/route-b-migrated.txt`) · rule 31 (no database id is
//           ever a visible value) · rule 33 (a LABEL ≤ 3 words, a FACT ≤ 6,
//           RATIONALE zero words on screen) · rule 37 (a drawn figure is an
//           illustration) · CLAUDE.md hard rule 2 (money is the SERVER's —
//           nothing here multiplies, sums or rounds).
// Tests:    src/features/customers/serviceRequestTableArrays.dom.test.tsx
// Impacts:  src/features/customers/ServiceRequestCapturePage.tsx (steps 3 and 4)
// ───────────────────────────────────────────────────────
//
// ══════════════════════════════════════════════════════════════════════════
// WHY THREE COMPONENTS AND NOT THREE BLOCKS OF PAGE
// ══════════════════════════════════════════════════════════════════════════
// B14 rule 43, ratified 2026-09-20 after *"use it"* turned out to mean 120
// lines inline in a 4,186-line page, importable by nothing. The two table
// arrays this redesign asks for are the exact shape that rule names: two
// tables, one screen, and a read-only twin of each on the Review beside them.
// So they are declared once here and mounted four times over there.
//
// ⚠ **THEY ARE TWO WRAPPERS OVER ONE TABLE, NOT TWO TABLES.** B14 rule 20 says
// this product has one table type and `EditableTable` is it. Services and fees
// hold different rows and answer to different endpoints, so they are not one
// component with a mode switch — they are two thin callers of the kit, which
// is what keeps their borders, their ✕, their footer row and their empty state
// identical without either of them owning any of that markup.
import { useMemo } from "react";
import type { ReactNode } from "react";

import { Button } from "@/components/Button";
import { EditableTable } from "@/components/EditableTable";
import { CellSelect, CellText, TableArray } from "@/components/TableArray";
import { DatePickerField, SelectField } from "@/components/FormModal";
import type { RegionalDateFormat } from "@/components/DateCell";
import { DateCell } from "@/components/DateCell";
import type { Translator } from "@/features/tenancy/settingsShared";

import { MoneyOrAbsence, Dash } from "./serviceRequestShared";
import type { Money, ServiceRequestFeeLine } from "./serviceRequestEndpoints";

// ══════════════════════════════════════════════════════════════════════════
// 1 · THE SERVICES TABLE ARRAY — `SERVICE · REQUESTED START · STATUS · ✕`
// ══════════════════════════════════════════════════════════════════════════

/**
 * ⚠ **`new` / `already_on_site` IS A FACT THIS PRODUCT DOES NOT YET SERVE PER
 * SERVICE, AND THIS TYPE SAYS SO RATHER THAN GUESSING.**
 *
 * The drawing carries a `STATUS` column reading *New* on all three rows, and
 * the reason it is worth a column is real: a clerk should know a service is
 * already on the property before promising a date for it. But the only
 * per-service field the request payload has is `available` — *can this address
 * take this service* — which is a different question, and `evidence
 * .unit_is_served` is about the whole unit rather than one service.
 *
 * **What is knowable today is the negative half, and only that is derived:** a
 * request whose address matched NO premises has nothing on site by
 * construction, so every service on it is `new`. Where a premises DID match,
 * the per-service answer lives in the metering register and no seam serves it
 * here, so the value is `null` and the cell draws this screen's own absence
 * glyph. **`null` is never drawn as `New`** — that would be the screen
 * inventing a fact about somebody's property.
 */
export type ServiceOnSite = "new" | "already_on_site" | null;

/** One drawn row. `code` is `""` on a row a clerk has just added and not yet
 *  answered — the drawing's *adding a row IS adding a service*, which needs a
 *  row to exist before it has a service in it. */
export interface ServiceTableRow {
  code: string;
  /** `YYYY-MM-DD`, raw end to end, or `""` for *not given*. */
  requested_start: string;
  status: ServiceOnSite;
}

/**
 * **THE TWO DRAWN PANELS BECOME ONE TABLE (PO, 2026-09-29).**
 *
 * *Which services* (a chip multiselect plus an *Add a service…* box) and *When
 * each one is wanted* (a table of dates) were two controls describing one act.
 * They are one table now: the service is a chooser IN the row, so picking it
 * and dating it is a single act, and **adding a row IS adding a service**.
 *
 * ⚠ **THE CONNECTION DATE IS NOT IN THIS TABLE AND THAT IS SETTLED FROM THE
 * CODE.** `service_requests.requested_start` — commented *"Connection date"* —
 * is ONE per request; `ServiceRequestService.requested_start` is one per
 * service. Two different stored facts, so a column repeating the first down the
 * second's rows would invite a clerk to believe they could differ per row. The
 * caller draws the job's date beneath this table, once.
 *
 * ⚠ **A SERVICE IS OFFERED ONCE.** A code already taken by another row is not
 * in that row's options, so the table cannot produce two rows for one service —
 * which the server's unique key would refuse anyway, one round trip later.
 */
export function ServicesTableArray(props: {
  rows: readonly ServiceTableRow[];
  /** The tenant's ENABLED services, name and code, in the catalogue's order.
   *  ⚠ Never a hand-typed list (CLAUDE.md: the eleventh service fails
   *  silently when a screen types the ten out). */
  options: readonly { value: string; label: string }[];
  onChange: (rows: ServiceTableRow[]) => void;
  t: Translator;
  dateFormat: RegionalDateFormat;
  /** `data-collection` — how a test or a walkthrough finds this table. */
  collection?: string;
}) {
  const t = props.t;
  const rows = props.rows;
  const taken = useMemo(
    () => new Set(rows.map((row) => row.code).filter((code) => code !== "")),
    [rows],
  );

  function write(index: number, patch: Partial<ServiceTableRow>): void {
    props.onChange(rows.map((row, at) => (at === index ? { ...row, ...patch } : row)));
  }

  const columns = [
    {
      key: "service",
      label: t("customers.serviceRequest.services.col.service"),
      cell: (row: ServiceTableRow, index: number) => (
        <SelectField
          id={`service_row_${index}`}
          // ⚠ **ANNOUNCED, NOT DRAWN — THE COLUMN HEADER IS THE LABEL.**
          // `tableTypes.ts`: *"A TABLE CELL HOLDS A VALUE, AND A CONTROL HOLDS
          // A LABEL"*; printing `Service` over every box in a column already
          // headed SERVICE is the same word twice.
          label={t("customers.serviceRequest.services.col.service")}
          labelHidden
          value={row.code}
          placeholder={t("customers.serviceRequest.services.pickAService")}
          onChange={(code) => write(index, { code })}
          options={props.options.filter(
            (option) => option.value === row.code || !taken.has(option.value),
          )}
        />
      ),
    },
    {
      key: "start",
      label: t("customers.serviceRequest.services.col.requestedStart"),
      cell: (row: ServiceTableRow, index: number) => (
        <DatePickerField
          id={`service_start_row_${index}`}
          label={t("customers.serviceRequest.services.col.requestedStart")}
          labelHidden
          value={row.requested_start}
          onChange={(value) => write(index, { requested_start: value })}
          dateFormat={props.dateFormat}
        />
      ),
    },
    {
      key: "status",
      label: t("customers.serviceRequest.services.col.status"),
      cell: (row: ServiceTableRow) =>
        row.status === null ? (
          <Dash />
        ) : (
          <span data-service-status={row.status}>
            {t(`customers.serviceRequest.services.status.${row.status}`)}
          </span>
        ),
    },
  ];

  return (
    <EditableTable<ServiceTableRow>
      data-collection={props.collection ?? "request-services"}
      // No caption bar: the panel this sits in is already headed *Services*.
      caption=""
      columns={columns}
      rows={[...rows]}
      // ⚠ **THE INDEX AND NOT THE CODE.** A freshly added row has no code and a
      // second one would collide with it; React would then reuse one row's
      // inputs for the other. The index is stable for as long as the row is.
      rowKey={(_row, index) => `service-${index}`}
      emptyText={t("customers.serviceRequest.services.noneAsked")}
      numbered={false}
      reorderable={false}
      onChange={(next) => props.onChange(next)}
      onRemove={(_row, index) => props.onChange(rows.filter((_r, at) => at !== index))}
      addRow={
        <Button
          variant="secondary"
          size="sm"
          data-add-service=""
          disabled={props.options.every((option) => taken.has(option.value))}
          onClick={() => props.onChange([...rows, { code: "", requested_start: "", status: null }])}
        >
          {t("customers.serviceRequest.services.addService")}
        </Button>
      }
      labels={{
        remove: t("customers.serviceRequest.services.removeService"),
        position: t("customers.serviceRequest.services.col.service"),
      }}
    />
  );
}

/**
 * **THE REVIEW'S TWIN — the same three columns, read-only, and NO connection
 * date column.**
 *
 * ⚠ **THIS IS THE FIX FOR `DEF-CUS-7840`.** The review drew `SERVICE ·
 * REQUESTED START · CONNECTION DATE` and printed the request-level date on
 * EVERY row, which made a per-request fact look per-service. It is printed
 * once, by the caller, beneath this table.
 */
export function ReviewServicesTable(props: {
  rows: readonly ServiceTableRow[];
  t: Translator;
  timeZone: string;
  dateFormat: RegionalDateFormat;
  collection?: string;
}) {
  const t = props.t;
  if (props.rows.length === 0) {
    return (
      <p className="text-sm text-neutral-700" data-services-table="none">
        {t("customers.serviceRequest.services.noneAsked")}
      </p>
    );
  }
  return (
    <EditableTable<ServiceTableRow>
      data-collection={props.collection ?? "review-services"}
      caption=""
      readOnly
      numbered={false}
      reorderable={false}
      rows={[...props.rows]}
      rowKey={(row, index) => `${row.code}-${index}`}
      emptyText={t("customers.serviceRequest.services.noneAsked")}
      columns={[
        {
          key: "service",
          label: t("customers.serviceRequest.services.col.service"),
          cell: (row: ServiceTableRow) => (
            <span data-service-row={row.code}>
              {t(`rating.service.${row.code}`, { defaultValue: row.code })}
            </span>
          ),
        },
        {
          key: "start",
          label: t("customers.serviceRequest.services.col.requestedStart"),
          cell: (row: ServiceTableRow) =>
            row.requested_start === "" ? (
              <Dash />
            ) : (
              <DateCell
                value={row.requested_start}
                timeZone={props.timeZone}
                dateFormat={props.dateFormat}
              />
            ),
        },
        {
          key: "status",
          label: t("customers.serviceRequest.services.col.status"),
          cell: (row: ServiceTableRow) =>
            row.status === null ? (
              <Dash />
            ) : (
              <span data-service-status={row.status}>
                {t(`customers.serviceRequest.services.status.${row.status}`)}
              </span>
            ),
        },
      ]}
    />
  );
}

// ══════════════════════════════════════════════════════════════════════════
// 2 · THE APPLICATION-FEES TABLE ARRAY
//     `FEE · CHARGED PER · QTY · UNIT PRICE · AMOUNT · ✕`, a Total, `+ Fee`
// ══════════════════════════════════════════════════════════════════════════

/**
 * ⚠⚠ **EVERY FIGURE IN THIS TABLE IS THE SERVER'S AND NOTHING HERE
 * MULTIPLIES — CLAUDE.md hard rule 2.**
 *
 * `AMOUNT` is `service_request_fees.amount`, `NUMERIC(18,4)`, priced by
 * `add_fee_line` from the charge code at the moment of the add. The `Total` is
 * `fees.quoted` — the server's own Decimal sum of the unwaived lines — and NOT
 * a sum of the cells on screen. `DEF-088` and `DEF-127` are what browser-side
 * money arithmetic has already cost this product.
 *
 * **Both are rendered through `MoneyOrAbsence`, which draws the stored 4-dp
 * amount through the one formatting path WITH ITS `CHAR(3)` and carries the
 * server's own 2-dp `display` beside it in `data-display`.** So the currency is
 * always printed — `DEF-CUS-7806` is a bare `535.00` on another screen — and a
 * test can prove the figure on screen is the figure the server sent without
 * re-implementing the rounding rule a third time.
 *
 * ⚠ **`QTY` IS DRAWN AS A VALUE AND NOT AS AN INPUT, AND THAT IS THIS FILE'S
 * ESTABLISHED POSTURE RATHER THAN A SHORTFALL.** The drawing draws a box; there
 * is no endpoint that sets a stored line's quantity, and the capture page
 * already refuses to draw a control that cannot save (*"A control that cannot
 * save is not drawn as an input"* — the SSN block). An input a clerk can type
 * into whose number never reaches the server, over an AMOUNT that does not
 * move, is worse than a printed figure: it is hard-won law 2 with money in it.
 * **The seam is the `qty` COLUMN itself:** the day a quantity endpoint lands,
 * that one cell becomes the drawn box and nothing else on this screen moves.
 * No prop is declared for it now — an optional prop nothing passes is the dead
 * UI law 2 is about, one layer up.
 *
 * ⚠ **`Waive` IS NOT A COLUMN HERE.** The drawing has six columns and a waive
 * is not one of them; waiving is the request's own act once it is open
 * (`BR-CUS-090`), and the read-only `FeeLinesTable` still draws a waived line
 * with its reason wherever one exists.
 */
export function ApplicationFeesTableArray(props: {
  fees: { lines: readonly ServiceRequestFeeLine[]; quoted: Money };
  /** What a clerk may raise — code and name, already filtered by the caller to
   *  the one-time, priceable codes. */
  codes: readonly { value: string; label: string }[];
  t: Translator;
  busy: boolean;
  /** A row's chooser answered: raise that fee. */
  onPick: (line: ServiceRequestFeeLine | null, code: string) => void;
  onRemove: (line: ServiceRequestFeeLine) => void;
  /** Why NO line may be removed right now — a request reopened for correction
   *  after it was submitted. Per-line reasons still win. */
  removeBlocked?: string;
  /** A row a clerk has added and not yet answered. `null` when there is none. */
  pendingRow: boolean;
  onAddRow: () => void;
  onDropPendingRow: () => void;
  collection?: string;
}) {
  const t = props.t;
  /** The stored lines, plus at most one unanswered row. The unanswered row is
   *  `null` in the row list and every cell branches on it, which is why the row
   *  type is nullable rather than a half-built fee line nobody could tell from
   *  a real one. */
  const rows: (ServiceRequestFeeLine | null)[] = props.pendingRow
    ? [...props.fees.lines, null]
    : [...props.fees.lines];

  const chosen = new Set(
    props.fees.lines.map((line) => line.charge_code ?? "").filter((code) => code !== ""),
  );

  const columns = [
    {
      key: "fee",
      label: t("customers.serviceRequest.fees.col.fee"),
      cell: (line: ServiceRequestFeeLine | null, index: number) =>
        line === null ? (
          <SelectField
            id={`fee_row_${index}`}
            label={t("customers.serviceRequest.fees.col.fee")}
            labelHidden
            value=""
            placeholder={t("customers.serviceRequest.fees.chooseAFee")}
            disabled={props.busy}
            onChange={(code) => {
              if (code !== "") props.onPick(null, code);
            }}
            options={props.codes.filter((option) => !chosen.has(option.value))}
          />
        ) : (
          <span data-fee-line-name={line.charge_code ?? ""}>
            {line.description ?? line.charge_code ?? ""}
          </span>
        ),
    },
    {
      key: "basis",
      label: t("customers.serviceRequest.fees.col.chargedPer"),
      cell: (line: ServiceRequestFeeLine | null) =>
        line === null ? (
          <Dash />
        ) : (
          // The basis comes FROM the fee and is never typed — the drawing says
          // so and `add_fee_line` is where it is set.
          <span data-fee-line-basis={line.basis ?? ""}>
            {line.basis === null || line.basis.trim() === "" ? (
              <Dash />
            ) : (
              t(`customers.serviceRequest.fees.basis.${line.basis.replace(/\s+/g, "_")}`, {
                defaultValue: line.basis,
              })
            )}
          </span>
        ),
    },
    {
      key: "qty",
      label: t("customers.serviceRequest.fees.col.qty"),
      numeric: true,
      cell: (line: ServiceRequestFeeLine | null) =>
        line === null ? <Dash /> : <span data-fee-line-qty="">{quantityText(line.quantity)}</span>,
    },
    {
      key: "unit",
      label: t("customers.serviceRequest.fees.col.unitPrice"),
      numeric: true,
      cell: (line: ServiceRequestFeeLine | null) =>
        line === null ? <Dash /> : <MoneyOrAbsence money={line.unit_amount} t={t} />,
    },
    {
      key: "amount",
      label: t("customers.serviceRequest.fees.col.amount"),
      numeric: true,
      cell: (line: ServiceRequestFeeLine | null) =>
        line === null ? (
          <Dash />
        ) : (
          // `data-fee-line-amount` carries the STORED 4-dp figure and
          // `MoneyOrAbsence` carries the server's 2-dp `display`; a test reads
          // both and neither is computed here.
          <span data-fee-line-amount={line.amount.amount}>
            <MoneyOrAbsence money={line.amount} t={t} />
          </span>
        ),
    },
  ];

  return (
    <EditableTable<ServiceRequestFeeLine | null>
      data-collection={props.collection ?? "application-fees"}
      caption=""
      columns={columns}
      rows={rows}
      rowKey={(line, index) => line?.id ?? `pending-${index}`}
      emptyText={t("customers.serviceRequest.fees.line.none")}
      numbered={false}
      reorderable={false}
      onChange={() => undefined}
      onRemove={(line) => {
        if (line === null) props.onDropPendingRow();
        else props.onRemove(line);
      }}
      rowRemoveBlocked={(line) =>
        line === null
          ? undefined
          : line.waived
            ? t("customers.serviceRequest.feeRemoveWaived")
            : line.settled_at !== null
              ? t("customers.serviceRequest.feeRemovePaid")
              : props.removeBlocked
      }
      // ⚠ **THE FOOTER IS HANDED A FIGURE, NEVER A SUM OF THE CELLS.** The kit
      // adds nothing up either — see `footerCells` in `EditableTable`.
      footerCells={
        props.fees.lines.length === 0
          ? undefined
          : {
              fee: t("customers.serviceRequest.fees.total"),
              amount: (
                <span data-fee-total={props.fees.quoted.amount}>
                  <MoneyOrAbsence money={props.fees.quoted} t={t} />
                </span>
              ),
            }
      }
      addRow={
        <Button
          variant="secondary"
          size="sm"
          data-add-fee=""
          disabled={props.busy || props.pendingRow || props.codes.length === 0}
          onClick={props.onAddRow}
        >
          {t("customers.serviceRequest.fees.addFeeRow")}
        </Button>
      }
      labels={{
        remove: t("customers.serviceRequest.fees.remove"),
        position: t("customers.serviceRequest.fees.col.fee"),
      }}
    />
  );
}

/** `1.0000` → `1`. The stored quantity is `NUMERIC`, and a fee taken once reads
 *  `1` on the drawing rather than `1.0000`. Trailing zeros only — no rounding,
 *  because rounding a stored figure on a screen is hard rule 2's business. */
export function quantityText(quantity: string): string {
  if (!/^-?\d+\.\d+$/.test(quantity)) return quantity;
  return quantity.replace(/0+$/, "").replace(/\.$/, "");
}

// ══════════════════════════════════════════════════════════════════════════
// 3 · WHAT THE CUSTOMER IS TOLD — `MESSAGE · CHANNEL · TO · WHEN`
// ══════════════════════════════════════════════════════════════════════════

/** One drawn row. Everything is resolved by the CALLER against the catalogue
 *  before it gets here — `BR-SHL-020` r2: nothing English crosses the wire, so
 *  the server sends keys and this component is handed sentences. The ADDRESS is
 *  data and travels as it is. */
export interface CustomerMessageRow {
  /** A stable handle for the row. ⚠ Never rendered (B14 rule 31). */
  key: string;
  /** *Request received* — resolved from the server's occasion key. */
  message: string;
  /** *Email* — resolved from the server's channel key. */
  channel: string;
  /** The address itself. Data, not a key. */
  to: string;
  /** *On submit*, or — where the message will NOT go — the reason it will not.
   *  ⚠ **A WITHHELD MESSAGE GETS ITS OWN ROW SAYING SO.** An absent row and a
   *  withheld one look identical on screen, and telling them apart is the whole
   *  point of drawing this card at all. */
  when: string;
  /** `true` where this row is a message that will NOT be sent. It changes no
   *  words — `when` already carries them — and exists so a test and a
   *  walkthrough can find the row without matching English. */
  withheld?: boolean;
}

/** `DEF-CUS-10042` — one message a CLERK added. Codes travel; the screen shows
 *  names (B14 rule 31). `fired` rows are history and cannot be edited. */
export interface ExtraMessageRow {
  template_code: string;
  channel: "email" | "text" | string;
  to_address: string;
  send_when: "on_submit" | "on_approve" | "on_refuse" | string;
  fired?: boolean;
}

export const EXTRA_SEND_WHEN = ["on_submit", "on_approve", "on_refuse"] as const;
export const EXTRA_CHANNELS = ["email", "text"] as const;

type MessageLine =
  | { kind: "auto"; row: CustomerMessageRow }
  | { kind: "extra"; index: number; row: ExtraMessageRow };

/**
 * **THE NEW CAPABILITY IN THIS REDESIGN (PO, 2026-09-29):** *"on review you
 * should display 1 card for communcaition to cusomer - in table format step
 * 4"* — and since `DEF-CUS-10042` (PO 2026-10-11) **built on the kit's
 * `TableArray` with an *Add a message* row**: *"use table array componnet and
 * allow user to add more communcation to user"*.
 *
 * The automatic rows are read-only and cannot be removed (*Sent
 * automatically.*); the clerk's added rows pick a message, a channel, an
 * address and a moment. Without `extra` the card is the read-back it was.
 *
 * ⚠ **A STATED ABSENCE IS A FIRST-CLASS ANSWER AND IS NEVER FILLED WITH ROWS.**
 * `absence` is the server's sentence, already resolved; when it is present NO
 * table is drawn, because inventing plausible rows would tell a clerk somebody
 * is about to be written to when nobody is.
 */
export function CustomerMessagesCard(props: {
  rows: readonly CustomerMessageRow[];
  /** The server's own stated absence, resolved. `null` where it answered. */
  absence: string | null;
  t: Translator;
  collection?: string;
  /** The heading the TableArray draws. */
  title?: string;
  /** `DEF-CUS-10042` — the clerk's added messages and how to change them. */
  extra?: {
    rows: readonly ExtraMessageRow[];
    templates: readonly { code: string; name: string }[];
    /** Where a new row goes by default — the applicant's email. */
    defaultAddress: string;
    onChange: (rows: ExtraMessageRow[]) => void;
  };
}) {
  const t = props.t;
  const title = props.title ?? t("customers.serviceRequest.messages.card");
  if (props.absence !== null) {
    return (
      <div>
        <h3>{title}</h3>
        <p className="text-sm text-neutral-700" data-messages-card="absent">
          {props.absence}
        </p>
      </div>
    );
  }
  const extra = props.extra;
  if (props.rows.length === 0 && extra === undefined) {
    return (
      <div>
        <h3>{title}</h3>
        <p className="text-sm text-neutral-700" data-messages-card="none">
          {t("customers.serviceRequest.messages.noneAtAll")}
        </p>
      </div>
    );
  }
  const lines: MessageLine[] = [
    ...props.rows.map((row): MessageLine => ({ kind: "auto", row })),
    ...(extra?.rows ?? []).map((row, index): MessageLine => ({ kind: "extra", index, row })),
  ];
  const templateName = (code: string) => extra?.templates.find((one) => one.code === code)?.name ?? code;
  const writeExtra = (index: number, patch: Partial<ExtraMessageRow>) =>
    extra?.onChange(extra.rows.map((row, at) => (at === index ? { ...row, ...patch } : row)));
  const locked = (line: MessageLine) => line.kind === "auto" || line.row.fired === true;

  const columns = [
    {
      key: "message",
      label: t("customers.serviceRequest.messages.col.message"),
      cell: (line: MessageLine) =>
        line.kind === "auto" ? (
          <span data-message-row={line.row.key} data-message-withheld={line.row.withheld === true ? "" : undefined}>
            {line.row.message}
          </span>
        ) : line.row.fired === true ? (
          <span data-extra-message={line.index}>{templateName(line.row.template_code)}</span>
        ) : (
          <CellSelect
            name={`extra_template_${line.index}`}
            fit
            label={t("customers.serviceRequest.messages.col.message")}
            value={line.row.template_code}
            placeholder={t("customers.serviceRequest.extra.pickTemplate")}
            options={(extra?.templates ?? []).map((one) => ({ value: one.code, label: one.name }))}
            onChange={(template_code) => writeExtra(line.index, { template_code })}
          />
        ),
    },
    {
      key: "channel",
      label: t("customers.serviceRequest.messages.col.channel"),
      cell: (line: MessageLine) =>
        line.kind === "auto" ? (
          renderOrDash(line.row.channel)
        ) : locked(line) ? (
          <span>{t(`customers.serviceRequest.extra.channel.${line.row.channel}`)}</span>
        ) : (
          <CellSelect
            name={`extra_channel_${line.index}`}
            fit
            label={t("customers.serviceRequest.messages.col.channel")}
            value={line.row.channel}
            placeholder={t("customers.serviceRequest.messages.col.channel")}
            options={EXTRA_CHANNELS.map((one) => ({ value: one, label: t(`customers.serviceRequest.extra.channel.${one}`) }))}
            onChange={(channel) => writeExtra(line.index, { channel })}
          />
        ),
    },
    {
      key: "to",
      label: t("customers.serviceRequest.messages.col.to"),
      cell: (line: MessageLine) =>
        line.kind === "auto" ? (
          renderOrDash(line.row.to)
        ) : locked(line) ? (
          <span>{line.row.to_address}</span>
        ) : (
          <CellText
            name={`extra_to_${line.index}`}
            label={t("customers.serviceRequest.messages.col.to")}
            value={line.row.to_address}
            onChange={(to_address) => writeExtra(line.index, { to_address })}
          />
        ),
    },
    {
      key: "when",
      label: t("customers.serviceRequest.messages.col.when"),
      cell: (line: MessageLine) =>
        line.kind === "auto" ? (
          renderOrDash(line.row.when)
        ) : locked(line) ? (
          <span>{t(`customers.serviceRequest.extra.when.${line.row.send_when}`)}</span>
        ) : (
          <CellSelect
            name={`extra_when_${line.index}`}
            fit
            label={t("customers.serviceRequest.messages.col.when")}
            value={line.row.send_when}
            placeholder={t("customers.serviceRequest.messages.col.when")}
            options={EXTRA_SEND_WHEN.map((one) => ({ value: one, label: t(`customers.serviceRequest.extra.when.${one}`) }))}
            onChange={(send_when) => writeExtra(line.index, { send_when })}
          />
        ),
    },
  ];
  const common = {
    title,
    collection: props.collection ?? "review-messages",
    columns,
    rows: lines,
    rowKey: (line: MessageLine) => (line.kind === "auto" ? line.row.key : `extra-${line.index}`),
    emptyText: t("customers.serviceRequest.messages.noneAtAll"),
    numbered: false,
  };
  return (
    <div data-messages-card="rows">
      {extra === undefined ? (
        <TableArray<MessageLine> {...common} readOnly />
      ) : (
        <TableArray<MessageLine>
          {...common}
          removeLabel={t("customers.serviceRequest.extra.remove")}
          rowRemoveBlocked={(line) =>
            line.kind === "auto"
              ? t("customers.serviceRequest.extra.automatic")
              : line.row.fired === true
                ? t("customers.serviceRequest.extra.alreadyQueued")
                : undefined
          }
          onChange={(next) =>
            extra.onChange(
              next.filter((line): line is Extract<MessageLine, { kind: "extra" }> => line.kind === "extra").map((line) => line.row),
            )
          }
          actions={[
            {
              key: "add-message",
              label: t("customers.serviceRequest.extra.add"),
              onClick: () =>
                extra.onChange([
                  ...extra.rows,
                  { template_code: "", channel: "email", to_address: extra.defaultAddress, send_when: "on_submit" },
                ]),
              blockedReason: extra.templates.length === 0 ? t("customers.serviceRequest.extra.noTemplates") : undefined,
              showReason: true,
            },
          ]}
        />
      )}
    </div>
  );
}

function renderOrDash(value: string): ReactNode {
  return value.trim() === "" ? <Dash /> : <span>{value}</span>;
}
