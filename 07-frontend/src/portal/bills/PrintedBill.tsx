// ── Trace ──────────────────────────────────────────────
// Story:    US-CWP-034 (EP-CWP-07) — the bill as it was printed.
//           Screen: CWP-029 (blueprint `P15`)
// Defects: DEF-CWP-3983 (the printed bill could not be LOOKED at — 22 words
//           and a download link where the drawing frames the issued page) ·
//           DEF-CWP-3986 (`DocumentPreview` was one of the named-but-unbuilt)
// Rules:    BR-CWP-045 (serves the issued file from its pinned template; NEVER
//           re-renders) · BR-NOT-027 (a legal document is frozen AS THE
//           DOCUMENT) · BR-CWP-093 (nothing empty ever appears) · B14 rule 21 ·
//           rule 31 (no database id on screen) · rule 32 (one sentence per
//           section; a stated absence) · rule 33 (a refusal is five or six
//           words) · rule 35 · rule 36
// Tests:    src/portal/bills/PrintedBill.dom.test.tsx
// Impacts:  src/portal/api/portalClient.ts `getPrintedBill` · `printedBillHref`
// ───────────────────────────────────────────────────────
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { PageHeader } from "@/components/PageHeader";
import { Link, useParams } from "react-router-dom";

import { Card, DocumentPreview, usePortalPath } from "../components/primitives";
import { usePortalDate } from "../components/regional";
import { getPrintedBill, printedBillHref, type PortalPrintedBill } from "../api/portalClient";
import { PortalScreen, PortalState } from "../components/states";

/**
 * `CWP-029` — *the bill we sent you*, and nothing that pretends to be it.
 *
 * ⚠ **THIS SCREEN FRAMES THE ISSUED FILE ITSELF, AND THIS PARAGRAPH USED TO SAY
 * THE OPPOSITE (`DEF-CWP-4151`).** It read *"THIS SCREEN DRAWS A DOWNLOAD,
 * NEVER A DOCUMENT … rendering a preview of a bill in this page would be a
 * second document beside the legal one"* — written when that was true, and left
 * standing when `DEF-CWP-3983` added the `DocumentPreview` twelve lines below
 * it. A docstring that forbids what its own file then does is hard-won law 1 in
 * its purest form, and it is worse than a missing comment: the next lane to
 * open this file reads a stated rule against the preview and deletes it.
 *
 * **What is actually true, and why it is not the hazard `BR-CWP-045` names:**
 * the bytes the utility posted are held by `tenancy.document_store`, frozen at
 * issue under `BR-NOT-027`, and the server streams them hash-verified. The
 * frame below points at THAT FILE (`?view=1` streams exactly what the download
 * streams and changes one header) — so it is the same document on screen, not a
 * re-render beside it. A re-RENDER is what `BR-CWP-045` forbids, and nothing
 * here renders anything.
 *
 * ⚠ **AND WHEN NO COPY WAS KEPT, IT SAYS SO** (`US-CWP-034` TC-4). Every bill
 * issued before the freeze landed is that case, so it is the common one rather
 * than the edge: a plain sentence and a route to ask, **not a re-render and not
 * an error page**. The alternative — quietly serving a rebuild under the
 * sentence *"exactly as it was printed"* — is the thing the story exists to
 * prevent, and the figures being right would not make it honest.
 */
