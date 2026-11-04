// ── Trace ──────────────────────────────────────────────
// Story:    US-CWP-017 (find my account, CWP-016) · US-CWP-018 (prove it is
//           you, CWP-017) · US-CWP-019 (choose a password, CWP-018).
//           ⚠ **THIS LINE READ `US-CWP-016 · 017 · 018` UNTIL 2026-09-05 AND
//           WAS ONE LOW THROUGHOUT WAVE E (`DEF-CWP-3862`)** — the wave read
//           each story id off the SCREEN number beside it. `EP-CWP-05` is
//           the register: `US-CWP-016` is the front door (`CWP-015`).
//           **Both ids are named on each pair from now on**, because two
//           series running one apart make every wrong pairing look right.
// Rules:    BR-CWP-030 (three facts, all printed on the paper bill) ·
//           BR-CWP-032 (NOTHING about the account is shown on CWP-016) ·
//           BR-CWP-033/034 (the masked contact; *ring the office* when there is
//           none) · BR-CWP-035 (ten minutes, and an expired code is its own
//           answer with a resend) · BR-CWP-036 (three tries) · BR-CWP-037 (the
//           helper line states the TENANT's own minimum) · BR-CWP-039 (the
//           consequence panel, and this is the first screen in the flow that
//           may show a balance) · 08-screen-layouts.md CWP-016 (T2) · CWP-017
//           (T7) · CWP-018 (T4 50/50) · B14 rule 33 · rule 21 · rule 36
// Tests:    src/portal/signin/Enrol.dom.test.tsx (13 cases)
//           ⚠ **THIS LINE NAMED `Enrol.test.tsx` FROM WAVE E UNTIL
//           2026-09-05 AND THAT FILE NEVER EXISTED (`DEF-CWP-3863`)** —
//           hard-won law 1, in the header of the file that holds the
//           portal's whole one-time-code path. No gate reads a `Tests:`
//           line and checks the file is there.
// Impacts:  src/portal/api/portalClient.ts
// ───────────────────────────────────────────────────────
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/Button";
import { WorkingButton } from "@/components/StateFrame";
import { Announced, FormScope, usePortalForm } from "../components/a11y";
import {
  Card,
  CommitButton,
  ConsequenceBox,
  DialInput,
  DisabledCommit,
  FormField,
  KVList,
  RadioList,
  SectionTitle,
  Stepper,
  TextInput,
  TwoCol,
  WhereNext,
  usePortalPath,
} from "../components/primitives";
import {
  findAccount,
  getConsequences,
  setPassword,
  verifyCode,
  type EnrolConsequences,
} from "../api/portalClient";

/** The three steps, as the URL strip reads them: *step n of 3*. */
const STEP_KEYS = ["find", "prove", "choose"] as const;

/**
 * `CWP-016` · `CWP-017` · `CWP-018` — one wizard, three drawings, one route.
 *
 * ⚠ **THREE SCREENS AND ONE ADDRESS, and that is the journey rather than a
 * shortcut.** Each step carries its own `data-screen`, which is what the
 * walkthrough and `G82`'s register both read; giving each its own path would
 * let somebody bookmark *choose a password* for an account they have not
 * proved they hold. The guard is not the URL either — `enrol/set-password`
 * refuses without a consumed code (`US-CWP-019` TC-4) — but there is no reason
 * to draw a door that the server then has to close.
 */
