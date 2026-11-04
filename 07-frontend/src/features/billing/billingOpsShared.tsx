// ── Trace ──────────────────────────────────────────────
// Story:    US-BIL-015 · US-BIL-018 · US-BIL-021 · US-BIL-022 · US-BIL-006
//           Screens: S30 (Fix a bill · Budget Bills · the pending queue · the
//           document panel) · S8 (Configure → Templates)
// Rules:    BR-TEN-043 (event time is stated by the CALLER — the browser names
//           the business day and the server reads no clock) · BR-SHL-020 (a
//           gap the server reports is rendered, never swallowed) · BR-SHL-023
//           (one money path) · CLAUDE.md rule 2
// ───────────────────────────────────────────────────────
// The three pieces the four new billing surfaces share. They live here rather
// than in `billingShared.tsx` because that file is S30's list/detail vocabulary
// and this is the operations family's — one lane, one diff.
import type {
  DocumentField,
  DocumentUsageMonth,
  DocumentUsageSeries,
  Unavailable,
} from "@/api/billingOpsEndpoints";
import { refusalSentence } from "@/api/refusalSentence";
import type { Translator } from "@/features/tenancy/settingsShared";

/**
 * Today, as an ISO date, FROM THE BROWSER.
 *
 * Every write on these surfaces takes its business date as an argument
 * (BR-TEN-043, gate G6): the server reads no clock, so the caller has to state
 * the day. The browser is the caller here, which means a clerk in another
 * timezone stamps THEIR day — reported rather than papered over, because the
 * alternative is the server guessing, which is the thing the rule forbids. The
 * tenant's own clock is `BR-TEN-020`'s regional setting and no endpoint
 * publishes "today" in it.
 */
export function todayIso(now: Date = new Date()): string {
  return now.toISOString().slice(0, 10);
}

/**
 * The gaps the SERVER reports about itself, rendered.
 *
 * Every one of these surfaces answers with an `unavailable` list — what the
 * build cannot do, with the rule id beside it. A screen that dropped them would
 * be hiding a limitation the API is being honest about, which is hard-won law 1
 * read from the client side. The renderer stays wired even when a list is
 * empty, so a gap added server-side appears without a screen edit.
 *
 * ══════════════════════════════════════════════════════════════════════════
 * WHOSE WORDS A BULLET IS — `DEF-BIL-5339`, 2026-09-15
 * ══════════════════════════════════════════════════════════════════════════
 * A gap that carries a `message_key` renders the CATALOGUE sentence for it,
 * in the clerk's language; one that does not renders its `detail`, exactly as
 * every bullet did before. The 2026-08-19 fix (below) stopped the `br_ref`
 * FIELD printing and could not see an id INSIDE `detail`'s sentence — so
 * `BR-RAT-043`, `OQ-237`, `OQ-142`, `budget_service.enroll` and
 * `budget.settle_up_gl_account` stood on the Budget Bills tab for four weeks
 * with every suite green, because every fixture seeded `unavailable: []`. The
 * key is optional so the six other lists that feed this component (Fix a bill,
 * the document, one-time, layout, pending) render unchanged until their server
 * publishes one; `budgetBillsClerkCopy.dom.test.tsx` reads the RENDERED output
 * of this component and fails on any id or identifier in it.
 *
 * ══════════════════════════════════════════════════════════════════════════
 * AND `detail` COULD STILL CARRY A UUID — `DEF-RAT-7991`, 2026-09-29
 * ══════════════════════════════════════════════════════════════════════════
 * The line above read `gap.message_key !== undefined ? t(gap.message_key) :
 * gap.detail` until this defect, and the `else` half is where the rating
 * chain's own sentence came through whole:
 *
 *     R2: 4 versions of schedule '01a0b366-61fa-7f50-8cc4-25fa070287cc' are in
 *     force for 'sewer' on 2026-10-29 (01a0b366-…, 01a0b388-…, …)
 *
 * **Four database uuids on screen** (B14 rule 31). `refusalSentence` is now
 * the one reader: it resolves the key WITH the server's facts — this component
 * passed none, so a sentence naming a service or a date could not have been
 * written before today — and it refuses to print a `detail` with a uuid in it.
 */
