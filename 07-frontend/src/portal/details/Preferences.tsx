// ── Trace ──────────────────────────────────────────────
// Story:    US-CWP-028 (EP-CWP-06) — the PREFERENCES half. Screen: CWP-025
//           (blueprint `P11`) · wireframes/CWP-025.png
// Rules:    08-screen-layouts.md CWP-025 (`PreferenceGrid` then T4: Panel
//           PAPER [KVList Paperless billing / You agreed · grey paragraph ·
//           Button(outline) *Go back to paper*] · Panel LANGUAGE
//           [FormField.Select + helper]) · BR-CWP-087 (paperless is a RECORDED
//           CONSENT with its wording version and a way to withdraw) ·
//           BR-NOT-024 / CR-068 R4 (print is the FLOOR — the grid says ALWAYS
//           and offers no control) · B14 rule 17 (an empty state says what
//           fills it) · rule 21 (Tailwind utilities; `portal/` is on
//           route-b-migrated.txt) · rule 31 (no database id on screen) ·
//           rule 32 (one sentence per section) · rule 33 (a refusal is five or
//           six words) · rule 35 (the catalogue writes the words) · rule 36
//           (compose the kit — `PreferenceGrid`, `TwoEqual` and `SelectInput`
//           were ADDED to it for this screen)
// Defect:   DEF-CWP-4442 — PO 2026-09-07, verbatim: *"currently in drop down
//           show only 2 elnglish and spanish"*. The LANGUAGE panel's options
//           are `offeredLocales(held.locales, held.locale)` from this day —
//           the server's two, plus this reader's own where it is neither.
// Tests:    src/portal/details/Preferences.dom.test.tsx
// Impacts:  src/portal/api/portalClient.ts `getPreferences` ·
//           `savePreferences` · `withdrawPaperless` ·
//           src/portal/shell/GuestLanguage.tsx (the OTHER picker — the two
//           call one function so they cannot show different lists)
// ───────────────────────────────────────────────────────
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { PageHeader } from "@/components/PageHeader";

import { Button } from "@/components/Button";
import { Panel } from "@/components/Panel";
import { Announced, PortalRefusal } from "../components/a11y";

import {
  Card,
  CommitButton,
  FormField,
  InfoBar,
  KVList,
  PreferenceGrid,
  SegmentedChoice,
  SelectInput,
  TwoEqual,
  type PreferenceCell,
  usePortalPath,
} from "../components/primitives";
import { offeredLocales, supportedLocale } from "../components/language";
import { languageName } from "../components/languageName";
import { PortalScreen, PortalState } from "../components/states";
import {
  getPreferences,
  savePreferences,
  withdrawPaperless,
  type PortalPreferences,
} from "../api/portalClient";

/** The four columns, in the wireframe's order. */
const COLUMNS = ["post", "email", "text", "portal"] as const;

/**
 * `CWP-025` — how we contact you, and the one thing the drawing does not know.
 *
 * ⚠ **THE GRID IS PER EVENT AND THE STORE IS NOT** (`DEF-CWP-3860`,
 * `OQ-CWP-1660`). This product holds `accounts.paperless` (adds email),
 * `accounts.sms_reminders` (adds text) and the print floor — three facts, not
 * forty-eight. `US-CWP-028` §5 points the per-event cell at the *notification
 * rule catalogue*, which is the TENANT's row: one per event per tenant by
 * unique constraint, so a customer saving there would change what every other
 * customer receives.
 *
 * **So the grid draws the rows and the switches sit ABOVE it, once**, with a
 * line saying the choice covers every document. Forty-eight controls wired to
 * two columns would look per-row and behave account-wide, which is hard-won law
 * 2 with better manners.
 *
 * ⚠ **AND POST IS A STATEMENT, NOT A DISABLED SWITCH** (`US-CWP-028` §2: *"the
 * screen must show it honestly rather than offering an off switch that quietly
 * does nothing"*). A greyed toggle still reads as *somebody could turn this
 * off*; a chip reading ALWAYS does not.
 */
