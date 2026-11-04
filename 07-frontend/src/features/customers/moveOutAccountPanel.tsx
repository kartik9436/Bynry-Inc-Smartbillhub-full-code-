// ── Trace ──────────────────────────────────────────────
// Screen:  ACC-06 step 1 — `05-prototype/move-out-acc06-2026-09-24/`
//          `01-find-account.png` (regular). Built from the IMAGE, per the PO's
//          release instruction of 2026-09-24: *"use images to build the screen
//          - dont use text or content ot build the screen"*, which is B14 rule
//          42 in the PO's own words.
// Defect:  DEF-CUS-6476 — the panel carried no mailing-address row, though the
//          Accounts blueprint p112 draws one and the payload has always served
//          it. An absence is invisible to every check this repo has.
// Rules:   B14 rule 43 (a piece of UI is a COMPONENT; standalone code inside a
//          page is not reuse) · B14 rule 21 (Tailwind utilities, no class added
//          to a stylesheet; this file is on `route-b-migrated.txt`) ·
//          B14 rule 36 (the shared kit is how you comply) · B14 rule 31 (no
//          database id is ever a visible value) · B14 rule 33 (a LABEL ≤ 3
//          words; RATIONALE is ZERO words on screen) · CLAUDE.md hard rule 8
//          (an address lives on `premises`; `customers.addresses kind='mailing'`
//          is one of three named exceptions) · CLAUDE.md hard rule 2 (money to
//          four decimals, displayed to two)
// Tests:   src/features/customers/MoveOutWizard.test.tsx
// ───────────────────────────────────────────────────────
//
// ╔══════════════════════════════════════════════════════════════════════════╗
// ║  WHY THIS IS A FILE AND NOT TWELVE MORE LINES IN THE WIZARD              ║
// ╚══════════════════════════════════════════════════════════════════════════╝
//
// **The drawing puts the account's facts in TWO COLUMNS of label-and-value.**
// The kit's `FactList` is `.met-facts`, a two-column grid — ONE label and ONE
// value per row — so it cannot draw the panel as drawn. The choices were to add
// a four-column class to a stylesheet, which B14 rule 21 forbids for new UI, or
// to write the panel in Tailwind utilities in a file the ledger lists.
//
// ⚠ **`MoveOutWizard.tsx` IS NOT ON `route-b-migrated.txt`, SO A UTILITY
// WRITTEN THERE FAILS `G31` AT MERGE.** That is the real consequence and it is
// worth stating plainly, because the warning this repo carried until 2026-09-12
// said such a utility *"renders as nothing at all"* — it does not; the compiler
// scans the whole of `src/`. The ledger gates the CHECKS, not the CSS, and the
// fix for an unlisted file is to list a file, never to reach for a stylesheet
// class. This file is listed, so the utilities here are owned by
// `routeBUtilities.test.ts`, which asks the stricter question.
//
// ⚠ **AND THAT STRICTER QUESTION EARNED ITS PLACE ON THE FIRST RUN.** This file
// was written with `text-lg` and `text-white`. Both read as perfectly ordinary
// Tailwind and **this theme defines neither** — the size scale has no `lg` step
// (it runs `xs · sm · base · md · lead · …`) and the palette runs
// `neutral-100..900` with no `white`. Both compile to NOTHING, and every check
// that could plausibly have caught it passed: `tsc`, eslint and all 68 unit
// cases. So would `expect(el.className).toContain("text-white")`, because the
// class genuinely IS in the DOM — it simply renders no rule.
// `routeBUtilities.test.ts` named both in one line; they are now `text-md`
// (14px, a real step) and `text-neutral-100`. **This is the argument for
// LISTING a file rather than leaving it to G31**, which asks only whether a
// stylesheet declares each class and would have said nothing about either.
//
// ⚠ **AND IT IS RULE 43's OWN CASE.** The wizard being rebuilt is 2,088 lines.
// Rule 43 was ratified after *"use it"* turned out to mean 120 lines inline in a
// 4,186-line page, importable by nothing. A panel that step 4's review will also
// want, and that the master variant changes row by row, is a component.

import type { ReactNode } from "react";

import { MoneyCell } from "@/components/MoneyCell";
import { DateCell } from "@/components/DateCell";
import type { RegionalDateFormat } from "@/components/DateCell";
import { StatusPill } from "@/components/StatusPill";
import { Dash, Fact, FactList, ServiceTags } from "@/features/metering/meteringShared";
import type { Translator } from "@/features/tenancy/settingsShared";
import type { AccountAddress, AccountDetail } from "@/api/endpoints";

import { addressLine } from "./AccountDetailPage";
import type { AccountCategoryOption } from "./customersShared";
import { accountCategoryName, accountStatusLabel, accountStatusTone } from "./customersShared";
import { unitPlanLine } from "./moveShared";

/** `master` is the owner's account for a building (`BR-CUS-068`). */
export const ACCOUNT_KIND_MASTER = "master";