export function GapNotes(props: { gaps: readonly Unavailable[]; t: Translator }) {
  if (props.gaps.length === 0) {
    return null;
  }
  return (
    <details
      className="mt-4 border-l-2 border-l-divider bg-surface px-3 py-2 text-base [&_summary]:cursor-pointer [&_summary]:font-heading [&_summary]:font-semibold [&_ul]:m-0 [&_ul]:mt-2 [&_ul]:pl-4 [&_ul]:leading-prose"
      data-bil="gaps"
    >
      <summary>{props.t("billing.gaps.title", { count: props.gaps.length })}</summary>
      <ul>
        {props.gaps.map((gap) => (
          // ⚠ `br_ref` NO LONGER RENDERS AS TEXT (CR-016, 2026-08-19). It used
          // to be the BOLD LEAD of every bullet, so a billing clerk read
          // "**BR-BIL-026 · OQ-149 (CLOSED 2026-08-12, extended 2026-08-16)** —
          // …" under a heading promising to explain what the screen cannot do.
          // The Product Owner photographed this list. The reference is kept on
          // the element for support, exactly as `RunGap` keeps its own.
          <li key={gap.code} data-br-ref={gap.br_ref}>
            {refusalSentence(gap, props.t)}
          </li>
        ))}
      </ul>
    </details>
  );
}

/**
 * CR-052 task 11 — THE TENANT'S BILL MESSAGE AND WAYS TO PAY, DRAWN AS PROSE.
 *
 * ══════════════════════════════════════════════════════════════════════════
 * WHAT WAS ALREADY TRUE, AND WHY IT WAS NOT ENOUGH
 * ══════════════════════════════════════════════════════════════════════════
 * `documents._footer` has emitted A19 §1.8's two fields since the renderer was
 * written, and `issue._stamp_bill_copy` began FILLING them on 2026-08-30
 * (CR-052 task 10) from the PINNED template version's `options`. So both facts
 * reach this client already, inside the `footer` band.
 *
 * They reached it as a `<dl>` grid of 220px label/value cells — the shape the
 * other seven bands want, because the other seven bands carry a date, a
 * number or a name. **These two carry PARAGRAPHS**: a bill message is a
 * tenant's own sentences and ways-to-pay is a list of addresses and hours.
 * Rendered as a grid cell they wrap into a column three words wide, and the
 * newlines the tenant typed are collapsed by HTML into one run-on line.
 *
 * So this draws them as what they are: full-measure prose, line breaks kept.
 *
 * ══════════════════════════════════════════════════════════════════════════
 * THE LATE-FEE DISCLOSURE — AND WHY THIS COMPONENT COMPOSES NOTHING
 * ══════════════════════════════════════════════════════════════════════════
 * CR-052's own audit row reads: *"`BR-BIL-021` — a tenant bill message and
 * footer … **Neither is stamped.** So the late-fee terms the product is
 * required to print are charged correctly and never disclosed on the paper"*.
 * The task therefore says *"including the late-fee terms the product is
 * required to disclose"*, and the honest reading of that — checked against the
 * code before a word of copy was written — is:
 *
 *     **THE PLATFORM COMPOSES NO LATE-FEE SENTENCE, AND MUST NOT.**
 *
 * `issue._stamp_bill_copy` says so in as many words (*"the late-fee terms are
 * the tenant's words to write … a platform that wrote a customer's disclosure
 * for them would be inventing legal copy in one language"*), and so does the
 * server's own absence text on the `message` field. Those terms are a legal
 * disclosure whose wording, thresholds and jurisdiction belong to the utility;
 * a default sentence shipped by us would be a disclosure this product invented
 * for a customer it has never met, in one language, with no authority behind
 * it. Decision log 2026-08-30 records the same finding.
 *
 * **So an empty message is not styled away — it is REPORTED, in the words a
 * clerk can act on**: this bill went out carrying no message, which means it
 * disclosed no late-payment terms, and one edit on the Templates screen fixes
 * every bill issued after it. What it does NOT say is that the terms are
 * missing from THIS bill in a way anyone can now repair: hard rule 4 makes an
 * issued bill immutable, and BR-BIL-030 means a reprint shows what was sent.
 *
 * ⚠ **THE SERVER'S OWN SENTENCE IS KEPT, AND IS NOT THE HEADLINE.** It is
 * engineering prose — backticks, rule ids, a quoted superseded draft — and
 * DEF-1931's test applies to a screen as much as to a status report: *if a
 * paragraph cannot be read aloud to someone who has never seen the register,
 * it is not finished*. It rides on `title` and `data-br-ref`, where support
 * can reach it, exactly as `GapNotes` keeps `br_ref` off the page. `DEF-2715`
 * carries the same problem on the other seven bands, which this lane did not
 * rewrite.
 */
