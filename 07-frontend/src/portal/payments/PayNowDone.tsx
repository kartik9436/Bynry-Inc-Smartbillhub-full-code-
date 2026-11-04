// ── Trace ──────────────────────────────────────────────
// Story:    US-CWP-045 (EP-CWP-09). Screen: CWP-077 — blueprint 37 *Payment
//           made* (p67), at `/{tenant}/portal/pay-now/done`
// Change:   CR-085 step 2 lane 6. PO 2026-09-11: *"it should be 3 screens -
//           confirmed"*, then *"ii). Your ruling was about the shape, not the
//           addresses."* ⚠ The guest receipt stays at `/pay/done`; this is the
//           SIGNED-IN one and the two addresses are deliberately crossed
//           against the drawing. Ruled — do not "correct" it.
// Rules:    R-10 (bad news carries its way out) · R-22 (three states, three
//           SENTENCES) · BR-CWP-047 (nothing here is cached) · B14 rule 2 (one
//           page head) · rule 20 (ONE table type) · rule 21 · rule 31 (the
//           `PMT-` number a customer reads out, never a row id) · rule 32 ·
//           rule 35 · rule 36 (compose the kit) · CLAUDE.md hard rule 2 (2 dp)
//           · hard rule 4 (a payment is never edited — this is a receipt, not a
//           form)
// Tests:    src/portal/payments/PayNowDone.dom.test.tsx
// Impacts:  src/portal/payments/PayNowCheck.tsx (the screen that reaches it)
// ───────────────────────────────────────────────────────
import { useTranslation } from "react-i18next";
import { useLocation } from "react-router-dom";

import type { ApiClient } from "@/api/client";
import { PageHeader } from "@/components/PageHeader";
import { Panel } from "@/components/Panel";

import {
  ButtonRow,
  Card,
  ErrandLink,
  KVList,
  MiniTable,
  StatusChip,
  Stepper,
  TotalRow,
  TwoCol,
  usePortalPath,
} from "../components/primitives";
import { PortalScreen, PortalState } from "../components/states";
import { formatMoney } from "../signin/Enrol";
import { PayNowShell, balanceAfterFrom, paidResultFrom } from "./payNowFlow";

/**
 * `CWP-077` — **a receipt somebody can screenshot.**
 *
 * ⚠ **THIS SCREEN CANNOT SAY A PAYMENT HAPPENED UNLESS ONE DID, AND THAT IS
 * ENFORCED BY ITS PARSER RATHER THAN BY CARE.** The ruling that split this
 * journey named the trap in the same breath: `/pay`'s route comment records
 * that *the lookup ships and the payment does not — no gateway exists, so the
 * Pay control renders disabled carrying its reason*, and **a screen called
 * *Payment made* must not imply money moved on a tenant with no gateway.**
 * `paidResultFrom` therefore reads a result whose `outcome` is anything but
 * `paid` as NO RESULT AT ALL, and this screen draws its wrong-turn card. Every
 * other outcome stays on `CWP-076` where the way out is (R-10), so the only
 * door into this address is a commit the server answered `paid`.
 *
 * ⚠ **AND WHEN THE UTILITY IS STILL TESTING, THE RECEIPT SAYS SO.** A sandbox
 * tenant CAN answer `paid` — nothing real was debited. The customer is entitled
 * to know that before they file the reference away (PO ruling 2026-09-05 §3),
 * so the `TESTING` panel the pay screens carry is carried here too.
 *
 * ⚠ **`WHERE YOU STAND` IS THE SERVER'S FIGURE, NOT A SUBTRACTION.** Blueprint
 * 37's own note is that *"the balance AFTER the payment is on the confirmation —
 * a customer who was behind should not have to navigate anywhere to learn
 * whether they still are"*. The commit's own body has no balance on it; what
 * this screen shows is `remaining_balance` off the preview that priced **this
 * payment**, carried through the commit that succeeded, and it is labelled as
 * exactly that — *Balance after this payment*. Nothing here computes it.
 *
 * ⚠ **THE DISCONNECTION PANEL IS ABSENT AND IT IS RECORDED, NOT FORGOTTEN.**
 * Blueprint 37 calls *"does this clear my shut-off notice"* the question the
 * customer came in with, and answers it in its own green/amber panel. No field
 * on `PortalPayResult` says whether a notice existed or whether this cleared
 * it, and a sentence about somebody's supply is the last place to guess
 * (R-23's shape). It needs a served fact; until then `/overdue` is where that
 * question is answered and this screen does not pretend otherwise.
 *
 * ⚠ **THERE IS NO HELD `Download receipt` OR `Email it to me`, DELIBERATELY.**
 * The drawing puts both on this screen. A held control over a screen that
 * exists is the `DEF-CWP-3925` shape, and a hold with no expiry test is a
 * promise nobody is keeping (hard-won law 2's mirror) — this product has paid
 * for eight of those. `/payments` carries a LIVE receipt icon on every row
 * whose document was kept, so the honest control is the door to it.
 */
