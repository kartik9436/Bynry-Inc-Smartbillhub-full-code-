// ── Trace ──────────────────────────────────────────────
// Story:    US-CWP-046 (EP-CWP-09) — your payment methods: a token, never a
//           card number, and why a control is refused · US-CWP-022 (EP-CWP-05)
//           — step up before a stored method changes. Screen: CWP-039
//           (blueprint `P25`) · wireframes/CWP-039.png
// Rules:    BR-CWP-057 (a token with a brand and a last four; the note about it
//           is a DESIGN REQUIREMENT, not reassurance copy) · BR-CWP-040
//           (step-up before a method is added, changed or removed) ·
//           BR-CWP-056 (a refused control is VISIBLE, DISABLED and carries its
//           reason — never hidden, never live-but-inert) · B14 rule 17 (an
//           empty state says what fills it) · rule 21 (Tailwind utilities;
//           `portal/` is on route-b-migrated.txt) · rule 31 (no database id on
//           screen) · rule 32 (one sentence per section) · rule 33 (a refusal
//           is five or six words) · rule 35 (the catalogue writes the words) ·
//           rule 36 (compose the shared kit)
// Tests:    src/portal/methods/Methods.dom.test.tsx
// Impacts:  src/portal/methods/methodsApi.ts · MethodsPage.tsx
// ───────────────────────────────────────────────────────
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/Button";
import { PencilIcon, TrashIcon } from "@/components/icons";
import { PageHeader } from "@/components/PageHeader";
import { RowAction, RowActions } from "@/components/RowActions";
import { Announced, PortalRefusal } from "../components/a11y";

import { usePortalDate } from "../components/regional";
import { PortalScreen, PortalState } from "../components/states";
import {
  ButtonRow,
  Card,
  CommitButton,
  ErrandLink,
  FormField,
  HeldButton,
  InfoBar,
  KVList,
  MiniTable,
  SectionTitle,
  StatusChip,
  TextInput,
  type ChipTone,
  WizardFooter,
} from "../components/primitives";
import {
  askForStepUpCode,
  getPaymentMethods,
  removePaymentMethod,
  savePaymentMethod,
  type PortalPaymentMethod,
  type PortalPaymentMethods,
} from "./methodsApi";

/** `active` · `verified` · `expired` → the kit's tones. An expired card is
 *  `warning` rather than `danger`: nothing is wrong, the card simply ran out. */
const TONE: Record<string, ChipTone> = {
  active: "success",
  verified: "success",
  expired: "warning",
};

/** What the step-up is FOR, once a code has been asked for. */
type Intent = { kind: "add" } | { kind: "remove"; ref: string; label: string };

/**
 * `CWP-039` — your payment methods, and the sentence that explains the whole
 * shape of the table.
 *
 * ⚠ **THE NOTE IS A DESIGN REQUIREMENT, NOT REASSURANCE COPY** (`US-CWP-046`
 * §1, in as many words). *We never hold your full card number — your bank gives
 * us a token, which is why we can only ever show the last four digits.* That
 * sentence is on screen because it is TRUE OF THE SCHEMA: there is no column a
 * card number would fit in, and a utility with one or two staff cannot carry
 * the compliance burden of one. It explains an apparent limitation rather than
 * apologising for it.
 *
 * ⚠ **ADDING OR REMOVING ONE DEMANDS A FRESH CODE** (`US-CWP-022`,
 * `BR-CWP-040`) — this is the one action that redirects money, so the session
 * alone is not enough. The code box appears only after a code has been sent,
 * and the endpoint refuses without one regardless of what this screen does: a
 * screen order is not the security.
 *
 * ⚠ **AND A REFUSED CONTROL IS VISIBLE, DISABLED AND CARRIES ITS REASON**
 * (`BR-CWP-056`). On a cash-only account, or one that has bounced payments,
 * *Set up autopay* is a `HeldButton` with the words on it — never removed,
 * because a customer who came here to find it would conclude the product does
 * not have it.
 */