export function BillCopyPanel(props: { fields: readonly DocumentField[]; t: Translator }) {
  const { fields, t } = props;
  if (fields.length === 0) {
    return null;
  }
  const missing = fields.filter((field) => field.absent !== null);
  return (
    <section
      className="border-t-2 border-t-divider bg-surface px-4 py-3"
      data-bil="bill-copy"
      aria-label={t("billing.document.band.footer")}
    >
      <h3 className="m-0 mb-3 text-h5">{t("billing.document.band.footer")}</h3>
      {fields.map((field) => (
        <div key={field.label} className="mb-3 last:mb-0" data-bil="bill-copy-field">
          <p className="m-0 text-xs tracking-tag uppercase text-[color-mix(in_srgb,var(--color-text)_60%,transparent)]">
            {field.label}
          </p>
          {field.absent === null ? (
            /* THE TENANT'S OWN WORDS. `whitespace-pre-line` keeps the line
               breaks they typed and collapses nothing else; `max-w-[68ch]`
               is a reading measure rather than the band's full width, which
               is what makes a paragraph legible at all. React escapes it on
               the way out — this is a string, never injected markup. */
            <p
              className="m-0 mt-1 max-w-[68ch] leading-prose whitespace-pre-line"
              data-bil="bill-copy-value"
            >
              {field.value}
            </p>
          ) : (
            <p
              className="m-0 mt-1 text-[color-mix(in_srgb,var(--color-text)_55%,transparent)]"
              data-bil="bill-copy-absent"
              data-br-ref={field.absent.br_ref}
              title={field.absent.why}
            >
              {t("billing.document.copyAbsent")}
            </p>
          )}
        </div>
      ))}
      {missing.length > 0 && (
        /* ONE consequence sentence for the whole block, not one per field: a
           tenant who has written neither has one problem, and repeating it
           twice is how a page teaches a reader to stop reading it. */
        <p
          className="m-0 mt-2 border-l-2 border-l-warning-500 bg-warning-100 px-3 py-2 text-base leading-prose"
          role="note"
          data-bil="bill-copy-consequence"
        >
          {t("billing.document.copyConsequence")}
        </p>
      )}
    </section>
  );
}

/**
 * A19 §1.7 — the twelve months this bill FROZE, drawn (CR-052 task 9).
 *
 * ⚠ **THE ONLY SOURCE IS `document.usage`, AND THERE IS DELIBERATELY NO PROP
 * FOR AN ACCOUNT ID.** The obvious alternative — ask the account for its usage
 * history and draw that — is the live join `BR-BIL-030` forbids: the bill's
 * contents are frozen at issue, so a 2026 bill reopened in 2033 would draw
 * 2033's twelve months above 2026's charges and the page would disagree with
 * itself. That was `DEF-2714`, and it is why the backend serialises the frozen
 * block rather than this file fetching anything. This component cannot reach a
 * live read because it is handed no way to.
 *
 * Renders `null` when the bill carries no block — every bill issued before the
 * stamp landed — so the section is omitted whole rather than drawn empty, which
 * is the posture the remarks band already takes.
 */
export function BillUsagePanel(props: {
  series: readonly DocumentUsageSeries[];
  t: Translator;
}) {
  const { series, t } = props;
  if (series.length === 0) {
    return null;
  }
  return (
    <section
      className="border-t-2 border-t-divider bg-surface px-4 py-3"
      data-bil="bill-usage"
      aria-label={t("billing.document.band.usage")}
    >
      <h3 className="m-0 mb-3 text-h5">{t("billing.document.band.usage")}</h3>
      {series.map((entry) => (
        <UsageSeriesChart key={entry.heading} entry={entry} t={t} />
      ))}
    </section>
  );
}

