// ── Trace ──────────────────────────────────────────────
// Story:    US-CWP-026 (EP-CWP-06) — all my accounts: four balances, totalled,
//           never merged. Screen: CWP-023 (blueprint `P9`)
// Rules:    BR-CWP-013 (the set is FLAT — the master is one more row and there
//           is no `children` key to draw) · BR-CWP-014 (*Billed to you as
//           owner* is a BILLING fact, not a permission) · BR-CWP-015 (shown
//           separately, totalled for information, NEVER merged) · BR-CWP-016
//           (a landlord sees the accounts they hold and never a tenant's —
//           PO 2026-09-04, *"(a) no"*) · BR-CWP-047 (re-read, never cached) ·
//           CLAUDE.md hard rule 2 (4 dp stored, 2 dp displayed) · hard rule 8
//           (the address is walked to `premises`) · B14 rule 20 (ONE table
//           type) · rule 21 (Tailwind utilities; `portal/` is on
//           `route-b-migrated.txt`) · rule 31 (no database id on screen) ·
//           rule 32 (one sentence per section) · rule 35 (the catalogue writes
//           the words)
// Tests:    src/portal/accounts/MyAccounts.dom.test.tsx
// Impacts:  src/portal/api/portalClient.ts `getMyAccounts` ·
//           src/portal/routing/portalRoutes.tsx · screenIds.ts
// ───────────────────────────────────────────────────────
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import { PageHeader } from "@/components/PageHeader";

import {
  Card,
  ErrandLink,
  NamedGaps,
  StatusChip,
  usePortalPath,
} from "../components/primitives";
import { onDate } from "../components/content";
import { DollarIcon, EyeIcon } from "@/components/icons";
import { useCurrentAccount } from "../shell/currentAccount";
import { PortalListTable } from "../components/listTable";

import { formatMoney } from "../signin/Enrol";
import { getMyAccounts, type MyAccountRow, type MyAccounts } from "../api/portalClient";
import { usePortalListWindow } from "../components/listWindow";
import { ListPager } from "@/components/ListPager";
import type { PageSize } from "@/components/tableTypes";

/**
 * `CWP-023` — every account this login holds, on one screen, with a total.
 *
 * ⚠ **THE ROWS ARE THE PRODUCT AND THE TOTAL IS INFORMATION** (`BR-CWP-015`).
 * There is no control anywhere near the total and there must never be: each
 * account is billed on its own, and a single control beside `$872.82` would
 * promise a merged payment this product does not make.
 *
 * ⚠ **THE MASTER IS ONE MORE ROW** (`BR-CWP-013`). No nesting, no expander, no
 * `children`: what makes it different is the label *Billed to you as owner*,
 * which is a billing fact rather than a permission (`BR-CWP-014`).
 *
 * ⚠ **THE TENANTS' OWN ACCOUNTS ARE NOT HERE, AND NOT BECAUSE THIS SCREEN
 * FILTERS THEM OUT.** `OQ-1397` was ruled *no* on 2026-09-04: the server builds
 * every row from the session's account set, so there is nothing for a screen
 * state to widen. A filter that could show them would be the bug.
 */