export function MethodsView() {
  const { t } = useTranslation();
  //: ⚠ **THE ADDED COLUMN WAS A RAW `2026-09-06`** (`DEF-CWP-4197`, the same
  //: fault the guest receipt had). `CWP-039.png` reads *4 Mar 2026*. The hook
  //: is the published one — a date helper written in this file would be the
  //: second formatter `DEF-CWP-3994` exists to stop.
  const asDate = usePortalDate();
  const [held, setHeld] = useState<PortalPaymentMethods | null>(null);
  const [failed, setFailed] = useState(false);
  const [working, setWorking] = useState(false);
  const [refused, setRefused] = useState<string | null>(null);
  const [intent, setIntent] = useState<Intent | null>(null);
  const [sentTo, setSentTo] = useState<string | null>(null);
  const [code, setCode] = useState("");
  const [reference, setReference] = useState("");

  useEffect(() => {
    let live = true;
    getPaymentMethods()
      .then((answer) => {
        if (live) setHeld(answer);
      })
      .catch(() => {
        if (live) setFailed(true);
      });
    return () => {
      live = false;
    };
  }, []);

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
  // ⚠ **AND THE LOADING BRANCH WAS `return null` — A WHOLE SCREEN RENDERING
  // NOTHING AT ALL.** R-22's ruling is that the three states are told apart by
  // their SENTENCE and that *"none of them may be a generic card with no
  // words"*; a branch that draws no words, no title and no frame is that rule
  // failing in its strongest form. `portal.methods.reading` is new in all
  // eleven catalogues.
  const head = (
    <PageHeader
      kicker={t("portal.methods.kicker")}
      title={t("portal.methods.title")}
      primaryAction={
        // ⚠ `data-add-method` IS A TEST HOOK AND IT EARNED ITS PLACE. The
        // three cases that press this control used to find it by its LABEL,
        // and the day the eleven catalogues arrived all three went red — the
        // label had become English. A control worth testing is worth naming.
        <Button
          variant="primary"
          data-add-method=""
          onClick={() => void askForCode({ kind: "add" })}
        >
          {t("portal.methods.add")}
        </Button>
      }
    />
  );

  if (failed) {
    return (
      <PortalScreen screen="CWP-039" head={head}>
        {/* ⚠ `data-methods-failed` IS KEPT — two suites select on it. The
            RefusalStrip around it is what changed, not the handle. */}
        <PortalState kind="failed" sentence={t("portal.methods.failed")}>
          <span data-methods-failed="" hidden />
        </PortalState>
      </PortalScreen>
    );
  }
  if (held === null) {
    return (
      <PortalScreen screen="CWP-039" head={head}>
        <PortalState kind="loading" sentence={t("portal.methods.reading")} />
      </PortalScreen>
    );
  }

  async function askForCode(wanted: Intent) {
    setWorking(true);
    setRefused(null);
    setCode("");
    try {
      const answer = await askForStepUpCode();
      if (!answer.sent) {
        // `BR-CWP-034` — no contact on file dead-ends into *ring the office*.
        // It must never fall back to something weaker.
        setRefused(t("portal.methods.noContact"));
        return;
      }
      setIntent(wanted);
      setSentTo(answer.sent_to ?? null);
    } catch {
      setRefused(t("portal.methods.codeFailed"));
    } finally {
      setWorking(false);
    }
  }

  async function reload() {
    setHeld(await getPaymentMethods());
    setIntent(null);
    setSentTo(null);
    setCode("");
    setReference("");
  }

  async function commit() {
    if (intent === null) return;
    setWorking(true);
    setRefused(null);
    try {
      const answer =
        intent.kind === "add"
          ? await savePaymentMethod({ code, reference })
          : await removePaymentMethod(intent.ref, { code });
      const done = "saved" in answer ? answer.saved : answer.removed;
      if (!done) {
        // ⚠ **FIVE OR SIX WORDS, AND THE CATALOGUE WRITES THEM** (B14 rules 33
        // and 35). The server answers a KEY — `wrong`, `expired`, `locked`,
        // `code_needed`, `not_a_reference` — never a sentence.
        setRefused(t(`portal.methods.refused.${answer.reason ?? "unknown"}`));
        return;
      }
      await reload();
    } catch {
      setRefused(t("portal.methods.saveFailed"));
    } finally {
      setWorking(false);
    }
  }

  const autopay = held.autopay;
  return (
    <div data-screen="CWP-039">
      {/* ⚠ **THE PRIMARY ACTION IS BESIDE THE TITLE, NOT INSIDE THE NOTICE**
          (`DEF-CWP-3973`, delta 39.2). It was drawn in the `InfoBar`'s
          right-hand slot — inside the bar that EXPLAINS card tokenisation —
          which is the one place a primary action should never be: it reads as
          part of the explanation rather than as the thing to press. Two valid
          kit components composed into one wrong screen, which is why nothing
          objected.

          ⚠ **AND IT IS LIVE, NOT HELD, THOUGH THE DRAWING SHOWS IT HELD.**
          `CWP-039.png` paints it brand-bordered with GREY text — this kit's
          held presentation, the same reading `DEF-CWP-3993` established for
          `CWP-034`'s `Send a reading`. The drawing is right about the SHAPE and
          out of date about the STATE: it was drawn when the stored-instrument
          table did not exist ("Rests on: nothing"), and `POST
          /portal/payment-methods` writes one today. A held control over a live
          path is `DEF-CWP-3925`, which this product has paid for eight times. */}
      {head}

      <Card testId="methods-list">
        <SectionTitle>{t("portal.methods.savedTitle")}</SectionTitle>
        {held.methods.length === 0 ? (
          // B14 rule 17 — a stated absence says what fills it. An empty table
          // would assert nothing rather than explaining what to do next.
          <p className="text-body text-neutral-600" data-methods-empty="">
            {t("portal.methods.none")}
          </p>
        ) : (
          <>
            {/* ⚠ **THE PHONE GETS A CARD PER METHOD AND THE DESK GETS THE
                TABLE** (`CR-085`, and the drawing's own phone frame). Measured
                at 390: the table's content is 459px wide inside a 316px column,
                so the METHOD cell wraps to one word a line, the status chip is
                clipped mid-word (`VE`, `AC`) and the whole ACTION column —
                Change and Remove — sits off the right-hand edge. This screen
                exists to answer *what is on file and what breaks if I remove
                one*; on a phone it could do neither. `CWP-027` and `CWP-041`
                take the same shape for the same reason.

                ⚠ **ONE SOURCE FOR BOTH.** Both halves render `held.methods`
                and both call the SAME `askForCode`, so a phone cannot reach a
                second path to the one write that redirects money
                (`BR-CWP-040`). */}
            <div className="mt-3 flex flex-col gap-3 md:hidden" data-methods-cards="">
              {held.methods.map((method) => (
                <MethodPhoneCard
                  key={method.last_four}
                  method={method}
                  onRemove={() =>
                    void askForCode({
                      kind: "remove",
                      ref: method.ref,
                      label: methodLabel(method),
                    })
                  }
                />
              ))}
            </div>
            <div className="max-md:hidden">
            <MiniTable
              caption={t("portal.methods.caption")}
              columns={[
                { key: "method", label: t("portal.methods.colMethod") },
                { key: "added", label: t("portal.methods.colAdded") },
                { key: "usedFor", label: t("portal.methods.colUsedFor") },
                { key: "status", label: t("portal.methods.colStatus") },
                { key: "act", label: t("portal.methods.colAct"), align: "right" },
              ]}
              rows={held.methods.map((method) => ({
                // ⚠ **THE ROW KEY IS THE FOUR DIGITS AND NOT THE ROW ID** (B14
                // rule 31). `data-row` reaches the DOM, so a `ref` here would put
                // a database id on screen in everything but name.
                key: method.last_four,
                muted: !method.usable,
                cells: {
                  // ⚠ **TWO LINES: the name a person recognises, then what KIND
                  // of thing it is** (delta 39.3, `CWP-039.png`). One line read
                  // `Chase ••••4021` and left a customer to work out from the
                  // brand whether that was a card or a bank mandate — which is
                  // the difference between a payment that clears the same day and
                  // one that takes three.
                  method: <MethodCell method={method} />,
                  added: asDate(method.added_on),
                  usedFor: method.used_for
                    .map((use) => t(`portal.methods.use.${use}`))
                    .join(" · "),
                  status: (
                    <StatusChip tone={TONE[method.status] ?? "neutral"} testKey={method.status}>
                      {t(`portal.methods.status.${method.status}`)}
                    </StatusChip>
                  ),
                  // ⚠ **ROW ICONS, WHICH IS WHAT B14 RULE 15 RESERVES THEM FOR**
                  // (delta 39.3 · X6). A full `Remove` button in every row spent
                  // the danger tier on a list, and the wireframe draws ✎ and −.
                  //
                  // ⚠ **THE PENCIL IS HELD AND SAYS WHY, RATHER THAN ABSENT.**
                  // There is no edit endpoint — `savePaymentMethod` adds and
                  // `removePaymentMethod` removes, and nothing changes one in
                  // place. `CR-068` R3: a control that may not be used is
                  // VISIBLE, DISABLED and carries its reason; hiding it would
                  // leave a customer who came looking for it concluding the
                  // product cannot do it at all. `RowAction`'s `reason` is the
                  // kit's single decision about what that looks like.
                  act: (
                    <RowActions>
                      {/* ⚠ **A `testId`, NOT AN INDEX AND NOT A LABEL.** The
                          case that presses remove used to click
                          `[data-row="4021"] button` at index 0 — which the day
                          this row grew a second icon silently became the PENCIL,
                          and the pencil is held, so the click did nothing and the
                          assertion failed on a screen that was correct. A label
                          query would be asserting one of eleven catalogues. */}
                      <RowAction
                        testId="method-edit"
                        label={t("portal.methods.edit")}
                        icon={<PencilIcon />}
                        reason={t("portal.methods.editHeld")}
                        onClick={() => undefined}
                      />
                      <RowAction
                        testId="method-remove"
                        danger
                        label={t("portal.methods.remove")}
                        icon={<TrashIcon />}
                        onClick={() =>
                          void askForCode({
                            kind: "remove",
                            ref: method.ref,
                            label: methodLabel(method),
                          })
                        }
                      />
                    </RowActions>
                  ),
                },
              }))}
            />
            </div>
          </>
        )}

        {/* ⚠ **THE SENTENCE THE WHOLE TABLE RESTS ON** — see the component
            docstring. It sits under the list because it explains why the list
            can only ever say `••••4021`. */}
        <InfoBar lead={t("portal.methods.tokenLead")} bold={t("portal.methods.tokenBold")} />

        {/* ⚠ **A REFUSAL RAISED BEFORE THE CODE BOX EXISTS HAS TO LAND
            SOMEWHERE, AND UNTIL ITS TEST WAS WRITTEN IT DID NOT.** Asking for a
            code can fail on its own — `BR-CWP-034`'s *no contact on file*, or
            the request itself — and at that moment `intent` is still null, so
            the step-up card is not on screen and the strip inside it cannot
            render. The customer pressed *Add a method* and nothing at all
            happened. Found by `Methods.dom.test.tsx`, which is the only thing
            that could have found it. */}
        {refused !== null && intent === null ? (
          <PortalRefusal data-methods-refused="">{refused}</PortalRefusal>
        ) : null}
      </Card>

      {intent !== null ? (
        <div className="mt-4">
          <Card testId="methods-step-up">
            {/* F-04 (`DEF-CWP-10552`): the opened step takes focus at its heading. */}
            <Announced tone="status" as="div">
              <SectionTitle>{t("portal.methods.stepUpTitle")}</SectionTitle>
            </Announced>
            {/* B14 rule 32 — ONE sentence for this section, and it is the one
                that says why a code is being asked for at all. */}
            <p className="max-w-measure text-body text-neutral-600" data-step-up-why="">
              {t("portal.methods.stepUpWhy")}
            </p>
            {/* ⚠ **THE MASKED DESTINATION IS ALSO ON THE ATTRIBUTE, AND THAT
                IS A TEST HOOK WITH A REASON RATHER THAN A CONVENIENCE.** The
                value only ever appears INSIDE an interpolated sentence, so a
                test can assert it only through whatever the catalogue happens
                to say — which makes the assertion a translation check instead
                of a *did the right contact reach the screen* check. It is the
                same shape `data-card-fee` already takes below. */}
            {sentTo !== null ? (
              <p className="text-body text-neutral-700" data-step-up-sent={sentTo}>
                {t("portal.methods.sentTo", { masked: sentTo })}
              </p>
            ) : null}
            {intent.kind === "remove" ? (
              <p
                className="text-body font-semibold text-neutral-900"
                data-step-up-target={intent.label}
              >
                {t("portal.methods.removing", { method: intent.label })}
              </p>
            ) : (
              <FormField
                id="method-reference"
                label={t("portal.methods.referenceLabel")}
                required
                helper={t("portal.methods.referenceHelper")}
              >
                <TextInput id="method-reference" value={reference} onChange={setReference} />
              </FormField>
            )}
            <FormField id="method-code" label={t("portal.methods.codeLabel")} required>
              <TextInput id="method-code" value={code} onChange={setCode} />
            </FormField>
            {refused !== null ? (
              <PortalRefusal data-methods-refused="">{refused}</PortalRefusal>
            ) : null}
            {/* `DEF-CWP-9164` — Cancel on the LEFT, the commit on the RIGHT. */}
            <WizardFooter
              back={
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => {
                    setIntent(null);
                    setRefused(null);
                  }}
                >
                  {t("portal.methods.cancel")}
                </Button>
              }
              forward={
                <CommitButton
                  label={
                    intent.kind === "add"
                      ? t("portal.methods.commitAdd")
                      : t("portal.methods.commitRemove")
                  }
                  working={working}
                  ready={code.trim() !== "" && (intent.kind === "remove" || reference.trim() !== "")}
                  reason={t("portal.methods.codeNeeded")}
                  onClick={() => void commit()}
                />
              }
            />
          </Card>
        </div>
      ) : null}

      <div className="mt-4">
        <Card testId="methods-autopay">
          <SectionTitle>{t("portal.methods.autopayTitle")}</SectionTitle>
          {/* ⚠ **THE STANDING OF AUTOPAY, SAID OUT LOUD** (delta 39.5). The
              wireframe gives autopay its own screen and its own red panel —
              *"Today this switch would be a promise nobody can keep."* This
              card is OURS (39.6) and it was showing nothing but a door, so a
              customer pressing it learned only on the next screen that nothing
              can charge anything. One sentence, B14 rule 32's budget. */}
          <p className="max-w-measure text-body text-neutral-600" data-autopay-stance="">
            {t("portal.methods.autopayStance")}
          </p>
          {/* ⚠ **A BUTTON ROW, AND THAT IS THE WHOLE FIX FOR THE FULL-WIDTH
              BAR** (delta 39.5). `Card` is `flex flex-col`, so a control placed
              directly in it STRETCHES to the card's width — which is not one of
              the kit's two button sizes and read, on screen, as a live switch
              spanning the card. Every correctly-sized control in this portal is
              inside a `flex` row; this one was not, and nothing could see it
              because the class list is identical either way. */}
          <ButtonRow>
            {autopay.allowed ? (
              // ⚠ **A LIVE LINK, BY ADDRESS, TO A ROUTED SCREEN.** `/autopay`
              // is `CWP-040` and is registered; a held control over a live
              // screen is `DEF-CWP-3925`, which cost this product six shut
              // doors. What cannot happen yet is the CHARGE, and that is
              // `CWP-040`'s own sentence to make — not a reason to shut its
              // door.
              <ErrandLink label={t("portal.methods.autopayGo")} to="/autopay" />
            ) : (
              // `BR-CWP-056` — visible, disabled, and the reason ON it. The
              // catalogue writes five or six words per key (B14 rule 33).
              <HeldButton
                label={t("portal.methods.autopayGo")}
                reason={t(`portal.methods.autopayBlocked.${autopay.reason ?? "unknown"}`, {
                  count: autopay.bounces,
                })}
              />
            )}
          </ButtonRow>
        </Card>
      </div>

      {/* ⚠ **THE FEE STANCE, AND NEVER A FIGURE.** `OQ-1394` closed with BOTH
          answers behind a per-tenant switch; pricing a surcharge needs a
          processor's own schedule and there is no processor, so this states
          what the utility has chosen and shows no number. */}
      <div className="mt-4">
        <Card testId="methods-card-fee">
          <SectionTitle>{t("portal.methods.feeTitle")}</SectionTitle>
          <p className="max-w-measure text-body text-neutral-600" data-card-fee={held.card_fee.payer}>
            {t(`portal.methods.fee.${held.card_fee.payer}`)}
          </p>
        </Card>
      </div>
    </div>
  );
}

