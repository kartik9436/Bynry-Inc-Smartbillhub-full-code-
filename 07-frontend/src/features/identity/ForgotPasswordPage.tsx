// ── Trace ──────────────────────────────────────────────
// Change:   CR-170-BRC10 (PO 2026-10-05, decision log *"FORGOT PASSWORD"*)
// Story:    US-IDN-002 TC-1 (forgot password, no-email v1)  Screen: ONB-06
// Rules:    BR-IDN-023 (as amended 2026-10-05 — its own page, NO contact) ·
//           BR-IDN-021 (no email is sent) · B14 rules 33 (on-screen text capped
//           by what it is for) · 43 (built on the shared AuthCard)
// ───────────────────────────────────────────────────────
/**
 * THE FORGOT-PASSWORD PAGE, at `/{tenant}/forgot-password` — public, signed out.
 *
 * It tells a person who has forgotten their password what to do, in the PO's
 * ruled words, and offers one way back. That is all it is, and three things it
 * deliberately is NOT are each a ruling rather than an omission:
 *
 * 1 · **NO CONTACT, OF ANY KIND.** PO 2026-10-05, verbatim: *"dont show any
 *     contact"*. No admin's name, no phone, no email, not the utility's. A test
 *     asserts it (`ForgotPasswordPage.test.tsx`).
 * 2 · **NO REQUEST TO THE SERVER.** The page renders from the catalogue alone.
 *     A signed-out page that looked anything up by tenant would answer *"does
 *     this utility exist"* to a stranger, and there is nothing it needs to know.
 * 3 · **NO KICKER.** The ruled page is a heading, one instruction and one
 *     button; the sign-in card's *"Already a customer"* line is not in it.
 * 4 · **NO FORM.** v1 has no reset endpoint and sends no email (`BR-IDN-021`).
 *     The reset is the System Admin's *Reset temp password* on Settings › Users
 *     & roles, unchanged.
 *
 * `?next=` — the sign-in door to go back to. The field app's door is
 * `/{tenant}/work/mobile/signin`, so its *Forgot password?* passes that, and
 * *Back to sign in* returns there rather than to the staff door that would
 * refuse a technician's login (`BR-WRK-043`). It goes through `safeReturnPath`,
 * so it can never leave this tenant; anything it will not vouch for is the
 * ordinary sign-in.
 */
import { useTranslation } from "react-i18next";
import { useSearchParams } from "react-router-dom";

import { AuthCard } from "@/components/AuthCard";
import { ButtonLink } from "@/components/Button";
import { RETURN_PARAM, SIGNIN_SEGMENT, safeReturnPath, useTenantPath } from "@/routing/tenantPath";

export function ForgotPasswordPage() {
  const { t } = useTranslation();
  const tenantPath = useTenantPath();
  const [searchParams] = useSearchParams();
  const back = safeReturnPath(searchParams.get(RETURN_PARAM)) ?? SIGNIN_SEGMENT;

  return (
    <AuthCard
      page="forgot-password"
      title={t("identity.forgotPassword.title")}
      lede={t("identity.forgotPassword.body")}
    >
      <ButtonLink variant="primary" className="w-full justify-center" to={tenantPath(back)}>
        {t("identity.forgotPassword.back")}
      </ButtonLink>
    </AuthCard>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// generated: 2026-10-05 by lane PWD (CR-170-BRC10)
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
