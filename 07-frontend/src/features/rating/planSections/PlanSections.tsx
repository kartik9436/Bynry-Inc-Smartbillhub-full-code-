// ── Trace ──────────────────────────────────────────────
// Change:   CR-167-BRC10 round 2 task 4 — THE ONE SHARED PLAN-SECTIONS
//           COMPONENT (ruling 11: *"similar to review page of add plan … how
//           you will align this"*; build note: *"one shared component for
//           both"*). The New form's Review (images 20–21) mounts it now; round
//           3's details Services / Charges / Billing tabs (images 26–30) mount
//           the same sections with `links` on.
// Defects:  DEF-RAT-9336 (the base shown is the code the bill uses, never the
//           catalogue) · DEF-RAT-9286 (no count above a section can contradict
//           its rows — no count is drawn) · DEF-RAT-9329 (a tax is one row,
//           named, with its authority under it)
// Rules:    ruling 8 (every referenced item shows a version pill and *from
//           MM/DD/YYYY*) · ruling 9 (Review is tables) · ruling 12 (*Base
//           charges* / *Usage charges* / *Monthly base charges*) · ruling 13
//           (every name is a link — on the details page) · B14 rules 20 (one
//           table type: the kit's `EditableTable`, read-only), 21, 31, 33, 43, 44
//           · CLAUDE.md hard rule 2 (money DISPLAYS 2 places, through
//           `formatMoney`; nothing here adds anything up)
// Tests:    src/features/rating/planSections/PlanSections.dom.test.tsx
// ───────────────────────────────────────────────────────
//
// ⚠ **IT DRAWS `PlanSections` AND NOTHING ELSE.** The details page reads that
// shape from `GET /plans/{id}?as_of=`; the New form builds it from its draft
// (`planFormModel.draftSections`). Neither screen draws a section of its own,
// so a plan cannot look one way on Review and another on its page.
//
// ⚠ **`show` CHOOSES WHICH SECTIONS, IN THE DRAWN ORDER, AND NOTHING ELSE.**
// Review shows all of them but the services totals strip (image 21); the
// details Services tab shows `services` + `servicesTotals` (image 27), Charges
// shows `charges` + `taxes` (29), Billing `deposits` + `discounts` +
// `billingTerms` (30). The order is the component's, never the caller's.
import type { ReactNode } from "react";
import { Link } from "react-router-dom";

import type {
  PlanChargeSection,
  PlanSectionDeposit,
  PlanDiscountSection,
  PlanGl,
  PlanNote,
  PlanPricedRow,
  PlanRef,
  PlanSections as PlanSectionsData,
  PlanServiceSection,
  PlanTaxSection,
  PlanUsageRow,
} from "@/api/planFormEndpoints";
import { formatDate } from "@/components/DateCell";
import type { RegionalDateFormat } from "@/components/DateCell";
import { EditableTable } from "@/components/EditableTable";
import type { EditableColumn } from "@/components/EditableTable";
import { FactBlock } from "@/components/FactBlock";
import { formatMoney } from "@/components/MoneyCell";
import { Panel } from "@/components/Panel";
import { useTenantPath } from "@/routing/tenantPath";

import { graceText } from "../chargeCodeParts";
import { definitionPath } from "../definitionDetail";
import { scheduleRoute } from "../RateSchedulesTab";
import { ServiceTags } from "../ratingShared";
import { sortBySize } from "../sizeOrder";
import type { Translator } from "../ratingShared";

export const PLAN_SECTION_IDS = [
  "plan",
  "services",
  "servicesTotals",
  "charges",
  "taxes",
  "deposits",
  "discounts",
  "billingTerms",
] as const;
export type PlanSectionId = (typeof PLAN_SECTION_IDS)[number];

/** What Review shows (image 21). */
export const REVIEW_SECTIONS: readonly PlanSectionId[] = [
  "plan",
  "services",
  "charges",
  "taxes",
  "deposits",
  "discounts",
  "billingTerms",
];