/**
 * **ONE SAVED METHOD, PHONE-SHAPED** (`CR-085`, wireframe frame *Phone · 390*).
 *
 * The drawing's phone frame stacks what the desk table spreads across five
 * columns: what the method IS, its status, when it was added, what it is used
 * for, and the two actions. Every value is the same one the table's cell
 * renders — `MethodCell`, the kit's `StatusChip`, `usePortalDate`'s published
 * format — so the two halves cannot say different things.
 *
 * ⚠ **THE PENCIL IS HELD HERE TOO, AND SAYS THE SAME SIX WORDS.** There is no
 * edit endpoint; a control that may not be used is VISIBLE, DISABLED and
 * carries its reason (`BR-CWP-056` / `CR-068` R3). Dropping it from the phone
 * because the card is smaller would leave a customer who came looking for it
 * concluding the product cannot do it at all.
 *
 * ⚠ **ITS OWN `testId`s, NOT THE TABLE'S.** Both halves are in the DOM at once
 * (only CSS hides one), so re-using `method-remove` would make
 * `[data-testid='method-remove']` answer with whichever came first in the
 * markup — a test silently changing what it asserts.
 *
 * ⚠ **THE MUTED CLASS IS WRITTEN OUT IN BOTH BRANCHES, NEVER INTERPOLATED**
 * (B14 rule 21's per-file clause, `DEF-974`): Tailwind's scanner cannot see a
 * class it did not read literally, and a class the compiler never emitted
 * renders as nothing while every check on the class list passes.
 */
