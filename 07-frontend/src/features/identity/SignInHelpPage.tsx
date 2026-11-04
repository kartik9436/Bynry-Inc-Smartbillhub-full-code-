// ── Trace ──────────────────────────────────────────────
// Story:    US-IDN-011 (EP-IDN-01 — reaching your utility's sign-in from a page
//           that has no tenant)  Screens: none (no A1 ID is claimed; S72 was a
//           PROPOSAL riding with OQ-078 and was never assigned — CLAUDE.md
//           forbids renumbering A1)
// Rules:    BR-IDN-027 (this landing performs NO lookup of any kind) ·
//           BR-IDN-021 (staff auth emails are not a v1 lookup surface) ·
//           BR-IDN-006 (a wrong tenant is indistinguishable from a missing one) ·
//           BR-SHL-020 (shared states) ·
//           BR-TEN-011 (the subdomain grammar this page mirrors, and only mirrors)
// ───────────────────────────────────────────────────────
// `/signin-help` — the tenant-less landing the public "Sign in" link points to.
//
// WHY THIS PAGE IS DELIBERATELY SMALL. Tenancy is path-based (PO 2026-08-10), so
// a session belongs to exactly one utility and sign-in lives at
// `/{tenant}/signin`. The public pages have no tenant, so their Sign-in link
// cannot know where to send you. Until 2026-08-10 this route rendered the
// literal string "SMARTBillHub — W0 scaffold" on a PUBLIC page, because the
// route was named by the path-tenancy ruling before any screen was designed for
// it. That was reported and left; the first real deployment put it in front of
// the PO, which is the right way to find out that a marker string had escaped
// onto a customer-facing surface.
//
// WHAT IT DOES, AND WHAT IT REFUSES TO DO. It builds a URL and nothing more: you
// type the web address your utility chose at signup, it sends you to that
// tenant's sign-in. There is NO lookup, because every lookup leaks. Searching by
// email would confirm membership to anyone who guessed an address, and
// BR-IDN-021 keeps staff auth emails out of v1 surfaces entirely; searching by
// utility name would confirm which utilities exist on the platform. Both are the
// same class of disclosure BR-IDN-006 exists to prevent, so this page declines
// both rather than shipping a convenience that answers a stranger's question.
//
// Consequently it does NOT validate the slug. It cannot: a "no such utility"
// response IS the membership oracle. You are forwarded to `/{slug}/signin`,
// which renders identically whether or not that tenant exists — the wrong-tenant
// and no-tenant cases are one case, by design.
//
// The genuine recovery path — "I do not remember our web address" — was routed
// as OQ-078 and **CLOSED by the PO on 2026-08-10: "leave it as it is."** Building
// the URL from a slug the user types, with no lookup by email, is the ruled
// trade: an email-based lookup would confirm membership to any stranger who
// guessed an address. So this page gains no recovery feature, and the copy under
// the form (`signinHelp.noAddress`) points at the one channel that leaks nothing
// — a colleague who is already signed in and has the address in their own
// browser bar. That sentence IS the ruling, not a placeholder for it.
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate } from "react-router-dom";

import { HOME_ROUTE, SIGNUP_ROUTE, SIGNIN_SEGMENT, tenantPathFrom } from "@/routing/tenantPath";

import { Button, ButtonLink } from "@/components/Button";
import { ProductName } from "@/components/ProductName";

// BR-TEN-011's grammar, the same one `selectors.subdomain_problem` enforces
// server-side: charset [a-z0-9-], 3–63 characters, no leading or trailing
// hyphen. Kept identical here so this page rejects locally exactly what
// provisioning would reject anyway — input hygiene on a value we already hold,
// not a lookup against tenant data.
//
// It does NOT check RESERVED_SUBDOMAINS. That list is server-side knowledge and
// mirroring it here would tell a stranger which names the platform holds back.
// A reserved name simply routes to a sign-in that finds nothing, like any other
// name that is not a tenant.
export const SLUG_PATTERN = /^[a-z0-9][a-z0-9-]{1,61}[a-z0-9]$/;

/**
 * THE WHOLE DECISION THIS PAGE MAKES, as a pure function: typed text → where to
 * go, or why not. Extracted 2026-08-15 with US-IDN-011 so the story's TC-2, TC-3
 * and TC-6 are asserted rather than left as `it.todo` — there is no DOM library
 * in package.json, so a behaviour that lives inside an event handler cannot be
 * proved, and "navigating to the right place" is the only thing this page does.
 *
 * The three cases it distinguishes are exactly BR-IDN-027's:
 *   · a well-formed address           → `/{tenant}/signin`, whether or not that
 *                                       utility exists (TC-3: unknown ≠ invalid,
 *                                       and the two must be indistinguishable)
 *   · a RESERVED name such as `api`   → forwarded like any other (TC-6): the
 *                                       reserved list is server knowledge and
 *                                       mirroring it would tell a stranger which
 *                                       names the platform holds back
 *   · anything failing BR-TEN-011     → refused LOCALLY, no navigation, no request
 */
