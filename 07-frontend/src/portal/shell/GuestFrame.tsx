// ── Trace ──────────────────────────────────────────────
// Story:    US-CWP-001 (EP-CWP-01) — the frame around every no-login screen.
//           Screens: CWP-001 (then CWP-002 … CWP-014)
// Rules:    09-component-inventory.md §1 `GuestFrame` (utility name left; Help ·
//           Visit us · Pay a bill · Report a problem as plain links + an
//           outlined Sign in; *Visit us* absent when no centre is shown, *Help*
//           absent when nothing is published — BR-CWP-093) · §0 tokens (the
//           accent is the TENANT's hex, never a constant) · CR-068 R3
//           (Sign in is HELD until CWP-015 lands — it landed in wave E)
// Defect:   DEF-CWP-3736 — the tenant's colour reached the DOM and no control
//           on the page (decision log 2026-09-04, measured in a browser) ·
//           DEF-CWP-3925 — three nav words and Sign in led nowhere
// Tests:    src/portal/shell/GuestFrame.test.tsx · src/portal/guest/FrontPage.test.tsx
// ───────────────────────────────────────────────────────
import type { CSSProperties, ReactNode } from "react";
import { useTranslation } from "react-i18next";

import { Link } from "react-router-dom";

import { BuildVersion } from "@/components/BuildVersion";
import { Panel } from "@/components/Panel";
import { BrandMark } from "@/features/tenancy/BrandMark";
import {
  HOVER_STEP,
  PRESSED_STEP,
  STOCK_ACCENT_INKS,
  STOCK_ACCENT_TEXT,
  brandInks,
  brandTextShade,
} from "@/lib/contrast";

import { cardIsAvailable, type PortalFront } from "../api/guestClient";
import { PortalAnnouncer } from "../components/a11y";
import { PortalRegionalProvider } from "../components/regional";
import { ErrandLink, NavLinkWord, usePortalPath } from "../components/primitives";
import { GuestLanguage } from "./GuestLanguage";

/**
 * THE TENANT'S OWN COLOUR, SET ONCE ON THE FRAME — as `--color-accent`, which
 * is the variable the whole product already reads.
 *
 * ⚠ **IT USED TO SET `--brand` AND `--accent`, AND THAT IS `DEF-CWP-3736`.**
 * The kit's controls are written `bg-accent` / `text-accent` /
 * `hover:bg-accent-600`, and Tailwind emits those as `var(--color-accent)` —
 * a THEME CONSTANT no tenant could move. So the hex was fetched, threaded
 * through three components, written onto a DOM element, and every button on
 * the guest surface still painted the PRODUCT's `#EC3013`. Measured in a real
 * engine on 2026-09-04, with a tenant hex of `#0F7B6C`: the frame carried
 * `--brand: #0F7B6C` and the primary button measured `rgb(236, 48, 19)`.
 *
 * ⚠ **AND NO TEST COULD HAVE CAUGHT IT, WHICH IS WHY THIS COMMENT IS LONG.**
 * The sample utility's `brand_primary_hex` is `#EC3013` and the theme's
 * `--color-accent` is `#ec3013` — the same colour to the byte. On every
 * fixture in this repository the wrong button and the right button are
 * identical pixels. Only a live utility with a colour of its own can tell
 * them apart, and that is exactly where the PO found it.
 *
 * ⚠ **THE TWO DARKER STEPS ARE DERIVED, NOT LEFT BEHIND.** The primary tier is
 * `bg-accent hover:bg-accent-600 active:bg-accent-700`. Move only the base and
 * a teal button turns RED under the pointer — a new defect wearing the old
 * one's fix. `color-mix` follows whatever colour the tenant chose, which a
 * hand-picked ramp cannot: on the stock hex it derives `#d02a11` / `#aa230e`
 * where the stock ramp holds `#dd2b0f` / `#ae1800`. One source, the rest
 * derived (hard-won law 5).
 *
 * ⚠ **`brand_accent_hex` IS DELIBERATELY NOT APPLIED — `DEF-CWP-3737`.**
 * `--color-accent-2` is declared in `tokens.css` and in `tailwind.css`'s
 * `@theme` and is read by NOTHING, and neither r10's `UI-RULES.md` nor B14
 * says what a second accent is for. Setting it would move dead wiring one
 * variable along, and `G90` refuses a property no `var()` consumes. When a
 * rule says where a second colour belongs, it gets a line here and a reader.
 *
 * ⚠ **A UTILITY WITH NO COLOUR OF ITS OWN GETS *OUR* STYLE GUIDE, NOT GREY —
 * PO RULING 2026-09-04, VERBATIM: *"default will be our style guide and then
 * we will allow utility users to change it"*.** The precedence has one
 * direction: `tokens.css` declares `--color-accent: #ec3013` at `:root`, that
 * IS the default, and a tenant's hex is a single override of the same
 * variable on this frame. Nothing is invented and no fallback chain exists —
 * when there is no hex, this function writes no ACCENT and r10's own accent
 * stands, which is what every staff screen already shows. (It does write the
 * three `--color-on-accent` inks for that stock accent — Group A, 2026-10-23,
 * below — which are text colours, not a tenant colour.)
 *
 * ⚠ **THE SENTENCE THIS REPLACES SAID THE OPPOSITE AND IS SUPERSEDED.** It
 * read *"No hex is invented for a tenant that has none: the variable is simply
 * absent and every `var(--brand)` falls back to the ink it sits in"* — and
 * *the ink it sits in* is GREY, which is half of what the PO was looking at
 * when they said the colours are not matching. It is corrected here rather
 * than deleted because this docstring is where a regression would show first
 * (hard-won law 1: a comment claiming a guarantee is not the guarantee, and a
 * comment claiming the WRONG guarantee is how the next lane rebuilds it).
 *
 * ⚠ **AN EMPTY STRING IS NOT A COLOUR.** `brand_primary_hex: ""` is falsy and
 * therefore writes nothing, which is the only correct answer: writing
 * `--color-accent: ""` would override the style guide with garbage and land
 * back at grey on precisely the tenants who never chose a colour. Asserted,
 * not assumed — `FrontPage.test.tsx` TC-1c.
 */