export interface PlanSectionsProps {
  sections: PlanSectionsData;
  show: readonly PlanSectionId[];
  t: Translator;
  dateFormat: RegionalDateFormat;
  timeZone: string;
  /** Every name is a link (ruling 13) — on the details page. Review leaves the
   *  names as text: following one would leave an unsaved form. */
  links: boolean;
  /** A section's *Edit*. Review opens that step; the details page opens that
   *  step of the Edit form (image 37). `service` names the service section. */
  onEdit?: (section: PlanSectionId, service?: string) => void;
  /**
   * **A SERVICE FOLDS TO ONE LINE — on the details page (ruling 13, images
   * 26–27).** Absent = every service is drawn open, which is Review (image 21).
   * Present = a service whose code is not in `open` draws its strip and ONE
   * line (*Base charges $10.00 – $40.00 · Usage charges $4.24 – $8.48 per
   * kgal*) with *Show sizes and blocks*; the caller owns `open` so its *Expand
   * all* opens every one. Added by lane PLAN-DETAIL (CR-167 r3 task 7), the
   * one consumer, under B14 rule 36.
   */
  fold?: {
    open: ReadonlySet<string>;
    onToggle: (service: string) => void;
    /** The folded line's two figures, worked out by the caller's model. */
    line: (section: PlanServiceSection) => { base: string; usage: string };
  };
  /**
   * **WHAT A SERVICE SECTION DRAWS UNDER ITS FACTS FOR ONE CALLER** — added
   * 2026-10-05 under B14 rule 36 with its first caller, the move-in's *See full
   * rates* (`CR-171-BRC10` P2.28, image 42: *Meters and devices on this
   * service*, the unit's meter → sub-meter → device tree, inside each
   * service). The tree is the UNIT's, not the plan's, so the caller hands it
   * in. Absent renders exactly what every existing caller rendered.
   */
  serviceExtra?: (section: PlanServiceSection) => ReactNode;
}

// ── Small pieces every section uses ─────────────────────────────────────────

const DASH = "—";

/** A money `*_display` (a bare 2-place figure) in the utility's currency. A
 *  value that is not a bare figure is the server's finished words and is shown
 *  as it came. */
export function moneyShown(display: string | null | undefined, currency: string | null): string {
  if (display === null || display === undefined || display === "") return DASH;
  if (currency === null || !/^-?\d+(\.\d+)?$/.test(display)) return display;
  return formatMoney(display, currency);
}

function glText(gl: PlanGl | null): string {
  return gl === null ? DASH : gl.name === "" ? gl.code : `${gl.code} · ${gl.name}`;
}

function dateShown(value: string | null, props: Pick<PlanSectionsProps, "dateFormat" | "timeZone">): string {
  return value === null || value === "" ? DASH : formatDate(value, props.timeZone, props.dateFormat);
}

/** Where a referenced item's own page is. */
export function refPath(ref: PlanRef): string {
  switch (ref.kind) {
    case "schedule":
      return scheduleRoute(ref.id);
    case "tax":
      return definitionPath("tax", ref.id);
    case "discount":
      return definitionPath("discount", ref.id);
    default:
      return definitionPath("charge", ref.id);
  }
}

/** *V2  from 09/01/2026* — ruling 8, on every referenced item. */
export function RefVersion(props: { item: PlanRef; t: Translator; dateFormat: RegionalDateFormat; timeZone: string }) {
  const { item, t } = props;
  return (
    <span className="mt-1 flex items-center gap-2 whitespace-nowrap text-sm text-neutral-700" data-ref-version={item.code}>
      {item.version !== null && (
        <span className="bg-neutral-300 px-1.5 font-heading text-xs font-semibold text-text" data-ref-pill="">
          {t("rating.taxes.list.version", { n: item.version })}
        </span>
      )}
      {item.effective_from !== null && (
        <span>{t("rating.planSections.from", { date: dateShown(item.effective_from, props) })}</span>
      )}
    </span>
  );
}

/** A referenced item's name: the CODE (a link on the details page) and its
 *  name after a dot, with the version line under it. */
export function RefName(props: {
  item: PlanRef;
  links: boolean;
  /** A schedule is named by its NAME (image 21), every code by its code. */
  byName?: boolean;
  t: Translator;
  dateFormat: RegionalDateFormat;
  timeZone: string;
}) {
  const tenantPath = useTenantPath();
  const { item } = props;
  const head = props.byName === true ? item.name || item.code : item.code;
  const tail = props.byName === true || item.name === "" || item.name === item.code ? null : item.name;
  return (
    <span className="flex flex-col" data-ref={item.kind}>
      <span>
        {props.links ? (
          <Link className="font-semibold text-accent underline" to={tenantPath(refPath(item))}>
            {head}
          </Link>
        ) : (
          <span className="font-semibold">{head}</span>
        )}
        {tail !== null && <span> · {tail}</span>}
      </span>
      <RefVersion item={item} t={props.t} dateFormat={props.dateFormat} timeZone={props.timeZone} />
    </span>
  );
}

function EditLink(props: { onEdit: (() => void) | undefined; t: Translator; label: string }) {
  if (props.onEdit === undefined) return null;
  return (
    <button
      type="button"
      className="bg-transparent p-0 font-semibold text-accent underline hover:text-text focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent"
      aria-label={props.t("rating.planSections.editSection", { section: props.label })}
      onClick={props.onEdit}
      data-section-edit=""
    >
      {props.t("rating.planSections.edit")}
    </button>
  );
}

function Trailing(props: { fact?: ReactNode; edit: ReactNode }) {
  return (
    <span className="flex items-center gap-2 text-base text-neutral-700">
      {props.fact}
      {props.edit}
    </span>
  );
}

