// ── Trace ──────────────────────────────────────────────
// Change:   CR-193-BRC10 — MQ-040 STEP 1 (decision log 2026-10-26, *"working
//           days per technician with one-day exceptions (web, technician
//           page)"*): the Overview's *Working days* and *Exceptions* groups.
// Server:   apps/work/shifts_api.py (`shiftsEndpoints.ts`)
// Rules:    B14 rule 21 (Tailwind; on route-b-migrated.txt) · rule 6 (a remove
//           is a destructive commit — the danger tier, asked first) · rule 15
//           (row actions are icons with tooltips) · rule 31 (no id on screen)
//           · rule 33 (labels ≤ 3 words; no rationale on screen) · rule 38/44
//           (the form is our kit's FormModal) · rule 43 (components, not page
//           code; the window reuses `ShiftField`) · NFR-3 (the list is paged by
//           the server)
// Tests:    src/features/work/TechnicianShifts.dom.test.tsx
// ───────────────────────────────────────────────────────
//
// THE WINDOW IS NOT EDITED HERE. A technician's daily window is the existing
// `shift_start`/`shift_end` (set on Add crew member); this group SHOWS it beside
// the days so a dispatcher reads the whole rule in one place, and edits only
// the days. A day that is not like the rule is an EXCEPTION, below.
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { z } from "zod";

import { formErrorEnvelope, isApiError } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { refusalText } from "@/api/refusalText";
import { Button } from "@/components/Button";
import { ChipToggle } from "@/components/Chip";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { DateCell } from "@/components/DateCell";
import { DatePickerField, FormModal, SegmentedField, TextField } from "@/components/FormModal";
import type { FormSubmitOutcome } from "@/components/FormModal";
import { PencilIcon, TrashIcon } from "@/components/icons";
import { ListPager } from "@/components/ListPager";
import { Panel } from "@/components/Panel";
import { RowAction, RowActions } from "@/components/RowActions";
import { PlainTable } from "@/components/Surfaces";
import { Note } from "@/components/TextBits";
import { PAGE_SIZES } from "@/components/tableTypes";
import type { PageSize } from "@/components/tableTypes";
import { Dash } from "@/features/customers/customersShared";

import { ShiftField } from "./ShiftField";
import {
  WEEKDAYS,
  addException,
  editException,
  getWorkingDays,
  listExceptions,
  removeException,
  setWorkingDays,
} from "./shiftsEndpoints";
import type { DayException, ExceptionKind, Weekday } from "./shiftsEndpoints";

type DateFormat = Parameters<typeof DateCell>[0]["dateFormat"];

const daysKey = (slug: string) => ["work", "technician", slug, "working-days"] as const;
const exceptionsKey = (slug: string) => ["work", "technician", slug, "exceptions"] as const;

/** The Overview's *Working days*: seven toggles, Monday first, and the window. */
export function WorkingDaysPanel(props: { slug: string; client: ApiClient }) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [saving, setSaving] = useState(false);
  const [said, setSaid] = useState<string | null>(null);
  const days = useQuery({
    queryKey: daysKey(props.slug),
    queryFn: () => getWorkingDays(props.slug, props.client),
  });
  const held = Array.isArray(days.data?.weekdays) ? days.data.weekdays : null;

  async function toggle(day: Weekday) {
    if (held === null) return;
    const next = held.includes(day) ? held.filter((d) => d !== day) : [...held, day];
    setSaving(true);
    setSaid(null);
    try {
      const saved = await setWorkingDays(
        props.slug,
        WEEKDAYS.filter((d) => next.includes(d)),
        props.client,
      );
      queryClient.setQueryData(daysKey(props.slug), saved);
    } catch (error) {
      setSaid(refusalText((key, params) => t(key, params), error));
    } finally {
      setSaving(false);
    }
  }

  return (
    <Panel as="section" title={t("work.technician.workingDays.title")} data-technician-working-days="">
      {days.isError || (days.data !== undefined && held === null) ? (
        <Note>{t("work.technician.workingDays.failed")}</Note>
      ) : held === null ? null : (
        <div className="flex flex-col gap-3">
          <div className="flex flex-wrap gap-2" role="group" aria-label={t("work.technician.workingDays.title")}>
            {WEEKDAYS.map((day) => (
              <ChipToggle
                key={day}
                selected={held.includes(day)}
                aria-disabled={saving ? true : undefined}
                data-weekday={day}
                onClick={() => {
                  if (!saving) void toggle(day);
                }}
              >
                {t(`work.technician.workingDays.day.${day}`)}
              </ChipToggle>
            ))}
          </div>
          <p className="m-0 text-base" data-working-window="">
            {days.data?.shift_start && days.data.shift_end
              ? t("work.technician.workingDays.window", { start: days.data.shift_start, end: days.data.shift_end })
              : t("work.technician.workingDays.noWindow")}
          </p>
          {said !== null && (
            <p className="m-0" role="status" data-working-days-said="">
              {said}
            </p>
          )}
        </div>
      )}
    </Panel>
  );
}

