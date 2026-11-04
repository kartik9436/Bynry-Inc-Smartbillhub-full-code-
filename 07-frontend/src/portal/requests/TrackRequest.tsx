// ── Trace ──────────────────────────────────────────────
// Story:    US-CWP-063 (EP-CWP-11) — track your request. Screen: CWP-051
//           (blueprint `P37`)
// Rules:    BR-CWP-078 (transitions plus notes flagged customer-visible, and
//           NEVER internal routing comments) · ⚠ BR-CWP-079 (*withdrawable
//           until approved*) is **SUPERSEDED 2026-09-19** by the PO ruling on
//           `OQ-CUS-12486` — the customer's door closed with the clerk's and
//           a withdrawal is a refusal REASON now; the screen draws no
//           withdraw control at all ·
//           BR-CWP-077 (a refusal always carries its reason) · B14 rule 31
//           (the request is named by its `SR-` number, never a row id) ·
//           rule 21 (Tailwind utilities; `portal/` is on route-b-migrated.txt)
//           · rule 32 (one sentence per section) · rule 33 (a refusal is five
//           or six words) · rule 36 (compose the kit)
// Open:     OQ-CWP-1680 — a service request carries no account, so *mine* is
//           matched on the login's own contact phone.
// Tests:    src/portal/requests/TrackRequest.dom.test.tsx
// Impacts:  src/portal/api/portalClient.ts `getRequest` · `addRequestNote`
//           (`withdrawRequest` is no longer called from any screen — see the
//           supersession above; the endpoint stays and refuses cleanly)
// ───────────────────────────────────────────────────────
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { PageHeader } from "@/components/PageHeader";

// ⚠ **DATES GO THROUGH THE TENANT'S OWN FORMAT, NEVER STRAIGHT TO THE
// SCREEN** (`DEF-CWP-4204`). Pine Hill asks for `MM/DD/YYYY`; this screen
// printed the wire's `2026-09-06`. `usePortalDate` returns the server's
// string unchanged when a tenant has stated no format — declining to say
// is honest, inventing one for a utility in Berlin is what shipped a
// five-hour error. Wave M took this fix (`DEF-CWP-4138`) and wave L took
// it (`DEF-CWP-4178`); wave I's five screens were never moved.
import { usePortalDate } from "../components/regional";


import {
  ButtonRow,
  Card,
  ChecklistTimeline,
  CommitButton,
  ErrandLink,
  FormField,
  KVList,
  SectionTitle,
  StatusChip,
  TextInput,
  TwoCol,
  usePortalPath,
  type ChipTone,
} from "../components/primitives";
import { PortalScreen, PortalState } from "../components/states";
import {
  addRequestNote,
  getRequest,
  type PortalRequestDetail,
} from "../api/portalClient";
import { Announced } from "../components/a11y";

/** The six steps `CWP-051` draws, in the server's own order. The KEYS are the
 *  server's; the WORDS are the eleven catalogues'. */
const STEP_KEYS = [
  "sent",
  "picked_up",
  "we_need_something",
  "we_decide",
  "in_hand",
  "finished",
] as const;

/** A request's state → the chip's tone. ⚠ `refused` is `danger` and `withdrawn`
 *  is `neutral`: one is the utility saying no and the other is the customer
 *  changing their mind, and painting them alike would read as a refusal
 *  somebody never received. */
