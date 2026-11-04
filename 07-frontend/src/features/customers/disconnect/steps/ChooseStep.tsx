// ── Trace ──────────────────────────────────────────
// Change:   the DISCONNECT WIZARD REBUILD of 2026-09-25 — **STEP 1 OF FOUR,
//           `Choose`**, built from `Step1Choose.png` and `MasterStep1.png` AS
//           IMAGES (B14 rule 42, PO: *"When you use images to create screens
//           your accuracy is higher; hence dont create screens using only
//           Text"*).
// Rules:    **BR-CUS-1098** (a master account's cut is a BUILDING's cut; step 1
//           carries ONE line — *"Master account · 25 occupying accounts"* — and
//           that single line is the whole warning) · **BR-CUS-097** (a
//           sub-account's unpayable residue transfers UP, which is why the
//           master's strip splits *Own debt* from *Transferred up*) ·
//           BR-CUS-053 (the published account search) · B14 rules 20, 21, 31,
//           32, 33, 43, 44
// Tests:    ../../DisconnectWizard.test.tsx
// ─────────────────────────────────────────────────────
//
// ══════════════════════════════════════════════════════════════════════════
// 1 · WHAT MOVED OFF THIS STEP, AND WHY — ITEMS 3.2 AND 3.8
// ══════════════════════════════════════════════════════════════════════════
// The five-step step 1 (blueprint p136) drew **twelve account facts**, a
// six-row money panel, the three unpaid bills behind the balance, and `Where
// the ladder has got to` with its three notice dates. The four-step step 1
// draws **four facts and one table**.
//
// Nothing was lost; each fact now appears ONCE, on the step that acts on it:
//
//   · the ladder's tier and its three served dates → **step 2's `Notice
//     served` check**, which is item 3.2: the ladder check was on step 1 AND
//     step 2 and is now on step 2 alone;
//   · the bills behind the balance → the ACCOUNT, which is one click away and
//     is where a clerk reads a bill;
//   · the twelve account facts → the account, for the same reason. Four are
//     kept here because a clerk about to cut somebody's water must see whose,
//     where, what they owe and what they have.
//
// ⚠ **AND THE RESTRICTOR SENTENCE IS GONE — ITEM 3.14.** p136 drew a
// `Restrictor / limiter` option beside a red box explaining that this product
// cannot record one. Offering a control and explaining in the next breath that
// it does not work is hard-won law 2's mirror wearing a caption. The OPTION is
// gone from the treatment list this step offers, so nothing needs explaining
// and nothing is explained — B14 rule 33 puts rationale at zero words.
//
// ══════════════════════════════════════════════════════════════════════════
// 2 · THE MASTER VARIANT IS THIS STEP WITH THREE CELLS ASKING DIFFERENT
//     QUESTIONS — IT IS NOT A SECOND SCREEN
// ══════════════════════════════════════════════════════════════════════════
// `MasterStep1.png` differs from `Step1Choose.png` in exactly four places: one
// banner line, two extra facts in the strip, and two column HEADINGS on the one
// table — `METER` becomes `POINTS`, `NOTE` becomes `WHO IT REACHES`. Everything
// else is identical, down to the add row.
//
// **So it is one component and `master` is a prop.** A second file would be a
// second screen to keep in step with this one, and `BR-CUS-1098` is explicit
// that the master case is the same act with a wider blast radius rather than a
// different act.
import { useMemo } from "react";

import { MoneyCell } from "@/components/MoneyCell";
import { SelectField } from "@/components/FormModal";
import { Panel } from "@/components/Panel";
import { RefusalStrip } from "@/components/Surfaces";
import { WarningBox } from "@/components/WarningBox";
import type { AccountDetail } from "@/api/endpoints";

import { DisconnectFacts } from "../DisconnectFacts";
import type { DisconnectFact } from "../DisconnectFacts";
import { DisconnectTableArray } from "../DisconnectTableArray";
import type { DisconnectArrayColumn } from "../DisconnectTableArray";
import type { DisconnectDraft, DisconnectServiceRow } from "../disconnectDraft";
import { servicesCut } from "../disconnectDraft";
import { CUT_REASONS, SERVICE_TREATMENTS, TREATMENT_RESTRICTOR } from "../../transferDisconnectShared";
import type { ServiceTreatment, Translator } from "../../transferDisconnectShared";
import { AccountFinder } from "../../accountFinder";
import type { AccountSearchState } from "../../accountFinder";
import type { DisconnectPreflightBlocker } from "../../transferDisconnectEndpoints";
import { disconnectRefusalTextForCode } from "../disconnectRefusal";
import { serviceLabel } from "@/features/assets/assetsShared";

