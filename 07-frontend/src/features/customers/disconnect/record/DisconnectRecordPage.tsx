// ── Trace ──────────────────────────────────────────────
// Change:   CR-125-BRC07 — **THE DISCONNECT CASE RECORD**, blueprint
//           `02 Accounts Menu Blueprint.pdf` p143, whose own red banner reads
//           *"TODAY: no disconnect case page exists"*. It did not: no route,
//           no component, no endpoint. PO ruling, verbatim: *"okay build it as
//           per specification and as per what you ahve mentioned - Disconnect
//           details view — every section - i will consolidate actions - too
//           many actions - keep critical ones"*.
// Rules:    B14 rule 42 (built from the drawing AS AN IMAGE — p143, p144 and
//           p145 rendered at 1.35x and cropped at 4x, never from extracted
//           text, whose digits all render as `&` in this PDF) · rule 41 (the
//           product matches the blueprint) · rule 40 (page-head title 32px,
//           which `PageHeader` carries) · rule 43 (a piece of UI is a
//           COMPONENT — four panels and two dialogs, each importable on its
//           own) · rule 37 (every figure drawn is an ILLUSTRATION) · rule 31
//           (no database id is a field's visible value — the kicker is the
//           CASE NUMBER) · rules 32/33 (the copy budget; the two divergences
//           are named in `ProtectionsPanel` and `CutPreviewPanel`) · rule 21 +
//           its per-file clause (Tailwind utilities; this directory is on
//           `styles/route-b-migrated.txt`) · rule 36 (the shared kit) ·
//           BR-SHL-025 (a refused control renders disabled WITH ITS REASON) ·
//           hard-won law 2 and its mirror
// ───────────────────────────────────────────────────────
/**
 * `/disconnects/{ref}` — one disconnection case, read back.
 *
 * ════════════════════════════════════════════════════════════════════════
 * THREE CONTROLS ON SCREEN, AND THE COMMIT IS THE ONE THIS STATE ADMITS
 * ════════════════════════════════════════════════════════════════════════
 * ⚠⚠ **THIS SECTION READ *"THREE ACTIONS, AND THAT IS THE WHOLE SET"* UNTIL
 * 2026-09-20, AND IT NAMED `Mark reconnecting` AND `Restore service` AS
 * DELIBERATELY ABSENT.** The PO has since ruled the opposite, verbatim:
 * *"The other half of the job. Today a utility can cut supply and cannot
 * restore it from the product."* — and, of a failed crew visit, *"The register
 * reflects reality. Today a failed visit is invisible and the case looks
 * untouched."* The earlier sentence is kept rather than deleted, because a
 * reader who learned this screen from it would go looking for a ruling that no
 * longer stands.
 *
 * **IT DOES NOT REOPEN *"too many actions - keep critical ones"*, AND THE
 * REASON IS STRUCTURAL RATHER THAN A PROMISE.** The commits are
 * **STATE-EXCLUSIVE**: a case is `scheduled` **or** `cut` **or**
 * `reconnecting`, never two of them, so the header still shows `Hold the case`,
 * `Open the account` and **exactly one commit** — the one this case can
 * actually take. `available_actions` on the server decides which, and this
 * screen reads it rather than working it out.
 *
 * ⚠ **AND IT REMOVES A CONTROL THAT COULD NEVER BE PRESSED.** `Mark as cut` on
 * a case cut last Tuesday is greyed for ever: `cut_readiness` answers
 * `already_cut` and always will. A permanently dead control over a live screen
 * is the mirror of hard-won law 2 — the shape that left the customer portal
 * with two working doors out of eight — so on a `cut` case the slot carries
 * `Mark reconnecting` instead.
 *
 * **STILL DELIBERATELY ABSENT: Stop the ladder, Advance a tier, Lift a
 * protection, Record a notice, Open a case.** Five write paths with no door,
 * down from ten. They are undrawn and none of them was ruled in.
 *
 * ════════════════════════════════════════════════════════════════════════
 * `Mark as cut` IS DRAWN GREYED, AND THE GREY CARRIES ITS REASON
 * ════════════════════════════════════════════════════════════════════════
 * Its server preconditions are: the case `scheduled`, the date reached,
 * services chosen, proof of service recorded, and a reconnection charge
 * configured. `cut_readiness` re-runs all of them READ-ONLY and answers with
 * the sentence `disconnects.py` itself wrote.
 *
 * ⚠ **THE REASON IS VISIBLE TEXT AND NEVER A HOVER TITLE.** `BR-SHL-025` and
 * the pattern `serviceRequestDecisions.tsx` ratified for the Approve dialog: a
 * touch or keyboard user never sees a tooltip, and the whole point of a
 * refusal is that it is READ. **A button a clerk can always press and always
 * be refused is a shape this repository has already been bitten by.**
 *
 * ⚠ **AND IT SITS UNDER THE ACTION ROW RATHER THAN IN IT.** B14: *"a row of
 * controls holds only things a person can PRESS — a status, an age, the reason
 * a control is disabled, those are FACTS and belong elsewhere."* So the button
 * is in the header where p143 draws it and its reason is the line beneath,
 * bound by `aria-describedby` so a screen reader reads them as one thing.
 *
 * ════════════════════════════════════════════════════════════════════════
 * ⛔ WHAT THIS SCREEN CANNOT SHOW, AND SAYS SO
 * ════════════════════════════════════════════════════════════════════════
 *   * `Oldest debt · 62 days past due` — no column, no read, no seam.
 *   * the NAME half of `Raised by` — `disconnect_cases` has `opened_on` and no
 *     actor column. The DATE half IS drawn.
 *   * the `CHANNEL` and `STATE` columns of `NOTICES SENT` — see
 *     `NoticesSentPanel`, where the absence is the correct behaviour.
 *   * the reconnection FEE on every tenant in this tree — three sources
 *     disagree and it is the PO's to settle.
 *   * `Who did it` on p145 — no argument, no column, no vocabulary.
 */
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { Link, useParams } from "react-router-dom";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { buttonClasses } from "@/components/Button";
import { DateCell } from "@/components/DateCell";
import { PageHeader } from "@/components/PageHeader";
import { LoadingSkeleton } from "@/components/StateFrame";
import { StatusPill } from "@/components/StatusPill";
import type { StatusTone } from "@/components/StatusPill";
import { useCrumbLeaf } from "@/components/crumbLeaf";
import { useRegional } from "@/features/metering/meteringShared";
import type { RegionalProps } from "@/features/metering/meteringShared";
import { useTenantPath } from "@/routing/tenantPath";
import { disconnectWizardPathFor } from "../../transferDisconnectShared";