const TONE: Record<string, ChipTone> = {
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

/**
 * `CWP-051` — where a request has got to, in the customer's own half of a
 * history the clerk already has.
 *
 * ⚠ **THE INTERNAL ROUTING NOTE IS NOT FILTERED HERE — IT NEVER ARRIVES.**
 * `BR-CWP-078` is enforced in `apps/portal/seams/customers_seam.py`, which
 * projects the clerk's read and names what it drops; this component renders
 * whatever it is sent. A screen doing the filtering would be one careless
 * `JSON.stringify` away from publishing what it was hiding.
 *
 * ⚠ **THERE IS NO WITHDRAW BUTTON ANY MORE, AND `BR-CWP-079` IS SUPERSEDED**
 * (PO ruling 2026-09-19, `OQ-CUS-12486`): *"if customer dont want it - they
 * will call and clark will refuse it. thats'it . keep it simple"*. The
 * `withdraw` move left the request's state table the same day, so
 * `may_withdraw` — which now genuinely reads that table (`DEF-CUS-5874`) — is
 * false in every state. **A withdrawal is a REASON now, not a state:**
 * `Applicant withdrew` is one of the five the clerk's Refuse dialog offers.
 *
 * ⚠ **`withdrawn` KEEPS ITS CHIP TONE AND ITS STEP WORD BELOW, DELIBERATELY.**
 * Nothing was migrated, so rows that were withdrawn before the ruling are
 * still withdrawn and must still read correctly on a customer's own screen.
 * What went is the way IN, never the way those rows are displayed.
 *
 * ⚠ **A REFUSAL SHOWS ITS REASON** (`BR-CWP-077`), and where a refused request
 * somehow carries none the screen says the office will explain rather than
 * drawing an empty panel — `BR-CWP-093`, *nothing empty ever appears*.
 */
export function TrackRequestView(props: { reference: string }) {
  const { t } = useTranslation();
  const asDate = usePortalDate();
  const path = usePortalPath();
  const [request, setRequest] = useState<PortalRequestDetail | null>(null);
  const [failed, setFailed] = useState(false);
  const [note, setNote] = useState("");
  const [working, setWorking] = useState(false);
  const [refused, setRefused] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    setFailed(false);
    getRequest(props.reference)
      .then((answer) => {
        if (live) setRequest(answer);
      })
      .catch(() => {
        if (live) setFailed(true);
      });
    return () => {
      live = false;
    };
  }, [props.reference]);

  async function reload() {
    setRequest(await getRequest(props.reference));
  }

  async function send() {
    setWorking(true);
    setRefused(null);
    try {
      await addRequestNote(props.reference, note);
      setNote("");
      await reload();
    } catch {
      setRefused(t("portal.request.couldNotAddNote"));
    } finally {
      setWorking(false);
    }
  }

  // ⚠ **THE HEAD IS BUILT ONCE AND RENDERS ON EVERY BRANCH, LOADING INCLUDED**
  // (`DEF-CWP-4000`; audit D1, delta X4/X5). It composes the shared
  // `components/PageHeader.tsx` — the ONE page head B14 rule 2 names, which
  // fifteen portal files already used and twenty-eight signed-in screens did
  // not. A head that lived only in the happy-path return would leave the page
  // with no `<h1>` for as long as the request takes.
  // ⚠ **THE HEAD NAMES THE REQUEST, AND UNTIL 2026-09-08 IT DID NOT**
  // (`DEF-CWP-4201` row 51.1, `CR-085` `CPB-12`). Every request in the product
  // was headed *"Track your request"* with the reference on a line of its own
  // underneath, so a customer with two open could not tell from the head which
  // one they had opened. `08-screen-layouts.md` heads it *"Move out · 1408 Elm
  // St · A"* with the reference as the KICKER, and that is the shape here: the
  // `SR-` number kicks, the request's own title is the `<h1>`, and *Raised …*
  // is the roll-up line the drawing puts under it.
  //
  // ⚠ **THE TITLE IS THE SERVER'S DERIVED KIND** (`customers_seam.request_kind`)
  // and its words are the catalogue's (B14 rule 35). Where the server could
  // not classify the row — a reported problem, an application — the customer's
  // OWN words are the answer and the old title is the fallback rather than a
  // blank `<h1>`.
  const head = (
    <PageHeader
      kicker={request?.reference ?? t("portal.kicker.requests")}
      title={requestTitle(t, request)}
      rollup={
        request?.raised_at ? (
          <span data-raised="">
            {t("portal.request.raisedOn", { date: asDate(request.raised_at) })}
          </span>
        ) : undefined
      }
      // ⚠ **THE STATE SITS WITH THE IDENTITY, WHICH IS THE KIT'S OWN SLOT.**
      // `PageHeader`'s `status` renders it under the `<h1>` — *"state is not an
      // action"*, `DEF-966` — and it was a chip on a line of its own below the
      // roll-up, orphaned to the right of an empty row. Same words, same tone,
      // one fewer hand-rolled row (B14 rule 36).
      status={
        request === null ? undefined : (
          <StatusChip tone={TONE[request.status] ?? "neutral"} testKey="request-status">
            {t(`portal.request.state.${request.status}`)}
          </StatusChip>
        )
      }
    />
  );

  // The thread, composed once so the card above can be guarded on it.
  const thread = request === null ? [] : threadOf(request);

  if (failed) {
    return (
      <PortalScreen screen="CWP-051" head={head}>
        {/* B14 rule 33 — five or six words, and ONE sentence for an unknown
            reference, another customer's and another utility's alike.
            R-10's way out beside it is the list this reference would have been
            in: whatever went wrong, *your requests* is a page that works. */}
        <PortalState
          kind="failed"
          testId="request-missing"
          sentence={t("portal.request.notFound")}
          waysOut={[
            {
              label: t("portal.request.backToRequests"),
              to: path("/requests"),
              tone: "primary",
              testKey: "requests",
            },
          ]}
        />
      </PortalScreen>
    );
  }
  if (request === null) {
    return (
      <PortalScreen screen="CWP-051" head={head}>
        <PortalState kind="loading" testId="request" sentence={t("portal.request.reading")} />
      </PortalScreen>
    );
  }

  return (
    // ⚠ **A LITERAL `<div data-screen="CWP-051">`, NOT `PortalScreen` — see
    // `usage/Usage.tsx`'s note.** Three SOURCE scanners find a portal screen by
    // grepping this exact string and none knows about a `screen=` prop.
    <div data-screen="CWP-051">
      {head}
      <TwoCol
        main={
          <>
            <Card testId="request-progress">
              <SectionTitle>{t("portal.request.progress")}</SectionTitle>
              {/* ⚠ **THE LADDER SAID WHEN AND NEVER WHAT** (`DEF-CWP-4201`
                  row 51.4). Every step in `08-screen-layouts.md` carries a
                  right-hand description; live drew the date alone, so six rows
                  told a customer that something happened on the 8th and never
                  what it was.
                  ⚠ **AND ONE OF THE DRAWING'S THREE DESCRIPTIONS CANNOT BE
                  BUILT, WHICH IS A RULE AND NOT A GAP.** *"Sarah at the
                  office"* is the acting clerk, and
                  `customers_seam._customer_visible_events` drops the actor BY
                  NAME — *"who inside the utility touched it is the utility's
                  business"* (`BR-CWP-052`). It is not served, so it is not
                  drawn, and this comment is here so the next reader does not
                  go looking for a field that was removed on purpose. */}
              <ChecklistTimeline
                steps={STEP_KEYS.map((key) => {
                  const step = request.steps.find((row) => row.key === key);
                  return {
                    label: t(`portal.request.step.${key}`),
                    detail: step?.at ? asDate(step.at) : undefined,
                    note: stepNote(t, request, key, step?.state ?? "future"),
                    state: step?.state ?? "future",
                  };
                })}
              />
            </Card>
            {request.status === "refused" ? (
              <Card testId="request-refusal">
                <SectionTitle>{t("portal.request.refusedTitle")}</SectionTitle>
                <p className="text-body text-neutral-800" data-refusal-reason="">
                  {request.refusal_reason ?? t("portal.request.refusalReasonAbsent")}
                </p>
              </Card>
            ) : null}
            {/* ⚠ **THE GUARD COUNTED ONE LIST AND THE BODY RENDERED ANOTHER,
                AND THAT WAS LIVE** (CR-085 group I, walked at `SR-26-0022` on
                2026-09-08). `request.timeline.length` counts every row the
                server sent; the body drew only rows WITH A NOTE — and the
                server drops a transition's note by name (`BR-CWP-078`), so a
                request whose whole history is transitions, which is every
                request this portal has ever raised, drew the heading **WHAT WE
                HAVE TOLD YOU** over an empty list. `BR-CWP-093` in its plainest
                form, and no test could see it because both assertions in this
                file's TC-3 used a fixture that HAS a note.
                **So the thread is composed FIRST and the card is guarded on
                what will actually be drawn.** */}
            {thread.length > 0 ? (
              <Card testId="request-timeline">
                <SectionTitle>{t("portal.request.whatHappened")}</SectionTitle>
                <ul className="m-0 list-none p-0" data-timeline-notes={thread.length}>
                  {thread.map((row) => (
                    <li key={row.key} className="border-b border-neutral-200 py-2">
                      {/* ⚠ **WHO, THEN WHEN.** The drawing's every entry names
                          a speaker — *Aug 13 · You*, *Aug 14 · Us* — because a
                          thread where the two voices look alike is one a
                          customer re-reads to work out whose turn it is, which
                          is the call this screen exists to prevent. The
                          speaker is `note_type`: the customer's own answer is
                          written `customer_note` by `services._note` and
                          nothing else is. */}
                      <span className="text-base text-neutral-600">
                        {t(row.who === "you" ? "portal.request.saidByYou" : "portal.request.saidByUs")}
                        {/* ⚠ **WITH THE TIME.** These are instants, and the
                            drawing's entries read *Aug 14, 11:20 AM* — two
                            notes on one day are otherwise two rows with the
                            same stamp and no order a reader can see. */}
                        {asDate(row.at, true) === "" ? "" : ` · ${asDate(row.at, true)}`}
                      </span>
                      <p
                        className="m-0 text-body text-neutral-900"
                        data-note=""
                        data-said={row.who}
                      >
                        {row.text}
                      </p>
                    </li>
                  ))}
                </ul>
              </Card>
            ) : null}
          </>
        }
        rail={
          <>
            <Card testId="request-details">
              <SectionTitle>{t("portal.request.details")}</SectionTitle>
              <KVList rows={detailRows(t, request, asDate)} />
              {/* ⚠ **AN OPEN REQUEST WITH NOTHING OUTSTANDING SAYS SO OUT
                  LOUD.** `detailRows` drops the *waiting on* row when the
                  server sends `null`, correctly — a label with nothing beside
                  it reads as *waiting on nothing* — and the screen then said
                  NOTHING AT ALL about whose turn it is. The drawing states it
                  as a heading of its own for one reason, in its own words:
                  uncertainty about whose turn it is drives the follow-up call.
                  It is stated only while the request is OPEN, because on a
                  finished one it would be true and pointless. */}
              {request.is_open && (request.waiting_on === null || request.waiting_on === "") ? (
                <p className="text-body text-neutral-700" data-nothing-waiting="">
                  {t("portal.request.nothingWaiting")}
                </p>
              ) : null}
            </Card>
            {/* ⚠ **NO REPLY BOX ON A FINISHED THREAD** (the drawing's CLOSED
                state). A box that posts onto a request nobody is working is a
                control whose far end nobody reads — and the door out is the
                one the drawing offers instead: ask a new question. */}
            {request.is_open ? (
              <Card testId="request-say-more">
                <SectionTitle>{t("portal.request.addANote")}</SectionTitle>
                <FormField id="request-note" label={t("portal.request.noteLabel")}>
                  <TextInput id="request-note" multiline value={note} onChange={setNote} />
                </FormField>
                <ButtonRow>
                  <CommitButton
                    label={t("portal.request.sendNote")}
                    working={working}
                    ready={note.trim() !== ""}
                    reason={t("portal.request.sendNoteHeld")}
                    onClick={() => void send()}
                  />
                </ButtonRow>
              </Card>
            ) : (
              <Card testId="request-ask-again">
                <SectionTitle>{t("portal.request.finishedTitle")}</SectionTitle>
                <ButtonRow>
                  <ErrandLink label={t("portal.question.title")} to="/ask-a-question" />
                </ButtonRow>
              </Card>
            )}
            {/* ⚠ **THE WITHDRAW CARD IS DELETED — PO ruling 2026-09-19
                (`OQ-CUS-12486`).** Verbatim: *"if customer dont want it - they
                will call and clark will refuse it. thats'it . keep it
                simple"*. `withdraw` left the request's state table the same
                day, so `may_withdraw` is now false in every state and this
                card could never draw again — a control that can never render
                is dead UI, and leaving it would have left the promise in the
                code for the next lane to "fix" by putting the button back.
                A customer who changes their mind rings the utility and a
                clerk refuses the request with `Applicant withdrew`, which is
                one of the five reasons the Refuse dialog already offers. */}
            {refused !== null ? (
              <Announced tone="error" className="text-body font-semibold text-danger-700" data-refused="">
                {refused}
              </Announced>
            ) : null}
          </>
        }
      />
    </div>
  );
}

