// ── Trace ──────────────────────────────────────────────
// Change:   CR-171-BRC10 P2.29 (lane MVI-WIZ-BILL) — the Billing step's
//           Preferences, Discounts and Tax, from images 41 and 44. PO, mock-up
//           v20: *"Preferences - … Paperless billing / Text reminders /
//           Autopay / Portal language — Discounts to claim - Same UI and drop
//           downs; Tax - same Ui and Exemption … date as date pickers and you
//           have to allow uplaod certificate"*.
// Rules:    decision log 2026-10-05 *"FOUR PO RULINGS"* (2) — *"Let billing
//           clerks record it themselves"*: a discount claimed and an exemption
//           recorded here take effect without a System Admin, so NOTHING on
//           this screen draws a *waiting for an admin* state · BR-CUS-059
//           (autopay is capture-only) · BR-BIL-036 (print is the floor; the
//           two elections add a channel) · B14 rules 20, 21, 31, 33, 43, 44
// Server:   §9.MONEY — `autopay_instrument_id`, `discount_claims`,
//           `tax_exemption` · GET /taxes/{id}/exemption-categories
// ───────────────────────────────────────────────────────
//
// ⚠ **EACH SECTION IS A PANEL WITH ITS TICK ON THE HEADING ROW** — image 41's
// *Set preferences*, *Claim discounts*, *Tax exempt*; image 44 draws the
// unticked state as the heading alone. That is `Panel`'s `trailing` slot, the
// kit's one place for a control beside a heading (B14 rule 36), and the body
// is simply not rendered while the tick is off.
import { useQueries } from "@tanstack/react-query";
import type { ReactNode } from "react";

import type { ApiClient } from "@/api/client";
import { getTaxExemptionCategories } from "@/api/endpoints";
import type { ClaimableDiscount } from "@/api/moveInMoneyEndpoints";
import type { PlanTaxSection } from "@/api/planFormEndpoints";
import { REFERENCE_STALE_MS } from "@/api/queryClient";
import type { RegionalDateFormat } from "@/components/DateCell";
import { FileField } from "@/components/FileField";
import { CheckboxField, DatePickerField, SelectField, TextField } from "@/components/FormModal";
import { Panel } from "@/components/Panel";
import { CellSelect, CellStatic, CellText, TableArray } from "@/components/TableArray";
import type { TableArrayColumn } from "@/components/TableArray";
import type { Translator } from "@/features/tenancy/settingsShared";

import { PreferencesPanel } from "../customerForm/PreferencesPanel";
import type { PreferencesForm } from "../NewAccountWizard";
import { rowKey } from "./billingModel";
import type { BillingProblem, CertificateFile, DiscountRowForm, StepBillingOwn } from "./billingModel";

/** The setting an Autopay or Paperless discount is kept matched to, by
 *  discount id (`pairs_with`, `DEF-RAT-9833`). */
export type PairedSettings = Readonly<Record<string, "autopay" | "paperless">>;

/** ⚖️ PO D2 (b) and ruling 4, 2026-10-06 (`DEF-RAT-9833`) — the claim list's
 *  rows that mirror a preference, from the server's `pairs_with`. */
export function pairedSettings(offered: readonly ClaimableDiscount[]): PairedSettings {
  const out: Record<string, "autopay" | "paperless"> = {};
  for (const row of offered) if (row.pairs_with) out[row.ref.id] = row.pairs_with;
  return out;
}

/** The discount rows left once `off` preferences are Off — a paired row goes
 *  with its preference, so the two never disagree (ruling 4, reading (b)). */
export function withoutPaired(own: StepBillingOwn, paired: PairedSettings, off: readonly string[]): StepBillingOwn {
  const discounts = own.discounts.filter((row) => !off.includes(paired[row.discountId] ?? ""));
  return discounts.length === own.discounts.length ? own : { ...own, discounts };
}

/** Four across, B14 rule 39's 20px between rows — the drawn grid. */
const GRID = "grid grid-cols-4 gap-x-6 gap-y-5";

