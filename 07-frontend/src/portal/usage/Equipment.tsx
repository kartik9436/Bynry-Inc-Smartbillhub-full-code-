// ── Trace ──────────────────────────────────────────────
// Story:    US-CWP-043 (EP-CWP-08) — *Meters and equipment at the property*.
//           Screen: CWP-037 (blueprint `P23`)
// Rules:    BR-CWP-073 (equipment is what an unmeasured service is billed on) ·
//           BR-CWP-093 (an empty state, never a blank table) · B14 rule 20
//           (ONE table type) · rule 21 · rule 31 (shown by SERIAL, never by a
//           database id) · rule 32 · rule 35 · rule 36 (compose the kit)
// Defects:  DEF-CWP-3991 — both meters read `Meter`, so two rows were
//           identical apart from their serials · DEF-CWP-3992 — `STATUS`
//           printed the stored lookup label `Installed/Active`, a slash and
//           all, on a customer screen in a portal with eleven catalogues ·
//           `13-wireframe-delta.md` 37.1 · 37.2 · 37.5 · 37.7 · 37.8 · 37.9
//           and `14-layout-audit.md` D1 (this screen's half of it)
// CR-085:   s52 (group H) — **BARE REFERENCE NUMBERS, NOT A DETAIL RECORD.**
//           Product Owner, verbatim: *"just show IDs not details - Equipment
//           ... W-2209, 8841-C, F-0118 - this is enough + account status"*, and
//           the drawing's table is `Equipment · Reference · Installed · Whose ·
//           Monthly`. `Where` and `Last read` left the screen; a phone gets a
//           stack of cards. `08-screen-layouts.md` CWP-037 amended the same day.
// Tests:    src/portal/usage/Equipment.dom.test.tsx
// Impacts:  src/portal/api/portalClient.ts `getAccountEquipment`
// ───────────────────────────────────────────────────────
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { formatMonthYear } from "@/components/DateCell";
import { PageHeader } from "@/components/PageHeader";

import {
  Card,
  ErrandLink,
  InfoBar,
  StatusChip,
  usePortalPath,
} from "../components/primitives";
import { PortalListTable } from "../components/listTable";
import { getAccountEquipment, type PortalEquipment } from "../api/portalClient";
import { PortalScreen, PortalState } from "../components/states";

/**
 * `behavior_class` → the catalogue key that writes the word.
 *
 * ⚠ **THE CLASS TRAVELS AND THE CATALOGUE WRITES THE WORD, AND ON THIS SURFACE
 * THAT BEATS THE TENANT'S OWN LABEL (`DEF-CWP-3992`).** The screen used to
 * print `asset.status.name` verbatim — which out of the seed is
 * **`Installed/Active`**, a lookup value with a slash in it, on a customer's
 * screen. `BR-AST-031` says a tenant may RENAME a stage and that staff filters
 * key off the CLASS *"never the label"*; the customer portal renders in eleven
 * languages and a tenant's one English label cannot be written in ten of them,
 * so the same clause decides it here: the class is the fact, and the catalogue
 * writes the word. A class outside these four falls back to the tenant's own
 * label rather than to nothing.
 */
/** `maintained_by` → the catalogue key that writes *Ours* or *Yours*.
 *
 * ⚠ **THE SAME SHAPE `STATE_KEY` BELOW USES, FOR THE SAME REASON** (`BR-AST-031`,
 * `DEF-CWP-3992`): the CLASS is the fact and the catalogue writes the word. A
 * server that shipped *"Ours"* would make ten of the eleven catalogues
 * impossible — and *ours* is barely translatable without knowing who *we* are. */
const WHOSE_KEY: Record<string, string> = {
  utility: "portal.equipment.whose.utility",
  customer: "portal.equipment.whose.customer",
};

const STATE_KEY: Record<string, string> = {
  available: "portal.equipment.state.available",
  in_service: "portal.equipment.state.inService",
  out_of_service: "portal.equipment.state.outOfService",
  terminal: "portal.equipment.state.terminal",
};

