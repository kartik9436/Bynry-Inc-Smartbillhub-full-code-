// ── Trace ──────────────────────────────────────────────
// Story:    US-CWP-047 (EP-CWP-09) — autopay: an intent that already exists,
//           waiting for a charge that does not. Screen: CWP-040 (blueprint
//           `P26`) at `/{tenant}/portal/autopay`
// Rules:    BR-CWP-056 (visible, disabled, carrying its reason — never
//           live-but-inert) · BR-PAY-015 (the intent is the record; `amount`
//           and `scheduled_on` are what the customer was TOLD) · BR-PAY-013
//           (two bounces and the account goes cash-only) · BR-CWP-093 (nothing
//           empty ever appears) · B14 rule 21 (Tailwind utilities, no new
//           stylesheet class) · rule 31 (no database id on screen) · rule 32
//           (one sentence per section) · rule 33 (a refusal is five or six
//           words) · rule 35 (the catalogue writes the words) · rule 36 (the
//           shared kit is how you comply) · CLAUDE.md hard rule 2
// Tests:    src/portal/methods/Autopay.dom.test.tsx
// Impacts:  src/portal/api/portalClient.ts `getAutopay` ·
//           06-backend/apps/payments/autopay.portal_position
// ───────────────────────────────────────────────────────
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { Panel } from "@/components/Panel";
import {
  ButtonRow,
  ConsequenceBox,
  ErrandLink,
  FormField,
  HeldButton,
  MiniTable,
  NamedGaps,
  StatusChip,
  TwoCol,
} from "../components/primitives";
import { Card } from "../components/primitives";
import { usePortalDate } from "../components/regional";
import { getAutopay, type PortalAutopay } from "../api/portalClient";

/**
 * `CWP-040` — *your bill, taken automatically*, over a product that cannot take
 * anything.
 *
 * ⚠ **THE SWITCH IS A PROMISE NOBODY CAN KEEP TODAY AND IT SAYS SO ON ITS
 * FACE.** `BR-PAY-015` makes autopay v1 a capture-INTENT: enrolment is stored,
 * an intent is written at bill issue, and **no path in this product charges a
 * stored instrument**. So *Turn autopay on* renders in its normal place,
 * disabled, carrying its reason (`BR-CWP-056` / `CR-068` R3) — never hidden,
 * and never live-but-inert.
 *
 * ⚠ **AND THE TABLE BESIDE IT IS REAL.** That is the whole shape of this
 * screen: the control is held and the *next few* rows are the intents bill
 * issue already wrote, with **the amount the customer was told**. Correcting
 * the bill afterwards does not move them (`US-CWP-047` TC-4) — the figure is
 * stored on the intent rather than recomputed, so what was promised survives.
 *
 * ⚠ **AN UNBILLED MONTH SHOWS TWO EM DASHES, NOT ONE.** The AMOUNT is absent
 * because the story says ⚠ *not an estimate*; the DATE is absent because
 * nothing in this product answers an account's next due date before the bill is
 * made. Drawing either would be this screen inventing a figure — and a date a
 * customer plans around is not a smaller lie than an amount.
 *
 * ⚠ **WHEN IS READ-ONLY AND THERE IS NO CONTROL TO CHANGE IT** (TC-5).
 * *Always the due date. It cannot be changed.* A disabled date picker would
 * still be a date picker; what renders is the sentence.
 *
 * ⚠ **AND THE SCREEN SAYS WHICH OF THREE STATES THE ACCOUNT IS IN
 * (`DEF-CWP-4683`, `CR-085` `CPB-02`).** It read NEITHER `elected` nor
 * `enrolled` — both of which the body has carried since wave Q — so every
 * account got the same page: *Turn autopay on*, over an account that might
 * already be on it. **Six of the 73 seeded Pine Hill accounts are**, and each
 * of those customers was offered a switch for something already running, with
 * no way off named anywhere.
 *
 * **The third state is the one that costs money.** `elected` is what the
 * customer ASKED FOR and nothing un-asks it; `enrolled` is whether the account
 * may be autopaid at all, and two bounces turn that off without touching their
 * election (`BR-PAY-013`). Such an account was reading *We take the balance on
 * each due date* while nothing would be taken — so somebody expecting their
 * bill to be paid collects a late fee instead. It is now said plainly.
 *
 * ⚠ **THE CONTROL IS STILL HELD IN ALL THREE, AND THAT IS NOT THE SAME AS
 * BEING UNCHANGED.** Turning autopay off is a WRITE, and `BR-CWP-001` allows
 * the portal rows of exactly six kinds; no ruling has opened a seventh, so this
 * lane did not invent one. What changed is that the held control now names the
 * thing the customer actually wants — *Turn autopay off* on an account that is
 * on it — and its reason tells them how. A held button offering the opposite of
 * what somebody needs is worse than a held button, because they read it as
 * *this is all I can do here*.
 */
