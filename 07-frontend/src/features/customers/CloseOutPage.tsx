// ── Trace ──────────────────────────────────────────────
// Story:    US-CUS-005 (the only story that owns any part of an account's
//           terminal path — it owns the MOVE-OUT wizard, S20).
//           ⚠ **NO STORY OWNS THIS SCREEN.** The PO ruled the ACT on
//           2026-08-27 and no epic covers it — hard-won law 8. A story is OWED
//           and is REPORTED rather than invented.
//           Screens: S21/S22 (the account it is reached from) · S90
// Change:   DEF-724 — *"A disconnected customer can never be closed - Add a
//           separate close-out act — Cleaner in the record"* (PO 2026-08-27).
//           AMENDED 2026-09-13 by lane A (`CR-094-BRC01`) — the screen is built
//           to its DRAWING, `04-docs/05-modules/03-customers/blueprint/`
//           `10-close-out.md` → `09-move-out-wizard-standalone.md`, pages
//           107–111. B14 rule 41: the product UI matches the blueprint exactly.
// Rules:    BR-CUS-430 (a SEPARATE act) · BR-CUS-431 (`closed_at` is the CUT
//           date) · BR-CUS-082 (a surviving debt is chased, TIER 1,
//           collections) · BR-CUS-110 (a cut ends occupancy) · BR-CUS-015
//           (`accounts.balance` is a CACHE — this screen renders the server's
//           AR reading or its absence, never $0.00) · BR-SHL-025 (who may) ·
//           BR-SHL-034 (one date formatter) · B14 rule 6 (the DANGER tier on a
//           destructive commit) · B14 rule 21 (new UI is Tailwind utilities and
//           adds NO class to a stylesheet) · B14 rule 31 (no database id, and
//           no service CODE, is ever the visible value of a field) · B14 rule
//           32 (one sentence per section; a stated absence is CLOSED) · B14
//           rule 33 (on-screen text capped by purpose) · B14 rule 36 (compose
//           the kit) · B14 rule 39 (the spacing scale) · B14 rule 41
// Tests:    07-frontend/src/features/customers/CloseOutPage.dom.test.tsx
// ───────────────────────────────────────────────────────
//
// ══════════════════════════════════════════════════════════════════════════
// B14 RULE 21 — THIS FILE IS ON `route-b-migrated.txt` AND THAT IS DELIBERATE
// ══════════════════════════════════════════════════════════════════════════
// It is a NEW screen written entirely in Tailwind utilities, so G31's rule
// ("a class must be declared by a .css file") is false for it from its first
// commit rather than from a migration. `RateScheduleDetail.tsx` is the
// precedent and carries the same note. The utilities are handed to
// `routeBUtilities.test.ts`, which asks the STRICTER question — every token
// must be declared by a stylesheet OR compile to a real rule through the actual
// Tailwind compiler — so a typo'd `itmes-end` fails there rather than rendering
// as nothing at all (the `DEF-SHL-5088` hazard CLAUDE.md now names).
// ⚠ **A COMPONENT MOUNTED FROM THE KIT MAY CARRY A STYLESHEET CLASS AND THAT IS
// NOT A BREACH** — `NotRecorded`'s `cus-refused` is declared in `customers.css`
// and written in `customersShared.tsx`, which is not this file. Rule 21 governs
// the class a screen WRITES; rule 36 governs where a screen gets its pieces.
//
// ══════════════════════════════════════════════════════════════════════════
// THE ONE THING THIS SCREEN EXISTS TO SHOW BEFORE IT IS WRITTEN
// ══════════════════════════════════════════════════════════════════════════
// `closed_at_will_be` — the CUT date. BR-CUS-431 puts it in `accounts.closed_at`
// and NOT the day the clerk clicks, and it is the one field on this page no
// correction row can un-say (CLAUDE.md hard rule 4). So it is rendered as a
// FACT, not as an input: a form that could name the date is a form that could
// get it wrong.
//
// ══════════════════════════════════════════════════════════════════════════
// WHAT THE DRAWING ASKS FOR THAT THIS SCREEN DID NOT HAVE — lane A, 2026-09-13
// ══════════════════════════════════════════════════════════════════════════
// Walked in a browser at 1280 and 1440 against pages 107–111. The drawing opens
// with TWO panels of facts — *"The account you are closing"* (nine rows) and
// *"What was cut, and when"* (seven) — and closes with three more: *"What
// pressing this writes"*, *"What it will not do"* and *"When it refuses"*. Not
// one of the five existed. The screen showed three facts and two boxes, so a
// clerk ending a customer's account could not see WHOSE account, WHAT was cut,
// WHEN, or what one press was about to write.
//
// **Every row in the first panel was already on the wire** and nothing asked
// for it: `GET /accounts/{id}` serves the customer, the customer number, the
// category, the status and its behaviour class, the service address, the unit,
// the services and the opened date. That is hard-won law 2's ordinary shape —
// built, and not wired — and it is why this screen now makes that read.
//
// **Four rows in the second panel were on the MODEL and not on the wire.**
// `DisconnectCase` has held `cut_reason`, `services_cut`, `opened_on` and
// `outstanding_at_cut` since it was written; `close_out.eligibility()` served
// none of them. They are served now, READ-ONLY, from the case that function had
// already resolved — no second query, because a second reader is a second
// answer to *which case is open*.
//
// **Two rows genuinely do not exist and are STATED rather than defaulted.** The
// final metered bill and the base charges since the cut are billing's, and
// billing has no invoices table. A dash would read as *"nothing"*; `$0.00`
// would be invented money (CLAUDE.md hard rule 2).
//
// ⚠ **THE COMMIT KEEPS ITS OWN LABEL AND DOES NOT TAKE THE DRAWN ONE.** The
// blueprint draws TWO screens — this one, whose button reads *"Record the
// close-out"* and opens `?confirm=1`, and that one, whose button reads *"Yes —
// close it out"* and does it. The second screen does not exist (`DEF-CUS-5162`),
// so ONE press here closes the account irreversibly. *"Record the close-out"*
// over that mechanism promises a step that is not there, which is the same
// falsification the drawn label exists to prevent. The button says what it does.
//
// ══════════════════════════════════════════════════════════════════════════
// EVERY MISSING COPY KEY CARRIES A `defaultValue` — IT IS NOT AN OVERSIGHT
// ══════════════════════════════════════════════════════════════════════════
// Lanes are banned from editing the eleven locale catalogues
// (`10-scripts/i18n_extract_defaults.py`'s own header). The sanctioned handover
// is exactly this: the English lives at the call site as `defaultValue`, that
// script recovers it from source, and the translation lane fans it in. G18
// excludes a `t()` carrying a `defaultValue` for the same reason.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { Button } from "@/components/Button";
import { DateCell } from "@/components/DateCell";
import { MoneyCell } from "@/components/MoneyCell";
import { PageHeader } from "@/components/PageHeader";
import { Panel } from "@/components/Panel";
import { InlineLinkTo, PlainTable, RefusalStrip } from "@/components/Surfaces";
import { Note } from "@/components/TextBits";
import { useRegional } from "@/features/metering/meteringShared";
import type { RegionalProps } from "@/features/metering/meteringShared";
import { useToast } from "@/components/Toast";
import { getAccountDetail } from "@/api/endpoints";
import type { AccountDetail } from "@/api/endpoints";
import { AccountServiceChips } from "./accountDetailHeader";
import { FROM_MOVE_IN_VALUE, forgetTenancyAfterMoveOut, moveInResumePath } from "./moveInWizard/moveInUnitSearch";
import { apiErrorText } from "@/features/tenancy/settingsShared";
import type { Translator } from "@/features/tenancy/settingsShared";
import { useTenantPath } from "@/routing/tenantPath";

