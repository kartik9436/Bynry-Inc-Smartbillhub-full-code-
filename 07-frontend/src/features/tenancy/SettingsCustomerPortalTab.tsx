// ── Trace ──────────────────────────────────────────────
// Story:    US-CWP-069 (EP-CWP-12) — Portal settings · Overview: the address a
//           utility could never find, the switch, and the five ·
//           US-CWP-070 — Branding: read from Company → Profile, stored nowhere
//           twice, with a live preview. Screens: CWP-069 · CWP-070
// Rules:    08-screen-layouts.md CWP-069 (T8 + TwoCol: address panel · five
//           switch rows · THE PORTAL IS · WHO IS USING IT) and CWP-070 (SHARED
//           WITH YOUR BILLS AND LETTERS read-only + *Edit in Company* · PORTAL
//           ONLY · a live miniature of CWP-001) · CR-068 R8 · hard-won law 3 ·
//           B14 rule 21 (this file is on route-b-migrated.txt) · rule 31 (no
//           id is a visible value — the service picker shows names, sends ids)
//           · rule 32 (one sentence per section) · rule 33 · BR-SHL-025 (a
//           view-only role sees the controls disabled with the reason)
// Tests:    src/features/tenancy/SettingsCustomerPortalTab.test.tsx
// Impacts:  src/api/portalSettingsEndpoints.ts · SettingsPage.tsx (the
//           `customer-portal` Configure segment and the `:segment` route) ·
//           src/portal/guest/FrontPageView.tsx (the preview IS the front page)
// ───────────────────────────────────────────────────────
//
// ⚠ STAFF SCREENS. CWP-069–075 carry portal numbers because the blueprint drew
// them, and they live HERE, in the staff app's Settings, never behind a
// customer login (EP-CWP-12 scope note).
//
// ⚠ Every utility here was asked of the compiler (see primitives.tsx in the
// portal folder): no `bg-white`, no `text-lg`, no `slate` — they render
// nothing under this theme.

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate, useParams } from "react-router-dom";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import {
  getPortalBranding,
  getPortalSettings,
  portalQrUrl,
  savePortalBranding,
  savePortalSettings,
} from "@/api/portalSettingsEndpoints";
import type {
  PortalBranding,
  PortalBrandingFields,
  PortalSettings,
  PortalUsageRow,
} from "@/api/portalSettingsEndpoints";
import { queryKeys } from "@/api/queryClient";
import { refusalText } from "@/api/refusalText";
import { Button, ButtonAnchor } from "@/components/Button";
import { ChipMultiSelect } from "@/components/ChipMultiSelect";
import { Switch } from "@/components/Switch";
import { FailedWithRetry, LoadingSkeleton } from "@/components/StateFrame";
import { useToast } from "@/components/Toast";
import { FrontPageView } from "@/portal/guest/FrontPageView";
import { brandStyle } from "@/portal/shell/GuestFrame";
import { useTenantPath } from "@/routing/tenantPath";

import { BrandMark } from "./BrandMark";
import { AgreementLinkDaysField } from "./SettingsAgreementLinkDays";
import { CONFIGURE_TAB } from "./SettingsPage";
import { PortalHelpEditor, PortalHelpList } from "./SettingsPortalHelp";
import { PortalTipsList } from "./SettingsPortalTips";
import { RefusalNotice, refusalOf } from "./settingsShared";

export const CUSTOMER_PORTAL_SUB_TAB = "customer-portal";

/** The third-level strip the wireframe draws. ⚠ Help & answers and Tips were
 *  ABSENT until CR-068 wave D landed the tables behind them (2026-09-04) —
 *  a segment with nothing behind it is the honest-absence trap hard-won law 1
 *  names, so they arrived with their screens and not before. */
export const PORTAL_SEGMENTS = [
  { id: "overview", labelKey: "settings.portal.segment.overview" },
  { id: "branding", labelKey: "settings.portal.segment.branding" },
  { id: "help", labelKey: "settings.portal.segment.help" },
  { id: "tips", labelKey: "settings.portal.segment.tips" },
] as const;

