// ── Trace ──────────────────────────────────────────────
// Drawing:  05-prototype/bulk-bill-run-2026-09-30/inventory.md §9 — "build once,
//           use many": fact cards, severity marks, the progress panel, the side
//           list panel, the problem boxes
// Plan:     15-bulk-bill-run-build-plan.md F3–F19
// Rules:    B14 rules 21 (Tailwind only — this file is on route-b-migrated.txt),
//           31, 32 (a stated absence), 33, 36, 43 (components, not inline code),
//           44 (our spacing, type and tokens win over the drawing's pixels)
// ───────────────────────────────────────────────────────
/**
 * The bulk run's repeated pieces. Each appears on two or more steps in the
 * drawing, so each is ONE component here (rule 43). Money, dates, the
 * collapsible panel and the figure table are the one-time bill's, imported
 * from `oneTimeBillShared.tsx` rather than written a second time.
 */
import type { ReactNode } from "react";
import { useEffect, useRef } from "react";

import type { Severity } from "@/api/bulkRunEndpoints";
import type { Translator } from "@/components/FormModal";
import { ChipToggle } from "@/components/Chip";
import { Panel } from "@/components/Panel";
import { StatusPill } from "@/components/StatusPill";
import { Kicker } from "@/components/TextBits";
import type { StatusTone } from "@/components/StatusPill";

export type { OtbFormat as RunFormat } from "../oneTimeBill/oneTimeBillShared";
export {
  CollapsiblePanel,
  OTB_TABLE as RUN_TABLE,
  PanelAside,
  ServiceLabel,
  TableScroll,
  day,
  money,
  span,
} from "../oneTimeBill/oneTimeBillShared";

/** The page's address, tenant-relative — the Bills page's `Run` door. */
export { BILL_RUN_ROUTE as BULK_RUN_ROUTE, RUN_PARAM } from "../billRunShared";

export const STEP_PARAM = "step";

/** DEF-BIL-8691 — a day of the month as the drawing writes it, `1st` (D1 01),
 *  through the catalogue's ordinal forms (`billing.bulkRun.ordinal_ordinal_*`). */
export function ordinalDay(day: number, t: (key: string, options?: Record<string, unknown>) => string): string {
  return t("billing.bulkRun.ordinal", { count: day, ordinal: true });
}

/** DEF-BIL-8700 — a row's place on one line, as D1 14 and 20 write it:
 *  `1487 Hill Dr · Unit A`. Null when the row has neither half. */
export function placeLine(row: { address: string | null; unit_label: string | null }): string | null {
  const parts = [row.address, row.unit_label].filter((part): part is string => !!part);
  return parts.length === 0 ? null : parts.join(" · ");
}

/** Whole numbers with the tenant's grouping — `1,406`. */
export function count(value: number | null | undefined): string {
  return value === null || value === undefined ? "—" : value.toLocaleString("en-US");
}

// ── Kicker — the kit's (B14 rule 36; G104) ──────────────────────────────────

export { Kicker };

// ── A stated absence (B14 rule 32) ──────────────────────────────────────────

/**
 * A figure or a control the drawing shows that nothing serves yet. It says so
 * in four words and never renders a zero or a dash, which would each claim an
 * answer. The defect that holds it is in the file that renders it, not on
 * screen (rule 33: rationale is zero words).
 */
export function NotAvailable(props: { t: Translator; id: string }) {
  return (
    <span className="text-base text-neutral-600" role="note" data-absent={props.id}>
      {props.t("billing.bulkRun.notAvailable")}
    </span>
  );
}

// ── Fact cards (Cycle details · This run covers · Run summary) ─────────────

export interface FactCardItem {
  id: string;
  label: string;
  value: ReactNode;
  note?: ReactNode;
  wide?: boolean;
}

