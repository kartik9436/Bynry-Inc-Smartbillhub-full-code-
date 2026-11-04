// ── Trace ──────────────────────────────────────────────
// Story:    US-BIL-021 (the template lifecycle — the CHOOSER half, which is all
//           R2 has) · US-BIL-022 (what future bills pin)
//           Screens: S8 (Settings → Configure → Templates)
// Rules:    BR-BIL-025 (the category-less template is the tenant's FALLBACK,
//           and there is exactly one) · BR-BIL-026 (choosing is a NEW VERSION;
//           publishing affects only FUTURE bills) · BR-BIL-027 (System Admin
//           publishes; a version pinned by any bill can never be deleted) ·
//           BR-SHL-020 · BR-SHL-025 (a forbidden control renders disabled WITH
//           its reason) · BR-TEN-043 (the business date is stated)
// ───────────────────────────────────────────────────────
// S8 → Configure → Templates. This tab rendered "arrives with …" for a week
// while `templates_service.py` held a complete draft→publish→archive lifecycle
// nothing could reach.
//
// ══════════════════════════════════════════════════════════════════════════
// WHAT REPLACED THE DESIGNER — PO RULING 2026-08-16
// ══════════════════════════════════════════════════════════════════════════
// A1 reserves S91–S96 for a bill-layout designer. **The PO cut all six**,
// verbatim: *"why cant we give 5 differnt tempaltes to start with and ask user
// to choose anyone; we will ahve 1 default tempalte allways"*. So this is a
// LIST and a CHOICE, and the trade is a good one rather than a reduction: no
// HTML/CSS rendering engine enters the deployment image, nothing a tenant types
// can reach a customer's page as markup, and there is always exactly one live
// layout because the database holds one published version per template.
//
// ══════════════════════════════════════════════════════════════════════════
// THE RULE THIS SCREEN MUST NOT LOSE — AND THE SENTENCE THAT NO LONGER SAYS IT
// ══════════════════════════════════════════════════════════════════════════
// **Choosing changes FUTURE bills only.** Every bill already issued carries its
// own pin and renders from it forever (BR-BIL-026 / BR-CUS-040). That is
// unchanged, it is enforced on the server, and nothing here may weaken it.
//
// ⚠ **WHAT WENT IS THE BANNER, NOT THE BEHAVIOUR (`DEF-BIL-4524`, 2026-09-07).**
// A note above the three layouts read *"Changing this affects bills issued from
// now on. Every bill already sent keeps the layout it was printed on and will
// always reprint that way."* The Product Owner asked for it to go, verbatim:
// *"we are in beta and Im going to delete previous references so you dont have
// to worry about previous bills - please fix this"*. They are discarding their
// own beta DATA, not the rule — so the rule stayed and the sentence went, and
// `billing.layout.futureOnly` was retired from all eleven catalogues in the
// same commit so G18 cannot find a dead key.
//
// B14 rule 32 is the second argument for the same edit: a screen has a
// description budget, and two paragraphs of standing explanation above a
// chooser spends it on something no clerk has asked about.
//
// **A LANE THAT WANTS TO PUT IT BACK NEEDS A NEW RULING**, not this comment.
// The place the fact still lives on screen is the version table below, which
// shows how many bills print on each version — "v1 · Standard · 1,847 bills"
// is why v1 can never be deleted, and it is a NUMBER rather than a warning.
import { useState } from "react";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { apiHref } from "@/api/apiHref";
import { api, isApiError } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { chooseBillLayout, getBillTemplateLibrary } from "@/api/billingOpsEndpoints";
import { Button } from "@/components/Button";
import { LoadingSkeleton } from "@/components/StateFrame";
import { StatusPill } from "@/components/StatusPill";
import { useToast } from "@/components/Toast";
import { PlainTable } from "@/components/Surfaces";
import { Panel } from "@/components/Panel";
import { apiErrorText } from "@/features/tenancy/settingsShared";
import type { Translator } from "@/features/tenancy/settingsShared";

import { useTenantPath } from "@/routing/tenantPath";

import { GapNotes, todayIso } from "./billingOpsShared";

export const billTemplateLibraryKey = ["bill-templates", "library"] as const;

export interface BillLayoutTabProps {
  client?: ApiClient; // test seam
  /** S8's A4 cell — a View role sees the library and cannot change it. */
  readOnly?: boolean;
}

