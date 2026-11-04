// ── Trace ──────────────────────────────────────────────
// Change:  CR-180-BRC10 — the pieces every Fix a bill step repeats
// Drawing: 05-prototype/fix-a-bill-2026-10-12/*.png
// Rules:   B14 rules 21 (utilities only), 31, 33, 43 (a piece of UI is a
//          component), 44 (our UI standard decides spacing and tokens) ·
//          hard rule 2 (money 2 places; a unit price up to 4)
// ───────────────────────────────────────────────────────
/**
 * Shared by the four steps: the money words (signed, 2 places; unit prices up
 * to 4), the class pill a row carries, and the coloured band a step states its
 * consequence in. The page's panels and tables are the kit's — `OtbPanel`,
 * `CollapsiblePanel`, `PlainTable`, `OTB_TABLE` — so Fix a bill looks like the
 * One-time bill beside it rather than like the mock-up (rule 44).
 */
import type { ReactNode } from "react";

import { formatMoney, formatRate } from "@/components/MoneyCell";
import { StatusPill } from "@/components/StatusPill";
import type { StatusTone } from "@/components/StatusPill";

import { signOf, unsigned } from "./fixABillModel";
import type { Translate } from "./fixABillModel";

/** The page's money context — one currency, served (never assumed). */
export interface FixFmt {
  t: Translate;
  currency: string;
  language: string;
}

const MINUS = "−";

/** `$232.70` — 2 places (hard rule 2). `—` for an absent figure. */
export function money(amount: string | null | undefined, fmt: FixFmt): string {
  if (amount === null || amount === undefined || amount === "") return "—";
  const sign = signOf(amount) === "down" ? MINUS : "";
  return `${sign}${formatMoney(unsigned(amount), fmt.currency)}`;
}

/** `+$18.74` · `−$11.38` · `$0.00` — a change always says which way. */
export function signedMoney(amount: string | null | undefined, fmt: FixFmt): string {
  if (amount === null || amount === undefined || amount === "") return "—";
  const way = signOf(amount);
  const sign = way === "up" ? "+" : way === "down" ? MINUS : "";
  return `${sign}${formatMoney(unsigned(amount), fmt.currency)}`;
}

/** A UNIT PRICE: 2 places where it has no more, up to 4 where it does (PO
 *  2026-10-02 — `$0.115`, `$8.9375`). */
export function unitPrice(amount: string, fmt: FixFmt): string {
  const fraction = amount.split(".")[1] ?? "";
  if (fraction.slice(2).replace(/0+$/, "") === "") return formatMoney(amount, fmt.currency);
  return formatRate(amount, fmt.currency);
}

/** A quantity or a reading as a person writes it — `5`, `1.6`, `1,159.9` —
 *  trailing zeros trimmed, never rounded. Not money. */
export function plainNumber(value: string | null | undefined, language: string): string {
  if (value === null || value === undefined || value === "") return "";
  const trimmed = value.includes(".") ? value.replace(/0+$/, "").replace(/\.$/, "") : value;
  const places = (trimmed.split(".")[1] ?? "").length;
  const parsed = Number(trimmed);
  if (!Number.isFinite(parsed)) return trimmed;
  try {
    return new Intl.NumberFormat(language, {
      minimumFractionDigits: places,
      maximumFractionDigits: places,
    }).format(parsed);
  } catch {
    return trimmed;
  }
}

/** `1%` · `0.25%` · `1.5%` from a served percent string. */
export function percent(value: string | null | undefined, language: string): string {
  if (value === null || value === undefined || value === "") return "";
  return `${plainNumber(value, language)}%`;
}

/** The colour a change is drawn in: up is accent, down is success. */
export function changeTone(amount: string | null | undefined): string {
  const way = signOf(amount);
  return way === "up" ? "text-accent-700" : way === "down" ? "text-success-700" : "";
}

/** The three classes' pill tones: re-price info, credit only success,
 *  reprint only muted — the drawing's blue, green and grey. */
export function classTone(cls: string | null): StatusTone {
  if (cls === "restatement") return "info";
  if (cls === "credit_only") return "success";
  return "muted";
}

export function ClassPill(props: { cls: string | null; t: Translate }) {
  if (props.cls === null) return null;
  return (
    <span data-fix-row-class="">
      <StatusPill tone={classTone(props.cls)}>
        {props.t(`billing.fixBill.class.${props.cls}`)}
      </StatusPill>
    </span>
  );
}

export type BandTone = "info" | "warning" | "success" | "danger" | "neutral";

const BAND: Record<BandTone, string> = {
  info: "bg-info-100 text-info-700",
  warning: "bg-warning-100 text-warning-700",
  success: "bg-success-100 text-success-700",
  danger: "bg-danger-100 text-danger-700",
  neutral: "bg-neutral-200 text-text",
};

/** A full-width coloured line: `What happens: Re-price.`, `This bill rises
 *  by $18.74.`, `Nothing is saved until you send it.` */
export function Band(props: {
  tone: BandTone;
  children: ReactNode;
  role?: "status" | "note" | "alert";
  hook?: string;
}) {
  const hook = props.hook === undefined ? {} : { [`data-fix-${props.hook}`]: "" };
  return (
    <p
      className={`m-0 mt-3 flex flex-wrap items-baseline gap-x-3 gap-y-1 px-3 py-2 text-base ${BAND[props.tone]}`}
      role={props.role ?? "status"}
      {...hook}
    >
      {props.children}
    </p>
  );
}

/** The band a change is stated in, coloured by its direction. */
export function changeBandTone(amount: string | null | undefined): BandTone {
  const way = signOf(amount);
  return way === "up" ? "warning" : way === "down" ? "success" : "success";
}
