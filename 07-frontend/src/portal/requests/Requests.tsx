// ── Trace ──────────────────────────────────────────────
// Story:    US-CWP-060 (EP-CWP-11) — *"What do you need: six cards, named by
//           what the customer wants."* Screen: CWP-046 (blueprint `P32`)
// Rules:    BR-CWP-075 (the customer makes four of the eleven transitions and
//           no more) · BR-CWP-076 (every row carries channel `customer_portal`)
//           · BR-CWP-080 (moving out and stopping service are DIFFERENT, and
//           the cards say which) · BR-CWP-093 (nothing empty ever appears) ·
//           BR-CWP-056 (a control that may not be used yet is disabled WITH
//           its reason) · B14 rule 21 · rule 31 (no database id on screen) ·
//           rule 32 (one sentence per section) · rule 33 (a refusal is five or
//           six words) · rule 35 (each catalogue in its own language) ·
//           rule 36 (compose the kit)
// Open:     OQ-CWP-1680 — should a request a CLERK raised at the counter
//           appear in this list? Until it is ruled, this screen says in words
//           that the list is what was asked ONLINE.
// Tests:    src/portal/requests/Requests.dom.test.tsx
// Impacts:  src/portal/api/portalClient.ts `getRequestHub`
// ───────────────────────────────────────────────────────
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { PageHeader } from "@/components/PageHeader";

import { PortalScreen, PortalState } from "../components/states";
import { Link } from "react-router-dom";

import {
  Card,
  CardGrid3,
  ErrandCard,
  ErrandLink,
  HeldButton,
  SectionTitle,
  SegmentedChoice,
  StatusChip,
  usePortalPath,
  type ChipTone,
} from "../components/primitives";
// ⚠ **DATES GO THROUGH THE TENANT'S OWN FORMAT, NEVER STRAIGHT TO THE
// SCREEN** (`DEF-CWP-4204`). Pine Hill asks for `MM/DD/YYYY`; this screen
// printed the wire's `2026-09-06`. `usePortalDate` returns the server's
// string unchanged when a tenant has stated no format — declining to say
// is honest, inventing one for a utility in Berlin is what shipped a
// five-hour error. Wave M took this fix (`DEF-CWP-4138`) and wave L took
// it (`DEF-CWP-4178`); wave I's five screens were never moved.
import { usePortalDate } from "../components/regional";
import { PortalListTable } from "../components/listTable";
import { EyeIcon } from "@/components/icons";
import {
  getRequestHub,
  type PortalOpenRequest,
  type PortalRequestHub,
} from "../api/portalClient";

/**
 * A catalogue key, or the utility's own words.
 *
 * ⚠ **A TENANT MAY RENAME A CARD AND ITS LABEL IS THEN NOT A KEY** (TC-8). The
 * server serves whatever is configured; `i18next` returns the key itself when
 * it does not know it, so *"Move out"* configured by Pine Hill renders as
 * *"Move out"* and `portal.errand.move_out.title` renders as the translated
 * sentence. One expression covers both, and neither needs the screen to know
 * which it is looking at.
 */
function words(t: (key: string) => string, value: string | null): string {
  return value ? t(value) : "";
}

