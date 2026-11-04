// ── Trace ──────────────────────────────────────────────
// Story:    US-TEN-005 (EP-TEN-05 §Stories)  Screens: S8 (Settings → Company profile)
// Rules:    BR-TEN-017 (values are stamped onto documents AT ISSUE — edits never re-render an issued bill) ·
//           BR-TEN-018 (EIN entered NN-NNNNNNN, stored as 9 digits, format-only validation) ·
//           BR-TEN-019 (logo SVG/PNG ≤ 2 MB; brand colors #RRGGBB; letterhead preview live from unsaved values) ·
//           BR-TEN-024 (sticky Save/Discard; the whole tab commits atomically with one audit row) ·
//           BR-TEN-016 (Save writes audit_log `settings.company_profile.updated`) ·
//           BR-SHL-017 (shared field kit + inline per-field errors) · BR-SHL-020 (plain-language failure) ·
//           BR-SHL-025 (a role that may only view gets disabled-with-reason controls)
// ───────────────────────────────────────────────────────
// S8 → Company profile: three panels (Utility details · Brand · Remittance)
// over ONE atomic `PUT /settings/company`.
//
// The whole tab is a draft held above the panels, so Discard is a real revert
// to the SERVER's values and Save is one call carrying only what changed
// (BR-TEN-024). Client validation mirrors the server's VAL codes for immediate
// feedback and is never the authority — every rejection rendered here comes
// back out of the B12 §3 envelope.
//
// BR-TEN-017 is a promise this screen must not break: nothing here re-renders
// anything already issued. There is no "re-render past bills" affordance, and
// the footer says so in plain language.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import type { CSSProperties } from "react";
import { useTranslation } from "react-i18next";
import { z } from "zod";

import { api, formErrorEnvelope, isApiError } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { getCompanyProfile, saveCompanyProfile, uploadCompanyLogo } from "@/api/endpoints";
import type { CompanyLogo, CompanyProfile } from "@/api/endpoints";
import { queryKeys } from "@/api/queryClient";
import { SelectField, TextField, collectFormErrors, envelopeErrors } from "@/components/FormModal";
import { FailedWithRetry, LoadingSkeleton } from "@/components/StateFrame";
import { useToast } from "@/components/Toast";
import { RefusalStrip } from "@/components/Surfaces";
import { Note } from "@/components/TextBits";

import { BrandMark, MARK_SIZE_LETTERHEAD, previewMark } from "./BrandMark";
import { SampleDataPanel } from "./SettingsSampleData";

import {
  Panel,
  PanelGrid,
  RefusalNotice,
  SaveBar,
  SettingsDenied,
  apiErrorText,
  isPermissionDenied,
  refusalOf,
} from "./settingsShared";
import type { Refusal, Translator } from "./settingsShared";

// ── Pure pieces (provable without a browser or a network) ──────────────────

/** The editable field set — exactly the columns `PUT /settings/company` takes. */
export const COMPANY_FIELDS = [
  "legal_name",
  "dba_name",
  // CR-060 C7 / task T2 — an identity FACT, so it sits with legal name and DBA
  // rather than on a finance tab. It rides the same draft, the same dirty
  // check and the same atomic PUT as every other field on this tab.
  "organisation_type",
  "ein",
  "state_utility_id",
  "mailing_address",
  "support_phone",
  "support_email",
  "website",
  "brand_primary_hex",
  "brand_accent_hex",
  // CR-199-BRC10 S5 — the email logo's link, set once here (PO ruling 1A).
  "brand_logo_link_url",
  "remit_to_address",
  "remit_payable_to",
  "service_hours",
] as const;

export type CompanyField = (typeof COMPANY_FIELDS)[number];
export type CompanyDraft = Record<CompanyField, string>;

export const EMPTY_COMPANY_DRAFT: CompanyDraft = {
  legal_name: "",
  dba_name: "",
  // The server seeds `utility` and falls back to it, so the empty draft says
  // the same thing rather than inventing a blank fourth state.
  organisation_type: "utility",
  ein: "",
  state_utility_id: "",
  mailing_address: "",
  support_phone: "",
  support_email: "",
  website: "",
  brand_primary_hex: "",
  brand_accent_hex: "",
  brand_logo_link_url: "",
  remit_to_address: "",
  remit_payable_to: "",
  service_hours: "",
};

