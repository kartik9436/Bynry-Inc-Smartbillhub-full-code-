// ── Trace ──────────────────────────────────────────────
// Story:    US-CWP-013 (EP-CWP-04) — About you, saved from the first keystroke
//           · US-CWP-014 — Check and send, where paperless consent is taken.
//           Screens: CWP-047 · CWP-009 · wireframes/CWP-047.png · CWP-009.png
// Rules:    08-screen-layouts.md CWP-047 (T2 under GuestFrame, URL strip *not
//           signed in · step 2 of 4*: Stepper 4 · kicker ABOUT YOU · TwoUp
//           names · person-or-business · TwoUp email/mobile · date of birth
//           with helper · start date with helper · Continue → · Save and
//           finish later; rail Panel THE ADDRESS · Panel.Info nothing is
//           promised yet) · CWP-009 (KVList · WE WILL NEED THESE FROM YOU ·
//           two AFTER YOU APPLY rows · boxed consent + helper · ConsequenceBox
//           ×4 · Send my application ✓ · Back; rail SAVED AS YOU GO ·
//           Panel.Info documents come after) · BR-CWP-087 (the consent) ·
//           CR-068 R4 (print stays the floor — *we print them as well*) ·
//           B14 rules 2 (one page header, every screen), 21, 31, 32, 33 ·
//           R-10 (PO 2026-09-11 — *"when a screen tells a customer something
//           bad, the thing they can do about it must be on that same screen,
//           next to the message"*)
// Defects:  DEF-CWP-4877 — six fields marked required gated NOTHING, so the
//           applicant reached the commit with an empty form and was answered
//           *"Finish an earlier step first."*, five words naming no step, over
//           a read-back visibly showing `Applicant —`. The server sends the
//           step in `params` and the catalogue sentence had nowhere to put it,
//           so it was thrown away. Both halves are fixed here: `unfinished()`
//           below is ONE arithmetic and `sendRefusal()` names the step.
//           · DEF-CWP-4876 — steps 2, 3 and 4 drew no heading of any kind
//           (`h1` count 0, measured at 1280 and 390), so after step 1 nothing
//           on screen said which address was being applied for.
//           · DEF-CWP-4875 — `— deposit on your first bill.` See
//           `ifYouApplyBullets` in `StartService.tsx`.
//           · 2026-10-02, PO with screenshots (decision log *"PORTAL
//           START-SERVICE FORM — FIVE DEFECTS"*): DEF-CWP-9166 (View beside
//           Remove) · DEF-CWP-9167 (one attach row per document; Check and
//           send says *Attached ✓* or *Bring later*) · DEF-CWP-9163 (mailing
//           address, if different) · DEF-CWP-9164 (Back LEFT, Continue / Send
//           RIGHT — `WizardFooter`) · DEF-CWP-9165 (*What you will pay* says
//           what its blank means)
// Tests:    src/portal/guest/StartService.test.tsx ·
//           src/portal/guest/CheckAndSend.dom.test.tsx ·
//           10-scripts/render-checks/cr068-c-start-service.mjs
// ───────────────────────────────────────────────────────
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { FocusEvent, ReactNode } from "react";
import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useParams, useSearchParams } from "react-router-dom";

import { api, isApiError } from "@/api/client";
import type { ApiClient, ApiError } from "@/api/client";
import { refusalText } from "@/api/refusalText";
import type { Translator } from "@/api/refusalText";
import { PageHeader } from "@/components/PageHeader";
import { Panel } from "@/components/Panel";
import { Button } from "@/components/Button";
import { LoadingSkeleton } from "@/components/StateFrame";

import {
  getAvailability,
  getDraft,
  saveDraft,
  submitApplication,
  tokeniseCard,
} from "../api/guestClient";
import type {
  ApplicationDraft,
  ApplicationFeePayment,
  Availability,
  MoneyCell,
  PortalCustomData,
  PortalCustomEntity,
  PortalCustomField,
} from "../api/guestClient";
import { ApplicationDocuments, DocumentChecklist } from "./ApplicationDocuments";
import { ApplicationCustomFields, answerText, hasUnanswered } from "./ApplicationCustomFields";
import {
  MailingAddressFields,
  mailingFromDraft,
  mailingIsComplete,
  mailingLine,
  mailingPayload,
} from "../components/MailingAddress";
import type { MailingValue } from "../components/MailingAddress";
import { SegmentedControl } from "@/components/SegmentedControl";
import { emailFormatProblem, phoneFormatProblem } from "@/features/customers/customerForm/CustomerWhoPanel";
import { FormSection } from "../components/FormSection";
import { Announced } from "../components/a11y";
import { PortalDateBox, PortalDateField } from "../components/PortalDateField";
import {
  CoApplicantCard,
  coApplicantFromDraft,
  coApplicantIsComplete,
  coApplicantPayload,
} from "./CoApplicantCard";
import type { CoApplicantValue } from "./CoApplicantCard";
import {
  ApplicationPreferences,
  preferencesFromDraft,
  preferencesPayload,
} from "./ApplicationPreferences";
import type { PreferencesValue } from "./ApplicationPreferences";
import {
  Card,
  ConsequenceBox,
  FormField,
  HeldButton,
  fieldErrorId,
  KVList,
  SectionTitle,
  SelectInput,
  Stepper,
  TextInput,
  TwoCol,
  TwoUp,
  WizardFooter,
} from "../components/primitives";
import { usePortalDate } from "../components/regional";

import { languageName } from "../components/languageName";

import { GuestPage } from "./GuestPage";
import { newDraftToken } from "../draftToken";
import {
  ApplicationFeeCard,
  EMPTY_FEE_CARD,
  feeCardIsComplete,
  feeToPay,
} from "./ApplicationFeeCard";
import type { FeeCardValue } from "./ApplicationFeeCard";
// ⚠ **ONE COPY OF THE *IF YOU APPLY* RULE, IMPORTED RATHER THAN REWRITTEN.**
// s15 and s16 draw the same three sentences off the same `if_you_apply` read,
// and `DEF-CWP-4875` was filed against BOTH screens — a second copy here is a
// second place the em dash comes back.
import { ifYouApplyBullets } from "./StartService";

/**
 * The three steps that live on `/start-service/:draft`.
 *
 * ⚠ **STEP 1 IS `CWP-008` AND IS ON ANOTHER ROUTE**, which is why there are
 * three names here and four on the step bar. The address is answered before a
 * draft exists at all — that is the whole point of asking it first — so it has
 * no place in a form whose state is a draft token.
 */
export type ApplyStep = "when" | "about" | "review";

/* ⚠ **THE TWO DOCUMENTS ARE THE SERVER'S LIST NOW** (`DEF-CWP-9167`). A
   `CHECKLIST` constant stood here — `["photo_id", "proof_of_address"]` — and
   the upload knew nothing about it, so two attached files sat under two rows
   reading *NOW OR LATER*. Both halves read `draft.document_requirements`. */

type Patch = Record<string, unknown>;

/* ═══════════════════════════════════════════════════════════════════════════
 * WHAT IS NOT FINISHED — ONE ARITHMETIC, FOUR PLACES THAT ASK IT
 * ═══════════════════════════════════════════════════════════════════════════
 *
 * ⚠ **`DEF-CWP-4877`, AND THE DAMAGE WAS THE SHAPE OF THE ANSWER RATHER THAN
 * THE ANSWER ITSELF.** Six fields carried the brand asterisk and gated
 * nothing: `Continue →` was live on step 2 with no date and on step 3 with all
 * five boxes empty, so an applicant could walk to the commit, read back
 * `Applicant —`, `Email —`, `Mobile —`, press **Send my application ✓** — and
 * be told *"Finish an earlier step first."* Five words naming no step, no
 * field and no way forward, at the one moment somebody has decided to act.
 *
 * ⚠ **AND THE SERVER WAS ALREADY SENDING THE STEP.** `services.submit` raises
 * `portal.application.stepIncomplete` with `params={"step": missing[0]}` under
 * a comment that reads *"The refusal names the step."* — which was true of the
 * wire and false of the screen, because the catalogue sentence has no
 * `{{…}}` in it and i18next drops a parameter nothing interpolates. Hard-won
 * law 1 exactly: a comment claiming a guarantee is not the guarantee.
 *
 * **So there is ONE list here and four callers read it**: step 2's gate, step
 * 3's gate, the commit's gate, and `firstUnfinishedStep` — which used to hold
 * a second, hand-written copy of the same conditions. `firstUnfinishedStep`'s
 * own docstring already warned what a second copy costs: *"Two rules
 * disagreeing about may this be sent would be a second arithmetic over the
 * same question."* It was right, and there were two.
 */

/**
 * The step keys `applications.missing_before_submit` returns, **in its order**.
 *
 * ⚠ **THE ORDER IS PART OF THE CONTRACT.** The server refuses on `missing[0]`,
 * so a screen that held on a different first item would name one step while
 * the server named another — two answers to *what is missing*, which is the
 * failure this whole block exists to end.
 */
type MissingKey =
  | "address"
  | "services"
  | "name"
  | "company_name"
  | "tax_id"
  | "contact"
  // ⊕ `DEF-CUS-10250` — a ticked *Add a co-applicant* with no name. The
  // category that stood here (`DEF-CWP-9818`) is NOT asked any more — PO
  // 2026-10-18, *"this is correct"*: staff set it before approving.
  | "co_applicant"
  | "mailing"
  | "start_date"
  // `CR-161-BRC10` W7 — a REQUIRED question the utility asks on the portal,
  // still blank: the applicant's own (customer / account) on step 3, the
  // property's on step 2. Last, in this order — the server's.
  | "your_questions"
  | "property_questions";

/**
 * Which of the four steps owns each.
 *
 * ⚠ **1 IS `CWP-008`, WHICH IS A DIFFERENT ROUTE.** The address and the
 * services are settled before a draft token exists at all, so nothing on
 * `/start-service/:draft` can gate on them or send anybody back to fix them —
 * re-entering step 1 mints a new token and loses everything typed. They are
 * here because the SERVER can still refuse on them and the refusal has to be
 * able to name the step; they are deliberately absent from `HELD_KEY` below.
 */
const STEP_OF: Record<MissingKey, 1 | 2 | 3> = {
  address: 1,
  services: 1,
  start_date: 2,
  name: 3,
  company_name: 3,
  tax_id: 3,
  contact: 3,
  co_applicant: 3,
  // DEF-CWP-9163 — an unticked *Same as the service address* with no address.
  mailing: 3,
  your_questions: 3,
  property_questions: 2,
};

/**
 * What a held control SAYS it is waiting for — B14 rule 33, six words or fewer,
 * and the instruction rather than the rationale.
 *
 * ⚠ **ONLY THE FOUR THINGS AN APPLICANT CAN DO SOMETHING ABOUT FROM THESE
 * SCREENS.** `address` and `services` have no entry on purpose (see `STEP_OF`):
 * a control held over *"we are still checking services"* would be a dead end
 * wearing a reason, and R-10 asks for the way out, not for a better-worded
 * wall.
 */
const HELD_KEY: Partial<Record<MissingKey, string>> = {
  // ⊕ **`services` HAS AN ENTRY NOW, AND ONLY ONE SCREEN CAN HOLD ON IT —
  // `DEF-CWP-4930`.** The note above was right for a HELD address, where the
  // address decides and step 2 has nothing to tick. For an address we do NOT
  // hold, step 2 now offers the utility's services as ticks (`offerToTick`),
  // so there the applicant can act on it, on the same screen, next to the
  // reason (R-10). `heldOnWhen` is the one caller that reaches this key.
  services: "portal.apply.held.services",
  start_date: "portal.apply.held.startDate",
  name: "portal.apply.held.name",
  company_name: "portal.apply.held.companyName",
  tax_id: "portal.apply.held.taxId",
  contact: "portal.apply.held.contact",
  co_applicant: "portal.apply.held.coApplicant",
  mailing: "portal.apply.held.mailing",
  your_questions: "portal.apply.held.questions",
  property_questions: "portal.apply.held.questions",
};

/** `DEF-CUS-10250` — *How should we contact you?*, the one `CONTACT_BY` list
 *  (`customers.models.CONTACT_BY`), in its order. */
const CONTACT_BY_OPTIONS = ["email", "text", "phone", "letter"] as const;

/** The last four of an SSN: four digits, or blank. */
function ssnLast4Problem(value: string): string | null {
  const typed = value.trim();
  return typed === "" || /^\d{4}$/u.test(typed) ? null : "portal.apply.ssnLast4Format";
}

/** Today in the browser, `YYYY-MM-DD` — the latest date of birth a box takes. */
function todayIso(): string {
  const now = new Date();
  const month = String(now.getMonth() + 1).padStart(2, "0");
  const day = String(now.getDate()).padStart(2, "0");
  return `${now.getFullYear()}-${month}-${day}`;
}

