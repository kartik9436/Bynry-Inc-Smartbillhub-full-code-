// ── Trace ──────────────────────────────────────────────
// Defect:   DEF-BIL-9077 — the one-time bill held a meter that rolled over
//           partway through the period (`possible_rollover`, DEF-BIL-9076) and
//           offered no way to accept it: a live screen behind a dead control
//           (CLAUDE.md law 2).
// Rules:    PO 2026-09-30, changes rows 45–46 (a rollover waits for a clerk to
//           accept it) · B14 rule 43 (a component, not inline code) · rule 21
//           (Tailwind; this file is on `src/styles/route-b-migrated.txt`) ·
//           rule 31 (the meter by its NUMBER, never an id) · rule 33 (labels
//           ≤ 3 words, facts ≤ 6) · rule 36 (the kit: `OtbPanel`, `FactBlock`,
//           `Button`)
// Tests:    OneTimeBillPage.dom.test.tsx — "a meter rollover held on the
//           preview (DEF-BIL-9077)"
// ───────────────────────────────────────────────────────
/**
 * THE ACCEPT-ROLLOVER CONTROL, beside the hold it clears.
 *
 * The preview refuses with `possible_rollover` when a meter's dial went
 * backwards inside the period and nobody has accepted it. Its 422 carries what
 * the clerk needs to judge it — the meter's number, the dial before the
 * rollover, after it and at the period's close, and the usage they imply — so
 * this panel shows exactly those and one button. Accepting adds the service to
 * the request's `accepted_rollovers`, which the API already takes; the next
 * preview then bills across the rollover (99,800 → 240 → 700 is 900 kWh).
 */
import { isApiError } from "@/api/client";
import { Button } from "@/components/Button";
import { FactBlock } from "@/components/FactBlock";
import type { Translator } from "@/components/FormModal";
import { formatQuantity } from "@/components/UnitCell";

import { OtbPanel } from "./oneTimeBillShared";

/** What a `possible_rollover` hold tells the clerk. Never an id. */
export interface RolloverHold {
  /** The service the hold is about — what `accepted_rollovers` names. */
  serviceCode: string;
  meter: string | null;
  /** The dial before the rollover, after it, and at the period's close. */
  dials: [string, string, string];
  usage: string;
  unit: string;
}

const ROLLOVER_REASON = "possible_rollover";

function text(value: unknown): string | null {
  return typeof value === "string" && value !== "" ? value : null;
}

/** The hold, read off a preview refusal — or null for any other refusal. */
export function rolloverHoldFrom(error: unknown): RolloverHold | null {
  if (!isApiError(error) || error.status !== 422) return null;
  const params = error.params;
  if (params.reason !== ROLLOVER_REASON) return null;
  const serviceCode = text(params.service_code);
  const before = text(params.from);
  const after = text(params.to);
  const closing = text(params.closing);
  const usage = text(params.suggested_quantity);
  const unit = text(params.unit);
  if (serviceCode === null || before === null || after === null || closing === null || usage === null || unit === null) {
    return null;
  }
  return { serviceCode, meter: text(params.meter), dials: [before, after, closing], usage, unit };
}

export function RolloverAccept(props: { hold: RolloverHold; onAccept: (serviceCode: string) => void; t: Translator }) {
  const { hold, t } = props;
  const title = t("billing.oneTimeBill.rollover.title");
  return (
    <OtbPanel id="otb-rollover" title={title}>
      <div className="flex flex-col gap-3">
        <FactBlock
          name="otb-rollover"
          facts={[
            { id: "meter", label: t("billing.oneTimeBill.rollover.meter"), value: hold.meter ?? "—" },
            {
              id: "dials",
              label: t("billing.oneTimeBill.rollover.dials"),
              value: hold.dials.map((dial) => formatQuantity(dial)).join(" → "),
            },
            {
              id: "usage",
              label: t("billing.oneTimeBill.rollover.usage"),
              value: `${formatQuantity(hold.usage)} ${hold.unit}`,
            },
          ]}
        />
        <div>
          <Button variant="primary" onClick={() => props.onAccept(hold.serviceCode)}>
            {t("billing.oneTimeBill.rollover.accept")}
          </Button>
        </div>
      </div>
    </OtbPanel>
  );
}