function MethodPhoneCard(props: { method: PortalPaymentMethod; onRemove: () => void }) {
  const { t } = useTranslation();
  const asDate = usePortalDate();
  const { method } = props;
  return (
    <div
      className={
        method.usable
          ? "border border-neutral-200 p-3"
          : "border border-neutral-200 p-3 text-neutral-600"
      }
      data-method-card={method.last_four}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <MethodCell method={method} />
        <StatusChip tone={TONE[method.status] ?? "neutral"} testKey={method.status}>
          {t(`portal.methods.status.${method.status}`)}
        </StatusChip>
      </div>
      {/* The kit's own label/value pair rather than a sentence built in this
          file — B14 rule 36, and it mints no key in eleven catalogues. */}
      <KVList
        rows={[
          {
            key: "used-for",
            label: t("portal.methods.colUsedFor"),
            value: method.used_for.map((use) => t(`portal.methods.use.${use}`)).join(" · "),
          },
          {
            key: "added",
            label: t("portal.methods.colAdded"),
            value: asDate(method.added_on),
          },
        ]}
      />
      <div className="mt-2">
        <RowActions>
          <RowAction
            testId="method-card-edit"
            label={t("portal.methods.edit")}
            icon={<PencilIcon />}
            reason={t("portal.methods.editHeld")}
            onClick={() => undefined}
          />
          <RowAction
            testId="method-card-remove"
            danger
            label={t("portal.methods.remove")}
            icon={<TrashIcon />}
            onClick={props.onRemove}
          />
        </RowActions>
      </div>
    </div>
  );
}

/** `Visa ••••8812` — what a person recognises, and the only digits there are. */
function methodLabel(method: PortalPaymentMethod): string {
  return `${method.brand} ••••${method.last_four}`;
}

/**
 * The `METHOD` cell — **two lines** (`CWP-039.png`, delta 39.3).
 *
 * **Chase ••••4021** over grey *Bank account*; **Visa ••••8812** over grey
 * *Card · expires 11/27*. The second line is the KIND, which is what tells a
 * customer whether the money leaves today or in three days — and `expires`
 * is null on a mandate, so a bank account says only what it is.
 */
function MethodCell(props: { method: PortalPaymentMethod }) {
  const { t } = useTranslation();
  const { method } = props;
  const kind = t(`portal.methods.kind.${method.kind}`, {
    defaultValue: t("portal.methods.kind.card"),
  });
  return (
    <span className="flex flex-col">
      <span className="font-semibold text-neutral-900" data-method-name="">
        {methodLabel(method)}
      </span>
      <span className="text-base text-neutral-600" data-method-kind="">
        {method.expires === null ? kind : t("portal.methods.kindExpires", {
          kind,
          expires: method.expires,
        })}
      </span>
    </span>
  );
}