export function brandStyle(tenant: PortalFront["tenant"]): CSSProperties {
  const style: Record<string, string> = {};
  const primary = tenant.brand_primary_hex;
  if (primary) {
    style["--color-accent"] = primary;
    // The hover and active steps of the one tier that fills — `bg-accent-600`
    // and `bg-accent-700`. Percentages, not literals, so any tenant's colour
    // darkens the same way.
    style["--color-accent-600"] = `color-mix(in srgb, ${primary} ${HOVER_STEP}%, black)`;
    style["--color-accent-700"] = `color-mix(in srgb, ${primary} ${PRESSED_STEP}%, black)`;
  }
  // THE TEXT ON THE BRAND COLOUR IS CHOSEN BY CONTRAST — Group A ruling 3(a),
  // PO/QA 2026-10-23: white when it reaches 4.5:1, otherwise the dark ink.
  // Every fill the kit paints with the accent writes `text-on-accent`
  // (`-600`/`-700` on hover and press), so this one place decides it for every
  // button, chosen segment and badge on the portal. Worked: the sample
  // `#EC3013` reads 4.20 with white, so its rest state takes black (5.00); its
  // hover and pressed steps are darker and take white (5.22, 7.10). A utility
  // with no colour shows our accent, which is the same `#ec3013`, so it is
  // corrected the same way (decision log 2026-10-23, judgment 3).
  const inks = primary ? brandInks(primary) : STOCK_ACCENT_INKS;
  if (inks !== null) {
    style["--color-on-accent"] = inks.rest;
    style["--color-on-accent-600"] = inks.hover;
    style["--color-on-accent-700"] = inks.pressed;
  }
  // BRAND-COLOURED TEXT takes its own darker shade — Group A decision 2,
  // PO/QA 2026-10-23: the brand mixed 88% with black, darkened further until
  // it reaches 4.5:1 on `#f3f2f2`. Every kicker, link, outline button and back
  // link the portal draws in the brand reads `--color-accent-text`; borders,
  // fills, the focus ring and the chart bars keep `--color-accent`. Worked:
  // `#EC3013` → `#D02A11` (5.22 on white, 4.67 on `#f3f2f2`).
  const text = primary ? brandTextShade(primary) : STOCK_ACCENT_TEXT;
  if (text !== null) style["--color-accent-text"] = text;
  return style as CSSProperties;
}