/**
 * The rail's details — **the reference, what it is waiting on, and how long it
 * has been open.**
 *
 * ⚠ **A ROW THE SERVER SENT AS `null` IS ABSENT, NEVER DRAWN AS A DASH**
 * (`BR-CWP-093`). *Waiting on* with nothing beside it reads as *waiting on
 * nothing*, which on a request a clerk has asked for documents about is the
 * opposite of the truth.
 */
function detailRows(
  t: (key: string, options?: Record<string, unknown>) => string,
  request: PortalRequestDetail,
  formatDate: (value: string | null, withTime?: boolean) => string,
) {
  const rows: { key: string; label: string; value: React.ReactNode }[] = [
    {
      key: "reference",
      label: t("portal.request.reference"),
      value: <span data-detail="reference">{request.reference}</span>,
    },
  ];
  // ⚠ **WHEN THEY RAISED IT — A FACT THE SERVER HAS ALWAYS SENT AND THIS RAIL
  // NEVER DREW** (`DEF-CWP-4201` row 51.2). The drawing's DETAILS rail has
  // four rows and this rendered two. Its fourth, *Last day of service*, is a
  // move-out fact that lives inside the composed sentence and has no column
  // (`DEF-CWP-3881`), so it stays absent rather than being guessed at —
  // `BR-CWP-093`, a stated absence over an invented value.
  if (request.raised_at !== null) {
    rows.push({
      key: "raised",
      label: t("portal.request.raisedLabel"),
      value: <span data-detail="raised">{formatDate(request.raised_at)}</span>,
    });
  }
  if (request.waiting_on !== null && request.waiting_on !== "") {
    rows.push({
      key: "waiting_on",
      label: t("portal.request.waitingOn"),
      value: <span data-detail="waiting_on">{request.waiting_on}</span>,
    });
  }
  if (request.open_for_days !== null) {
    rows.push({
      key: "open_for",
      label: t("portal.request.openFor"),
      value: (
        <span data-detail="open_for">
          {t("portal.request.days", { count: request.open_for_days })}
        </span>
      ),
    });
  }
  return rows;
}

