// ── Trace ──────────────────────────────────────────────
// Defects:  DEF-CUS-9774 (the account page read "Tax exempt: No" over a live
//           certificate) · DEF-CUS-9775 (the move record's Billing tab read
//           "Tax: Taxed" for the same account)
// Rules:    BR-RAT-105 (a certificate is per tax) · PO ruling (A) 2026-10-05
//           (DEF-CUS-9724: an exemption removes only the tax on its
//           certificate, and the blanket `tax_exempt` flag stays false)
// Screens:  S21 Account setup (Tax exempt · Exemption reference · Exemption
//           expires, the drawn rows) · the move record's Billing tab, Tax cell
// ───────────────────────────────────────────────────────
/**
 * ONE reading of an account's tax exemption, for every screen that states it.
 *
 * Two facts can make an account exempt and both screens read both:
 *   * the BLANKET exemption — `tax_exempt` / `_ref` / `_expires`, every tax;
 *   * a per-tax CERTIFICATE — `tax_exemptions[]`, rating's row, ONE tax.
 * Until 2026-10-06 both screens read only the first, and ruling (A) means a
 * move-in never sets it — so the church exempt from the City's tax read as not
 * exempt on its own account while its bill dropped the City's 2.00%.
 *
 * Only LIVE certificates exempt: an expired one has reinstated the tax
 * (CR-013 part 4), so it is not drawn as an exemption.
 */
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";

import type { AccountTaxExemption } from "@/api/endpoints";

/** The exemption facts an account detail carries. */
export interface ExemptionFacts {
  tax_exempt: boolean;
  tax_exempt_ref: string | null;
  tax_exempt_expires: string | null;
  tax_exemptions?: AccountTaxExemption[];
}

/** The certificates that exempt today — live, in the server's order. */
export function liveExemptions(facts: ExemptionFacts): AccountTaxExemption[] {
  return (facts.tax_exemptions ?? []).filter((row) => row.state === "live");
}

/** True when the account pays less tax than an ordinary one: blanket, or a live certificate. */
export function isTaxExempt(facts: ExemptionFacts): boolean {
  return facts.tax_exempt || liveExemptions(facts).length > 0;
}

/**
 * The Account setup group's three drawn rows' VALUES, one line per live
 * certificate so a tax, its number and its expiry sit on the same line of
 * each row. The blanket exemption keeps its own reading (`Yes · ref`).
 */
export function ExemptionLines(props: {
  facts: ExemptionFacts;
  part: "exempt" | "reference" | "expires";
  renderDate: (iso: string) => ReactNode;
  none: ReactNode;
}) {
  const { t } = useTranslation();
  const { facts, part } = props;
  if (facts.tax_exempt) {
    if (part === "exempt") {
      return (
        <>
          {t("customers.account.yes")}
          {facts.tax_exempt_ref !== null && facts.tax_exempt_ref !== "" && (
            <span className="text-sm text-[color-mix(in_srgb,var(--color-text)_55%,transparent)]"> · {facts.tax_exempt_ref}</span>
          )}
        </>
      );
    }
    if (part === "reference") return <>{facts.tax_exempt_ref ?? props.none}</>;
    return <>{facts.tax_exempt_expires ? props.renderDate(facts.tax_exempt_expires) : props.none}</>;
  }
  const live = liveExemptions(facts);
  if (live.length === 0) {
    return <>{part === "exempt" ? t("customers.account.no") : props.none}</>;
  }
  return (
    <span className="inline-flex flex-col items-start" data-exemption-part={part}>
      {live.map((row) => (
        <span key={row.id}>
          {part === "exempt"
            ? t("customers.account.exemptFrom", { tax: row.tax_name })
            : part === "reference"
              ? (row.certificate_ref ?? props.none)
              : row.expires_on
                ? props.renderDate(row.expires_on)
                : props.none}
        </span>
      ))}
    </span>
  );
}

/**
 * The move record's one-cell reading: `Exempt from <tax> · <number> · until
 * <date>` per live certificate, `Exempt · <ref> · until <date>` for the
 * blanket exemption, and `taxed` otherwise. The words are the cell's own keys
 * (`customers.moveDetail.*`) plus the shared `exemptFrom`.
 */
export function ExemptionSummary(props: {
  facts: ExemptionFacts;
  renderDate: (iso: string) => ReactNode;
  taxed: ReactNode;
}) {
  const { t } = useTranslation();
  const { facts } = props;
  const one = (head: string, ref: string | null, expires: string | null, key: string) => (
    <span key={key}>
      {[head, ref].filter(Boolean).join(" · ")}
      {expires ? (
        <>
          {" · "}
          {t("customers.moveDetail.until")} {props.renderDate(expires)}
        </>
      ) : null}
    </span>
  );
  if (facts.tax_exempt) {
    return one(t("customers.moveDetail.taxExempt"), facts.tax_exempt_ref, facts.tax_exempt_expires, "blanket");
  }
  const live = liveExemptions(facts);
  if (live.length === 0) return <>{props.taxed}</>;
  return (
    <span className="inline-flex flex-col" data-exemption="certificates">
      {live.map((row) =>
        one(t("customers.account.exemptFrom", { tax: row.tax_name }), row.certificate_ref, row.expires_on, row.id),
      )}
    </span>
  );
}
