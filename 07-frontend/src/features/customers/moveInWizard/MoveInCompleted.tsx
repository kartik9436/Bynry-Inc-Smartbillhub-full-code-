// ── Trace ──────────────────────────────────────────────
// Story:    US-CUS-004 (S19 Move-In wizard — its answer) · CR-171-BRC10 P2.16,
//           image 48 · fixes the screen half of DEF-CUS-9702
// Rules:    BR-SHL-019 (one commit; its answer replaces the wizard) ·
//           BR-MET-036 (occupancy is derived — the unit row reports it) ·
//           BR-NOT-013 (a message is never reported *sent*) · hard rule 2
//           (amounts at 2 places) · B14 rules 31 (no id on screen), 33, 41, 43
// ───────────────────────────────────────────────────────
// **MOVE-IN COMPLETED — image 48 (PO v14: *"on complete move in we should show
// Move In request number and show what happned in the background and then
// allow user ot go back to account or move in request or create another move
// in"*).**
//
// The head is the back link, *Move-in completed*, a COMPLETED pill, the `MVI-`
// number and *From request SR-… · name · unit*. One panel, *What happened*, is
// the server's own list (`what_happened.items`, §9.FLOW P1.21) as ✓ rows —
// `CheckList`, the kit's row-per-check list, never a second one. The footer is
// *+ Start another move-in* on the left and *Open the move-in* · *Open the
// account →* on the right.
//
// ⚠ **A ROW IS DRAWN ONLY FOR A KEY THE COMMIT REPORTED.** The server leaves a
// key out when it did not happen (`what_happened`'s own rule: *"absent, never
// zero"*), so a move-in with no co-owners shows no co-owner row rather than
// *0 added*. Nothing here re-reads the product to fill a row.
//
// ⚠ **WHAT THE DRAWING SHOWS AND THE ANSWER CANNOT, AND IS THEREFORE NOT
// DRAWN** (rule 37 — a figure in a wireframe is an illustration):
//   · the opening reads row lists each meter's value WITH its unit in the
//     image (*W-5000 1,031 kgal*); the answer's posted reads carry no unit, so
//     the row states how many were recorded (hard rule 3 — never a quantity
//     without its unit);
//   · the plan in the account row is a LINK in the image; this prints the
//     plan's name and version as the account carries them, unlinked;
//   · the customer number is a link in the image; there is no customer page
//     to link to, so it is text.
//
// ⚠ **THE SERVER'S REMAINING WARNINGS STILL SHOW, UNDER THE PANEL.** Image 48
// draws none, but each is a true fact about this move-in (e.g. *"No deposit
// was carried forward."*); the two FALSE ones are no longer served
// (`DEF-CUS-9702`, P1.21). Hiding a true warning because the illustration had
// none would be the drawing outvoting the record.

import { ButtonLink, Button } from "@/components/Button";
import { CheckList } from "@/components/CheckList";
import type { CheckRow } from "@/components/CheckList";
import { formatDate } from "@/components/DateCell";
import type { RegionalDateFormat } from "@/components/DateCell";
import { formatMoney } from "@/components/MoneyCell";
import { PageHeader } from "@/components/PageHeader";
import { Panel } from "@/components/Panel";
import { StatusPill } from "@/components/StatusPill";
import type { AccountMoveInResult } from "@/api/endpoints";
import type { Translator } from "@/features/tenancy/settingsShared";
import { useTenantPath } from "@/routing/tenantPath";

import { WarningList, accountDetailPath } from "../customersShared";
import { moveRecordPath } from "../MoveRecordPage";
import { MOVE_INS_TAB_PATH } from "../moveShared";

/** One item of `what_happened.items` (§9.FLOW, P1.21). Every fact is optional:
 *  the server sends what the commit reported and nothing else. */
export interface WhatHappenedItem {
  key: string;
  outcome?: string | null;
  customer_no?: string | null;
  account_no?: string | null;
  count?: number;
  starts_on?: string | null;
  posted?: number;
  now?: string;
  was?: string;
  declined?: boolean;
  orders?: { order_no: string | null; assignee: string | null }[];
  detail?: unknown;
  queued?: number;
  planned?: number;
}

/** The keys the four-step Complete adds to the old answer (§9.FLOW, §9.MONEY). */
export interface MoveInCompletedResult extends AccountMoveInResult {
  request_no?: string | null;
  what_happened?: {
    move_no: string | null;
    request_no: string | null;
    items: WhatHappenedItem[];
  };
}

