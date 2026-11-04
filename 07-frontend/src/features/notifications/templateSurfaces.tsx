// ── Trace ──────────────────────────────────────────────
// Change:  SET-10's FIVE DOCUMENT SHAPES, from the wireframes and the written
//          specification the Product Owner ratified on 2026-09-07. The
//          governing sentence is theirs, verbatim: *"user does not udnerstand
//          so many option - you should show what customer is going to get -
//          rest is only for information"*. The document IS the screen;
//          everything else is a caption.
// Screens: SET-10 (Settings → Configure → Templates → one template)
// Rules:   B14 rule 21 (utilities only in a file on `route-b-migrated.txt` —
//          this file is listed) · rule 31 (no database id is ever the visible
//          value of a field) · rule 32 (one sentence per section) · rule 33 (a
//          refusal caps at five or six words) · rule 35 (a catalogue is written
//          in its own language) · BR-SHL-020 (an absent fact is NAMED, never
//          faked and never blank) · CLAUDE.md hard-won law 2 (built is not
//          wired) · law 6 (no gate reads rendered output)
// Defects: DEF-NOT-4464 (an email printed its first body line twice) and
//          DEF-NOT-4465 (an email previewed as a text blob) were both closed in
//          `TemplateDetail.tsx` by a sibling lane before this file existed;
//          this file is why they cannot come back — see EmailSurface.
// ───────────────────────────────────────────────────────
/**
 * THE FIVE SHAPES A TEMPLATE IS DRAWN AS, each in its own renderer.
 *
 * Before this file there were TWO drawings for five shapes: `printable` and
 * `contract` rendered as a page, `email` as a framed page, and SMS and in-app
 * shared one bordered box with a phone's measure. So *"what does the customer
 * actually get"* — the only question this screen exists to answer — had no
 * answer at all for three of the five, and a clerk comparing a text message
 * with a letter was comparing two views of the same box.
 *
 * ⚠ **WHY THE RENDERERS LEFT `TemplateDetail.tsx`.** They are the part of that
 * file with no state, no fetching and no routing: given a rendered body and the
 * server's sample rows they return a drawing, which makes them the part that
 * can be tested by rendering rather than by mounting a screen. Splitting them
 * out is also what let a second lane build three of the five while the first
 * was still in the screen file — two lanes in one file is the revert-by-
 * subtraction shape hard-won law 11 is about.
 *
 * ⚠ **EVERY STRING DRAWN HERE CAME OFF THE WIRE.** Nothing is composed,
 * defaulted or guessed. The one thing this file adds to the server's words is
 * TYPOGRAPHY — where a line sits, how wide it is, what weight it carries.
 * That distinction is the whole of why a preview can be trusted.
 *
 * ⚠ **AND THE PO'S FIFTH SHAPE IS THE ONE WITH A DIFFERENT READER.**
 * `staff_bulk_summary` is the product speaking to a CLERK; every other class in
 * the catalogue is the utility speaking to a customer. The screen says so out
 * loud (`InAppSurface`) rather than leaving it to be assumed from the absence
 * of a letterhead, and it carries NO *Send test to me* — see that component's
 * own note for why the control is ABSENT rather than disabled.
 */
import { Fragment } from "react";
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";

import type { TemplateDetail, TemplatePreview } from "@/api/endpoints";

import {
  DOC_CARD,
  DOC_GAP,
  DOC_HEADING,
  DOC_MASTHEAD,
  DOC_PAIR,
  DOC_PAIR_VALUE,
  DOC_RULE,
  DOC_TEXT,
  HEAD_META_ABSENT,
  INBOX_LINES,
  SMS_METER_WARN,
} from "./notificationsKit";
import {
  APP_AUDIENCE,
  APP_BANNER,
  APP_SKETCH,
  APP_SKETCH_BAR,
  APP_SKETCH_BAR_SHORT,
  APP_SKETCH_ROWS,
  INBOX_META,
  INBOX_META_LABEL,
  INBOX_META_ROW,
  INBOX_META_VALUE,
  SIGN_BLOCK,
  SIGN_FIELD,
  SIGN_INK,
  SIGN_LABEL,
  SIGN_RULE,
  SMS_PHONE_BUBBLE,
  SMS_PHONE_METER,
} from "./templateSurfacesKit";
import { smsCost } from "./smsSegments";
import { documentBlocks, documentSamples } from "./templateDocument";
import type { DocBlock } from "./templateDocument";

