// ── Trace ──────────────────────────────────────────────
// Defect:   DEF-PAY-10706 — a master account could not pay a unit's bill, and
//           one cheque could not be split across accounts, from ANY screen: the
//           four server routes (CR-059 CS-12 / CS-27) had no screen calling them
//           (tester L1-08, Grand Vista AC-2026-00618).
// Ruling:   PO 2026-10-30 — *"Eight open payment questions answered"*, Q4 = A:
//           build the "Pay for…" screen AS IN THE MOCK-UP, all six pieces
//           including the "Pay units" button
//           (https://claude.ai/artifact/Y99Ca4jBKMwMnuy5AtmLWf, rendered to
//           images and built from them — B14 rule 42).
//           2026-09-01 BR-PAY-1126..1130 — a master may pay its units' bills;
//           money no unit bill absorbs is the MASTER's credit; a split must sum
//           EXACTLY or nothing commits.
// Rules:    hard rule 2 (money as decimal strings; exact BigInt sums, never a
//           float — `sumDecimalStrings`) · B14 rules 21 (Tailwind; on the
//           Route B ledger), 31 (no database id on screen — numbers and names
//           only), 33 (copy caps), 43 (components), 44 (our UI standard builds
//           what the drawing arranges)
// Tests:    src/features/payments/payForSeveral.dom.test.tsx ·
//           06-backend/tests/test_def_pay_10706_pay_for_screen_body.py
// ───────────────────────────────────────────────────────
/**
 * **"Pay for: Several accounts"** — one cheque, aimed bill by bill across a
 * landlord's units (or one customer's accounts), with a row for the payer's
 * own account where the leftover becomes credit.
 *
 * WHAT THE MOCK-UP DRAWS, top to bottom, and where each piece lives here:
 *   1  the *Pay for* switch            → `PayForSwitch` (the kit's
 *                                         `SegmentedField`), handed to BOTH
 *                                         forms as a slot under the counter
 *                                         banner, so it sits where it is drawn
 *   2  bills grouped by unit, a box    → `PayForAllocationTable`
 *      per bill
 *   3  *Left to allocate* to $0.00     → `LeftToAllocate`; the commit is
 *      before Record payment works       BLOCKED until it is exactly zero
 *   4  the payer's own row — leftover  → the last row of the table, posted as
 *      becomes credit                    `apply_to: carry_credit`
 *   5  counter banner + "what this     → `RecordCounterBanner` (the one-account
 *      will do"                          form's own) + `ConsequenceBox`
 *   6  *Pay units* on a master        → `AccountDetailPage`, navigating here
 *                                         with the master in router STATE
 *                                         (`PayForState`) — never in the URL
 *
 * ⚠ **WHICH ROUTE IS CALLED IS DECIDED BY THE PAYER'S KIND, NOT BY A CHOICE.**
 * A MASTER pays its units through `POST /accounts/{id}/premises-payments`
 * (CS-27: the master carries the TENDER and no payment entry except its
 * leftover; a unit row that would leave money as a tenant's credit is refused
 * whole — BR-PAY-1130). Any other account pays for its CUSTOMER's accounts
 * through `POST /customers/{id}/payments` (CS-12). Both refuse a split that
 * does not sum exactly and a hand tender with no till open; the screen blocks
 * the first before sending and shows the server's sentence for the second.
 *
 * ⚠ **EACH ACCOUNT IS ONE PART, EACH BOX ONE TARGET.** The boxes are per BILL
 * (a unit with an older bill shows two), and the server's parts are per
 * ACCOUNT, so an account's boxes are summed into one part with
 * `apply_to: "split"` and one target per bill. A box left at 0.00 is not sent.
 *
 * ⚠ **THE MASTER'S OWN OPEN BILLS ARE NOT LISTED** (the mock-up draws units
 * and the credit row only). The credit row posts `carry_credit`, so a leftover
 * is held as the landlord's credit rather than silently meeting their hallway
 * bill. Recorded in the decision log as this lane's judgment.
 */
