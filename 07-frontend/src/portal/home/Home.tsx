// ── Trace ──────────────────────────────────────────────
// Story:    US-CWP-024 (the lead tile, wave E) · US-CWP-025 (the rest of the
//           page, wave F). Screen: CWP-022
// Rules:    BR-CWP-047 (re-read on every load; no portal screen caches a
//           balance) · BR-CWP-015 (balances shown SEPARATELY and totalled for
//           information, never merged) · BR-CWP-093 (nothing empty ever
//           appears) · BR-CWP-095 (one tip, on and in season; no tip ⇒ no
//           slot) · BR-BIL-036 (print is the FLOOR — paperless ADDS email) ·
//           CLAUDE.md hard rule 2 (4 dp stored, DISPLAY 2) · hard rule 3
//           (consumption ALWAYS with its unit) · B14 rule 15 (row actions are
//           icons) · rule 17 · rule 20 (one table type) · rule 21 · rule 31
//           (no database id is ever the visible value of a field) · rule 32
//           (one sentence per section) · rule 35 · rule 36 (compose the kit)
// Tests:    src/portal/home/Home.dom.test.tsx ·
//           10-scripts/render-checks/cr068-f-home-accounts-details.mjs
// Defects:  DEF-CWP-3766 — this line cited `Home.test.tsx` from the day the
//           tile shipped and that file has never existed. G95 refuses the
//           shape now; the test beside it is the citation made true.
//           DEF-CWP-3965 — the whole page was a stack of hand-built cards.
// Impacts:  src/portal/api/portalClient.ts `getHome` ·
//           src/portal/components/primitives.tsx `KpiRow` · `KpiTile`
// ───────────────────────────────────────────────────────
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import { useAnnounce } from "../components/a11y";
import {
  Card,
  ErrandLink,
  KpiRow,
  KpiTile,
  KVList,
  NamedGaps,
  SectionTitle,
  SelectInput,
  shortMonthText,
  StatusChip,
  TwoCol,
  UsageBars,
  usePortalPath,
  type ChipTone,
  type UsageBar,
} from "../components/primitives";
import { TipBar, onDate } from "../components/content";
import { PortalScreen, PortalState } from "../components/states";
import { EyeIcon, PrinterIcon } from "@/components/icons";
import { formatQuantity } from "@/components/UnitCell";
import { Panel } from "@/components/Panel";
import { formatMoney } from "../signin/Enrol";
import { getHome, type HomeBill, type HomeIdentity, type HomeServiceFact, type PortalHome } from "../api/portalClient";

/** Whole days from `today` to `iso`, or null. A date, never a timestamp. */
export function daysUntil(iso: string | null, today: Date): number | null {
  if (!iso) return null;
  const due = new Date(`${iso}T00:00:00Z`);
  const now = new Date(Date.UTC(today.getUTCFullYear(), today.getUTCMonth(), today.getUTCDate()));
  return Math.round((due.getTime() - now.getTime()) / 86_400_000);
}

/** `state` → the chip's tone. ⚠ **THE SAME MAP `CWP-027` PAINTS FROM**, because
 *  it is the same `_bill_state` on the server: a home page with its own opinion
 *  about which bills are overdue is two answers to one question, one tab
 *  apart. */
const BILL_TONE: Record<string, ChipTone> = {
  paid: "success",
  due: "warning",
  part_paid: "info",
  overdue: "danger",
  corrected: "neutral",
};

/**
 * `CWP-022` — *do I owe anything and by when*, above everything else.
 *
 * ⚠ **THE SHAPE IS `08-screen-layouts.md`'s AND IT WAS NOT, UNTIL 2026-09-05
 * (`DEF-CWP-3965`).** The Product Owner signed in and said *"the UI is not as
 * per agreement"*. The screen drew one wide *WHAT YOU OWE* card, an attention
 * card whose entire content was the bare text `Pay $155.45`, two stacked money
 * cards and a list of bills — **and no right rail at all**, so the twelve-month
 * chart, the service summary and the instalments panel were simply absent.
 * Every figure on it was correct; the SHAPE was not, and **no check in this
 * repository reads rendered output** (hard-won law 6), so `tsc`, 391 portal
 * cases and every gate passed over it.
 *
 * The layout it draws now, region for region:
 *
 *     KpiRow ×4  BALANCE (lead) · LAST BILL · LAST PAYMENT · <service> THIS MONTH
 *     TwoCol     main [ NEEDS YOUR ATTENTION · RECENT BILLS ]
 *                rail [ TWELVE MONTHS OF … · YOUR SERVICE · PAYING BY INSTALMENTS? ]
 *
 * ⚠ **NOTHING BELOW IS DRAWN OUT OF RAW UTILITIES.** `TwoCol` was already used
 * by 28 portal screens and `KVList` by 23, and this screen used neither. The one
 * piece the kit genuinely lacked — the balance strip — was ADDED TO THE KIT,
 * which is B14 rule 36's own mechanism and the reason `CWP-033` and `CWP-066`
 * will not each grow a fourth one.
 *
 * ⚠ **RE-READ ON EVERY MOUNT, NEVER CACHED** (`BR-CWP-047`). There is no
 * `useQuery` with a stale time here and there must not be one: *a credit that
 * was real on Tuesday can be spent by Thursday.* The server sends `no-store`
 * as well — both halves, because either alone is one refactor from being lost.
 *
 * ⚠ **THE LEAD TILE CARRIES THE TOTAL AND THE ROWS LIVE ON `CWP-023`, WHICH IS
 * WHAT `BR-CWP-015` ASKS FOR RATHER THAN A NARROWING OF IT.** The rule says
 * balances are shown *separately and totalled for information*, and
 * `US-CWP-024`'s own acceptance places that presentation on **the accounts
 * screen** — *"when the accounts screen loads, then it shows four rows
 * totalling $872.82 without merging them"*. `MyAccounts.tsx` draws exactly
 * that, with nothing beside the total to press. Home is the thirty-second
 * answer: one figure, its date, and a door to the rows for the landlord who
 * needs them. Four rows were drawn here as well until 2026-09-05 and the
 * layout has no room for them beside a `KpiRow`.
 *
 * ⚠ **EVERY PANEL BELOW CAN BE ABSENT, AND ABSENT IS RENDERED AS NOTHING**
 * (`BR-CWP-093`): no attention items ⇒ no panel, no tip ⇒ no slot, no measured
 * service ⇒ no usage tile **and no empty chart**, no bill yet ⇒ no bill tile
 * rather than a `$0.00` that says *you were billed nothing*.
 *
 * ⚠ **THE TWELVE-MONTH CHART IS DRAWN HERE NOW, AND THE COMMENT THAT SAID IT
 * SHOULD NOT BE IS SUPERSEDED (hard-won law 1).** It argued that `CWP-033` is
 * one tab away and a second chart would be a second place to look. That is a
 * reasonable product argument and it is not this lane's to make: the signed
 * layout draws a `ChartPanel` in the rail, the PO read the screen against that
 * layout, and `usage_series` was already coming down with the page. `UsageBars`
 * is the kit's chart (added by `CR-068` wave H) and this composes it.
 */
