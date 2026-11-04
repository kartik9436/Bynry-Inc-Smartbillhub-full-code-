// ── Trace ──────────────────────────────────────────────
// Change:   CR-171-BRC10 P2.13 — the move-in's own modals: *Change move-in
//           date*, *Enter opening read*, *Cancel move-in…* (with what it
//           reverses, J6), *Discard draft…*, *Add a work order* (images 10,
//           12–14). Print is the browser's (image 16) and has no modal.
// Defect:   DEF-CUS-10167 — *Enter opening read* takes a READ DATE (required,
//           opening on the move-in date, never after today, never before the
//           meter's last reading) and Fetch, through the shared
//           `MeterReadingEntry` (PO 2026-10-17: *"use same code components"*).
// Rules:    B14 rule 6 (Cancel and Discard are the danger tier) · rule 33 ·
//           BR-SHL-025 (a commit the server refuses is DISABLED with its reason)
// Doors:    §9.FLOW — `POST /moves/{ref}/move-in-date` · `/opening-reads` ·
//           `GET /cancel-preview` + `POST /cancel` · `/work-orders`; a draft is
//           discarded through the wizard park's own door.
// ⚠ OQ-CUS-12790 WAS RULED (a) ON 2026-10-05 (decision log, 95705dfb8): a
//   cancelled move-in releases a held deposit and refunds everything as ONE
//   refund (e.g. $175.00), Finance approving it as usual. Until the server lane
//   builds it, the preview still refuses with the question. Nothing here is
//   hard-coded: the commit is held only while the PREVIEW says `allowed: false`
//   (its own refusal sentence shown), and the refund line is listed whenever the
//   preview serves a non-zero amount — so the hold lifts by itself the day the
//   server stops naming the question.
// ───────────────────────────────────────────────────────
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { z } from "zod";

import { api, formErrorEnvelope, isApiError } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { ConsequenceBox } from "@/components/ConsequenceBox";
import { DatePickerField, FormModal } from "@/components/FormModal";
import type { FormSubmitOutcome } from "@/components/FormModal";
import { todayInZone } from "@/components/DateCell";
import { formatMoney } from "@/components/MoneyCell";
import { LoadingSkeleton } from "@/components/StateFrame";
import { FieldVisitOrders, emptyFieldVisit, fieldVisitPayload } from "@/features/work/FieldVisitOrders";
import type { FieldVisitValue } from "@/features/work/FieldVisitOrders";
import { MeterReadingEntry, READ_DATE_PROBLEM_KEY, readDateProblem } from "@/features/metering/MeterReadingEntry";

import { discardWizardPark } from "../wizardParkEndpoints";
import {
  addMoveWorkOrders,
  cancelMoveIn,
  changeMoveInDate,
  getCancelPreview,
  getUnitMoveInMeters,
  postOpeningReads,
} from "./moveDetailEndpoints";
import type { UnitMeterRow } from "./moveDetailEndpoints";
import type { Regional } from "./moveDetailParts";

export type MoveModal = "changeDate" | "enterOpeningRead" | "cancel" | "discardDraft" | "addWorkOrder";

async function attempt(work: () => Promise<unknown>, done: () => void): Promise<FormSubmitOutcome> {
  try {
    await work();
    done();
    return { ok: true };
  } catch (error) {
    if (isApiError(error)) return { ok: false, error: formErrorEnvelope(error) };
    return { ok: false, error: { code: "", message_key: "api.error.unexpected" } };
  }
}

function Effect(props: { title: string; body?: string | null; name: string }) {
  const { t } = useTranslation();
  return (
    <ConsequenceBox
      tone="publish"
      tag={t("customers.moveDetail.effect")}
      title={props.title}
      body={props.body ?? null}
      data-consequence={props.name}
    />
  );
}

/** `Account AC-… closes 10/09/2026. Refund $175.00 queued. …` — J6's lines,
 *  each from the preview, never derived here. */
export function cancelLines(
  preview: Awaited<ReturnType<typeof getCancelPreview>>,
  t: (key: string, options?: Record<string, unknown>) => string,
): string[] {
  const r = preview.reverses;
  if ("job" in r) return [t("customers.moveDetail.cancel.job")];
  const lines = [t("customers.moveDetail.cancel.account", { account: r.account.account_no })];
  if (r.refund.amount !== null && Number(r.refund.amount) !== 0) {
    lines.push(
      t("customers.moveDetail.cancel.refund", {
        amount: formatMoney(r.refund.amount, r.refund.currency ?? "USD"),
      }),
    );
  }
  // `DEF-CUS-9789` — money not yet cleared is called off (never refunded).
  for (const paid of r.called_off ?? []) {
    lines.push(
      t("customers.moveDetail.cancel.calledOff", {
        payment: paid.payment_no ?? "",
        amount: formatMoney(paid.amount, paid.currency ?? "USD"),
      }),
    );
  }
  if (r.work_orders.length > 0) {
    lines.push(t("customers.moveDetail.cancel.workOrders", { orders: r.work_orders.join(", ") }));
  }
  lines.push(t("customers.moveDetail.cancel.unit"));
  return lines;
}