export function FactCards(props: { name: string; items: readonly FactCardItem[] }) {
  return (
    <dl className="m-0 grid grid-cols-4 gap-3" data-run-facts={props.name}>
      {props.items.map((item) => (
        <div
          key={item.id}
          className={`m-0 border border-divider bg-surface px-3 py-3 ${item.wide === true ? "col-span-2" : ""}`}
          data-run-fact={item.id}
        >
          <dt className="font-heading text-xs uppercase tracking-label text-neutral-700">{item.label}</dt>
          <dd className="m-0 mt-1 font-heading text-md font-semibold">{item.value}</dd>
          {item.note !== undefined && <dd className="m-0 mt-1 text-sm text-neutral-700">{item.note}</dd>}
        </div>
      ))}
    </dl>
  );
}

// ── Severity (a square, a pill) ─────────────────────────────────────────────

const SQUARE: Record<Severity | "ok", string> = {
  blocks: "bg-danger-700",
  decision: "bg-warning-700",
  warning: "bg-info-700",
  ok: "bg-success-700",
};

export function SeverityMark(props: { severity: Severity | "ok" }) {
  return <span aria-hidden="true" className={`inline-block h-2.5 w-2.5 shrink-0 ${SQUARE[props.severity]}`} />;
}

const TONE: Record<Severity | "ok", StatusTone> = {
  blocks: "danger",
  decision: "warning",
  warning: "info",
  ok: "success",
};

export function severityTone(severity: Severity | "ok"): StatusTone {
  return TONE[severity];
}

export function SeverityPill(props: { severity: Severity | "ok"; t: Translator }) {
  return (
    <StatusPill tone={TONE[props.severity]}>{props.t(`billing.bulkRun.severity.${props.severity}`)}</StatusPill>
  );
}

/** The tag's clerk name — the drawn name (inventory §3.3). */
export function tagName(tagId: string, t: Translator): string {
  return t(`billing.bulkRun.tag.${tagId}.name`);
}

export function tagMeaning(tagId: string, t: Translator): string {
  return t(`billing.bulkRun.tag.${tagId}.meaning`);
}

export function categoryName(categoryId: string, t: Translator): string {
  return t(`billing.bulkRun.category.${categoryId}`);
}

/** A chip naming another tag an account carries — pressing it opens that tag. */
export function TagChip(props: { code: string; severity: Severity; label: string; onOpen: (code: string) => void }) {
  const tone =
    props.severity === "blocks" ? "text-danger-700" : props.severity === "decision" ? "text-warning-700" : "text-info-700";
  return (
    <ChipToggle selected={false} className={tone} data-also-has={props.code} onClick={() => props.onOpen(props.code)}>
      {props.label}
    </ChipToggle>
  );
}

// ── Progress (Checking · Calculating · Sending) ────────────────────────────

export function ProgressPanel(props: {
  name: string;
  title: string;
  /** `n of N` when a job reports it; absent when nothing does (DEF-BIL-8224). */
  progress: { done: number; total: number } | null;
  note: string;
  t: Translator;
}) {
  const { progress } = props;
  const percent =
    progress === null || progress.total === 0 ? null : Math.min(100, Math.round((progress.done / progress.total) * 100));
  return (
    <Panel
      as="section"
      title={props.title}
      aria-label={props.title}
      trailing={
        progress === null ? undefined : (
          <Kicker as="div">{props.t("billing.bulkRun.progress.of", { done: count(progress.done), total: count(progress.total) })}</Kicker>
        )
      }
      data-run-progress={props.name}
    >
      <progress
        className={
          "mt-3 block h-2 w-full appearance-none border-0 bg-neutral-200 accent-accent " +
          "[&::-webkit-progress-bar]:bg-neutral-200 [&::-webkit-progress-value]:bg-accent [&::-moz-progress-bar]:bg-accent"
        }
        aria-label={props.title}
        {...(percent === null ? {} : { value: percent, max: 100 })}
      />
      <p className="m-0 mt-3 text-base text-neutral-700">{props.note}</p>
    </Panel>
  );
}

// ── The side list panel (Nobody to bill · Missing meter · Fix account · Failed to draft)

