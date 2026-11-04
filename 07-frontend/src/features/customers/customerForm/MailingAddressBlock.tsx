// ── Trace ──────────────────────────────────────────────
// Change:   lane CF-1 (2026-10-18), task 8 — the SHARED *Mailing address*
//           block, lifted out of Move-in's Customer step so Move-in, the staff
//           service request and New connect draw one (customer-forms drawing
//           set, images 01, 03, 06, 13 — read as IMAGES, B14 rule 42).
// Rules:    hard rule 8 — `customers.addresses` `kind='mailing'` is where the
//           BILL goes, the first named exception; the service address is the
//           unit's, WALKED, and is never typed here · `DEF-CUS-6359` (*Same as
//           service address* ticked writes NO mailing row) · B14 rules 21, 33,
//           43, 44 · the kit's `UsAddressFields` (street, Apt/Unit, city, a
//           state list, ZIP)
// Tests:    customerForm/customerForm.dom.test.tsx
// ───────────────────────────────────────────────────────
//
// THE BLOCK, AS DRAWN: a panel with *Same as service address* ticked on its
// heading row. Ticked, one line — *Service address* and the unit's address,
// walked. Unticked, one card titled *Mailing address* with what is typed as its
// summary, open, holding the five US fields (image 13).
import { Disclosure } from "@/components/Disclosure";
import { UsAddressFields } from "@/components/UsAddressFields";
import type { Translator } from "@/features/tenancy/settingsShared";

import { TickPanel } from "../CoOwnerCards";

/** The mailing half of the customer form — `CustomerForm`'s six fields. */
export interface MailingAddressValue {
  mailing_same: boolean;
  mailing_line1: string;
  mailing_line2: string;
  mailing_city: string;
  mailing_state: string;
  mailing_postal_code: string;
}

export function MailingAddressBlock(props: {
  value: MailingAddressValue;
  onChange: (patch: Partial<MailingAddressValue>) => void;
  /** The service address in words — the unit's, walked (hard rule 8). `""`
   *  when the host does not know it yet (a request not yet matched). */
  serviceAddress: string;
  t: Translator;
}) {
  const { t, value } = props;
  const typed = [value.mailing_line1, value.mailing_line2, value.mailing_city, value.mailing_state]
    .filter((part) => part.trim() !== "")
    .join(", ");
  return (
    <TickPanel
      name="mailing"
      title={t("customers.account.field.mailingAddress")}
      tickId="mailing_same"
      tickLabel={t("customers.account.field.mailingSame")}
      ticked={value.mailing_same}
      onTick={(checked) => props.onChange({ mailing_same: checked })}
    >
      {value.mailing_same ? (
        <div
          className="flex flex-wrap items-baseline gap-2 border border-divider bg-surface px-4 py-3"
          data-mailing="service"
        >
          <span className="font-heading font-semibold">
            {t("customers.moveIn.customer.serviceAddress")}
          </span>
          <span>{props.serviceAddress === "" ? "—" : props.serviceAddress}</span>
        </div>
      ) : (
        <Disclosure
          variant="card"
          defaultOpen
          title={t("customers.account.field.mailingAddress")}
          summary={typed === "" ? t("customers.moveIn.customer.notEntered") : typed}
        >
          <UsAddressFields
            idPrefix="mailing"
            value={{
              line1: value.mailing_line1,
              line2: value.mailing_line2,
              city: value.mailing_city,
              state: value.mailing_state,
              postal_code: value.mailing_postal_code,
            }}
            onChange={(next) =>
              props.onChange({
                mailing_line1: next.line1,
                mailing_line2: next.line2,
                mailing_city: next.city,
                mailing_state: next.state,
                mailing_postal_code: next.postal_code,
              })
            }
          />
        </Disclosure>
      )}
    </TickPanel>
  );
}