/**
 * The `<h1>` — what this request IS.
 *
 * ⚠ **THE OLD TITLE IS THE FALLBACK AND NOT THE ANSWER.** *"Track your
 * request"* is what the page is FOR, not what the request is, and it headed
 * every request in the product until `CPB-12`. It survives for the branch the
 * server cannot classify — a reported problem, an application — where the
 * customer's own words are in the body and a KIND would be an invention.
 */
function requestTitle(
  t: (key: string, options?: Record<string, unknown>) => string,
  request: PortalRequestDetail | null,
): string {
  const title = request?.title ?? null;
  if (title === null) return t("portal.trackRequest.title");
  if (title.kind === "bill_query") {
    return title.number === null
      ? t("portal.requests.kind.billQueryPlain")
      : t("portal.requests.kind.billQuery", { number: title.number });
  }
  const key = TITLE_KEYS[title.kind];
  return key === undefined ? t("portal.trackRequest.title") : t(`portal.requests.kind.${key}`);
}

/** ⚠ **THE SAME MAP `CWP-046` KEEPS, AND THE TWO SCREENS MUST AGREE** — a
 *  request titled one thing in the list and another on its own page is the
 *  fault `DEF-CWP-4709` recorded for the STATE words one column along. */
const TITLE_KEYS: Record<string, string> = {
  question: "question",
  stop_service: "stopService",
  // CR-183-BRC10 B4 — *Restart my service now*.
  restart_now: "restartNow",
  payment_plan: "paymentPlan",
  help_paying: "helpPaying",
  quick_ask: "quickAsk",
};