/** Stacked lines in one cell — a code priced by class or size draws one line
 *  per class, and the amount cell beside it draws the same number of lines. */
function Lines(props: { lines: readonly string[]; name: string }) {
  return (
    <span className="flex flex-col gap-1" data-lines={props.name}>
      {props.lines.map((line, index) => (
        <span key={`${props.name}-${index}`}>{line}</span>
      ))}
    </span>
  );
}

// ── Plan facts ──────────────────────────────────────────────────────────────

const INTENDED_KEYS = ["cap_proof", "min_demand_25kw", "owner_occupied"] as const;

const NOTE_ATTRIBUTE_KEYS: Readonly<Record<string, string>> = {
  customer_class: "rating.plan.customerClassLabel",
  service: "rating.filter.service",
};

export function noteText(note: PlanNote, t: Translator): string {
  const attribute = NOTE_ATTRIBUTE_KEYS[note.attribute];
  const operator = t(`rating.plan.eligibility.operator.${note.operator}`, { defaultValue: note.operator });
  return `${attribute === undefined ? note.attribute : t(attribute)} ${operator} ${note.value}`;
}

function PlanFacts(props: PlanSectionsProps) {
  const { sections, t } = props;
  const details = sections.details;
  const intended = INTENDED_KEYS.filter((key) => details.intended_for[key]).map((key) =>
    t(`rating.planForm.intended.${key}`),
  );
  const rows: [string, string, string][] = [
    ["name", t("rating.planSections.plan.name"), details.name || DASH],
    ["code", t("rating.planSections.plan.code"), details.code || DASH],
    [
      "classes",
      t("rating.planSections.plan.classes"),
      details.customer_classes.length === 0
        ? t("rating.planForm.classes.every")
        : details.customer_classes.map((row) => row.label).join(", "),
    ],
    ["description", t("rating.planSections.plan.description"), details.description ?? DASH],
    ["intended", t("rating.planSections.plan.intended"), intended.length === 0 ? DASH : intended.join(", ")],
    [
      "notes",
      t("rating.planSections.plan.notes"),
      details.notes.length === 0 ? DASH : details.notes.map((note) => noteText(note, t)).join("; "),
    ],
  ];
  const title = t("rating.planSections.plan.title");
  return (
    <Panel
      as="section"
      title={title}
      trailing={<Trailing edit={<EditLink onEdit={props.onEdit && (() => props.onEdit?.("plan"))} t={t} label={title} />} />}
      data-plan-section="plan"
    >
      <dl className="m-0 border border-divider" data-plan-facts="">
        {rows.map(([id, label, value]) => (
          <div key={id} className="grid grid-cols-[200px_minmax(0,1fr)] border-b border-divider last:border-b-0" data-plan-fact={id}>
            <dt className="m-0 bg-neutral-100 px-3 py-2 text-base text-neutral-700">{label}</dt>
            <dd className="m-0 px-3 py-2 text-base">{value}</dd>
          </div>
        ))}
      </dl>
    </Panel>
  );
}

// ── One service ─────────────────────────────────────────────────────────────

interface BaseLine {
  key: string;
  size: string;
  base: string;
  minimum: string;
}

/** The base table's rows: one per size (base and minimum side by side), or
 *  *Every size* for a flat base. */
export function baseLines(section: PlanServiceSection, currency: string | null, t: Translator): BaseLine[] {
  const { base, minimum } = section;
  if (base.by_size.length > 0) {
    // `DEF-RAT-9507` — smallest size first (`sizeOrder.ts`), as `DEF-RAT-9503`
    // did for priced rows: the server serves sizes in CODE order (1" < 5/8").
    return sortBySize(base.by_size, (size) => size.size_label).map((size) => {
      const min = minimum.by_size.find((row) => row.size_class === size.size_class);
      return {
        key: size.size_class,
        size: size.size_label,
        base: moneyShown(size.amount_display, currency),
        minimum: moneyShown(min?.amount_display ?? minimum.flat_display, currency),
      };
    });
  }
  if (base.flat_display !== null) {
    return [
      {
        key: "flat",
        size: t("rating.planSections.service.everySize"),
        base: moneyShown(base.flat_display, currency),
        minimum: moneyShown(minimum.flat_display, currency),
      },
    ];
  }
  return [];
}

