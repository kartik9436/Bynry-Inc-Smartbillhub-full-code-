// ── Trace ──────────────────────────────────────────────
// Change:   `CR-136-BRC07` `P2.6` — §03 frame **3·3a Start**,
//           `05-prototype/06 Payments Page Blueprint.pdf` p054–p055, read as
//           an IMAGE at scale 2.0 (B14 rule 42).
// Screens:  3·3a · opened from `PAY-04` Counters
// Rules:    B14 rule 10 (a required field carries the asterisk on its LABEL) ·
//           rule 11 (a consequence preview before a commit that writes money) ·
//           rule 33 (a LABEL ≤ 3 words · a CONSEQUENCE ≤ 6 words per sentence,
//           at most two) · rule 38 (where the drawing and our UI rules
//           disagree about how a FORM is built, the UI rules win — the footer
//           and the label → input → helper order are ours; the two fields are
//           the drawing's) · rule 21 · rule 43 · `CR-136-BRC07` §3.1
// Tests:    src/features/payments/counterScreens.dom.test.tsx
// ───────────────────────────────────────────────────────
// *"I am opening the counter for my shift."*
//
// ══════════════════════════════════════════════════════════════════════════
// ONE ACT, NOT TWO — AND IT IS A RULING, NOT AN IMPLEMENTATION DETAIL
// ══════════════════════════════════════════════════════════════════════════
// p054 ②, and the ruling it carries is dated 2026-09-21: *"When a counter is
// started a batch should be automatically started with it."* The blueprint
// spells out what that buys: *"the batch exists from the moment the till
// opens, so **every payment carries its id from the first one**, and closing
// only seals it and records the count. That removes a window in which a
// counter payment would have had no batch."*
//
// So this form has ONE commit and there is no separate *start batch* control
// anywhere in the product. The `CHECK` box says so on screen in eight words
// over two sentences, which is what B14 rule 11 asks for and what rule 33
// caps.
//
// ══════════════════════════════════════════════════════════════════════════
// ⚠ THREE FIELDS SINCE 2026-09-23 — p055 DRAWS TWO AND A PO RULING ADDED THE
//   THIRD (`DEF-PAY-6314`)
// ══════════════════════════════════════════════════════════════════════════
// This block read *"TWO FIELDS"* and quoted p055's own *Fields* row, *"Two.
// Service centre (required) · Opening float (required)"*, as the authority for
// it. **That row still says two and the form now draws three**, so the
// divergence is written here rather than left for the next lane to read as a
// defect and "fix" back.
//
// The server has required `opened_at` since `P2.1` — `BR-TEN-043` and gate G6
// forbid a wall clock anywhere under `apps/payments/`, so the moment a till
// opened is an INPUT or it is nothing. Neither the drawing nor this form had a
// field for it, and the result was `DEF-PAY-6314`: every *Start counter* on the
// deployed build refused with *"Give the opening time."* over a form holding
// nothing to type it into.
//
// **PO ruling 2026-09-23, verbatim:** *"show date and time pciker and deult
// should be as per date time format set by utility and timezone - show the
// detault time"*. So it is a DATE AND TIME picker, PREFILLED with the current
// moment, rendered in the utility's own format and its own timezone — not the
// browser's and not ISO. A drawing is the agreement (B14 rule 41) and a PO
// ruling outranks it; that is the supersession, dated, in the place a lane
// building this screen actually reads.
//
// ══════════════════════════════════════════════════════════════════════════
// ⚠ AND `Counter setup`'s AUTO-CLOSE IS STILL NOT ONE OF THEM
// ══════════════════════════════════════════════════════════════════════════
// `CR-136-BRC07` §3.1, PO ruling 2026-09-23: *"(a) Your ruling stands — no
// auto-close. A System Admin closes it. Dana cannot work Tuesday until someone
// is free to do that"*. The blueprint's `Counter setup` setting ships with the
// float alone and **no auto-close toggle is built**, here or on Settings — a
// setting nothing honours is hard-won law 1.
import { useEffect, useMemo, useState } from "react";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { z } from "zod";

import { api, formErrorEnvelope, isApiError } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { getCounterCentres, startCounter } from "@/api/counterEndpoints";
import type { CounterDetail } from "@/api/counterEndpoints";
import { ConsequenceBox } from "@/components/ConsequenceBox";
import {
  DateTimeField,
  FormModal,
  SelectField,
  TextField,
  nowInZone,
  sameDayBounds,
} from "@/components/FormModal";
import type { FormSubmitOutcome } from "@/components/FormModal";
import { useRegional } from "@/features/metering/meteringShared";
import type { RegionalProps } from "@/features/metering/meteringShared";

import { countersQueryKey } from "./counterQueries";

/** The reference list 3·3a ① reuses. Cached under its own key so opening the
 *  dialog twice in a shift does not re-fetch what cannot have changed. */