export function HomeView(props: { today?: Date }) {
  const { t, i18n } = useTranslation();
  const path = usePortalPath();
  const [data, setData] = useState<PortalHome | null>(null);
  const [failed, setFailed] = useState(false);
  /** ⚠ **A COUNTER, BECAUSE R-10's WAY OUT HAS TO ACTUALLY DO SOMETHING.**
   *  `PortalState` can carry a control and its own docstring says why it does
   *  not require one: a `Try again` wired to nothing is `EmptyList`'s
   *  `onCta: () => undefined` defect (`DEF-MET-4764`). Bumping this re-runs the
   *  effect below, which is the only read this screen makes, so the button
   *  re-reads the balance rather than looking as though it did. */
  const [attempt, setAttempt] = useState(0);
  /** The tip's `×` lasts the visit — see `Usage.tsx` for why nothing
   *  remembers it (decision log 2026-09-05). */
  const [tipShown, setTipShown] = useState(true);

  useEffect(() => {
    let live = true;
    setFailed(false);
    getHome()
      .then((answer) => {
        if (live) setData(answer);
      })
      .catch(() => {
        if (live) setFailed(true);
      });
    return () => {
      live = false;
    };
  }, [attempt]);

  // ⚠ **THREE STATES, THREE SENTENCES, AND THE CARD SAYS WHICH ONE IT IS —
  // R-22 (PO 2026-09-11, verbatim: *"differntiate it using text message"*).**
  // This screen drew a bare `Card` with one grey line for failed, for loading
  // and — one level down — for empty. The three SENTENCES already differed;
  // what was missing is that nothing in the DOM said which state it was, so
  // the rule was unobservable by anything but a person reading the words, and
  // the loading branch carried no `data-screen="CWP-022"` at all — every
  // rendered check in this repo selects on that mark, so a slow or failed read
  // made this screen invisible to all of them.
  //
  // ⚠ **AND NO PAGE TITLE IS ADDED HERE, DELIBERATELY.** `PortalScreen` takes
  // the head as a `ReactNode` and this screen's is `null`: the drawing
  // (blueprint screen 25) opens on the account line and then **AMOUNT DUE**,
  // and `pageHeadCensus.test.ts` records `CWP-022` in `CORRECTLY_HEADLESS`
  // with the reason — *"a title above it would push the one figure the page
  // exists for below the fold"*. `DEF-CWP-4000` counted this screen as
  // headless and it is headless ON PURPOSE; what was actually missing is the
  // `data-screen` mark, which is what this fixes.
  if (failed) {
    return (
      <PortalScreen screen="CWP-022" head={<HomeHeading />}>
        <PortalState
          kind="failed"
          testId="home-balance"
          sentence={t("portal.home.couldNotRead")}
          // ⚠ **R-10, LITERALLY** (PO 2026-09-11): *"when a screen tells a
          // customer something bad, the thing they can do about it must be on
          // that same screen, next to the message."* The drawing also asks
          // this state to offer the telephone number; `getHome` does not carry
          // one and the frame's front payload is not threaded into this view,
          // so the number is NOT invented here — recorded as still-open on
          // `DEF-CWP-4906` rather than faked (R-23).
          waysOut={[
            {
              label: t("portal.payNow.tryAgain"),
              onClick: () => setAttempt((n) => n + 1),
              tone: "primary",
              testKey: "home-retry",
            },
          ]}
        />
      </PortalScreen>
    );
  }
  if (!data) {
    return (
      <PortalScreen screen="CWP-022" head={<HomeHeading />}>
        <PortalState kind="loading" testId="home-balance" sentence={t("portal.home.reading")} />
      </PortalScreen>
    );
  }

  const today = props.today ?? new Date();
  const summary = data.balances;
  const rows = summary.accounts;
  const many = rows.length > 1;
  // The householder's own row carries the due date; a landlord's set has four
  // of them, so the tile names the count instead and the dates sit on CWP-023.
  const only = rows.length === 1 ? rows[0] : null;
  const days = daysUntil(only?.due_on ?? null, today);
  //: The figure the lead tile prints, as a NUMBER, so the *nothing due* branch
  //: below asks the same question the tile answers rather than a second one.
  const owingNow = Number(summary.total_owing ?? only?.owing ?? "0");

  return (
    // ⚠ **THE ID IS WRITTEN OUT HERE, AS A LITERAL, AND THAT IS NOT A STYLE
    // CHOICE** (`DEF-CWP-4936`, lane 8's open row; `bills/BillDetail.tsx` does
    // the same and for the same reason).
    //
    // `PortalScreen` renders exactly `<div data-screen={screen} className={…}>`,
    // so passing the id as a PROP produces an identical DOM and every rendered
    // check still finds this screen in a browser. **Three SOURCE scanners do
    // not run a browser**: they read the file and look for the string
    // `data-screen="CWP-…"`. To them a screen with no literal is not an
    // unknown screen, it is *the frame* — and `g100_every_screen_has_a_door`
    // then credits this file's doors to EVERY node in the portal, which is the
    // opposite of what that gate exists to prove.
    //
    // ⚠ **THIS FILE WAS THE WORST CASE IN THE PORTAL WHILE IT LASTED: NINE
    // DOORS, more than `PortalShell` (7) or `GuestFrame` (8) — the two actual
    // frames.** It was not caught by counting, because `grep -c 'data-screen'`
    // returns 1 for the sentence two hundred lines above that *describes* the
    // mark. A count that does not say what it counted is not a measurement.
    //
    // The loading and failed branches keep `PortalScreen`: one literal per
    // screen is what the scanners need, and the frame still owns the rest.
    <div data-screen="CWP-022" className="flex flex-col gap-4">
      <HomeHeading />
      {/* `BR-CWP-095` — at most one tip, on and in season, and the slot sits
          BETWEEN THE TAB STRIP AND THE TILES (`08-screen-layouts.md`). It was
          drawn at the foot of the page until 2026-09-05, which is the one place
          a customer leaving in thirty seconds never reaches. `null` closes it up
          so completely that nobody can tell it was there. */}
      {/* ⚠ **THE KIT'S `TipBar`, NOT A SECOND ONE** (`DEF-CWP-3985`, B14 rule
          36) — this screen and `CWP-033` had each drawn their own, so the
          product carried three tip bars and the drawn one was rendered by
          nobody. ⚠ **AND BOTH COPIES RENDERED AN EMPTY BOX** (`DEF-CWP-3998`):
          they read `tip.body ?? tip.title` and the server sends `text`. */}
      {tipShown ? (
        <TipBar
          tip={data.tip}
          kicker={t("portal.tip.kicker")}
          dismissLabel={t("portal.tip.dismiss")}
          onDismiss={() => setTipShown(false)}
        />
      ) : null}

      {/* ⚠ **THE ACCOUNT CARD, AND WHERE IT SITS IS THE WHOLE ARGUMENT.**
          The Product Owner signed in on 2026-09-08 and said the home page had
          no identifier on it at all — *"we are not displaying account # of
          Customer nmae - ther eis no identifier"*. This screen's OWN question
          is still *what do I owe*, so the money must not go below the fold to
          make room: on a WIDE screen the card is a band above the tiles, and
          on a PHONE it sits BELOW them. Where space is scarce the money wins
          and the identity is one scroll away.

          ⚠ **`max-md:` AND NEVER `md:`** — `tailwind.css` clears Tailwind's
          min-width namespace, so `md:order-1` compiles to NOTHING while `tsc`,
          eslint and every `toContain` assertion pass on it (`DEF-CWP-4004`),
          and `G107` refuses the min-width form. The phone rule is the
          override; the wide layout is the base. */}
      <div className="flex flex-col gap-4">
        <div className="max-md:order-2">
          <AccountCard identity={data.identity} service={data.service} />
        </div>
        <div className="max-md:order-1">
        {rows.length === 0 ? (
          // ⚠ **THE THIRD OF R-22's THREE, AND IT WAS THE SAME PICTURE AS THE
          // OTHER TWO.** B14 rule 17 asks for an empty state that says what
          // will fill it; the sentence already did, and it was a DEAD sentence
          // — *Add an account and your balance appears here.* with nothing to
          // press, on a screen whose only door to `/accounts/add` is two
          // clicks away. R-10 is the rule that closes that: the way out sits
          // next to the message.
          <PortalState
            kind="empty"
            testId="home-balance"
            sentence={t("portal.home.noAccountsYet")}
            waysOut={[
              {
                label: t("portal.addAccount.title"),
                to: path("/accounts/add"),
                tone: "primary",
                testKey: "home-add-account",
              },
            ]}
          />
        ) : (
          <KpiRow>
            <KpiTile
              lead
              testKey="balance"
              // ⚠ **AN EXISTING CATALOGUE KEY, NOT A NEW ONE** (B14 rule 35,
              // the same call this file already makes for
              // `portal.yourAccount.title` and `portal.documents.kind.bill`).
              // `portal.accounts.colBalance` is *Balance* in all eleven and is
              // this same figure's heading on `CWP-023`, one screen over. The
              // word does NOT become *What you owe* here: R-05 (*amount due in
              // the same place on every screen*) is a PROPOSAL and unratified,
              // so the divergence with `/account` is recorded on the lane's
              // conformance file rather than unified on a lane's own authority.
              label={t("portal.accounts.colBalance")}
              value={
                <span data-owing="">
                  {formatMoney(summary.total_owing ?? only?.owing ?? "0", summary.currency)}
                </span>
              }
              sub={
                many ? (
                  // ⚠ **A DOOR, NOT A DEAD SENTENCE.** A landlord's four balances
                  // are four facts and this tile shows their total; `CWP-023` is
                  // where the rows are, and it is live (`DEF-CWP-3954` is what a
                  // screen with no door into it costs).
                  <Link
                    to={path("/accounts")}
                    className="text-neutral-600 underline"
                    data-home-accounts-door=""
                  >
                    {/* ⚠ The catalogues carry `_one` and `_other`; this door is
                        only drawn for two accounts or more, so the plural is the
                        only form that can reach a reader here. */}
                    {t("portal.home.acrossAccounts", { count: rows.length })}
                  </Link>
                ) : only?.due_on ? (
                  <span data-due="">
                    {t("portal.home.due", { date: onDate(only.due_on, i18n.language) })}
                    {days !== null && days >= 0
                      ? ` · ${t("portal.home.inDays", { count: days })}`
                      : ""}
                  </span>
                ) : owingNow <= 0 ? (
                  // ⚠ **THE DRAWN *NOTHING DUE* STATE, WHICH WAS A BARE FIGURE.**
                  // The drawing is explicit — *"'You are all paid up.' with the
                  // next bill date. **Not an empty card.**"* — and this tile
                  // printed `$0.00` with no sub-line at all, which reads as a
                  // read that returned nothing rather than as good news.
                  //
                  // ⚠ **AND THE NEXT BILL DATE IS NOT DRAWN HERE, BECAUSE THE
                  // PAYLOAD HAS NO SUCH FIELD.** `getHome` carries the LAST
                  // bill, never the next one, so the date is stated nowhere
                  // rather than computed from a cycle this screen cannot see
                  // (R-23 — no sentence states a fact it does not derive). The
                  // missing half is recorded on `DEF-CWP-4906`.
                  <span data-home-paid-up="">{t("portal.home.allPaidUp")}</span>
                ) : null
              }
            />
            {data.last_bill ? (
              <KpiTile
                testKey="last-bill"
                label={t("portal.home.lastBill")}
                value={
                  <span data-last-bill="">
                    {formatMoney(data.last_bill.total, data.last_bill.currency)}
                  </span>
                }
                sub={
                  data.last_bill.issued_on
                    ? t("portal.home.billedOn", { date: onDate(data.last_bill.issued_on, i18n.language) })
                    : null
                }
              />
            ) : null}
            {data.last_payment ? (
              <KpiTile
                testKey="last-payment"
                label={t("portal.home.lastPayment")}
                value={
                  <span data-last-payment="">
                    {formatMoney(data.last_payment.amount, data.last_payment.currency)}
                  </span>
                }
                sub={
                  data.last_payment.paid_on
                    ? `${t("portal.home.paidOn", { date: onDate(data.last_payment.paid_on, i18n.language) })}${
                        data.last_payment.method ? ` · ${data.last_payment.method}` : ""
                      }`
                    : null
                }
              />
            ) : null}
            {/* ⚠ ONE TILE PER MEASURED SERVICE, NOT ONE TILE. The layout draws
                *WATER THIS MONTH* because the drawing's customer takes one
                measured service; a customer taking water AND electricity has two
                figures in two units and hard rule 3 forbids a third that adds
                them. `[]` — a trash-only account — draws no tile at all. */}
            {data.usage.map((row) => (
              <KpiTile
                key={`${row.service}-${row.unit}`}
                testKey={`usage-${row.service}`}
                label={t("portal.home.usageThisMonth", {
                  service: t(`rating.service.${row.service}`, { defaultValue: row.service }),
                })}
                value={
                  // ⚠ **`quantity_display`, NOT `quantity` (`DEF-CWP-3770`).** The
                  // stored figure is `NUMERIC(18,6)`, so this read `4820.000000`
                  // on the live product while the DOM test passed on a hand-typed
                  // `"4820"` no server has ever sent.
                  //
                  // ⚠ **AND IT IS GROUPED HERE, NOT ON THE WIRE (`DEF-CWP-4140`).**
                  // The server sent `10700` and the tile printed `10700`, where
                  // the drawing writes *4,820 gal*. Grouping is a READER's
                  // question — a thousands separator is a comma in English, a
                  // full stop in German and absent in Japanese — so it belongs on
                  // the last step before the screen and never in the payload.
                  // `formatQuantity` is the kit's own, already used by
                  // `formatDialFigure`, so this adds no second opinion about how
                  // a number looks (B14 rule 36).
                  <span data-home-usage="">
                    {formatQuantity(String(row.quantity_display ?? row.quantity))}
                  </span>
                }
                unit={row.unit}
              />
            ))}
          </KpiRow>
        )}
        </div>
      </div>


      {/* ⚠ NAMED GAPS, NEVER A SILENTLY WRONG TOTAL — the posture every read in
          `payments` already takes, carried through to the screen. The SENTENCES
          are the kit's, and a gap with no sentence draws nothing: this list used
          to fall back to the server's `detail` and printed module paths and rule
          ids on a customer's home page (`DEF-CWP-3926`). */}
      <NamedGaps problems={summary.problems} mark="data-home-problems" />

      <TwoCol
        main={
          <div className="flex flex-col gap-4">
            {/* ⚠ THE PORTAL'S ONLY PROACTIVE SURFACE, and it is ABSENT when
                there is nothing to act on — not an empty box saying "no items"
                (`BR-CWP-093`). */}
            {data.attention.length > 0 ? (
              <Card testId="home-attention">
                <div className="flex items-start justify-between gap-3">
                  <SectionTitle>{t("portal.home.attention")}</SectionTitle>
                  {/* ⚠ **SHOWN ONLY WHEN THERE IS MORE TO SEE THAN THIS PANEL
                      HOLDS.** The layout draws *View all*; the server sends
                      every item it has, untruncated, so on a one-account login
                      the link would go where the reader already is. A landlord's
                      other accounts are the case where it is true. */}
                  {many ? (
                    <Link
                      to={path("/accounts")}
                      className="text-base font-semibold text-accent-text"
                      data-attention-all=""
                    >
                      {t("portal.home.viewAll")}
                    </Link>
                  ) : null}
                </div>
                <ul className="flex flex-col gap-3" data-home-attention="">
                  {data.attention.map((item, index) => (
                    <li
                      // ⚠ KIND AND POSITION — `high_consumption` comes once per
                      // meter, so the kind alone is not a unique key.
                      key={`${item.kind}-${index}`}
                      className="flex flex-col gap-2 border-b border-neutral-200 pb-3 last:border-b-0 last:pb-0"
                      data-attention={item.kind}
                    >
                      {item.kind === "high_consumption" || item.kind === "high_bill" ? (
                        <HighUsageNotice item={item} />
                      ) : item.kind === "pay" && item.amount ? (
                        <>
                          <div>
                            <StatusChip tone="danger" testKey="attention-pay">
                              {t("portal.home.dueSoon")}
                            </StatusChip>
                          </div>
                          {/* B14 rule 32 — ONE sentence, with the two things a
                              customer acts on in bold: the amount and the day. */}
                          <p className="m-0 text-body text-neutral-700">
                            {only?.due_on
                              ? t("portal.home.paySentenceDated", {
                                  amount: formatMoney(item.amount, item.currency ?? null),
                                  date: onDate(only.due_on, i18n.language),
                                })
                              : t("portal.home.paySentence", {
                                  amount: formatMoney(item.amount, item.currency ?? null),
                                })}
                          </p>
                          <div>
                            <ErrandLink
                              label={t("portal.home.pay", {
                                amount: formatMoney(item.amount, item.currency ?? null),
                              })}
                              to="/pay-now"
                            />
                          </div>
                        </>
                      ) : (
                        <p className="m-0 text-body text-neutral-700">
                          {t(`portal.home.attention.${item.kind}`, { defaultValue: item.kind })}
                        </p>
                      )}
                    </li>
                  ))}
                </ul>
              </Card>
            ) : null}

            {data.recent_bills.length > 0 ? (
              <Card testId="home-recent-bills">
                <div className="flex items-start justify-between gap-3">
                  {/* ⚠ **`portal.documents.kind.bill` IS *Your bill* IN ALL ELEVEN** and is
                      the utility's own word for this same object one screen over. A new
                      `portal.home.yourBill` would render English in nine languages
                      (`G27`'s ratchet, B14 rule 35). */}
                  <SectionTitle>{t("portal.documents.kind.bill")}</SectionTitle>
                  <Link
                    to={path("/bills")}
                    className="text-base font-semibold text-accent-text"
                    data-home-all-bills=""
                  >
                    {t("portal.home.allBills")}
                  </Link>
                </div>
                <div data-home-recent-bills="">
                  <YourBill bills={data.recent_bills} />
                </div>
              </Card>
            ) : null}
          </div>
        }
        rail={
          <>
            {/* ⚠ ONE CHART PER MEASURED SERVICE AND **NO EMPTY CHART**
                (`BR-CWP-073`, `US-CWP-025` TC-5). A trash-only account draws
                nothing here; an axis with no bars on it is the claim we are
                forbidden to make. */}
            <UsageCharts series={data.usage_series} />
            {/* ⚠ **`ServicePanel` IS GONE FROM THE RAIL AND ITS FOUR ROWS ARE
                IN `AccountCard`, WHICH IS A MOVE AND NOT A DELETION.** The
                wireframe draws ONE card that identifies the account —
                *"the answer to 'am I in the right place, and does this look
                like me'"* — and the rail panel was the four-row precursor of
                it. Two cards, one saying *Address · Plan · Billed · Paperless*
                and another saying *name · services · equipment · how we reach
                you*, are one fact split across a page; the Product Owner has
                complained four times that a screen carries more than a person
                will read (B14 rule 32). Every row it drew still draws, in the
                card above. */}
            <Panel as="aside" title={t("portal.home.instalments")}>
              <p className="m-0 text-body leading-relaxed text-neutral-800" data-home-instalments="">
                {t("portal.home.instalmentsBody")}
              </p>
              {/* ⚠ **`/overdue` HAD ONE DOOR IN THE WHOLE PORTAL AND IT WAS ON
                  `CWP-027`** (`DEF-CWP-4652`, `CR-085`, 2026-09-08). This page
                  linked to `/pay-now` and `/ask-for-a-plan` and nothing else,
                  and *overdue* appeared in this file only as a comment and a
                  chip tone. **The customer who is behind LANDS HERE**, and the
                  screen that tells them what happens next — and everything
                  under it, protections included — was two clicks away behind an
                  errand list on another tab. It goes beside *ask for a plan*
                  because a person reading this panel is already the person it
                  is for, and the portal's own rule is that bad news carries the
                  way out with it. Same shape as the accounts door above, and
                  `DEF-CWP-3954` is what leaving it out costs. */}
              <div className="mt-3 flex flex-wrap gap-2">
                <ErrandLink
                  label={t("portal.home.askForPlan")}
                  to="/ask-for-a-plan"
                />
                <ErrandLink label={t("portal.overdue.whereThingsStand")} to="/overdue" />
              </div>
            </Panel>
          </>
        }
      />
    </div>
  );
}