export function EnrolView() {
  const { t } = useTranslation();
  const path = usePortalPath();
  const navigate = useNavigate();

  const [step, setStep] = useState(1);
  const [working, setWorking] = useState(false);
  const [refused, setRefused] = useState<string | null>(null);
  // F-02 / F-03 / F-04: one scope for whichever step is on screen.
  const form = usePortalForm();

  const [accountNumber, setAccountNumber] = useState("");
  const [postcode, setPostcode] = useState("");
  const [lastName, setLastName] = useState("");

  const [accountRef, setAccountRef] = useState<string | null>(null);
  const [sentTo, setSentTo] = useState<string | null>(null);
  const [code, setCode] = useState("");

  const [consequences, setConsequences] = useState<EnrolConsequences | null>(null);
  const [email, setEmail] = useState("");
  const [chosen, setChosen] = useState("");
  const [again, setAgain] = useState("");
  const [otpChannel, setOtpChannel] = useState("sms");

  async function doFind() {
    setWorking(true);
    setRefused(null);
    try {
      const found = await findAccount({
        account_number: accountNumber,
        postcode,
        last_name: lastName,
      });
      // ⚠ EVERY BRANCH BELOW READS A KEY THE SERVER SENT AND NEVER A FIELD
      // ABOUT THE ACCOUNT — there is no name, no balance and no address on
      // this response and the type says so (BR-CWP-032).
      if (!found.matched || !found.account_ref) {
        setRefused(t(`portal.enrol.reason.${found.reason ?? "not_matched"}`));
        return;
      }
      setAccountRef(found.account_ref);
      setSentTo(found.sent_to ?? null);
      setStep(2);
    } finally {
      setWorking(false);
    }
  }

  async function doVerify() {
    if (!accountRef) return;
    setWorking(true);
    setRefused(null);
    try {
      const verdict = await verifyCode({ account_ref: accountRef, code });
      if (verdict.result !== "ok") {
        // `expired` is its OWN sentence with a resend beside it, never an
        // error page (BR-CWP-035).
        setRefused(t(`portal.enrol.code.${verdict.result}`));
        return;
      }
      setConsequences(await getConsequences({ account_ref: accountRef }));
      setStep(3);
    } finally {
      setWorking(false);
    }
  }

  async function doResend() {
    // A resend re-runs the match, which is what invalidates the live code on
    // the server side (`credentials.issue_code` supersedes in the same
    // transaction). The screen does not hold a second door for it.
    await doFind();
    setStep(2);
  }

  async function doCreate() {
    if (!accountRef) return;
    setWorking(true);
    setRefused(null);
    try {
      const result = await setPassword({
        account_ref: accountRef,
        email,
        password: chosen,
        otp_channel: otpChannel,
      });
      if (!result.ok) {
        setRefused(
          (result.failures ?? [])
            .map((failure) =>
              t(`portal.enrol.password.${failure}`, { count: result.min_length ?? 8 }),
            )
            .join(" "),
        );
        return;
      }
      navigate(path("/home"));
    } finally {
      setWorking(false);
    }
  }

  const steps = STEP_KEYS.map((key) => t(`portal.enrol.step.${key}`));
  const bothTyped = chosen.length > 0 && chosen === again;
  // ⚠ **`DEF-CWP-4858` — all three, trimmed.** `BR-CWP-030` names the three
  // facts this step matches on and all three are printed on the paper bill, so
  // a blank one is never a near-miss the server could work with: it is an
  // attempt that can only fail, against a three-attempt lock.
  const readyToFind =
    accountNumber.trim() !== "" && postcode.trim() !== "" && lastName.trim() !== "";

  return (
    <div data-enrol-wizard="">
      <Stepper steps={steps} current={step} />

      {step === 1 ? (
        <TwoCol
          main={
            <Card testId="enrol-find">
              <div data-screen="CWP-016">
                <p className="text-xs font-bold uppercase tracking-wide text-neutral-900">
                  {t("portal.enrol.kicker")}
                </p>
                <h1 className="text-h1 leading-tight text-neutral-900">
                  {t("portal.enrol.findTitle")}
                </h1>
                <p className="mt-1 text-body leading-relaxed text-neutral-600">
                  {t("portal.enrol.findLead")}
                </p>
                <div className="mt-4 flex flex-col gap-5">
                  <FormScope form={form}>
                  <FormField id="enrol-account" label={t("portal.enrol.accountNumber")} required>
                    <TextInput
                      id="enrol-account"
                      value={accountNumber}
                      placeholder={t("portal.enrol.accountNumberExample")}
                      onChange={setAccountNumber}
                    />
                  </FormField>
                  <FormField
                    id="enrol-postcode"
                    label={t("portal.enrol.postcode")}
                    helper={t("portal.postcodeHelper")}
                    required
                  >
                    <TextInput id="enrol-postcode" value={postcode} onChange={setPostcode} />
                  </FormField>
                  <FormField id="enrol-lastname" label={t("portal.enrol.lastName")} required>
                    <TextInput id="enrol-lastname" value={lastName} onChange={setLastName} />
                  </FormField>
                  </FormScope>
                  {refused ? (
                    <Announced tone="error" className="text-base font-semibold text-danger-700" data-enrol-refused="">
                      {refused}
                    </Announced>
                  ) : null}
                  {/* ⚠ **THE COMMIT IS REFUSED UNTIL ALL THREE ARE TYPED, AND
                      IT SAYS SO — `DEF-CWP-4858`, `CR-085` step 2.** This was a
                      bare `WorkingButton` with no guard at all: measured live at
                      390 and 1280, *Continue →* was PRESSABLE with account
                      number, ZIP code and last name all blank, so an empty
                      submission reached `findAccount` and spent one of the
                      three tries this screen's own rail warns about
                      (`BR-CWP-036`, and the rail says *"Three wrong tries locks
                      this form for fifteen minutes."*).

                      ⚠ **IT WAS THE ONLY ONE OF THE FIVE GUEST FORMS WITHOUT A
                      GUARD, AND THE ONE WITH THE HIGHEST COST OF PRESSING IT.**
                      `/report` and `/track` both compose `CommitButton` with a
                      `ready` and a reason; `/sign-in` and `/forgot-password`
                      are correctly ungated because each answers one sentence
                      either way and spends nothing. This screen spends a try.

                      `CommitButton` is the kit's shape for exactly this — a
                      disabled control that carries WHY (`BR-CWP-056`, r10's
                      *never a dead control with no reason*) — so the refusal
                      is the same one word-for-word as the other two forms
                      rather than a fourth opinion. */}
                  <div className="flex items-center gap-3">
                    <CommitButton
                      label={t("portal.enrol.continue")}
                      working={working}
                      ready={readyToFind}
                      reason={t("portal.enrol.notReady")}
                      onClick={() => void doFind()}
                    />
                  </div>
                </div>
              </div>
            </Card>
          }
          rail={
            <Card testId="enrol-nobill">
              <SectionTitle>{t("portal.enrol.noBillTitle")}</SectionTitle>
              <p className="mt-2 text-body leading-relaxed text-neutral-600">
                {t("portal.enrol.noBillBody")}
              </p>
              <p className="mt-3 text-base font-semibold text-neutral-800" data-enrol-tries="">
                {t("portal.enrol.threeTries")}
              </p>
              {/*
                ⚠ **THE ESCAPE HATCH, AND `s4` IS EXPLICIT ABOUT WHY IT IS ON
                THIS SCREEN:** *"Quick-pay is offered on the same screen.
                Someone who cannot complete this must not leave without having
                paid."* The account number is the barrier this whole form is
                built around, and a person who cannot find it had nowhere to go
                from here at all — the rail told them to ring the office and
                offered no other way to settle the bill in their hand.

                ⚠ **IT IS A DOOR, NOT A SECOND PRIMARY.** The kit's
                `WhereNext` draws it at the foot of the panel in the outlined
                tier, so *Continue →* stays the only filled control on the
                screen, and its label is the key `/sign-in` already uses for
                the same destination.
              */}
              <WhereNext
                mark="enrol"
                doors={[{ key: "quick_pay", label: t("portal.signIn.doorQuickPay"), to: "/pay" }]}
              />
            </Card>
          }
        />
      ) : null}

      {step === 2 ? (
        <Card testId="enrol-prove">
          <div data-screen="CWP-017">
            <p className="text-xs font-bold uppercase tracking-wide text-neutral-900">
              {t("portal.enrol.foundKicker")}
            </p>
            <h1 className="text-h1 leading-tight text-neutral-900">
              {t("portal.enrol.proveTitle")}
            </h1>
            {/* ⚠ THE MASKED CONTACT IS THE SERVER'S STRING, RENDERED AS IT
                ARRIVED. Masking here as well would be a second implementation
                of BR-CWP-033 and the two would drift. */}
            <p className="mt-1 text-body leading-relaxed text-neutral-600">
              {t("portal.enrol.sentTo")}{" "}
              <strong data-enrol-sentto="">{sentTo ?? ""}</strong>
              {". "}
              {t("portal.enrol.tenMinutes")}
            </p>
            <div className="mt-4 flex max-w-[240px] flex-col gap-3">
              <FormScope form={form}>
              <FormField id="enrol-code" label={t("portal.enrol.sixDigit")} required>
                <DialInput id="enrol-code" value={code} onChange={setCode} maxLength={6} />
              </FormField>
              </FormScope>
            </div>
            {refused ? (
              <Announced tone="error" className="mt-2 text-base font-semibold text-danger-700" data-enrol-refused="">
                {refused}
              </Announced>
            ) : null}
            <div className="mt-3 flex items-center gap-3">
              <WorkingButton working={working} onClick={form.guard(doVerify)}>
                {t("portal.enrol.verify")}
              </WorkingButton>
              <Button variant="secondary" size="sm" onClick={doResend}>
                {t("portal.enrol.resend")}
              </Button>
            </div>
            <p className="mt-3 text-base text-neutral-600" data-enrol-wrongnumber="">
              {t("portal.enrol.wrongNumber")}
            </p>
          </div>
        </Card>
      ) : null}

      {step === 3 && consequences ? (
        <div className="grid grid-cols-2 gap-4 max-md:grid-cols-1" data-screen="CWP-018">
          <Card testId="enrol-choose">
            <h1 className="text-h1 leading-tight text-neutral-900">
              {t("portal.enrol.chooseTitle")}
            </h1>
            <div className="mt-4 flex flex-col gap-5">
              <FormScope form={form}>
              <FormField id="enrol-email" label={t("portal.signIn.email")} required>
                <TextInput id="enrol-email" type="email" value={email} onChange={setEmail} />
              </FormField>
              <FormField
                id="enrol-new"
                label={t("portal.enrol.newPassword")}
                required
                // ⚠ THE TENANT'S OWN MINIMUM, READ FROM THE SERVER AND NEVER
                // HARDCODED (BR-CWP-037). Eight characters are refused on a
                // tenant whose `pw_min_length` is twelve, and this line is
                // what tells the person that before they type.
                helper={t("portal.enrol.minLength", { count: consequences.policy_min_length })}
              >
                <TextInput id="enrol-new" type="password" value={chosen} onChange={setChosen} />
              </FormField>
              <FormField id="enrol-again" label={t("portal.enrol.typeAgain")} required>
                <TextInput id="enrol-again" type="password" value={again} onChange={setAgain} />
              </FormField>
              </FormScope>
              <SectionTitle>{t("portal.enrol.howCodes")}</SectionTitle>
              <RadioList
                name="otp-channel"
                value={otpChannel}
                onChange={setOtpChannel}
                options={[
                  { value: "sms", label: t("portal.enrol.bySms") },
                  { value: "email", label: t("portal.enrol.byEmail") },
                ]}
              />
              {refused ? (
                <Announced tone="error" className="text-base font-semibold text-danger-700" data-enrol-refused="">
                  {refused}
                </Announced>
              ) : null}
              <div className="flex items-center gap-3">
                {bothTyped ? (
                  <WorkingButton working={working} onClick={form.guard(doCreate)}>
                    {t("portal.enrol.createLogin")}
                  </WorkingButton>
                ) : (
                  // F-22 (`DEF-CWP-10551`): the reason is text, tied to the button.
                  <DisabledCommit
                    label={t("portal.enrol.createLogin")}
                    reason={t("portal.enrol.typeItTwice")}
                  />
                )}
              </div>
            </div>
          </Card>

          <Card testId="enrol-consequences">
            <SectionTitle>{t("portal.enrol.whatYouGet")}</SectionTitle>
            <div className="mt-3">
              <KVList
                rows={[
                  {
                    key: "account",
                    label: t("portal.enrol.account"),
                    value: consequences.account_no,
                  },
                  {
                    key: "address",
                    label: t("portal.enrol.serviceAddress"),
                    value: consequences.service_address ?? "—",
                  },
                  {
                    key: "services",
                    label: t("portal.enrol.services"),
                    value: consequences.services
                      .map((code) => t(`service.${code}`, { defaultValue: code }))
                      .join(" · "),
                  },
                  {
                    key: "balance",
                    label: t("portal.enrol.balanceToday"),
                    // ⚠ FOUR DECIMALS ON THE WIRE, TWO ON THE SCREEN (hard
                    // rule 2). The rounding is the display's and the precision
                    // is the store's; `Number` here would be a float on a
                    // money path, so the string is trimmed instead.
                    value: (
                      <span data-enrol-balance="">
                        {formatMoney(consequences.balance, consequences.currency)}
                      </span>
                    ),
                  },
                ]}
              />
            </div>
            <div className="mt-4">
              <ConsequenceBox
                heading={t("portal.enrol.whenYouFinish")}
                bullets={consequences.cannot.map((key) => t(`portal.enrol.cannot.${key}`))}
              />
            </div>
          </Card>
        </div>
      ) : null}
    </div>
  );
}