/**
 * THE PORTAL'S SURFACE IS WHITE — `09-component-inventory.md` §0, row
 * *Surface*, which names both consumers in one line: **cards, panels**.
 *
 * ⚠ **`DEF-CWP-3987`, AND IT IS `DEF-CWP-3736` ONE TOKEN OVER.** The portal's
 * own `Card` writes `bg-[white]`; the shared `Panel` writes `bg-surface`,
 * which is `#eae9e9` — the STAFF app's surface, and correct there. So every
 * signed-in screen that has a rail drew a white main column beside a grey
 * rail, and the two columns of one page did not look like one page.
 *
 * ⚠ **THE FIX IS THE VARIABLE, NOT THE COMPONENT** (B14 rule 36). Recolouring
 * `Panel` would either move 149 staff call sites or fork the component under
 * its own name, which is exactly the drift `DEF-CWP-3655` folded back
 * together. The portal already moves `--color-accent` on this frame for the
 * tenant's hex; the surface travels the same way, in the same style
 * attribute, and every shared piece the portal composes — `Panel` today,
 * `DataTable` and `FilterBar` when the lists lane lands them — reads the
 * portal's answer without being told about the portal.
 *
 * ⚠ **IT IS OURS AND NOT THE TENANT'S**, so it is written unconditionally.
 * `brandStyle` writes nothing when a utility has chosen no colour; folding
 * the surface in there would have left the rail grey on precisely the
 * unbranded tenants, which is the same defect with a smaller blast radius.
 */
export const PORTAL_SURFACE = "#ffffff";

/** Everything the portal frame sets on itself: the tenant's colour when there
 *  is one, and the portal's own surface always. Both frames call this, so the
 *  guest half and the signed-in half cannot end up different colours — the
 *  reason `PortalShell` imports `brandStyle` rather than re-implementing it. */
export function portalFrameStyle(tenant: PortalFront["tenant"]): CSSProperties {
  return { ...brandStyle(tenant), "--color-surface": PORTAL_SURFACE } as CSSProperties;
}

/**
 * THE EMERGENCY LINE, ABOVE EVERYTHING, ON EVERY SIGNED-OUT SCREEN.
 *
 * ⚠ **THE WIREFRAME PUTS IT AT THE TOP AND THIS PRODUCT PUT IT IN THE
 * FOOTER.** `s1`'s note is one sentence and it is the whole reason this
 * component exists: *"Somebody standing in water must not have to read a
 * page."* Until now the utility's emergency number appeared exactly once on a
 * guest screen — in grey, at 15px, under the fold, beside the office hours —
 * so a person with a burst main had to scroll past six errand cards to find
 * it. `s3`'s rules line says it plainly too: *"Emergency number on every
 * unauthenticated screen."*
 *
 * ⚠ **SO IT BELONGS TO THE FRAME AND NOT TO THE FRONT PAGE.** Putting it on
 * `CWP-001` would leave it off `/sign-in`, `/enrol` and `/forgot-password`,
 * which is where somebody who cannot get in is standing when the pipe bursts.
 * `03-field-map.md` already says as much of this field — *"Shown on every
 * guest screen"* — and this is the first thing that makes that true.
 *
 * ⚠ **IT MINTS ONE STRING AND REUSES TWO.** `portal.report.emergencyTitle`
 * and `portal.report.emergencyLead` are already written natively in all
 * eleven catalogues for `CWP-006`'s rail panel, and reusing them is what
 * makes the sentence on the frame and the sentence on the report screen the
 * SAME sentence rather than two drifting spellings (B14 rule 35, and hard-won
 * law 5's one-source rule wearing a catalogue).
 *
 * ⚠ **WHAT IS NOT REUSED IS `portal.report.emergencyTail`, AND THAT IS
 * DELIBERATE.** It reads *". Any hour. Do not use this form."* — correct
 * beside a report form and actively wrong on `/sign-in`, where *this form* is
 * the sign-in box and the sentence would tell a customer not to use it. The
 * new key is that tail with its second sentence removed, and each catalogue's
 * own words are kept **including its punctuation**: German's begins `" an."`
 * because its lead ends with a separable verb, and Japanese's begins `"。"`.
 * A hard-coded `". "` in this file would have been wrong in four languages.
 *
 * ⚠ **NO PHONE, NO BAND.** A utility that has published no emergency number
 * gets nothing here rather than a heading over an empty space — `BR-CWP-093`,
 * and the same reading `GuestFrame`'s footer already takes of this field.
 */
