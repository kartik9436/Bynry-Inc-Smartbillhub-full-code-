/**
 * `CR-185-BRC10` — a move-out's tie-back to the owner, as one short fact.
 *
 * Only money IN THE BOOKS moves (coordinator ruling 2026-10-14): when the
 * move-out drafted a final bill the tie-back is PENDING until that bill is
 * sent, then POSTED for what the closed account owed then. The completion
 * screen, the move-out record and the account all read the server's state
 * and render it here, so the three can never word it differently.
 */
import { formatMoney } from "@/components/MoneyCell";
import type { Translator } from "@/features/tenancy/settingsShared";

export interface BalanceToOwnerStateValue {
  status?: "pending" | "posted" | "nothing_owed" | string | null;
  posted?: boolean;
  pending?: boolean;
  amount?: { display?: string | null } | null;
}

export function BalanceToOwnerState({
  state,
  currency,
  t,
  testId,
}: {
  state: BalanceToOwnerStateValue;
  currency: string;
  t: Translator;
  testId?: string;
}) {
  const word =
    state.posted === true || state.status === "posted"
      ? t("customers.moveOut.done.posted")
      : state.pending === true || state.status === "pending"
        ? t("customers.moveOut.done.whenBillSent")
        : t("customers.moveOut.done.nothingOwed");
  return (
    <span data-testid={testId}>
      {formatMoney(state.amount?.display ?? "0", currency)} · {word}
    </span>
  );
}
