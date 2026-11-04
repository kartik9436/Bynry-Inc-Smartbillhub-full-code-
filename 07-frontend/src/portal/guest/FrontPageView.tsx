// ── Trace ──────────────────────────────────────────────
// Story:    US-CWP-001 (EP-CWP-01) — the six cards, drawn from the server's
//           list · US-CWP-070 TC-3/TC-4 — the same drawing is the Branding
//           screen's live preview. Screens: CWP-001 · CWP-070 (the miniature)
// Rules:    08-screen-layouts.md CWP-001 (T1: PageHead → CardGrid3 → InfoBar)
//           · PO ruling 2026-09-05 — ALL SIX cards are drawn, DISABLED where
//           they cannot be used, each carrying its reason (this REVERSES the
//           layout's old *a card whose switch is off is ABSENT*) · BR-CWP-093
//           (still governs the NAV WORDS, which come and go) · B14 rule 31 (no
//           id and no internal code is a visible value) · rule 32 · rule 33 (a
//           reason is a FACT in six words; the RATIONALE is not on screen at
//           all) · CR-068 R3 (every `Start →` is HELD until its screen lands)
// Tests:    src/portal/guest/FrontPage.test.tsx ·
//           src/features/tenancy/SettingsCustomerPortalTab.test.tsx
// ───────────────────────────────────────────────────────
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";

import { PageHeader } from "@/components/PageHeader";

import type { ErrandCardKey, ErrandCardReason, PortalFront } from "../api/guestClient";
import {
  CardGrid3,
  ErrandCard,
  ErrandLink,
  HeldButton,
  InfoBar,
  usePortalPath,
} from "../components/primitives";

/**
 * The card copy, keyed by the server's card key. The server decides WHICH
 * cards; this table only knows the words for each.
 *
 * ⚠ **THIS COMMENT USED TO SAY *written as LITERAL keys so the catalogue gate
 * (G27) can see every one*, AND G27 CANNOT SEE THEM (corrected 2026-09-05).**
 * The gate's regex is `t("some.key")` — a literal INSIDE the call — and these
 * keys reach `t()` through a table lookup, so not one of the twelve is
 * scanned. Nothing is broken today because all twelve are in `en.json`
 * already; what was broken was the sentence, which told the next lane a
 * guarantee existed (hard-won law 1). The guarantee that actually holds is in
 * `FrontPage.test.tsx`: it renders the page and refuses any `portal.` key
 * appearing as visible text.
 */
const CARD_COPY: Record<ErrandCardKey, { title: string; description: string }> = {
  pay_bill: { title: "portal.card.pay_bill.title", description: "portal.card.pay_bill.description" },
  report_problem: {
    title: "portal.card.report_problem.title",
    description: "portal.card.report_problem.description",
  },
  check_my_area: {
    title: "portal.card.check_my_area.title",
    description: "portal.card.check_my_area.description",
  },
  start_service: {
    title: "portal.card.start_service.title",
    description: "portal.card.start_service.description",
  },
  what_things_cost: {
    title: "portal.card.what_things_cost.title",
    description: "portal.card.what_things_cost.description",
  },
  help_answers: {
    title: "portal.card.help_answers.title",
    description: "portal.card.help_answers.description",
  },
};

/**
 * The one sentence a DISABLED card says, keyed by the server's reason code and
 * written as LITERAL keys so the catalogue gate (G27) can see every one.
 *
 * ⚠ **THREE CODES, THREE SENTENCES, AND THEY MUST NOT READ ALIKE** — that is
 * the whole of `DEF-CWP-3953`. *Switched off* is something the utility undoes
 * itself in its own settings; *nothing published yet* is undone by publishing
 * one answer, today; *no status page* is undone by nobody here. A utility
 * reading its own front page in the `CWP-070` preview has to be able to tell
 * the five-minute job from the permanent one, and until this ruling all three
 * looked identical because all three looked like nothing.
 *
 * Each is a FACT and not a RATIONALE (B14 rule 33): six words at most, and not
 * one word of *why the product works this way*, which belongs here in the code
 * and in the register. No rule id, no code, nothing internal (rule 31).
 *
 * ⚠ **EACH CARRIES ITS ENGLISH, AND THAT IS NOT BELT-AND-BRACES.** These keys
 * are not in the eleven catalogues yet — they were written by this lane and
 * handed to the lane that owns those files, which four lanes share. `t()`
 * answers a missing key WITH THE KEY, so without the fallback this screen
 * would print `portal.card.unavailable.switchedOff` to a customer: the exact
 * defect G27 was built for after a Settings panel rendered its own source
 * code. `i18next` prefers a real catalogue entry the moment one exists, so the
 * fallback costs nothing once the words land, and the ten other languages read
 * English until then rather than reading a key.
 */