/**
 * The MAILING address, as an envelope reads it — or the claim that there is no
 * separate one.
 *
 * ⚠ **AN ABSENT ROW IS A REAL ANSWER AND A DIFFERENT ONE FROM AN EMPTY
 * ADDRESS**, which is why this returns a discriminated answer rather than a
 * string or a null. `addressLine`'s own docstring makes the point: *"an account
 * with no mailing row means 'same as service', which is a different claim from
 * 'no address'"*. Collapsing the two is how a landlord's bills quietly start
 * going to the flat they do not live in.
 *
 * ⚠ **HARD RULE 8 IS SATISFIED BY READING, NOT BY STORING.** An address lives on
 * `premises` and nowhere else — except the three the rule names, and
 * `customers.addresses kind='mailing'` is the first of them, because where the
 * BILL goes is a different fact from where the service is (for a landlord it is
 * another building entirely). `kind='service'` is RETIRED and refused by name,
 * so the service address on this panel is derived by walking to the premises and
 * is never read from here.
 *
 * Pure, so the distinction can be proved without a mount.
 */
export function mailingAddressAnswer(
  addresses: readonly AccountAddress[],
): { kind: "line"; text: string } | { kind: "same" } {
  const row = addresses.find((address) => address.kind === "mailing");
  if (row === undefined) return { kind: "same" };
  const text = addressLine(row);
  return text === "" ? { kind: "same" } : { kind: "line", text };
}

/**
 * One drawn row. **The KIT builds it** — `Fact` renders the `<dt>`/`<dd>` pair
 * inside `FactList`'s `.met-facts` grid, which already owns the label column's
 * width and the row rhythm.
 *
 * ⚠ **THIS WRAPPER EXISTS ONLY TO CARRY *EMPHASIS*, WHICH THE DRAWING HAS AND
 * THE KIT DOES NOT.** `01-find-account.png` sets the account number and the
 * balance in a heavier weight; everything else about the row — padding, gap,
 * label width, type size — is the kit's and is not re-decided here (B14 rule
 * 44: the drawing says WHAT is on the screen, our UI standard says HOW it is
 * built, all the time).
 */
function Row(props: { label: string; children: ReactNode; strong?: boolean }) {
  return (
    <Fact label={props.label}>
      {props.strong === true ? <span className="font-semibold">{props.children}</span> : props.children}
    </Fact>
  );
}

/**
 * The two columns the drawing arranges the facts in — and **the only thing in
 * this file that is a layout decision at all.**
 *
 * ⚠ **NO MIN-WIDTH VARIANT, AND THAT IS RULE 44 BITING ON THIS LANE'S OWN
 * WORK.** The first version wrote `md:flex-row`, `md:gap-4`, `md:w-40` and
 * `lg:grid-cols-2` — six of them. **This theme is DESKTOP-FIRST** and the staff
 * app is laptop and desktop only, verified at 1280 and 1440 and nothing
 * narrower (PO 2026-09-10), so widening from a phone breakpoint is construction
 * for a case the product does not have. `G107` refuses a new min-width site in
 * the staff app, and it had all six — **invisible to this lane's own gate diff,
 * which compared each gate's PASS/FAIL and not its finding COUNT, and `G107`
 * was already red.** Two columns is the base rule and there is no variant.
 *
 * `gap-x-8` is `--space-8`, 32px, a named step. The first version used
 * `gap-x-10` (40px) and `py-2.5` (10px), neither of which is on the scale.
 * The whole finding is `DEF-CUS-6496`, filed against this lane's own wave 3.
 */
function Columns(props: { left: ReactNode; right: ReactNode }) {
  return (
    <div className="grid grid-cols-2 gap-x-8">
      <FactList>{props.left}</FactList>
      <FactList>{props.right}</FactList>
    </div>
  );
}

export interface MoveOutAccountPanelProps {
  detail: AccountDetail;
  categories: readonly AccountCategoryOption[];
  timeZone: string;
  dateFormat: RegionalDateFormat;
  t: Translator;
}

/**
 * *This account* — `01-find-account.png`, the panel under the search box.
 *
 * **THE ROW SET IS THE DRAWING'S AND THE ORDER IS PART OF IT.** Left: Account ·
 * Name · Service address · Mailing address · Services · Plan. Right: Type ·
 * Sub-type · Kind · Status · Since · Balance. Four of those rows — the mailing
 * address, the type, the sub-type and the kind — were not on this panel before
 * 2026-09-24, and **every one of them was already on the wire**: the payload has
 * carried `addresses`, `account_type`, `account_subtype_name` and `kind` all
 * along. That is `DEF-CUS-6476`'s lesson rather than a coincidence — an absence
 * is invisible to every check this repo has, so a panel is diffed against its
 * drawing row by row or the gap is never found.
 *
 * ⚠ **THE THREE LABELS ON THE RIGHT DIVERGE FROM THE REST OF THE PRODUCT, AND
 * THAT IS RULED RATHER THAN CHOSEN.** The account detail page calls the same
 * three fields *Category*, *Sub-category* and *Account kind*. The PO ratified
 * these drawings on 2026-09-24 **after** the panel gained *Type · Sub-type ·
 * Kind* — *"okay we are good with all changes agreed for move out"* — so the
 * drawing wins here. The product now calls one field two things on two screens,
 * which is filed (`DEF-CUS-6491`) rather than silently resolved either way: it
 * is the PO's to unify, and a lane running a copy audit must not "fix" it.
 *
 * ⚠ **NO DATABASE ID IS VISIBLE (B14 rule 31).** `account_type` is a platform
 * code and `account_subtype` is the tenant's own; both resolve to a NAME, and
 * the fallback is the code rather than an invented label — inventing one is how
 * `government` quietly starts reading as *Municipal* (`DEF-684`).
 */
