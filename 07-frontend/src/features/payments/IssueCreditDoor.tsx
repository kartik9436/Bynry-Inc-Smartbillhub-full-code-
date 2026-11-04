// ── Trace ──────────────────────────────────────────────
// Change:   CR-138-BRC07 · P4.10 — "Refunds moves, and **Credit joins it**".
//           Blueprint `05-prototype/06 Payments Page Blueprint.pdf` p022 (the
//           task row) and p072–p073 (screen 6·1, read AS IMAGES at scale 2 per
//           B14 rule 42). The drawing's Primary-action row, verbatim: *"**Raise
//           refund**, with **Issue credit** beside it — so the cheaper option is
//           visible at the moment the choice is made."*
//           Screens: 6·1 Refunds (S58 · PAY-P)
// Rules:    B14 rule 4 (`Verb →` NAVIGATES; `Verb ✓` commits — this button
//           navigates and is spelled accordingly) · rule 31 (no database id is
//           ever the visible value of a field — a bill is chosen by its NUMBER)
//           · rule 32 (a stated absence) · rule 33 (a LABEL ≤ 3 words, a FACT
//           ≤ 6) · rule 21 (Tailwind utilities, no stylesheet class — this file
//           is on `styles/route-b-migrated.txt` from its first commit) · rule
//           43 (a piece of UI is a COMPONENT) · BR-BIL-041 (the REASON derives
//           the correction class; a screen never picks the class) ·
//           BR-SHL-025 (a control that cannot act renders DISABLED WITH ITS
//           REASON, never hidden)
// Tests:    07-frontend/src/features/payments/issueCreditDoor.dom.test.tsx
// Impacts:  features/payments/RefundsPage.tsx (the page head that opens it) ·
//           api/endpoints.getAccountCreditPath (`P4.12`, the read behind it) ·
//           features/billing/FixABillTab.tsx (WHERE IT SENDS YOU — untouched)
// ───────────────────────────────────────────────────────
//
// A DOOR TO THE CREDIT PATH. **NOT A COPY OF IT.**
//
// ╔══════════════════════════════════════════════════════════════════════════╗
// ║  PO, 2026-09-22: "we can not have two path for 1 capabilities wew will   ║
// ║  confuse user." SO THIS COMPONENT MINTS NO WRITE VERB AT ALL.            ║
// ╚══════════════════════════════════════════════════════════════════════════╝
// It asks two questions and then LEAVES:
//
//   1. which account?      — `AccountPickerFields`, the picker the raise modal
//                            beside it already uses. Not a second one.
//   2. which bill?         — from `GET /accounts/{id}/credit-path`, which
//                            serves the bills a goodwill credit could be raised
//                            against and mints no write verb of its own.
//
// …and `Continue →` navigates to `/accounts/{id}/issue-credit?bill=<id>`, which
// has been the ONE credit path's address since `CR-101`. `FixABillTab` renders
// there, reads `?bill=`, and owns every write: `POST /corrections`,
// `…/approve`, `…/execute`, reaching `corrections.execute_credit_only`. **This
// file posts nothing.**
//
// ══════════════════════════════════════════════════════════════════════════
// THE FACT A PAYMENTS SCREEN CANNOT KNOW BY ITSELF, AND IT IS WHY THIS IS TWO
// QUESTIONS RATHER THAN ONE
// ══════════════════════════════════════════════════════════════════════════
// **A CREDIT IS RAISED AGAINST A BILL AND A REFUND AGAINST AN ACCOUNT.** So
// *credit them instead* is NOT symmetrical with *refund them*: `Raise refund`
// beside this needs an account and is done; this needs an account AND a bill,
// and there is no way to skip the second. A door that navigated on the account
// alone would land the clerk on a screen asking a question they came here to
// have answered.
//
// ⚠ **`available: false` MEANS THIS ACCOUNT HAS NOTHING TO CREDIT TODAY — NOT
// THAT THE FEATURE IS UNBUILT**, and the two must not read the same. The reason
// travels on `problems`, so the screen prints a sentence rather than greying a
// control and leaving the clerk with *"why not?"* (`BR-SHL-025`).
import { useState } from "react";

import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { z } from "zod";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { getAccountCreditPath } from "@/api/endpoints";
import { FormModal, SelectField } from "@/components/FormModal";
import type { FormSubmitOutcome } from "@/components/FormModal";
import { MoneyCell } from "@/components/MoneyCell";
import { Note } from "@/components/TextBits";
import { AccountPickerFields, useAccountSearch } from "./paymentsShared";
import type { Translator } from "@/features/tenancy/settingsShared";

/**
 * WHERE THE ONE CREDIT PATH LIVES. Declared here as a function rather than
 * typed at the call site, because a second literal `/accounts/…/issue-credit`
 * in a second file is how two answers to one question start drifting — the
 * reasoning `COLLECTIONS_LADDER_ROUTE` already records one file over.
 *
 * ⚠ **THE `bill` QUERY NAME IS BILLING'S, NOT OURS.** `FixABillTab` reads
 * `FIX_A_BILL_PARAM`, and `App.tsx`'s own comment says this route *"hands it
 * the same query the billing address does"*. It is spelled out here rather than
 * imported so payments does not take a build dependency on a billing module for
 * one string; the day it moves, this is the one line that changes and the test
 * below names the address it must produce.
 */
export function issueCreditPath(accountId: string, invoiceId: string): string {
  return `/accounts/${encodeURIComponent(accountId)}/issue-credit?bill=${encodeURIComponent(invoiceId)}`;
}