export type PortalSegment = (typeof PORTAL_SEGMENTS)[number]["id"];

export function portalSegmentFromParam(raw: string | undefined): PortalSegment {
  return PORTAL_SEGMENTS.some((seg) => seg.id === raw) ? (raw as PortalSegment) : "overview";
}

const SWITCH_ROWS = [
  "quick_pay_enabled",
  "self_read_enabled",
  "plans_enabled",
  "requests_enabled",
  "outage_reporting_enabled",
] as const;

type SwitchKey = (typeof SWITCH_ROWS)[number];

/** Copy for a switch row, as LITERAL keys so G27 can see every one. */
const SWITCH_COPY: Record<SwitchKey, { name: string; sub: string }> = {
  quick_pay_enabled: { name: "settings.portal.switch.quick_pay.name", sub: "settings.portal.switch.quick_pay.sub" },
  self_read_enabled: { name: "settings.portal.switch.self_read.name", sub: "settings.portal.switch.self_read.sub" },
  plans_enabled: { name: "settings.portal.switch.plans.name", sub: "settings.portal.switch.plans.sub" },
  requests_enabled: { name: "settings.portal.switch.requests.name", sub: "settings.portal.switch.requests.sub" },
  outage_reporting_enabled: {
    name: "settings.portal.switch.outage.name",
    sub: "settings.portal.switch.outage.sub",
  },
};

const USAGE_COPY: Record<PortalUsageRow["key"], string> = {
  requests_from_portal: "settings.portal.usage.requests_from_portal",
  readings_sent_in: "settings.portal.usage.readings_sent_in",
  customers_enrolled: "settings.portal.usage.customers_enrolled",
  signed_in_this_month: "settings.portal.usage.signed_in_this_month",
};

const USAGE_REASON: Record<NonNullable<PortalUsageRow["reason"]>, string> = {
  readings_off: "settings.portal.usage.reason.readings_off",
};

/** A panel: small-caps header row with a bottom rule, then a body. */
function Panel(props: { title: string; link?: React.ReactNode; children: React.ReactNode }) {
  return (
    <section className="border border-neutral-200 bg-[white]">
      <header className="flex items-center justify-between border-b border-neutral-200 px-4 py-3">
        <h3 className="text-xs font-bold uppercase tracking-wide text-neutral-900">{props.title}</h3>
        {props.link}
      </header>
      <div className="p-4 text-body text-neutral-700">{props.children}</div>
    </section>
  );
}

/**
 * ⚠ **REPLACED BY THE KIT'S `Switch` ON 2026-09-04 — B14 rule 36 breach (d),
 * named in the rule itself:** *"the portal's Overview drew on/off as bordered
 * word-buttons rather than a control"*. This wrapper keeps the call sites'
 * shape and hands the visual decision to the one component that now owns it,
 * so this screen, the tips list and the service-centre editor cannot drift
 * into three different switches.
 */
function OnOff(props: { on: boolean; disabled: boolean; label: string; onChange: (on: boolean) => void }) {
  const { t } = useTranslation();
  return (
    <Switch
      on={props.on}
      label={props.label}
      onLabel={t("settings.portal.on")}
      offLabel={t("settings.portal.off")}
      disabled={props.disabled}
      onChange={props.onChange}
    />
  );
}

// ── CWP-069 · Overview ───────────────────────────────────────────────────────