/* ══ 1 · THE PRINTED PAGE ══════════════════════════════════════════════════ */

/**
 * CR-076 addendum — THE PAPER. The design's *"white document card … showing the
 * real rendered document, not a text blob"*.
 *
 * ⚠ **WHAT IS DRAWN HERE IS THE SERVER'S STRING AND NOTHING ELSE.** Every
 * figure, name, address and amount on this page came out of `POST …/preview`
 * for THIS template. Nothing is composed and nothing is defaulted.
 *
 * ⚠ **THE SHAPE COMES FROM THE BODY, NOT FROM A SCHEMA.** There is no
 * line-item array on the wire; `documentBlocks` reads the shape the AUTHOR gave
 * their own wording and gives each part its typography. Its module header
 * states exactly what it will and will not recognise — read that before
 * changing anything here.
 *
 * ⚠ **`whitespace-pre-wrap` LIVES ON THE PROSE BLOCKS, NOT ON THE CARD.** A
 * page that declares it wholesale cannot right-align anything: the newline
 * between a label and the next line would be preserved inside a flex row.
 *
 * `renderBlock` is how `ContractSurface` puts a signature block where the
 * author's own signature line falls, WITHOUT this component learning what a
 * contract is. Return `undefined` and the default drawing is used.
 */
export function DocumentPaper(props: {
  body: string;
  rows: TemplateDetail["merge_field_rows"];
  renderBlock?: (block: DocBlock, index: number) => ReactNode | undefined;
}) {
  const blocks = documentBlocks(props.body, documentSamples(props.rows));
  return (
    <div className={DOC_CARD} data-testid="preview-page">
      {blocks.map((block, index) => {
        const key = `${index}:${block.kind}`;
        const override = props.renderBlock?.(block, index);
        if (override !== undefined) {
          return <Fragment key={key}>{override}</Fragment>;
        }
        if (block.kind === "blank") {
          return <div key={key} className={DOC_GAP} aria-hidden="true" />;
        }
        if (block.kind === "masthead") {
          return (
            <p key={key} className={DOC_MASTHEAD} data-testid="preview-letterhead">
              {block.text}
            </p>
          );
        }
        if (block.kind === "rule") {
          // The design's accent rule under the letterhead. `aria-hidden`
          // because it is the PAGE's furniture, not a thematic break in the
          // document a screen reader should announce.
          return (
            <div key={key} className={DOC_RULE} data-testid="preview-rule" aria-hidden="true" />
          );
        }
        if (block.kind === "heading") {
          return (
            <p key={key} className={DOC_HEADING} data-doc-heading>
              {block.text}
            </p>
          );
        }
        if (block.kind === "pair") {
          return (
            <p key={key} className={DOC_PAIR} data-doc-pair>
              <span>{block.text}</span>
              <span className={DOC_PAIR_VALUE}>{block.value}</span>
            </p>
          );
        }
        return (
          <p key={key} className={DOC_TEXT}>
            {block.text}
          </p>
        );
      })}
    </div>
  );
}

/**
 * `printable` and the NULL group — a page, rendered as a page.
 *
 * There is deliberately no component of its own: a printed notice IS the paper
 * and nothing else. Named so the switch below reads as five shapes rather than
 * four and a special case.
 */
export function PrintedPageSurface(props: { preview: TemplatePreview; data: TemplateDetail }) {
  return <DocumentPaper body={props.preview.body} rows={props.data.merge_field_rows} />;
}

/* ══ 2 · THE EMAIL ═════════════════════════════════════════════════════════ */