/** A null column becomes an empty input; an empty input goes back as null. */
export function draftFromProfile(profile: CompanyProfile): CompanyDraft {
  const draft = { ...EMPTY_COMPANY_DRAFT };
  for (const field of COMPANY_FIELDS) {
    draft[field] = profile[field] ?? "";
  }
  return draft;
}

/** BR-TEN-024: the PUT carries only what the user actually changed. */
export function companyChanges(
  draft: CompanyDraft,
  original: CompanyDraft,
): Partial<CompanyProfile> {
  const changes: Record<string, string | null> = {};
  for (const field of COMPANY_FIELDS) {
    if (draft[field] !== original[field]) {
      changes[field] = draft[field].trim() === "" ? null : draft[field].trim();
    }
  }
  return changes as Partial<CompanyProfile>;
}

export function isDirty(draft: CompanyDraft, original: CompanyDraft): boolean {
  return COMPANY_FIELDS.some((field) => draft[field] !== original[field]);
}

/**
 * CR-060 C7 — the English an option renders until the eleven catalogues carry
 * `settings.company.organisationType.*`.
 *
 * ⚠ **THIS IS A FALLBACK, NOT A COPY OF THE CATALOGUE.** The KEY is built from
 * the server's own served vocabulary, so a fourth organisation type needs no
 * edit here to appear in the picker — it renders its own code until somebody
 * translates it, which is visible and correctable, where a hardcoded list would
 * silently drop it. i18next prefers the catalogue whenever the key resolves.
 */
export const ORGANISATION_TYPE_ENGLISH: Record<string, string> = {
  utility: "Utility",
  sub_metering: "Sub-metering company",
  hoa: "HOA",
};