/**
 * `142.1800` → `$142.18`.
 *
 * ⚠ **STRING ARITHMETIC ON PURPOSE — no `Number`, no `parseFloat`.** Hard rule
 * 2 says money is never a float, and that is as true in a browser as in the
 * database: `Number("142.1800")` is a double, and the day a figure is summed
 * on screen it is a rounding error a customer can see. Four decimals arrive,
 * two are shown, and the trailing two are cut rather than rounded because the
 * SERVER has already rounded at finalisation (B4's rule) — rounding twice is
 * how a total stops matching its rows.
 */
export function formatMoney(amount: string, currency: string | null): string {
  return withCurrency(amount, currency, 2);
}

/**
 * `5.2000` → `$5.20`, `0.0425` → `$0.0425` — a unit PRICE: up to **four**
 * places, at least two (PO 2026-10-02; narrows OQ-620(a)'s zeros-kept form).
 *
 * ⚠ **A RATE IS NOT MONEY AND IS NOT A QUANTITY** (`OQ-620(a)`, PO 2026-08-27:
 * *"A rate is not money and not a quantity - 4 decimal places"*). Handing a
 * rate to `formatMoney` prints `$0.01` for `0.0089` — a figure that cannot
 * reproduce the line it priced.
 *
 * ⚠ **AND IT IS THE SAME IMPLEMENTATION AS `formatMoney`, DELIBERATELY.** This
 * is not a second money formatter; it is the one below with a different
 * decimal count. Two independent copies of the symbol rule and the digit
 * grouping is how a product starts printing `USD 5.20` on one screen and
 * `$5.20` on the next (law 5).
 */
export function formatRate(amount: string, currency: string | null): string {
  // PO ruling 2026-10-02 — *"Show unit prices with up to 4 decimals and keep
  // every total at 2."* Four places at most, two at least: `0.0425` →
  // `$0.0425`, `5.2000` → `$5.20`, `0.1420` → `$0.142`. The trim is of ZEROS
  // only, after the cut to four, so no digit is ever rounded away here.
  return trimPriceZeros(withCurrency(amount, currency, 4));
}

/** Drop trailing zeros after the second decimal: `$5.2000` → `$5.20`. */
function trimPriceZeros(text: string): string {
  return text.replace(/(\.\d\d\d*?)0+$/, "$1");
}

/** The one implementation. `places` is the ONLY thing that varies. */
function withCurrency(amount: string, currency: string | null, places: number): string {
  const [whole = "0", decimals = ""] = String(amount ?? "0").split(".");
  const fraction = (decimals + "0".repeat(places)).slice(0, places);
  const symbol = currency === "USD" || currency === null ? "$" : `${currency} `;
  const negative = whole.startsWith("-");
  const digits = negative ? whole.slice(1) : whole;
  const grouped = digits.replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  return `${negative ? "-" : ""}${symbol}${grouped}.${fraction}`;
}