/** The value a `From:` line shows, or the STATED absence in its place.
 *
 *  ⚠ **BR-SHL-020, AND THE PRECEDENT IS ALREADY ON THIS SCREEN.** The five
 *  BR-TEN-017 identity tokens — `utility_name` among them — are stamped from
 *  Settings → Company at render and are deliberately unsampled, so a fresh
 *  tenant HAS no utility name to show here. Inventing a plausible one would be
 *  the exact failure the support-phone em-dash exists to avoid: a preview that
 *  looks complete over a profile that is not. The em-dash is the same mark the
 *  head's meta line uses, and the server's own sentence is on hover.
 */
function senderOf(
  rows: TemplateDetail["merge_field_rows"],
): { value: string } | { absent: string } {
  const row = rows.find((candidate) => candidate.token === "utility_name");
  if (row === undefined) return { absent: "" };
  if (row.sample_value !== null && row.sample_value !== "") return { value: row.sample_value };
  return { absent: row.sample_unavailable ?? "" };
}

/**
 * An INBOX MESSAGE: the subject in bold, who it is from and who it is going to
 * beneath, then the wording.
 *
 * ⚠ **NOT ONE LINE OF THE WORDING IS DRAWN TWICE, AND THAT IS `DEF-NOT-4464`
 * MADE STRUCTURALLY IMPOSSIBLE RATHER THAN MERELY FIXED.** The version the
 * Product Owner found drew `firstLine(preview.body)` as a stand-in preheader
 * and then the whole body underneath, so the first line appeared twice on every
 * one of the twenty email classes, with a sentence explaining our own database
 * — *"first line of the body — this product has no preheader field"* — between
 * the two copies. Both elements were correct in isolation and every DOM
 * assertion about each one passed; nothing in this repo reads rendered output,
 * so only a person looking at the screen could see it.
 * **The header above the rule is now built from FIELDS ONLY** — the subject,
 * the sender, the recipient — and the body appears once, below. There is no
 * expression in this component that reads a slice of `preview.body`, which is
 * the property a reviewer can check at a glance and the reason the defect
 * cannot return by a different route.
 *
 * ⚠ **AND NO CAPTION HERE EXPLAINS OUR SCHEMA TO A CLERK (B14 rule 32).** The
 * absent preheader is not mentioned, because a clerk has no preheader to fill
 * in and could do nothing about it if they had. What the screen owes them is
 * what the customer will see.
 *
 * ⚠ **THE BODY GOES THROUGH `DocumentPaper` — `DEF-NOT-4465`.** It was one
 * paragraph element carrying the raw string while printed notices got real
 * typography, so *"what does the customer receive"* looked completely different
 * depending on which template a clerk happened to open. Same renderer for every
 * surface that produces a document; what stays different is the FRAME, which is
 * what an inbox actually is.
 */
export function EmailSurface(props: { preview: TemplatePreview; data: TemplateDetail }) {
  const { t } = useTranslation();
  const sender = senderOf(props.data.merge_field_rows);
  const recipient = props.data.sample_identity.customer_name;
  return (
    <div data-testid="preview-inbox">
      <div className={INBOX_LINES}>
        <strong data-testid="preview-subject">
          {props.preview.subject ?? t("templates.detail.noSubject")}
        </strong>
        <div className={INBOX_META}>
          <p className={INBOX_META_ROW} data-testid="preview-email-from">
            <span className={INBOX_META_LABEL}>{t("templates.detail.emailFrom")}</span>
            {"value" in sender ? (
              <span className={INBOX_META_VALUE}>{sender.value}</span>
            ) : (
              // The em-dash the head's meta line uses for a fact the server
              // does not hold, with the server's own sentence on hover. Never a
              // plausible stand-in.
              <span
                className={`${INBOX_META_VALUE} ${HEAD_META_ABSENT}`}
                data-testid="preview-email-from-absent"
                title={sender.absent}
                aria-description={sender.absent}
              >
                {"—"}
              </span>
            )}
          </p>
          <p className={INBOX_META_ROW} data-testid="preview-email-to">
            <span className={INBOX_META_LABEL}>{t("templates.detail.emailTo")}</span>
            {recipient === null ? (
              <span
                className={`${INBOX_META_VALUE} ${HEAD_META_ABSENT}`}
                data-testid="preview-email-to-absent"
              >
                {"—"}
              </span>
            ) : (
              <span className={INBOX_META_VALUE}>{recipient}</span>
            )}
          </p>
        </div>
      </div>
      <DocumentPaper body={props.preview.body} rows={props.data.merge_field_rows} />
    </div>
  );
}

