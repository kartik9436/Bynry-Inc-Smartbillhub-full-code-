// ── Trace ──────────────────────────────────────────────
// Change:   CR-162-BRC10 items 3, 5, 38 — Approve / Activate a New Connection.
// Ruling:   decision log 2026-10-02 (commit 56eb54ba9): *"activate one, several
//           or all services/units whose work orders are complete; open orders
//           listed in a warning and stay pending (Partly activated)"* · Q2: *"a
//           gate inspection that has not passed blocks activation of its unit;
//           every other open work order only warns."*
// Rules:    B14 rule 31 (orders by NUMBER, never an id) · rule 33 (a fact ≤ 6
//           words, an instruction ≤ 6 words per sentence) · rule 43 (one
//           component — the header's Approve and the Units tab's buttons both
//           open it) · rule 21 (Tailwind utilities)
// ───────────────────────────────────────────────────────
/**
 * **The one Approve dialog.** It is handed what the clerk chose and the
 * build's activation read, and it says three things before anything is
 * written:
 *
 *   1. what will be activated — the chosen rows that are READY;
 *   2. what is held back and why — a gate not passed (blocks its unit), or the
 *      unit's own orders still open;
 *   3. the warning — every open order on the build, *"2 of 4 not complete:
 *      WO-0055, WO-0056"*, and the open to-dos (which never block).
 *
 * *Activate what is ready* sends only the ready rows and the acknowledgement;
 * the server re-checks every one of them (`connection_activation.activate`).
 */
import { Button } from "@/components/Button";
import { ModalShell } from "@/components/FormModal";
import { WorkingButton } from "@/components/StateFrame";
import { WarningBox } from "@/components/WarningBox";
import type { Translator } from "@/features/customers/newConnectShared";
import type { ActivationRead, ActivationRow } from "@/features/customers/buildLifecycleEndpoints";

/** The chosen rows split three ways — pure, so a test asks it without a DOM. */
export function splitChoice(
  read: ActivationRead,
  chosen: readonly string[],
): { ready: ActivationRow[]; gated: ActivationRow[]; waiting: ActivationRow[] } {
  const rows = read.rows.filter((row) => chosen.includes(row.id) && row.state !== "activated");
  return {
    ready: rows.filter((row) => row.ready),
    gated: rows.filter((row) => !row.ready && row.blocked_by_gate !== null),
    waiting: rows.filter((row) => !row.ready && row.blocked_by_gate === null),
  };
}

function rowName(row: ActivationRow, t: Translator): string {
  return `${row.unit_label ?? ""} · ${t(`rating.service.${row.service}`, { defaultValue: row.service })}`;
}

export function ActivateBuildDialog(props: {
  t: Translator;
  read: ActivationRead;
  chosen: readonly string[];
  working: boolean;
  /** Why the last press was refused, already in the clerk's words. */
  refusal?: string | null;
  onActivate: (ids: string[], acknowledge: boolean) => void;
  onClose: () => void;
}) {
  const { t, read } = props;
  const { ready, gated, waiting } = splitChoice(read, props.chosen);
  const openOrders = read.open_orders;
  const warn = openOrders.length > 0;

  return (
    <ModalShell
      title={t("customers.build.activate.title", { defaultValue: "Approve and activate" })}
      kicker={read.connection_no ?? undefined}
      onClose={props.onClose}
      role="alertdialog"
    >
      <div className="modal-body flex flex-col gap-3" data-activate-dialog="">
        {ready.length > 0 ? (
          <div data-activate-ready="">
            <p className="m-0 font-semibold">
              {t("customers.build.activate.ready", {
                count: ready.length,
                defaultValue: `Ready to activate: ${ready.length}`,
              })}
            </p>
            <ul className="m-0 mt-1 list-disc pl-5 text-sm">
              {ready.map((row) => (
                <li key={row.id} data-activate-row={row.id}>
                  {rowName(row, t)}
                </li>
              ))}
            </ul>
          </div>
        ) : (
          <p className="m-0 font-semibold" data-activate-none="">
            {t("customers.build.activate.noneReady", { defaultValue: "Nothing chosen is ready." })}
          </p>
        )}

        {gated.length > 0 && (
          <div data-activate-gated="" className="text-danger-700">
            {gated.map((row) => (
              <p key={row.id} className="m-0 text-sm">
                {t("customers.build.activate.gated", {
                  unit: rowName(row, t),
                  order: row.blocked_by_gate ?? "",
                  defaultValue: `${rowName(row, t)}: gate ${row.blocked_by_gate ?? ""} not passed.`,
                })}
              </p>
            ))}
          </div>
        )}

        {waiting.length > 0 && (
          <div data-activate-waiting="">
            {waiting.map((row) => (
              <p key={row.id} className="m-0 text-sm">
                {t("customers.build.activate.waiting", {
                  unit: rowName(row, t),
                  orders: row.open_orders.filter(Boolean).join(", "),
                  defaultValue: `${rowName(row, t)}: waits on ${row.open_orders.filter(Boolean).join(", ")}.`,
                })}
              </p>
            ))}
          </div>
        )}

        {warn && (
          <WarningBox
            tone="soon"
            data-warning="activate-open-orders"
            sentence={
              <>
                {t("customers.build.activate.openOrders", {
                  open: openOrders.length,
                  total: read.orders_total,
                  defaultValue: `${openOrders.length} of ${read.orders_total} not complete:`,
                })}{" "}
                <span data-open-orders="">
                  {openOrders
                    .map((order) => order.order_no)
                    .filter(Boolean)
                    .join(", ")}
                </span>
              </>
            }
            note={t("customers.build.activate.openStay", { defaultValue: "Those stay pending." })}
          />
        )}

        {read.open_todos.length > 0 && (
          <div data-activate-todos="">
            <p className="m-0 text-sm font-semibold">
              {t("customers.build.activate.todos", {
                count: read.open_todos.length,
                defaultValue: `To-dos open: ${read.open_todos.length}`,
              })}
            </p>
            <ul className="m-0 mt-1 list-disc pl-5 text-sm">
              {read.open_todos.map((todo) => (
                <li key={todo.id}>{todo.title}</li>
              ))}
            </ul>
          </div>
        )}

        {props.refusal !== undefined && props.refusal !== null && (
          <p className="m-0 text-sm text-danger-700" role="alert" data-activate-refusal="">
            {props.refusal}
          </p>
        )}
      </div>
      <div className="modal-foot">
        <Button variant="ghost" disabled={props.working} onClick={props.onClose}>
          {t("confirm.cancel", { defaultValue: "Cancel" })}
        </Button>
        <WorkingButton
          working={props.working}
          disabled={ready.length === 0}
          onClick={() => props.onActivate(ready.map((row) => row.id), warn)}
        >
          <span data-act="activateReady">
            {warn || gated.length > 0 || waiting.length > 0
              ? t("customers.build.activate.whatIsReady", { defaultValue: "Activate what is ready" })
              : t("customers.build.activate.confirm", { defaultValue: "Activate" })}
          </span>
        </WorkingButton>
      </div>
    </ModalShell>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-162-BRC10 (decision log 2026-10-02, Q2 and the approval items)
// generated: 2026-10-02 by lane NC-A
// gates: G31 (route-b-migrated.txt) · G13 (mounted by BuildDetailPage)
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
