// ── Trace ──────────────────────────────────────────────
// Change:  `BR-CUS-1081` — PO ruling 2026-09-20, walking the transfer wizard in
//          the live product: *"step 2 dont allow to take kYC documents - DOB,
//          all detaisl we need to create account - Similar to Move in request
//          we will need all details for account"*, and, when told a backend
//          lane would be needed: *"we have it - we have created it for service
//          request move in - use it"*.
// Rules:   `BR-CUS-1022` (a company is never asked for a licence or a date of
//          birth; a person is never asked for a Tax ID) · `BR-CUS-092`(a)/(d)
//          (both identifiers are captured, and the encryption promise is only
//          printed where a test reads the column back raw) · B14 rule 32 (one
//          sentence per section) · rule 33 (LABEL ≤ 3 words · FACT ≤ 6 ·
//          RATIONALE zero words on screen) · rule 21 (Tailwind only; this file
//          is on `src/styles/route-b-migrated.txt`) · rule 38 (where a drawing
//          and our UI rules disagree about how a FORM is BUILT, the rules win)
// Screens: S19/REQ-03.1 move-in capture, step 1 · `TRF-02.2` transfer, step 2
//          ("Who is buying it", Accounts blueprint p126–p127)
// Tests:   applicantCapture.dom.test.tsx (rendered output, not props)
// ───────────────────────────────────────────────────────
//
// ══════════════════════════════════════════════════════════════════════════
// WHY THIS FILE EXISTS — IT IS A MOVE, NOT A SECOND IMPLEMENTATION
// ══════════════════════════════════════════════════════════════════════════
// The PO did not ask for a buyer form. They asked for THE ONE THEY ALREADY
// HAVE: *"we have it - we have created it for service request move in - use
// it"*. That form was 120 lines inline inside `ServiceRequestCapturePage.tsx`,
// which is 4,186 lines long and is not importable by anything — so "use it"
// was not a thing a lane could do without first making it a component.
//
// ⚠ **THE FIELDS BELOW ARE THAT BLOCK, MOVED, NOT RE-TYPED.** Same order, same
// catalogue keys, same `max={today}` bound, same per-kind branch, same
// `FieldGrid` construction. A second spelling of a government-identifier form
// is precisely what `BR-CUS-1020` exists to refuse, and the PO's standing
// instruction of 2026-09-12 refuses it generally: *build from the actual code,
// and do not create duplicate code*.
//
// ⚠ **THE KIND PICKER IS DELIBERATELY NOT IN HERE.** Both hosts already draw
// it, and they draw it DIFFERENTLY — the capture page as a `SelectField`, the
// transfer as a `SegmentedField` — because each matches its own drawing. B14
// rule 38 hands a form's CONSTRUCTION to the UI rules and its CONTENT to the
// drawing, and a shared component that forced one idiom onto both screens
// would be deciding construction for a screen it cannot see. What IS shared is
// everything the kind DECIDES, which is the part `BR-CUS-1022` is about.
//
// ⚠ **`preferred_language` IS IN `CAPTURE_FIELDS` AND IS NOT DRAWN HERE.**
// Stated rather than forgotten. The benchmark the PO named — the move-in
// capture — does not ask for it either, the Accounts blueprint does not draw
// it on p126/p127, and an account's language column is nullable, so it is not
// one of the *"details we need to create account"*. Adding a field neither the
// benchmark nor the drawing has would be this lane deciding a screen's content
// on its own, against rule 32's description budget on a screen the PO has just
// told us has *"too much text"*. Recorded in the decision log of 2026-09-20.

/**
 * **The capture vocabulary, spelt the way the SERVER spells it.**
 *
 * Every name here is one of `service_request_service.CAPTURE_FIELDS`, which is
 * what `transfers.BUYER_CAPTURE_FIELDS` is derived from — and
 * `transfers._capture_vocabulary()` RAISES if the two ever drift. Keeping the
 * client on the same words is what makes that guarantee reach the screen: a
 * field renamed on one side goes red on the other instead of quietly sending a
 * key nothing reads.
 */
export interface ApplicantCaptureValue {
  /** `person` | `company`. Drawn by each HOST (see the header), read here. */
  applicant_kind: string;
  applicant_email: string;
  applicant_phone: string;
  /** A person's, and only a person's — `BR-CUS-1022`. */
  ssn: string;
  date_of_birth: string;
  drivers_licence: string;
  /** A company's, and only a company's. */
  tax_id: string;
  add_co_applicant: boolean;
  co_applicant_name: string;
  co_applicant_email: string;
  co_applicant_phone: string;
}

