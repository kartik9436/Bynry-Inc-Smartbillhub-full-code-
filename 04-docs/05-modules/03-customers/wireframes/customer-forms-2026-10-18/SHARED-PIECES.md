# Shared customer-form pieces — paths and props (lane CF-1, 2026-10-18)

Built from the images in this folder (B14 rule 42). Every create screen mounts these; none keeps its own copy (B14 rule 43). **The props below are stable from the commit that adds this file; later changes are additive and in their own commits.** All paths are under `07-frontend/src/features/customers/`.

| Piece | Path | Props |
|---|---|---|
| **Who** panel | `customerForm/CustomerWhoPanel.tsx` → `CustomerWhoPanel` | `title` (host's words: *Who is moving in* / *Who is applying* / *Who will own the account* / *Who is buying*) · `customer: CustomerForm` + `onCustomer` · `extras: CustomerWhoExtras` (`contact_by`, `trading_as`, `business_type`, `registered_in`) + `onExtras(patch)` · `showCategory?` (default true; portal passes false) · `showCompanyFacts?` (default true) · `showCompanyContact?` (default false — email/phone in Who for a company) · `companyTrailing?` (a company's search button + answer) · `note?` · `footer?` · `showErrors?` (format/required refusals after Continue) · `t`, `dateFormat`, `timeZone` |
| **Identity** panel (a person's) | same file → `CustomerIdentityPanel` | `customer` + `onCustomer` · `trailing?` (*Search customer ID* button; omit = no search, as the service request) · `children?` (the search answer, a fact from the request) · `ssnPlaceholder?`, `licencePlaceholder?` (masks of a number on file) · `t`. SSN has *Staff see the last four only.*; the at-least-one-ID line sits under the row. |
| Format checks | same file → `phoneFormatProblem(v)`, `emailFormatProblem(v)`, `customerFormatProblem(customer)`, `emptyCustomerWhoExtras()`, `BUSINESS_TYPES` | catalogue keys `customers.form.phoneInvalid` / `customers.form.emailInvalid`; blank is no error |
| **Search results table** | `customerMatch/CustomerMatchPanel.tsx` → `CustomerMatchPanel` (same name and props as before) | `result`, `pending`, `failed`, `linkedId`, `linkedRow`, `dismissed`, `onLink(row)`, `onUnlink()`, `onNotThem(row)`, `timeZone`, `dateFormat`. Server rows now carry `date_of_birth`, `phone_last4`, `accounts.open_count`. Row controls are named *name · customer no.* |
| **More about the customer** (custom fields) | `customerForm/CustomerCustomFieldsPanel.tsx` → `CustomerCustomFieldsPanel` | `screen: "S18" \| "REQUEST_NEW" \| "NEW_CONNECTION_OWNER"` · `values` + `onChange` · `t` · `client?`. Draws nothing when the slot has no fields. `customerCustomPayload(values)` → answered keys or `undefined`. A new slot = a new literal branch (the W1 pairing test reads literals). |
| **Co-owner** cards | `CoOwnerCards.tsx` → `CoOwnerCards` | existing props + `label?: "co_owner" \| "co_applicant" \| "co_buyer"` (heading, tick, add-button words) + `showPhotoId?` (default true). `coOwnerFormatProblem(rows)` added. Payload unchanged: `coOwnersPayload(kind, rows)`. |
| **Documents** table | `MoveInDocumentsTable.tsx` → `MoveInDocumentsTable` | existing props + `stage?(args: {file, docType}) → Promise<{card_id, name}>` (where an upload goes; default = staged for the move-in). Offers the nine types (`DESIGNED_DOC_TYPES` + `other`). |
| **Mailing address** block | `customerForm/MailingAddressBlock.tsx` → `MailingAddressBlock` | `value: MailingAddressValue` (`mailing_same`, `mailing_line1`, `mailing_line2`, `mailing_city`, `mailing_state`, `mailing_postal_code` — `CustomerForm`'s six) · `onChange(patch)` · `serviceAddress` (walked, hard rule 8) · `t` |
| **Preferences** panel | `customerForm/PreferencesPanel.tsx` → `PreferencesPanel` | `on` + `onTick(on)` · `value: PreferencesValue` (`paperless`, `sms_reminders`, `autopay`, `preferred_language`) + `onChange(patch)` · `showAutopay` (only where a payment method can be saved — never on a request) · `autopayFrom?` · `tickId?` · `t`, `client?`. Also `OnOffField`. |
| Icons | `components/icons.tsx` | `ChevronRightIcon`, `LinkIcon`, `UnlinkIcon`, `HomeIcon` |

New catalogue keys (all eleven locales): `customers.form.*` (emailInvalid, phoneInvalid, oneIdRule, moreAbout, utilityFields, coApplicants.*, coBuyers.*, yes, no) and `customers.moveIn.customer.match.*` (count, strongestFirst, col.open/match/customer/dob/phone/accounts/owed/actions, countOpen, showAccounts, hideAccounts, noAccountsRead, linkName, view, notThemName, noneOfThese).

Move-in (`moveInWizard/StepCustomer.tsx`) is the first host and the worked example of every prop above.

## Additive props (second commit, 2026-10-18) — nothing above changed

| Piece | Added |
|---|---|
| `CustomerWhoPanel` | `categoryPlaceholder?` (the category select's empty option, e.g. *Pick a category*) · `client?` (passed to the category lists — a host with its own client passes it) |
| `CustomerFields.tsx` → `CustomerTypeFields` | `typePlaceholder?` · `client?` |
| `MoveInDocumentsTable` | `requiredTypes?` (the host's required document types; when given, the move-in's own requirement read is not made) · `fileHref?(cardId)` (where a row's file opens; default = the move-in's) |
| `customerForm/requestCarry.ts` (new) | `coApplicantDrafts(applicant)` → `CoOwnerDraft[]` · `requestCustomerCustom(detail)` → `CustomFieldValues` · `requestMailing(detail)` → five parts or `null` — an approved request's answers as the shared form's values, for any host opening from a request |
| `CaptureCustomerForm.tsx` (new, the service request's host) | the worked example of the form with NO *Search customer ID*, `label="co_applicant"`, `showPhotoId={false}`, `showAutopay={false}` |

## Additive props (third commit, 2026-10-18, New connect) — nothing above changed

| Piece | Added |
|---|---|
| `CustomerWhoPanel` | `dobError?` (a host's own date-of-birth refusal on the field — New connect's under-18 / future rule) |
| `CustomerIdentityPanel` | `licenceMasked?` (licence masked with Show/Hide, as New connect has had it since DEF-CUS-9194) |
| `CoOwnerCards` | `licenceMasked?` (the same, on each card) |
| `MoveInDocumentsTable` | `openFile?(cardId)` (a host whose files are not on a server yet opens them itself; wins over `fileHref`) |
| `NewConnectCustomerForm.tsx` (new, New connect's host) | the worked example with *Search customer ID*, co-owner cards, files held until Create, and `ownerToCustomer` / `customerToOwnerPatch` mapping the draft's `OwnerForm` |
| `newConnectOwnerRules.ts` (moved, unchanged) | `ownerBirthDateProblem`, `ownerBirthDateSentence`, `ownerHasABirthDate`, `todayIn` — still re-exported from `NewConnectOwnerStep.tsx` |

## Additive (fourth commit, 2026-10-18) — nothing above changed

| Piece | Added |
|---|---|
| `CoOwnerCards.tsx` → `CoOwnerDraft` | `id_on_file?` — the mask of an identifier the server holds (`•••-••-2208`); shown in the card's summary, never sent. `idOnFileMask(ssnLast4, licenceLast4)` builds it; `idSummary(row)` is what the summary shows (`DEF-CUS-10232`). |
| `moveInWizard/BillingExtras.tsx` → `TaxSection`, `DiscountsSection` | now also mounted by New connect's charges step, unchanged; the Tax panel's *Issued* and *Expires* are the utility's date picker (`regional`) on both screens. |
