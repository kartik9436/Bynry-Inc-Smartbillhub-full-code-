// ── Trace ──────────────────────────────────────────────
// Story:    US-CWP-031 (EP-CWP-06) — your account: the deposit we hold, the
//           exemption that lapses, the history. Screen: CWP-065
// Rules:    BR-CWP-049 (the deposit is shown WHILE it is held) · BR-CWP-053
//           (the exemption shows its expiry and that a reminder comes) ·
//           BR-CWP-052 (⚠ the credit tier is held back — this screen has no
//           field for it) · B14 rule 17 (an absence is a sentence, or nothing
//           at all — never a `$0.00`) · rule 21 (`portal/` is on
//           route-b-migrated.txt) · rule 32 (one sentence per section) ·
//           rule 35 (the catalogue writes the words) · hard rule 2 (2 dp shown)
// Tests:    src/portal/accounts/YourAccount.dom.test.tsx
// Impacts:  src/portal/api/portalClient.ts `getAccountSummary`
// ───────────────────────────────────────────────────────
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import {
  Card,
  HeldButton,
  KpiRow,
  KpiTile,
  KVList,
  SectionTitle,
  StatusChip,
  TwoCol,
  usePortalPath,
  WhereNext,
} from "../components/primitives";
import { onDate } from "../components/content";
import { PageHeader } from "@/components/PageHeader";
import { Panel } from "@/components/Panel";
import { formatMoney } from "../signin/Enrol";
import { PortalScreen, PortalState } from "../components/states";
import { TemporaryStopCard } from "./TemporaryStopCard";
import {
  getAccountBalance,
  getAccountSummary,
  type AccountBalance,
  type AccountSummary,
} from "../api/portalClient";

/**
 * `CWP-065` — four panels of facts that never appear on a bill.
 *
 * ⚠ **THE DEPOSIT PANEL IS THE ONE THAT STINGS.** `$150.00` of the customer's
 * money, taken in 2021, visible on the day it was quoted and on the day it
 * comes back and invisible for the five years between. It says three things in
 * order: how much and since when, that it returns at closing with interest,
 * and — the sentence that stops a phone call — **that it is not money off a
 * bill**. A customer who reads a held deposit as credit stops paying, and then
 * owes the utility money and still has the deposit.
 *
 * ⚠ **AND WHEN THERE IS NO DEPOSIT THERE IS NO PANEL**, not a `$0.00`: a zero
 * reads as *we took nothing from you*, which is a different claim from *there
 * is nothing here* (`US-CWP-031` TC-8).
 *
 * ⚠ **AN INTEREST FIGURE THE ENGINE CANNOT COMPUTE IS SAID IN WORDS, NEVER
 * SHOWN AS ZERO.** The signed accrual answers `null` when it cannot compute,
 * and the settlement that actually pays this money out fails closed on the
 * same value rather than paying principal alone. A `$0.00` here would be a
 * figure disagreeing with the customer's own final bill.
 */
