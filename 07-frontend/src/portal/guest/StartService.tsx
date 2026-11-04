// ── Trace ──────────────────────────────────────────────
// Story:    US-CWP-012 (EP-CWP-04) — can I get service here. Screens: CWP-008
//           · wireframes/CWP-008.png
// Rules:    08-screen-layouts.md CWP-008 (T3 under GuestFrame: PageHead kicker
//           START SERVICE · main Card [FormField Address · Check → · rule ·
//           WE SERVE THIS ADDRESS · MiniTable with the Electric row greyed ·
//           ConsequenceBox IF YOU APPLY · Apply for service →] · rail [Panel
//           ALREADY SERVED? · Panel.Info an unknown address is not a refusal])
//           · BR-CWP-021 (never a person) · B14 rule 21 (Tailwind utilities;
//           `portal/` is on route-b-migrated.txt) · rule 31 (no id on screen)
//           · rule 32 (one sentence per section) · hard rule 2 (the screen
//           renders `display`, never `amount`)
//           · CR-085 task (c), wireframe s15: this is STEP 1 OF 4 and the
//           screen never said so, and it asks the unit — PO ruling: *"please
//           show all 4 screens - address, when , about you, check"*
// Defects:  DEF-CWP-9817 — step 1 asked the address as ONE free-text box plus a
//           unit, where the blueprint (p31, *15 Start service · 1 Address*,
//           read as an IMAGE — B14 rule 42) draws Street address · Town · ZIP
//           code · *Is there a unit or apartment number?*. The check could not
//           use town and ZIP, and every later step printed what was typed. It
//           now asks the parts and the server matches all three through the
//           staff side's own matcher (`BR-CUS-1091`). *Or use my location* is
//           drawn and is NOT built (no geolocation read exists on the portal).
//           DEF-CWP-4875 — *IF YOU APPLY* printed `— deposit on your first
//           bill.`, a sentence beginning with an em dash, whenever the server
//           correctly answered that there was no deposit to quote. See
//           `ifYouApplyBullets` below.
// Tests:    src/portal/guest/StartService.test.tsx ·
//           src/portal/guest/CheckAndSend.dom.test.tsx (the four steps) ·
//           10-scripts/render-checks/cr068-c-start-service.mjs
// ───────────────────────────────────────────────────────
import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate, useParams } from "react-router-dom";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { PageHeader } from "@/components/PageHeader";
import { Button } from "@/components/Button";
import { refusalText } from "@/api/refusalText";
import type { Translator } from "@/api/refusalText";

import { Panel } from "@/components/Panel";
import { US_ZIP } from "@/components/UsAddressFields";

import { getAvailability } from "../api/guestClient";
import type { AddressParts, AddressSuggestion, Availability, MoneyCell } from "../api/guestClient";
import { AddressSuggestInput, ApartmentChoice, NOT_LISTED } from "../components/AddressSuggest";
import { Announced } from "../components/a11y";
import {
  ButtonReason,
  Card,
  ConsequenceBox,
  FormField,
  MiniTable,
  SectionTitle,
  StatusChip,
  Stepper,
  TextInput,
  TwoCol,
  TwoUp,
  fieldErrorId,
} from "../components/primitives";
import { newDraftToken } from "../draftToken";

import { GuestPage } from "./GuestPage";

/**
 * A money cell as a person reads it.
 *
 * ⚠ **THE SCREEN NEVER FORMATS `amount` ITSELF.** The server sends the stored
 * four-decimal figure AND the two-decimal sentence (hard rule 2, and
 * `apps/portal/money.py` says why both travel); a screen that rounded the
 * first would be a second rounding rule, and two rounding rules is how a total
 * stops matching its own lines. The other two kinds carry no `display` on
 * purpose — `Included` and the em dash are words, and words come out of the
 * catalogue (B14 rule 35).
 */
