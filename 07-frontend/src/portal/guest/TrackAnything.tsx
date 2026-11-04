// ── Trace ──────────────────────────────────────────────
// Story:    US-CWP-010 (EP-CWP-03) — Track anything: progress, and never data.
//           Screens: CWP-012
// Rules:    B14 rule 36 (layout from `08-screen-layouts.md` CWP-012 and
//           `wireframes/CWP-012.png`; look from r10; compose the kit) ·
//           BR-CWP-024 (progress and never data) · BR-CWP-025 (a second fact
//           only the sender would know) · BR-CWP-023 (the lock's sentence
//           comes from the SERVER's message key — the screen invents none) ·
//           r10 rule 4 (`Verb →` advances) · rule 6 (nothing here is danger) ·
//           rule 10 · B14 rule 31 · rule 33
// Tests:    src/portal/guest/TrackAnything.test.tsx ·
//           src/portal/guest/TrackAnything.payment.dom.test.tsx (the payment
//           kind, added 2026-09-05 — a separate file for hard-won law 11's
//           reason: six lanes, one branch, and a new path collides with none)
// Impacts:  06-backend/apps/portal/guest_api.track ·
//           06-backend/apps/portal/selectors.payment_progress_view
// ───────────────────────────────────────────────────────
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { PageHeader } from "@/components/PageHeader";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { refusalText } from "@/api/refusalText";

import { Panel } from "@/components/Panel";

import type { ProblemKind, TrackView } from "../api/guestClient";
import { postTrack } from "../api/guestClient";
import { Announced, PortalRefusal } from "../components/a11y";
import { usePortalDate } from "../components/regional";
import {
  ButtonRow,
  Card,
  CommitButton,
  FormField,
  KVList,
  StatusChip,
  TextInput,
  TwoCol,
} from "../components/primitives";

import { KIND_COPY } from "./ReportProblem";
import { TrackAddDocument } from "./TrackAddDocument";

/** The three interruption statuses and the tone each carries (inventory §4). */
const REPORT_STATUS: Record<string, { key: string; tone: "warning" | "neutral" | "success" }> = {
  looking_into_it: { key: "portal.status.looking_into_it", tone: "warning" },
  // ⚠ **`crew_on_site` IS `warning`, NOT `danger`, AND THAT IS r10 RULE 6 READ
  // ONE STEP FURTHER.** The component inventory puts CREW ON SITE in the brand
  // tone with OVERDUE and BOUNCED; rule 6 keeps the loudest colour of the
  // product for a destructive commit, and a crew arriving to fix your water is
  // the best news on this screen. `StatusChip`'s three tones are the kit's,
  // and this is the one that carries "something is happening".
  crew_on_site: { key: "portal.status.crew_on_site", tone: "warning" },
  resolved: { key: "portal.status.resolved", tone: "success" },
};

/** The customer words a tracked payment can carry (`selectors.PAYMENT_PROGRESS_WORDS`). */
const PAYMENT_WORDS: ReadonlySet<string> = new Set([
  "received",
  "processing",
  "failed",
  "cancelled",
  "unknown",
]);

/**
 * The words for a status, whichever series it came from.
 *
 * ⚠ A REQUEST'S STATE REUSES THE STAFF CATALOGUE — `customers.serviceRequest.
 * state.*` already exists in all eleven catalogues and already says *Submitted*
 * and *Under review* in each. A second set of eleven translations for the same
 * eleven words would be two vocabularies for one lifecycle.
 */
export function statusKey(view: TrackView): string {
  if (view.series === "report") {
    return REPORT_STATUS[view.status]?.key ?? "portal.status.looking_into_it";
  }
  // ⚠ A PAYMENT REUSES THE PORTAL'S OWN MONEY WORDS (`portal.money.state.*`),
  // the same chip the signed-in money list draws, for the reason given just
  // above about a request. **AMENDED 2026-10-21 (`DEF-CWP-10341`)**: this read
  // the STAFF words (`payments.status.*`) until then, and the server folded
  // `posted` into *Cleared* — a claim about bank reconciliation a posted
  // payment cannot make — and sent nothing for `cancelled`, which then read
  // *Processing*. The server now sends one of five (`selectors.
  // PAYMENT_PROGRESS_WORDS`); anything else draws *Status unavailable* here
  // rather than a raw key.
  if (view.series === "payment") {
    const word = PAYMENT_WORDS.has(view.status) ? view.status : "unknown";
    return `portal.money.state.${word}`;
  }
  return `customers.serviceRequest.state.${view.status}`;
}

export function statusTone(view: TrackView): "warning" | "success" | "neutral" {
  return view.series === "report" ? (REPORT_STATUS[view.status]?.tone ?? "warning") : "neutral";
}

