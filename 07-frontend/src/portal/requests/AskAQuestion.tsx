// ── Trace ──────────────────────────────────────────────
// Story:    US-CWP-066 (EP-CWP-11) — ask a question, attached to the bill it is
//           about. Screen: CWP-054 (blueprint `P40`)
// Rules:    BR-CWP-076 (the row carries channel `customer_portal`) ·
//           BR-CWP-093 (nothing empty ever appears — *might answer it now* is
//           ABSENT when nothing is published, never an empty panel) ·
//           BR-CWP-056 (a control that may not be used yet is disabled WITH its
//           reason) · B14 rule 31 · rule 21 · rule 32 · rule 33 · rule 36
// Open:     `CR-068` §2b — consumer upload is a SIGNED DEFERRAL (PO 2026-08-08,
//           `DF-4`), so the photo box renders HELD and there is no file input.
// Tests:    src/portal/requests/AskAQuestion.dom.test.tsx
// Impacts:  src/portal/api/portalClient.ts `askAQuestion`
// ───────────────────────────────────────────────────────
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { PageHeader } from "@/components/PageHeader";

import {
  ButtonRow,
  Card,
  CommitButton,
  ErrandLink,
  FormField,
  PhotoPicker,
  SectionTitle,
  SelectInput,
  TextInput,
  TwoCol,
  usePortalPath,
} from "../components/primitives";
// ⚠ **DATES GO THROUGH THE TENANT'S OWN FORMAT, NEVER STRAIGHT TO THE
// SCREEN** (`DEF-CWP-4204`). Pine Hill asks for `MM/DD/YYYY`; this screen
// printed the wire's `2026-09-06`. `usePortalDate` returns the server's
// string unchanged when a tenant has stated no format — declining to say
// is honest, inventing one for a utility in Berlin is what shipped a
// five-hour error. Wave M took this fix (`DEF-CWP-4138`) and wave L took
// it (`DEF-CWP-4178`); wave I's five screens were never moved.
import { usePortalDate } from "../components/regional";
import { getPortalCentres, getPortalFront, getPortalHelp } from "../api/guestClient";
import type { HelpAnswerSummary, PortalFront } from "../api/guestClient";
import { askAQuestion, getBills, type PortalBill } from "../api/portalClient";
import { Announced } from "../components/a11y";

/** What a question can be about. ⚠ **A FIXED LIST AND NOT THE UTILITY'S OWN,
 *  AND THE REASON IS A DEFECT RATHER THAN A CHOICE** (`DEF-CWP-3701`):
 *  `service_requests` has no `category` column and no category table, so there
 *  is nothing tenant-configurable to read. The chosen label travels in the
 *  clerk's sentence, exactly as `CWP-010`'s quick asks do. */
const TOPICS = ["a_bill", "a_reading", "my_details", "paying", "something_else"] as const;

/**
 * `CWP-054` — a question with the bill attached to it.
 *
 * ⚠ **ATTACHING IT IS THE WHOLE SCREEN** (`US-CWP-066` §1): *"a free-text
 * message with no context becomes a phone call anyway."* The bill number
 * travels with the question and lands in the first sentence a clerk reads.
 *
 * ⚠ **AND A QUESTION WITH NO BILL IS STILL A QUESTION** (TC-5). The dropdown's
 * first row is an explicit *not about one bill*; refusing to send without one
 * would push somebody to the telephone for not knowing which bill they meant.
 *
 * ⚠ **THE *MIGHT ANSWER IT NOW* PANEL IS ABSENT WHEN NOTHING IS PUBLISHED**
 * (`BR-CWP-093`, TC-3) — absent, not empty. A container with nothing in it is
 * the failure that rule is written against.
 *
 * ⚠ **THE PHOTO BOX IS HELD AND THERE IS NO `<input type="file">`** (`CR-068`
 * §2b, a signed deferral of 2026-08-08). A disabled file input is still a file
 * input; what renders is the control's SHAPE with its reason inside it, and the
 * server has no route to post a file to either.
 */