export const serviceCentresQueryKey = () => ["counters", "service-centres"] as const;

/**
 * All three fields are required (3·3a ①, p055's *Fields* row and the PO ruling
 * above). The float is a DECIMAL STRING and stays one all the way to the wire
 * — CLAUDE.md hard rule 2, *"never float/cents"* — so the schema validates its
 * SHAPE rather than parsing it into a number that would lose the fourth
 * decimal.
 *
 * ⚠ **THE KEYS HERE ARE THE FORM'S FIELD IDS, NOT THE WIRE'S.** `FormModal`
 * maps a zod path onto the input with that `id`, so `service_centre` is the
 * name of a control a clerk looks at; `service_centre_id` is what the server
 * reads and it is named once, at the `startCounter` call below. Keeping the
 * control's id off the wire is what `DEF-PAY-6314` was: the two were assumed
 * to be one name, and they are not.
 *
 * `opened_at` is a tenant WALL CLOCK — `YYYY-MM-DDTHH:mm`, optionally with the
 * seconds some browsers append — and never an instant. See `DateTimeField`.
 */
export const startCounterSchema = z.object({
  service_centre: z.string().min(1),
  opening_float: z.string().regex(/^\d+(\.\d{1,4})?$/),
  opened_at: z.string().regex(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2}(\.\d+)?)?$/),
});

export interface StartCounterModalProps extends RegionalProps {
  onClose: () => void;
  /** Where a started till takes the clerk — 3·2, its own address. */
  onStarted: (counter: CounterDetail) => void;
  /** BR-SHL-025: null = this deployment can commit it; a string cannot. */
  writeBlockedReason: string | null;
  client?: ApiClient;
}