/**
 * A field whose value is MALFORMED is left out of the save rather than sent,
 * so one half-typed email cannot get the whole form refused by the server
 * (which checks the same shapes) and lose every other box with it — the box
 * says what is wrong, and the stored value stays until a good one replaces it.
 */
function withoutMalformed(patch: Patch): Patch {
  const out: Patch = { ...patch };
  const bad = (key: string, problem: (value: string) => string | null) => {
    const value = out[key];
    if (typeof value === "string" && problem(value) !== null) delete out[key];
  };
  bad("phone", phoneFormatProblem);
  bad("email", emailFormatProblem);
  bad("co_applicant_phone", phoneFormatProblem);
  bad("co_applicant_email", emailFormatProblem);
  bad("ssn_last4", ssnLast4Problem);
  return out;
}

/** Everything the form holds, seeded from a draft. One shape, two readers. */
function valuesOf(draft: ApplicationDraft | null) {
  return {
    first_name: draft?.first_name ?? "",
    last_name: draft?.last_name ?? "",
    company_name: draft?.company_name ?? "",
    email: draft?.email ?? "",
    phone: draft?.phone ?? "",
    date_of_birth: draft?.date_of_birth ?? "",
    tax_id: draft?.tax_id ?? "",
    requested_start: draft?.requested_start ?? "",
    // ⊕ `DEF-CUS-10250` — Move-in's two remaining boxes on this card.
    contact_by: draft?.contact_by ?? "",
    ssn_last4: draft?.ssn_last4 ?? "",
  };
}

type FormValues = ReturnType<typeof valuesOf>;

/**
 * What is still missing — **the browser's copy of
 * `applications.missing_before_submit`, field for field and in its order**.
 *
 * ⚠ **THE DATE OF BIRTH IS NOT ON THIS LIST AND THE ASTERISK CAME OFF IT.**
 * The server accepts an application without one; wireframe s17 draws the field
 * with no required mark at all, and its own *WHY WE ASK* panel calls it the
 * credit check rather than a condition of applying. A screen that demanded it
 * would refuse applications the product accepts, on a journey whose epic says
 * in as many words that *"they may never become a customer if we refuse
 * them"*. The asterisk now tells the truth instead of the server being asked
 * to agree with it.
 *
 * ⚠ **IT READS THE LIVE FORM, NOT THE SAVED DRAFT, FOR EVERYTHING BUT THE
 * ADDRESS.** The draft is written when a field is LEFT and a save can be in
 * flight or turned away (`DEF-CWP-3710`), so a gate reading the draft would
 * hold the commit over a field the applicant had just filled in — a control
 * refusing with a reason that is visibly false on the same screen, which is
 * worse than no gate. The address and the services are the draft's because
 * step 1 put them there and no box on these screens can change them.
 */
function unfinished(
  draft: ApplicationDraft | null,
  values: FormValues,
  kind: string,
  mailing: MailingValue = mailingFromDraft(draft),
  custom: PortalCustomData = draft?.custom_data ?? {},
  coApplicant: CoApplicantValue = coApplicantFromDraft(draft),
): MissingKey[] {
  const missing: MissingKey[] = [];
  if (!(draft?.address_as_given ?? "").trim()) missing.push("address");
  if ((draft?.service_codes ?? []).length === 0) missing.push("services");
  if (kind === "business") {
    // TC-4 — a business is identified by company name and tax ID.
    if (!values.company_name.trim()) missing.push("company_name");
    if (!values.tax_id.trim()) missing.push("tax_id");
  } else if (!values.first_name.trim() || !values.last_name.trim()) {
    missing.push("name");
  }
  // ⊕ `DEF-CUS-10250` — EMAIL IS OPTIONAL (Move-in's rule everywhere, PO
  // 2026-10-18); the mobile number is what is required.
  if (
    !values.phone.trim() ||
    phoneFormatProblem(values.phone) !== null ||
    emailFormatProblem(values.email) !== null
  ) {
    missing.push("contact");
  }
  // The server's own order: after contact, before mailing.
  if (!coApplicantIsComplete(coApplicant)) missing.push("co_applicant");
  // DEF-CWP-9163 — the server's `MAILING_REQUIRED`, in the server's order.
  if (!mailingIsComplete(mailing)) missing.push("mailing");
  if (!values.requested_start.trim()) missing.push("start_date");
  // `CR-161-BRC10` W7 — the server's `application_unanswered`, step by step,
  // read off the LIVE answers for `DEF-CWP-3710`'s reason (see above).
  const asked = draft?.custom_fields ?? {};
  if (
    hasUnanswered(asked.customers, custom.customers) ||
    hasUnanswered(asked.accounts, custom.accounts)
  ) {
    missing.push("your_questions");
  }
  if (hasUnanswered(asked.premises, custom.premises)) missing.push("property_questions");
  return missing;
}

/** The first thing THIS step is waiting for, or null when it is finished. */
function heldOnStep(missing: MissingKey[], step: 1 | 2 | 3): MissingKey | null {
  return missing.find((key) => STEP_OF[key] === step) ?? null;
}

/**
 * The services an applicant at an address we do NOT hold may tick — the
 * utility's own list, or empty where the address decides (`DEF-CWP-4930`).
 */
function offerToTick(availability: Availability | null): { service_code: string; service_name: string }[] {
  if (availability === null || availability.matched) return [];
  return availability.offered ?? [];
}

/**
 * Step 2's gate. On an address we do NOT hold the services are TICKED on this
 * step, so a missing tick holds it here — before the start date, in the
 * server's own order — rather than being refused at the last button for a step
 * the applicant was never shown (`DEF-CWP-4930`).
 */
function heldOnWhen(missing: MissingKey[], availability: Availability | null): MissingKey | null {
  if (offerToTick(availability).length > 0 && missing.includes("services")) return "services";
  return heldOnStep(missing, 2);
}

/**
 * The services this application asks for, BY NAME — what the rail and the
 * check screen restate. A held address names its carried rows; an address we
 * do not hold names what was ticked (`DEF-CWP-4930`).
 */
function askedForNames(draft: ApplicationDraft | null, availability: Availability | null): string {
  const offered = offerToTick(availability);
  if (offered.length > 0) {
    const ticked = new Set(draft?.service_codes ?? []);
    return offered
      .filter((one) => ticked.has(one.service_code))
      .map((one) => one.service_name)
      .join(", ") || "—";
  }
  return (
    (availability?.rows ?? [])
      .filter((row) => row.available)
      .map((row) => row.service_name)
      .join(", ") || "—"
  );
}

/**
 * The first thing the COMMIT is waiting for that the applicant can act on.
 *
 * ⚠ **STEP 1'S TWO KEYS ARE EXCLUDED, AND THAT IS A DELIBERATE LIMIT ON THIS
 * GATE (hard-won law 1 — say what a thing does not guarantee).** An
 * application for an address we do not hold carries no services, and the
 * server refuses it on `services` — a step the applicant was never shown and
 * cannot finish, on the one journey `EP-CWP-04` §1 says must stay open to
 * them. Holding *Send* over it would turn a bad refusal into a dead button.
 * That is `DEF-CWP-4930`, filed with its reproduction; the fix is the server's
 * rule and not this screen's. Until it lands the refusal at least NAMES the
 * step it is refusing on, which it did not before.
 */
function heldOnCommit(missing: MissingKey[]): MissingKey | null {
  return missing.find((key) => STEP_OF[key] >= 2) ?? null;
}

/**
 * A refusal from `POST …/submit`, **with the step it names**.
 *
 * Returns the sentence to print and, where the step is one of the two that
 * live on this route, the way back to it — R-10, verbatim: *"the thing they
 * can do about it must be on that same screen, next to the message. Not a page
 * away. Not in a menu. Right there."*
 *
 * ⚠ **THE STEP KEY NEVER REACHES THE GLASS.** `params.step` is `start_date`,
 * `contact`, `company_name` — internal names, and B14 rule 31 keeps those off
 * a customer's screen. What is rendered is the step NUMBER in the sentence and
 * the step's own drawn NAME on the control, both out of the eleven catalogues.
 *
 * ⚠ **AND ANY OTHER REFUSAL FALLS THROUGH TO `refusalText` UNCHANGED.** A
 * throttled save, a draft that has gone, a token that is not ours — those have
 * their own sentences and this function must not swallow them.
 */
function sendRefusal(
  t: Translator,
  error: unknown,
): { sentence: string; goTo: ApplyStep | null; label: string } {
  const step = stepFromRefusal(error);
  if (step === null) {
    return { sentence: refusalText(t, error), goTo: null, label: "" };
  }
  const number = STEP_OF[step];
  return {
    sentence: t("portal.application.stepIncompleteNamed", { number }),
    // Step 1 is on another route and re-entering it mints a new draft token,
    // so there is no way back to offer — see `STEP_OF`.
    goTo: number === 2 ? "when" : number === 3 ? "about" : null,
    label: t(`portal.apply.step${number}`),
  };
}

/** The step key the server refused on, when that is what this error is. */
function stepFromRefusal(error: unknown): MissingKey | null {
  if (!isApiError(error)) return null;
  const apiError = error as ApiError;
  if (apiError.messageKey !== "portal.application.stepIncomplete") return null;
  const step = apiError.params.step;
  return typeof step === "string" && step in STEP_OF ? (step as MissingKey) : null;
}

/**
 * The held control's row: the reason UNDER the button as well as on it.
 *
 * ⚠ **A `title` ALONE IS A TOOLTIP, AND THE PORTAL'S DESIGN TARGET IS A
 * 390px PHONE WHERE NOBODY CAN HOVER.** `BR-CWP-056` asks for *disabled WITH
 * the reason*; the kit's own `HeldButton` renders it as text for exactly this
 * reason and puts it on `title` as well. This is that shape with a live
 * control in it — `HeldButton` is the permanently-held one, and a `Continue →`
 * that becomes pressable is not that.
 *
 * ⚠ **AND IT IS NOT `CommitButton`, FOR THE REASON `StartService.tsx` ALREADY
 * RECORDS ABOUT ITS OWN `Check →`:** the kit's commit control forwards no
 * `data-*`, and `10-scripts/render-checks/cr068-c-start-service.mjs` drives
 * this journey with `page.click('[data-action="continue"]')`. Routing through
 * the kit would silently break the only check that opens these screens in a
 * real browser.
 */
function HeldReason(props: { held: MissingKey | null }) {
  const { t } = useTranslation();
  if (props.held === null) return null;
  const key = HELD_KEY[props.held];
  if (key === undefined) return null;
  return (
    // F-22 (`DEF-CWP-10551`): the held button points here (`HELD_REASON_ID`),
    // so the sentence is read WITH the button rather than only by a mouse.
    <p id={HELD_REASON_ID} className="text-base text-neutral-600" data-step-held={props.held}>
      {t(key)}
    </p>
  );
}

/** One step is on screen at a time, so one id serves all three steps. */
const HELD_REASON_ID = "apply-held-reason";

/** The same sentence, for the control's own `title`. */
function heldTitle(t: Translator, held: MissingKey | null): string | undefined {
  if (held === null) return undefined;
  const key = HELD_KEY[held];
  return key === undefined ? undefined : t(key);
}

/**
 * ⚠ **SAVED FROM THE FIRST KEYSTROKE, AND THAT IS A `PUT` PER FIELD, NOT PER
 * LETTER.** `US-CWP-013` TC-1 asks that closing the tab loses nothing; a save
 * on every keypress would be forty calls to type an email address, which the
 * response-time specification's *"no portal endpoint whose cost grows"*
 * forbids in spirit. So the draft is written when a field is LEFT — the moment
 * the value is finished — and once more before the step advances. A person who
 * closes the tab mid-word loses that word and nothing else.
 */
/** What the in-flight guard asks a refused caller to wait — `guards.py`
 *  `INFLIGHT_RETRY_AFTER_SECONDS`, plus a little, so the retry is late
 *  rather than early. */
const RETRY_AFTER_MS = 1200;

