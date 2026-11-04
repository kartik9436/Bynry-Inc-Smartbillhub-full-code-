// ── Trace ──────────────────────────────────────────────
// Story:    US-CWP-051 (EP-CWP-10) — ask for a payment plan, and the last
//           instalment carries the rounding. Screen: CWP-042 (blueprint `P28`)
// Rules:    BR-CWP-062 (the remainder goes on the FINAL instalment and the
//           screen SHOWS it) · BR-CWP-063 (a plan holds the arrears; new bills
//           still arrive and still have to be paid) · BR-CWP-064 (late-fee
//           suspension is a PER-PLAN election; where it is off the box says
//           fees still apply) · BR-CWP-066 (a plan is GRANTED BY A CLERK — the
//           customer may only ASK; PO 2026-09-04) · B14 rule 20 · rule 21 ·
//           rule 31 · rule 32 · rule 33 · rule 35 · rule 36 (compose the kit) ·
//           CLAUDE.md hard rule 2 (2 dp displayed)
// Open:     OQ-CWP-1720 — the blueprint's *"miss two and the plan ends"* against
//           the PO's 2026-08-11 ruling that nobody is dropped. **Until it is
//           answered this screen does not say a plan ends.**
// Tests:    src/portal/plans/AskForPlan.dom.test.tsx
// Impacts:  src/portal/api/portalClient.ts `previewPlan` · `askForPlan`
// ───────────────────────────────────────────────────────
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { PageHeader } from "@/components/PageHeader";
// ⚠ **THE ONE FUNCTION THAT TURNS A REFUSAL INTO THE SENTENCE A PERSON READS**
// (`DEF-322`'s fix, `BR-SHL-020` r2). It renders the server's `message_key`
// from the catalogue and STRIPS `detail`, so engineering prose cannot reach a
// customer even if a catalogue value interpolates it.
import { refusalText } from "@/api/refusalText";

import { PortalScreen } from "../components/states";
import { Announced } from "../components/a11y";
import {
  ButtonReason,
  ButtonRow,
  Card,
  CommitButton,
  ConsequenceBox,
  ErrandLink,
  FormField,
  MiniTable,
  SectionTitle,
  Stepper,
  TextInput,
  TotalRow,
  TwoCol,
  TwoUp,
  usePortalPath,
} from "../components/primitives";
import { Button } from "@/components/Button";
import { Panel } from "@/components/Panel";
import { usePortalDate } from "../components/regional";
import { formatMoney } from "../signin/Enrol";
import {
  askForPlan,
  getAccountBalance,
  previewPlan,
  type PortalPlanPreview,
} from "../api/portalClient";

/**
 * `CWP-042` — spread what you owe, and see the instalments before you ask.
 *
 * ⚠ **THE UNEVEN LAST INSTALMENT IS DELIBERATE AND IT IS SHOWN** (`BR-CWP-062`).
 * Dividing a balance into equal parts leaves a remainder and the product puts it
 * on the FINAL payment rather than silently absorbing a cent — *and a customer
 * comparing the plan against their bank statement will notice.* The row is
 * flagged by the ENGINE (`carries_the_rounding`), not inferred from position by
 * this file.
 *
 * ⚠ **NOT ONE FIGURE ON THIS SCREEN IS COMPUTED HERE.** `$172.20` less `$40.00`
 * over six is five of `$22.03` and a final `$22.05`, `$132.20` in total — all of
 * it out of the same instalment engine the clerk's wizard uses. A second
 * implementation would be a second answer to the one number a customer argues
 * about, and a clerk and a customer would be reading different plans down the
 * same telephone line.
 *
 * ⚠ **THE COUNT IN THE COPY COMES FROM THE SERVER TOO** — *five payments of
 * `$22.03`, then one of `$22.05`* — because the blueprint's own box said **six**
 * then one, seven payments totalling `$154.23`, beside its own table of six
 * totalling `$132.20`. A box that counts the table beside it can go wrong; one
 * that is served the count cannot.
 *
 * ⚠ **THE VERB IS *ASK*** (`BR-CWP-066`, PO 2026-09-04: *"Utility Clark will di
 * it for Consumer; COnsumer cannot do it by themself; these are special
 * cases"*). Pressing the button raises a request a person works — no plan is
 * created, no late fee stops and the collection ladder keeps running until a
 * clerk grants it. The confirmation says exactly that.
 *
 * ⚠ **AND ONE SENTENCE IS DELIBERATELY MISSING.** The blueprint's consequence
 * box ends *"miss two and the plan ends"*. **This product does not do that** —
 * PO 2026-08-11, *"nodrop we chase for payments until write off"* — so the box
 * says what the code does instead, and `OQ-CWP-1720` carries the collision to
 * the Product Owner. Printing the blueprint's sentence would be a promise on a
 * customer's screen that nothing behind it keeps.
 */