/* ══ 3 · THE TEXT MESSAGE ══════════════════════════════════════════════════ */

/**
 * A BUBBLE AT PHONE WIDTH, WITH WHAT IT COSTS UNDERNEATH.
 *
 * ⚠ **THE COUNT IS PART OF THE DOCUMENT NOW, AND THAT IS THE CHANGE.** It used
 * to be `SmsMeter` inside the composer, so the only way to learn that a body had
 * become three messages was to press *Edit wording* — and the person who most
 * needs to know is the one reading the preview and deciding whether to send it.
 * 160 characters is one message; a wording that silently becomes three triples
 * a utility's bill for that run, and on a 2,000-account send that is real money.
 *
 * ⚠ **IT IS MOVED, NOT COPIED.** Two live counts that can disagree is worse
 * than one in the wrong place, and a duplicated count is also the repeated-text
 * defect this screen has already had once (`DEF-NOT-4464`).
 *
 * The arithmetic is `smsSegments.ts`'s and is not re-done here: the segment
 * size is SERVED (`sms_character_counter`), the count is `ceil(length / size)`,
 * and that module's header records why the GSM concatenation figure of 153 is
 * deliberately absent — no signed rule of this product states it.
 *
 * `rendered_length` is preferred over `body.length` because what is SENT is the
 * rendered message, not the wording with `{tokens}` still in it: a body of
 * `{first_name}` is twelve characters and sends as three.
 */
export function SmsSurface(props: { preview: TemplatePreview; data: TemplateDetail }) {
  const { t } = useTranslation();
  const length = props.preview.rendered_length;
  const cost = smsCost(length, props.data.sms_character_counter);
  return (
    <div data-testid="preview-sms">
      <p className={SMS_PHONE_BUBBLE} data-testid="preview-sms-bubble">
        {props.preview.body}
      </p>
      <p className={SMS_PHONE_METER} data-testid="preview-sms-count">
        <span data-testid="preview-sms-characters">
          {t("templates.detail.smsCounter", {
            count: cost.length,
            limit: props.data.sms_character_counter,
          })}
        </span>
        <span data-testid="preview-sms-messages">
          {t("templates.detail.smsSegments", { count: cost.segments })}
        </span>
        {/* Kept from the composer's meter rather than dropped: "how much room
            is left" is the fact that stops a body crossing the boundary in the
            first place, and removing it would also orphan a locale key that
            all eleven catalogues already carry in their own language. */}
        <span data-testid="preview-sms-remaining">
          {t("templates.detail.smsRemaining", { count: cost.remaining })}
        </span>
        {cost.overSegment && (
          <span className={SMS_METER_WARN} data-testid="preview-sms-cost">
            {t("templates.detail.smsCostWarning", { count: cost.segments })}
          </span>
        )}
      </p>
    </div>
  );
}

/* ══ 4 · THE DOCUMENT TO SIGN ══════════════════════════════════════════════ */

/** One field of a signature block: what the sample put on the line, and the
 *  author's own label under it. */
export interface SignatureField {
  readonly label: string;
  readonly ink: string;
}

/**
 * THE AUTHOR'S SIGNATURE LINE, READ AS FIELDS.
 *
 * All four contract bodies end with one line of the shape
 * `Customer signature: (signed electronically)          Date: 01/31/2026` —
 * two `label: value` pairs held apart by a run of spaces.
 *
 * ⚠ **IT IS PARSED, NOT MATCHED AGAINST ENGLISH WORDS.** The separator is a run
 * of two or more spaces and the label ends at the first colon; nothing here
 * knows the word *signature* in any language. That matters because the body is
 * the TENANT's text: a utility that rewrites its own agreement in Spanish, or
 * renames the field, still gets a signature block. B14 rule 35's principle —
 * a catalogue is written in its own language — applied to the one place on this
 * screen where the words belong to the customer rather than to us.
 *
 * Returns `null` when the line does not parse as fields, and the caller then
 * draws it as ordinary text. **Never a guess:** a contract whose signature line
 * we cannot read is a contract we draw exactly as its author typed it.
 */