/** The Overview's *Exceptions*: one day off, or one day of different hours. */
export function ExceptionsPanel(props: {
  slug: string;
  client: ApiClient;
  timeZone: string;
  dateFormat: DateFormat;
}) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const [per, setPer] = useState<PageSize>(PAGE_SIZES[0]);
  const [editing, setEditing] = useState<DayException | "new" | null>(null);
  const [asking, setAsking] = useState<DayException | null>(null);
  const [working, setWorking] = useState(false);
  const [said, setSaid] = useState<string | null>(null);

  const list = useQuery({
    queryKey: [...exceptionsKey(props.slug), page, per],
    queryFn: () => listExceptions(props.slug, { page, per }, props.client),
  });
  const refresh = () => void queryClient.invalidateQueries({ queryKey: exceptionsKey(props.slug) });

  async function remove(row: DayException) {
    setWorking(true);
    try {
      await removeException(props.slug, row.id, props.client);
      setSaid(null);
      refresh();
    } catch (error) {
      setSaid(refusalText((key, params) => t(key, params), error));
    } finally {
      setWorking(false);
      setAsking(null);
    }
  }

  const rows = list.data?.rows ?? [];
  return (
    <Panel
      as="section"
      title={t("work.technician.exceptions.title")}
      data-technician-exceptions=""
      trailing={
        <Button variant="secondary" size="sm" data-add-exception="" onClick={() => setEditing("new")}>
          {t("work.technician.exceptions.add")}
        </Button>
      }
    >
      {said !== null && (
        <p className="m-0 mb-3" role="status" data-exceptions-said="">
          {said}
        </p>
      )}
      {list.isError ? (
        <Note>{t("work.technician.exceptions.failed")}</Note>
      ) : list.data !== undefined && rows.length === 0 ? (
        <Note data-exceptions-empty="">{t("work.technician.exceptions.empty")}</Note>
      ) : list.data === undefined ? null : (
        <>
          <PlainTable data-exceptions-table="">
            <thead>
              <tr>
                <th>{t("work.technician.exceptions.col.date")}</th>
                <th>{t("work.technician.exceptions.col.change")}</th>
                <th>{t("work.technician.exceptions.col.note")}</th>
                <th>{t("work.technician.exceptions.col.actions")}</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.id} data-exception-kind={row.kind}>
                  <td>
                    <DateCell value={row.date} timeZone={props.timeZone} dateFormat={props.dateFormat} />
                  </td>
                  <td>
                    {row.kind === "off"
                      ? t("work.technician.exceptions.kind.off")
                      : // Two clock times and a dash — no words, so nothing to translate.
                        `${row.start ?? ""}–${row.end ?? ""}`}
                  </td>
                  <td>{row.note ?? <Dash />}</td>
                  <td>
                    <RowActions>
                      <RowAction
                        label={t("work.technician.exceptions.edit")}
                        icon={<PencilIcon />}
                        onClick={() => setEditing(row)}
                      />
                      <RowAction
                        label={t("work.technician.exceptions.remove")}
                        icon={<TrashIcon />}
                        danger
                        onClick={() => setAsking(row)}
                      />
                    </RowActions>
                  </td>
                </tr>
              ))}
            </tbody>
          </PlainTable>
          <ListPager
            total={list.data.total}
            page={page}
            per={per}
            onPage={setPage}
            onPer={(next) => {
              setPer(next);
              setPage(1);
            }}
          />
        </>
      )}
      {editing !== null && (
        <ExceptionModal
          slug={props.slug}
          client={props.client}
          dateFormat={props.dateFormat}
          current={editing === "new" ? null : editing}
          onClose={() => setEditing(null)}
          onSaved={() => {
            setEditing(null);
            refresh();
          }}
        />
      )}
      {asking !== null && (
        <ConfirmDialog
          title={t("work.technician.exceptions.removeTitle")}
          consequence={t("work.technician.exceptions.removeConsequence")}
          confirmLabel={t("work.technician.exceptions.removeConfirm")}
          cancelLabel={t("work.technician.exceptions.cancel")}
          confirmVariant="danger"
          working={working}
          onConfirm={() => void remove(asking)}
          onCancel={() => setAsking(null)}
        />
      )}
    </Panel>
  );
}