const REASON_COPY: Record<ErrandCardReason, { key: string; en: string }> = {
  switched_off_by_the_utility: {
    key: "portal.card.unavailable.switchedOff",
    en: "Not offered online at the moment.",
  },
  status_page_not_offered: {
    key: "portal.card.unavailable.noStatusPage",
    en: "No status page here yet.",
  },
  nothing_published_yet: {
    key: "portal.card.unavailable.nothingPublished",
    en: "Nothing published here yet.",
  },
};

//: The neutral sentence, for a reason code this build has never heard of.
const REASON_FALLBACK = {
  key: "portal.card.unavailable.other",
  en: "Not available just now.",
} as const;

/**
 * ⚠ **A CODE THIS BUILD HAS NEVER HEARD OF MUST NOT PRINT ITSELF.** `t()`
 * answers a missing key with the key, so a server that grows a fourth reason
 * before this client learns the word for it would put
 * `portal.card.unavailable.somethingNew` on a customer's screen — an internal
 * code on the glass, B14 rule 31, and `DEF-CWP-3952`'s shape one surface over.
 * The neutral sentence is true of every reason there could ever be, so it is
 * the safe thing to fall back to and the honest one.
 */
function reasonCopy(code: ErrandCardReason | null): { key: string; en: string } {
  return (code !== null && REASON_COPY[code]) || REASON_FALLBACK;
}

/**
 * Where a card GOES, for the cards whose screen is built. A key absent here is
 * still HELD with its reason (`CR-068` R3) — which is the honest state for a
 * screen a later wave builds, and the opposite of hard-won law 2's dead UI: a
 * card that navigates does so because its route exists in `portalRoutes.tsx`.
 *
 * ⚠ **R3 SAYS *held UNTIL ITS SCREEN LANDS*, AND FOUR OF THEM HAD LANDED
 * WITHOUT THIS TABLE HEARING ABOUT IT (`DEF-CWP-3925`).** Wave A shipped every
 * `Start →` and the sign-in bar held with its reason, correctly — no screen
 * existed yet. Waves C, D, E and P then built them, and each wave tested its
 * own screen at its own address, so nothing anywhere asked whether the FRONT
 * PAGE had started pointing at them. A visitor to Pine Hill was told *Opens
 * with the next release* on five of six cards and on Sign in, over four
 * screens that were live, routed and tested. It is the same shape as
 * `DEF-CWP-3820` and `DEF-CWP-3821` on the staff side the day before — a
 * disabled control over a working destination — and it is why this table is
 * now checked against `PORTAL_SCREENS` by a test rather than by a reader.
 *
 * Still held, and correctly: `what_things_cost`, which has no screen in this
 * product yet — R3's own hold, and the only card still in that state.
 *
 * ⚠ **`check_my_area` LEFT THIS SENTENCE ON 2026-09-05 AND DID NOT JOIN THE
 * TABLE.** It used to be described here as *the card the server never sends*;
 * the server sends it now, unavailable, so the front page can say why. It
 * still has no route and must not get one until `CR-068` R9 is reversed —
 * `FrontPage.test.tsx` refuses a `CWP-005` row in `PORTAL_SCREENS` for exactly
 * that reason, and that case is what goes red the day the status page lands.
 */
export const CARD_ROUTE: Partial<Record<ErrandCardKey, string>> = {
  //: `CWP-002` — the LOOKUP is live and the payment behind it is not, which is
  //: the screen's own held control (CR-068 R2/R3) and not a reason to hold the
  //: door: a customer who cannot pay online still comes here to find the bill.
  pay_bill: "/pay",
  report_problem: "/report",
  //: `CWP-008` — *can I get service here?*, wave C.
  start_service: "/start-service",
  //: `CWP-011` — wave D. The SERVER only offers this card when something is
  //: published (BR-CWP-093), so the link can never open an empty list.
  help_answers: "/help",
};

/**
 * CWP-001's body, given the front-page data. Pure: the same component draws
 * the live page and the Branding screen's miniature, so the two can never
 * disagree about what a visitor sees (US-CWP-070 §1: *"the preview is what
 * makes the screen worth opening"*).
 */