/** The base CODE a bill charges, or why there is no single one. */
function BaseCell(props: { section: PlanServiceSection } & Pick<PlanSectionsProps, "links" | "t" | "dateFormat" | "timeZone">) {
  const { base } = props.section;
  if (base.state === "ok" && base.code !== null) {
    return <RefName item={base.code} links={props.links} t={props.t} dateFormat={props.dateFormat} timeZone={props.timeZone} />;
  }
  if (base.state === "not_named") {
    // `DEF-RAT-9832` — the schedule names none: the bill charges `$0.00` (the
    // amount column says so) and nothing is taken from the pool.
    return (
      <span className="font-semibold" data-base-state="not_named">
        {props.t("rating.planSections.service.baseChooseCode")}
      </span>
    );
  }
  if (base.state === "ambiguous") {
    return (
      <span className="flex flex-col" data-base-state="ambiguous">
        <span className="font-semibold">{props.t("rating.planSections.service.baseChooseCode")}</span>
        {base.options.length === 0 ? (
          <span className="text-sm text-neutral-700">{base.codes.join(", ")}</span>
        ) : (
          // `DEF-RAT-9504` — which class pays which code (an every-class plan).
          base.options.map((option) => (
            <span key={option.code} className="text-sm text-neutral-700">
              {option.classes.length === 0 ? option.code : `${option.code} · ${option.classes.join(", ")}`}
            </span>
          ))
        )}
      </span>
    );
  }
  if (base.state === "refused") {
    return (
      <span className="font-semibold" data-base-state="refused">
        {props.t("rating.planSections.service.baseRefused")}
      </span>
    );
  }
  return (
    <span className="font-semibold" data-base-state="none">
      {props.t("rating.planSections.none")}
    </span>
  );
}

// ── The server's words, in the catalogue's (DEF-RAT-9502) ───────────────────
// The server sends finished English words (CR-167 §7.6) AND, since 2.486.2,
// the codes behind them. Each helper words the code from the catalogue and
// falls back to the server's English only for a code no catalogue names —
// which is what a German clerk read on every plan screen before.

const SIZED_BY_SERVICES = new Set(["trash", "fire"]);

/** *meter size*, *cart size*, *fire line size* — the base table's noun. */
export function sizedByWord(section: PlanServiceSection, t: Translator): string | null {
  const label = section.base.sized_by_label;
  if (label === null) return null;
  const which = SIZED_BY_SERVICES.has(section.service) ? section.service : "meter";
  return t(`rating.planSections.sizedBy.${which}`, { defaultValue: label });
}

/** *Block (per month)*, *Per cart, per month* — the usage table's kind. */
export function usageKindWord(section: PlanServiceSection, t: Translator): string | null {
  const { kind, kind_label: label } = section.usage;
  if (label === null) return null;
  const which = kind === "per_size" && SIZED_BY_SERVICES.has(section.service) ? `per_size_${section.service}` : kind;
  return which === "" ? label : t(`rating.planSections.usageKind.${which}`, { defaultValue: label });
}

/** `DEF-RAT-9507` — a per-size usage table (carts, fire lines) reads smallest
 *  size first; blocks and seasons keep the served order, which is their order. */
export function usageRowsInOrder(usage: { kind: string; rows: readonly PlanUsageRow[] }): PlanUsageRow[] {
  return usage.kind === "per_size" ? sortBySize(usage.rows, (row) => row.label) : [...usage.rows];
}

/** `DEF-RAT-9509` — a service in the screen's language: the catalogue's word
 *  for its code, the server's (English) name only where no catalogue has one. */
export function serviceWord(service: string, name: string, t: Translator): string {
  return t(`rating.service.${service}`, { defaultValue: name });
}

/** One usage row's first cell: *Over 500 kWh*, *Each month*, a size's name. */
export function usageRowLabel(row: PlanUsageRow, t: Translator): string {
  const key = row.label_key ?? null;
  if (key === null) return row.label;
  const args: Record<string, string> = { ...(row.label_args ?? {}) };
  if (key === "share" && args.service !== undefined) {
    args.service = t(`rating.service.${args.service}`, { defaultValue: args.service });
  }
  const word = t(`rating.planSections.usageRow.${key}`, { ...args, defaultValue: row.label });
  return row.season ? `${row.season} · ${word}` : word;
}

/** One usage row's rate: *$0.11 per kWh* in the language. */
export function usageRowRate(row: PlanUsageRow, t: Translator): string {
  if (row.rate_amount && row.rate_unit) {
    return t("rating.planSections.usageRow.per", { amount: row.rate_amount, unit: row.rate_unit });
  }
  return row.rate_display;
}

/** A price row's class or size, or *Everyone* in the catalogue's word. */
export function classOrSizeWord(row: PlanPricedRow, t: Translator): string {
  return row.everyone === true || !row.class_or_size_label ? t("rating.planSections.everyone") : row.class_or_size_label;
}

/** *Every bill*, *After the due date* — when a charge code is charged. */
export function whenWord(row: PlanChargeSection, t: Translator): string {
  if (row.when_label === null) return DASH;
  return row.type_label ? t(`rating.planSections.when.${row.type_label}`, { defaultValue: row.when_label }) : row.when_label;
}

/** PO 2026-10-06 11 (a) — a penalty code's late-fee grace, shown beside its
 *  *When*: *Grace: 5 calendar days*; `(this plan)` for an override the plan
 *  stated before the ruling, which still applies. `null` for any other code. */
