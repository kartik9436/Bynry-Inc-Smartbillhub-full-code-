// ── Trace ──────────────────────────────────────────────
// Story:    US-BIL-022 (the pinned document — a reprint renders the version the
//           bill was sent on, forever) · US-BIL-026 (S30 bill detail's
//           `document_url`, which pointed at nothing until the route landed) ·
//           US-BIL-028 (the custom-field snapshot — stamped at draft since
//           2026-08-11 and, until this band, printed nowhere: the Remarks &
//           notes section the PO ruled on 2026-08-12 closing OQ-125/OQ-118,
//           *"in remark or note section on bill"*)
//           Screens: S30 (bill detail → View the bill as sent)
// Rules:    BR-BIL-026 (the pinned template version, rendered by the SERVER) ·
//           BR-BIL-030 (the snapshot is stamped with the document instance and
//           read back from it — never joined live to master data) ·
//           BR-TEN-048 (a custom field can never influence money — this screen
//           prints strings and computes with none) ·
//           BR-BIL-030 (the bill is LOCKED at issue — this page shows the
//           frozen instance, never a live join) · BR-CUS-040 (a reprint
//           re-renders, never recomputes) · BR-BIL-036 (print is the floor, so
//           the printable page is one click away) · BR-SHL-020 (plain language
//           when something is absent) · BR-SHL-044 (one page header)
// ───────────────────────────────────────────────────────
// The bill a person can actually open.
//
// ══════════════════════════════════════════════════════════════════════════
// ⚠ THIS PAGE USED TO REBUILD THE BILL ON EVERY OPEN (DEF-2553, CR-049 task 4)
// ══════════════════════════════════════════════════════════════════════════
// Its title says *the bill as it was sent* and, until 2026-08-30, it asked the
// server to assemble a fresh document from the frozen payload every time it was
// opened. Every FIGURE was right — `BR-BIL-030` freezes the data — and the
// DOCUMENT could still be a different document. The bill's data is locked and so
// is the tenant's chosen template row (a database trigger refuses an edit to a
// published version). **What is locked by nothing is the CODE that draws the
// page, and the platform's library of layouts**: a deploy moves the first, a
// rollback moves the second, and an already-sent bill then re-opens on a
// different page — proved, with a whole section missing. Neither writes anything
// on the invoice, which is why hard rule 4 never noticed.
//
// The Product Owner's sentence, and the reason this changed:
//
//     *"otherwie everytime we reproduce it using data in table, we might change
//     something about it and that is not correct"*
//
// So the page now draws ONE of two states and never blurs them, exactly as the
// notifications reprint panel does for a letter:
//
//   · **THE ORIGINAL** — the HTML kept when the bill was issued, byte for byte,
//     hash-checked on this read, in a sandboxed frame. The printable page beside
//     it is the kept page too.
//   · **NOT THE ORIGINAL** — no copy was kept, which is every bill issued before
//     `v2.88.0`. The page says so in a warning tier, and the bands below are
//     labelled as a rebuild rather than presented as the bill.
//
// **THE SERVER DECIDES WHICH AND WRITES THE SENTENCE.** This file branches on
// `provenance` and prints `message_key`; it never composes its own account of
// provenance, because two descriptions of one state is how they drift apart.
//
// `documents.py` has rendered every bill twice — as a structure with an HTML
// serialisation and as a printable US Letter page — since the day it landed,
// and `issue.py` threw the result away on every bill it issued. Its own
// `DOCUMENT_UNAVAILABLE` carried the sentence: *"`GET /invoices/{id}/document`
// is still unmounted, so no human can open one either (hard-won law 2)."*
//
// ══════════════════════════════════════════════════════════════════════════
// WHAT THIS PAGE DRAWS, AND WHAT IT REFUSES TO
// ══════════════════════════════════════════════════════════════════════════
//   · **It draws the STRUCTURE, not the server's HTML string.** The response
//     carries `body` and this screen does not inject it: rendering a server
//     HTML blob into the app would be `dangerouslySetInnerHTML` over a document
//     that contains customer-supplied text. The structure has the same fields
//     in the same A19 order and is escaped by React on the way out.
//   · **Every absence is badged ON ITS OWN FIELD.** The server attaches the
//     reason to the field it belongs to, so the screen never prints a bare
//     em-dash and leaves a clerk to guess which of twelve fields is missing.
//   · **The three kinds of gap stay apart.** What this bill's snapshot lacks
//     (`absent`), what the page could not spell (`pdf_unrepresentable`) and what
//     the build cannot do at all (`unavailable`) are three lists with three
//     different fixes. Merging them would tell a clerk a missing total due and
//     an un-embeddable font are the same problem.
//   · **The printable page is a LINK, never a fetch-and-blob.** The PDF route
//     answers `application/pdf` inline; a browser opens it in its own viewer
//     with its own print and save. Downloading bytes into memory to re-offer
//     them would add a second copy of the document with no gain.
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { useNavigate, useParams } from "react-router-dom";

