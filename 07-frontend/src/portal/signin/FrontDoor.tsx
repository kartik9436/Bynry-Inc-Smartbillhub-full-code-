// ── Trace ──────────────────────────────────────────────
// Story:    US-CWP-016 (CWP-015, EP-CWP-05) — the front door: sign in and
//           three doors. ⚠ **THIS READ `US-CWP-020 (EP-CWP-03)` UNTIL
//           2026-09-05 — `DEF-CWP-3862`.** `US-CWP-020` is *forgotten
//           password* and `EP-CWP-03` is *report a problem*; this screen is
//           `EP-CWP-05`'s first story. Screens: CWP-015
// Rules:    08-screen-layouts.md CWP-015 (split Card 50/50: a brand panel on
//           the left, SIGN IN on the right, then three doors) · BR-CWP-004 (a
//           staff email and password are refused with the ORDINARY failure —
//           this screen has no branch that could say otherwise) · B14 rule 33
//           (a refusal is five or six words) · rule 21 · rule 36
// Tests:    ⚠ **NONE — `SignIn.test.tsx` DOES NOT EXIST AND THIS LINE NAMED
//           IT ANYWAY (`DEF-CWP-3862`, 2026-09-05).** No test file imports
//           `FrontDoor`; hard-won law 1 — a Tests: line is not a test.
// Impacts:  src/portal/api/portalClient.ts `signIn`
// ───────────────────────────────────────────────────────
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";

import { Card, FormField, SectionTitle, TextInput, usePortalPath } from "../components/primitives";
import { Announced, FormScope, usePortalForm } from "../components/a11y";
import { emailRefusal } from "./ForgotPassword";
import { WorkingButton } from "@/components/StateFrame";
import type { PortalFront } from "../api/guestClient";
import { signIn } from "../api/portalClient";

/**
 * `CWP-015` — the front door, and it is not the front page.
 *
 * ⚠ **THREE DOORS, AND THE THIRD ONE NEEDS NO PASSWORD.** *Sign in* · *first
 * time here* · *just want to pay*. The third is the one people arrive for and
 * it must never be behind the first, which is why it is a peer of the other
 * two on this card rather than a line inside the sign-in form.
 *
 * ⚠ **THERE IS NO "ARE YOU STAFF?" LINK AND NO SEPARATE STAFF BOX.** Pine
 * Hill's admin can type their office email and password here and will get the
 * ordinary failure, because the customer store has never heard of them
 * (`BR-CWP-004`). A link saying *staff sign in here* would answer *is this a
 * utility that has staff accounts* to anyone who looked, and — worse — would
 * teach a customer that the two are the same door.
 */