/**
 * What a row is CALLED, and **the size a customer can check their charge
 * against** — `DEF-CWP-4848`, both clauses, one place.
 *
 * The drawing's cell, verbatim: `⚡ Electric meter` · `💧 Water meter · 5/8 inch`
 * · `🔥 Fire line · 2 inch sprinkler supply`, and its note says why the size is
 * there — *"Size is stated in inches, as the customer's plumber would."*
 *
 * ⚠ **CLAUSE ONE: THE SERVICE IS PREFIXED ONLY WHERE THE KIND DOES NOT
 * ALREADY NAME IT.** The cell was composed unconditionally as
 * `{{service}} {{kind}}`, which reads well for the seed word *Meter* — that is
 * `DEF-CWP-3991`, two rows at one property both reading `Meter` with only the
 * serial telling them apart — and stutters for anything the registry already
 * names after its own service. The fire asset type is `Fire service line`
 * (`assets/services.py` `SEED_ASSET_TYPES`, the thirteenth row), so the live
 * seed drew **`Fire Fire service line`** on the utility being onboarded.
 *
 * ⚠ **CLAUSE TWO: THE SIZE'S LEADING WORDS ARE DROPPED WHERE THE NAME
 * ALREADY SAID THEM.** The ratified vocabulary names every band after its
 * service — `Water 5/8"`, `Fire line 2"`, `Trash 96-gallon cart` — because it
 * is read on a settings screen where nothing else says which service it
 * belongs to. Here the row already says. Rendering it whole gives
 * `Water Meter · Water 5/8"`; dropping only words the title has ALREADY shown
 * gives `Water Meter · 5/8"` and `Fire service line · 2"`, which is the
 * drawing. **Nothing a reader has not already seen is removed**, which is what
 * keeps this a rendering decision rather than an edit of the tenant's own
 * words (B14 rule 35).
 *
 * ⚠ **AND A SYNONYM IS NOT A STUTTER THIS CAN SEE.** A tenant whose trash
 * type is called *Refuse cart* still gets `Trash Refuse cart`: the two words
 * share no letters and no check short of a thesaurus would join them. Said out
 * loud rather than left for the next lane to re-derive.
 */
export function equipmentName(
  item: PortalEquipment,
  t: (key: string, vars?: Record<string, unknown>) => string,
): string {
  const service = item.service_name;
  const named =
    service && !namesItsOwnService(item.kind, service)
      ? t("portal.equipment.kindOfService", { service, kind: item.kind })
      : item.kind;
  const size = sizeBeyond(item.size_class_name, named);
  return size === "" ? named : t("portal.equipment.kindWithSize", { kind: named, size });
}

/** Does this kind already say which service it is on? Case-insensitive, and a
 *  substring rather than a word match: *Wastewater meter* on a `Water` service
 *  is correctly left alone. */
function namesItsOwnService(kind: string, service: string): boolean {
  return kind.toLowerCase().includes(service.toLowerCase());
}

/** The part of the size name the title has not already said, left to right.
 *  `('Fire line 2"', "Fire service line")` → `2"`. Stops at the first word the
 *  title does not carry, so nothing in the MIDDLE of a size name can be lost —
 *  `Trash 96-gallon cart` under a `Trash Container / Cart` title keeps
 *  `96-gallon cart` and not `96-gallon`. */
function sizeBeyond(size: string | null, title: string): string {
  if (size === null || size === "") return "";
  const said = new Set(title.toLowerCase().split(/\s+/));
  const words = size.split(/\s+/);
  let from = 0;
  while (from < words.length && said.has(words[from].toLowerCase())) from += 1;
  return words.slice(from).join(" ");
}

/**
 * `CWP-037` — which meter is mine, where it is, and what state it is in.
 *
 * ⚠ **A SMALL SCREEN THAT ANSWERS A REAL QUESTION.** A customer standing in
 * their garden needs to know which box is theirs before they can read it or
 * tell us it is damaged — and the note says *tell us rather than touching it:
 * the meter belongs to the utility.*
 *
 * ⚠ **A TRASH CART IS ONE OF THESE** (`BR-CWP-073`): some services are billed
 * on equipment at the unit rather than on any reading. Its **last-read cell is
 * EMPTY, not zero** — a `0` would say the cart measured nothing.
 *
 * ⚠ **EVERY IDENTIFIER IS A SERIAL** (B14 rule 31, `US-CWP-043` TC-5), and the
 * payload carries no database id at all, so there is nothing here to truncate
 * into one either (`DEF-3158`).
 */
