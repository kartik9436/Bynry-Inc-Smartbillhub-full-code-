// ── Trace ──────────────────────────────────────────────
// Change:   CR-171-BRC10 P2.24 (lane MVI-WIZ-CUST, 2026-10-05) — *Co-owners*
//           (images 33, 38) and *Owners and officers* (image 40): a tick in the
//           heading, then one collapsible card per person with the full fields.
// Rules:    B14 rule 43 (built AS A COMPONENT — one component, two kinds) ·
//           rule 44 (our kit decides how: `Panel`, `Disclosure` card,
//           `FormModal` fields) · rule 37 (every figure drawn is an
//           illustration) · rule 33 (labels ≤ 3 words, no rationale) ·
//           BR-CUS-092 (SSN and licence are sent once, never shown back) ·
//           hard rule 2 (the share is a string, never a float)
// Server:   CR §9.IDN-2 — `co_owners: [{full_name*, relationship | title,
//           ownership_pct, signs_for_company, personal_guarantee,
//           date_of_birth, ssn, driving_licence, phone, email, contact_by,
//           responsible_for_bills}]`; the KIND is the account holder's, never
//           the clerk's, so this component sends only the fields its kind has.
// Tests:    moveInWizard/StepCustomer.dom.test.tsx
// ───────────────────────────────────────────────────────
//
// ⚠ **THE PHOTO ID IS NOT TAKEN HERE, AND THE BUTTON SAYS SO RATHER THAN
// VANISHING.** Image 38 draws *Photo ID [Upload]* on the card, but the photo is
// a filing card ON THE ACCOUNT (`account_co_owners.photo_id_document_id`), and
// the account does not exist until Complete (CR §9.IDN-2, *"Not here,
// stated"*). So the button is drawn disabled with its reason (BR-SHL-025) and
// the summary reads *No ID*; the upload itself is P2.24's Account-tab half.
import { useMutation } from "@tanstack/react-query";
import type { ReactNode } from "react";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";

import { Button } from "@/components/Button";
import type { RegionalDateFormat } from "@/components/DateCell";
import { nowInZone } from "@/components/DateCell";
import { UploadButton } from "@/components/FileField";
import { Disclosure } from "@/components/Disclosure";
import {
  CheckboxField,
  DatePickerField,
  FieldLabel,
  SelectField,
  TextField,
} from "@/components/FormModal";
import { Panel } from "@/components/Panel";
import type { Translator } from "@/features/tenancy/settingsShared";

import { uploadCoOwnerPhotoId } from "./customerEndpoints";

/** `co_owner_models.KINDS` — a person's account holds co-owners, a company's
 *  owners and officers. */
export type CoOwnerKind = "co_owner" | "officer";

/** `models.CONTACT_BY` — one vocabulary for the holder, a co-owner and a
 *  company's contact person (§9.1). */
export const CONTACT_BY = ["email", "text", "phone", "letter"] as const;

/**
 * Image 38's *Relationship*. ⚠ **A VOCABULARY OF OURS** (decision log
 * 2026-10-05, P2.24): `account_co_owners.relationship` is free text and no
 * rule names its values; these four cover the drawn *Spouse* without asking
 * the clerk to type it. The stored value is the code.
 */
export const RELATIONSHIPS = ["spouse", "partner", "family", "other"] as const;

/** One card, as the clerk types it. Every value a STRING (hard rule 2). */
export interface CoOwnerDraft {
  /** React key and nothing else — B14 rule 31. */
  key: string;
  full_name: string;
  relationship: string;
  title: string;
  ownership_pct: string;
  signs_for_company: boolean;
  personal_guarantee: boolean;
  date_of_birth: string;
  ssn: string;
  driving_licence: string;
  phone: string;
  email: string;
  contact_by: string;
  responsible_for_bills: boolean;
  /**
   * ⊕ Lane CF-1 (additive) — the MASK of an identifier the server already
   * holds for this person and will carry (`•••-••-2208`), for a card opened
   * from a request: the screen is only ever given the last four, so the box
   * stays empty and the summary says an ID is on file. Never sent.
   */
  id_on_file?: string;
}