import {
  NotRecorded,
  accountDetailPath,
  accountStatusLabel,
  useAccountCategories,
} from "./customersShared";
import {
  closeOutAccount,
  getCloseOutEligibility,
} from "./closeOutEndpoints";
import type { CloseOutAbsence, CloseOutEligibility } from "./closeOutEndpoints";

export const closeOutEligibilityKey = (accountId: string) =>
  ["accounts", "close-out", accountId] as const;

// ══════════════════════════════════════════════════════════════════════════
// THE SCREEN SPEAKS; THE SERVER EXPLAINS. `DEF-CUS-5087`, 2026-09-12.
// ══════════════════════════════════════════════════════════════════════════
// Until that day this screen rendered the server's `detail` strings straight
// into the DOM — `blocked_by.detail`, `dunning_if_closed.reason` and every
// `absences[].detail` — plus each absence's `tracks` id as visible text. Those
// strings are ENGINEERING PROSE, written for a lane reading a payload, and they
// carry exactly what B14 rule 31 forbids on screen: `BR-CUS-082`, `BR-CUS-430`,
// `BR-CUS-097`, `BR-CUS-107`, `OQ-830`, `OQ-680`, `DEF-724`, `DSC-02.4`,
// `accounts.close_reason`, and a PO quotation with its typos intact. They are
// also four-sentence paragraphs of RATIONALE, which rule 33 caps at ZERO words
// on screen.
//
// ⚠ **IT WAS INVISIBLE BECAUSE OF THE OTHER DEFECT, AND THAT IS THE WHOLE
// STORY.** `DEF-CUS-5073` made this screen's read 404 on every tenant, so every
// one of those fields arrived `undefined` and the page rendered dashes. Fixing
// one character published all of it at once. **A screen that cannot reach its
// server cannot be reviewed** — and `G28`, which enforces rule 31, scans the
// eleven catalogues and the backend's own strings, not what a component does
// with a payload field at runtime. Nothing in this repository was looking at
// the join.
//
// So: the SERVER's sentence is evidence and rides on `title`, exactly as rule 31
// prescribes for an internal value. What a clerk READS is this product's own
// sentence, keyed by the server's `code`, from the catalogues. An unrecognised
// code falls back to a short honest line rather than to the payload — a new
// server code must reach a translator, not a clerk.

// ⚠ **EVERY `t()` KEY BELOW IS A LITERAL, AND THAT IS NOT A STYLE CHOICE.**
// The first draft of these maps held bare English and resolved the catalogue
// key by interpolation — `` t(`customers.account.closeOut.absence.${code}`) ``.
// It works, it type-checks, and it renders correctly in English, and it would
// have left these sentences **untranslated in all eleven languages for ever**:
// `10-scripts/i18n_extract_defaults.py` is how a lane hands copy to the
// translation lane (lanes are BANNED from editing the catalogues directly), and
// it recovers `t("literal.key", { defaultValue: … })` **from source**. A
// template literal is invisible to it. Measured: of the keys this lane adds, 14
// were recovered and every interpolated one was not.
//
// So the lookup is still BY THE SERVER'S CODE — which is what keeps a new
// server code from reaching a clerk as English — and each entry is a `t()` call
// the extractor can see.