export function EquipmentView(props: { accountId: string }) {
  const { t } = useTranslation();
  const path = usePortalPath();
  const [rows, setRows] = useState<PortalEquipment[] | null>(null);
  const [failed, setFailed] = useState(false);
  /** R-10's way out, wired to a real read — see `Usage.tsx`'s note on why a
   *  `Try again` that calls nothing is worse than no button at all. */
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let live = true;
    setRows(null);
    setFailed(false);
    getAccountEquipment(props.accountId)
      .then((answer) => {
        if (live) setRows(answer.equipment);
      })
      .catch(() => {
        if (live) setFailed(true);
      });
    return () => {
      live = false;
    };
  }, [props.accountId, attempt]);

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
      backTo={{ to: path("/usage"), label: t("portal.equipment.backToUsage") }}
      title={t("portal.equipment.title")}
    />
  );

  if (failed) {
    return (
      <PortalScreen screen="CWP-037" head={head}>
        <PortalState
          kind="failed"
          testId="equipment"
          sentence={t("portal.equipment.couldNotRead")}
          /* `DEF-CWP-4846`'s other half — R-10, *"the thing they can do about
             it must be on that same screen, next to the message"*. Lane 1 put
             the HEAD back on this branch; `states.tsx` deliberately left
             `waysOut` optional because the read lives in each screen's own
             effect and per-screen actions belong to the lane that owns the
             screen. This is that lane supplying it. The head's `← Usage` is
             the second way out and is above this card on every branch. */
          waysOut={[
            {
              label: t("portal.state.tryAgain"),
              tone: "primary",
              testKey: "retry",
              onClick: () => setAttempt((n) => n + 1),
            },
          ]}
        />
      </PortalScreen>
    );
  }
  if (!rows) {
    return (
      <PortalScreen screen="CWP-037" head={head}>
        <PortalState kind="loading" testId="equipment" sentence={t("portal.equipment.reading")} />
      </PortalScreen>
    );
  }

  return (
    // ⚠ **A LITERAL `<div data-screen="CWP-037">`, NOT `PortalScreen` — see
    // `Usage.tsx`'s note.** Three SOURCE scanners find a portal screen by
    // grepping this exact string and none of them knows about a `screen=`
    // prop; `bills/BillDetail.tsx` keeps the literal for the same reason.
    <div data-screen="CWP-037">
      {head}
      {rows.length === 0 ? (
        // ⚠ **`BR-CWP-093`'s SENTENCE, AND NOW THE CONTROL THE DRAWING PUTS
        // BESIDE IT — `DEF-CWP-4849` clause 3.** Screen 52's `NOTHING
        // RECORDED` state reads *"We have not recorded your equipment yet."*
        // **With a way to ask**, and the way to ask lived INSIDE the non-empty
        // branch: the safety callout and its `Report a problem` door were
        // drawn only where there was already equipment to report a problem
        // with. So the customer most likely to need us — the one whose
        // property we have recorded nothing for — got one grey sentence and no
        // control at all. That is R-10 (*"when a screen tells a customer
        // something bad, the thing they can do about it must be on that same
        // screen, next to the message"*) from the empty side.
        //
        // ⚠ **`data-equipment-empty` IS KEPT DELIBERATELY.** Two walkthroughs
        // assert on it — `cr068-h-usage-readings.mjs` checks the count is ZERO
        // to prove the screen is NOT empty — and an attribute quietly renamed
        // turns both of them into checks that can no longer fail (hard-won law
        // 7, the *structurally incapable of failing* shape).
        <div data-equipment-empty="">
          <PortalState
            kind="empty"
            testId="equipment"
            sentence={t("portal.equipment.none")}
            waysOut={[
              {
                label: t("portal.equipment.reportProblem"),
                to: path("/report"),
                tone: "primary",
                testKey: "report",
              },
            ]}
          />
        </div>
      ) : (
        <Card testId="equipment">
          <>
            {/* ⚠ **THE DRAWING'S PHONE FRAME IS A STACK OF CARDS, NOT A
                TABLE THAT SCROLLS SIDEWAYS** — measured in the browser at
                390px, this table wanted 484. `bills/Bills.tsx` reached the
                same conclusion on the same evidence and this composes the same
                pattern (B14 rule 36). ⚠ **ONE SOURCE FOR BOTH**: each half
                renders `rows`, so a fact cannot be true on one width and not
                the other. */}
            <div className="mt-3 hidden flex-col gap-3 max-md:flex" data-equipment-cards="">
              {rows.map((item, index) => (
                <EquipmentCard
                  key={item.serial_no ?? item.asset_no ?? `equipment-${index}`}
                  item={item}
                />
              ))}
            </div>
            <div className="mt-3 max-md:hidden">
              <PortalListTable<PortalEquipment>
                screen="CWP-037"
                caption={t("portal.equipment.caption")}
                rows={rows}
                // The manufacturer's serial is the number on the box; our own
                // asset number is the fallback where none was recorded. Neither
                // is a database id (`BR-AST-026`).
                rowKey={(item) =>
                  item.serial_no ?? item.asset_no ?? `equipment-${rows.indexOf(item)}`
                }
                empty={
                  <p className="mt-2 text-body text-neutral-600" data-equipment-empty="">
                    {t("portal.equipment.none")}
                  </p>
                }
                // ⚠ **NO FOOTER, AND THE DRAWING SAYS SO IN SO MANY WORDS** —
                // `08-screen-layouts.md` CWP-037 ends *"Status (StatusChip …),
                // no footer"*. A household has two or three meters; a pager
                // over three rows is furniture standing on nothing, which is
                // the same judgement B14 rule 16 makes for a wizard summary
                // table. `CWP-039` is the other one.
                footer={false}
                // ⚠ **NO SEARCH AND NO ROW ICONS EITHER, FOR THE SAME REASON
                // AND ON THE SAME AUTHORITY.** The drawing gives this list
                // neither. Sorting is the one piece of furniture it does draw
                // and is what 34.3 asks for here.
                columns={[
                  {
                    key: "kind",
                    label: t("portal.equipment.colKind"),
                    sortable: true,
                    //  Sort on the words the customer can actually see — the
                    //  composed name, not a field one of them is built from.
                    sortValue: (item) => equipmentName(item, t),
                    // ⚠ **NAMED FOR WHAT IT IS, NOT FOR ITS TYPE ROW**
                    // (`DEF-CWP-3991`). `kind` is the tenant's own word for the
                    // TYPE and out of the seed that word is `Meter`, so a
                    // property with a water meter and an electric meter drew
                    // two rows reading `Meter` and only the serial told them
                    // apart. The CATALOGUE joins the two — never this file, and
                    // never the server (rule 35).
                    cell: (item) => (
                      <span data-kind={item.serial_no ?? item.asset_no ?? ""}>
                        {equipmentName(item, t)}
                      </span>
                    ),
                  },
                  {
                    key: "serial",
                    label: t("portal.equipment.colSerial"),
                    sortable: true,
                    sortValue: (item) => item.serial_no ?? item.asset_no,
                    cell: (item) => (
                      <span className="font-semibold" data-serial={item.serial_no ?? item.asset_no ?? ""}>
                        {item.serial_no ?? item.asset_no ?? ""}
                      </span>
                    ),
                  },
                  /* ⚠ **`WHERE` AND `LAST READ` USED TO BE COLUMNS HERE AND
                     ARE GONE (`CR-085` s52).** The Product Owner ruled on this
                     screen in so many words — *"just show IDs not details -
                     Equipment ... W-2209, 8841-C, F-0118 - this is enough +
                     account status"* — and the signed-off drawing agrees: its
                     table is `Equipment · Reference · Installed · Whose ·
                     Monthly`, with no location and no last-read cell in it. A
                     customer asking *which box is mine* is answered by the
                     reference printed on the box; `Front boundary box` and a
                     bare `2026-08-14` are the utility's own record, and
                     `CWP-034` one door away is where a reading belongs. */
                  {
                    key: "fitted",
                    label: t("portal.equipment.colFitted"),
                    sortable: true,
                    // ⚠ **THE SORT READS THE ISO DATE, NOT THE RENDERED
                    // `Aug 2026`.** Sorting the displayed month-and-year would
                    // put April before August in every year at once.
                    sortValue: (item) => item.fitted_on,
                    // `13-wireframe-delta.md` 37.5 — month and year, which is
                    // the density r10's list columns use and which
                    // `formatMonthYear` has served since CR-028.
                    cell: (item) => (
                      <span data-fitted={item.serial_no ?? item.asset_no ?? ""}>
                        {item.fitted_on ? formatMonthYear(item.fitted_on, "UTC") : "—"}
                      </span>
                    ),
                  },
                  /* ⚠ **`WHOSE` AND `MONTHLY` — `CPB-10`, THE TWO FACTS THIS
                     SCREEN WAS MISSING.** Screen 52's own question is *"what is
                     installed at my address, whose is it, and what am I paying
                     for it?"* and the table answered one third of it. The
                     drawing's table is `Equipment · Reference · Installed ·
                     Whose · Monthly` and these are the two that were not
                     there. */
                  {
                    key: "whose",
                    label: t("portal.equipment.colWhose"),
                    sortable: true,
                    sortValue: (item) => item.maintained_by,
                    cell: (item) => (
                      <WhoseCell item={item} shown={item.serial_no ?? item.asset_no ?? ""} />
                    ),
                  },
                  {
                    key: "monthly",
                    label: t("portal.equipment.colMonthly"),
                    cell: (item) => (
                      <MonthlyCell item={item} shown={item.serial_no ?? item.asset_no ?? ""} />
                    ),
                  },
                  {
                    key: "status",
                    label: t("portal.equipment.colStatus"),
                    cell: (item) => (
                      <StatusCell item={item} shown={item.serial_no ?? item.asset_no ?? ""} />
                    ),
                  },
                ]}
              />
            </div>
            {/* One sentence, and the route it names (B14 rule 32). The meter
                belongs to the utility, so the answer to *it is damaged* is
                never *fix it* — which is why the BOLD span is the instruction
                and not the reassurance (37.8), and why the button sits under
                the sentence inside the same box, where `CWP-037.png` draws it.
                `/report` is CWP-006 and is BUILT: this is a live door, not a
                hold. */}
            {/* ⚠ **THE COLUMN IS ONLY USEFUL IF THE WORDS ARE DEFINED, AND
                THE DRAWING DEFINES THEM RIGHT HERE** — *"Equipment marked Ours
                is maintained by us at no cost to you. Anything marked Yours is
                your responsibility to repair."* One sentence for the section
                (B14 rule 32); it is what settles a repair bill without anybody
                reading a policy. */}
            <p className="mt-3 text-base text-neutral-600" data-whose-note="">
              {t("portal.equipment.whoseNote", {
                ours: t("portal.equipment.whose.utility"),
                yours: t("portal.equipment.whose.customer"),
              })}
            </p>
            <div className="mt-3">
              <InfoBar
                lead={t("portal.equipment.noteLead")}
                bold={t("portal.equipment.noteBold")}
                tail={t("portal.equipment.noteTail")}
                below={
                  <ErrandLink label={t("portal.equipment.reportProblem")} to="/report" />
                }
              />
            </div>
          </>
        </Card>
      )}
    </div>
  );
}

