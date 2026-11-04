// ── Trace ──────────────────────────────────────────────
// Change:   DEF-BIL-10052 task 5 (PO 2026-10-11) — ticking *Estimate* on a
//           move-out meter shows the estimate straight away, marked Estimated,
//           computed by billing's own draft-bill path
//           (`GET /accounts/{id}/move-out-estimate`) so step 2 shows the figure
//           step 3 prices. No history → it says so, and the clerk types one.
// Rules:    hard rule 3 (a quantity always carries its unit) · B14 rules 21,
//           33, 43 · BR-MET-026 (an estimate from the register's own history)
// ───────────────────────────────────────────────────────
import { useQuery } from "@tanstack/react-query";

import type { ApiClient } from "@/api/client";
import type { Translator } from "@/features/tenancy/settingsShared";

export interface MoveOutEstimate {
  estimated: boolean;
  consumption?: string;
  unit?: string;
  reason?: string;
}

export async function getMoveOutEstimate(
  client: ApiClient,
  accountId: string,
  meterNo: string,
  movedOutOn: string,
): Promise<MoveOutEstimate> {
  const answer = await client.get<MoveOutEstimate>(
    `/accounts/${encodeURIComponent(accountId)}/move-out-estimate` +
      `?meter_no=${encodeURIComponent(meterNo)}&moved_out_on=${encodeURIComponent(movedOutOn)}`,
  );
  return answer.data ?? { estimated: false, reason: "no_answer" };
}

/** Two places, never more: the usage the estimate gives, as a person reads it. */
function shown(amount: string): string {
  const value = Number(amount);
  return Number.isFinite(value) ? value.toLocaleString(undefined, { maximumFractionDigits: 2 }) : amount;
}

export function MoveOutEstimateNote(props: {
  client: ApiClient;
  accountId: string;
  meterNo: string;
  movedOutOn: string;
  t: Translator;
}) {
  const { t } = props;
  const ready = props.accountId !== "" && props.meterNo !== "" && props.movedOutOn !== "";
  const estimate = useQuery({
    queryKey: ["customers", "move-out-estimate", props.accountId, props.meterNo, props.movedOutOn],
    queryFn: () => getMoveOutEstimate(props.client, props.accountId, props.meterNo, props.movedOutOn),
    enabled: ready,
    retry: false,
  });
  if (!ready || estimate.isLoading) return null;
  const answer = estimate.data;
  if (estimate.isError || answer === undefined) {
    return (
      <span className="text-sm text-neutral-700" data-move-out-estimate="unavailable">
        {t("customers.moveOut.estimate.unavailable")}
      </span>
    );
  }
  // A reading the period ALREADY holds wins over an estimate, and the draft
  // bill prices it — so say that, with the usage it will bill.
  if (answer.reason === "read_on_file" && answer.consumption !== undefined && answer.unit) {
    return (
      <span className="text-sm text-neutral-700" data-move-out-estimate="read-on-file">
        {t("customers.moveOut.estimate.readOnFile", { amount: shown(answer.consumption), unit: answer.unit })}
      </span>
    );
  }
  if (!answer.estimated || answer.consumption === undefined || !answer.unit) {
    return (
      <span className="text-sm text-warning-700" data-move-out-estimate="no-history">
        {answer.reason === "no_history"
          ? t("customers.moveOut.estimate.noHistory")
          : t("customers.moveOut.estimate.unavailable")}
      </span>
    );
  }
  return (
    <span className="flex flex-col text-sm" data-move-out-estimate="estimated">
      <span className="font-semibold tabular-nums">
        {t("customers.moveOut.estimate.used", { amount: shown(answer.consumption), unit: answer.unit })}
      </span>
      <span className="text-neutral-700">{t("customers.moveOut.estimate.why")}</span>
    </span>
  );
}