export function graceLine(row: Pick<PlanChargeSection, "grace">, t: Translator): string | null {
  if (!row.grace) return null;
  const grace = graceText(t, row.grace.days, row.grace.mode);
  return t(row.grace.from === "plan" ? "rating.planSections.graceOnPlan" : "rating.planSections.graceLine", { grace });
}

/** *Usage and base charges* — what a tax is levied on. */
/** `DEF-RAT-9519` — a tax none of the plan's classes pays is listed, marked
 *  and left out of *combined*; never refused (a plan's classes may widen). */
export function TaxNotCharged(props: { row: Pick<PlanTaxSection, "reaches_plan_classes">; t: Translator }) {
  if (props.row.reaches_plan_classes !== "none") return null;
  return (
    <span className="text-sm text-warning-700" data-tax-not-charged="">
      {props.t("rating.planSections.taxes.notCharged")}
    </span>
  );
}

export function taxedWord(row: PlanTaxSection, t: Translator): string {
  const codes = row.what_is_taxed ?? [];
  if (codes.includes("usage") && codes.includes("base")) {
    return t("rating.planSections.taxed.both", { defaultValue: row.what_is_taxed_label ?? DASH });
  }
  if (codes.length === 1 && (codes[0] === "usage" || codes[0] === "base")) {
    return t(`rating.taxForm.taxed.${codes[0]}`, { defaultValue: row.what_is_taxed_label ?? DASH });
  }
  return row.what_is_taxed_label ?? DASH;
}

function ServiceSection(props: PlanSectionsProps & { section: PlanServiceSection }) {
  const { section, sections, t } = props;
  const currency = sections.currency;
  const lines = baseLines(section, currency, t);
  const sizedBy = sizedByWord(section, t);
  const baseHeading =
    sizedBy === null
      ? t("rating.planSections.service.baseHeading")
      : t("rating.planSections.service.baseBy", { size: sizedBy });
  const kindWord = usageKindWord(section, t);
  const usageHeading =
    kindWord === null
      ? t("rating.planSections.service.usageHeading")
      : t("rating.planSections.service.usageKind", { kind: kindWord });
  const baseColumns: EditableColumn<BaseLine>[] = [
    { key: "size", label: baseHeading, cell: (row) => row.size },
    { key: "base", label: t("rating.planSections.service.baseCharge"), numeric: true, cell: (row) => row.base },
    { key: "minimum", label: t("rating.planSections.service.minimum"), numeric: true, cell: (row) => row.minimum },
  ];
  const usageColumns: EditableColumn<PlanUsageRow>[] = [
    { key: "label", label: usageHeading, cell: (row) => usageRowLabel(row, t) },
    { key: "rate", label: t("rating.planSections.service.rate"), numeric: true, cell: (row) => usageRowRate(row, t) },
  ];
  const title = (
    <span className="flex items-center gap-2">
      <ServiceTags services={[section.service]} />
      {serviceWord(section.service, section.name, t)}
    </span>
  );
  return (
    <Panel
      as="section"
      title={title}
      trailing={
        <Trailing
          fact={section.gl === null ? undefined : <span>{t("rating.planSections.service.gl", { code: section.gl.code })}</span>}
          edit={
            <EditLink
              onEdit={props.onEdit && (() => props.onEdit?.("services", section.service))}
              t={t}
              label={serviceWord(section.service, section.name, t)}
            />
          }
        />
      }
      data-plan-section="service"
      data-plan-service={section.service}
    >
      <div className="flex flex-col gap-4">
        <FactBlock
          name={`service-${section.service}`}
          variant="strip"
          columns={3}
          facts={[
            {
              id: "schedule",
              label: t("rating.planSections.service.schedule"),
              value:
                section.schedule === null ? (
                  DASH
                ) : (
                  <RefName
                    item={section.schedule}
                    byName
                    links={props.links}
                    t={t}
                    dateFormat={props.dateFormat}
                    timeZone={props.timeZone}
                  />
                ),
            },
            {
              id: "base",
              label: t("rating.planSections.service.baseCharges"),
              value: <BaseCell section={section} links={props.links} t={t} dateFormat={props.dateFormat} timeZone={props.timeZone} />,
            },
            {
              id: "outside",
              label: t("rating.planSections.service.outsideCity"),
              value:
                section.outside_city.surcharged && section.outside_city.percent_display !== null
                  ? `+${section.outside_city.percent_display}`
                  : t("rating.planSections.service.samePrice"),
            },
          ]}
        />
        {props.serviceExtra?.(section)}
        {props.fold !== undefined && (
          <FoldBar
            section={section}
            open={props.fold.open.has(section.service)}
            onToggle={props.fold.onToggle}
            line={props.fold.line(section)}
            t={t}
          />
        )}
        {(props.fold === undefined || props.fold.open.has(section.service)) && (
        <div className="grid grid-cols-2 items-start gap-3" data-service-tables={section.service}>
          <EditableTable<BaseLine>
            readOnly
            caption=""
            numbered={false}
            reorderable={false}
            columns={baseColumns}
            rows={lines}
            rowKey={(row) => row.key}
            emptyText={t("rating.planSections.service.noBase")}
            data-collection={`base-${section.service}`}
          />
          <EditableTable<PlanUsageRow>
            readOnly
            caption=""
            numbered={false}
            reorderable={false}
            columns={usageColumns}
            rows={usageRowsInOrder(section.usage)}
            rowKey={(row, index) => `${row.label}-${index}`}
            emptyText={t("rating.planSections.service.noUsage")}
            data-collection={`usage-${section.service}`}
          />
        </div>
        )}
      </div>
    </Panel>
  );
}