export function signatureFields(line: string): SignatureField[] | null {
  const segments = line
    .split(/ {2,}|\t+/)
    .map((segment) => segment.trim())
    .filter((segment) => segment !== "");
  if (segments.length === 0) return null;
  const fields: SignatureField[] = [];
  for (const segment of segments) {
    const colon = segment.indexOf(":");
    if (colon <= 0) return null;
    const label = segment.slice(0, colon).trim();
    const ink = segment.slice(colon + 1).trim();
    if (label === "") return null;
    fields.push({ label, ink });
  }
  return fields;
}

/**
 * A PRINTED PAGE PLUS THE SIGNATURE BLOCK, DRAWN WHERE IT FALLS ON THE PAGE.
 *
 * ⚠ **WHERE IT FALLS, AND NOT APPENDED UNDERNEATH.** The block replaces the
 * author's own signature line in position, so a contract that puts the
 * signature above a schedule of charges still puts it above the schedule. An
 * appended block would also print the labels TWICE — once as the author's text
 * and once as ours — which is the repeated-text defect this screen has already
 * had (`DEF-NOT-4464`), and would put OUR words for *Customer signature* on a
 * document whose author chose their own.
 *
 * ⚠ **THE LINE IS FOUND BY THE SIGNATURE TOKEN'S OWN SAMPLE VALUE, NOT BY
 * POSITION AND NOT BY WORDING.** `customer_signature` is served in
 * `merge_field_rows` for all four contract classes and renders to a sample the
 * server chose; the line containing that sample is the signature line. So the
 * detection travels with the class's palette rather than with a guess about
 * which line is last — a contract with a footer after the signature works, and
 * a class that has no signature token draws no block at all.
 *
 * ⚠ **AND THERE IS NO *Send test to me* FOR A CONTRACT.** That control belongs
 * to the head and not to this component, but the reason is a document-shape
 * fact and so is recorded here: a signature request is not an email, and the
 * server already refuses it — `can_test_send` is false for a print class with
 * its own sentence beside the button (BR-SHL-025).
 */
export function ContractSurface(props: {
  /** The wording to draw. A RENDERED body from `POST …/preview` on a contract
   *  that has a version, or the platform's OFFERED body — which still carries
   *  its `{tokens}`, because nobody has published it and there is nothing to
   *  render it against yet. Both are documents and both are drawn as one. */
  body: string;
  data: TemplateDetail;
}) {
  const signatureRow = props.data.merge_field_rows.find(
    (row) => row.token === "customer_signature",
  );
  /* ⚠ **TWO SPELLINGS, BECAUSE THE SAME LINE ARRIVES BOTH WAYS.** A rendered
     contract holds the sample the server substituted — `(signed
     electronically)`; the platform's offered wording still holds the raw
     `{customer_signature}`. Matching only the first is how this renderer came
     to be DEAD UI on all four contract classes for its first hour: none of them
     has a published version, so none of them ever takes the rendered path, and
     every test passed because each tested the path it was written for. Hard-won
     law 2, found by a browser sweep and by nothing else. */
  const marks = [signatureRow?.sample_value, signatureRow?.insert].filter(
    (m): m is string => typeof m === "string" && m !== "",
  );

  function renderBlock(block: DocBlock): ReactNode | undefined {
    if (marks.length === 0) return undefined;
    // `pair` and `text` are both possible: `documentBlocks` splits a line whose
    // trailing sample reads as a label, so the same line arrives as one shape or
    // the other depending on the author's spacing. Rejoin before parsing.
    const line =
      block.kind === "pair"
        ? `${block.text} ${block.value ?? ""}`
        : block.kind === "text"
          ? block.text
          : null;
    if (line === null || !marks.some((mark) => line.includes(mark))) return undefined;
    const fields = signatureFields(line);
    if (fields === null) return undefined;
    return (
      <div className={SIGN_BLOCK} data-testid="preview-signature">
        {fields.map((field) => (
          <span key={field.label} className={SIGN_FIELD} data-testid="preview-signature-field">
            {/* The sample sits ON the rule, which is what a signed page looks
                like. Empty when the server sampled nothing — a blank line to
                sign is the correct drawing, never a stand-in name. */}
            <span className={SIGN_INK}>{field.ink}</span>
            <span className={SIGN_RULE} aria-hidden="true" />
            <span className={SIGN_LABEL}>{field.label}</span>
          </span>
        ))}
      </div>
    );
  }

  return (
    <DocumentPaper
      body={props.body}
      rows={props.data.merge_field_rows}
      renderBlock={renderBlock}
    />
  );
}

