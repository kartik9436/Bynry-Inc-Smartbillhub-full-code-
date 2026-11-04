// ── Trace ──────────────────────────────────────────────
// Change:   Lane E wave 1 — SPLIT OUT OF `NewConnectWizard.tsx`, unchanged.
//           Lane TEXT — 2026-09-28 — six sentences deleted (PO reported bug 1).
//           **Lane CUSTOMER-PREMISE — 2026-09-29 — REBUILT FROM THE DRAWING**
//           `05-prototype/new-connect-redesign-2026-09-28/step1-customer.png`,
//           read AS AN IMAGE (B14 rule 42) and built with our own kit
//           (rule 44). `CR-150-BRC09` `NCT-01` tasks 4 and 5.
// Rules:    BR-MET-111 (the owner captured here BECOMES a customer, which is
//           what makes them billable at the charges step — DEF-650) ·
//           BR-CUS-1022/1023/1024 (party kind + one identifier, or the door
//           refuses the master account) · BR-CUS-053 (the account CATEGORY is
//           the tenant's own list) · BR-SHL-025 (a control that cannot act is
//           DISABLED WITH ITS REASON) · CLAUDE.md hard rule 8 (an address
//           lives on `premises`; `kind='mailing'` is one of its three named
//           exceptions) · B14 rule 21 (Tailwind only; this file is on
//           `src/styles/route-b-migrated.txt`) · rule 31 (no database id on
//           screen) · rule 32 · rule 33 · rule 37 (a drawn figure is an
//           illustration) · rule 42 · rule 43 (reuse the component, never
//           inline a second one) · rule 44 (the drawing arranges; our UI
//           standard builds)
// Questions: OQ-249 (Work is R5 — the *"We schedule it"* mode is disabled by
//           name, matching `_check_mode`'s `NotImplementedError`)
// Tests:    newConnectSteps12Redesign.dom.test.tsx · NewConnectWizard.test.tsx
// ───────────────────────────────────────────────────────
//
// ══════════════════════════════════════════════════════════════════════════
// STEP 1 · CUSTOMER — *"Who is asking, and what for?"*
// ══════════════════════════════════════════════════════════════════════════
//
// ⚠ **THE FILE IS STILL CALLED `NewConnectOwnerStep.tsx` AND THE STEP IS
// CALLED `customer`.** The rail word is the PO's and the step id moved with
// it; renaming a file is a separate, noisy act and is recorded as a tidy-up in
// `05-prototype/new-connect-redesign-2026-09-28/DIVERGENCES-steps-1-2.md`
// rather than done inside this build. **An *owner type* field is not a step
// id** — the two read identically and only one of them changed.
//
// ── WHAT THE DRAWING SETTLED THAT THE OLD SCREEN GOT WRONG ────────────────
//   * **`Search customer ID` and `Account details` are ONE BLOCK.** PO,
//     verbatim: *"Existing customer B2A - this should be search Customer ID …
//     Account details … this should merge with Search customer ID"*. They were
//     two places on the old screen and the search sat ABOVE the owner's fields;
//     the drawing puts the merged block BELOW them, which is why the help line
//     reads *"Searched on the details entered above."* — the search is run on
//     what has just been typed rather than on a term hunted for first.
//   * **`Scope` and `Mode` are no longer *What is built* / *How it's done*.**
//     Scope MOVES TO STEP 2 (the drawing's own *Removed from this step* list),
//     and Mode becomes the `Work` panel's one dropdown beside `Reference`.
//   * **Documents sit BELOW the co-applicant**, not at the foot of the step.
//     PO: *"Documents B4Q2 - it should be below Co-applicant"*.
//   * **Five things the old screen never asked for at all**: the customer
//     CATEGORY, a date of birth, the communication preferences, a co-applicant
//     and a mailing address.
//
// ── THE PANEL ORDER IS THE DRAWING'S OWN, CONFIRMED 28 SEP ────────────────
// *"Owner → Gov-ID & Communication → Co-applicant & Mailing → Documents →
// Search customer ID (with account details) → Reference & Work."*
//
// ── WHY THE FIELDS ARE IN A GRID AND NOT A STACK ──────────────────────────
// ⚠ **THIS FILE USED `FieldStack` AND CITED B14 RULE 38 FOR IT.** Rule 44
// (2026-09-24) is rule 38 with its scope removed and it splits the two halves
// the other way round: **the drawing says what is on the screen AND HOW IT IS
// ARRANGED**; our standard says how it is BUILT — spacing, sizes, the type
// scale, the tokens and the component kit. Three columns is an ARRANGEMENT,
// and the kit already owns a three-column form grid (`FieldGrid`), so
// following the drawing here costs the standard nothing and re-lays no dialog
// anywhere else in the product.
import { useQuery } from "@tanstack/react-query";

