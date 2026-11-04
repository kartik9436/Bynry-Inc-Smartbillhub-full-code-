// ── Trace ──────────────────────────────────────────────
// Change:   CR-191-BRC10 (PO 2026-10-23) — a portal application whose fee is
//           above $0.00 is paid by card on its last step, before it is sent.
//           PO, verbatim: "if there is a application or service fee then
//           consumer will have to pay it online; they can't say pay later",
//           and "3A" (the card on the same screen, through the portal's
//           existing online payment).
// Rules:    BR-CWP-057 (a token, a brand, a last four — never a card number on
//           the wire) · BR-CWP-056 (a control that may not be used is held
//           WITH its reason) · B14 rules 21, 33, 35, 36, 43
// Tests:    src/portal/guest/ApplicationFeeCard.dom.test.tsx
// Impacts:  ApplyForService.tsx (CheckAndSend, Sent) · guestClient.ts
// ───────────────────────────────────────────────────────
import { useTranslation } from "react-i18next";

import type { MoneyCell } from "../api/guestClient";
import { FormField, SectionTitle, TextInput, TwoUp } from "../components/primitives";

/** What the applicant typed. ⚠ **IT NEVER LEAVES THE BROWSER AS TYPED** — the
 *  caller reduces the number to a token, a brand and a last four through
 *  `tokeniseCard`, quick pay's own function, before anything is posted. */
export interface FeeCardValue {
  cardNumber: string;
  expires: string;
  securityCode: string;
}

export const EMPTY_FEE_CARD: FeeCardValue = { cardNumber: "", expires: "", securityCode: "" };

/** The fee the last step must take, or null — no code marked, a `$0.00` fee
 *  (*"many time utilities charger 0 application fees"*), or not answered yet. */
export function feeToPay(fee: MoneyCell | undefined): MoneyCell | null {
  if (fee === undefined || fee.kind !== "amount" || fee.amount === null) return null;
  return /^0+(\.0+)?$/.test(fee.amount.trim()) ? null : fee;
}

export function feeCardIsComplete(value: FeeCardValue): boolean {
  return (
    value.cardNumber.trim() !== "" && value.expires.trim() !== "" && value.securityCode.trim() !== ""
  );
}

/**
 * `HOW YOU ARE PAYING` on the application's last step — the same three boxes,
 * in the same order and with the same catalogue words, as quick pay's `CWP-003`
 * (the PO's *"existing online payment"*). A component rather than a copy inside
 * the page (B14 rule 43).
 *
 * ⚠ **A UTILITY THAT CANNOT TAKE A CARD SHOWS ITS REASON, NOT THE BOXES.** The
 * fee must be paid online and there is no way to pay, so the caller holds Send
 * and this says why in quick pay's own five words (`BR-CWP-056`).
 */
export function ApplicationFeeCard(props: {
  cardAvailable: boolean;
  value: FeeCardValue;
  onChange: (next: FeeCardValue) => void;
}) {
  const { t } = useTranslation();
  const set = (patch: Partial<FeeCardValue>) => props.onChange({ ...props.value, ...patch });
  return (
    <div data-fee-card="" className="flex flex-col gap-3">
      <SectionTitle>{t("portal.quickPay.howPaying")}</SectionTitle>
      {props.cardAvailable ? (
        <>
          <FormField id="appfee-card" label={t("portal.quickPay.cardNumber")} required>
            <TextInput
              id="appfee-card"
              value={props.value.cardNumber}
              onChange={(cardNumber) => set({ cardNumber })}
              placeholder={t("portal.quickPay.cardNumberExample")}
            />
          </FormField>
          <TwoUp>
            <FormField id="appfee-expires" label={t("portal.quickPay.expires")} required>
              <TextInput
                id="appfee-expires"
                value={props.value.expires}
                onChange={(expires) => set({ expires })}
                placeholder={t("portal.quickPay.expiresExample")}
              />
            </FormField>
            <FormField id="appfee-security" label={t("portal.quickPay.securityCode")} required>
              <TextInput
                id="appfee-security"
                value={props.value.securityCode}
                onChange={(securityCode) => set({ securityCode })}
              />
            </FormField>
          </TwoUp>
        </>
      ) : (
        <p className="text-base text-danger-700" role="status" data-card-unavailable="">
          {t("portal.quickPay.cannotPayHere")}
        </p>
      )}
    </div>
  );
}
