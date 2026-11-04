// ── Trace ──────────────────────────────────────────────
// Story:    US-CWP-036 (EP-CWP-07) — *"Documents and letters: what we sent,
//           when, and by which route"*. Screen: CWP-031 (blueprint `P17`)
// Rules:    BR-CWP-083 (post and email remain the DELIVERY RECORD; the portal
//           shows the record) · BR-CWP-045 (documents are SERVED, never
//           re-rendered) · BR-CWP-056 (a control that may not be used is
//           DISABLED WITH ITS REASON — never hidden) · BR-CWP-093 (nothing
//           empty ever appears) · `OQ-1399` CLOSED 2026-09-04 — the portal is
//           a CONVENIENCE COPY · B14 rule 20 (one table type) · rule 21
//           (Tailwind utilities; `portal/` is on route-b-migrated.txt) ·
//           rule 31 (no database id is a visible value) · rule 32 (one
//           sentence per section) · rule 33 (a refusal is five or six words) ·
//           rule 35 (each catalogue in its own language) · rule 36 (compose
//           the kit — `SegmentedControl` and `MiniTable` are the kit's)
// Tests:    src/portal/documents/Documents.dom.test.tsx
// Impacts:  src/portal/api/portalClient.ts `getDocuments`
// ───────────────────────────────────────────────────────
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { PageHeader } from "@/components/PageHeader";
import { DownloadIcon, EyeIcon } from "@/components/icons";

import { usePortalDate } from "../components/regional";
import { splitNeedle, usePortalListWindow } from "../components/listWindow";
import { ButtonAnchor } from "@/components/Button";
import { Card, HeldButton, rowActionName, StatusChip, usePortalPath } from "../components/primitives";
import { PortalScreen, PortalState } from "../components/states";
import { Link, useParams } from "react-router-dom";
import { formatMoney } from "../signin/Enrol";
import { PortalListTable } from "../components/listTable";
import type { PageSize } from "@/components/tableTypes";
import {
  documentFileHref,
  documentsBundleHref,
  getDocuments,
  type PortalDocuments,
  type PortalDocument,
  type PortalDocumentRoute,
} from "../api/portalClient";

/** `state` → the chip's tone.
 *
 * ⚠ **THERE IS NO `success` TONE ON THIS SCREEN AND THAT IS THE WHOLE POINT.**
 * Green reads as *arrived*. Nothing on this deployment reports a delivery on
 * any channel, so the strongest thing this product may say is *we sent it* —
 * which is a neutral fact, not a happy one (`BR-CWP-083`). A customer ringing
 * up about a letter that never came must not be shown a green tick.
 */
const TONE: Record<string, "neutral" | "warning" | "danger" | "info"> = {
  sent: "neutral",
  queued: "info",
  held: "warning",
  could_not_send: "danger",
};

/**
 * `CWP-031` — everything we sent, when, and by which route.
 *
 * ⚠ **THE SCREEN SAYS WHAT WAS SENT AND NEVER THAT IT ARRIVED.** That single
 * sentence is the whole design. `outbound_messages` is the record of what left
 * the building; `delivered` and `bounced` are provider facts and no provider
 * adapter exists on print, email or SMS, so the server carries
 * `delivery_reported: false` with its reason on every row and this screen
 * prints it ONCE above the table (B14 rule 32 — one sentence per section,
 * never the same caveat on forty rows).
 *
 * ⚠ **AN EMPTY LIST AND AN UNREACHABLE QUEUE ARE TWO DIFFERENT SENTENCES.**
 * `documents: []` is a new customer and gets the empty state naming what will
 * fill it (`US-CWP-036` TC-4 — *"the commonest first impression the portal
 * makes"*). `documents: null` is the queue not answering, and says so: drawing
 * the first over the second would tell somebody with eleven months of bills
 * that we never wrote to them, which is the fabricated-value family the staff
 * Documents FRAME is written against.
 *
 * ⚠ **A SKIPPED NOTICE IS NOT HERE, AND THAT SPLIT IS DELIBERATE**
 * (`US-CWP-036` TC-8, J47 step 2). A notice the ladder decided not to send
 * produced no document, so it cannot appear in a list of documents; it belongs
 * on `CWP-068`, which reads the notice history.
 */