/** This product's own words for each close-out blocker, at rule 33's cap: six
 *  words a sentence, two sentences at most. Keyed by the server's `code`. */
function blockerSentence(t: Translator): Record<string, string> {
  return {
    still_occupying: t("customers.account.closeOut.blocked.stillOccupying", {
      defaultValue: "This customer still holds the unit. File a move-out instead.",
    }),
    already_terminal: t("customers.account.closeOut.blocked.alreadyTerminal", {
      defaultValue: "This account is already closed.",
    }),
    not_a_cut_account: t("customers.account.closeOut.blocked.notACutAccount", {
      defaultValue: "Service was never cut here. A cut comes first.",
    }),
  };
}

/** And for each stated absence. Each is a FACT or a CONSEQUENCE about what this
 *  screen did NOT do — never the reason the product is built this way. */
function absenceSentence(t: Translator): Record<string, string> {
  return {
    close_out_reason_vocabulary_unruled: t("customers.account.closeOut.absence.reasonVocabulary", {
      defaultValue: "Your words are saved. No report can count them.",
    }),
    close_out_clearance_not_performed: t("customers.account.closeOut.absence.clearance", {
      defaultValue: "Nothing was checked for you. Check plans and disputes yourself.",
    }),
    close_out_shortfall_not_tied_back: t("customers.account.closeOut.absence.shortfall", {
      defaultValue: "No debt moves to an owner here.",
    }),
    disconnected_is_not_a_closed_account: t("customers.account.closeOut.absence.cutIsNotClosed", {
      defaultValue: "A cut account is not closed. This closes it.",
    }),
  };
}

/** One stated absence, in the clerk's language.
 *
 *  `tracks` stays on `data-tracks` — G38 reads the attribute, and it was never
 *  the attribute that reached a reader. `title` carries the server's own
 *  sentence as evidence, which is rule 31's named exception for an internal
 *  value, and it is read as `title` rather than as text so a check over the DOM
 *  string does not go green on the breach and red on the fix. */
function Absence({ absence, t }: { absence: CloseOutAbsence; t: Translator }) {
  const ours = absenceSentence(t)[absence.code];
  return (
    <li className="mb-3 last:mb-0" data-tracks={absence.tracks ?? undefined}>
      <span className="block text-sm" title={absence.detail}>
        {ours ??
          t("customers.account.closeOut.absenceUnworded", {
            defaultValue: "This screen cannot state this yet.",
          })}
      </span>
    </li>
  );
}

/** One drawn fact row: the label on the left, the value on the right. The
 *  drawing's two fact panels are both built from this, so their rows line up on
 *  the same edges without either panel measuring anything. */
function Fact({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-4 py-1">
      <span className="text-sm opacity-80">{label}</span>
      <span className="text-right text-sm font-semibold">{children}</span>
    </div>
  );
}

/** A dash is a claim. Where the screen has nothing, it says so in words and
 *  carries the reason on hover, never as a visible sentence (rule 33 —
 *  RATIONALE is zero words on screen). */
function Blank({ t }: { t: Translator }) {
  return (
    <span className="opacity-60">
      {t("customers.account.closeOut.notOnFile", { defaultValue: "not on file" })}
    </span>
  );
}

export interface CloseOutPageProps extends RegionalProps {
  accountId?: string;
  client?: ApiClient;
}