function Money(props: { cell: MoneyCell }) {
  const { t } = useTranslation();
  if (props.cell.kind === "amount") {
    return <span data-money={props.cell.amount ?? ""}>{props.cell.display}</span>;
  }
  if (props.cell.kind === "included") {
    return <span data-money="included">{t("portal.availability.included")}</span>;
  }
  return (
    <span data-money="none" aria-label={t("portal.availability.nothingToQuote")}>
      —
    </span>
  );
}

/**
 * The *IF YOU APPLY* bullets — and **a money cell with nothing to quote is a
 * bullet that is ABSENT, never a sentence starting with an em dash**
 * (`DEF-CWP-4875`).
 *
 * ⚠ **WHAT SHIPPED, AND WHY EVERY CHECK PASSED OVER IT.** The two money
 * bullets were written `t("…onFirstBill", { amount: cell.display ?? "—" })`,
 * and `display` is `null` for `kind: "included"` and `kind: "none"` **on
 * purpose** — `money.py` says so in as many words: *"`display` is filled in
 * ONLY for a currency figure … for the screen to name from its own words"*.
 * So on any address where the plan sets no deposit the server correctly
 * answered *there is nothing to quote* and the screen printed
 *
 *     — deposit on your first bill.
 *
 * an English sentence beginning with an em dash, on the first two screens of
 * the move-in journey, on a utility being onboarded. The `?? "—"` is doing
 * exactly what it says; the fault is that a table CELL may be a dash and a
 * SENTENCE may not. `Money` above is the cell case and is right as it stands.
 *
 * ⚠ **THE DRAWING NAMES THIS STATE RATHER THAN LEAVING IT TO BE INFERRED.**
 * Wireframe s16's `NO ESTIMATE AVAILABLE`: *"The panel is absent, not shown
 * with a dash."* So the LINE goes, and the panel stays when it still has
 * something true to say — `$90.00 before we start` and `about 3 working days`
 * are facts whether or not a deposit was ever priced. A panel deleted whole
 * would take two true sentences with it.
 *
 * ⚠ **IT IS EXPORTED AND `ApplyForService.tsx` IMPORTS IT.** Wireframes s15
 * and s16 draw the same three sentences off the same `if_you_apply` read, so a
 * second copy of this rule is a second place the dash can come back — and the
 * defect was filed against BOTH screens for exactly that reason. The keys are
 * `portal.startService.*` because this screen is where they were written.
 */
export function ifYouApplyBullets(
  t: Translator,
  apply: NonNullable<Availability["if_you_apply"]>,
): string[] {
  const bullets: string[] = [];
  if (apply.before_we_start.kind === "amount" && apply.before_we_start.display) {
    bullets.push(
      t("portal.startService.beforeWeStart", { amount: apply.before_we_start.display }),
    );
  }
  if (apply.on_first_bill.kind === "amount" && apply.on_first_bill.display) {
    bullets.push(t("portal.startService.onFirstBill", { amount: apply.on_first_bill.display }));
  }
  bullets.push(t("portal.startService.howLong", { days: apply.working_days }));
  return bullets;
}