export function DocumentsView(props: { accountId: string }) {
  const { t } = useTranslation();
  // `DEF-CWP-3994` — the tenant's own date format, published at the frame.
  const asDate = usePortalDate();
  /**
   * ⚠ **ONE PAGE, AND THE SEARCH, THE CHIPS AND THE SORT TRAVEL WITH IT**
   * (`DEF-CWP-5747`, `NFR-3`). This screen asked for everything the utility
   * has ever sent this account and let the browser search, chip, sort and
   * slice it. Moving only the page would have been worse than leaving it — a
   * customer typing a bill number that is on page 7 would be told no such
   * letter exists.
   *
   * ⚠ **THE GROUP WORD IS RESOLVED HERE BECAUSE ONLY THIS SIDE KNOWS THE
   * LANGUAGE.** The first column's biggest words are the KIND, and the chips
   * read *Bills · Receipts · Letters* — all catalogue words (B14 rule 35), all
   * of which a customer will type. The server stores `bill` · `receipt` ·
   * `letter`, so the screen turns the word it drew back into the code.
   */
  const list = usePortalListWindow({
    resolve: (needle) =>
      splitNeedle(needle, [
        {
          name: "group",
          words: Object.fromEntries(
            (["bill", "receipt", "letter"] as const).map((group) => [
              group,
              // Both the column's word and the chip's, because a customer may
              // type either — the column reads *Bill* and the chip *Bills*.
              `${t(`portal.documents.group.${group}`)} ${t(
                `portal.documents.filter${group === "bill" ? "Bills" : group === "receipt" ? "Receipts" : "Letters"}`,
              )}`,
            ]),
          ),
        },
      ]),
  });
  const [answer, setAnswer] = useState<PortalDocuments | null>(null);
  const rows = answer?.documents ?? null;
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState(false);
  // ⚠ **R-10's `Try again` RE-RUNS THE READ** rather than looking as though it
  // does (`DEF-MET-4764`). Two of this screen's four branches are bad news and
  // both of them are a read that did not work, so both get it.
  const [attempt, setAttempt] = useState(0);
  const path = usePortalPath();
  // ⚠ **THE TENANT COMES FROM THE ROUTE AND FROM NOWHERE ELSE**, the same
  // source `PrintedBill.tsx` reads and for its reason (`BR-TEN-003`: the tenant
  // is never client input). It is not a prop — a prop supplied only by a test
  // is a second way of getting a fact the router already has, which is what
  // `G13` refuses.
  const tenant = useParams().tenant ?? "";

  const { request } = list;
  useEffect(() => {
    let live = true;
    setFailed(false);
    // The rows stay on screen while the next page is in flight — see
    // `Readings.tsx`'s note: blanking a list on every page turn loses the
    // reader's place and reads as the screen breaking.
    setBusy(true);
    getDocuments(props.accountId, request)
      .then((next) => {
        if (!live) return;
        setAnswer(next);
        setBusy(false);
      })
      .catch(() => {
        if (live) {
          setFailed(true);
          setBusy(false);
        }
      });
    return () => {
      live = false;
    };
  }, [props.accountId, request, attempt]);

  // ⚠ **THE HEAD IS BUILT ONCE AND RENDERS ON EVERY BRANCH, LOADING INCLUDED**
  // (`DEF-CWP-4000`; audit D1, delta X4/X5). It composes the shared
  // `components/PageHeader.tsx` — B14 rule 2's one page head — never a second.
  //
  // ⚠ **`↓ Download a year` IS LIVE (`CR-085` `CPB-15`).** It moved from the
  // foot of the table into the head with `DEF-CWP-4000` and stayed HELD there,
  // reading *"Downloads are not ready yet"* — and its row in `holds.ts` said
  // *"No file-serving path exists in apps/portal at all"*, which stopped being
  // true the day `US-CWP-034` shipped the bill PDF and was never re-read. That
  // is hard-won law 2's mirror: a live capability behind a dead control.
  //
  // ⚠ **IT IS HELD AGAIN THE MOMENT THERE IS NOTHING KEPT TO SEND**, and that
  // refusal CANNOT ROT: it is answered by the rows on the screen every time it
  // draws, so it is a `fact` in `holds.ts`'s vocabulary rather than a promise
  // about the future. An archive of nothing is worse than a held button —
  // pressing it would download an empty file and look like the product
  // working.
  // ⚠ **THE SERVER'S ANSWER OVER THE WHOLE SET, NOT THIS PAGE'S**
  // (`DEF-CWP-5747`). It was `rows.filter(...)` over every document the
  // account had; counted off a page it would hold `Download a year` on page 2
  // for a customer whose kept documents are all on page 1 — a refusal that is
  // simply false, which is hard-won law 2's mirror wearing a page number.
  const anyKept = answer?.any_kept === true;
  const populated = answer?.populated === true;
  const head = (
    <PageHeader
      kicker={t("portal.kicker.documents")}
      // ⚠ **`Your documents` — THE BLUEPRINT'S OWN TITLE (PO 2026-09-11).** It
      // read *Documents and letters*, which is the module pack's. The ruling
      // that the 8 September PDF is the design settles it, and the same key
      // names the door on `CWP-027` and `CWP-022`, so all three move together.
      title={t("portal.documents.title")}
      // ⚠ **HOW MANY, WHICH IS HALF OF `CPB-15` AND THE HALF WE CAN DERIVE.**
      // The drawing's sub-line is *6 documents · kept for seven years*. The
      // COUNT is on the screen already. The RETENTION PERIOD is not: it is a
      // per-deployment setting (`audit.retention.law` interpolates `{{years}}`)
      // and nothing serves it to the portal, so printing *seven years* here
      // would be this screen making a promise about how long a utility keeps
      // its records — the same family of fault as `Came back to us on .` two
      // hundred lines below, and a worse one because a customer would act on
      // it. The other half of `CPB-15` is reported, not invented.
      rollup={
        // ⚠ **THE SERVER'S `count`, NOT `rows.length`** — *6 documents* is
        // the whole set and a page would read *50 documents* on page 1 of
        // eleven years (`DEF-NOT-5746`'s footer, one line up the page).
        answer === null || !populated ? undefined : (
          <span data-documents-count={answer.count}>
            {t("portal.documents.count", { count: answer.count })}
          </span>
        )
      }
      secondaryActions={
        <span data-documents-download="">
          {!anyKept ? (
            <HeldButton
              label={t("portal.documents.downloadYear")}
              reason={t("portal.documents.yearNothingKeptHeld")}
            />
          ) : (
            <ButtonAnchor
              variant="secondary"
              href={documentsBundleHref(tenant, props.accountId)}
              data-download="documents-year"
            >
              {t("portal.documents.downloadYear")}
            </ButtonAnchor>
          )}
        </span>
      }
    />
  );

  // ⚠ **FOUR BRANCHES, FOUR SENTENCES, ONE CARD — R-22 AS THE PO RULED IT**
  // (2026-09-11: *"differntiate it using text message"*). They were four
  // hand-rolled `Card`s each holding one grey `<p>`, so *reading*, *the queue
  // would not answer*, *nothing has been sent* and *the read failed* all drew
  // the same picture. `PortalState` keeps the one picture and puts the kind in
  // the DOM, which is the only way anything but a reader can tell them apart.
  const retry = {
    label: t("portal.state.tryAgain"),
    onClick: () => setAttempt((n: number) => n + 1),
    tone: "primary" as const,
    testKey: "retry",
  };
  if (failed) {
    return (
      <PortalScreen screen="CWP-031" head={head}>
        <PortalState
          kind="failed"
          testId="documents"
          sentence={t("portal.documents.couldNotRead")}
          // R-10 — the way out beside the message (PO 2026-09-11).
          waysOut={[retry, { label: t("portal.state.getHelp"), to: path("/help"), testKey: "help" }]}
        />
      </PortalScreen>
    );
  }
  if (answer === null) {
    return (
      <PortalScreen screen="CWP-031" head={head}>
        <PortalState kind="loading" testId="documents" sentence={t("portal.documents.reading")} />
      </PortalScreen>
    );
  }
  // `documents: null` WITH a reason — the queue could not be asked. A different
  // sentence from the empty state below, and the reason it is a different
  // branch rather than a shared one.
  //
  // ⚠ **IT IS A `failed` KIND AND NOT AN `empty` ONE, WHICH IS THE WHOLE POINT
  // OF KEEPING THE BRANCH.** Nothing is listed, so it LOOKS empty; what has
  // actually happened is that nobody could ask. Marking it `empty` would tell
  // a customer of eleven months that we never wrote to them.
  if (rows === null) {
    return (
      <PortalScreen screen="CWP-031" head={head}>
        <PortalState
          kind="failed"
          testId="documents"
          sentence={t("portal.documents.queueUnavailable")}
          waysOut={[retry]}
        >
          <span data-documents-unavailable="" />
        </PortalState>
      </PortalScreen>
    );
  }

  return (
    <PortalScreen screen="CWP-031" head={head}>
      <Card testId="documents">
        {!populated ? (
          // B14 rule 17 — a sentence naming what will fill the page, never a
          // table of dashes and never an empty `<tbody>`, which asserts
          // "nothing was ever filed".
          <PortalState kind="empty" sentence={t("portal.documents.none")}>
            <span data-documents-empty="" />
          </PortalState>
        ) : (
          <>
            {/* B14 rule 32 — said ONCE, above the rows. Repeating it per row
                would put the same caveat on the screen forty-one times. */}
            <p className="mt-2 text-body text-neutral-600" data-documents-caveat="">
              {t("portal.documents.sentNotDelivered")}
            </p>
            {/* ⚠ **AT 390 THIS WAS STILL A SIX-COLUMN TABLE — 507px of
                content inside a 316px column — AND ITS SIBLING LIST HAD
                ALREADY SOLVED IT.** `CWP-027` becomes a stack of cards below
                `md`; `CWP-031` kept the table and pushed `HOW`, `What we know`
                and both row controls off the right-hand edge behind a sideways
                scroll nobody told the customer about. The page body never
                moved, so every overflow check passed over it. The rule is the
                one the skill states in capitals: **a table does not become a
                small table** — either cards or its own scroller — and cards is
                what the drawing's own phone frame draws (*August bill / Aug 5,
                2026 · PDF / ↓*).
                ⚠ **ONE SOURCE FOR BOTH HALVES.** Both render `rows`, so they
                cannot drift; what the phone drops is the toolbar and the
                sort headers, exactly as the drawing's phone frame does. */}
            <div className="mt-3 flex flex-col gap-3 md:hidden" data-documents-cards="">
              {rows.map((row) => (
                <DocumentCard
                  key={row.reference ?? `${row.queued_on ?? "?"}-${rows.indexOf(row)}`}
                  row={row}
                  tenant={tenant}
                />
              ))}
            </div>
            <div className="mt-3 max-md:hidden">
              <PortalListTable<PortalDocument>
                screen="CWP-031"
                caption={t("portal.documents.caption")}
                rows={rows}
                // ⚠ NOT a database id — the body carries none (B14 rule 31).
                // The reference where there is one, the queue stamp where there
                // is not; a React key is not a value a person reads.
                rowKey={(row) => row.reference ?? `${row.queued_on ?? "?"}-${rows.indexOf(row)}`}
                empty={
                  <p className="mt-2 text-body text-neutral-600" data-documents-empty="">
                    {t("portal.documents.none")}
                  </p>
                }
                noMatch={
                  <span data-documents-filter-empty="">{t("portal.documents.noneInFilter")}</span>
                }
                /* ⚠ **THE SEARCH AND THE THREE CHIPS ARE THE SERVER'S NOW
                   (`DEF-CWP-5747`).** The browser predicate matched the
                   reference, the four dates, the composed row NAME, the GROUP
                   word and the KIND word — the last three of which are
                   catalogue words in the reader's own language, which a server
                   may not write in any of eleven (B14 rule 35). So the data
                   half is `apps/portal/selectors.DOCUMENT_SEARCH_FIELDS` and
                   the word half is `resolve` above, which turns *Bills* back
                   into `f.group=bill`. `DEF-CWP-3969`'s lesson is kept: what
                   the reader can SEE is what a search looks at. There is no
                   `match` to pass here — the predicate is the server's. */
                server={list.window({
                  total: answer.count,
                  page: answer.page,
                  per: answer.per as PageSize,
                  populated,
                  busy,
                  search: { placeholder: t("portal.documents.search") },
                  chips: {
                    name: "group",
                    label: t("portal.documents.filterLabel"),
                    options: [
                      { key: "bill", label: t("portal.documents.filterBills") },
                      { key: "receipt", label: t("portal.documents.filterReceipts") },
                      { key: "letter", label: t("portal.documents.filterLetters") },
                    ],
                  },
                })}
                icons={[
                  {
                    key: "view",
                    icon: <EyeIcon />,
                    // ⚠ **ONLY A BILL HAS A SCREEN TO OPEN.** `CWP-029` draws
                    // the bill as it was printed and is addressed by the number
                    // on the paper. A receipt or a letter has no such screen,
                    // and `BR-CWP-045` means nothing here re-renders one — so
                    // this icon is ABSENT on those rows and the one beside it
                    // hands over the file itself. It used to be present and
                    // permanently refused, which is a control that has never
                    // once been usable.
                    absent: (row) => row.group !== "bill",
                    // DEF-CWP-10566: every row's icon was named alike; the name now carries the row's number.
                    label: (row) => rowActionName(t("portal.documents.viewRow"), row.reference, t),
                    to: (row) => path(`/bills/${encodeURIComponent(row.reference ?? "")}/document`),
                    reason: (row) =>
                      row.reference !== null && row.stored_document.available
                        ? null
                        : t("portal.documents.cannotOpen"),
                  },
                  {
                    // ⚠ **`CR-085` `CPB-14` — THE COPY ITSELF, FOR EVERY KIND
                    // OF DOCUMENT AND NOT ONLY FOR A BILL** (`DEF-CWP-4697`). Until this row
                    // existed, `CWP-031` listed a customer's receipts and
                    // letters, named them, dated them, said which way they went
                    // — and refused to hand any of them over with the sentence
                    // *"We kept no copy of this."*, which is FALSE about every
                    // one whose copy we did keep. The list has been the
                    // register of what we sent since `US-CWP-036`; it is now
                    // also the way to get it.
                    key: "copy",
                    icon: <DownloadIcon />,
                    label: (row) => rowActionName(t("portal.documents.downloadRow"), row.reference, t),
                    // ⚠ **THE ADDRESS CARRIES THE NUMBER ON THE PAPER** (B14
                    // rule 31) — which is also the honest limit of this
                    // control: a letter that minted no number cannot be
                    // addressed one at a time, and the refusal SAYS where to
                    // get it instead rather than pretending nothing exists.
                    href: (row) =>
                      row.reference === null
                        ? null
                        : documentFileHref(tenant, row.reference),
                    reason: (row) =>
                      !row.stored_document.available
                        ? t("portal.documents.cannotOpen")
                        : row.reference === null
                          ? t("portal.documents.takeItInTheYear")
                          : null,
                  },
                ]}
                columns={[
                  {
                    key: "document",
                    label: t("portal.documents.colDocument"),
                    sortable: true,
                    sortValue: (row) => row.reference,
                    cell: (row) => <DocumentCell row={row} />,
                  },
                  {
                    key: "kind",
                    label: t("portal.documents.colKind"),
                    sortable: true,
                    sortValue: (row) => t(`portal.documents.group.${row.group}`),
                    // The KIND column is the three words the filter uses —
                    // Bill · Receipt · Letter — which is what J36 step 10 and
                    // J47 step 4 both draw.
                    cell: (row) => t(`portal.documents.group.${row.group}`),
                  },
                  {
                    key: "sent",
                    label: t("portal.documents.colSent"),
                    sortable: true,
                    sortValue: (row) => row.sent_on ?? row.queued_on,
                    // The DATE is the day the document was made and queued.
                    // `sent_on` is the dispatcher's stamp and is null on
                    // everything this deployment has written, so the column
                    // shows what it actually knows and the state beside it is
                    // what stops that reading as an arrival.
                    cell: (row) => asDate(row.sent_on ?? row.queued_on) || "—",
                  },
                  // ⚠ **FOUR COLUMNS — `DOCUMENT · KIND · SENT · HOW` — PO
                  // RULING 2026-09-11.** The 8 September blueprint is the
                  // design and the 3 September wireframe images are superseded,
                  // so every drawing-versus-drawing disagreement on this screen
                  // decides the same way. The build had six: these four plus
                  // *What we know* and the row actions. The actions stay (the
                  // drawing ends every row `↓ PDF`); the fifth column's chip
                  // moved into this cell, beside the routes it is derived from.
                  {
                    key: "how",
                    label: t("portal.documents.colHow"),
                    cell: (row) => <Routes routes={row.routes} state={row.state} />,
                  },
                ]}
              />
            </div>
            {/* ⚠ **THIS NOTE SAID THE OPPOSITE OF THE TRUTH AND IS CORRECTED
                RATHER THAN DELETED** (`CR-085` `CPB-15`). It read: *"no portal
                route serves one: the two document routes that exist are
                staff-only"*. `US-CWP-034` shipped `bill_document_pdf` on the
                portal edge, behind the portal session and the `download`
                permission, and this sentence was left standing over it — so a
                lane reading the file was told the capability did not exist.
                `US-CWP-036` TC-7's *Download a year* is live above; the row
                control beside each document is `CPB-14`. Both serve the frozen
                artefact and neither renders anything (`BR-CWP-045`). */}
          </>
        )}
      </Card>
    </PortalScreen>
  );
}

