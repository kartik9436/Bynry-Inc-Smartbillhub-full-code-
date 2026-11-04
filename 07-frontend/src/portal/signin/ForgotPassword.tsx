// ── Trace ──────────────────────────────────────────────
// Story:    US-CWP-020 (CWP-019, EP-CWP-05) — forgotten password, answered
//           the same way either way. ⚠ **THIS READ `US-CWP-019 (EP-CWP-03)`
//           UNTIL 2026-09-05 — `DEF-CWP-3862`.** `US-CWP-019` is *choose a
//           password* (`CWP-018`); the wave read the story id off the SCREEN
//           number beside it. Screens: CWP-019 · CWP-018 (the reset link's
//           *choose a new password*, US-CWP-020 TC-4)
// Defects:  DEF-CWP-10380 (a blank or malformed address was sent and answered
//           *check your inbox*) · DEF-CWP-10381 (the emailed link had no page
//           to open — there was no client call for `auth/reset-password`)
// Rules:    BR-CWP-038 (the SAME *check your email* panel whether or not the
//           address has a login — it STANDS, PO ruling 2026-10-22) ·
//           08-screen-layouts.md CWP-019 (T7, an InfoBar inside the card) ·
//           CR-189-BRC10 (*Not getting the email? Update your registered
//           email*) · B14 rule 33 · rule 21 · rule 36
// Tests:    src/portal/signin/ForgotPassword.dom.test.tsx
// Impacts:  src/portal/api/portalClient.ts `forgotPassword` · `resetPassword`
// ───────────────────────────────────────────────────────
import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";

import { ApiError } from "@/api/client";
import { WorkingButton } from "@/components/StateFrame";
import {
  Card,
  FormField,
  InfoBar,
  TextInput,
  WhereNext,
  DisabledCommit,
  fieldErrorId,
  usePortalPath,
} from "../components/primitives";
import { Announced, FormScope, usePortalForm } from "../components/a11y";
import { useLinkSecret } from "@/routing/useLinkSecret";

import { forgotPassword, resetPassword } from "../api/portalClient";

/**
 * Where *Update your registered email* goes. ⚠ **THAT SCREEN LANDS WITH
 * `CR-189-BRC10` AND IS NOT BUILT ON THIS BRANCH** — the door is drawn now and
 * `ForgotPassword.dom.test.tsx` asserts it BY ADDRESS, so the day the route is
 * registered nothing here has to move (hard-won law 2: a hold's test is
 * written with the hold).
 */
export const UPDATE_EMAIL_PATH = "/update-email";

/** The two shapes a typed address can be refused for, as the SERVER spells
 *  them (`credentials.email_refusal`) — so a 400 and this check name the same
 *  catalogue key. */
type EmailRefusal = "email_required" | "email_invalid";

/** A deliberately loose shape check: something, `@`, something, `.`,
 *  something, no spaces. The server's `validate_email` is the authority; this
 *  only stops the request a blank or obviously broken box would make. */
const EMAIL_SHAPE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export function emailRefusal(value: string): EmailRefusal | null {
  const typed = value.trim();
  if (typed === "") return "email_required";
  return EMAIL_SHAPE.test(typed) ? null : "email_invalid";
}

/**
 * `CWP-019` — and, when the address carries `ref` and `token`, the reset
 * link's *choose a new password*.
 *
 * ⚠ **THE TWO HALVES ARRIVE IN THE URL FRAGMENT** (`#ref=…&token=…`, decision
 * log 2026-10-22, MERGE-ACCESS): a browser never sends a fragment to a server,
 * so no server or proxy log holds the secret. A link emailed before that
 * change carries them in the query and still works for its lifetime; the
 * fragment wins where both are present (`routing/linkSecret`).
 *
 * ⚠ **THE LINK'S TWO HALVES ARE HELD IN STATE AND TAKEN OFF THE ADDRESS
 * BAR.** A token left in the URL travels in browser history; it is single
 * use, but there is no reason to leave it lying about. `useLinkSecret` holds
 * it after the replace, so removing it does not switch the screen back to the
 * ask form, and it re-reads on every location change, because a link pasted
 * into this same tab differs only by its fragment and does not reload.
 */
/** The reset link's two halves, as `credentials.reset_link` names them. */
const RESET_LINK_KEYS = ["ref", "token"] as const;

export function ForgotPasswordView() {
  const { ref, token } = useLinkSecret(RESET_LINK_KEYS);
  return ref && token ? <ChooseNewPassword link={{ ref, token }} /> : <AskForLink />;
}

/** *Not getting the email? Update your registered email* — on the form and on
 *  its answer panel (PO 2026-10-22, `CR-189-BRC10`). */