function useDraft(token: string, client: ApiClient) {
  const queryClient = useQueryClient();
  const key = ["portal", "draft", token];
  const query = useQuery({
    queryKey: key,
    queryFn: () => getDraft(token, client),
    // A draft that does not exist yet is not an error: nothing has been typed.
    retry: false,
  });
  const save = useMutation({
    mutationFn: (patch: Patch) => saveDraft(token, patch, client),
    // ⚠ **A SAVE NEVER CHANGES THE FILES, SO ITS ANSWER NEVER REPLACES THEM —
    // `DEF-CWP-9051`.** Found in a browser: tab out of a box (a save leaves),
    // choose a file at once (the upload leaves second and answers FIRST), and
    // the save's answer — the draft as it stood before the file — wiped the
    // file off the screen although the server held it. The files belong to the
    // upload and remove doors (`ApplicationDocuments` writes their answers
    // through `onDraft`); every other field is the save's.
    onSuccess: (row) =>
      queryClient.setQueryData<ApplicationDraft | null>(key, (cached) =>
        cached?.documents !== undefined ? { ...row, documents: cached.documents } : row,
      ),
  });

  /* ── ONE SAVE IN FLIGHT, AND THE LAST FIELD IS NEVER THE ONE THAT IS LOST ──
   *
   * ⚠ **DEF-CWP-3710 — FOUND IN THE BROWSER, AND IT WAS THE PRODUCT'S OWN
   * DOOR POLICY REFUSING THE PRODUCT'S OWN FORM.** The portal admits two
   * requests at a time (`PORTAL_INFLIGHT_MAX`, `guards.py`); a form that
   * fires a `PUT` per field can have six of them in the air in eighty
   * milliseconds. The third is answered `429` with `Retry-After: 1` — which
   * is correct, and is the guard saying *the door is full, come back* rather
   * than *no*. When the field it was carrying was the LAST one, nothing
   * followed it, the draft was missing `requested_start`, and *Send* was
   * refused with *"Finish an earlier step first."* — a sentence about a step
   * the applicant had in fact finished.
   *
   * **Nothing could have caught it but clicking**: `tsc`, the vitest cases and
   * all 87 backend cases were green, and the refusal came from the running
   * product agreeing with itself.
   *
   * So the form keeps ONE save in flight and coalesces the rest. A save asked
   * for while another is running is merged into `pending` and sent the moment
   * the first returns, so the newest value always wins and the last field is
   * always sent. A refused save is re-queued ONCE, after the second the guard
   * asked for; if that fails too the line under the form says so and the
   * applicant is told, rather than reassured.
   */
  const inFlight = useRef(false);
  const pending = useRef<Patch | null>(null);
  const retried = useRef(false);
  const flushRef = useRef<() => void>(() => {});
  const mutate = save.mutate;

  const flush = useCallback(() => {
    if (inFlight.current) return;
    const patch = pending.current;
    if (!patch) return;
    pending.current = null;
    inFlight.current = true;
    mutate(patch, {
      onSuccess: () => {
        retried.current = false;
      },
      onError: () => {
        if (retried.current) return;
        retried.current = true;
        // Put it back UNDER anything typed since, so newer values still win.
        pending.current = { ...patch, ...(pending.current ?? {}) };
        window.setTimeout(() => flushRef.current(), RETRY_AFTER_MS);
      },
      onSettled: () => {
        inFlight.current = false;
        if (pending.current) flushRef.current();
      },
    });
  }, [mutate]);
  flushRef.current = flush;

  const queueSave = useCallback((patch: Patch) => {
    pending.current = { ...(pending.current ?? {}), ...patch };
    flushRef.current();
  }, []);

  /** True while anything is still on its way to the server. */
  const settling = useCallback(() => inFlight.current || pending.current !== null, []);

  return { query, save, queueSave, settling };
}

/** Everything the form holds, as the draft's own field names. */
function payloadFrom(
  values: Record<string, string>,
  kind: string,
  mailing: MailingValue,
  custom: PortalCustomData | null = null,
  extra: { coApplicant: CoApplicantValue; preferences: PreferencesValue } | null = null,
): Patch {
  const out: Patch = { applicant_kind: kind };
  for (const [name, value] of Object.entries(values)) out[name] = value || null;
  // DEF-CWP-9163 — the mailing block rides with the whole form, for
  // `DEF-CWP-3706`'s reason: any dropped save is repaired by the next one.
  // `CR-161-BRC10` W7 — and so do the answers to the utility's own questions,
  // for the same reason; `null` (a utility that asks nothing) sends no key at
  // all, so the payload is exactly what it was before.
  // ⊕ `DEF-CUS-10250` — the co-applicant card and the Preferences panel ride
  // with the whole form too, for the same reason.
  return withoutMalformed({
    ...out,
    ...mailingPayload(mailing),
    ...(custom === null ? {} : { custom_data: custom }),
    ...(extra === null
      ? {}
      : { ...coApplicantPayload(extra.coApplicant), ...preferencesPayload(extra.preferences) }),
  });
}

/** Does this utility ask anything on the portal? */
function asksQuestions(draft: ApplicationDraft | null): boolean {
  const asked = draft?.custom_fields ?? {};
  return Object.values(asked).some((fields) => (fields ?? []).length > 0);
}

/** A refused answer's sentence per box, keyed `custom_data.<entity>.<key>` —
 *  the server's own field paths (`tenancy_seam._entity_field`). */
function questionErrors(t: Translator, error: unknown): Record<string, string> {
  if (!isApiError(error)) return {};
  const out: Record<string, string> = {};
  for (const problem of (error as ApiError).fieldErrors) {
    if (problem.field && problem.field.startsWith("custom_data.")) {
      out[problem.field] = t(problem.message_key, problem.params ?? {});
    }
  }
  return out;
}

/**
 * The whole application form, in ONE piece of state, split across two screens.
 *
 * ⚠ **IT IS HOISTED ABOVE THE STEPS ON PURPOSE, AND `DEF-CWP-3706` IS THE
 * REASON.** That defect's fix is *"the whole form goes every time, not just the
 * field that was left"*: the guest edge is throttled, a save that is turned
 * away is silent, and sending everything makes any single dropped request
 * harmless because the next one carries the lot again. Splitting *About you*
 * into a **When** step and an **About you** step (`CR-085` task (c), the
 * signed-off wireframes s16 and s17) would have quietly halved that guarantee
 * if each step had held its own half of the form — a dropped save on step 2
 * could then never be repaired by anything typed on step 3. One state, one
 * payload, two screens.
 */
function useApplicationForm(draft: ApplicationDraft | null, onSave: (patch: Patch) => void) {
  const [kind, setKind] = useState(draft?.applicant_kind ?? "person");
  // ⚠ ONE SHAPE, SHARED WITH `unfinished()` — see that function's note. The
  // gate and the form must read the same eight boxes or they will disagree.
  const [values, setValues] = useState<FormValues>(() => valuesOf(draft));
  /**
   * ⚠ **THE SAVED VALUE IS READ OFF THE EVENT, NOT OFF REACT STATE, AND THAT
   * IS `DEF-CWP-3705` (found by the walkthrough, 2026-09-04).** The obvious
   * handler is `onBlur: () => onSave({ [name]: values[name] })` — and `values`
   * is the state as it was AT RENDER TIME. Type into a box and leave it in the
   * same frame and React has not re-rendered yet, so the handler closes over
   * the OLD value and saves an empty field over a filled one.
   *
   * **It is not a theoretical race and the browser caught it: four of six
   * fields were saved as NULL** — email, mobile, date of birth and the start
   * date — while the two the test happened to type slowly survived. Every
   * unit test passed, because a unit test asserts on state and state was
   * correct; only a real keyboard in a real browser could see it.
   *
   * The DOM's `value` is the truth about what the box shows, whatever React
   * has caught up with, so that is what is sent.
   */
  const kindRef = useRef(kind);
  kindRef.current = kind;
  // The current form, readable from an event handler without waiting for a
  // re-render — the same reason `kindRef` exists.
  const valuesRef = useRef(values);
  valuesRef.current = values;
  // DEF-CWP-9163 — the mailing block, held beside the boxes for the same two
  // reasons (one payload; readable from a handler before React re-renders).
  const [mailing, setMailingState] = useState<MailingValue>(() => mailingFromDraft(draft));
  const mailingRef = useRef(mailing);
  mailingRef.current = mailing;
  const setMailing = (next: MailingValue) => {
    mailingRef.current = next;
    setMailingState(next);
  };
  // `CR-161-BRC10` W7 — the answers to the utility's own questions, held
  // beside the boxes for the same two reasons, and sent with the whole form
  // ONLY when the utility asks something (`asksRef`).
  const [custom, setCustomState] = useState<PortalCustomData>(() => draft?.custom_data ?? {});
  const customRef = useRef(custom);
  customRef.current = custom;
  const asksRef = useRef(asksQuestions(draft));
  asksRef.current = asksQuestions(draft);
  const customPayload = () => (asksRef.current ? customRef.current : null);
  // ⊕ `DEF-CUS-10250` — the co-applicant card and the Preferences panel, held
  // beside the boxes for the same two reasons (one payload; readable from a
  // handler before React re-renders).
  const [coApplicant, setCoApplicantState] = useState<CoApplicantValue>(() =>
    coApplicantFromDraft(draft),
  );
  const coApplicantRef = useRef(coApplicant);
  coApplicantRef.current = coApplicant;
  const [preferences, setPreferencesState] = useState<PreferencesValue>(() =>
    preferencesFromDraft(draft),
  );
  const preferencesRef = useRef(preferences);
  preferencesRef.current = preferences;
  /** The whole form as the draft's own field names — every save sends it. */
  const build = (
    values: Record<string, string>,
    kind: string,
    mailing: MailingValue,
    custom: PortalCustomData | null,
  ): Patch =>
    payloadFrom(values, kind, mailing, custom, {
      coApplicant: coApplicantRef.current,
      preferences: preferencesRef.current,
    });
  const setCoApplicant = (next: CoApplicantValue) => {
    coApplicantRef.current = next;
    setCoApplicantState(next);
  };
  const commitCoApplicant = (next: CoApplicantValue) => {
    setCoApplicant(next);
    onSave(build(valuesRef.current, kindRef.current, mailingRef.current, customPayload()));
  };
  const commitPreferences = (next: PreferencesValue) => {
    preferencesRef.current = next;
    setPreferencesState(next);
    onSave(build(valuesRef.current, kindRef.current, mailingRef.current, customPayload()));
  };
  const commitMailing = (next: MailingValue) => {
    setMailing(next);
    onSave(build(valuesRef.current, kindRef.current, next, customPayload()));
  };
  const setAnswer = (entity: PortalCustomEntity, key: string, value: unknown) => {
    const next = { ...customRef.current, [entity]: { ...(customRef.current[entity] ?? {}), [key]: value } };
    customRef.current = next;
    setCustomState(next);
  };
  const commitAnswer = (entity: PortalCustomEntity, key: string, value: unknown) => {
    setAnswer(entity, key, value);
    onSave(build(valuesRef.current, kindRef.current, mailingRef.current, customPayload()));
  };

  const field = (name: keyof typeof values) => ({
    value: values[name],
    onChange: (value: string) => {
      const next = { ...valuesRef.current, [name]: value };
      valuesRef.current = next;
      setValues(next);
    },
    onBlur: (event: FocusEvent<HTMLElement>) => {
      const input = event.target as HTMLInputElement | HTMLSelectElement;
      const value = input?.value ?? valuesRef.current[name];
      // ⚠ **THE WHOLE FORM GOES EVERY TIME, NOT JUST THE FIELD THAT WAS LEFT
      // — `DEF-CWP-3706`, and the browser is the only thing that could have
      // found it.** The guest edge is throttled at sixty requests a minute per
      // address (`BR-CWP-022`, and rightly); a save that is turned away is a
      // field the applicant typed and we did not keep, **silently**, because a
      // `429` on a background save has nothing to show them. Sending the whole
      // form makes any single dropped request harmless: the next one carries
      // everything again.
      //
      // ⚠ **AND THE SEND HAPPENS HERE, NOT INSIDE THE STATE UPDATER.** The
      // first version called `onSave` from inside `setValues(old => …)`, which
      // is a side effect in a function React requires to be pure — it fires
      // during render, and React Query drops a mutation started there. Three
      // fields out of six were saved and three were not, with nothing in the
      // console to say why (`DEF-CWP-3708`).
      const next = { ...valuesRef.current, [name]: value };
      valuesRef.current = next;
      setValues(next);
      onSave(build(next, kindRef.current, mailingRef.current, customPayload()));
    },
  });

  /** `DEF-CWP-9818` — a dropdown's pick: set AND saved at once, because a
   *  choice is finished the moment it is made (there is no typing to wait
   *  out). Several fields in one patch, so a category change clears a
   *  sub-category that does not belong to it in the same save. */
  const choose = (patch: Partial<FormValues>) => {
    const next = { ...valuesRef.current, ...patch };
    valuesRef.current = next;
    setValues(next);
    onSave(build(next, kindRef.current, mailingRef.current, customPayload()));
  };

  const chooseKind = (next: "person" | "business") => {
    setKind(next);
    kindRef.current = next;
    onSave(build(valuesRef.current, next, mailingRef.current, customPayload()));
  };

  /** Everything, as it stands right now — what a step sends on the way out. */
  const wholeForm = () => build(valuesRef.current, kindRef.current, mailingRef.current, customPayload());

  return {
    kind,
    chooseKind,
    choose,
    values,
    field,
    wholeForm,
    mailing,
    setMailing,
    commitMailing,
    custom,
    setAnswer,
    commitAnswer,
    coApplicant,
    setCoApplicant,
    commitCoApplicant,
    preferences,
    commitPreferences,
  };
}