/**
 * The drawing's PHONE row — *⚡ Electric meter · 8841-C · installed Jun 2,
 * 2026* — and nothing else.
 *
 * ⚠ **THE PRODUCT OWNER'S RULING IS WHAT DECIDES WHAT IS ON IT** — *"just show
 * IDs not details ... this is enough + account status"*. What the thing is,
 * the reference printed on it, when it went in, what state it is in.
 */
function EquipmentCard(props: { item: PortalEquipment }) {
  const { t } = useTranslation();
  const { item } = props;
  const reference = item.serial_no ?? item.asset_no ?? "";
  return (
    <div className="border border-neutral-200 p-3" data-equipment-card={reference}>
      {/* ⚠ **ONE COMPOSER FOR BOTH WIDTHS** (`DEF-CWP-4848`). Every item is
          drawn twice — once as a table row and once as this card — and a
          second copy of the name-and-size rule here is how the phone and the
          desktop start saying different things about one meter. */}
      <span className="text-h3 font-bold text-neutral-900" data-card-kind={reference}>
        {equipmentName(item, t)}
      </span>
      <p className="m-0 text-base font-semibold text-neutral-700" data-card-serial={reference}>
        {reference}
      </p>
      <div className="mt-2 flex flex-wrap items-end justify-between gap-2">
        {/* ⚠ **THE DATE IS LABELLED.** A card has no column heads, and a bare
            `Jan 2026` on a row about a meter could be read as anything — the
            drawing writes *installed Jun 2, 2026* for the same reason. The
            word is the TABLE'S own column label, so the two widths cannot say
            it differently. */}
        <span className="flex flex-col">
          <span className="text-xs font-bold uppercase tracking-wide text-neutral-600">
            {t("portal.equipment.colFitted")}
          </span>
          <span className="text-body text-neutral-700" data-card-fitted={reference}>
            {item.fitted_on ? formatMonthYear(item.fitted_on, "UTC") : "—"}
          </span>
        </span>
        {/* ⚠ **THE CARD MARKS ITS OWN CHIPS.** Every item is drawn twice —
            once here and once as a table row — and only one is ever visible,
            so two chips carrying `data-chip="status-W-2209"` would make every
            assertion written before today ambiguous (the shape
            `bills/Bills.tsx` records). */}
        <StatusCell item={item} shown={`card-${reference}`} />
      </div>
      {/* ⚠ **THE PHONE GETS THE SAME TWO FACTS, FROM THE SAME `item`**
          (`CPB-10`). One source for both widths, so a fact cannot be true at
          1280 and absent at 390 — which is the trap `Bills.tsx` records and
          which a per-width test would never see. The card labels its cells
          because a card has no column heads: a bare `$12.00` on a row about a
          fire line could be read as anything. */}
      <dl className="mt-2 flex flex-wrap gap-x-6 gap-y-1">
        <div className="flex flex-col">
          <dt className="text-xs font-bold uppercase tracking-wide text-neutral-600">
            {t("portal.equipment.colWhose")}
          </dt>
          <dd className="m-0 text-body text-neutral-700">
            <WhoseCell item={item} shown={`card-${reference}`} />
          </dd>
        </div>
        <div className="flex flex-col">
          <dt className="text-xs font-bold uppercase tracking-wide text-neutral-600">
            {t("portal.equipment.colMonthly")}
          </dt>
          <dd className="m-0 text-body text-neutral-700">
            <MonthlyCell item={item} shown={`card-${reference}`} />
          </dd>
        </div>
      </dl>
    </div>
  );
}