let nextKey = 0;

export function emptyCoOwner(): CoOwnerDraft {
  nextKey += 1;
  return {
    key: `co-${Date.now().toString(36)}-${nextKey}`,
    full_name: "",
    relationship: "",
    title: "",
    ownership_pct: "",
    signs_for_company: false,
    personal_guarantee: false,
    date_of_birth: "",
    ssn: "",
    driving_licence: "",
    phone: "",
    email: "",
    contact_by: "",
    responsible_for_bills: false,
  };
}

/** The fields the server refuses on the other kind, by name (§9.IDN-2). */
const OFFICER_ONLY = ["title", "ownership_pct", "signs_for_company", "personal_guarantee"] as const;
const CO_OWNER_ONLY = ["relationship"] as const;

/**
 * The commit's `co_owners` rows for this kind — a blank is OMITTED, never
 * sent as `""`, and a field the other kind owns is never sent at all (the
 * server would refuse the whole move-in by its name).
 */
export function coOwnersPayload(
  kind: CoOwnerKind,
  rows: readonly CoOwnerDraft[],
): Record<string, unknown>[] {
  const skip: readonly string[] = kind === "officer" ? CO_OWNER_ONLY : OFFICER_ONLY;
  return rows.map((row) => {
    const out: Record<string, unknown> = {};
    for (const [name, value] of Object.entries(row)) {
      if (name === "key" || name === "id_on_file" || skip.includes(name)) continue;
      if (typeof value === "boolean") {
        if (value) out[name] = true;
      } else if (value.trim() !== "") {
        out[name] = value.trim();
      }
    }
    return out;
  });
}

/** A parked card, distrusted field by field (a draft is a week-old blob). */
export function hydrateCoOwners(raw: unknown): CoOwnerDraft[] {
  if (!Array.isArray(raw)) return [];
  return raw
    .filter((row): row is Record<string, unknown> => typeof row === "object" && row !== null)
    .map((row) => {
      const base = emptyCoOwner();
      const out: Record<string, unknown> = { ...base };
      for (const name of Object.keys(base)) {
        if (name === "key") continue;
        const value = row[name];
        if (typeof value === typeof out[name]) out[name] = value;
      }
      return out as unknown as CoOwnerDraft;
    });
}

/** Which card first holds the step: a card with no name (the server's
 *  `customers.contact.name_required` on `co_owners[i].full_name`). */
export function coOwnerProblem(rows: readonly CoOwnerDraft[]): string | null {
  return rows.some((row) => row.full_name.trim() === "")
    ? "customers.moveIn.customer.problem.coOwnerName"
    : null;
}

/**
 * **A PANEL WITH A TICK IN ITS HEADING** — *Has co-owners* (image 33), *Same
 * as service address* (images 33, 39). The tick is on the heading's right, as
 * drawn; the body is the host's. Exported because the mailing address is
 * "built like co-owners" (CR §8 P2.26) and two hand-rolled headings would be
 * two answers to one drawing.
 */
export function TickPanel(props: {
  name: string;
  title: string;
  tickId: string;
  tickLabel: string;
  ticked: boolean;
  onTick: (next: boolean) => void;
  children?: ReactNode;
}) {
  return (
    <Panel
      as="section"
      title={props.title}
      data-tick-panel={props.name}
      trailing={
        <CheckboxField
          id={props.tickId}
          label={props.tickLabel}
          checked={props.ticked}
          onChange={props.onTick}
        />
      }
    >
      {props.children}
    </Panel>
  );
}

/** The line a closed card shows after the name — image 38's *Spouse · (732)
 *  555-0144 · Responsible for bills · No ID*, image 40's *Managing member ·
 *  50% · Signs · No ID*. Facts only, each one present only when typed. */