import { apiHref } from "@/api/apiHref";
import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { getBillDocument } from "@/api/billingOpsEndpoints";
import type {
  BillDocumentLayout,
  DocumentField as BillDocumentField,
  FrozenBillDocument,
  RenderedBillDocument,
} from "@/api/billingOpsEndpoints";
import { ButtonAnchor } from "@/components/Button";
import { PageHeader } from "@/components/PageHeader";
import { Panel } from "@/components/Panel";
import { PlainTable } from "@/components/Surfaces";
import { LoadingSkeleton, PermissionDenied } from "@/components/StateFrame";
import { isDenied, useAccessCell } from "@/features/metering/meteringShared";
import { apiErrorText, isPermissionDenied } from "@/features/tenancy/settingsShared";
import type { Translator } from "@/features/tenancy/settingsShared";
import { useTenantPath } from "@/routing/tenantPath";

import { BILLING_PERMISSION, DASHBOARD_ROUTE, billDetailPath } from "./billingShared";
import { BillCopyPanel, BillUsagePanel, GapNotes } from "./billingOpsShared";

export const billDocumentKey = (invoiceId: string) => ["billing", "document", invoiceId] as const;

/**
 * The platform default layout's switches — `standard-letter-v1`, and it is
 * NAMED rather than "all true" (`DEF-2826`).
 *
 * It stands in when a response carries no `layout` at all. That is not a
 * hypothetical: a server deployed before the field existed answers without it,
 * and every fixture written before this change does too. The default layout is
 * what every pre-library bill genuinely renders on (`documents.LAYOUTS` is
 * byte-identical to it), so drawing it is honest, and it happens to be the
 * only safe fallback: each switch means *draw this*, so any "empty" default
 * would blank four bands and present the result as the customer's page.
 */
export const DEFAULT_BILL_LAYOUT: BillDocumentLayout = {
  key: "standard-letter-v1",
  masthead: true,
  services_band: true,
  detail_columns: true,
  summary_first: false,
  stub: true,
  reserve_rows: 0,
};

/**
 * The layout, in words a clerk reads — B14 rule 31 and rule 32 clause 4.
 *
 * ⚠ **THE KEY IS NOT THE NAME.** This sentence printed
 * `platform-layout-compact-letter-v1` on screen, which is an internal
 * identifier at a billing clerk. The key is not deleted: it rides on
 * `data-layout-key` and the full source on `data-layout-source`, which is the
 * escape rule 31 names in its own text.
 *
 * A key the catalogue has never heard of falls back to the generic word rather
 * than printing itself — the same posture as `billing.run.reason.unmapped`. A
 * layout published by a build this client does not know about is exactly when
 * a raw key would leak, and it is exactly when nobody is watching.
 */
export function layoutName(key: string, t: Translator): string {
  return t(`billing.document.layout.${key}`, {
    defaultValue: t("billing.document.layout.unnamed"),
  });
}

