// ── Trace ──────────────────────────────────────────────
// Story:    US-CWP-072 (EP-CWP-12) — help on the portal: the list, and one
//           answer. Screens: CWP-011 (the list) · CWP-060 (one answer)
// Rules:    08-screen-layouts.md CWP-011 (T3 under GuestFrame: PageHead HELP ·
//           *Answers* → main Card [chips · list rows] · rail Panel **STILL
//           STUCK?**) and CWP-060 (T6 + TwoCol: body · in-text actions · *Did
//           this help?* · RELATED · rail STILL STUCK? · ALSO WRITTEN IN) ·
//           BR-CWP-093 (absent entirely when nothing is published) ·
//           BR-CWP-094 (only published; English fallback WITH a line saying
//           so) · CR-068 R8 (a portal that is OFF shows the holding page and
//           nothing else, on EVERY route) · R-10 (PO 2026-09-11 — the way out
//           beside the bad news) · R-22 (PO 2026-09-11, verbatim:
//           *"differntiate it using text message"*) · B14 rule 21 · rule 31 ·
//           rule 32 · rule 35
// Defects:  DEF-CWP-4851 (both screens served in full at a utility that had
//           not switched its portal on) · DEF-CWP-4854 (a utility with nothing
//           published served an empty search box, a chooser with one option,
//           and *"Nothing here matches what you typed."* to somebody who had
//           typed nothing — with a *Still stuck?* rail naming no way to reach
//           anybody at all) · DEF-CWP-4853 (one answer's NOT FOUND was the
//           staff failure panel)
// Tests:    src/portal/guest/HelpAndCentres.test.tsx
// Impacts:  src/portal/api/guestClient.ts · routing/portalRoutes.tsx
// ───────────────────────────────────────────────────────
import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useParams } from "react-router-dom";

import { api, isApiError } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { Button } from "@/components/Button";
import { ChipToggle } from "@/components/Chip";
import { PageHeader } from "@/components/PageHeader";
import { Panel } from "@/components/Panel";

import {
  getPortalCentres,
  getPortalFront,
  getPortalHelp,
  getPortalHelpAnswer,
  sendHelpFeedback,
} from "../api/guestClient";
import type { PortalFront, PortalHelpAnswer } from "../api/guestClient";
import { StatusChip, TextInput, TwoCol, usePortalPath } from "../components/primitives";
import { PortalScreen, PortalState } from "../components/states";
import { languageName, readerLocale, sentenceNamingLanguage } from "../components/languageName";
import { usePortalDate } from "../components/regional";

import { GuestPage } from "./GuestPage";

/** The frame every guest screen needs: the tenant's colours and its links. */
function useFront(client: ApiClient) {
  return useQuery({ queryKey: ["portal", "front"], queryFn: () => getPortalFront(client) });
}

/** A 404 here is *there is no such answer*, not *the read did not work* — the
 *  same split `CentresPage` makes, for the same reason (`DEF-CWP-4853`). */
function isNotFound(error: unknown): boolean {
  return isApiError(error) && error.status === 404;
}

/**
 * **STILL STUCK? — AND IT NOW NAMES A WAY TO REACH SOMEBODY** (`DEF-CWP-4854`).
 *
 * ⚠ **THE RAIL PROMISED A CALL AND GAVE NO NUMBER.** Its one sentence is
 * *"Call us or come in and someone will go through it with you."* and the
 * phone, the hours and the walk-in link were each drawn only when the utility
 * had published them — so on a tenant that had published none, this panel told
 * a customer to ring and named nothing to ring. The drawing makes this the
 * loudest thing on the screen and says why: *"A number without hours produces
 * a call to a closed office and a second call tomorrow."*
 *
 * So the SENTENCE now follows the facts: with a number, the call is offered and
 * the number is there; with none, the panel says where the number actually is —
 * on the paper bill, which every customer of this product has, because the
 * portal is a second channel and every bill is printed regardless. Nothing is
 * promised that the screen cannot deliver.
 *
 * ⚠ **THE EMAIL ADDRESS THE DRAWING ALSO ASKS FOR IS NOT HERE, DELIBERATELY.**
 * No endpoint serves one — `public/front` carries a phone and an hours STRING
 * and nothing else — so a line naming an inbox would be a sentence stating a
 * fact the product does not hold. Recorded rather than invented.
 *
 * ⚠ **NEITHER OF THOSE TWO SENTENCES IS A RULE CITATION, AND THAT IS
 * DELIBERATE.** The blueprint's appendix A states both as rules — *the portal
 * is a second channel* and *no sentence states a fact it does not derive* —
 * and **twelve of its twenty-four rules are stated only there and are
 * PROPOSALS until the Product Owner rules them in.** Both of these are among
 * them. The reasoning above stands on its own; the rule ids are deliberately
 * not cited, because a live screen built on an unratified rule is how a
 * proposal becomes law without anybody signing it (`CR-085` step-1 lane 2 §5,
 * which found three of this lane's screens already doing exactly that).
 */