export function StartCounterModal(props: StartCounterModalProps) {
  const { t } = useTranslation();
  const client = props.client ?? api;
  const queryClient = useQueryClient();
  const [serviceCentre, setServiceCentre] = useState("");
  const [openingFloat, setOpeningFloat] = useState("");
  const [openedAt, setOpenedAt] = useState("");
  // IS-8 / BR-SHL-023 — an explicit prop wins, the shell's published tenant
  // settings are the fallback, and there is NO seed default in the shipped
  // bundle: a screen nobody told which utility it is fails loudly rather than
  // drawing a plausible wrong time (hard-won law 3).
  const { timeZone, dateFormat } = useRegional(props);
  // The proposal is computed ONCE. Re-deriving it every render would move the
  // default under a clerk who is looking at it, and `DateTimeField` commits it
  // into state on mount anyway (BR-PAY-033).
  const openedAtPrefill = useMemo(() => nowInZone(timeZone), [timeZone]);
  // `BR-PAY-1191` — backward within today and no further. Drawn here and
  // REFUSED at the endpoint; a bound only a form applies is a suggestion.
  const openedAtBounds = useMemo(() => sameDayBounds(timeZone), [timeZone]);

  const centresQuery = useQuery({
    queryKey: serviceCentresQueryKey(),
    // DEF-PAY-10768 — payments' own read: a Billing Clerk may not read the
    // Settings list (A4), and the clerk is who opens a till.
    queryFn: () => getCounterCentres(client),
  });

  const start = useMutation({
    mutationFn: () =>
      startCounter(client, {
        // ⚠ **`service_centre_id` IS THE SERVER'S KEY AND THE VALUE IS A SLUG.**
        // Not a contradiction: `counters._service_centre()` resolves by slug
        // first and falls back to a uuid pk. This posted `service_centre` until
        // `DEF-PAY-6314` and was refused with `BR-PAY-1160` every time.
        service_centre_id: serviceCentre,
        opening_float: openingFloat,
        // A naive tenant wall clock, on purpose — `_moment` anchors it in the
        // utility's own zone (BR-TEN-081). An offset computed here would be the
        // same derivation done twice, with DST in it.
        opened_at: openedAt,
      }),
  });

  // ⚠ **A CENTRE A CUSTOMER CANNOT SEE IS STILL A COUNTER A CLERK SITS AT.**
  // `is_shown_to_customers` is a PORTAL state — the depot stays in the list —
  // so it is deliberately not filtered here. Filtering on it would hide the
  // back-office window from the person working at it.
  const centreOptions = (centresQuery.data?.centres ?? []).map((centre) => ({
    value: centre.slug,
    label: centre.name,
  }));

  // ⚠ **`DEF-PAY-10731` (L1-11) — THE SELECT MUST NEVER SHOW A CENTRE THE FORM
  // DOES NOT HOLD.** State starts at `""`, and a `<select>` with no empty
  // option draws its FIRST option while React holds nothing — so the tester
  // saw *Main office*, pressed Start, and was told *"This is required."*. Two
  // halves: a `Choose…` placeholder (below) so `""` has an option to draw, and
  // when the utility has exactly ONE centre it is chosen for the clerk, since
  // there is nothing to choose between.
  const onlyCentre = centreOptions.length === 1 ? centreOptions[0].value : null;
  useEffect(() => {
    if (onlyCentre !== null && serviceCentre === "") {
      setServiceCentre(onlyCentre);
    }
  }, [onlyCentre, serviceCentre]);

  async function submit(): Promise<FormSubmitOutcome> {
    try {
      const counter = await start.mutateAsync();
      void queryClient.invalidateQueries({ queryKey: countersQueryKey() });
      props.onStarted(counter);
      return { ok: true };
    } catch (error) {
      // BR-SHL-020 — the server's refusal is SHOWN as a sentence. A till act
      // that failed silently is the worst possible outcome on a money path.
      if (isApiError(error)) {
        return { ok: false, error: formErrorEnvelope(error) };
      }
      return { ok: false, error: { code: "", message_key: "api.error.unexpected" } };
    }
  }

  return (
    <FormModal
      // p054 draws the eyebrow `NEW COUNTER` over the heading `Start your
      // counter`. Three words and three words (B14 rule 33's label cap).
      kicker={t("payments.counter.start.kicker")}
      title={t("payments.counter.start.title")}
      schema={startCounterSchema}
      values={{
        service_centre: serviceCentre,
        opening_float: openingFloat,
        opened_at: openedAt,
      }}
      onSubmit={submit}
      onClose={props.onClose}
      submitLabel={t("payments.counter.start.commit")}
      // ⚠ NOT the danger tier. Opening a till writes a session and a batch and
      // moves no money; B14 rule 6's tier is for a DESTRUCTIVE commit, and
      // p055's own *Primary action* row draws this as the standard one.
      commitBlocked={props.writeBlockedReason ?? undefined}
      cancelLabel={t("payments.counter.start.cancel")}
    >
      <SelectField
        id="service_centre"
        label={t("payments.counter.start.centre")}
        required
        value={serviceCentre}
        onChange={setServiceCentre}
        options={centreOptions}
        placeholder={t("payments.counter.start.centreChoose")}
        help={t("payments.counter.start.centreHelp")}
      />
      {/* ⚠ **NO `USD` ADORNMENT INSIDE THE BOX, WHERE p054 DRAWS ONE.** B14
          rule 38: where the drawing and our UI rules disagree about how a form
          is BUILT, the rules win. `TextField numeric` is the one money input
          in this product — the Record-payment amount is the same control — and
          the kit has no suffix slot. Growing one for a single screen would put
          a second money field in the product, which rule 20's reasoning and
          hard-won law 5 both refuse. The divergence is REPORTED. */}
      <TextField
        id="opening_float"
        label={t("payments.counter.start.float")}
        required
        numeric
        value={openingFloat}
        onChange={setOpeningFloat}
        help={t("payments.counter.start.floatHelp")}
      />
      {/* ⚠ **THE THIRD FIELD, AND IT IS APPENDED RATHER THAN INSERTED.** p055
          draws the centre and the float in that order and the PO ruling added
          a moment; putting it last leaves the two drawn fields exactly where
          the drawing puts them. It carries no help line: rule 33 puts
          RATIONALE at ZERO WORDS ON SCREEN, and *why the time is editable* is
          rationale. The default sitting in the box says what it needs to. */}
      <DateTimeField
        id="opened_at"
        label={t("payments.counter.start.openedAt")}
        required
        value={openedAt}
        onChange={setOpenedAt}
        prefill={openedAtPrefill}
        dateFormat={dateFormat}
        min={openedAtBounds.min}
        max={openedAtBounds.max}
      />
      {/* B14 rule 11 — 3·3a ②'s `CHECK` box, which is the one place the
          one-act ruling is said to a clerk. Two sentences, four words and five
          (rule 33's consequence cap is six per sentence, at most two). */}
      <ConsequenceBox
        tone="check"
        title={t("payments.counter.start.consequenceTitle")}
        body={t("payments.counter.start.consequenceBody")}
      />
    </FormModal>
  );
}

export default StartCounterModal;

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-136-BRC07 §3.1 · §4 row `P2.6` · blueprint p054–p055 as images at 2.0
// generated: 2026-09-23 by LANE P2-SCREENS
// checklist: A✔ B=n/a(`POST /counters` is `P2.1`, LANE P2-API's) C✔ D=n/a E✔ F✔ G✔ H=n/a
// gates: tsc --noEmit · vitest src/features/payments/counterScreens.dom.test.tsx · G31 · routeBUtilities.test.ts
// exceptions: E3 `POST /counters` is NOT SERVED at this commit — the form renders and its refusal reaches the clerk as a sentence · E3 the blueprint's `Counter setup` auto-close toggle is deliberately NOT built (§3.1)
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