function TickedPanel(props: {
  title: string;
  tickId: string;
  tickLabel: string;
  on: boolean;
  onTick: (on: boolean) => void;
  name: string;
  children: ReactNode;
}) {
  return (
    <Panel
      as="section"
      title={props.title}
      trailing={<CheckboxField id={props.tickId} label={props.tickLabel} checked={props.on} onChange={props.onTick} />}
      data-billing-section={props.name}
      data-billing-section-open={props.on ? "true" : "false"}
    >
      {props.on ? props.children : null}
    </Panel>
  );
}

export function PreferencesSection(props: {
  own: StepBillingOwn;
  set: (next: StepBillingOwn) => void;
  preferences: PreferencesForm;
  setPreferences: (next: PreferencesForm) => void;
  /** `DEF-RAT-9833` — a preference set Off takes its paired discount row with it. */
  paired?: PairedSettings;
  client: ApiClient;
  t: Translator;
}) {
  const { own, set, t, preferences: prefs } = props;
  const paired = props.paired ?? {};
  // Lane CF-1 (2026-10-18) — the panel is the SHARED one
  // (`customerForm/PreferencesPanel.tsx`); what stays here is the move-in's
  // own reading of each change: a paired discount goes with its preference.
  return (
    <PreferencesPanel
      on={own.prefsOn}
      onTick={(on) => {
        const next = { ...own, prefsOn: on, autopayFrom: on ? own.autopayFrom : "" };
        set(on ? next : withoutPaired(next, paired, ["autopay", "paperless"]));
        // Unticked is *no preferences set*: every election back to Off. The
        // language stays — it is the utility's default, not an election.
        if (!on) props.setPreferences({ ...prefs, paperless: false, sms_reminders: false, autopay: false });
      }}
      value={prefs}
      onChange={(patch) => {
        props.setPreferences({ ...prefs, ...patch });
        if (patch.paperless === false) set(withoutPaired(own, paired, ["paperless"]));
        if (patch.autopay === false) set(withoutPaired({ ...own, autopayFrom: "" }, paired, ["autopay"]));
      }}
      showAutopay
      autopayFrom={
        // ⚠ **NO OPTIONS, AND IT SAYS SO — `DEF-CUS-9739`.** An autopay
        // source is a payments instrument the CUSTOMER has saved, and no
        // read serves those to this step; a new customer has none at all.
        // The box is drawn (image 41) and held with its reason (BR-SHL-025)
        // rather than offering a list this screen would have to invent.
        <SelectField
          id="move_in_autopay_from"
          label={t("customers.moveIn.prefs.autopayFrom")}
          value=""
          onChange={() => undefined}
          options={[]}
          placeholder={t("customers.moveIn.prefs.noSavedMethod")}
          disabled
        />
      }
      client={props.client}
      t={t}
    />
  );
}