export function AutopayView(props: { accountId: string }) {
  const { t } = useTranslation();
  const [body, setBody] = useState<PortalAutopay | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let live = true;
    getAutopay(props.accountId)
      .then((answer) => {
        if (live) setBody(answer);
      })
      .catch(() => {
        if (live) setFailed(true);
      });
    return () => {
      live = false;
    };
  }, [props.accountId]);

  if (failed) {
    return (
      <Card testId="autopay">
        <p className="text-body text-neutral-600">{t("portal.autopay.couldNotRead")}</p>
      </Card>
    );
  }
  if (body === null) {
    return (
      <Card testId="autopay">
        <p className="text-body text-neutral-600">{t("portal.autopay.reading")}</p>
      </Card>
    );
  }

  return (
    <div className="flex flex-col gap-4" data-screen="CWP-040">
      <TwoCol
        main={<Choices body={body} />}
        rail={<NextFew body={body} />}
      />
    </div>
  );
}

/** The left card: take it from · how much · when · what happens · the switch. */
/**
 * Which of the three, as ONE word (`DEF-CWP-4683`).
 *
 * ⚠ **THE ORDER IS LOAD-BEARING AND IT IS THE UNCOMFORTABLE ONE FIRST.**
 * *asked for and not running* is tested before *running*, because an account
 * that is both `elected` and refused must never fall through to the reassuring
 * branch. Reading a stopped account as *on* is the answer that produces a
 * missed bill; reading an *on* account as *stopped* would only alarm somebody.
 * The safe wrong answer goes second.
 */
function autopayState(body: PortalAutopay): "stopped" | "on" | "off" {
  if (body.elected && !body.enrolled) return "stopped";
  if (body.elected) return "on";
  return "off";
}