export function MyAccountsView() {
  const { t, i18n } = useTranslation();
  //: The row actions below change WHICH account the shell is scoped to and then
  //: navigate — the same act as changing the switcher — so no account id ever
  //: reaches an address (B14 rule 31).
  const path = usePortalPath();
  const [, setCurrent] = useCurrentAccount();
  /**
   * ⚠ **ONE PAGE, AND THE SEARCH, THE CHIP AND THE SORT TRAVEL WITH IT**
   * (`DEF-CWP-5747`, `NFR-3`). A householder has one account and a landlord
   * has as many as they hold; this screen asked for all of them and searched,
   * chipped, sorted and sliced them in the browser. Moving only the page would
   * have been worse than leaving it — a landlord typing an address that is on
   * page 2 would be told they do not hold that property.
   *
   * ⚠ **`BR-CWP-016` IS NOT WEAKENED BY ANY OF THIS AND CANNOT BE.** Every row
   * is built from the session's own flat account set, re-derived on the read;
   * there is no query here for a page, a sort or a filter to widen, so a
   * landlord still has no path to a tenant's balance (`OQ-1397`, ruled **no**
   * on 2026-09-04).
   */
  const list = usePortalListWindow();
  const [data, setData] = useState<MyAccounts | null>(null);
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState(false);

  const { request } = list;
  useEffect(() => {
    let live = true;
    // The rows stay on screen while the next page is in flight — see
    // `Readings.tsx`'s note.
    setBusy(true);
    getMyAccounts(request)
      .then((answer) => {
        if (live) {
          setData(answer);
          setBusy(false);
        }
      })
      .catch(() => {
        if (live) {
          setFailed(true);
          setBusy(false);
        }
      });
    return () => {
      live = false;
    };
  }, [request]);


  // ⚠ **THE HEAD IS BUILT ONCE AND RENDERS ON EVERY BRANCH, LOADING INCLUDED**
  // (`DEF-CWP-4000`; audit D1, delta X4/X5). It composes the shared
  // `components/PageHeader.tsx` — the ONE page head B14 rule 2 names and the
  // one fifteen portal files already use — never a second one.
  //
  // ⚠ **`+ Add an account` MOVES UP; `Pay several` IS NOT DRAWN.** The drawing
  // gives this head two actions. The first has a built screen behind it
  // (`CWP-020` at `/accounts/add`) and is now where the drawing puts it. The
  // second has no address in the product at all, and a held button pointing at
  // nothing is the promise `DEF-CWP-3925` cost a week — so it is REPORTED, not
  // drawn.
  const head = (
    <PageHeader
      kicker={t("portal.kicker.accounts")}
      title={t("portal.accounts.title")}
      secondaryActions={<ErrandLink label={t("portal.addAccount.title")} to="/accounts/add" />}
    />
  );

  if (failed) {
    return (
      <div data-screen="CWP-023">
        {head}
        <Card testId="my-accounts">
          <p className="text-body text-neutral-600">{t("portal.accounts.couldNotRead")}</p>
        </Card>
      </div>
    );
  }
  if (!data) {
    return (
      <div data-screen="CWP-023">
        {head}
        <Card testId="my-accounts">
          <p className="text-body text-neutral-600">{t("portal.accounts.reading")}</p>
        </Card>
      </div>
    );
  }

  return (
    <div data-screen="CWP-023">
      {head}
      <Card testId="my-accounts">
        {/* B14 rule 32 — ONE sentence for this section, and it says the thing a
            landlord needs to know before reading the table: nothing here is
            combined. */}
        <p className="mt-1 text-body text-neutral-600">{t("portal.accounts.intro")}</p>

        {/* ⚠ **`account_count` IS THE WHOLE SET AND `count` IS WHAT THE
            SEARCH MATCHED** (`DEF-CWP-5747`). A landlord who typed an address
            they do not hold must read *none of your accounts says that*, not
            *you hold no accounts*. */}
        {data.account_count === 0 ? (
          // B14 rule 17 — an empty state that says what will fill it.
          <p className="mt-3 text-body text-neutral-600" data-accounts-empty="">
            {t("portal.accounts.none")}
          </p>
        ) : (
          <>
            {/* The total sits ABOVE the table, which is where CWP-023 draws it
                and where a landlord looks first. `show_total` is the SERVER's
                answer (US-CWP-026 TC-5) — deciding it here is how two screens
                come to disagree. */}
            {data.show_total && data.total_owing ? (
              <p
                className="mt-3 border-b-2 border-neutral-900 pb-2 text-body font-bold"
                data-accounts-total=""
              >
                {t("portal.accounts.totalOwing")}{" "}
                <span className="tabular-nums">
                  {formatMoney(data.total_owing, data.currency)}
                </span>
              </p>
            ) : null}

            {/* ⚠ **AT 390 THE TWO FACTS THIS SCREEN EXISTS TO ANSWER WERE OFF
                THE RIGHT-HAND EDGE** (`DEF-CWP-4905`). Measured in a browser on
                2026-09-11: the table's own content is **492px wide inside a
                350px column**, so `BALANCE` and `STATUS` sit past the edge
                behind a sideways scroll a customer has no reason to look for.
                `MiniTable`'s `overflow-x-auto` is correct and stops the PAGE
                moving — it does not make the figures readable, and the page
                body never scrolling sideways is exactly why every check passed
                over this. The drawing answers it the same way: its phone frame
                for screen 27 is a stack — address, account, money, status,
                action — and its desktop frame is the table.

                ⚠ **THE SAME PATTERN `Bills.tsx`, `Equipment.tsx` AND
                `Readings.tsx` ALREADY USE** (B14 rule 36 — build from the kit,
                and where the kit has no piece, follow the shape the product
                already agreed on). ⚠ **ONE SOURCE FOR BOTH:** each half
                renders `data.accounts`, so a fact cannot be true at 1280 and
                absent at 390.

                ⚠ **`hidden … max-md:flex`, NEVER `md:hidden`** — this theme is
                DESKTOP-FIRST and `G107` refuses the min-width form by name. The
                three sibling screens above write `md:hidden` and G107 has been
                RED on all four portal files since 2026-09-08 (`a2aa63cfb`,
                `e83971d55`); this lane did not cause that and did not join it. */}
            <div className="mt-3 hidden flex-col gap-3 max-md:flex" data-accounts-cards="">
              {data.accounts.map((row) => (
                <AccountCard key={row.id} row={row} onOpen={() => setCurrent(row.id)} />
              ))}
              {/* ⚠ **THE PHONE GETS A FOOTER TOO** (`DEF-CWP-5747`): the card
                  stack held every account and a landlord scrolled. It holds ONE
                  PAGE now, so without this the fifty-first property would be
                  unreachable on the device most customers open the portal on.
                  Same shared `ListPager`, same four keys (B14 rule 16). */}
              <ListPager
                total={data.count}
                page={data.page}
                per={data.per as PageSize}
                onPage={list.setPage}
                onPer={list.setPer}
              />
            </div>
            <div className="mt-3 max-md:hidden">
              <PortalListTable<MyAccountRow>
                screen="CWP-023"
                caption={t("portal.accounts.caption")}
                rows={data.accounts}
                rowKey={(row) => row.id}
                rowMuted={(row) => row.state === "clear"}
                empty={
                  <p className="mt-2 text-body text-neutral-600" data-accounts-empty="">
                    {t("portal.accounts.caption")}
                  </p>
                }
                /* ⚠ **THE SEARCH AND THE CHIP ARE THE SERVER'S NOW
                   (`DEF-CWP-5747`) AND MATCH WHAT THEY ALWAYS MATCHED.** The
                   address, the customer's own account number and the utility's
                   own words for the services — every one of them a value
                   already on the screen, and `row.id` is still not among them
                   (B14 rule 31: a database id is not a thing a person can
                   type). The service words are the TENANT'S data rather than a
                   catalogue's, so the server can match them itself — which is
                   why this screen needs no `resolve` and `CWP-027` does.

                   ⚠ **`All | Owing` KEEPS ITS CONDITION**: it appears only
                   where there is more than one ACCOUNT — `account_count`, the
                   whole set's, never this page's — because one account has
                   nothing to narrow.

                   ⚠ **THE DRAWING'S THIRD CHIP, `On a plan`, IS STILL NOT
                   BUILT AND IS STILL NOT FAKED.** `MyAccountRow` carries no
                   payment-plan field, so there is nothing to match on; a chip
                   that matched nothing would be a control that silently
                   empties the list. It needs a server change first. */
                server={list.window({
                  total: data.count,
                  page: data.page,
                  per: data.per as PageSize,
                  populated: data.account_count > 0,
                  busy,
                  search: { placeholder: t("portal.accounts.search") },
                  chips:
                    data.account_count > 1
                      ? {
                          name: "state",
                          label: t("portal.accounts.filterLabel"),
                          testId: "accounts-filter",
                          options: [
                            { key: "owing", label: t("portal.accounts.filterOwing") },
                          ],
                        }
                      : undefined,
                })}
                // ⚠ **NO ROW ICONS HERE, AND THE REASON IS STRUCTURAL RATHER
                // THAN AN OMISSION.** The drawing gives this list 👁 and 💳.
                // Every account-scoped screen in the portal — `/account`,
                // `/bills`, `/pay-now` — is addressed for whichever account the
                // shell's switcher currently holds, and that switcher is
                // in-memory state, not a URL segment. So a row icon would need
                // either an account-scoped address that does not exist, or the
                // account's database id in the URL, which B14 rule 31 forbids
                // by name. Two controls that went nowhere would be hard-won law
                // 2's mirror; this is stated instead.
                columns={[
                  {
                    key: "address",
                    label: t("portal.accounts.colAddress"),
                    sortable: true,
                    sortValue: (row) => row.service_address,
                    cell: (row) => <AddressCell row={row} />,
                  },
                  {
                    key: "services",
                    label: t("portal.accounts.colServices"),
                    cell: (row) => row.services.map((service) => service.name).join(" · "),
                  },
                  {
                    key: "due",
                    label: t("portal.accounts.colDue"),
                    sortable: true,
                    sortValue: (row) => row.due_on,
                    cell: (row) => (row.due_on ? onDate(row.due_on, i18n.language) : "—"),
                  },
                  {
                    key: "balance",
                    label: t("portal.accounts.colBalance"),
                    align: "right",
                    sortable: true,
                    sortValue: (row) => Number(row.owing ?? "0"),
                    cell: (row) => (
                      <span className="tabular-nums" data-owing={row.id}>
                        {formatMoney(row.owing ?? "0", row.currency)}
                      </span>
                    ),
                  },
                  {
                    key: "status",
                    label: t("portal.accounts.colStatus"),
                    cell: (row) => <StateChip row={row} />,
                  },
                  // ⚠ **THE ROW ACTIONS THE DRAWING ASKS FOR, AND THEY WERE NOT
                  // HERE AT ALL** (`DEF-CWP-4133`). The captured wireframe puts
                  // two icons on every row and its own caption insists on the
                  // shape — *"Note the row actions are icons, not links: view
                  // and pay, with anything rarer behind an overflow"* — and
                  // `08-screen-layouts.md` CWP-023 writes `icons`. The table
                  // ended at the status chip, so a landlord reading four
                  // balances had no way to open one from the screen that lists
                  // them. r10 rule 15 governs the shape: icons with tooltips,
                  // never text links, at most two visible.
                  //
                  // ⚠ **NEITHER ICON PUTS THE ACCOUNT ID IN AN ADDRESS**
                  // (B14 rule 31, and `portalRoutes.tsx` says the same thing in
                  // its own comment): they SET THE CURRENT ACCOUNT and then go
                  // to the screen, which is exactly what changing the switcher
                  // does. The destination is scoped by the session, never by a
                  // uuid somebody could edit in the bar.
                  {
                    key: "actions",
                    label: "",
                    cell: (row) => (
                      <span className="flex items-center justify-end gap-2">
                        {/* ⚠ **THE EYE WENT TO `/bills` AND THE DRAWING SENDS
                            IT TO THE PROPERTY'S OWN PAGE** (`DEF-CWP-4901`).
                            Screen 27 draws `→ Open` on the paid-up row and
                            says what Open means — *"Open being this property's
                            own page"*. `CWP-065` had **one** inbound link in
                            the whole portal (`MyDetails.tsx`), which is not
                            where a landlord looks for one of four properties;
                            `/bills` is still one press away on the frame's own
                            nav, so this trades a duplicate door for a missing
                            one. */}
                        <Link
                          to={path("/account")}
                          onClick={() => setCurrent(row.id)}
                          aria-label={t("portal.accounts.openAccount", {
                            label: row.service_address ?? row.account_no,
                          })}
                          title={t("portal.accounts.openAccount", {
                            label: row.service_address ?? row.account_no,
                          })}
                          data-account-open={row.id}
                        >
                          <EyeIcon />
                        </Link>
                        {/* ⚠ **THE PAY ICON IS DRAWN ONLY WHERE THERE IS
                            SOMETHING TO PAY.** A control offering to settle
                            `$0.00` is noise on the row that is already CLEAR,
                            and `BR-CWP-093` is the same instinct one level up:
                            nothing empty ever appears. It is an absence per
                            row, decided by the server's own figure, so it
                            cannot rot the way a hold does. */}
                        {Number(row.owing ?? "0") > 0 ? (
                          <Link
                            to={path("/pay-now")}
                            onClick={() => setCurrent(row.id)}
                            aria-label={t("portal.accounts.payAccount", {
                              label: row.service_address ?? row.account_no,
                            })}
                            title={t("portal.accounts.payAccount", {
                              label: row.service_address ?? row.account_no,
                            })}
                            data-account-pay={row.id}
                          >
                            <DollarIcon />
                          </Link>
                        ) : null}
                      </span>
                    ),
                  },
                ]}
              />
            </div>

          </>
        )}

        {/* Named gaps rather than a silently wrong total — the same list, from
            the same payload, as `CWP-022`'s, so it is the same component
            (B14 rule 36) and the sentence cannot differ between two screens
            showing one figure. `DEF-CWP-3926`. */}
        <NamedGaps problems={data.problems} mark="data-accounts-problems" />

        {/* ⚠ **`+ Add an account` WAS DRAWN ONCE AND BUILT TWICE, AND THE
            SECOND COPY IS GONE** (`DEF-CWP-4905`). Two lanes each added it
            citing a different drawing: the head action comes from
            `08-screen-layouts.md` CWP-023 (*actions `Button(outline)`
            + Add an account*) and this `WhereNext` came from the blueprint's
            screen 27, which puts `+ Add an account` under the list. Both are
            drawings, so *the frame wins* cannot settle it — B14 rule 37's own
            case — and what they AGREE on is that the control exists ONCE.
            The head keeps it, because `pageHeadCensus.test.ts` enforces the
            head action from `08-screen-layouts.md` and would go red without
            it; the blueprint's placement is recorded as a divergence rather
            than built a second time. ⚠ `DEF-CWP-3954` is what a doorless
            `CWP-020` cost and that door is still here — one of it. */}
      </Card>
    </div>
  );
}