/** The eleven request states, in the customer's words rather than ours.
 *
 * ⚠ **THE STATE CODE TRAVELS AND THE CATALOGUE WRITES THE WORD** (B14 rule
 * 35). *Waiting for us to look at it* in eleven languages is eleven catalogue
 * lines; one English sentence from a server is ten screens that cannot be
 * translated.
 *
 * ⚠ **AND A STATE WE HAVE NO WORD FOR IS NOT RENDERED RAW.** `submitted` is a
 * word this product invented for itself, and printing `in_fulfilment` on a
 * customer's screen would be an internal code in clerk-facing copy — which is
 * B14 rule 31's neighbour and rule 32's own list. An unknown state falls back
 * to *with us*, which is true of every non-terminal state there is.
 *
 * ⚠ **IT HELD SEVEN OF THE ELEVEN AND THE FOUR MISSING ONES ARE THE FINISHED
 * STATES** (`DEF-CWP-4706`, 2026-09-08). Harmless while this panel could only
 * ever draw an open request; the moment `CPB-11` gave the list its closed half,
 * a WITHDRAWN request would have drawn the fallback chip *With us* — which is
 * the opposite of the truth about a request the customer themselves called
 * off. **And the vocabulary is now ONE map read by two screens**: this list and
 * `CWP-051` each had their own eleven-state catalogue and the two DISAGREED —
 * `submitted` read *With us* here and *Sent* there, `approved` read *Agreed*
 * here and *Approved* there — so a customer clicking a row watched the state
 * change words on the way in (`DEF-CWP-4709`). `portal.request.state.*` is the
 * survivor because it is the one that covers all eleven.
 */
const STATE_TONE: Record<string, ChipTone> = {
  draft: "neutral",
  submitted: "info",
  under_review: "info",
  more_info: "warning",
  approved: "success",
  in_fulfilment: "info",
  on_hold: "warning",
  completed: "success",
  refused: "danger",
  withdrawn: "neutral",
  closed: "neutral",
};

const KNOWN_STATES = new Set(Object.keys(STATE_TONE));

/**
 * `CWP-046` — *"tell us what you need, in your own words"*.
 *
 * ⚠ **THE CARDS ARE THE UTILITY'S LIST AND NOT A LITERAL HERE** (TC-8). The
 * six that ship are a SEED on the utility's own settings row, exactly as
 * `CWP-010`'s quick-service cards are; a tenant that renames *Move out* sees
 * the new label because this screen never held the old one.
 *
 * ⚠ **THREE OF THE SIX ARE HELD TODAY AND THE SERVER DECIDES WHICH** (hard-won
 * law 2). `CWP-048` (moving out), the move-home form and the add-a-service form
 * are not built, and a card linking to one of them would be a link with no
 * screen behind it — the exact failure that law names. The card renders with
 * the kit's held control and its reason instead, so a customer can see the
 * utility does this and can tell the online route is not open yet.
 *
 * ⚠ **IT SAID FOUR UNTIL 2026-09-05, AND THE FOURTH WAS A SHUT DOOR OVER A
 * LIVE SCREEN.** *Something else* was greyed with *"Not online yet — ring
 * us"* while `CWP-054` — heading ASK US SOMETHING, routed, tested — had been
 * answering at `/ask-a-question` since **73 minutes after the hold was
 * written**. Hard-won law 2's mirror: a rule of the form *held until X* rots
 * on the day X arrives, because landing the screen and releasing the control
 * are two acts and only the first feels like the work. What goes red on that
 * day now is `06-backend/tests/test_cwp_holds_expire.py`, which reads the
 * server's `ERRAND_HELD_UNTIL` against this front end's own screen register.
 *
 * ⚠ **AND THE HELD/LIVE DECISION IS ONE MAP ON THE SERVER, NOT TWO.** If this
 * screen decided it, the wave that builds `CWP-048` would have to remember to
 * change the front end as well as the back — which is how the service list came
 * to be typed out by hand in two places (`CLAUDE.md`, hard-won law 2's own
 * example).
 *
 * ⚠ **THE LIST SAYS WHAT IT HOLDS** (`OQ-CWP-1680`). A request a clerk raised
 * at the counter carries no link to this login — a portal service request
 * carries no account at all, `BR-CWP-026` — so it cannot appear here, and the
 * screen states that rather than letting a customer read the list as everything
 * they have ever asked for.
 */