/** ⊕ Lane CF-1 — the mask of a number the server holds (a request card's
 *  `ssn_last4` / `driving_licence_last4`), or `""` when it holds none. */
export function idOnFileMask(ssnLast4: string | null | undefined, licenceLast4: string | null | undefined): string {
  if ((ssnLast4 ?? "") !== "") return `•••-••-${ssnLast4}`;
  if ((licenceLast4 ?? "") !== "") return `•••• ${licenceLast4}`;
  return "";
}

/** The card's identifier as a mask (last four only, BR-CUS-092(c)), or null. */
export function idSummary(row: CoOwnerDraft): string | null {
  const lastFour = (value: string) => value.replace(/[^0-9A-Za-z]/g, "").slice(-4);
  if (row.ssn.trim() !== "") return `•••-••-${lastFour(row.ssn)}`;
  if (row.driving_licence.trim() !== "") return `•••• ${lastFour(row.driving_licence)}`;
  return row.id_on_file !== undefined && row.id_on_file !== "" ? row.id_on_file : null;
}

export function coOwnerSummary(kind: CoOwnerKind, row: CoOwnerDraft, t: Translator): string {
  const parts: string[] = [];
  if (kind === "co_owner") {
    if (row.relationship !== "") {
      parts.push(t(`customers.moveIn.customer.relationship.${row.relationship}`));
    }
    if (row.phone.trim() !== "") parts.push(row.phone.trim());
    if (row.responsible_for_bills) parts.push(t("customers.moveIn.customer.coOwner.responsibleShort"));
  } else {
    if (row.title.trim() !== "") parts.push(row.title.trim());
    if (row.ownership_pct.trim() !== "") {
      parts.push(t("customers.moveIn.customer.officer.shareShort", { pct: row.ownership_pct.trim() }));
    }
    if (row.signs_for_company) parts.push(t("customers.moveIn.customer.officer.signsShort"));
  }
  // ⊕ `DEF-CUS-10232` (lane CF-1) — the ID part says what is held: a typed
  // SSN or licence as its mask, a number on file from a request as its mask,
  // and *No ID* only when there is none. It read *No ID* on every card.
  parts.push(idSummary(row) ?? t("customers.moveIn.customer.coOwner.noId"));
  return parts.join(" · ");
}

/**
 * Lane CF-1 (2026-10-18), task 6 — the WORDS a host calls the people beside
 * the holder: *Co-owners* (Move-in, New connect), *Co-applicants* (the
 * service request), *Co-buyers* (Transfer). The card, the fields and the
 * payload are one; only the heading, the tick and the add button differ.
 */
export type CoOwnerLabel = "co_owner" | "co_applicant" | "co_buyer";

const LABEL_KEYS: Record<CoOwnerLabel, { title: string; tick: string; add: string }> = {
  co_owner: {
    title: "customers.moveIn.customer.coOwners.title",
    tick: "customers.moveIn.customer.coOwners.tick",
    add: "customers.moveIn.customer.coOwners.add",
  },
  co_applicant: {
    title: "customers.form.coApplicants.title",
    tick: "customers.form.coApplicants.tick",
    add: "customers.form.coApplicants.add",
  },
  co_buyer: {
    title: "customers.form.coBuyers.title",
    tick: "customers.form.coBuyers.tick",
    add: "customers.form.coBuyers.add",
  },
};

/** Format checks for a card — the shared form's (`customerForm/
 *  CustomerWhoPanel.tsx`), restated here as two one-liners so this file does
 *  not import the panel that imports it. Blank is no error. */
function phoneShapeProblem(value: string): string | null {
  const typed = value.trim();
  if (typed === "") return null;
  const digits = typed.replace(/\D/g, "");
  const ok =
    /^[+\d\s().-]+$/.test(typed) &&
    (digits.length === 10 || (digits.length === 11 && digits.startsWith("1")));
  return ok ? null : "customers.form.phoneInvalid";
}