/** The key a chooser row and its bill agree on — the number on the paper where
 *  there is one, and the issue date where there is not (a bill can reach this
 *  screen before it is numbered). Never `id`: there is none on this type, and a
 *  database id is not a thing that appears on screen (B14 rule 31). */
/**
 * `CR-182-BRC10` — the two high-usage notices in *Needs your attention*.
 *
 * PO 2026-10-14, verbatim: *"A1 … when we get high consumption expectation is
 * we will immedately send it high consumption alert to get in portal in app
 * msage or warning"* and, once a bill carries the reading, *"Your last bill is
 * higher than usual · See why →"*.
 *
 *   · `high_consumption` — a reading flagged high (BR-MET-020/120's own flag,
 *     so it is exactly what staff see) and not yet billed. The thing to do is
 *     look at the readings: a leak is something a customer can check.
 *   · `high_bill` — the last bill priced such a reading; *See why* opens that
 *     bill's comparison (`CWP-030`), which is where *why* is answered.
 *
 * B14 rule 33: the chip is a LABEL (three words), the sentence a FACT (six),
 * and nothing says how the utility judges "high" — that is rationale.
 */
/**
 * The page's h1, read by a screen reader and drawn for nobody
 * (`DEF-CWP-10563`; PO/QA 2026-10-23, Group D ruling 2: *"Signed-in Home gets
 * an h1 that is hidden from sight and read by screen readers: "Your account
 * home". Nothing on screen changes."*).
 *
 * ⚠ **HIDDEN, NOT ABSENT, AND THAT KEEPS BOTH RULINGS.** The screen is
 * headless on purpose — `pageHeadCensus.test.ts` records why: a title above it
 * would push the one figure the page exists for below the fold. `sr-only`
 * takes no space, so the drawing is unchanged and the outline gains its h1.
 * It is also what the tab title reads (`PortalDocumentTitle`).
 */