function StillStuck(props: { front: PortalFront; visitLink: boolean }) {
  const { t } = useTranslation();
  const path = usePortalPath();
  const { front } = props;
  return (
    <Panel as="aside" title={t("portal.help.stuck.title")}>
      <p className="m-0" data-stuck-sentence={front.emergency_phone ? "call" : "bill"}>
        {front.emergency_phone ? t("portal.help.stuck.sentence") : t("portal.help.stuck.billNumber")}
      </p>
      {front.emergency_phone ? (
        <p className="mt-2 font-bold text-neutral-900" data-stuck-phone="">
          {front.emergency_phone}
        </p>
      ) : null}
      {/* ⚠ THE HOURS UNDER THE NUMBER AND NOT BESIDE IT — the drawing's own
          reason is that a number read without its hours produces two calls. */}
      {front.office_hours_text ? (
        <p className="mt-1 text-neutral-600" data-stuck-hours="">
          {front.office_hours_text}
        </p>
      ) : null}
      {/* ⚠ ABSENT when no centre is shown (US-CWP-072 TC-10). */}
      {props.visitLink ? (
        <a
          className="mt-3 inline-block font-semibold text-accent-text"
          href={path("/visit")}
          data-link="visit"
        >
          {t("portal.nav.visit")} →
        </a>
      ) : null}
    </Panel>
  );
}

// ══ CWP-011 · the list ═════════════════════════════════════════════════════