export function YourAccountView(props: { accountId: string }) {
  const { t, i18n } = useTranslation();
  const path = usePortalPath();
  const [data, setData] = useState<AccountSummary | null>(null);
  const [failed, setFailed] = useState(false);
  /** ⚠ **THE MONEY IS A SECOND READ AND IT MUST NOT BLOCK THE PAGE.** This
   *  screen is *everything about one property*; the summary answers the
   *  services, the plan and the deposit, and the BALANCE lives in `payments`
   *  because that is the module that owns what is owed (`BR-CWP-047` — never
   *  cached, on either read). A failure here leaves the strip absent and the
   *  rest of the screen intact, which is the opposite of what one combined
   *  read would do. */
  const [balance, setBalance] = useState<AccountBalance | null>(null);

  useEffect(() => {
    let live = true;
    getAccountSummary(props.accountId)
      .then((answer) => {
        if (live) setData(answer);
      })
      .catch(() => {
        if (live) setFailed(true);
      });
    getAccountBalance(props.accountId)
      .then((answer) => {
        if (live) setBalance(answer);
      })
      .catch(() => {
        //: An absent strip, never a `$0.00` — a zero here reads as *you owe us
        //: nothing*, which is a different claim from *we could not look*
        //: (`BR-CWP-093`, and `US-CWP-031` TC-8 makes the same call about the
        //: deposit one panel down).
        if (live) setBalance(null);
      });
    return () => {
      live = false;
    };
  }, [props.accountId]);

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
      kicker={t("portal.kicker.myDetails")}
      title={t("portal.yourAccount.title")}
      // ⚠ **THE SCREEN ABOUT ONE PROPERTY HAD NO WAY BACK TO THE LIST OF THEM**
      // (`DEF-CWP-4910`). The blueprint draws `← Accounts` on this screen at
      // BOTH widths, and B14's own back-link rule (appendix `R-15`) puts it
      // under the bar rather than inside it — which is where `PageHeader` puts
      // it and where `/accounts/add` and `/my-details/preferences` already
      // draw theirs. This screen drew none at all.
      //
      // ⚠ **IT IS THE PARENT, NOT THE HISTORY.** A customer can now reach here
      // from three places (Home's account card, the accounts table's row, and
      // `My details`), and a back-link that guessed which would be wrong two
      // times in three. `portal.accounts.title` is the same word
      // `/accounts/add` already goes back with, so the two cannot drift.
      backTo={{ to: path("/accounts"), label: t("portal.accounts.title"), testId: "account-back" }}
    />
  );

  if (failed) {
    return (
      <PortalScreen screen="CWP-065" head={head}>
        <PortalState
          kind="failed"
          testId="your-account"
          sentence={t("portal.yourAccount.couldNotRead")}
        />
      </PortalScreen>
    );
  }
  if (!data) {
    return (
      <PortalScreen screen="CWP-065" head={head}>
        <PortalState kind="loading" testId="your-account" sentence={t("portal.yourAccount.reading")} />
      </PortalScreen>
    );
  }

  return (
    <div data-screen="CWP-065">
      {/* ⚠ **AND IT HAD NO HEADING EITHER, UNTIL 2026-09-06 (`DEF-CWP-4135`).**
          `08-screen-layouts.md` opens `CWP-065` `PageHead` kicker **MY
          DETAILS** · title *Your account* · subtitle, and the wireframe draws
          all three with the sentence beneath. The screen emitted no `<h1>`
          anywhere, so somebody arriving from the account switcher met **YOUR
          SERVICES** with nothing above it and no statement of what they were
          looking at. `DEF-CWP-4000` measured this across the portal and left
          three screens open, naming this one — its `pageHeadCensus.test.ts`
          asserted the absence IN THE NEGATIVE, which is why adding the head
          here also moves the entry there, in this same commit. */}
      {/* ⚠ **KICKER AND TITLE, AND DELIBERATELY NO SUBTITLE YET.** The drawing
          adds *The facts about this account that are not on a bill.* and no
          catalogue holds that sentence. Minting it means writing it NATIVELY in
          all eleven — B14 rule 35, and `DEF-SHL-4013` is what a machine
          translation costs when somebody who reads the language sees it. The
          defect filed here is that the screen had NO HEADING AT ALL; that is
          closed. The missing sentence is recorded on the row rather than
          guessed at in ten languages. */}
      {head}
      {/* ⚠ **THE SCREEN ABOUT ONE PROPERTY DID NOT SAY WHAT THAT PROPERTY
          OWED.** The captured wireframe puts *Amount due · $191.00 · Due Aug
          22* on this page, second only to the address, because a landlord opens
          it holding exactly that question about exactly this account — and the
          screen answered the plan, the services and the deposit and never the
          money. A customer had to change the switcher and go back to Home to
          find out.

          ⚠ **THE KIT'S OWN BALANCE STRIP, NOT A FOURTH MONEY CARD** (B14 rule
          36). `KpiRow`/`KpiTile lead` is what `CWP-022` and `CWP-033` already
          draw a figure with; a `Panel` with a big number in it here would be a
          second visual decision about what money looks like.

          ⚠ **ABSENT WHEN THE READ FAILS, NEVER `$0.00`** — a zero says *you owe
          us nothing*, which is a different claim from *we could not look*. */}
      {balance ? (
        <div className="mb-4">
          <KpiRow columns={3}>
            <KpiTile
              lead
              testKey="account-balance"
              label={t("portal.home.whatYouOwe")}
              value={
                <span data-account-owing="">
                  {formatMoney(balance.owing, balance.currency)}
                </span>
              }
              sub={
                balance.due_on ? (
                  <span data-account-due="">
                    {t("portal.home.due", { date: onDate(balance.due_on, i18n.language) })}
                  </span>
                ) : null
              }
            />
          </KpiRow>
        </div>
      ) : null}
      {/* ⚠ **THIS SCREEN HAD NO RIGHT-HAND COLUMN AT ALL** — `DEF-CWP-3984`,
          audit row D9. It composed `Card`, `KVList` and `SectionTitle` and
          nothing else, so the tax panel, the *send a new certificate* button
          and *when this account opened* had nowhere to be, and the drawing's
          two columns were four cards down one. `08-screen-layouts.md`
          `CWP-065` splits them: the deposit, the services and how you are
          billed on the left; tax and the account's own dates on the right. */}
      <TwoCol
        main={
          <>
      {/* CR-183-BRC10 T8 — a temporary stop, and *Restart my service now*. */}
      <TemporaryStopCard accountId={props.accountId} />
      {data.deposit ? (
        <Card testId="your-account-deposit">
          <SectionTitle>{t("portal.yourAccount.depositTitle")}</SectionTitle>
          <p className="mt-2 text-body font-bold" data-deposit-held="">
            {t("portal.yourAccount.depositHeld", {
              amount: formatMoney(data.deposit.held, data.deposit.currency),
              date: onDate(data.deposit.taken_on, i18n.language),
            })}
          </p>
          <p className="mt-1 text-body text-neutral-600" data-deposit-interest="">
            {data.deposit.interest === null
              ? t("portal.yourAccount.depositInterestUnknown")
              : t("portal.yourAccount.depositInterest", {
                  amount: formatMoney(data.deposit.interest, data.deposit.currency),
                })}
          </p>
          <p className="mt-2 text-body text-neutral-600">
            {t("portal.yourAccount.depositReturns")}
          </p>
          {/* ⚠ NOT decoration and not a nicety — see the component docstring. */}
          <p className="mt-1 text-body font-semibold" data-deposit-not-credit="">
            {t("portal.yourAccount.depositNotCredit")}
          </p>
        </Card>
      ) : null}

      {data.services.length > 0 ? (
        <Card testId="your-account-services">
          <SectionTitle>{t("portal.yourAccount.servicesTitle")}</SectionTitle>
          <div className="mt-2">
            <KVList
              rows={data.services.map((service) => ({
                key: service.code,
                label: service.name,
                value: service.since
                  ? t("portal.yourAccount.since", { date: onDate(service.since, i18n.language) })
                  : "—",
              }))}
            />
          </div>
        </Card>
      ) : null}

      <Card testId="your-account-billing">
        <SectionTitle>{t("portal.yourAccount.billingTitle")}</SectionTitle>
        {data.billing.current ? (
          <p className="mt-2 text-body" data-plan-current="">
            {t("portal.yourAccount.planSince", {
              plan: data.billing.current.name,
              date: onDate(data.billing.current.since, i18n.language),
            })}
          </p>
        ) : (
          <p className="mt-2 text-body text-neutral-600">{t("portal.yourAccount.noPlan")}</p>
        )}
        {data.billing.before.length > 0 ? (
          <ul className="mt-1 flex flex-col" data-plan-before="">
            {data.billing.before.map((row) => (
              <li key={`${row.name}-${row.from}`} className="text-base text-neutral-600">
                {t("portal.yourAccount.planBefore", { plan: row.name })}
              </li>
            ))}
          </ul>
        ) : null}
        {/* ⚠ **`CWP-032` HAD NO DOOR ANYWHERE IN THE PRODUCT**
            (`DEF-CWP-3954`). `screenIds.ts` records why it sits at
            `/final-bill` rather than under `/bills/:number` — *"a customer
            reaches their final bill from a move-out letter and from the
            account"* — and this IS the account. It is in the panel about HOW
            YOU ARE BILLED, which is always drawn, rather than in a card of its
            own: the deposit and the tax panels are both absent on most
            accounts, and a door that comes and goes is a door nobody learns.
            It shows whether or not the service has ended — `CWP-032` answers
            *"When your service ends, your last bill will be here."* */}
        {/* ⚠ **`/stop-or-restart` HAD NO DOOR ANYWHERE IN THE PORTAL** until
            2026-09-08 (`DEF-CWP-4654`, `CR-085`). It was routed, rendered and
            tested, and every test passed, because a screen is tested at its own
            address — the one place a door is not needed. A customer could not
            stop service at all, which is one of the commonest reasons anybody
            opens a utility portal. It goes HERE first because this screen is
            one property, and stopping service is something you do to one
            property rather than to an account list. */}
        <WhereNext
          mark="your-account"
          doors={[
            { key: "final-bill", label: t("portal.finalBill.title"), to: "/final-bill" },
            { key: "stop-or-restart", label: t("portal.stopRestart.title"), to: "/stop-or-restart" },
          ]}
        />
      </Card>

          </>
        }
        rail={
          <>
            {/* ⚠ **ABSENT, NEVER AN EMPTY PANEL** (`BR-CWP-093`): most accounts
                hold no exemption, and a *Tax exempt* panel saying *not exempt*
                is a fact nobody asked for. */}
            {data.tax_exemption ? (
              <Panel
                as="aside"
                title={t("portal.yourAccount.taxTitle")}
                data-testid="your-account-tax"
                trailing={
                  <StatusChip tone="neutral" testKey="tax-exempt">
                    {t("portal.yourAccount.taxExempt")}
                  </StatusChip>
                }
              >
                <div data-tax-until="">
                  <KVList
                    rows={[
                      /* ⚠ `DEF-CWP-9795` — A PER-TAX CERTIFICATE IS DRAWN AS
                         THE LAYOUT'S *From / Runs out* PAIR, ONE PAIR PER TAX.
                         Ruling (A) (2026-10-05) leaves the blanket flag false
                         for a certificate, so the church exempt from the City's
                         tax had no panel at all. The blanket exemption keeps
                         its one *Runs out* row: it covers every tax. */
                      ...((data.tax_exemption.taxes ?? []).length > 0
                        ? (data.tax_exemption.taxes ?? []).flatMap((row, index) => [
                            {
                              key: `from-${index}`,
                              label: t("portal.yourAccount.taxFrom"),
                              value: row.tax,
                            },
                            {
                              key: index === 0 ? "runs-out" : `runs-out-${index}`,
                              label: t("portal.yourAccount.taxRunsOut"),
                              value: onDate(row.until, i18n.language) || "—",
                            },
                          ])
                        : [
                            {
                              key: "runs-out",
                              label: t("portal.yourAccount.taxRunsOut"),
                              value: onDate(data.tax_exemption.until, i18n.language) || "—",
                            },
                          ]),
                      ...(data.tax_exemption.certificate_on_file
                        ? [
                            {
                              key: "on-file",
                              label: t("portal.yourAccount.taxOnFile"),
                              value: t("portal.yourAccount.taxOnFileYes"),
                            },
                          ]
                        : []),
                    ]}
                  />
                </div>
                {/* `BR-CWP-053` — an exemption that lapses silently becomes a
                    bigger bill and a complaint, so the screen promises the
                    reminder. */}
                <p className="mt-2 text-base text-neutral-600" data-tax-reminder="">
                  {t("portal.yourAccount.taxReminder")}
                </p>
                {/* ⚠ **HELD, AND ITS REASON IS A RULING RATHER THAN A MISSING
                    SCREEN — WHICH IS THE KIND OF HOLD THAT CANNOT ROT**
                    (`DEF-CWP-3925`'s own finding: a hold waiting on a screen
                    has a clock in it; one answered by a standing decision does
                    not). `US-CWP-064` carries a SIGNED deferral of consumer
                    upload — `08-screen-layouts.md`'s own divergence table says
                    of `CWP-049`: *"consumer upload is a signed deferral — a
                    sentence; no file input"* — so this button has nowhere to
                    send a file even after `CWP-049` lands. It is drawn because
                    the drawing draws it and because a customer looking for the
                    way to renew should find the answer here rather than
                    nowhere. `YourAccount.dom.test.tsx` carries the case that
                    fires if that deferral is ever lifted. */}
                <HeldButton
                  label={t("portal.yourAccount.sendCertificate")}
                  reason={t("portal.yourAccount.sendCertificateHeld")}
                />
              </Panel>
            ) : null}

            {/* ⚠ **THE *GO TO* LIST THE DRAWING PUTS ON THIS PAGE, AND THE
                REASON IT MATTERS IS NAVIGATION RATHER THAN DECORATION.** The
                wireframe's rail is *Bills · Usage · Equipment · Requests ·
                Documents*, and this screen is where somebody holding several
                properties arrives to answer a question about ONE of them:
                every one of those five is then the next thing they want, for
                THIS account, which the switcher has already scoped. The page
                offered two doors — the final bill and stopping service — both
                of them ends rather than errands.

                ⚠ **NO COUNTS, BECAUSE NONE ARE SERVED.** The drawing writes
                *Bills · 3*, *Equipment · 3 items*, *Requests · 1 open*.
                `AccountSummary` carries no count of anything and inventing a
                plausible one in front of a customer is the failure this
                product keeps paying for. The doors go where they say; the
                numbers are recorded as missing rather than guessed
                (`DEF-CWP-3767`'s shape, five fields over). */}
            <Panel
              as="aside"
              /* ⚠ **AN EXISTING CATALOGUE KEY** — *Things you can do here*, in all
                 eleven languages, is what the nav already calls a list of
                 places to go. A new `portal.yourAccount.goTo` would have been
                 either eleven machine translations or English on nine screens
                 (B14 rule 35; `G27` refuses the debt). */
              title={t("portal.nav.label")}
              data-testid="your-account-go-to"
            >
              <WhereNext
                mark="your-account-go-to"
                doors={[
                  { key: "bills", label: t("portal.tab.bills"), to: "/bills" },
                  { key: "usage", label: t("portal.tab.usage"), to: "/usage" },
                  // DEF-CWP-10567: one name per function — the door Usage uses (PO/QA 2026-10-23).
                  { key: "equipment", label: t("portal.usage.seeEquipment"), to: "/equipment" },
                  { key: "requests", label: t("portal.tab.requests"), to: "/requests" },
                  { key: "documents", label: t("portal.documents.title"), to: "/documents" },
                  // `DEF-CWP-9131` — `CWP-078`, the property statement, had NO
                  // door anywhere from the day it landed (2026-09-27) until
                  // 2026-10-02. It is about the account this page is on — the
                  // server walks THIS account to its property — so this is
                  // where a landlord looks for it, and the statement's back
                  // link returns here. The label is the screen's own existing
                  // word (*This property*), already in all eleven catalogues.
                  { key: "property", label: t("portal.property.unnamed"), to: "/property" },
                ]}
              />
            </Panel>

            {/* The account's own dates. ⚠ *Transferred from* is on the drawing
                and is NOT served — `AccountSummary` has no such field, and a
                transfer is not modelled as a link between accounts. An absent
                row is dropped rather than dashed; inventing the sentence would
                be a claim the product cannot check (`DEF-CWP-3767`'s shape,
                one field over). */}
            {data.opened_on ? (
              <Panel
                as="aside"
                title={t("portal.yourAccount.thisAccountTitle")}
                data-testid="your-account-this"
              >
                <div data-opened-on="">
                  <KVList
                    rows={[
                      {
                        key: "opened",
                        label: t("portal.yourAccount.openedLabel"),
                        value: onDate(data.opened_on, i18n.language),
                      },
                    ]}
                  />
                </div>
              </Panel>
            ) : null}
          </>
        }
      />
    </div>
  );
}