function UpdateEmailLine(props: { mark: string }) {
  const { t } = useTranslation();
  const path = usePortalPath();
  return (
    <p className="mt-3 text-base text-neutral-600" data-update-email={props.mark}>
      {t("portal.reset.notGetting")}{" "}
      <Link
        to={path(UPDATE_EMAIL_PATH)}
        className="text-base text-accent-text no-underline hover:underline"
      >
        {t("portal.reset.updateEmail")}
      </Link>
    </p>
  );
}

/**
 * The ask.
 *
 * ⚠ **THERE IS EXACTLY ONE ANSWER AND NO BRANCH THAT COULD PRODUCE A SECOND**
 * (`BR-CWP-038`). `asked` is a boolean; the panel below it is a constant. The
 * server returns the same object for an address with a login and one without —
 * and a client that told them apart would put back the disclosure the server
 * took out. `US-CWP-020` TC-2 compares the two rendered panels as STRINGS.
 *
 * ⚠ **A BLANK OR MALFORMED BOX IS NOT AN ADDRESS AND NEVER LEAVES THE SCREEN
 * (`DEF-CWP-10380`).** It used to be sent, answered 200 and confirmed with
 * *check your email* — a promise of a message to nobody. The check is about
 * what was TYPED, so it discloses nothing; the server refuses the same input
 * with 400 and the same key, should anything reach it.
 */
function AskForLink() {
  const { t } = useTranslation();
  const [email, setEmail] = useState("");
  const [working, setWorking] = useState(false);
  const [asked, setAsked] = useState(false);
  const [refused, setRefused] = useState<EmailRefusal | null>(null);
  const form = usePortalForm();

  async function submit(event?: FormEvent) {
    event?.preventDefault();
    const local = emailRefusal(email);
    setRefused(local);
    if (local !== null) {
      form.failed();
      return;
    }
    setWorking(true);
    try {
      await forgotPassword({ email: email.trim() });
      setAsked(true);
    } catch (error) {
      if (error instanceof ApiError && error.status === 400) {
        setRefused(
          error.messageKey === "portal.reset.email_required" ? "email_required" : "email_invalid",
        );
        form.failed();
        return;
      }
      throw error;
    } finally {
      setWorking(false);
    }
  }

  return (
    <Card testId="forgot-password">
      <div data-screen="CWP-019">
        <p className="text-xs font-bold uppercase tracking-wide text-neutral-900">
          {t("portal.reset.kicker")}
        </p>
        <h1 className="text-h1 leading-tight text-neutral-900">{t("portal.reset.title")}</h1>
        {/*
          ⚠ **WHAT THE LINK IS, BEFORE THEY ASK FOR IT** — the wireframe's
          `s5` note. It says *once* and NOT *how long*: the lifetime is the
          utility's own `password_link_valid_days` setting (PO 2026-10-22,
          *"don't do any hardcoding"*), on no payload this screen reads, so a
          figure here would be a second copy of a number free to drift.
        */}
        <p className="mt-1 text-body leading-relaxed text-neutral-600" data-reset-lead="">
          {t("portal.reset.beforeSubmit")}
        </p>
        <form
          className="mt-4 flex max-w-[420px] flex-col gap-3"
          noValidate
          onSubmit={(event) => void submit(event)}
        >
          <FormScope form={form}>
          {/* F-18 (`DEF-CWP-10550`), PO 2026-10-23: a malformed address is
              named in the ruled sentence before anything is sent. */}
          <FormField
            id="reset-email"
            label={t("portal.signIn.email")}
            required
            error={
              refused === "email_invalid"
                ? t("portal.form.emailFormat")
                : refused
                  ? t(`portal.reset.${refused}`)
                  : null
            }
          >
            <TextInput
              id="reset-email"
              type="email"
              value={email}
              onChange={(value) => {
                setEmail(value);
                if (refused) setRefused(null);
              }}
              required
              invalid={refused !== null}
              describedBy={fieldErrorId("reset-email")}
              autoComplete="email"
            />
          </FormField>
          </FormScope>
          <div className="flex items-center gap-3">
            <WorkingButton working={working} type="submit">
              {t("portal.reset.send")}
            </WorkingButton>
          </div>
        </form>
        {/* ⚠ The live region is ALWAYS in the tree and the answer appears
            inside it, so a screen reader hears *Check your email* the moment
            it arrives (accessibility question 7) — a region mounted together
            with its text is not reliably announced. */}
        {/* F-02 / F-04: the answer is announced through the frame's region
            and takes focus (`Announced`); this wrapper no longer needs to be
            a live region of its own, which would read it twice. */}
        <div>
          {asked ? (
            <Announced tone="status" as="div" className="mt-4" data-reset-answer="">
              {/*
              ⚠ **THE CONFIRMATION SAYS WHAT TO DO NEXT, NOT WHY WE ANSWER THE
              WAY WE DO** (B14 rule 33). The bold clause leads and `tail`
              carries the qualification. The *update your registered email*
              line rides in `below` — the same words for every address, so the
              panel is still a constant (`BR-CWP-038`).
            */}
              <InfoBar
                lead=""
                bold={t("portal.reset.checkYourEmail")}
                tail={t("portal.reset.sameEither")}
                below={<UpdateEmailLine mark="answer" />}
              />
            </Announced>
          ) : null}
        </div>
        {asked ? null : <UpdateEmailLine mark="form" />}
        <WhereNext
          mark="reset"
          doors={[{ key: "sign_in", label: t("portal.signIn"), to: "/sign-in" }]}
        />
      </div>
    </Card>
  );
}