function Overview(props: { readOnly: boolean; client: ApiClient }) {
  const { t } = useTranslation();
  const { readOnly, client } = props;
  const queryClient = useQueryClient();
  const fireToast = useToast();
  const tenantPath = useTenantPath();
  const navigate = useNavigate();
  const query = useQuery({ queryKey: queryKeys.portalSettings, queryFn: () => getPortalSettings(client) });
  const [copied, setCopied] = useState(false);
  const save = useMutation({
    mutationFn: (changes: Parameters<typeof savePortalSettings>[0]) => savePortalSettings(changes, client),
    onSuccess: (data) => {
      queryClient.setQueryData(queryKeys.portalSettings, data);
      void queryClient.invalidateQueries({ queryKey: queryKeys.portalBranding });
      fireToast(t("settings.portal.saved"));
    },
  });

  if (query.isPending) return <LoadingSkeleton variant="card" />;
  if (query.data === undefined) {
    return (
      <FailedWithRetry
        title={t("settings.portal.failedTitle")}
        reason={refusalText(t, query.error)}
        onRetry={() => void query.refetch()}
        onDownloadReport={() => undefined}
      />
    );
  }
  const data: PortalSettings = query.data;
  const address = data.address.url ?? `${window.location.origin}${data.address.path}`;
  const qrUrl = portalQrUrl(data.address.slug, false);
  const qrDownload = portalQrUrl(data.address.slug, true);
  const readOnlyReason = t("settings.readOnlyReason");

  return (
    <div data-screen="CWP-069" className="flex flex-col gap-4">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <p className="text-xs font-bold uppercase tracking-wide text-neutral-900">{t("settings.portal.kicker")}</p>
          <h2 className="text-h3 font-bold leading-tight text-neutral-900">{t("settings.portal.overview.title")}</h2>
          <p className="mt-1 max-w-[640px] text-body text-neutral-600">{t("settings.portal.overview.subtitle")}</p>
        </div>
        <ButtonAnchor href={address} target="_blank" rel="noopener" data-action="open-portal">
          {t("settings.portal.openPortal")}
        </ButtonAnchor>
      </header>
      <RefusalNotice refusal={save.isError ? refusalOf(save.error, t) : null} />
      <div className="grid grid-cols-12 gap-4">
        <div className="col-span-12 flex flex-col gap-4 md:col-span-8">
          <Panel title={t("settings.portal.address.title")}>
            <div className="flex flex-wrap items-center gap-2 border border-divider bg-surface px-3 py-2">
              <code className="min-w-0 flex-1 break-all font-mono text-md" data-portal-address="">
                {address}
              </code>
              <Button
                size="sm"
                onClick={() => {
                  void navigator.clipboard?.writeText(address);
                  setCopied(true);
                }}
              >
                {copied ? t("settings.portal.address.copied") : t("settings.portal.address.copy")}
              </Button>
              <ButtonAnchor size="sm" href={address} target="_blank" rel="noopener">
                {t("settings.portal.address.open")}
              </ButtonAnchor>
            </div>
            <p className="mt-2 text-base text-neutral-600">{t("settings.portal.address.sentence")}</p>
            <div className="mt-4 flex flex-wrap items-center gap-2">
              <ButtonAnchor size="sm" href={qrDownload} data-action="qr-download">
                {t("settings.portal.address.qr")}
              </ButtonAnchor>
              <Button size="sm" onClick={() => navigate(tenantPath(`/settings/${CONFIGURE_TAB}/templates`))} data-action="add-to-template">
                {t("settings.portal.address.addToTemplate")}
              </Button>
            </div>
            <img
              src={qrUrl}
              alt={t("settings.portal.address.qrAlt")}
              className="mt-4 h-32 w-32 border border-neutral-200"
              data-portal-qr=""
            />
          </Panel>
          <Panel title={t("settings.portal.switches.title")}>
            <ul className="divide-y divide-neutral-200">
              {SWITCH_ROWS.map((key) => (
                <li key={key} className="flex items-center justify-between gap-4 py-3" data-switch={key}>
                  <div className="min-w-0">
                    <p className="font-bold text-neutral-900">{t(SWITCH_COPY[key].name)}</p>
                    <p className="text-base text-neutral-600">{t(SWITCH_COPY[key].sub)}</p>
                  </div>
                  <OnOff
                    on={data.switches[key]}
                    disabled={readOnly || save.isPending}
                    label={t(SWITCH_COPY[key].name)}
                    onChange={(on) => save.mutate({ [key]: on })}
                  />
                </li>
              ))}
            </ul>
            {readOnly ? <p className="mt-2 text-base text-neutral-600">{readOnlyReason}</p> : null}
            {/* CR-190-BRC10 — the agreement link's life, a setting (seeded 7). */}
            <div className="mt-3 border-t border-neutral-200 pt-3">
              <AgreementLinkDaysField
                days={data.agreement_link_valid_days}
                readOnly={readOnly}
                readOnlyReason={readOnlyReason}
                saving={save.isPending}
                onSave={(days) => save.mutate({ agreement_link_valid_days: days })}
              />
            </div>
            {/* DEF-BIL-10531 — the bill email link's life, a setting (seeded 30). */}
            <div className="mt-3 border-t border-neutral-200 pt-3">
              <AgreementLinkDaysField
                days={data.bill_link_valid_days}
                readOnly={readOnly}
                readOnlyReason={readOnlyReason}
                saving={save.isPending}
                onSave={(days) => save.mutate({ bill_link_valid_days: days })}
                setting="bill_link_valid_days"
                fieldId="bill-link-days"
                labelKey="settings.portal.billLinkDays"
              />
            </div>
          </Panel>
        </div>
        <div className="col-span-12 flex flex-col gap-4 md:col-span-4">
          <Panel title={t("settings.portal.live.title")}>
            <p className="text-h4 font-bold text-neutral-900" data-portal-live={data.is_live ? "live" : "off"}>
              {data.is_live ? t("settings.portal.live.on") : t("settings.portal.live.off")}
            </p>
            <p className="mt-1 text-base text-neutral-600">{t("settings.portal.live.sentence")}</p>
            <div className="mt-3">
              <OnOff
                on={data.is_live}
                disabled={readOnly || save.isPending}
                label={t("settings.portal.live.title")}
                onChange={(on) => save.mutate({ is_live: on })}
              />
            </div>
          </Panel>
          <Panel title={t("settings.portal.usage.title")}>
            <dl>
              {data.usage.map((row) => (
                <div
                  key={row.key}
                  className="flex items-baseline justify-between gap-3 border-b border-neutral-200 py-2 text-body"
                  data-usage={row.key}
                >
                  <dt className="text-neutral-600">{t(USAGE_COPY[row.key])}</dt>
                  <dd className="text-right font-semibold tabular-nums">
                    {row.count === null ? "—" : row.count.toLocaleString()}
                  </dd>
                </div>
              ))}
            </dl>
            {data.usage
              .filter((row) => row.reason !== null)
              .map((row) => (
                <p key={row.key} className="mt-2 text-base text-neutral-600" data-usage-reason={row.reason ?? ""}>
                  {t(USAGE_REASON[row.reason as NonNullable<PortalUsageRow["reason"]>])}
                </p>
              ))}
          </Panel>
        </div>
      </div>
    </div>
  );
}