/**
 * One account, on a phone — the drawing's own phone frame for screen 27.
 *
 * ⚠ **THE MONEY AND THE STATUS ARE THE LARGEST THINGS ON IT**, because they are
 * the two the screen exists to answer and they are the two the table pushed off
 * the edge. Both are LABELLED with the table's own column words, so the two
 * widths cannot say the same fact differently and a card with no column heads
 * still says what its figure is.
 *
 * ⚠ **THE ACTIONS CARRY THEIR WORDS HERE, AND THAT IS THE PORTAL'S OWN
 * STANDARD A** — *"In the portal every icon carries its word … Never an icon
 * alone. On a customer's phone there is no hover, so a tooltip is invisible."*
 * The table's row icons are icon-only (B14 rule 15, the staff shape) and they
 * keep a `title` a mouse can reach; a phone has no mouse, which is the whole of
 * the portal's reversal. Reversing it in the TABLE as well is a kit-wide change
 * to every portal list and is recorded rather than taken here.
 *
 * ⚠ **THE CARD MARKS ITS OWN CHIP.** Every account is drawn twice — once here
 * and once as a table row — and only one is ever visible, so two chips carrying
 * `data-chip="state-<id>"` would make every assertion written before today
 * ambiguous (the shape `Equipment.tsx` records).
 */
