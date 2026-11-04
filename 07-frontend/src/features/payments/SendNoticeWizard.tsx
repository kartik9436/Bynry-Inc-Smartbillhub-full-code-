// ── Trace ──────────────────────────────────────────────
// Change:   CR-138-BRC07 · P4.14 ("7·3d Send notice — three steps: who · the
//           picker with the letter each tone selects · the per-row
//           sent-or-skipped table") and P4.27 ("7·3d is a **wizard, not a
//           modal** — three steps on `WizardFrame`, the step is URL state and
//           clamps to the highest validated step").
//           Blueprint `05-prototype/06 Payments Page Blueprint.pdf` p022–p023
//           (the task rows) and p087–p089 (screen 7·3d, read AS IMAGES at
//           scale 2.0 per B14 rule 42).
//           Screens: 7·3d Notice (S35 · PAY-B) · S34 (the door that opens it)
// Rules:    B14 rule 4 (`Verb →` navigates, `Verb ✓` commits) · rule 6 (danger
//           tier on a destructive commit) · rule 8 (a 5+ option dropdown is
//           searchable) · rule 10 (required fields carry the asterisk) · rule
//           11 (a consequence preview before a commit that writes money,
//           service state or LEGAL NOTICES) · rule 31 (no database id on
//           screen) · rule 33 (a LABEL ≤ 3 words, a FACT ≤ 6, an INSTRUCTION
//           ≤ 6 per sentence, RATIONALE zero words) · rule 36 (the kit is how
//           you comply) · rule 38 (the UI rules win on how a FORM is built) ·
//           rule 21 (Tailwind utilities, no stylesheet class — this file is on
//           `styles/route-b-migrated.txt` from its first commit) · rule 43 (a
//           piece of UI is a COMPONENT) · BR-SHL-018 (rail semantics: a done
//           step clicks BACK, a forward click is a no-op) · BR-SHL-019 (ONE
//           transactional commit, at the last step) · BR-PAY-017 (four rungs,
//           five stop conditions) · BR-PAY-035 / BR-NOT-008 (the tone→step
//           table, and that a regulated step ALWAYS renders the disconnect
//           class) · BR-NOT-005 (every notice is a queue write) · BR-TEN-043
//           (the business date is an argument, never a clock)
// Ruling:   OQ-PAY-12607 (2026-09-23, CLOSED — **no fourth tone**)
// Tests:    07-frontend/src/features/payments/sendNoticeWizard.dom.test.tsx
// Impacts:  features/payments/OutstandingsTab.tsx (the ONE door — two dead
//           buttons are replaced by it in the same commit) · App.tsx (route) ·
//           api/bankRecEndpoints.sendCollectionsNotices (`P4.13`)
// ───────────────────────────────────────────────────────
//
// 7·3d — SEND A NOTICE. A WIZARD, BECAUSE THE LETTER HAS TO BE SEEN FIRST.
//
// ╔══════════════════════════════════════════════════════════════════════════╗
// ║  "A clerk sees that *Firm* sends a regulated 10-day disconnect notice    ║
// ║   BEFORE pressing, not after."                                           ║
// ╚══════════════════════════════════════════════════════════════════════════╝
// The blueprint's own panel, *"Why this is a wizard and not a modal — it was
// drawn as one until 2026-09-22"*: *"Because the letter has to be seen before
// it is sent, and a modal had nowhere to put it."* `BR-NOT-008`, verbatim:
// *"regulated ladder steps ALWAYS render the disconnect-notice template class
// regardless of the tone picked in the reminder modal."* **So choosing *Firm*
// does not send a firmer reminder — it sends the regulated 10-day disconnect
// notice**, with a cut date and a statutory footer, and that is the single most
// dangerous sentence on this screen (annotation ③).
//
// ══════════════════════════════════════════════════════════════════════════
// ⚠ THERE ARE **THREE** TONES AND THE DRAWING SAYS FOUR. THE RULING WINS.
// ══════════════════════════════════════════════════════════════════════════
// p088's helper line reads *"Four tones. Each one selects a different letter."*
// and annotation ④ repeats it. **Both are superseded.** `OQ-PAY-12607` CLOSED
// 2026-09-23 — PO, verbatim: ***"(b) Leave it — use Final to escalate"***.
//
//   the RUNGS (`ladder.LADDER_RUNGS`)    four: friendly reminder · first 10-day
//                                        · second 5-day · final 48-hour
//   the TONES (`notices.TONE_TO_STEP`)   three: friendly · firm · final
//
// **THE ASYMMETRY IS DELIBERATE, NOT A GAP.** The four rungs are the sequence a
// utility walks automatically; the three tones are what a person may choose
// when they step in by hand, and a clerk escalating reaches for *Final*. The
// register row says it in terms: *"nobody should 'fix' it again."* Minting a
// fourth tone would widen `BR-PAY-035`'s RATIFIED table and move
// `GET /notice-tones`, this picker and eleven catalogues on an implementer's
// authority. **The tone list below is read off the server's response and is
// never typed out here**, so this screen cannot drift from that table either
// way. Filed as `DEF-PAY-6280` rather than silently resolved.
//
// ⚠ **AND THE SCREEN SAYS NOTHING ABOUT WHY.** B14 rule 33 puts RATIONALE at
// ZERO words on screen, so the picker offers three tones and does not explain
// the ladder's fourth rung to a clerk. The reason lives here and in the
// register, which is exactly where the rule says to put it.
//
// ══════════════════════════════════════════════════════════════════════════
// NEVER INVENT A VALUE THE SERVER REFUSED TO ANSWER — FOUR PLACES HERE
// ══════════════════════════════════════════════════════════════════════════
//   · **the ladder days.** `GET /notice-tones` serves `stage_days` OR
//     `stage_days_unavailable` with a reason. When the tenant's settings cannot
//     be read this screen prints NO day number at all — not `10`, which is a
//     seed and not this utility's. `P4.15` asks for exactly this: *"day numbers
//     from tenant config never constants, and the tones still render when the
//     settings cannot be read."*
//   · **`runs: null`.** The board is THREE-VALUED: `true` steps, `false` was
//     stopped and `skip_reason` says which, and **`null` means this deployment
//     cannot say** because no balance floor could be read. A screen that drew
//     null as *will not send* would tell a clerk the opposite of the truth.
//   · **the count in the commit button.** It counts rows the board says WILL
//     go. If ANY row is `runs: null` the prediction is incomplete, so the
//     button drops its number rather than asserting one that is too low.
//   · **the letter body.** See the step-3 note below — the only render this
//     product has is SAMPLE data, and it is labelled as such.
import { useMemo, useState } from "react";