/** One service's axis: a bar per month, then the months under it. */
function UsageSeriesChart(props: { entry: DocumentUsageSeries; t: Translator }) {
  const { entry, t } = props;
  // The tallest MEASURED month is the axis. An absent month contributes
  // nothing to it — it is not a zero, it is a month nobody read.
  const peak = entry.months.reduce(
    (max, month) => (month.absent ? max : Math.max(max, Number(month.quantity || 0))),
    0,
  );
  const anyEstimated = entry.months.some((month) => month.estimated && !month.absent);
  return (
    <div className="mb-4 last:mb-0" data-bil="bill-usage-series">
      <p
        className="m-0 mb-2 text-xs tracking-tag uppercase text-[color-mix(in_srgb,var(--color-text)_60%,transparent)]"
        data-bil="bill-usage-caption"
      >
        {entry.unit ? `${entry.heading} · ${entry.unit}` : entry.heading}
      </p>
      {entry.absent !== null && (
        <p
          className="m-0 mb-2 text-sm text-[color-mix(in_srgb,var(--color-text)_55%,transparent)]"
          data-bil="bill-usage-unit-absent"
          data-br-ref={entry.absent.br_ref}
          title={entry.absent.why}
        >
          {t("billing.document.usageMixedUnits")}
        </p>
      )}
      <div className="flex h-[120px] items-end gap-1 border-b border-[var(--color-divider)] py-2">
        {entry.months.map((month) => (
          <UsageBar key={month.label} month={month} peak={peak} t={t} />
        ))}
      </div>
      <div className="flex gap-1">
        {entry.months.map((month) => (
          <p
            key={month.label}
            className="m-0 mt-1 flex-1 text-center text-xs text-[color-mix(in_srgb,var(--color-text)_60%,transparent)]"
            data-bil="bill-usage-month"
          >
            {month.label}
          </p>
        ))}
      </div>
      {anyEstimated && (
        <p className="m-0 mt-2 text-sm" data-bil="bill-usage-estimated">
          {t("billing.document.usageEstimated")}
        </p>
      )}
    </div>
  );
}

/** One month. An unread month draws NO bar — `BR-MET-106`, absent never zero.
 *
 *  Deliberately the same mark as `customers/AccountUsageTab.UsageBar`: the same
 *  customer's consumption should not look like two different things on two
 *  screens (B14's consistency rule), and that component's shape was arrived at
 *  by screenshotting rather than by reasoning. The colour is an inline style
 *  there and here — `background: var(--color-accent)` — rather than a Tailwind
 *  arbitrary value, which is the proven path.
 */
function UsageBar(props: { month: DocumentUsageMonth; peak: number; t: Translator }) {
  const { month, peak, t } = props;
  if (month.absent) {
    // No bar. An empty slot, and nothing that could be read as "used nothing".
    return (
      <div
        className="h-full flex-1 self-stretch"
        data-bil="bill-usage-bar"
        data-month={month.label}
        data-absent="true"
        title={t("billing.document.usageNoReading")}
      />
    );
  }
  const value = Number(month.quantity || 0);
  // A HEIGHT is data, so it is an inline style; every non-data style here is a
  // utility. The 2% floor keeps a real but tiny month visible as a mark rather
  // than letting it vanish into the axis and read as an absence.
  const height = peak > 0 ? Math.max(2, (value / peak) * 100) : 2;
  return (
    <div
      className="flex-1 self-end"
      data-bil="bill-usage-bar"
      data-month={month.label}
      data-absent="false"
      data-estimated={month.estimated ? "true" : "false"}
      title={`${month.quantity_display}${month.unit ? ` ${month.unit}` : ""}`}
      style={{
        height: `${height}%`,
        background: "var(--color-accent)",
        // The estimated month is MARKED, not hidden and not equal-looking.
        opacity: month.estimated ? 0.55 : 1,
        outline: month.estimated ? "1px dashed var(--color-accent)" : undefined,
        outlineOffset: month.estimated ? "-1px" : undefined,
      }}
    />
  );
}

// ── Routes (tenant-relative, like every route constant since path tenancy) ──