/** The document's own name, and under it the reference a person can quote.
 *
 * ⚠ **NO ID AND NO PART OF ONE** (B14 rule 31; `DEF-3158` is the staff bills
 * list doing `row.invoice_no ?? row.id.slice(0, 8)` and shipping eight
 * characters of a uuid as link text). Where no human number was minted the row
 * says so in words, which is rule 31's own answer for that case.
 */
/**
 * **THE ROW'S OWN NAME** — `DEF-CWP-3969`.
 *
 * ⚠ **IT NAMED ITS KIND, AND A KIND IS SHARED BY EVERY ROW THAT HAS IT.** This
 * cell rendered `portal.documents.kind.<kind>`, so five of the six rows on the
 * live screen read *A letter from us* — identically — and the **kind is also
 * its own column**, so the same word appeared twice on every row. A list whose
 * entire purpose is finding a document could not be used to find one, and no
 * test could see it: the key resolves, the catalogue has it, `tsc` is clean,
 * and an assertion that the row renders its kind label passes exactly as
 * written.
 *
 * ⚠ **A DOCUMENT IS NAMED BY WHAT DISTINGUISHES IT FROM ITS NEIGHBOURS.** For
 * a bill that is the period it covers; for a receipt, the amount it is for.
 * Both come down as FACTS and the sentence is assembled from the catalogue
 * (B14 rule 35) — a server composing *"Bill for August"* would be composing it
 * in English on a screen that renders in eleven languages.
 *
 * ⚠ **THE FALLBACK IS THE KIND WORD, AND IT IS STILL THE HONEST ANSWER.** A
 * letter has no period and no amount, so *Your payment plan agreement* or
 * *A letter from us* is the most this product can truthfully call it — and an
 * unruled class still falls to `unknown` rather than to the nearest kind,
 * because naming it would decide `OQ-1164` from a screen.
 *
 * ⚠ **THE PERIOD IS DRAWN THROUGH THE TENANT'S OWN DATE FORMAT** and not as a
 * month name: the product has one date formatter (`BR-SHL-023`) and it has no
 * month-only mode. Inventing one here would be the second formatter that
 * `regional.tsx` exists to prevent.
 */
