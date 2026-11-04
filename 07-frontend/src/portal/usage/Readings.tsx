// ── Trace ──────────────────────────────────────────────
// Story:    US-CWP-041 (EP-CWP-08) — *Every reading, how it was taken, and why
//           one was corrected*. Screen: CWP-034 (blueprint `P20`)
// Rules:    BR-CWP-071 (the method is as prominent as the number, estimation
//           included) · BR-CWP-072 (why a read was corrected, and by how much) ·
//           BR-CWP-069 (a superseded read must not leave the customer charged
//           twice) · CLAUDE.md hard rule 3 (a quantity always with its unit) ·
//           B14 rule 20 (ONE table type) · rule 21 · rule 31 (no database id
//           on screen) · rule 32 (one sentence per section) · rule 35 (the
//           catalogue writes the words) · rule 36 (compose the kit)
// Defects:  DEF-CWP-3990 — every meter in one list with nothing saying which
//           row belonged to which box; the payload carried `meter_serial` and
//           `meter_no` per row and this screen dropped both ·
//           `13-wireframe-delta.md` 34.1 · 34.2 · 34.4 · 34.7 · 34.9 and
//           `14-layout-audit.md` D1 (this screen's half of it)
// CR-085:   s51 (group H) — the drawing scopes this screen to ONE meter and
//           gives a phone a stack of cards. That REVERSES the 2026-09-05
//           decision to answer `DEF-CWP-3990` with a meter column; the column
//           returns whenever a service answers from more than one meter, which
//           is the one case a tab cannot state. `08-screen-layouts.md` CWP-034
//           amended the same day.
// Tests:    src/portal/usage/Readings.dom.test.tsx
// Impacts:  src/portal/api/portalClient.ts `getAccountReadings`
// ───────────────────────────────────────────────────────
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import { PageHeader } from "@/components/PageHeader";
import { ButtonLink } from "@/components/Button";

import {
  Card,
  formatDialFigure,
  formatQuantity,
  InfoBar,
  rowActionName,
  ServicePicker,
  StatusChip,
  usePortalPath,
} from "../components/primitives";
import { usePortalDate } from "../components/regional";
import { PortalListTable } from "../components/listTable";
import { usePortalListWindow } from "../components/listWindow";
import { ListPager } from "@/components/ListPager";
import type { PageSize } from "@/components/tableTypes";
import { EyeIcon } from "@/components/icons";
import { PortalScreen, PortalState } from "../components/states";
import {
  getAccountReadings,
  type PortalNextRead,
  type PortalReading,
  type PortalReadings,
  type PortalReadingService,
} from "../api/portalClient";

/**
 * ⚠ **`CWP-035` — *Send us your reading* — LANDED 2026-10-17 (`DEF-CWP-10175`,
 * `US-CWP-042`), AND THIS HEAD ACTION WAS ITS HOLD.** It was a `HeldButton`
 * with *Sending readings is not ready yet* and two cases asserting no route
 * answered the address; the screen arrived, those cases went red exactly as
 * written, and the button is now a link to the drawing's own address. The
 * address and id are re-exported from the screen that owns them, so a test
 * here and the router can never name two different places.
 *
 * ⚠ **AND IT IS ABSENT, NOT HELD, WHEN THE UTILITY HAS SELF-READ OFF**
 * (`US-CWP-042` TC-7, `BR-CWP-093`): the server says so in
 * `self_read_enabled`, and a greyed control would read as *coming soon* for
 * a feature this utility has chosen not to offer.
 */
export { SEND_A_READING_PATH, SEND_A_READING_SCREEN } from "./SendReading";

/**
 * The two methods that get a CHIP. Everything else is plain text.
 *
 * ⚠ **THE CHIP IS THE EXCEPTION, AND SPENDING IT ON EVERY ROW SPENT THE
 * EMPHASIS** (`13-wireframe-delta.md` 34.4, confirmed against `CWP-034.png`).
 * The drawing writes *Read by a meter reader* and *You sent it in* as plain
 * text in the same column at the same size, and gives an outlined `ESTIMATED`
 * chip to the ONE row that differs, followed by a plain *then corrected*. Four
 * grey chips in a column say nothing is unusual about any of them, which is the
 * opposite of what the column is for.
 *
 * ⚠ **`BR-CWP-071` IS STILL HELD, AND THIS IS WHAT IT ASKS FOR.** The rule says
 * the method is as prominent AS THE NUMBER — a full-width column of body text
 * beside the figure is exactly that. It never asked for a chip.
 *
 * ⚠ **AN ESTIMATE IS `warning`, NOT `danger`.** Nothing went wrong: an estimate
 * is our best guess when nobody could get to the meter, and a correction is the
 * product working as designed. Painting either red would tell a customer there
 * is a problem with their account.
 */
const CHIPPED: Record<string, "warning"> = {
  estimated: "warning",
  estimated_corrected: "warning",
};

/** One entry in the drawing's meter tabs — `⚡ Electric · 8841-C`. */
export interface ReadingService {
  code: string;
  name: string;
  /** How many distinct meters answered on this service in this payload. */
  meters: number;
}