export function AskForPlanView(props: { accountId: string }) {
  const { t } = useTranslation();
  const path = usePortalPath();
  const [months, setMonths] = useState("6");
  const [firstDue, setFirstDue] = useState("");
  const [upFront, setUpFront] = useState("");
  const [plan, setPlan] = useState<PortalPlanPreview | null>(null);
  // ⚠ **THE FIGURE THE WHOLE SCREEN IS ABOUT, AND IT WAS NOT ON IT**
  // (`CR-085` task (c), wireframe screen 42). The drawing opens *What you owe ·
  // $247.30* and the product opened on an empty number box: a customer had to
  // choose how many months to spread a total the screen had not told them.
  // The balance read is the SERVER'S (`owing`) — the same read `CWP-022` and
  // `CWP-027` print — and nothing here divides, adds or rounds it.
  const [owed, setOwed] = useState<{ amount: string; currency: string | null } | null>(null);
  const [reference, setReference] = useState<string | null>(null);
  const [refused, setRefused] = useState<string | null>(null);
  const [working, setWorking] = useState(false);

  useEffect(() => {
    let live = true;
    getAccountBalance(props.accountId)
      .then((answer) => {
        // ⚠ An ABSENCE rather than a `$0.00`: a zero here would tell somebody
        // asking for a plan that they owe nothing.
        if (live && answer.owing !== null) {
          setOwed({ amount: answer.owing, currency: answer.currency });
        }
      })
      // ⚠ A balance we could not read simply does not draw. It is context for
      // the choice below, not the choice itself, and the instalment preview
      // states the total again from its own read.
      .catch(() => undefined);
    return () => {
      live = false;
    };
  }, [props.accountId]);

  const body = {
    term_months: Number.parseInt(months, 10),
    first_due_on: firstDue,
    down_payment: upFront || "0",
  };
  const ready = firstDue !== "" && months !== "";

  // ⚠ **THE SERVER'S OWN REFUSAL, NOT ONE SENTENCE FOR FIVE CAUSES —
  // `DEF-CWP-4141`.** Both handlers caught EVERYTHING into
  // `portal.askPlan.couldNotRead` — *"We could not work that out. Please check
  // the dates."* — which names neither the field nor the bound and is simply
  // false for four of the five things the edge actually refuses:
  //
  //   · `portal.plan.termOutOfRange`  *Choose between 2 and 12 months.*
  //   · `portal.plan.termRequired`    *Choose how many months.*
  //   · `portal.plan.firstDueRequired` *Choose the first payment date.*
  //   · `portal.plan.cannotAsk`       *A plan is not available now.*
  //   · `portal.plan.refused`         *Those figures do not work.*
  //
  // All five exist in all eleven catalogues and were rendered by **nothing**.
  // A customer asking for thirteen months was told to check dates they had
  // filled in correctly, and the number the screen already knew — twelve — was
  // on the wire in `params` and thrown away with it.
  //
  // ⚠ **`refusalText` AND NOT `t(error.messageKey)` BY HAND.** It is the
  // function that owns this job: it falls back to the client's own copy for a
  // thrown `TypeError` or an aborted fetch, which have no catalogue key of
  // their own, and it strips `detail` so the engine's prose — *"a down payment
  // that settles the whole balance"* — cannot reach a customer screen
  // (`BR-SHL-020` r2, `DEF-322`). Six places once wrote this by hand and
  // sixteen catalogue values interpolated `{{detail}}`.
  async function see() {
    setWorking(true);
    setRefused(null);
    try {
      setPlan(await previewPlan(props.accountId, body));
    } catch (error) {
      setPlan(null);
      setRefused(refusalText(t, error));
    } finally {
      setWorking(false);
    }
  }

  async function ask() {
    setWorking(true);
    setRefused(null);
    try {
      const answer = await askForPlan(props.accountId, body);
      setReference(answer.reference);
    } catch (error) {
      setRefused(refusalText(t, error));
    } finally {
      setWorking(false);
    }
  }

  // ⚠ **THIS SCREEN HAD NO PAGE HEADING AT ALL — `DEF-CWP-4912`.** The only
  // heading in its whole document was an `h3` reading *There may be help too*,
  // in the rail, so a customer arriving from the overdue screen landed on a
  // form with no title and a screen reader announced the assistance panel as
  // the page. It is the LAST of `DEF-CWP-4000`'s ten: the head sweep fixed
  // nine screens by moving a head above the branches, and this one had no head
  // to move. The shared `components/PageHeader` is the one B14 rule 2 names —
  // no second page head is built here.
  //
  // ⚠ **BUILT ONCE, ABOVE BOTH BRANCHES**, so the confirmation card carries it
  // too: a customer who has just asked for a plan should still be able to see
  // what screen they are on.
  const head = (
    // ⚠ **`← Past due` IS THE DRAWING’S FIRST LINE AT BOTH WIDTHS**
    // (`CR-085` lane 7, *Screen 42*), and it is the only way back to the
    // screen the customer arrived from. `portal.overdue.title` is already in
    // all eleven catalogues, so this adds no key.
    <PageHeader
      kicker={t("portal.kicker.payments")}
      title={t("portal.askPlan.title")}
      backTo={{
        label: t("portal.overdue.title"),
        to: path("/overdue"),
        testId: "ask-plan-back",
      }}
    />
  );

  if (reference !== null) {
    return (
      <PortalScreen screen="CWP-042" head={head}>
        <Card testId="ask-plan-sent">
          {/* F-02 / F-04: the confirmation's heading takes focus, and the
              reference sentence is what is heard. */}
          <Announced tone="status" as="div" say={t("portal.askPlan.sent", { reference })}>
            <SectionTitle>{t("portal.askPlan.sentTitle")}</SectionTitle>
          </Announced>
          {/* ⚠ THE REFERENCE IS THE WHOLE RECORD OF THE INTERACTION
              (`BR-CWP-028`), and it is an `SR-` number — never a row id. */}
          <p className="text-body text-neutral-800" data-reference={reference}>
            {t("portal.askPlan.sent", { reference })}
          </p>
          <p className="text-body text-neutral-600">{t("portal.askPlan.sentNote")}</p>
        </Card>
      </PortalScreen>
    );
  }

  return (
    <div data-screen="CWP-042">
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
      <Stepper
        steps={[t("portal.askPlan.step1"), t("portal.askPlan.step2"), t("portal.askPlan.step3")]}
        current={2}
      />
      <TwoCol
        main={
          <Card testId="ask-plan">
            {/* ⚠ **NO SECOND HEADING.** The page head above now carries
                `portal.askPlan.title`; printing it here as well is what
                `DEF-CWP-4183` is on two neighbouring screens. The card opens
                on the lead, which is what the customer needs to read. */}
            <p className="text-body text-neutral-600">{t("portal.askPlan.lead")}</p>
            {/* ⚠ **THE TOTAL BEFORE THE CHOICE, NEVER AFTER IT.** */}
            {owed !== null ? (
              <TotalRow
                label={t("portal.askPlan.whatYouOwe")}
                value={formatMoney(owed.amount, owed.currency)}
                testKey="what-you-owe"
              />
            ) : null}
            <TwoUp>
              <FormField
                id="term-months"
                label={t("portal.askPlan.fieldMonths")}
                helper={t("portal.askPlan.fieldMonthsHelper")}
                required
              >
                <TextInput id="term-months" value={months} onChange={setMonths} />
              </FormField>
              <FormField id="first-due" label={t("portal.askPlan.fieldFirstDue")} required>
                <TextInput id="first-due" type="date" value={firstDue} onChange={setFirstDue} />
              </FormField>
            </TwoUp>
            <FormField
              id="up-front"
              label={t("portal.askPlan.fieldUpFront")}
              helper={t("portal.askPlan.fieldUpFrontHelper")}
            >
              <TextInput id="up-front" value={upFront} onChange={setUpFront} />
            </FormField>
            {/* ⚠ **DISABLED *WITH* THE REASON** (`BR-SHL-025`, `BR-CWP-056`).
                This was a bare `<Button disabled>` carrying nothing — not even
                a `title` — twenty lines above a `CommitButton` in the same file
                that does it correctly, which is how it survived review: the
                file already knew how. The reason is `askHeld` and not a second
                sentence because it is the SAME refusal: this button and the one
                in the rail are both waiting on the two date boxes, and two
                different sentences for one cause is how a customer learns to
                stop reading them. */}
            <ButtonRow>
              <Button
                variant="secondary"
                size="sm"
                disabled={!ready}
                title={ready ? undefined : t("portal.askPlan.askHeld")}
                // F-22 (`DEF-CWP-10551`): the reason is drawn as text too.
                aria-describedby={ready ? undefined : "ask-plan-see-reason"}
                onClick={() => void see()}
              >
                {t("portal.askPlan.see")}
              </Button>
            </ButtonRow>
            <ButtonReason id="ask-plan-see-reason" reason={ready ? null : t("portal.askPlan.askHeld")} />
            {refused !== null ? (
              <Announced tone="error" className="text-body font-semibold text-danger-700" data-refused="">
                {refused}
              </Announced>
            ) : null}
            {plan !== null ? (
              // F-02 / F-04: the worked plan is the result of *See the plan*.
              <Announced tone="status" as="div" say={t("portal.askPlan.consequenceHeading")}>
                <Instalments plan={plan} />
              </Announced>
            ) : null}
          </Card>
        }
        rail={
          <>
            {plan !== null ? (
              <>
                <ConsequenceBox
                  heading={t("portal.askPlan.consequenceHeading")}
                  bullets={consequences(t, plan)}
                />
                {/* ⚠ **NOT THE DANGER TIER** (r10 rule 6): asking for a plan is
                    not a destructive commit. */}
                <CommitButton
                  label={t("portal.askPlan.ask")}
                  working={working}
                  ready={ready}
                  reason={t("portal.askPlan.askHeld")}
                  onClick={() => void ask()}
                />
              </>
            ) : null}
            {/* ⚠ **ASSISTANCE IS OFFERED HERE, AND IT IS NOT DECORATION**
                (wireframe screen 42): *"a customer asking for a plan is exactly
                the one who may qualify for a grant — and most do not know it
                exists."* It is OUTSIDE the preview branch above, so it is on
                the screen from the moment the customer arrives rather than
                appearing only once they have worked out an instalment. The
                sentence promises no money and names no figure — the help
                screen itself carries what this utility actually offers. */}
            <Panel as="aside" tone="info" title={t("portal.askPlan.helpHeading")}>
              <p className="m-0 text-body text-neutral-800" data-ask-plan-help="">
                {t("portal.askPlan.helpBody")}
              </p>
              <div className="mt-2">
                <ErrandLink label={t("portal.overdue.helpPaying")} to="/help-paying" />
              </div>
            </Panel>
          </>
        }
      />
    </div>
  );
}