function emailShapeProblem(value: string): string | null {
  const typed = value.trim();
  if (typed === "") return null;
  return /^[^\s@]+@[^\s@.]+(\.[^\s@.]+)+$/.test(typed) ? null : "customers.form.emailInvalid";
}

/** The first card whose phone or email is malformed, as a catalogue key. */
export function coOwnerFormatProblem(rows: readonly CoOwnerDraft[]): string | null {
  for (const row of rows) {
    const problem = phoneShapeProblem(row.phone) ?? emailShapeProblem(row.email);
    if (problem !== null) return problem;
  }
  return null;
}

export function CoOwnerCards(props: {
  kind: CoOwnerKind;
  /** The heading's tick — *Has co-owners* / *Has owners or officers*. */
  enabled: boolean;
  onEnabledChange: (next: boolean) => void;
  rows: readonly CoOwnerDraft[];
  onChange: (rows: CoOwnerDraft[]) => void;
  t: Translator;
  dateFormat: RegionalDateFormat;
  timeZone: string;
  showErrors: boolean;
  /** What a person's co-owners are called on this screen (default
   *  `co_owner`). A company's officers keep their own words. */
  label?: CoOwnerLabel;
  /** The *Photo ID* box. Default true (Move-in and New connect, where the
   *  photo is filed on the account after Complete — the button says so). A
   *  host with nowhere to file one (the service request) passes false. */
  showPhotoId?: boolean;
  /** Lane CF-1 (additive) — the licence masked with Show/Hide, as New
   *  connect's co-applicant has had it since `DEF-CUS-9826` (N6). */
  licenceMasked?: boolean;
}) {
  const { t, kind, rows } = props;
  const officer = kind === "officer";
  const licenceMasked = props.licenceMasked === true;
  const words = LABEL_KEYS[props.label ?? "co_owner"];
  const set = (index: number, patch: Partial<CoOwnerDraft>) =>
    props.onChange(rows.map((row, at) => (at === index ? { ...row, ...patch } : row)));
  const today = nowInZone(props.timeZone).slice(0, 10);
  const shown = (problem: string | null): string | undefined =>
    props.showErrors && problem !== null ? t(problem) : undefined;

  return (
    <TickPanel
      name={kind}
      title={t(officer ? "customers.moveIn.customer.officers.title" : words.title)}
      tickId={`${kind}_enabled`}
      tickLabel={t(officer ? "customers.moveIn.customer.officers.tick" : words.tick)}
      ticked={props.enabled}
      onTick={(next) => {
        props.onEnabledChange(next);
        // Ticking with nothing yet opens the first card — the drawn state.
        if (next && rows.length === 0) props.onChange([emptyCoOwner()]);
      }}
    >
      {props.enabled ? (
        <div className="flex flex-col gap-3" data-co-owner-cards={kind}>
          {rows.map((row, index) => {
            const id = (field: string) => `${kind}_${index}_${field}`;
            const name = row.full_name.trim();
            const removeLabel = t("customers.moveIn.customer.coOwners.remove", {
              name: name === "" ? String(index + 1) : name,
            });
            return (
              <Disclosure
                key={row.key}
                variant="card"
                defaultOpen={name === ""}
                title={name === "" ? t("customers.moveIn.customer.coOwners.unnamed") : name}
                summary={coOwnerSummary(kind, row, t)}
              >
                {/* Images 01 and 12, row by row: name · relationship (or an
                    officer's title and share) · responsible for bills; phone ·
                    email · date of birth; SSN · licence · photo ID. */}
                <div className="grid grid-cols-3 gap-x-6 gap-y-5" data-co-owner-card={String(index + 1)}>
                  <TextField
                    id={id("full_name")}
                    label={t("customers.account.field.fullName")}
                    required
                    value={row.full_name}
                    onChange={(value) => set(index, { full_name: value })}
                  />
                  {officer ? (
                    <>
                      <TextField
                        id={id("title")}
                        label={t("customers.moveIn.customer.officer.title")}
                        value={row.title}
                        onChange={(value) => set(index, { title: value })}
                      />
                      <TextField
                        id={id("ownership_pct")}
                        label={t("customers.moveIn.customer.officer.share")}
                        numeric
                        value={row.ownership_pct}
                        onChange={(value) => set(index, { ownership_pct: value })}
                      />
                    </>
                  ) : (
                    <>
                      <SelectField
                        id={id("relationship")}
                        label={t("customers.moveDetail.col.relationship")}
                        placeholder={t("customers.moveIn.customer.choose")}
                        value={row.relationship}
                        options={RELATIONSHIPS.map((code) => ({
                          value: code,
                          label: t(`customers.moveIn.customer.relationship.${code}`),
                        }))}
                        onChange={(value) => set(index, { relationship: value })}
                      />
                      <SelectField
                        id={id("responsible_for_bills")}
                        label={t("customers.moveIn.customer.coOwner.responsibleShort")}
                        value={row.responsible_for_bills ? "yes" : "no"}
                        options={[
                          { value: "yes", label: t("customers.form.yes") },
                          { value: "no", label: t("customers.form.no") },
                        ]}
                        onChange={(value) => set(index, { responsible_for_bills: value === "yes" })}
                      />
                    </>
                  )}
                  <TextField
                    id={id("phone")}
                    label={t("customers.account.field.phone")}
                    autoComplete="tel"
                    value={row.phone}
                    error={shown(phoneShapeProblem(row.phone))}
                    onChange={(value) => set(index, { phone: value })}
                  />
                  <TextField
                    id={id("email")}
                    label={t("customers.account.field.email")}
                    autoComplete="email"
                    value={row.email}
                    error={shown(emailShapeProblem(row.email))}
                    onChange={(value) => set(index, { email: value })}
                  />
                  <DatePickerField
                    id={id("date_of_birth")}
                    label={t("customers.account.field.dob")}
                    regional
                    value={row.date_of_birth}
                    max={today}
                    dateFormat={props.dateFormat}
                    onChange={(value) => set(index, { date_of_birth: value })}
                  />
                  <TextField
                    id={id("ssn")}
                    label={t("customers.newAccount.field.ssn")}
                    autoComplete="off"
                    masked
                    revealable
                    value={row.ssn}
                    onChange={(value) => set(index, { ssn: value })}
                  />
                  <TextField
                    id={id("driving_licence")}
                    label={t("customers.newAccount.field.drivingLicence")}
                    autoComplete="off"
                    masked={licenceMasked}
                    revealable={licenceMasked}
                    value={row.driving_licence}
                    onChange={(value) => set(index, { driving_licence: value })}
                  />
                  {props.showPhotoId === false ? null : (
                    <div className="field" data-co-owner-photo="">
                      <FieldLabel
                        htmlFor={id("photo")}
                        label={t("customers.moveDetail.col.photoId")}
                        required={false}
                      />
                      <div>
                        <Button
                          id={id("photo")}
                          size="sm"
                          disabled
                          title={t("customers.moveIn.customer.coOwner.photoLater")}
                          aria-describedby={id("photo_help")}
                        >
                          {t("customers.moveIn.customer.upload")}
                        </Button>
                      </div>
                      <p className="field-help mt-1.5 mb-0" id={id("photo_help")}>
                        {t("customers.moveIn.customer.coOwner.photoLater")}
                      </p>
                    </div>
                  )}
                  {/* *Contact by* is not drawn on the card (image 12) and is
                      kept: a value already typed on a parked draft or a
                      request still travels, and dropping the box would make
                      it unreachable. It sits last, after what is drawn. */}
                  <SelectField
                    id={id("contact_by")}
                    label={t("customers.moveDetail.col.contactBy")}
                    placeholder={t("customers.moveIn.customer.choose")}
                    value={row.contact_by}
                    options={CONTACT_BY.map((code) => ({
                      value: code,
                      label: t(`customers.moveDetail.contactBy.${code}`),
                    }))}
                    onChange={(value) => set(index, { contact_by: value })}
                  />
                </div>
                {officer ? (
                  <div className="mt-4 flex flex-wrap gap-6">
                    <CheckboxField
                      id={id("signs_for_company")}
                      label={t("customers.moveIn.customer.officer.signs")}
                      checked={row.signs_for_company}
                      onChange={(checked) => set(index, { signs_for_company: checked })}
                    />
                    <CheckboxField
                      id={id("personal_guarantee")}
                      label={t("customers.moveIn.customer.officer.guarantee")}
                      checked={row.personal_guarantee}
                      onChange={(checked) => set(index, { personal_guarantee: checked })}
                    />
                    <CheckboxField
                      id={id("responsible_for_bills")}
                      label={t("customers.moveIn.customer.coOwner.responsible")}
                      checked={row.responsible_for_bills}
                      onChange={(checked) => set(index, { responsible_for_bills: checked })}
                    />
                  </div>
                ) : null}
                <div className="mt-4">
                  <Button
                    data-co-owner-remove={String(index + 1)}
                    onClick={() => props.onChange(rows.filter((_, at) => at !== index))}
                  >
                    {removeLabel}
                  </Button>
                </div>
              </Disclosure>
            );
          })}
          <div className="flex items-center justify-between gap-3">
            <p className="m-0 text-sm text-neutral-700" data-co-owner-count="">
              {t("customers.moveIn.customer.coOwners.added", { count: rows.length })}
            </p>
            <Button data-co-owner-add="" onClick={() => props.onChange([...rows, emptyCoOwner()])}>
              {t(officer ? "customers.moveIn.customer.officers.add" : words.add)}
            </Button>
          </div>
          {props.showErrors && coOwnerProblem(rows) !== null ? (
            <p role="alert" className="field-error m-0" data-co-owner-problem="">
              {t(coOwnerProblem(rows) ?? "")}
            </p>
          ) : null}
        </div>
      ) : null}
    </TickPanel>
  );
}