/**
 * The drawing's meter tabs, from the SERVER's own list of them.
 *
 * ⚠ **THE SET QUESTION MOVED TO THE SERVER ON 2026-09-19 (`DEF-CWP-5747`) AND
 * HAD TO.** This used to fold the PAYLOAD — every reading the account had ever
 * taken — into a tab per service. The payload is now ONE PAGE, and tabs folded
 * from a page would read *the services in the newest fifty readings*: an
 * electric meter read once a quarter would simply lose its tab, silently, with
 * `tsc` and every test green. `apps/metering/portal_reads.reading_services`
 * answers it over the whole account in one query instead, and what is left
 * here is the LABEL — which is a display decision and belongs on this side.
 *
 * ⚠ **BUILT FROM WHAT THE SERVER SENT AND NEVER FROM A LIST TYPED OUT HERE.**
 * The drawing says so for the Usage picker — *"The picker is built from the
 * services this customer actually has — never a fixed list"* — and CLAUDE.md's
 * hard-won law 2 says what a typed-out list costs: the front end names the
 * eleven services by hand in two files, and the eleventh one silently never
 * appeared on screen.
 *
 * ⚠ **THE METER REFERENCE RIDES IN THE LABEL WHERE THERE IS EXACTLY ONE**, and
 * that is `DEF-CWP-3990`'s fix kept rather than undone: the defect was that
 * nothing said which box a row came off. The drawing puts that fact in the tab
 * — `⚡ Electric · 8841-C` — and the column comes back on its own below when a
 * service answers from more than one meter, which is the only case a tab
 * cannot state.
 *
 * ⚠ **A METER ON NO SERVICE POINT IS ITS OWN ENTRY, NOT A DROPPED ROW.** The
 * server codes it `unassigned` and its NAME is its own reference, so a reading
 * a customer cannot reach does not exist — which is worse than a tab with an
 * odd name on it.
 */
export function tabsFrom(served: PortalReadingService[], fallback: string): ReadingService[] {
  return served.map((one) => {
    const seen = one.meters;
    const name = one.name ?? seen[0] ?? fallback;
    return {
      code: one.code,
      // The CATALOGUE joins the two halves, never this file (B14 rule 35), and
      // neither half is a database id (rule 31): a serial is printed on the box
      // and a meter number is the utility's own from its series.
      //
      // ⚠ **AND NEVER `88-40219 · 88-40219`** — a meter on no service point has
      // no service word, so its NAME already is its reference and joining the
      // two prints it twice. Found by the case that pins the fallback.
      name: seen.length === 1 && name !== seen[0] ? `${name} · ${seen[0]}` : name,
      meters: seen.length,
    };
  });
}

/**
 * `CWP-034` — every reading, **how it was taken**, and the bill it fed.
 *
 * ⚠ **HOW A READING WAS TAKEN IS AS IMPORTANT AS THE NUMBER** (`BR-CWP-071`).
 * The product records the method on every read, estimation included, and
 * estimates are trued up by the next actual reading. Showing that plainly is
 * what prevents the most common dispute in metered billing — *"you estimated
 * and overcharged me"* — from being a phone call.
 *
 * ⚠ **A CORRECTION SHOWS ITS REASON AND ITS SIZE** (`BR-CWP-072`): *estimated
 * 144,600, corrected to 144,130 when the meter was read on 3 July — you were
 * not charged twice*. Both figures, or the sentence is an assurance with
 * nothing behind it.
 *
 * ⚠ **AND *ON WHICH BILL* IS EMPTY RATHER THAN GUESSED.** A reading no issued
 * bill covers shows nothing in that cell; naming the nearest one would tell a
 * customer they were charged for a reading nobody has billed.
 */