// BR-TEN-018: the INPUT shape is NN-NNNNNNN; the server stores 9 digits.
const EIN_SHAPE = /^\d{2}-\d{7}$/;
const HEX_SHAPE = /^#[0-9a-fA-F]{6}$/;
const EMAIL_SHAPE = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;
/** CR-199-BRC10 S5 — `https://` and a host, no space, quote or angle bracket. */
export const LOGO_LINK_SHAPE = /^https:\/\/[^\s/"'<>`\\@]+(?:[/?#][^\s"'<>`\\]*)?$/;

/** US-TEN-005 §5 text limits — the same numbers the server enforces. */
export const COMPANY_TEXT_LIMITS: Partial<Record<CompanyField, number>> = {
  legal_name: 200,
  dba_name: 200,
  state_utility_id: 40,
  mailing_address: 500,
  support_phone: 40,
  website: 200,
  remit_to_address: 500,
  remit_payable_to: 200,
  service_hours: 60,
};

/**
 * BR-SHL-017 client validation — UX only; the SERVER is authoritative (B8).
 * Every rule below mirrors a server check so the two never disagree in kind.
 */
export function companySchema(t: Translator) {
  const optionalLength = (field: CompanyField) =>
    z
      .string()
      .max(COMPANY_TEXT_LIMITS[field] ?? 500, t("settings.company.tooLong", {
        max: COMPANY_TEXT_LIMITS[field] ?? 500,
      }));
  return z.object({
    // CR-060 C7 — three values and no blank. The picker cannot produce a
    // fourth, so this mirrors the SERVER's refusal rather than adding a rule
    // of its own (BR-SHL-017: client validation is UX, the server is law).
    organisation_type: z
      .string()
      .refine((v) => v !== "", t("settings.company.organisationTypeUnknown", {
        defaultValue: "Choose utility, sub-metering company or HOA.",
      })),
    legal_name: optionalLength("legal_name"),
    dba_name: optionalLength("dba_name"),
    state_utility_id: optionalLength("state_utility_id"),
    mailing_address: optionalLength("mailing_address"),
    support_phone: optionalLength("support_phone"),
    website: optionalLength("website"),
    remit_to_address: optionalLength("remit_to_address"),
    remit_payable_to: optionalLength("remit_payable_to"),
    service_hours: optionalLength("service_hours"),
    // US-TEN-005 TC-4: "Enter as NN-NNNNNNN".
    ein: z.string().refine((v) => v === "" || EIN_SHAPE.test(v), t("settings.company.einFormat")),
    support_email: z
      .string()
      .refine((v) => v === "" || EMAIL_SHAPE.test(v), t("settings.company.emailFormat")),
    brand_primary_hex: z
      .string()
      .refine((v) => v === "" || HEX_SHAPE.test(v), t("settings.company.hexFormat")),
    brand_accent_hex: z
      .string()
      .refine((v) => v === "" || HEX_SHAPE.test(v), t("settings.company.hexFormat")),
    // CR-199-BRC10 S5 — mirrors `tenancy.services.brand_logo_link_ok`; the
    // server is authoritative and also refuses credentials and quotes.
    brand_logo_link_url: z
      .string()
      .refine(
        (v) => v.trim() === "" || LOGO_LINK_SHAPE.test(v.trim()),
        t("settings.company.logoLinkHttps"),
      ),
  });
}

// ── BR-TEN-019 logo guard (US-TEN-005 TC-5) ────────────────────────────────

export const LOGO_MAX_BYTES = 2 * 1024 * 1024; // "PNG or JPG, max 2 MB"
// DEF-TEN-10618 (PO 2026-10-27, "Allow PNG, JPG"; BR-TEN-019 SUPERSEDED):
// the whole allowlist, and the file picker's `accept` is built from it.
export const LOGO_TYPES: readonly string[] = ["image/png", "image/jpeg"];

export type LogoProblem = "too_large" | "unsupported_type" | "svg" | null;

/**
 * The client-side half of the logo law, pure so it is provable without a
 * browser. It refuses BEFORE the bytes leave, in the shapes the server answers:
 * 413 (too large), 415 (unsupported type) and — `DEF-TEN-10618` — an SVG, by
 * its type or by its name, with its own sentence. The server re-checks the
 * type AND the file's contents — this guard saves a round trip, it does not
 * replace the check.
 */
export function logoProblem(file: { size: number; type: string; name?: string }): LogoProblem {
  if (file.type === "image/svg+xml" || /\.svgz?$/i.test(file.name ?? "")) {
    return "svg";
  }
  if (!LOGO_TYPES.includes(file.type)) {
    return "unsupported_type";
  }
  if (file.size > LOGO_MAX_BYTES) {
    return "too_large";
  }
  return null;
}

export function logoProblemKey(problem: LogoProblem): string | null {
  if (problem === "too_large") {
    return "settings.company.logo.tooLarge"; // 413
  }
  if (problem === "svg") {
    return "settings.company.logo_svg_not_accepted"; // 415, the server's own key
  }
  if (problem === "unsupported_type") {
    return "settings.company.logo.badType"; // 415
  }
  return null;
}

/**
 * Human-sized bytes for the "what is on file" line. Display only, and never
 * near money — this is a file size, not a NUMERIC(18,6) amount.
 */
export function formatLogoSize(bytes: number | null): string | null {
  if (bytes === null || bytes < 0) {
    return null; // the server sent no size — say nothing rather than "0 KB"
  }
  if (bytes < 1024) {
    return `${bytes} B`;
  }
  const kb = bytes / 1024;
  return kb < 1024 ? `${Math.round(kb)} KB` : `${(kb / 1024).toFixed(1)} MB`;
}

/**
 * The file type as the word a person uses — `PNG`, `JPG`, `SVG` — never the
 * MIME string `image/png` (`DEF-TEN-10636`). An unknown type reads as its
 * subtype in capitals, so nothing is hidden.
 */
export function formatLogoType(contentType: string): string {
  const subtype = (contentType.split("/")[1] ?? contentType).split(";")[0].trim().toLowerCase();
  if (subtype === "jpeg" || subtype === "pjpeg") return "JPG";
  if (subtype.startsWith("svg")) return "SVG";
  return subtype.toUpperCase();
}

// ── The tab ────────────────────────────────────────────────────────────────

export interface CompanyTabProps {
  readOnly: boolean;
  client?: ApiClient;
}

export function CompanyTab(props: CompanyTabProps) {
  const { t } = useTranslation();
  const client = props.client ?? api;
  const fireToast = useToast();
  const queryClient = useQueryClient();

  const profileQuery = useQuery({
    queryKey: queryKeys.companyProfile,
    queryFn: () => getCompanyProfile(client),
  });

  // The draft sits above the panels so a rail-free tab still reverts cleanly.
  // `null` means "not touched yet" — the server's values render straight.
  const [edits, setEdits] = useState<CompanyDraft | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [refusal, setRefusal] = useState<Refusal | null>(null);
  // The logo is its OWN resource with its own endpoint, so it carries its own
  // error and its own toast — it is not part of the tab's atomic PUT.
  const [logoNotice, setLogoNotice] = useState<string | null>(null);
  const [logoError, setLogoError] = useState<string | null>(null);

  const uploadLogo = useMutation({
    mutationFn: (file: File) => uploadCompanyLogo(file, client),
    onSuccess: () => {
      // The 201 carries the new reference; the profile read is what renders it,
      // so re-read rather than patching a second copy into the cache.
      void queryClient.invalidateQueries({ queryKey: queryKeys.companyProfile });
      // DEF-SHL-4272 — the app shell draws the tenant's name and mark from `GET /shell/display`,
      // its OWN key. Saving here must invalidate it or the sidebar and every
      // date on screen keep the value that was just replaced until a reload.
      void queryClient.invalidateQueries({ queryKey: queryKeys.shellDisplay });
      // BR-TEN-015: the S62 checklist counts the logo as a company-profile gap.
      void queryClient.invalidateQueries({ queryKey: queryKeys.checklist });
      setLogoError(null);
      setLogoNotice(null);
      fireToast(t("settings.company.logo.uploaded"));
    },
    onError: (error: unknown) => {
      // 415 / 413 arrive as B12 r1 HTTP-series envelopes (`code: null`) and 422
      // as the ordinary catalog one — all three render as THIS field's error,
      // in the server's own words, with the size/type it names in params.
      setLogoNotice(null);
      setLogoError(apiErrorText(error, t));
    },
  });

  const save = useMutation({
    mutationFn: (changes: Partial<CompanyProfile>) => saveCompanyProfile(changes, client),
    onSuccess: (saved: CompanyProfile) => {
      queryClient.setQueryData(queryKeys.companyProfile, saved);
      // DEF-SHL-4272 — the app shell draws the tenant's name and mark from `GET /shell/display`,
      // its OWN key. Saving here must invalidate it or the sidebar and every
      // date on screen keep the value that was just replaced until a reload.
      void queryClient.invalidateQueries({ queryKey: queryKeys.shellDisplay });
      // BR-TEN-015: the S62 checklist derives company_profile from this data.
      void queryClient.invalidateQueries({ queryKey: queryKeys.checklist });
      setEdits(null);
      setFieldErrors({});
      setRefusal(null);
      fireToast(t("settings.company.saved"));
    },
    onError: (error: unknown) => {
      // B12 §3: field errors land under their fields, the rest is form-level.
      if (isApiError(error)) {
        const mapped = envelopeErrors(formErrorEnvelope(error), (key, params) => t(key, params));
        setFieldErrors(mapped.fields);
      }
      setRefusal(refusalOf(error, t));
    },
  });

  if (profileQuery.isPending) {
    return <LoadingSkeleton variant="card" />;
  }
  if (profileQuery.data === undefined) {
    if (isPermissionDenied(profileQuery.error)) {
      return <SettingsDenied helper={t("settings.denied.tab")} />;
    }
    return (
      <FailedWithRetry
        title={t("settings.company.failedTitle")}
        reason={apiErrorText(profileQuery.error, t)}
        onRetry={() => void profileQuery.refetch()}
        onDownloadReport={() => undefined}
        onCancel={() => void profileQuery.refetch()}
      />
    );
  }

  const original = draftFromProfile(profileQuery.data);
  const draft = edits ?? original;
  function patch(field: CompanyField, value: string): void {
    setEdits({ ...draft, [field]: value });
  }

  function handleSave(): void {
    const validation = collectFormErrors(companySchema(t), draft);
    setFieldErrors(validation.errors);
    setRefusal(null);
    if (validation.count > 0) {
      return; // BR-SHL-017: nothing is posted until the shape is right
    }
    save.mutate(companyChanges(draft, original));
  }

  function handleLogo(file: File | null): void {
    setLogoError(null);
    setLogoNotice(null);
    if (file === null) {
      return;
    }
    const key = logoProblemKey(logoProblem(file));
    if (key !== null) {
      // The client half of the logo law: refuse BEFORE the bytes leave, in the
      // shapes the server answers (413 too large / 415 wrong type or SVG).
      // This SAVES a round trip; the server re-checks the type and contents,
      // so it is a mirror of the law, never a replacement for it.
      setLogoError(t(key));
      return;
    }
    uploadLogo.mutate(file);
  }

  // BR-TEN-019: the letterhead preview renders LIVE from unsaved values. The
  // colors are tenant DATA, so they ride in as custom properties and the
  // painting itself stays in the stylesheet (no inline design values).
  const brandStyle = {
    "--settings-brand-primary": draft.brand_primary_hex === "" ? "transparent" : draft.brand_primary_hex,
    "--settings-brand-accent": draft.brand_accent_hex === "" ? "transparent" : draft.brand_accent_hex,
  } as CSSProperties;

  return (
    <div className="settings-tab">
      <PanelGrid>
        <Panel title={t("settings.company.details")} hint={t("settings.company.detailsHint")} accent>
          <TextField
            id="legal_name"
            label={t("settings.company.legalName")}
            value={draft.legal_name}
            onChange={(v) => patch("legal_name", v)}
            error={fieldErrors.legal_name}
          />
          <TextField
            id="dba_name"
            label={t("settings.company.dbaName")}
            value={draft.dba_name}
            onChange={(v) => patch("dba_name", v)}
            error={fieldErrors.dba_name}
          />
          {/* CR-060 C7 / task T2 — beside legal name and DBA, because it is an
              identity FACT and that is where identity lives. There is no empty
              option: the server seeds `utility` and falls back to it, so there
              is no unknown state for a placeholder to represent. The OPTIONS
              come from the server's own `organisation_types`, never from a copy
              held here (B14's one-vocabulary posture). */}
          <SelectField
            id="organisation_type"
            label={t("settings.company.organisationType", {
              defaultValue: "Organisation type",
            })}
            value={draft.organisation_type}
            onChange={(v) => patch("organisation_type", v)}
            required
            options={profileQuery.data.organisation_types.map((value) => ({
              value,
              label: t(`settings.company.organisationType.${value}`, {
                defaultValue: ORGANISATION_TYPE_ENGLISH[value] ?? value,
              }),
            }))}
            error={fieldErrors.organisation_type}
          />
          <TextField
            id="ein"
            label={t("settings.company.ein")}
            value={draft.ein}
            onChange={(v) => patch("ein", v)}
            help={t("settings.company.einHelp")}
            error={fieldErrors.ein}
          />
          <TextField
            id="state_utility_id"
            label={t("settings.company.stateUtilityId")}
            value={draft.state_utility_id}
            onChange={(v) => patch("state_utility_id", v)}
            error={fieldErrors.state_utility_id}
          />
          <TextField
            id="mailing_address"
            label={t("settings.company.mailingAddress")}
            value={draft.mailing_address}
            onChange={(v) => patch("mailing_address", v)}
            error={fieldErrors.mailing_address}
          />
          <TextField
            id="support_phone"
            label={t("settings.company.supportPhone")}
            value={draft.support_phone}
            onChange={(v) => patch("support_phone", v)}
            error={fieldErrors.support_phone}
          />
          <TextField
            id="support_email"
            label={t("settings.company.supportEmail")}
            value={draft.support_email}
            onChange={(v) => patch("support_email", v)}
            error={fieldErrors.support_email}
          />
          <TextField
            id="website"
            label={t("settings.company.website")}
            value={draft.website}
            onChange={(v) => patch("website", v)}
            error={fieldErrors.website}
          />
        </Panel>

        <Panel title={t("settings.company.brand")} hint={t("settings.company.brandHint")}>
          <div className="settings-dropzone">
            <label htmlFor="company-logo">{t("settings.company.logo.drop")}</label>
            <input
              id="company-logo"
              type="file"
              accept={LOGO_TYPES.join(",")}
              disabled={props.readOnly || uploadLogo.isPending}
              onChange={(event) => handleLogo(event.target.files?.[0] ?? null)}
            />
          </div>
          {/* BR-TEN-019: what is ON FILE. The endpoint returns a REFERENCE, not
              bytes, and no route streams the image back — so this states the
              stored facts instead of drawing an <img> at a URL that does not
              exist. There is also no remove control: the API has no DELETE. */}
          <LogoOnFile logo={profileQuery.data.logo} working={uploadLogo.isPending} />
          {logoError !== null && (
            <RefusalStrip role="alert">
              {logoError}
            </RefusalStrip>
          )}
          {logoNotice !== null && (
            <RefusalStrip role="alert">
              {logoNotice}
            </RefusalStrip>
          )}
          {/* r10 SET-01.profile draws a filled chip beside each hex input. It
              is not decoration: a six-character hex is unreadable as a COLOUR,
              so without the chip the only way to check you typed the right one
              is to save and look at a bill. The chip is `aria-hidden` — it
              restates the input's own value and would otherwise be announced
              twice — and it paints from the DRAFT, so it answers while you
              type. `#RRGGBB` is tenant data, so it rides in as a custom
              property and the painting stays in the stylesheet (B8: no hex
              literals in TSX). An empty or half-typed value paints nothing
              rather than guessing at black. */}
          <ColorField
            id="brand_primary_hex"
            label={t("settings.company.primaryColor")}
            value={draft.brand_primary_hex}
            onChange={(v) => patch("brand_primary_hex", v)}
            placeholder="#1B5E9E"
            error={fieldErrors.brand_primary_hex}
          />
          <ColorField
            id="brand_accent_hex"
            label={t("settings.company.accentColor")}
            value={draft.brand_accent_hex}
            onChange={(v) => patch("brand_accent_hex", v)}
            // r10 seeds the bill accent #0F7A6B. The old #201E1D was the ink
            // token, which read as "the default is near-black" — it is not.
            placeholder="#0F7A6B"
            error={fieldErrors.brand_accent_hex}
          />
          {/* CR-199-BRC10 S5 (PO ruling 1A) — where the logo in every customer
              email points. Set ONCE here; the Templates preview reads it. */}
          <TextField
            id="brand_logo_link_url"
            label={t("settings.company.logoLink")}
            value={draft.brand_logo_link_url}
            onChange={(v) => patch("brand_logo_link_url", v)}
            placeholder="https://"
            error={fieldErrors.brand_logo_link_url}
          />
          <div className="settings-letterhead" style={brandStyle}>
            {/* CR-048 wave D / DEF-195. This was `<span
                className="settings-letterhead-mark" aria-hidden />` — a 26x26
                block of the brand colour with NO LETTERS IN IT, rendering
                identically with a logo on file and without one, so the one
                screen a utility uses to confirm its branding could not tell
                them whether their upload had worked. It now draws the logo
                when there is one and the generated two-letter mark when there
                is not, and it keeps rendering LIVE from unsaved values
                (BR-TEN-019) — type a new trading name and the letters change
                before you save. */}
            <BrandMark
              className="settings-letterhead-mark"
              mark={previewMark(draft)}
              hasLogo={profileQuery.data.has_logo}
              logoRef={profileQuery.data.logo_ref}
              size={MARK_SIZE_LETTERHEAD}
              name={draft.dba_name === "" ? draft.legal_name : draft.dba_name}
            />
            <div>
              <b>{draft.dba_name === "" ? draft.legal_name : draft.dba_name}</b>
              <div className="settings-letterhead-note">
                {/* CR-048 wave D. The preview now says WHICH of the two things
                    it is showing. Before, it showed the same coloured square
                    either way and said nothing, so a utility had no way to
                    tell a working upload from a broken one. */}
                {profileQuery.data.has_logo
                  ? t("settings.company.letterheadNote")
                  : t("settings.company.mark.generated")}
              </div>
            </div>
          </div>
          {/* The contrast rule, said out loud. A utility that picks a pale
              colour will see black letters appear and should know that is
              deliberate — the product never changes their colour, only the
              text drawn on it (OQ-800(a), decided 2026-08-30). */}
          {!profileQuery.data.has_logo && <Note>{t("settings.company.mark.readable")}</Note>}
        </Panel>

        <Panel title={t("settings.company.remittance")} hint={t("settings.company.remittanceHint")}>
          <TextField
            id="remit_to_address"
            label={t("settings.company.remitTo")}
            value={draft.remit_to_address}
            onChange={(v) => patch("remit_to_address", v)}
            error={fieldErrors.remit_to_address}
          />
          <TextField
            id="remit_payable_to"
            label={t("settings.company.payableTo")}
            value={draft.remit_payable_to}
            onChange={(v) => patch("remit_payable_to", v)}
            error={fieldErrors.remit_payable_to}
          />
          <TextField
            id="service_hours"
            label={t("settings.company.serviceHours")}
            value={draft.service_hours}
            onChange={(v) => patch("service_hours", v)}
            error={fieldErrors.service_hours}
          />
        </Panel>
      </PanelGrid>

      <RefusalNotice refusal={refusal} />

      <SaveBar
        saveLabel={t("settings.company.save")}
        working={save.isPending}
        dirty={isDirty(draft, original)}
        readOnly={props.readOnly}
        readOnlyReason={t("settings.readOnlyReason")}
        onSave={handleSave}
        onDiscard={() => {
          setEdits(null);
          setFieldErrors({});
          setRefusal(null);
        }}
        // BR-TEN-017 stated where the user is about to change identity values.
        note={t("settings.company.issuedNote")}
      />

      {/* US-TEN-019 / BR-TEN-069 (2026-08-16, unreachable-screens lane): BOTH
          sample-data actions live on Company profile, and the rule is explicit
          about the placement. It sits BELOW the SaveBar deliberately — it is
          not part of the BR-TEN-024 atomic draft this tab commits, it writes
          through its own endpoints, and putting it inside the draft's panel
          grid would imply Save/Discard governed it. */}
      <SampleDataPanel readOnly={props.readOnly} client={props.client} />
    </div>
  );
}

/**
 * A hex field with r10's live colour chip beside it (SET-01.profile).
 *
 * `isPaintableHex` is the same shape `companySchema` validates, deliberately:
 * the chip must appear exactly when the value is one the server would accept,
 * so a chip on screen is itself the "this hex is well-formed" signal and a user
 * mid-keystroke is never shown a colour for input that will be refused.
 */
export function isPaintableHex(value: string): boolean {
  return HEX_SHAPE.test(value);
}

function ColorField(props: {
  id: CompanyField;
  label: string;
  value: string;
  onChange: (value: string) => void;
  placeholder: string;
  error?: string;
}) {
  const swatch = { "--settings-swatch": props.value } as CSSProperties;
  return (
    <div className="settings-color-field">
      {isPaintableHex(props.value) && (
        <span className="settings-swatch" style={swatch} aria-hidden="true" />
      )}
      <TextField
        id={props.id}
        label={props.label}
        value={props.value}
        onChange={props.onChange}
        placeholder={props.placeholder}
        error={props.error}
      />
    </div>
  );
}

/**
 * The stored-logo line. BR-TEN-019 gives back a reference (`logo_file_id`,
 * content type, size); this renders the type and the size. The reference is a
 * database id and is NEVER drawn (B14 rule 31, `DEF-TEN-10636` — it printed
 * beside the size until 2.605). It offers no Remove: `POST /settings/company/logo`
 * has no DELETE sibling, and a control that 405s is worse than none.
 */
function LogoOnFile(props: { logo: CompanyLogo | null; working: boolean }) {
  const { t } = useTranslation();
  if (props.working) {
    return <Note>{t("settings.company.logo.uploading")}</Note>;
  }
  if (props.logo === null) {
    return <Note>{t("settings.company.logo.none")}</Note>;
  }
  const size = formatLogoSize(props.logo.size_bytes);
  return (
    <Note>
      {t("settings.company.logo.onFile", {
        type: formatLogoType(props.logo.content_type),
        size: size ?? t("settings.company.logo.sizeUnknown"),
      })}
    </Note>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-TEN-005@0733260 (story+rules snapshot hash — EP-TEN-05)
// generated: 2026-08-09 by story-coder v1 (W0 Settings screens lane) · AMENDED 2026-08-09 by story-coder (frontend integration lane: the logo upload works end to end)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: trace_lint✔ run_gates✔ (11 PASS · 0 FAIL · 1 SKIP) tsc✔ eslint✔ vitest 296 passed / 83 todo across 30 files✔ (239+72 baseline unchanged and green; this packet adds 57 passing + 11 todo — the todos are browser-interaction, server/RLS and unbuilt-neighbour-screen scope)
// exceptions: E4 "Last edited by {user} · {date}" (US-TEN-005 §1) has no field in `GET /settings/company`; it is NOT rendered rather than invented — reported · E3 the logo endpoint returns a REFERENCE and no route streams the bytes back (no signed-URL/document-delivery contract exists in core), so the panel states type/size/id instead of drawing an <img> at a URL that does not exist — reported · E3 there is no DELETE for the logo (neither US-TEN-005 nor the prototype anchors removal), so no remove control is offered — a replacement upload is the only path · E4 BR-TEN-019's "rasterized for PDF/print" clause is the W6 renderer's, not this screen's
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