function HomeHeading() {
  const { t } = useTranslation();
  return <h1 className="sr-only">{t("portal.home.pageTitle")}</h1>;
}

function HighUsageNotice(props: { item: PortalHome["attention"][number] }) {
  const { t, i18n } = useTranslation();
  const { item } = props;
  if (item.kind === "high_bill") {
    return (
      <>
        <div>
          <StatusChip tone="warning" testKey="attention-high-bill">
            {t("portal.billDetail.highUsage")}
          </StatusChip>
        </div>
        <p className="m-0 text-body text-neutral-700">{t("portal.home.highUsage.bill")}</p>
        {item.number ? (
          <div>
            <ErrandLink
              label={t("portal.home.highUsage.seeWhy")}
              to={`/bills/${encodeURIComponent(item.number)}/comparison`}
            />
          </div>
        ) : null}
      </>
    );
  }
  const date = item.taken_on ? onDate(item.taken_on, i18n.language) : "";
  return (
    <>
      <div>
        <StatusChip tone="warning" testKey="attention-high-consumption">
          {t("portal.home.highUsage.chip")}
        </StatusChip>
      </div>
      <p className="m-0 text-body text-neutral-700">
        {item.service_name
          ? t("portal.home.highUsage.reading", { service: item.service_name, date })
          : t("portal.home.highUsage.readingNoService", { date })}
      </p>
      <div>
        <ErrandLink label={t("portal.home.highUsage.seeReadings")} to="/readings" />
      </div>
    </>
  );
}

