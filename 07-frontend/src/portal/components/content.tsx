// ── Trace ──────────────────────────────────────────────
// Story:    US-CWP-072 (EP-CWP-12) — help on the portal · US-CWP-073 — the tip
//           slot · US-CWP-074 — where you can walk in.
//           Screens: CWP-011 · CWP-060 · CWP-013 · CWP-014 (and the signed-in
//           slots CWP-059 · CWP-061 · CWP-062, which land in wave H reusing
//           `TipBar` and `AttachedAnswerCard` from here — defined ONCE)
// Rules:    09-component-inventory.md (`Panel` — the KIT's since DEF-CWP-3655
//           — `StatusChip`, `CentreCard`,
//           `TipBar`, `AttachedAnswerCard`) · B14 rule 21 (Tailwind utilities;
//           `portal/` is a directory entry on route-b-migrated.txt) · rule 31
//           (no id is a visible value) · rule 32 (one sentence per section) ·
//           rule 35 (⚠ **NO SENTENCE IS ASSEMBLED FROM ENGLISH GRAMMAR HERE** —
//           see `centreStatusLine` below) · BR-CWP-093 (nothing empty appears)
// Tests:    src/portal/guest/HelpPage.test.tsx · CentresPage.test.tsx
// ───────────────────────────────────────────────────────
//
// ⚠ EVERY CLASS HERE WAS ASKED OF THE COMPILER. This theme clears Tailwind's
// stock palette (`src/styles/tailwind.css`), so `bg-white`, `text-lg` and every
// `slate` shade compile to NOTHING while `tsc` and every `toContain` pass
// (DEF-974). The portal writes the theme's own names — `bg-[white]`,
// `text-neutral-*`, `text-body`, `text-lead` — and the walkthrough reads
// computed style so the next lane cannot lose this quietly.

import type { TFunction } from "i18next";

import { Button } from "@/components/Button";

import type { PortalCentre, PortalCentreToday, PortalTip } from "../api/guestClient";
import { StatusChip } from "./primitives";

/* ⚠ **`Panel` AND `Chip` USED TO BE DECLARED HERE — `DEF-CWP-3655`, B14 rule
 * 36.** This file exported a bordered `Panel` with three border tones and a
 * header row, and a `Chip` whose own comment admitted what it was: *"the guest
 * surface's status chip — the staff kit's tones, its own markup."* Both now
 * come from the one place they belong:
 *
 *   `Panel`  → `@/components/Panel`, which gained `trailing` and `tone` to
 *              hold what this one did (and `as="aside"` for the rail).
 *   `Chip`   → `StatusChip` in `./primitives`, which wraps the kit's
 *              `StatusPill` — six tones whose contrast against each fill was
 *              MEASURED (`DEF-722`) rather than picked here for the fourth time.
 *
 * Nothing was redrawn. Two names were deleted and their call sites now name a
 * component that already existed.
 */

/* ⚠ **`TwoCol` USED TO BE DECLARED HERE TOO — `DEF-CWP-3984`, B14 rule 36.**
 * A second twelve-column main-and-rail grid under the same name as
 * `./primitives`'s, one directory away, exactly as `Panel` and `Chip` were
 * before `DEF-CWP-3655`. They agreed on the grid and differed in one place:
 * THIS one gapped the main column and the other did not.
 *
 * The survivor is `./primitives`'s — it is the portal kit's home and had
 * twenty-seven callers to this file's two — and it took THIS one's behaviour
 * with it, because the gap was the correct half. Nothing was redrawn; a name
 * was deleted and two call sites now import the one that remains.
 */

// ══ The clock, in the reader's own language ════════════════════════════════
//
// ⚠ **B14 RULE 35 IS THE WHOLE REASON THESE TWO FUNCTIONS EXIST.** The server
// sends a weekday NUMBER and an `HH:MM`; if it sent *"Opens Thursday at
// 9:00am"* the other ten catalogues would be a word-for-word translation of an
// English sentence, which is exactly what the rule forbids. So the day name
// and the clock are produced by `Intl` in the reader's own language — a
// Japanese reader gets 午前9:00, a French one 09:00 — and the catalogue holds
// the FRAME (*"Opens {{day}} at {{time}}"*), written natively in each of the
// eleven.