/**
 * THE FRONT PAGE, DRAWN AT ITS OWN WIDTH AND SHRUNK TO FIT — `DEF-CWP-3723`.
 *
 * ⚠ **WHY THE OLD ONE BROKE, AND WHY NO TEST COULD SEE IT.** The preview
 * rendered the real `FrontPageView` straight into a four-of-twelve column: 329
 * pixels, measured on the running product at a 1440-wide window. `CardGrid3` is
 * `md:grid-cols-3`, and `md:` is a **VIEWPORT** query, not a container one — so
 * the browser saw a 1440px window, drew three columns, and gave each card about
 * 90px. The result wrapped **one word per line for eleven lines** and the
 * *Sign in* button sat on top of the info icon. Every suite in this repo asserts
 * on TEXT CONTENT, and text content is identical however it wraps: the same
 * sentence in one line and in eleven is byte-for-byte the same string, so
 * nothing went red and the PO found it by looking (hard-won law 6).
 *
 * ⚠ **THE FIX IS TO STOP LYING ABOUT THE WIDTH.** A preview of a page is a
 * MINIATURE of that page, so the page is laid out at the width a visitor's
 * browser really gives it — `GuestFrame` caps its main column at 1100px — and
 * the whole thing is then scaled down to whatever the panel has. Every line
 * break, every column and every wrap is then the one a customer will see, which
 * is the only thing a live preview is for. Restyling the front page to fit a
 * narrow box would have made the preview *legible* and *wrong*.
 *
 * ⚠ **AND THE SCALE IS MEASURED, NOT GUESSED.** A hard-coded factor is right at
 * one window width and wrong at every other, and this panel is `md:col-span-4`
 * — a different number of pixels on a laptop, a wide monitor and a phone.
 * `ResizeObserver` reads the panel and the transform follows it. The outer box
 * then takes the SCALED height, because a transform does not change layout:
 * without that line the panel reserves the full 1100px-wide page's height and
 * leaves a screenful of white space under a small picture.
 *
 * `aria-hidden`: it is a PICTURE of a page. Its buttons must not be reachable by
 * tab or read out as if they were this screen's own controls — a screen reader
 * announcing a *Start* button that belongs in a customer's browser is a control
 * onto nothing (hard-won law 2).
 *
 * ⚠ **WITHOUT `ResizeObserver` IT RENDERS AT 1:1 AND CLIPS, WHICH IS THE HONEST
 * FALLBACK.** jsdom has none, so the static suite sees the page at its real
 * width — which is what those tests are asserting about anyway. Every browser
 * this product supports has had it since 2018.
 */
