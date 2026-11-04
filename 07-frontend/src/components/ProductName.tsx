// ── Trace ──────────────────────────────────────────────
// Change:  CR-088 follow-on — decision log 2026-10-02, "THE PRODUCT NAME IS SET
//          IN TWO SIZES AND TWO COLOURS". PO, verbatim: "A · Two sizes, as in
//          the example. On the pricing and sign-in help pages it would be 16px
//          and 12px. and two differnt colors".
// Rules:   B14 rule 21 (Tailwind only) · rule 43 (one component, three callers)
//          · rule 44 (type-scale steps only) · WCAG 1.4.3
// Callers: AppShell (side menu) · PricingPage · SignInHelpPage
// ───────────────────────────────────────────────────────
//
// THE PRODUCT NAME AS IT IS DRAWN: "SMART360" large and extra-bold, "Next"
// smaller, lighter and in the accent.
//
//                      SMART360          Next
//   side menu ("shell")  text-brand 18px   text-md 14px
//   public pages         text-lead  16px   text-sm 12px
//
// ⚠ THE ACCENT IS NOT `--color-accent` ITSELF ON EITHER SURFACE, AND THE RULING
// SAID IT MIGHT NOT BE. `#ec3013` measures 3.95:1 on the ink side menu and
// 3.76:1 on the public page's `--color-bg`; text this size at a normal weight
// needs 4.5:1. So each surface takes the accent ramp's nearest step that passes
// THERE: `accent-500` (#ff563c, 5.26:1) on ink and `accent-700` (#ae1800,
// 6.41:1) on the page. Pre-authorised by the ruling ("if it fails on either,
// the accent's darker/lighter step is used there and recorded") and recorded in
// the decision log's follow-up row of the same day.
//
// ⚠ ONE ACCESSIBLE NAME. The split is visual only: both visible parts are
// `aria-hidden` and one visually-hidden run reads "SMART360 Next" (`app.name`,
// the same key the browser tab uses), so a screen reader says the name once
// rather than "SMART360" and "Next" as two words, or the name twice.
import { useTranslation } from "react-i18next";

const SIZES = {
  shell: {
    // The family keeps the ink panel's light colour by inheritance — the
    // colour it always had there.
    family: "text-brand font-extrabold",
    edition: "text-md font-semibold text-accent-500",
  },
  public: {
    family: "text-lead font-extrabold text-text",
    edition: "text-sm font-semibold text-accent-700",
  },
} as const;

export function ProductName({
  size,
  className,
}: {
  /** `shell` is the side menu (on ink); `public` is the pricing and sign-in
   *  help pages (on the page background). */
  size: keyof typeof SIZES;
  className?: string;
}) {
  const { t } = useTranslation();
  const parts = SIZES[size];
  const frame = "inline-flex items-baseline gap-1 whitespace-nowrap font-heading";
  return (
    <span data-product-name={size} className={className === undefined ? frame : `${frame} ${className}`}>
      <span className="sr-only">{t("app.name")}</span>
      <span aria-hidden="true" data-product-name-part="family" className={parts.family}>
        {t("app.nameFamily")}
      </span>
      <span aria-hidden="true" data-product-name-part="edition" className={parts.edition}>
        {t("app.nameEdition")}
      </span>
    </span>
  );
}