import { reconnectPath } from "../reconnect/reconnectEndpoints";

import { accountDetailPath } from "../../customersShared";
import { CaseFactsPanel } from "./CaseFactsPanel";
import { CutPreviewPanel } from "./CutPreviewPanel";
import { FinishCutDialog } from "./FinishCutDialog";
import { HoldCaseDialog } from "./HoldCaseDialog";
import { MarkAsCutDialog } from "./MarkAsCutDialog";
import { NoticesSentPanel } from "./NoticesSentPanel";
import { RecordVisitDialog } from "./RecordVisitDialog";
import { Refusal } from "./recordFacts";
// ⚠ **ONLY WHAT THIS FILE USES.** The route constant and the path builder are
// RE-EXPORTED below and never read here, and importing them to re-export is
// two unused bindings — eslint's `no-unused-vars` is right about that, and a
// lane silencing it would be one `// eslint-disable` away from the habit
// CLAUDE.md forbids outright.
import {
  DISCONNECT_RECORD_SCREEN,
  disconnectRecordKey,
  readDisconnectRecord,
} from "./disconnectRecordEndpoints";
import { ProtectionsPanel } from "./ProtectionsPanel";

export {
  DISCONNECT_RECORD_ROUTE,
  DISCONNECT_RECORD_SCREEN,
  disconnectRecordPath,
} from "./disconnectRecordEndpoints";

/** Where the register lives — the one place this page links backwards to. */
export const DISCONNECT_REGISTER_PATH = "/accounts?tab=disconnects";