/**
 * What happened at a step, under its date.
 *
 * ⚠ **EVERY LINE HERE IS A FACT THE SERVER SENT.** *through this website* is
 * `raised_through`, the row's own channel; *We are waiting for …* is
 * `waiting_on`, which the model calls orthogonal to state and which the rail
 * already draws; the two terminal sentences are read off `status`. Nothing is
 * composed out of a guess, and a step with nothing true to say gets nothing —
 * `BR-CWP-093`, and the reason the return type is `undefined` rather than an
 * empty string.
 */
function stepNote(
  t: (key: string, options?: Record<string, unknown>) => string,
  request: PortalRequestDetail,
  key: string,
  state: "done" | "current" | "future",
): string | undefined {
  if (state === "future") return undefined;
  if (key === "sent" && request.raised_through === "customer_portal") {
    return t("portal.request.throughThePortal");
  }
  if (key === "we_need_something" && request.waiting_on !== null && request.waiting_on !== "") {
    return t("portal.request.stepAwaiting", { what: request.waiting_on });
  }
  if (key === "we_decide" && request.status === "refused") return t("portal.request.stepRefused");
  if (key === "finished" && request.status === "withdrawn") {
    return t("portal.request.stepWithdrawn");
  }
  return undefined;
}

/** One line of the *What has happened* thread. */
interface ThreadEntry {
  key: string;
  /** `null` where the server has no stamp for it; the entry is still drawn,
   *  without a date, rather than dropped (`BR-CWP-093` runs both ways). */
  at: string | null;
  who: "you" | "us";
  text: string;
}