import type { ApiClient } from "@/api/client";

import { getLookupEntries } from "@/api/endpoints";
import { SelectField, TextField } from "@/components/FormModal";
import { CustomFieldsInput, useCustomFieldRegistry } from "@/components/CustomFields";
import { Panel } from "@/components/Panel";

import type { DocumentRow } from "@/components/documents";
import { useRegional } from "@/features/metering/meteringShared";

import { accountSubtypesUnder } from "./customersShared";
import type { AccountSubtypeRow } from "./customersShared";
import {
  connectModeWord,
  OWNER_KINDS,
  OWNER_SUBCATEGORIES,
} from "./newConnectDraft";
import type { DraftDocument, NewConnectDraft, OwnerForm } from "./newConnectDraft";
import type { RequestPrefillDocument } from "./newConnectEndpoints";
import { NewConnectCustomerForm } from "./NewConnectCustomerForm";
import type { Translator } from "./newConnectShared";
import { accountIdentityShortfall, emptyCustomerForm } from "./NewAccountWizard";
import { StepIntro } from "./newConnectStepKit";
import { FieldGrid } from "./serviceRequestShared";

// ⊕ **THE FINDER IS A COMPONENT — `DEF-CUS-6386`, B14 rule 43.** The four
// names below are RE-EXPORTED so every existing import keeps working.
export {
  CUSTOMER_SEARCH_IDLE,
  MIN_CUSTOMER_SEARCH_CHARS,
  customerFinderLabel,
  useCustomerSearch,
} from "./CustomerFinder";
export type { CustomerSearchState } from "./CustomerFinder";

/**
 * Does what the clerk has typed earn the owner an ACCOUNT? The catalogue key of
 * the one thing missing, or `null`.
 *
 * ⚠ **THE RULE IS NOT RESTATED HERE.** It is `accountIdentityShortfall`'s —
 * `BR-CUS-1023` / `BR-CUS-1024`, shared with the new-account, move-in and
 * transfer wizards — and a fourth copy of *what counts as an identifier* is a
 * fourth thing to drift the day a fifth identifier arrives.
 *
 * ⚠ **AN ATTACHED CUSTOMER NEEDS NO EVIDENCE, AND THAT IS THE SERVER'S RULE
 * TOO.** `refuse_account_without_identity` returns early when the payload names
 * a `customer_id`.
 */
export function ownerIdentityShortfall(owner: OwnerForm): string | null {
  if (owner.matchedCustomerId !== null) return null;
  // ⊕ `DEF-CUS-9074` — a business whose Tax ID is on its portal application
  // is identified already; the server carries the number (`DEF-CWP-9045`).
  if (
    owner.partyKind === "company" &&
    owner.taxId.trim() === "" &&
    (owner.applicationTaxIdLast4 ?? "") !== "" &&
    owner.name.trim() !== ""
  ) {
    return null;
  }
  return accountIdentityShortfall({
    ...emptyCustomerForm(),
    full_name: owner.name,
    customer_kind: owner.partyKind,
    phone: owner.phone,
    ssn: owner.ssn,
    driving_licence: owner.drivingLicence,
    tax_id: owner.taxId,
  });
}

/**
 * The shortfall as the sentence CONTINUE shows, or `null` when the map has no
 * sentence for it.
 *
 * ⚠ **IT IS READ BY THE WIZARD'S `validate`, NOT RENDERED BESIDE THE FIELDS**
 * (PO 2026-09-28, reported bug 1). The drawing lists *"Name the owner first."*
 * under *Removed from this step* with the note *"shown only as an error on
 * Continue"*. **Nothing is now allowed through that was refused before.**
 */
export function ownerShortfallSentence(shortfall: string, t: Translator): string | null {
  const sentence = SHORTFALL_SENTENCE[shortfall];
  return sentence === undefined ? null : t(sentence.key, { defaultValue: sentence.en });
}