interface FeesDetail {
  lines?: { code?: string | null }[];
  total?: string | null;
  currency?: string | null;
}
interface PaymentDetail {
  mode?: string;
  currency?: string | null;
  amount_paid?: string | null;
  on_first_bill?: string | null;
  receipt_no?: string | null;
}

function money(
  amount: string | null | undefined,
  currency: string | null | undefined,
): string | null {
  if (amount === null || amount === undefined || currency === null || currency === undefined) {
    return null;
  }
  return formatMoney(amount, currency);
}

/** The ✓ rows, in the server's order. Pure, so a test can read it. */
export function whatHappenedRows(
  result: MoveInCompletedResult,
  t: Translator,
  fmt: { timeZone: string; dateFormat: RegionalDateFormat },
): CheckRow[] {
  const rows: CheckRow[] = [];
  const add = (id: string, fact: string | null) => {
    if (fact === null || fact === "") return;
    rows.push({ id, label: t(`customers.moveIn.completed.row.${id}`), state: "ok", fact });
  };
  // `DEF-CUS-10196` — the agreements THIS move-in opened: a reopened account
  // (CR-181-BRC10) also carries its earlier tenancy's, already ended.
  const services = result.service_agreements
    .filter((agreement) => agreement.ended_on === null || agreement.ended_on === undefined)
    .map((agreement) => agreement.service)
    .filter((code): code is string => code !== null)
    .map((code) => t(`rating.service.${code}`, { defaultValue: code }));
  for (const item of result.what_happened?.items ?? []) {
    switch (item.key) {
      case "customer": {
        const number = item.customer_no ?? result.customer_no ?? "";
        const name = result.customer?.display_name ?? "";
        const verb =
          item.outcome === "linked"
            ? t("customers.moveIn.completed.customerLinked", { number })
            : item.outcome === "created"
              ? t("customers.moveIn.completed.customerCreated", { number })
              : null;
        add("customer", verb === null ? null : [verb, name].filter((part) => part).join(" · "));
        break;
      }
      case "account": {
        const plan = result.unit_plan;
        const planText =
          plan?.name == null
            ? ""
            : plan.version == null
              ? plan.name
              : t("customers.moveIn.completed.planVersion", {
                  plan: plan.name,
                  version: plan.version,
                });
        add(
          "account",
          [
            t("customers.moveIn.completed.accountOpened", {
              number: item.account_no ?? result.account_no ?? "",
            }),
            planText,
          ]
            .filter((part) => part)
            .join(" · "),
        );
        break;
      }
      case "services":
        add(
          "services",
          item.starts_on
            ? t("customers.moveIn.completed.servicesStart", {
                services: services.join(" · "),
                date: formatDate(item.starts_on, fmt.timeZone, fmt.dateFormat),
              })
            : services.join(" · "),
        );
        break;
      case "opening_reads":
        add(
          "opening_reads",
          t("customers.moveIn.completed.readsRecorded", { count: item.posted ?? 0 }),
        );
        break;
      case "unit":
        add(
          "unit",
          t("customers.moveIn.completed.unitNow", {
            unit: result.unit_label ?? result.premise ?? "",
            was: t(`customers.moveIn.completed.occupancy.${item.was ?? "vacant"}`),
            now: t(`customers.moveIn.completed.occupancy.${item.now ?? "occupied"}`),
          }),
        );
        break;
      // ⚠ A ✓ row says something HAPPENED, so a co-owner or document count of
      // 0 draws no row: *"0 added"* ticked would claim an act nobody did.
      case "co_owners":
        add(
          "co_owners",
          (item.count ?? 0) > 0
            ? t("customers.moveIn.completed.coOwnersAdded", { count: item.count })
            : null,
        );
        break;
      case "documents":
        add(
          "documents",
          (item.count ?? 0) > 0
            ? t("customers.moveIn.completed.documentsFiled", { count: item.count })
            : null,
        );
        break;
      case "work_orders": {
        const orders = (item.orders ?? [])
          .map((order) => [order.order_no, order.assignee].filter((part) => part).join(" · "))
          .filter((line) => line !== "");
        add(
          "work_orders",
          orders.length > 0
            ? orders.join(", ")
            : item.declined
              ? t("customers.moveIn.completed.visitNotNeeded")
              : null,
        );
        break;
      }
      case "fees": {
        const fees = (item.detail ?? {}) as FeesDetail;
        const total = money(fees.total, fees.currency);
        const codes = (fees.lines ?? []).map((line) => line.code).filter((code) => code);
        add(
          "fees",
          total === null
            ? null
            : [t("customers.moveIn.completed.feesPosted", { total }), codes.join(", ")]
                .filter((p) => p)
                .join(" · "),
        );
        break;
      }
      case "payment": {
        const payment = (item.detail ?? {}) as PaymentDetail;
        if (payment.mode === "add_to_bill") {
          const onBill = money(payment.on_first_bill, payment.currency);
          add(
            "payment",
            onBill === null
              ? null
              : t("customers.moveIn.completed.paymentOnBill", { amount: onBill }),
          );
        } else {
          const paid = money(payment.amount_paid, payment.currency);
          add(
            "payment",
            paid === null
              ? null
              : payment.receipt_no
                ? t("customers.moveIn.completed.paymentReceipt", {
                    amount: paid,
                    receipt: payment.receipt_no,
                  })
                : t("customers.moveIn.completed.paymentReceived", { amount: paid }),
          );
        }
        break;
      }
      case "messages":
        add(
          "messages",
          [
            t("customers.moveIn.completed.messagesQueued", { count: item.queued ?? 0 }),
            (item.planned ?? 0) > 0
              ? t("customers.moveIn.completed.messagesPlanned", { count: item.planned ?? 0 })
              : "",
          ]
            .filter((part) => part)
            .join(" · "),
        );
        break;
      default:
        // A key this screen does not know (e.g. `deposit`, whose figure the
        // Fees row already carries) is not invented into a row.
        break;
    }
  }
  return rows;
}

