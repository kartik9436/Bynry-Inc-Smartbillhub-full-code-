// ── Trace ──────────────────────────────────────────────
// Story:    US-TEN-005 (S8 Company profile → Brand)  Screens: S8, shell-chrome
// Change:   CR-048 wave D — the utility's own mark, drawn.
// Defect:   DEF-195 (ruled 2026-08-16, drawn nowhere) · DEF-192 (no route
//           served the bytes, so no logo could be drawn either)
// Rules:    BR-TEN-019 · CR-007 PO ruling 2026-08-16 (*"Create name based or
//           initial base dummy logo"*, *"2 letters"*) · B14 rule 21 ·
//           B8 (no hex literals — a tenant colour is DATA, not a token)
// Tests:    07-frontend/src/features/tenancy/BrandMark.test.tsx
// ───────────────────────────────────────────────────────
/**
 * ONE element that answers "what goes where the logo goes" everywhere.
 *
 * With a logo on file it draws the logo. Without one it draws the generated
 * two-letter mark the PO ruled: the utility's initials, in the utility's own
 * colour, with the ink the server chose so they are readable on it. There is
 * no third state and no empty corner.
 *
 * ⚠ WHAT THIS REPLACED, because the shape of the bug is the useful part:
 * `SettingsCompanyTab` drew `<span className="settings-letterhead-mark" />` —
 * a 26 x 26 block of `brand_primary_hex` with NOTHING IN IT — and it rendered
 * IDENTICALLY whether a logo was on file or not. So the one screen a utility
 * uses to confirm its branding could not tell them whether their upload had
 * worked. Every test passed on it; a coloured square is a coloured square.
 *
 * ── WHY IT IS AN INLINE SVG WITH INLINE STYLES AND NO CLASS OF ITS OWN ─────
 * Two constraints meet here and only one shape satisfies both.
 *
 * B14 rule 21 says a new piece of UI adds NO class to a stylesheet, and its
 * migration clause says a Tailwind utility is emitted ONLY for a file listed
 * in `src/styles/route-b-migrated.txt`. Neither of this component's two call
 * sites is on that list, so a utility written here would be a class no
 * stylesheet declares: it renders as NOTHING and every check passes on it.
 *
 * B8 forbids hex literals — every colour in this product is a token. But a
 * tenant's brand colour is DATA, not a token: it lives in a database row, it
 * differs per tenant, and it cannot be written into a stylesheet at all
 * (OQ-800(b) raised exactly this and left the mechanism to be decided once
 * rather than invented per screen).
 *
 * An inline `style` settles both: the two colours ride on it as DATA, and NO
 * class name and NO stylesheet rule is added anywhere. `size` is a prop so the
 * sidebar and the letterhead can differ without a second rule existing.
 *
 * ⚠ AND IT IS A `<span>` RATHER THAN AN INLINE `<svg>`, WHICH THE FIRST DRAFT
 * WAS. Two gates said no, and both were right. G37 (B14 rule 15) allows an
 * `<svg>` in exactly one file — `components/icons.tsx`, the icon vocabulary's
 * one owner (DEF-348/DEF-349) — and a mark whose content is tenant data is not
 * a glyph that belongs in a vocabulary. G34 (B14 rule 5) bans an inline
 * `fontSize` anywhere, and an `<svg>` needs one to size its `<text>` against
 * its viewBox. A span sized in px with INHERITED type needs neither: it is
 * smaller, it scales with the block it sits in, and it kept both rules whole.
 *
 * ── THE FALLBACK COLOURS ARE TOKENS, NOT A GUESS ──────────────────────────
 * A tenant that has set no brand colour gets `background_hex: null` from the
 * server — the server deliberately invents nothing. Here that resolves to
 * `var(--color-neutral-300)` behind `var(--color-text)`: two tokens this app
 * already declares, so the mark is legible and B8 is not bent to reach it.
 */