export function CloseOutPage(props: CloseOutPageProps = {}) {
  const params = useParams();
  const accountId = props.accountId ?? params.accountId ?? "";
  const client = props.client ?? api;
  const { t } = useTranslation();
  const navigate = useNavigate();
  const tenantPath = useTenantPath();
  const toast = useToast();
  const queryClient = useQueryClient();
  // BR-SHL-034 — ONE date formatter, and the tenant's own zone and format
  // behind it. `useRegional` is the product's resolution order (an explicit
  // prop, then what `ShellWithSession` published) and there is deliberately no
  // step three: under `vite build` the branch that would guess is stripped, so
  // a screen rendered outside the provider fails loudly rather than drawing a
  // plausible wrong date. `DEF-SHL-3964` is the sixteen days that cost.
  const regional = useRegional(props);
  const categories = useAccountCategories(client);

  const [closedOutOn, setClosedOutOn] = useState("");
  const [reason, setReason] = useState("");
  const [failure, setFailure] = useState<string | null>(null);

  const preview = useQuery<CloseOutEligibility>({
    queryKey: closeOutEligibilityKey(accountId),
    queryFn: () => getCloseOutEligibility(accountId, client),
    enabled: accountId !== "",
    retry: false,
  });

  // ⚠ **THE ACCOUNT ITSELF — WIRED 2026-09-13, AND IT IS THE WHOLE FIRST PANEL
  // OF THE DRAWING.** `GET /accounts/{id}` has served every one of those nine
  // rows since the account screen was built and this screen never asked, so a
  // clerk about to end a customer's account saw an account NUMBER and nothing
  // else about whose it was. Its own query key, shared with the account screen,
  // so opening this over the account it belongs to costs no second request.
  const account = useQuery<AccountDetail>({
    queryKey: ["accounts", "detail", accountId],
    queryFn: () => getAccountDetail(accountId, client),
    enabled: accountId !== "",
    retry: false,
  });

  const [searchParams] = useSearchParams();
  const fromMoveIn = searchParams.get(FROM_MOVE_IN_VALUE) ?? "";
  const commit = useMutation({
    mutationFn: () => closeOutAccount(accountId, { closed_out_on: closedOutOn, reason }, client),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: closeOutEligibilityKey(accountId) });
      // `DEF-CUS-10193` — the cut account's cached reads go with it.
      void forgetTenancyAfterMoveOut(queryClient, {
        accountId,
        unitId: account.data?.unit_id ?? "",
        moveInParkId: fromMoveIn,
      });
      toast(
        t("customers.account.closeOut.done", {
          defaultValue: "Account closed out. The record shows the cut date it ended on.",
        }),
      );
      // `DEF-CUS-10190` — raised from a move-in on this cut account's unit:
      // back to that parked move-in, its opening reads carried from the cut.
      navigate(
        tenantPath(fromMoveIn === "" ? accountDetailPath(accountId) : moveInResumePath(fromMoveIn)),
      );
    },
    onError: (error: unknown) => setFailure(apiErrorText(error, t)),
  });

  const data = preview.data;
  const detail = account.data;
  const blocker = data?.blocked_by ?? null;
  // ⚠ The BUTTON's guard is the SERVER's answer, never a second opinion
  // assembled here. A screen that decided eligibility itself would be a second
  // implementation of BR-CUS-430 free to drift from the first.
  const ready = Boolean(data?.eligible) && closedOutOn !== "" && reason.trim() !== "";

  const date = (value: string | null | undefined) =>
    value == null || value === "" ? (
      <Blank t={t} />
    ) : (
      <DateCell value={value} timeZone={regional.timeZone} dateFormat={regional.dateFormat} />
    );

  // ⚠ **THE NAME OR NOTHING (the `AccountHeaderChips` reasoning, and the same
  // rule).** `accountCategoryName`'s documented fallback is the CODE, and a code
  // is what B14 rule 31 forbids on screen. While the catalogue is loading there
  // is simply no category, which is a row arriving late rather than a wrong one.
  const category = categories.all.find((row) => row.code === detail?.account_type)?.name ?? null;
  const behaviour =
    detail?.status_behavior_class == null
      ? ""
      : t(`customers.account.behaviourClass.${detail.status_behavior_class}`, { defaultValue: "" });

  // The drawn roll-up: `A-11488 · Okafor, D. · cut on 08/18/2026`. Assembled
  // from what is actually present, so a missing customer name drops a segment
  // rather than printing an empty one.
  const rollup = [
    data?.account_no ?? detail?.account_no ?? null,
    detail?.name ?? null,
  ].filter((part): part is string => part !== null && part !== "");

  return (
    <>
      <PageHeader
        kicker={t("customers.account.closeOut.kicker", { defaultValue: "Close out account" })}
        title={t("customers.account.closeOut.title", { defaultValue: "Close out this account" })}
        rollup={
          rollup.length === 0 ? undefined : (
            <span>
              {rollup.join(" · ")}
              {data?.cut_on != null && data.cut_on !== "" ? (
                <>
                  {" · "}
                  {t("customers.account.closeOut.cutOnInline", { defaultValue: "cut on" })}{" "}
                  {date(data.cut_on)}
                </>
              ) : null}
            </span>
          )
        }
        backTo={{
          to: tenantPath(accountDetailPath(accountId)),
          // Drawn `←  Account A-11488`. The account it exits to, named — the
          // same shape the move wizards' back arrow takes.
          label:
            data?.account_no != null && data.account_no !== ""
              ? t("customers.account.closeOut.backToNumbered", {
                  account: data.account_no,
                  defaultValue: "Account {{account}}",
                })
              : t("customers.account.closeOut.back", { defaultValue: "Back to the account" }),
        }}
      />

      {/* ── 1 · THE ACCOUNT YOU ARE CLOSING — nine drawn rows, in order ────── */}
      <Panel as="section" className="mb-4">
        <h2 className="mb-2 text-base font-semibold">
          {t("customers.account.closeOut.whoTitle", {
            defaultValue: "The account you are closing",
          })}
        </h2>
        <div>
          <Fact
            label={t("customers.account.closeOut.accountNoLabel", {
              defaultValue: "Account number",
            })}
          >
            {data?.account_no ?? detail?.account_no ?? <Blank t={t} />}
          </Fact>
          <Fact label={t("customers.accounts.col.name")}>{detail?.name ?? <Blank t={t} />}</Fact>
          <Fact
            label={t("customers.account.closeOut.customerNoLabel", {
              defaultValue: "Customer number",
            })}
          >
            {detail?.customer_no ?? <Blank t={t} />}
          </Fact>
          <Fact
            label={t("customers.account.closeOut.categoryLabel", { defaultValue: "Category" })}
          >
            {category === null ? (
              <Blank t={t} />
            ) : detail?.account_subtype_name != null && detail.account_subtype_name !== "" ? (
              `${category} · ${detail.account_subtype_name}`
            ) : (
              category
            )}
          </Fact>
          <Fact
            label={t("customers.account.closeOut.statusNowLabel", { defaultValue: "Status now" })}
          >
            {detail === undefined ? (
              <Blank t={t} />
            ) : behaviour === "" ? (
              accountStatusLabel(detail, t)
            ) : (
              `${accountStatusLabel(detail, t)} · ${behaviour}`
            )}
          </Fact>
          {/* BR-MET-1161 — the address is the PREMISES', walked to. This screen
              declares no address of its own and composes nothing a screen
              elsewhere could disagree with: `premise` is the street line and
              `premise_locality` the town, both served by the same walk. */}
          <Fact label={t("customers.account.field.serviceAddress")}>
            {detail?.premise == null || detail.premise === "" ? (
              <Blank t={t} />
            ) : (
              [
                detail.premise,
                detail.premise_locality?.city ?? null,
                detail.premise_locality?.state ?? null,
                detail.premise_locality?.postal_code ?? null,
              ]
                .filter((part): part is string => part !== null && part !== "")
                .join(", ")
            )}
          </Fact>
          <Fact label={t("customers.moveOut.field.unit")}>
            {detail?.unit_label ?? <Blank t={t} />}
          </Fact>
          {/* B14 rule 31 — the badges, never the service CODES the wire carries. */}
          <Fact label={t("customers.accounts.col.services")}>
            {detail === undefined ? (
              <Blank t={t} />
            ) : (
              <AccountServiceChips services={detail.services ?? []} meters={[]} t={t} />
            )}
          </Fact>
          <Fact label={t("customers.account.closeOut.openedLabel", { defaultValue: "Opened" })}>
            {date(detail?.opened_at)}
          </Fact>
        </div>
        {/* B14 rule 32 — ONE sentence for this section, at rule 33's cap. The
            drawing's paragraph explains WHY the screen exists, and rationale is
            zero words on screen; what a clerk needs is the fact. */}
        <Note className="mt-3">
          {t("customers.account.closeOut.cutIsNotClosed", {
            defaultValue: "A cut account is still open. It still owes money.",
          })}
        </Note>
      </Panel>

      {/* ── 2 · WHAT WAS CUT, AND WHEN — seven drawn rows, in order ────────── */}
      <Panel as="section" className="mb-4">
        <h2 className="mb-2 text-base font-semibold">
          {t("customers.account.closeOut.cutTitle", { defaultValue: "What was cut, and when" })}
        </h2>
        <div>
          <Fact
            label={t("customers.account.closeOut.caseLabel", {
              defaultValue: "Disconnection case",
            })}
          >
            {data?.case_no ??
              t("customers.account.closeOut.caseUnnumbered", { defaultValue: "no reference" })}
          </Fact>
          <Fact
            label={t("customers.account.closeOut.cutReasonLabel", { defaultValue: "Reason" })}
          >
            {data?.cut_reason != null && data.cut_reason !== "" ? (
              data.cut_reason
            ) : (
              <Blank t={t} />
            )}
          </Fact>
          <Fact
            label={t("customers.account.closeOut.servicesCutLabel", {
              defaultValue: "Services cut",
            })}
          >
            {data?.services_cut != null && data.services_cut.length > 0 ? (
              <AccountServiceChips services={data.services_cut} meters={[]} t={t} />
            ) : (
              <Blank t={t} />
            )}
          </Fact>
          <Fact label={t("customers.account.closeOut.cutOnLabel", { defaultValue: "Cut on" })}>
            {date(data?.cut_on)}
          </Fact>
          {/* Billing has no invoices table, so this screen genuinely cannot
              know either figure. A dash reads as "nothing" and `$0.00` would be
              invented money (CLAUDE.md hard rule 2) — so both are STATED. */}
          <Fact
            label={t("customers.account.closeOut.finalBillLabel", {
              defaultValue: "Final metered bill",
            })}
          >
            <NotRecorded
              label={t("customers.account.closeOut.notServed", { defaultValue: "not served" })}
              why={t("customers.account.closeOut.notServedWhy", {
                defaultValue:
                  "The final bill is raised by billing on its own cycle. This screen prices nothing and shows no figure it was not given.",
              })}
              ruleRef="BR-CUS-031"
            />
          </Fact>
          <Fact
            label={t("customers.account.closeOut.baseSinceLabel", {
              defaultValue: "Base charges since",
            })}
          >
            {t("customers.account.closeOut.baseSinceValue", {
              defaultValue: "None — they stop at the cut",
            })}
          </Fact>
          {/* ⚠ **THROUGH `MoneyCell`, AND THE CURRENCY IS THE REASON.** This
              row printed `data.balance.display` as a bare string, so a clerk
              read `8240.00` where every other money in this product — and the
              drawing on blueprint p108 — reads `$8,240.00`. The server sends
              `currency` in the same payload and nothing used it. `MoneyCell` is
              the kit's one formatter (it is what closed `DEF-088`) and it reads
              the 4 dp `stored` figure and displays 2, which is CLAUDE.md hard
              rule 2 rather than a re-rounding of `display`.
              **The null case is untouched and stays a sentence**: a balance that
              could not be read is never `$0.00`, because a fabricated zero on
              an account in arrears looks exactly like a settled one
              (DEF-127 / DEF-628). */}
          <Fact
            label={t("customers.account.closeOut.balanceLabel", {
              defaultValue: "Outstanding balance",
            })}
          >
            {data?.balance == null ? (
              t("customers.account.closeOut.balanceUnreadable", {
                defaultValue: "could not be read",
              })
            ) : (
              <>
                <MoneyCell amount={data.balance.stored} currency={data.currency} />
                {/* The drawn *"unchanged since the cut"* is a COMPARISON, made
                    only where the screen holds both figures. Where it does not,
                    it says nothing rather than asserting it. */}
                {data.outstanding_at_cut != null &&
                data.outstanding_at_cut.stored === data.balance.stored ? (
                  <span className="ml-2 text-sm font-normal opacity-60">
                    {t("customers.account.closeOut.unchangedSinceCut", {
                      defaultValue: "unchanged since the cut",
                    })}
                  </span>
                ) : null}
              </>
            )}
          </Fact>
        </div>
      </Panel>

      {blocker ? (
        /* The clerk reads why they are refused, in six-word sentences. The
           server's paragraph rides on `title` as evidence (B14 rule 31). Before
           `DEF-CUS-5087` this strip printed that paragraph, rule ids and all,
           and the commit sat disabled beside it with no reason a clerk could
           act on. */
        <RefusalStrip as="div" className="mb-4" title={blocker.detail}>
          {blockerSentence(t)[blocker.code] ??
            t("customers.account.closeOut.blockedUnworded", {
              defaultValue: "This account cannot be closed out yet.",
            })}
        </RefusalStrip>
      ) : null}

      {/* ── 3 · WHAT YOU ARE RECORDING — the drawn three fields ────────────── */}
      <Panel as="section" className="mb-4">
        <h2 className="mb-2 text-base font-semibold">
          {t("customers.account.closeOut.actTitle", { defaultValue: "What you are recording" })}
        </h2>
        <label className="mb-3 block">
          <span className="mb-1 block text-sm opacity-80">
            {t("customers.account.closeOut.onLabel", {
              defaultValue: "Closing this account out on",
            })}
            <span aria-hidden="true"> *</span>
          </span>
          <input
            type="date"
            value={closedOutOn}
            disabled={!data?.eligible}
            required
            onChange={(event) => setClosedOutOn(event.target.value)}
            className="w-full border px-2 py-1"
          />
          {/* B14 rule 38 — help sits under its input, which is how this product
              builds a form whatever a drawing does with it. */}
          <span className="mt-1 block text-sm opacity-60">
            {t("customers.account.closeOut.onHelp", {
              defaultValue: "Today, or the day you decided.",
            })}
          </span>
        </label>
        <label className="mb-3 block">
          <span className="mb-1 block text-sm opacity-80">
            {t("customers.account.closeOut.reasonLabel", { defaultValue: "Why" })}
            <span aria-hidden="true"> *</span>
          </span>
          <textarea
            value={reason}
            rows={3}
            disabled={!data?.eligible}
            required
            onChange={(event) => setReason(event.target.value)}
            className="w-full border px-2 py-1"
          />
          <span className="mt-1 block text-sm opacity-60">
            {t("customers.account.closeOut.reasonHelp", {
              defaultValue: "A sentence, in your own words.",
            })}
          </span>
        </label>
        {/* ⚠ **THE DRAWING PUTS A SELECT HERE AND THIS IS A FACT, DELIBERATELY.**
            The blueprint draws `Status it takes  Closed ▼`. `CloseOutRequest`
            does carry an optional `status`, and naming one here would decide
            for a tenant: BR-CUS-055's statuses are TENANT-EXTENSIBLE and the
            server picks that tenant's own seeded terminal one. A select offering
            this product's guess at their vocabulary is the `MoveOutWizard`
            exception restated — so the row keeps its drawn LABEL and states
            what will happen instead of pretending to choose it. */}
        <Fact
          label={t("customers.account.closeOut.statusTakesLabel", {
            defaultValue: "Status it takes",
          })}
        >
          {t("customers.account.closeOut.statusTakesValue", {
            defaultValue: "A terminal status",
          })}
        </Fact>
        {/* B14 rule 32 — a stated absence is a `<details>` CLOSED by default. */}
        <details className="mt-3">
          <summary className="cursor-pointer text-sm">
            {t("customers.account.closeOut.reasonListSummary", {
              defaultValue: "No reason list",
            })}
          </summary>
          <p className="mt-2 text-sm">
            {t("customers.account.closeOut.reasonHint", {
              defaultValue: "Your words are saved. No report can count them.",
            })}
          </p>
        </details>
      </Panel>

      {/* ── 4 · WHAT PRESSING THIS WRITES — the drawn five rows ────────────── */}
      <Panel as="section" className="mb-4">
        <h2 className="mb-2 text-base font-semibold">
          {t("customers.account.closeOut.writesTitle", {
            defaultValue: "What pressing this writes",
          })}
        </h2>
        {/* BR-CUS-431 — the date is shown BEFORE it is written, because it is
            the one thing here that no correction row can un-say. */}
        <PlainTable>
          <thead>
            <tr>
              <th>{t("customers.account.closeOut.col.what", { defaultValue: "What" })}</th>
              <th>{t("customers.account.closeOut.col.value", { defaultValue: "Value" })}</th>
              <th>{t("customers.account.closeOut.col.whyThat", { defaultValue: "Why that" })}</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>
                {t("customers.account.closeOut.writes.dateWhat", {
                  defaultValue: "The date the account closed",
                })}
              </td>
              <td>{date(data?.closed_at_will_be)}</td>
              <td>
                {t("customers.account.closeOut.writes.dateWhy", {
                  defaultValue: "The cut date, not today",
                })}
              </td>
            </tr>
            <tr>
              <td>
                {t("customers.account.closeOut.writes.statusWhat", {
                  defaultValue: "The account's status",
                })}
              </td>
              <td>
                {t("customers.account.closeOut.statusTakesValue", {
                  defaultValue: "A terminal status",
                })}
              </td>
              <td>
                {t("customers.account.closeOut.writes.statusWhy", {
                  defaultValue: "Terminal at last",
                })}
              </td>
            </tr>
            <tr>
              <td>
                {t("customers.account.closeOut.writes.agreementsWhat", {
                  defaultValue: "Every open service agreement",
                })}
              </td>
              <td>{date(data?.closed_at_will_be)}</td>
              <td>
                {t("customers.account.closeOut.writes.agreementsWhy", {
                  defaultValue: "The day service actually stopped",
                })}
              </td>
            </tr>
            <tr>
              <td>
                {t("customers.account.closeOut.writes.caseWhat", {
                  defaultValue: "The disconnection case",
                })}
              </td>
              <td>
                {t("customers.account.closeOut.writes.caseValue", { defaultValue: "Closed out" })}
              </td>
              <td>
                {t("customers.account.closeOut.writes.caseWhy", {
                  defaultValue: "Today's date and your name",
                })}
              </td>
            </tr>
            <tr>
              <td>
                {t("customers.account.closeOut.writes.recordWhat", {
                  defaultValue: "The record of the act",
                })}
              </td>
              <td>
                {t("customers.account.closeOut.writes.recordValue", { defaultValue: "One row" })}
              </td>
              <td>
                {t("customers.account.closeOut.writes.recordWhy", {
                  defaultValue: "Closed out, never closed",
                })}
              </td>
            </tr>
          </tbody>
        </PlainTable>
        {data?.dunning_if_closed ? (
          /* B14 rule 11's consequence, DERIVED from the three structured fields
             the server already sends — never its `reason` prose, which names
             BR-CUS-082 and quotes the PO. `will_restart === null` is the third
             state DEF-628 created and is NOT "no ladder": it means the balance
             could not be read, and saying "chasing stops" over it would be a
             clearance nobody computed. */
          <Note className="mt-3" title={data.dunning_if_closed.reason}>
            {data.dunning_if_closed.will_restart === null
              ? t("customers.account.closeOut.dunningUnread", {
                  defaultValue: "The balance could not be read.",
                })
              : data.dunning_if_closed.will_restart
                ? t("customers.account.closeOut.dunningRestarts", {
                    defaultValue: "A debt survives this closure. Chasing starts again.",
                  })
                : t("customers.account.closeOut.dunningStops", {
                    defaultValue: "Nothing is owed. Chasing stops here.",
                  })}
          </Note>
        ) : null}
      </Panel>

      {/* ── 5 · WHAT IT WILL NOT DO — the drawn five rows ──────────────────── */}
      <Panel as="section" className="mb-4">
        <h2 className="mb-2 text-base font-semibold">
          {t("customers.account.closeOut.notDoTitle", { defaultValue: "What it will not do" })}
        </h2>
        <PlainTable>
          <tbody>
            <tr>
              <td>
                {t("customers.account.closeOut.notDo.readWhat", {
                  defaultValue: "Take a final read",
                })}
              </td>
              <td>
                {t("customers.account.closeOut.notDo.read", {
                  defaultValue: "No. It was read at the cut.",
                })}
              </td>
            </tr>
            <tr>
              <td>
                {t("customers.account.closeOut.notDo.depositWhat", {
                  defaultValue: "Settle the deposit",
                })}
              </td>
              <td>
                {t("customers.account.closeOut.notDo.deposit", {
                  defaultValue: "No. That is the payments side.",
                })}
              </td>
            </tr>
            <tr>
              <td>
                {t("customers.account.closeOut.notDo.debtWhat", {
                  defaultValue: "Decide where the debt goes",
                })}
              </td>
              <td>
                {t("customers.account.closeOut.notDo.debt", {
                  defaultValue: "No. Not on this screen.",
                })}
              </td>
            </tr>
            <tr>
              <td>
                {t("customers.account.closeOut.notDo.moveOutWhat", {
                  defaultValue: "Write a move-out record",
                })}
              </td>
              <td>
                {t("customers.account.closeOut.notDo.moveOut", {
                  defaultValue: "No. This was not a move.",
                })}
              </td>
            </tr>
            <tr>
              <td>
                {t("customers.account.closeOut.notDo.balanceWhat", {
                  defaultValue: "Clear the balance",
                })}
              </td>
              <td>
                {t("customers.account.closeOut.notDo.balance", {
                  defaultValue: "No. The balance survives it.",
                })}
              </td>
            </tr>
          </tbody>
        </PlainTable>
      </Panel>

      {failure ? (
        <RefusalStrip as="div" className="mb-4">
          {failure}
        </RefusalStrip>
      ) : null}

      {/* The drawn footer: the way back on the left, the commit on the right. */}
      <div className="mb-6 flex items-center justify-between gap-4">
        <InlineLinkTo to={tenantPath(accountDetailPath(accountId))}>
          {t("customers.account.closeOut.back", { defaultValue: "Back to the account" })}
        </InlineLinkTo>
        {/* B14 rule 6 — the DANGER tier, because this is a destructive commit
            that cannot be undone by an edit (hard rule 4). */}
        <Button
          variant="danger"
          disabled={!ready || commit.isPending}
          onClick={() => {
            setFailure(null);
            commit.mutate();
          }}
        >
          {t("customers.account.closeOut.commit", { defaultValue: "Close out this account" })}
        </Button>
      </div>

      {/* ── 6 · WHEN IT REFUSES — the drawn six, as a reference ────────────── */}
      <Panel as="section" className="mb-4">
        <h2 className="mb-2 text-base font-semibold">
          {t("customers.account.closeOut.refusesTitle", { defaultValue: "When it refuses" })}
        </h2>
        {/* ⚠ **THE DRAWN SENTENCES ARE NOT COPIED, AND THE REASON IS A SIGNED
            RULE.** Four of the six run past B14 rule 33's six-word cap — *"Enter
            the date you are closing this account out."* is nine. The `IF` column
            is the drawing's, word for word; the answer column is this product's
            own wording, which `DEF-CUS-5087` wrote to that cap on 2026-09-12,
            and the three LIVE blockers read from the very same map the refusal
            strip above uses — so a clerk cannot be told one thing here and
            another there. */}
        <PlainTable>
          <thead>
            <tr>
              <th>{t("customers.account.closeOut.col.if", { defaultValue: "If" })}</th>
              <th>
                {t("customers.account.closeOut.col.told", { defaultValue: "What you are told" })}
              </th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>
                {t("customers.account.closeOut.refuses.alreadyClosed", {
                  defaultValue: "The account is already closed",
                })}
              </td>
              <td>{blockerSentence(t).already_terminal}</td>
            </tr>
            <tr>
              <td>
                {t("customers.account.closeOut.refuses.stillThere", {
                  defaultValue: "They still live there",
                })}
              </td>
              <td>{blockerSentence(t).still_occupying}</td>
            </tr>
            <tr>
              <td>
                {t("customers.account.closeOut.refuses.neverCut", {
                  defaultValue: "The supply was never cut",
                })}
              </td>
              <td>{blockerSentence(t).not_a_cut_account}</td>
            </tr>
            <tr>
              <td>
                {t("customers.account.closeOut.refuses.beforeCut", {
                  defaultValue: "Your date is before the cut",
                })}
              </td>
              <td>
                {t("customers.account.closeOut.refuses.beforeCutTold", {
                  defaultValue: "Not earlier than the cut date.",
                })}
              </td>
            </tr>
            <tr>
              <td>
                {t("customers.account.closeOut.refuses.noDate", {
                  defaultValue: "You left the date empty",
                })}
              </td>
              <td>
                {t("customers.account.closeOut.refuses.noDateTold", {
                  defaultValue: "Enter the date you are closing.",
                })}
              </td>
            </tr>
            <tr>
              <td>
                {t("customers.account.closeOut.refuses.noReason", {
                  defaultValue: "You left the reason empty",
                })}
              </td>
              <td>
                {t("customers.account.closeOut.refuses.noReasonTold", {
                  defaultValue: "Say why it is being closed.",
                })}
              </td>
            </tr>
          </tbody>
        </PlainTable>
      </Panel>

      <Panel as="section">
        <h2 className="mb-2 text-base font-semibold">
          {t("customers.account.closeOut.absencesTitle", {
            defaultValue: "What this screen is not telling you",
          })}
        </h2>
        {/* B14 rule 32 — a stated absence is a `<details>` CLOSED by default.
            Four of them open on arrival is four paragraphs a clerk did not ask
            for on the screen that ends a customer's account. */}
        <details>
          <summary className="cursor-pointer text-sm">
            {/* ⚠ NOT "Four things…". The server decides how many absences it
                sends and a hand-typed count is wrong the day it changes a
                fifth — the skill's own rule 12, and the same hazard as the
                eleventh service. Two words, under rule 33's label cap, and
                true at any length. */}
            {t("customers.account.closeOut.absencesSummary", {
              defaultValue: "Not checked",
            })}
          </summary>
          <ul className="m-0 mt-2 list-none p-0">
            {(data?.absences ?? []).map((absence) => (
              <Absence key={absence.code} absence={absence} t={t} />
            ))}
          </ul>
        </details>
      </Panel>
    </>
  );
}