export function FrontPageView(props: { front: PortalFront }) {
  const { t } = useTranslation();
  const path = usePortalPath();
  const { front } = props;
  return (
    <div data-screen="CWP-001">
      <PageHeader
        kicker={front.tenant.name.toUpperCase()}
        title={t("portal.front.title")}
        rollup={front.strapline ?? t("portal.front.subtitle")}
      />
      {front.services.length > 0 ? (
        <ul className="mb-4 flex flex-wrap gap-2" aria-label={t("portal.front.servicesLabel")}>
          {front.services.map((chip) => (
            <li
              key={chip.code}
              data-service-chip={chip.code}
              className="border px-2 py-1 text-base font-semibold"
              style={chip.color ? { borderColor: chip.color, color: chip.color } : undefined}
            >
              {chip.name}
            </li>
          ))}
        </ul>
      ) : null}
      {/*
        ⚠ **ALL SIX, ALWAYS, AND TWO KINDS OF NOT-YET AMONG THEM.** The server
        sends every card with whether it may be used; this decides which of
        three things the bottom of each card is.

          · UNAVAILABLE — the utility cannot offer it at all. Disabled card,
            and the reason is the server's (switched off · nothing published ·
            no status page).
          · AVAILABLE with no route — offered, but this product draws no screen
            for it yet. `CR-068` R3's hold, and its reason is R3's.
          · AVAILABLE with a route — a live link.

        The middle one is why an unavailable card is not simply *held*: R3's
        hold says **we** have not built the screen, and these three say
        something about **this tenant** or about a ruling. Collapsing them
        would put *"Opens with the next release"* under a card whose own
        utility switched it off this morning.
      */}
      <CardGrid3>
        {front.cards.map((card) => (
          <ErrandCard
            key={card.key}
            cardKey={card.key}
            unavailable={!card.available}
            reasonCode={card.available ? undefined : card.reason_code}
            title={t(CARD_COPY[card.key].title)}
            description={t(CARD_COPY[card.key].description)}
            action={
              !card.available ? (
                <HeldButton
                  label={t("portal.card.start")}
                  reason={t(reasonCopy(card.reason_code).key, {
                    defaultValue: reasonCopy(card.reason_code).en,
                  })}
                />
              ) : CARD_ROUTE[card.key] === undefined ? (
                <HeldButton label={t("portal.card.start")} reason={t("portal.held.card")} />
              ) : (
                /*
                  ⚠ **ONE FILLED CONTROL ON THE PAGE, AND IT IS *Pay a bill*.**
                  The wireframe's `s1` note is the rule and it names the loser
                  as well as the winner: *"One filled button, and it is not
                  'Sign in' — most visits are a payment, and most of those
                  people have no account and do not want one. Sign-in is the
                  outlined second path."* Every card drew `secondary` before
                  this, so the busiest page in the portal offered a stranger
                  six identical grey outlines and no primary action at all.

                  ⚠ **IT IS KEYED OFF THE CARD, NOT OFF THE POSITION.** A
                  tenant with quick pay switched off sends `pay_bill`
                  UNAVAILABLE, so this branch is not reached and the page
                  correctly has no filled control rather than promoting
                  whatever happens to be drawn first.
                */
                <ErrandLink
                  label={t("portal.card.start")}
                  to={CARD_ROUTE[card.key] as string}
                  variant={card.key === "pay_bill" ? "primary" : "secondary"}
                />
              )
            }
          />
        ))}
      </CardGrid3>
      <div className="mt-4">
        {/*
          The sign-in bar. ⚠ HELD UNTIL WAVE E AND LIVE SINCE — `CWP-015` is
          routed at `/sign-in` and `DEF-CWP-3925` is this control still saying
          otherwise. It is drawn at `default` because the bar's control is a
          full-size one; the held version was, so the live one is too.
        */}
        {/*
          ⚠ **`below` CARRIES THE TWO DOORS THIS PAGE DID NOT HAVE.** The
          wireframe draws them under the sign-in on `s1` — *"Create one ·
          Forgot your password?"* — and `s4` says in as many words where a
          person is expected to find enrolment: *"The landing page — one of the
          three doors it carries beneath the sign-in form."* Until now the
          front page offered `Sign in` and nothing else, so a paper-bill
          customer with no login and a customer who had forgotten one both had
          to guess that `/sign-in` carries the way on.

          ⚠ **BOTH LABELS ARE KEYS THE ELEVEN CATALOGUES ALREADY HOLD**, and
          both are the same words the sign-in screen uses for the same doors —
          `WhereNext`'s own rule, so a customer reads one spelling of *set up
          your login* rather than two.
        */}
        <InfoBar
          lead={t("portal.front.loginLead")}
          bold={t("portal.front.loginBold")}
          trailing={<ErrandLink label={t("portal.signIn")} to="/sign-in" size="default" />}
          below={
            <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-body">
              <Link
                to={path("/enrol")}
                data-door="enrol"
                className="font-bold text-accent-text no-underline hover:underline"
              >
                {t("portal.signIn.doorEnrol")}
              </Link>
              <Link
                to={path("/forgot-password")}
                data-door="forgot_password"
                className="font-bold text-accent-text no-underline hover:underline"
              >
                {t("portal.signIn.forgot")}
              </Link>
            </div>
          }
        />
      </div>
    </div>
  );
}