/**
 * ⚠ **THE RESTRICTOR IS NOT OFFERED — ITEM 3.14.**
 * `assert_treatments_expressible` refuses a restrictor BY NAME, because
 * `disconnect_cases` knows cut and not-cut and a restricted service is neither:
 * it keeps flowing, keeps billing and is under enforcement. The old screen
 * offered it disabled with a sentence saying so. **A control nobody may press
 * beside a paragraph about why is two breaches — a dead control and rationale
 * on screen — and removing the option is one fix for both.**
 *
 * ⚠ **THE UNDERLYING GAP IS UNCHANGED AND IS NOT HIDDEN BY THIS.** The server
 * still refuses, `RESTRICTOR_UNBUILDABLE` still records what it would take, and
 * the day a schema can hold a restricted supply this list gets its third entry
 * back. What is gone is the screen pretending to offer it.
 */
const OFFERED_TREATMENTS = SERVICE_TREATMENTS.filter(
  (treatment) => treatment.code !== TREATMENT_RESTRICTOR,
);

export interface ChooseStepProps {
  draft: DisconnectDraft;
  account: AccountDetail | null;
  /** `true` when the account read failed — the finder stays usable and the
   *  strip states the absence rather than drawing empty facts. */
  failed: boolean;
  onPatch: (next: Partial<DisconnectDraft>) => void;
  term: string;
  onTermChange: (term: string) => void;
  search: AccountSearchState;
  t: Translator;
  /** `BR-CUS-1098` — a MASTER account's cut is a building's cut. Derived from
   *  `account.kind`, never typed. */
  master: boolean;
  /** How many accounts occupy the building, for the master banner and for the
   *  `WHO IT REACHES` cell. `null` when it could not be read — which is a
   *  different answer from zero and is rendered as such. */
  occupants: number | null;
  /** ⛔ **`DEF-CUS-7680` — WHY THIS CASE CANNOT BE SCHEDULED, ANSWERED HERE
   *  RATHER THAN AFTER FOUR STEPS.**
   *
   *  The SERVER's own answer (`disconnect_reads.schedule_readiness`, which
   *  runs `schedule_cut`'s guards read-only), `null` when there is nothing to
   *  say or when the read has not landed. This step renders the sentence and
   *  decides nothing: the code selects catalogue copy through
   *  `disconnectRefusalTextForCode`, which is the SAME map the commit failure
   *  uses, so a clerk cannot be told two different things about one refusal.
   *
   *  ⚠ **`detail` IS ON THIS OBJECT AND IS NEVER RENDERED** — `BR-SHL-020` r2
   *  (PO 2026-08-19): server prose does not reach a clerk. It travels so the
   *  shape matches the wire and so support can read it from the network tab. */
  preflight: DisconnectPreflightBlocker | null;
}