function documentName(
  t: (key: string, options?: Record<string, unknown>) => string,
  asDate: (value: string | null | undefined) => string,
  row: PortalDocument,
): string {
  if (row.group === "bill" && row.period_start && row.period_end) {
    return t("portal.documents.name.billFor", {
      from: asDate(row.period_start),
      to: asDate(row.period_end),
    });
  }
  if (row.group === "receipt" && row.amount) {
    return t("portal.documents.name.receiptFor", {
      amount: formatMoney(row.amount, row.currency),
    });
  }
  return t(`portal.documents.kind.${row.kind ?? "unknown"}`, {
    // ⚠ A KIND `OQ-1164` HAS NOT RULED ON FALLS HERE, NOT ON THE NEAREST ONE.
    // *"A letter from us"* is true of anything; calling an unruled class a bill
    // would be this screen deciding a question the Product Owner has open.
    defaultValue: t("portal.documents.kind.unknown"),
  });
}

function DocumentCell(props: { row: PortalDocument }) {
  const { t } = useTranslation();
  const asDate = usePortalDate();
  const { row } = props;
  return (
    <span className="flex flex-col">
      <span className="font-semibold" data-document-name="">
        {documentName(t, asDate, row)}
      </span>
      <span className="text-base text-neutral-600" data-reference={row.reference ?? ""}>
        {row.reference ?? t("portal.documents.noReference")}
      </span>
      {row.stored_document.available ? null : (
        // `BR-CWP-056` again, at row level: the copy control is held with the
        // reason the store gave, never missing.
        <span className="text-base text-neutral-600" data-no-copy="">
          {t("portal.documents.noCopyKept")}
        </span>
      )}
    </span>
  );
}

