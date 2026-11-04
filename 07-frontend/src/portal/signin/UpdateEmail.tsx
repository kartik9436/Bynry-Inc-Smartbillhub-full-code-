// ── Trace ──────────────────────────────────────────────
// Change:   CR-189-BRC10 — `CWP-079`, *Update your registered email*, for a
//           customer who is locked out (PO 2026-10-22).
// Rules:    decision log 2026-10-22 (the CR-189 entries, incl. *"call the
//           office"*) · BR-CWP-030 (three bill facts) · BR-CWP-032 (nothing
//           about the account before it is proved) · BR-CWP-033 (masked
//           contacts, shown as the server sent them) · BR-CWP-034 (dead end,
//           never something weaker) · B14 rules 21, 33, 35, 36, 43
// Tests:    src/portal/signin/UpdateEmail.dom.test.tsx
// Impacts:  src/portal/api/updateEmailClient.ts · routing/portalRoutes.tsx
// ───────────────────────────────────────────────────────
import { useEffect, useRef, useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/Button";
import { WorkingButton } from "@/components/StateFrame";
import type { ApiClient } from "@/api/client";
import { Announced, FormScope, usePortalForm } from "../components/a11y";
import { GuestPage } from "../guest/GuestPage";
import {
  Card,
  CommitButton,
  DialInput,
  FormField,
  KVList,
  RadioList,
  SectionTitle,
  Stepper,
  TextInput,
  WhereNext,
} from "../components/primitives";
import {
  confirmNewEmail,
  findForEmailUpdate,
  sendEmailUpdateCode,
  startNewEmail,
  verifyEmailUpdateCode,
  type ContactOption,
  type OfficeContact,
} from "../api/updateEmailClient";

const STEP_KEYS = ["find", "prove", "email", "done"] as const;

/** A step's heading. It takes focus when it appears, so a screen reader and a
 *  keyboard both land on the new step instead of on a button that has gone
 *  (accessibility questions 1, 2 and 7). */
function StepHeading(props: { children: ReactNode }) {
  const ref = useRef<HTMLHeadingElement>(null);
  useEffect(() => {
    ref.current?.focus();
  }, []);
  return (
    <h1 ref={ref} tabIndex={-1} className="text-h1 leading-tight text-neutral-900 outline-none">
      {props.children}
    </h1>
  );
}

/** The refusal line every step uses, so it reads and announces the same.
 *  F-02 / F-04: announced through the frame's always-present region and
 *  focused (`Announced`) — a `role="alert"` mounted WITH its text is not
 *  reliably read, which is the finding. */
function Refused(props: { text: string | null }) {
  if (!props.text) return null;
  return (
    <Announced tone="error" className="text-base font-semibold text-danger-700" data-update-refused="">
      {props.text}
    </Announced>
  );
}

/**
 * The dead end, by PO ruling of 2026-10-22: *"We can't verify you online. Call
 * the office"*, with the utility's own phone and hours. Both are Settings
 * values off the wire; a missing one is left out, never invented.
 */
function CallTheOffice(props: { office: OfficeContact | null }) {
  const { t } = useTranslation();
  const rows: { key: string; label: string; value: ReactNode }[] = [];
  const phone = props.office?.phone;
  if (phone) {
    rows.push({
      key: "phone",
      label: t("portal.updateEmail.office.phone"),
      // A phone on a phone is a tap, not a number to copy by hand.
      value: (
        <a
          className="text-accent-text no-underline hover:underline"
          href={`tel:${phone.replace(/[^\d+]/g, "")}`}
        >
          {phone}
        </a>
      ),
    });
  }
  const hours = props.office?.hours;
  if (hours) {
    rows.push({ key: "hours", label: t("portal.updateEmail.office.hours"), value: hours });
  }
  return (
    <Card testId="update-email-office">
      <div data-update-office="">
        <StepHeading>{t("portal.updateEmail.office.title")}</StepHeading>
        <p className="mt-1 text-body leading-relaxed text-neutral-600">
          {t("portal.updateEmail.office.cantVerify")}
        </p>
        {rows.length > 0 ? (
          <div className="mt-4">
            <KVList rows={rows} />
          </div>
        ) : null}
        <WhereNext
          mark="update-email-office"
          doors={[{ key: "sign_in", label: t("portal.signIn"), to: "/sign-in" }]}
        />
      </div>
    </Card>
  );
}

/**
 * `CWP-079` — one route, four steps, like `/enrol`. Each step's guard is on
 * the server: a later call with an unproven ref answers *start again*, so the
 * step order here is a convenience and not the security.
 */
export function UpdateEmailView(props: { client?: ApiClient }) {
  const { t } = useTranslation();
  const client = props.client;

  const [step, setStep] = useState(1);
  const [working, setWorking] = useState(false);
  const [refused, setRefused] = useState<string | null>(null);
  const form = usePortalForm();

  const [accountNumber, setAccountNumber] = useState("");
  const [postcode, setPostcode] = useState("");
  const [lastName, setLastName] = useState("");

  const [matchRef, setMatchRef] = useState<string | null>(null);
  const [options, setOptions] = useState<ContactOption[]>([]);
  const [picked, setPicked] = useState<string | null>(null);
  const [office, setOffice] = useState<OfficeContact | null>(null);
  const [deadEnd, setDeadEnd] = useState(false);

  const [proveRef, setProveRef] = useState<string | null>(null);
  const [sentTo, setSentTo] = useState<string | null>(null);
  const [minutes, setMinutes] = useState<number | null>(null);
  const [code, setCode] = useState("");

  const [newEmail, setNewEmail] = useState("");
  const [confirmRef, setConfirmRef] = useState<string | null>(null);
  const [confirmCode, setConfirmCode] = useState("");
  const [next, setNext] = useState<string | null>(null);

  async function run(action: () => Promise<void>) {
    setWorking(true);
    setRefused(null);
    try {
      await action();
    } finally {
      setWorking(false);
    }
  }

  function startAgain() {
    setRefused(t("portal.updateEmail.reason.start_again"));
    setStep(1);
    setMatchRef(null);
    setProveRef(null);
    setConfirmRef(null);
  }

  const doFind = () =>
    run(async () => {
      const found = await findForEmailUpdate(
        { account_number: accountNumber, postcode, last_name: lastName },
        client,
      );
      if (!found.matched) {
        setRefused(t(`portal.updateEmail.reason.${found.reason ?? "not_matched"}`));
        return;
      }
      setOffice(found.office ?? null);
      if (!found.ref || !found.options || found.options.length === 0) {
        setDeadEnd(true);
        return;
      }
      setMatchRef(found.ref);
      setOptions(found.options);
      setPicked(found.options[0]?.key ?? null);
      setStep(2);
    });

  const doSend = () =>
    run(async () => {
      if (!matchRef || !picked) return;
      const sent = await sendEmailUpdateCode({ ref: matchRef, option: picked }, client);
      if (!sent.sent || !sent.ref) {
        startAgain();
        return;
      }
      setProveRef(sent.ref);
      setSentTo(sent.sent_to ?? null);
      setMinutes(sent.expires_in_minutes ?? null);
      setCode("");
    });

  const doVerify = () =>
    run(async () => {
      if (!proveRef) return;
      const verdict = await verifyEmailUpdateCode({ ref: proveRef, code }, client);
      if (verdict.result !== "ok") {
        setRefused(t(`portal.enrol.code.${verdict.result}`));
        return;
      }
      setStep(3);
    });

  const doStart = () =>
    run(async () => {
      if (!proveRef) return;
      const started = await startNewEmail({ ref: proveRef, email: newEmail }, client);
      if (!started.ok || !started.ref) {
        if (started.reason === "start_again") {
          startAgain();
          return;
        }
        setRefused(t(`portal.updateEmail.reason.${started.reason ?? "email_invalid"}`));
        return;
      }
      setConfirmRef(started.ref);
      setSentTo(started.sent_to ?? null);
      setMinutes(started.expires_in_minutes ?? null);
      setConfirmCode("");
    });

  const doConfirm = () =>
    run(async () => {
      if (!confirmRef) return;
      const done = await confirmNewEmail(
        { ref: confirmRef, code: confirmCode, email: newEmail },
        client,
      );
      if (!done.ok) {
        setRefused(t(`portal.enrol.code.${done.reason ?? "wrong"}`));
        return;
      }
      setSentTo(done.sent_to ?? null);
      setNext(done.next ?? null);
      setStep(4);
    });

  if (deadEnd) return <CallTheOffice office={office} />;

  const steps = STEP_KEYS.map((key) => t(`portal.updateEmail.step.${key}`));
  const readyToFind =
    accountNumber.trim() !== "" && postcode.trim() !== "" && lastName.trim() !== "";
  const lasts =
    minutes !== null ? (
      <span data-update-lasts="">{t("portal.updateEmail.lasts", { count: minutes })}</span>
    ) : null;

  return (
    <div data-update-email-wizard="">
      <Stepper steps={steps} current={step} />

      {step === 1 ? (
        <Card testId="update-email-find">
          <div data-screen="CWP-079">
            <p className="text-xs font-bold uppercase tracking-wide text-neutral-900">
              {t("portal.updateEmail.kicker")}
            </p>
            <h1 className="text-h1 leading-tight text-neutral-900">
              {t("portal.updateEmail.title")}
            </h1>
            <p className="mt-1 text-body leading-relaxed text-neutral-600">
              {t("portal.enrol.findLead")}
            </p>
            <div className="mt-4 flex max-w-[420px] flex-col gap-5">
              <FormField id="update-account" label={t("portal.enrol.accountNumber")} required>
                <TextInput
                  id="update-account"
                  value={accountNumber}
                  placeholder={t("portal.enrol.accountNumberExample")}
                  onChange={setAccountNumber}
                  required
                />
              </FormField>
              <FormField
                id="update-postcode"
                label={t("portal.enrol.postcode")}
                helper={t("portal.postcodeHelper")}
                required
              >
                <TextInput
                  id="update-postcode"
                  value={postcode}
                  onChange={setPostcode}
                  inputMode="numeric"
                  required
                />
              </FormField>
              <FormField id="update-lastname" label={t("portal.enrol.lastName")} required>
                <TextInput id="update-lastname" value={lastName} onChange={setLastName} required />
              </FormField>
              <Refused text={refused} />
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
            <WhereNext
              mark="update-email"
              doors={[{ key: "sign_in", label: t("portal.signIn"), to: "/sign-in" }]}
            />
          </div>
        </Card>
      ) : null}

      {step === 2 ? (
        <Card testId="update-email-prove">
          <div data-update-step="prove">
            <p className="text-xs font-bold uppercase tracking-wide text-neutral-900">
              {t("portal.enrol.foundKicker")}
            </p>
            <StepHeading>{t("portal.updateEmail.pickTitle")}</StepHeading>
            <p className="mt-1 text-body leading-relaxed text-neutral-600">
              {t("portal.updateEmail.pickLead")}
            </p>
            <div className="mt-4">
              <SectionTitle>{t("portal.updateEmail.onFile")}</SectionTitle>
              <RadioList
                name={t("portal.updateEmail.onFile")}
                value={picked}
                options={options.map((option) => ({
                  value: option.key,
                  label: option.masked,
                  hint:
                    option.channel === "sms" ? t("portal.enrol.bySms") : t("portal.enrol.byEmail"),
                }))}
                onChange={setPicked}
              />
            </div>
            {proveRef === null ? (
              <div className="mt-4 flex flex-col gap-3">
                <Refused text={refused} />
                <div className="flex items-center gap-3">
                  <WorkingButton working={working} onClick={doSend}>
                    {t("portal.updateEmail.sendCode")}
                  </WorkingButton>
                </div>
              </div>
            ) : (
              <div className="mt-4 flex flex-col gap-3" data-update-code="">
                <p className="text-body leading-relaxed text-neutral-600" role="status">
                  {t("portal.updateEmail.sentTo")}{" "}
                  <strong data-update-sentto="">{sentTo ?? ""}</strong>
                  {". "}
                  {lasts}
                </p>
                <div className="flex max-w-[240px] flex-col gap-3">
                  <FormScope form={form}>
                  <FormField id="update-code" label={t("portal.enrol.sixDigit")} required>
                    <DialInput id="update-code" value={code} onChange={setCode} maxLength={6} />
                  </FormField>
                  </FormScope>
                </div>
                <Refused text={refused} />
                <div className="flex items-center gap-3">
                  <WorkingButton working={working} onClick={form.guard(doVerify)}>
                    {t("portal.enrol.verify")}
                  </WorkingButton>
                  <Button variant="secondary" size="sm" onClick={() => void doSend()}>
                    {t("portal.enrol.resend")}
                  </Button>
                </div>
              </div>
            )}
            <div className="mt-4 border-t border-neutral-200 pt-3">
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setDeadEnd(true)}
                data-update-cant-reach=""
              >
                {t("portal.updateEmail.cantReach")}
              </Button>
            </div>
          </div>
        </Card>
      ) : null}

      {step === 3 ? (
        <Card testId="update-email-new">
          <div data-update-step="email">
            <StepHeading>{t("portal.updateEmail.newTitle")}</StepHeading>
            <p className="mt-1 text-body leading-relaxed text-neutral-600">
              {t("portal.updateEmail.newLead")}
            </p>
            <div className="mt-4 flex max-w-[420px] flex-col gap-3">
              <FormField id="update-new-email" label={t("portal.updateEmail.newLabel")} required>
                <TextInput
                  id="update-new-email"
                  type="email"
                  value={newEmail}
                  onChange={setNewEmail}
                  required
                />
              </FormField>
              {confirmRef === null ? (
                <>
                  <Refused text={refused} />
                  <div className="flex items-center gap-3">
                    <CommitButton
                      label={t("portal.updateEmail.sendCode")}
                      working={working}
                      ready={newEmail.trim() !== ""}
                      reason={t("portal.updateEmail.reason.email_required")}
                      onClick={() => void doStart()}
                    />
                  </div>
                </>
              ) : (
                <div className="flex flex-col gap-3" data-update-confirm="">
                  <p className="text-body leading-relaxed text-neutral-600" role="status">
                    {t("portal.updateEmail.sentTo")}{" "}
                    <strong data-update-sentto="">{sentTo ?? ""}</strong>
                    {". "}
                    {lasts}
                  </p>
                  <div className="flex max-w-[240px] flex-col gap-3">
                    <FormScope form={form}>
                    <FormField id="update-confirm-code" label={t("portal.enrol.sixDigit")} required>
                      <DialInput
                        id="update-confirm-code"
                        value={confirmCode}
                        onChange={setConfirmCode}
                        maxLength={6}
                      />
                    </FormField>
                    </FormScope>
                  </div>
                  <Refused text={refused} />
                  <div className="flex items-center gap-3">
                    <WorkingButton working={working} onClick={form.guard(doConfirm)}>
                      {t("portal.updateEmail.confirm")}
                    </WorkingButton>
                    <Button variant="secondary" size="sm" onClick={() => void doStart()}>
                      {t("portal.enrol.resend")}
                    </Button>
                  </div>
                </div>
              )}
            </div>
          </div>
        </Card>
      ) : null}

      {step === 4 ? (
        <Card testId="update-email-done">
          <div data-update-step="done" data-update-next={next ?? ""}>
            <StepHeading>{t("portal.updateEmail.doneTitle")}</StepHeading>
            {next === "enrol" ? (
              <p className="mt-1 text-body leading-relaxed text-neutral-600">
                {t("portal.updateEmail.doneEnrol")}
              </p>
            ) : (
              <p className="mt-1 text-body leading-relaxed text-neutral-600">
                {t("portal.updateEmail.doneReset")}{" "}
                <strong data-update-sentto="">{sentTo ?? ""}</strong>
              </p>
            )}
            <WhereNext
              mark="update-email-done"
              doors={
                next === "enrol"
                  ? [{ key: "enrol", label: t("portal.updateEmail.setUpLogin"), to: "/enrol" }]
                  : [{ key: "sign_in", label: t("portal.signIn"), to: "/sign-in" }]
              }
            />
          </div>
        </Card>
      ) : null}
    </div>
  );
}

/** `CWP-079` inside the guest frame, which honours the utility's live switch. */
export function UpdateEmailPage(props: { client?: ApiClient }) {
  return (
    <GuestPage client={props.client}>
      <UpdateEmailView client={props.client} />
    </GuestPage>
  );
}