/**
 * **P2.24's SECOND HALF — THE PHOTO ID, ON THE ACCOUNT TAB (image 25).** One
 * control for one co-owner row: *Upload* while the row has no ID, and the
 * upload files it on the account and points the row at it
 * (`POST /accounts/{id}/co-owners/{coOwnerId}/photo-id`). `onDone` lets the
 * host re-read its table. Built here, beside the cards, so the move-in has one
 * co-owner component file (B14 rule 43); the Account tab mounts it.
 */
export function CoOwnerPhotoIdUpload(props: {
  accountId: string;
  /** The row's handle — never shown (B14 rule 31). */
  coOwnerId: string;
  name: string;
  t: Translator;
  onDone: () => void;
  client?: ApiClient;
}) {
  const { t } = props;
  const upload = useMutation({
    mutationFn: (file: File) =>
      uploadCoOwnerPhotoId(props.accountId, props.coOwnerId, file, props.client ?? api),
    onSuccess: () => props.onDone(),
  });
  return (
    <span className="inline-flex items-center gap-2" data-co-owner-photo-upload={props.coOwnerId}>
      <UploadButton
        id={`co-owner-photo-${props.coOwnerId}`}
        label={upload.isPending ? t("states.loading") : t("customers.moveIn.customer.upload")}
        name={t("customers.moveIn.customer.coOwner.photoFor", { name: props.name })}
        accept=".pdf,.png,.jpg,.jpeg,application/pdf,image/png,image/jpeg"
        disabled={upload.isPending}
        onFile={(file) => upload.mutate(file)}
      />
      {upload.isError ? (
        <span role="alert" className="field-error m-0">
          {t("customers.moveIn.customer.docs.uploadFailed")}
        </span>
      ) : null}
    </span>
  );
}
