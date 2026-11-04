// ── Trace ──────────────────────────────────────────────
// Defect:   DEF-CUS-10050 — *Fetch reading* on each metered row of Move-in
//           step 1's *Services and meters* (ACC-05). PO ruling 2026-10-11,
//           verbatim: *"this si correct 0 fix it"*. DEF-CUS-10051 (Move-out
//           step 2) mounts THIS component next, with `asOf`.
// Rules:    B14 rule 43 (a piece of UI is a COMPONENT, never code inside a
//           page) · B14 row actions are icons (`RowAction`, rule 15's
//           accessible name) · rule 21 (Tailwind; on route-b-migrated.txt) ·
//           rule 33 (each line ≤ 6 words) · hard rule 3 (a reading carries
//           its unit) · hard-won law 1 (never a reading we did not receive)
// Data:     `POST /integrations/meter-reading/fetch` → `{result, reading,
//           message_key}` (apps/integrations/meter_reading.py)
// Tests:    FetchMeterReading.dom.test.tsx ·
//           customers/moveInWizard/StepUnit.dom.test.tsx
// ───────────────────────────────────────────────────────
//
// ⚠ **THE COMPONENT NEVER WRITES THE BOX — THE HOST DOES, THROUGH
// `onFetched`.** The move-in keeps its readings in the wizard's draft keyed by
// meter number; the move-out keeps them keyed by asset id with a prefill laid
// over them. A component that reached into either would be two components
// pretending to be one. It hands back `{value, unit, read_on}` and the host
// decides where that goes — which is also why manual typing is untouched: the
// box is the host's and a typed value simply replaces whatever is in it.
//
// ⚠ **`asOf` IS THE MOVE-OUT'S AND IS ENFORCED BY THE SERVER TOO.** Absent, the
// head-end's latest reading; present (`YYYY-MM-DD`), the reading on or last
// before that day — a later one comes back `no_reading`, never as a figure
// recorded against the wrong day.
import { useState } from "react";

import type { ApiClient } from "@/api/client";
import { formatDate } from "@/components/DateCell";
import type { RegionalDateFormat } from "@/components/DateCell";
import { FetchIcon } from "@/components/icons";
import { RowAction } from "@/components/RowActions";
import type { Translator } from "@/features/tenancy/settingsShared";

export const FETCH_METER_READING_PATH = "/integrations/meter-reading/fetch";

/** A reading the head-end gave: decimal string, its own unit, ISO date. */
export interface FetchedMeterReading {
  meter_no: string;
  value: string;
  unit: string;
  read_on: string;
}

export type FetchMeterReadingResult = "fetched" | "not_connected" | "no_reading" | "unavailable";

export interface FetchMeterReadingAnswer {
  result: FetchMeterReadingResult;
  reading: FetchedMeterReading | null;
  message_key: string | null;
  /** The sentence's values, e.g. `{provider: "Neptune 360"}`. */
  params?: Record<string, string>;
}

/** The one request. `asOf` = `YYYY-MM-DD`, or absent for the latest. */
export async function fetchMeterReading(
  client: ApiClient,
  meterNo: string,
  asOf?: string,
): Promise<FetchMeterReadingAnswer> {
  const body = asOf === undefined || asOf === "" ? { meter_no: meterNo } : { meter_no: meterNo, as_of: asOf };
  const response = await client.post<FetchMeterReadingAnswer>(FETCH_METER_READING_PATH, body);
  if (response.data === null) {
    throw new Error(`empty ${response.status} body where the contract promises one`);
  }
  return response.data;
}

type Shown =
  | { kind: "idle" }
  | { kind: "fetched"; readOn: string; value: string }
  | { kind: "said"; key: string; params?: Record<string, string> };

export function FetchMeterReading(props: {
  /** The meter NUMBER the head-end knows (`W-5023`) — never a database id. */
  meterNo: string;
  /** `YYYY-MM-DD`: the reading on or last before it. Absent = the latest. */
  asOf?: string;
  client: ApiClient;
  t: Translator;
  timeZone: string;
  dateFormat: RegionalDateFormat;
  /** The host fills its own box. Called only on `fetched`. */
  onFetched: (reading: FetchedMeterReading) => void;
  /** A host that locks the box (an estimate ticked) locks this too. */
  disabled?: boolean;
  /**
   * The unit the host's box is in (its affix). A reading in another unit is
   * NOT handed back — hard rule 3: a quantity is never re-read in a unit it
   * was not taken in, and converting here would be a rule nobody signed.
   */
  expectedUnit?: string | null;
  /**
   * What the host's box holds now. The *Read on* line is shown only while it
   * still holds the fetched value: a clerk who types over it has replaced the
   * head-end's reading, and its date no longer describes the box.
   */
  currentValue?: string;
}) {
  const { t } = props;
  const [working, setWorking] = useState(false);
  const [shown, setShown] = useState<Shown>({ kind: "idle" });

  async function press(): Promise<void> {
    setWorking(true);
    try {
      const answer = await fetchMeterReading(props.client, props.meterNo, props.asOf);
      const expected = (props.expectedUnit ?? "").trim().toLowerCase();
      if (
        answer.result === "fetched" &&
        answer.reading !== null &&
        expected !== "" &&
        answer.reading.unit.trim().toLowerCase() !== expected
      ) {
        setShown({ kind: "said", key: "metering.fetchReading.unitMismatch" });
      } else if (answer.result === "fetched" && answer.reading !== null) {
        props.onFetched(answer.reading);
        setShown({ kind: "fetched", readOn: answer.reading.read_on, value: answer.reading.value });
      } else {
        setShown({
          kind: "said",
          key: answer.message_key ?? "integrations.meterReading.unavailable",
          params: answer.params ?? {},
        });
      }
    } catch {
      setShown({ kind: "said", key: "metering.fetchReading.failed" });
    } finally {
      setWorking(false);
    }
  }

  return (
    <span className="flex flex-col items-start gap-1" data-fetch-reading={props.meterNo}>
      <RowAction
        label={t("metering.fetchReading.label", { meter: props.meterNo })}
        icon={<FetchIcon />}
        working={working || props.disabled === true}
        onClick={() => void press()}
      />
      {shown.kind === "fetched" && (props.currentValue === undefined || props.currentValue === shown.value) ? (
        <span className="text-sm text-neutral-700" data-fetch-reading-state="fetched">
          {t("metering.fetchReading.readOn", {
            date: formatDate(shown.readOn, props.timeZone, props.dateFormat),
          })}
        </span>
      ) : shown.kind === "said" ? (
        <span className="text-sm text-warning-700" role="status" data-fetch-reading-state="said">
          {t(shown.key, shown.kind === "said" ? shown.params : undefined)}
        </span>
      ) : null}
    </span>
  );
}