export function HelpPage(props: { client?: ApiClient }) {
  const { t } = useTranslation();
  const client = props.client ?? api;
  const [topic, setTopic] = useState<string | null>(null);
  const [needle, setNeedle] = useState("");
  const front = useFront(client);
  // ⚠ **`enabled` — A SWITCHED-OFF PORTAL DOES NOT ASK THE SERVER FOR CONTENT**
  // (`DEF-CWP-4851`). `GuestPage` decides what a visitor SEES; this decides
  // what the browser FETCHES, and they are not the same thing.
  const live = front.data?.is_live === true;
  const help = useQuery({
    queryKey: ["portal", "help", topic],
    queryFn: () => getPortalHelp(topic, client),
    enabled: live,
  });

  // ⚠ **BUILT ONCE, ABOVE THE BRANCHES** — `PortalScreen`'s rule and
  // `DEF-CWP-4926`'s cure. This screen used to `return` its loading and its
  // failure before the `PageHeader` line was reached, so a slow or refused
  // read threw the title, the screen mark and the frame away together.
  const head = (
    <PageHeader
      kicker={t("portal.help.kicker")}
      title={t("portal.help.title")}
      rollup={t("portal.help.subtitle")}
    />
  );

  // ⚠ **THE SEARCH THE DRAWING PUTS AT THE TOP OF THIS SCREEN ON BOTH WIDTHS**
  // (`CR-085`, 2026-09-08). It filters the rows the server already sent rather
  // than asking for a new read, and that is honest here for one reason worth
  // stating: `GET /public/help` returns the whole published set in one answer,
  // so nothing is hidden from the box. **The day that endpoint learns to page,
  // this has to become a server query** — a box that searches only the current
  // page is a box that says *nothing matches* about answers that do.
  //
  // ⚠ Matching on the QUESTION and not on the body: the body is not on this
  // payload at all, so a box that appeared to search the answers would be
  // searching their titles and quietly failing on the words a reader actually
  // remembers. The drawing's own note says why the titles are the right target
  // — *"'Billing enquiries' is a filing category; 'Why is my bill higher this
  // month?' is what someone types."*
  const typed = needle.trim().toLocaleLowerCase();
  const all = help.data?.answers ?? [];
  const rows =
    typed === "" ? all : all.filter((row) => row.question.toLocaleLowerCase().includes(typed));
  // **WHAT THE VISITOR IS ACTUALLY LOOKING AT, AND IT IS THREE THINGS RATHER
  // THAN TWO — `DEF-CWP-4854`, R-22.**
  //
  // ⚠ *Nothing is published here* and *your search matched none of the eleven
  // answers that are* are different facts, and the screen said the second one
  // in both cases: a tenant with zero published answers served an empty search
  // box, a chooser with one option (`All`), and **"Nothing here matches what
  // you typed."** to somebody who had typed nothing. The blueprint's own
  // `NO ARTICLES` state is one sentence and all three of its clauses were
  // broken: *"Falls back to the phone number and email — **never an empty
  // search box**."*
  //
  // `narrowed` is the honest test: a chip or a typed word is the visitor
  // having asked for less. Without one, an empty list is the UTILITY's absence
  // and no control on this screen can undo it — so the search box and the chip
  // row do not render at all, and what does render is the way to reach a
  // person (R-10).
  const narrowed = typed !== "" || topic !== null;
  const nothingPublished = all.length === 0 && !narrowed;

  const body = () => {
    if (front.isPending || help.isPending) {
      return <PortalState kind="loading" sentence={t("portal.help.state.loading")} />;
    }
    if (front.data === undefined || help.data === undefined) {
      return (
        <PortalState
          kind="failed"
          sentence={t("portal.help.state.failed")}
          waysOut={[
            {
              label: t("portal.payNow.tryAgain"),
              onClick: () => void help.refetch(),
              tone: "primary",
              testKey: "retry",
            },
          ]}
        />
      );
    }
    const list = help.data;
    return (
      <TwoCol
        main={
          nothingPublished ? (
            // ⚠ **NO SEARCH BOX OVER ZERO ROWS, AND NO CHOOSER WITH ONE
            // OPTION.** Both are furniture here: a box that can only ever
            // answer *nothing matches*, and an `All` chip that filters nothing
            // to nothing. What replaces them is the sentence that is true and
            // the rail beside it that names a person.
            <PortalState
              kind="empty"
              testId="cwp011-none-published"
              sentence={t("portal.help.state.none")}
            />
          ) : (
            <section className="border border-neutral-200 bg-[white]" data-help-list="">
              {/* ⚠ **THE PLACEHOLDER IS NOT THE LABEL.** It disappears the
                  moment somebody types, which is exactly when a screen-reader
                  user needs to know what the field is — the same reasoning
                  `listTable.tsx` writes down for the staff lists' search box,
                  and the same markup. */}
              <div className="border-b border-neutral-200 px-4 py-3">
                <label className="sr-only" htmlFor="cwp011-search">
                  {t("portal.help.search")}
                </label>
                <TextInput
                  id="cwp011-search"
                  type="search"
                  value={needle}
                  placeholder={t("portal.help.search")}
                  onChange={setNeedle}
                />
              </div>
              <div className="flex flex-wrap gap-2 border-b border-neutral-200 px-4 py-3">
                {/* ⚠ THE KIT'S FILTER CHIP, NOT A BOX THIS SCREEN DREW
                    (`DEF-CWP-3655` · r10 rule 12 · B14 rule 36). It was a raw
                    `<button>` with its own border, padding and two-state
                    colouring — the fifth opinion about what a filter chip
                    looks like, and `ChipToggle` already holds the only one,
                    `aria-pressed` and all. */}
                <ChipToggle
                  selected={topic === null}
                  onClick={() => setTopic(null)}
                  data-topic-chip="all"
                >
                  {t("portal.help.topic.all")}
                </ChipToggle>
                {/* ⚠ DERIVED, never a constant: a chip that filters to nothing
                    is a container with nothing in it (BR-CWP-093). */}
                {list.topics.map((one) => (
                  <ChipToggle
                    key={one}
                    selected={topic === one}
                    onClick={() => setTopic(one)}
                    data-topic-chip={one}
                  >
                    {t(`portal.help.topic.${one}`)}
                  </ChipToggle>
                ))}
              </div>
              {/* ⚠ **THE NO-MATCH STATE CARRIES THE WAY BACK — R-10.** Saying
                  *nothing matches* and leaving the visitor holding the filter
                  that produced it is bad news with no way out; the control
                  that undoes it is one press, and it belongs beside the
                  sentence rather than somewhere above it. `portal.table.noMatch`
                  is already written natively in all eleven catalogues, so the
                  words a person reads here are the product's one spelling of
                  this (B14 rule 35). */}
              {rows.length === 0 ? (
                <div className="px-4 py-4">
                  <PortalState
                    kind="empty"
                    testId="cwp011-no-match"
                    sentence={t("portal.table.noMatch")}
                    waysOut={[
                      {
                        label: t("portal.help.showEvery"),
                        onClick: () => {
                          setNeedle("");
                          setTopic(null);
                        },
                        testKey: "show_every",
                      },
                    ]}
                  />
                </div>
              ) : null}
              <ul className="divide-y divide-neutral-200">
                {rows.map((row) => (
                  <li key={row.slug} data-answer={row.slug}>
                    <a
                      className="flex items-center justify-between gap-3 px-4 py-3 text-body"
                      href={`help/${row.slug}`}
                    >
                      <span className="min-w-0 font-semibold text-neutral-900">{row.question}</span>
                      <span className="flex shrink-0 items-center gap-3">
                        <StatusChip tone="info" testKey={`topic-${row.topic}`}>
                          {t(`portal.help.topic.${row.topic}`)}
                        </StatusChip>
                        <span aria-hidden="true" className="text-accent-text">
                          →
                        </span>
                      </span>
                    </a>
                  </li>
                ))}
              </ul>
              {/* ⚠ NO FOOTER COUNT AT ALL. `US-CWP-071` TC-3 forbids telling
                  the customer how many are hidden, and a *"6 answers"* line is
                  one refactor away from becoming *"6 of 8"* — the rows on the
                  page are the honest number and they are countable by looking. */}
            </section>
          )
        }
        rail={<StillStuck front={front.data} visitLink={list.visit_link} />}
      />
    );
  };

  return (
    <GuestPage client={client}>
      <PortalScreen screen="CWP-011" head={head}>
        {body()}
      </PortalScreen>
    </GuestPage>
  );
}