export function PrintedBillView(props: { number?: string }) {
  const { t } = useTranslation();
  const params = useParams();
  const path = usePortalPath();
  const asDate = usePortalDate();
  const number = props.number ?? params.number ?? "";
  // ⚠ **THE TENANT COMES FROM THE ROUTE AND FROM NOWHERE ELSE, AND IT IS NOT A
  // PROP.** `G13` flagged it as one nothing supplies and was right to: a prop
  // read only by a test is a second way of getting the same fact, and the day
  // the two disagree the download link points at another utility. It is the
  // same source `api/client.ts` reads for every request — the URL the browser
  // is actually on (`BR-TEN-003`: the tenant is never client input).
  const tenant = params.tenant ?? "";
  const [document, setDocument] = useState<PortalPrintedBill | null>(null);
  const [failed, setFailed] = useState(false);
  // ⚠ **R-10's `Try again` RE-RUNS THE READ.** A way out wired to nothing is
  // `DEF-MET-4764` — pressable, and inert.
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let live = true;
    setDocument(null);
    setFailed(false);
    getPrintedBill(number)
      .then((answer) => {
        if (live) setDocument(answer);
      })
      .catch(() => {
        if (live) setFailed(true);
      });
    return () => {
      live = false;
    };
  }, [number, attempt]);

  // ⚠ **THE HEAD IS BUILT ONCE, ABOVE THE BRANCHES, AND RENDERS ON EVERY ONE
  // OF THEM — `DEF-CWP-4926` (`CR-085` step 2).** It was declared INSIDE the
  // success branch, below `if (failed) return …`, so a failed or a slow read
  // threw away the page title, the `data-screen` mark every rendered check in
  // this repo selects on, and the drawing's whole top row of controls — the
  // one row that could have got the customer anywhere else. Ten signed-in
  // screens shared that single misplaced `return`; `arrears/Overdue.tsx` is
  // the model that already did it this way. R-10 (PO 2026-09-11: *"when a
  // screen tells a customer something bad, the thing they can do about it must
  // be on that same screen"*) cannot be met by a branch that renders no
  // controls at all.
  const head = (
    // ⚠ `data-back` IS THE WALKTHROUGH'S HANDLE ON THE BACK LINK and travels
    // with the head rather than staying behind in the success branch.
    <span data-back="bill">
      <PageHeader
        kicker={t("portal.kicker.bills")}
        title={t("portal.billDocument.title")}
        backTo={{
          to: path(`/bills/${encodeURIComponent(number)}`),
          label: t("portal.billDocument.backToBill", { number }),
        }}
      />
    </span>
  );

  if (failed) {
    return (
      <PortalScreen screen="CWP-029" head={head}>
        <PortalState
          kind="failed"
          testId="printed-bill"
          sentence={t("portal.billDocument.couldNotRead")}
          // ⚠ **R-10 — the way out beside the message** (PO 2026-09-11). This
          // screen matters most to somebody who followed a cold link to send
          // their bill to a landlord or an accountant, so a dead end here is
          // the expensive one: `Try again` re-runs the read, and the bill
          // itself is the address they can still get the figures from.
          waysOut={[
            {
              label: t("portal.state.tryAgain"),
              onClick: () => setAttempt((n) => n + 1),
              tone: "primary",
              testKey: "retry",
            },
            {
              label: t("portal.bills.seeWholeBill"),
              to: path(`/bills/${encodeURIComponent(number)}`),
              testKey: "bill",
            },
          ]}
        />
      </PortalScreen>
    );
  }
  if (!document) {
    return (
      <PortalScreen screen="CWP-029" head={head}>
        <PortalState
          kind="loading"
          testId="printed-bill"
          sentence={t("portal.billDocument.reading")}
        />
      </PortalScreen>
    );
  }

  return (
    <PortalScreen screen="CWP-029" head={head}>
      <Card testId="printed-bill">
        {document.available ? (
          <>
            {/* B14 rule 32 — ONE sentence, and it carries the date rather than
                a rule id or an internal code. */}
            {/* ⚠ **THE DATE GOES THROUGH `asDate`** (`DEF-CWP-4150`, delta
                `X1`). It was interpolated raw, so the one sentence on this
                screen read *"Exactly as it was printed and posted on
                2026-08-02."* — an ISO string in the middle of an English
                sentence, on the screen whose entire job is to say WHEN the
                paper went out. `data-printed-on` keeps the machine-readable
                value for the walkthrough; the prose gets the tenant's format. */}
            <p className="text-body text-neutral-700" data-printed-on={document.issued_on ?? ""}>
              {t("portal.billDocument.exactly", { date: asDate(document.issued_on) })}
            </p>
            {/* ⚠ AN ANCHOR, NOT A FETCH. The response is `application/pdf` with
                `Content-Disposition: attachment`, so the browser's own download
                is what the customer pressed the button for. */}
            {/* ⚠ **THE DOCUMENT ITSELF, FRAMED — `DEF-CWP-3983`.** This
                screen shipped as the sentence above plus the link below: 22
                words, where the drawing gives the issued page most of the
                page, letter-shaped and centred. The bytes are the KEPT file
                (`?view=1` streams exactly what the download streams and
                changes one header), so this is not the re-render
                `BR-CWP-045` forbids — it is the same document, on screen.
                The download stays, inside the frame's fallback and beneath
                it, because pressing *Download* is still a thing people do. */}
            <DocumentPreview
              href={`${printedBillHref(tenant, number)}?view=1`}
              title={t("portal.billDocument.title")}
            >
              <a
                href={printedBillHref(tenant, number)}
                className="text-body font-bold text-neutral-900 no-underline hover:underline"
                data-download="printed-bill-fallback"
              >
                {t("portal.billDocument.download")}
              </a>
            </DocumentPreview>
            {/* ⚠ **AT 390 THE FRAME ABOVE IS 165 × 213 px AND NOBODY CAN
                READ IT — `DEF-CWP-4865`, AND THIS IS A MITIGATION RATHER THAN
                THE FIX.** `DocumentPreview` hardcodes `w-[62%]` with no
                responsive step: 62 % of a 1,026px column is a readable 605,
                62 % of a 316px one is a thumbnail of a letter page. **The fix
                is one responsive class on that component** (`w-full md:w-[62%]`
                and a smaller frame padding), and `primitives.tsx` is outside
                this lane's boundary for `CR-085` step 2 — it is handed to the
                lane that owns the kit, written up in
                `conformance/CR-085-lane5-04-step2-after.md`.
                **What this screen can do without touching the kit is give the
                phone a way to READ the document**: the browser's own viewer,
                full screen, at the one width where the framed copy is useless.
                It is the same `?view=1` stream the frame embeds — the KEPT
                bytes, not a re-render (`BR-CWP-045`) — and it is drawn only
                below `md`, because above it the frame is already readable and
                a second control would be furniture. */}
            <a
              href={`${printedBillHref(tenant, number)}?view=1`}
              target="_blank"
              rel="noreferrer"
              className="text-body font-bold text-neutral-900 no-underline hover:underline md:hidden"
              data-open="printed-bill-full"
            >
              {t("portal.billDocument.openFullScreen")}
            </a>
            <a
              href={printedBillHref(tenant, number)}
              className="text-body font-bold text-neutral-900 no-underline hover:underline"
              data-download="printed-bill"
            >
              {t("portal.billDocument.download")}
            </a>
          </>
        ) : (
          <>
            {/* ⚠ **A STATED ABSENCE, IN THE CUSTOMER'S WORDS** (B14 rule 32) —
                never a blank panel and never a rebuild. The reason code the
                server sent is deliberately NOT shown: rule 32 forbids an
                internal code in customer-facing copy.

                ⚠ **TWO ABSENCES, TWO SENTENCES (`CR-085` `CPB-19`).**
                `BR-NOT-027` distinguishes *we no longer have it* from *what we
                have is not what you received*, and this screen said the first
                over both — when it drew anything at all, because the second
                used to reach the customer as a **500**. They want different
                actions from us: the first is a copy that is simply gone, the
                second is a document nobody may serve until somebody looks at
                it. The code stays off the screen either way. */}
            <p className="text-body text-neutral-700" data-document-absent={document.unavailable_reason ?? ""}>
              {document.unavailable_reason === "document_bytes_do_not_match"
                ? t("portal.document.notTrusted")
                : t("portal.billDocument.notKept")}
            </p>
            <Link
              to={path("/help")}
              className="text-body text-neutral-900 no-underline hover:underline"
              data-link="ask"
            >
              {t("portal.billDocument.askUs")}
            </Link>
          </>
        )}
      </Card>
    </PortalScreen>
  );
}