import { useMutation, useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { useLocation, useNavigate, useSearchParams } from "react-router-dom";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { getCollectionsLadder, sendCollectionsNotices } from "@/api/bankRecEndpoints";
import type { LadderBoardRow, NoticeSendResult } from "@/api/bankRecEndpoints";
import { getNoticeTones, getTemplateDetail } from "@/api/endpoints";
import type {
  NoticeToneRow,
  OutstandingRow,
  TemplateDetail,
  TemplatePreview,
} from "@/api/endpoints";
import { TemplateSurface } from "@/features/notifications/templateSurfaces";
import { Button } from "@/components/Button";
import { SelectField, TextField } from "@/components/FormModal";
import { MoneyCell } from "@/components/MoneyCell";
import { PageHeader } from "@/components/PageHeader";
import { Panel } from "@/components/Panel";
import { StatusPill } from "@/components/StatusPill";
import { PlainTable } from "@/components/Surfaces";
import { Note } from "@/components/TextBits";
import { WizardFrame, clampStepToReached, initialWizardNav } from "@/components/WizardFrame";
import type { WizardCommitOutcome, WizardNavState, WizardStep } from "@/components/WizardFrame";
import { useTenantPath } from "@/routing/tenantPath";
import { apiErrorText } from "@/features/tenancy/settingsShared";
import type { Translator } from "@/features/tenancy/settingsShared";
import { collectionTierLabel, ladderSkipLabel } from "./paymentsShared";

/** 7·3d's address. TENANT-RELATIVE, like every route constant in this module —
 *  the screen that navigates puts it through `tenantPath()`. */
export const SEND_NOTICE_ROUTE = "/payments/outstandings/send-notice";

/** The three steps, in the drawing's order and its words. The ids are stable
 *  because `?step=` is a URL a clerk may have in a tab. */
const STEP_COUNT = 3;

/**
 * WHAT THE DOOR HANDS OVER.
 *
 * ⚠ **THE SELECTION TRAVELS IN ROUTER STATE, NOT IN THE URL, AND THAT IS B14
 * RULE 31.** A selection is N account ids; putting them in the address bar
 * would print database ids on a clerk's screen, which the rule forbids by name
 * — the same reasoning that makes a counter resolve by its CODE. The STEP is
 * URL state (`?step=`), exactly as `P4.27` requires; the SELECTION is not, and
 * a hard refresh therefore lands on an honest empty step 1 with the way back to
 * Debtors rather than on a silent empty send.
 */
export interface SendNoticeHandover {
  accounts: OutstandingRow[];
  asOf: string;
  /** ⚠ **THE TENANT'S CURRENCY TRAVELS WITH THE SELECTION BECAUSE THE ROW DOES
   *  NOT CARRY ONE.** `OutstandingRow` has `balance` and no `currency`:
   *  `BR-TEN-042` gives a tenant ONE currency, so the outstandings list reads
   *  it off the payments response once and passes it down as a prop. This
   *  wizard is opened from that list and is handed the same value, rather than
   *  defaulting to a symbol — a money figure drawn in the wrong currency is a
   *  figure a clerk reads aloud to a customer. */
  currency: string;
}

export function sendNoticeHandover(value: unknown): SendNoticeHandover | null {
  if (typeof value !== "object" || value === null) {
    return null;
  }
  const candidate = value as Partial<SendNoticeHandover>;
  if (
    !Array.isArray(candidate.accounts) ||
    typeof candidate.asOf !== "string" ||
    typeof candidate.currency !== "string"
  ) {
    return null;
  }
  return {
    accounts: candidate.accounts,
    asOf: candidate.asOf,
    currency: candidate.currency,
  };
}

// ── Pure pieces (provable without a browser or a network) ──────────────────

/** What the board decided for one selected account, joined by `account_id`. */
export interface NoticePlanRow {
  account: OutstandingRow;
  board: LadderBoardRow | undefined;
}

/**
 * Will this account's letter go out?
 *
 * ⚠ **THREE-VALUED, AND COLLAPSING IT IS THE DEFECT.** `undefined` here means
 * the BOARD did not return this account at all, which `notices_by_hand.send`
 * treats as `nothing_overdue` and skips — *"a notice to a customer who owes
 * nothing is the worst letter this product can post"*. `null` on `runs` means
 * the deployment could not read a balance floor and genuinely cannot say.
 */
export function noticeWillSend(row: NoticePlanRow): boolean | null {
  if (row.board === undefined) {
    return false;
  }
  return row.board.runs;
}

/** The count the commit button may assert, or `null` when it may not.
 *
 *  A single unpredictable row makes the whole number a guess that is too LOW,
 *  and a clerk reading *Send 2* who sends three has been lied to by arithmetic.
 */
export function assertableSendCount(rows: readonly NoticePlanRow[]): number | null {
  let sending = 0;
  for (const row of rows) {
    const verdict = noticeWillSend(row);
    if (verdict === null) {
      return null;
    }
    if (verdict) {
      sending += 1;
    }
  }
  return sending;
}

/**
 * The letter one tone selects — resolved from the SERVER's table, never from a
 * map in this file.
 *
 * `GET /notice-tones` publishes `notices.TONE_TO_STEP` and this picker reads
 * it, so *"the picker a clerk uses and the resolution the send performs cannot
 * disagree"* — which is `notices_by_hand`'s own stated design and is what makes
 * the no-double-send guarantee reachable at all.
 */
export function toneRow(tones: readonly NoticeToneRow[], tone: string): NoticeToneRow | undefined {
  return tones.find((candidate) => candidate.tone === tone);
}

// ── The screen ─────────────────────────────────────────────────────────────

export function SendNoticeWizard(props: { client?: ApiClient }) {
  const { t } = useTranslation();
  const translate: Translator = (key, params) => t(key, params);
  const client = props.client ?? api;
  const navigate = useNavigate();
  const tenantPath = useTenantPath();
  const location = useLocation();

  const handover = sendNoticeHandover(location.state);
  const accounts = handover?.accounts ?? [];
  const asOf = handover?.asOf ?? "";
  const currency = handover?.currency ?? "";

  const [tone, setTone] = useState("");
  const [why, setWhy] = useState("");
  const [removed, setRemoved] = useState<readonly string[]>([]);
  const [result, setResult] = useState<NoticeSendResult | null>(null);
  // One token per opened wizard (hard rule 6). The door REFUSES a body without
  // it, and a key the server invented would differ on the second submit and
  // dedupe nothing.
  const [submitToken] = useState(() => crypto.randomUUID());

  // ⚠ **`reached` IS COMPONENT STATE AND `step` IS THE URL — `P4.27` asks for
  // BOTH.** Several wizards in this product pass `nav={{ step, reached: step }}`,
  // which makes the fence equal the request and lets a pasted `?step=3` open
  // the letter over a tone nobody picked. `clampStepToReached` is the kit's own
  // answer (`BR-SHL-018`: *"a URL-restored `?step=` clamps to the highest
  // validated step — a pasted deep link can never skip past unvisited
  // steps"*), and this screen uses it rather than re-deriving one.
  const [reached, setReached] = useState<WizardNavState>(initialWizardNav());
  const [searchParams, setSearchParams] = useSearchParams();
  const requested = Number(searchParams.get("step") ?? "1");
  const nav = clampStepToReached(requested, reached, STEP_COUNT);

  function setNav(next: WizardNavState): void {
    setReached(next);
    const params = new URLSearchParams(searchParams);
    params.set("step", String(next.step));
    // ⚠⚠ **`state` IS NOT OPTIONAL HERE, AND OMITTING IT BROKE THE WHOLE
    // SCREEN (`DEF-PAY-6301`).** `setSearchParams` builds a PARTIAL PATH, and
    // a partial path carries no `state` unless it is passed again — so the
    // first press of Continue destroyed the handover this wizard is built on.
    // Measured before the fix: `location.state` present at mount, `null` at
    // `?step=2`; `accounts` became `[]`, the commit read **Send 0 ✓**, Back
    // showed the empty state as though the clerk had removed everybody, and
    // the commit POSTed `account_ids: []`, which `notices_by_hand.send`
    // refuses by name. **7·3d could not send a notice at all.**
    //
    // The docstring above reasons correctly that a selection must not go in
    // the URL (B14 rule 31) and then handed navigation to the one API that
    // drops what it was protecting. Keeping the selection OUT of the URL and
    // carrying it through the navigation are two separate obligations.
    //
    // ⚠ **THIS IS THE ONLY WIZARD IN THE PRODUCT THAT HOLDS ITS DATA IN
    // `location.state`** — measured across every `setSearchParams` caller in
    // `src/`: eight others, none of which passes `state`, because none of them
    // has any to lose. So this line cannot be copied from a sibling and will
    // not be protected by one.
    setSearchParams(params, { replace: true, state: location.state });
  }

  const selected = accounts.filter((row) => !removed.includes(row.account_id));

  const tonesQuery = useQuery({
    queryKey: ["notifications", "notice-tones"],
    queryFn: () => getNoticeTones(client),
    retry: false,
  });

  // ⚠ A READ THAT STEPS NOTHING. `POST /collections/run` sends; this is the
  // look-before-you-send, and it is what annotation ② asks for: *"Rung and last
  // contact · so a clerk can see who has already been chased, before sending
  // again."*
  const boardQuery = useQuery({
    queryKey: ["payments", "notice-board", asOf],
    queryFn: () => getCollectionsLadder({ as_of: asOf }, client),
    enabled: asOf !== "",
    retry: false,
  });

  const plan: NoticePlanRow[] = useMemo(() => {
    const byAccount = new Map<string, LadderBoardRow>();
    for (const row of boardQuery.data?.rows ?? []) {
      byAccount.set(row.account_id, row);
    }
    return selected.map((account) => ({ account, board: byAccount.get(account.account_id) }));
  }, [selected, boardQuery.data]);

  const chosen = tone === "" ? undefined : toneRow(tonesQuery.data?.tones ?? [], tone);

  // The letter the tone selects, rendered by the template service. See the
  // step-3 note for why this is SAMPLE wording and is labelled as such.
  const letterQuery = useQuery({
    queryKey: ["notifications", "notice-letter", chosen?.template_class ?? ""],
    queryFn: () => getTemplateDetail(chosen?.template_class ?? "", null, client),
    enabled: chosen !== undefined,
    retry: false,
  });

  const sendable = assertableSendCount(plan);

  const send = useMutation({
    mutationFn: () =>
      sendCollectionsNotices(
        {
          account_ids: selected.map((row) => row.account_id),
          tone,
          as_of: asOf,
          idempotency_key: submitToken,
        },
        client,
      ),
  });

  async function commit(): Promise<WizardCommitOutcome> {
    try {
      setResult(await send.mutateAsync());
      return { ok: true };
    } catch (error) {
      // BR-SHL-020. The whole batch failed — a PER-ACCOUNT refusal is a 200
      // with `skipped` beside `sent`, and never reaches here.
      return { ok: false, reason: apiErrorText(error, translate) };
    }
  }

  const steps: WizardStep[] = [
    {
      id: "who",
      label: t("payments.notice.step.who"),
      // ⚠ **FOUND BY LOOKING AT THE SCREEN, NOT BY A TEST (hard-won law 6).**
      // A pasted `?step=3` clamped to step 1 correctly and drew the honest
      // *Nobody is selected* panel — **with a live red `Continue` beneath it**.
      // Pressing it would have walked an EMPTY selection to the letter and left
      // the server to refuse the send at the end, which is the refusal-after-
      // the-work shape this product keeps filing.
      //
      // A STRING verdict blocks AND says why, which is `DEF-936`'s whole point:
      // *"a step whose validate can fail for a reason no field carries must be
      // able to supply its own sentence, or the frame will keep telling people
      // to look at fields that are already correct."* There is no field on this
      // step — the selection is carried in — so the generic *fill in what's
      // marked above* would point at nothing.
      validate: () => (selected.length > 0 ? true : t("payments.notice.who.invalid")),
      content: (
        <WhoStep
          rows={plan}
          currency={currency}
          boardUnreadable={boardQuery.isError}
          onRemove={(accountId) => setRemoved((prior) => [...prior, accountId])}
          onBack={() => navigate(tenantPath("/payments/outstandings"))}
          t={translate}
        />
      ),
    },
    {
      id: "which",
      label: t("payments.notice.step.which"),
      // The tone is REQUIRED (B14 rule 10 marks it; this is the floor beneath
      // the mark). Without it step 3 has no letter to render and the send has
      // no rung, so the frame must not advance.
      validate: () => (tone !== "" ? true : t("payments.notice.preview.noTone")),
      content: (
        <WhichStep
          tones={tonesQuery.data?.tones ?? []}
          stageDays={tonesQuery.data?.stage_days ?? null}
          stageDaysUnavailable={tonesQuery.data?.stage_days_unavailable ?? null}
          unreadable={tonesQuery.isError ? apiErrorText(tonesQuery.error, translate) : null}
          tone={tone}
          onToneChange={setTone}
          why={why}
          onWhyChange={setWhy}
          t={translate}
        />
      ),
    },
    {
      id: "preview",
      label: t("payments.notice.step.preview"),
      content: (
        <PreviewStep
          rows={plan}
          chosen={chosen}
          letterPreview={letterQuery.data?.preview ?? null}
          letterDetail={letterQuery.data ?? null}
          // ⚠ THE SERVER'S OWN SENTENCE, not a key minted here. CR-048 wave I
          // shortened it to one line precisely so a pane could draw it, and
          // `template_preview.preview` serves it beside every body: *"the pane
          // must never stop announcing that it is a preview."*
          sampleNotice={letterQuery.data?.preview?.sample_data_notice ?? null}
          letterUnreadable={
            letterQuery.isError
              ? apiErrorText(letterQuery.error, translate)
              : (letterQuery.data?.preview_unavailable ?? null)
          }
          result={result}
          t={translate}
        />
      ),
    },
  ];

  return (
    <div>
      <PageHeader
        kicker={t("payments.notice.kicker")}
        title={t("payments.notice.title")}
        backTo={{
          to: tenantPath("/payments/outstandings"),
          label: t("payments.notice.exit"),
        }}
      />
      <WizardFrame
        steps={steps}
        nav={nav}
        onNavChange={setNav}
        // B14 rule 6 — a destructive commit. It reaches a customer, costs
        // postage and **cannot be recalled**, which is the blueprint's own
        // wording for the Primary-action row: *"**Send 2**, danger tier."*
        commitVariant="danger"
        // B14 rule 4: `Verb ✓` commits. The drawing letters the button *Send 2*
        // with no glyph; rule 38 gives the UI rules the last word on how a FORM
        // is built, and every other commit in this product carries the ✓.
        // The NUMBER drops when the board could not predict every row — see
        // `assertableSendCount`.
        commitLabel={
          sendable === null
            ? t("payments.notice.commitUnknown")
            : t("payments.notice.commit", { count: sendable })
        }
        commitFailedTitle={t("payments.notice.commitFailed")}
        onCommit={commit}
        onCommitted={() => navigate(tenantPath("/payments/outstandings"))}
      />
    </div>
  );
}

// ── Step 1 · Who ───────────────────────────────────────────────────────────

function WhoStep(props: {
  rows: readonly NoticePlanRow[];
  currency: string;
  boardUnreadable: boolean;
  onRemove: (accountId: string) => void;
  onBack: () => void;
  t: Translator;
}) {
  const { t } = props;
  if (props.rows.length === 0) {
    // ⚠ **AN HONEST EMPTY, NOT A SILENT ONE.** Reached two ways: a hard refresh
    // (the selection lives in router state — see `SendNoticeHandover`), or a
    // clerk removing everybody. Both end here, and both get the way back rather
    // than a wizard that would post an empty `account_ids` the server refuses.
    return (
      <Panel>
        <h3>{t("payments.notice.who.emptyTitle")}</h3>
        <p>{t("payments.notice.who.empty")}</p>
        <Button variant="secondary" onClick={props.onBack}>
          {t("payments.notice.backToDebtors")}
        </Button>
      </Panel>
    );
  }
  return (
    <section>
      <h3>{t("payments.notice.who.heading")}</h3>
      <Note>{t("payments.notice.who.helper")}</Note>
      {props.boardUnreadable ? <Note>{t("payments.notice.boardUnreadable")}</Note> : null}
      <PlainTable>
        <thead>
          <tr>
            <th scope="col">{t("payments.notice.col.account")}</th>
            <th scope="col">{t("payments.notice.col.customer")}</th>
            <th scope="col" className="text-right">
              {t("payments.notice.col.owed")}
            </th>
            <th scope="col">{t("payments.notice.col.rung")}</th>
            <th scope="col">{t("payments.notice.col.lastContact")}</th>
            <th scope="col">
              <span className="sr-only">{t("payments.notice.col.actions")}</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {props.rows.map((row) => (
            <tr key={row.account.account_id}>
              {/* B14 rule 31 — the account NUMBER. `account_no` is null when an
                  account genuinely has none, which is stated rather than fallen
                  back to the uuid (DEF-2580's exact defect, one screen over). */}
              <td>
                {row.account.account_no ?? (
                  <span className="text-neutral-700">{t("payments.notice.noNumber")}</span>
                )}
              </td>
              <td>
                {row.account.customer_name ?? (
                  <span className="text-neutral-700">{t("payments.notice.noCustomer")}</span>
                )}
              </td>
              <td className="text-right">
                <MoneyCell amount={row.account.balance} currency={props.currency} />
              </td>
              <td>
                {/* ② The rung ALREADY SENT — *"so a clerk can see who has
                    already been chased, before sending again"*. Absent means
                    the ladder has not reached this account, which is a fact and
                    not a gap. */}
                {row.board?.current_tier == null ? (
                  <span className="text-neutral-700">{t("payments.notice.notChased")}</span>
                ) : (
                  <StatusPill tone="neutral">
                    {collectionTierLabel(row.board.current_tier, t)}
                  </StatusPill>
                )}
              </td>
              <td>
                {row.board?.last_notice_on == null ? (
                  <span className="text-neutral-700">{t("payments.notice.noContact")}</span>
                ) : (
                  row.board.last_notice_on
                )}
              </td>
              <td>
                <Button
                  size="sm"
                  variant="secondary"
                  onClick={() => props.onRemove(row.account.account_id)}
                >
                  {t("payments.notice.remove")}
                </Button>
              </td>
            </tr>
          ))}
        </tbody>
      </PlainTable>
    </section>
  );
}

// ── Step 2 · Which notice ──────────────────────────────────────────────────

function WhichStep(props: {
  tones: readonly NoticeToneRow[];
  stageDays: number[] | null;
  stageDaysUnavailable: string | null;
  unreadable: string | null;
  tone: string;
  onToneChange: (tone: string) => void;
  why: string;
  onWhyChange: (why: string) => void;
  t: Translator;
}) {
  const { t } = props;
  const chosen = props.tone === "" ? undefined : toneRow(props.tones, props.tone);
  return (
    <section>
      <h3>{t("payments.notice.which.heading")}</h3>

      {/* ③ **What a tone actually sends** — the blueprint calls it *"the single
          most dangerous sentence on this screen"*, and it is a FACT rather than
          a rationale, so it is on screen and it is short (B14 rule 33). */}
      <Note>{t("payments.notice.which.toneIsALetter")}</Note>

      {props.unreadable !== null ? (
        // ⚠ `P4.15`: *"the tones still render when the settings cannot be
        // read"*. This branch is the OTHER failure — the tone TABLE itself is
        // unreadable, so there is nothing to pick from and the screen says so
        // instead of drawing an empty select.
        <Note>{t("notifications.tones.unavailable", { reason: props.unreadable })}</Note>
      ) : (
        <SelectField
          id="tone"
          label={t("payments.notice.which.label")}
          value={props.tone}
          onChange={props.onToneChange}
          placeholder={t("payments.notice.which.prompt")}
          // ⚠ **READ OFF THE SERVER'S TABLE, NEVER TYPED OUT HERE.** There are
          // three today and the drawing says four; `OQ-PAY-12607` ruled the
          // asymmetry deliberate, and a hand-typed list is how a screen and a
          // ratified vocabulary drift apart in silence (`CLAUDE.md` hard-won
          // law 2's service-list trap, one module over).
          options={props.tones.map((row) => ({
            value: row.tone,
            label: t(`notifications.tones.tone.${row.tone}`),
          }))}
          help={t("payments.notice.which.helper", { count: props.tones.length })}
          required
        />
      )}

      {chosen === undefined ? null : (
        <Panel>
          <p>
            <strong>{t("payments.notice.which.sends")}</strong>{" "}
            {t(`notifications.tones.class.${chosen.template_class}`)}
          </p>
          <p>
            {chosen.regulated
              ? t("notifications.tones.regulatedYes")
              : t("notifications.tones.regulatedNo")}
          </p>
          {chosen.certified_mail ? <p>{t("notifications.tones.certified")}</p> : null}
          {/* ⚠ **THE DAY NUMBERS ARE THE TENANT'S OR THEY ARE ABSENT.** Never
              the 7/14/30 seeds — `P4.15` names this trap by name, and the
              catalogue has carried both sentences since the tones read was
              built. */}
          {props.stageDays !== null ? (
            <p>{t("notifications.tones.days", { days: props.stageDays.join(" · ") })}</p>
          ) : props.stageDaysUnavailable !== null ? (
            <p>{t("notifications.tones.daysUnavailable", { reason: props.stageDaysUnavailable })}</p>
          ) : null}
        </Panel>
      )}

      {/* ⑤ **Why** — *"kept on every row, sent or skipped"*. */}
      <TextField
        id="why"
        label={t("payments.notice.why.label")}
        value={props.why}
        onChange={props.onWhyChange}
        help={t("payments.notice.why.helper")}
      />
    </section>
  );
}

// ── Step 3 · Preview & send ────────────────────────────────────────────────

function PreviewStep(props: {
  rows: readonly NoticePlanRow[];
  chosen: NoticeToneRow | undefined;
  letterPreview: TemplatePreview | null;
  letterDetail: TemplateDetail | null;
  sampleNotice: string | null;
  letterUnreadable: string | null;
  result: NoticeSendResult | null;
  t: Translator;
}) {
  const { t } = props;
  const sendable = assertableSendCount(props.rows);
  return (
    <section>
      <h3>{t("payments.notice.preview.heading")}</h3>
      <Note>{t("payments.notice.preview.helper")}</Note>

      <Panel>
        {/* ⚠ **THE ONLY LETTER RENDER THIS PRODUCT HAS IS SAMPLE DATA, AND IT
            SAYS SO.** The blueprint draws this panel holding the customer's own
            letter — their name, their address, *"Amount now due $1,284.60"*,
            *"disconnected on or after October 2, 2026"*. Nothing serves that:
            `GET /template-catalog/{code}` renders through
            `template_preview.preview`, whose payload carries `sample_data:
            true`, and there is no per-account render anywhere in the product.
            Drawing sample figures under this customer's name would be the
            *"$0.00 taken today"* defect with a cut-off date attached — a clerk
            would read the amount and the date and believe both. So the panel
            shows the LETTER THE TONE SELECTS, in its own words, labelled a
            sample. Reported, not faked — `DEF-PAY-6279`'s neighbour on the same
            screen family, and this lane's own exception (1) below. */}
        {props.chosen === undefined ? (
          <p>{t("payments.notice.preview.noTone")}</p>
        ) : props.letterUnreadable !== null ? (
          <p>{t("payments.notice.preview.unreadable", { reason: props.letterUnreadable })}</p>
        ) : props.letterPreview === null || props.letterDetail === null ? (
          <p>{t("payments.notice.preview.noBody")}</p>
        ) : (
          <>
            <Note>{props.sampleNotice ?? t("payments.notice.preview.sample")}</Note>
            {/* ⚠ **`TemplateSurface`, NOT A `<pre>` OF THE BODY — AND THE
                DIFFERENCE IS A NAMED DEFECT.** `templateSurfacePrint.dom.test`
                lists *"PRINTING A RE-RENDER OF THE BODY TEXT"* as one of three
                shapes it exists to refuse: *"`<pre>{preview.body}</pre>` … is a
                DIFFERENT document from the one on screen: no inbox lines on an
                email, no page on a letter, no locked rights footer, no
                sample-data notice. It is the receipt defect's own shape."* A
                disconnect notice is a LETTER, so it renders as a printed page
                — which is also the only way a clerk can judge the thing they
                are about to post. B14 rule 43: the kit owns this, not us. */}
            <TemplateSurface
              preview={props.letterPreview}
              data={props.letterDetail}
              kind="printable"
            />
          </>
        )}
      </Panel>

      {/* ⑥ **Per row, sent or skipped — with the reason.** *"A silent exclusion
          is the one thing a collections trail may not contain."* Before the
          commit this is the BOARD's prediction; after it, the server's own
          answer. One table, one shape, so a clerk reads the same columns
          either side of pressing Send. */}
      <PlainTable>
        <thead>
          <tr>
            <th scope="col">{t("payments.notice.col.account")}</th>
            <th scope="col">{t("payments.notice.col.goesOut")}</th>
          </tr>
        </thead>
        <tbody>
          {props.result === null
            ? props.rows.map((row) => (
                <tr key={row.account.account_id}>
                  <td>
                    {row.account.account_no ?? (
                      <span className="text-neutral-700">{t("payments.notice.noNumber")}</span>
                    )}
                  </td>
                  <td>
                    <PlannedOutcome row={row} chosen={props.chosen} t={t} />
                  </td>
                </tr>
              ))
            : [
                ...props.result.sent.map((row) => (
                  <tr key={`sent-${row.account_id}`}>
                    <td>
                      {row.account_no ?? (
                        <span className="text-neutral-700">{t("payments.notice.noNumber")}</span>
                      )}
                    </td>
                    <td>{collectionTierLabel(row.rung, t)}</td>
                  </tr>
                )),
                ...props.result.skipped.map((row) => (
                  <tr key={`skipped-${row.account_id}`}>
                    <td>
                      {row.account_no ?? (
                        <span className="text-neutral-700">{t("payments.notice.noNumber")}</span>
                      )}
                    </td>
                    <td>
                      <SkipCell reason={row.reason} t={t} />
                    </td>
                  </tr>
                )),
              ]}
        </tbody>
      </PlainTable>

      {/* ⑦ **What it will do** — B14 rule 11's consequence preview, which the
          rule requires of *"any form writing money, service state or LEGAL
          NOTICES"*. Two sentences, six words each (rule 33), and never cut
          below clarity. */}
      <Panel>
        <p>
          <strong>
            {sendable === null
              ? t("payments.notice.consequence.unknown")
              : t("payments.notice.consequence.willSend", { count: sendable })}
          </strong>
        </p>
        <p>{t("payments.notice.consequence.noRecall")}</p>
      </Panel>
    </section>
  );
}

/** What the BOARD says will happen to one row, before anything is pressed. */
function PlannedOutcome(props: {
  row: NoticePlanRow;
  chosen: NoticeToneRow | undefined;
  t: Translator;
}) {
  const { t } = props;
  const verdict = noticeWillSend(props.row);
  if (verdict === null) {
    // The third state. NOT *will not send* and NOT *will send*.
    return <span className="text-neutral-700">{t("payments.notice.cannotSay")}</span>;
  }
  if (!verdict) {
    return <SkipCell reason={props.row.board?.skip_reason ?? null} t={t} />;
  }
  if (props.chosen === undefined) {
    return <span className="text-neutral-700">{t("payments.notice.preview.noTone")}</span>;
  }
  return <>{t(`notifications.tones.class.${props.chosen.template_class}`)}</>;
}

/** A skip, with its reason. ⚠ Never the raw code — rule 31 keeps an internal
 *  string off a clerk's screen, and an unknown code renders the fact of the
 *  skip without pretending to know why. */
function SkipCell(props: { reason: string | null; t: Translator }) {
  if (props.reason === null || props.reason === "") {
    return <StatusPill tone="neutral">{props.t("payments.notice.skipped")}</StatusPill>;
  }
  return (
    <StatusPill tone="neutral">
      {props.t("payments.notice.skippedWhy", { reason: ladderSkipLabel(props.reason, props.t) })}
    </StatusPill>
  );
}

export default SendNoticeWizard;

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-138-BRC07 P4.14 + P4.27 (payments blueprint phase 4, wave 2) —
//         built from p087–p089 read AS IMAGES at scale 2.0 (B14 rule 42).
// generated: 2026-09-23 by LANE P4-SCREENS-B
// exceptions: (1) **The letter is the template's SAMPLE render, labelled**, not
//         this customer's — no per-account render exists anywhere in the
//         product (see the step-3 note). (2) **No cut date is printed in the
//         Sends block.** The drawing shows *"cut date 10/02"*; `cut_date`
//         defaults INSIDE `ladder.step_one` and no read publishes what it will
//         be, so printing one would be a date the letter might not carry.
//         (3) **No per-row channel.** The drawing draws *Post · email* on one
//         row and *Post* on another; `channels` is one argument for the whole
//         batch and the response carries none per row, so the column is the
//         letter rather than the medium. All three are reported rather than
//         invented.
// ──────────────────────────────────────────────────────────