/** The instalment table and its total — `TotalRow` from the kit, not a bold
 *  `<tr>` of this screen's own (B14 rule 36). */
function Instalments(props: { plan: PortalPlanPreview }) {
  const { t } = useTranslation();
  //: `DEF-CWP-4138` — the tenant's own date format, through the ONE formatter
  //: (`DEF-CWP-3994`'s wire). A due date printed as `2026-10-14` is the wire
  //: string, not a date a customer of a `MM/DD/YYYY` utility recognises.
  const showDate = usePortalDate();
  const { plan } = props;
  return (
    <div className="mt-3" data-instalments="">
      <MiniTable
        caption={t("portal.askPlan.caption")}
        columns={[
          { key: "due", label: t("portal.askPlan.colDue") },
          { key: "amount", label: t("portal.askPlan.colAmount"), align: "right" as const },
        ]}
        rows={plan.instalments.map((row) => ({
          key: String(row.seq),
          cells: {
            due: showDate(row.due_on),
            amount: (
              <span
                className="tabular-nums"
                data-instalment={row.seq}
                data-rounding={row.carries_the_rounding ? "true" : undefined}
              >
                {formatMoney(row.amount, plan.currency)}
              </span>
            ),
          },
        }))}
      />
      <TotalRow
        label={t("portal.askPlan.total")}
        value={formatMoney(plan.spread, plan.currency)}
        testKey="spread"
      />
      {/* `BR-CWP-062` — said in words as well as shown in the table, because a
          customer reconciling a bank statement is the person who notices.

          ⚠ **AND ONLY WHEN THERE IS A REMAINDER TO CARRY** (`DEF-CWP-4140`).
          This sentence was unconditional, so `$120.00` over six — six
          instalments of `$20.00`, the wave M demo script's own second case —
          told the customer the last one carried a rounding that does not
          exist. The SERVER decides (`carries_the_rounding`); the screen does
          not re-derive it, because a second answer to *is this uneven* is how
          a table and its caption end up disagreeing. */}
      {plan.instalments.some((row) => row.carries_the_rounding) ? (
        <p className="mt-2 text-base text-neutral-600" data-rounding-note="">
          {t("portal.askPlan.roundingNote")}
        </p>
      ) : null}
    </div>
  );
}