import { useMemo, useState } from "react";
import type { ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { z } from "zod";

import type { ApiClient, ApiResponse } from "@/api/client";
import { formErrorEnvelope, isApiError } from "@/api/client";
import { getAccountDetail } from "@/api/endpoints";
import type {
  OpenBillPosition,
  OpenBillRow,
  PaymentMethodOption,
  RecordedPayment,
} from "@/api/endpoints";
import { Button } from "@/components/Button";
import { formatDate } from "@/components/DateCell";
import type { RegionalDateFormat } from "@/components/DateCell";
import { ConsequenceBox } from "@/components/ConsequenceBox";
import { FormPage, SegmentedField, SelectField, TextField } from "@/components/FormModal";
import type { FormSubmitOutcome } from "@/components/FormModal";
import { formatMoney, formatMoneyInput } from "@/components/MoneyCell";
import { PlainTable } from "@/components/Surfaces";
import type { Translator } from "@/features/tenancy/settingsShared";

import { RecordCounterBanner } from "./CounterDoors";
import {
  AccountPickerFields,
  methodOptions,
  sumDecimalStrings,
  useAccountSearch,
} from "./paymentsShared";

// ── The wire ───────────────────────────────────────────────────────────────

/** `GET /accounts/{id}/premises-position` — `payments.premises_position`. */
export interface PremisesPosition {
  payer: {
    id: string;
    account_no: string | null;
    name: string | null;
    own_total_open: string | null;
    own_bills: OpenBillRow[];
  };
  units: {
    unit_id: string | null;
    label: string | null;
    accounts: (OpenBillPosition & { customer_name?: string | null })[];
  }[];
  unit_count: number;
  units_total_open: string | null;
}

/** `GET /customers/{id}/open-bills` — `payments.customer_position`. */
export interface CustomerOpenBills {
  customer: { id: string; customer_no: string | null; display_name: string | null };
  accounts: OpenBillPosition[];
  total_open: string | null;
  currency: string | null;
}

/** One part of the cheque, as both POST routes take it. */
export interface TenderPartBody {
  account_id: string;
  amount: string;
  apply_to: "split" | "carry_credit";
  targets?: { invoice_number: string; amount: string }[];
}

export interface TenderBody {
  amount: string;
  posted_at: string;
  method: string | null;
  reference: string | null;
  memo: string | null;
  idempotency_key: string;
  parts: TenderPartBody[];
}

/** `_recorded_tender_dict` — `payments` is in the order the parts were sent. */
export interface RecordedTender {
  created: boolean;
  amount: string;
  currency: string;
  reference: string | null;
  part_count: number;
  payments: RecordedPayment[];
}

function requireData<T>(response: ApiResponse<T>): T {
  if (response.data === null) {
    throw new Error(`empty ${response.status} body where the contract promises one`);
  }
  return response.data;
}

export async function getPremisesPosition(
  client: ApiClient,
  accountId: string,
): Promise<PremisesPosition> {
  return requireData(
    await client.get<PremisesPosition>(
      `/accounts/${encodeURIComponent(accountId)}/premises-position`,
    ),
  );
}

export async function getCustomerOpenBills(
  client: ApiClient,
  customerId: string,
): Promise<CustomerOpenBills> {
  return requireData(
    await client.get<CustomerOpenBills>(`/customers/${encodeURIComponent(customerId)}/open-bills`),
  );
}

export async function postTender(
  client: ApiClient,
  route: PayForRoute,
  body: TenderBody,
): Promise<RecordedTender> {
  const path =
    route.kind === "premises"
      ? `/accounts/${encodeURIComponent(route.id)}/premises-payments`
      : `/customers/${encodeURIComponent(route.id)}/payments`;
  return requireData(await client.post<RecordedTender>(path, body));
}

// ── The model the table draws ─────────────────────────────────────────────

export type PayForRoute = { kind: "premises" | "customer"; id: string };

/** One account's group of bills — a unit (premises) or an account (customer). */
export interface PayForGroup {
  accountId: string;
  accountNo: string | null;
  /** The unit's label on a premises; null on a customer's accounts. */
  unit: string | null;
  holder: string | null;
  bills: OpenBillRow[];
}

export interface PayForPosition {
  route: PayForRoute;
  currency: string | null;
  groups: PayForGroup[];
  /** Where a leftover is held as credit: the master, or the picked account. */
  creditAccount: { id: string; accountNo: string | null };
}

/** The master's units that have something open, in the served order. */
export function fromPremises(position: PremisesPosition): PayForPosition {
  const groups: PayForGroup[] = [];
  let currency: string | null = null;
  for (const unit of position.units) {
    for (const account of unit.accounts) {
      currency = currency ?? account.currency;
      if (account.bills.length === 0) continue;
      groups.push({
        accountId: account.account_id,
        accountNo: account.account_no,
        unit: unit.label,
        holder: account.customer_name ?? null,
        bills: account.bills,
      });
    }
  }
  return {
    route: { kind: "premises", id: position.payer.id },
    currency,
    groups,
    creditAccount: { id: position.payer.id, accountNo: position.payer.account_no },
  };
}

/** One customer's accounts that have something open. */
export function fromCustomer(
  position: CustomerOpenBills,
  picked: { id: string; accountNo: string | null },
): PayForPosition {
  return {
    route: { kind: "customer", id: position.customer.id },
    currency: position.currency,
    groups: position.accounts
      .filter((account) => account.bills.length > 0)
      .map((account) => ({
        accountId: account.account_id,
        accountNo: account.account_no,
        unit: null,
        holder: position.customer.display_name,
        bills: account.bills,
      })),
    creditAccount: picked,
  };
}

/** Keyed by bill NUMBER (never its id — B14 rule 31). */
export type BillAmounts = Readonly<Record<string, string>>;

/** Each box starts at what its bill still owes — the mock-up's first state. */
export function owedAmounts(groups: readonly PayForGroup[]): BillAmounts {
  const out: Record<string, string> = {};
  for (const group of groups) {
    for (const bill of group.bills) out[bill.number] = formatMoneyInput(bill.open_balance);
  }
  return out;
}

const isBlank = (value: string) => value.trim() === "";

/** `amount − Σ boxes − credit`, exactly, or null when any figure is not a number. */
export function leftToAllocate(amount: string, boxes: BillAmounts, credit: string): string | null {
  if (isBlank(amount)) return null;
  const typed = [...Object.values(boxes), credit].filter((value) => !isBlank(value));
  return sumDecimalStrings([
    amount.trim(),
    ...typed.map((value) =>
      value.trim().startsWith("-") ? value.trim().slice(1) : `-${value.trim()}`,
    ),
  ]);
}

const isPositive = (value: string) => {
  const sum = sumDecimalStrings([value.trim()]);
  return sum !== null && !sum.startsWith("-") && /[1-9]/.test(sum);
};

/**
 * The parts the server takes: one per account with money on it, its boxes as
 * `split` targets; the credit row as `carry_credit` on the credit account — or,
 * when that account also has bills here (a customer's own account), added to
 * its part, where what no target takes carries as credit.
 */
export function partsFor(
  position: PayForPosition,
  boxes: BillAmounts,
  credit: string,
): TenderPartBody[] {
  const parts: TenderPartBody[] = [];
  for (const group of position.groups) {
    const targets = group.bills
      .filter((bill) => isPositive(boxes[bill.number] ?? ""))
      .map((bill) => ({ invoice_number: bill.number, amount: (boxes[bill.number] ?? "").trim() }));
    if (targets.length === 0) continue;
    const amount = sumDecimalStrings(targets.map((target) => target.amount)) ?? "0";
    parts.push({ account_id: group.accountId, amount, apply_to: "split", targets });
  }
  if (isPositive(credit)) {
    const own = parts.find((part) => part.account_id === position.creditAccount.id);
    if (own !== undefined) {
      own.amount = sumDecimalStrings([own.amount, credit.trim()]) ?? own.amount;
    } else {
      parts.push({
        account_id: position.creditAccount.id,
        amount: credit.trim(),
        apply_to: "carry_credit",
      });
    }
  }
  return parts;
}

// ── Router state for the "Pay units" door ─────────────────────────────────

/** What *Pay units* hands Record payment — in router STATE, never the URL. */
export interface PayForState {
  payFor: { id: string; accountNo: string | null; kind: string };
}

export function payForFromState(state: unknown): PayForState["payFor"] | null {
  if (state === null || typeof state !== "object" || !("payFor" in state)) return null;
  const payFor = (state as PayForState).payFor;
  return payFor && typeof payFor.id === "string" ? payFor : null;
}

// ── Pieces ─────────────────────────────────────────────────────────────────

export type PayForMode = "one" | "several";

/** Piece 1 — *Pay for: One account · Several accounts*. */
export function PayForSwitch(props: { value: PayForMode; onChange: (mode: PayForMode) => void }) {
  const { t } = useTranslation();
  return (
    <SegmentedField
      id="pay_for"
      label={t("payments.payFor.label")}
      value={props.value}
      onChange={(next) => props.onChange(next === "several" ? "several" : "one")}
      options={[
        { value: "one", label: t("payments.payFor.one") },
        { value: "several", label: t("payments.payFor.several") },
      ]}
    />
  );
}

const AMOUNT_INPUT =
  "w-32 border border-field-border bg-field-fill px-2 py-1.5 text-right tabular-nums " +
  "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-info-700";

/** Piece 2 + 4 — bills grouped by unit, a box per bill, and the credit row. */
export function PayForAllocationTable(props: {
  position: PayForPosition;
  boxes: BillAmounts;
  onBox: (billNumber: string, value: string) => void;
  credit: string;
  onCredit: (value: string) => void;
  /** The tenant's regional pair — an issue date reads as every date does. */
  timeZone: string;
  dateFormat: RegionalDateFormat;
}) {
  const { t } = useTranslation();
  const { position } = props;
  const money = (value: string | null) =>
    value === null || position.currency === null ? "" : formatMoney(value, position.currency);
  const creditNo = position.creditAccount.accountNo ?? "";
  return (
    <div className="overflow-x-auto" data-pay-for-table="">
      <PlainTable className="min-w-155 [&_[data-num]]:text-right">
        <thead>
          <tr>
            <th scope="col">{t("payments.openBills.col.pick")}</th>
            <th scope="col">{t("payments.openBills.col.bill")}</th>
            <th scope="col">{t("payments.openBills.col.issued")}</th>
            <th scope="col" data-num="">
              {t("payments.openBills.col.issuedFor")}
            </th>
            <th scope="col" data-num="">
              {t("payments.openBills.col.owes")}
            </th>
          </tr>
        </thead>
        <tbody>
          {position.groups.map((group) => (
            <GroupRows key={group.accountId} group={group}>
              {group.bills.map((bill) => (
                <tr key={bill.number}>
                  <td>
                    <input
                      type="text"
                      inputMode="decimal"
                      className={AMOUNT_INPUT}
                      aria-label={t("payments.openBills.amountFor", { number: bill.number })}
                      value={props.boxes[bill.number] ?? ""}
                      onChange={(event) => props.onBox(bill.number, event.target.value)}
                    />
                  </td>
                  <td>{bill.number}</td>
                  <td>
                    {bill.issued_on
                      ? formatDate(bill.issued_on, props.timeZone, props.dateFormat)
                      : ""}
                  </td>
                  <td data-num="" className="tabular-nums">
                    {money(bill.total)}
                  </td>
                  <td data-num="" className="tabular-nums">
                    {money(bill.open_balance)}
                  </td>
                </tr>
              ))}
            </GroupRows>
          ))}
          <tr className="bg-neutral-100" data-pay-for-credit-row="">
            <td>
              <input
                type="text"
                inputMode="decimal"
                className={AMOUNT_INPUT}
                aria-label={t("payments.payFor.creditFor", { account: creditNo })}
                value={props.credit}
                onChange={(event) => props.onCredit(event.target.value)}
              />
            </td>
            <td colSpan={4}>
              <span className="font-semibold">
                {t("payments.payFor.ownAccount", { account: creditNo })}
              </span>
              <span className="text-neutral-700"> · {t("payments.payFor.leftoverCredit")}</span>
            </td>
          </tr>
        </tbody>
      </PlainTable>
    </div>
  );
}

function GroupRows(props: { group: PayForGroup; children: ReactNode }) {
  const { group } = props;
  const head = [group.unit, group.accountNo]
    .filter((part) => part !== null && part !== "")
    .join(" · ");
  return (
    <>
      <tr className="bg-surface" data-pay-for-group="">
        <td colSpan={5}>
          <span className="font-semibold">{head}</span>
          {group.holder ? <span className="text-neutral-700"> · {group.holder}</span> : null}
        </td>
      </tr>
      {props.children}
    </>
  );
}

/** Piece 3 — the running remainder, green at exactly $0.00. */
export function LeftToAllocate(props: { left: string | null; currency: string | null }) {
  const { t } = useTranslation();
  const zero = props.left !== null && !/[1-9]/.test(props.left);
  const over = props.left !== null && props.left.startsWith("-") && !zero;
  const tone = zero
    ? "bg-success-100 text-success-700"
    : over
      ? "bg-danger-100 text-danger-700"
      : "bg-surface text-text";
  return (
    <p
      className={`flex flex-wrap items-center justify-between gap-3 px-3 py-2.5 font-semibold tabular-nums ${tone}`}
      data-left-to-allocate={zero ? "zero" : over ? "over" : "open"}
      role="status"
    >
      <span>{t("payments.payFor.left")}</span>
      <span>
        {props.left === null || props.currency === null
          ? ""
          : formatMoney(props.left, props.currency)}
      </span>
    </p>
  );
}

// ── The form ───────────────────────────────────────────────────────────────

/** The payer the switch is aimed at, as the picker or the door names it. */
interface Payer {
  id: string;
  accountNo: string | null;
  kind: string;
}

function usePayForPosition(client: ApiClient, payer: Payer | null) {
  return useQuery({
    queryKey: ["payments", "pay-for", payer?.id ?? "", payer?.kind ?? ""],
    enabled: payer !== null,
    retry: false,
    queryFn: async (): Promise<PayForPosition | "no_customer"> => {
      if (payer === null) throw new Error("no payer");
      if (payer.kind === "master") {
        return fromPremises(await getPremisesPosition(client, payer.id));
      }
      const detail = await getAccountDetail(payer.id, client);
      if (detail.customer === null) return "no_customer";
      return fromCustomer(await getCustomerOpenBills(client, detail.customer.id), {
        id: payer.id,
        accountNo: payer.accountNo,
      });
    },
  });
}

const schema = z.object({ payer: z.string().min(1), amount: z.string().min(1) });

export function PayForSeveralForm(props: {
  client: ApiClient;
  methods: readonly PaymentMethodOption[];
  today: string;
  timeZone: string;
  dateFormat: RegionalDateFormat;
  /** Piece 1, drawn under the counter banner exactly as on the one-account form. */
  modeSwitch: ReactNode;
  /** *Pay units* — the master already chosen. */
  initialPayer: Payer | null;
  onCancel: () => void;
  onRecorded: (tender: RecordedTender, labels: string[]) => void;
}) {
  const { t } = useTranslation();
  const translate: Translator = (key, params) => t(key, params);
  const [term, setTerm] = useState(props.initialPayer?.accountNo ?? "");
  const [payer, setPayer] = useState<Payer | null>(props.initialPayer);
  const [amount, setAmount] = useState("");
  const [method, setMethod] = useState("");
  const [reference, setReference] = useState("");
  const [memo, setMemo] = useState("");
  const [boxes, setBoxes] = useState<BillAmounts>({});
  const [credit, setCredit] = useState("0.00");
  const [submitToken] = useState(() => crypto.randomUUID());
  const search = useAccountSearch(term, props.client, "pay-for-picker");
  const read = usePayForPosition(props.client, payer);
  const position = read.data !== undefined && read.data !== "no_customer" ? read.data : null;

  // A newly read position re-seeds every box at what its bill owes — once per
  // read, adjusted during render (React's derived-state pattern), so a box the
  // clerk has typed into is never overwritten by a re-render.
  const [seededAt, setSeededAt] = useState(0);
  if (position !== null && read.dataUpdatedAt !== seededAt) {
    setSeededAt(read.dataUpdatedAt);
    setBoxes(owedAmounts(position.groups));
    setCredit("0.00");
  }

  const left = useMemo(() => leftToAllocate(amount, boxes, credit), [amount, boxes, credit]);
  const ready = position !== null && left !== null && !/[1-9]/.test(left) && isPositive(amount);
  const parts = position === null ? [] : partsFor(position, boxes, credit);
  const currency = position?.currency ?? null;

  const owes =
    position === null
      ? null
      : sumDecimalStrings(
          position.groups.flatMap((g) => g.bills.map((b) => b.open_balance ?? "0")),
        );
  const billCount = position?.groups.reduce((n, g) => n + g.bills.length, 0) ?? 0;

  let blocked: string | undefined;
  if (!ready) {
    blocked =
      left !== null && left.startsWith("-") && /[1-9]/.test(left)
        ? t("payments.payFor.overAllocated")
        : t("payments.payFor.allocateRest");
  }

  const methodName = props.methods.find((m) => m.code === method)?.name ?? null;

  async function handleSubmit(): Promise<FormSubmitOutcome> {
    if (position === null)
      return { ok: false, error: { code: "", message_key: "payments.payFor.allocateRest" } };
    try {
      const recorded = await postTender(props.client, position.route, {
        amount: amount.trim(),
        posted_at: props.today,
        method: method === "" ? null : method,
        reference: reference.trim() === "" ? null : reference.trim(),
        memo: memo.trim() === "" ? null : memo.trim(),
        idempotency_key: submitToken,
        parts,
      });
      const labels = parts.map((part) => {
        const group = position.groups.find((g) => g.accountId === part.account_id);
        return group?.accountNo ?? position.creditAccount.accountNo ?? "";
      });
      props.onRecorded(recorded, labels);
      return { ok: true };
    } catch (error) {
      if (isApiError(error)) return { ok: false, error: formErrorEnvelope(error) };
      return { ok: false, error: { code: "", message_key: "api.error.unexpected" } };
    }
  }

  return (
    <FormPage
      schema={schema}
      values={{ payer: payer?.id ?? "", amount }}
      submitLabel={t("payments.form.submit")}
      onSubmit={handleSubmit}
      onCancel={props.onCancel}
      commitBlocked={payer === null ? undefined : blocked}
    >
      <RecordCounterBanner
        client={props.client}
        dateFormat={props.dateFormat}
        methodCode={method === "" ? null : method}
      />
      {props.modeSwitch}
      <div className="grid grid-cols-2 gap-5 max-md:grid-cols-1">
        <AccountPickerFields
          searchLabel={t("payments.form.accountSearch")}
          accountLabel={t("payments.payFor.payer")}
          term={term}
          onTermChange={setTerm}
          search={search}
          value={payer?.id ?? ""}
          startClosed={props.initialPayer !== null}
          onChange={(id) => {
            const row = search.matches.find((match) => match.id === id);
            setPayer(
              id === "" ? null : { id, accountNo: row?.account_no ?? null, kind: row?.kind ?? "" },
            );
          }}
          t={translate}
        />
        <TextField
          id="amount"
          label={t("payments.form.amount")}
          value={amount}
          onChange={setAmount}
          numeric
          required
        />
        <SelectField
          id="method"
          label={t("payments.form.method")}
          value={method}
          onChange={setMethod}
          options={methodOptions(props.methods)}
          placeholder={t("payments.form.methodPlaceholder")}
        />
        <TextField
          id="confirmation"
          label={t("payments.form.confirmation")}
          value={reference}
          onChange={setReference}
        />
      </div>
      <TextField id="memo" label={t("payments.form.memo")} value={memo} onChange={setMemo} />

      {payer !== null && read.isPending ? (
        <p className="text-neutral-700">{t("payments.payFor.loading")}</p>
      ) : null}
      {read.isError ? <p role="alert">{t("payments.payFor.failed")}</p> : null}
      {read.data === "no_customer" ? <p role="alert">{t("payments.payFor.noCustomer")}</p> : null}

      {position !== null ? (
        <>
          <p className="font-semibold" data-pay-for-owes="">
            {owes !== null && currency !== null
              ? t("payments.payFor.owes", {
                  amount: formatMoney(owes, currency),
                  bills: t("payments.payFor.bills", { count: billCount }),
                  accounts: t("payments.payFor.accounts", { count: position.groups.length }),
                })
              : null}
          </p>
          <PayForAllocationTable
            position={position}
            boxes={boxes}
            onBox={(number, value) => setBoxes({ ...boxes, [number]: value })}
            credit={credit}
            onCredit={setCredit}
            timeZone={props.timeZone}
            dateFormat={props.dateFormat}
          />
          <LeftToAllocate left={left} currency={currency} />
          {currency !== null && isPositive(amount) ? (
            <ConsequenceBox
              tone="check"
              tag={t("payments.consequence.tag")}
              data-consequence="pay-for"
              title={t("payments.payFor.willTitle", {
                count: parts.length,
                amount: formatMoney(amount.trim(), currency),
              })}
              body={
                <>
                  {methodName !== null
                    ? reference.trim() !== ""
                      ? t("payments.payFor.willFromRef", {
                          method: methodName,
                          reference: reference.trim(),
                        })
                      : t("payments.payFor.willFrom", { method: methodName })
                    : null}{" "}
                  {isPositive(credit)
                    ? t("payments.payFor.willCredit", {
                        amount: formatMoney(credit.trim(), currency),
                        account: position.creditAccount.accountNo ?? "",
                      })
                    : null}{" "}
                  {ready ? t("payments.payFor.ready") : null}
                </>
              }
            />
          ) : null}
        </>
      ) : null}
    </FormPage>
  );
}

/** What was recorded — one line per payment, by its PY- number. */
export function PayForRecorded(props: {
  tender: RecordedTender;
  labels: readonly string[];
  onDone: () => void;
}) {
  const { t } = useTranslation();
  const { tender } = props;
  return (
    <div
      className="grid gap-3 bg-success-100 p-4 text-success-700"
      role="status"
      data-pay-for-recorded=""
    >
      <p className="font-semibold">
        {t("payments.payFor.recorded", {
          count: tender.part_count,
          amount: formatMoney(tender.amount, tender.currency),
        })}
      </p>
      <PlainTable className="text-text [&_[data-num]]:text-right">
        <thead>
          <tr>
            <th scope="col">{t("payments.payFor.col.account")}</th>
            <th scope="col">{t("payments.payFor.col.payment")}</th>
            <th scope="col" data-num="">
              {t("payments.payFor.col.amount")}
            </th>
          </tr>
        </thead>
        <tbody>
          {tender.payments.map((payment, index) => (
            <tr key={payment.id}>
              <td>{props.labels[index] ?? ""}</td>
              <td>{payment.payment_no ?? ""}</td>
              <td data-num="" className="tabular-nums">
                {formatMoney(payment.amount, payment.currency)}
              </td>
            </tr>
          ))}
        </tbody>
      </PlainTable>
      <div>
        <Button variant="secondary" onClick={props.onDone}>
          {t("payments.form.back")}
        </Button>
      </div>
    </div>
  );
}