import { contrastRatio, parseHex, relativeLuminance } from "@/lib/contrast";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { companyLogoFileUrl } from "@/api/endpoints";
import type { CompanyMark } from "@/api/endpoints";

/** The letterhead chip on S8 — the size the old empty block occupied. */
export const MARK_SIZE_LETTERHEAD = 26;
/** The sidebar chip beside the utility's name. */
export const MARK_SIZE_SIDEBAR = 28;

/**
 * The tokens a mark falls back to when the tenant has set no brand colour.
 * Named here so the two call sites cannot drift, and so a reader can see that
 * they ARE tokens rather than a hex someone typed.
 */
const FALLBACK_BACKGROUND = "var(--color-neutral-300)";
const FALLBACK_INK = "var(--color-text)";

/* ── The live-preview half, and why it is a SECOND implementation ──────────
 *
 * The server owns the mark: `apps/tenancy/brand.py` computes it and every
 * saved surface — the sidebar, and the documents a customer receives — reads
 * that one answer. This function exists for exactly one thing the server
 * cannot do: BR-TEN-019 requires the S8 letterhead preview to render LIVE FROM
 * UNSAVED VALUES, so while a utility is typing its trading name and picking a
 * colour there is nothing on the server to ask.
 *
 * Duplicating a rule is how two answers drift, so it is pinned rather than
 * hoped: `BrandMark.test.tsx` asserts this function on the SAME worked
 * examples the backend test asserts (`Silver Creek Water` → SC, `#1B5E9E` →
 * white ink, `#F5E9A0` → black ink, the 0.179 crossover). If either side
 * moves, one of the two suites goes red.
 *
 * The threshold and its derivation live in `apps/tenancy/brand.py` — read that
 * docstring before changing anything here.
 */
const INK_DARK = "#000000";
const INK_LIGHT = "#FFFFFF";
/** Relative luminance where black and white score identically (see backend). */
export const INK_LUMINANCE_THRESHOLD = 0.1791287847;

// The ratio arithmetic is the ONE shared helper, `@/lib/contrast` (portal a11y
// Group A, 2026-10-23); re-exported so this module's callers are unchanged.
export { contrastRatio, relativeLuminance } from "@/lib/contrast";

/** Black or white — whichever a reader can actually see on `background`. */
export function readableInk(background: string | null): string | null {
  const luminance = relativeLuminance(background);
  if (luminance === null) return null;
  return luminance > INK_LUMINANCE_THRESHOLD ? INK_DARK : INK_LIGHT;
}

/** The mark's two letters: trading name → legal name → whatever is left. */
export function markLetters(dbaName: string | null, legalName: string | null): string {
  const source = [dbaName, legalName].find((n) => n != null && n.trim() !== "")?.trim() ?? "";
  const words: string[] = source.match(/[\p{L}\p{N}]+/gu) ?? [];
  const [first, second] = words;
  if (first === undefined) return "";
  if (second !== undefined) return (first.charAt(0) + second.charAt(0)).toUpperCase();
  return first.slice(0, 2).toUpperCase();
}

/** The whole mark from UNSAVED form values — S8's live letterhead only. */
export function previewMark(draft: {
  dba_name: string;
  legal_name: string;
  brand_primary_hex: string;
}): CompanyMark {
  const background = parseHex(draft.brand_primary_hex) ? draft.brand_primary_hex.trim() : null;
  const ink = readableInk(background);
  const ratio = ink === null ? null : contrastRatio(ink, background);
  return {
    letters: markLetters(draft.dba_name, draft.legal_name),
    background_hex: background,
    ink_hex: ink,
    contrast_ratio: ratio === null ? null : Math.round(ratio * 100) / 100,
  };
}