/** Every capture field blank, and `add_co_applicant` closed. */
export function emptyApplicantCapture(): ApplicantCaptureValue {
  return {
    // ⚠ **EMPTY, NOT `person`** (`BR-CUS-1022`). A pre-selected kind would
    // judge a business by a date of birth it has not got and file its Tax ID
    // nowhere. `emptyCustomerForm` and `emptyCaptureForm` both already get
    // this right; this restates neither, it matches them.
    applicant_kind: "",
    applicant_email: "",
    applicant_phone: "",
    ssn: "",
    date_of_birth: "",
    drivers_licence: "",
    tax_id: "",
    add_co_applicant: false,
    co_applicant_name: "",
    co_applicant_email: "",
    co_applicant_phone: "",
  };
}

/** `2026-09-20` — nobody was born tomorrow, so the input says so rather than a
 *  help sentence claiming a bound over an unbounded box (`DEF-MET-4974`). */
export function todayIsoDate(): string {
  return new Date().toISOString().slice(0, 10);
}

export const CAPTURE_KIND_PERSON = "person";
export const CAPTURE_KIND_COMPANY = "company";

/**
 * **`BR-CUS-1022` — which identifiers this kind is asked for, and only those.**
 *
 * ⚠ **THE OTHER KIND'S FIELDS ARE NOT MERELY HIDDEN.** The rule's own words:
 * *"asking for both and leaving one blank turns a rule into a habit and the
 * blank field eventually gets filled with something."* A host that switches
 * kind must BLANK what this function stops naming — `clearedForKind` below is
 * that act, so neither host has to remember it.
 */
export function captureIdentityFieldsFor(
  kind: string,
): readonly ("date_of_birth" | "ssn" | "drivers_licence" | "tax_id")[] {
  if (kind === CAPTURE_KIND_COMPANY) return ["tax_id"];
  if (kind === CAPTURE_KIND_PERSON) return ["date_of_birth", "ssn", "drivers_licence"];
  // An UNSTATED kind is a real answer (`BR-CUS-1023`): it mints no customer
  // number and it is asked for no identifier at all.
  return [];
}

/** The patch that empties whatever the NEW kind is not asked for. */
export function clearedForKind(kind: string): Partial<ApplicantCaptureValue> {
  const asked = new Set<string>(captureIdentityFieldsFor(kind));
  const patch: Partial<ApplicantCaptureValue> = {};
  if (!asked.has("tax_id")) patch.tax_id = "";
  if (!asked.has("ssn")) patch.ssn = "";
  if (!asked.has("date_of_birth")) patch.date_of_birth = "";
  if (!asked.has("drivers_licence")) patch.drivers_licence = "";
  return patch;
}

// ⛔ **`ApplicantCaptureFields` IS DELETED (G40, lane CF-2, 2026-10-18).** Its
// last host — the transfer buyer step — now draws the shared customer form
// (`CustomerWhoPanel` / `CustomerIdentityPanel`, image `07-transfer.png`), and
// the service request's `CaptureApplicantPanel` went the same way (lane CF-1).
// A component nothing renders is dead UI (hard-won law 2). The value type and
// the payload/kind helpers above and below stay: the transfer still sends them.

/**
 * **What the capture block sends, in `CAPTURE_FIELDS`' own spelling.**
 *
 * ⊕ **A CO-APPLICANT IS STORED SINCE 2026-09-23 — `OQ-CUS-12514` CLOSED, T4
 * (`DEF-CUS-6391`).** On a transfer the commit writes it as the account's
 * second contact; the three keys are SENT whatever the host, because the
 * server is what decides where a captured fact goes. When the box is unticked the three are sent EMPTY, which is the
 * same act `ssn` already spells this way — an empty string CLEARS, it does not
 * mean *leave what is there*.
 */
export function applicantCapturePayload(
  value: ApplicantCaptureValue,
): Record<string, string> {
  const asked = new Set<string>(captureIdentityFieldsFor(value.applicant_kind));
  const out: Record<string, string> = {
    applicant_email: value.applicant_email.trim(),
    applicant_phone: value.applicant_phone.trim(),
    co_applicant_name: value.add_co_applicant ? value.co_applicant_name.trim() : "",
    co_applicant_email: value.add_co_applicant ? value.co_applicant_email.trim() : "",
    co_applicant_phone: value.add_co_applicant ? value.co_applicant_phone.trim() : "",
  };
  // ⛔ ONLY THE IDENTIFIERS THAT BELONG TO THE STATED KIND (`BR-CUS-1022`). The
  // server strips the others anyway — but putting a person's government
  // identifier on a wire for no purpose is the wrong side of `BR-CUS-1020`
  // even when it is harmless.
  if (asked.has("date_of_birth")) out.date_of_birth = value.date_of_birth.trim();
  if (asked.has("ssn")) out.ssn = value.ssn.trim();
  if (asked.has("drivers_licence")) out.drivers_licence = value.drivers_licence.trim();
  if (asked.has("tax_id")) out.tax_id = value.tax_id.trim();
  return out;
}