// ⊕ lane CF-1 — moved to `newConnectOwnerRules.ts`, re-exported unchanged.
export {
  ownerBirthDateProblem,
  ownerBirthDateSentence,
  ownerHasABirthDate,
  todayIn,
} from "./newConnectOwnerRules";

/**
 * ── `DEF-CUS-9192` — *Owner type* IS THE UTILITY'S OWN LIST ──────────────────
 * `/lookups/owner_categories` (`BR-TEN-150`), which a utility edits on Settings.
 * It was four hand-typed codes of which three matched nothing in that list.
 *
 * ⚠ **A STORED CODE THE LIST NO LONGER HOLDS IS KEPT AND NAMED**, never dropped:
 * a parked draft written before this change carries one of the four old codes,
 * and silently blanking it would be the screen answering for the clerk.
 */
export const OWNER_CATEGORIES_QUERY_KEY = ["lookups", "owner_categories"] as const;

export function ownerKindOptions(
  rows: readonly { code: string; name: string; active?: boolean }[],
  stored: string,
  t: Translator,
): { value: string; label: string }[] {
  const options = rows
    .filter((row) => row.active !== false)
    .map((row) => ({ value: row.code, label: row.name }));
  if (stored !== "" && !options.some((option) => option.value === stored)) {
    const legacy = OWNER_KINDS.find((kind) => kind.code === stored);
    options.push({
      value: stored,
      label:
        legacy !== undefined
          ? t(`customers.newConnect.ownerKind.${legacy.code}`, { defaultValue: legacy.en })
          : stored,
    });
  }
  return options;
}

/**
 * ── `DEF-CUS-9822` (N1) — STEP 1's SUB-CATEGORY IS THE UTILITY'S OWN LIST ────
 * The ACTIVE sub-types under the chosen category (`accountSubtypesUnder`) —
 * the same rows, under the same rule, that move-in and request capture offer.
 *
 * ⚠ **A STORED CODE FROM BEFORE THIS CHANGE IS KEPT AND NAMED, NEVER
 * OFFERED.** A parked draft may hold `construction_temporary` or `permanent`
 * (`OWNER_SUBCATEGORIES`); it reads as its word in a DISABLED option so the
 * clerk sees what was chosen and cannot choose it again. It is never sent as
 * the account's sub-type (`ownerAccountSubtype` in `newConnectDraft.ts`).
 */
export function ownerSubcategoryOptions(
  rows: readonly AccountSubtypeRow[],
  category: string,
  stored: string,
  t: Translator,
): { value: string; label: string; disabled?: boolean }[] {
  const options: { value: string; label: string; disabled?: boolean }[] = accountSubtypesUnder(
    rows,
    category,
  ).map((row) => ({ value: row.code, label: row.name }));
  if (stored !== "" && !options.some((option) => option.value === stored)) {
    const legacy = OWNER_SUBCATEGORIES.find((row) => row.code === stored);
    if (legacy !== undefined) {
      options.push({
        value: stored,
        label: t(`customers.newConnect.ownerSub.${legacy.code}`, { defaultValue: legacy.en }),
        disabled: true,
      });
    }
  }
  return options;
}

const SHORTFALL_SENTENCE: Record<string, { key: string; en: string }> = {
  "customers.account.identity_name_required": {
    key: "customers.newConnect.step1.needName",
    en: "Name the owner first.",
  },
  "customers.account.identity_kind_required": {
    key: "customers.newConnect.step1.needKind",
    en: "Say person or company.",
  },
  "customers.account.identity_required_person": {
    key: "customers.newConnect.step1.needPerson",
    en: "Needs one identifier to continue.",
  },
  "customers.account.identity_required_company": {
    key: "customers.newConnect.step1.needCompany",
    en: "Add the Tax ID.",
  },
};

/*
 * ⊖ **LANE CF-1 (2026-10-18) — `OwnerFieldSet`, `CoApplicantFieldSet`,
 * `GovIdFields` AND THE OWNER LOOKUP CARD ARE DELETED, NOT HIDDEN.** The step
 * now mounts Move-in's shared customer form (`NewConnectCustomerForm`, drawing
 * set `customer-forms-2026-10-18` image 06): its Who and Identity panels ask
 * what these asked, its *Search customer ID* replaces the automatic card, and
 * its co-owner cards replace the one co-applicant. A second copy kept "just in
 * case" is the four-forms defect (`DEF-CUS-10225`) this lane closes.
 */

