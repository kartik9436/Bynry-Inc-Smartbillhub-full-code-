// ── Trace ──────────────────────────────────────────────
// Change:   lane CF-1 (2026-10-18), task 5 — the utility's own CUSTOMER fields
//           as a panel of the shared customer form, *More about the customer*
//           with *Utility's own fields* on its heading row (customer-forms
//           drawing set, images 01, 03, 06 — read as IMAGES, B14 rule 42).
// Rulings:  decision log *"2026-10-18 — CUSTOMER DATA AND UI CONSISTENT ACROSS
//           THE CREATE SCREENS"*, *Same day, PO rulings closing the review*:
//           *"Move-in gains the utility's custom fields panel (today it always
//           sends `custom_data: {}`)"* — `DEF-CUS-10224`.
// Rules:    EP-TEN-09 / US-SHL-015 (the tenant's own fields; the server refuses
//           a key it holds no definition for) · BR-TEN-048 (never priced) ·
//           B14 rules 21, 36 (the kit's `CustomFieldsInput`, opt-in `bare`),
//           43, 44
// Tests:    customerForm/customerForm.dom.test.tsx
// ───────────────────────────────────────────────────────
//
// ⚠ **EVERY `<CustomFieldsInput>` BELOW CARRIES LITERAL `entity` AND `screen`
// STRINGS, ONE BRANCH PER SCREEN.** `tests/test_cr161_w1_custom_field_settings
// .py` pairs every rendered slot with a call it can READ out of the source; a
// computed `screen={props.screen}` would be a slot no test could see.
//
// WHICH SLOT EACH HOST USES, AND WHY:
//   · `S18` — Move-in. The move-in's Customer step IS New account's customer
//     field set (`CustomerFields.tsx`: "Hosts: NewAccountWizard.tsx (step 1) ·
//     MoveInWizard.tsx (step 2)"), so a field a utility places on New account's
//     customer form is asked on the move-in too. No new slot is minted: a
//     second slot for the same form would make a utility place every field
//     twice. The move-in door validates the block's `custom_data` against the
//     definitions with no screen (`services._validate_account`), exactly as
//     before this panel existed.
//   · `REQUEST_NEW` — the staff service request (W6's slot).
//   · `NEW_CONNECTION_OWNER` — New connect's owner step (W4's slot).
//
// Drawn ONLY when the utility placed a field on the slot — a utility with no
// fields sees no empty box (TC-4).
import type { ApiClient } from "@/api/client";
import { CustomFieldsInput, useCustomFieldRegistry } from "@/components/CustomFields";
import type { CustomFieldValues } from "@/components/CustomFields";
import { Panel } from "@/components/Panel";
import { StatusPill } from "@/components/StatusPill";
import type { Translator } from "@/features/tenancy/settingsShared";

export type CustomerFieldsScreen = "S18" | "REQUEST_NEW" | "NEW_CONNECTION_OWNER";

export function CustomerCustomFieldsPanel(props: {
  screen: CustomerFieldsScreen;
  values: CustomFieldValues;
  onChange: (values: CustomFieldValues) => void;
  t: Translator;
  client?: ApiClient;
}) {
  const { t } = props;
  const registry = useCustomFieldRegistry({
    entity: "customers",
    screen: props.screen,
    mode: "input",
    client: props.client,
  });
  if ((registry.data ?? []).length === 0) return null;
  return (
    <Panel
      as="section"
      title={t("customers.form.moreAbout")}
      trailing={<StatusPill tone="info">{t("customers.form.utilityFields")}</StatusPill>}
      data-customer-panel="custom"
    >
      {props.screen === "S18" ? (
        <CustomFieldsInput entity="customers" screen="S18"
          bare
          values={props.values}
          onChange={props.onChange}
          client={props.client}
        />
      ) : props.screen === "REQUEST_NEW" ? (
        <CustomFieldsInput entity="customers" screen="REQUEST_NEW"
          bare
          values={props.values}
          onChange={props.onChange}
          client={props.client}
        />
      ) : (
        <CustomFieldsInput entity="customers" screen="NEW_CONNECTION_OWNER"
          bare
          values={props.values}
          onChange={props.onChange}
          client={props.client}
        />
      )}
    </Panel>
  );
}

/** The answered keys only — what a commit sends as the customer block's
 *  `custom_data`, or `undefined` when nothing was typed (a utility with no
 *  fields posts exactly what it posted before). */
export function customerCustomPayload(values: CustomFieldValues): CustomFieldValues | undefined {
  const out = Object.fromEntries(
    Object.entries(values).filter(([, value]) => {
      if (value === undefined || value === null || value === "") return false;
      if (Array.isArray(value)) return value.length > 0;
      return !(typeof value === "string" && value.trim() === "");
    }),
  );
  return Object.keys(out).length === 0 ? undefined : out;
}