export function EmergencyBand(props: { phone: string }) {
  const { t } = useTranslation();
  return (
    <Panel
      as="aside"
      tone="emergency"
      title={t("portal.report.emergencyTitle")}
      data-emergency-band=""
    >
      {t("portal.report.emergencyLead")}{" "}
      <span className="font-bold text-neutral-900" data-emergency-phone="">
        {props.phone}
      </span>
      {t("portal.emergency.anyHour")}
    </Panel>
  );
}

export function GuestFrame(props: { front: PortalFront; children: ReactNode }) {
  const { t } = useTranslation();
  const path = usePortalPath();
  const { front } = props;
  const live = front.is_live;
  return (
    // ⚠ **THE GUEST HALF GETS IT TOO, AND NOT AS AN AFTERTHOUGHT**
    // (`DEF-CWP-3994`). A quick-pay receipt carries the date the payment was
    // taken, and *Track anything* carries the date a request was raised —
    // neither of which a person is signed in for. Publishing at both frames is
    // what makes *every* portal date the tenant's own rather than most of them.
    <PortalRegionalProvider front={front}>
    <div
      className="min-h-screen bg-bg text-neutral-900"
      style={portalFrameStyle(front.tenant)}
      data-portal-frame="guest"
      data-live={live ? "true" : "false"}
    >
      <header className="border-b border-neutral-200 bg-[white]">
        {/* ⚠ **`min-h-[3.5rem]` AND NOT `h-14`, AND A MEASUREMENT IS WHY
            (`DEF-CWP-4440`, 2026-09-07).** A FIXED height CLIPS whatever does
            not fit — silently, and only in some languages. Measured in
            Chromium at 1440px on the Spanish catalogue: this row was **56px**
            and the nav inside it **853×52**, seven pixels of headroom, with
            *Pagar un recibo* and *Reportar un problema* already wrapping onto
            two lines to achieve it. Adding the language control took the nav
            to **886×70** and both of those words were then cut in half by the
            header, in the customer's own language, on the front page. **Only
            a screenshot could ever have said so** — no gate here reads
            rendered output (hard-won law 6).

            **The header GROWS instead of clipping**, and the two classes do
            different jobs: `min-h` + `py-2` here lets the row get taller,
            while `flex-wrap` on the NAV (and deliberately NOT on this row)
            wraps the words underneath each other. Wrapping this row instead
            was tried and measured worse — it puts the utility's name on a
            line of its own and the nav below it, which is not the shipped
            shape. Capping the control's width was tried too: **852×79, worse
            than 865×67**, and it truncates the one label the person who needs
            this control has to read (B14 rule 35).

            ⚠ **THAT RESIDUAL IS CLOSED — `CR-085` step 2, 2026-09-11.** This
            note used to end *"in English the header is two rows (84px) where it
            used to be one"*, and `DEF-CWP-4468` carried it as a copy decision
            this lane did not own. It was never a copy problem: measured at 390
            the bar was **three** rows and 147px. The seven errand words have
            moved to a band of their own beneath this row — see the comment on
            that `<nav>` — so this row holds ONE row at both widths with the
            brand, the language control and *Sign in* in it, and nothing was
            shortened, dropped or clipped in any of the eleven.

            ⚠ **`min-h-14` AND NOT `min-h-[3.5rem]`** — the same 56px, written
            as a step of the scale rather than as an arbitrary value (B14 rule
            39; `DEF-CWP-4928` counts 36 of those across the front end). Still
            `min-h`, never `h`: the clause above is still why. */}
        <div className="mx-auto flex min-h-14 max-w-[1100px] items-center justify-between gap-4 px-5 py-2">
          {/* ⚠ **THE LINK IS INSIDE `live`, AND A TEST CAUGHT IT NOT BEING.**
              `US-CWP-001` TC-3 is *the portal is off → no nav, so no door of any
              kind*, and a clickable brand on a switched-off portal is a door.
              The name still shows; it just does not go anywhere. */}
          {/* CR-172-BRC10 / DEF-TEN-9705 — the utility's logo (or its generated
              two-letter mark) beside its name, from the one logo address the
              staff app uses. The logo read needs no sign-in: it is the
              utility's public face. Drawn only when the server sent the mark. */}
          <span className="flex min-w-0 items-center gap-3" data-portal-brand="">
            {front.tenant.mark !== undefined && (
              <BrandMark
                mark={front.tenant.mark}
                hasLogo={front.tenant.has_logo === true}
                logoRef={front.tenant.logo_ref ?? null}
                size={32}
                name={front.tenant.name}
              />
            )}
            {live ? (
              <Link
                to={path("")}
                className="truncate font-bold text-neutral-900 no-underline hover:underline"
                data-portal-tenant-name=""
                data-link="brand_home"
              >
                {front.tenant.name}
              </Link>
            ) : (
              <span className="truncate font-bold" data-portal-tenant-name="">
                {front.tenant.name}
              </span>
            )}
          </span>
          {/* ⚠ **THE DOOR STAYS IN THE BAR; THE ERRANDS AND THE LANGUAGE
              CONTROL MOVED OUT — `CR-085` step 2, measured.** See the band
              below for the whole reason. *Sign in* is what the signed-in bar
              keeps in its own row (`Help`, `Sign out`, the avatar), so keeping
              it here is what makes the two frames the same shape rather than
              two opinions.

              ⚠ **AND THE LANGUAGE CONTROL WENT DOWN WITH THE ERRANDS RATHER
              THAN STAYING UP HERE, WHICH A TEST DECIDED AND NOT A
              PREFERENCE.** `GuestLanguage.dom.test.tsx` asserts
              `control.closest("nav")` — it encodes the PO's ruling of
              2026-09-07, *"you can also provdie language option for gurst
              customers on top menu as drop down"*, as *inside the nav*. The
              first draft of this split left it here, that case went red, and
              **the honest answer was to move the control, not to re-word the
              assertion**: a ruling encoded in somebody else's test is not a
              baseline to widen. It is still last in the row, which is the
              reason its own note gives — *a reader scanning for an errand
              should not meet a `<select>` first*. */}
          {live ? (
            <div className="flex shrink-0 items-center gap-5 text-body">
              <ErrandLink label={t("portal.signIn")} to="/sign-in" size="default" />
            </div>
          ) : null}
        </div>
      </header>
      {/* ══ THE ERRANDS, IN A BAND OF THEIR OWN — `CR-085` step 2 ═════════════
          ⚠ **THE GUEST BAR WAS 96px AT 1280 AND 147px — THREE ROWS — AT 390**,
          measured in a browser on 2026-09-11 across all thirteen guest
          addresses, against a signed-in bar of **57px** at both widths. The
          blueprint's standards block D draws exactly TWO heading bars *"because
          a third would mean a customer could not tell at a glance whether they
          are signed in"* — and a bar that is one row on one side of the product
          and three on the other is that distinction dissolving at the width
          most customers arrive at.

          ⚠ **THE CAUSE WAS ARITHMETIC AND NOT STYLE, WHICH IS WHY NOTHING WAS
          SHORTENED.** `DEF-CWP-4440` measured the nav at **853px inside ~860**
          BEFORE the language control existed; `DEF-CWP-4468` then recorded two
          rows in English as the residue. Seven errand words, a language control
          and a sign-in button do not fit beside a utility's name in 390px and
          never will, so the row was never the problem — putting them in the row
          was.

          ⚠ **IT IS THE SIGNED-IN SHELL'S OWN SHAPE, NOT A NEW ONE.** The PO
          ruled that arrangement on 2026-09-08 for the signed-in half — *"here
          header bar should ahve menu - and below that we should have a line for
          account"* — and `PortalShell.tsx` has drawn header → nav → account
          line ever since. The guest half now draws header → nav. Same classes,
          same wrap, same `gap-x-6`, so the two cannot drift apart.

          ⚠ **`flex-wrap` AND NOT `overflow-x-auto`, for the reason the signed-in
          strip records one file over:** wrapping keeps every errand tappable,
          where a sideways scroll pushes two of them off the edge — *"a door you
          cannot see is hard-won law 2's mirror."* The band gets taller on a
          phone; the BAR does not, and the bar is what the blueprint ratifies. */}
      {live ? (
        <nav
          className="border-b border-neutral-200 bg-[white]"
          aria-label={t("portal.nav.label")}
        >
          <div className="mx-auto flex max-w-[1100px] flex-wrap items-center gap-x-6 gap-y-2 px-5 py-3 text-body">
              {/* ⚠ **THREE OF THESE FOUR WERE PLAIN `<span>`s AND `Sign in` WAS
                  HELD, ON EVERY GUEST SCREEN — `DEF-CWP-3925`.** `CWP-011`,
                  `CWP-013`, `CWP-002` and `CWP-015` all landed in waves B, D, E
                  and P, each tested at its own address, and the frame around
                  them was never asked whether it had started pointing at them.
                  A word styled as a nav item that does nothing when pressed is
                  hard-won law 2 in its plainest form — which is exactly what the
                  *Track* comment below says, written by the lane that noticed it
                  for one link and not for the three above it. The conditions are
                  unchanged: `help` and `visit` still appear only when the server
                  says something is published (`BR-CWP-093`), and `Pay a bill`
                  only when the card is offered.

                  ⚠ **AND THEY STAYED UNCHANGED THROUGH THE 2026-09-05
                  RULING, DELIBERATELY.** That ruling puts all six errand cards
                  on the front page, disabled where a tenant cannot use them —
                  a CATALOGUE, which is what a grid of six is for. A nav word
                  is not a catalogue, it is a DESTINATION, and a greyed word in
                  a top bar that goes nowhere is the dead control four lines
                  up. So the words still come and go.

                  ⚠ **WHAT DID HAVE TO CHANGE IS HOW THE QUESTION IS
                  ASKED.** `front.cards.includes(key)` was the test until that
                  day and it would now be TRUE FOR ALL SIX — every key is sent,
                  so presence stopped meaning anything and only `available`
                  still does. `cardIsAvailable` asks the surviving question.
                  The payload's new shape made this a COMPILE ERROR rather than
                  a silent extra nav word, which is the only reason it was not
                  one. */}
              {/* ⚠ **THERE WAS NO WAY BACK FROM ANY GUEST SCREEN.** The top
                  bar held the utility's name as plain text and four errands, so
                  once a visitor opened *Pay a bill* or *Start service* the only
                  route home was the browser's back button. PO, 2026-09-05:
                  *"I ahve no way to go bak to home screen … you ahve to give
                  Hom as option befor pay Bill"*. It goes FIRST, which is where
                  they asked for it and where a reader looks. The brand is a
                  link now as well — that is the convention every visitor
                  already knows and it costs no space — but a convention is not
                  a control, which is why the word is here too. The word reuses
                  `portal.tab.home`, already in all eleven catalogues; minting a
                  twelfth spelling of *Home* would be 33 strings for a word the
                  product has. */}
              <NavLinkWord name="home" to="" label={t("portal.tab.home")} />
              {front.links.help ? (
                <NavLinkWord name="help" to="/help" label={t("portal.nav.help")} />
              ) : null}
              {front.links.visit ? (
                <NavLinkWord name="visit" to="/visit" label={t("portal.nav.visit")} />
              ) : null}
              {cardIsAvailable(front, "pay_bill") ? (
                <NavLinkWord name="pay_bill" to="/pay" label={t("portal.card.pay_bill.title")} />
              ) : null}
              {cardIsAvailable(front, "report_problem") ? (
                <NavLinkWord
                  name="report_problem"
                  to="/report"
                  label={t("portal.card.report_problem.title")}
                />
              ) : null}
              {/* ⚠ **TRACK HAS NO CARD AND NEEDS A DOOR.** `CWP-001`'s six
                  errand cards do not include it and `CWP-012` is drawn with no
                  entry point at all — a screen nobody can reach is hard-won
                  law 2 with the arrow reversed. It goes in the nav, beside the
                  other things a guest does without signing in. Decision log
                  2026-09-04. */}
              {/* ⚠ **`CWP-010` HAD NO DOOR EITHER, AND IT IS THE SAME SHAPE
                  AS TRACK ONE LINE BELOW** (`DEF-CWP-3954`). *Ask for a quick
                  service* is one of the six things `CR-068` §9 puts on the
                  guest surface, `CWP-001`'s errand cards do not include it, and
                  no anchor anywhere in the product named `/ask` — so the only
                  way to it was typing the address. It goes in the nav beside
                  the other errands a visitor runs without signing in.
                  ⚠ **GATED ON THE SWITCH, NOT SHOWN AND GREYED.** A utility
                  with requests off serves an empty category list, and
                  `CWP-010` then draws no cards at all (`BR-CWP-093`); a word
                  in the nav opening a page with nothing on it is the same
                  empty container the rule forbids. */}
              {front.switches?.requests_enabled ? (
                <NavLinkWord name="quick_service" to="/ask" label={t("portal.quick.title")} />
              ) : null}
              <NavLinkWord name="track" to="/track" label={t("portal.nav.track")} />
              {/* ⚠ **THE GUEST'S OWN LANGUAGE, RULED BY THE PO ON 2026-09-07:**
                  *"you can also provdie language option for gurst customers on
                  top menu as drop down"* (`DEF-CWP-4440`, `BR-CWP-105`). It
                  goes in the top menu because that is where they asked for it,
                  and LAST in the row because it is a setting rather than an
                  errand — *Home*, *Help*, *Pay a bill* and *Track* are places
                  to go, and a reader scanning for one should not meet a
                  `<select>` first.

                  ⚠ **IT IS INSIDE `live`, WITH EVERY OTHER CONTROL.**
                  `US-CWP-001` TC-3 is *the portal is off → no nav, so no door
                  of any kind*, and a holding page carries the utility's name
                  and colours and no sentence to translate. A language picker
                  over two words nobody reads would be a control with nothing
                  to act on.

                  ⚠ **AND IT IS THE GUEST FRAME ONLY.** A signed-in customer
                  changes theirs on `CWP-024`, where the choice is STORED on
                  their account and reaches their letters too — the PO's own
                  *"Signed customer should get their own references"*. Two
                  controls for one setting, one of them forgetful, is how a
                  product tells one person two things. */}
            <GuestLanguage offer={front.locales} />
          </div>
        </nav>
      ) : null}
      <main className="mx-auto max-w-[1100px] px-5 py-6">
        {/* ⚠ **FIRST, BEFORE THE SCREEN'S OWN HEADING** — see `EmergencyBand`.
            It is inside `live` with every other control: a switched-off portal
            draws the utility's name and nothing else (`US-CWP-001` TC-3). */}
        {live && front.emergency_phone ? <EmergencyBand phone={front.emergency_phone} /> : null}
        {/* F-02 (`DEF-CWP-10547`): the always-present message regions. Inside
            `PortalApp` this defers to the one mounted there; a frame drawn on
            its own still has them. */}
        <PortalAnnouncer>{props.children}</PortalAnnouncer>
      </main>
      {/* ⚠ **THE FOOTER IS DRAWN ON EVERY PAGE NOW, FOR THE BUILD — `DEF-CWP-9162`.**
          It used to exist only when the utility had set office hours or an
          emergency number, so most portals had no footer and NO portal showed
          which build it was (PO 2026-10-02: *"The Customer Portal does not
          display the application/version number."*). The two facts keep their
          old condition; the version is unconditional, including on the holding
          page, because a screenshot of a switched-off portal is a defect report
          too — the staff frame's own reason (`AppShell.tsx`). */}
      <footer className="mx-auto flex max-w-[1100px] flex-wrap items-baseline gap-x-6 gap-y-2 px-5 pb-6 text-base text-neutral-600">
        {live && front.office_hours_text ? (
          <span data-footer="office-hours">
            {t("portal.footer.officeHours")} {front.office_hours_text}
          </span>
        ) : null}
        {live && front.emergency_phone ? (
          <span data-footer="emergency">
            {t("portal.footer.emergency")} {front.emergency_phone}
          </span>
        ) : null}
        {/* Quiet, last, and dark enough to read (`neutral-700` passes AA on
            the page ground where the `neutral-500` facts beside it do not). */}
        <BuildVersion className="ml-auto text-sm text-neutral-700" />
      </footer>
    </div>
    </PortalRegionalProvider>
  );
}