function AccountCard(props: { row: MyAccountRow; onOpen: () => void }) {
  const { t } = useTranslation();
  const path = usePortalPath();
  const { row } = props;
  const label = row.service_address ?? row.account_no;
  return (
    <div className="flex flex-col gap-2 border border-neutral-200 p-3" data-account-card={row.id}>
      <AddressCell row={row} />
      <div className="flex flex-wrap items-end justify-between gap-2">
        <span className="flex flex-col">
          <span className="text-table-header font-bold uppercase tracking-table-header text-neutral-600">
            {t("portal.accounts.colBalance")}
          </span>
          <span className="text-metric-sm font-bold tabular-nums" data-card-owing={row.id}>
            {formatMoney(row.owing ?? "0", row.currency)}
          </span>
        </span>
        <StateChip row={row} mark={`card-state-${row.id}`} />
      </div>
      {/* ⚠ **A `<Link>` AND NOT `ErrandLink`, FOR ONE REASON THAT IS NOT
          STYLE.** These two doors must SET THE CURRENT ACCOUNT before they
          navigate — the same act the switcher performs — because no
          account-scoped screen in this portal takes an id in its address
          (B14 rule 31, and `portalRoutes.tsx` says so in its own comment).
          `ErrandLink` takes `label`, `to`, `size` and `variant` and no
          `onClick`, so it cannot carry that; widening the kit for one caller
          is a change to every errand card in the product and is not this
          lane's to make. The class is the same text-door shape `Home.tsx`
          already uses for *All bills →*. */}
      <div className="flex flex-wrap items-center gap-3">
        <Link
          to={path("/account")}
          onClick={props.onOpen}
          className="text-base font-semibold text-accent-text"
          data-card-open={row.id}
        >
          {t("portal.accounts.openAccount", { label })}
        </Link>
        {Number(row.owing ?? "0") > 0 ? (
          <Link
            to={path("/pay-now")}
            onClick={props.onOpen}
            className="text-base font-semibold text-accent-text"
            data-card-pay={row.id}
          >
            {t("portal.accounts.payAccount", { label })}
          </Link>
        ) : null}
      </div>
    </div>
  );
}