const PREVIEW_PAGE_WIDTH = 1100;

function PagePreview(props: { brand: React.CSSProperties; children: React.ReactNode }) {
  const frame = useRef<HTMLDivElement | null>(null);
  const page = useRef<HTMLDivElement | null>(null);
  const [scale, setScale] = useState(1);
  const [height, setHeight] = useState(0);

  useEffect(() => {
    const outer = frame.current;
    const inner = page.current;
    if (outer === null || inner === null || typeof ResizeObserver === "undefined") return;
    const measure = () => {
      const next = outer.clientWidth / PREVIEW_PAGE_WIDTH;
      setScale(next);
      setHeight(inner.offsetHeight * next);
    };
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(outer);
    observer.observe(inner);
    return () => observer.disconnect();
  }, []);

  return (
    <div
      ref={frame}
      className="overflow-hidden border border-neutral-200 bg-bg"
      style={{ height: height === 0 ? undefined : height }}
      data-portal-preview=""
      data-preview-scale={scale.toFixed(3)}
    >
      <div
        ref={page}
        aria-hidden="true"
        className="origin-top-left"
        style={{ ...props.brand, width: PREVIEW_PAGE_WIDTH, transform: `scale(${scale})` }}
        data-preview-page=""
      >
        {props.children}
      </div>
    </div>
  );
}

// ── CWP-070 · Branding ───────────────────────────────────────────────────────

const EMPTY_FIELDS: PortalBrandingFields = {
  strapline: null,
  front_page_service_ids: [],
  office_hours_text: null,
  emergency_phone: null,
};

function ReadOnlyField(props: { label: string; value: string }) {
  return (
    <div>
      <p className="mb-1 text-base font-semibold text-neutral-900">{props.label}</p>
      {/* ⚠ NO LONGER A GREY SLAB THE SHAPE OF AN INPUT (B14 rule 36). Four
          read-only facts drawn as bordered boxes at input height read as four
          fields that will not accept typing, which is the most frustrating
          thing a form can do. A fact is a fact: the label above, the value
          beneath, and the *Edit in Company* link this panel already carries is
          the way to change it. */}
      <p className="m-0 text-body text-neutral-700" data-readonly="">
        {props.value}
      </p>
    </div>
  );
}