export function StartServiceBody(props: { client?: ApiClient }) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const params = useParams();
  const client = props.client ?? api;
  // ⊕ `DEF-CWP-9817` — the address in the PARTS the blueprint draws (p31):
  // Street address · Town · ZIP code. No state: the drawing asks none, because
  // a utility serves its own state (the server writes it from the profile).
  const [address, setAddress] = useState("");
  const [town, setTown] = useState("");
  const [zip, setZip] = useState("");
  const [zipLeft, setZipLeft] = useState(false);
  /**
   * ⚠ **THE UNIT IS A LABEL ON A PREMISES, NOT A SECOND ADDRESS** (CLAUDE.md
   * hard rule 8, and the wireframe says the same in its own Rules line: *"A
   * unit refines a premises by label, not by a second address."*). It is asked
   * HERE because the drawing asks it here — on the step that establishes where
   * — and because service is per unit, so a multi-unit building that is not
   * asked produces an application a clerk has to phone about.
   *
   * ⊕ **AND SINCE `CR-200-BRC10` IT IS PART OF THE QUESTION (PO 2A).** It
   * read *"IT IS NOT PART OF THE AVAILABILITY QUESTION"* — the building was
   * judged whole, so Apt B empty beside an occupied Apt A read *move-in*
   * (`DEF-CWP-10680`). The check now sends it as `unit`: at a building with
   * several units the server names the one it means (a LABEL, never an id) and
   * judges THAT unit; one it does not hold matches nothing at the address and
   * is *a person will look at it*, never a refusal. It still rides on the link
   * to step 2 as `address_unit_as_given`, so the draft and the request carry it.
   */
  const [unit, setUnit] = useState("");
  const [answer, setAnswer] = useState<Availability | null>(null);
  /** ⊕ `CR-200-BRC10` — *Which apartment?*: a label, *Mine isn't listed*, or
   *  not answered yet (null). */
  const [apartment, setApartment] = useState<string | null>(null);

  const check = useMutation({
    mutationFn: (parts: AddressParts) => getAvailability(parts, client),
    onSuccess: (data) => {
      setAnswer(data);
      setApartment(data.unit ?? null);
    },
  });

  const checked = answer !== null;
  //: ⊕ `CR-200-BRC10` (PO 2A) — a building with several units asks which
  //: one before it answers; *Mine isn't listed* is *a person will look at it*.
  const labels = answer?.units ?? [];
  const asksApartment = answer?.matched === true && labels.length > 1;
  const notListed = asksApartment && apartment === NOT_LISTED;
  //: Answered for a building only once the server named THAT unit.
  const unitAnswered = !asksApartment || (answer?.unit != null && !notListed);
  const matched = answer?.matched === true && unitAnswered;
  const personWillLook = checked && (answer?.matched !== true || notListed);
  //: Five digits or ZIP+4 — the server's `US_ZIP_RE` and the kit's `US_ZIP`.
  const zipOk = US_ZIP.test(zip.trim());
  //: Four characters of street, because *"1 A"* is not an address — and a
  //: town and a well-formed ZIP, because those are what make the match exact
  //: rather than a guess on the street alone (`DEF-CWP-9817`).
  const tooShort = address.trim().length < 4 || town.trim() === "" || !zipOk;
  const parts: AddressParts = {
    street: address.trim(),
    city: town.trim(),
    postalCode: zip.trim(),
    ...(unit.trim() ? { unit: unit.trim() } : {}),
  };
  /** ⊕ `CR-200-BRC10` (PO 1A) — a pick fills street, town and ZIP and runs
   *  the check at once. */
  const onPick = (row: AddressSuggestion) => {
    setAddress(row.street);
    setTown(row.city);
    setZip(row.postal_code ?? "");
    setAnswer(null);
    check.mutate({
      street: row.street,
      city: row.city,
      postalCode: row.postal_code ?? "",
      ...(unit.trim() ? { unit: unit.trim() } : {}),
    });
  };
  /** The apartment picked: its label is the unit, and the check runs again
   *  for THAT unit (PO 2A — judged for the unit, not the building). */
  const onApartment = (value: string) => {
    setApartment(value);
    if (value === NOT_LISTED) {
      // A label picked a moment ago is not what they now say; their own typed
      // apartment (if any) rides on to step 2 as said.
      if (labels.includes(unit.trim())) setUnit("");
      return;
    }
    setUnit(value);
    check.mutate({ ...parts, unit: value });
  };
  //: The ZIP's own refusal, said once the box is LEFT with something in it —
  //: never while it is still being typed (five keystrokes are not a mistake).
  const zipError = zipLeft && zip.trim() !== "" && !zipOk ? t("portal.application.mailingZipFormat") : null;

  /**
   * What step 2 needs to know, as a query string.
   *
   * ⚠ **THE UNIT IS OMITTED WHEN IT IS EMPTY RATHER THAN SENT AS `""`.** The
   * draft's cleaner turns an empty string into `null` anyway, but a query
   * string that carries `&unit=` on every application is a parameter that
   * looks answered and is not — and the seed effect on step 2 reads presence,
   * not truthiness.
   *
   * ⚠ **THE ADDRESS ITSELF IS BUILT AT THE `navigate` CALL AND NOT IN HERE,
   * AND THAT IS NOT A STYLE CHOICE.** `G100` walks the portal's doors by
   * reading `navigate(`…`)` in the source; a helper that returns the whole
   * path hides the destination from it, and the gate went from PASS to
   * *"nothing in the product points at CWP-047"* the moment this function
   * held the literal. It is a fair complaint about a human reader too — a
   * grep for `start-service` should find the door.
   */
  const nextStepQuery = () => {
    const unitParam = unit.trim();
    // ⚠ **THE TYPED PARTS TRAVEL, NEVER THE MATCHED LINE (`DEF-CWP-9817`).**
    // This handed step 2 `answer.address` — the premises' composed line — on a
    // match, which then became `address_as_given`: the applicant was recorded
    // as having SAID the register's spelling (`BR-CUS-070` keeps what they
    // said). The draft re-matches the parts itself and serves the premises'
    // address to show (`service_address`), so nothing is lost.
    const query = new URLSearchParams({ address: parts.street, city: parts.city, zip: parts.postalCode });
    if (unitParam) query.set("unit", unitParam);
    return query.toString();
  };

  return (
    <div data-screen="CWP-008">
      <PageHeader
        kicker={t("portal.startService.kicker")}
        title={t("portal.startService.title")}
        rollup={t("portal.startService.subtitle")}
      />
      {/* ⚠ **THIS IS STEP ONE OF FOUR AND THE SCREEN NEVER SAID SO**
          (`CR-085` task (c), the signed-off wireframe s15: *"Step 1 of 4"*
          above the four named steps). The applicant met a bare form, pressed a
          button labelled *Apply for service* and landed on a stepper that
          announced they were on step 2 — the first they had heard of steps at
          all. PO ruling: *"please show all 4 screens - address, when , about
          you, check"*. The same four labels are used here and on the three
          steps that follow, out of one set of catalogue keys, so the journey
          cannot describe itself two ways. */}
      <Stepper
        current={1}
        steps={[
          t("portal.apply.step1"),
          t("portal.apply.step2"),
          t("portal.apply.step3"),
          t("portal.apply.step4"),
        ]}
      />
      <TwoCol
        main={
          <Card testId="start-service">
            {/* The drawn heading over the four boxes (p31). */}
            <SectionTitle>{t("portal.startService.whereHeading")}</SectionTitle>
            <FormField
              id="availability-address"
              label={t("portal.startService.addressLabel")}
              required
              error={check.isError ? refusalText(t, check.error) : null}
            >
              {/* ⊕ `CR-200-BRC10` F2 — suggestions from the fourth character. */}
              <AddressSuggestInput
                id="availability-address"
                value={address}
                onChange={setAddress}
                onPick={onPick}
                client={client}
                required
                autoComplete="address-line1"
                describedBy={fieldErrorId("availability-address")}
                placeholder={t("portal.startService.addressPlaceholder")}
              />
            </FormField>
            {/* Town and ZIP side by side, as drawn at 1280; `TwoUp` stacks
                them below `md`, where the phone frame draws them in one row of
                two — B14 rule 44 lets the kit decide the construction. */}
            <TwoUp>
              <FormField id="availability-town" label={t("portal.startService.townLabel")} required>
                <TextInput
                  id="availability-town"
                  value={town}
                  onChange={setTown}
                  required
                  autoComplete="address-level2"
                />
              </FormField>
              <FormField id="availability-zip" label={t("portal.startService.zipLabel")} required error={zipError}>
                <span onBlur={() => setZipLeft(true)}>
                  <TextInput
                    id="availability-zip"
                    value={zip}
                    onChange={setZip}
                    required
                    inputMode="numeric"
                    autoComplete="postal-code"
                    invalid={zipError !== null}
                    describedBy={fieldErrorId("availability-zip")}
                  />
                </span>
              </FormField>
            </TwoUp>
            {/* The wireframe's optional line, and the only other thing step one
                asks. `helper` carries the example, so the box itself is empty
                rather than pre-filled with a value somebody might send. */}
            <FormField
              id="availability-unit"
              label={t("portal.startService.unitLabel")}
              helper={t("portal.startService.unitHelper")}
            >
              <TextInput
                id="availability-unit"
                value={unit}
                onChange={setUnit}
                autoComplete="address-line2"
                placeholder={t("portal.startService.unitPlaceholder")}
              />
            </FormField>
            {/* ⚠ **DISABLED *WITH* THE REASON** — `BR-SHL-025`, the rule
                `CommitButton`'s own docstring states: *"disabled WITH the
                reason, never a vanished control"*. This control was a bare
                `<Button disabled>` with nothing on it at all until 2026-09-05,
                on one of the four working doors the public front page has: a
                greyed *Check →* and no hint that the address box above is what
                it is waiting for. Every other refusal in this portal carries a
                sentence.

                ⚠ **AND IT IS NOT `CommitButton`, WHICH IS WHERE THIS BELONGS,
                FOR ONE REASON WORTH WRITING DOWN.** The kit's commit control
                takes no pass-through props, and `10-scripts/render-checks/
                cr068-c-start-service.mjs` drives this screen with
                `page.click('[data-action="check"]')`. Routing through the kit
                would silently break the only check that opens `CWP-008` in a
                real browser — so the DOM the kit produces (primary tier,
                default size, the reason on `title`) is reproduced here instead,
                and the hook survives. If `CommitButton` ever forwards
                `data-*`, this is a two-line change back.

                ⚠ **PENDING IS NOT A REFUSAL, AND IT GETS ITS OWN WORDS.** A
                control disabled because it is WORKING has nothing to explain;
                saying *"Type an address first"* over an address that is being
                checked would be the shape of lie this fix exists to remove. */}
            <div className="flex flex-col items-start gap-1">
              <Button
                variant="primary"
                size="default"
                data-action="check"
                disabled={tooShort || check.isPending}
                // F-22 (`DEF-CWP-10551`): the reason is also drawn as text below.
                aria-describedby={tooShort && !check.isPending ? "availability-check-reason" : undefined}
                title={
                  check.isPending
                    ? t("states.working")
                    : tooShort
                      ? t("portal.startService.checkHeld", {
                          // B14 rule 33 — four words. The `defaultValue` is the
                          // English the key was written from, so the screen
                          // reads correctly before the catalogue fan-in lands
                          // rather than rendering the key itself (the posture
                          // `workflow/kinds.ts` records, and G18's own
                          // documented exclusion).
                          defaultValue: "Fill in street, town and ZIP.",
                        })
                      : undefined
                }
                onClick={() => check.mutate(parts)}
              >
                {t("portal.startService.check")}
              </Button>
              <ButtonReason
                id="availability-check-reason"
                reason={
                  tooShort && !check.isPending
                    ? t("portal.startService.checkHeld", { defaultValue: "Fill in street, town and ZIP." })
                    : null
                }
              />
            </div>

            {/* ⊕ `DEF-CWP-10693` — the question comes BEFORE its answer, so a
                pick draws the answer underneath rather than pushing the radio
                the person is on below *Continue*. */}
            {asksApartment ? (
              <>
                <hr className="border-neutral-200" />
                <ApartmentChoice labels={labels} value={apartment} onChange={onApartment} />
              </>
            ) : null}

            {checked && matched && answer !== null ? (
              <>
                <hr className="border-neutral-200" />
                {/* F-02 / F-04: the answer's heading takes focus and is heard.
                    ⊕ `DEF-CWP-10693` — EXCEPT after an apartment pick: the
                    arrow keys are still walking the radios, and taking focus
                    stopped them at the first one. It is spoken, and spoken
                    again for each apartment (`signal`). */}
                <Announced tone="status" as="div" focus={!asksApartment} signal={answer.unit ?? null}>
                  <SectionTitle>{t("portal.startService.weServeThis")}</SectionTitle>
                </Announced>
                <MiniTable
                  caption={t("portal.startService.tableCaption")}
                  columns={[
                    { key: "service", label: t("portal.startService.colService") },
                    { key: "available", label: t("portal.startService.colAvailable") },
                    { key: "to_connect", label: t("portal.startService.colToConnect"), align: "right" },
                    { key: "deposit", label: t("portal.startService.colDeposit"), align: "right" },
                  ]}
                  rows={answer.rows.map((row) => ({
                    key: row.service_code,
                    // The wireframe greys the row a service is not carried on.
                    muted: !row.available,
                    cells: {
                      service: row.service_name,
                      available: (
                        <StatusChip tone={row.available ? "success" : "neutral"}>
                          {row.available
                            ? t("portal.availability.yes")
                            : t("portal.availability.notHere")}
                        </StatusChip>
                      ),
                      to_connect: <Money cell={row.to_connect} />,
                      deposit: <Money cell={row.deposit} />,
                    },
                  }))}
                />
                {answer.if_you_apply !== null ? (
                  <ConsequenceBox
                    heading={t("portal.startService.ifYouApply")}
                    bullets={ifYouApplyBullets(t, answer.if_you_apply)}
                  />
                ) : null}
                <div>
                  <Button
                    variant="primary"
                    size="default"
                    data-action="apply"
                    onClick={() =>
                      navigate(
                        `/${params.tenant ?? ""}/portal/start-service/${newDraftToken()}?${nextStepQuery()}`,
                      )
                    }
                  >
                    {t("portal.startService.apply")}
                  </Button>
                </div>
              </>
            ) : null}

            {personWillLook ? (
              <>
                <hr className="border-neutral-200" />
                {/* ⚠ TC-2 — NOT A REFUSAL AND NOT AN EMPTY TABLE. The *Apply*
                    route stays open, because *"they may never become a
                    customer if we refuse them"* (EP-CWP-04 §1). */}
                <Announced
                  tone="status"
                  focus={!notListed}
                  className="text-body leading-relaxed text-neutral-800"
                  data-availability={notListed ? "unit-not-listed" : "unmatched"}
                >
                  {notListed ? t("portal.address.unitNotListed") : t("portal.startService.aPersonWillLook")}
                </Announced>
                <div>
                  <Button
                    variant="primary"
                    size="default"
                    data-action="apply"
                    onClick={() =>
                      navigate(
                        `/${params.tenant ?? ""}/portal/start-service/${newDraftToken()}?${nextStepQuery()}`,
                      )
                    }
                  >
                    {t("portal.startService.apply")}
                  </Button>
                </div>
              </>
            ) : null}
          </Card>
        }
        rail={
          <>
            <Panel as="aside" title={t("portal.startService.alreadyServed")}>
              {t("portal.startService.alreadyServedBody")}
            </Panel>
            {/* ⚠ **A PLAIN PANEL, AND `tone="info"` WAS WRONG HERE — SEEN BY LOOKING,
                which is the only way it could be (hard-won law 6).** This rail note
                used to be a quiet grey box; the B14 rule 36 fold gave it the kit's
                `info` tone, which is a blue border — and on `CWP-005` that put the
                loudest thing on the page around *"someone may have reported this
                already"* while the panel that says *ring this number, a smell of gas
                is an emergency* stayed quiet. r10 draws no blue at all: its device
                for an aside is `.hint`, grey text, and its emphasis is a rule in
                `--color-accent`. A second hue also competes with the tenant's own
                colour, which is the whole point of this wave. `info` still means
                blue-bordered and `CWP-013`'s holiday panel still uses it; a note is
                not an `info`. */}
            <Panel as="aside">{t("portal.startService.unknownIsNotRefusal")}</Panel>
          </>
        }
      />
    </div>
  );
}

export function StartServicePage(props: { client?: ApiClient }) {
  return (
    <GuestPage client={props.client}>
      <StartServiceBody client={props.client} />
    </GuestPage>
  );
}