type ApplicationForm = ReturnType<typeof useApplicationForm>;

/** The four step labels, out of ONE set of keys — `CWP-008` draws the same
 *  four, so the journey cannot describe itself two ways. */
function StepBar(props: { current: number }) {
  const { t } = useTranslation();
  return (
    <Stepper
      current={props.current}
      steps={[
        t("portal.apply.step1"),
        t("portal.apply.step2"),
        t("portal.apply.step3"),
        t("portal.apply.step4"),
      ]}
    />
  );
}

/**
 * The saved-as-you-go line, and the one case where it must NOT reassure.
 *
 * ⚠ **THIS SENTENCE IS A CLAIM, SO IT HAS TO BE CHECKED — hard-won law 1.**
 * *"Everything you type is saved as you go"* was printed unconditionally,
 * including while the last save had been refused, which is the most expensive
 * possible moment to reassure somebody. The guest edge is throttled
 * (`BR-CWP-022`) and a background save CAN be turned away; when it has been,
 * the line says so and names what to do, in the applicant's own language.
 */
function SavedNote(props: { error: unknown }) {
  const { t } = useTranslation();
  if (props.error) {
    return (
      // F-02: announced, but it does NOT take focus — it fires when a box is
      // left, and moving focus then would pull the customer out of the next box.
      <Announced tone="error" focus={false} className="text-base font-semibold text-danger-700" data-saved-note="failed">
        {t("portal.apply.saveFailed")}
      </Announced>
    );
  }
  return (
    <p className="text-base text-neutral-600" data-saved-note="ok">
      {t("portal.apply.savedAlready")}
    </p>
  );
}

/**
 * The service address as every step after step 1 shows it — `DEF-CWP-9817`.
 *
 * The SERVER composes it (`selectors.draft_service_address`): the matched premises'
 * own address in US form — *1841 Quarry Hill Ct, #12, Silver Creek, TX 78611*
 * — or the typed parts with the utility's state when we hold none
 * (`BR-CUS-1091`: once a premises is matched, the premises is what shows).
 * The browser never re-composes it, so the head, the rail and Check and send
 * cannot write one address three ways. A payload without it (an older server)
 * falls back to the street as typed.
 */
function serviceLine(draft: ApplicationDraft | null): string {
  return draft?.service_address ?? draft?.address_as_given ?? "—";
}

/** `DEF-CUS-10250` — the Preferences panel on one line for Check and send. */
function preferencesLine(t: Translator, draft: ApplicationDraft): string {
  const parts: string[] = [];
  if (draft.paperless === true) parts.push(t("portal.apply.preferences.paperless"));
  if (draft.text_reminders === true) parts.push(t("portal.apply.preferences.textReminders"));
  if (draft.preferred_language) parts.push(languageName(draft.preferred_language));
  return parts.join(" · ") || "—";
}

/** The rail both middle steps carry: the address, and what is not promised.
 *
 * ⚠ `extra` is wireframe s19's *Already done* panel and is drawn FIRST, because
 * a returning applicant reads the rail to find out where they got to. It is
 * `null` on a first visit, when there is nothing already done to list. */
function AddressRail(props: {
  draft: ApplicationDraft | null;
  availability: Availability | null;
  extra?: ReactNode;
}) {
  const { t } = useTranslation();
  return (
    <>
      {props.extra ?? null}
      <Panel as="aside" title={t("portal.apply.theAddress")}>
        <KVList
          rows={[
            {
              key: "address",
              label: t("portal.apply.serviceAddress"),
              value: serviceLine(props.draft),
            },
            // ⚠ **DRAWN ONLY WHEN THERE IS ONE** (`BR-CWP-093`). A row reading
            // *Unit —* on every application in a town of houses is furniture.
            // ⊕ `DEF-CWP-9817` — and only for a draft the server wrote no
            // `service_address` for: that line already carries the unit.
            ...(props.draft?.address_unit_as_given && !props.draft.service_address
              ? [
                  {
                    key: "unit",
                    label: t("portal.apply.unit"),
                    value: props.draft.address_unit_as_given,
                  },
                ]
              : []),
            {
              key: "services",
              label: t("portal.apply.servicesHere"),
              value: askedForNames(props.draft, props.availability),
            },
          ]}
        />
      </Panel>
      {/* ⚠ **A PLAIN PANEL, AND `tone="info"` WAS WRONG HERE — SEEN BY LOOKING,
          which is the only way it could be (hard-won law 6).** r10 draws no blue
          at all: its device for an aside is grey text, and its emphasis is a
          rule in `--color-accent`. A note is not an `info`. */}
      <Panel as="aside">{t("portal.apply.nothingPromised")}</Panel>
    </>
  );
}

/**
 * **STEP 2 — WHEN** (wireframe s16: *"when do I need it on, which of the
 * optional services do I want, and what will it cost to start?"*).
 *
 * ⚠ **THIS STEP DID NOT EXIST AND THE STEP BAR CLAIMED IT DID.** The journey
 * ran *address → about you → check* under a four-label stepper, so step 3 was
 * marked ✓ **done** on the check screen having never been shown to anybody. PO
 * ruling: *"please show all 4 screens - address, when , about you, check"*.
 * Nothing here is a new question — the start date and the person-or-business
 * choice were both on the old *About you* — they are asked where the drawing
 * asks them, which is before anybody types their name.
 *
 * ⚠ **THE SERVICES ARE FACTS AND NOT TICK-BOXES, AND THAT IS THE WIREFRAME'S
 * OWN STATE RATHER THAN A SHORTCUT.** s16 draws ticked-and-locked boxes with a
 * reason each — *required*, *required with water*, *optional · $18.00 a month*
 * — and lists **No optional services** among its states: *"The list is shown
 * as facts, not tick-boxes, when nothing is optional."* `GET
 * premises/availability` answers `available` per service and says nothing
 * about required, optional, or a monthly price, so every service it names is
 * in the same class and there is nothing to choose. Drawing tick-boxes over
 * that would be a control that changes nothing (hard-won law 2).
 *
 * ⚠ **THE COST PANEL IS `CWP-008`'s ARITHMETIC RESTATED, NEVER RECOMPUTED.**
 * Both figures come from the same availability read the address step showed and
 * the check step shows again, so a disagreement between the three is
 * impossible rather than merely unlikely (`US-CWP-014` §7's rule, applied one
 * step earlier).
 */
function WhenStep(props: {
  form: ApplicationForm;
  draft: ApplicationDraft | null;
  availability: Availability | null;
  head: ReactNode;
  /** The step's name inside the card — see `stepTitle` in `ApplicationSteps`. */
  stepTitle: ReactNode;
  /** `CR-161-BRC10` W7 — the property's questions (`ApplicationCustomFields`), or
   *  `null` when the utility asks none. */
  questions: ReactNode;
  held: MissingKey | null;
  rail?: ReactNode;
  saving: boolean;
  error: unknown;
  onSave: (patch: Patch) => void;
  onContinue: () => void;
}) {
  const { t } = useTranslation();
  const form = props.form;
  const apply = props.availability?.if_you_apply ?? null;
  const served = (props.availability?.rows ?? []).filter((row) => row.available);
  const offered = offerToTick(props.availability);
  // ⚠ **HELD HERE AS WELL AS ON THE DRAFT, FOR `DEF-CWP-3705`'s REASON.** Two
  // ticks in quick succession would otherwise both be computed from the draft
  // as it was before the first save came back, and the second would send a
  // list without the first. The screen's own copy is the truth about the boxes.
  const [picks, setPicks] = useState<string[] | null>(null);
  const ticked = picks ?? props.draft?.service_codes ?? [];
  const toggle = (code: string, on: boolean) => {
    // In the utility's order, whatever order they were ticked in.
    const next = offered
      .map((one) => one.service_code)
      .filter((one) => (one === code ? on : ticked.includes(one)));
    setPicks(next);
    props.onSave({ service_codes: next });
  };

  return (
    // ⚠ **THE HEAD IS INSIDE THE `data-screen` MARK AND ABOVE EVERY BRANCH** —
    // the shape `components/states.tsx`'s `PortalScreen` exists to make cheap
    // (`DEF-CWP-4926`). It is written out here rather than composed because
    // this screen carries a SECOND mark: `data-step` is what
    // `cr068-c-start-service.mjs` and `CheckAndSend.dom.test.tsx` select on to
    // tell the three steps apart, and `PortalScreen` has no slot for it.
    <div data-screen="CWP-047" data-step="when">
      {props.head}
      <StepBar current={2} />
      <TwoCol
        main={
          <Card testId="when">
            {props.stepTitle}
            <FormField
              id="requested_start"
              label={t("portal.apply.startDate")}
              required
              helper={t("portal.apply.startDateHelper")}
              // A refused ANSWER is printed on its own box, not on the date's (W7).
              error={
                props.error && Object.keys(questionErrors(t, props.error)).length === 0
                  ? refusalText(t, props.error)
                  : null
              }
            >
              {/* ⊕ `DEF-CUS-10250` — the product's date picker, never a native
                  browser date box (PO 2026-10-18, *"any date field … should be
                  date picker"*). */}
              <PortalDateBox
                id="requested_start"
                value={form.values.requested_start}
                required
                onChange={(requested_start) => form.choose({ requested_start })}
              />
            </FormField>
            {/* ⊕ `DEF-CUS-10250` — *person or business* MOVED to the top of
                About you, where Move-in and the drawing ask it (*"I'm applying
                as"*, image `04-portal.png`). */}

            <SectionTitle>{t("portal.apply.whichServices")}</SectionTitle>
            {/* B14 rule 32 — one sentence for the section. ⊕ `DEF-CWP-4930`:
                NOT over the tick boxes — *"there is nothing to choose"* is
                false where the applicant is choosing, and the boxes carry
                their own one sentence. */}
            {offered.length === 0 ? (
              <p className="text-body text-neutral-700" data-services-note="">
                {t("portal.apply.servicesAreSet")}
              </p>
            ) : null}
            {served.length > 0 ? (
              <KVList
                rows={served.map((row) => ({
                  key: row.service_code,
                  label: row.service_name,
                  value: t("portal.availability.included"),
                }))}
              />
            ) : offered.length > 0 ? (
              // ⚠ **`DEF-CWP-4930` — AN ADDRESS WE DO NOT HOLD HAS NOTHING TO
              // READ, SO THE APPLICANT TICKS.** Until 2026-10-02 this branch
              // fell through to *"We will confirm the services"* and the
              // draft carried none, so Send was refused for ever on a step the
              // applicant was never shown. The names are the utility's own,
              // in its own order; nothing is priced, because nobody has looked
              // at the address yet.
              <div className="flex flex-col gap-2" data-services="pick">
                <p className="text-body text-neutral-700">{t("portal.apply.servicesPick")}</p>
                {offered.map((one) => (
                  <label
                    key={one.service_code}
                    className="flex items-center gap-2 text-body text-neutral-900"
                    data-service-pick={one.service_code}
                  >
                    <input
                      type="checkbox"
                      checked={ticked.includes(one.service_code)}
                      onChange={(event) => toggle(one.service_code, event.target.checked)}
                    />
                    {one.service_name}
                  </label>
                ))}
              </div>
            ) : (
              // BR-CWP-093 — an empty list is a sentence, never a frame with
              // nothing in it.
              <p className="text-body text-neutral-600" data-services="none">
                {t("portal.apply.servicesNotKnown")}
              </p>
            )}

            {props.questions}

            {apply !== null ? (
              // ⚠ The deposit line is ABSENT when there is nothing to quote,
              // never `— deposit on your first bill.` — `DEF-CWP-4875`, and
              // the rule is written out beside `ifYouApplyBullets`.
              <ConsequenceBox
                heading={t("portal.apply.whatItCostsToStart")}
                bullets={ifYouApplyBullets(t, apply)}
              />
            ) : null}

            {/* ⚠ **THE COMMIT ON THE RIGHT — `DEF-CWP-9164`.** Step 2 has no way
                back on this route (step 1 is `CWP-008`, and re-entering it mints
                a new draft — see `STEP_OF`), so the left side is empty and
                Continue sits exactly where it sits on steps 3 and 4. */}
            <WizardFooter
              forward={
                <>
                  {/* ⚠ *Save and finish later* IS NOT A SECOND WRITE PATH — the
                      draft is already saved on every field. So it is drawn the
                      way this product draws a control somebody may not use: the
                      staff disabled presentation WITH its reason beneath it
                      (`BR-CWP-056`, CR-068 R3), never a live-looking button over
                      nothing. The wireframe draws the control; hard-won law 2
                      says what it must not pretend to be. */}
                  <HeldButton
                    label={t("portal.apply.saveAndFinishLater")}
                    reason={t("portal.apply.saveLaterHeld")}
                    size="default"
                  />
                  {/* ⚠ **HELD UNTIL THE STEP IS ANSWERED — `DEF-CWP-4877`.** The
                      start date carries the brand asterisk and this control was
                      live with the box empty, so the whole of step 2 could be
                      skipped and the refusal arrived two screens later. */}
                  <Button
                    variant="primary"
                    size="default"
                    data-action="continue"
                    disabled={props.saving || props.held !== null}
                    title={heldTitle(t, props.held)}
                    aria-describedby={props.held !== null ? HELD_REASON_ID : undefined}
                    onClick={() => {
                      props.onSave(form.wholeForm());
                      props.onContinue();
                    }}
                  >
                    {t("portal.apply.continue")}
                  </Button>
                </>
              }
            />
            <HeldReason held={props.held} />
            <SavedNote error={props.error} />
          </Card>
        }
        rail={
          <AddressRail draft={props.draft} availability={props.availability} extra={props.rail} />
        }
      />
    </div>
  );
}