/** The folded line and its toggle (images 26–27). Open, the line is gone and
 *  the tables say it in full. */
function FoldBar(props: {
  section: PlanServiceSection;
  open: boolean;
  onToggle: (service: string) => void;
  line: { base: string; usage: string };
  t: Translator;
}) {
  const { t, section } = props;
  return (
    <div className="flex items-baseline justify-between gap-4" data-service-fold={section.service}>
      {props.open ? (
        <span />
      ) : (
        <span className="text-base" data-service-line={section.service}>
          <strong className="font-semibold">{t("rating.planSections.service.baseCharges")}</strong> {props.line.base}
          <span aria-hidden="true"> · </span>
          <strong className="font-semibold">{t("rating.planSections.service.usageHeading")}</strong> {props.line.usage}
        </span>
      )}
      <button
        type="button"
        className="whitespace-nowrap bg-transparent p-0 font-semibold text-accent underline hover:text-text focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent"
        aria-expanded={props.open}
        onClick={() => props.onToggle(section.service)}
        data-service-toggle={section.service}
      >
        {props.open ? t("rating.planSections.service.hideSizes") : t("rating.planSections.service.showSizes")}{" "}
        <span aria-hidden="true">{props.open ? "▴" : "▾"}</span>
      </button>
    </div>
  );
}

function surchargedNames(sections: PlanSectionsProps["sections"], served: string[], t: Translator): string[] {
  const words = sections.services
    .filter((line) => line.outside_city.surcharged)
    .map((line) => serviceWord(line.service, line.name, t));
  return words.length > 0 ? words : served;
}

function ServicesTotals(props: PlanSectionsProps) {
  const { sections, t } = props;
  const surcharge = sections.outside_city_surcharge;
  return (
    <Panel as="section" data-plan-section="servicesTotals">
      <FactBlock
        name="services-totals"
        variant="strip"
        columns={3}
        facts={[
          {
            id: "monthly",
            label: t("rating.planSections.terms.monthly"),
            value: moneyShown(sections.base_total.amount_display, sections.currency),
          },
          {
            id: "surcharge",
            label: t("rating.planSections.terms.surcharge"),
            value:
              surcharge === null
                ? t("rating.planSections.none")
                : t("rating.planSections.terms.surchargeOn", {
                    percent: surcharge.percent_display,
                    // `DEF-RAT-9518` — the services in the screen's language
                    // (`serviceWord`), the server's English names only as fallback.
                    services: surchargedNames(sections, surcharge.service_names, t).join(", "),
                  }),
          },
        ]}
      />
    </Panel>
  );
}

// ── Codes, taxes, deposits, discounts ───────────────────────────────────────

const PRICED_BY_KEYS: Readonly<Record<string, string>> = {
  class: "rating.planSections.pricedBy.class",
  size: "rating.planSections.pricedBy.size",
  one_amount: "rating.planSections.pricedBy.one_amount",
  percent: "rating.planSections.pricedBy.percent",
};

export function pricedByText(pricedBy: string, t: Translator): string {
  const key = PRICED_BY_KEYS[pricedBy];
  return key === undefined ? pricedBy : t(key);
}

/** One priced row's amount: `$75.00`, `1.50% · min $5.00`. */
export function pricedAmount(row: PlanPricedRow, currency: string | null, t: Translator): string {
  const head = row.percent_display ?? (row.amount_display === null ? null : moneyShown(row.amount_display, currency));
  if (head === null) return DASH;
  return row.min_display === null
    ? head
    : t("rating.planSections.withMin", { amount: head, min: moneyShown(row.min_display, currency) });
}

/** `DEF-RAT-9503` — a code priced BY SIZE reads smallest size first, by the
 *  size its name states (`sizeOrder.ts`): the server serves price rows in CODE
 *  order, so `W-2` ($600.00) arrived above `W-58` ($150.00). Rows priced by
 *  class keep the served order. One helper for the sections and the form. */
export function pricedRowsInOrder(item: { priced_by: string; rows: readonly PlanPricedRow[] }): readonly PlanPricedRow[] {
  return item.priced_by === "size" ? sortBySize(item.rows, (row) => row.class_or_size_label) : item.rows;
}