export function ChooseStep(props: ChooseStepProps) {
  const t = props.t;
  const account = props.account;
  const cut = servicesCut(props.draft);

  // ⚠ **THE SERVICES ON THE TABLE ARE THE ACCOUNT'S OWN AND ARE NOT TYPED
  // HERE** (§12 of the UI method — never hand-type a list). `account.services`
  // is one code per ACTIVE service agreement (`BR-CUS-015`), which is the same
  // list the account screen shows. An eleventh service appears on this table on
  // the day the account has one.
  const available = useMemo(() => {
    const onTable = new Set(props.draft.services.map((row) => row.code));
    return (account?.services ?? []).filter((code) => !onTable.has(code));
  }, [account, props.draft.services]);

  function setRows(rows: DisconnectServiceRow[]): void {
    props.onPatch({ services: rows });
  }

  function patchRow(index: number, next: Partial<DisconnectServiceRow>): void {
    setRows(props.draft.services.map((row, i) => (i === index ? { ...row, ...next } : row)));
  }

  const columns: DisconnectArrayColumn<DisconnectServiceRow>[] = [
    {
      key: "service",
      label: t("customers.disconnect.choose.colService", { defaultValue: "Service" }),
      cell: (row) => (
        <span className="font-semibold">{serviceLabel(row.code, t)}</span>
      ),
    },
    {
      key: "meter",
      // ⚠ ONE COLUMN, TWO QUESTIONS — `METER` on a regular account and `POINTS`
      // on a master, which is what `MasterStep1.png` draws. `BR-CUS-1098`: a
      // master's common supply is one point and its units are many.
      label: props.master
        ? t("customers.disconnect.choose.colPoints", { defaultValue: "Points" })
        : t("customers.disconnect.choose.colMeter", { defaultValue: "Meter" }),
      cell: (row) => <span>{row.meter === "" ? "—" : row.meter}</span>,
    },
    {
      key: "treatment",
      label: t("customers.disconnect.choose.colTreatment", { defaultValue: "Treatment" }),
      cell: (row, index) => (
        <SelectField
          id={`disconnect-treatment-${row.code}`}
          // The COLUMN HEADER is the label, so it is announced and not drawn —
          // `SelectField`'s own `labelHidden`, which exists for exactly this.
          labelHidden
          label={t("customers.disconnect.choose.colTreatment", { defaultValue: "Treatment" })}
          value={row.treatment}
          placeholder={t("customers.disconnect.choose.pickTreatment", {
            defaultValue: "Choose",
          })}
          onChange={(value) =>
            patchRow(index, { treatment: value as ServiceTreatment | "" })
          }
          options={OFFERED_TREATMENTS.map((treatment) => ({
            value: treatment.code,
            label: t(`customers.disconnect.treatment.${treatment.code}`, {
              defaultValue: treatment.en,
            }),
          }))}
        />
      ),
    },
    {
      key: "note",
      label: props.master
        ? t("customers.disconnect.choose.colReaches", { defaultValue: "Who it reaches" })
        : t("customers.disconnect.choose.colNote", { defaultValue: "Note" }),
      cell: (row) => <span>{row.note === "" ? "—" : row.note}</span>,
    },
  ];

  const facts: DisconnectFact[] = [];
  if (account !== null) {
    // ⚠ **THE ACCOUNT NUMBER IS ON THE STRIP, AND THE DRAWING PUTS IT IN THE
    // FIELD — `DEF-CUS-6765`.** `Step1Choose.png` shows the finder reading
    // *"AC-2026-00054 — John Mauli · Unit 1"*, so the number IS on the screen.
    // The shared `AccountFinder` cannot show it: on the pre-selected path it
    // prints the raw database id instead, which is B14 rule 31 and is filed.
    // **Until that is fixed the strip is the only honest place a clerk can
    // read which account they are about to cut**, and a clerk cutting somebody's
    // water must be able to. When the finder is repaired this fact becomes the
    // duplicate item 3.8 forbids and should come off.
    facts.push({
      id: "account-no",
      label: t("customers.disconnect.choose.factAccount", { defaultValue: "Account" }),
      value: account.account_no ?? "—",
    });
    facts.push({
      id: "customer",
      label: t("customers.disconnect.choose.factCustomer", { defaultValue: "Customer" }),
      // ⚠ **`account.name` AND NOT `accountHeadline` — IT CRASHED.**
      // `accountHeadline` walks `contacts`, which is OPTIONAL on the wire and
      // absent on more than one fixture, so it threw `Cannot read properties of
      // undefined (reading 'find')` and took the whole step down. The drawing
      // asks for the customer's NAME and that is a field of its own.
      value: account.name ?? "—",
    });
    facts.push({
      id: "address",
      label: t("customers.disconnect.choose.factAddress", { defaultValue: "Address" }),
      value: account.premise ?? "—",
    });
    if (props.master) {
      // `BR-CUS-097` — the owner's own debt and the residue transferred up are
      // two different facts, and a single `Balance` hides which is which.
      facts.push({
        id: "own-debt",
        label: t("customers.disconnect.choose.factOwnDebt", { defaultValue: "Own debt" }),
        value: <AccountMoney account={account} />,
      });
      facts.push({
        id: "transferred-up",
        label: t("customers.disconnect.choose.factTransferred", {
          defaultValue: "Transferred up",
        }),
        // ⛔ **NOT SERVED, AND STATED RATHER THAN COMPUTED.** `BR-CUS-097`'s
        // residue is a real fact and `GET /accounts/{id}` does not carry it;
        // subtracting one figure from another in a browser would be money
        // arithmetic in JavaScript, which hard rule 2 exists to prevent.
        value: (
          <span className="text-neutral-700">
            {t("customers.disconnect.choose.notServed", { defaultValue: "Not shown yet" })}
          </span>
        ),
      });
    }
    facts.push({
      id: "balance",
      label: t("customers.disconnect.choose.factBalance", { defaultValue: "Balance" }),
      value: <AccountMoney account={account} />,
    });
    facts.push({
      id: "services",
      label: t("customers.disconnect.choose.factServices", { defaultValue: "Services" }),
      value:
        account.services.length === 0
          ? "—"
          : account.services.map((code) => serviceLabel(code, t)).join(", "),
    });
  }

  return (
    <div className="flex flex-col gap-6" data-step="choose">
      {/* ⚠ **ONE LINE IS THE WHOLE WARNING — `BR-CUS-1098`, confirmed by the PO
          in those words.** Not a panel, not a list of the twenty-five, not a
          sentence about what that means. */}
      {props.master && (
        <WarningBox
          tone="now"
          data-warning="master-account"
          sentence={
            <strong>
              {props.occupants === null
                ? t("customers.disconnect.master.bannerUnknown", {
                    defaultValue: "Master account · occupants not counted",
                  })
                : t("customers.disconnect.master.banner", {
                    defaultValue: "Master account · {{count}} occupying accounts",
                    count: props.occupants,
                  })}
            </strong>
          }
        />
      )}

      {/* ⛔ **`DEF-CUS-7680` — WHY THIS CASE CANNOT BE SCHEDULED, SAID HERE
          RATHER THAN AFTER FOUR STEPS.** One sentence, from the catalogue,
          keyed on the SERVER's own refusal code — B14 rule 32 keeps the code
          off the screen and rule 33 keeps the reason WHY out of it entirely.
          `Continue` is refused with the same sentence by this step's
          `validate`, so a clerk cannot walk past it into three steps of work.

          ⚠ **ABOVE THE PANEL, NOT UNDER THE FINDER — AND THAT IS A BROWSER
          FINDING, NOT A PREFERENCE.** It was first placed inside `The account`
          panel, directly under the account field, on the reasoning that the
          ACCOUNT is what carries the refusal. **The account finder's own
          results list is drawn over that spot**, so on a wizard opened from
          `?account=` the sentence was covered by the combobox and only a
          sliver of the strip showed. Every test passed — the element was in
          the DOM with the right text — and it was found by putting the
          screenshot in front of a person, which is CLAUDE.md hard-won law 6
          word for word. It is also the better place on its own merits: this
          refuses the whole STEP, not one field.

          ⚠ **THE CODE RIDES ON `data-preflight` AND IS NOT PART OF THE
          SENTENCE** — `RefusalNotice`'s `data-br-ref` precedent, `DEF-332`. A
          `data-` attribute is invisible to a screen reader by design and never
          enters the accessible name, so the clerk reads the sentence while
          support, the inspector and this screen's own tests read the handle. */}
      {props.preflight !== null && (
        <RefusalStrip role="alert" data-preflight={props.preflight.code}>
          {disconnectRefusalTextForCode(t, props.preflight.code)}
        </RefusalStrip>
      )}

      {/* ⚠ **A `Panel` AND NOT A TABLE ARRAY.** The account block is a form
          and a fact strip; the drawing draws no rows a clerk adds to or removes
          from, so it is not a collection and must not borrow a collection's
          frame. */}
      <Panel as="section" title={t("customers.disconnect.choose.account", { defaultValue: "The account" })} data-panel="account">
        {/* The finder and the reason sit side by side, as drawn. B14 rule 44:
            the SHAPE is the drawing's, the spacing and the field anatomy are
            our standard's. */}
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-[2fr_1fr]">
          <AccountFinder
            idPrefix="dsc"
            label={t("customers.disconnect.choose.accountLabel", { defaultValue: "Account" })}
            term={props.term}
            onTermChange={props.onTermChange}
            search={props.search}
            value={props.draft.accountId}
            onChange={(id) => props.onPatch({ accountId: id, services: [] })}
            required
            t={t}
          />
          <SelectField
            id="disconnect-reason"
            label={t("customers.disconnect.choose.reason", { defaultValue: "Reason" })}
            value={props.draft.reason}
            placeholder={t("customers.disconnect.choose.pickReason", {
              defaultValue: "Choose",
            })}
            onChange={(value) => props.onPatch({ reason: value })}
            options={CUT_REASONS.map((reason) => ({
              value: reason.code,
              label: t(`customers.disconnect.reason.${reason.code}`, { defaultValue: reason.en }),
            }))}
          />
        </div>
        {props.failed ? (
          <p className="mt-4 mb-0 text-base text-danger-700" data-account-failed="">
            {t("customers.disconnect.choose.accountFailed", {
              defaultValue: "The account did not load.",
            })}
          </p>
        ) : (
          facts.length > 0 && (
            <div className="mt-4">
              <DisconnectFacts facts={facts} name="account" />
            </div>
          )
        )}
      </Panel>

      <DisconnectTableArray<DisconnectServiceRow>
        title={t("customers.disconnect.choose.services", { defaultValue: "Which services" })}
        fact={
          props.master && props.occupants !== null
            ? t("customers.disconnect.master.reachFact", {
                defaultValue: "{{count}} occupants lose supply. None of them owes anything.",
                count: props.occupants,
              })
            : t("customers.disconnect.choose.oneEach", {
                defaultValue: "One decision per service",
              })
        }
        columns={columns}
        rows={props.draft.services}
        rowKey={(row, index) => `${row.code}-${index}`}
        onChange={setRows}
        removeLabel={t("customers.disconnect.choose.removeService", {
          defaultValue: "Remove this service",
        })}
        emptyText={t("customers.disconnect.choose.noServices", {
          defaultValue: "No service chosen. Add one below.",
        })}
        addLabel={t("customers.disconnect.choose.addService", {
          defaultValue: "+ Add a service",
        })}
        onAdd={() => {
          const code = available[0];
          if (code === undefined) return;
          setRows([...props.draft.services, blankServiceRow(code, props.master, props.occupants, t)]);
        }}
        addBlockedReason={
          available.length > 0
            ? undefined
            : // BR-SHL-025 — disabled with its reason, never hidden.
              t("customers.disconnect.choose.allAdded", {
                defaultValue: "Every service is already listed.",
              })
        }
        addFact={t("customers.disconnect.choose.willCut", {
          defaultValue: "{{count}} will be cut",
          count: cut.length,
        })}
        collection="services"
      />
    </div>
  );
}