/**
 * The address, and underneath it the one label that says who is billed.
 *
 * ⚠ **THE ADDRESS IS THE VISIBLE VALUE, NEVER THE ACCOUNT'S DATABASE ID**
 * (B14 rule 31). `account_no` is the customer's own reference off their bill
 * and is shown as a second line, because that is the number they will quote on
 * the telephone.
 */
function AddressCell(props: { row: MyAccountRow }) {
  const { t } = useTranslation();
  const { row } = props;
  const billedTo =
    row.billed_to === "owner"
      ? t("portal.accounts.billedToOwner")
      : t("portal.accounts.billedToTenant");
  return (
    <span className="flex flex-col">
      <span className="font-semibold">{row.service_address ?? row.account_no}</span>
      <span className="text-base text-neutral-600">
        {/* ⚠ **THE NUMBER WAS MISSING AND THE DOCSTRING ABOVE SAID IT WAS
            HERE** — hard-won law 1, in the same file as the claim. This cell
            drew the address and *Tenant billed*, and `account_no` appeared
            only as a FALLBACK for an address that is null and in the search
            match; a landlord about to telephone about one of four properties
            could not read the number off the screen that lists them. The
            captured wireframe gives it a column of its own; a second line
            under the address is the same fact in the width a phone has, which
            is also how the wireframe draws it at 390. */}
        {row.service_address ? (
          <>
            <span data-account-no={row.id}>{row.account_no}</span>
            {" · "}
          </>
        ) : null}
        <span data-billed-to={row.billed_to}>{billedTo}</span>
      </span>
    </span>
  );
}