export function signInHelpDestination(typed: string): { path: string } | { error: true } {
  const cleaned = typed.trim().toLowerCase();
  if (!SLUG_PATTERN.test(cleaned)) {
    return { error: true };
  }
  return { path: tenantPathFrom(cleaned, SIGNIN_SEGMENT) };
}

/**
 * ⛔ **DEF-050 — THE HINT USED TO TYPE THE LIVE PRODUCTION HOST INTO THE COPY.**
 *
 * `signinHelp.hint` read *"…the part after smartbillhub.bynry.com/"*, so the
 * sentence was wrong for every other deployment — and wrong in a way that reads
 * as CORRECT to a reviewer sitting on that host. The locale expansion then took
 * one wrong string to eleven: ten catalogues carry a translation OF the
 * hardcoded host.
 *
 * ⚠ **AND IT IS THE SECOND TIME.** A 2026-08-10 sweep replaced a hardcoded
 * `{{subdomain}}.smartbillhub.app` and could not see this one, because it
 * searched for the DEAD domain. *"A search shaped by the bug you already know
 * about finds only that bug."* G19 is the durable half — it matches the SHAPE
 * of a host in any catalogue value and carries no domain list at all.
 *
 * The fix is the one `SignupWizard` already uses and the one DEF-050's
 * prevention names: the host is `window.location.host`. Path tenancy (PO
 * 2026-08-10) is what makes that correct rather than convenient — a utility
 * lives at a PATH on the origin the visitor is already on, so the host in this
 * sentence is BY DEFINITION the host serving this page. There is nothing to
 * configure, nothing to put in a `.env` that a deployed host would never
 * receive (hard-won law 4), and no way for it to be right in one environment
 * and wrong in another.
 *
 * ⚠ **IT IS A NEW KEY (`signinHelp.hintHost`) AND THAT IS DELIBERATE.**
 * `signinHelp.hint`'s value in all eleven catalogues is the sentence WITH the
 * host typed into it, and i18next ignores `defaultValue` for a key that exists
 * — so reusing the old key would have left the wrong sentence on screen until
 * eleven catalogue files were re-translated, i.e. this change would have read
 * as a fix and rendered the defect (hard-won law 1). Under a key nothing
 * defines yet, the `defaultValue` below renders, interpolated, TODAY.
 *
 * ⚠ **THEREFORE `signinHelp.hint` IS NOW DEAD AND MUST BE DELETED FROM ALL
 * ELEVEN CATALOGUES**, together with its line in
 * `10-scripts/gates/env_hostname_gaps.txt` — that register is EXPIRING by
 * design and G19 FAILS on an entry that no longer reproduces, which is what
 * forces the two to move in one diff. This lane may not edit either file; both
 * are reported with the change.
 */
function currentAppHost(): string {
  return typeof window === "undefined" ? "" : window.location.host;
}

export interface SignInHelpPageProps {
  /** Test seam — SSR has no `window.location`. Same seam, same reason and same
   *  name as `SignupWizard`'s. This product does not server-render, so in a
   *  browser this is never empty. */
  appHost?: string;
}