export function PayNowDoneView() {
  const { t } = useTranslation();
  const path = usePortalPath();
  const location = useLocation();
  const result = paidResultFrom(location.state);
  const balanceAfter = balanceAfterFrom(location.state);

  const head = (
    <PageHeader
      kicker={t("portal.money.kicker")}
      title={result === null ? t("portal.payNowDone.noReceiptTitle") : t("portal.payNowDone.title")}
    />
  );

  const steps = (
    <Stepper
      steps={[
        t("portal.payNow.step.choose"),
        t("portal.payNow.step.check"),
        t("portal.payNow.step.done"),
      ]}
      current={3}
    />
  );

  // ⚠ **A RELOAD IS A WRONG TURN, NOT AN ERROR.** This address carries nothing
  // — the receipt travels in router state — so a refreshed tab, a bookmark or a
  // kept link has nothing to draw. One sentence saying so, and two LIVE doors
  // by address: the payments list, where the receipt actually lives, and the
  // pay screen. R-22: this is EMPTY, not FAILED, and its sentence says which.
  if (result === null) {
    return (
      <PortalScreen screen="CWP-077" head={head}>
        {steps}
        <PortalState
          kind="empty"
          testId="pay-now-no-receipt"
          sentence={t("portal.payNowDone.noReceiptBody")}
          waysOut={[
            {
              label: t("portal.money.title"),
              to: path("/payments"),
              tone: "primary",
              testKey: "payments",
            },
            { label: t("portal.payNow.title"), to: path("/pay-now"), testKey: "pay-now" },
          ]}
        />
      </PortalScreen>
    );
  }

  return (
    <div data-screen="CWP-077">
      {/* ⚠ **THE SCREEN ID IS A LITERAL HERE AND MUST STAY ONE.**
          `PortalScreen` renders an identical DOM from its `screen` PROP, and two
          source scanners find a portal screen by the exact string
          `data-screen="CWP-…"` — `pageHeadCensus.test.ts`'s `screenFiles()`
          (`/data-screen="(CWP-\d+)"/g`) and `g100_every_screen_has_a_door.py`'s
          `SCREEN_MARK`. Neither reads a prop. This screen was BORN on
          `PortalScreen` for every branch, so it was invisible to both from its
          first commit and the census reported green over a scope that silently
          excluded it — hard-won law 7's *reporting zero over a scope it
          excludes*. `bills/BillDetail.tsx` and `payments/Fees.tsx` keep the
          literal on their populated branch for exactly this reason; `CR-085`
          step 2 lane 7 restored it on ten more. Do not tidy it back. */}
      {head}
      {steps}
      <TwoCol
        main={
          <Card testId="pay-now-done">
            <StatusChip tone="success" testKey="outcome-paid">
              {t("portal.payNow.outcome.paid")}
            </StatusChip>
            <p className="text-body text-neutral-800" data-outcome-said="">
              {t("portal.payNow.done.paid")}
            </p>
            <KVList
              rows={[
                {
                  key: "reference",
                  label: t("portal.payNow.doneReference"),
                  // B14 rule 31 — the PMT- number, which is what a customer
                  // would read out on the telephone. Never a row id.
                  value: <span data-payment-no="">{result.payment_no}</span>,
                },
                {
                  key: "amount",
                  label: t("portal.payNow.doneAmount"),
                  value: (
                    <span className="tabular-nums" data-paid-amount={result.amount}>
                      {formatMoney(result.amount, result.currency)}
                    </span>
                  ),
                },
              ]}
            />
            {result.lands_on.length > 0 ? (
              <MiniTable
                caption={t("portal.payNow.panelCaption")}
                columns={[
                  { key: "bill", label: t("portal.payNow.colBill") },
                  { key: "paying", label: t("portal.payNow.colPaying"), align: "right" as const },
                  { key: "after", label: t("portal.payNow.colAfter"), align: "right" as const },
                ]}
                rows={result.lands_on.map((row, index) => ({
                  key: row.number,
                  cells: {
                    bill: <span data-done-bill={index}>{row.number}</span>,
                    paying: (
                      <span className="tabular-nums">
                        {formatMoney(row.paying, result.currency)}
                      </span>
                    ),
                    after: (
                      <span className="tabular-nums" data-done-after={index}>
                        {formatMoney(row.owing_after, result.currency)}
                      </span>
                    ),
                  },
                }))}
              />
            ) : null}
            <ButtonRow>
              {/* ⚠ **A REAL DESTINATION, ASSERTED BY ADDRESS IN THE DOM TEST**
                  (`DEF-CWP-3925`). `CWP-041` is live and has been since release
                  2, so this is a LINK and not a held control. */}
              <ErrandLink label={t("portal.payNow.seeItOnYourList")} to="/payments" />
            </ButtonRow>
          </Card>
        }
        rail={
          <>
            <Panel as="aside" title={t("portal.payNowDone.whereYouStandHeading")}>
              {balanceAfter === null ? (
                // B14 rule 17 / R-23 — a figure we did not derive is an absence
                // with a sentence, never an em dash a customer reads as zero.
                <p className="text-body text-neutral-600" data-no-balance="">
                  {t("portal.payNowDone.balanceUnknown")}
                </p>
              ) : (
                <TotalRow
                  label={t("portal.payNowDone.balanceAfter")}
                  value={
                    <span data-balance-after={balanceAfter}>
                      {formatMoney(balanceAfter, result.currency)}
                    </span>
                  }
                  testKey="balance-after"
                />
              )}
              <p className="mt-2 text-base text-neutral-600" data-receipt-note="">
                {t("portal.payNowDone.copyInPayments")}
              </p>
            </Panel>
            {/* ⚠ **A SANDBOX TENANT ANSWERS `paid` AND NO REAL MONEY MOVED.**
                Saying so on the receipt is the whole of the trap the split
                ruling named. */}
            {result.environment === "sandbox" ? (
              <Panel as="aside" tone="warning" title={t("portal.payNow.testingTitle")}>
                <p className="text-body text-neutral-700" data-sandbox="">
                  {t("portal.payNow.testing")}
                </p>
              </Panel>
            ) : null}
          </>
        }
      />
    </div>
  );
}

/**
 * `CWP-077` inside the signed-in shell.
 *
 * ⚠ **NO ACCOUNT ID AND NO PAYMENT NUMBER IN THE ADDRESS** (B14 rule 31). The
 * receipt travels in router state, which is why a reload draws the wrong-turn
 * card rather than somebody else's payment.
 */
export function PayNowDonePage(props: { client?: ApiClient }) {
  return <PayNowShell client={props.client}>{() => <PayNowDoneView />}</PayNowShell>;
}