/**
 * The consequence bullets — **read from the plan, never written here.**
 *
 * ⚠ **THE COUNT IS THE SERVER'S** (`base_instalment_count`), so the copy and the
 * table beside it cannot disagree.
 *
 * ⚠ **THE LATE-FEE BULLET HAS TWO FORMS AND THE ELECTION PICKS ONE**
 * (`BR-CWP-064`). A plan the clerk left the suspension off on says fees still
 * apply — the blueprint calls a box promising otherwise *worse than a blank
 * space*.
 *
 * ⚠ **THERE IS NO *"miss two and the plan ends"* BULLET, AND ITS ABSENCE IS THE
 * DECISION.** See the component docstring and `OQ-CWP-1720`.
 */
function consequences(
  t: (key: string, options?: Record<string, unknown>) => string,
  plan: PortalPlanPreview,
): string[] {
  return [
    t("portal.askPlan.consequence.instalments", {
      count: plan.base_instalment_count,
      amount: formatMoney(plan.base_amount, plan.currency),
      final: formatMoney(plan.final_amount, plan.currency),
    }),
    plan.suspend_late_fees
      ? t("portal.askPlan.consequence.feesStop")
      : t("portal.askPlan.consequence.feesApply"),
    plan.suspend_disconnect
      ? t("portal.askPlan.consequence.noDisconnect")
      : t("portal.askPlan.consequence.disconnectApplies"),
    // `BR-CWP-063` — the sentence customers get wrong, and the one that is
    // cheaper to say here than to explain on the telephone next month.
    t("portal.askPlan.consequence.newBills"),
    // What actually happens when a payment is missed, in place of a promise
    // this product does not keep (`OQ-CWP-1720`).
    t("portal.askPlan.consequence.missed"),
  ];
}