/** One register's opening read, as the modal holds it. */
interface OpeningRead {
  value: string;
  readDate: string;
  /** The clerk set the date; until then it follows the move-in date. */
  dateTouched: boolean;
  fetched: boolean;
}

/** Every READ meter on the unit by number — its unit and last reading. */
function metersByNumber(rows: readonly UnitMeterRow[]): Map<string, UnitMeterRow> {
  const out = new Map<string, UnitMeterRow>();
  const walk = (list: readonly UnitMeterRow[]) => {
    for (const row of list) {
      out.set(row.asset_no, row);
      walk(row.children ?? []);
    }
  };
  walk(rows);
  return out;
}

/**
 * *Enter opening read* — one row per unread register through the shared
 * `MeterReadingEntry`: the reading, its READ DATE and Fetch (`DEF-CUS-10167`).
 *
 * ⚠ **A ROW IS OPTIONAL; ITS DATE IS NOT.** The modal has always taken any of
 * the unread registers (a clerk may have one reading of three), so only a row
 * with a value posts — and a posted row carries a lawful date, the same
 * bounds as the wizard's step 1 and the server's `_refuse_bad_read_dates`.
 * The last reading (the lower bound) and the unit come from the unit's own
 * `move-in-meters` read; where it cannot be read the server still refuses a
 * date before the last reading, by row. No Estimate: an opening read is never
 * estimated (decision log 2026-10-17, *"estimates never on opening readings"*).
 */
function EnterOpeningReadModal(props: {
  moveNo: string;
  unreadRegisters: readonly string[];
  unitId: string | null;
  moveInDate: string;
  regional: Regional;
  client: ApiClient;
  onClose: () => void;
  done: () => void;
}) {
  const { t } = useTranslation();
  const [rows, setRows] = useState<Record<string, OpeningRead>>({});
  const meters = useQuery({
    queryKey: ["move-detail-opening-read-meters", props.unitId],
    enabled: props.unitId !== null && props.unitId !== "",
    queryFn: () => getUnitMoveInMeters(props.unitId ?? "", props.client),
    retry: false,
  });
  const known = metersByNumber([
    ...(meters.data?.services ?? []).flatMap((service) => service.meters ?? []),
    ...(meters.data?.unplaced ?? []),
  ]);
  const today = todayInZone(props.regional.timeZone);
  const rowOf = (meter: string): OpeningRead =>
    rows[meter] ?? { value: "", readDate: "", dateTouched: false, fetched: false };
  const shownDate = (row: OpeningRead) => (row.dateTouched || row.fetched ? row.readDate : props.moveInDate);
  const idOf = (meter: string) => `read-${meter}`;

  const shape: Record<string, z.ZodTypeAny> = {};
  const values: Record<string, string> = {};
  const typed: { meter_no: string; value: string; read_at: string }[] = [];
  for (const meter of props.unreadRegisters) {
    const row = rowOf(meter);
    if (row.value.trim() === "") continue;
    const minDate = known.get(meter)?.last_read?.read_at ?? null;
    shape[`${idOf(meter)}-date`] = z.string().superRefine((day, ctx) => {
      const problem = readDateProblem(day, { minDate, maxDate: today });
      if (problem !== null) ctx.addIssue({ code: z.ZodIssueCode.custom, message: t(READ_DATE_PROBLEM_KEY[problem]) });
    });
    values[`${idOf(meter)}-date`] = shownDate(row);
    typed.push({ meter_no: meter, value: row.value.trim(), read_at: shownDate(row) });
  }

  return (
    <FormModal
      title={t("customers.moveDetail.openingRead.title")}
      schema={z.object(shape)}
      values={values}
      onClose={props.onClose}
      submitLabel={t("customers.moveDetail.openingRead.submit")}
      commitBlocked={typed.length === 0 ? t("customers.moveDetail.openingRead.none") : undefined}
      onSubmit={() => attempt(() => postOpeningReads(props.moveNo, typed, props.client), props.done)}
    >
      <Effect title={t("customers.moveDetail.openingRead.effect")} name="move-opening-read" />
      <div className="mt-4 flex flex-col gap-3">
        {props.unreadRegisters.map((meter) => {
          const row = rowOf(meter);
          const facts = known.get(meter);
          return (
            <MeterReadingEntry
              key={meter}
              meterNo={meter}
              idPrefix={idOf(meter)}
              readingLabel={meter}
              unit={facts?.unit ?? facts?.last_read?.unit ?? null}
              lastReading={
                facts?.last_read ? { value: facts.last_read.value, readAt: facts.last_read.read_at } : null
              }
              value={row.value}
              readDate={shownDate(row)}
              fetched={row.fetched}
              defaultReadDate={props.moveInDate}
              maxDate={today}
              showFetch
              showLastReading
              client={props.client}
              t={t}
              timeZone={props.regional.timeZone}
              dateFormat={props.regional.dateFormat}
              onChange={(next) =>
                setRows((was) => ({
                  ...was,
                  [meter]: {
                    value: next.value,
                    readDate: next.readDate,
                    fetched: next.fetched,
                    dateTouched: next.fetched ? false : row.dateTouched || next.readDate !== shownDate(row),
                  },
                }))
              }
            />
          );
        })}
      </div>
    </FormModal>
  );
}