export function OwnerScopeStep(props: {
  draft: NewConnectDraft;
  onPatch: (next: Partial<NewConnectDraft>) => void;
  t: Translator;
  /** ⊕ `CR-164-BRC10` — the owner lookup's client; absent means the app's. */
  client?: ApiClient;
  /** ⊕ lane CF-1 — Continue was pressed: the shared form shows its refusals. */
  showErrors?: boolean;
}) {
  const { t } = props;
  const setOwner = (patch: Partial<OwnerForm>) =>
    props.onPatch({ owner: { ...props.draft.owner, ...patch } });
  const { dateFormat, timeZone } = useRegional({});
  // `DEF-CUS-9192` — the utility's own owner list (`BR-TEN-150`).
  const ownerCategories = useQuery({
    queryKey: OWNER_CATEGORIES_QUERY_KEY,
    queryFn: () => getLookupEntries("owner_categories", { per: 200 }, props.client),
    staleTime: 5 * 60 * 1000,
    retry: false,
  });
  const ownerRows = ownerCategories.data?.results ?? [];
  const accountFields =
    useCustomFieldRegistry({ entity: "accounts", screen: "S18", mode: "input", client: props.client })
      .data ?? [];
  return (
    <>
      {/* ══════════════════════════════════════════════════════════════════
          ⊕ LANE CF-1 (2026-10-18) — THE SHARED CUSTOMER FORM
          ══════════════════════════════════════════════════════════════════
          Drawing set `customer-forms-2026-10-18`, image 06, read as an IMAGE
          (B14 rule 42): *Who will own the account* · *Identity* with *Search
          customer ID* and Move-in's results table · *More about the customer*
          · *Co-owners* · *Documents* · *Mailing address* — Move-in's own
          pieces (rule 43). They replace this step's Owner, Gov-ID,
          Communication, Existing customer, Co-applicant, Mailing and
          Documents panels; the Communication answers move to the charges
          step's *Preferences*, where image 02 draws them. */}
      <NewConnectCustomerForm
        draft={props.draft}
        onPatch={props.onPatch}
        showErrors={props.showErrors === true}
        t={t}
        dateFormat={dateFormat}
        timeZone={timeZone}
        client={props.client}
        ownerTypeField={
          <SelectField
            id="nc_owner_kind"
            label={t("customers.newConnect.step1.kind", { defaultValue: "Owner type" })}
            required
            value={props.draft.owner.kind}
            onChange={(kind) => setOwner({ kind })}
            placeholder={t("customers.newConnect.step1.kindPlaceholder", {
              defaultValue: "Choose an owner type",
            })}
            options={ownerKindOptions(ownerRows, props.draft.owner.kind, t)}
          />
        }
        onOpenHeldFile={(localId: string) => {
          const row = draftDocumentRows(props.draft.ownerDocuments).find((one) => one.id === localId);
          if (row !== undefined) openDraftDocument(row, props.draft.ownerDocuments);
        }}
      />

      {/* ══════════════════════════════════════════════════════════════════
          ACCOUNT DETAILS — ITS OWN PANEL SINCE `CR-164-BRC10`
          ══════════════════════════════════════════════════════════════════
          It shared a panel with *Search customer ID*, which PO item 11 of
          2026-10-02 removed (the lookup now runs by itself, above). The
          panel is drawn only when the utility placed a field here, so a
          utility with none sees no heading over nothing (`US-SHL-015` TC-4). */}
      {accountFields.length > 0 && (
      <Panel as="section" data-step-content="account-details-panel">
        {/* ══ ACCOUNT DETAILS — THE TENANT'S OWN FIELDS ═══════════════════
            ⚠ **THE DRAWING ANSWERS THE PO'S QUESTION AND THE ANSWER IS
            *TYPED, BY THE CLERK, FROM THE UTILITY'S OWN LIST*.** Its note:
            *"The clerk fills these in. They are the extra fields this utility
            set up in Settings, so the three drawn here are only an example. A
            list field offers the utility's own list; a text field is typed.
            Nothing appears if the utility set none up."* That is
            `CustomFieldsInput` exactly, so *Service area · Rate class code ·
            Legacy account no.* are NOT typed into this file (B14 rule 37 —
            every drawn figure is an illustration).

            ⚠ **`S18` IS THE SLOT, NOT A NEW ONE.** `custom_fields.SLOTS`
            (the one served list, `CR-161-BRC10`) gives `accounts` two rendered
            input placements, `S18` and `S21`; `S18` is the account-CREATION
            slot the new-account wizard already uses, so a field a utility
            placed there appears in BOTH doors that create an account rather
            than in one of them. ⚠ **WHAT IS TYPED HERE WAS DROPPED AT COMMIT
            UNTIL `CR-161-BRC10` W3 (`DEF-CUS-9159`)** — `commitPlanOf` now
            sends `accountCustomData` as the owner block's `custom_data`, and
            `create_owner_account` passes it to the account door.

            ⚠ **IT RENDERS NOTHING AT ALL WHEN THE UTILITY DEFINED NONE**
            (`US-SHL-015` TC-4), which is the drawing's own last sentence. */}
        <div data-step-content="account-details">
          <StepIntro
            title={t("customers.newConnect.step1.accountDetails", { defaultValue: "Account details" })}
          />
          <CustomFieldsInput
            entity="accounts"
            screen="S18"
            values={props.draft.accountCustomData}
            onChange={(accountCustomData) => props.onPatch({ accountCustomData })}
            client={props.client}
          />
        </div>
      </Panel>
      )}

      {/* ══════════ REFERENCE · WORK — side by side, as drawn ═════════════ */}
      <div className="grid grid-cols-2 gap-x-6 gap-y-5 max-lg:grid-cols-1">
        <Panel as="section" data-step-content="reference">
          <StepIntro
            title={t("customers.newConnect.step1.reference", { defaultValue: "Reference" })}
          />
          <FieldGrid columns={2}>
            <TextField
              id="nc_prefix"
              label={t("customers.newConnect.step1.prefix", { defaultValue: "Prefix" })}
              value={props.draft.pattern.prefix}
              onChange={(prefix) =>
                props.onPatch({ pattern: { ...props.draft.pattern, prefix } })
              }
            />
            {/* ⚠ **THE DRAWING DRAWS A DROPDOWN AND THIS IS A TEXT BOX, AND
                THE DRAWING ITSELF FLAGS IT** — its open-question `A` reads
                *"External system reference drawn as a dropdown — what fills
                the list?"*. Nothing answers that, and a `<select>` with no
                list behind it is a control that cannot act. It stays the box
                it has always been until the question is ruled. */}
            <TextField
              id="nc_external_ref"
              label={t("customers.newConnect.step1.externalRef", {
                defaultValue: "External system reference",
              })}
              value={props.draft.owner.externalRef}
              onChange={(externalRef) => setOwner({ externalRef })}
            />
          </FieldGrid>
        </Panel>

        {/* ══════════════════ WORK ════════════════════════════════════════
            ⚠ **THE DRAWING MAKES THIS A DROPDOWN AND THAT IS WHAT IS BUILT**
            — it was a segmented control plus a dead button beside it. The
            third mode is still refused: `we_schedule` raises
            `NotImplementedError("OQ-249")` on the server, so it is DRAWN IN
            THE LIST AND DISABLED rather than offered and then refused
            (`BR-SHL-025`, B14 rule 37 — the drawing's own *We schedule it
            (disabled)*).

            ⚠ **THE PARAGRAPH UNDER IT IS GONE.** *"Coming with the Work
            module — crews, dispatch and scheduling are a later release."* is
            the definition of rule 33's RATIONALE — why a control is absent —
            at zero words on screen, and rationale is REMOVED rather than
            shortened. **The unselectable option is itself the statement**: the
            clerk learns the mode exists and learns they cannot pick it, which
            is what `BR-SHL-025` is for, without a paragraph. The words live in
            this comment and in `OQ-249`. */}
        <Panel as="section" data-step-content="work">
          <StepIntro title={t("customers.newConnect.step1.work", { defaultValue: "Work" })} />
          <SelectField
            id="nc_mode"
            label={t("customers.newConnect.step2.mode", { defaultValue: "Mode" })}
            required
            value={props.draft.mode}
            onChange={(mode) => props.onPatch({ mode })}
            /* ⚠ **THE WORDS COME FROM `CONNECT_MODES`, NOT FROM THIS FILE
                (`DEF-CUS-6100`).** They were typed out here and nowhere else,
                which is what let the REVIEW screen invent its own fallback and
                print `our_crew` to a clerk. */
            options={[
              { value: "our_crew", label: connectModeWord("our_crew", t) },
              { value: "external", label: connectModeWord("external", t) },
              {
                value: "we_schedule",
                label: connectModeWord("we_schedule", t),
                disabled: true,
              },
            ]}
          />
        </Panel>
      </div>
    </>
  );
}