function classLines(rows: readonly PlanPricedRow[], t: Translator): string[] {
  return rows.length === 0
    ? [DASH]
    : rows.map((row) => classOrSizeWord(row, t));
}

function SectionPanel(props: {
  id: PlanSectionId;
  title: string;
  fact?: ReactNode;
  owner: PlanSectionsProps;
  children: ReactNode;
}) {
  return (
    <Panel
      as="section"
      title={props.title}
      trailing={
        <Trailing
          fact={props.fact}
          edit={<EditLink onEdit={props.owner.onEdit && (() => props.owner.onEdit?.(props.id))} t={props.owner.t} label={props.title} />}
        />
      }
      data-plan-section={props.id}
    >
      {props.children}
    </Panel>
  );
}

function ChargeCodes(props: PlanSectionsProps) {
  const { sections, t } = props;
  const currency = sections.currency;
  const columns: EditableColumn<PlanChargeSection>[] = [
    {
      key: "code",
      label: t("rating.planSections.col.code"),
      cell: (row) => <RefName item={row.ref} links={props.links} t={t} dateFormat={props.dateFormat} timeZone={props.timeZone} />,
    },
    { key: "pricedBy", label: t("rating.planSections.col.pricedBy"), cell: (row) => pricedByText(row.priced_by, t) },
    { key: "classOrSize", label: t("rating.planSections.col.classOrSize"), cell: (row) => <Lines name="class" lines={classLines(pricedRowsInOrder(row), t)} /> },
    {
      key: "amount",
      label: t("rating.planSections.col.amount"),
      numeric: true,
      cell: (row) => <Lines name="amount" lines={row.rows.length === 0 ? [DASH] : pricedRowsInOrder(row).map((line) => pricedAmount(line, currency, t))} />,
    },
    { key: "gl", label: t("rating.planSections.col.gl"), cell: (row) => glText(row.gl) },
    {
      key: "when",
      label: t("rating.planSections.col.when"),
      cell: (row) => {
        const grace = graceLine(row, t);
        return grace === null ? whenWord(row, t) : <Lines name="when" lines={[whenWord(row, t), grace]} />;
      },
    },
  ];
  return (
    <SectionPanel id="charges" title={t("rating.planSections.charges.title")} owner={props}>
      <EditableTable<PlanChargeSection>
        readOnly
        caption=""
        numbered={false}
        reorderable={false}
        columns={columns}
        rows={sections.charge_codes}
        rowKey={(row) => row.ref.id}
        emptyText={t("rating.planSections.charges.empty")}
        data-collection="plan-charges"
      />
    </SectionPanel>
  );
}

function Taxes(props: PlanSectionsProps) {
  const { sections, t } = props;
  const columns: EditableColumn<PlanTaxSection>[] = [
    {
      key: "tax",
      label: t("rating.planSections.col.tax"),
      cell: (row) => (
        <span className="flex flex-col">
          <RefName item={row.ref} byName links={props.links} t={t} dateFormat={props.dateFormat} timeZone={props.timeZone} />
          {row.authority !== null && <span className="text-sm text-neutral-700">{row.authority}</span>}
          <TaxNotCharged row={row} t={t} />
        </span>
      ),
    },
    { key: "rate", label: t("rating.planSections.col.rate"), numeric: true, cell: (row) => row.rate_display ?? DASH },
    { key: "taxed", label: t("rating.planSections.col.whatIsTaxed"), cell: (row) => taxedWord(row, t) },
    { key: "gl", label: t("rating.planSections.col.gl"), cell: (row) => glText(row.gl) },
  ];
  return (
    <SectionPanel
      id="taxes"
      title={t("rating.planSections.taxes.title")}
      fact={
        sections.combined_tax_rate_display === null ? undefined : (
          <span data-plan-combined="">{t("rating.planSections.taxes.combined", { rate: sections.combined_tax_rate_display })}</span>
        )
      }
      owner={props}
    >
      <EditableTable<PlanTaxSection>
        readOnly
        caption=""
        numbered={false}
        reorderable={false}
        columns={columns}
        rows={sections.taxes}
        rowKey={(row) => row.ref.id}
        emptyText={t("rating.planSections.taxes.empty")}
        data-collection="plan-taxes"
      />
    </SectionPanel>
  );
}

