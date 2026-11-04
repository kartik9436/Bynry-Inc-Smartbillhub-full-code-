// ── Trace ──────────────────────────────────────────────
// Story:    US-CWP-050 (EP-CWP-09) — collecting a connection fee. Screen:
//           CWP-050 (blueprint `P36`) at `/{tenant}/portal/fees`
// Rules:    BR-CWP-058 (the consequence is shown before the commit) ·
//           BR-CWP-056 (the Pay control appears disabled until rails) ·
//           BR-CWP-093 (nothing empty ever appears) · B14 rule 21 · rule 31
//           (no database id on screen — the `SR-` number is the identity) ·
//           rule 32 · rule 33 · rule 35 · rule 36 · CLAUDE.md hard rule 2
// Ruling:   PO 2026-09-05 (`OQ-CWP-1600`) — a fee is a CHARGE CODE and the
//           PLAN says how much. Every figure on this screen is read.
// Tests:    src/portal/payments/Fees.dom.test.tsx
// Impacts:  src/portal/api/portalClient.ts `getFees` ·
//           06-backend/apps/portal/paying.fees_position
// ───────────────────────────────────────────────────────
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { Panel } from "@/components/Panel";
import {
  Card,
  ErrandLink,
  HeldButton,
  MiniTable,
  NamedGaps,
  TotalRow,
  TwoCol,
  usePortalPath,
} from "../components/primitives";
import { PortalScreen, PortalState, type PortalWayOut } from "../components/states";
import { getFees, type PortalFees } from "../api/portalClient";

/**
 * `CWP-050` — *what starting service will cost*.
 *
 * ⚠ **A WAIVED FEE IS LISTED, STRUCK THROUGH, AND IN NEITHER TOTAL.** The
 * record keeps a WAIVER rather than deleting the line, which is what lets an
 * applicant see they were **let off** rather than wonder whether they were
 * quoted correctly (`US-CWP-050` TC-3). Removing the row would be tidier and
 * would take that away.
 *
 * ⚠ **THE DEPOSIT IS NOT TAKEN NOW AND THE SCREEN SAYS SO TWICE** — once as
 * its own row reading *on your first bill*, and once in the closing sentence.
 * TC-4 is explicit that paying the `$335.00` leaves it exactly where it was.
 *
 * ⚠ **THERE IS NO AMOUNT BOX AND THERE IS NO PART PAYMENT** (TC-6). Fees are
 * collected in full before work starts, and the server sends ONE figure — no
 * minimum, no instalments, nothing a screen could turn into a field. The
 * refusal is structural rather than a validation message.
 *
 * ⚠ **AND THE PAY CONTROL IS HELD** (`BR-CWP-056` / `CR-068` R3): no gateway
 * exists, so it renders in its normal place, disabled, with its reason. Never
 * hidden, never live-but-inert.
 */
export function FeesView() {
  const { t } = useTranslation();
  const path = usePortalPath();
  const [body, setBody] = useState<PortalFees | null>(null);
  const [failed, setFailed] = useState(false);
  //: R-10's *Try again* needs something to try — see `arrears/Overdue.tsx`.
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let live = true;
    setFailed(false);
    getFees()
      .then((answer) => {
        if (live) setBody(answer);
      })
      .catch(() => {
        if (live) setFailed(true);
      });
    return () => {
      live = false;
    };
  }, [attempt]);

  // ⚠ **`head={null}` AND THAT IS NOT A SHORTCUT.** `CWP-050`'s `PageHeader`
  // lives in `FeesPage`, because that file serves TWO readers at one address —
  // a signed-in applicant and a stranger — and the head is the thing they
  // share. What this view was missing is the other half `PortalScreen` carries:
  // **`data-screen` was on two of its four branches**, so a failed or still-
  // loading `/fees` rendered no screen mark at all and every rendered check in
  // this repository selects on exactly that.
  const feesWaysOut: PortalWayOut[] = [
    {
      label: t("portal.payNow.tryAgain"),
      onClick: () => setAttempt((n) => n + 1),
      tone: "primary",
      testKey: "try-again",
    },
    // ⚠ **THE SAME DESTINATION THE RAIL ALREADY USES**, asserted by address in
    // its own test (`DEF-CWP-3925`) — an applicant who cannot read what they
    // have been quoted wants to ask a person, and this is where that happens.
    { label: t("portal.fees.askAQuestion"), to: path("/ask-a-question"), testKey: "ask-a-question" },
  ];

  if (failed) {
    return (
      <PortalScreen screen="CWP-050" head={null}>
        <PortalState
          kind="failed"
          testId="fees"
          sentence={t("portal.fees.couldNotRead")}
          waysOut={feesWaysOut}
        />
      </PortalScreen>
    );
  }
  if (body === null) {
    return (
      <PortalScreen screen="CWP-050" head={null}>
        <PortalState kind="loading" testId="fees" sentence={t("portal.fees.reading")} />
      </PortalScreen>
    );
  }
  if (!body.any) {
    // ⚠ `BR-CWP-093` — one sentence, never an empty table with a held button
    // over it. Fees are quoted AFTER a clerk approves (TC-8), and the server is
    // what decides that.
    // ⚠ **NO `waysOut` — THIS IS NOT BAD NEWS.** *There is nothing to pay* is
    // the good answer, and the sentence beside it already says a quote follows
    // approval. R-10 is about a threat with no route out.
    return (
      <PortalScreen screen="CWP-050" head={null}>
        <PortalState kind="empty" testId="fees" sentence={t("portal.fees.none")} />
      </PortalScreen>
    );
  }

  return (
    <div data-screen="CWP-050" className="flex flex-col gap-4">
      {/* ⚠ **THE SCREEN ID IS A LITERAL HERE AND MUST STAY ONE — `CR-085` lane 8.**
          `PortalScreen` renders an identical DOM from its `screen` prop, but THREE
          source scanners find a portal screen by the exact string
          `data-screen="CWP-…"` and not one of them reads a prop: this census,
          `g100_every_screen_has_a_door.py` and `g103_holds_cannot_rot.py`. Wrapping
          this branch too made the whole file invisible to all three — hard-won law
          7’s *reporting zero over a scope it silently excluded*.
          `bills/BillDetail.tsx` keeps the literal on its populated branch for
          exactly this reason. */}
      {/* ⚠ The `SR-` number is the identity and the only reference on screen
          (B14 rule 31) — it is what an applicant reads down the telephone. */}
      <p className="m-0 text-base uppercase tracking-wide text-neutral-600" data-reference="">
        {body.reference}
      </p>
      <TwoCol main={<Bill body={body} />} rail={<WhatHappensNext body={body} />} />
    </div>
  );
}