/** The pending-billing queue — S30's own sub-route, not a seventh tab. The
 *  prototype's Billing strip has six and G14 compares the shipped labels
 *  against it; the queue is reached from the header instead. */
export const BILLING_PENDING_ROUTE = "/billing/pending";

/** The document a clerk opens — `/billing/bills/{id}/document`. A ROUTE rather
 *  than a modal so a support ticket can carry the link to the exact page a
 *  customer is holding. */
export function billDocumentPath(invoiceId: string): string {
  return `/billing/bills/${encodeURIComponent(invoiceId)}/document`;
}

/**
 * CR-053 task 11 — THE PRINTABLE PAGE'S OWN ADDRESS, for a caller that has a
 * row and not a document.
 *
 * ⚠ **THIS IS AN API PATH AND NOT A ROUTE, AND THE DIFFERENCE IS DEF-2450.**
 * It is the value `documents_api._rendered_dict` publishes as `pdf_url` —
 * `f"/invoices/{invoice_id}/document.pdf"` — and it is therefore missing the
 * `/api` prefix and the tenant segment that `client.ts` adds for a fetch and
 * that a browser navigation must be given by hand. Handing the bare string to
 * an anchor navigates the SPA to a route that does not exist — the defect this
 * docstring is named after.
 *
 * ⚠ **THIS PARAGRAPH TOLD YOU TO WRITE `` `/api${tenantPath(...)}` `` BY HAND
 * UNTIL 2026-09-28, AND THAT IS NOW THE DEFECT RATHER THAN THE FIX
 * (`CR-144-BRC07`).** The API answers on its OWN ORIGIN now, so a root-relative
 * string opens on the STATIC host — which serves `index.html` for an unknown
 * path, so the clerk gets a new tab containing the application and no error at
 * all. **A caller handing this to an `<a href>`, an `<iframe src>` or a
 * `window.open` writes `apiHref(tenantPath(billDocumentPdfPath(id)))`**, which
 * is what `BillDocumentPage` and the other sixteen sites do.
 *
 * **WHY IT IS COMPOSED HERE AT ALL.** The bill DETAIL reads `pdf_url` off `GET
 * /invoices/{id}/document` and never composes anything; a LIST row cannot,
 * because that would be one request per row for a fact the id already
 * determines. Composing a path a client already composes for every other route
 * in `endpoints.ts` is the same trade the whole API layer makes, and it is made
 * in ONE place so a change to the route is a change to one line.
 */
export function billDocumentPdfPath(invoiceId: string): string {
  return `/invoices/${encodeURIComponent(invoiceId)}/document.pdf`;
}

export const FIX_A_BILL_PARAM = "bill";

/**
 * S30's Fix-a-bill tab with ONE BILL already chosen — the "Correct this bill"
 * exit from the bill detail.
 *
 * The bill travels in the URL rather than in a prop, and that is the whole
 * reason this function exists: a prop nothing passes is dead UI (hard-won law
 * 2, and G13 catches it), while a query parameter makes the pre-filled screen a
 * shareable link a support ticket can carry — which is what a clerk actually
 * needs when somebody else has to finish the correction.
 */
export function fixABillPath(invoiceId: string): string {
  return `/billing/fix?${FIX_A_BILL_PARAM}=${encodeURIComponent(invoiceId)}`;
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-BIL-015@a71c4e2 (sources: EP-BIL-04-corrections.md · EP-BIL-05-budget-billing.md · EP-BIL-06-templates-delivery.md · EP-BIL-01-bill-run.md US-BIL-006 · 07-billing/02-business-rules.md; co-packets US-BIL-018, US-BIL-021, US-BIL-022, US-BIL-006)
// generated: 2026-08-16 by story-coder (billing SURFACE lane)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: tsc✔ · eslint --max-warnings 0✔ · vitest✔ · vite build✔ · run_gates✔
// exceptions: E3 `todayIso` reads the BROWSER's clock and that is REPORTED, not hidden: BR-TEN-043 forbids the server reading one, so somebody has to state the day, and no endpoint publishes the tenant's today · E3 the pending queue is a ROUTE and not a seventh S30 tab — the prototype's strip has six and G14 compares the shipped labels against it
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