export function FrontDoorView(props: { front: PortalFront }) {
  const { t } = useTranslation();
  const path = usePortalPath();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [working, setWorking] = useState(false);
  const [refused, setRefused] = useState<string | null>(null);
  // ⚠ **F-18 (`DEF-CWP-10550`), PO 2026-10-23: WHAT WAS TYPED IS CHECKED
  // BEFORE IT IS SENT.** An empty or malformed email and an empty password
  // never reach the server, so naming them discloses nothing about any
  // account. The one sentence for a wrong email OR password below is
  // untouched (`BR-CWP-004`, `BR-CWP-038`).
  const [emailError, setEmailError] = useState<string | null>(null);
  const [passwordError, setPasswordError] = useState<string | null>(null);
  const form = usePortalForm();

  async function submit() {
    const badEmail = emailRefusal(email);
    const nextEmail =
      badEmail === "email_required"
        ? t("portal.reset.email_required")
        : badEmail === "email_invalid"
          ? t("portal.form.emailFormat")
          : null;
    const nextPassword = password === "" ? t("portal.signIn.passwordRequired") : null;
    setEmailError(nextEmail);
    setPasswordError(nextPassword);
    if (nextEmail !== null || nextPassword !== null) {
      setRefused(null);
      form.failed();
      return;
    }
    setWorking(true);
    setRefused(null);
    try {
      await signIn({ email, password });
      navigate(path("/home"));
    } catch {
      // ⚠ ONE SENTENCE FOR EVERY FAILURE — an unknown address, a wrong
      // password and a staff credential are indistinguishable here because
      // they are indistinguishable on the wire (BR-CWP-004). Six words
      // (B14 rule 33).
      setRefused(t("portal.signIn.refused"));
    } finally {
      setWorking(false);
    }
  }

  return (
    // ⚠ **ON A PHONE THE FORM COMES FIRST, AND IT DID NOT.** The two halves
    // are a 50/50 split above 900px — brand left, SIGN IN right, which is the
    // drawing. Below it they stack in source order, so a person who tapped
    // *Sign in* on a 390px phone met the utility's name, its strapline, its
    // four services, its office hours and its phone number — about 550px of
    // reading — before the email box. The wireframe's phone drawing has no
    // brand panel above the form at all.
    //
    // ⚠ **`order` AND NOT A SOURCE SWAP**, because the source order is the
    // READING order for a screen reader and for anybody on a keyboard, and
    // above 900px the brand panel genuinely is first. Two `max-md:` rules move
    // only the phone, which is the width that was wrong (`tailwind.css`: this
    // theme authors max-width, never min-width).
    <div className="grid grid-cols-2 gap-4 max-md:grid-cols-1" data-screen="CWP-015">
      <div className="max-md:order-2">
      <Card testId="front-door-brand">
        <h2 className="text-lead font-bold text-neutral-900">{props.front.tenant.name}</h2>
        {props.front.strapline ? (
          <p className="mt-1 text-body leading-relaxed text-neutral-600">{props.front.strapline}</p>
        ) : null}
        <p className="mt-3 text-body text-neutral-600" data-front-services="">
          {props.front.services.map((service) => service.name).join(" · ")}
        </p>
        <hr className="my-4 border-neutral-200" />
        {props.front.office_hours_text ? (
          <p className="text-base text-neutral-600">{props.front.office_hours_text}</p>
        ) : null}
        {props.front.emergency_phone ? (
          <p className="text-base text-neutral-600">{props.front.emergency_phone}</p>
        ) : null}
      </Card>

      </div>
      <div className="max-md:order-1">
      <Card testId="front-door-signin">
        <p className="text-xs font-bold uppercase tracking-wide text-neutral-900">
          {t("portal.signIn.kicker")}
        </p>
        <h1 className="text-h1 leading-tight text-neutral-900">
          {t("portal.signIn.title")}
        </h1>
        <div className="mt-4 flex flex-col gap-5">
          <FormScope form={form}>
          <FormField id="portal-email" label={t("portal.signIn.email")} required error={emailError}>
            <TextInput
              id="portal-email"
              type="email"
              value={email}
              onChange={(value) => {
                setEmail(value);
                setEmailError(null);
              }}
            />
          </FormField>
          <FormField
            id="portal-password"
            label={t("portal.signIn.password")}
            required
            error={passwordError}
          >
            <TextInput
              id="portal-password"
              type="password"
              value={password}
              onChange={(value) => {
                setPassword(value);
                setPasswordError(null);
              }}
            />
          </FormField>
          </FormScope>
          <Link to={path("/forgot-password")} className="text-base text-accent-text no-underline hover:underline">
            {t("portal.signIn.forgot")}
          </Link>
          {refused ? (
            <Announced tone="error" className="text-base font-semibold text-danger-700" data-signin-refused="">
              {refused}
            </Announced>
          ) : null}
          <div className="flex items-center gap-3">
            <WorkingButton working={working} onClick={submit}>
              {t("portal.signIn.commit")}
            </WorkingButton>
          </div>
        </div>
        <hr className="my-4 border-neutral-200" />
        <SectionTitle>{t("portal.signIn.otherDoors")}</SectionTitle>
        <ul className="mt-2 flex flex-col gap-2 text-body">
          <li>
            <Link
              to={path("/enrol")}
              data-door="enrol"
              className="font-bold text-accent-text no-underline hover:underline"
            >
              {t("portal.signIn.doorEnrol")}
            </Link>
          </li>
          <li>
            <Link
              // DEF-CWP-10567 (F-24): this door said "Pay with a bill number"
              // and opened the front page; every other door with these words
              // opens Pay (`/enrol` already did).
              to={path("/pay")}
              data-door="quick_pay"
              className="font-bold text-accent-text no-underline hover:underline"
            >
              {t("portal.signIn.doorQuickPay")}
            </Link>
          </li>
          <li>
            <Link
              to={path("/start-service")}
              data-door="start_service"
              className="font-bold text-accent-text no-underline hover:underline"
            >
              {t("portal.signIn.doorStartService")}
            </Link>
          </li>
        </ul>
      </Card>
      </div>
    </div>
  );
}