export function MoveActionModal(props: {
  open: MoveModal;
  moveNo: string;
  parkId: string | null;
  /** Registers still waiting for an opening read (Enter opening read). */
  unreadRegisters: readonly string[];
  /** DEF-CUS-10167 — the unit, for each meter's unit and last reading. */
  unitId?: string | null;
  /** DEF-CUS-10167 — the date every Read date opens on (the move-in date). */
  moveInDate?: string | null;
  regional: Regional;
  onClose: () => void;
  onDone: (modal: MoveModal) => void;
  client?: ApiClient;
}) {
  const { t } = useTranslation();
  const client = props.client ?? api;
  const done = () => props.onDone(props.open);
  const [date, setDate] = useState("");
  const [visit, setVisit] = useState<FieldVisitValue>(emptyFieldVisit);
  const preview = useQuery({
    queryKey: ["move-detail-cancel-preview", props.moveNo],
    enabled: props.open === "cancel",
    queryFn: () => getCancelPreview(props.moveNo, client),
    retry: false,
  });

  if (props.open === "changeDate") {
    return (
      <FormModal
        title={t("customers.moveDetail.changeDate.title")}
        schema={z.object({ date: z.string().min(1) })}
        values={{ date }}
        onClose={props.onClose}
        submitLabel={t("customers.moveDetail.changeDate.submit")}
        onSubmit={() => attempt(() => changeMoveInDate(props.moveNo, date, client), done)}
      >
        <Effect title={t("customers.moveDetail.changeDate.effect")} name="move-change-date" />
        <div className="mt-4">
          <DatePickerField
            id="date"
            label={t("customers.moveDetail.tile.moveInDate")}
            value={date}
            onChange={setDate}
            dateFormat={props.regional.dateFormat}
            required
          />
        </div>
      </FormModal>
    );
  }

  if (props.open === "enterOpeningRead") {
    return (
      <EnterOpeningReadModal
        moveNo={props.moveNo}
        unreadRegisters={props.unreadRegisters}
        unitId={props.unitId ?? null}
        moveInDate={props.moveInDate ?? ""}
        regional={props.regional}
        client={client}
        onClose={props.onClose}
        done={done}
      />
    );
  }

  if (props.open === "addWorkOrder") {
    const payload = fieldVisitPayload(visit);
    return (
      <FormModal
        title={t("customers.moveDetail.addWorkOrder.title")}
        schema={z.object({})}
        values={{}}
        onClose={props.onClose}
        submitLabel={t("customers.moveDetail.addWorkOrder.submit")}
        onSubmit={() => attempt(() => addMoveWorkOrders(props.moveNo, payload ?? {}, client), done)}
      >
        <FieldVisitOrders
          flowKind="move_in"
          value={visit}
          onChange={setVisit}
          dateFormat={props.regional.dateFormat}
          timeZone={props.regional.timeZone}
          t={t}
          client={client}
        />
      </FormModal>
    );
  }

  if (props.open === "discardDraft") {
    return (
      <FormModal
        title={t("customers.moveDetail.discard.title", { ref: props.moveNo })}
        schema={z.object({})}
        values={{}}
        onClose={props.onClose}
        submitLabel={t("customers.moveDetail.discard.submit")}
        submitVariant="danger"
        commitBlocked={props.parkId === null ? t("customers.moveDetail.absent.notReadable") : undefined}
        onSubmit={() => attempt(() => discardWizardPark(props.parkId ?? "", client), done)}
      >
        <Effect title={t("customers.moveDetail.discard.effect")} name="move-discard" />
      </FormModal>
    );
  }

  // ── Cancel move-in… ───────────────────────────────────────────────────────
  const answer = preview.data ?? null;
  const blocked =
    preview.isError
      ? t("customers.moveIn.cancel.notCancellable")
      : answer !== null && !answer.allowed
        ? t(answer.refusal?.message_key ?? "customers.moveIn.cancel.notCancellable")
        : undefined;
  return (
    <FormModal
      title={t("customers.moveDetail.cancel.title", { ref: props.moveNo })}
      schema={z.object({})}
      values={{}}
      onClose={props.onClose}
      submitLabel={t("customers.moveDetail.cancel.submit")}
      submitVariant="danger"
      commitBlocked={answer === null && !preview.isError ? t("customers.moveDetail.cancel.checking") : blocked}
      onSubmit={() => attempt(() => cancelMoveIn(props.moveNo, {}, client), done)}
    >
      {answer === null && !preview.isError ? (
        <LoadingSkeleton variant="card" rows={2} />
      ) : answer !== null ? (
        <div data-cancel-reverses="">
          <Effect title={t("customers.moveDetail.cancel.effect")} name="move-cancel" />
          <ul className="mt-3 list-disc pl-5 text-base" data-cancel-lines="">
            {cancelLines(answer, t).map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
        </div>
      ) : null}
    </FormModal>
  );
}