export function TrackAnything(props: { client?: ApiClient }) {
  const { t } = useTranslation();
  //: ⚠ **THE ONE DATE PATH ON THIS SCREEN** (`BR-SHL-023`, `DEF-CWP-4197`).
  //: `reportedAtText` — the browser's locale and the browser's ZONE — used to
  //: draw the *Reported* row here and was five hours out for a Texas utility;
  //: it now draws nothing on this screen and lives on `CWP-007`, which is a
  //: separate fix. `withTime` for an instant, plain for a date: a date put
  //: through the instant path acquires a `12:00 AM` nobody stated.
  const asDate = usePortalDate();
  const client = props.client ?? api;
  const [reference, setReference] = useState("");
  const [secondFact, setSecondFact] = useState("");
  const [working, setWorking] = useState(false);
  const [refusal, setRefusal] = useState<string | null>(null);
  const [found, setFound] = useState<TrackView | null>(null);
  // `DEF-CWP-9049` — the pair that FOUND the request, kept as found: the
  // add-a-document door proves them again, and a box edited after the lookup
  // must not send a file under a pair nobody checked.
  const [proved, setProved] = useState<{ reference: string; secondFact: string } | null>(null);

  const ready = reference.trim() !== "" && secondFact.trim() !== "";

  async function look() {
    setWorking(true);
    setRefusal(null);
    setFound(null);
    try {
      setFound(await postTrack(reference.trim(), secondFact.trim(), client));
      setProved({ reference: reference.trim(), secondFact: secondFact.trim() });
    } catch (error) {
      // ⚠ THE WORDS ARE THE SERVER'S. *Not found* and *locked* are two
      // different refusals and this screen must not decide which; the message
      // key decides, and both are five or six words in eleven catalogues.
      setRefusal(refusalText(t, error));
    } finally {
      setWorking(false);
    }
  }

  return (
    <div data-screen="CWP-012">
      {/* ⚠ **THIS WAS A FOURTH PAGE HEAD, HAND-ROLLED INSIDE THE CARD**
          (`DEF-CWP-4000`): a `SectionTitle` standing in for the kicker, an
          `<h2>` standing in for the title, and a grey lead — the exact three
          pieces `components/PageHeader.tsx` draws, in a screen that never
          composed it. So the page had no `<h1>` at all, which is what the
          audit measured, and the portal had one more spelling of a head than
          it has heads. `DEF-CWP-3655` deleted the last one of these; this is
          the same move, one screen further on. */}
      <PageHeader
        kicker={t("portal.track.kicker")}
        title={t("portal.track.title")}
        rollup={t("portal.track.lead")}
      />
      <TwoCol
        main={
          <>
            <Card testId="cwp012-form">
              {/* ⚠ **`gap-5` — B14 rule 39's *field → field 20px*
                (`DEF-CWP-4856`).** Both fields were direct children of `Card`,
                whose gap is the scale's BLOCK step (16). Measured at 390 and
                1280 before the change: reference → second fact was **16**
                against the reference's own 6px helper, so the helper sat
                almost exactly between the input above it and the label below —
                which is the failure rule 39's anatomy clause describes in
                words. `Card` is the kit's and is not moved for one screen; the
                field stack gets the field figure. */}
              <div className="flex flex-col gap-5">
                <FormField
                  id="cwp012-reference"
                  label={t("portal.track.reference")}
                  helper={t("portal.track.referenceHelp")}
                  required
                >
                  <TextInput id="cwp012-reference" value={reference} onChange={setReference} />
                </FormField>
                <FormField id="cwp012-second-fact" label={t("portal.track.secondFact")} required>
                  <TextInput id="cwp012-second-fact" value={secondFact} onChange={setSecondFact} />
                </FormField>
              </div>
              {refusal !== null ? <PortalRefusal>{refusal}</PortalRefusal> : null}
              <ButtonRow>
                <CommitButton
                  label={t("portal.track.lookItUp")}
                  working={working}
                  ready={ready}
                  reason={t("portal.track.notReady")}
                  onClick={() => void look()}
                />
              </ButtonRow>
            </Card>
            {found !== null && proved !== null ? (
              <TrackAddDocument
                key={`${proved.reference}|${proved.secondFact}`}
                reference={proved.reference}
                secondFact={proved.secondFact}
                view={found}
                onView={setFound}
                client={client}
              />
            ) : null}
          </>
        }
        rail={
          <Panel
            as="aside"
            title={found === null ? t("portal.track.panelTitle") : t("portal.track.foundTitle")}
          >
            {found === null ? (
              <p className="m-0">{t("portal.track.panelNote")}</p>
            ) : (
              // F-02 / F-04: the answer takes focus and its heading is heard.
              <Announced tone="status" as="div" say={t("portal.track.foundTitle")}>
                <KVList
                  rows={[
                    {
                      key: "reference",
                      label: t("portal.track.reference"),
                      value: <span data-reference="">{found.reference}</span>,
                    },
                    ...(found.kind !== undefined
                      ? [
                          {
                            key: "what",
                            label: t("portal.track.what"),
                            value: `${t(KIND_COPY[found.kind as ProblemKind].label)}${
                              found.location_text === undefined ? "" : `, ${found.location_text}`
                            }`,
                          },
                        ]
                      : []),
                    {
                      key: "reported",
                      // ⚠ *Reported* is right for a report and for a request
                      // and is simply wrong for a payment — nobody REPORTS
                      // one. Both words already exist in eleven catalogues, so
                      // this costs no translation (B14 rule 35).
                      label:
                        found.series === "payment"
                          ? t("portal.quickPay.paidAt")
                          : t("portal.track.reported"),
                      // ⚠ **THIS READ `reportedAtText` UNTIL `CR-085`
                      // (2026-09-08) AND IT WAS `DEF-CWP-4197` STILL SITTING
                      // HERE.** That helper formats in the BROWSER's locale and
                      // in the BROWSER's zone, so a report made at 9:52am in
                      // Texas rendered *Sep 2, 2026, 2:52 PM* — five hours out,
                      // on the one line telling somebody when they rang. The
                      // receipt screen was fixed for exactly this a fortnight
                      // ago; the same fault was one directory away.
                      //
                      // ⚠ It also made the panel print two date formats side by
                      // side once the rows below it landed, which is how it was
                      // noticed at all: seen by looking (hard-won law 6).
                      // `usePortalDate` is the product's one path (`BR-SHL-023`)
                      // and is what `/pay/check` and `/pay/done` already use.
                      value: found.reported_at === null ? "—" : asDate(found.reported_at, true),
                    },
                    {
                      key: "now",
                      label: t("portal.track.now"),
                      value: (
                        <StatusChip tone={statusTone(found)}>{t(statusKey(found))}</StatusChip>
                      ),
                    },
                    // ⚠ **THE THREE DATES THE SERVER HAS ALWAYS SENT AND THIS
                    // SCREEN THREW AWAY** (`CR-085`, 2026-09-08). The drawing
                    // names the first of them as the whole point of the screen:
                    // *"The status has a time attached — 'expected fixed today,
                    // by 4 PM' — because 'in progress' with no date is what
                    // makes somebody phone."* `report_progress_view` returns
                    // `expected_back_on` and `resolved_at` on every report and
                    // `payment_progress_view` returns `cleared_at`; all three
                    // were typed on `TrackView`, none was drawn. That is
                    // hard-won law 2 read the other way round — not a control
                    // with nothing behind it, but a FACT with no control in
                    // front of it — and nothing in this repo can see it: the
                    // field is on the payload, the type compiles, and every
                    // assertion about what is on the panel passes because they
                    // all name rows that ARE there.
                    //
                    // ⚠ **EACH IS ABSENT RATHER THAN DASHED WHEN IT IS NOT
                    // KNOWN.** A row reading *Expected fixed —* tells somebody
                    // an estimate exists and has been withheld; no row says the
                    // true thing, which is that nobody has set one yet.
                    ...(found.expected_back_on
                      ? [
                          {
                            key: "expected",
                            label: t("portal.track.expectedFixed"),
                            value: (
                              <span data-expected-fixed="">{asDate(found.expected_back_on)}</span>
                            ),
                          },
                        ]
                      : []),
                    ...(found.resolved_at
                      ? [
                          {
                            key: "fixed",
                            label: t("portal.track.fixed"),
                            value: <span data-fixed="">{asDate(found.resolved_at, true)}</span>,
                          },
                        ]
                      : []),
                    // ⚠ A STAFF KEY, DELIBERATELY, AND THE ROWS ABOVE ALREADY
                    // DO THIS TWICE: `payments.col.clearedAt` is *Cleared* in
                    // all eleven catalogues today, so reusing it costs no
                    // translation and invents no twelfth word for a thing this
                    // product already names (B14 rule 35).
                    ...(found.cleared_at
                      ? [
                          {
                            key: "cleared",
                            label: t("payments.col.clearedAt"),
                            value: <span data-cleared="">{asDate(found.cleared_at, true)}</span>,
                          },
                        ]
                      : []),
                  ]}
                />
                <p className="mt-3 border-t border-neutral-200 pt-3 text-body text-neutral-600">
                  {t("portal.track.panelNote")}
                </p>
              </Announced>
            )}
          </Panel>
        }
      />
    </div>
  );
}
