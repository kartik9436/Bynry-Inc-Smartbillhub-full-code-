// ── Trace ──────────────────────────────────────────────
// Change:   FB-033 — availability from the phone reaches the office (decision
//           log 2026-10-31, D4 = B: Off duty and End shift are separate) ·
//           DEF-FLD-10799
// Rules:    B14 rules 31 (no id on screen), 33 (a FACT ≤ 6 words), 35 (every
//           word from the catalogue), 43 (a piece of UI is a component)
// Tests:    src/features/work/fb033StatusPill.dom.test.tsx
// Impacts:  CrewsPage.tsx (STATUS column) · TechnicianDetailPage.tsx (meta pill)
// ───────────────────────────────────────────────────────
//
// One technician's status as a pill, WITH ITS TIME where the server knows it:
// *Off duty · since 15:30* · *On break · since 10:42* · *Shift ended · 17:02*.
// The time is read off the server's string as written — it is already the
// UTILITY's wall clock (`workforce._since`), so no zone arithmetic happens in
// the browser.
import { useTranslation } from "react-i18next";

import { StatusPill } from "@/components/StatusPill";
import type { StatusTone } from "@/components/StatusPill";

import { STATUS_FALLBACK } from "./workforceLabels";

export const TECHNICIAN_STATUS_TONE: Record<string, StatusTone> = {
  on_shift: "success",
  off_today: "info",
  unavailable: "warning",
  on_break: "warning",
  off_duty: "neutral",
};

/** `2026-10-28T15:30:00-05:00` → `15:30`; anything else → null. */
export function wallClockOf(since: string | null | undefined): string | null {
  const match = /T(\d{2}:\d{2})/.exec(since ?? "");
  return match ? match[1] : null;
}

/** The words the pill shows — a pure function so a test can read them. */
export function statusPillText(
  status: string,
  since: string | null | undefined,
  shiftEnded: boolean | undefined,
  t: (key: string, params?: Record<string, unknown>) => string,
): string {
  const word = t(`work.crews.status.${status}`, { defaultValue: STATUS_FALLBACK[status] ?? status });
  const time = wallClockOf(since);
  if (time === null) return word;
  if (status === "off_today" && shiftEnded === true) return t("work.crews.shiftEnded", { time });
  if (status === "off_duty" || status === "on_break") return t("work.crews.statusSince", { status: word, time });
  return word;
}

export function TechnicianStatusPill(props: {
  status: string;
  since?: string | null;
  shiftEnded?: boolean;
}) {
  const { t } = useTranslation();
  return (
    <StatusPill tone={TECHNICIAN_STATUS_TONE[props.status] ?? "muted"}>
      {statusPillText(props.status, props.since, props.shiftEnded, (key, params) => t(key, params))}
    </StatusPill>
  );
}