export function ReadingsView(props: { accountId: string }) {
  const { t, i18n } = useTranslation();
  // `DEF-CWP-3994` — the tenant's own date format, published at the frame.
  const asDate = usePortalDate();
  const path = usePortalPath();
  /**
   * ⚠ **ONE PAGE, AND THE SEARCH AND THE SORT TRAVEL WITH IT (`DEF-CWP-5747`,
   * `NFR-3`).** This screen used to ask for EVERY reading the account had ever
   * taken and let the browser search, sort and slice them. A household is a few
   * hundred rows; an AMI deployment writes an interval reading per meter per
   * HOUR, so two years is about 17,000 rows over the wire to draw fifty. All
   * three moved together on purpose — a server page under a browser search
   * would tell a customer that a reading on page 7 does not exist.
   */
  const list = usePortalListWindow();
  const [answer, setAnswer] = useState<PortalReadings | null>(null);
  const [failed, setFailed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [open, setOpen] = useState<string | null>(null);
  /**
   * ⚠ **WHICH METER THE CUSTOMER IS LOOKING AT — the drawing scopes this whole
   * screen to one** (`⚡ Electric · meter 8841-C ▾` on a phone, two tabs on a
   * desktop). A CODE is held rather than an index, so a payload that changes
   * under it cannot leave the picker pointing at a service that is no longer
   * there; `null` means *the one the server listed first*.
   *
   * ⚠ **AND IT IS A SERVER FILTER NOW, NOT A `rows.filter`.** It rides as
   * `?f.service=`, because narrowing a PAGE to one meter would show a customer
   * whichever of their meters happened to appear in the newest fifty rows.
   */
  const chosen = list.filter("service");
  /** R-10's way out, wired to a real read — see `Usage.tsx`'s note on why a
   *  `Try again` that calls nothing is worse than no button at all. */
  const [attempt, setAttempt] = useState(0);

  const { request } = list;
  useEffect(() => {
    let live = true;
    // ⚠ **THE ROWS STAY ON SCREEN WHILE THE NEXT PAGE IS IN FLIGHT.** Setting
    // them to `null` here would blank the whole card to a loading state on
    // every page turn and on every settled keystroke, which loses the reader's
    // place and reads as the screen breaking. `busy` is what says *in flight*,
    // and only the FIRST load has nothing to show.
    setBusy(true);
    setFailed(false);
    getAccountReadings(props.accountId, request)
      .then((next) => {
        if (live) {
          setAnswer(next);
          setBusy(false);
        }
      })
      .catch(() => {
        if (live) {
          setFailed(true);
          setBusy(false);
        }
      });
    return () => {
      live = false;
    };
  }, [props.accountId, request, attempt]);

  const rows = answer === null ? null : answer.readings;
  //: `CPB-09` — when somebody is coming next. `null` closes the line up.
  const nextRead: PortalNextRead | null = answer?.next_read ?? null;

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
  const head = (
    <PageHeader
      backTo={{ to: path("/usage"), label: t("portal.readings.backToUsage") }}
      title={t("portal.readings.title")}
      primaryAction={
        // `US-CWP-042` — the drawing's *Send a reading*, live while the
        // utility offers self-read and ABSENT otherwise (`BR-CWP-093`).
        answer?.self_read_enabled === true ? (
          <ButtonLink
            // A LITERAL, not the constant: `everyRouteHasADoor` reads doors
            // from source, and `SEND_A_READING_PATH` is asserted equal to it.
            to={path("/usage/submit")}
            variant="secondary"
            className="min-h-11"
            data-send-reading=""
          >
            {t("portal.readings.sendReading")}
          </ButtonLink>
        ) : undefined
      }
    />
  );

  if (failed) {
    return (
      <PortalScreen screen="CWP-034" head={head}>
        <PortalState
          kind="failed"
          testId="readings"
          sentence={t("portal.readings.couldNotRead")}
          /* `DEF-CWP-4846`'s other half — R-10, the way out beside the
             message. Lane 1 put the HEAD back on this branch; `states.tsx`
             left `waysOut` optional because the read is held in each screen's
             own effect and per-screen actions belong to the lane that owns the
             screen. This is that lane supplying it. The head's `← Usage` is
             the second way out and is above this card on every branch. */
          waysOut={[
            {
              label: t("portal.state.tryAgain"),
              tone: "primary",
              testKey: "retry",
              onClick: () => setAttempt((n) => n + 1),
            },
          ]}
        />
      </PortalScreen>
    );
  }
  if (rows === null || answer === null) {
    return (
      <PortalScreen screen="CWP-034" head={head}>
        <PortalState kind="loading" testId="readings" sentence={t("portal.readings.reading")} />
      </PortalScreen>
    );
  }

  // ⚠ **THE TABS ARE THE SERVER'S ANSWER OVER THE WHOLE ACCOUNT**
  // (`DEF-CWP-5747`). They used to be built from the payload, and the payload
  // is now one page — tabs built from a page would read *the services in the
  // newest fifty readings*, so a meter read once a quarter would lose its tab
  // and a customer would be told they have no water readings.
  const services = tabsFrom(answer.services, t("portal.readings.colMeter"));
  const current = services.find((one) => one.code === chosen) ?? services[0] ?? null;
  // ⚠ **NO `rows.filter` HERE ANY MORE.** The service is `?f.service=` and the
  // rows that arrive are already the answer; narrowing them again would filter
  // the filtered set, and on a PAGE it would show whichever of the customer's
  // meters happened to land in the newest fifty rows.
  const shown = rows;
  // ⚠ **THE METER COLUMN COMES BACK ONLY WHERE THE TAB CANNOT NAME THE BOX**
  // (`DEF-CWP-3990`). One meter on the chosen service and its reference is
  // already in the tab; two and the column is the only thing telling two rows
  // taken on the same day apart.
  const meterColumnNeeded = current === null || current.meters !== 1;
  // ⚠ **`count` CANNOT ANSWER *HAS THIS CUSTOMER ANY READINGS AT ALL*, AND
  // THE TAB LIST CAN.** `count` is the MATCHING set, so a customer with eleven
  // months of readings who types a serial matching none of them has `count: 0`
  // — and answering that with *Your first reading will appear here* would be a
  // plain lie. `services` is the server's read over the WHOLE account, with no
  // search and no tab applied, so it is non-empty exactly when the account has
  // a reading. It is already in the payload, so this costs nothing.
  const populated = answer.services.length > 0;

  return (
    <div data-screen="CWP-034">
      {/* ⚠ **THE KIT'S OWN PAGE HEAD, NOT A NEW ONE** (`14-layout-audit.md`
          D1, B14 rule 36). `components/PageHeader.tsx` has drawn this exact
          skeleton — back link, kicker, title, right-aligned actions — since
          B14 rule 2, and thirteen portal files already compose it. `backTo`
          gives the drawing's `← USAGE`; the action slot is where the drawing
          puts *Send a reading*, and it is the row D1 says is missing from 28
          screens. Nothing here is a competing header. */}
      {head}
      {/* ⚠ **`CPB-09` — ABOVE THE LIST, WHICH IS WHERE THE BLUEPRINT PUTS IT**:
          *"The Readings screen reads 'Next read: Sep 30 · in 22 days' above the
          list."* A person looking at a column of past readings is asking when
          the next one happens, and until today the screen could not say.

          ⚠ **THE SOURCE IT WAS SUPPOSED TO READ COULD NEVER ANSWER**
          (`DEF-MET-4684`): an OPEN read window is unreachable by construction —
          the one writer in the product sets `read_on` at creation — so this
          figure comes from the route's CYCLE SCHEDULE, which stores nothing and
          cannot go empty. */}
      {/* ⚠ **THE LINE IS SUPPRESSED WHERE THE EMPTY STATE BELOW SAYS THE
          SAME THING** (`DEF-CWP-4849` clause 2). With no readings at all the
          screen drew *Next read: Sep 30 · in 19 days* over *Your first
          reading will appear here.* — two sentences about one fact, neither of
          which is the drawing's. Screen 51's `NO READS YET` state is a single
          sentence that carries the date: *"Your first read is due around Sep
          30."* */}
      {populated ? <NextReadLine next={nextRead} /> : null}
      <Card testId="readings">
        {!populated ? (
          // B14 rule 17 — a sentence naming what will fill it, never a table
          // of dashes.
          //
          // ⚠ **AND IT NAMES THE DATE WHEN THERE IS ONE** (`DEF-CWP-4849`
          // clause 2). *Your first reading will appear here.* is true and says
          // nothing a customer can act on; the drawing's own sentence is *"Your
          // first read is due around Sep 30."* The date is the SAME
          // `next_read` the line above uses — one derivation, so the two
          // sentences cannot disagree about one date — and where the cycle has
          // no schedule to answer from, the plain sentence stands rather than
          // an invented month (`BR-CWP-093`).
          <p className="mt-2 text-body text-neutral-600" data-readings-empty="">
            {nextRead === null
              ? t("portal.readings.none")
              : t("portal.readings.noneFirstDue", {
                  date: monthDayText(nextRead.from, i18n.language),
                })}
          </p>
        ) : (
          <>
            {/* ⚠ **ONE METER AT A TIME, WHICH IS THE DRAWING AND A REVERSAL
                OF A RECORDED DECISION — SAID OUT LOUD RATHER THAN QUIETLY.**
                `DEF-CWP-3990` was fixed on 2026-09-05 with a meter COLUMN and
                the decision log of that day argues against a chooser: the
                screen is called *Every reading* and a default view that is a
                SUBSET invites *"where did my electric readings go"*. The
                signed-off wireframe for `CR-085` draws the chooser anyway, on
                both widths, and answers that worry in the drawing itself — the
                other service is a live tab a foot away, never a filter a
                customer can forget they set. The column is not deleted: it
                returns whenever a service answers from more than one meter,
                which is the one case a tab cannot state. */}
            {/* One guard, in the component (see `CWP-033`'s note): an account
                with one meter gets no chooser at all. */}
            <div className="mt-3">
              <ServicePicker
                testId="meter"
                label={t("portal.readings.serviceLabel")}
                services={services}
                current={current?.code ?? ""}
                onChoose={(code) => list.setFilter("service", code)}
              />
            </div>
            {/* ⚠ **A SIX-COLUMN TABLE ON A 390px PHONE SCROLLS SIDEWAYS, AND
                `overflow-x-auto` STOPS THE PAGE MOVING WITHOUT MAKING THE
                FIGURES READABLE** — `bills/Bills.tsx` reached the same
                conclusion on the same evidence, and the drawing answers it the
                same way: its phone frame is a stack of cards (date, how it was
                taken, the dial figure, what was used) and its desktop frame is
                the table. Measured in the browser at 390: the table wanted
                559px.

                ⚠ **ONE SOURCE FOR BOTH.** Both halves render `shown`, so
                nothing can drift; what the phone drops is the toolbar and the
                columns the drawing itself leaves out of its phone frame. */}
            <div className="mt-3 hidden flex-col gap-3 max-md:flex" data-reading-cards="">
              {shown.map((row, index) => (
                <ReadingCard
                  key={`${row.taken_on ?? "read"}-${index}`}
                  row={row}
                  withMeter={meterColumnNeeded}
                  open={open === row.taken_on}
                  onOpen={setOpen}
                />
              ))}
              {/* ⚠ **THE PHONE GETS A FOOTER TOO, AND IT IS NOT FURNITURE —
                  WITHOUT IT THIS COMMIT WOULD HAVE BUILT A WALL**
                  (`DEF-CWP-5747`). The card stack had no pager because it had
                  every row and a customer scrolled. It now holds ONE PAGE, so
                  a phone with no footer would leave reading 51 unreachable —
                  the payload defect fixed by manufacturing a worse one, which
                  is exactly the shape this defect was filed rather than
                  half-fixed to avoid. It is the SHARED `ListPager` on the
                  same four `table.pager.*` keys as the table's own, so there
                  is still one footer in the product (B14 rule 16). */}
              <ListPager
                total={answer.count}
                page={answer.page}
                per={answer.per as PageSize}
                onPage={list.setPage}
                onPer={list.setPer}
              />
            </div>
            <div className="mt-3 max-md:hidden">
              <PortalListTable<PortalReading>
                screen="CWP-034"
                caption={t("portal.readings.caption")}
                rows={shown}
                // ⚠ **THE KEY IS THE DATE, NOT A ROW ID** (B14 rule 31): the
                // payload carries no id to reach for, which is the type making
                // the rule impossible to break.
                rowKey={(row) => `${row.taken_on ?? "read"}-${shown.indexOf(row)}`}
                empty={
                  <p className="mt-2 text-body text-neutral-600" data-readings-empty="">
                    {t("portal.readings.none")}
                  </p>
                }
                /* ⚠ **THE SEARCH IS THE SERVER'S NOW (`DEF-CWP-5747`) AND
                   LOOKS AT THE SAME FIVE FIELDS.** It was
                   `[taken_on, meter_serial, meter_no, meter_service_name,
                   on_bill].some(includes)` over every row in the browser;
                   `apps/metering/portal_reads._reading_search` is that
                   predicate in SQL, and it says so field by field. There is no
                   `match` to pass here, deliberately — a predicate this
                   component were free to ignore is the dead prop hard-won law 2
                   is about. */
                server={list.window({
                  total: answer.count,
                  page: answer.page,
                  per: answer.per as PageSize,
                  populated,
                  busy,
                  search: { placeholder: t("portal.readings.search") },
                })}
                icons={[
                  {
                    key: "view",
                    icon: <EyeIcon />,
                    // DEF-CWP-10566: named for the bill it opens.
                    label: (row) => rowActionName(t("portal.readings.viewRow"), row.on_bill, t),
                    // ⚠ **THE DRAWING'S ✎ IS NOT DRAWN.** It would send a
                    // correction, which is `CWP-035`, and `CWP-035` has no
                    // route and no register row — the page head above already
                    // holds *Send a reading* for that reason and carries the
                    // test that fires when the screen lands. A second control
                    // pointing at the same absent screen would be a second
                    // thing to remember to release.
                    to: (row) => path(`/bills/${encodeURIComponent(row.on_bill ?? "")}`),
                    // A reading taken since the last run is on no bill yet.
                    reason: (row) =>
                      row.on_bill === null || row.on_bill === ""
                        ? t("portal.readings.notBilledYet")
                        : null,
                  },
                ]}
                columns={[
    // ⚠ **THE METER COLUMN IS CONDITIONAL NOW, AND `DEF-CWP-3990` IS STILL
    // ANSWERED.** That defect was *every meter in one list with nothing saying
    // which row belonged to which box*. The drawing answers it in the TAB —
    // `⚡ Electric · 8841-C` — so where the chosen service has exactly one
    // meter the column would print the same seven characters down eight rows.
    // Where it has two, the tab cannot name either and the column is the only
    // thing telling two readings taken on the same day apart, so it comes
    // back. It goes FIRST when it is here, because it is what the row is
    // about.
                  ...(meterColumnNeeded
                    ? [
                        {
                          key: "meter",
                          label: t("portal.readings.colMeter"),
                          sortable: true,
                          sortValue: (row: PortalReading) => row.meter_serial ?? row.meter_no,
                          // ⚠ **WHICH BOX ON THE WALL THIS READING CAME OFF.**
                          // The service is what a customer calls the meter and
                          // the serial is what is printed on it; neither is a
                          // database id (B14 rule 31).
                          cell: (row: PortalReading) => <MeterCell row={row} />,
                        },
                      ]
                    : []),
                  {
                    key: "taken",
                    label: t("portal.readings.colTaken"),
                    sortable: true,
                    sortValue: (row) => row.taken_on,
                    cell: (row) => asDate(row.taken_on) || "—",
                  },
                  {
                    key: "reading",
                    label: t("portal.readings.colReading"),
                    align: "right",
                    sortable: true,
                    sortValue: (row) => (row.reading === null ? null : Number(row.reading)),
                    // ⚠ **GROUPED ON THE CLIENT (`DEF-CWP-4009`, delta X2).**
                    // The wire value is `quantity_display.quantity_text`, which
                    // returns a bare `6462` on purpose and is shared with the
                    // staff screens — so the grouping happens here, where the
                    // locale is, through the kit's one place that knows how.
                    // This is the figure a customer checks against the box on
                    // their wall, which is why the delta singles it out.
                    cell: (row) => (
                      <span className="tabular-nums" data-reading={row.taken_on ?? ""}>
                        {formatDialFigure(row.reading_display) ?? "—"}
                      </span>
                    ),
                  },
                  {
                    key: "used",
                    label: t("portal.readings.colUsed"),
                    align: "right",
                    sortable: true,
                    sortValue: (row) => (row.used_since === null ? null : Number(row.used_since)),
                    // ⚠ HARD RULE 3 — the server composed the PAIR, and a
                    // reading whose unit did not arrive dashes rather than
                    // printing a bare number.
                    cell: (row) => (
                      <span className="flex flex-col items-end gap-1">
                        <span className="tabular-nums" data-used={row.taken_on ?? ""}>
                          {usedText(row) ?? "—"}
                        </span>
                        <HighConsumptionTag row={row} />
                      </span>
                    ),
                  },
                  {
                    key: "how",
                    label: t("portal.readings.colHow"),
                    cell: (row) => (
                      <HowCell row={row} onOpen={setOpen} open={open === row.taken_on} />
                    ),
                  },
                  {
                    key: "bill",
                    label: t("portal.readings.colBill"),
                    sortable: true,
                    sortValue: (row) => row.on_bill,
                    cell: (row) => <span data-bill={row.taken_on ?? ""}>{row.on_bill ?? ""}</span>,
                  },
                ]}
              />
            </div>
            {/* `BR-CWP-071`'s second half, and the sentence that stops the
                phone call. One section, one sentence (B14 rule 32). */}
            <div className="mt-3">
              {/* ⚠ **THE BOLD SPAN IS THE WORD BEING DEFINED** (34.7). It used
                  to be the whole second sentence, so the emphasis landed on the
                  assurance and not on *estimated*, which is the term the notice
                  exists to explain. Three fragments, and each catalogue writes
                  all three and may put the emphasis where its own grammar puts
                  it (B14 rule 35). */}
              <InfoBar
                lead={t("portal.readings.estimateLead")}
                bold={t("portal.readings.estimateBold")}
                tail={t("portal.readings.estimateTail")}
              />
            </div>
          </>
        )}
      </Card>
    </div>
  );
}

/**
 * The drawing's PHONE row — *Jul 31, 2026 · Read by us · 41,208 · 800 kWh
 * used* — one card, in the order a customer reads it.
 *
 * ⚠ **BOTH FIGURES, AS THE DRAWING INSISTS**: the dial reading because a
 * customer checks it against the box on their wall, and what was used because
 * that is the number on the bill. The difference between them is computed by
 * the server (`used_since_display`), never here.
 *
 * ⚠ **THE UNIT RIDES WITH THE CONSUMPTION AND NEVER WITH THE DIAL FIGURE**
 * (hard rule 3, and `formatDialFigure`'s own note): `used_since_display` is the
 * server-composed pair `800 kWh`; a register index with `kWh` after it would
 * claim the meter has measured 41,208 kWh since it was made.
 */
function ReadingCard(props: {
  row: PortalReading;
  withMeter: boolean;
  open: boolean;
  onOpen: (key: string | null) => void;
}) {
  const { t } = useTranslation();
  const asDate = usePortalDate();
  const path = usePortalPath();
  const { row } = props;
  const key = row.taken_on ?? "";
  return (
    // ⚠ **THE THIRD SIGNAL, ON THE WIDTH THIS LANE CAN GIVE IT**
    // (`DEF-CWP-4849` clause 1). Screen 51's note is explicit: *"Flagged with
    // colour AND the word 'Estimated' AND a row tint — three signals, because
    // this is the fact most likely to be disputed."* The chip and the word were
    // built; nothing was tinted, and `getComputedStyle` returned
    // `rgba(0, 0, 0, 0)` for every row including the estimated one.
    //
    // ⚠ **THE 1280 TABLE STILL HAS ONLY TWO SIGNALS AND IT IS NOT THIS
    // LANE'S TO FIX.** `MiniTable` owns the `<tr>` and offers `muted` alone —
    // grey TEXT, which is the wrong signal entirely: an estimate is not less
    // important than a measured read. A tinted row needs one optional tone on
    // that component, and `primitives.tsx` belongs to the frame lane this
    // session. Said out loud rather than half-done in silence; the register row
    // carries the residual.
    <div
      className={
        row.estimated
          ? "border border-warning-500 bg-warning-100 p-3"
          : "border border-neutral-200 p-3"
      }
      data-reading-card={key}
      data-estimated={row.estimated ? "true" : undefined}
    >
      <span className="text-h3 font-bold text-neutral-900">{asDate(row.taken_on) || "—"}</span>
      {props.withMeter ? (
        <p className="m-0 text-base text-neutral-600">
          <MeterCell row={row} mark="card-" />
        </p>
      ) : null}
      <div className="mt-1">
        <HowCell row={row} open={props.open} onOpen={props.onOpen} mark="card-" />
      </div>
      {/* ⚠ **BOTH FIGURES ARE LABELLED, AND ON A CARD THAT IS NOT OPTIONAL.**
          The table has column heads; a card has none, so `1,024` beside
          `8 kgal` leaves the reader to work out which is the dial and which is
          the consumption — and getting that backwards is exactly the confusion
          this screen exists to settle. The words are the TABLE'S OWN column
          labels, so the two widths cannot say it differently (B14 rule 35 —
          the catalogue writes them, once). */}
      <div className="mt-2 flex flex-wrap items-end justify-between gap-3">
        <span className="flex flex-col">
          <span className="text-xs font-bold uppercase tracking-wide text-neutral-600">
            {t("portal.readings.colReading")}
          </span>
          <span className="text-h3 font-bold tabular-nums" data-card-reading={key}>
            {formatDialFigure(row.reading_display) ?? "—"}
          </span>
        </span>
        <span className="flex flex-col items-end">
          <span className="text-xs font-bold uppercase tracking-wide text-neutral-600">
            {t("portal.readings.colUsed")}
          </span>
          <span className="text-body text-neutral-700 tabular-nums" data-card-used={key}>
            {usedText(row) ?? "—"}
          </span>
          <HighConsumptionTag row={row} mark="card-" />
        </span>
      </div>
      {/* ⚠ **A READING NO ISSUED BILL COVERS SHOWS NOTHING** (`US-CWP-041`
          TC-4) — naming the nearest bill would tell a customer they were
          charged for a reading nobody has billed. */}
      {row.on_bill ? (
        <p className="m-0 mt-2 text-base">
          <Link
            to={path(`/bills/${encodeURIComponent(row.on_bill)}`)}
            className="text-neutral-700"
            data-card-bill={key}
          >
            {row.on_bill}
          </Link>
        </p>
      ) : null}
    </div>
  );
}

/**
 * Which meter — the service the customer calls it by, then the serial printed
 * on the box.
 *
 * ⚠ **THE CATALOGUE JOINS THE TWO, NOT THIS FILE** (B14 rule 35). English
 * writes `{{service}} · {{serial}}`; a language that separates them differently
 * writes it differently, and one that would rather lead with the serial can.
 *
 * ⚠ **NEITHER HALF IS A DATABASE ID** (B14 rule 31). `meter_serial` is the
 * manufacturer's number on the box and `meter_no` is the utility's own from its
 * series (`BR-AST-049`); the payload carries no id at all, which is the type
 * making the rule impossible to break here.
 */
function MeterCell(props: { row: PortalReading; mark?: string }) {
  const { t } = useTranslation();
  const { row } = props;
  const mark = props.mark ?? "";
  const serial = row.meter_serial ?? row.meter_no;
  const said =
    serial === null
      ? (row.meter_service_name ?? "—")
      : row.meter_service_name
        ? t("portal.readings.meterOfService", {
            service: row.meter_service_name,
            serial,
          })
        : serial;
  return <span data-meter={`${mark}${row.taken_on ?? ""}`}>{said}</span>;
}

/**
 * What was used since the reading before — **grouped, like the dial figure
 * beside it** (`DEF-CWP-4168`).
 *
 * ⚠ **THE SAME NUMBER, WRITTEN TWO WAYS, ONE COLUMN APART.** `reading` goes
 * through the kit's `formatDialFigure` and comes out `41,208`; `used_since`
 * came straight off the wire as `quantity_with_unit`, which rounds and trims
 * and does NOT group, so a heavy month read `8402 kWh` beside `41,208`. The
 * kit's `formatQuantity` applies the server's OWN rounding rule before it
 * groups, so no digit changes — only the separator appears.
 *
 * ⚠ **THE SERVER STILL DECIDES WHETHER A PAIR MAY BE SHOWN AT ALL, AND THAT
 * ORDER IS DELIBERATE.** `used_since_display` is `null` exactly when there is
 * no quantity or no unit — which is hard rule 3 enforced once, on the wire —
 * so it is checked FIRST and a `null` dashes whatever else the row carries.
 * Reading `used_since` and `unit` directly and skipping that check would move
 * the rule's enforcement onto this screen, where the next lane would not know
 * to look for it.
 *
 * ⚠ **AND THE CLIENT MAY ONLY RE-FORMAT THE SERVER'S OWN ANSWER — IF THE TWO
 * EVER DISAGREE THE SERVER WINS.** This is the whole difference between a
 * rendering change and a second answer to a question the server has already
 * answered (`CPB-08`'s own rule, and `DEF-CWP-3655`'s shape). `used_since` and
 * `used_since_display` are derived from ONE field by ONE function today, so
 * they cannot diverge in the product — but nothing in the types says so, and a
 * fixture that set one and not the other made this screen print **`4,820 kWh`
 * where the server had said `1400 kWh`**. Comparing the DIGITS (never the
 * string — the separator is the reader's locale and the unit may carry a
 * numeral, as `m3` does) keeps this strictly a re-render: same figure,
 * separators added, or the server's own words untouched.
 */
/**
 * `CR-182-BRC10` (PO A3, 2026-10-14) — *"high conumption alert"* on the reading
 * BR-MET-020/120 flagged high. Beside the USED figure, because that is the
 * number it is about. Absent on every other row (`CHIPPED`'s rule: the chip
 * marks the row that differs). `mark` keeps the phone card's copy apart from
 * the table's, as `HowCell` does.
 */
function HighConsumptionTag(props: { row: PortalReading; mark?: string }) {
  const { t } = useTranslation();
  if (!props.row.high_consumption) return null;
  return (
    <StatusChip tone="warning" testKey={`${props.mark ?? ""}high-${props.row.taken_on ?? ""}`}>
      {t("portal.readings.highConsumption")}
    </StatusChip>
  );
}

function usedText(row: PortalReading): string | null {
  const said = row.used_since_display;
  if (said === null) return null;
  const grouped = formatQuantity(row.used_since, row.unit);
  return grouped !== null && digitsOf(grouped) === digitsOf(said) ? grouped : said;
}

/** Every digit of a rendered quantity, in order, and nothing else. */
function digitsOf(text: string): string {
  return text.replace(/\D/g, "");
}

/**
 * The method, in words, with the correction opening underneath it.
 *
 * ⚠ **THE CHIP IS AS PROMINENT AS THE NUMBER BESIDE IT** — that is
 * `BR-CWP-071` on screen, not a paraphrase of it. A method tucked into a
 * tooltip would be the same as not showing it.
 *
 * ⚠ **AND *AS PROMINENT AS* IS NOT *A CHIP ON EVERY ROW*** — see `CHIPPED`
 * above. Plain body text in its own column is as prominent as the figure beside
 * it; the chip is what marks the row that differs.
 */
function HowCell(props: {
  row: PortalReading;
  open: boolean;
  onOpen: (key: string | null) => void;
  /** ⚠ **THE SCREEN DRAWS EVERY READING TWICE — ONCE AS A TABLE ROW AND ONCE
   *  AS A PHONE CARD — AND ONLY ONE IS EVER VISIBLE** (the switch is CSS, and
   *  `bills/Bills.tsx` records the same shape). Two elements carrying
   *  `data-how="2026-08-31"` would make every existing assertion ambiguous, so
   *  the card marks its own. Empty for the table, which is what every test
   *  written before today already reads. */
  mark?: string;
}) {
  const { t } = useTranslation();
  // ⚠ **THE TENANT'S OWN FORMAT, NOT THE WIRE'S ISO STRING**
  // (`DEF-CWP-4172`). The correction sentence interpolated
  // `correction.corrected_on` raw, so a customer on a utility that asks for
  // `MM/DD/YYYY` read *"…corrected it when the meter was read on
  // **2026-05-02**"* two lines under a `TAKEN` column reading `04/30/2026` —
  // the same date, written two ways, on the one screen a customer opens to
  // dispute a bill. Every other date here already went through this hook.
  const asDate = usePortalDate();
  const { row } = props;
  const correction = row.correction;
  const mark = props.mark ?? "";

  const chipped = CHIPPED[row.how];
  return (
    <span className="flex flex-col gap-1">
      {chipped === undefined ? (
        // Plain text, at the same size as the figure beside it — the drawing's
        // *Read by a meter reader* and *You sent it in*.
        <span data-how={`${mark}${row.taken_on ?? ""}`}>{t(`portal.readings.how.${row.how}`)}</span>
      ) : (
        // The exception, and the only chip in the column: `ESTIMATED`, with a
        // plain *then corrected* after it when a real read has since replaced
        // it. Two spans and not one string, because the drawing emphasises the
        // first half and not the second.
        <span className="flex flex-wrap items-center gap-2" data-how={`${mark}${row.taken_on ?? ""}`}>
          <StatusChip tone={chipped} testKey={`${mark}how-${row.taken_on}`}>
            {t("portal.readings.how.estimated")}
          </StatusChip>
          {row.how === "estimated_corrected" ? (
            <span>{t("portal.readings.thenCorrected")}</span>
          ) : null}
        </span>
      )}
      {correction ? (
        <>
          <button
            type="button"
            className="cursor-pointer border-0 bg-transparent p-0 text-left text-base text-neutral-700 underline"
            aria-expanded={props.open}
            data-open-correction={`${mark}${row.taken_on ?? ""}`}
            onClick={() => props.onOpen(props.open ? null : (row.taken_on ?? null))}
          >
            {props.open ? t("portal.readings.hideWhy") : t("portal.readings.whyCorrected")}
          </button>
          {props.open ? (
            <span className="text-base text-neutral-700" data-correction={`${mark}${row.taken_on ?? ""}`}>
              {/* `BR-CWP-072` — the reason AND the size. ⚠ When the estimate
                  carried no dial figure (`BR-MET-028`: an estimate is a
                  consumption, because nobody read a dial) the shorter sentence
                  is written — never a `0` standing in for the figure. */}
              {/* ⚠ **GROUPED HERE TOO (`DEF-CWP-4009`, the second half).**
                  The column above was grouped and this caption was not, so one
                  screen printed `153,040` in the table and `144600` two lines
                  under it — the same kind of number, written two ways. Both of
                  these ARE dial figures (a register index the customer checks
                  against the box), so both go through the kit's one place that
                  knows how. `TC-2` pinned the ungrouped form and was amended
                  with this change; that assertion is the reason the first
                  sweep stopped at the column. */}
              {correction.estimated_reading_display
                ? t("portal.readings.correctedWithBoth", {
                    estimated: formatDialFigure(correction.estimated_reading_display) ?? "",
                    corrected: formatDialFigure(correction.corrected_to_display) ?? "",
                    date: asDate(correction.corrected_on) || "",
                  })
                : t("portal.readings.correctedWithoutDial", {
                    corrected: formatDialFigure(correction.corrected_to_display) ?? "",
                    date: asDate(correction.corrected_on) || "",
                  })}{" "}
              {/* `BR-CWP-069`, said out loud where it matters. */}
              {t("portal.readings.notChargedTwice")}
            </span>
          ) : null}
        </>
      ) : null}
    </span>
  );
}


/**
 * `CPB-09` — *"Next read: Sep 30 · in 22 days"*.
 *
 * ⚠ **THE SERVER SHIPS A DATE AND A COUNT; THE CATALOGUE WRITES THE SENTENCE**
 * (B14 rule 35). Hindi and Japanese put the number in a different place in the
 * sentence, so an English string from a server would make ten of the eleven
 * catalogues impossible. The month is written by `Intl`, never by a catalogue
 * list of twelve names.
 *
 * ⚠ **THREE SENTENCES, NOT ONE WITH A NUMBER IN IT.** *We are reading meters
 * now* is a different fact from a countdown — a crew already on the route is not
 * *"in 0 days"* — and *tomorrow* is its own key because *"in 1 days"* is the
 * off-by-one a customer actually notices.
 *
 * ⚠ **NOTHING SCHEDULED DRAWS NOTHING AT ALL** (`BR-CWP-093`). A dash above a
 * list of readings reads as a date we lost.
 */
function NextReadLine(props: { next: PortalNextRead | null }) {
  const { t, i18n } = useTranslation();
  const next = props.next;
  if (next === null) return null;
  if (next.open_now) {
    return (
      <p className="m-0 mb-3 text-body text-neutral-700" data-next-read="">
        {t("portal.readings.readingNow", { until: monthDayText(next.to, i18n.language) })}
      </p>
    );
  }
  const when =
    next.days_until === 0
      ? t("portal.readings.nextReadToday")
      : next.days_until === 1
        ? t("portal.readings.nextReadTomorrow")
        : t("portal.readings.nextReadInDays", { count: next.days_until });
  return (
    <p className="m-0 mb-3 text-body text-neutral-700" data-next-read="">
      {t("portal.readings.nextRead", {
        date: monthDayText(next.from, i18n.language),
        when,
      })}
    </p>
  );
}

/** `Sep 30` in the reader's own language — `Intl`, never twelve catalogue names. */
function monthDayText(iso: string, language: string): string {
  return new Intl.DateTimeFormat(language, {
    month: "short",
    day: "numeric",
    timeZone: "UTC",
  }).format(new Date(`${iso}T00:00:00Z`));
}