function billKey(bill: HomeBill): string {
  return bill.number ?? String(bill.issued_on ?? "");
}

/**
 * `YourBill` — ONE bill, and a chooser over the last six months.
 *
 * ⚠ **THE CHOOSER IS A PRODUCT OWNER RULING AND NOT A NICETY**, 2026-09-08,
 * verbatim: *"please give me drop down to select last 6 months - on this -
 * August bill · BL-2608-000077"*. The commonest reason to leave the home page
 * is to compare this month with last, and that round trip — bills list, open
 * one, back, open another — is four screens to answer one question.
 *
 * ⚠ **IT REPLACED A THREE-ROW TABLE, WHICH IS A REDESIGN AND NOT A LOSS.**
 * `08-screen-layouts.md` drew *RECENT BILLS* as `Bill / Period / Usage /
 * Amount / Status`; the signed wireframe draws *Your bill* — one bill, its
 * period, its charges and its total, with the chooser above it. The full list
 * is one click away on `CWP-027` and *All bills →* is still beside the
 * heading. What the table could do and this cannot is show three months at
 * once; what this can do and the table could not is show SIX, which is what
 * was asked for.
 *
 * ⚠ **EVERYTHING BELOW THE CHOOSER BELONGS TO THE CHOSEN MONTH.** The bill
 * number, the period, the due date, the usage and the total all follow the
 * selection, so nothing on screen can belong to a different month than the
 * heading says. That is the whole reason the panel redraws in place rather
 * than filtering a table underneath a fixed heading.
 *
 * ⚠ **NO CHOOSER FOR ONE BILL** — *"a chooser with one option is furniture"*,
 * the same rule the account switcher already follows two components away.
 *
 * ⚠ **THE BILL NUMBER IS A LINK AND THE VISIBLE VALUE IS THE NUMBER ON THE
 * PAPER** (B14 rule 31, `DEF-CWP-3954`). Bold text is what `CWP-027` shipped
 * with and it meant a customer could see every bill they had been sent and
 * open none of them.
 *
 * ⚠ **THE ROW ACTIONS ARE ICONS WITH ACCESSIBLE NAMES** (B14 rule 15,
 * `BR-SHL-045`): a title attribute alone is a label a keyboard user never
 * hears.
 */