/**
 * **STEP 3 — ABOUT YOU** (wireframe s17: *"who are you, how do we reach you,
 * and can you prove it? This is the step people abandon."*).
 *
 * ⚠ **THE PROOF-OF-IDENTITY BOX IS LIVE — `CR-158-BRC10`, PO 2026-10-01.**
 * The wireframe gives a document drop the largest block on the screen. Until
 * 2026-10-01 it was HELD: consumer upload was a signed deferral (PO 2026-08-08,
 * `DF-4`: *consumer upload portal = v2*), so `PhotoPicker` drew the SHAPE with
 * its reason and there was no file input. The PO superseded `DF-4` for this
 * request — *"we need to now accept the document from portal - make provisio,
 * and use upload document component we build"* — so the box is
 * `ApplicationDocuments`, the product's own `FileDropField`, posting each file
 * to the draft the moment it is chosen. **It stays optional**: the wireframe's
 * *Send it later* is still a real option, because nothing waits for a file.
 * (`reports` still refuses a photo by name; `DF-4` holds there.)
 */
function AboutYou(props: {
  form: ApplicationForm;
  draft: ApplicationDraft | null;
  availability: Availability | null;
  /** `CR-158-BRC10` — the drop zone the wireframe draws, now live. */
  documents: ReactNode;
  head: ReactNode;
  /** The step's name inside the card — see `stepTitle` in `ApplicationSteps`. */
  stepTitle: ReactNode;
  /** `CR-161-BRC10` W7 — the applicant's own questions, or `null`. */
  questions: ReactNode;
  held: MissingKey | null;
  rail?: ReactNode;
  saving: boolean;
  error: unknown;
  onSave: (patch: Patch) => void;
  onBack: () => void;
  onContinue: () => void;
}) {
  const { t } = useTranslation();
  const form = props.form;
  const kind = form.kind;
  const values = form.values;
  const field = form.field;
  // ⊕ `DEF-CUS-10250` — Move-in's format checks, the SAME functions Move-in's
  // Who panel uses (`CustomerWhoPanel`), shown on the box as it is typed;
  // blank is never an error here (whether a box is required is the gate's).
  const phoneProblem = phoneFormatProblem(values.phone);
  const emailProblem = emailFormatProblem(values.email);
  const ssnProblem = ssnLast4Problem(values.ssn_last4);
  const coApplicantProblems = {
    ...(phoneFormatProblem(form.coApplicant.phone) !== null
      ? { co_applicant_phone: t(phoneFormatProblem(form.coApplicant.phone) ?? "") }
      : {}),
    ...(emailFormatProblem(form.coApplicant.email) !== null
      ? { co_applicant_email: t(emailFormatProblem(form.coApplicant.email) ?? "") }
      : {}),
  };
  const today = todayIso();

  return (
    // See `WhenStep` for why the head is written out here rather than composed
    // from `PortalScreen`: this screen carries a second mark, `data-step`.
    <div data-screen="CWP-047" data-step="about">
      {props.head}
      <StepBar current={3} />
      <TwoCol
        main={
          <Card testId="about-you">
            {props.stepTitle}
            {/* ⊕ **`DEF-CUS-10250` — MOVE-IN'S FIELDS, IN MOVE-IN'S ORDER, IN
                THE PORTAL LOOK** (PO 2026-10-18; image `04-portal.png`): I'm
                applying as · first and last name · mobile phone (required) and
                email (OPTIONAL) · how should we contact you · date of birth ·
                last 4 of SSN · the co-applicant card · the mailing address ·
                Preferences. NO category or sub-category: *"they may not able
                to provide cargory etc upfront"* — staff set it before
                approving. */}
            <FormSection testId="applying-as">
              <div className="flex flex-col gap-1.25">
                <span id="applying-as-label" className="text-base font-semibold text-neutral-800">
                  {t("portal.apply.applyingAs")}
                </span>
                <SegmentedControl
                  purpose="choice"
                  name="applicant_kind"
                  labelledBy="applying-as-label"
                  label={t("portal.apply.applyingAs")}
                  active={kind}
                  onSelect={(next) => form.chooseKind(next as "person" | "business")}
                  segments={[
                    { id: "person", label: t("portal.apply.aPerson") },
                    { id: "business", label: t("portal.apply.aBusiness") },
                  ]}
                />
              </div>
            </FormSection>
            <FormSection testId="about-fields">
              {kind === "business" ? (
                // TC-4 — a business is identified by company name and tax ID
                // rather than a date of birth.
                <TwoUp>
                  <FormField id="company_name" label={t("portal.apply.companyName")} required>
                    <span onBlur={field("company_name").onBlur}>
                      <TextInput id="company_name" value={values.company_name} required onChange={field("company_name").onChange} />
                    </span>
                  </FormField>
                  <FormField id="tax_id" label={t("portal.apply.taxId")} required>
                    <span onBlur={field("tax_id").onBlur}>
                      <TextInput id="tax_id" value={values.tax_id} required onChange={field("tax_id").onChange} />
                    </span>
                  </FormField>
                </TwoUp>
              ) : null}
              <TwoUp>
                <FormField id="first_name" label={t("portal.apply.firstName")} required={kind === "person"}>
                  <span onBlur={field("first_name").onBlur}>
                    <TextInput id="first_name" value={values.first_name} autoComplete="given-name" required={kind === "person"} onChange={field("first_name").onChange} />
                  </span>
                </FormField>
                <FormField id="last_name" label={t("portal.apply.lastName")} required={kind === "person"}>
                  <span onBlur={field("last_name").onBlur}>
                    <TextInput id="last_name" value={values.last_name} autoComplete="family-name" required={kind === "person"} onChange={field("last_name").onChange} />
                  </span>
                </FormField>
              </TwoUp>
              <TwoUp>
                <FormField
                  id="phone"
                  label={t("portal.apply.mobile")}
                  required
                  error={phoneProblem === null ? null : t(phoneProblem)}
                >
                  <span onBlur={field("phone").onBlur}>
                    <TextInput
                      id="phone"
                      type="tel"
                      value={values.phone}
                      required
                      autoComplete="tel"
                      invalid={phoneProblem !== null}
                      describedBy={fieldErrorId("phone")}
                      onChange={field("phone").onChange}
                    />
                  </span>
                </FormField>
                <FormField
                  id="email"
                  label={t("portal.apply.email")}
                  helper={t("portal.apply.optional")}
                  error={emailProblem === null ? null : t(emailProblem)}
                >
                  <span onBlur={field("email").onBlur}>
                    <TextInput
                      id="email"
                      type="email"
                      value={values.email}
                      autoComplete="email"
                      invalid={emailProblem !== null}
                      describedBy={fieldErrorId("email")}
                      onChange={field("email").onChange}
                    />
                  </span>
                </FormField>
              </TwoUp>
              <TwoUp>
                <FormField id="contact_by" label={t("portal.apply.contactBy")}>
                  <SelectInput
                    id="contact_by"
                    value={values.contact_by}
                    placeholder={t("portal.apply.contactByChoose")}
                    options={CONTACT_BY_OPTIONS.map((code) => ({
                      value: code,
                      label: t(`portal.apply.contactByOption.${code}`),
                    }))}
                    onChange={(contact_by) => form.choose({ contact_by })}
                  />
                </FormField>
                {kind === "person" ? (
                  // ⚠ NO ASTERISK (`DEF-CWP-4877`): the application is accepted
                  // without a date of birth. ⊕ `DEF-CUS-10250` — the product's
                  // date picker, never a native browser date box.
                  <PortalDateField
                    id="date_of_birth"
                    label={t("portal.apply.dateOfBirth")}
                    value={values.date_of_birth}
                    max={today}
                    onChange={(date_of_birth) => form.choose({ date_of_birth })}
                  />
                ) : null}
              </TwoUp>
              {kind === "person" ? (
                <TwoUp>
                  {/* 🔒 THE LAST FOUR AND NOTHING MORE — PO 2026-10-18 (*"okay"*
                      to *"last 4 of SSN only"*): no full SSN, no licence online. */}
                  <FormField
                    id="ssn_last4"
                    label={t("portal.apply.ssnLast4")}
                    helper={t("portal.apply.ssnLast4Helper")}
                    error={ssnProblem === null ? null : t(ssnProblem)}
                  >
                    <span onBlur={field("ssn_last4").onBlur}>
                      <TextInput
                        id="ssn_last4"
                        value={values.ssn_last4}
                        inputMode="numeric"
                        autoComplete="off"
                        invalid={ssnProblem !== null}
                        describedBy={fieldErrorId("ssn_last4")}
                        onChange={(typed) => field("ssn_last4").onChange(typed.replace(/\D/g, "").slice(0, 4))}
                      />
                    </span>
                  </FormField>
                </TwoUp>
              ) : null}
            </FormSection>

            <CoApplicantCard
              value={form.coApplicant}
              onChange={form.setCoApplicant}
              onCommit={form.commitCoApplicant}
              today={today}
              errors={coApplicantProblems}
            />

            {/* ⚠ **WHERE THE BILL GOES — `DEF-CWP-9163`.** A mailing address,
                never a second service address (hard rule 8's named exception). */}
            <MailingAddressFields
              value={form.mailing}
              serviceAddress={serviceLine(props.draft)}
              onChange={form.setMailing}
              onCommit={form.commitMailing}
            />

            <ApplicationPreferences
              value={form.preferences}
              locales={props.draft?.locales ?? ["en"]}
              onCommit={form.commitPreferences}
            />

            {props.questions}

            <SectionTitle>{t("portal.apply.proofOfIdentity")}</SectionTitle>
            {/* B14 rule 32 — one sentence for the section, and it is the
                sentence that keeps the applicant moving: nothing here blocks
                the application. */}
            <p className="text-body text-neutral-700" data-identity-note="">
              {t("portal.apply.proofComesLater")}
            </p>
            {/* ⚠ **THE HOLD HAS EXPIRED — `CR-158-BRC10`, PO 2026-10-01.** This
                was `<PhotoPicker reason="Documents come to the counter." />`,
                the drawn shape with no input, because `DF-4` deferred consumer
                upload to v2. The PO superseded `DF-4` for this request (*"we
                need to now accept the document from portal"*), so the box is
                the product's own drop zone and posts to the draft. It is still
                OPTIONAL: Continue and Send never wait for a file. */}
            {props.documents}

            {/* `DEF-CWP-9164` — Back on the LEFT, Continue on the RIGHT. */}
            <WizardFooter
              back={
                // r10 rule 1: inside a stepper the footer's `← Back` means
                // PREVIOUS STEP and nothing else.
                <Button variant="secondary" size="default" data-action="back" onClick={props.onBack}>
                  {t("portal.apply.backStep")}
                </Button>
              }
              forward={
                // ⚠ **HELD UNTIL THE STEP IS ANSWERED — `DEF-CWP-4877`.** Five
                // boxes carried the brand asterisk and this control was live
                // with every one of them empty.
                <Button
                  variant="primary"
                  size="default"
                  data-action="continue"
                  disabled={props.saving || props.held !== null}
                  title={heldTitle(t, props.held)}
                  aria-describedby={props.held !== null ? HELD_REASON_ID : undefined}
                  onClick={() => {
                    props.onSave(form.wholeForm());
                    props.onContinue();
                  }}
                >
                  {t("portal.apply.continue")}
                </Button>
              }
            />
            <HeldReason held={props.held} />
            <SavedNote error={props.error} />
          </Card>
        }
        rail={
          <AddressRail draft={props.draft} availability={props.availability} extra={props.rail} />
        }
      />
    </div>
  );
}