export default CloseOutPage;

// ── Lifecycle ─────────────────────────────────────────────
// packet: DEF-724 (PO ruling 2026-08-27) · BR-CUS-430 / BR-CUS-431 · CR-094-BRC01 lane A (the blueprint, pages 107–111)
// generated: 2026-08-27 by the close-out lane · AMENDED 2026-09-13 by lane A — built to the drawing
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=OWED(no story owns this screen — law 8)
// exceptions: the eligibility decision is the SERVER's and is never re-derived here — a screen that decided BR-CUS-430 itself would be a second implementation free to drift · `closed_at` is rendered as a FACT and is not an input, because BR-CUS-431 derives it and a field that could name it is a field that could get it wrong · the balance renders through `MoneyCell` or the words "could not be read" and NEVER `$0.00` — a fabricated zero on an account in arrears looks exactly like a settled one (DEF-127/DEF-628) · the drawn `Status it takes` SELECT is rendered as a FACT: BR-CUS-055's statuses are tenant-extensible and the server picks the tenant's own seeded terminal one, so a select here would offer this product's guess at their vocabulary · the drawn commit label *"Record the close-out"* is NOT used, because the drawing's second screen (`?confirm=1`) does not exist (`DEF-CUS-5162`) and one press here is irreversible — the button says what it does · four of the six drawn refusal sentences run past B14 rule 33's cap and the screen uses this product's own wording, from the same map the live refusal strip reads · the final metered bill and the base charges since the cut are STATED as not served — billing has no invoices table and a figure here would be invented money · the four stated absences are RENDERED, not summarised: OQ-680 (no clearance was performed), OQ-830 (the reason has no fixed list), BR-CUS-097 (nothing is tied back to a master here) and BR-CUS-107 (the `Disconnected` status is still assigned by nothing) · every new copy key carries a `defaultValue` because lanes may not edit the eleven catalogues; the keys are REPORTED for the translation lane
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