// ══ CWP-060 · one answer ═══════════════════════════════════════════════════

/**
 * The head of one answer, as its own component **so that it renders INSIDE
 * `GuestFrame`** — which is the whole reason it is not written inline.
 *
 * ⚠ **`usePortalDate` READS A CONTEXT THE FRAME PUBLISHES, AND `AnswerPage`
 * IS ABOVE THAT FRAME.** `AnswerPage` RETURNS the frame (`<GuestPage>` since
 * `DEF-CWP-4851`, `<GuestFrame>` before it — either way this component is
 * inside it and `AnswerPage`'s own body is outside), so a hook in that body
 * sits one level up from `PortalRegionalProvider` and gets `null` — and
 * `usePortalDate` then hands back the server's raw string, by design.
 * Written inline, this line printed *Updated 2026-09-07* on a tenant that has
 * chosen `MM/DD/YYYY`: not the documented *no format published* fallback but a
 * published format read from the wrong side of its own provider, and visible
 * only by looking at the page (hard-won law 6). The screens that get this right
 * — `CWP-003`, `CWP-004`, `CWP-012` — are all CHILDREN of `GuestPage` rather
 * than callers of `GuestFrame`.
 */
function AnswerHead(props: { data: PortalHelpAnswer; backTo: string }) {
  const { t } = useTranslation();
  const asDate = usePortalDate();
  const { data } = props;
  return (
    <span data-back="help">
      {/* ⚠ **AN ABSOLUTE PORTAL PATH, NOT `../help`.** `usePortalPath` exists
          because a relative link works until a screen is rendered from a route
          that is not `/:tenant/portal`, and then it silently points somewhere
          else (`BR-CWP-005` · `BR-CWP-007`). The kit's `backTo` renders a
          router `Link`, so the path has to be the real one. */}
      <PageHeader
        backTo={{ to: props.backTo, label: t("portal.help.title") }}
        kicker={t(`portal.help.topic.${data.topic}`)}
        title={data.question}
        // ⚠ **WHEN IT WAS LAST WRITTEN — SERVED SINCE WAVE D, DRAWN BY
        // NOTHING** (`CR-085`, 2026-09-08). `updated_on` is on
        // `PortalHelpAnswer`, on the live payload (`"2026-09-07"` for the demo
        // tenant), and in this screen's own test fixture; the article never
        // printed it. The drawing puts it directly under the title — *"Updated
        // August 2026 · about 2 minutes to read"* — and the reason is
        // credibility: an answer with no date is one a reader has to guess the
        // age of, and a utility's help page is where that guess goes wrong.
        //
        // ⚠ The FRAME is the catalogue's and the DATE is the tenant's format
        // (B14 rule 35 · `BR-SHL-023`): eleven word-for-word translations of an
        // English sentence is what the rule forbids, and `2026-09-07` is no
        // human's language either.
        //
        // ⚠ ABSENT when the server sends none — *Updated —* is worse than
        // silence. And the drawing's *"about 2 minutes to read"* is NOT here:
        // no reading time is served, and a number this screen invented from the
        // body's length would be a figure the product cannot stand behind.
        rollup={
          data.updated_on ? (
            <span data-updated-on={data.updated_on}>
              {t("portal.help.updatedOn", { date: asDate(data.updated_on) })}
            </span>
          ) : undefined
        }
      />
    </span>
  );
}