/** What the clerk has taken so far, in the shape the shared table reads.
 *
 *  ⚠ **`uploaded_at` AND `uploaded_by_name` ARE `null` BECAUSE NOTHING HAS
 *  BEEN UPLOADED**, and the table draws that honestly — the drawing's own
 *  *hidden until created?* on both columns, confirmed 28 Sep. A date here
 *  would be the moment a file was CHOSEN, which is a different fact from the
 *  moment it was filed. */
/**
 * ⊕ **`DEF-CUS-9825` (N5) — VIEW A FILE THAT EXISTS ONLY IN THIS BROWSER.**
 * Nothing is uploaded before Create (`BR-MET-112`), so the draft's file is
 * opened from the browser's own copy through an object URL, which is revoked a
 * minute later — long enough for the new tab to load it, and never left alive
 * for the life of the page. Returns the URL it opened, or `null`.
 */
export function openDraftDocument(
  row: DocumentRow,
  held: readonly DraftDocument[],
  open: (url: string) => void = (url) => {
    window.open(url, "_blank", "noopener,noreferrer");
  },
): string | null {
  const doc = held.find((one) => one.id === row.id);
  if (doc === undefined) return null;
  const url = URL.createObjectURL(doc.file);
  open(url);
  setTimeout(() => URL.revokeObjectURL(url), 60_000);
  return url;
}