/**
 * One A19 band. A field the snapshot did not carry SAYS SO, in words.
 *
 * ══════════════════════════════════════════════════════════════════════════
 * `DEF-2715` — B14 RULE 32 CLAUSE 4. WHAT WAS THERE, AND WHY IT LOOKED FINE
 * ══════════════════════════════════════════════════════════════════════════
 * `{field.absent.why}`, verbatim, under every absent field. `why` is
 * `documents.AbsentField.detail` and it is written for an engineer reading
 * `documents.py` — because that is who has always read it. A clerk opening a
 * live bill got, under **Utility**:
 *
 *     "A19 §1.1 mastheads the bill with the utility's name; the snapshot stamps
 *      no tenant identity, so the document cannot say who sent it. BR-BIL-030
 *      lists 'tenant identity and branding reference' as stamped."
 *
 * and under **Bill date**, a sentence naming `cycles.bill_date` in backticks.
 * A19 section numbers, a rule id, a database column and a module's internal
 * vocabulary, on the screen a utility opens to see what its customer received.
 *
 * **NOTHING COULD CATCH IT.** `G33` counts refusal keys; `G28` part 1 scans the
 * eleven catalogues and this string is in none of them, because it never
 * enters `en.json` at all. It is a server string rendered straight through.
 *
 * ══════════════════════════════════════════════════════════════════════════
 * WHY THE SENTENCE IS NOT SHORTENED IN `documents.py`
 * ══════════════════════════════════════════════════════════════════════════
 * The same seam decision `CaseFinding` records for `DEF-2883`, one screen
 * over, and the second reason is again the decisive one:
 *   · `detail` has OTHER readers — a lane report, a pre-issue check, an
 *     engineer diagnosing why a bill prints an em-dash — and for every one of
 *     them the A19 reference and the rule id are the useful part;
 *   · it is English hard-coded in Python and this product ships **eleven**
 *     catalogues (`BR-SHL-041`). Prose composed server-side is untranslatable
 *     BY CONSTRUCTION, and no parity gate can see the ten that show nothing.
 * So `detail` is neither deleted nor shortened. It rides on `data-absent-why`
 * and the rule id on `data-br-ref`, exactly as `BillCopyPanel` and `GapNotes`
 * already carry theirs.
 *
 * **DELIBERATELY NOT ON `title`.** B14 rule 31 permits an internal value there
 * and `DEF-2883` declined the permission for the same reason this does: a
 * tooltip is clerk-facing, and `BR-BIL-030` in a tooltip is still `BR-BIL-030`
 * on the screen.
 *
 * **WHAT THE CLERK GETS INSTEAD** is four words — the field already carries its
 * own LABEL and its own em-dash, so the only fact missing was whether the dash
 * means *nothing to show* or *we failed to load it*. One catalogue sentence
 * answers that, and rule 32 clause 1 is why it is not one paragraph per field.
 */
export function DocumentBand(props: {
  heading: string;
  fields: readonly BillDocumentField[];
  t: Translator;
}) {
  const { t } = props;
  if (props.fields.length === 0) {
    return null;
  }
  return (
    <section className="border-t-2 border-t-divider bg-surface px-4 py-3 [&_h3]:m-0 [&_h3]:mb-3 [&_h3]:text-h5 [&_dl]:m-0 [&_dl]:grid [&_dl]:grid-cols-[repeat(auto-fit,minmax(220px,1fr))] [&_dl]:gap-3 [&_dt]:text-xs [&_dt]:tracking-tag [&_dt]:uppercase [&_dt]:text-[color-mix(in_srgb,var(--color-text)_60%,transparent)] [&_dd]:m-0 [&_dd]:mt-1">
      <h3>{props.heading}</h3>
      <dl>
        {props.fields.map((field) => (
          <div
            key={field.label}
            className={
              field.absent !== null
                ? "[&_dd]:text-[color-mix(in_srgb,var(--color-text)_55%,transparent)]"
                : undefined
            }
          >
            <dt>{field.label}</dt>
            <dd>
              {field.value}
              {field.absent !== null && (
                // The absence travels WITH the field, so nobody has to match an
                // em-dash to an entry in a list at the bottom of the page. The
                // SENTENCE comes from the catalogue; the server's own words and
                // its rule id ride on the element for support (DEF-2715).
                <span
                  className="block text-xs text-[color-mix(in_srgb,var(--color-text)_60%,transparent)]"
                  data-bil="field-absent"
                  data-br-ref={field.absent.br_ref}
                  data-absent-field={field.absent.field}
                  data-absent-why={field.absent.why}
                >
                  {t("billing.document.fieldAbsent")}
                </span>
              )}
            </dd>
          </div>
        ))}
      </dl>
    </section>
  );
}

/** Bytes as a short human figure. A bill is kilobytes; one decimal is plenty. */
export function byteLabel(bytes: number): string {
  if (bytes < 1024) {
    return `${String(bytes)} B`;
  }
  return `${(bytes / 1024).toFixed(1)} KB`;
}