function Bill(props: { body: PortalFees }) {
  const { t } = useTranslation();
  const { body } = props;
  return (
    <Card testId="fees">
      <div className="flex flex-col gap-4">
        <MiniTable
          caption={t("portal.fees.caption")}
          columns={[
            { key: "fee", label: t("portal.fees.colFee") },
            { key: "when", label: t("portal.fees.colWhen") },
            { key: "amount", label: t("portal.fees.colAmount"), align: "right" as const },
          ]}
          rows={body.lines.map((line, index) => ({
            key: `${line.what}-${index}`,
            muted: line.waived,
            cells: {
              fee: <span data-fee={index}>{line.what}</span>,
              when: (
                <span data-fee-when={line.when}>
                  {line.waived
                    ? t("portal.fees.waived")
                    : t(`portal.fees.when.${line.when}`)}
                </span>
              ),
              amount: line.waived ? (
                // ⚠ **STRUCK THROUGH AND STILL LISTED** (TC-3).
                <s className="tabular-nums" data-fee-amount={index} data-waived="">
                  {line.display}
                </s>
              ) : (
                <span className="tabular-nums" data-fee-amount={index}>
                  {line.display}
                </span>
              ),
            },
          }))}
        />

        {body.to_pay_now?.display ? (
          <TotalRow
            label={t("portal.fees.toPayNow")}
            value={body.to_pay_now.display}
            testKey="to-pay-now"
          />
        ) : null}
        {/* ⚠ **ABSENT, NEVER `$0.00`.** A plan that prices no deposit for this
            class draws no row, because a zero states a deposit was assessed and
            set to nothing — a different fact. */}
        {body.on_first_bill?.display ? (
          <TotalRow
            label={t("portal.fees.onFirstBill")}
            value={body.on_first_bill.display}
            testKey="on-first-bill"
          />
        ) : null}

        {/* ⚠ ONE control, ONE figure, and no field beside it (TC-6). The
            figure is on the wrapper as data as well as inside the label,
            because the label is a catalogue sentence with the amount
            interpolated and a test may not assert one language's word order. */}
        <div
          data-fees-hold={body.held_reason}
          data-pay-amount={body.to_pay_now?.display ?? ""}
        >
          <HeldButton
            label={t("portal.fees.pay", { amount: body.to_pay_now?.display ?? "" })}
            reason={t(`portal.fees.held.${body.held_reason}`)}
          />
        </div>
        <NamedGaps problems={body.problems} mark="data-fees-gaps" />
      </div>
    </Card>
  );
}

/** The rail: what paying does, and what it does not do. `BR-CWP-058`. */
function WhatHappensNext(props: { body: PortalFees }) {
  const { t } = useTranslation();
  return (
    <>
      <Panel as="aside" tone="info" title={t("portal.fees.beforeYouPayHeading")}>
        {/* B14 rule 32 — one sentence per section. */}
        <p className="m-0 text-body text-neutral-700" data-work-starts="">
          {t("portal.fees.workStarts")}
        </p>
      </Panel>
      {props.body.on_first_bill?.display ? (
        <Panel as="aside" title={t("portal.fees.depositHeading")}>
          <p className="m-0 text-body text-neutral-700" data-deposit-note="">
            {t("portal.fees.depositComesBack")}
          </p>
        </Panel>
      ) : null}
      <Panel as="aside" title={t("portal.fees.questionsHeading")}>
        {/* ⚠ A REAL DESTINATION. `/ask-a-question` is routed and live, and the
            test asserts it BY ADDRESS (`DEF-CWP-3925`) rather than by label. */}
        <ErrandLink label={t("portal.fees.askAQuestion")} to="/ask-a-question" />
      </Panel>
    </>
  );
}