/**
 * `CWP-018` reached from the reset email (`US-CWP-020` TC-4: *opens with the
 * password fields empty*).
 *
 * ⚠ **THE TENANT'S POLICY DECIDES, AND IT IS CHECKED BEFORE THE LINK IS
 * SPENT.** A refused password leaves the link usable (the server checks the
 * policy first), so the customer simply types another.
 */
function ChooseNewPassword(props: { link: { ref: string; token: string } }) {
  const { t } = useTranslation();
  const [chosen, setChosen] = useState("");
  const [again, setAgain] = useState("");
  const [working, setWorking] = useState(false);
  const [refused, setRefused] = useState<string | null>(null);
  const [dead, setDead] = useState<string | null>(null);
  const [done, setDone] = useState(false);
  const bothTyped = chosen.length > 0 && chosen === again;
  const form = usePortalForm();

  async function submit(event?: FormEvent) {
    event?.preventDefault();
    if (!bothTyped) return;
    setWorking(true);
    setRefused(null);
    try {
      await resetPassword({ ref: props.link.ref, token: props.link.token, password: chosen });
      setDone(true);
    } catch (error) {
      if (!(error instanceof ApiError) || error.status !== 422) throw error;
      if (error.messageKey.startsWith("portal.reset.link.")) {
        setDead(t(error.messageKey));
        return;
      }
      const failures = Array.isArray(error.params.failures)
        ? (error.params.failures as string[])
        : [];
      const count = typeof error.params.min_length === "number" ? error.params.min_length : 8;
      setRefused(
        failures.length > 0
          ? failures.map((key) => t(`portal.enrol.password.${key}`, { count })).join(" ")
          : t("portal.reset.policy"),
      );
      form.failed();
    } finally {
      setWorking(false);
    }
  }

  return (
    <Card testId="reset-choose">
      <div data-screen="CWP-018" data-reset-choose="">
        <p className="text-xs font-bold uppercase tracking-wide text-neutral-900">
          {t("portal.reset.kicker")}
        </p>
        <h1 className="text-h1 leading-tight text-neutral-900">{t("portal.reset.chooseTitle")}</h1>
        <div>
          {done ? (
            <Announced tone="status" as="div" className="mt-4" data-reset-done="">
              <InfoBar
                lead=""
                bold={t("portal.reset.doneTitle")}
                tail={t("portal.reset.signInNow")}
              />
            </Announced>
          ) : null}
        </div>
        {done ? (
          <div data-reset-done-doors="">
            <WhereNext
              mark="reset-done"
              doors={[{ key: "sign_in", label: t("portal.signIn"), to: "/sign-in" }]}
            />
          </div>
        ) : dead ? (
          <div className="mt-4" data-reset-dead="">
            <Announced tone="error" className="text-base font-semibold text-danger-700">
              {dead}
            </Announced>
            <WhereNext
              mark="reset-dead"
              doors={[
                { key: "ask_again", label: t("portal.reset.askAgain"), to: "/forgot-password" },
              ]}
            />
          </div>
        ) : (
          <form
            className="mt-4 flex max-w-[420px] flex-col gap-3"
            noValidate
            onSubmit={(event) => void submit(event)}
          >
            <FormScope form={form}>
            <FormField
              id="reset-new"
              label={t("portal.enrol.newPassword")}
              required
              error={refused}
            >
              <TextInput
                id="reset-new"
                type="password"
                value={chosen}
                onChange={setChosen}
                required
                invalid={refused !== null}
                describedBy={fieldErrorId("reset-new")}
                autoComplete="new-password"
              />
            </FormField>
            <FormField id="reset-again" label={t("portal.enrol.typeAgain")} required>
              <TextInput
                id="reset-again"
                type="password"
                value={again}
                onChange={setAgain}
                required
                autoComplete="new-password"
              />
            </FormField>
            </FormScope>
            <div className="flex items-center gap-3">
              {bothTyped ? (
                <WorkingButton working={working} type="submit">
                  {t("portal.reset.save")}
                </WorkingButton>
              ) : (
                // F-22 (`DEF-CWP-10551`): the reason is text, tied to the button.
                <DisabledCommit label={t("portal.reset.save")} reason={t("portal.enrol.typeItTwice")} />
              )}
            </div>
          </form>
        )}
      </div>
    </Card>
  );
}