/**
 * `CPB-10`'s `Whose` — **Ours** or **Yours**, from a CODE.
 *
 * ⚠ **THE SERVER SHIPS `utility` / `customer` AND THE CATALOGUE WRITES THE
 * WORD** (B14 rule 35). *Ours* is not translatable from a server; it is barely
 * translatable at all without knowing who *we* are, which is exactly why it is
 * a catalogue line in each of eleven languages rather than a string on a wire.
 *
 * ⚠ **AN UNKNOWN CODE SAYS NOTHING RATHER THAN GUESSING.** The column is not
 * decoration — it decides who pays for a repair — so a value this screen does
 * not recognise draws blank instead of defaulting to *Ours*, which would be a
 * claim the product cannot support.
 */
function WhoseCell(props: { item: PortalEquipment; shown: string }) {
  const { t } = useTranslation();
  const key = WHOSE_KEY[props.item.maintained_by];
  if (key === undefined) return null;
  const mark = props.shown.startsWith("card-")
    ? { "data-card-whose": props.shown.slice(5) }
    : { "data-whose": props.shown };
  return <span {...mark}>{t(key)}</span>;
}

/**
 * `CPB-10`'s `Monthly` — and **the two absences it keeps apart**.
 *
 * ⚠ **THIS IS THE WHOLE REASON `charge_basis` TRAVELS AT ALL.**
 *   * `usage_only` → **No charge**, and it is a FACT: a meter is not what you
 *     pay for, the water is. The drawing prints exactly this.
 *   * `per_item` with a figure → the bill's own rate, at two places.
 *   * `per_item` with NO figure → a GAP, and it must NOT read *No charge* —
 *     that would be a false statement about money, on the customer's own
 *     screen, over a cart they are in fact paying for.
 * Collapsing the first and third into one `null` is the mistake this component
 * exists to make impossible. B14 rule 33 caps the refusal at five words.
 */