export function BillLayoutTab(props: BillLayoutTabProps) {
  const { t } = useTranslation();
  const translate: Translator = (key, params) => t(key, params);
  const client = props.client ?? api;
  const queryClient = useQueryClient();
  const tenantPath = useTenantPath();
  const toast = useToast();
  const [pending, setPending] = useState<string | null>(null);

  const libraryQuery = useQuery({
    queryKey: billTemplateLibraryKey,
    queryFn: () => getBillTemplateLibrary(client),
    retry: false,
  });
  const chooseMutation = useMutation({
    mutationFn: (layoutKey: string) =>
      chooseBillLayout({ layout_key: layoutKey, on_date: todayIso() }, client),
  });

  if (libraryQuery.isError) {
    return (
      <Panel role="alert">
        <h3>{t("billing.layout.errorTitle")}</h3>
        <p className="font-body text-base leading-normal font-normal tracking-normal text-[color-mix(in_srgb,var(--color-text)_62%,transparent)] [&[role=alert]]:text-accent-700">
          {apiErrorText(libraryQuery.error, translate)}
        </p>
      </Panel>
    );
  }
  const library = libraryQuery.data;
  if (library === undefined) {
    return <LoadingSkeleton variant="card" />;
  }

  // NULL is a repairable state and a DIFFERENT one from an empty library. A
  // tenant whose provisioning seeder did not run has no template; a build with
  // no layouts would be a defect. The screen must be able to say which.
  if (library.template === null) {
    return (
      <Panel role="alert">
        <h3>{t("billing.layout.noTemplateTitle")}</h3>
        <p className="font-body text-base leading-normal font-normal tracking-normal text-[color-mix(in_srgb,var(--color-text)_62%,transparent)] [&[role=alert]]:text-accent-700">
          {t("billing.layout.noTemplate")}
        </p>
      </Panel>
    );
  }

  return (
    <div className="flex flex-col gap-2">
      {/* ⚠ **ONE SENTENCE, AND IT SAYS WHAT THESE THINGS ARE (`DEF-BIL-4458`,
          B14 rule 32).** It opened *"Choose the page your customers receive"* —
          true, and it never said that the five boxes below it were PAGE
          DESIGNS. The Product Owner, looking at the running screen: *"I see
          some boxes - standard, compact, amount due first, no remitance stub
          pre-printed leterhead - it doe snot match - I dont know what these
          boxes are and why so much content below them"*. Each card now shows
          the page itself, so the sentence has less to carry, not more. */}
      <p className="m-0 mb-4 max-w-measure text-base leading-prose text-[color-mix(in_srgb,var(--color-text)_70%,transparent)]">
        {t("billing.layout.explainer")}
      </p>
      {/* ⚠ **THREE COLUMNS AND NOT `.chooser`'s FIVE (`DEF-BIL-4458`).**
          `.chooser` is `minmax(220px, 1fr)`, which is right for a card holding
          a title and a sentence and far too narrow for a US Letter page: at
          1120px it draws five 212px columns and a bill in one of those is a
          grey smudge. Three columns give each preview ~360px, which is the
          width the page below actually needs to be legible. Utilities and no
          new stylesheet class (B14 rule 21; this file is on
          `route-b-migrated.txt`), the ruled breakpoints only (OQ-274), and
          MAX-WIDTH variants because `tailwind.css` says in capitals that this
          theme is desktop-first — `max-lg:` and never `lg:`. Both compile and
          render the same at every width, which is why `G107` exists. */}
      <div className="mt-3 mb-4 grid grid-cols-3 items-stretch gap-3 max-lg:grid-cols-2 max-sm:grid-cols-1">
        {library.layouts.map((layout) => {
          const blocked =
            props.readOnly === true
              ? t("billing.layout.readOnly")
              : !layout.renders
                ? t("billing.layout.notRenderable")
                : null;
          return (
            <label
              key={layout.key}
              className={layout.is_current ? "chooser-option is-selected" : "chooser-option"}
            >
              <span className="co-title">{layout.label}</span>
              {/* ⚠ **THE PAGE ITSELF, RENDERED BY THE SERVER (`DEF-BIL-4458`).**
                  The Product Owner's question was *"can you show me the screen
                  where I can clearly wsee how actual template look like"*, and
                  until this frame the answer was a paragraph of prose per
                  layout: a System Admin was choosing the page every customer
                  receives, sight unseen.

                  ⚠ **IT IS THE SERVER'S PRINTABLE PAGE, EMBEDDED — NOT A
                  RE-DRAWING OF IT.** `bill-templates/layouts/{key}/preview.pdf`
                  renders one of this tenant's REAL issued bills through
                  `documents.py`'s own serialiser for that layout, so what a
                  person compares here is what will print. Anything this file
                  drew from the payload would be a second renderer, which is
                  hard-won law 5 with a customer's bill in it.

                  ⚠ **A FRAME AND NOT `<embed>`/`<object>`**, for the reason
                  `BillDetailPage` already records: it takes a `title` a screen
                  reader announces, and the browser's own PDF viewer carries
                  print and save without this app re-implementing either.

                  ⚠ **AND WHEN THERE IS NOTHING TO DRAW IT SAYS SO** — a blank
                  grey box asserts "this layout prints an empty page", which is
                  a different and alarming claim (BR-SHL-020). The server sends
                  one sentence for the whole library, because the reason is the
                  same for all five: this utility has not issued a bill yet. */}
              {layout.preview_url !== null && layout.preview_unavailable === null ? (
                <iframe
                  title={t("billing.layout.previewTitle", { layout: layout.label })}
                  /* ⚠ **`view=Fit` AND NOT `view=FitH`, AND THE BROWSER IS
                     WHAT SAID SO.** `FitH` fits the page WIDTH, which in a
                     333px frame means the top inch of a US Letter page at
                     enormous magnification — measured at 1440, three of the
                     five frames settled on a readable whole page and two on a
                     giant `UTILITY BILL` heading, so the five could not be
                     compared at all. `Fit` fits the whole page, which is the
                     only zoom under which "these five differ" is a thing a
                     person can see. `page=1` pins the first sheet, because a
                     three-page bill scrolled to wherever the viewer left it.
                     No check in this repo could have found this: the frames
                     are identical in the DOM and the difference is inside the
                     browser's own PDF viewer (hard-won law 6). */
                  src={`${apiHref(tenantPath(layout.preview_url))}#page=1&toolbar=0&navpanes=0&scrollbar=0&view=Fit`}
                  className="my-2 h-[24rem] w-full border border-divider bg-neutral-100"
                  data-bil="layout-preview"
                  data-layout-key={layout.key}
                />
              ) : (
                <span
                  className="my-2 flex h-[24rem] w-full items-center border border-dashed border-divider p-3 text-sm leading-prose text-[color-mix(in_srgb,var(--color-text)_60%,transparent)]"
                  role="note"
                  data-bil="layout-preview-absent"
                  data-layout-key={layout.key}
                >
                  {layout.preview_unavailable ?? t("billing.layout.notRenderable")}
                </span>
              )}
              <span className="co-desc">{layout.summary}</span>
              <span className="co-meta">
                {layout.is_current && (
                  <StatusPill tone="success">{t("billing.layout.current")}</StatusPill>
                )}
                {layout.is_platform_default && !layout.is_current && (
                  <StatusPill tone="neutral">{t("billing.layout.platformDefault")}</StatusPill>
                )}
              </span>
              <Button
                variant="secondary"
                disabled={blocked !== null || layout.is_current || pending !== null}
                title={blocked ?? undefined}
                onClick={async () => {
                  setPending(layout.key);
                  try {
                    const outcome = await chooseMutation.mutateAsync(layout.key);
                    await queryClient.invalidateQueries({ queryKey: ["bill-templates"] });
                    // The server's OWN sentence, so the reason a version was or
                    // was not minted cannot drift from what actually happened.
                    toast(outcome.reason);
                  } catch (error) {
                    toast(
                      isApiError(error)
                        ? apiErrorText(error, translate)
                        : t("api.error.unexpected"),
                    );
                  } finally {
                    setPending(null);
                  }
                }}
              >
                {layout.is_current ? t("billing.layout.inUse") : t("billing.layout.chooseAction")}
              </Button>
              {blocked !== null && (
                <span
                  className="block text-xs text-[color-mix(in_srgb,var(--color-text)_60%,transparent)]"
                  role="note"
                >
                  {blocked}
                </span>
              )}
            </label>
          );
        })}
      </div>

      <Panel as="section">
        <h3>{t("billing.layout.versionsTitle")}</h3>
        <PlainTable>
          <thead>
            <tr>
              <th scope="col">{t("billing.layout.col.version")}</th>
              <th scope="col">{t("billing.layout.col.layout")}</th>
              <th scope="col">{t("billing.layout.col.status")}</th>
              <th scope="col">{t("billing.layout.col.published")}</th>
              <th scope="col" className="fin-num">
                {t("billing.layout.col.pinned")}
              </th>
            </tr>
          </thead>
          <tbody>
            {library.versions.map((version) => (
              <tr key={version.id}>
                <td>{t("billing.layout.versionNo", { version: version.version_no })}</td>
                <td>
                  {library.layouts.find((layout) => layout.key === version.layout_key)?.label ??
                    version.layout_key}
                </td>
                <td>
                  <StatusPill
                    tone={version.status === library.published_status ? "success" : "neutral"}
                  >
                    {t(`billing.layout.versionStatus.${version.status}`, {
                      defaultValue: version.status,
                    })}
                  </StatusPill>
                </td>
                <td>
                  {version.published_on ?? (
                    <span className="font-body text-base leading-normal font-normal tracking-normal text-[color-mix(in_srgb,var(--color-text)_62%,transparent)] [&[role=alert]]:text-accent-700">
                      {t("billing.layout.notPublished")}
                    </span>
                  )}
                </td>
                <td className="fin-num">
                  {/* BR-BIL-027's audit-lock number, and the reason a version
                      can never be deleted once a bill prints on it. */}
                  {t("billing.layout.pinnedBills", { count: version.pinned_bills })}
                </td>
              </tr>
            ))}
          </tbody>
        </PlainTable>
      </Panel>

      {/* ⚠ **CLOSED BY DEFAULT (B14 rule 32, and `DEF-BIL-4458`'s second
          half).** The Product Owner's sentence had two complaints in it and
          this is the other one: *"why so much content below them"*. `ArrivesWith`
          draws an always-open note, so a 194-character paragraph about a page
          designer this product deliberately does not have sat under the choice
          on every visit. Rule 32 says a stated absence is CLOSED by default —
          the fact is not removed, it is folded, exactly as `GapNotes` beside it
          already is. */}
      <details
        className="mt-4 border-l-2 border-l-divider bg-surface px-3 py-2 text-base [&_p]:m-0 [&_p]:mt-2 [&_p]:leading-prose [&_summary]:cursor-pointer [&_summary]:font-heading [&_summary]:font-semibold"
        data-bil="layout-awaits"
      >
        <summary>{t("billing.layout.awaitsTitle")}</summary>
        <p>{t("billing.layout.awaits")}</p>
      </details>
      <GapNotes gaps={library.unavailable} t={translate} />
    </div>
  );
}