/**
 * **STEP 4 — CHECK** (wireframe s18: *"is all of that right, what have I
 * agreed to, and what happens next?"*).
 *
 * ⚠ **EVERY SECTION CARRIES A CHANGE LINK BACK TO THE STEP IT CAME FROM,
 * AND THE WIREFRAME IS EXPLICIT THAT A GENERIC BACK IS NOT THAT:** *"each with
 * a change link that returns to the step it came from — not a generic Back.
 * This is the same discipline the rate wizard's review needed and did not
 * have."* Before `CR-085` this screen had one ← Back, which from the *You*
 * block meant *go to the step before this one* and from the *Service* block
 * meant nothing at all.
 *
 * ⚠ **THE START DATE GOES THROUGH THE TENANT'S OWN FORMAT** (`DEF-CWP-4193`,
 * `DEF-CWP-4204`). It reached the applicant as `2026-10-14` — the wire's own
 * string — on the last screen before a request that starts a legal supply,
 * while Pine Hill's Regional setting says `MM/DD/YYYY`. Waves M and L took this
 * fix for their screens; the start-service journey was never moved.
 */
function applicationFeeRow(
  fee: MoneyCell | undefined,
  t: Translator,
): { key: string; label: string; value: string }[] {
  if (fee === undefined || fee.kind !== "amount" || fee.amount === null) return [];
  const zero = /^0+(\.0+)?$/.test(fee.amount.trim());
  return [
    {
      key: "application_fee",
      label: t("portal.apply.applicationFee"),
      value: zero ? t("portal.apply.payNothing") : (fee.display ?? fee.amount),
    },
  ];
}

function CheckAndSend(props: {
  draft: ApplicationDraft;
  availability: Availability | null;
  /** `CR-158-BRC10` / `DEF-CWP-9167` — the files attached on step 3, per
   *  document asked for; the name opens the file (`DEF-CWP-9166`). */
  documents: ReactNode;
  head: ReactNode;
  held: MissingKey | null;
  onBack: () => void;
  onChangeStep: (step: ApplyStep) => void;
  onSend: (paperless: boolean, payment: ApplicationFeePayment | null) => void;
  sending: boolean;
  error: unknown;
}) {
  const { t } = useTranslation();
  const showDate = usePortalDate();
  // 🔒 CR-191-BRC10 (PO 2026-10-23) — a fee above $0.00 is paid by card HERE,
  // before the application is sent; there is no "pay later". `$0.00` or no
  // fee → no payment step at all, and *Nothing is charged today.* stays.
  const fee = feeToPay(props.availability?.application_fee);
  const cardAvailable = props.availability?.card_payment_available === true;
  const [card, setCard] = useState<FeeCardValue>(EMPTY_FEE_CARD);
  const [cardWrong, setCardWrong] = useState(false);
  // ⛔ NOT THE IDEMPOTENCY KEY ANY MORE (DEF-PAY-10554, 2026-10-23): a reload
  // minted a new token and so a second debit. The server makes the key from
  // the draft and keeps it on the draft; this token is still sent and is not
  // read. Hard rule 6 now lives in `portal/services._fee_key`.
  const attemptToken = useRef(newDraftToken());
  useEffect(() => {
    if (
      isApiError(props.error) &&
      (props.error as ApiError).messageKey === "portal.quickPay.declined"
    ) {
      attemptToken.current = newDraftToken();
    }
  }, [props.error]);
  const cardHeld = fee !== null && (!cardAvailable || !feeCardIsComplete(card));
  const send = () => {
    if (fee === null) {
      props.onSend(paperless, null);
      return;
    }
    // ⚠ TOKENISED BEFORE ANYTHING IS POSTED (`BR-CWP-057`): the number is
    // reduced to a token, a brand and a last four and is not in the body.
    const instrument = tokeniseCard(card.cardNumber);
    if (instrument === null) {
      setCardWrong(true);
      return;
    }
    setCardWrong(false);
    props.onSend(paperless, {
      instrument,
      // The STORED figure the applicant saw; the server re-reads and compares.
      fee_amount: fee.amount ?? "",
      attempt_token: attemptToken.current,
    });
  };
  // ⚠ **UNTICKED UNTIL THE APPLICANT TICKS IT — `DEF-CWP-9079`.** Every
  // delivery election is `NOT NULL DEFAULT FALSE` (decision log 2026-08-31,
  // hard-won law 3: defaults fail closed), and `BR-CWP-087` makes paperless a
  // RECORDED consent. A box that arrives ticked records one nobody gave.
  //
  // ⊕ `DEF-CUS-10250` — **EXCEPT WHERE THE APPLICANT ALREADY TICKED IT.**
  // About you now asks *Paperless billing* in its Preferences panel; an
  // applicant who chose *On* there has given the answer once, and this box
  // opens on THEIR choice — never on ours. Unset or *Off* opens unticked.
  const [paperless, setPaperless] = useState(props.draft.paperless === true);
  // ⚠ The refusal, WITH the step it names — `DEF-CWP-4877`. See `sendRefusal`.
  const refusal = props.error ? sendRefusal(t, props.error) : null;
  const apply = props.availability?.if_you_apply ?? null;
  const applicant =
    props.draft.applicant_kind === "business"
      ? (props.draft.company_name ?? "—")
      : [props.draft.first_name, props.draft.last_name].filter(Boolean).join(" ") || "—";
  const mailing = mailingFromDraft(props.draft);
  // `CR-161-BRC10` W7 — the answers to the utility's own questions, restated
  // under the block whose step asked them (the property's under *The
  // service*, the applicant's under *You*), so each has its Change link.
  const answerRows = (entity: PortalCustomEntity) =>
    (props.draft.custom_fields?.[entity] ?? []).map((field: PortalCustomField) => ({
      key: `cf-${entity}-${field.key}`,
      label: field.label,
      value: answerText(field, props.draft.custom_data?.[entity]?.[field.key], t),
    }));
  /**
   * ⚠ **WHAT A BLANK UNDER *WHAT YOU WILL PAY* MEANS, SAID IN WORDS —
   * `DEF-CWP-9165`.** Both lines drew a bare `—` for two different absences:
   * an address we do NOT hold has had no figures worked out at all
   * (`if_you_apply` is null — nobody has looked at the address yet), and a
   * held address whose plan charges no deposit has nothing to put on the
   * first bill (`money.nothing()`). A dash cannot tell *nothing to pay* from
   * *not known yet*, and on the last screen before somebody commits to a
   * supply that is the one thing it must say. So: *We will tell you* where
   * nothing was worked out, *No deposit* where the plan charges none. A real
   * figure, `$0.00` included, is printed as the figure. **The dash survives
   * for one state only — the availability read has not ANSWERED yet**
   * (`availability` is null), which is a wait of one round trip and not a
   * statement about money.
   */
  const payValue = (cell: { display: string | null } | undefined, none: string): string =>
    props.availability === null
      ? "—"
      : apply === null || cell === undefined
        ? t("portal.apply.payNotKnownYet")
        : (cell.display ?? none);

  return (
    // See `WhenStep` for why the head is written out here: `CWP-009` is the
    // fourth step of one journey and the step bar needs its own mark.
    <div data-screen="CWP-009" data-step="review">
      {props.head}
      <StepBar current={4} />
      <TwoCol
        main={
          <Card testId="check-and-send">
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <SectionTitle>{t("portal.apply.theService")}</SectionTitle>
              <Button
                variant="secondary"
                size="sm"
                data-change="when"
                onClick={() => props.onChangeStep("when")}
              >
                {t("portal.apply.change")}
              </Button>
            </div>
            <KVList
              rows={[
                { key: "address", label: t("portal.apply.address"), value: serviceLine(props.draft) },
                ...(props.draft.address_unit_as_given && !props.draft.service_address
                  ? [
                      {
                        key: "unit",
                        label: t("portal.apply.unit"),
                        value: props.draft.address_unit_as_given,
                      },
                    ]
                  : []),
                {
                  key: "services",
                  label: t("portal.apply.services"),
                  value: askedForNames(props.draft, props.availability),
                },
                {
                  key: "start",
                  label: t("portal.apply.startOn"),
                  value: showDate(props.draft.requested_start) || "—",
                },
                ...answerRows("premises"),
              ]}
            />
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <SectionTitle>{t("portal.apply.youHeading")}</SectionTitle>
              <Button
                variant="secondary"
                size="sm"
                data-change="about"
                onClick={() => props.onChangeStep("about")}
              >
                {t("portal.apply.change")}
              </Button>
            </div>
            <KVList
              rows={[
                { key: "applicant", label: t("portal.apply.applicant"), value: applicant },
                { key: "email", label: t("portal.apply.email"), value: props.draft.email ?? "—" },
                { key: "phone", label: t("portal.apply.mobile"), value: props.draft.phone ?? "—" },
                // ⊕ `DEF-CUS-10250` — Move-in's fields, restated before Send.
                // No category: the portal does not ask one (PO 2026-10-18).
                {
                  key: "contact_by",
                  label: t("portal.apply.contactBy"),
                  value: props.draft.contact_by
                    ? t(`portal.apply.contactByOption.${props.draft.contact_by}`)
                    : "—",
                },
                ...(props.draft.applicant_kind === "business"
                  ? []
                  : [
                      {
                        key: "date_of_birth",
                        label: t("portal.apply.dateOfBirth"),
                        value: showDate(props.draft.date_of_birth) || "—",
                      },
                      {
                        key: "ssn_last4",
                        label: t("portal.apply.ssnLast4"),
                        value: props.draft.ssn_last4 ?? "—",
                      },
                    ]),
                {
                  key: "co_applicant",
                  label: t("portal.apply.coApplicant.readBack"),
                  value: props.draft.co_applicant
                    ? [
                        props.draft.co_applicant_name,
                        // DEF-CUS-10257 — the stored CODE, named in Move-in's words.
                        props.draft.co_applicant_relationship
                          ? t(`customers.moveIn.customer.relationship.${props.draft.co_applicant_relationship}`)
                          : null,
                      ]
                        .filter(Boolean)
                        .join(" · ") || "—"
                    : t("portal.apply.coApplicant.none"),
                },
                // DEF-CWP-9163 — where the bill goes, restated before Send.
                {
                  key: "mailing",
                  label: t("portal.apply.mailingAddress"),
                  value: mailing.same ? t("portal.apply.mailingSame") : mailingLine(mailing) || "—",
                },
                {
                  key: "preferences",
                  label: t("portal.apply.preferences.title"),
                  value: preferencesLine(t, props.draft),
                },
                ...answerRows("customers"),
                ...answerRows("accounts"),
              ]}
            />
            <SectionTitle>{t("portal.apply.whatYouWillPay")}</SectionTitle>
            <KVList
              rows={[
                {
                  key: "before_we_start",
                  // ⚠ US-CWP-014 §7: this RESTATES CWP-008's arithmetic and must
                  // not recompute it. Both figures come from the same
                  // availability read, so a disagreement is impossible rather
                  // than merely unlikely.
                  label: t("portal.apply.toPayBeforeWeStart"),
                  value: payValue(apply?.before_we_start, t("portal.apply.payNothing")),
                },
                {
                  key: "on_first_bill",
                  label: t("portal.apply.onYourFirstBill"),
                  value: payValue(apply?.on_first_bill, t("portal.apply.noDeposit")),
                },
                // 🔒 DEF-CUS-9819 (PO 2026-10-06) — the application fee the
                // request will arrive with, from the code the utility marked
                // and the same read the clerk's line is priced from. $0.00
                // reads "Nothing to pay"; no row when no code is marked.
                ...applicationFeeRow(props.availability?.application_fee, t),
              ]}
            />
            <SectionTitle>{t("portal.apply.weWillNeedThese")}</SectionTitle>
            {/* ⚠ **ATTACHING IS OPTIONAL — AND EACH ROW NOW SAYS WHETHER IT IS
                DONE (`DEF-CWP-9167`, PO ruling 2026-10-02).** Nothing here is
                required and Send never waits for a file (US-CWP-014 §1). Each
                document asked for reads *Attached ✓* with its file — which
                opens it — or *Bring later*; until this, both rows read *NOW OR
                LATER* over two attached files, because nothing said which file
                was which. */}
            {props.documents}
            {fee !== null ? (
              <ApplicationFeeCard cardAvailable={cardAvailable} value={card} onChange={setCard} />
            ) : null}
            <div className="border border-neutral-300 p-3" data-consent-box="">
              <FormField
                id="paperless"
                label={t("portal.consent.paperless.legend")}
                required
                // ⚠ CR-068 R4 · US-CWP-014 TC-3 — PRINT STAYS THE FLOOR, and
                // any copy claiming paperless stops paper bills fails review.
                // This helper is part of the consent, not decoration: it is
                // listed in the wording version (`apps/portal/wording.py`).
                helper={t("portal.consent.paperless.helper")}
              >
                <label className="flex items-center gap-2 text-body text-neutral-900">
                  <input
                    id="paperless"
                    type="checkbox"
                    checked={paperless}
                    onChange={(event) => setPaperless(event.target.checked)}
                  />
                  {t("portal.consent.paperless.label")}
                </label>
              </FormField>
            </div>
            <ConsequenceBox
              heading={t("portal.apply.whatThisWillDo")}
              bullets={[
                t("portal.apply.sendsYourApplication"),
                t("portal.apply.recordsHowWeSend"),
                // CR-191-BRC10 — Q8 of the portal's eight: before money moves
                // the applicant reads the figure and that it is not refunded.
                ...(fee !== null
                  ? [
                      t("portal.apply.feeChargedNow", { amount: fee.display ?? "" }),
                      t("portal.apply.feeNotRefunded"),
                    ]
                  : [t("portal.apply.nothingCharged")]),
                t("portal.apply.weAnswerWithinTwo"),
              ]}
            />
            {cardWrong ? (
              <Announced tone="error" className="text-base font-semibold text-danger-700" data-card-wrong="">
                {t("portal.quickPay.cardLooksWrong")}
              </Announced>
            ) : null}
            {refusal !== null ? (
              // ⚠ **R-10, LITERALLY — *"the thing they can do about it must be
              // on that same screen, next to the message"*.** The sentence now
              // names the step the server refused on, and where that step is
              // one of the two on this route the way back to it is the control
              // directly beneath it rather than a `Change` link beside some
              // other block. Before this, five words named nothing and the
              // step the server had sent was thrown away.
              <div className="flex flex-col items-start gap-2" data-send-error="">
                <Announced tone="error" className="text-base font-semibold text-danger-700">
                  {refusal.sentence}
                </Announced>
                {refusal.goTo !== null ? (
                  <Button
                    variant="secondary"
                    size="sm"
                    data-action="fix-step"
                    onClick={() => props.onChangeStep(refusal.goTo as ApplyStep)}
                  >
                    {t("portal.apply.openStep", { step: refusal.label })}
                  </Button>
                ) : null}
              </div>
            ) : null}
            {/* `DEF-CWP-9164` — Back on the LEFT, Send on the RIGHT. */}
            <WizardFooter
              back={
                // r10 rule 1: inside a stepper the footer's `← Back` means
                // PREVIOUS STEP and nothing else. A header `←` names where it
                // EXITS to; the two never share a label.
                <Button variant="secondary" size="default" data-action="back" onClick={props.onBack}>
                  {t("portal.apply.backStep")}
                </Button>
              }
              forward={
                // ⚠ **HELD UNTIL THE APPLICATION IS COMPLETE — `DEF-CWP-4877`.**
                // A commit that can only be refused is not a commit. `held` is
                // what steps 2 and 3 own; step 1's two keys are deliberately
                // not in it (see `heldOnCommit`).
                <Button
                  variant="primary"
                  size="default"
                  data-action="send"
                  data-pay-amount={fee?.display ?? undefined}
                  disabled={props.sending || props.held !== null || cardHeld}
                  title={heldTitle(t, props.held)}
                  aria-describedby={props.held !== null ? HELD_REASON_ID : undefined}
                  onClick={send}
                >
                  {fee !== null
                    ? t("portal.apply.payAndSubmit", { amount: fee.display ?? "" })
                    : t("portal.apply.sendMyApplication")}
                </Button>
              }
            />
            <HeldReason held={props.held} />
            {props.held === null && fee !== null && cardAvailable && !feeCardIsComplete(card) ? (
              <p className="text-base text-neutral-600" role="status" data-card-held="">
                {t("portal.quickPay.needCard")}
              </p>
            ) : null}
          </Card>
        }
        rail={
          <>
            <Panel as="aside" title={t("portal.apply.savedAsYouGo")}>{t("portal.apply.savedAsYouGoBody")}</Panel>
            <Panel as="aside">{t("portal.apply.documentsComeAfter")}</Panel>
          </>
        }
      />
    </div>
  );
}