/**
 * THE ORIGINAL — the bill exactly as it was issued.
 *
 * ⚠ **WHY A SANDBOXED FRAME AND NOT `dangerouslySetInnerHTML`.** This file has
 * always refused to inject the server's HTML into the app, and that refusal is
 * still right: the document contains customer-supplied text, and injecting it
 * would put it inside this page's own origin, scripts and all. A frame with
 * `sandbox=""` — no `allow-scripts`, no `allow-same-origin`, no forms — is a
 * different trade: the bytes are rendered as their own inert document, with no
 * access to this page, no script execution and no network of its own.
 *
 * **And it is the only honest way to show the original at all.** Re-deriving the
 * bands from the structure and calling THAT the original would be the defect
 * wearing a better label: the whole point is that the bytes we kept are what a
 * person sees. The structure is drawn below, as a rebuild, and says so.
 */
function TheOriginalBill(props: {
  html: string;
  document: FrozenBillDocument;
  t: Translator;
}) {
  const { html, document: kept, t } = props;
  return (
    <section className="flex flex-col gap-3">
      <p className="m-0 rounded-md border border-success-500 bg-success-100 px-3 py-2 text-sm text-text">
        {/* THE SERVER'S OWN SENTENCE for this state, from the key the backend
            named (`frozen_bill.I18N_ORIGINAL`). Nothing here composes a second
            "when was it sealed" sentence beside it. */}
        <strong>
          {t("billing.document.original", {
            sealedOn: new Date(kept.stored_at).toLocaleString(),
          })}
        </strong>
      </p>
      <iframe
        title={t("billing.document.originalFrameTitle")}
        srcDoc={html}
        sandbox=""
        className="h-[720px] w-full rounded-md border border-divider bg-surface"
      />
      <dl className="m-0 grid grid-cols-[repeat(auto-fit,minmax(180px,1fr))] gap-3 text-xs">
        <div>
          <dt className="uppercase tracking-tag text-[color-mix(in_srgb,var(--color-text)_60%,transparent)]">
            {t("billing.document.fileName")}
          </dt>
          <dd className="m-0 mt-1 break-words">{kept.display_name}</dd>
        </div>
        <div>
          <dt className="uppercase tracking-tag text-[color-mix(in_srgb,var(--color-text)_60%,transparent)]">
            {t("billing.document.size")}
          </dt>
          <dd className="m-0 mt-1">{byteLabel(kept.byte_length)}</dd>
        </div>
        <div>
          {/* The checksum is shown because it is the thing that PROVES this copy
              is unchanged: an auditor holding their own copy can compare it
              without asking us. It was re-computed and matched on THIS read — a
              mismatch never reaches this component, it is a refusal. */}
          <dt className="uppercase tracking-tag text-[color-mix(in_srgb,var(--color-text)_60%,transparent)]">
            {t("billing.document.checksum")}
          </dt>
          <dd className="m-0 mt-1 break-all font-mono">{kept.content_hash}</dd>
        </div>
      </dl>
    </section>
  );
}

/**
 * NOT THE ORIGINAL — said plainly, in a warning tier, above the rebuild.
 *
 * ⚠ **THE NOTIFICATIONS PANEL DRAWS NOTHING IN THIS STATE AND THIS PAGE DRAWS
 * THE BANDS. The difference is deliberate and is worth reading before "fixing"
 * it.** There, the panel exists only to answer *"what did we send"*, so a
 * reconstruction under a caption would be the whole content of the screen and a
 * caption is what nobody reads. Here the bands are S30's long-standing view of a
 * bill's own frozen data — a clerk answering a phone call needs the figures, and
 * every figure is the frozen one (`BR-BIL-030`). What must never happen is the
 * rebuild being presented AS the bill, so it is headed as a rebuild and this
 * warning sits above it.
 */
function NotTheOriginal(props: { document: RenderedBillDocument; t: Translator }) {
  const { document: answer, t } = props;
  return (
    <div
      role="alert"
      className="flex flex-col gap-2 rounded-md border border-warning-500 bg-warning-100 px-3 py-2"
    >
      <p className="m-0 text-sm text-text">
        <strong>{t(answer.message_key)}</strong>
      </p>
      {/* The server's own sentence, in its own words — it knows which reason
          applies and this screen does not re-say it differently. */}
      <p className="m-0 text-xs text-[color-mix(in_srgb,var(--color-text)_75%,transparent)]">
        {answer.provenance_detail}
      </p>
    </div>
  );
}