/** ⊕ `DEF-CUS-9828` (N2) — the request's documents in the shared table's
 *  shape, unchanged: who brought it, when, and the verdict already recorded on
 *  the request (verified / not checked). */
export function requestDocumentRows(held: readonly RequestPrefillDocument[]): DocumentRow[] {
  return held.map((doc) => ({
    id: doc.id,
    doc_type: doc.doc_type,
    what_it_proves: doc.what_it_proves,
    document_number: doc.document_number,
    name: doc.name,
    uploaded_at: doc.uploaded_at,
    uploaded_by_name: doc.uploaded_by_name,
    uploaded_by_role: doc.uploaded_by_role ?? null,
    required: doc.required,
    size_bytes: doc.size_bytes,
    original_size_bytes: doc.original_size_bytes,
    file_present: doc.file_present,
    content_type: doc.content_type ?? null,
    verification_state: doc.verification_state,
    reject_reason: doc.reject_reason,
  }));
}

export function draftDocumentRows(held: readonly DraftDocument[]): DocumentRow[] {
  return held.map((doc) => ({
    id: doc.id,
    doc_type: doc.docType,
    what_it_proves: doc.whatItProves === "" ? null : doc.whatItProves,
    // ⚠ **CARRIED AT LAST — the drawn `DOCUMENT NUMBER` column.** This read
    // `null` unconditionally until 2026-09-29 and its own comment said why:
    // the shared form asked for a number and `DraftDocument` had nowhere to
    // keep it, so what the clerk typed was dropped between the form and the
    // table. `DraftDocument.documentNumber` closes that half.
    document_number:
      doc.documentNumber === undefined || doc.documentNumber === "" ? null : doc.documentNumber,
    name: doc.name,
    // ⊕ `DEF-CUS-9824` (N4, PO 2026-10-06) — the clerk who attached it and
    // when, while it is a draft; after Create the stored record carries both.
    uploaded_at: doc.attachedAt ?? null,
    uploaded_by_name: doc.attachedBy ?? null,
    required: doc.required,
    size_bytes: doc.file.size,
    original_size_bytes: null,
    file_present: true,
    // Nobody has decided on it yet — `BR-CUS-036`'s own posture. The shared
    // STATE cell prints NOTHING for this value (`DEF-SHL-6347`).
    verification_state: "not_checked",
    reject_reason: null,
  }));
}