function Sent(props: {
  reference: string | null;
  consentRecorded: boolean;
  /** CR-191-BRC10 — the fee taken by card, or null when nothing was charged. */
  feePaid?: MoneyCell | null;
}) {
  const { t } = useTranslation();
  return (
    <div data-screen="CWP-009" data-sent="true">
      <PageHeader
        kicker={t("portal.apply.kicker")}
        title={t("portal.apply.sentTitle")}
        rollup={t("portal.apply.sentSubtitle")}
      />
      <Card testId="application-sent">
        <KVList
          rows={[
            {
              key: "reference",
              label: t("portal.apply.yourReference"),
              // ⚠ THE FIRST AND ONLY IDENTIFIER THIS JOURNEY SHOWS ANYBODY —
              // allocated at submit, never at draft (US-CWP-013 §2). It is a
              // human reference, not a database id, so B14 rule 31 is met.
              value: <span data-reference="">{props.reference ?? "—"}</span>,
            },
          ]}
        />
        <ConsequenceBox
          heading={t("portal.apply.whatHappensNow")}
          bullets={[
            t("portal.apply.weAnswerWithinTwo"),
            props.feePaid
              ? t("portal.apply.feeReceived", { amount: props.feePaid.display ?? "" })
              : t("portal.apply.nothingCharged"),
            props.consentRecorded
              ? t("portal.apply.consentRecorded")
              : t("portal.apply.consentNotTaken"),
          ]}
        />
      </Card>
    </div>
  );
}

/**
 * Which step to open on when somebody comes BACK to a link they left — the
 * whole of wireframe s19 in one function.
 *
 * ⚠ **IT DECIDES NAVIGATION AND NOTHING ELSE.** `applications.py`'s
 * `missing_before_submit` is the authority on whether an application may be
 * sent, and it still refuses on the server; this only chooses which of the
 * three steps to put in front of a returning person. Two rules disagreeing
 * about *may this be sent* would be a second arithmetic over the same
 * question — this one is asked a different question, and its wrong answer
 * costs a click rather than a refusal.
 *
 * The drawing is emphatic about why it matters: *"It opens on the fields, not
 * on a checklist. The first version of this screen listed what was still
 * needed and made the clerk press Carry on to reach it. That is one more tap
 * between a person holding their licence and the thing that takes a photo of
 * it."*
 */
function firstUnfinishedStep(draft: ApplicationDraft | null): ApplyStep {
  if (draft === null) return "when";
  // ⚠ **READ OFF `unfinished()` AND NOT HAND-WRITTEN — `DEF-CWP-4877`.** This
  // function used to carry its own copy of the same seven conditions, which is
  // precisely the second arithmetic the docstring above warns about. It answers
  // a different QUESTION from the gates (where do I put this person, rather
  // than may this be sent) and it must answer it off the same list.
  const missing = unfinished(draft, valuesOf(draft), draft.applicant_kind ?? "person", mailingFromDraft(draft));
  // ⊕ `DEF-CWP-4930` — a draft with no services is one whose address we do not
  // hold (a held address stamps its own on step 1), and those are TICKED on
  // step 2, so that is where a returning applicant is put back.
  if (missing.includes("services")) return "when";
  if (missing.some((key) => STEP_OF[key] === 2)) return "when";
  if (missing.some((key) => STEP_OF[key] === 3)) return "about";
  return "review";
}

/**
 * The three steps that live on this route, and the form they share.
 *
 * ⚠ **IT IS A COMPONENT RATHER THAN A BLOCK INSIDE THE BODY SO THAT THE FORM
 * IS SEEDED FROM A DRAFT THAT HAS ALREADY ARRIVED.** `useApplicationForm`
 * reads the draft in a `useState` initialiser — mount it while the read is
 * still in flight and every box is seeded empty and stays empty, which is the
 * *"closing the tab loses nothing"* promise broken in the one case it exists
 * for. The body renders this only after `query.isPending` is false.
 */