export interface BillDocumentPageProps {
  client?: ApiClient; // test seam — screens never build their own transport
}

export function BillDocumentPage(props: BillDocumentPageProps) {
  const { t } = useTranslation();
  const translate: Translator = (key, params) => t(key, params);
  const client = props.client ?? api;
  const navigate = useNavigate();
  const tenantPath = useTenantPath();
  const routeParams = useParams();
  // THE ROUTE PARAM AND NOTHING ELSE. An `invoiceId` PROP was written here
  // first and removed: nothing passed it, which makes it dead UI (hard-won law
  // 2) and is precisely what G13 flagged. A test drives this screen through a
  // memory router, the same way a browser drives it.
  const invoiceId = routeParams.invoiceId ?? "";
  const cell = useAccessCell(BILLING_PERMISSION, client);

  const documentQuery = useQuery({
    queryKey: billDocumentKey(invoiceId),
    queryFn: () => getBillDocument(invoiceId, client),
    enabled: invoiceId !== "",
    retry: false,
  });

  if (isDenied(cell)) {
    return (
      <PermissionDenied
        helper={t("billing.denied")}
        onBack={() => navigate(tenantPath(DASHBOARD_ROUTE))}
      />
    );
  }
  if (documentQuery.isError && isPermissionDenied(documentQuery.error)) {
    return (
      <PermissionDenied
        helper={t("billing.denied")}
        onBack={() => navigate(tenantPath(DASHBOARD_ROUTE))}
      />
    );
  }

  const document = documentQuery.data;
  // DEF-2826 — the switches the two server serialisations were built from, or
  // the platform default when the answer carries none (a server older than this
  // field, or a hand-built fixture).
  //
  // ⚠ **NEVER `{}` AND NEVER OPTIONAL CHAINING PER SWITCH.** Every member reads
  // *"draw this band"*, so an absent object treated as empty would suppress the
  // masthead, the services band, the detail columns and the stub in one go and
  // present the result as the customer's bill. The fallback is the layout every
  // pre-library bill actually renders on, which makes it the honest stand-in as
  // well as the safe one.
  const layout = document?.layout ?? DEFAULT_BILL_LAYOUT;
  return (
    <div className="px-4 pt-6 pb-8">
      <PageHeader
        title={t("billing.document.title")}
        backTo={{
          to: tenantPath(billDetailPath(invoiceId)),
          label: t("billing.document.backToBill"),
        }}
        rollup={
          document === undefined ? null : (
            <span>
              {t("billing.document.rollup", {
                billNo: document.invoice_no ?? t("billing.bills.noNumber"),
                version: document.template_version,
                pages: document.pdf_page_count,
              })}
            </span>
          )
        }
        secondaryActions={
          document === undefined ? undefined : (
            // BR-BIL-036's floor, one click away. A LINK, so the browser's own
            // viewer handles print and save; the route answers inline PDF.
            // ⚠ THE LABEL CHANGES WITH THE STATE, and that is the only place a
            // person is told which page they are about to open. A PDF response
            // cannot carry a caption — `X-Document-Provenance` says it to a
            // machine — so the BUTTON has to say it to a human: the kept page
            // for a frozen bill, a rebuild for one issued before `v2.88.0`.
            <ButtonAnchor
              variant="secondary"
              href={apiHref(tenantPath(document.pdf_url))}
              target="_blank"
              rel="noreferrer"
            >
              {document.provenance === "original"
                ? t("billing.document.openOriginalPdf")
                : t("billing.document.openPdf")}
            </ButtonAnchor>
          )
        }
      />

      {documentQuery.isError ? (
        <Panel role="alert">
          <h3>{t("billing.document.errorTitle")}</h3>
          {/* A DRAFT lands here, and the server's sentence says exactly why:
              no template version has been pinned to it yet. That is a state a
              clerk can act on, and it is not a 404. */}
          <p className="font-body text-base leading-normal font-normal tracking-normal text-[color-mix(in_srgb,var(--color-text)_62%,transparent)] [&[role=alert]]:text-accent-700">
            {apiErrorText(documentQuery.error, translate)}
          </p>
        </Panel>
      ) : document === undefined ? (
        <LoadingSkeleton variant="card" />
      ) : (
        <>
          {/* ⚠ IS THIS THE BILL, OR A REBUILD OF IT — FIRST, ABOVE EVERYTHING.
              The one question the page's own title makes a promise about, and
              the one it could not answer until CR-049 task 4. */}
          {document.provenance === "original" &&
          document.original_html !== null &&
          document.frozen_document !== null ? (
            <TheOriginalBill
              html={document.original_html}
              document={document.frozen_document}
              t={translate}
            />
          ) : (
            <NotTheOriginal document={document} t={translate} />
          )}

          {/* WHICH PAGE THIS IS, on every document — and, since `DEF-2826`, in
              words rather than in the key.
              ⚠ It describes the RE-RENDER below it, not the kept copy above —
              which is why it moved under the provenance block rather than
              staying at the top of the page.
              ⚠ **`platform-layout-compact-letter-v1` WAS THE VISIBLE VALUE OF
              THIS SENTENCE UNTIL 2026-08-31.** That is an internal key on a
              clerk's screen (B14 rule 31, and rule 32 clause 4). The layout is
              now named from the catalogue and the raw source rides on
              `data-layout-source`, which is the escape rule 31 itself names —
              support and the browser inspector still read it. A key the
              catalogue does not know falls back to the generic sentence rather
              than printing itself. */}
          <p
            className="font-body text-base leading-normal font-normal tracking-normal text-[color-mix(in_srgb,var(--color-text)_62%,transparent)] [&[role=alert]]:text-accent-700"
            role="note"
            data-layout-source={document.layout_source}
            data-layout-key={layout.key}
          >
            {t("billing.document.rebuiltBands")}{" "}
            {t("billing.document.layoutSource", { source: layoutName(layout.key, t) })}
          </p>

          <article className="flex max-w-[900px] flex-col gap-4">
            {/* ══════════════════════════════════════════════════════════════
                THE LAYOUT'S OWN SWITCHES, HONOURED — `DEF-2826`.
                ══════════════════════════════════════════════════════════════
                Every band below used to be drawn unconditionally, so this page
                announced a layout and then drew a different one. Measured in a
                browser on two bills issued minutes apart: the standard bill's
                frozen HTML contains *Rate* once and *Usage* twice; the compact
                one contains NEITHER — and this screen drew DESCRIPTION / USAGE
                / RATE / AMOUNT for both.

                ⚠ **THE SWITCHES ARE THE SERVER'S AND ARE NOT RE-DERIVED HERE.**
                A screen that decided for itself which bands `compact-letter-v1`
                suppresses would be a second copy of `documents.LayoutSpec`, and
                the two would disagree the first time a layout changed — on the
                one screen whose whole purpose is to show a clerk what the
                customer will receive. */}
            {layout.masthead && (
              <DocumentBand
                heading={t("billing.document.band.masthead")}
                fields={document.masthead}
                t={translate}
              />
            )}
            <DocumentBand
              heading={t("billing.document.band.meta")}
              fields={document.meta}
              t={translate}
            />
            {/* A19 §1.3 ABOVE the charges on `summary-first-letter-v1`: the
                figure most customers are looking for is the amount due. Drawn
                once either way — the band below is behind the mirrored test. */}
            {layout.summary_first && (
              <DocumentBand
                heading={t("billing.document.band.summary")}
                fields={document.summary}
                t={translate}
              />
            )}
            {layout.services_band && (
              <DocumentBand
                heading={t("billing.document.band.services")}
                fields={document.services}
                t={translate}
              />
            )}
            {document.groups.map((group) => (
              <section
                key={group.heading}
                className="border-t-2 border-t-divider bg-surface px-4 py-3 [&_h3]:m-0 [&_h3]:mb-3 [&_h3]:text-h5 [&_dl]:m-0 [&_dl]:grid [&_dl]:grid-cols-[repeat(auto-fit,minmax(220px,1fr))] [&_dl]:gap-3 [&_dt]:text-xs [&_dt]:tracking-tag [&_dt]:uppercase [&_dt]:text-[color-mix(in_srgb,var(--color-text)_60%,transparent)] [&_dd]:m-0 [&_dd]:mt-1"
              >
                <h3>{group.heading}</h3>
                <PlainTable>
                  <thead>
                    <tr>
                      <th scope="col">{t("billing.document.col.description")}</th>
                      {/* `detail_columns` — dropped by `compact-letter-v1`,
                          whose own comment says a line is description + amount,
                          which is what a customer on a flat plan needs and all
                          a two-line trash bill can honestly fill. */}
                      {layout.detail_columns && (
                        <>
                          <th scope="col" className="fin-num">
                            {t("billing.document.col.usage")}
                          </th>
                          <th scope="col" className="fin-num">
                            {t("billing.document.col.rate")}
                          </th>
                        </>
                      )}
                      <th scope="col" className="fin-num">
                        {t("billing.document.col.amount")}
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {group.lines.map((line, index) => (
                      <tr key={`${group.heading}-${index}`}>
                        <td>{line.description}</td>
                        {layout.detail_columns && (
                          <>
                            <td className="fin-num">{line.quantity}</td>
                            <td className="fin-num">{line.unit_price}</td>
                          </>
                        )}
                        {/* ALREADY FORMATTED BY THE SERVER, with the bill's own
                            currency, at the precision the payload froze. Nothing
                            here parses, sums or re-rounds a money figure. */}
                        <td className="fin-num">{line.amount}</td>
                      </tr>
                    ))}
                  </tbody>
                </PlainTable>
              </section>
            ))}
            {!layout.summary_first && (
              <DocumentBand
                heading={t("billing.document.band.summary")}
                fields={document.summary}
                t={translate}
              />
            )}
            {/* US-BIL-028 — the tenant's own custom fields, in the ONE section
                the PO ruled on 2026-08-12 (*"in remark or note section on
                bill"*). It sits exactly where both server serialisations put
                it, between the summary box and the messages, so this viewer
                and the printed page cannot disagree about where a customer's
                own data appears. `DocumentBand` renders nothing when the band
                is empty, so a tenant with no custom fields sees no heading. */}
            {/* ══════════════════════════════════════════════════════════════
                CR-052 TASK 9 — A19 §1.7's TWELVE MONTHS, DRAWN.
                ══════════════════════════════════════════════════════════════
                It sits between the summary box and the remarks because that is
                where BOTH server serialisations put it, so this viewer and the
                printed page cannot disagree about where a customer's own
                consumption appears — the same reason the remarks band sits
                where it does.

                ⚠ **THE SERIES COMES FROM THE DOCUMENT AND FROM NOWHERE ELSE.**
                The bill's contents are frozen at issue (`BR-BIL-030`), so the
                lawful source is `bill_payload.usage_history`, stamped by
                `issue._stamp_usage_history`. Asking the ACCOUNT for its usage
                history instead would draw today's twelve months over a bill
                sent years ago — that is `DEF-2714`, and it is why the block is
                serialised on the response rather than fetched here. */}
            <BillUsagePanel series={document.usage} t={translate} />
            <DocumentBand
              heading={t("billing.document.band.remarks")}
              fields={document.remarks}
              t={translate}
            />
            {/* ══════════════════════════════════════════════════════════════
                CR-052 TASK 11 — THE MESSAGE AND WAYS TO PAY, AS PROSE.
                ══════════════════════════════════════════════════════════════
                This was `<DocumentBand … fields={document.footer} />`, i.e.
                A19 §1.8's two paragraphs in the 220px label/value grid the
                other seven bands use for a date or a name. Both fields have
                been SERVED since the renderer was written and FILLED since
                2026-08-30 (CR-052 task 10, `issue._stamp_bill_copy`), so
                nothing new arrives here — what changes is that a tenant's
                sentences are now drawn at a reading measure with the line
                breaks they typed, and that an EMPTY message states its
                consequence instead of an em-dash.

                ⚠ **THE CONSEQUENCE IS THE LATE-FEE DISCLOSURE, AND THIS FILE
                COMPOSES NONE OF IT.** See `BillCopyPanel`: the terms are the
                tenant's own words, they are charged whether or not they are
                printed, and a platform that wrote a customer's legal
                disclosure for them would be inventing it in one language.
                The panel says the bill carries none; it does not supply one. */}
            <BillCopyPanel fields={document.footer} t={translate} />
            {/* A19 §1.8's tear-off. `no-stub-letter-v1` drops it: a tenant that
                takes payment by ACH or portal only is posting a page with a
                tear-off nobody returns. */}
            {layout.stub && (
              <DocumentBand
                heading={t("billing.document.band.stub")}
                fields={document.stub}
                t={translate}
              />
            )}
          </article>

          {/* THREE KINDS OF GAP, THREE LISTS. One is fixed by stamping more at
              issue, one by embedding a font, one by building something that does
              not exist yet. */}
          {/* ⚠ BOTH LISTS PRINTED THE SERVER'S OWN PROSE UNTIL 2026-08-31 —
              `DEF-2715` again, one panel down from `DocumentBand`. Under
              *Worth looking at*, a clerk read a paragraph naming `OQ-117`,
              `BR-BIL-035`, `bill_payload` in backticks and
              `apps/billing/stages/assemble_document.py`. Every one of those is
              the RIGHT thing to write for the lane report, the log and support,
              and none of them is for the person holding the bill.

              Both `RunProblem.code` and `AbsentField.field` are STABLE CODES —
              that is what they are for — so the sentence is composed in the
              catalogue against the code, and a code this build has never seen
              says so rather than printing itself. The prose is not deleted: it
              rides on `data-detail` with its `data-br-ref`, which is where
              support already looks on this page. */}
          {document.problems.length > 0 && (
            <Panel role="alert">
              <h3>{t("billing.document.problemsTitle")}</h3>
              <ul>
                {document.problems.map((problem) => (
                  <li
                    key={problem.code}
                    data-bil="document-problem"
                    data-code={problem.code}
                    data-br-ref={problem.br_ref}
                    data-detail={problem.detail}
                  >
                    {t(`billing.document.problem.${problem.code}`, {
                      billNo: problem.invoice_no ?? t("billing.bills.noNumber"),
                      defaultValue: t("billing.document.problem.unmapped"),
                    })}
                  </li>
                ))}
              </ul>
            </Panel>
          )}
          {document.pdf_unrepresentable.length > 0 && (
            <Panel role="note">
              <h3>{t("billing.document.pageLimitsTitle")}</h3>
              <ul>
                {document.pdf_unrepresentable.map((entry) => (
                  <li
                    key={entry.field}
                    data-bil="page-limit"
                    data-br-ref={entry.br_ref}
                    data-detail={entry.why}
                  >
                    {t(`billing.document.pageLimit.${entry.field}`, {
                      defaultValue: t("billing.document.pageLimit.unmapped"),
                    })}
                  </li>
                ))}
              </ul>
            </Panel>
          )}
          <GapNotes gaps={document.unavailable} t={translate} />
        </>
      )}
    </div>
  );
}