function YourBill(props: { bills: HomeBill[] }) {
  const { t, i18n } = useTranslation();
  const path = usePortalPath();
  const bills = props.bills;
  const [chosen, setChosen] = useState<string>(billKey(bills[0]));
  // F-04 (`DEF-CWP-10552`): picking another month redraws the panel under the
  // picker; focus stays on it and the month picked is said.
  const say = useAnnounce();
  //: ⚠ **FALL BACK TO THE NEWEST, NEVER TO NOTHING.** The list is re-read on
  //: every mount (`BR-CWP-047`), so a bill can be corrected out from under a
  //: chosen key between two visits; an empty panel would read as a failed load.
  const bill = bills.find((one) => billKey(one) === chosen) ?? bills[0];
  const number = bill.number ?? "";

  const monthLabel = (one: HomeBill): string => {
    const issued = one.issued_on ?? "";
    //: `shortMonthText` is the kit's own month word, from `Intl` rather than
    //: from twelve strings in eleven catalogues (B14 rule 35). A second
    //: formatter here would be a second opinion about what August is called.
    const month = issued.slice(0, 7);
    const year = issued.slice(0, 4);
    return month ? `${shortMonthText(month, i18n.language)} ${year}` : (one.number ?? "");
  };

  const rows = [
    {
      key: "bill",
      // ⚠ **EXISTING KEYS, NOT NEW ONES.** `portal.bills.colBill`,
      // `colCovers`, `colDue`, `portal.tab.usage` and `colAmount` are these same
      // words for this same object elsewhere in the portal, in all eleven
      // languages; minting a `portal.home.*` family would have been forty-four
      // lines saying what the product already says (B14 rule 35).
      // ⚠ **AND BORROWING A KEY MAKES ANOTHER LANE'S RENAME YOUR DEFECT
      // (`DEF-CWP-4940`, found and fixed the same day).** This block asked for
      // `portal.bills.col` + `Period` and + `Usage`, which both existed when it was
      // written. The bills lane renamed the first and deleted the second in
      // `448776e5a` — the very commit this lane then pinned as its tip and
      // re-derived all eleven catalogues from — so Home began printing two raw
      // key strings as column headings. **Re-deriving a blob from the tip
      // protects the FILE and says nothing about the RELATIONSHIP between two
      // files**, which is the half of law 11 that has no command.
      // i18next renders the KEY when the key is missing, so it cannot fail
      // loudly: `tsc` is silent, and every rendering assertion passes because
      // the string IS in the DOM. The case below asserts that no heading in this
      // table starts with `portal.`, so the next rename goes red here.
      label: t("portal.bills.colBill"),
      value:
        number === "" ? (
          <span data-bill="">{t("portal.bills.noNumber")}</span>
        ) : (
          <Link
            to={path(`/bills/${encodeURIComponent(number)}`)}
            className="font-semibold text-neutral-900 no-underline hover:underline"
            data-bill={number}
          >
            {number}
          </Link>
        ),
    },
    bill.period_start && bill.period_end
      ? {
          key: "period",
          label: t("portal.bills.colCovers"),
          value: (
            <span data-bill-period={number}>
              {t("portal.bills.period", {
                from: onDate(bill.period_start, i18n.language),
                to: onDate(bill.period_end, i18n.language),
              })}
            </span>
          ),
        }
      : null,
    bill.due_on
      ? {
          key: "due",
          label: t("portal.bills.colDue"),
          value: <span data-bill-due={number}>{onDate(bill.due_on, i18n.language)}</span>,
        }
      : null,
    //: ⚠ ONE ENTRY PER UNIT, never a sum across units (hard rule 3), and the
    //: row is ABSENT for a bill that charged for no measured quantity — a
    //: base-only bill is not a bill for nothing (`BR-CWP-093`).
    (bill.usage ?? []).length > 0
      ? {
          key: "usage",
          label: t("portal.tab.usage"),
          value: (
            <span className="tabular-nums" data-bill-usage={number}>
              {(bill.usage ?? []).map((one) => `${one.quantity_display} ${one.unit}`).join(" · ")}
            </span>
          ),
        }
      : null,
    {
      key: "amount",
      label: t("portal.bills.colAmount"),
      value: (
        <span className="tabular-nums" data-amount={number}>
          {formatMoney(bill.total, bill.currency)}
        </span>
      ),
    },
  ].filter((row): row is { key: string; label: string; value: JSX.Element } => row !== null);

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <span className="text-lead font-bold text-neutral-900" data-bill-heading="">
          {monthLabel(bill)} · {formatMoney(bill.total, bill.currency)}
        </span>
        <span className="flex items-center gap-2">
          {bill.state ? (
            <StatusChip tone={BILL_TONE[bill.state] ?? "neutral"} testKey={`state-${number}`}>
              {t(`portal.bills.state.${bill.state}`)}
            </StatusChip>
          ) : null}
          {/* ⚠ **DRAWN ONLY WHERE THERE IS A CHOICE TO MAKE.** One bill and the
              chooser is furniture — the same call `AccountSwitcher` makes for
              one account, and the wireframe states it for this panel in as many
              words: *"a first bill means no chooser at all"*. */}
          {bills.length > 1 ? (
            <SelectInput
              id="home-bill-month"
              // DEF-CWP-10564 (F-12): the chooser had no name at all.
              ariaLabel={t("portal.home.billMonth")}
              value={billKey(bill)}
              onChange={(value) => {
                setChosen(value);
                const picked = bills.find((one) => billKey(one) === value);
                if (picked !== undefined) {
                  say.polite(`${monthLabel(picked)} · ${formatMoney(picked.total, picked.currency)}`);
                }
              }}
              options={bills.map((one) => ({
                value: billKey(one),
                label: `${monthLabel(one)} · ${formatMoney(one.total, one.currency)}`,
              }))}
            />
          ) : null}
        </span>
      </div>

      <KVList rows={rows} />

      <span className="flex items-center gap-3">
        <Link
          to={path(`/bills/${encodeURIComponent(number)}`)}
          className="text-base font-semibold text-accent-text"
          aria-label={t("portal.home.openBill", { number })}
          data-bill-open={number}
        >
          <EyeIcon />
        </Link>
        <Link
          to={path(`/bills/${encodeURIComponent(number)}/document`)}
          className="text-base font-semibold text-accent-text"
          aria-label={t("portal.home.printedBill", { number })}
          data-bill-printed={number}
        >
          <PrinterIcon />
        </Link>
      </span>
    </div>
  );
}