export function SidePanel(props: {
  name: string;
  kicker: string;
  title: ReactNode;
  note?: string;
  closeLabel: string;
  onClose: () => void;
  children: ReactNode;
  footer?: ReactNode;
}) {
  const closeRef = useRef<HTMLButtonElement | null>(null);
  useEffect(() => {
    closeRef.current?.focus();
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") props.onClose();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  return (
    <div className="fixed inset-0 z-40 flex justify-end" data-run-panel={props.name}>
      <button
        type="button"
        aria-label={props.closeLabel}
        tabIndex={-1}
        className="absolute inset-0 cursor-default border-0 bg-text/40"
        onClick={props.onClose}
      />
      <div
        role="dialog"
        aria-modal="true"
        aria-label={props.kicker}
        className="relative flex h-full w-160 max-w-full flex-col overflow-y-auto bg-bg p-5"
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <Kicker as="div">{props.kicker}</Kicker>
            <h2 className="m-0 mt-1 font-heading text-h4 font-semibold">{props.title}</h2>
            {props.note !== undefined && <p className="m-0 mt-1 text-base text-neutral-700">{props.note}</p>}
          </div>
          <button
            ref={closeRef}
            type="button"
            className="flex h-8 w-8 shrink-0 cursor-pointer items-center justify-center border border-text bg-bg"
            aria-label={props.closeLabel}
            onClick={props.onClose}
            data-run-panel-close=""
          >
            <span aria-hidden="true">✕</span>
          </button>
        </div>
        <div className="mt-4">{props.children}</div>
        {props.footer !== undefined && (
          <div className="mt-4 flex items-center justify-end gap-3 border-t border-divider pt-4">{props.footer}</div>
        )}
      </div>
    </div>
  );
}

// ── The two problem boxes at the top of Scope (changes row 35) ─────────────

export interface ProblemLine {
  key: string;
  /** The field this line is about — a link that focuses it; `null` = no field. */
  field: string | null;
  fieldLabel: string;
  message: string;
  link?: { label: string; onPress: () => void } | { label: string; href: string };
}

export function ProblemBox(props: {
  tone: "refusal" | "warning";
  title: string;
  lines: readonly ProblemLine[];
}) {
  if (props.lines.length === 0) return null;
  const refusal = props.tone === "refusal";
  return (
    <div
      className={`px-4 py-3 text-base ${refusal ? "bg-danger-100 text-danger-700" : "bg-warning-100 text-warning-700"}`}
      role={refusal ? "alert" : "status"}
      data-run-problems={props.tone}
    >
      <p className="m-0 font-heading font-semibold">{props.title}</p>
      <ul className="m-0 mt-1 list-none p-0">
        {props.lines.map((line) => (
          <li key={line.key} className="mt-1" data-problem-line={line.key}>
            {line.field === null ? (
              <strong className="font-heading">{line.fieldLabel}</strong>
            ) : (
              <a
                href={`#${line.field}`}
                className={`font-heading font-semibold underline ${refusal ? "text-danger-700" : "text-warning-700"}`}
                onClick={(event) => {
                  event.preventDefault();
                  document.getElementById(line.field as string)?.focus();
                }}
              >
                {line.fieldLabel}
              </a>
            )}
            {" — "}
            {line.message}
            {line.link !== undefined &&
              ("href" in line.link ? (
                <a href={line.link.href} target="_blank" rel="noreferrer" className="ml-1 font-semibold underline">
                  {line.link.label}
                </a>
              ) : (
                <button
                  type="button"
                  className="ml-1 cursor-pointer border-0 bg-transparent p-0 font-semibold text-inherit underline"
                  onClick={line.link.onPress}
                >
                  {line.link.label}
                </button>
              ))}
          </li>
        ))}
      </ul>
    </div>
  );
}

/** A small fact row of the summary aside — label left, value right. */
export function AsideRow(props: { label: string; children: ReactNode; name?: string }) {
  return (
    <div className="flex items-center justify-between gap-3 text-base" data-aside-row={props.name}>
      <span className="text-neutral-700">{props.label}</span>
      <span className="text-right">{props.children}</span>
    </div>
  );
}
