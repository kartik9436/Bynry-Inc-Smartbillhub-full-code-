// ── Trace ──────────────────────────────────────────────
// Change:   DEF-CUS-10041 (PO 2026-10-11) — New request step 3's payment panel:
//           *Payment details*, a Pay now / Pay later choice, and the inputs each
//           payment method actually needs. PO, verbatim: *"each method should
//           have relavant method ... user can make the payment now or user can
//           make the payment later ; if now take the payment detail if payment
//           later user should move on"*. The per-method table was put to the PO
//           the same turn and accepted by their go (decision log 2026-10-11).
// Rules:    BR-CUS-090 / OQ-CUS-12624 (the fee is paid in full or waived — so
//           the amount is the total and is not typed) · OQ-CUS-12617 (Pay later
//           leaves Approve off until paid or waived) · never the full card
//           number, expiry or security code · B14 rules 21, 33, 43
// ───────────────────────────────────────────────────────
import { useQuery } from "@tanstack/react-query";

import type { ApiClient } from "@/api/client";
import { getPayments } from "@/api/endpoints";
import type { PaymentMethodOption } from "@/api/endpoints";
import type { RegionalDateFormat } from "@/components/DateCell";
import { DatePickerField, SelectField, TextField } from "@/components/FormModal";
import { formatMoney } from "@/components/MoneyCell";
import { RecordCounterBanner } from "@/features/payments/CounterDoors";

import { FieldGrid } from "./serviceRequestShared";

type Translate = (key: string, params?: Record<string, unknown>) => string;

/** What the panel reads and writes on the capture form — nothing else of it. */
export interface PaymentDetailsForm {
  fee_timing: string;
  fee_method: string;
  fee_receipt_no: string;
  cash_received: string;
  card_last4: string;
  card_brand: string;
  card_auth_code: string;
  cheque_no: string;
  cheque_bank: string;
  cheque_date: string;
  ach_holder: string;
  ach_last4: string;
  ach_reference: string;
  money_order_no: string;
  money_order_issuer: string;
  wire_reference: string;
  wire_bank: string;
  wire_date: string;
}

export const PAY_NOW = "collect_now";
export const PAY_LATER = "collect_later";

/** Lockbox money arrives in the bank's file, never across a counter. */
const NOT_AT_A_COUNTER = new Set(["lockbox"]);

export const CARD_BRANDS = ["visa", "mastercard", "amex", "discover"] as const;

/** The request's legacy spelling is `cheque`; Settings seeds `check`. */
export function methodKind(method: string): string {
  const code = method.trim().toLowerCase();
  return code === "cheque" ? "check" : code;
}

/** The inputs each method asks for, by id — the table the PO accepted. Any
 *  method a utility added itself asks for one reference. */
export function requiredPaymentFields(method: string): readonly (keyof PaymentDetailsForm)[] {
  switch (methodKind(method)) {
    case "cash":
      return ["cash_received"];
    case "check":
      return ["cheque_no", "cheque_bank", "cheque_date"];
    case "card":
      return ["card_brand", "card_last4", "card_auth_code"];
    case "ach":
      return ["ach_holder", "ach_last4", "ach_reference"];
    case "money_order":
      return ["money_order_no", "money_order_issuer"];
    case "wire":
      return ["wire_reference", "wire_bank", "wire_date"];
    default:
      return ["ach_reference"];
  }
}

const MONEY = /^\d+(\.\d{1,4})?$/;

/** Cash handed over minus the fee, to four places and shown at two; `null`
 *  when either side is not a number yet. Strings throughout (hard rule 2). */
export function changeDue(received: string, owing: string): string | null {
  const a = received.trim();
  const b = owing.trim();
  if (!MONEY.test(a) || !MONEY.test(b)) return null;
  const scale = (text: string) => {
    const [whole = "0", frac = ""] = text.split(".");
    return BigInt(whole) * 10000n + BigInt(frac.padEnd(4, "0"));
  };
  const diff = scale(a) - scale(b);
  const negative = diff < 0n;
  const abs = negative ? -diff : diff;
  const cents = (abs + 50n) / 100n;
  const text = `${cents / 100n}.${(cents % 100n).toString().padStart(2, "0")}`;
  return negative ? `-${text}` : text;
}

/**
 * The first reason Pay now cannot be taken as typed, as a catalogue key, or
 * `null` when it can. Pay later and no fee need nothing.
 */