export function AskAQuestionView(props: { billNumber?: string | null }) {
  const { t } = useTranslation();
  const asDate = usePortalDate();
  const path = usePortalPath();
  const [topic, setTopic] = useState<string>(props.billNumber ? "a_bill" : "");
  const [bill, setBill] = useState<string>(props.billNumber ?? "");
  const [what, setWhat] = useState("");
  const [bills, setBills] = useState<PortalBill[]>([]);
  const [answers, setAnswers] = useState<HelpAnswerSummary[]>([]);
  const [front, setFront] = useState<PortalFront | null>(null);
  const [office, setOffice] = useState<string | null>(null);
  const [reference, setReference] = useState<string | null>(null);
  const [refused, setRefused] = useState<string | null>(null);
  const [working, setWorking] = useState(false);

  useEffect(() => {
    let live = true;
    // ⚠ **A PICKER WANTS THE WHOLE LIST, SO IT ASKS FOR IT (`DEF-CWP-5747`).**
    // `getBills` takes a page since 2026-09-19 and its default is fifty. This
    // is a `SelectInput` of *which bill is your question about* — there is no
    // footer a customer could press to reach a second page, so a default page
    // would silently hide every bill older than the fiftieth from somebody
    // asking a question about exactly that bill. It names the top of the IS-2
    // page-size vocabulary rather than accepting a page it cannot turn.
    void getBills({ per: 1000 })
      .then((answer) => live && setBills(answer.bills))
      .catch(() => undefined);
    void getPortalHelp(null)
      .then((answer) => live && setAnswers(answer.answers.slice(0, 3)))
      .catch(() => undefined);
    void getPortalFront()
      .then((answer) => live && setFront(answer))
      .catch(() => undefined);
    // ⚠ **THE OFFICE NUMBER IS A CENTRE'S, BECAUSE THAT IS WHERE IT LIVES.**
    // `PortalFront` carries the EMERGENCY number and no other; a second field
    // for the office would be a second place to keep one telephone number
    // (law 5). `HelpPage` already composes the pair this way.
    void getPortalCentres()
      .then((rows) => live && setOffice(rows.find((row) => row.phone)?.phone ?? null))
      .catch(() => undefined);
    return () => {
      live = false;
    };
  }, []);

  const ready = what.trim() !== "" && topic !== "";

  async function send() {
    setWorking(true);
    setRefused(null);
    try {
      const answer = await askAQuestion({
        topic: t(`portal.question.topic.${topic}`),
        what: what.trim(),
        bill_number: bill,
      });
      setReference(answer.reference);
    } catch {
      setRefused(t("portal.question.couldNotSend"));
    } finally {
      setWorking(false);
    }
  }

  // ⚠ `DEF-CWP-4000` — the shared `components/PageHeader.tsx`, never a second
  // one. This screen is NOT one of the four the drawing gives a step bar
  // instead of a head ({CWP-038, CWP-042, CWP-047, CWP-055}): it is a single
  // form on a page of its own, and the audit records it as missing its title.
  const head = <PageHeader kicker={t("portal.kicker.requests")} title={t("portal.question.title")} />;

  if (reference !== null) {
    return (
      <div data-screen="CWP-054">
        {head}
        <Card testId="question-sent">
          {/* F-02 / F-04: the confirmation takes focus; the reference is heard. */}
          <Announced tone="status" as="div" say={t("portal.question.sent", { reference })}>
            <SectionTitle>{t("portal.question.sentTitle")}</SectionTitle>
          </Announced>
          <p className="text-body text-neutral-800" data-reference={reference}>
            {t("portal.question.sent", { reference })}
          </p>
          <p className="text-body text-neutral-600">{t("portal.question.sentNote")}</p>
          <ButtonRow>
            <ErrandLink
              label={t("portal.question.track")}
              to={`/requests/${encodeURIComponent(reference)}`}
            />
          </ButtonRow>
        </Card>
      </div>
    );
  }

  return (
    <div data-screen="CWP-054">
      {head}
      <TwoCol
        main={
          <Card testId="question">
            <p className="text-body text-neutral-600">{t("portal.question.lead")}</p>
            <FormField id="question-topic" label={t("portal.question.topicLabel")} required>
              <SelectInput
                id="question-topic"
                value={topic}
                placeholder={t("portal.question.topicPlaceholder")}
                options={TOPICS.map((key) => ({
                  value: key,
                  label: t(`portal.question.topic.${key}`),
                }))}
                onChange={setTopic}
              />
            </FormField>
            <FormField
              id="question-bill"
              label={t("portal.question.billLabel")}
              helper={t("portal.question.billHelper")}
            >
              <SelectInput
                id="question-bill"
                value={bill}
                placeholder={t("portal.question.billPlaceholder")}
                options={bills
                  .filter((row) => row.number !== null)
                  .map((row) => ({
                    value: row.number as string,
                    // B14 rule 31 — the bill's own number, never a row id.
                    label: `${row.number as string} · ${row.issued_on ? asDate(row.issued_on) : ""}`,
                  }))}
                onChange={setBill}
              />
            </FormField>
            <FormField id="question-what" label={t("portal.question.whatLabel")} required>
              <TextInput id="question-what" multiline value={what} onChange={setWhat} />
            </FormField>
            {/* ⚠ HELD — a signed deferral, and there is NO file input here. */}
            <PhotoPicker reason={t("portal.question.photoHeld")} />
            <ButtonRow>
              <CommitButton
                label={t("portal.question.send")}
                working={working}
                ready={ready}
                reason={t("portal.question.sendHeld")}
                onClick={() => void send()}
              />
            </ButtonRow>
            {refused !== null ? (
              <Announced tone="error" className="text-body font-semibold text-danger-700" data-refused="">
                {refused}
              </Announced>
            ) : null}
          </Card>
        }
        rail={
          <>
            {/* `BR-CWP-093` — ABSENT when nothing is published, not empty. */}
            {answers.length > 0 ? (
              <Card testId="question-suggestions">
                <SectionTitle>{t("portal.question.mightAnswer")}</SectionTitle>
                <ul className="m-0 list-none p-0" data-suggestions={answers.length}>
                  {answers.map((row) => (
                    <li key={row.slug} className="border-b border-neutral-200 py-2">
                      <a
                        className="font-semibold text-accent-text no-underline hover:underline"
                        href={path(`/help/${row.slug}`)}
                        data-answer={row.slug}
                      >
                        {row.question}
                      </a>
                    </li>
                  ))}
                </ul>
              </Card>
            ) : null}
            {/* ⚠ **THE CARD IS ABSENT WHEN NEITHER NUMBER EXISTS, NOT
                EMPTY** (`BR-CWP-093`, `DEF-CWP-4854`). Both phone lines were
                correctly conditional and the BOX that holds them was not, so a
                utility that has published no telephone number at all drew a
                heading reading *Or ring us* with nothing under it — at both
                widths, on the live tenant. The file's own docstring states the
                rule about the suggestions panel one block above and this card
                is three lines below it, which is how it survived: the
                CONTAINER is the thing rule 093 is about and the conditional
                was one level too deep. */}
            {office !== null || front?.emergency_phone ? (
              <Card testId="question-or-ring">
                <SectionTitle>{t("portal.question.orRing")}</SectionTitle>
                {/* ⚠ TWO DIFFERENT NUMBERS, AND THE SCREEN SAYS WHICH IS
                    WHICH (`US-CWP-066` TC-8). Each is absent when the utility
                    has not given it, rather than drawn as a blank line. */}
                {office !== null ? (
                  <p className="text-body text-neutral-700" data-phone="office">
                    {t("portal.question.officePhone", { phone: office })}
                  </p>
                ) : null}
                {front?.emergency_phone ? (
                  <p className="text-body text-neutral-700" data-phone="emergency">
                    {t("portal.question.emergencyPhone", { phone: front.emergency_phone })}
                  </p>
                ) : null}
              </Card>
            ) : null}
          </>
        }
      />
    </div>
  );
}