export default BillLayoutTab;

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-BIL-021@2b52def (sources: 04-docs/05-modules/07-billing/06-epics/EP-BIL-06-templates-delivery.md US-BIL-021 · 07-billing/02-business-rules.md BR-BIL-025/026/027 · 08-qa/01-e2e/journeys/J22-template-life.md · the PO ruling of 2026-08-16 in 12-governance/02-decision-log.md, which CUT S91–S96 · 06-backend/apps/billing/templates_api.py; co-packet US-BIL-022)
// generated: 2026-08-16 by story-coder (billing SURFACE lane — S8's Templates sub-tab, which rendered "arrives with …")
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: RED PROVED FIRST — the browser check asserted five named layouts on S8 → Configure → Templates and found the "arrives with the template designer" panel instead. Verbatim in the lane report. tsc✔ · eslint --max-warnings 0✔ · vitest✔ · vite build✔ · run_gates✔
// exceptions: E3 S91–S96 (the DESIGNER) are CUT by PO ruling 2026-08-16 and nothing here stands in for them — no canvas, no blocks, no colour, no logo · E3 a layout the platform lists but cannot RENDER is drawn DISABLED with its reason rather than hidden · E3 [DEF-BIL-4524, 2026-09-07] the "future bills only" BANNER is gone by PO ruling ("we are in beta and Im going to delete previous references so you dont have to worry about previous bills - please fix this") and the RULE is untouched — the pin is server-side (BR-BIL-026) and the version table still shows the bill count per version, which is the same fact as a number rather than as a warning · E3 the toast carries the SERVER's own sentence, so "no new version was created" cannot drift from what happened · E3 a missing tenant template is an explicit repairable state, distinct from an empty library
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