function Deposits(props: PlanSectionsProps) {
  const { sections, t } = props;
  const currency = sections.currency;
  const columns: EditableColumn<PlanSectionDeposit>[] = [
    {
      key: "deposit",
      label: t("rating.planSections.col.deposit"),
      // DEF-RAT-9740 — a typed rule (`ref: null`) is the plan's own figure with
      // no code behind it: named by the column's own word, nothing to link.
      cell: (row) =>
        row.ref === null ? (
          t("rating.planSections.col.deposit")
        ) : (
          <RefName item={row.ref} links={props.links} t={t} dateFormat={props.dateFormat} timeZone={props.timeZone} />
        ),
    },
    { key: "pricedBy", label: t("rating.planSections.col.pricedBy"), cell: (row) => pricedByText(row.priced_by, t) },
    { key: "classOrSize", label: t("rating.planSections.col.classOrSize"), cell: (row) => <Lines name="class" lines={classLines(pricedRowsInOrder(row), t)} /> },
    {
      key: "amount",
      label: t("rating.planSections.col.amount"),
      numeric: true,
      cell: (row) => <Lines name="amount" lines={row.rows.length === 0 ? [DASH] : pricedRowsInOrder(row).map((line) => pricedAmount(line, currency, t))} />,
    },
    { key: "gl", label: t("rating.planSections.col.gl"), cell: (row) => glText(row.gl) },
  ];
  return (
    <SectionPanel id="deposits" title={t("rating.planSections.deposits.title")} owner={props}>
      <EditableTable<PlanSectionDeposit>
        readOnly
        caption=""
        numbered={false}
        reorderable={false}
        columns={columns}
        rows={sections.deposits}
        rowKey={(row, index) => row.ref?.id ?? `typed-${index}`}
        emptyText={t("rating.planSections.deposits.empty")}
        data-collection="plan-deposits"
      />
    </SectionPanel>
  );
}

function Discounts(props: PlanSectionsProps) {
  const { sections, t } = props;
  const columns: EditableColumn<PlanDiscountSection>[] = [
    {
      key: "discount",
      label: t("rating.planSections.col.discount"),
      cell: (row) => <RefName item={row.ref} links={props.links} t={t} dateFormat={props.dateFormat} timeZone={props.timeZone} />,
    },
    { key: "value", label: t("rating.planSections.col.value"), numeric: true, cell: (row) => row.value_display ?? DASH },
    { key: "from", label: t("rating.planSections.col.offeredFrom"), cell: (row) => dateShown(row.offered_from, props) },
    {
      key: "until",
      label: t("rating.planSections.col.offeredUntil"),
      cell: (row) => (row.offered_until === null ? t("rating.planSections.noEnd") : dateShown(row.offered_until, props)),
    },
    { key: "gl", label: t("rating.planSections.col.gl"), cell: (row) => glText(row.gl) },
    {
      key: "enrolled",
      label: t("rating.planSections.col.enrolled"),
      numeric: true,
      cell: (row) => (row.enrolled === null ? DASH : String(row.enrolled)),
    },
  ];
  return (
    <SectionPanel id="discounts" title={t("rating.planSections.discounts.title")} owner={props}>
      <EditableTable<PlanDiscountSection>
        readOnly
        caption=""
        numbered={false}
        reorderable={false}
        columns={columns}
        rows={sections.discounts}
        rowKey={(row) => row.ref.id}
        emptyText={t("rating.planSections.discounts.empty")}
        data-collection="plan-discounts"
      />
    </SectionPanel>
  );
}

function BillingTerms(props: PlanSectionsProps) {
  const { sections, t } = props;
  return (
    <SectionPanel id="billingTerms" title={t("rating.planSections.terms.title")} owner={props}>
      <FactBlock
        name="billing-terms"
        variant="strip"
        columns={3}
        facts={[
          {
            id: "monthly",
            label: t("rating.planSections.terms.monthly"),
            value: moneyShown(sections.base_total.amount_display, sections.currency),
          },
          {
            id: "minimum",
            label: t("rating.planSections.terms.minimum"),
            value:
              sections.details.minimum_bill_display === null
                ? t("rating.planSections.none")
                : moneyShown(sections.details.minimum_bill_display, sections.currency),
          },
          {
            id: "budget",
            label: t("rating.planSections.terms.budget"),
            value: sections.details.budget_billing
              ? t("rating.planSections.terms.offered")
              : t("rating.planSections.terms.notOffered"),
          },
        ]}
      />
    </SectionPanel>
  );
}

// ── The component ───────────────────────────────────────────────────────────

export function PlanSections(props: PlanSectionsProps) {
  const shown = (id: PlanSectionId) => props.show.includes(id);
  return (
    <div className="flex flex-col gap-5" data-plan-sections="">
      {shown("plan") && <PlanFacts {...props} />}
      {shown("services") &&
        props.sections.services.map((section) => <ServiceSection key={section.service} {...props} section={section} />)}
      {shown("servicesTotals") && <ServicesTotals {...props} />}
      {shown("charges") && <ChargeCodes {...props} />}
      {shown("taxes") && <Taxes {...props} />}
      {shown("deposits") && <Deposits {...props} />}
      {shown("discounts") && <Discounts {...props} />}
      {shown("billingTerms") && <BillingTerms {...props} />}
    </div>
  );
}
