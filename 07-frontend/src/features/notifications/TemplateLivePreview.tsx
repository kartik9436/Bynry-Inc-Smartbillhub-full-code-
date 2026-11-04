// ── Trace ──────────────────────────────────────────────
// Story:    CR-199-BRC10 F7 — the live Preview beside the wording (`02`, `04`,
//           `05`, `14`, `17`)
// Rules:    BR-NOT-005 (nothing here sends) · CR-076 item 1 (one wording, its
//           surfaces) · OQ-252 (Set as default, disabled with its reason) · E4
//           (locked blocks in the preview too) · B14 rules 33 · 43 · 44
// ───────────────────────────────────────────────────────
// THE RIGHT HALF OF THE WORKSPACE: what the customer gets.
//
//   Preview                         [Pat Rivera | Lin Chen] [Expand]
//   ┌─────────────────────────────────────────────┐
//   │  an email in its branded shell · a text on a │
//   │  phone · a printed letter · an in-app banner │
//   └─────────────────────────────────────────────┘
//
// ⚠ **EVERY WORD INSIDE THE FRAME IS THE SERVER'S RENDER.** The body is
// `POST …/preview`'s answer — the same renderer that sends — and this file
// never turns clerk-typed markup into HTML. What it adds is the FRAME a
// customer sees it in (the phone, the paper, the inbox).
//
// ⚠ **WHAT THE OLD PREVIEW PANE DID IS ALL HERE (`CR-199-BRC10` §6 W7–W10,
// W20, W23):** the preview-as tabs for a wording with two surfaces, Print, the
// Default pill or the disabled *Set as default* with its reason, the disabled
// *Download sample PDF* with its reason, the *nothing here is sent* caption
// with the server's sentence on hover, the unfilled and unsampled placeholders,
// the locked rights blocks, and — for a contract nobody has published — the
// platform's offered wording with *Create from our default*.
import { useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import { useId } from "react";
import { useTranslation } from "react-i18next";

import type { ApiClient } from "@/api/client";
import { previewTemplateBody } from "@/api/endpoints";
import type {
  TemplateBodyFormat,
  TemplateBranding,
  TemplateDetail,
  TemplatePreview,
} from "@/api/endpoints";
import { Link, useParams } from "react-router-dom";
import { Button } from "@/components/Button";
import { ModalShell } from "@/components/FormModal";
import { RefusalStrip } from "@/components/Surfaces";
import { useToast } from "@/components/Toast";
import { apiErrorText } from "@/features/tenancy/settingsShared";
import { openPrintWindow, printRenderedDocument } from "./printPreview";
import { TemplateSurface } from "./templateSurfaces";
import type { DesignerKind } from "./TemplateDetail";
import { ControlNote, SurfaceTabs, groupByReason } from "./TemplateDetail";
import { LockedPhrases } from "./TemplateWordingPane";

/**
 * The server's render of the words in the box, re-asked 400ms after the last
 * keystroke (`CR-199-BRC10` §6 W24). Starts from the payload's own preview, so
 * a template that is only being READ costs no request at all.
 *
 * It refuses exactly what the save refuses — both run `validate_body` — so a
 * preview that renders is a body that saves.
 */
export function useLivePreview(opts: {
  code: string;
  client: ApiClient;
  body: string;
  subject: string;
  version: number;
  /** `rich` or `plain` where the class offers rich (`CR-199-BRC10` §5b). */
  bodyFormat?: TemplateBodyFormat;
  initial: TemplatePreview | null;
  initialError: string | null;
  /** Only re-render once the person has changed something; reading a
   *  template shows the payload's preview and asks nothing. */
  dirty: boolean;
}): { preview: TemplatePreview | null; error: string | null } {
  const { t } = useTranslation();
  const [preview, setPreview] = useState<TemplatePreview | null>(opts.initial);
  const [error, setError] = useState<string | null>(opts.initialError);
  const { code, client, body, subject, version, dirty, bodyFormat } = opts;
  useEffect(() => {
    if (!dirty || body === "") return;
    let live = true;
    const timer = setTimeout(() => {
      previewTemplateBody(
        code,
        { body, subject: subject || null, version, body_format: bodyFormat },
        client,
      )
        .then((next) => {
          if (!live) return;
          setPreview(next);
          setError(null);
        })
        .catch((failure: unknown) => {
          if (!live) return;
          setPreview(null);
          setError(apiErrorText(failure, t));
        });
    }, 400);
    return () => {
      live = false;
      clearTimeout(timer);
    };
  }, [code, client, body, subject, version, dirty, bodyFormat, t]);
  return { preview, error };
}

/** The black phone a text message is read on (`05`). The bubble and its count
 *  are `SmsSurface`'s; this is only the device around them. */
function PhoneFrame(props: { children: ReactNode; sender: string | null }) {
  return (
    <div
      className="mx-auto flex w-full max-w-[18rem] flex-col border-8 border-neutral-900 bg-surface p-3"
      data-testid="preview-phone"
    >
      {props.sender !== null && (
        <p className="m-0 mb-2 text-center text-xs text-[color-mix(in_srgb,var(--color-text)_65%,transparent)]">
          {props.sender}
        </p>
      )}
      <div className="min-h-80">{props.children}</div>
    </div>
  );
}

/** `02`'s line over the email: the brand colour as a swatch, where the logo
 *  links, and the door to where both are set (PO ruling 1A: *Settings ›
 *  Company › Branding*). Drawn only when the server served a brand. The
 *  swatch is the UTILITY's colour, so it is the one inline style on this
 *  screen — a tenant's hex is data, not a design token. */
function BrandingLine(props: { branding: TemplateBranding | null }) {
  const { t } = useTranslation();
  const { tenant } = useParams();
  const brand = props.branding;
  if (brand === null) {
    return null;
  }
  return (
    <p
      className="m-0 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm"
      data-testid="preview-branding"
    >
      {brand.brand_primary_hex !== null && (
        <span className="inline-flex items-center gap-1">
          <span
            aria-hidden="true"
            className="inline-block h-3 w-3 border border-divider"
            style={{ backgroundColor: brand.brand_primary_hex }}
          />
          {t("templates.workspace.brandColour")}
        </span>
      )}
      <span data-testid="preview-logo-link">
        {brand.logo_link_url !== null && brand.logo_link_url !== ""
          ? t("templates.workspace.logoLinksTo", { address: brand.logo_link_url })
          : t("templates.workspace.logoLinksNowhere")}
      </span>
      {tenant !== undefined && (
        <Link to={`/${tenant}/settings/company/profile`} data-testid="preview-branding-settings">
          {t("templates.workspace.editBranding")}
        </Link>
      )}
    </p>
  );
}

/** The paper, the inbox or the phone, on the grey well the drawing puts it in. */
export function PreviewStage(props: {
  kind: DesignerKind;
  data: TemplateDetail;
  preview: TemplatePreview;
}) {
  const sender =
    props.data.merge_field_rows.find((row) => row.token === "utility_name")?.sample_value ?? null;
  const surface = <TemplateSurface preview={props.preview} kind={props.kind} data={props.data} />;
  const html = props.preview.html ?? null;
  return (
    <div className="bg-bg p-4" data-testid="preview-stage" data-preview-kind-stage={props.kind}>
      {props.kind === "sms" ? (
        <PhoneFrame sender={sender}>{surface}</PhoneFrame>
      ) : props.kind === "email" && html !== null && html !== "" ? (
        /* CR-199-BRC10 §5b — the WHOLE branded email (band, logo, the button,
           the footer) is the server's render. It is drawn in a SANDBOXED frame
           with no permission at all — no script, no same-origin, no form, no
           navigation — and never into this document: the wording is clerk-
           typed, and a screen that turned it into HTML here would be the
           injection the closed markup exists to prevent. The frame needs a
           height because a sandboxed document cannot be measured from outside;
           *Expand* gives it the whole dialog. */
        /* ⚠ DEF-NOT-10688 — A LINK IN THE PREVIEW OPENS A NEW TAB. An empty
           sandbox still lets the frame navigate ITSELF, so clicking the logo
           or Pay now replaced the preview with the linked site. Every link
           now targets a new tab (`linksOpenOutside`), and the sandbox gains
           exactly the two tokens that allow that — still no script, no
           same-origin, no form, no top navigation. */
        <iframe
          sandbox="allow-popups allow-popups-to-escape-sandbox"
          srcDoc={linksOpenOutside(html)}
          title={props.preview.subject ?? props.data.name}
          className="mx-auto block h-[40rem] w-full max-w-[40rem] border border-divider bg-surface"
          data-testid="preview-email-frame"
        />
      ) : (
        <div className="mx-auto max-w-[40rem] border border-divider bg-surface p-4 shadow-sm">
          {surface}
        </div>
      )}
    </div>
  );
}

/** The server's email document with every link sent to a new tab: a
 *  `<base target="_blank">` as the first thing in its head (DEF-NOT-10688). */
export function linksOpenOutside(html: string): string {
  const base = '<base target="_blank">';
  return /<head[^>]*>/i.test(html)
    ? html.replace(/<head[^>]*>/i, (head) => `${head}${base}`)
    : `${base}${html}`;
}

export function TemplateLivePreview(props: {
  data: TemplateDetail;
  /** The composer's shape — the preview starts as it. */
  kind: DesignerKind;
  /** The surfaces one wording previews as (`["printable", "email"]` for a
   *  notice that is posted and emailed); fewer than two draws no tabs. */
  surfaces: readonly DesignerKind[];
  preview: TemplatePreview | null;
  error: string | null;
  selectedVariantId: string | null;
  /** The contract offer, drawn where the document would be. */
  offer: ReactNode;
}) {
  const { t } = useTranslation();
  const fireToast = useToast();
  const ids = useId();
  const [chosen, setChosen] = useState<DesignerKind | null>(null);
  const [expanded, setExpanded] = useState(false);
  const printableRef = useRef<HTMLDivElement | null>(null);
  const kind = chosen !== null && props.surfaces.includes(chosen) ? chosen : props.kind;
  const nothing = props.preview === null || props.error !== null;
  const selected =
    props.data.variants.find((variant) => variant.id === props.selectedVariantId) ?? null;

  function print() {
    const node = printableRef.current;
    if (node === null) return;
    const opened = printRenderedDocument({
      node,
      title: `${props.data.name} — ${t(`templates.detail.previewSurface.${kind}`)}`,
      styleSource: document,
      target: openPrintWindow(),
    });
    if (!opened) {
      fireToast(t("templates.detail.printBlocked"));
    }
  }

  const document_ =
    props.error !== null ? (
      <RefusalStrip as="div" role="note" data-testid="preview-refused">
        {props.error}
      </RefusalStrip>
    ) : props.preview === null ? (
      props.data.platform_default !== null ? null : (
        <p className="m-0 text-sm" data-testid="preview-pending">
          {t("templates.detail.previewPending")}
        </p>
      )
    ) : (
      <div ref={printableRef} data-testid="preview-printable">
        <PreviewStage kind={kind} data={props.data} preview={props.preview} />
        <LockedPhrases phrases={props.data.mandatory_content} idPrefix="preview-locked" />
        <p
          className="m-0 mt-2 max-w-measure text-sm"
          data-desc
          data-testid="preview-notice"
          title={`${props.preview.sample_data_notice} ${props.preview.sample_data_detail}`}
        >
          {t("templates.detail.previewOnly")}
        </p>
        {props.preview.absences.length > 0 && (
          <details data-testid="preview-absences">
            <summary>
              {t("templates.detail.absences", { count: props.preview.absences.length })}
            </summary>
            <ul>
              {props.preview.absences.map((absence) => (
                <li key={absence.token} data-br-ref={absence.br_ref}>
                  {absence.detail}
                </li>
              ))}
            </ul>
          </details>
        )}
        {props.preview.unsampled.length > 0 && (
          <details data-testid="preview-unsampled">
            <summary>{t("templates.detail.unsampled")}</summary>
            <ul>
              {groupByReason(props.preview.unsampled).map((group) => (
                <li key={group.reason}>
                  {group.tokens.map((token, i) => (
                    <span key={token}>
                      {i > 0 ? " " : null}
                      <code>{`{${token}}`}</code>
                    </span>
                  ))}
                  {" — "}
                  {group.reason}
                </li>
              ))}
            </ul>
          </details>
        )}
      </div>
    );

  return (
    <section
      className="flex min-w-0 flex-col gap-3 border border-divider bg-surface p-4"
      aria-labelledby={`${ids}-title`}
      data-testid="preview-pane"
    >
      {/* THE STRIP: the panel head (title, whose sample data, Expand) and the
          one thin line under it (the surface tabs, the default marker, Print).
          One element, so the tabs are IN the strip above the paper. */}
      <div className="flex flex-col gap-3" data-testid="preview-strip">
        <div
          className="flex flex-wrap items-center justify-between gap-2"
          data-testid="preview-head"
        >
          <h3 id={`${ids}-title`} className="m-0 font-heading text-lead font-semibold">
            {t("templates.workspace.preview")}
          </h3>
          <div className="flex flex-wrap items-center gap-2">
            <span data-testid="preview-sample-identity" className="text-sm">
              {t("templates.detail.sampleDataIs", {
                customer: props.data.sample_identity.customer_name ?? "—",
                account: props.data.sample_identity.account_no ?? "—",
              })}
            </span>
            <Button
              variant="secondary"
              size="sm"
              disabled={nothing}
              onClick={() => setExpanded(true)}
              data-testid="preview-expand"
            >
              {t("templates.workspace.expand")}
            </Button>
          </div>
        </div>

        <BrandingLine branding={props.preview?.branding ?? null} />

        {/* The surface tabs, Print and the default marker — one thin line. */}
        <div className="flex flex-wrap items-center gap-2 print:hidden">
          {props.surfaces.length > 1 ? (
            <SurfaceTabs surfaces={props.surfaces} current={kind} onSelect={setChosen} />
          ) : (
            <strong className="text-sm" data-testid="preview-kind">
              {props.data.kind}
            </strong>
          )}
          <span className="ml-auto flex flex-wrap items-center gap-2">
            {selected?.is_default === true ? (
              <span
                className="border border-divider px-2 py-px text-xs tracking-wide"
                data-badge
                data-testid="preview-default-pill"
              >
                {t("templates.detail.defaultVariantPill")}
              </span>
            ) : (
              selected !== null && (
                <>
                  <Button
                    variant="link"
                    disabled
                    title={props.data.set_default_reason}
                    data-br-ref={props.data.set_default_br_ref}
                    data-testid="set-default"
                  >
                    {t("templates.detail.setDefault")}
                  </Button>
                  <ControlNote
                    label={props.data.set_default_label}
                    reason={props.data.set_default_reason}
                    testId="set-default-reason"
                    brRef={props.data.set_default_br_ref}
                  />
                </>
              )
            )}
            <Button
              variant="secondary"
              size="sm"
              disabled={nothing}
              title={
                nothing
                  ? t("templates.detail.printNothingYet")
                  : t("templates.detail.printPreviewHint")
              }
              onClick={print}
              data-testid="print-preview"
            >
              {t("templates.detail.printPreview")}
            </Button>
            <Button
              variant="secondary"
              size="sm"
              disabled
              title={props.data.download_pdf_reason}
              data-testid="download-pdf"
            >
              {t("templates.detail.downloadPdf")}
            </Button>
            <ControlNote
              label={props.data.download_pdf_label}
              reason={props.data.download_pdf_reason}
              testId="download-pdf-reason"
            />
          </span>
        </div>
      </div>

      <div data-testid="preview-scroll">{document_}</div>
      {props.offer}

      {expanded && props.preview !== null && (
        <ModalShell title={props.data.name} onClose={() => setExpanded(false)} size="wide">
          <div className="modal-body" data-testid="preview-expanded">
            <PreviewStage kind={kind} data={props.data} preview={props.preview} />
          </div>
          <div className="modal-foot">
            <Button
              variant="secondary"
              onClick={() => setExpanded(false)}
              data-testid="preview-expanded-close"
            >
              {t("templates.workspace.close")}
            </Button>
          </div>
        </ModalShell>
      )}
    </section>
  );
}