export function MoveOutAccountPanel(props: MoveOutAccountPanelProps) {
  const { detail, t } = props;
  const mailing = mailingAddressAnswer(detail.addresses);
  const isMaster = detail.kind === ACCOUNT_KIND_MASTER;

  return (
    <section data-move-out-account-panel={isMaster ? "master" : "regular"}>
      <h3 className="mb-3 flex items-center gap-3 font-heading text-md font-semibold">
        {/* ⚠ **THE PANEL'S OWN HEADING, WHICH IS *NOT* THE STEP'S.**
            `01-find-account.png` draws TWO panels on step 1 — *Find the
            account* over the search, and *This account* over the facts — and
            the wizard's `customers.moveOut.account.title` (*"Which account is
            moving out?"*) was the STEP's question. Rendering it here as well
            printed the same sentence twice, one line apart, which the browser
            walk showed and no unit case could: both headings are legitimate
            strings that resolve in eleven languages. */}
        {t("customers.moveOut.account.thisAccount", { defaultValue: "This account" })}
        {/* The kind, as a badge beside the heading — `01M`'s own mark. It is a
            STATE and not a control, so it is a chip rather than a button. */}
        {isMaster ? (
          <span
            className="bg-neutral-900 px-2 py-1 font-mono text-xs uppercase tracking-tag text-neutral-100"
            data-account-kind="master"
          >
            {t("customers.accounts.kind.master")}
          </span>
        ) : null}
      </h3>

      <Columns
        left={
          <>
            <Row label={t("customers.accounts.col.account")} strong>
              {detail.account_no ?? <Dash>{t("customers.account.noNumber")}</Dash>}
            </Row>
            <Row label={t("customers.accounts.col.name")}>
              {detail.name ?? <Dash>{t("customers.accounts.noName")}</Dash>}
            </Row>
            {/* ⚠ **DERIVED BY WALKING TO THE PREMISES (hard rule 8).** `premise`
                is composed by the server from `account → unit → premises`; it is
                NOT read from an `addresses` row, because `kind='service'` is
                retired and refused by name. `DEF-CUS-3653` is what that
                retirement cost when nobody grepped for the consumers. */}
            <Row label={t("customers.account.field.serviceAddress")}>
              {detail.premise ?? detail.unit_label ?? <Dash />}
            </Row>
            <Row label={t("customers.account.field.mailingAddress")}>
              {mailing.kind === "line" ? (
                mailing.text
              ) : (
                <Dash>{t("customers.account.field.mailingSame")}</Dash>
              )}
            </Row>
            <Row label={t("customers.accounts.col.services")}>
              <ServiceTags services={detail.services} t={t} />
            </Row>
            {/* The UNIT's plan, never the account's snapshot — `DEF-2419` is the
                defect that came from reading one as the other. One formatter in
                `moveShared` answers here and on the review, so they cannot
                drift. */}
            <Row label={t("customers.moveOut.field.plan", { defaultValue: "Plan" })}>
              {unitPlanLine(detail.unit_plan) ?? <Dash>{t("customers.account.planNone")}</Dash>}
            </Row>
          </>
        }
        right={
          <>
            <Row label={t("customers.moveOut.account.type", { defaultValue: "Type" })}>
              {accountCategoryName(detail.account_type, props.categories)}
            </Row>
            <Row label={t("customers.moveOut.account.subtype", { defaultValue: "Sub-type" })}>
              {detail.account_subtype_name ?? detail.account_subtype ?? <Dash />}
            </Row>
            <Row
              label={t("customers.moveOut.account.kind", { defaultValue: "Kind" })}
              strong={isMaster}
            >
              {isMaster
                ? t("customers.accounts.kind.master")
                : t("customers.accounts.kind.regular")}
            </Row>
            <Row label={t("customers.accounts.col.status")}>
              <StatusPill tone={accountStatusTone(detail)}>
                {accountStatusLabel(detail, t)}
              </StatusPill>
            </Row>
            <Row label={t("customers.accounts.col.since")}>
              {detail.opened_at !== null ? (
                <DateCell
                  value={detail.opened_at}
                  timeZone={props.timeZone}
                  dateFormat={props.dateFormat}
                />
              ) : (
                <Dash />
              )}
            </Row>
            {/* BR-SHL-023 / hard rule 2: the decimal string and its CHAR(3) code
                travel together and nothing here parses or rounds one. Four
                decimals stored, two displayed, by the cell. */}
            <Row label={t("customers.accounts.col.balance")} strong>
              {detail.balance !== null ? (
                <MoneyCell amount={detail.balance} currency={detail.currency} />
              ) : (
                <Dash />
              )}
            </Row>
          </>
        }
      />
    </section>
  );
}