export function RequestsView() {
  const { t } = useTranslation();
  const path = usePortalPath();
  const asDate = usePortalDate();
  const [hub, setHub] = useState<PortalRequestHub | null>(null);
  const [failed, setFailed] = useState(false);
  // ⚠ **THE SCOPE IS PER-VIEWER STATE AND NOT AN ADDRESS** (`CPB-11`). See the
  // panel below for why this is a switch rather than the drawing's second
  // screen.
  const [scope, setScope] = useState<"open" | "all">("open");
  /** R-10's way out, wired to a real read — see `Usage.tsx`'s note on why a
   *  `Try again` that calls nothing is worse than no button at all. */
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let live = true;
    setHub(null);
    setFailed(false);
    getRequestHub()
      .then((answer) => {
        if (live) setHub(answer);
      })
      .catch(() => {
        if (live) setFailed(true);
      });
    return () => {
      live = false;
    };
  }, [attempt]);

  // ⚠ **THE HEAD IS BUILT ONCE AND RENDERS ON EVERY BRANCH, LOADING INCLUDED**
  // (`DEF-CWP-4000`; audit D1, delta X4/X5). It composes the shared
  // `components/PageHeader.tsx` — the ONE page head B14 rule 2 names, which
  // fifteen portal files already used and twenty-eight signed-in screens did
  // not. A head that lived only in the happy-path return would leave the page
  // with no `<h1>` for as long as the request takes.
  const head = (
    <PageHeader
      kicker={t("portal.kicker.requests")}
      title={t("portal.requests.title")}
    />
  );

  // ⚠ **ONE CARD, THREE SENTENCES — R-22 (PO 2026-09-11, verbatim:
  // *"differntiate it using text message"*), AND THE KIND IS IN THE DOM.** The
  // two branches below already differed by their words; what they could not do
  // is SAY which state they were, so nothing in this repo could check that the
  // failed address and the loading address do not render the same thing.
  // `PortalState` puts `data-portal-state` on the card and carries R-10's way
  // out beside the sentence rather than a page away.
  if (failed) {
    return (
      <PortalScreen screen="CWP-046" head={head}>
        <PortalState
          kind="failed"
          testId="requests"
          sentence={t("portal.requests.couldNotRead")}
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
  if (hub === null) {
    return (
      <PortalScreen screen="CWP-046" head={head}>
        <PortalState kind="loading" testId="requests" sentence={t("portal.requests.reading")} />
      </PortalScreen>
    );
  }

  // ⚠ **ONE ORDER ACROSS BOTH HALVES.** The server orders each list newest
  // first; concatenating them would print every open request above every
  // closed one whatever the dates said, so a request raised last week would
  // sit under one raised last year. The SORT still runs on the ISO string,
  // which is the only thing that sorts correctly.
  const shown =
    scope === "all"
      ? [...hub.open_requests, ...hub.closed_requests].sort((a, b) =>
          (b.raised_on ?? "").localeCompare(a.raised_on ?? ""),
        )
      : hub.open_requests;

  return (
    // ⚠ **A LITERAL `<div data-screen="CWP-046">`, NOT `PortalScreen` — see
    // `usage/Usage.tsx`'s note.** Three SOURCE scanners find a portal screen by
    // grepping this exact string and none knows about a `screen=` prop.
    <div data-screen="CWP-046" className="flex flex-col gap-4">
      {head}
      <Card testId="requests-errands">
        {/* B14 rule 32 — one sentence for the section. */}
        <p className="text-body text-neutral-700" data-requests-lead="">
          {t("portal.requests.lead")}
        </p>
        <CardGrid3>
          {hub.errands.map((errand) => (
            <ErrandCard
              key={errand.code}
              cardKey={errand.code}
              title={words(t, errand.label)}
              description={words(t, errand.hint)}
              action={
                errand.to ? (
                  <ErrandLink label={t("portal.requests.start")} to={errand.to} />
                ) : (
                  <HeldButton
                    label={t("portal.requests.start")}
                    reason={t(`portal.requests.held.${errand.held_reason ?? "not_online_yet"}`)}
                  />
                )
              }
            />
          ))}
        </CardGrid3>
      </Card>

      <Card testId="requests-open">
        {/* ⚠ **`All requests →` IS A SWITCH HERE AND A SECOND SCREEN IN THE
            DRAWING, AND THE DIFFERENCE IS DELIBERATE** (`CPB-11`,
            `DEF-CWP-4203`). `08-screen-layouts.md` puts *All requests →* at the
            top right of this panel; it allocates no `CWP-###` for the screen it
            would open, and `G82` refuses a portal route whose id nobody issued
            — *"an invented id is an id nobody can look up in a bug report"*.
            A switch delivers the outcome the drawing is after (a customer can
            reach a request that is finished) at this screen's own address and
            invents nothing. Recorded in the decision log of 2026-09-08 so the
            next reader does not "fix" the screen to match the picture.

            ⚠ **AND IT IS ABSENT UNTIL THERE IS SOMETHING BEHIND IT**
            (`BR-CWP-093`). A customer who has never finished a request is
            offered no filter over a list with one half — and the control
            appears on its own the day one closes, so it cannot rot. */}
        <div className="flex flex-wrap items-baseline justify-between gap-3">
          <SectionTitle>
            {t(scope === "all" ? "portal.requests.allTitle" : "portal.requests.openTitle")}
          </SectionTitle>
          {hub.closed_requests.length > 0 ? (
            <SegmentedChoice
              label={t("portal.requests.scopeLabel")}
              testId="requests-scope"
              current={scope}
              onChoose={(key) => setScope(key === "all" ? "all" : "open")}
              options={[
                { key: "open", label: t("portal.requests.scopeOpen") },
                { key: "all", label: t("portal.requests.scopeAll") },
              ]}
            />
          ) : null}
        </div>
        {shown.length === 0 ? (
          // B14 rule 17 / BR-CWP-093 — a sentence naming what will fill it,
          // never a table of dashes (TC-6).
          <p className="text-body text-neutral-600" data-requests-empty="">
            {t("portal.requests.none")}
          </p>
        ) : (
          <div className="mt-1">
            <PortalListTable
              screen="CWP-046"
              caption={t(scope === "all" ? "portal.requests.allCaption" : "portal.requests.caption")}
              rows={shown}
              rowKey={(row) => row.reference ?? `row-${shown.indexOf(row)}`}
              empty={
                <p className="text-body text-neutral-600" data-requests-empty="">
                  {t("portal.requests.none")}
                </p>
              }
              // ⚠ **NO FOOTER ON THE OPEN LIST, ON THE DRAWING'S AUTHORITY —
              // AND ONE ON THE FULL LIST, FOR THE REASON THE DRAWING GIVES.**
              // `08-screen-layouts.md` gives `CWP-046` a `Panel` **OPEN
              // REQUESTS** holding a `MiniTable` and one icon: a panel on an
              // errand page, not a list screen, and a customer has two or three
              // things open. *All of them* is the other thing — everything they
              // have ever asked us, which grows for as long as they are a
              // customer — so it takes the shared pager rather than printing a
              // list with no end (B14 rule 16).
              footer={scope === "all"}
              icons={[
                {
                  key: "view",
                  icon: <EyeIcon />,
                  label: () => t("portal.requests.viewRow"),
                  // ⚠ **THE VISIBLE VALUE AND THE PATH SEGMENT ARE BOTH THE
                  // `SR-` NUMBER** (B14 rule 31) — the same door `ReferenceCell`
                  // already opens, now also as the icon the drawing draws
                  // beside it.
                  to: (row) => path(`/requests/${encodeURIComponent(row.reference ?? "")}`),
                  // `/requests/` with an empty segment opens nothing, so a row
                  // carrying no reference gets the reason instead of a dead
                  // link (`BR-CWP-093`, `BR-SHL-025`).
                  reason: (row) =>
                    row.reference === null || row.reference === ""
                      ? t("portal.requests.cannotTrack")
                      : null,
                },
              ]}
              columns={[
              // ⚠ **WHAT THEY ASKED FOR COMES FIRST, THE REFERENCE SECOND**
              // (CR-085 group I). The drawing's column order is *What you
              // asked · Reference · Raised · Where it is*, and its naming note
              // says why: a request is titled by what the customer wanted, in
              // their own words, not by our filing number. The reference is
              // still the door and is still bold — a person scanning the list
              // for *the one about my bill* reads the sentence, and a person
              // on the telephone reads the number.
                {
                  key: "what",
                  label: t("portal.requests.colWhat"),
                  cell: (row) => <RequestWhat row={row} />,
                },
                {
                  key: "reference",
                  label: t("portal.requests.colReference"),
                  // ⚠ The human reference, never a row id (B14 rule 31), and a
                  // stated absence where the record carries none.
                  cell: (row) => (
                    <ReferenceCell reference={row.reference} index={shown.indexOf(row)} />
                  ),
                },
                {
                  key: "raised",
                  label: t("portal.requests.colRaised"),
                  sortable: true,
                  // The SORT still runs on the ISO string, which is the only
                  // thing that sorts correctly; only the CELL is formatted.
                  sortValue: (row) => row.raised_on,
                  cell: (row) => (row.raised_on ? asDate(row.raised_on) : "—"),
                },
                {
                  key: "status",
                  label: t("portal.requests.colStatus"),
                  cell: (row) => <RequestStatus row={row} />,
                },
              ]}
            />
          </div>
        )}
        {hub.lists_only_portal_requests ? (
          <p className="text-base text-neutral-600" data-requests-scope="">
            {t("portal.requests.onlineOnly")}
          </p>
        ) : null}
      </Card>
    </div>
  );
}

/**
 * **WHAT THIS REQUEST IS — and it used to be the sentence a CLERK reads.**
 *
 * ⚠ **`DEF-CWP-4198`, AND THE HALF OF IT THE ROW CALLS *"a design decision and
 * not a formatting one"*.** This column is documented as the customer's own
 * words. Four of the six portal shapes have nowhere else to put their facts
 * (`service_requests` carries no category column, `DEF-CWP-3881`), so they
 * compose a worklist sentence into `what_they_said` and this table printed it
 * verbatim. Read off Ana's live screen on 2026-09-08: **271 characters**
 * beginning *"Queried through the customer portal bill BL-2608-000044
 * (2026-07-01 to 2026-07-31, 843.36 USD): … Their reason: …"* — two ISO dates,
 * a doubled full stop, and the customer described to herself in the third
 * person.
 *
 * ⚠ **THE TITLE IS THE SERVER'S AND ITS WORDS ARE THE CATALOGUE'S** (B14 rule
 * 35): `customers_seam.request_kind` classifies the row by the marker its own
 * write put there, the same mechanism `open_query_on_bill` has used since wave
 * R, and a KIND CODE travels.
 *
 * ⚠ **AND `null` IS NOT A GAP.** A reported problem and an application write
 * what the customer actually typed, so there is nothing to replace and their
 * words are shown exactly as before.
 */
function RequestWhat(props: { row: PortalOpenRequest }) {
  const { t } = useTranslation();
  const title = props.row.title;
  if (title === null) {
    return <span data-what="their-words">{props.row.what ?? t("portal.requests.noWords")}</span>;
  }
  if (title.kind === "bill_query") {
    return (
      <span data-what="bill_query">
        {title.number === null
          ? t("portal.requests.kind.billQueryPlain")
          : t("portal.requests.kind.billQuery", { number: title.number })}
      </span>
    );
  }
  const key = KIND_KEYS[title.kind];
  if (key === undefined) {
    // ⚠ **A KIND THIS SCREEN HAS NO WORD FOR IS NOT RENDERED RAW.** `i18next`
    // returns the KEY when it does not know one, so a seventh marker added on
    // the server before this map learns it would print
    // `portal.requests.kind.undefined` in a customer's table. Their own words
    // are always a true answer; the code never is.
    return <span data-what="their-words">{props.row.what ?? t("portal.requests.noWords")}</span>;
  }
  return <span data-what={title.kind}>{t(`portal.requests.kind.${key}`)}</span>;
}

/** kind code → the catalogue's own spelling of it. ⚠ **A KIND WITH NO ENTRY
 *  FALLS BACK TO THE CUSTOMER'S WORDS RATHER THAN PRINTING THE CODE** — an
 *  internal code in clerk-facing copy is B14 rule 31's neighbour. */
const KIND_KEYS: Record<string, string> = {
  question: "question",
  stop_service: "stopService",
  // CR-183-BRC10 B4 — *Restart my service now*.
  restart_now: "restartNow",
  payment_plan: "paymentPlan",
  help_paying: "helpPaying",
  quick_ask: "quickAsk",
};

/**
 * The request's reference, and it is the door to `CWP-051`.
 *
 * ⚠ **`CWP-051` *Track your request* HAD NO DOOR IN THE PRODUCT**
 * (`DEF-CWP-3954`) — this table listed a customer's open requests and none of
 * the rows could be opened, which is the same shape as the bills list a tab
 * away. `08-screen-layouts.md` draws the reference in bold with an eye icon
 * beside it; the bold reference IS the control here, for the same reason the
 * bill number is on `CWP-027`.
 *
 * ⚠ **THE VISIBLE VALUE AND THE PATH SEGMENT ARE BOTH THE `SR-` NUMBER**
 * (B14 rule 31). `screenIds.ts` records it for this very route — *"`:reference`
 * IS AN `SR-` NUMBER and `:number` IS A `BL-` NUMBER — not one database id
 * between them"* — and it is what the customer reads out on the telephone.
 *
 * ⚠ **A ROW WITH NO REFERENCE IS STILL DRAWN AND IS NOT A LINK.** `/requests/`
 * with an empty segment opens nothing, and a stated absence is the rule
 * (`BR-CWP-093`).
 */
function ReferenceCell(props: { reference: string | null; index: number }) {
  const { t } = useTranslation();
  const path = usePortalPath();
  const reference = props.reference ?? "";
  if (reference === "") {
    return (
      <span className="font-bold" data-reference={props.index}>
        {t("portal.requests.noReference")}
      </span>
    );
  }
  return (
    <Link
      to={path(`/requests/${encodeURIComponent(reference)}`)}
      className="font-bold text-neutral-900 no-underline hover:underline"
      data-reference={props.index}
      data-request-link={reference}
    >
      {reference}
    </Link>
  );
}

/**
 * The chip.
 *
 * ⚠ **WAITING ON DOCUMENTS OVERRIDES THE STATE, BECAUSE IT IS THE ONE THING
 * THE CUSTOMER CAN ACT ON** (TC-4). A request sitting in `more_info` because we
 * need two documents reads *we need two documents* — the count comes from the
 * server and `_one` / `_other` does the grammar, so *one document* and *two
 * documents* are one catalogue entry rather than a sentence assembled here.
 */
function RequestStatus(props: { row: PortalOpenRequest }) {
  const { t } = useTranslation();
  const { row } = props;
  if (row.documents_wanted > 0) {
    return (
      <StatusChip tone="warning" testKey="documents-wanted">
        {t("portal.requests.documentsWanted", { count: row.documents_wanted })}
      </StatusChip>
    );
  }
  const known = KNOWN_STATES.has(row.status);
  return (
    <StatusChip tone={known ? STATE_TONE[row.status] : "neutral"} testKey={row.status}>
      {known ? t(`portal.request.state.${row.status}`) : t("portal.requests.state.withUs")}
    </StatusChip>
  );
}