function MonthlyCell(props: { item: PortalEquipment; shown: string }) {
  const { t } = useTranslation();
  const { item } = props;
  const mark = props.shown.startsWith("card-")
    ? { "data-card-monthly": props.shown.slice(5) }
    : { "data-monthly": props.shown };
  if (item.charge_basis !== "per_item") {
    return <span {...mark}>{t("portal.equipment.noCharge")}</span>;
  }
  if (item.monthly_charge === null) {
    return (
      <span {...mark} className="text-neutral-600">
        {t("portal.equipment.chargeUnknown")}
      </span>
    );
  }
  return (
    <span {...mark} className="font-semibold">
      {t("portal.equipment.perMonth", { amount: item.monthly_charge })}
    </span>
  );
}

/**
 * What state the thing is in, in the reader's own language.
 *
 * ⚠ **THE CLASS TRAVELS AND THE CATALOGUE WRITES THE WORD (`DEF-CWP-3992`).**
 * This used to print `item.status` — the tenant's own lifecycle LABEL, which
 * out of the seed is `Installed/Active`. On a staff screen that is right and
 * `BR-AST-031` says so. On a customer screen served in eleven languages it is
 * a stored English lookup value with a slash in it, and ten catalogues cannot
 * write it. The behaviour class is the FACT — `billable_asset_count`'s own
 * docstring already says transitions and filters key off *"the class, never the
 * label"* — so the class is what this screen keys on too. An unrecognised class
 * falls back to the tenant's label, because saying the utility's word is better
 * than saying nothing.
 *
 * ⚠ **AND *TEST DUE NOV* IS DERIVED FROM THE CADENCE** (`BR-AST-007`), so it
 * is a DATE on the wire and a month in the reader's own language here — never
 * an English string shipped from a server (B14 rule 35).
 *
 * ⚠ **IT IS `test_due_on` AND NOT `test_due`, WHICH I CHECKED RATHER THAN
 * ASSUMED.** A future date looked like a false alarm until
 * `test_us_cwp_043_equipment.py` TC-3 settled it: the backflow device's next
 * test is 14 Nov 2026, `test_due` is `False` on 2 September, and the drawing
 * still paints `TEST DUE NOV` on that row. The chip says *due*, not *overdue*.
 *
 * ⚠ **ONE CHIP ON AN ORDINARY ROW, TWO WHEN SOMETHING IS ACTUALLY WRONG.**
 * `CWP-037.png` draws exactly one chip per row and the test-due row does not
 * also say `IN SERVICE`, so an in-service thing with a test coming shows the
 * test. Anything NOT in service keeps its state chip as well — hiding
 * *needs repair* behind *test due Nov* would be the drawing followed off a
 * cliff.
 */
function StatusCell(props: { item: PortalEquipment; shown: string }) {
  const { t, i18n } = useTranslation();
  const { item } = props;
  const due = item.test_due_on ? new Date(`${item.test_due_on}T00:00:00`) : null;
  const month =
    due !== null
      ? new Intl.DateTimeFormat(i18n.language, { month: "short" }).format(due).toUpperCase()
      : null;
  const key = STATE_KEY[item.behavior_class];
  const inService = item.behavior_class === "in_service";
  return (
    <span className="flex flex-col gap-1">
      {month !== null && inService ? null : (
        <StatusChip tone={inService ? "success" : "neutral"} testKey={`status-${props.shown}`}>
          {key === undefined ? item.status : t(key)}
        </StatusChip>
      )}
      {month ? (
        <StatusChip tone="warning" testKey={`test-due-${props.shown}`}>
          {t("portal.equipment.testDue", { month })}
        </StatusChip>
      ) : null}
    </span>
  );
}
