// ── Trace ──────────────────────────────────────────────
// Defect:   DEF-MET-10164 (PO 2026-10-17 — the Age column on the Premises and
//           Units lists). THE shared Age cell: the asset and account age
//           columns render through this one component (PO: "use same code
//           components"), never a copy of it (B14 rule 43).
// Rules:    BR-SHL-023 (tenant zone) · B14 rule 21 (Tailwind only) · rule 33
//           (a cell holds a value; `note` is a short fact, never a sentence)
// Tests:    07-frontend/src/components/AgeCell.test.tsx
// ───────────────────────────────────────────────────────
// `start` is a calendar date or an instant; `end` (optional) stops the clock
// on that day — a retired asset's age is fixed at its retirement — and absent
// means today in the tenant's zone. The arithmetic and the words are
// `lib/age.ts`; this file only lays them out.
//
// ⚠ **THE ZONE IS THE TENANT'S, AND A SCREEN THAT HAS ONE PASSES IT.** With no
// `timeZone` prop the cell reads the published tenant setting
// (`TenantRegionalProvider`). With neither it throws in the product — a
// plausible wrong age is worse than a loud failure (hard-won law 3) — and
// falls back to UTC only under test, exactly as `resolveRegional` does.
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";

import { useTenantRegional } from "@/components/TenantRegional";
import { ageBetween, formatAge } from "@/lib/age";

export interface AgeCellProps {
  /** `YYYY-MM-DD` or an ISO instant. Null/blank renders a quiet dash. */
  start: string | null | undefined;
  /** Stop the clock on this day (`YYYY-MM-DD` or instant); absent = today. */
  end?: string | null;
  /** A short second line (e.g. a state word). Never a sentence. */
  note?: ReactNode;
  /** `danger` accents the cell (e.g. an asset past its life). */
  tone?: "danger";
  /** The tenant's IANA zone, when the screen already holds it. */
  timeZone?: string;
}

export function AgeCell(props: AgeCellProps) {
  const { t } = useTranslation();
  const published = useTenantRegional();
  const timeZone = props.timeZone ?? published?.timeZone ?? testZone();
  const age = ageBetween(props.start ?? null, props.end ?? null, timeZone);
  const tone = props.tone === "danger" ? "text-danger-700" : "text-neutral-900";
  return (
    <span className="inline-flex flex-col" data-age-cell="">
      <span className={`tabular-nums whitespace-nowrap ${age === null ? "text-neutral-600" : tone}`}>
        {age === null ? "—" : formatAge(age, t)}
      </span>
      {props.note !== undefined && props.note !== null && props.note !== "" && (
        <span className={`text-xs ${props.tone === "danger" ? "text-danger-700" : "text-neutral-600"}`}>
          {props.note}
        </span>
      )}
    </span>
  );
}

function testZone(): string {
  if (import.meta.env.MODE === "test") return "UTC";
  throw new Error("AgeCell: no tenant time zone published (TenantRegionalProvider missing)");
}