/* ══ 5 · THE IN-APP MESSAGE ════════════════════════════════════════════════ */

/**
 * THE BANNER, AT THE WIDTH IT APPEARS IN, OVER A SKETCH OF THE SCREEN BENEATH.
 *
 * ⚠ **NO LETTERHEAD, AND THE ABSENCE IS RULED.** *"Every other template is a
 * letter FROM the utility; this one is the product speaking to the operator."*
 * A test asserts the absence so a later consistency pass cannot add one.
 *
 * ⚠ **THE SCREEN SAYS WHO READS IT RATHER THAN LEAVING IT TO BE ASSUMED.**
 * `staff_bulk_summary` is the ONE class in the catalogue whose reader is a
 * clerk, and until now the only signal was the missing letterhead — an absence,
 * which is the thing every check in this repo is blind to and which a person
 * reads as "unfinished" rather than as "different". One sentence, inside B14
 * rule 32's budget, carrying no rule id and no internal code.
 *
 * ⚠ **THE SKETCH IS DECORATION AND IS `aria-hidden`.** It gives the banner a
 * SCALE — a message that looks roomy in a preview pane and cramped in the app
 * is the thing a preview exists to prevent — and it deliberately carries no
 * words, because a sketch with real text on it would be a second document
 * competing with the one being previewed.
 */
export function InAppSurface(props: { preview: TemplatePreview }) {
  const { t } = useTranslation();
  return (
    <div data-testid="preview-in-app">
      <div className={APP_SKETCH} data-testid="preview-app-sketch">
        <div className={APP_SKETCH_ROWS}>
          <div className={APP_SKETCH_BAR_SHORT} aria-hidden="true" />
          <div className={APP_BANNER} data-testid="preview-bell-panel">
            {props.preview.body}
          </div>
          <div className={APP_SKETCH_BAR} aria-hidden="true" />
          <div className={APP_SKETCH_BAR} aria-hidden="true" />
          <div className={APP_SKETCH_BAR_SHORT} aria-hidden="true" />
        </div>
      </div>
      <p className={APP_AUDIENCE} data-testid="preview-audience">
        {t("templates.detail.inAppAudience")}
      </p>
    </div>
  );
}

/* ══ THE SWITCH ════════════════════════════════════════════════════════════ */

/** The five shapes, resolved once. `printable` and an unknown group share the
 *  page, which is the drawing every document in this product had before the
 *  shapes were separated — a fallback to a real document rather than to a blank
 *  pane. */
export function TemplateSurface(props: {
  preview: TemplatePreview;
  data: TemplateDetail;
  kind: "printable" | "email" | "sms" | "in_app" | "contract";
}) {
  if (props.kind === "sms") return <SmsSurface preview={props.preview} data={props.data} />;
  if (props.kind === "in_app") return <InAppSurface preview={props.preview} />;
  if (props.kind === "email") return <EmailSurface preview={props.preview} data={props.data} />;
  if (props.kind === "contract")
    return <ContractSurface body={props.preview.body} data={props.data} />;
  return <PrintedPageSurface preview={props.preview} data={props.data} />;
}