export function PreferencesView() {
  const { t, i18n } = useTranslation();
  const path = usePortalPath();
  const [held, setHeld] = useState<PortalPreferences | null>(null);
  const [failed, setFailed] = useState(false);
  const [working, setWorking] = useState(false);
  const [refused, setRefused] = useState<string | null>(null);
  const [saved, setSaved] = useState<number | null>(null);

  useEffect(() => {
    let live = true;
    getPreferences()
      .then((answer) => {
        if (live) setHeld(answer);
      })
      .catch(() => {
        if (live) setFailed(true);
      });
    return () => {
      live = false;
    };
  }, []);

  // ⚠ **THE HEAD IS BUILT ONCE, ABOVE THE BRANCHES, AND RENDERS ON EVERY ONE
  // OF THEM — `DEF-CWP-4926` (`CR-085` step 2).** It was declared INSIDE the
  // success branch, below `if (failed) return …`, so a failed or a slow read
  // threw away the page title, the `data-screen` mark every rendered check in
  // this repo selects on, and the drawing's whole top row of controls — the
  // one row that could have got the customer anywhere else. Ten signed-in
  // screens shared that single misplaced `return`; `arrears/Overdue.tsx` is
  // the model that already did it this way. R-10 (PO 2026-09-11: *"when a
  // screen tells a customer something bad, the thing they can do about it must
  // be on that same screen"*) cannot be met by a branch that renders no
  // controls at all.
  // ⚠ **AND THE LOADING BRANCH WAS `return null`** — see `methods/Methods.tsx`
  // for the same note; `portal.preferences.reading` is new in all eleven.
  const head = (
    <PageHeader
      kicker={t("portal.kicker.myDetails")}
      title={t("portal.preferences.title")}
      backTo={{ to: path("/my-details"), label: t("portal.preferences.backToDetails") }}
    />
  );

  if (failed) {
    return (
      <PortalScreen screen="CWP-025" head={head}>
        {/* ⚠ `data-preferences-failed` IS KEPT — a suite selects on it. */}
        <PortalState kind="failed" sentence={t("portal.preferences.failed")}>
          <span data-preferences-failed="" hidden />
        </PortalState>
      </PortalScreen>
    );
  }
  if (held === null) {
    return (
      <PortalScreen screen="CWP-025" head={head}>
        <PortalState kind="loading" sentence={t("portal.preferences.reading")} />
      </PortalScreen>
    );
  }

  // ⚠ **ONE LIST, READ TWICE — THE OPTIONS AND THE SENTENCE ABOVE THEM.**
  // `DEF-CWP-4442`: the offer is the server's two and the reader's own language
  // is added where it is neither, so the count and the control must come from
  // the same array or the caption contradicts the list beneath it.
  const shownLocales = offeredLocales(held.locales, held.locale);

  // What the reader is looking at RIGHT NOW. `i18n.language` can carry a
  // region i18next resolved from a fallback, so it goes through the same
  // mapper the guest picker uses — a raw `en-GB` here would be named as a
  // language this build does not draw.
  const reading = supportedLocale(i18n.language) ?? "en";

  async function apply(fields: Record<string, unknown>) {
    setWorking(true);
    setRefused(null);
    try {
      const result = await savePreferences(fields);
      setSaved(result.accounts_updated);
      setHeld(await getPreferences());
    } catch {
      // ⚠ FIVE OR SIX WORDS (B14 rule 33), and the catalogue writes them.
      setRefused(t("portal.preferences.saveFailed"));
    } finally {
      setWorking(false);
    }
  }

  async function goBackToPaper() {
    setWorking(true);
    setRefused(null);
    try {
      await withdrawPaperless();
      setHeld(await getPreferences());
    } catch {
      setRefused(t("portal.preferences.saveFailed"));
    } finally {
      setWorking(false);
    }
  }

  const consent = held.paperless;
  const withdrawn = consent !== null && consent.withdrawn_on !== null;

  return (
    <div data-screen="CWP-025">
      {/* ⚠ **THE BACK CONTROL IS A TEXT LINK IN THE HEAD NOW, NOT A BORDERED
          BUTTON ABOVE THE CARD** (`DEF-CWP-4000`; delta X5 names exactly this
          — *"a bordered button captioned `Back to …`, sitting where a primary
          action would sit"*). `PageHeader` draws `← {label}`, so the arrow
          left the eleven catalogue values with it: the component owns the
          glyph, and a translated string carrying its own arrow would draw two.
          Back to `CWP-024`, so the pair is not a one-way street. */}
      {head}
      <Card testId="preferences-grid">
        {/* ⚠ **THE HONEST SENTENCE, ABOVE THE TABLE RATHER THAN UNDER IT.**
            One answer covers every document; saying so is what makes a grid
            with two switches truthful. */}
        <p className="mt-1 max-w-measure text-body text-neutral-600" data-applies-to-all="">
          {t("portal.preferences.appliesToEveryDocument", { count: held.account_count })}
        </p>

        {held.floor_readable ? (
          <>
            {/* ⚠ **A CHANNEL THE UTILITY HAS NOT SWITCHED ON IS STATED, NOT
                OFFERED** (CR-085 group I, 2026-09-08). `channels` has been on
                this wire since the screen was built and NOTHING read it, so
                both switches were drawn on every tenant — including one with
                no SMS provider, where turning *text* on means a customer waits
                for a reminder that can never be sent. The drawing names this
                twice and calls it *"the failure this panel exists to
                prevent"*.
                ⚠ **THE ROW STAYS AND SAYS WHY, RATHER THAN VANISHING.** A
                missing row reads as an oversight; the same reasoning `CWP-024`
                applies to the legal name it may not edit, and the same
                reasoning TC-3 applies to post — a chip, never a dead switch. */}
            <div className="mt-3 flex flex-wrap items-center gap-4">
              {(["email", "text"] as const).map((channel) =>
                held.channels.includes(channel) ? (
                  <SegmentedChoice
                    key={channel}
                    label={t(`portal.preferences.${channel}Label`)}
                    testId={channel}
                    current={(channel === "email" ? held.email_on : held.text_on) ? "on" : "off"}
                    options={[
                      { key: "on", label: t("portal.preferences.on") },
                      { key: "off", label: t("portal.preferences.off") },
                    ]}
                    onChoose={(key) =>
                      void apply(
                        channel === "email"
                          ? { email_on: key === "on" }
                          : { text_on: key === "on" },
                      )
                    }
                  />
                ) : (
                  <p
                    key={channel}
                    className="text-body text-neutral-600"
                    data-channel-off={channel}
                  >
                    {t(`portal.preferences.channelOff.${channel}`)}
                  </p>
                ),
              )}
            </div>
            {held.election_varies ? (
              <p className="mt-2 text-body text-neutral-600" data-election-varies="">
                {t("portal.preferences.varies")}
              </p>
            ) : null}
            <div className="mt-3">
              <PreferenceGrid
                caption={t("portal.preferences.whatWeSend")}
                columns={COLUMNS.map((key) => ({
                  key,
                  label: t(`portal.preferences.column.${key}`),
                }))}
                rows={held.rows.map((row) => ({
                  key: row.kind,
                  label: t(`portal.preferences.kind.${row.kind}`, { defaultValue: row.kind }),
                  cells: Object.fromEntries(
                    COLUMNS.map((key) => [key, row[key] as PreferenceCell]),
                  ),
                }))}
                alwaysLabel={t("portal.preferences.always")}
                onLabel={t("portal.preferences.on")}
                offLabel={t("portal.preferences.off")}
                noneLabel={t("portal.preferences.notSent")}
              />
            </div>
            {/* ⚠ **WHAT SWITCHING EMAIL OFF ACTUALLY DOES**, said before
                somebody does it: these columns only ever ADD a channel
                (`BR-BIL-036`), so nothing here stops a letter. */}
            <div className="mt-3">
              <InfoBar
                lead={t("portal.preferences.printFloorLead")}
                bold={t("portal.preferences.printFloorBold")}
              />
            </div>
          </>
        ) : (
          // B14 rule 17 — a stated absence, never an empty table. An empty
          // grid would assert *nothing is sent*, which is the opposite of true.
          <p className="mt-3 text-body text-neutral-600" data-floor-unreadable="">
            {t("portal.preferences.floorUnreadable")}
          </p>
        )}

        {refused !== null ? (
          <div className="mt-3">
            <PortalRefusal data-preferences-refused="">{refused}</PortalRefusal>
          </div>
        ) : null}
        {saved !== null && refused === null ? (
          <Announced tone="status" className="mt-2 text-body text-neutral-700" data-preferences-saved="">
            {t("portal.preferences.saved", { count: saved })}
          </Announced>
        ) : null}
      </Card>

      <TwoEqual
        left={
          <Panel as="section" title={t("portal.preferences.paperTitle")}>
            {consent === null ? (
              // ⚠ **AN ABSENT CONSENT IS NOT A WITHDRAWN ONE** (`US-CWP-014`
              // TC-2). Every customer who connected before the online form
              // existed sees this, and it must not read as *you opted out*.
              <p className="text-body text-neutral-600" data-no-consent="">
                {t("portal.preferences.noConsent")}
              </p>
            ) : (
              <>
                <KVList
                  rows={[
                    {
                      key: "paperless",
                      label: t("portal.preferences.paperlessBilling"),
                      value: (
                        <span data-consent-state={withdrawn ? "withdrawn" : "agreed"}>
                          {withdrawn
                            ? t("portal.preferences.withdrawn")
                            : t("portal.preferences.agreed")}
                        </span>
                      ),
                    },
                    {
                      key: "agreed-on",
                      label: t("portal.preferences.youAgreed"),
                      value: (
                        <span data-agreed-on={consent.agreed_on ?? ""}>
                          {onDate(consent.agreed_on, i18n.language)}
                        </span>
                      ),
                    },
                    ...(withdrawn
                      ? [
                          {
                            key: "withdrawn-on",
                            label: t("portal.preferences.youWithdrew"),
                            value: onDate(consent.withdrawn_on, i18n.language),
                          },
                        ]
                      : []),
                  ]}
                />
                <p className="mt-2 text-body text-neutral-600">
                  {t("portal.preferences.paperExplain")}
                </p>
                {!withdrawn ? (
                  <div className="mt-3">
                    {/* r10 rule 6 — danger is for DESTRUCTIVE commits. Going
                        back to paper destroys nothing: the consent row keeps
                        its wording version and gains a withdrawal date. */}
                    <Button
                      variant="secondary"
                      data-action="withdraw-paperless"
                      disabled={working}
                      onClick={() => void goBackToPaper()}
                    >
                      {t("portal.preferences.goBackToPaper")}
                    </Button>
                  </div>
                ) : null}
              </>
            )}
          </Panel>
        }
        right={
          <Panel as="section" title={t("portal.preferences.languageTitle")}>
            {/* ⚠ **THE HELPER COUNTS WHAT IS ON SCREEN, NOT WHAT THE SERVER
                OFFERS, AND THAT CHANGED ON 2026-09-07 (`DEF-CWP-4442`).** It
                read `held.locales.length`, which was harmless while the two
                numbers were always equal. They are not any more: a customer
                whose account says German is shown THREE and the offer is TWO,
                so the sentence would have read *2 languages available.* under
                a list of three — a caption contradicting the control beneath
                it. No catalogue string moved; `{{count}}` was already
                interpolated in all eleven, so `G15`'s untranslated count did
                not move either. */}
            <FormField
              id="preferences-locale"
              label={t("portal.preferences.languageLabel")}
              helper={t("portal.preferences.languageHelper", { count: shownLocales.length })}
            >
              <SelectInput
                id="preferences-locale"
                value={held.locale ?? ""}
                options={[
                  ...(held.locale === null
                    ? [{ value: "", label: t("portal.preferences.languageUnset") }]
                    : []),
                  // ⚠ EACH IS NAMED IN ITS OWN LANGUAGE — `languageName` is the
                  // kit's one answer to that, and a list of English names would
                  // be unreadable to the very person choosing one (B14 rule 35).
                  //
                  // ⚠ **`offeredLocales` AND NOT `held.locales` RAW, SINCE
                  // 2026-09-07 (`DEF-CWP-4442`).** The Product Owner narrowed
                  // the offer to two — *"currently in drop down show only 2
                  // elnglish and spanish"* — and ruled nothing about the
                  // accounts already holding `de` or `hi`. Rendering two
                  // options over a stored third leaves this control BLANK, with
                  // no error and every test green, so the reader's own language
                  // is listed as what it is. It is the SAME function the guest
                  // dropdown in the portal frame calls, because two controls
                  // for one setting offering different lists is how a product
                  // tells one person two things.
                  ...shownLocales.map((code) => ({
                    value: code,
                    label: languageName(code),
                    // Named in itself, so marked as such (DEF-CWP-10561).
                    lang: code,
                  })),
                ]}
                onChange={(value) => void apply({ locale: value })}
              />
            </FormField>
            <div className="mt-3">
              <CommitButton
                label={t("portal.preferences.saveLanguage")}
                working={working}
                ready={held.locale !== null}
                reason={t("portal.preferences.pickALanguage")}
                onClick={() => void apply({ locale: held.locale })}
              />
            </div>
            {/* ⚠ **THERE ARE TWO LANGUAGES AND THIS PANEL NAMED ONE**
                (CR-085 group I, the drawing's screen 59: *"There are two, and
                they can differ — which is usually not what anyone
                intends."*). The control above sets the language a BILL and a
                shut-off notice arrive in; this line names the one the reader
                is looking at right now, so the two cannot be mistaken for one
                setting.
                ⚠ **AND THE SENTENCE UNDERNEATH SAID SOMETHING THAT WAS NOT
                TRUE, WHICH IS A DEFECT AND NOT A DESIGN DIFFERENCE
                (`DEF-CWP-4935`).** It read *"Your bills and letters use the
                language above; this site follows it."* — i.e. the product
                asserting the two CANNOT differ. **PO ruling 2026-09-11,
                verbatim: *"(b) Allow them to differ - currently bills are
                offered only in english"*.** The second half is the fact that
                settles it: the website ships in ELEVEN languages and the bill
                in ONE, so the two already differ for every customer who reads
                this screen in anything but English, and the old sentence was
                telling them otherwise. It now says what is true — bills go out
                in English today, and this site follows the choice above.
                ⚠ **IT IS STILL A STATEMENT AND NOT A SECOND PICKER, AND THAT
                IS `BR-CWP-105` RATHER THAN A SHORTCUT.** The PO ruled the
                order on 2026-09-07 — the account's own preference comes FIRST
                — so `PortalLanguage` re-applies the account language on every
                render and a website picker offered here would revert under the
                customer's hand on any account that states one. A control that
                undoes itself is hard-won law 2's mirror. The 2026-09-11 ruling
                permits the two to differ; it does NOT reverse 2026-09-07's
                order, so the drawn *make my bills Spanish too* banner and the
                drawn second picker still need a screen that can hold a website
                choice without it being overwritten. **That is a build and
                not a sentence, and this commit does not attempt it** — it is
                recorded as the open half of delta `P-09` in
                `04-docs/05-modules/15-portal/conformance/CR-085-lane4-05-step2-after.md`.
                ⚠ **NAMED IN ITS OWN LANGUAGE** (B14 rule 35) — `languageName`
                is the kit's one answer, the same one the picker above uses. */}
            <p className="mt-3 text-body text-neutral-700" data-website-language={reading}>
              {t("portal.preferences.websiteLanguage")}: {languageName(reading)}
            </p>
            <p className="mt-1 text-base text-neutral-600">
              {t("portal.preferences.websiteLanguageWhy")}
            </p>
          </Panel>
        }
      />
    </div>
  );
}

/** `2025-09-21` → `21 Sep 2025`, in the reader's own locale. */
export function onDate(iso: string | null, locale: string): string {
  if (iso === null) return "—";
  return new Date(`${iso}T00:00:00Z`).toLocaleDateString(locale, {
    day: "numeric",
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  });
}