/**
 * `ChartPanel` **TWELVE MONTHS OF …**, one per measured service.
 *
 * ⚠ **AN ABSENT MONTH IS AN EMPTY SLOT, NEVER A ZERO BAR** (`BR-MET-106`) —
 * `UsageBars` holds that rule and this only feeds it. The series the server
 * sends carries STATED months only, so a month with no read is simply not in it
 * and the chart is drawn over the months that are.
 */
function UsageCharts(props: { series: PortalHome["usage_series"] }) {
  const { t } = useTranslation();
  const path = usePortalPath();
  const services: string[] = [];
  for (const row of props.series) if (!services.includes(row.service)) services.push(row.service);
  return (
    <>
      {services.map((code) => {
        const points = props.series.filter((row) => row.service === code);
        const unit = points[0]?.unit ?? "";
        const bars: UsageBar[] = points.map((row) => ({
          month: row.month,
          quantity: row.quantity,
          quantityDisplay: row.quantity_display,
          absent: false,
          estimated: row.estimated,
        }));
        const name = t(`rating.service.${code}`, { defaultValue: code });
        return (
          <Panel
            as="aside"
            key={code}
            /* ⚠ **THE SERVICE WORD IS PASSED AS THE CATALOGUE WROTE IT AND IS
                NOT LOWER-CASED HERE.** `toLocaleLowerCase()` is an English
                assumption: German capitalises every noun, so *Zwölf Monate
                wasser* would be wrong in the one language most likely to
                notice. The catalogue phrases its own heading (B14 rule 35). */
            title={t("portal.home.chartTitle", { service: name })}
            trailing={
              <Link
                to={path("/usage")}
                className="text-base font-semibold text-accent-text"
                data-home-usage-door={code}
              >
                {/* ⚠ The WORD is the catalogue's (`portal.tab.usage`, the same
                    one the frame's own nav renders in all eleven); the ARROW is
                    not language and is written here, exactly as `PageHeader`
                    writes its own `←`. A `portal.home.usageDoor` family would
                    have been eleven strings for one existing word. */}
                {t("portal.tab.usage")} →
              </Link>
            }
          >
            <UsageBars
              testId={`home-${code}`}
              bars={bars}
              unit={unit}
              axisLabel={t("portal.usage.axis", { unit })}
              caption={t("portal.usage.chartCaption", {
                service: name,
                months: bars.length,
                unit,
              })}
              emptyLabel={t("portal.usage.noReadingsYet")}
              barTitle={(bar) =>
                t(bar.estimated ? "portal.usage.barEstimated" : "portal.usage.bar", {
                  month: bar.month,
                  value: bar.quantityDisplay ?? "",
                  unit,
                })
              }
            />
          </Panel>
        );
      })}
    </>
  );
}

/**
 * `AccountCard` **YOUR ACCOUNT** — who this is, what they take, what is fitted.
 *
 * ⚠ **IT EXISTS BECAUSE THE HOME PAGE HAD NO IDENTITY ON IT.** The Product
 * Owner signed in on 2026-09-08 and said so in as many words — *"once I login
 * as consumer - 03 Home ... we are not displaying account # of Customer nmae -
 * ther eis no identifier"* — then asked for *"name account #, service area,
 * Utility services, assets, phone # and email ID, govt ID - last 4 digits etc
 * - you can mask these detials"*, and then TRIMMED it, which is what decides
 * the shape here: *"just show IDs not details - Equipment ... W-2209, 8841-C,
 * F-0118 - this is enough + account status"*.
 *
 * ⚠ **SO EQUIPMENT IS BARE REFERENCES.** `E-5000 · W-5000`, never *Electric
 * meter E-5000 · 5/8 inch*. A customer knows what is fitted at their own
 * property; what they cannot produce from memory is the number a clerk asks
 * for on the telephone or a plumber reads off the meter. Three references fit
 * on one line where three descriptions took three, and the room that frees
 * carries the ACCOUNT STATUS, which is the fact people actually check.
 * `CWP-037` keeps the sizes, the ownership and the last read, one tap away.
 *
 * ⚠ **NO ACCOUNT NUMBER AND NO ADDRESS ON THIS CARD, DELIBERATELY.** The frame
 * draws both on the account bar, one line above, on every signed-in screen
 * (`PortalShell.AccountBar`, PO 2026-09-08: *"below that we should have a line
 * for account"*). Drawing them again would put the same two facts twice on one
 * screen, which is the *"too much content"* the Product Owner has now objected
 * to four times (B14 rule 32).
 *
 * ⚠ **THE MASKS ARRIVE MASKED.** `identity.phone` and `identity.email` are
 * already `••• ••• 1000` and `a•••@example.invalid` when they reach this file,
 * so no edit here can reveal a full one. The government ID the drawing asks
 * for is NOT served and is NOT invented — that row is simply absent, which is
 * what the drawing itself asks for when there is no ID on file.
 *
 * ⚠ **A ROW WITH NO ANSWER IS ABSENT AND A ROW THE ACCOUNTS DISAGREE ON SAYS
 * SO** (`BR-CWP-093`). A landlord's three properties are three facts, and
 * showing the first would tell them their service is at one building; the
 * server folds each fact on its own, so the plan can state the plan while the
 * status says *varies by account*.
 *
 * ⚠ **PAPERLESS ADDS EMAIL AND NEVER STOPS PAPER** (`BR-BIL-036`, CONFIRMED
 * 2026-08-10: print is the FLOOR and *a paperless customer still receives the
 * document*). So the value is the two channels rather than *On*, which is what
 * a customer would read as *we stopped posting it*.
 */