/**
 * CR-172-BRC10 / DEF-TEN-9705 — the logo ITSELF, where this row used to say
 * only *On file*. Drawn by `BrandMark` from the one logo address the header and
 * Company › Brand use, so a utility sees here exactly what its customers see;
 * with no logo it draws the generated mark and says so.
 */
function LogoField(props: { label: string; shared: PortalBranding["shared"]; noneLabel: string }) {
  return (
    <div>
      <p className="mb-1 text-base font-semibold text-neutral-900">{props.label}</p>
      <div className="flex items-center gap-3" data-portal-logo="" data-readonly="">
        <BrandMark
          mark={props.shared.mark}
          hasLogo={props.shared.has_logo}
          logoRef={props.shared.logo_ref}
          size={48}
          name={props.shared.trading_name}
        />
        {!props.shared.has_logo && <span className="text-body text-neutral-700">{props.noneLabel}</span>}
      </div>
    </div>
  );
}

function Branding(props: { readOnly: boolean; client: ApiClient }) {
  const { t } = useTranslation();
  const { readOnly, client } = props;
  const queryClient = useQueryClient();
  const fireToast = useToast();
  const tenantPath = useTenantPath();
  const query = useQuery({ queryKey: queryKeys.portalBranding, queryFn: () => getPortalBranding(client) });
  // Seeded from the cache when the read is already answered (a static first
  // paint, a warm cache) and by the effect when it arrives later — an effect
  // alone never runs at `renderToStaticMarkup`, and a draft that waits for one
  // is a skeleton the test suite cannot see past.
  const [draft, setDraft] = useState<PortalBrandingFields | null>(() => query.data?.portal_only ?? null);
  useEffect(() => {
    if (query.data !== undefined && draft === null) setDraft(query.data.portal_only);
  }, [query.data, draft]);
  const save = useMutation({
    mutationFn: (changes: Partial<PortalBrandingFields>) => savePortalBranding(changes, client),
    onSuccess: (data) => {
      queryClient.setQueryData(queryKeys.portalBranding, data);
      void queryClient.invalidateQueries({ queryKey: queryKeys.portalFront });
      setDraft(data.portal_only);
      fireToast(t("settings.portal.saved"));
    },
  });

  if (query.isPending || draft === null) return <LoadingSkeleton variant="card" />;
  if (query.data === undefined) {
    return (
      <FailedWithRetry
        title={t("settings.portal.failedTitle")}
        reason={refusalText(t, query.error)}
        onRetry={() => void query.refetch()}
        onDownloadReport={() => undefined}
      />
    );
  }
  const data: PortalBranding = query.data;
  const dirty = JSON.stringify(draft) !== JSON.stringify(data.portal_only);
  const readOnlyReason = t("settings.readOnlyReason");

  // THE PREVIEW: the server's front-page data with the DRAFT's portal-only
  // fields laid over it, drawn by the same component a visitor gets. Updates
  // as you type; nothing is saved until Save (US-CWP-070 TC-3).
  const byId = new Map(data.services.map((row) => [row.id, row]));
  const preview = {
    ...data.preview,
    is_live: true,
    strapline: draft.strapline,
    office_hours_text: draft.office_hours_text,
    emergency_phone: draft.emergency_phone,
    services: draft.front_page_service_ids
      .map((id) => byId.get(id))
      .filter((row): row is NonNullable<typeof row> => row !== undefined)
      .map((row) => ({ code: row.code, name: row.name, color: row.color })),
  };

  const field = (key: keyof PortalBrandingFields, value: string | string[]) =>
    setDraft({ ...draft, [key]: typeof value === "string" ? (value === "" ? null : value) : value });

  return (
    <div data-screen="CWP-070" className="flex flex-col gap-4">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <p className="text-xs font-bold uppercase tracking-wide text-neutral-900">{t("settings.portal.kicker")}</p>
          <h2 className="text-h3 font-bold leading-tight text-neutral-900">{t("settings.portal.branding.title")}</h2>
          <p className="mt-1 max-w-[640px] text-body text-neutral-600">{t("settings.portal.branding.subtitle")}</p>
        </div>
        <div className="flex items-center gap-2">
          {/* ⚠ r10 RULE 6 — THE DANGER TIER IS FOR THE DESTRUCTIVE COMMIT, AND
              ON THIS SCREEN THAT IS *Reset to defaults*, NOT *Save*. Reset
              writes `EMPTY_FIELDS`: it wipes the strapline, the office hours,
              the emergency number and the whole front-page service list in one
              press, with no undo. It was the calm outlined secondary while
              Save — the ordinary, reversible commit — was the loudest thing on
              the page, and the PO read that emphasis as backwards on
              2026-09-04. Outlined at rest and filled on hover, so the press is
              not reachable without the colour having changed first. */}
          <Button
            variant="danger"
            disabled={readOnly || save.isPending}
            title={readOnly ? readOnlyReason : undefined}
            onClick={() => save.mutate(EMPTY_FIELDS)}
            data-action="reset"
          >
            {t("settings.portal.branding.reset")}
          </Button>
          <Button
            variant="primary"
            disabled={readOnly || !dirty || save.isPending}
            title={readOnly ? readOnlyReason : undefined}
            onClick={() => save.mutate(draft)}
            data-action="save"
          >
            {t("settings.portal.save")}
          </Button>
        </div>
      </header>
      <RefusalNotice refusal={save.isError ? refusalOf(save.error, t) : null} />
      <div className="grid grid-cols-12 gap-4">
        <div className="col-span-12 flex flex-col gap-4 md:col-span-8">
          <Panel
            title={t("settings.portal.shared.title")}
            link={
              <a href={tenantPath(data.shared.edited_at)} className="text-base text-accent underline" data-link="edit-in-company">
                {t("settings.portal.shared.editInCompany")}
              </a>
            }
          >
            <div className="grid grid-cols-2 gap-4">
              <LogoField
                label={t("settings.portal.shared.logo")}
                shared={data.shared}
                noneLabel={t("settings.portal.shared.logoNone")}
              />
              <ReadOnlyField label={t("settings.portal.shared.tradingName")} value={data.shared.trading_name} />
              <ReadOnlyField label={t("settings.portal.shared.brandColour")} value={data.shared.brand_primary_hex ?? "—"} />
              <ReadOnlyField label={t("settings.portal.shared.accentColour")} value={data.shared.brand_accent_hex ?? "—"} />
            </div>
            <p className="mt-3 text-base text-neutral-600">{t("settings.portal.shared.sentence")}</p>
          </Panel>
          <Panel title={t("settings.portal.only.title")}>
            <label className="block">
              <span className="mb-1 block text-base font-semibold text-neutral-900">{t("settings.portal.only.strapline")}</span>
              <textarea
                className="input min-h-24 w-full resize-y"
                value={draft.strapline ?? ""}
                maxLength={140}
                readOnly={readOnly}
                onChange={(e) => field("strapline", e.target.value)}
                data-field="strapline"
              />
            </label>
            {/* ⚠ **CHIPS, NOT A WALL OF CHECKBOXES** — r10 rule 9 forbids it
                by name and B14 rule 36 breach (e) names THIS field: *"the
                portal's Branding screen drew* Services shown on the front page
                *as a WALL OF CHECKBOXES"*. Fixed here rather than filed,
                because the kit piece it needed now exists and this wave was
                already in the file (`DEF-CWP-3648`). The chip carries the
                service NAME and sends its id — rule 31 is untouched. */}
            <div className="mt-4">
              <p className="mb-1 text-md font-semibold">{t("settings.portal.only.services")}</p>
              <ChipMultiSelect
                label={t("settings.portal.only.services")}
                options={data.services.map((row) => ({ value: row.id, label: row.name }))}
                selected={draft.front_page_service_ids}
                onChange={(next) => field("front_page_service_ids", next)}
                disabled={readOnly}
                reason={readOnly ? t("settings.readOnlyReason") : null}
                addLabel={t("settings.portal.only.addService")}
                emptyLabel={t("settings.portal.only.noServices")}
                removeLabel={t("settings.portal.only.removeService")}
                testKey="services"
              />
              <p className="mt-1 text-md text-[color-mix(in_srgb,var(--color-text)_60%,transparent)]">{t("settings.portal.only.servicesHelp")}</p>
            </div>
            <div className="mt-4 grid grid-cols-2 gap-4">
              <label className="block">
                <span className="mb-1 block text-base font-semibold text-neutral-900">{t("settings.portal.only.hours")}</span>
                <textarea
                  className="input min-h-24 w-full resize-y"
                  value={draft.office_hours_text ?? ""}
                  readOnly={readOnly}
                  onChange={(e) => field("office_hours_text", e.target.value)}
                  data-field="office_hours_text"
                />
              </label>
              <label className="block">
                <span className="mb-1 block text-base font-semibold text-neutral-900">{t("settings.portal.only.emergency")}</span>
                <input
                  className="input w-full"
                  value={draft.emergency_phone ?? ""}
                  readOnly={readOnly}
                  onChange={(e) => field("emergency_phone", e.target.value)}
                  data-field="emergency_phone"
                />
              </label>
            </div>
          </Panel>
        </div>
        <div className="col-span-12 md:col-span-4">
          <Panel title={t("settings.portal.preview.title")}>
            <PagePreview brand={brandStyle(preview.tenant)}>
              <FrontPageView front={preview} />
            </PagePreview>
            <p className="mt-2 text-base text-neutral-600">{t("settings.portal.preview.caption")}</p>
          </Panel>
        </div>
      </div>
    </div>
  );
}