/** A new row for a service the account holds. ⚠ **THE TREATMENT STARTS BLANK**
 *  — defaulting it either way decides for the clerk, and one of the two
 *  directions cuts a service nobody asked to cut. */
function blankServiceRow(
  code: string,
  master: boolean,
  occupants: number | null,
  t: Translator,
): DisconnectServiceRow {
  return {
    code,
    // ⛔ THE METER IS NOT SERVED ON THE ACCOUNT READ. `GET /accounts/{id}`
    // carries the service CODES and no meter per service; the number a clerk
    // reads is metering's and reaches this screen through nothing today.
    // Stated as an absence rather than left to render `undefined`.
    meter: "",
    treatment: "",
    note:
      master && occupants !== null
        ? t("customers.disconnect.master.reaches", {
            defaultValue: "All {{count}} occupants",
            count: occupants,
          })
        : "",
  };
}

/** The account's balance, through the kit's one money path.
 *  ⚠ **`balance` IS NULLABLE AND A NULL IS NOT A ZERO** (`DEF-127`): the books
 *  being unreadable and the account owing nothing are different claims, and
 *  only one of them is good news. */
function AccountMoney(props: { account: AccountDetail }) {
  if (props.account.balance === null || props.account.balance_currency === null) {
    return <span className="text-neutral-700">—</span>;
  }
  return (
    <MoneyCell amount={props.account.balance} currency={props.account.balance_currency} />
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: the disconnect wizard rebuild, 2026-09-25 · `Step1Choose.png` ·
//         `MasterStep1.png` · blueprint p136 (the five-step shape, departed
//         from and recorded above) · BR-CUS-097 · BR-CUS-015 · BR-CUS-053 ·
//         BR-CUS-1098 · BR-SHL-025 · B14 rules 20, 21, 31, 32, 33, 37, 42, 43, 44
// generated: 2026-09-25 by lane WIZARD
// exceptions:
//   E3 **the METER cell is `—` on every row.** The account read serves service
//      codes and no meter per service; nothing is invented.
//   E3 **`Transferred up` states an absence on the master strip.** `BR-CUS-097`'s
//      residue is real and is not on the wire; deriving it in a browser would be
//      money arithmetic in JavaScript (hard rule 2).
//   E3 **the restrictor treatment is REMOVED rather than disabled** — item 3.14.
//      The server's refusal and `RESTRICTOR_UNBUILDABLE` are untouched.
//   E3 **blueprint p136's twelve account facts, its three unpaid bills and its
//      ladder panel are NOT drawn here** — item 3.8, each fact once. The ladder
//      is step 2's `Notice served` row; the rest is the account screen's.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