function AccountCard(props: { identity: HomeIdentity; service: PortalHome["service"] }) {
  const { t } = useTranslation();
  const { service } = props;
  // ⚠ **A VERSION-SKEW GUARD, NOT A STATEMENT ABOUT THE MODEL.** The server
  // always sends `identity`, and the type above says so. But a browser holding
  // yesterday's bundle against today's server — or today's bundle against a
  // host that has not been restarted — reads `undefined` here, and the FIRST
  // thing this card touches is `identity.status_class.value`. That threw
  // *"Cannot read properties of undefined"* and replaced the WHOLE HOME PAGE
  // with a React error screen: the balance, the bill and the charts all gone
  // because one new block was absent. Found by opening the page in a real
  // browser after a backend restart was missed — `tsc` and 28 jsdom cases
  // passed over it, which is hard-won law 6 exactly. An absent card is a card
  // that closes up (`BR-CWP-093`); an absent card must never be a blank screen.
  const identity: HomeIdentity | undefined = props.identity;
  if (!identity) return null;
  const varies = t("portal.home.service.varies");
  const say = (fact: HomeServiceFact, render: (value: string) => string): string | null => {
    if (fact.varies) return varies;
    if (fact.value === null) return null;
    return render(String(fact.value));
  };

  const rows = [
    {
      key: "name",
      label: t("portal.myDetails.legalName"),
      value: say(identity.name, (one) => one),
    },
    {
      key: "services",
      label: t("portal.accounts.colServices"),
      // ⚠ THE UTILITY'S OWN WORD FOR EACH SERVICE, joined — never our own
      // eleven-language service vocabulary, which would rename a utility's
      // *Refuse* to *Trash* on its own customers' screens (B14 rule 35).
      value: identity.services.length
        ? identity.services.map((one) => one.name).join(" · ")
        : null,
    },
    {
      key: "plan",
      label: t("portal.home.service.plan"),
      value: say(service.plan, (one) => one),
    },
    {
      key: "billed",
      label: t("portal.home.service.billed"),
      // ⚠ The wire carries one of the eight business WORDS and the catalogue
      // writes it (B14 rule 35). `settings.cycles.frequency.*` already holds
      // all eight in all eleven languages — a second family here would be
      // eighty-eight new strings saying what the product already says.
      value: say(service.billed, (one) =>
        t(`settings.cycles.frequency.${one.toLocaleLowerCase()}`, { defaultValue: one }),
      ),
    },
    {
      key: "equipment",
      label: t("portal.equipment.colKind"),
      value: identity.equipment.length ? identity.equipment.join(" · ") : null,
    },
    // ⚠ **TWO ROWS AND NOT ONE *How we reach you*, BECAUSE THE CATALOGUES
    // ALREADY HOLD BOTH WORDS NATIVELY** — `portal.myDetails.mobile` and
    // `portal.myDetails.email`, on the screen that edits these very two
    // fields. One combined row would have needed a new string in eleven
    // languages to say what the product already says in eleven languages
    // (B14 rule 35; `G27` refuses the debt).
    //
    // ⚠ **`varies` IS SAID, NOT SWALLOWED.** Four accounts carrying four
    // different telephone numbers is one bill going nowhere, and showing the
    // commonest of them would read as settled (`CWP-024` takes the same
    // posture on the same two fields).
    {
      key: "phone",
      label: t("portal.myDetails.mobile"),
      value: identity.phone_varies ? varies : identity.phone,
    },
    {
      key: "email",
      label: t("portal.myDetails.email"),
      value: identity.email_varies ? varies : identity.email,
    },
    {
      key: "paperless",
      label: t("portal.home.service.paperless"),
      value: service.paperless.varies
        ? varies
        : service.paperless.value === null
          ? null
          : service.paperless.value
            ? t("portal.home.service.paperlessOn")
            // ⚠ `portal.documents.channel.pdf_print` is *Post* in all eleven and
            // is this same delivery channel's word one screen over.
            : t("portal.documents.channel.pdf_print"),
    },
  ].filter((row): row is { key: string; label: string; value: string } => row.value !== null);

  const status = identity.status.varies ? varies : identity.status.value;
  // B14 rule 17's shape — a card with nothing in it is not drawn at all.
  if (rows.length === 0 && status === null) return null;
  return (
    <Card testId="home-account">
      <div className="flex items-start justify-between gap-3">
        {/* ⚠ **AN EXISTING CATALOGUE KEY, NOT A NEW ONE** (B14 rule 35, `G27`).
            `portal.yourAccount.title` is *Your account* in all eleven
            languages, written by people who read them; minting
            `portal.home.yourAccount` would have meant either eleven machine
            translations or English on nine screens. Same words, same object,
            one string. */}
        <SectionTitle>{t("portal.yourAccount.title")}</SectionTitle>
        {/* ⚠ **THE COLOUR READS `behavior_class`, NEVER THE NAME.**
            `account_statuses` is a tenant-extensible LOOKUP (`BR-CUS-055`): a
            utility may rename *Active* or add *Legal hold* tomorrow, and a
            chip matching on the word would go quietly grey on the day it did.
            The five classes are the utility's own classification of its own
            statuses, which is exactly what a colour should follow. */}
        {status ? (
          <StatusChip tone={statusTone(identity.status_class.value)} testKey="account-status">
            {String(status)}
          </StatusChip>
        ) : null}
      </div>
      <KVList
        rows={rows.map((row) => ({
          ...row,
          value: <span data-identity={row.key}>{row.value}</span>,
        }))}
      />
      {/* ⚠ **THE DRAWN DOOR, AND `CWP-065` HAD ONE INBOUND LINK IN THE WHOLE
          PORTAL** (`DEF-CWP-4901`). The drawing ends this card with
          *→ All account details* on a phone and *→ Everything about this
          account* on a desktop; the screen it opens — the whole picture of one
          property — was reachable only from `My details`, which is not where
          anybody looks for it. **One label and not two**: B14 rule 36's own
          instinct, and a phone that renders a different word from a desktop is
          two strings to keep in step in eleven languages. Same shape as the
          accounts door on the tile above, and `DEF-CWP-3954` is what leaving
          a screen doorless costs. */}
      <div className="mt-3">
        <ErrandLink label={t("portal.home.accountDoor")} to="/account" />
      </div>
    </Card>
  );
}

/**
 * `behavior_class` → the chip's tone. The five `BR-CUS-055` seeds, and an
 * unknown class — a tenant's own addition — reads NEUTRAL rather than guessing.
 *
 * ⚠ **`billable_base_only` IS A WARNING AND NOT A SUCCESS.** A vacation hold
 * is still billing the standing charge; a green chip would tell somebody who
 * has stopped using the service that nothing is happening on the account.
 */
function statusTone(behaviorClass: string | boolean | null): ChipTone {
  const tones: Record<string, ChipTone> = {
    billable: "success",
    non_billable: "warning",
    billable_base_only: "warning",
    terminal: "danger",
  };
  return tones[String(behaviorClass ?? "")] ?? "neutral";
}