/** `"09:00"` → the reader's own clock. */
export function clockText(hhmm: string | null, language: string): string {
  if (!hhmm) return "";
  const [hour, minute] = hhmm.split(":").map((part) => Number(part));
  const when = new Date(2000, 0, 1, hour, minute);
  const text = new Intl.DateTimeFormat(language, { hour: "numeric", minute: "2-digit" }).format(when);
  // English reads *9:00am* on the prototype's own screens, not *9:00 AM*.
  return /\s?(AM|PM)$/i.test(text) ? text.replace(/\s?(AM|PM)$/i, (m) => m.trim().toLowerCase()) : text;
}

/** Monday = 0 … Sunday = 6 → the day's name in the reader's language. */
export function weekdayText(day: number, language: string): string {
  // 2024-01-01 was a Monday, so `1 + day` lands on the wanted weekday.
  const when = new Date(2024, 0, 1 + day);
  return new Intl.DateTimeFormat(language, { weekday: "long" }).format(when);
}

/**
 * `"2025-09-21"` → *21 Sep 2025*, in the reader's own locale.
 *
 * ⚠ **THE ONE DATE HELPER FOR THE SIGNED-IN PORTAL, BECAUSE THERE WERE TWO AND
 * THREE SCREENS USED NEITHER (`DEF-CWP-4131`).** `dayMonthText` above drops the
 * year, which is right for an opening time and wrong for *taken on 4 March
 * 2021*; `Preferences.tsx` had grown its own private copy of this one. Five
 * wave-F screens meanwhile interpolated the RAW ISO string straight into a
 * correct catalogue frame, so a customer read *Issued 2026-08-02* where every
 * wireframe in the wave draws *Issued 30 Aug*.
 *
 * **B14 rule 35 is why this is a rule and not a preference**: a catalogue is
 * written in its own language, and `2026-08-02` is no human's language. The
 * FRAME stays in the catalogue (*"Issued {{date}}"*, written natively in each
 * of the eleven) and `Intl` produces the date itself, so a Japanese reader gets
 * 2025年9月21日 without any catalogue being a word-for-word translation of an
 * English one.
 *
 * ⚠ **`timeZone: "UTC"` IS LOAD-BEARING.** These are DATES, not timestamps.
 * Parsed as local time, `2026-09-01` renders as *31 Aug* for every reader west
 * of Greenwich — a bill dated the day before it was issued.
 */
export function onDate(iso: string | null | undefined, language: string): string {
  if (!iso) return "";
  return new Date(`${iso}T00:00:00Z`).toLocaleDateString(language, {
    day: "numeric",
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  });
}

/** `"2026-11-26"` → *26 November* / *November 26* / *11月26日*, natively. */
export function dayMonthText(iso: string, language: string): string {
  const [year, month, day] = iso.split("-").map((part) => Number(part));
  return new Intl.DateTimeFormat(language, { day: "numeric", month: "long" }).format(
    new Date(year, month - 1, day),
  );
}

/**
 * The one line under a centre's name. ⚠ Assembled from a CATALOGUE FRAME and
 * `Intl`, never from English word order — and the holiday branch comes first
 * because *"closed today"* with no reason is the answer that sends somebody to
 * a locked door wondering.
 */
export function centreStatusLine(today: PortalCentreToday, t: TFunction, language: string): string {
  if (today.is_open_now) {
    return t("portal.centre.openUntil", { time: clockText(today.closes_at, language) });
  }
  const parts: string[] = [];
  if (today.closed_for_holiday) {
    parts.push(
      t("portal.centre.closedForHoliday", { label: today.closed_for_holiday.label }),
    );
  } else {
    parts.push(t("portal.centre.closedToday"));
  }
  if (today.opens_later_today && today.next_open_at) {
    parts.push(t("portal.centre.opensTodayAt", { time: clockText(today.next_open_at, language) }));
  } else if (today.next_open_weekday !== null && today.next_open_at) {
    parts.push(
      t("portal.centre.opensDayAt", {
        day: weekdayText(today.next_open_weekday, language),
        time: clockText(today.next_open_at, language),
      }),
    );
  }
  return parts.join(" · ");
}