export function AnswerPage(props: { client?: ApiClient }) {
  const { t, i18n } = useTranslation();
  const client = props.client ?? api;
  const path = usePortalPath();
  const params = useParams();
  const slug = params.slug ?? "";
  // ⚠ THE BROWSER'S language, not the app's — see `readerLocale`.
  const language = readerLocale(i18n.language || "en");
  const front = useFront(client);
  // ⚠ `enabled` — see `HelpPage` above. It matters more here than on the list:
  // opening an answer is an EVENT the back office counts (`CP-34`), so a
  // switched-off portal that still read this would be logging *read this
  // month* against a utility whose customers cannot reach the page at all.
  const live = front.data?.is_live === true;
  const [voted, setVoted] = useState<"helpful" | "not_helpful" | null>(null);
  const answer = useQuery({
    enabled: live,
    queryKey: ["portal", "help", "answer", slug, language],
    queryFn: async () => {
      const data = await getPortalHelpAnswer(slug, language, client);
      // ⚠ OPENING IT IS AN EVENT, and it is NOT the same event as a vote
      // (CP-34). The back office's *read this month* column is this call.
      void sendHelpFeedback(slug, "read", data.shown_in, client).catch(() => undefined);
      return data;
    },
  });
  const vote = useMutation({
    mutationFn: (event: "helpful" | "not_helpful") =>
      sendHelpFeedback(slug, event, answer.data?.shown_in ?? language, client),
    onSuccess: (_result, event) => setVoted(event),
  });
  const centres = useQuery({
    queryKey: ["portal", "centres"],
    queryFn: () => getPortalCentres(client).catch(() => []),
    enabled: live,
  });

  const data = answer.data;
  // ⚠ **THE HEAD ON EVERY BRANCH, AND THE BACK LINK WITH IT.** A stale or
  // mistyped answer address used to render the STAFF failure panel — outside
  // the frame, with a *Download error report* button and no way back to the
  // list (`DEF-CWP-4853`). `← Answers` is now on the page whatever the read
  // did, which is R-10's *"the thing they can do about it"* for the commonest
  // way anybody arrives here wrongly: a link that has moved.
  const head = data ? (
    <AnswerHead data={data} backTo={path("/help")} />
  ) : (
    <span data-back="help">
      <PageHeader
        backTo={{ to: path("/help"), label: t("portal.help.title") }}
        kicker={t("portal.help.kicker")}
        title={t("portal.help.title")}
      />
    </span>
  );

  const body = () => {
    if (front.isPending || answer.isPending) {
      return <PortalState kind="loading" sentence={t("portal.help.answer.loading")} />;
    }
    if (front.data === undefined || data === undefined) {
      const empty = isNotFound(answer.error);
      return (
        <PortalState
          kind={empty ? "empty" : "failed"}
          sentence={
            empty ? t("portal.help.answer.notFound") : t("portal.help.answer.failed")
          }
          waysOut={[
            ...(empty
              ? []
              : [
                  {
                    label: t("portal.payNow.tryAgain"),
                    onClick: () => void answer.refetch(),
                    tone: "primary" as const,
                    testKey: "retry",
                  },
                ]),
            { label: t("portal.help.showEvery"), to: path("/help"), testKey: "all_answers" },
          ]}
        />
      );
    }
    return (
      <>
        {/* ⚠ THE LINE THAT SAYS SO. A missing translation shows English and
            NEVER hides the answer, and the reader is told which language they
            are reading (BR-CWP-094, US-CWP-072 TC-8). No workflow is promised
            here or anywhere — OQ-1398 is open. */}
        {data.is_fallback ? (
          <p className="mb-4 border border-info-700 bg-info-100 px-4 py-3 text-body text-neutral-700" data-fallback-note="">
            {(() => {
              // DEF-CWP-10561: the language's own name is marked as such (WCAG 3.1.2).
              const cut = sentenceNamingLanguage((marker) => t("portal.help.fallback", { language: marker }), data.shown_in);
              return (
                <>
                  {cut.before}
                  <span lang={data.shown_in}>{cut.name}</span>
                  {cut.after}
                </>
              );
            })()}
          </p>
        ) : null}
        <TwoCol
          main={
            <>
              {/* DEF-CWP-10561 (WCAG 3.1.2): the answer is written in the
                  language the SERVER chose for it (the reader's browser, or
                  the fallback), which need not be the page's. */}
              <article className="border border-neutral-200 bg-[white] p-4" data-answer-body="" lang={data.shown_in}>
                <p className="whitespace-pre-line text-body leading-relaxed text-neutral-700">{data.body}</p>
              </article>
              <section className="border border-neutral-200 bg-[white] p-4" data-feedback="">
                <p className="m-0 font-semibold text-neutral-900">{t("portal.help.didThisHelp")}</p>
                {voted === null ? (
                  <div className="mt-2 flex gap-2">
                    {/* ⚠ THE KIT'S BUTTON. Both of these drew their own box —
                        `border border-neutral-300 px-3 py-1 …` — three
                        directories from `buttonKit.ts`, which holds the one
                        answer (`DEF-CWP-3655`, B14 rule 36). Secondary, not
                        primary: neither answer is the page's commit. */}
                    <Button size="sm" onClick={() => vote.mutate("helpful")} data-vote="helpful">
                      {t("portal.help.yes")}
                    </Button>
                    <Button size="sm" onClick={() => vote.mutate("not_helpful")} data-vote="not_helpful">
                      {t("portal.help.no")}
                    </Button>
                  </div>
                ) : (
                  <p className="mt-2 text-base text-neutral-600" data-vote-thanks="">
                    {t("portal.help.thanks")}
                  </p>
                )}
              </section>
              {data.related.length > 0 ? (
                <Panel as="aside" title={t("portal.help.related")}>
                  <ul className="divide-y divide-neutral-200">
                    {data.related.map((row) => (
                      <li key={row.slug}>
                        {/* ⚠ AN ABSOLUTE PORTAL PATH. A bare `{slug}` here is a
                            RELATIVE href, so from `/{tenant}/portal/help/a` it
                            resolves to `/{tenant}/portal/help/help/b` on the
                            answer screens that have a related list — the exact
                            `DEF-CWP-4655` fault one directory over. */}
                        <a
                          className="flex items-center justify-between gap-3 py-2"
                          href={path(`/help/${row.slug}`)}
                          data-related={row.slug}
                        >
                          <span className="font-semibold text-neutral-900">{row.question}</span>
                          <span aria-hidden="true" className="text-accent-text">
                            →
                          </span>
                        </a>
                      </li>
                    ))}
                  </ul>
                </Panel>
              ) : null}
            </>
          }
          rail={
            <>
              {/* ⚠ EVERY ANSWER ENDS IN A PERSON — the same panel the list
                  screen draws, so the two cannot drift into two spellings of
                  *ring us* (B14 rule 36, `DEF-CWP-4854`). */}
              <StillStuck front={front.data} visitLink={(centres.data ?? []).length > 0} />
              {data.also_written_in.length > 1 ? (
                <Panel as="aside" title={t("portal.help.alsoWrittenIn")}>
                  <p data-also-written-in="">
                    {data.also_written_in.map((code, index) => (
                      <span key={code}>
                        {index > 0 ? " · " : null}
                        <span lang={code}>{languageName(code)}</span>
                      </span>
                    ))}
                  </p>
                </Panel>
              ) : null}
            </>
          }
        />
      </>
    );
  };

  return (
    <GuestPage client={client}>
      <PortalScreen screen="CWP-060" head={head}>
        {body()}
      </PortalScreen>
    </GuestPage>
  );
}