export function paymentDetailsProblem(form: PaymentDetailsForm, owing: string): string | null {
  if (form.fee_timing !== PAY_NOW) return null;
  if (form.fee_method.trim() === "" || form.fee_receipt_no.trim() === "") {
    return "customers.serviceRequest.pay.detailsMissing";
  }
  for (const field of requiredPaymentFields(form.fee_method)) {
    if (form[field].trim() === "") return "customers.serviceRequest.pay.detailsMissing";
  }
  if (methodKind(form.fee_method) === "cash") {
    const change = changeDue(form.cash_received, owing);
    if (change === null || change.startsWith("-")) return "customers.serviceRequest.pay.receivedTooLittle";
  }
  return null;
}

/**
 * The body `POST .../fee-collection` takes for what was typed. The amount is
 * what is OWED — the counter takes the whole fee — never what the cash drawer
 * received. Card and check go in the server's allow-listed objects; every
 * other method's reference goes in `confirmation` and the rest in `memo`.
 */
export function feeCollectionBody(form: PaymentDetailsForm, owing: string, postedAt: string) {
  const kind = methodKind(form.fee_method);
  const base = {
    amount: owing,
    method: form.fee_method.trim() === "cheque" ? "check" : form.fee_method.trim(),
    receipt_no: form.fee_receipt_no.trim(),
    posted_at: postedAt,
  };
  const clean = (parts: readonly string[]) => parts.map((part) => part.trim()).filter((part) => part !== "");
  switch (kind) {
    case "card":
      return {
        ...base,
        confirmation: form.card_auth_code.trim(),
        card: { last4: form.card_last4.trim(), brand: form.card_brand.trim(), auth_code: form.card_auth_code.trim() },
      };
    case "check":
      return {
        ...base,
        confirmation: form.cheque_no.trim(),
        check: { number: form.cheque_no.trim(), bank: form.cheque_bank.trim(), date: form.cheque_date },
      };
    case "cash":
      return { ...base, confirmation: null, memo: null };
    case "ach":
      return {
        ...base,
        confirmation: form.ach_reference.trim(),
        memo: clean([form.ach_holder, form.ach_last4 === "" ? "" : `••••${form.ach_last4.trim()}`]).join(" · ") || null,
      };
    case "money_order":
      return { ...base, confirmation: form.money_order_no.trim(), memo: form.money_order_issuer.trim() || null };
    case "wire":
      return {
        ...base,
        confirmation: form.wire_reference.trim(),
        memo: clean([form.wire_bank, form.wire_date]).join(" · ") || null,
      };
    default:
      return { ...base, confirmation: form.ach_reference.trim() || null, memo: null };
  }
}

export function usePaymentMethods(client: ApiClient) {
  const lookups = useQuery({
    queryKey: ["payments", "record-new-lookups"],
    queryFn: () => getPayments({ per: 1 }, client),
    retry: false,
  });
  return (lookups.data?.methods ?? []).filter((method: PaymentMethodOption) => !NOT_AT_A_COUNTER.has(method.code));
}