// ── The segment strip ────────────────────────────────────────────────────────

export function CustomerPortalTab(props: { readOnly: boolean; client?: ApiClient; segment?: string }) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const tenantPath = useTenantPath();
  const params = useParams();
  const client = props.client ?? api;
  const active = portalSegmentFromParam(props.segment ?? params.segment);
  const [openAnswer, setOpenAnswer] = useState<string | null>(null);
  const base = `/settings/${CONFIGURE_TAB}/${CUSTOMER_PORTAL_SUB_TAB}`;
  return (
    <div className="settings-subtabs">
      <div className="settings-tabs" role="tablist" aria-label={t("settings.configure.subTab.customerPortal")}>
        {PORTAL_SEGMENTS.map((seg) => (
          <button
            key={seg.id}
            type="button"
            role="tab"
            aria-selected={seg.id === active}
            className={seg.id === active ? "active" : undefined}
            onClick={() => {
              setOpenAnswer(null);
              navigate(tenantPath(seg.id === "overview" ? base : `${base}/${seg.id}`));
            }}
          >
            {t(seg.labelKey)}
          </button>
        ))}
      </div>
      {active === "branding" ? (
        <Branding readOnly={props.readOnly} client={client} />
      ) : active === "help" ? (
        // CWP-071 → CWP-072. The editor replaces the list in the same
        // segment: one screen id per view, one back link (BR-SHL-035).
        openAnswer === null ? (
          <PortalHelpList readOnly={props.readOnly} client={client} onOpen={setOpenAnswer} />
        ) : (
          <PortalHelpEditor
            slug={openAnswer}
            readOnly={props.readOnly}
            client={client}
            onBack={() => setOpenAnswer(null)}
          />
        )
      ) : active === "tips" ? (
        <PortalTipsList readOnly={props.readOnly} client={client} />
      ) : (
        <Overview readOnly={props.readOnly} client={client} />
      )}
    </div>
  );
}