export function DiscountsSection(props: {
  own: StepBillingOwn;
  set: (next: StepBillingOwn) => void;
  /** The discounts a clerk may claim (`GET /move-ins/pricing` → `plan.claimable_discounts`). */
  offered: readonly ClaimableDiscount[];
  /** `DEF-RAT-9833` — picking Autopay or Paperless switches that preference On. */
  preferences?: PreferencesForm;
  setPreferences?: (next: PreferencesForm) => void;
  problems: readonly BillingProblem[];
  tried: boolean;
  t: Translator;
}) {
  const { own, set, t } = props;
  const byId = new Map(props.offered.map((discount) => [discount.ref.id, discount]));
  const paired = pairedSettings(props.offered);
  const patch = (key: string, next: Partial<DiscountRowForm>) => {
    const rows = own.discounts.map((row) => (row.key === key ? { ...row, ...next } : row));
    // ⚖️ PO D2 (b) and ruling 4, 2026-10-06 (`DEF-RAT-9833`): ticking the
    // Paperless (or Autopay) discount switches that preference On — the server
    // does the same at Complete — so the step never shows the two apart.
    const setting = next.discountId === undefined ? undefined : paired[next.discountId];
    if (setting !== undefined && props.preferences !== undefined && props.setPreferences !== undefined) {
      props.setPreferences({ ...props.preferences, [setting]: true });
      set({ ...own, prefsOn: true, discounts: rows });
      return;
    }
    set({ ...own, discounts: rows });
  };
  const columns: TableArrayColumn<DiscountRowForm>[] = [
    { key: "no", label: "#", cell: (_row, index) => <CellStatic name="no">{index + 1}</CellStatic> },
    {
      key: "discount",
      label: t("customers.moveIn.discounts.col.discount"),
      cell: (row) => (
        <CellSelect
          name="discount"
          label={t("customers.moveIn.discounts.col.discount")}
          placeholder={t("customers.moveIn.discounts.choose")}
          value={row.discountId}
          fit
          onChange={(discountId) => patch(row.key, { discountId })}
          // A discount already on another row drops out of this one's list —
          // the server refuses one claimed twice (`discountTwice`).
          options={props.offered.map((discount) => ({
            value: discount.ref.id,
            label: discount.ref.name,
            disabled: discount.ref.id !== row.discountId && own.discounts.some((o) => o.discountId === discount.ref.id),
          }))}
        />
      ),
    },
    {
      key: "amount",
      label: t("customers.moveIn.discounts.col.amount"),
      numeric: true,
      cell: (row) => <CellStatic name="amount">{byId.get(row.discountId)?.value_display ?? ""}</CellStatic>,
    },
    {
      key: "note",
      label: t("customers.moveIn.fees.col.note"),
      cell: (row) => (
        <CellText
          name="note"
          label={t("customers.moveIn.fees.col.note")}
          placeholder={t("customers.moveIn.optional")}
          value={row.note}
          onChange={(note) => patch(row.key, { note })}
        />
      ),
    },
  ];
  const left = props.offered.length - own.discounts.length;
  const onTick = (on: boolean) =>
    set({
      ...own,
      discountsOn: on,
      discounts: on && own.discounts.length === 0 ? [{ key: rowKey("discount"), discountId: "", note: "" }] : on ? own.discounts : [],
    });
  const tick = (
    <CheckboxField
      id="move_in_discounts_on"
      label={t("customers.moveIn.discounts.tick")}
      checked={own.discountsOn}
      onChange={onTick}
    />
  );
  // Unticked (image 44) it is the heading and its tick, like the other two.
  // Ticked, the section IS the table array — the kit's own panel, heading and
  // tick on its heading row — rather than a table box nested in a panel box.
  if (!own.discountsOn) {
    return (
      <TickedPanel
        title={t("customers.moveIn.discounts.title")}
        tickId="move_in_discounts_on"
        tickLabel={t("customers.moveIn.discounts.tick")}
        on={false}
        onTick={onTick}
        name="discounts"
      >
        {null}
      </TickedPanel>
    );
  }
  return (
    <div data-billing-section="discounts" data-billing-section-open="true">
      <TableArray<DiscountRowForm>
        title={t("customers.moveIn.discounts.title")}
        fact={tick}
        collection="move-in-discounts"
        columns={columns}
        rows={own.discounts}
        rowKey={(row) => row.key}
        emptyText={props.offered.length === 0 ? t("customers.moveIn.discounts.noneOffered") : t("customers.moveIn.discounts.empty")}
        cellError={(row, _index, column) =>
          props.tried && column === "discount" && row.discountId === "" ? t("customers.moveIn.discounts.required") : undefined
        }
        onChange={(rows) => set({ ...own, discounts: rows })}
        removeLabel={t("customers.moveIn.discounts.remove")}
        actions={[
          {
            key: "add-discount",
            label: t("customers.moveIn.discounts.add"),
            onClick: () => set({ ...own, discounts: [...own.discounts, { key: rowKey("discount"), discountId: "", note: "" }] }),
            blockedReason: left > 0 ? undefined : t("customers.moveIn.discounts.allAdded"),
          },
        ]}
        footerTrailing={<span className="text-base text-neutral-700">{t("customers.moveIn.discounts.fromPlan")}</span>}
      />
    </div>
  );
}