export default BillDocumentPage;

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-BIL-022@5397d5f (sources: 04-docs/01-spec/19-document-templates.md A19 §1 field order · 04-docs/05-modules/07-billing/06-epics/EP-BIL-06-templates-delivery.md US-BIL-022 · 07-billing/02-business-rules.md BR-BIL-026/030/033/036 · 06-backend/apps/billing/documents_api.py; co-packets US-BIL-026 · US-BIL-028 from EP-BIL-02-invoice-gl.md TC-9/TC-10 + 12-governance/01-open-questions.md OQ-125/OQ-118)
// generated: 2026-08-16 by story-coder (billing SURFACE lane — the viewer documents.py's DOCUMENT_UNAVAILABLE said no human could reach) · AMENDED 2026-08-16 by the billing-9 lane (the Remarks & notes band — US-BIL-028's screen half, the one that was cited from five modules)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: RED PROVED FIRST — the browser check for the document route failed against the W0 placeholder before this screen existed, and the "open the printable page" assertion failed before the link was added. Verbatim in the lane report. tsc✔ · eslint --max-warnings 0✔ · vitest✔ · vite build✔ · run_gates✔
// exceptions: E3 the server's `body` HTML is NOT injected: the page renders the STRUCTURE instead, because `dangerouslySetInnerHTML` over a document containing customer-supplied text is not a trade worth making for markup React already produces · E3 the PDF is a LINK to the inline route, not a fetched blob — the browser's own viewer owns print and save · E3 an absence is badged on ITS OWN field, never as a bare em-dash · E3 `problems`, `pdf_unrepresentable` and `unavailable` render as three separate blocks because they have three different fixes
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
