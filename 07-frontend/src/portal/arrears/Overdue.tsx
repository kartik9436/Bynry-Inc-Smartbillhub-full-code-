// ── Trace ──────────────────────────────────────────────
// Story:    US-CWP-057 (EP-CWP-10) — what happens if this is not paid: the
//           ladder, and what it would cost. Screen: CWP-057 (blueprint `P43`)
// Rules:    BR-CWP-092 (an unmapped tier renders as an ABSENCE, never rounded)
//           · BR-CWP-091 (a hold stops a disconnection, not the debt) ·
//           BR-CWP-051 (a write-off shows amount and date, never its reason) ·
//           BR-CWP-093 (nothing empty ever appears) · BR-CWP-056 (a held
//           control carries its reason) · B14 rule 21 · rule 31 (no database id
//           on screen) · rule 32 (one sentence per section) · rule 33 (a
//           refusal is five or six words) · rule 35 · rule 36 ·
//           CLAUDE.md hard rule 2 (2 dp displayed)
// Open:     OQ-CWP-1600 — nothing in this product prices a reconnection
//           deposit, so the panel states the requirement and quotes no figure,
//           and the closing row is a SUBTOTAL rather than a total.
// Tests:    src/portal/arrears/Overdue.dom.test.tsx
// Impacts:  src/portal/api/portalClient.ts `getArrears`
// ───────────────────────────────────────────────────────
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { PageHeader } from "@/components/PageHeader";

// ⚠ **DATES GO THROUGH THE TENANT'S OWN FORMAT, NEVER STRAIGHT TO THE SCREEN**
// (`DEF-CWP-4138`'s fix, which wave M's five screens took and these four did
// not). `usePortalDate` returns the server's string unchanged when the tenant
// has set no drawable format — declining to state one is honest; inventing
// `MM/DD/YYYY` for a utility in Berlin is what shipped a five-hour error.
import { usePortalDate } from "../components/regional";

import {
  Card,
  ChecklistTimeline,
  ErrandLink,
  KVList,
  SectionTitle,
  StatusChip,
  TotalRow,
  TwoCol,
  usePortalPath,
} from "../components/primitives";
import { PortalScreen, PortalState, type PortalWayOut } from "../components/states";
import { AttachedAnswerCard } from "../components/content";
import { Panel } from "@/components/Panel";
import { formatMoney } from "../signin/Enrol";
import { getArrears, type PortalArrears, type PortalLadderStep } from "../api/portalClient";

/**
 * `CWP-057` — the most uncomfortable screen in the portal, and the most useful.
 *
 * ⚠ **EVERYTHING HERE IS THIS ACCOUNT'S OWN RECORD, NOT THE UTILITY'S CADENCE.**
 * The customer's own disconnection case carries the tier reached, the date a cut
 * is scheduled for, the reconnection fee and which services would be cut — *"the
 * single most consequential record about them is the one they cannot see."*
 *
 * ⚠ **A RUNG THE TIER VOCABULARY CANNOT NAME IS DRAWN AS AN ABSENCE**
 * (`BR-CWP-092`). Showing somebody at the five-day notice as though they were at
 * the ten-day one **moves the date they think they have**, and tells a regulator
 * they were sent a letter they were not sent.
 *
 * ⚠ **A FUTURE STEP READS *no earlier than*, NEVER A DATE ON ITS OWN.** Nothing
 * in this product advances a tier on a date, so the stored date is a floor the
 * utility will not act before. The server says which rows are floors and this
 * screen reads that flag rather than guessing.
 *
 * ⚠ **THE CLOSING ROW IS A SUBTOTAL AND SAYS WHAT IS MISSING FROM IT.** The
 * blueprint's *if it goes that far `$657.60`* adds a `$150.00` deposit that no
 * read in this product answers (`OQ-CWP-1600`). Showing a number nobody set, on
 * the screen most likely to frighten somebody, is worse than showing the gap.
 */