export function SignInHelpPage(props: SignInHelpPageProps = {}) {
  const { t } = useTranslation();
  const appHost = props.appHost ?? currentAppHost();
  const navigate = useNavigate();
  const [slug, setSlug] = useState("");
  const [error, setError] = useState<string | null>(null);

  function onSubmit(event: React.FormEvent) {
    event.preventDefault();
    const destination = signInHelpDestination(slug);
    if ("error" in destination) {
      setError(t("signinHelp.invalid"));
      return;
    }
    setError(null);
    navigate(destination.path);
  }

  return (
    <div className="min-h-screen bg-bg" data-public-page="signin-help">
      {/* The public nav is the SAME shape S1 carries; CR-018 moved it off
          `PricingPage.css` onto utilities on both pages rather than leaving one
          screen importing another feature's stylesheet — carrying the old
          `.public-nav a` (0,1,1) specificity bug across with it. DEF-573 removed
          it from both pages together: the wordmark and the CTA each carry their
          own size and colour, and no page rule reaches into the button kit. */}
      <nav
        className="flex items-center gap-6 border-b-2 border-b-divider px-8 py-4"
        aria-label={t("public.nav.label")}
      >
        <Link className="mr-auto" data-public-brand to={HOME_ROUTE}>
          <ProductName size="public" />
        </Link>
        <ButtonLink variant="primary"  to={SIGNUP_ROUTE}>
          {t("public.nav.startFree")}
        </ButtonLink>
      </nav>

      <main className="mx-auto max-w-[640px] px-4 py-8">
        <h1 className="m-0 mb-3">{t("signinHelp.title")}</h1>
        <p>{t("signinHelp.body")}</p>

        <form className="my-4 flex flex-col items-start gap-2" onSubmit={onSubmit} noValidate>
          <label htmlFor="signin-help-slug">{t("signinHelp.label")}</label>
          <p className="field-help" id="signin-help-hint">
            {/* DEF-050 — the host is the one serving this page, never a name
                typed into the copy. `defaultValue` carries the corrected
                English so the sentence is right the moment this ships, before
                the eleven catalogues are re-translated. */}
            {t("signinHelp.hintHost", {
              host: appHost,
              defaultValue:
                "The name your utility chose at signup — the part after {{host}}/",
            })}
          </p>
          <input
            className="input"
            id="signin-help-slug"
            name="slug"
            type="text"
            autoComplete="organization"
            spellCheck={false}
            value={slug}
            aria-describedby="signin-help-hint"
            aria-invalid={error ? true : undefined}
            onChange={(event) => setSlug(event.target.value)}
          />
          {error ? <p role="alert">{error}</p> : null}
          <Button variant="primary"  type="submit">
            {t("signinHelp.submit")}
          </Button>
        </form>

        <p>{t("signinHelp.noAddress")}</p>
      </main>
    </div>
  );
}

export default SignInHelpPage;

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-IDN-011@f1f263c (EP-IDN-01 — story authored 2026-08-10 BECAUSE the G1/G3
//         gates refused a traced file with no US-ID; that refusal was correct)
// context: `/signin-help` was named by the PO's
//         2026-08-10 path-tenancy ruling as public surface; no A1 screen and no
//         A13 copy were ever written for it (S72 is PROPOSED, not assigned).
// generated: 2026-08-10 by Eng-Lead, from the PO's FIRST LIVE DEPLOYMENT report
//         · AMENDED 2026-08-15 by story-coder (tenancy/identity lane): the file
//         finally CLAIMS US-IDN-011 in its Trace header (it said `Story: (none)`
//         because the page predated the story — the reverse of the usual failure,
//         and G1/G3 are what forced the story into existence); OQ-078's CLOSURE
//         ("leave it as it is", PO 2026-08-10) is recorded where the code used to
//         say the PO had not decided; and `signInHelpDestination` is extracted so
//         TC-2/TC-3/TC-6/TC-7 are ASSERTED instead of deferred to an it.todo
//         ("Unable to login nor signup") — the route was rendering the literal
//         marker string "SMARTBillHub — W0 scaffold" on a public page.
// checklist: A✔ B✔ C✔ D=deferred(no API call by design — BR-IDN-027) E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: tsc✔ · vitest src/features/identity/SignInHelpPage.test.tsx 11 passed/1 todo✔ ·
//        suite 540 passed/135 todo (529 was the baseline; this packet adds 11)✔ ·
//        vite build✔ · run_gates 11-PASS/0-FAIL/1-SKIP✔
//        [2026-08-15 amendment] tsc --noEmit✔ · vitest this file 16 passed/1 todo✔
//        (was 11 passed/1 todo — the 5 new ones are US-IDN-011 TC-2/TC-3/TC-4-5/TC-6/TC-7,
//        replacing the navigation it.todo with the pure decision it stood for) ·
//        full frontend suite 1047 passed / 185 todo across 71 files✔ (1042 was the
//        baseline when this lane started) · run_gates: G1/G2/G3/G10/G11/G13/G14/G15/G18
//        all PASS; the run's 2 FAILs (G6, G7) name only apps/ledger, apps/notifications
//        and apps/billing files from concurrent lanes, none of them this one's
// exceptions: [2026-08-15] three STALE comments corrected, not deleted — `tenantPath.ts`'s
//        SIGNIN_HELP_ROUTE docstring, that file's Lifecycle exceptions line, and the routing
//        comment in App.tsx all still said this route "renders the W0 marker", five days
//        after this page replaced it. Hard-won law 1, three times on one route · NO screen ID is claimed — inventing one would renumber A1, which
//        CLAUDE.md forbids; the S72 proposal rides with OQ-078 · NO lookup of any
//        kind is performed, so a nonexistent utility is indistinguishable from a
//        real one (BR-IDN-006); the reserved-name list is deliberately NOT
//        mirrored client-side · the real "I lost our address" recovery path is
//        OQ-078 and is NOT guessed here · copy is not A13-derived because A13 has
//        no entry for this route — REPORTED
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