function Choices(props: { body: PortalAutopay }) {
  const { t } = useTranslation();
  const { body } = props;
  //: ⚠ `cash_only` outranks `no_rails` and the SERVER decides which — a screen
  //: that picked its own reason would be a second implementation of a refusal.
  const reason = t(`portal.autopay.held.${body.held_reason}`, {
    count: body.bounces,
  });
  const state = autopayState(body);
  return (
    <Card testId="autopay">
      <div className="flex flex-col gap-4" data-autopay-state={state}>
        {/* ⚠ **WHAT IS TRUE RIGHT NOW, BEFORE ANY OF THE CHOICES BELOW IT.**
            B14 rule 32 — one sentence, and it is the one a customer opened this
            page to read. */}
        <p className="m-0 text-body font-semibold text-neutral-800" data-autopay-status="">
          {t(`portal.autopay.state.${state}`)}
        </p>
        <FormField
          id="autopay-take-from"
          label={t("portal.autopay.takeItFrom")}
          helper={t("portal.autopay.takeItFromHelper")}
        >
          {/* ⚠ **A LINK, NOT A SELECT.** Adding or removing a method is
              `CWP-039`'s job and demands a fresh code; a select here would be a
              second place a payment method is chosen. The destination is
              asserted BY ADDRESS in the test (`DEF-CWP-3925`).

              ⚠ **AND IT IS INSIDE A `ButtonRow`, WHICH IS THE WHOLE FIX FOR
              THE FULL-WIDTH BAR** (`DEF-CWP-4133`, the same fault delta row
              39.5 records one screen over). `Card` is `flex flex-col`, so a
              control placed directly in it STRETCHES to the card — 668px of
              bordered button reading *Your payment methods*, which is not one
              of the kit's two button sizes (B14 rule 36, r10 rule 5). The
              class list is identical either way, so no test, no `tsc` and no
              gate can see it; only a browser can. `CWP-039` was measured at
              1060px before its `ButtonRow` and 121px after. */}
          <ButtonRow>
            <ErrandLink label={t("portal.autopay.manageMethods")} to="/payment-methods" />
          </ButtonRow>
        </FormField>

        <FormField
          id="autopay-how-much"
          label={t("portal.autopay.howMuch")}
          helper={t("portal.autopay.howMuchHelper")}
        >
          <p className="m-0 text-body text-neutral-900" data-how-much={body.how_much}>
            {t(`portal.autopay.amount.${body.how_much}`)}
          </p>
        </FormField>

        {/* ⚠ **READ-ONLY, AND NOT A DISABLED DATE PICKER** (TC-5). */}
        <FormField
          id="autopay-when"
          label={t("portal.autopay.when")}
          helper={t("portal.autopay.whenHelper")}
        >
          <p className="m-0 text-body text-neutral-900" data-when={body.when}>
            {t(`portal.autopay.on.${body.when}`)}
          </p>
        </FormField>

        {/* ⚠ **THE HEADING IS SCOPED WHERE THE PRESENT TENSE WOULD BE A LIE**
            (`DEF-CWP-4683`, found by looking at the screen). The bullets
            describe the PRODUCT and are correct in every state; *WHAT HAPPENS*
            is what claims they describe THIS account today, and on a stopped
            account *"We take the balance on each due date"* sat four lines
            under *"we are not taking payments automatically"*. The bullets are
            left alone — somebody deciding whether to get it running again needs
            to read exactly those. */}
        <ConsequenceBox
          heading={t(
            state === "stopped"
              ? "portal.autopay.consequenceHeadingStopped"
              : "portal.autopay.consequenceHeading",
          )}
          bullets={[
            t("portal.autopay.consequenceTakes"),
            t("portal.autopay.consequenceWarns"),
            t("portal.autopay.consequenceStops"),
          ]}
        />

        {/* ⚠ **VISIBLE, DISABLED, CARRYING ITS REASON** (`BR-CWP-056`).
            The reason and the bounce COUNT are also on the wrapper as data,
            because the sentence is the catalogue's and a test that asserted
            English would be asserting one of eleven catalogues (B14 rule 35). */}
        {/* ⚠ **THE CONTROL MATCHES THE STATE.** An account already on autopay
            is not offered *Turn autopay on*; it is offered the thing it would
            actually want, held, with the reason that says what to do instead.
            Still `HeldButton` in every branch — stopping autopay is a write and
            `BR-CWP-001` names six kinds, none of them this (`BR-CWP-056`:
            visible, disabled, carrying its reason — never live-but-inert). */}
        <div data-autopay-hold={body.held_reason} data-bounces={String(body.bounces)}>
          <HeldButton
            label={state === "off" ? t("portal.autopay.turnOn") : t("portal.autopay.turnOff")}
            reason={state === "off" ? reason : t("portal.autopay.turnOffHeld")}
          />
        </div>

        {/* ⚠ The gaps in the customer's own words, or nothing at all —
            `NamedGaps` renders a code with no sentence as NOTHING rather than
            printing the server's engineering prose (`DEF-CWP-3926`). */}
        <NamedGaps problems={body.problems} mark="data-autopay-gaps" />
      </div>
    </Card>
  );
}

