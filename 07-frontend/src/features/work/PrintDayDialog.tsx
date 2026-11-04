// ── Trace ──────────────────────────────────────────────
// Change:   CR-168-BRC10 round 6, lane SRV-5 — ruling 3, *"a day's pack
//           prints"* (P6.3). The door to `GET /work/print/day-pack`.
// Rules:    B14 rule 43 (a piece of UI is a component) · rule 38/44 (built from
//           the kit's `FormModal`) · rule 33 (labels ≤ 3 words) · rule 31 (the
//           technician travels as the SLUG the page is addressed by, never an id)
// ───────────────────────────────────────────────────────
//
// ⚠ **NO DRAWING SHOWS THIS DIALOG.** Ruling 3 names the print and P6 has *"no
// screen drawn"*, so the shape is the kit's smallest form: one date, today by
// default, and *Print*, which opens the PDF in the browser's own viewer — its
// print button prints it. A dispatcher printing tomorrow's packs the evening
// before picks tomorrow.
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { z } from "zod";

import { apiHref } from "@/api/apiHref";
import { DatePickerField, FormModal } from "@/components/FormModal";
import type { FormSubmitOutcome } from "@/components/FormModal";
import type { RegionalDateFormat } from "@/components/DateCell";
import { todayInZone } from "@/components/DateCell";

/** The day pack's address for one holder and one day — the ONE place the
 *  query is spelt, so the dialog and its test cannot disagree. */
export function dayPackHref(
  tenantPath: (segment: string) => string,
  holder: { technician: string } | { crew: string },
  date: string,
): string {
  const who =
    "technician" in holder
      ? `technician=${encodeURIComponent(holder.technician)}`
      : `crew=${encodeURIComponent(holder.crew)}`;
  return apiHref(tenantPath(`/work/print/day-pack?date=${encodeURIComponent(date)}&${who}`));
}

export function PrintDayDialog(props: {
  name: string;
  holder: { technician: string } | { crew: string };
  tenantPath: (segment: string) => string;
  timeZone: string;
  dateFormat: RegionalDateFormat;
  onClose: () => void;
  /** Injected so a test can see the address without a browser tab. */
  open?: (href: string) => void;
}) {
  const { t } = useTranslation();
  const [date, setDate] = useState(todayInZone(props.timeZone));
  const schema = z.object({ date: z.string().min(1, t("work.print.dateRequired")) });

  async function submit(): Promise<FormSubmitOutcome> {
    const href = dayPackHref(props.tenantPath, props.holder, date);
    (props.open ?? ((url: string) => window.open(url, "_blank", "noopener")))(href);
    props.onClose();
    return { ok: true };
  }

  return (
    <FormModal
      title={t("work.print.dayTitle", { name: props.name })}
      schema={schema}
      values={{ date }}
      onSubmit={submit}
      onClose={props.onClose}
      submitLabel={t("work.print.submit")}
      cancelLabel={t("work.print.back")}
    >
      <DatePickerField
        id="date"
        label={t("work.print.day")}
        value={date}
        onChange={setDate}
        dateFormat={props.dateFormat}
        required
      />
    </FormModal>
  );
}