/** The picker refuses to hand over until BOTH questions are answered — see the
 *  header for why the bill is not optional. */
function issueCreditSchema(t: Translator) {
  return z.object({
    account_id: z.string().min(1, t("payments.refunds.accountRequired")),
    invoice_id: z.string().min(1, t("payments.refunds.credit.billRequired")),
  });
}

export function IssueCreditDoor(props: {
  client?: ApiClient;
  /** Navigates. Passed in rather than calling `useNavigate` here so the modal
   *  can be mounted and asserted without a router that already knows the
   *  tenant — and so the page that opens it owns `tenantPath()`, which is the
   *  one place that knows a route constant is tenant-relative. */
  onGo: (path: string) => void;
  onClose: () => void;
}) {
  const { t } = useTranslation();
  const translate: Translator = (key, params) => t(key, params);
  const client = props.client ?? api;
  const [accountQuery, setAccountQuery] = useState("");
  const [accountId, setAccountId] = useState("");
  const [invoiceId, setInvoiceId] = useState("");

  const accountSearch = useAccountSearch(accountQuery, client, "issue-credit-account-picker");

  // Only once an account is chosen — there is no tenant-wide "which bills could
  // be credited" question, and asking one would be a list of every bill in the
  // utility, which is not what a clerk pressed *Issue credit* to see.
  const pathQuery = useQuery({
    queryKey: ["payments", "credit-path", accountId],
    queryFn: () => getAccountCreditPath(accountId, client),
    enabled: accountId !== "",
    retry: false,
  });

  const creditPath = pathQuery.data;
  const bills = creditPath?.bills ?? [];

  async function handleSubmit(): Promise<FormSubmitOutcome> {
    // ⚠ NOTHING IS POSTED HERE AND NOTHING MAY BE. This is a handoff: the write
    // is billing's and is three steps long (`POST /corrections`, `…/approve`,
    // `…/execute`). A "convenience" call from this file would be the second
    // implementation the PO's ruling forbids.
    props.onGo(issueCreditPath(accountId, invoiceId));
    return { ok: true };
  }

  return (
    <FormModal
      title={t("payments.refunds.credit.title")}
      schema={issueCreditSchema(translate)}
      values={{ account_id: accountId, invoice_id: invoiceId }}
      // B14 rule 4: `Verb →` NAVIGATES. This button does not commit anything,
      // and spelling it `Issue credit ✓` would promise a write that happens
      // three screens later, after two approvals.
      submitLabel={t("payments.refunds.credit.continue")}
      onSubmit={handleSubmit}
      onClose={props.onClose}
    >
      <AccountPickerFields
        searchLabel={t("payments.refunds.accountSearch")}
        accountLabel={t("payments.refunds.account")}
        term={accountQuery}
        onTermChange={setAccountQuery}
        search={accountSearch}
        value={accountId}
        onChange={(next) => {
          setAccountId(next);
          // The bill belongs to the account. Leaving one selected from the
          // previous account would build an address that opened somebody
          // else's bill, and the screen would look correct doing it.
          setInvoiceId("");
        }}
        t={translate}
      />

      {accountId === "" ? null : pathQuery.isPending ? (
        <Note>{t("payments.refunds.credit.looking")}</Note>
      ) : pathQuery.isError ? (
        <Note>{t("payments.refunds.credit.unreadable")}</Note>
      ) : bills.length === 0 ? (
        // ⚠ **A STATED ABSENCE, NOT A GREYED CONTROL** (`BR-SHL-025`). This is
        // *this account has nothing to credit today*, which is a fact about the
        // account; a clerk who reads "unavailable" goes looking for a build.
        <Note>{t("payments.refunds.credit.noBills")}</Note>
      ) : (
        <>
          <SelectField
            id="invoice_id"
            label={t("payments.refunds.credit.bill")}
            value={invoiceId}
            onChange={setInvoiceId}
            placeholder={t("payments.refunds.credit.billPrompt")}
            options={bills.map((bill) => ({
              value: bill.invoice_id,
              // B14 rule 31 — the NUMBER, never `invoice_id`. A bill with no
              // number is a DRAFT and billing normalises its `""` to null; it
              // is labelled by what it still owes rather than by a blank,
              // because a blank option reads as a broken list.
              label:
                bill.number ?? t("payments.refunds.credit.unnumbered", { amount: bill.balance }),
            }))}
            required
          />
          {invoiceId === "" ? null : (
            <p className="text-neutral-800">
              {t("payments.refunds.credit.owes")}{" "}
              <MoneyCell
                amount={bills.find((bill) => bill.invoice_id === invoiceId)?.balance ?? "0"}
                currency={bills.find((bill) => bill.invoice_id === invoiceId)?.currency ?? ""}
              />
            </p>
          )}
        </>
      )}
    </FormModal>
  );
}

export default IssueCreditDoor;

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-138-BRC07 P4.10 (payments blueprint phase 4, wave 2) — built from
//         p072–p073 read AS IMAGES at scale 2.0 (B14 rule 42).
// generated: 2026-09-23 by LANE P4-SCREENS-B
// exceptions: (1) the modal shows the bill's BALANCE and not the credit amount
//         — the amount is billing's to collect on `FixABillTab`, where the
//         goodwill field and its refusals already live. Collecting it here
//         would be the second implementation the ruling forbids, one field at
//         a time.
// ──────────────────────────────────────────────────────────