/**
 * p143's three controls, resolved through the kit ONCE.
 *
 * ⚠ **HOISTED, RATHER THAN CALLED INSIDE A `className` EXPRESSION — a guard
 * caught that and it was right to, twice: the second time it read the very
 * sentence that explained the first.** `routeBUtilities.test.ts` reads
 * every `className` expression in a listed file and asks the Tailwind compiler
 * whether each token is a real rule; an argument sitting inside one reads as a
 * class token, and `secondary` and `danger` compile to nothing. The test was
 * not confused — a bare word in a `className` IS how `DEF-SHL-5088` shipped
 * three screens with no colour at all, and a checker that let this one through
 * could not catch that one. `TransferRecordPage` hoists for the same reason.
 *
 * ⚠ **THE VARIANTS ARE THE KIT'S, NOT THIS SCREEN'S.** Both doors are BOXED,
 * which p143 draws and a browser walk corrected (`ghost` rendered `Open the
 * account` as a bare link); `Mark as cut` is the DANGER tier because it is the
 * destructive commit (B14 rule 6).
 */
const DOOR = buttonClasses("secondary");
const COMMIT_DANGER = buttonClasses("danger");
/**
 * The way back takes the ORDINARY primary, not the danger tier.
 *
 * ⚠ **B14 rule 6 RESERVES `danger` FOR A DESTRUCTIVE COMMIT** — disconnect,
 * retire, reverse, write-off. Putting somebody's supply back on is the opposite
 * act; dressing it in red would teach a clerk that the colour means *important*
 * rather than *irreversible*, and the one control on this screen that genuinely
 * is irreversible would stop standing out.
 */
const COMMIT_BACK = buttonClasses("primary");

/** The refusal's element id, so the disabled button can point at it. */
const CUT_REFUSAL_ID = "disconnect-record-cut-refusal";