export function MoveInCompleted(props: {
  result: MoveInCompletedResult;
  t: Translator;
  timeZone: string;
  dateFormat: RegionalDateFormat;
  /** Clears the wizard for the next household (the page stays mounted). */
  onStartAnother: () => void;
}) {
  const { result, t } = props;
  const tenantPath = useTenantPath();
  const moveNo = result.what_happened?.move_no ?? null;
  const requestNo = result.what_happened?.request_no ?? result.request_no ?? null;
  const who = [result.customer?.display_name, result.unit_label ?? result.premise]
    .filter((part) => part)
    .join(" · ");
  const sub = [
    requestNo === null ? null : t("customers.moveIn.completed.fromRequest", { request: requestNo }),
    who,
  ]
    .filter((part) => part)
    .join(" · ");
  const rows = whatHappenedRows(result, t, {
    timeZone: props.timeZone,
    dateFormat: props.dateFormat,
  });
  return (
    <div className="flex flex-col gap-5" data-screen="move-in-completed">
      <PageHeader
        backTo={{ to: tenantPath(MOVE_INS_TAB_PATH), label: t("customers.accounts.tab.moveIns") }}
        title={t("customers.moveIn.completed.title")}
        status={
          <span className="flex flex-wrap items-baseline gap-2" data-move-in-completed-id="">
            <StatusPill tone="success">{t("customers.moveIn.completed.status")}</StatusPill>
            {moveNo === null ? null : <span className="font-semibold text-text">{moveNo}</span>}
            {sub === "" ? null : <span className="text-sm text-neutral-700">{sub}</span>}
          </span>
        }
      />

      <Panel as="section">
        <h3>{t("customers.moveIn.completed.whatHappened")}</h3>
        <CheckList
          rows={rows}
          label={t("customers.moveIn.completed.whatHappened")}
          stateLabels={{
            ok: t("customers.moveIn.completed.state.ok"),
            bad: t("customers.moveIn.completed.state.bad"),
            noted: t("customers.moveIn.completed.state.noted"),
            notReached: t("customers.moveIn.completed.state.notReached"),
          }}
        />
      </Panel>

      {result.warnings.length > 0 ? (
        <WarningList
          warnings={result.warnings}
          title={t("customers.account.warningsTitle")}
          t={t}
        />
      ) : null}

      <div
        className="flex flex-wrap items-center gap-2 border-t border-t-divider pt-4"
        data-move-in-completed-actions=""
      >
        <Button className="mr-auto" onClick={props.onStartAnother}>
          {t("customers.moveIn.completed.startAnother")}
        </Button>
        {moveNo === null ? null : (
          <ButtonLink to={tenantPath(moveRecordPath(moveNo))}>
            {t("customers.moveIn.completed.openMoveIn")}
          </ButtonLink>
        )}
        <ButtonLink variant="primary" to={tenantPath(accountDetailPath(result.id))}>
          {t("customers.moveIn.completed.openAccount")}
        </ButtonLink>
      </div>
    </div>
  );
}