/**
 * ONE tip, or nothing at all. ⚠ `tip === null` renders NOTHING — not a frame,
 * not a placeholder, not an older tip: the slot closes up and nobody can tell
 * it was there (`BR-CWP-095`, `US-CWP-073` TC-3). Defined here once; wave H's
 * signed-in screens import this exact component.
 */
export function TipBar(props: {
  tip: PortalTip | null;
  kicker?: string;
  onDismiss?: () => void;
  dismissLabel?: string;
}) {
  if (props.tip === null) return null;
  return (
    <aside
      // ⚠ **THE BRAND LEFT RULE AND THE WHITE GROUND ARE THE DRAWING'S**
      // (`08-screen-layouts.md` `CWP-062`: *"brand left rule · kicker TIP in
      // brand · … · ×"*). It was `border-info-700 bg-info-100` — a blue
      // notice, which is the shape of a system message rather than of the
      // utility talking to its own customer.
      //
      // ⚠ **`border-l-accent`, NEVER `border-l-[var(--brand)]`**, which is
      // what the inventory's prose says: `--brand` is a variable this product
      // sets NOWHERE and every rule that read it painted grey
      // (`DEF-CWP-3736`). The tenant's hex arrives as an override of
      // `--color-accent` on the portal frame.
      //
      // ⚠ The two border utilities COMPOSE rather than race, and that is
      // checked rather than assumed: `border`/`border-l-4` are
      // `border-width`/`border-left-width` and `border-neutral-200`/
      // `border-l-accent` are `border-color`/`border-left-color` — different
      // properties, so neither is a coin toss decided at build time (the trap
      // `Panel.tsx` records for its own tone slot).
      className="mb-4 flex items-start gap-3 border border-neutral-200 border-l-4 border-l-accent bg-[white] px-4 py-3 text-body"
      data-tip-bar={props.tip.target_screen}
    >
      {/* ⚠ **A WORD FROM THE CATALOGUE, NOT A GLYPH** (B14 rule 35). This was
          a bare `i`, which is a letter in one alphabet and a decoration in the
          other ten. The drawing asks for the kicker **TIP** in brand; absent,
          nothing is drawn rather than a fallback English word. */}
      {props.kicker ? (
        <span
          className="shrink-0 text-xs font-bold uppercase tracking-wide text-accent-text"
          data-tip-kicker=""
        >
          {props.kicker}
        </span>
      ) : null}
      <p className="min-w-0 flex-1 text-neutral-700">{props.tip.text}</p>
      {props.onDismiss ? (
        // ⚠ THE KIT'S BUTTON, NOT A BOX THIS FILE DREW (B14 rule 36 · `G86`).
        // It was `border border-neutral-300 px-2 py-1 text-base` — a fourth
        // opinion about what a small button looks like, three directories away
        // from `buttonKit.ts`, which holds the only one. The guest surface is
        // the surface with the least excuse for its own button.
        <Button size="sm" className="shrink-0" onClick={props.onDismiss} data-tip-dismiss="">
          {props.dismissLabel}
        </Button>
      ) : null}
    </aside>
  );
}

/**
 * The same answer where the question is asked (`also_show_on_screen`). ⚠ The
 * utility wrote it ONCE; this is the second placement, not a second row.
 * `answer === null` renders nothing.
 */
export function AttachedAnswerCard(props: {
  question: string;
  body: string;
  readMoreLabel: string;
  href: string;
  whyLabel: string;
}) {
  return (
    <section className="border border-neutral-200 bg-[white] p-4" data-attached-answer="">
      <h2 className="text-lead font-bold text-neutral-900">{props.question}</h2>
      <p className="mt-2 text-body leading-relaxed text-neutral-700">{props.body}</p>
      <a className="mt-3 inline-block text-body font-semibold text-accent-text" href={props.href}>
        {props.readMoreLabel}
      </a>
      <p className="mt-2 text-base text-neutral-600">{props.whyLabel}</p>
    </section>
  );
}