export function OverdueView(props: { accountId: string }) {
  const { t } = useTranslation();
  const asDate = usePortalDate();
  // ⚠ **A ROUTED PATH, NOT A BARE `/help/…`** — a portal address is built
  // under `/:tenant/portal`, and a link that forgets the tenant comes out
  // `//portal/…`, which is a protocol-relative URL to ANOTHER HOST that reads
  // as a perfectly good string to every assertion we have (`BR-CWP-007`).
  const path = usePortalPath();
  const [body, setBody] = useState<PortalArrears | null>(null);
  const [failed, setFailed] = useState(false);
  // ⚠ **`attempt` IS WHAT MAKES *Try again* A REAL CONTROL AND NOT A PROP**
  // (R-10, `DEF-CWP-4927`). `states.tsx` says in its own docstring why it will
  // not require `waysOut` on a failed card: on the day it was written *"the
  // read they would retry is held in each screen's own effect"*, and a
  // required prop would have been satisfied ten times by a button wired to
  // nothing — `EmptyList`'s `onCta: () => undefined` defect. This is the
  // effect's own re-run key, so the button re-issues the request that failed.
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let live = true;
    setFailed(false);
    getArrears(props.accountId)
      .then((answer) => {
        if (live) setBody(answer);
      })
      .catch(() => {
        if (live) setFailed(true);
      });
    return () => {
      live = false;
    };
  }, [props.accountId, attempt]);

  // ⚠ **THE HEAD IS BUILT ONCE AND RENDERS ON EVERY BRANCH, LOADING INCLUDED**
  // (`DEF-CWP-4000`; audit D1, delta X4/X5) — the shared
  // `components/PageHeader.tsx`, never a second one.
  //
  // ⚠ **THE TITLE IS THE SCREEN'S NAME AND NOT THE FIGURE, WHICH IS A STATED
  // DIVERGENCE FROM THE DRAWING.** `08-screen-layouts.md` gives this head the
  // title *$412.60 is overdue by 19 days*. The figure is not known on the
  // loading or failed branch, so a head carrying it would have to appear late
  // or say two different things; and the same sentence already opens the card
  // as `[data-headline]`, so putting it in the title too would print it twice
  // — B14 rule 32's description budget. REPORTED rather than quietly settled:
  // moving the sentence out of the card and into the title is one edit and one
  // test selector, and it wants a decision rather than a lane's preference.
  //
  // ⚠ **THE THREE WAYS OUT ARE ONE GROUP, IN THE PANEL, AND NOT ONE IN THE
  // HEAD** (`CR-085` task (c), wireframe screen 41). The drawing's own note is
  // the rule: *"Pay is filled; the plan and the assistance route are outlined
  // and equally prominent as a pair. A customer who cannot pay must not have to
  // leave to find the alternative."* The head carried *Ask for a plan* alone,
  // which split the pair across two boxes and left the FILLED action — pay —
  // off the screen altogether: the most frightening screen in the portal named
  // two ways out of three and never the obvious one.
  //
  // ⚠ **THE TITLE IS *Past due*, THE WORD THE LETTER USED.** The drawing is
  // explicit — *"'Past due' and 'shut off' — the words the letter used. Not
  // 'in arrears'"* — and the head previously repeated the card's own
  // `Where things stand` heading a second time, which is B14 rule 32's
  // description budget spent twice on one sentence. `whereThingsStand` stays
  // exactly as it is: it is the LINK LABEL on `CWP-027` and on Home.
  const head = (
    <PageHeader
      kicker={t("portal.kicker.bills")}
      title={t("portal.overdue.title")}
    />
  );

  // ⚠ **R-10 ON THE BRANCH THAT USED TO BE A BARE SENTENCE** (PO 2026-09-11,
  // verbatim: *"when a screen tells a customer something bad, the thing they
  // can do about it must be on that same screen, next to the message"*). This
  // screen's three ways out lived ONLY in the rail of the populated branch, so
  // a customer whose arrears read failed was told the read failed and offered
  // nothing — on the most frightening address in the portal. The two doors are
  // the two that need no figure: a plan and the assistance route are true
  // whatever the balance turns out to be, where *Pay $247.30* is not.
  const failedWaysOut: PortalWayOut[] = [
    {
      label: t("portal.payNow.tryAgain"),
      onClick: () => setAttempt((n) => n + 1),
      tone: "primary",
      testKey: "try-again",
    },
    { label: t("portal.overdue.askForAPlan"), to: path("/ask-for-a-plan"), testKey: "ask-for-a-plan" },
    { label: t("portal.overdue.helpPaying"), to: path("/help-paying"), testKey: "help-paying" },
  ];

  if (failed) {
    return (
      <PortalScreen screen="CWP-057" head={head}>
        <PortalState
          kind="failed"
          testId="overdue"
          sentence={t("portal.overdue.couldNotRead")}
          waysOut={failedWaysOut}
        />
      </PortalScreen>
    );
  }
  if (body === null) {
    return (
      <PortalScreen screen="CWP-057" head={head}>
        <PortalState kind="loading" testId="overdue" sentence={t("portal.overdue.reading")} />
      </PortalScreen>
    );
  }
  if (!body.overdue) {
    // ⚠ `BR-CWP-093` — the screen and its link are ABSENT when nothing is
    // overdue. An empty ladder on an account in good standing is a letter
    // nobody sent.
    // ⚠ **NO `waysOut` HERE, DELIBERATELY.** R-10 is about bad news, and
    // *nothing is overdue* is the best news this screen has. A row of buttons
    // under it would invite somebody in good standing to ask for a payment
    // plan they do not need.
    return (
      <PortalScreen screen="CWP-057" head={head}>
        <PortalState kind="empty" testId="overdue" sentence={t("portal.overdue.nothingOverdue")} />
      </PortalScreen>
    );
  }

  return (
    <div data-screen="CWP-057">
      {/* ⚠ **THE SCREEN ID IS A LITERAL HERE AND MUST STAY ONE — `CR-085` lane 8.**
          `PortalScreen` renders an identical DOM from its `screen` prop, but THREE
          source scanners find a portal screen by the exact string
          `data-screen="CWP-…"` and not one of them reads a prop: this census,
          `g100_every_screen_has_a_door.py` and `g103_holds_cannot_rot.py`. Wrapping
          this branch too made the whole file invisible to all three — hard-won law
          7’s *reporting zero over a scope it silently excluded*.
          `bills/BillDetail.tsx` keeps the literal on its populated branch for
          exactly this reason. */}
      {head}
      <TwoCol
        main={
          <>
          <Card testId="overdue">
            {/* ⚠ **NO SECOND HEADING.** The head above already names the
                screen; this card opens on the figure, which is what the phone
                drawing does. */}
            <p className="text-body text-neutral-800" data-headline="">
              {/* ⚠ The SIGN the server sent. Nothing here strips a minus. */}
              {t("portal.overdue.headline", {
                amount: formatMoney(body.owed ?? "0", body.currency),
                count: body.days_overdue ?? 0,
              })}
            </p>
            {/* ⚠ **THE DATE IT WAS DUE — `DEF-CWP-4919`.** `due_on` has been on
                the wire since `CR-068` wave H and not one line of this file
                read it: the screen said *overdue by 22 days* and never which
                day it was counting from. The blueprint states the date in BOTH
                frames and names it under TONE, and a relative count is the one
                form a customer cannot check against the letter in their hand.
                ⚠ **IT IS A SEPARATE LINE RATHER THAN AN EXTENSION OF THE
                HEADLINE.** Folding it into `portal.overdue.headline` would
                rewrite a plural key in eleven languages to carry two facts in
                one sentence — and `ja-JP` and `ko-KR` do not order those two
                facts the way English does. A tiny key of its own is what B14
                rule 35 asks for.
                ⚠ **`null` DRAWS NOTHING** (`BR-CWP-093`): an account whose due
                date was never recorded says nothing rather than an em-dash. */}
            {body.due_on !== null ? (
              <p className="m-0 text-base text-neutral-600" data-due-on={body.due_on}>
                {t("portal.overdue.dueOn", { date: asDate(body.due_on) })}
              </p>
            ) : null}
            {body.tier_unmapped ? (
              // ⚠ `BR-CWP-092` — the ABSENCE, in words, and never a neighbour's
              // chip. B14 rule 32: one sentence, and it is stated rather than
              // left as a blank.
              <p className="text-body text-neutral-600" data-tier="absent">
                {t("portal.overdue.tierUnmapped")}
              </p>
            ) : body.tier !== null ? (
              <div>
                <StatusChip tone="warning" testKey="tier">
                  {t(`portal.overdue.tier.${body.tier}`)}
                </StatusChip>
              </div>
            ) : null}
            <ChecklistTimeline steps={body.timeline.map((step) => timelineRow(step, t, asDate))} />
            {body.services_at_risk.length > 0 ? (
              <p className="text-body text-neutral-600" data-services-at-risk="">
                {t("portal.overdue.servicesAtRisk", {
                  services: body.services_at_risk.join(", "),
                  count: body.services_at_risk.length,
                })}
              </p>
            ) : null}
            {body.write_offs.length > 0 ? (
              <div data-write-offs="">
                <SectionTitle>{t("portal.overdue.writtenOff")}</SectionTitle>
                {/* ⚠ `BR-CWP-051` — the amount and the date, and the response
                    carries no reason for this screen to be able to show one. */}
                <KVList
                  rows={body.write_offs.map((row, index) => ({
                    key: `write-off-${index}`,
                    label: t("portal.overdue.writtenOffOn", { date: asDate(row.date) }),
                    value: formatMoney(row.amount, row.currency),
                  }))}
                />
              </div>
            ) : null}
          </Card>
          {/* ⚠ **THE ANSWER A CLERK PINNED TO THIS SCREEN — `CWP-060`'s SECOND
              PLACEMENT (`DEF-CWP-3945`).** The column, the staff field, the
              published read and this very component all existed; what did not
              was any way for `apps/portal/` to REACH the read, a field on a
              payload, and one caller. So a utility ticked *also show this on
              the overdue screen*, the tick saved, and the answer appeared
              nowhere — with the clerk getting a confirmation either way, which
              is why nobody looked. Hard-won law 2 in its purest form.
              ⚠ **`null` DRAWS NOTHING AT ALL** (`BR-CWP-093`) — an empty card
              headed with a question is worse than no card. */}
          {body.attached_answer ? (
            <AttachedAnswerCard
              question={body.attached_answer.question}
              body={body.attached_answer.body}
              readMoreLabel={t("portal.attachedAnswer.readMore")}
              href={path(`/help/${body.attached_answer.slug}`)}
              whyLabel={t("portal.attachedAnswer.why")}
            />
          ) : null}
          </>
        }
        rail={
          <>
            <Panel as="aside" title={t("portal.overdue.whatItWouldCost")}>
              <KVList
                rows={body.cost.parts.map((part) => ({
                  key: part.part,
                  label: t(`portal.overdue.part.${part.part}`),
                  value:
                    part.amount === null ? (
                      // ⚠ **AN ABSENCE IN WORDS, NEVER AN EM-DASH AND NEVER A
                      // `$0.00`.** `OQ-CWP-1600`: no rule prices a reconnection
                      // deposit, and a zero here would tell somebody that
                      // getting reconnected costs nothing beyond the fee.
                      <span className="font-normal text-neutral-600" data-part-absent={part.part}>
                        {t(`portal.overdue.partUnknown.${part.part}`)}
                      </span>
                    ) : part.already_owed ? (
                      // ⚠ **THE FEE IS SHOWN AND IS NOT ADDED — `DEF-CWP-6072`.**
                      // The cut ISSUES the reconnection fee, so it is already in
                      // what this customer owes and the subtotal must not add it
                      // a second time. Dropping the row would say the fee does
                      // not exist; showing it with no word beside it leaves a
                      // reader with arithmetic that does not add up. B14 rule 33
                      // — a FACT, five words, no rule id and no reasoning.
                      <span className="tabular-nums" data-part={part.part}>
                        {formatMoney(part.amount, body.cost.currency)}{" "}
                        <span className="font-normal text-neutral-600" data-part-included={part.part}>
                          {t(`portal.overdue.partIncluded.${part.part}`)}
                        </span>
                      </span>
                    ) : (
                      <span className="tabular-nums" data-part={part.part}>
                        {formatMoney(part.amount, body.cost.currency)}
                      </span>
                    ),
                }))}
              />
              {body.cost.subtotal !== null ? (
                <TotalRow
                  label={t("portal.overdue.subtotal")}
                  value={formatMoney(body.cost.subtotal, body.cost.currency)}
                  testKey="if-it-goes-that-far"
                />
              ) : null}
              {body.cost.parts_missing.length > 0 ? (
                <p className="m-0 text-base text-neutral-600" data-subtotal-note="">
                  {t("portal.overdue.subtotalNote", { count: body.cost.parts_missing.length })}
                </p>
              ) : null}
            </Panel>
            {body.held_by.length > 0 ? (
              // ⚠ `BR-CWP-091` — the hold is named AND the debt is said to
              // stand. A customer who reads a hold as a pause on the debt stops
              // paying and is cut the week it lapses.
              <Panel as="aside" tone="info" title={t("portal.overdue.onHoldHeading")}>
                <p className="m-0 text-body text-neutral-800" data-held-by="">
                  {t("portal.overdue.onHold", {
                    kind: t(`portal.protections.kind.${body.held_by[0]?.kind}`),
                  })}
                </p>
              </Panel>
            ) : null}
            <Panel as="aside" tone="warning" title={t("portal.overdue.stopItHeading")}>
              <p className="m-0 text-body text-neutral-800" data-stop-it="">
                {t("portal.overdue.stopIt")}
              </p>
              {/* ⚠ **BOTH OF THESE POINTED AT NOWHERE UNTIL 2026-09-05.**
                  `usePortalPath` concatenates — `/${tenant}/portal` + `to` —
                  so a `to` with no leading slash produced
                  `/pine-hill/portalask-for-a-plan`, an address no route
                  serves. It rendered as a perfectly ordinary button, `tsc` was
                  happy, and every `toContain` assertion passed because the
                  string IS in the DOM. Nobody met it because `CWP-057` itself
                  had no door either (`DEF-CWP-3954`) — a broken link on an
                  unreachable screen is invisible twice over. The mechanical
                  cure is `G100`, which reads every `to=` in this directory and
                  fails one that resolves to no registered screen. */}
              {/* ⚠ **THREE WAYS OUT, TOGETHER, AND PAY IS THE FILLED ONE.**
                  The amount is the SERVER'S `owed`, re-used through the label
                  Home already prints (`portal.home.pay`) rather than a second
                  copy of the same four words — the reuse rule this repo
                  already applies to month names. Nothing is computed here. */}
              <div className="mt-2 flex flex-col gap-2">
                <ErrandLink
                  variant="primary"
                  label={t("portal.home.pay", {
                    amount: formatMoney(body.owed ?? "0", body.currency),
                  })}
                  to="/pay-now"
                />
                <ErrandLink label={t("portal.overdue.askForAPlan")} to="/ask-for-a-plan" />
                <ErrandLink label={t("portal.overdue.helpPaying")} to="/help-paying" />
              </div>
            </Panel>
            {/* ⚠ **`CWP-064`'S DOOR, AND IT NO LONGER CLAIMS A HOLD EXISTS.**
                The link was labelled *Something is holding this* — the heading
                of the panel that appears when one DOES — so on the ordinary
                account, where nothing is holding anything, the screen stated
                the opposite of the truth in the label of its own link. The
                drawing puts a medical-equipment prompt here instead, and that
                is a question rather than a claim: it is right in both states.
                Nothing on this panel is a figure and nothing is a promise —
                the protections screen itself says what applies. */}
            <Panel as="aside" tone="info" title={t("portal.overdue.medicalHeading")}>
              <p className="m-0 text-body text-neutral-800" data-medical="">
                {t("portal.overdue.medicalBody")}
              </p>
              <div className="mt-2">
                <ErrandLink label={t("portal.overdue.yourProtections")} to="/protections" />
              </div>
            </Panel>
          </>
        }
      />
    </div>
  );
}

/**
 * One timeline row, and **three of its four shapes are absences.**
 *
 * A step with no recorded date says so; a step whose tier the vocabulary cannot
 * name says so; a future step says *no earlier than* rather than naming a day
 * the product will not act on. Only a step that happened states a plain date.
 */
function timelineRow(
  step: PortalLadderStep,
  t: (key: string, options?: Record<string, unknown>) => string,
  asDate: (value: string | null | undefined) => string,
): { label: string; detail?: string; state: "done" | "current" | "future" } {
  const label = step.unmapped
    ? t("portal.overdue.step.unmapped")
    : step.tier !== null
      ? t(`portal.overdue.tier.${step.tier}`)
      : t(`portal.overdue.step.${step.step}`);
  const detail =
    step.on === null
      ? t("portal.overdue.noDateRecorded")
      : step.is_floor
        ? t("portal.overdue.noEarlierThan", { date: asDate(step.on) })
        : asDate(step.on);
  return { label, detail, state: step.state };
}