/** `clear · due · overdue` as a chip, worded here because the language is
 *  known here (B14 rule 35) and the day count is a NUMBER on the wire. */
function StateChip(props: { row: MyAccountRow; mark?: string }) {
  const { t, i18n } = useTranslation();
  const { row } = props;
  //: ⚠ **THE CARD PASSES ITS OWN HANDLE.** Every account is drawn twice — once
  //: as a card and once as a table row — and only one is visible at a time, so
  //: two chips carrying `data-chip="state-<id>"` would make every assertion
  //: written before today ambiguous. Default unchanged, so the table does not
  //: move (`Equipment.tsx` records the same shape).
  const mark = props.mark ?? `state-${row.id}`;
  if (row.state === "clear") {
    return (
      <StatusChip tone="neutral" testKey={mark}>
        {t("portal.accounts.stateClear")}
      </StatusChip>
    );
  }
  if (row.state === "overdue") {
    return (
      <StatusChip tone="danger" testKey={mark}>
        {t("portal.accounts.stateOverdue", { count: row.days_overdue ?? 0 })}
      </StatusChip>
    );
  }
  return (
    <StatusChip tone="warning" testKey={mark}>
      {t("portal.accounts.stateDue", { date: onDate(row.due_on, i18n.language) })}
    </StatusChip>
  );
}