export function DisconnectRecordPage(props: RegionalProps & { client?: ApiClient } = {}) {
  const { t } = useTranslation();
  const { ref = "" } = useParams<{ ref: string }>();
  const tenantPath = useTenantPath();
  const client = props.client ?? api;
  // IS-8 — a date renders in the TENANT's zone AND format. One regional path,
  // the same every other dated screen uses.
  const { timeZone, dateFormat } = useRegional(props);

  // ⚠ **EVERY HOOK IS DECLARED ABOVE EVERY EARLY RETURN, AND THAT IS NOT A
  // STYLE CHOICE (`DEF-CUS-5911`).** React counts hooks per render: a
  // `useState` placed below a loading guard runs zero times on the first paint
  // and once on the next, and React throws *"Rendered more hooks than during
  // the previous render"* — which turned the whole move record into
  // `Unexpected Application Error!` for both its flows, with every unit test
  // green, because `renderToStaticMarkup` renders ONCE.
  const [dialog, setDialog] = useState<
    "hold" | "cut" | "finish" | "reconnect" | "visit" | null
  >(null);
  const query = useQuery({
    queryKey: disconnectRecordKey(ref),
    queryFn: () => readDisconnectRecord(ref, client),
    enabled: ref !== "",
  });
  // The leaf is the case NUMBER and never the id (B14 rule 31), and `null`
  // until the server has sent one — *"an empty crumb is not the same claim as
  // no crumb"*.
  useCrumbLeaf(query.data?.case_no?.value ?? null);

  if (query.isLoading) return <LoadingSkeleton variant="card" />;
  if (query.isError || !query.data) {
    return (
      <div className="p-6">
        <PageHeader
          title={t("customers.disconnectRecord.notFound.title")}
          backTo={{
            to: tenantPath(DISCONNECT_REGISTER_PATH),
            label: t("customers.disconnectRecord.back"),
          }}
        />
        <p className="mt-4 text-sm text-neutral-600">
          {t("customers.disconnectRecord.notFound.body")}
        </p>
      </div>
    );
  }

  const record = query.data;
  // `DEF-CUS-6063` — the fourth door, and it is SERVED rather than derived on
  // the screen. `cut_is_unfinished` reads the case state and the account's
  // current status together, and a second opinion computed here would be a
  // second rule about when a cut is finished.
  const canFinish = (record.actions?.available ?? []).includes("finish_cut");
  const readiness = record.actions?.mark_as_cut;
  const cutReady = readiness?.ready === true;
  // ── WHICH COMMIT THIS CASE ADMITS — the server's answer, not this page's ──
  // ⚠ **READ FROM `actions.available` RATHER THAN FROM `state`.** The rule that
  // decides it (`disconnect_record.available_actions`) is the same one
  // `record_visit` and `mark_reconnecting` enforce, and a second copy of it
  // here would be a screen offering a button the server refuses. A payload from
  // a server older than 2026-09-20 carries neither new action and simply falls
  // back to `Mark as cut`, which is what it has always shown.
  const available = record.actions?.available ?? [];
  const reconnectStep = available.includes("restore_service")
    ? "restore_service"
    : available.includes("mark_reconnecting")
      ? "mark_reconnecting"
      : null;
  const reconnectPanel = record.actions?.reconnect;
  const reconnectReady = reconnectPanel?.ready === true;
  const canRecordVisit = available.includes("record_visit");

  // ══════════════════════════════════════════════════════════════════════════
  // ⚠ THE WAY BACK INTO THE SCHEDULING WIZARD — AND IT IS A REPAIR DOOR, NOT A
  //   FIFTH ACTION
  // ══════════════════════════════════════════════════════════════════════════
  // A case can reach `scheduled` with NOBODY having said which services go off.
  // `Mark as cut` then refuses it, correctly, with *"No service is chosen"* —
  // **and until this door there was nowhere to go from that refusal.** The
  // case-record lane established the repair by doing it: re-running the
  // scheduling wizard on such a case re-schedules it and the services land.
  //
  // ⚠ **`10-scripts/cr094_wave_b_seed_cut_account.py`'s HEADER CALLS
  // RE-SCHEDULING *"a dead end by design"*. THAT SENTENCE IS STALE** — it was
  // disproved by running it — and it is corrected in the same commit as this
  // door, because a comment claiming a guarantee is not the guarantee
  // (hard-won law 1) and the next reader would have believed it.
  //
  // ⚠ **OFFERED ONLY WHERE IT REPAIRS SOMETHING, WHICH IS THE PO's *"too many
  // actions - keep critical ones"* APPLIED RATHER THAN OVERRIDDEN.** A case
  // that names its services has nothing to fix, and a fifth door on every case
  // is three more words on a screen already called too full. A control offered
  // where it can never help is the same fault as one offered where it can never
  // act (`BR-SHL-025`).
  const servicesAffected = record.what_a_cut_would_do?.services_affected;
  const needsRescheduling =
    record.actions?.account_id != null &&
    available.includes("mark_as_cut") &&
    servicesAffected !== undefined &&
    (servicesAffected.value ?? []).length === 0;
  const refusalCode = readiness?.refusal?.code;
  const refusalText = refusalCode
    ? t(`customers.disconnectRecord.refused.${refusalCode}`, {
        defaultValue: t("customers.disconnectRecord.refused.generic"),
      })
    : t("customers.disconnectRecord.refused.generic");
  // The reconnection's refusal, resolved the same way. ⚠ **ONE SENTENCE PER
  // REFUSAL CODE, FROM THE CATALOGUE** — the server's `detail` is the RATIONALE
  // and is zero words on screen (B14 rule 33); what a clerk reads is the short
  // sentence the eleven catalogues own.
  const reconnectRefusalText = t(
    `customers.disconnectRecord.refused.${reconnectPanel?.refusal?.code ?? "generic"}`,
    { defaultValue: t("customers.disconnectRecord.refused.generic") },
  );
  // Which commit's refusal the strip under the action row is carrying.
  // ⚠ **`DEF-CUS-10666` — A CLOSED CASE OFFERS NO COMMIT, AND THIS PAGE DREW
  // ONE.** `available_actions` answers only `hold` and `open_account` for a
  // `restored`, `stopped` or `closed_out` case; the fallback below (kept for a
  // server older than 2026-09-20, which sends no list at all) caught a CLOSED
  // case too and drew `Mark as cut` greyed for ever with *"This supply is
  // already cut."* — reachable from a screen since `DEF-CUS-10657` let a clerk
  // restore one. So the cut commit is drawn only where the server offers it,
  // or where it sent no list.
  const offersCut = available.length === 0 || available.includes("mark_as_cut");
  const commitRefused = reconnectStep ? !reconnectReady : offersCut && !cutReady;
  const commitRefusalText = reconnectStep ? reconnectRefusalText : refusalText;
  // ⚠ **THE WARNINGS BELONG TO WHICHEVER COMMIT IS IN THE SLOT**, exactly as
  // the refusal above does — a clerk on a cut case must not read the reconnect's
  // warning and the other way round. Defaulted to `[]` so a server older than
  // 2026-09-25 renders the page unchanged rather than crashing on a missing key.
  const commitWarnings = (reconnectStep ? reconnectPanel?.warnings : readiness?.warnings) ?? [];

  // ── p143's head chips: state · tier · cut date · class ──────────────────
  const chips: { key: string; label: ReactNode; tone: StatusTone }[] = [];
  if (record.state?.value) {
    chips.push({
      key: "state",
      // BORROWED from the register's own vocabulary — one pair of words for
      // one fact, in all eleven catalogues (B14 rule 34's reasoning).
      label: t(`customers.disconnects.state.${record.state.value}`, {
        defaultValue: record.state.value,
      }),
      tone: record.state.value === "cut" ? "danger" : "warning",
    });
  }
  if (record.tier?.value) {
    chips.push({
      key: "tier",
      label: t("customers.disconnectRecord.chip.tierSent", {
        tier: t(`customers.disconnect.notice.${record.tier.value}`, {
          defaultValue: record.tier.value,
        }),
      }),
      tone: "warning",
    });
  }
  if (record.cut_date?.value) {
    chips.push({
      key: "cutDate",
      label: (
        <>
          {t("customers.disconnectRecord.chip.cutDate")}{" "}
          <DateCell value={record.cut_date.value} timeZone={timeZone} dateFormat={dateFormat} />
        </>
      ),
      tone: "neutral",
    });
  }
  if (record.customer_class?.value) {
    chips.push({ key: "class", label: record.customer_class.value, tone: "neutral" });
  }

  return (
    <div className="p-6" data-screen={DISCONNECT_RECORD_SCREEN}>
      <PageHeader
        // p143: `← The register`.
        backTo={{
          to: tenantPath(DISCONNECT_REGISTER_PATH),
          label: t("customers.disconnectRecord.back"),
        }}
        // The kicker is the CASE NUMBER — what a clerk reads back to a customer
        // holding a notice. B14 rule 31: never the uuid.
        kicker={
          <span className="uppercase tracking-wide">
            {t("customers.disconnectRecord.kicker")} {record.case_no?.value ?? ""}
          </span>
        }
        // The title is the CUSTOMER (p143), at 32px — `PageHeader` carries rule
        // 40's size on both heading branches, so this screen sets none and
        // cannot drift from the other ~137.
        title={record.customer_name?.value ?? record.case_no?.value ?? ""}
        status={
          <span className="flex flex-wrap items-center gap-2">
            {chips.map((chip) => (
              <StatusPill key={chip.key} tone={chip.tone}>
                {chip.label}
              </StatusPill>
            ))}
          </span>
        }
        // ── THE THREE ACTIONS, AND NOTHING ELSE ─────────────────────────────
        // ⚠ **THE DRAWING READS LEFT TO RIGHT `Hold · Open · Mark as cut` AND
        // THIS HEADER RENDERS `secondaryActions` BEFORE `primaryAction` ON ALL
        // ~137 SCREENS**, so the drawn order survives with `Mark as cut` as the
        // primary — which is also the one that COMMITS something. B14 rule 38
        // settles the general case and it does not have to be invoked here,
        // because the drawing and the frame agree.
        secondaryActions={
          <>
            <button
              type="button"
              className={DOOR}
              data-testid="disconnect-record-hold"
              onClick={() => setDialog("hold")}
            >
              {t("customers.disconnectRecord.action.hold")}
            </button>
            {/* ⚠ **BOXED, NOT BORDERLESS — MEASURED IN A BROWSER AND CORRECTED
                (hard-won law 6).** The first build gave this `ghost` and it
                rendered as a bare link beside a boxed `Hold the case`; p143
                draws BOTH doors boxed, and draws this one HEAVIER. Nine
                defects in this repository were found this way and by nothing
                else — no gate reads rendered output. */}
            <Link
              className={DOOR}
              to={tenantPath(accountDetailPath(record.actions.account_id))}
              data-testid="disconnect-record-open-account"
            >
              {t("customers.disconnectRecord.action.openAccount")}
            </Link>
            {/* ⚠ **THE FOURTH CONTROL, AND IT IS ABSENT RATHER THAN GREYED ON
                EVERY CASE BUT ONE** (`DEF-CUS-6063`). The PO's *"too many
                actions - keep critical ones"* was said over TEN further writes,
                each of them a new thing a clerk could START. This starts
                nothing: `Mark as cut` promises *"Status becomes Disconnected"*
                on this very page and delivers two of its three consequences
                when billing refuses the bill, and this is that same act
                reaching its end. A control offered where it can never apply is
                three more words on a screen already called too full. */}
            {canFinish ? (
              <button
                type="button"
                className={DOOR}
                data-testid="disconnect-record-finish-cut"
                onClick={() => setDialog("finish")}
              >
                {t("customers.disconnectRecord.action.finishCut")}
              </button>
            ) : null}
            {/* ⚠ **A CREW ATTENDS A SCHEDULED CASE AND NOTHING ELSE**, so this
                door exists only where the server says it can be used. A control
                that would always be refused is not offered at all
                (`BR-SHL-025`), and the two other states each have their own
                commit in the slot below. */}
            {canRecordVisit ? (
              <button
                type="button"
                className={DOOR}
                data-testid="disconnect-record-record-visit"
                onClick={() => setDialog("visit")}
              >
                {t("customers.disconnectRecord.action.recordVisit")}
              </button>
            ) : null}
            {/* See `needsRescheduling` above — the repair door, and only where
                there is something to repair. */}
            {needsRescheduling && record.actions?.account_id != null ? (
              <Link
                className={DOOR}
                to={tenantPath(disconnectWizardPathFor(record.actions.account_id))}
                data-testid="disconnect-record-reschedule"
              >
                {t("customers.disconnectRecord.action.reschedule", {
                  defaultValue: "Choose the services",
                })}
              </Link>
            ) : null}
          </>
        }
        primaryAction={
          /* ── ONE COMMIT, AND IT IS THE ONE THIS STATE ADMITS ──────────────
             `cut` → `Mark reconnecting` · `reconnecting` → `Restore service` ·
             anything else → `Mark as cut`, greyed with its reason exactly as
             p143 draws it on a `notice_sent` case. The three can never be
             simultaneously available, so the header still holds three controls
             and the PO's *"keep critical ones"* is not reopened. */
          reconnectStep ? (
            /* ⚠ **A LINK AND NOT A DIALOG SINCE 2026-09-25 — S148 LANDED.**
               Reconnection was a dialog on this record because it had nowhere
               else to be; lane RECONNECT built it as a screen of two steps at
               an address of its own, and a screen that exists behind a control
               still opening a dialog is hard-won law 2's mirror — a live screen
               nobody can reach. `ReconnectPage.dom.test.tsx` asserts this
               destination BY ADDRESS and BY SCREEN ID, so pointing it wrongly
               goes red by name rather than opening onto the wrong thing.
               ⚠ **IT IS NEVER DISABLED.** `BR-CUS-1097` (PO 2026-09-25) —
               the balance need not be clear, and what is still owed is stated
               in the warning strip below rather than greying the door. The
               screen itself decides what its own step admits. */
            <Link
              className={COMMIT_BACK}
              data-testid="disconnect-record-reconnect"
              data-step={reconnectStep}
              to={tenantPath(reconnectPath(record.case_no?.value ?? ""))}
            >
              {t(`customers.disconnectRecord.action.${reconnectStep}`)}
            </Link>
          ) : offersCut ? (
            <button
              type="button"
              className={COMMIT_DANGER}
              data-testid="disconnect-record-mark-cut"
              disabled={!cutReady}
              aria-describedby={cutReady ? undefined : CUT_REFUSAL_ID}
              onClick={() => setDialog("cut")}
            >
              {t("customers.disconnectRecord.action.markCut")}
            </button>
          ) : null
        }
      />

      {/* p143 draws the address under the head chips. Hard rule 8: it is
          WALKED to the premises by the server and no entity on this page
          declares one. */}
      {record.address?.value ? (
        <p className="mt-2 text-sm text-neutral-600" data-testid="disconnect-record-address">
          {record.address.value}
        </p>
      ) : null}

      {/* ⛔ **THE GREY'S REASON — VISIBLE TEXT, UNDER THE ACTION ROW.**
          ⚠ ONE STRIP, SERVING WHICHEVER COMMIT IS IN THE SLOT. Two strips would
          mean a clerk reading the reason a button they cannot see is disabled. */}
      {commitRefused ? (
        <div className="mt-3">
          <Refusal id={CUT_REFUSAL_ID} testId="disconnect-record-cut-refused">
            {commitRefusalText}
          </Refusal>
        </div>
      ) : null}

      {/* ⚠ **WHAT IS TRUE BUT DOES NOT STOP THE CLERK — `BR-CUS-1096`'s
          PRINCIPLE, WIRED FOR ITS TWO 2026-09-25 SIBLINGS.** `BR-CUS-1097` (the
          balance need not be clear to reconnect) and `BR-CUS-1099` (no recorded
          proof of certified service) each turned a refusal into a fact. A fact
          with nowhere to render is the ruling half-built: the clerk would simply
          stop being told. These sit BELOW the refusal strip and never instead of
          it — a warning is not a reason a button is grey, and the two must not
          be mistaken for each other.
          ⚠ **ONE SENTENCE PER CODE, FROM THE CATALOGUE.** The server's `detail`
          is RATIONALE and is zero words on screen (B14 rule 33). */}
      {commitWarnings.length > 0 ? (
        <ul className="mt-3 flex flex-col gap-1" data-testid="disconnect-record-warnings">
          {commitWarnings.map((warning) => (
            <li
              key={warning.code}
              data-warning={warning.code}
              className="text-sm font-semibold text-neutral-900"
            >
              {t(`customers.disconnectRecord.warned.${warning.code}`, {
                defaultValue: t("customers.disconnectRecord.warned.generic"),
              })}
            </li>
          ))}
        </ul>
      ) : null}

      {/* p143 is TWO COLUMNS at desktop and one at phone width. The staff app's
          design target is 1280–1440 (PO ruling 2026-09-10); the single column
          below `lg` costs nothing and keeps the page from scrolling sideways. */}
      <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-2">
        <div className="flex flex-col gap-6">
          <CaseFactsPanel record={record} timeZone={timeZone} dateFormat={dateFormat} />
          <NoticesSentPanel record={record} timeZone={timeZone} dateFormat={dateFormat} />
        </div>
        <div className="flex flex-col gap-6">
          <ProtectionsPanel record={record} timeZone={timeZone} dateFormat={dateFormat} />
          <CutPreviewPanel record={record} timeZone={timeZone} dateFormat={dateFormat} />
        </div>
      </div>

      {dialog === "hold" ? (
        <HoldCaseDialog
          record={record}
          today={record.protections?.as_of ?? ""}
          dateFormat={dateFormat}
          client={client}
          onClose={() => setDialog(null)}
          onHeld={() => void query.refetch()}
        />
      ) : null}
      {dialog === "finish" ? (
        <FinishCutDialog
          record={record}
          timeZone={timeZone}
          dateFormat={dateFormat}
          client={client}
          onClose={() => setDialog(null)}
          onFinished={() => void query.refetch()}
        />
      ) : null}
      {dialog === "cut" ? (
        <MarkAsCutDialog
          record={record}
          today={record.protections?.as_of ?? ""}
          dateFormat={dateFormat}
          timeZone={timeZone}
          client={client}
          onClose={() => setDialog(null)}
          // DEF-CUS-10168 — FormModal never closes itself on success; a cut
          // that committed must not leave its dialog open over a cut case.
          onCut={() => {
            setDialog(null);
            void query.refetch();
          }}
        />
      ) : null}
      {dialog === "visit" ? (
        <RecordVisitDialog
          record={record}
          today={record.protections?.as_of ?? ""}
          dateFormat={dateFormat}
          client={client}
          onClose={() => setDialog(null)}
          onRecorded={() => void query.refetch()}
        />
      ) : null}
    </div>
  );
}

export default DisconnectRecordPage;