/**
 * One centre on `CWP-013`. ⚠ **`Not here:` IS DRAWN, NOT OMITTED** — a list of
 * what a place can do is a brochure; a list that also shows what it cannot do
 * saves somebody a wasted journey (`US-CWP-074` §1).
 */
export function CentreCard(props: {
  centre: PortalCentre;
  t: TFunction;
  language: string;
  href: string;
}) {
  const { centre, t, language } = props;
  const open = centre.today.is_open_now;
  return (
    <section className="border border-neutral-200 bg-[white]" data-centre={centre.slug}>
      <header className="flex items-center justify-between gap-3 border-b border-neutral-200 px-4 py-3">
        <h2 className="text-lead font-bold text-neutral-900">{centre.name}</h2>
        <a
          className="text-body font-semibold text-accent-text"
          href={props.href}
          data-centre-link={centre.slug}
          // DEF-CWP-10566: every card's link read "See this center"; it is named for its centre.
          aria-label={t("portal.actionName", { label: t("portal.centre.seeThis"), value: centre.name })}
        >
          {t("portal.centre.seeThis")}
        </a>
      </header>
      <div className="flex flex-col gap-3 p-4 text-body text-neutral-700">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <p className="font-bold text-neutral-900">{centre.address}</p>
          <StatusChip tone={open ? "success" : "neutral"} testKey={open ? "open" : "closed"}>
            {open ? t("portal.centre.openNow") : t("portal.centre.closedNow")}
          </StatusChip>
        </div>
        {/* ⚠ **THE UTILITY WROTE THIS AND NOTHING DREW IT** (`CR-085`,
            2026-09-08). `directions_note` has been on the wire, on
            `PortalCentre`, and in this screen's own test FIXTURE since wave D
            — *"Parking behind the building, off the alley."* — and no
            component in the portal rendered it, on either centre screen. The
            drawing asks for exactly this before somebody sets out: *"Parking
            and step-free access are facts somebody needs before setting out,
            not afterwards."*

            ⚠ **NO HEADING AND NO NEW CATALOGUE KEY.** It is the utility's own
            sentence in the utility's own words (B14 rule 35 is satisfied by
            not translating it at all), and a label over one sentence is the
            *description budget* rule 32 exists to protect. Absent when unset —
            never an empty line under the address. */}
        {centre.directions_note ? (
          <p className="text-neutral-600" data-directions-note={centre.slug}>
            {centre.directions_note}
          </p>
        ) : null}
        {centre.phone ? <p>{centre.phone}</p> : null}
        <p className="text-neutral-600" data-centre-status={centre.slug}>
          {centreStatusLine(centre.today, t, language)}
        </p>
        <hr className="border-neutral-200" />
        <p className="text-xs font-bold uppercase tracking-wide text-neutral-900">
          {t("portal.centre.youCanHere")}
        </p>
        <ul className="flex flex-wrap gap-2">
          {centre.allowed_actions.map((action) => (
            <li key={action} className="border border-neutral-300 px-2 py-1 text-base font-semibold text-neutral-700">
              {t(`portal.centre.action.${action}`)}
            </li>
          ))}
        </ul>
        {centre.cannot_do.length > 0 ? (
          <p className="text-neutral-600" data-centre-cannot={centre.slug}>
            <span className="font-bold text-neutral-900">{t("portal.centre.notHere")}</span>{" "}
            {centre.cannot_do.map((action) => t(`portal.centre.action.${action}`)).join(" · ")}
          </p>
        ) : null}
        {centre.payment_methods_accepted.length > 0 ? (
          <p className="text-neutral-600">
            <span className="font-bold text-neutral-900">{t("portal.centre.takes")}</span>{" "}
            {centre.payment_methods_accepted.map((one) => t(`portal.centre.method.${one}`)).join(" · ")}
          </p>
        ) : null}
      </div>
    </section>
  );
}