/** `HH:MM`, both ends, end after start — the server's own rule and sentence. */
export function exceptionSchema(messages: { date: string; window: string }) {
  return z
    .object({
      date: z.string().regex(/^\d{4}-\d{2}-\d{2}$/u, { message: messages.date }),
      kind: z.enum(["off", "window"]),
      start: z.string(),
      end: z.string(),
    })
    .refine(
      (v) => v.kind === "off" || (/^\d{2}:\d{2}$/u.test(v.start) && /^\d{2}:\d{2}$/u.test(v.end) && v.end > v.start),
      { message: messages.window, path: ["window"] },
    );
}

export function ExceptionModal(props: {
  slug: string;
  client: ApiClient;
  dateFormat: DateFormat;
  current: DayException | null;
  onClose: () => void;
  onSaved: () => void;
}) {
  const { t } = useTranslation();
  const [date, setDate] = useState(props.current?.date ?? "");
  const [kind, setKind] = useState<ExceptionKind>(props.current?.kind ?? "off");
  const [hours, setHours] = useState({ start: props.current?.start ?? "", end: props.current?.end ?? "" });
  const [note, setNote] = useState(props.current?.note ?? "");

  async function handleSubmit(): Promise<FormSubmitOutcome> {
    const body = {
      date,
      kind,
      ...(kind === "window" ? { start: hours.start, end: hours.end } : {}),
      note: note.trim(),
    };
    try {
      if (props.current === null) await addException(props.slug, body, props.client);
      else await editException(props.slug, props.current.id, body, props.client);
      props.onSaved();
      return { ok: true };
    } catch (error) {
      if (isApiError(error)) return { ok: false, error: formErrorEnvelope(error) };
      return { ok: false, error: { code: "", message_key: "api.error.unexpected" } };
    }
  }

  return (
    <FormModal
      title={t(props.current === null ? "work.technician.exceptions.addTitle" : "work.technician.exceptions.editTitle")}
      schema={exceptionSchema({ date: t("work.shifts.date_invalid"), window: t("work.shifts.window_invalid") })}
      values={{ date, kind, start: hours.start, end: hours.end }}
      onSubmit={handleSubmit}
      onClose={props.onClose}
      submitLabel={t("work.technician.exceptions.save")}
    >
      <DatePickerField
        id="date"
        label={t("work.technician.exceptions.field.date")}
        value={date}
        onChange={setDate}
        dateFormat={props.dateFormat}
        required
      />
      <SegmentedField
        id="kind"
        label={t("work.technician.exceptions.field.kind")}
        value={kind}
        onChange={(next) => setKind(next === "window" ? "window" : "off")}
        options={[
          { value: "off", label: t("work.technician.exceptions.kind.off") },
          { value: "window", label: t("work.technician.exceptions.kind.window") },
        ]}
        required
      />
      {kind === "window" && (
        <ShiftField
          id="window"
          label={t("work.technician.exceptions.field.hours")}
          value={hours}
          onChange={setHours}
        />
      )}
      <TextField id="note" label={t("work.technician.exceptions.field.note")} value={note} onChange={setNote} />
    </FormModal>
  );
}