/** A file → the base64 the commit carries. */
export function readCertificate(file: File): Promise<CertificateFile> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const url = String(reader.result ?? "");
      resolve({ name: file.name, contentType: file.type, base64: url.slice(url.indexOf(",") + 1) });
    };
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(file);
  });
}

export function TaxSection(props: {
  own: StepBillingOwn;
  set: (next: StepBillingOwn) => void;
  /** The taxes that reach this customer (`plan.taxes`, narrowed). */
  taxes: readonly PlanTaxSection[];
  problems: readonly BillingProblem[];
  tried: boolean;
  dateFormat: RegionalDateFormat;
  client: ApiClient;
  t: Translator;
}) {
  const { own, set, t } = props;
  const tax = own.tax;
  const categories = useQueries({
    queries: props.taxes.map((row) => ({
      queryKey: ["rating", "tax", row.ref.id, "exemption-categories"],
      queryFn: () => getTaxExemptionCategories(row.ref.id, props.client),
      staleTime: REFERENCE_STALE_MS,
      retry: false,
      enabled: own.taxOn,
    })),
  });
  const options = categories
    .flatMap((query) => query.data ?? [])
    .filter((category) => category.status !== "retired")
    .map((category) => ({ value: category.id, label: category.name }));
  const patch = (next: Partial<StepBillingOwn["tax"]>) => set({ ...own, tax: { ...tax, ...next } });
  const error = (problem: BillingProblem, key: string) =>
    props.tried && props.problems.includes(problem) ? t(key) : undefined;

  return (
    <TickedPanel
      title={t("customers.moveIn.tax.title")}
      tickId="move_in_tax_on"
      tickLabel={t("customers.moveIn.tax.tick")}
      on={own.taxOn}
      onTick={(on) => set({ ...own, taxOn: on })}
      name="tax"
    >
      <div className={GRID}>
        <SelectField
          id="move_in_tax_category"
          label={t("customers.moveIn.tax.exemption")}
          required
          value={tax.categoryId}
          onChange={(categoryId) => patch({ categoryId })}
          options={options}
          placeholder={t("customers.moveIn.tax.choose")}
          error={error("tax_category", "customers.moveIn.tax.categoryRequired")}
        />
        <TextField
          id="move_in_tax_ref"
          label={t("customers.moveIn.tax.certificateNumber")}
          required
          value={tax.certificateRef}
          onChange={(certificateRef) => patch({ certificateRef })}
          error={error("tax_ref", "customers.moveIn.tax.refRequired")}
        />
        <DatePickerField
          id="move_in_tax_issued"
          regional
          label={t("customers.moveIn.tax.issued")}
          value={tax.issuedOn}
          dateFormat={props.dateFormat}
          onChange={(issuedOn) => patch({ issuedOn })}
        />
        <DatePickerField
          id="move_in_tax_expires"
          regional
          label={t("customers.moveIn.tax.expires")}
          required
          value={tax.expiresOn}
          min={tax.issuedOn === "" ? undefined : tax.issuedOn}
          dateFormat={props.dateFormat}
          onChange={(expiresOn) => patch({ expiresOn })}
          error={error("tax_expires", "customers.moveIn.tax.expiresRequired")}
        />
      </div>
      <div className="mt-5" data-tax-certificate={tax.file === null ? "none" : "chosen"}>
        <FileField
          id="move_in_tax_certificate"
          label={t("customers.moveIn.tax.certificate")}
          required
          accept="application/pdf,image/*"
          fileName={tax.file?.name ?? null}
          error={error("tax_file", "customers.moveIn.tax.fileRequired")}
          onChange={(file) => {
            if (file === null) {
              patch({ file: null });
              return;
            }
            void readCertificate(file).then((read) => patch({ file: read }));
          }}
        />
      </div>
    </TickedPanel>
  );
}