function ApplicationSteps(props: {
  draft: ApplicationDraft | null;
  availability: Availability | null;
  /** `CR-158-BRC10` — the draft's token and the client the documents block
   *  uploads through, and how it hands the server's answer back. */
  token: string;
  client: ApiClient;
  onDraft: (draft: ApplicationDraft) => void;
  resumed: boolean;
  saving: boolean;
  saveError: unknown;
  onSave: (patch: Patch) => void;
  onSend: (paperless: boolean, payment: ApplicationFeePayment | null) => void;
  sending: boolean;
  sendError: unknown;
}) {
  const { t } = useTranslation();
  const showDate = usePortalDate();
  const form = useApplicationForm(props.draft, props.onSave);
  const [step, setStep] = useState<ApplyStep>(() =>
    props.resumed ? firstUnfinishedStep(props.draft) : "when",
  );

  /**
   * What is still missing — ONE list, and the three gates below slice it.
   * See `unfinished()` for why it reads the live form rather than the draft.
   */
  const missing = unfinished(props.draft, form.values, form.kind, form.mailing, form.custom, form.coApplicant);

  /* ══ THE UTILITY'S OWN QUESTIONS — `CR-161-BRC10` W7 ═════════════════════
   *
   * One `ApplicationCustomFields` per record type, each mounted on the step
   * where the thing it is about is asked: the PROPERTY's on step 2 beside the
   * start date, the applicant's own (customer, then account) on step 3 beside
   * their name. Each draws nothing when the utility asks nothing.
   *
   * ⚠ **EVERY BLANK REQUIRED BOX IS MARKED ONCE SEND HAS BEEN REFUSED ON ITS
   * STEP.** Until then a box is marked when it is LEFT blank, so an applicant
   * is not greeted by a screen of errors before typing anything. */
  const refusedStep = stepFromRefusal(props.sendError);
  const answerErrors = questionErrors(t, props.saveError);
  const headings: Record<PortalCustomEntity, string> = {
    premises: t("portal.apply.questions.property"),
    customers: t("portal.apply.questions.you"),
    accounts: t("portal.apply.questions.account"),
  };
  /** Everything a block needs but its record type and screen, which are
   *  written LITERALLY on each tag below so the W1 pairing test can read them
   *  (`tests/test_cr161_w1_custom_field_settings.py`). */
  const shared = (entity: PortalCustomEntity) => ({
    fields: props.draft?.custom_fields?.[entity] ?? [],
    values: form.custom[entity] ?? {},
    heading: headings[entity],
    showRequired: refusedStep === (entity === "premises" ? "property_questions" : "your_questions"),
    errors: answerErrors,
    onChange: (key: string, value: unknown) => form.setAnswer(entity, key, value),
    onCommit: (key: string, value: unknown) => form.commitAnswer(entity, key, value),
  });
  const propertyQuestions = (
    <ApplicationCustomFields entity="premises" screen="PORTAL_NEW_SERVICE" {...shared("premises")} />
  );
  const yourQuestions = (
    <>
      <ApplicationCustomFields entity="customers" screen="PORTAL_NEW_SERVICE" {...shared("customers")} />
      <ApplicationCustomFields entity="accounts" screen="PORTAL_NEW_SERVICE" {...shared("accounts")} />
    </>
  );

  /* ══ THE PAGE HEAD — `DEF-CWP-4876` ═══════════════════════════════════════
   *
   * ⚠ **STEPS 2, 3 AND 4 DREW NO HEADING OF ANY KIND.** Measured in a browser
   * at 1280 and at 390 on 2026-09-11: `h1` count **0**, `.page-header` nodes
   * **0**. The page went navigation → step bar → an eleven-pixel section
   * title, so there was no `<h1>` in the document at all and — the half that
   * actually costs an applicant something — **after step 1 nothing on screen
   * said which address was being applied for.** The two branches that DID
   * carry a head, *resumed* and *sent*, are the two an applicant reaches
   * least.
   *
   * ⚠ **THE RESUMED HEAD IS KEPT AS IT IS, AND THAT IS THE DRAWING'S CALL
   * RATHER THAN AN EXCEPTION.** Wireframe s19 heads the returning applicant
   * *"Picked up where you left off. You started this on Sep 6 for 1841 Quarry
   * Hill Ct…"* and names the step BELOW, in the section title — *"ABOUT YOU —
   * THE PART YOU DID NOT FINISH"*. So the step identity is on screen either
   * way, and both heads carry the address, which is what was missing.
   *
   * ⚠ **AND THE STEP NUMBER IN THE SUB-LINE IS THE SAME NUMBER THE STEP BAR
   * DRAWS.** Two places saying where somebody is can disagree; they cannot
   * here, because both read `stepNumber` below. Wireframes s16, s17 and s18
   * each draw the title, the sub-line and the bar together.
   *
   * ⚠ **AND IT DOES NOT SAY WHEN THEY STARTED, OR HOW LONG IT IS HELD.** The
   * drawing puts both on the page — *"started Sep 6"*, *"held until Oct 6"*,
   * *"we hold an unfinished request for 30 days"*. `GET
   * portal/public/applications/{token}` serves neither a created date nor an
   * expiry, and there is no retention rule written for a draft anywhere in
   * this module. Inventing *30 days* on a customer's screen would be a promise
   * nothing in the product keeps. The head says what is TRUE — this is the one
   * you started, and here is where you stopped. */
  const stepNumber = step === "review" ? 4 : step === "about" ? 3 : 2;
  /**
   * ⚠ **THE QUERY STRING IS THE FALLBACK, AND ON STEP 2 IT IS THE ONLY SOURCE
   * THERE IS — measured in a browser on 2026-09-11, at 390 and at 1280.**
   * A first visit reaches step 2 with NO DRAFT: step 1 hands the address over
   * in the address bar (`?address=1408+Bluestem+Ln`) and the first draft is
   * not written until *Continue* saves one. So reading the address from the
   * draft alone left the head saying *"Step 2 of 4"* and naming no address —
   * on the exact screen `DEF-CWP-4876` was filed about, whose complaint was
   * that **after step 1 nothing says which address is being applied for**.
   * Steps 3 and 4 always have a draft by then and never showed it.
   * This is the same fallback the page component already applies when it
   * seeds the form; the two now agree instead of differing by one step.
   */
  const [headSearch] = useSearchParams();
  // ⊕ `DEF-CWP-9817` — the served US-format line once a draft exists; before
  // the first save lands, the matched premises' line from the availability
  // read, and only then the street as typed.
  const address =
    props.draft?.service_address ??
    props.draft?.address_as_given ??
    (props.availability?.matched ? props.availability.address : null) ??
    headSearch.get("address") ??
    "";
  /** The step's own drawn title. `whenHeading` and `aboutYou` STOPPED being
   *  SMALL-CAPS section titles on 2026-09-11 and became these — see below. */
  const stepTitleKey =
    step === "review"
      ? "portal.apply.checkTitle"
      : step === "about"
        ? "portal.apply.aboutYou"
        : "portal.apply.whenHeading";
  const head = props.resumed ? (
    <PageHeader
      kicker={t("portal.apply.kicker")}
      title={t("portal.apply.resumedTitle")}
      rollup={
        address
          ? t("portal.apply.resumedFor", { address })
          : t("portal.apply.resumedSubtitle")
      }
    />
  ) : (
    <PageHeader
      kicker={t("portal.apply.kicker")}
      title={t(stepTitleKey)}
      // B14 rule 32 — ONE sentence, and the address is the half of it an
      // applicant cannot get anywhere else on these three screens.
      rollup={
        address
          ? t("portal.apply.stepLine", { address, step: stepNumber })
          : t("portal.apply.stepLineNoAddress", { step: stepNumber })
      }
    />
  );

  /**
   * The step's name INSIDE the card — drawn only when the head is not already
   * saying it.
   *
   * ⚠ **BECAUSE THE TWO USED TO BE THE SAME SENTENCE, TWICE.** Step 2 opened
   * `SectionTitle` *"WHEN WOULD YOU LIKE IT ON?"* and step 3 opened
   * *"ABOUT YOU"*; giving those screens the page head the drawing asks for
   * would have put the identical words directly above them — B14 rule 32's
   * own failure case (*"too much content"*). Wireframes s16 and s17 draw the
   * sentence ONCE, at the top, with no section title above the first field, so
   * the two catalogue values moved from small caps to sentence case and became
   * the titles. **s19 is the case that still needs one:** a returning
   * applicant is headed *"Picked up where you left off"* and the drawing names
   * the step below it — *"ABOUT YOU — THE PART YOU DID NOT FINISH"*.
   */
  const stepTitle = props.resumed ? <SectionTitle>{t(stepTitleKey)}</SectionTitle> : null;

  /** *Already done — nothing to redo*, the small panel beside the unfinished
   *  step. Only what the draft actually holds, each with the way back to it. */
  const doneRows = props.resumed
    ? [
        props.draft?.address_as_given
          ? { key: "address", label: t("portal.apply.address"), value: serviceLine(props.draft), step: null }
          : null,
        props.draft?.requested_start
          ? {
              key: "start",
              label: t("portal.apply.startOn"),
              value: showDate(props.draft.requested_start),
              step: "when" as ApplyStep,
            }
          : null,
      ].filter((row): row is { key: string; label: string; value: string; step: ApplyStep | null } => row !== null)
    : [];

  const rail =
    doneRows.length > 0 ? (
      <Panel as="aside" title={t("portal.apply.alreadyDone")}>
        <KVList
          rows={doneRows.map((row) => ({
            key: row.key,
            label: row.label,
            value:
              row.step === null ? (
                row.value
              ) : (
                <span className="flex flex-wrap items-baseline gap-2">
                  <span>{row.value}</span>
                  <Button
                    variant="secondary"
                    size="sm"
                    data-change={row.key}
                    onClick={() => setStep(row.step as ApplyStep)}
                  >
                    {t("portal.apply.change")}
                  </Button>
                </span>
              ),
          }))}
        />
      </Panel>
    ) : null;

  /* ⚠ **THE HEAD GOES DOWN INTO THE STEP, NOT ABOVE IT.** It used to render
     here, OUTSIDE the `data-screen` mark, so a rendered check selecting on
     `[data-screen="CWP-047"]` could not see the heading at all — the same
     split `components/states.tsx` records as `DEF-CWP-4926`. */
  return step === "review" && props.draft !== null ? (
    <CheckAndSend
      draft={props.draft}
      availability={props.availability}
      documents={<DocumentChecklist token={props.token} draft={props.draft} />}
      head={head}
      held={heldOnCommit(missing)}
      onBack={() => setStep("about")}
      onChangeStep={setStep}
      onSend={props.onSend}
      sending={props.sending}
      error={props.sendError}
    />
  ) : step === "about" ? (
    <AboutYou
      form={form}
      draft={props.draft}
      availability={props.availability}
      documents={
        props.draft !== null ? (
          <ApplicationDocuments
            token={props.token}
            draft={props.draft}
            onDraft={props.onDraft}
            client={props.client}
          />
        ) : null
      }
      head={head}
      stepTitle={stepTitle}
      questions={yourQuestions}
      held={heldOnStep(missing, 3)}
      rail={rail}
      saving={props.saving}
      error={props.saveError}
      onSave={props.onSave}
      onBack={() => setStep("when")}
      onContinue={() => setStep("review")}
    />
  ) : (
    <WhenStep
      form={form}
      draft={props.draft}
      availability={props.availability}
      head={head}
      stepTitle={stepTitle}
      questions={propertyQuestions}
      held={heldOnWhen(missing, props.availability)}
      rail={rail}
      saving={props.saving}
      error={props.saveError}
      onSave={props.onSave}
      onContinue={() => setStep("about")}
    />
  );
}

export function ApplyForServiceBody(props: { client?: ApiClient }) {
  const client = props.client ?? api;
  const params = useParams();

  const [search] = useSearchParams();
  const token = params.draft ?? "";
  const { query, save, queueSave, settling } = useDraft(token, client);
  const queryClient = useQueryClient();
  const [sent, setSent] = useState<{
    reference: string | null;
    consent: boolean;
    feePaid: MoneyCell | null;
  } | null>(null);
  // True from the click until the submit actually leaves — see onSend below.
  const [holding, setHolding] = useState(false);
  // ⚠ **BOTH OF THESE ARE REFS BECAUSE AN EFFECT THAT FIRES A MUTATION MUST
  // BE ABLE TO SAY IT ALREADY DID — `DEF-CWP-3708`, found by the walkthrough.**
  // `save` is a new object on every render, so the effect below runs on every
  // render; a mutation started there re-renders (`isPending`), which runs the
  // effect again, which starts another. Between the first call and the server's
  // answer the condition is still true, so it is not one extra request — it is
  // **a request storm that exhausts the sixty-a-minute guest throttle in about
  // a second**, and the saves the applicant actually made are then refused with
  // `429`. The browser found it; nothing else could, because every unit test
  // renders once.
  const seeded = useRef(false);
  const servicesStamped = useRef(false);

  const draft = query.data ?? null;
  // ⊕ `DEF-CWP-9817` — the PARTS, from the draft once it exists and from the
  // link step 1 built until then. A draft from before step 1 asked the parts
  // has a street and no town or ZIP, and is matched as it always was.
  const address = draft?.address_as_given ?? search.get("address") ?? "";
  const city = draft !== null ? (draft.address_city_as_given ?? "") : (search.get("city") ?? "");
  const zip = draft !== null ? (draft.address_postal_code_as_given ?? "") : (search.get("zip") ?? "");
  const unit = search.get("unit") ?? "";
  // ⊕ `CR-200-BRC10` F3 — the apartment the draft keeps (else the link's),
  // asked of the availability read so the services and fees are THAT unit's.
  const unitForCheck = draft !== null ? (draft.address_unit_as_given ?? "") : unit;

  /**
   * ⚠ **WHETHER THE SERVER ALREADY HELD THIS DRAFT, DECIDED ON THE FIRST
   * SETTLED READ AND NEVER AGAIN.** It is what separates wireframe s19 —
   * *"picked up where you left off"* — from a first visit, and it has to be
   * captured before the seed below creates the row, because a second later
   * every application looks resumed.
   */
  const resumed = useRef<boolean | null>(null);
  if (resumed.current === null && !query.isPending) {
    resumed.current = query.data !== undefined;
  }

  const availabilityQuery = useQuery({
    queryKey: ["portal", "availability", address, city, zip, unitForCheck],
    queryFn: () =>
      getAvailability({ street: address, city, postalCode: zip, unit: unitForCheck }, client),
    enabled: address.length > 0,
  });

  // The address arrives on the link from CWP-008 and is written into the draft
  // once — after that the DRAFT is the truth, so a reopened link shows what was
  // typed rather than what a stale query string says.
  useEffect(() => {
    if (query.isPending) return;
    const services = (availabilityQuery.data?.rows ?? [])
      .filter((row) => row.available)
      .map((row) => row.service_code);
    if (!seeded.current && draft === null && address) {
      seeded.current = true;
      // ⚠ The unit rides on the same link and is written in the same breath —
      // `address_unit_as_given` has been an accepted draft field since the
      // draft existed and no screen ever filled it in (`CR-085` task (c),
      // wireframe s15: *"Is there a unit or apartment number?"*). It is
      // omitted when the applicant left it empty rather than written as null
      // over something a later save might set.
      queueSave({
        address_as_given: address,
        // DEF-CWP-9817 — the town and ZIP, into their own `_as_given` boxes.
        ...(city ? { address_city_as_given: city } : {}),
        ...(zip ? { address_postal_code_as_given: zip } : {}),
        service_codes: services,
        ...(unit ? { address_unit_as_given: unit } : {}),
      });
      return;
    }
    // ⚠ **THE SERVICES ARE STAMPED WHEN THEY ARRIVE, NOT ONLY WHEN THE DRAFT IS
    // CREATED.** The availability read is a second round trip and often lands
    // AFTER the first save, so the draft was written with an empty list and the
    // submit was then refused for an incomplete step — a refusal about
    // something the applicant had already told us. Found by the walkthrough
    // (`DEF-CWP-3705`).
    if (
      !servicesStamped.current &&
      draft !== null &&
      !draft.submitted &&
      draft.service_codes.length === 0 &&
      services.length > 0
    ) {
      servicesStamped.current = true;
      queueSave({ service_codes: services });
    }
  }, [address, city, zip, unit, draft, query.isPending, queueSave, availabilityQuery.data]);

  const submit = useMutation({
    mutationFn: (sending: { paperless: boolean; payment: ApplicationFeePayment | null }) =>
      submitApplication(token, sending.paperless, client, sending.payment),
    onSuccess: (result) =>
      setSent({
        reference: result.reference,
        consent: result.consent_recorded,
        feePaid: result.fee_paid ?? null,
      }),
  });

  if (query.isPending) {
    return <LoadingSkeleton variant="card" />;
  }
  if (sent !== null) {
    return (
      <Sent reference={sent.reference} consentRecorded={sent.consent} feePaid={sent.feePaid} />
    );
  }
  return (
    <ApplicationSteps
      draft={draft}
      availability={availabilityQuery.data ?? null}
      token={token}
      client={client}
      onDraft={(next) => queryClient.setQueryData(["portal", "draft", token], next)}
      resumed={resumed.current === true}
      saving={save.isPending}
      saveError={save.isError ? save.error : null}
      onSave={queueSave}
      /* ⚠ **SEND WAITS FOR THE LAST SAVE — DEF-CWP-3710.** A save queued
         on the way out of *About you* can still be on the wire when a fast
         hand reaches *Send*; the submit would then be judged against a draft
         one field short and refused for a step the applicant had finished.
         One tick per attempt, and the button stays in its sending state
         while it waits, so nothing on screen claims more than is true. */
      onSend={(paperless, payment) => {
        setHolding(true);
        const go = () => {
          if (settling()) {
            window.setTimeout(go, 120);
            return;
          }
          setHolding(false);
          submit.mutate({ paperless, payment });
        };
        go();
      }}
      sending={submit.isPending || holding}
      sendError={submit.isError ? submit.error : null}
    />
  );
}

export function ApplyForServicePage(props: { client?: ApiClient }) {
  return (
    <GuestPage client={props.client}>
      <ApplyForServiceBody client={props.client} />
    </GuestPage>
  );
}