export interface BrandMarkProps {
  /** The server-computed mark. Always present on `GET /settings/company`. */
  mark: CompanyMark;
  /** True when a logo is on file — then the logo is drawn instead. */
  hasLogo: boolean;
  /**
   * CR-172-BRC10 — the logo's reference (`logo_ref` on every payload that
   * carries `has_logo`). It goes into the image address, so a replaced logo
   * is a new address and is drawn at once. Optional only so a caller that has
   * no reference still draws the logo; every call site in the app passes it.
   */
  logoRef?: string | null;
  /** Edge length in px. */
  size?: number;
  /**
   * The utility's name, for the accessible label. The mark is the utility's
   * identity, not decoration, so it is NOT `aria-hidden` — the block it
   * replaced was, correctly, because an empty square says nothing.
   */
  name?: string | null;
  /** An existing stylesheet class the call site already owns. */
  className?: string;
}

export function BrandMark(props: BrandMarkProps) {
  const { t } = useTranslation();
  const size = props.size ?? MARK_SIZE_LETTERHEAD;
  const label =
    props.name != null && props.name !== ""
      ? t("settings.company.mark.label", { name: props.name })
      : t("settings.company.mark.labelUnnamed");

  // A logo needs a tenant in the URL to be fetchable. Inside the app there
  // always is one; where there is not (a first paint outside `/{tenant}/…`),
  // the generated mark is drawn rather than a broken image.
  //
  // CR-172-BRC10 — and when the image cannot be fetched (the store is down, or
  // the address answers anything but a picture) the generated mark is drawn in
  // its place. A broken-image icon in the app header is what `DEF-TEN-9704`
  // put on every deployed screen; it must not be the failure shape again.
  const logoUrl = props.hasLogo ? companyLogoFileUrl(props.logoRef) : null;
  const [failedUrl, setFailedUrl] = useState<string | null>(null);
  if (logoUrl !== null && failedUrl !== logoUrl) {
    return (
      <img
        className={props.className}
        src={logoUrl}
        alt={label}
        width={size}
        height={size}
        data-brand-logo=""
        onError={() => setFailedUrl(logoUrl)}
        // The stored file is any shape a designer exported; `contain` shows all
        // of it rather than cropping a wordmark to a square.
        style={{ objectFit: "contain" }}
      />
    );
  }

  const background = props.mark.background_hex ?? FALLBACK_BACKGROUND;
  const ink = props.mark.ink_hex ?? FALLBACK_INK;
  return (
    <span
      className={props.className}
      role="img"
      aria-label={label}
      style={{
        // The two colours — the only values here that are tenant DATA.
        backgroundColor: background,
        color: ink,
        // Geometry. No `fontSize`: B14 rule 5 keeps type on the token scale
        // (G34 bans an inline one outright), so the letters simply INHERIT the
        // size of the block they sit in — `--text-sm` at both call sites — and
        // the box clips rather than grows if that ever changes.
        width: size,
        height: size,
        flex: "0 0 auto",
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        overflow: "hidden",
        fontWeight: 700,
        letterSpacing: "0.02em",
        lineHeight: 1,
      }}
    >
      {props.mark.letters}
    </span>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-048 wave D · CR-007 PO ruling 2026-08-16 · OQ-257 · OQ-800
// generated: 2026-08-30 by the CR-048 wave-D lane
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO)
// exceptions: [CR-172-BRC10 2026-10-05] the PDF half is BUILT on the server — an SVG logo is rendered to PNG once at upload (apps/tenancy/logo.py raster_png) and bills draw that PNG; this read "E3 the mark is drawn on SCREEN only — BR-TEN-019's 'rasterized for PDF/print' clause is still unbuilt" until then · E3 no Remove control: `POST /settings/company/logo` has no DELETE sibling and no story anchors removal, so a replacement upload is still the only path (unchanged from the upload lane) · E4 the collapsed sidebar hides the whole `.tenant` block (AppShell.css `.app-shell.collapsed .tenant {display:none}`), so the mark is hidden with it — a collapsed-rail mark would be a new stylesheet rule, which B14 rule 21 forbids in an unmigrated file; REPORTED, not smuggled in
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