/**
 * ONE DOCUMENT ON A PHONE — the drawing's phone frame, card for card.
 *
 * ⚠ **IT DRAWS THE SAME FOUR FACTS THE TABLE DRAWS** — what it is, what kind,
 * when it went, and by which route with its state — so a customer who reads
 * the list on a phone and again on a laptop is reading one screen. Anything
 * the table can show and this cannot is a column the phone silently loses,
 * which is `DEF-CWP-4864` on the sibling list and is the reason this exists.
 *
 * ⚠ **THE DOOR IS A WORD, NOT AN ICON.** The table's two row controls are
 * icons with `aria-label` and `title`; the blueprint's standard A says every
 * icon in the portal carries its word because *a phone has no hover*, and 390
 * is the width where that is literally true. The `Open` door is drawn only for
 * a bill — the only group with a screen of its own (`CWP-029`) — and the
 * download only where a copy was actually kept, with the reason in words where
 * it was not (`BR-CWP-056`: a control that may not be used is refused with its
 * reason, never hidden).
 */
function DocumentCard(props: { row: PortalDocument; tenant: string }) {
  const { t } = useTranslation();
  const asDate = usePortalDate();
  const path = usePortalPath();
  const { row } = props;
  const reference = row.reference ?? "";
  return (
    <div className="border border-neutral-200 p-3" data-document-card={reference}>
      <span className="text-h3 font-bold text-neutral-900">{documentName(t, asDate, row)}</span>
      <p className="text-base text-neutral-600">
        {t(`portal.documents.group.${row.group}`)}
        {reference === "" ? "" : ` · ${reference}`}
      </p>
      <p className="text-body text-neutral-700">{asDate(row.sent_on ?? row.queued_on) || "—"}</p>
      <div className="mt-2">
        <Routes routes={row.routes} state={row.state} />
      </div>
      <p className="mt-2 flex flex-wrap gap-4" data-document-card-doors={reference}>
        {row.group === "bill" && reference !== "" && row.stored_document.available ? (
          <Link
            to={path(`/bills/${encodeURIComponent(reference)}/document`)}
            className="text-body text-neutral-700 no-underline hover:underline"
            data-card-view={reference}
            aria-label={rowActionName(t("portal.documents.viewRow"), reference, t)}
          >
            {t("portal.documents.viewRow")}
          </Link>
        ) : null}
        {row.stored_document.available && reference !== "" ? (
          <a
            href={documentFileHref(props.tenant, reference)}
            className="text-body text-neutral-700 no-underline hover:underline"
            data-card-download={reference}
            aria-label={rowActionName(t("portal.documents.downloadRow"), reference, t)}
          >
            {t("portal.documents.downloadRow")}
          </a>
        ) : (
          <span className="text-base text-neutral-600" data-card-no-copy={reference}>
            {row.stored_document.available
              ? t("portal.documents.takeItInTheYear")
              : t("portal.documents.cannotOpen")}
          </span>
        )}
      </p>
    </div>
  );
}