export function RequestPaymentDetails(props: {
  form: PaymentDetailsForm;
  update: (patch: Partial<PaymentDetailsForm>) => void;
  /** The fee still owed, as the server's 4-dp string; `""` when none. */
  owing: string;
  /** The same figure as a person reads it (`$45.00`). */
  owingText: string;
  /** The fee's currency, so *Change due* reads `$55.00`, not `55.00`. */
  currency?: string | null;
  client: ApiClient;
  timeZone: string;
  dateFormat: RegionalDateFormat;
  t: Translate;
}) {
  const { form, update, t } = props;
  const methods = usePaymentMethods(props.client);
  const kind = methodKind(form.fee_method);
  const field = (id: keyof PaymentDetailsForm, label: string, extra: { numeric?: boolean } = {}) => (
    <TextField
      id={id}
      label={label}
      required
      numeric={extra.numeric}
      value={form[id]}
      onChange={(value) => update({ [id]: value })}
    />
  );
  const date = (id: "cheque_date" | "wire_date", label: string) => (
    <DatePickerField
      id={id}
      label={label}
      required
      value={form[id]}
      onChange={(value) => update({ [id]: value })}
      dateFormat={props.dateFormat}
    />
  );
  const change = kind === "cash" ? changeDue(form.cash_received, props.owing) : null;

  return (
    <section data-payment-details={form.fee_timing || "unset"}>
      <h3>{t("customers.serviceRequest.pay.heading")}</h3>
      <fieldset className="m-0 min-w-0 border-0 p-0">
        <legend className="mb-2 p-0 text-sm text-neutral-700">{t("customers.serviceRequest.pay.timing")}</legend>
        <div className="flex flex-wrap gap-2" role="radiogroup">
          {[PAY_NOW, PAY_LATER].map((option) => (
            <label
              key={option}
              data-pay-option={option}
              className={`flex cursor-pointer items-center gap-2 border px-3 py-2 ${
                form.fee_timing === option ? "border-accent bg-accent-100" : "border-divider"
              }`}
            >
              <input
                type="radio"
                name="fee-timing"
                value={option}
                checked={form.fee_timing === option}
                onChange={() => update({ fee_timing: option })}
              />
              <span className="font-semibold">
                {t(option === PAY_NOW ? "customers.serviceRequest.pay.now" : "customers.serviceRequest.pay.later")}
              </span>
            </label>
          ))}
        </div>
      </fieldset>

      {form.fee_timing === PAY_LATER && (
        <p className="mt-4 max-w-prose text-sm text-neutral-700" data-pay-later="">
          {t("customers.serviceRequest.pay.laterLine")}
        </p>
      )}

      {form.fee_timing === PAY_NOW && (
        <div className="mt-5 flex flex-col gap-5">
          <FieldGrid columns={2}>
            <SelectField
              id="fee_method"
              label={t("payments.form.method")}
              required
              value={form.fee_method}
              onChange={(value) => update({ fee_method: value })}
              placeholder={t("payments.form.methodPlaceholder")}
              options={methods.map((method) => ({ value: method.code, label: method.name }))}
            />
            <TextField
              id="fee_amount"
              label={t("payments.form.amount")}
              value={props.owingText}
              onChange={() => undefined}
              readOnly
            />
          </FieldGrid>
          {form.fee_method !== "" && (
            <RecordCounterBanner
              client={props.client}
              timeZone={props.timeZone}
              dateFormat={props.dateFormat}
              methodCode={form.fee_method}
              announceBatch={false}
            />
          )}
          {kind === "cash" && (
            <FieldGrid columns={2}>
              {field("cash_received", t("customers.serviceRequest.pay.cashReceived"), { numeric: true })}
              <TextField
                id="cash_change"
                label={t("customers.serviceRequest.pay.changeDue")}
                value={
                  change === null || change.startsWith("-")
                    ? ""
                    : props.currency
                      ? formatMoney(change, props.currency)
                      : change
                }
                onChange={() => undefined}
                readOnly
              />
            </FieldGrid>
          )}
          {kind === "check" && (
            <FieldGrid columns={3}>
              {field("cheque_no", t("customers.serviceRequest.capture.chequeNo"))}
              {field("cheque_bank", t("customers.serviceRequest.capture.chequeBank"))}
              {date("cheque_date", t("customers.serviceRequest.capture.chequeDate"))}
            </FieldGrid>
          )}
          {kind === "card" && (
            <FieldGrid columns={3}>
              <SelectField
                id="card_brand"
                label={t("customers.serviceRequest.capture.cardBrand")}
                required
                value={form.card_brand}
                onChange={(value) => update({ card_brand: value })}
                options={CARD_BRANDS.map((brand) => ({
                  value: brand,
                  label: t(`customers.serviceRequest.pay.brand.${brand}`),
                }))}
              />
              {field("card_last4", t("customers.serviceRequest.capture.cardLast4"), { numeric: true })}
              {field("card_auth_code", t("customers.serviceRequest.capture.cardAuthCode"))}
            </FieldGrid>
          )}
          {kind === "ach" && (
            <FieldGrid columns={3}>
              {field("ach_holder", t("customers.serviceRequest.pay.achHolder"))}
              {field("ach_last4", t("customers.serviceRequest.pay.achLast4"), { numeric: true })}
              {field("ach_reference", t("customers.serviceRequest.pay.achReference"))}
            </FieldGrid>
          )}
          {kind === "money_order" && (
            <FieldGrid columns={2}>
              {field("money_order_no", t("customers.serviceRequest.pay.moNumber"))}
              {field("money_order_issuer", t("customers.serviceRequest.pay.moIssuer"))}
            </FieldGrid>
          )}
          {kind === "wire" && (
            <FieldGrid columns={3}>
              {field("wire_reference", t("customers.serviceRequest.pay.wireReference"))}
              {field("wire_bank", t("customers.serviceRequest.pay.wireBank"))}
              {date("wire_date", t("customers.serviceRequest.pay.wireDate"))}
            </FieldGrid>
          )}
          {form.fee_method !== "" && !["cash", "check", "card", "ach", "money_order", "wire"].includes(kind) && (
            <FieldGrid columns={2}>{field("ach_reference", t("customers.serviceRequest.pay.reference"))}</FieldGrid>
          )}
          {form.fee_method !== "" && (
            <FieldGrid columns={2}>
              <TextField
                id="fee_receipt_no"
                label={t("customers.serviceRequest.collect.receipt")}
                required
                value={form.fee_receipt_no}
                onChange={(value) => update({ fee_receipt_no: value })}
                help={t("customers.serviceRequest.collect.receiptBrief")}
              />
            </FieldGrid>
          )}
        </div>
      )}
    </section>
  );
}