/**
 * The thread, newest first, with the customer's own opening sentence last.
 *
 * ⚠ **`what_they_said` WAS ON THE WIRE AND ON NO SCREEN.** It is the sentence
 * the customer typed — the drawing's first entry, *Aug 13 · You* — and
 * `CWP-051` did not draw it anywhere, so a customer could not read back what
 * they had asked us. It goes at the BOTTOM because it is the oldest thing in
 * the thread and the drawing is explicit that the newest is on top.
 *
 * ⚠ **AND IT IS ONLY THEIR SENTENCE WHEN THE SERVER COULD NOT CLASSIFY THE
 * REQUEST — `DEF-CWP-4708`, FOUND BY WALKING THIS WAVE'S OWN WORK.**
 * `DEF-CWP-4198`'s second surface is right here: four of the six portal shapes
 * compose a CLERK's sentence into `what_they_said`, and this thread printed it
 * under **You**, so Ana read, of herself, *"Queried through the customer
 * portal … Their reason: …"*. `CPB-05` gave those shapes a customer-visible
 * note carrying what she actually typed — and for one browser run the screen
 * then showed **both**, the same claim twice, once in her words and once in
 * ours. **A `title` is the server saying *we wrote this sentence*, so where
 * there is one the opener is dropped.** Where there is none — a reported
 * problem, an application — `what_they_said` IS their words and is drawn
 * exactly as before.
 *
 * ⚠ **A TRANSITION WITH NO NOTE IS NOT AN ENTRY.** The server keeps every
 * transition on the wire for the PROGRESS ladder and drops its note
 * (`BR-CWP-078`); a row with nothing to read is a bullet with no sentence.
 */
function threadOf(request: PortalRequestDetail): ThreadEntry[] {
  const entries: ThreadEntry[] = request.timeline
    .filter((row) => row.note !== null && row.note !== "")
    .map((row, index) => ({
      key: `${row.at}-${row.kind}-${index}`,
      at: row.at,
      who: row.note_type === "customer_note" ? ("you" as const) : ("us" as const),
      text: row.note as string,
    }));
  const said = request.title === null ? (request.what_they_said ?? "").trim() : "";
  if (said !== "") {
    entries.push({ key: "what-they-said", at: request.raised_at, who: "you", text: said });
  }
  return entries;
}