/** *Post · Email* — **every route it went by** (`BR-CWP-083`, J47 step 4).
 *
 * ⚠ **A ROUTE THAT FAILED IS NAMED, NOT DROPPED.** A bill posted and emailed
 * where the email had no address must not read as though both went: the
 * channel is listed with its own state beside it, because `BR-BIL-036` makes
 * *"we hold no email address for you"* a normal fact worth telling somebody.
 */
function Routes(props: { routes: PortalDocumentRoute[]; state?: string }) {
  const { t } = useTranslation();
  const asDate = usePortalDate();
  return (
    <span className="flex flex-col gap-1" data-routes="">
      <span>
        {props.routes
          .map((route) =>
            t(`portal.documents.channel.${route.channel}`, { defaultValue: route.channel }),
          )
          .join(" · ")}
      </span>
      {/* ⚠ **THE DOCUMENT'S OWN STATE, FOLDED INTO THE *HOW* CELL — AND THIS
          IS THE FOUR-COLUMN RULING ARRIVING (PO 2026-09-11).** The blueprint
          draws `DOCUMENT · KIND · SENT · HOW`; the build had a fifth, `What we
          know`, holding this chip. Dropping the chip outright would have lost
          *Could not send* and *On hold*, which are facts a customer needs — so
          it moves rather than goes, and it moves HERE because this is where it
          was computed from: `_document_state(route_states)` in
          `notifications/correspondence_reads.py` derives the document's state
          from the states of exactly these routes. A rollup belongs beside the
          things it rolls up. */}
      {props.state === undefined ? null : (
        <StatusChip tone={TONE[props.state] ?? "neutral"} testKey={`route-state-${props.state}`}>
          {t(`portal.documents.state.${props.state}`)}
        </StatusChip>
      )}
      {props.routes
        .filter((route) => route.state === "could_not_send" || route.state === "held")
        .map((route) => (
          <span
            key={route.channel}
            className="text-base text-neutral-600"
            data-route-problem={route.channel}
          >
            {t(`portal.documents.routeState.${route.state}`, {
              channel: t(`portal.documents.channel.${route.channel}`, {
                defaultValue: route.channel,
              }),
            })}
          </span>
        ))}
      {/* ⚠ **THIS ROW CLAIMED A LETTER HAD BOUNCED, WITH NO DATE —
          `DEF-CWP-4860`.** Two faults, and only one of them needed a server to
          show it.
          **(a) The guard was `!== null` over a field typed `string | null`.**
          A key ABSENT from the JSON arrives as `undefined`, and `undefined !==
          null` is true — so a payload that simply omits `returned_on` renders
          *Came back to us on .* on every row: a statement that the post office
          returned the customer's bill, with the date blank. `tsc` cannot see
          it, because the TYPE says the key is there. **A truthiness test is
          what the fact actually needs** — a bounce is a DATE, and no date means
          no bounce.
          ⚠ **HONESTLY: the live server always sends the key** — the builder in
          `notifications/correspondence_reads.py` writes `returned_at … if …
          else None` — so (a) reproduced against a fixture rather than against
          the running stack, and it is fixed as hardening, not as a live bug.
          Said plainly because a finding that did not reproduce is worth more
          written down than quietly deleted.
          **(b) The date was interpolated RAW and that one IS live.** It read
          *Came back to us on 2026-08-14.* — an ISO string in the middle of an
          English sentence, on the same screen whose `SENT` column has gone
          through the tenant's own formatter since `DEF-CWP-3994`. The same
          file, two formats for one kind of fact. */}
      {props.routes
        .filter((route) => Boolean(route.returned_on))
        .map((route) => (
          <span
            key={`${route.channel}-back`}
            className="text-base text-neutral-600"
            data-route-returned={route.channel}
          >
            {t("portal.documents.cameBack", { date: asDate(route.returned_on) })}
          </span>
        ))}
    </span>
  );
}