/** The rail: the *next few* table. `BR-CWP-093` — never an empty one. */
function NextFew(props: { body: PortalAutopay }) {
  const { t } = useTranslation();
  const { body } = props;
  //: ⚠ **THE TENANT'S OWN DATE FORMAT, FROM THE PUBLISHED FORMATTER**
  //: (`DEF-CWP-4870`, and `DEF-CWP-4197`'s family). This table printed
  //: `2026-08-22` — a raw ISO date — on the ONE screen that tells somebody when
  //: money will leave their bank account, while `/payments` two clicks away
  //: rendered `08/13/2026` and `/payment-methods` rendered `06/02/2026`. It was
  //: the fourth occurrence of that family and it was not in the grep that
  //: closed the other three; `DEF-CWP-4131`'s own prevention note says to grep
  //: every sibling screen that renders the same KIND of value.
  //:
  //: ⚠ **WRITING A DATE HELPER IN THIS FILE IS WHAT `DEF-CWP-3994` EXISTS TO
  //: STOP** — the portal has ONE formatter, published at the frame, and it
  //: carries the tenant's format AND its time zone.
  const asDate = usePortalDate();
  //: ⚠ **AN EMPTY TABLE IS HEADERS OVER NOTHING, WHICH IS WHAT B14 rule 17 AND
  //: R-22 BOTH FORBID.** On an account with autopay off this rail drew `DATE ·
  //: EXPECTED · STATUS` and not one row, with only the footnote beneath — a
  //: picture that says nothing at all, where the customer needs a sentence
  //: saying WHAT WOULD FILL IT. The PO's ruling on R-22 is that states are
  //: told apart by their words (*"differntiate it using text message"*), so
  //: this is a sentence and not a second layout.
  if (body.next_few.length === 0) {
    return (
      <Panel as="aside" title={t("portal.autopay.nextFewHeading")}>
        <p className="m-0 text-body text-neutral-600" data-next-few-empty="">
          {t("portal.autopay.nextFewEmpty")}
        </p>
      </Panel>
    );
  }
  return (
    <Panel as="aside" title={t("portal.autopay.nextFewHeading")}>
      <MiniTable
        caption={t("portal.autopay.nextFewCaption")}
        columns={[
          { key: "date", label: t("portal.autopay.colDate") },
          { key: "expected", label: t("portal.autopay.colExpected"), align: "right" as const },
          { key: "status", label: t("portal.autopay.colStatus") },
        ]}
        rows={body.next_few.map((slot, index) => ({
          key: `${slot.state}-${index}`,
          muted: slot.state !== "scheduled",
          cells: {
            // ⚠ **AN EM DASH, NEVER A GUESSED DATE.**
            //: The ATTRIBUTE keeps the server's own string — it is what a
            //: test and a walkthrough read — and the VISIBLE value is the
            //: tenant's format. The two must not be the same string, which is
            //: exactly what made the fault invisible one screen over.
            date: (
              <span data-slot-date={index} data-slot-on={slot.scheduled_on ?? ""}>
                {asDate(slot.scheduled_on) || t("portal.autopay.noDateYet")}
              </span>
            ),
            // ⚠ **AN EM DASH, NEVER AN ESTIMATE** (TC-3).
            expected: (
              <span className="tabular-nums" data-slot-amount={index}>
                {slot.display ?? t("portal.autopay.noAmountYet")}
              </span>
            ),
            status: (
              <StatusChip
                tone={slot.state === "scheduled" ? "warning" : "neutral"}
                testKey={`slot-${index}`}
              >
                {t(`portal.autopay.slot.${slot.state}`)}
              </StatusChip>
            ),
          },
        }))}
      />
      {/* B14 rule 32 — one sentence, and it is the one that stops a customer
          believing the row above is a bill. */}
      <p className="m-0 mt-3 text-base text-neutral-600" data-next-few-note="">
        {t("portal.autopay.nextFewNote")}
      </p>
    </Panel>
  );
}
