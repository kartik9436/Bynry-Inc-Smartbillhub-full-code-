// ── Trace ──────────────────────────────────────────────
// Change:   CR-110-BRC04 wave A — THE CONNECTOR SET-UP SCREEN. S147 · INT-07,
//           at `/:tenant/settings/connectors/:providerKey/configure`.
//           Before this wave the address returned the product's *not built
//           yet* page; no URLconf declared it.
// Rules:    BR-INT-037 (adding a connector is DATA, not code — one component
//           rendered 28 ways from the manifest) · BR-INT-026 (production and
//           sandbox are two connection ROWS, unique on tenant+key+environment)
//           · BR-INT-043 (the field slot is a CLOSED vocabulary of kinds with
//           no provider branch) · BR-INT-003 (a secret is typed once; the hint
//           is all a screen holds) · B14 rule 40 (the page title is 32px) ·
//           rule 38 (where the drawing and our UI rules disagree about how a
//           FORM is built, the UI rules win) · rule 33 (a label ≤ 3 words, a
//           fact ≤ 6, an instruction ≤ 6 per sentence, rationale ZERO) ·
//           rule 32 (one sentence per section; no rule id in clerk copy) ·
//           rule 31 (no database id is a visible value) · rule 21 (Tailwind
//           utilities; this file is on route-b-migrated.txt) · rule 36 (layout
//           and detail from the document, visual style from r10, the kit is
//           how you comply).
// Drawing:  `05-prototype/05 Integration Blueprint.pdf`, read AS IMAGES at
//           scale 2 (B14 rule 42, and the PO's standing instruction this
//           session — *"I want you to use images only to create screens"*).
//           Frames: CFG-02 p024 (a vendor sign-in) · CFG-06 p034–035 (sixteen
//           operations, the `…8 more` case) · CFG-10 p045–046 (the fullest
//           form there is) · CFG-23 p079–080 (a file channel, a mapping
//           editor, choice fields) · CFG-28 p091 (still generic + coming soon).
// Tests:    src/features/integrations/ConnectorSetupRoute.test.tsx — the route
//           by ADDRESS and by the connector it opens.
// ───────────────────────────────────────────────────────
//
// ⚠ **ONE SCREEN, TWENTY-EIGHT CONNECTORS, AND NO VENDOR IS NAMED IN THIS
// FILE.** That is not tidiness, it is the deliverable: `BR-INT-037` says a
// connector is a ROW and a 29th next year adds no table, no column and no
// screen code. Everything vendor-specific below — the kicker's words, the
// title, the summary, the fields and their kinds, the operations and their
// directions — is read off `ProviderCard`, which is read off a manifest file.
// `ConnectorSetupRoute.test.tsx`'s last case asserts this directly by opening
// the address for a vendor nobody has written: the screen must still render.
//
// ══════════════════════════════════════════════════════════════════════════
// WHAT THE DRAWING SHOWS THAT THIS SCREEN DELIBERATELY DOES NOT BUILD
// ══════════════════════════════════════════════════════════════════════════
// Every one is a PO ruling of 2026-09-16, recorded with their words in
// `12-governance/change-requests/CR-110-BRC04-connectors.md`. They are written
// out here because **an absence is invisible to every check this repo has** —
// a later lane holding the drawing beside this screen must find the reason in
// writing rather than file it as a defect.
//
//  1. **The Token panel, in full** — *Token address*, *Scope*'s blank-means-
//     everything help, *Generate token*, every expiry, renewal and
//     re-authorise path, and the word *token* itself. PO: *"i only want to
//     issue a key per conenction … i dont understand the differnt between key
//     and token"*. Measured over all 18 manifests: ten take a key the vendor
//     gave us, two issue one of ours, **none does both** — so one credential
//     per connection is right and the two-panel form was a misreading of it.
//  2. **The clock box** — the *Time* field and its *Your time zone. The only
//     part you choose.* PO: *"conenctor i a conenctor not a logic to to ETL"*.
//     Scheduling moved to Runbooks, so the box's owner left the module.
//     ⚠ **AND ITS WHOLE PANEL WENT WITH IT** — see `WHEN IT RUNS` below.
//  3. **A clerk control on the call limit.** PO: *"so wecant allow clark to
//     reset it … keep the check in code - thats it"*. The limit is a value in
//     a cell. There is no input and no Save for it anywhere on this screen.
//  4. **The usage count** — *Calls used this week — 4,180 of 10,000*. Drawn on
//     p017 and argued for well; not ruled. Recorded as a candidate, unbuilt.
//  5. **The card-page choice** — *hosted by them | embedded*, drawn on CFG-10.
//     PO: *"A · their page only"*. ⚠ **IT NEEDS NO CODE HERE AND THAT IS THE
//     POINT**: the field slot renders what a manifest declares, so a field no
//     manifest declares cannot appear. There is no disabled control and no
//     *coming soon* note, because a tenant must not be able to reach it at all.
//  6. **The refusal strips' trailing references** — the drawing ends two of
//     them *"See CR-3 and CR-11"* and *"see RAN-2"*. B14 rule 32: no rule id
//     or internal code in clerk-facing copy. The sentences ship; the pointers
//     do not.
//  7. **Fields two to a row.** CFG-10 and CFG-23 draw `Merchant ID` beside
//     `Merchant secret`. B14 rule 38 names side-by-side fields as CONSTRUCTION
//     rather than layout and hands it to our UI rules, which is one labelled
//     row per field — the shape every other form in this product uses.
//
// ⚠ **THE `When it runs` PANEL IS THE EMPTY REGION, REPORTED RATHER THAN
// FILLED.** Take the clock box away and the drawn panel holds one sentence —
// *"13 of 16 run on a clock. The rest are started by a person, by a queue, or
// by them."* — which is the WHEN column of the table above it, aggregated. A
// panel whose only control has moved to another module and whose only
// remaining sentence restates the row above is a heading over nothing, so it
// is not drawn. **The connection's `cadence` is untouched**: it is shipped,
// read, and belongs to the Runbooks hand-over the PO put out of scope today.
//
// ══════════════════════════════════════════════════════════════════════════
// WHAT IS DRAWN, HAS NO STORE BEHIND IT YET, AND IS THEREFORE NOT INVENTED
// ══════════════════════════════════════════════════════════════════════════
// `RATE LIMIT` is a column the drawing puts on all 78 operation rows and
// nothing in this product stores. It renders as an honest absence until the
// back-end lane's `rate_limit` row lands — a dash, never a number, because
// B14 rule 37 says every figure drawn in a wireframe is an ILLUSTRATION and
// `120 / min` is a shape rather than a ceiling. `BR-INT-018`'s *a dash is not
// a zero* is the same instinct one module over. The moment the field is
// served, `rateLimitText` below reads it and the column fills with no edit here.
//
// ⚠ **THE COLUMN IS DRAWN ANYWAY, AND `DEF-INT-5487` IS WHY.** The blueprint
// PDF is horizontally clipped — the right-hand column of all 56 connector
// frames is absent from the file's own content stream, and the API table's
// last header text-extracts as `RATE LIMIT T`, the **TEST** column truncated to
// one letter. A lane building this table from the renders alone builds it one
// column short and never knows. Both columns are here.
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate, useParams } from "react-router-dom";

import { api, isApiError } from "@/api/client";
import { refusalText } from "@/api/refusalText";
import {
  connectIntegration,
  getIntegrationsGrid,
  issuePartnerKey,
  startOAuth,
  updateIntegration,
} from "@/api/integrationsEndpoints";
import type {
  IntegrationsGrid,
  ManifestField,
  OperationRow,
  ProviderCard,
} from "@/api/integrationsEndpoints";
import { queryKeys } from "@/api/queryClient";
import { Button } from "@/components/Button";
import { Panel } from "@/components/Panel";
import { PageHeader } from "@/components/PageHeader";
import { RefusalStrip, PlainTable } from "@/components/Surfaces";
import { Switch } from "@/components/Switch";
import { SegmentedControl } from "@/components/SegmentedControl";
import { FailedWithRetry, LoadingSkeleton } from "@/components/StateFrame";
import { useToast } from "@/components/Toast";
import { useTenantPath } from "@/routing/tenantPath";

import { RENDER, fieldLabel, testableOperation } from "./ConnectModal";
import { FieldGroupPanel, fieldGroups } from "./FieldGroupPanel";

/** Where the back link goes. The GRID keeps its shipped address: the 16 Sep
 *  route ruling leaves `settings/integrations` alone because changing it
 *  breaks every bookmark to buy a word in a place nobody reads for meaning.
 *  The visible word is *Connectors* either way, which is the half that matters. */
const GRID_ROUTE = "/settings/integrations";

/**
 * The manifest field whose blank means *any address may call*.
 *
 * ⚠ **A FIELD NAME AND NOT A PROVIDER KEY**, so `G77` is satisfied and the six
 * manifests that declare it — the five ERPs and the kiosk — share one sentence
 * without this screen knowing any of their names (`BR-INT-037`).
 */
const ALLOWLIST_FIELD = "allowed_addresses";

/** The drawing lists eight operation rows and then `…N more` (CFG-06 p035).
 *  Sixteen rows of a meter head-end is a wall; eight is a page. */
const ROWS_BEFORE_MORE = 8;

/** ⚠ ONE character for *nothing is recorded here*, filled in one place. The
 *  WHEN cell used an em-dash and the RATE LIMIT cell an en-dash, side by side
 *  on the same row, which reads as two different meanings and is one. It is a
 *  DASH and not a zero, deliberately (`BR-INT-018`): *not set* and *none* are
 *  different sentences and only one of them is reassuring. */
const EMPTY = "—";

/** The kinds a secret is typed into — `BR-INT-003`, the value is typed once
 *  and a screen never holds more than its hint. The list is a subset of the
 *  closed `FieldKind` vocabulary, so it cannot drift into naming a kind that
 *  does not exist. */
const SECRET_KINDS: readonly string[] = ["secret"];

/** The drawing's own words for each `trigger`, in its own order (CFG-02 p024,
 *  CFG-10 p046). Written here rather than left to `t()`'s key-as-fallback,
 *  which is precisely how `ACCOUNTING · OUT.THEM` reached a clerk. */
const TRIGGER_WORDS: Record<string, string> = {
  scheduled: "On a schedule",
  manual: "On demand",
  dispatcher: "By a bill run",
  // ⚠ **BOTH PARTNER-INITIATED TRIGGERS SAY THE SAME FIVE WORDS, AND THE
  // DRAWING IS WHERE THAT COMES FROM (`DEF-INT-5493`).** p064 and p066 both
  // put `They call us` in the WHEN column — on the sandbox's `webhook` row and
  // on Aclarian's three `partner` rows alike. This screen had invented a third
  // vocabulary (*When they send* / *When they ask*) beside the run history's
  // (*They called us* / *A partner*), so the same operation answered the same
  // question in two different words on two screens. The run HISTORY keeps its
  // own past-tense words, because there the question is what started a run
  // that already happened; here it is when this API runs.
  webhook: "They call us",
  partner: "They call us",
  inline: "While you wait",
};

type Environment = "production" | "sandbox";

const ENVIRONMENTS: readonly Environment[] = ["production", "sandbox"];

/**
 * The kicker's words: the CATEGORY, then EVERY direction this connector has a
 * door for — `PAYMENTS · WE COLLECT · WE SEND` on CFG-10.
 *
 * ⚠ **IT IS A UNION AND NOT THE FIRST OPERATION'S PAIR, WHICH IS WHAT THE CARD
 * DOES AND IS WRONG.** `Manifest.kicker` returns the first operation's
 * `(direction, initiative)` only, so a two-door vendor wears one word: the
 * grid shows *Bulk email service* as `EMAIL · WE SEND` while `CFG-04` draws
 * `EMAIL · WE SEND · THEY SEND`. Four of eighteen manifests span two doors
 * today and the blueprint says nine of twenty-eight after phase 1. The fix is
 * a union over `operations[]`, where `BR-INT-028` already puts the fact —
 * never a branch on a provider.
 */
function kickerWords(card: ProviderCard, word: (key: string, fallback: string) => string): string {
  const doors: string[] = [];
  for (const operation of card.operations) {
    const key = `${operation.direction}.${operation.initiative}`;
    if (!doors.includes(key)) {
      doors.push(key);
    }
  }
  const category = word(
    `integrations.category.${card.category}`,
    card.category.replace(/_/g, " "),
  );
  return [category, ...doors.map((door) => doorWord(door, word))].join(" · ").toUpperCase();
}

/**
 * `We send` · `We collect` · `They send` — ONE function, used by the DIRECTION
 * column AND by the kicker above. Two facts on the operation, one word to a
 * clerk (`BR-INT-028`).
 *
 * ⚠ **THE WRITTEN FALLBACK IS THE POINT, AND ITS ABSENCE WAS A LIVE DEFECT
 * A TEST COULD NOT HAVE SEEN (`DEF-INT-5491`).** The kicker used to build its
 * own key and hand `t()` the KEY as the fallback, so with no catalogue line the
 * Third-party GL header read **`ACCOUNTING · OUT.THEM`** — a raw enum pair,
 * uppercased, to a clerk. B14 rule 32 forbids an internal code in clerk-facing
 * copy and rule 31 is the same instinct about ids. Every assertion passed:
 * `tsc` was clean, the route test was green, and the walkthrough's own
 * *"no rule id reaches the clerk"* check does not match a bare enum. **It was
 * found by looking at the screenshot**, which is hard-won law 6 exactly.
 */
function doorWord(door: string, word: (key: string, fallback: string) => string): string {
  const [direction, initiative] = door.split(".");
  // ⚠ **FOUR QUADRANTS NEED FOUR WORDS, AND THIS HAD THREE (`DEF-INT-5536`).**
  // The old fallback collapsed `out · them` and `in · them` into *They send*,
  // so an Aclarian row read **"Read payments · They send"** — a row
  // contradicting itself in four words — while the kiosk, which genuinely IS
  // `in · them`, read correctly. One connector proves nothing about a
  // four-quadrant rule; the kiosk and an ERP side by side prove it.
  //
  // ⚠ **AND `integrations.door.*` IS DECLARED IN NO CATALOGUE**, in any of the
  // eleven — so every call fell through to the fallback and the fallback was
  // the whole implementation. `integrations.kicker.{initiative}.{direction}`
  // has all four, in all eleven, and is what the CONNECTION view already
  // reads. The product held the right answer and this screen wrote its own.
  const fallback =
    initiative === "them"
      ? direction === "out"
        ? "They read"
        : "They send"
      : direction === "in"
        ? "We collect"
        : "We send";
  return word(`integrations.kicker.${initiative}.${direction}`, fallback);
}

function directionWord(
  operation: OperationRow,
  word: (key: string, fallback: string) => string,
): string {
  return doorWord(`${operation.direction}.${operation.initiative}`, word);
}

/**
 * The RATE LIMIT cell.
 *
 * ⚠ **NOTHING SERVES THIS TODAY AND THE HONEST ANSWER IS A DASH.** The read is
 * written against the field the back-end lane will add (`rate_limit` on the
 * operation row, a row per connection AND per operation, seeded from the
 * manifest default at provisioning) so the column fills itself the day that
 * lands — hard-won law 2's *a hold that releases itself is better than a hold
 * with a good test*. It is read defensively rather than typed into
 * `OperationRow`, because declaring a field the server does not send is the
 * other half of the same lie.
 */
function rateLimitText(operation: OperationRow): number | null {
  // ⚠ **THIS READ `rate_limit`, A FIELD NO PAYLOAD HAS EVER CARRIED
  // (`DEF-INT-5550`).** ⚠ This comment cited `DEF-INT-5538` for one commit, and
  // that is a REAL ROW ABOUT SOMETHING ELSE — a sibling lane's hold-expiry
  // cases — so every id-existence check in the repo passed straight over it.
  // `DEF-2804`'s shape, corrected the same hour it was noticed. The server has served `rate_limit_per_minute` since
  // wave B and the connection view has drawn it since; this cell asked for a
  // STRING called `rate_limit` and therefore drew a dash on every row of every
  // connector, for ever. It is hard-won law 7's *structurally incapable of
  // passing*: the cast to `unknown` is exactly what stopped `tsc` objecting,
  // and a dash is a legitimate value so no assertion could tell the two apart.
  const served = operation.rate_limit_per_minute;
  return typeof served === "number" ? served : null;
}

/**
 * The endpoint under the operation's name, monospace — **AS THE SERVER
 * RESOLVED IT**, never worked out again here.
 *
 * ⚠ **THIS FUNCTION USED TO DERIVE IT, AND ANSWERED DIFFERENTLY FROM THE
 * CONNECTION VIEW ON 9 OF 91 OPERATIONS (`DEF-INT-5613`).** It read
 * `card.connection.settings[operation.host_field ?? "base_url"]` and stopped
 * there — one rung of a ladder with three. The server climbs the other two: the
 * connector's single declared address field when the operation's own names
 * nothing, then the address WE publish for a door a partner dials. So `S142`
 * printed `/partner/v1/bills` for Invoice Cloud's partner doors and for
 * Aclarian's, and `/auth/saml/acs`'s connector its metadata address, while this
 * screen printed a dash for the same operation. Nothing could see it: both are
 * strings, so `tsc` was content, and a dash is a legitimate value, so no
 * assertion could tell an absent address from a wrongly absent one.
 *
 * **The address is decided ONCE, in `apps/integrations/addressing.py`**
 * (`CR-115-BRC05` lane 1), and both screens read `OperationRow.endpoint` —
 * which is what `ConnectionDetailPage` has always done. `G128` refuses a second
 * resolver, in either language.
 *
 * ⚠ **AND THE PER-API URL LANDS IN THAT ONE PLACE TOO.** When lane 2's form
 * gives an API row its own URL, this function keeps working and needs no edit,
 * which is the whole point of the refactor.
 *
 * **No placeholder** — `api.vendor.example` is the blueprint's illustration
 * (B14 rule 37) and printing it would tell a clerk we call an address we do
 * not call.
 */
function endpointText(operation: OperationRow): string | null {
  const value = operation.endpoint;
  return typeof value === "string" && value.length > 0 ? value : null;
}

export function ConnectorSetupPage() {
  const { t } = useTranslation();
  const params = useParams<{ providerKey: string }>();
  const providerKey = params.providerKey ?? "";
  const tenantPath = useTenantPath();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const toast = useToast();

  /** `t` with a written fallback, in one place. ⚠ THE KEYS ARE NEW AND THE
   *  ELEVEN CATALOGUES ARE ANOTHER LANE'S FILE THIS HOUR (the 319-key
   *  Connector rename), so every string below names its key and carries its
   *  English. The fan-in is reported rather than done quietly here — two lanes
   *  writing the same catalogue is `DEF-1782`'s whole-file revert. */
  const word = (key: string, fallback: string): string => t(key, { defaultValue: fallback });

  const gridQuery = useQuery<IntegrationsGrid>({
    queryKey: queryKeys.integrations,
    queryFn: () => getIntegrationsGrid(api),
  });

  const card = gridQuery.data?.providers.find((one) => one.key === providerKey) ?? null;

  const [values, setValues] = useState<Record<string, string>>({});
  /**
   * ⚠ **THE FORM OPENED EMPTY ON A CONNECTED CONNECTOR (`DEF-INT-5581`).**
   * `values` started `{}` and nothing ever seeded it, so *Edit* showed blank
   * boxes over settings that were really there — and a clerk who pressed Save
   * would have written the blanks. The connection's own NON-SECRET settings
   * are already on the wire (`ConnectionRow.settings`, filtered server-side by
   * the manifest's field kinds), which is exactly what that field's docstring
   * says it is for: *"a screen that has to SET a control cannot read a
   * sentence"*.
   *
   * ⚠ **IT SEEDS ONCE AND THEN LEAVES THE FORM ALONE.** The guard is the
   * clerk's OWN state being untouched, not a ref or a mount-only effect: a
   * background refetch must never overwrite half-typed input. A secret cannot
   * arrive here — the server does not serve one — so there is nothing to
   * re-mask.
   */
  const storedSettings = card?.connection?.settings;

  /**
   * ⚠ **CLEARING A NON-EMPTY ALLOWED-ADDRESSES LIST WIDENS A SECURITY CONTROL
   * IN TWO SECONDS WITH NOTHING SAID — `OQ-INT-12398`, closed by PO ruling
   * 2026-09-17.** Three options were put: (a) a short line under the field,
   * (b) a confirmation dialog, (c) leave it. Verbatim: *"a) A short line under
   * the field when you clear it — "This allows any address." - yes okay"*.
   *
   * ⚠ **THE DIALOG WAS DECLINED DELIBERATELY AND THAT IS WHY THIS IS A LINE.**
   * The PO had just made the restriction OPTIONAL (`allowed_addresses` is
   * `required=False` on all six connectors that carry it, and
   * `runners/serve.py:allowlist_permits` has always read an empty list as
   * *permit everything*). A dialog on every clear would fight the decision it
   * follows.
   *
   * ⚠ **ONLY ON THE TRANSITION, AND THIS IS THE WHOLE DIFFICULTY.** A field
   * that was ALREADY blank when the form opened says nothing: the clerk is not
   * changing anything, and a line that sits permanently under an always-blank
   * box is noise that teaches people to stop reading lines under boxes. So the
   * *before* is read from `storedSettings` — what the SERVER sent, a fact —
   * and never from a ref or a mount-only effect, which a background refetch or
   * a re-render can silently reset.
   *
   * ⚠ **WHAT WOULD MAKE THIS RENDER WRONGLY:** keying off `values[field] === ""`
   * alone shows it on every connector that never had a list (it would be
   * ALWAYS on, which looks like working); keying off a ref set in `onChange`
   * misses a clear made by any other path and re-arms on re-render. Both are
   * tested, and both are walked in a browser — `G13` and `tsc` cannot see
   * either, because a wrong CONDITION is a live control, not a dead one.
   */
  const allowlistWasSet = String(storedSettings?.[ALLOWLIST_FIELD] ?? "").trim() !== "";
  const allowlistNowBlank = String(values[ALLOWLIST_FIELD] ?? "").trim() === "";
  const allowlistJustCleared = allowlistWasSet && allowlistNowBlank;
  useEffect(() => {
    if (storedSettings === undefined) return;
    setValues((current) => {
      if (Object.keys(current).length > 0) return current;
      const seeded: Record<string, string> = {};
      for (const [name, value] of Object.entries(storedSettings)) {
        if (value !== null && value !== undefined) seeded[name] = String(value);
      }
      return Object.keys(seeded).length > 0 ? seeded : current;
    });
  }, [storedSettings]);
  const [environment, setEnvironment] = useState<Environment>("production");
  const [expanded, setExpanded] = useState(false);
  const [refusal, setRefusal] = useState<string | null>(null);
  /**
   * ⚠ **THE BANNER SAYS *Check the highlighted fields* AND NOTHING WAS EVER
   * HIGHLIGHTED (`DEF-INT-5593`).** This screen passed a literal
   * `error: undefined` into every field slot from the day it was written
   * (`a460ebaa`, 2026-09-16), so a server refusal drew the sentence at the
   * foot of the form and left the clerk to guess WHICH of up to nine boxes it
   * meant — on a form where the answer is usually one character. The modal
   * has carried the per-field map since `US-INT-019`; this is the same shape,
   * not a second one, so the two screens cannot disagree about a refusal.
   *
   * ⚠ It is hard-won law 2's mirror: a live control making a promise nothing
   * on the screen could keep, with `tsc` and every test green — and no gate in
   * this repo reads rendered output, so it was found by pasting a bad value
   * into the running product and looking (law 6).
   */
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

  /** The banner AND the per-field map, from one refusal. */
  function takeRefusal(error: unknown): void {
    if (!isApiError(error)) {
      setRefusal(null);
      setFieldErrors({});
      return;
    }
    const perField: Record<string, string> = {};
    for (const one of error.fieldErrors) {
      if (one.field !== null) perField[one.field] = t(one.message_key, one.params ?? {});
    }
    setFieldErrors(perField);
    setRefusal(refusalText(t, error));
  }
  /** The issued key, held in component state for as long as the panel is open
   *  and never put in the query cache — `issuePartnerKey`'s own docstring says
   *  why: a cached key is a copy of a secret sitting in browser memory for the
   *  life of the tab. */
  const [issued, setIssued] = useState<string | null>(null);
  /**
   * ⚠ **WHICH APIS THE KEY MAY CALL — the control the PO asked for by name.**
   * Verbatim, 2026-09-16: *"we need to allow all apis to be read - all 4
   * currently i can select only 1 or you remove it and put selection on off
   * directly on apis"*. They offered two fixes and named the one they wanted;
   * this is it, and the `scopes` field it replaces is REMOVED from all five
   * ERP manifests in the same commit, because two controls for one fact is how
   * they come to disagree.
   *
   * `null` means *not decided on this screen yet* and is resolved below to the
   * key's own scope when one exists, or to EVERY operation when none does —
   * which is the PO's *all 4*, not an empty grant. A `Set` here would look
   * tidier and would not compare by value for React; an array of names is what
   * goes on the wire, so it is what is held.
   */
  const [scope, setScope] = useState<string[] | null>(null);

  /**
   * What the key would be issued with RIGHT NOW — the clerk's switches when
   * they have touched one, otherwise the standing answer.
   *
   * ⚠ **THE STANDING ANSWER IS THE KEY'S OWN SCOPE, NOT A DEFAULT TYPED HERE.**
   * A connector that already has a live key shows what that key reaches, so
   * re-issuing without touching a switch cannot silently widen or narrow it.
   * With no key yet, EVERY operation is on — the PO's *"we need to allow all
   * apis to be read - all 4"* — and a clerk switches off what they do not want.
   * ⚠ That is a deliberate exception to hard-won law 3, and it is safe for the
   * reason law 3 is about: the key does not exist until this screen mints it,
   * so *all* is a proposal on a form, not a permission already granted. The
   * unsafe default law 3 forbids would be a key issued by a clerk who read
   * nothing — and `machine_auth._validated_scope` still refuses an EMPTY one,
   * so switching everything off cannot mint a key that opens everything.
   */
  const liveKeyScope: string[] | null =
    (gridQuery.data?.providers
      .find((one) => one.key === providerKey)
      ?.issued_keys.find((one) => one.state === "active")?.scope ?? null) || null;
  const allOperationNames: string[] = (
    gridQuery.data?.providers.find((one) => one.key === providerKey)?.operations ?? []
  ).map((one) => one.name);
  const scopeNames: string[] = scope ?? liveKeyScope ?? allOperationNames;
  const scopeHas = (name: string): boolean => scopeNames.includes(name);
  const toggleScope = (name: string, on: boolean): void =>
    setScope(on ? [...scopeNames, name] : scopeNames.filter((one) => one !== name));

  /**
   * ── THE SECOND VISIT (`DEF-INT-5581`) ─────────────────────────────────────
   *
   * ⚠ **THIS FORM'S SAVE COULD NOT WORK ON A CONNECTOR THAT WAS ALREADY
   * CONNECTED, AND THAT IS THE PO'S OWN LIVE BLOCKER.** It posted
   * `connectIntegration` every time. Measured through the real door on
   * 2026-09-17: `POST /api/brazosbend/integrations/erp_aclarian/connect`
   * answered **`409 · BIZ-STATE · integrations.refusal.already_connected`
   * (`BR-INT-026`)**, because `services.connect_with_fields` refuses a
   * connection that is enabled or holds a live credential. For the five ERP
   * connectors the form holds exactly two fields — the allowed addresses and
   * the key we issue — so *Edit* on Aclarian MEANS *change which addresses may
   * call us*, and there was no screen in the product that could do it. That is
   * hard-won law 2's mirror: a live control leading to a refusal.
   *
   * ⚠ **`PATCH /integrations/{key}` EXISTED ALL ALONG AND NO SCREEN CALLED IT.**
   * `updateIntegration` has been in `integrationsEndpoints.ts` since wave J;
   * grepping the whole front end for it returned the declaration and its
   * tests, and no caller. The server could already do the thing the product
   * could not — law 2 in the other direction, and nothing checks whether a
   * declared endpoint has a reader.
   *
   * ⚠ **TWO VERBS, ONE SCREEN, CHOSEN BY WHETHER A CONNECTION EXISTS.** POST
   * creates and PATCH amends; there is no third case and no flag.
   *
   * ⚠ **A SECRET NEVER GOES THROUGH PATCH, AND THAT SPLIT IS NOT WIDENED
   * HERE.** `PATCH`'s own contract is non-secret settings only and
   * `update_connection` refuses a secret BY NAME; a password rotates through
   * `rotateCredential`, which S142's *Replace password* is the door to. So the
   * body below carries only the fields the manifest does NOT mark secret,
   * filtered from the manifest rather than from a list typed here
   * (`BR-INT-043`, and `G77` fails a provider-key branch).
   */
  const connected = card?.connection != null;
  const secretNames = new Set(
    (card?.fields ?? []).filter((one) => one.kind === "secret" || one.kind === "issued_secret")
      .map((one) => one.name),
  );
  const save = useMutation({
    mutationFn: () =>
      connected
        ? updateIntegration(api, providerKey, {
            config: Object.fromEntries(
              Object.entries(values).filter(([name]) => !secretNames.has(name)),
            ),
          })
        : connectIntegration(api, providerKey, {
        environment,
        // ⚠ `cadence` IS CARRIED THROUGH, NEVER CHOSEN HERE. `ConnectBody`
        // requires it and the clock ruling of 16 Sep leaves it exactly as it
        // is — shipped, read, and part of the Runbooks hand-over. This screen
        // draws no control for it and changes no value.
        cadence: card?.connection?.cadence ?? "manual",
        fields: values,
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.integrations });
      navigate(tenantPath(`${GRID_ROUTE}/${providerKey}`));
    },
    onError: (error) => {
      takeRefusal(error);
    },
  });

  /**
   * ⚠ **THE SIGN-IN BUTTON THE DRAWING PUTS UNDER THE LEAD SENTENCE, AND ITS
   * ABSENCE WAS A REAL GAP THE SCREENSHOT CAUGHT (`DEF-INT-5494`).**
   * `RENDER.redirect` draws only the sentence — in the modal, the button lives
   * in the FOOTER, which a full page does not have in the same place — so the
   * first build of this screen rendered *"You will be sent to Google Workspace
   * and brought back here"* over a form with **no way to be sent anywhere**.
   * That is hard-won law 2's mirror at its purest: a live screen making a
   * promise no control on it can keep, with every assertion green.
   *
   * ⚠ **AND IT IS WIRED TO THE REAL DOOR, NOT A NO-OP.** The first draft passed
   * `onStartOAuth: () => undefined` into the field slot because nothing called
   * it; a handler that exists and does nothing is how a dead control survives
   * a review. The redirect kind has **no Save at all** — the round trip IS the
   * save — so this button is the whole commit path for those connectors.
   */
  const signIn = useMutation({
    mutationFn: async () => {
      const started = await startOAuth(
        api,
        providerKey,
        // The browser's own return address: the front end knows its origin and
        // the server does not, and a hardcoded one would work on the demo host
        // and send every production sign-in somewhere else.
        `${window.location.origin}${window.location.pathname}`,
      );
      window.location.assign(started.authorize_url);
    },
    onError: (error) => {
      takeRefusal(error);
    },
  });

  const issue = useMutation({
    // ⚠ **THIS POSTED AN EMPTY BODY AND THE DOOR REFUSES A KEY WITH NO SCOPE
    // (`DEF-INT-5535`).** `machine_auth._validated_scope` raises
    // `REFUSAL_NO_SCOPE` on an empty list — deliberately, under hard-won law 3,
    // because *everything* must not be what a clerk gets by reading nothing —
    // and the front end was never moved when that landed. So the one control
    // this whole screen exists for could not succeed, on any of the six
    // connectors we issue a key to. `tsc` was satisfied because the body
    // argument is optional, and no test followed the request to a real door.
    mutationFn: () => issuePartnerKey(api, providerKey, scopeNames),
    onSuccess: (result) => {
      setIssued(result.key);
      void queryClient.invalidateQueries({ queryKey: queryKeys.integrations });
    },
    onError: (error) => {
      toast(isApiError(error) ? refusalText(t, error) : word("integrations.setup.keyFailed", "The key was not issued."));
    },
  });

  if (gridQuery.isLoading) {
    return <LoadingSkeleton variant="card" />;
  }
  if (gridQuery.isError) {
    return (
      <FailedWithRetry
        title={word("integrations.setup.failedTitle", "The connectors did not load")}
        reason={word("integrations.setup.failedReason", "Try again in a moment.")}
        onRetry={() => void gridQuery.refetch()}
        onDownloadReport={() => undefined}
        onCancel={() => navigate(tenantPath(GRID_ROUTE))}
      />
    );
  }

  const name = card
    ? word(`integrations.provider.${providerKey}.name`, card.display_name)
    : providerKey;
  const operations: OperationRow[] = card?.operations ?? [];
  const shown = expanded ? operations : operations.slice(0, ROWS_BEFORE_MORE);
  const hidden = operations.length - shown.length;
  const testable = card === null ? null : testableOperation(card);
  /**
   * ⚠ **`issued_secret` IS FILTERED OUT OF THE FIELD SLOT, AND IT IS A FIX
   * RATHER THAN A PREFERENCE (`DEF-INT-6444`).** The manifest declares the key
   * we hand a partner as a FIELD, so the slot drew its own block for it — and
   * the Key panel below drew the same thing again. The running screen carried
   * **two boxes headed *The key for them to use***, one stranded in the
   * control column beside an unrelated label. The drawing (CFG-10) gives the
   * key a panel of its OWN, below the API list, and gives it once. It is a
   * branch on the KIND and never on the provider, so `BR-INT-043` holds.
   */
  const visibleFields: ManifestField[] = (card?.fields ?? []).filter(
    // CR-173-BRC10 — a GROUPED field is drawn in its group's own panel below
    // (`FieldGroupPanel`) with its own save, never in Connection details.
    (one) => one.kind !== "issued_secret" && !one.group,
  );
  const issuedField = (card?.fields ?? []).find((one) => one.kind === "issued_secret") ?? null;
  /* ⚠ **`twoWay` LIVED HERE AND WAS DEAD FROM THE MOMENT ITS READER MOVED.**
     It measured in/out and the footnote below was corrected to ask WHOSE
     ceiling it is (`initiative`, not `direction`) — the two lines at the
     footnote say so — but the variable was left behind. `eslint` has been red
     on it since `a460ebaa5` (2026-09-16), `tsc`, `vitest` and `vite build` are
     all green over it (an unused const is legal TypeScript and the bundler
     strips it), and it sat inside a crowd of thirteen other lint failures where
     a true one goes to hide (`DEF-CUS-3935`; `G98`). Removed here rather than
     filed, because it is one dead line in a file this change already owns. */
  /** WHOSE ceiling each row carries — `them` means they dial us, so the limit
   *  is ours to set and `serve.check_rate_limit` is what enforces it. */
  const theyCallUs = operations.some((one) => one.initiative === "them");
  const weCall = operations.some((one) => one.initiative === "us");
  /** `they_hold_ours` — the two connectors where the key is OURS to give them. */
  const weIssueTheKey = card?.auth.mode === "they_hold_ours" || issuedField !== null;
  const comingSoon = card?.disposition.kind === "coming_soon";

  return (
    <section
      className="flex flex-col gap-4"
      data-screen="S147"
      data-provider={providerKey}
    >
      <PageHeader
        title={name}
        kicker={card === null ? undefined : kickerWords(card, word)}
        rollup={card === null ? undefined : word(`integrations.provider.${providerKey}.summary`, card.summary)}
        backTo={{
          to: tenantPath(GRID_ROUTE),
          label: word("integrations.setup.backTo", "Connectors"),
        }}
        secondaryActions={
          // `CR-174-BRC10` — the door to S143 for a connector whose manifest
          // ships a vocabulary (their words for our things). Read off the
          // card's `vocabularies`, never a provider key. Before switching on:
          // a connector whose fallback word is unmapped is refused by name.
          (card?.vocabularies ?? []).length > 0 ? (
            <Button
              size="sm"
              data-mappings-door=""
              onClick={() => navigate(tenantPath(`${GRID_ROUTE}/${providerKey}/mappings`))}
            >
              {word("integrations.setup.mapWords", "Map their words →")}
            </Button>
          ) : undefined
        }
      />

      {/* ── The two notices CFG-28 stacks above the first panel ──────────────
          Left-ruled, above the form, never inside it. Both are FACTS about the
          vendor (rule 33: ≤ 6 words is the instruction cap; a fact is its own
          sentence), and both come off the manifest — `display_name` still
          reading as a category, and `disposition.kind`. */}
      {card === null && (
        <RefusalStrip data-unknown-connector="">
          {word("integrations.setup.unknown", "No connector with that name.")}
        </RefusalStrip>
      )}
      {comingSoon && (
        <RefusalStrip data-coming-soon="">
          {card?.disposition.wave === null
            ? word("integrations.setup.comingSoon", "Coming soon — not built yet.")
            : word("integrations.setup.comingSoonWave", "Coming soon · {{wave}} — not built yet.").replace(
                "{{wave}}",
                card?.disposition.wave ?? "",
              )}
        </RefusalStrip>
      )}

      {card !== null && (
        <>
          {/* ══ PANEL 1 · Connection details — THE ACCENT PANEL ══════════════
              PO, verbatim: *"i want you to use panel with acsent - where ever
              shown it that way"*. The drawing runs a 2px accent rule along the
              TOP edge of this panel on every one of the 28 frames and along no
              other, and `Panel`'s own `accent` prop is exactly that rule
              (`border-t-2 border-t-accent`) — so the ruling costs no new class
              in any stylesheet, which B14 rule 21 requires. */}
          <Panel as="section" accent title={word("integrations.setup.details", "Connection details")}>
            <div data-field-slot="true">
              {visibleFields.map((field) => (
                <div key={field.name} data-field={field.name} data-kind={field.kind}>
                  {/* ⚠ THE THREE KINDS THAT ARE NOT FIELDS CARRY NO LABEL —
                      `redirect` is a button and a return trip, `issued_secret`
                      is a key we hand them, `mapping_editor` is a second step
                      that appears once a file has been seen. Each is a branch
                      on the KIND and never on the provider (`BR-INT-043`), and
                      the same grid keeps them in the control column so they do
                      not read as stray paragraphs. */}
                  {field.kind === "redirect" ||
                  field.kind === "mapping_editor" ||
                  field.kind === "issued_secret" ? (
                    <div className="grid grid-cols-[160px_1fr] gap-3 py-2">
                      <div />
                      <div>
                        {RENDER[field.kind](
                          {
                            card,
                            field,
                            value: values[field.name] ?? "",
                            error: fieldErrors[field.name],
                            mode: "connect",
                            replacing: false,
                            readOnly: false,
                            onChange: (fieldName, value) =>
                              setValues((current) => ({ ...current, [fieldName]: value })),
                            onStartOAuth: () => signIn.mutate(),
                          },
                          t,
                        )}
                        {field.kind === "redirect" && (
                          <Button
                            type="button"
                            variant="secondary"
                            disabled={signIn.isPending}
                            onClick={() => {
                              setRefusal(null);
                              signIn.mutate();
                            }}
                            data-sign-in={providerKey}
                          >
                            {word("integrations.setup.signIn", "Sign in with {{name}}").replace(
                              "{{name}}",
                              name,
                            )}
                          </Button>
                        )}
                      </div>
                    </div>
                  ) : (
                    // B14 rule 38: the drawing puts two fields on a row and our
                    // UI rules put one, and construction is the UI rules'.
                    <div className="grid grid-cols-[160px_1fr] items-baseline gap-3 py-2">
                      <label className="text-sm font-semibold" htmlFor={`field-${field.name}`}>
                        {fieldLabel(t, card, field)}
                        {field.required && <span className="text-danger-700"> *</span>}
                      </label>
                      <div>
                        {RENDER[field.kind](
                          {
                            card,
                            field,
                            value: values[field.name] ?? "",
                            error: fieldErrors[field.name],
                            mode: "connect",
                            replacing: false,
                            readOnly: false,
                            onChange: (fieldName, value) =>
                              setValues((current) => ({ ...current, [fieldName]: value })),
                            onStartOAuth: () => signIn.mutate(),
                          },
                          t,
                        )}
                        {/* ⚠ THE HELP UNDER A SECRET, WHICH THE DRAWING PUTS
                            THERE AND THE FIRST BUILD OF THIS SCREEN LOST. Two
                            sentences, because B14 rule 33 caps an instruction
                            at six words PER SENTENCE and says in as many words
                            that *two sentences of six beat one sentence of
                            twelve*. The drawing's own third clause — *"This
                            key is used by all 4 APIs"* — is 7 words and is
                            said here in 5. Help goes UNDER its input, which is
                            rule 38's construction half, and the drawing agrees. */}
                        {/* ⚠ **WHAT A BLANK MEANS, SAID ONCE (PO ruling
                            2026-09-17).** Verbatim: *"In fact we dont want
                            allowed_addresses - restriction - can we make it
                            options"*, and on being told plainly that with no
                            addresses listed the key alone is the whole door:
                            *"pls fix this"*. The five ERP manifests now declare
                            the field `required=False`, so the red asterisk
                            above is gone — and an optional field with no
                            sentence leaves a clerk guessing whether blank means
                            *none may call* or *any may call*, which is the
                            opposite of the truth. `allowlist_permits` has
                            always read an empty list as permit-everything and
                            is deliberately untouched; this is the FORM catching
                            up with the door.

                            ⚠ **KEYED OFF THE MANIFEST'S OWN FIELD NAME, which
                            is the one place `BR-INT-043`'s closed vocabulary
                            of KINDS cannot help**: `text` is the kind and six
                            manifests give this particular name a meaning no
                            kind expresses. It is a field NAME and not a
                            provider key, so `G77` is satisfied and a seventh
                            connector declaring it gets the sentence free.

                            Rule 33: six words, one sentence. */}
                        {/* ⚠ THE SENTENCE UNDER THE BOX, IN THE MODAL'S OWN
                            SHAPE AND MARKUP (`DEF-INT-5593`). It is FIRST,
                            above the help, because a refusal is what the clerk
                            came back to read. */}
                        {fieldErrors[field.name] !== undefined && (
                          <p className="mt-1 text-sm text-danger-700" data-field-error={field.name}>
                            {fieldErrors[field.name]}
                          </p>
                        )}
                        {field.name === ALLOWLIST_FIELD && allowlistJustCleared && (
                          <p
                            className="mt-1 text-sm text-danger-700"
                            data-allowlist-cleared=""
                          >
                            {t("integrations.setup.allowlistCleared")}
                          </p>
                        )}
                        {field.name === ALLOWLIST_FIELD && (
                          <p className="mt-1 text-sm text-neutral-600" data-allowlist-help="">
                            {t("integrations.setup.allowedAddressesHelp")}
                          </p>
                        )}
                        {SECRET_KINDS.includes(field.kind) && (
                          <p className="mt-1 text-sm text-neutral-600" data-secret-help="">
                            {word(
                              "integrations.setup.secretHelp",
                              "Stored encrypted. Never shown again.",
                            )}{" "}
                            {word("integrations.setup.secretShared", "All {{count}} APIs use it.").replace(
                              "{{count}}",
                              String(operations.length),
                            )}
                          </p>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>

            {/* ── Where it runs — TWO CONNECTION ROWS, NOT TWO COLUMNS ───────
                `BR-INT-026`: `integration_connection` is unique on
                `(tenant, provider_key, environment)`, so choosing Sandbox here
                addresses the sandbox ROW. It is not a second form and it is not
                a second set of credentials on one row. */}
            <div className="grid grid-cols-[160px_1fr] items-baseline gap-3 py-2">
              <span className="text-sm font-semibold" id="where-it-runs">
                {word("integrations.setup.whereItRuns", "Where it runs")}
              </span>
              <SegmentedControl
                name="environment"
                label={word("integrations.setup.whereItRuns", "Where it runs")}
                labelledBy="where-it-runs"
                active={environment}
                segments={ENVIRONMENTS.map((value) => ({
                  id: value,
                  label: t(`integrations.environment.${value}`),
                }))}
                onSelect={(id) => setEnvironment(id as Environment)}
              />
            </div>
          </Panel>

          {/* ══ CR-173-BRC10 · a named field group, e.g. *Send to City folder* ══
              Drawn only on a CONNECTED connector: the section saves onto the
              connection row, so there is nothing to save it to before one
              exists. PO approved 2026-10-07 (*"this is okay"*). */}
          {connected &&
            fieldGroups(card).map((group) => (
              <FieldGroupPanel key={group} card={card} group={group} />
            ))}

          {/* ══ PANEL 2 · The API list ═══════════════════════════════════════
              The heading pluralises off the count, exactly as the frames do:
              `1 API on this connector` / `APIs on this connector  4`. */}
          <Panel
            as="section"
            title={
              operations.length === 1
                ? word("integrations.setup.oneApi", "API on this connector")
                : word("integrations.setup.manyApis", "APIs on this connector")
            }
            trailing={
              <span
                className="border border-divider px-2 py-0.5 text-table-header"
                data-api-count={operations.length}
              >
                {operations.length}
              </span>
            }
          >
            <PlainTable data-api-table="">
              <thead>
                <tr>
                  {/* ── CR-110-BRC04 phase 2 · the PO's own fix ───────────
                      *"you remove it and put selection on off directly on
                      apis"*. FIRST column, because it is the thing a clerk
                      acts on and every other column on this row is a fact
                      about it. Drawn only where we ISSUE the key — on the
                      twelve connectors we DIAL there is nothing to grant, so
                      the column is ABSENT rather than present and disabled. */}
                  {weIssueTheKey && (
                    <th scope="col">{word("integrations.setup.column.on", "On")}</th>
                  )}
                  <th scope="col">{word("integrations.setup.column.api", "API · Endpoint")}</th>
                  <th scope="col">{word("integrations.setup.column.direction", "Direction")}</th>
                  <th scope="col">{word("integrations.setup.column.when", "When")}</th>
                  <th scope="col">{word("integrations.setup.column.rateLimit", "Rate limit")}</th>
                  {/* ⚠ THE COLUMN THE PDF CLIPS — `DEF-INT-5487`. Its header
                      text-extracts as one letter, `T`. It is here because the
                      blueprint's PROSE (p154) describes it, not because any
                      render shows it. */}
                  <th scope="col">{word("integrations.setup.column.test", "Test")}</th>
                </tr>
              </thead>
              <tbody>
                {shown.map((operation) => {
                  const endpoint = endpointText(operation);
                  const limit = rateLimitText(operation);
                  // ⚠ THE DRAWN WORDS, NEVER THE ENUM. The frames say *Nightly*,
                  // *On demand*, *When queued*, *While you wait*; the manifest
                  // says `scheduled`, `manual`, `dispatcher`, `inline`. A raw
                  // enum on a clerk's screen is what `DEF-INT-5491` was.
                  const when = operation.trigger;
                  return (
                    <tr key={operation.name} data-operation={operation.name}>
                      {weIssueTheKey && (
                        <td>
                          <Switch
                            on={scopeHas(operation.name)}
                            // The accessible name is WHAT the switch is for,
                            // never its state — `Switch`'s own contract, and
                            // the reason it takes the name as a required prop.
                            label={word(
                              `integrations.provider.${providerKey}.operation.${operation.name}`,
                              operation.label,
                            )}
                            onLabel={word("integrations.setup.on", "On")}
                            offLabel={word("integrations.setup.off", "Off")}
                            testKey={operation.name}
                            onChange={(on) => toggleScope(operation.name, on)}
                          />
                        </td>
                      )}
                      <td>
                        <span className="font-semibold">
                          {word(
                            `integrations.provider.${providerKey}.operation.${operation.name}`,
                            operation.label,
                          )}
                        </span>
                        {endpoint !== null && (
                          /* `data-endpoint` is how a BROWSER walk addresses
                             this cell — S142's twin has carried it since wave
                             B and this one did not, so a walk comparing the
                             two screens read every S147 row as "no endpoint
                             drawn" and reported six false failures. That is
                             hard-won law 7's *looking at the wrong thing*, and
                             it cost an hour on the run that found it. The two
                             screens answer one question and are now addressed
                             one way. */
                          <span
                            className="block font-mono text-table-header text-neutral-600"
                            data-endpoint=""
                          >
                            {endpoint}
                          </span>
                        )}
                      </td>
                      <td>{directionWord(operation, word)}</td>
                      <td>
                        {when === undefined ? EMPTY : word(`integrations.setup.when.${when}`, TRIGGER_WORDS[when])}
                      </td>
                      {/* A DASH IS NOT A ZERO and it is not a ceiling either. */}
                      {/* ⚠ **THE UNIT IS PART OF THE FIGURE.** p065 draws
                          `300 / min` and the connection view already renders
                          `{{count}} / min`; a bare `60` in a column headed
                          RATE LIMIT is a number a clerk has to guess the unit
                          of, which is CLAUDE.md hard rule 3's instinct one
                          domain over. Same catalogue key as the connection
                          view, so the two screens cannot say it differently. */}
                      <td className="font-mono" data-rate-limit={limit ?? "unset"}>
                        {limit === null
                          ? EMPTY
                          : t("integrations.runs.ratePerMinute", {
                              count: limit,
                              defaultValue: "{{count}} / min",
                            })}
                      </td>
                      <td>
                        {/* ⚠ **ONE LIVE BUTTON, NOT ONE PER ROW, AND
                            `DEF-INT-5489` IS THE REASON.** `POST
                            /integrations/{key}/test` takes `{recipient?}` and
                            **no operation**, so a button on every row would
                            test the CONNECTOR while appearing to test the row —
                            a control that does the wrong thing, which is worse
                            than a dead one. The one row the door can actually
                            reach gets the button; the rest say nothing. The day
                            the door takes an operation, every row lights up. */}
                        {testable?.name === operation.name ? (
                          <Button
                            size="sm"
                            variant="secondary"
                            type="button"
                            disabled={card.connection === null}
                            onClick={() => save.mutate()}
                            data-test-operation={operation.name}
                          >
                            {word("integrations.setup.test", "Test")}
                          </Button>
                        ) : null}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </PlainTable>

            {hidden > 0 && (
              <Button
                size="sm"
                variant="link"
                type="button"
                onClick={() => setExpanded(true)}
                data-show-more={hidden}
              >
                {word("integrations.setup.more", "…{{count}} more").replace(
                  "{{count}}",
                  String(hidden),
                )}
              </Button>
            )}

            {/* The two footnotes the frames carry under every API table. The
                second says which way the limits point, and on a two-door
                connector it has to say BOTH — outward is what they allow us,
                inward is what we allow them, one row apart on one table. */}
            {/* ⚠ **THE SENTENCE IS ONLY DRAWN WHILE IT IS TRUE
                (`CR-115-BRC05` §7).** *All use the address above* was an
                unconditional claim, and it became FALSE the first time a clerk
                gave one API its own URL through the per-API form (§7.3, PO R32)
                — a footnote asserting a guarantee the rows above it already
                contradict, which is hard-won law 1 in one line of copy. It was
                found by WALKING this screen after adding a custom API, not by
                any check: both states render, both are legal strings, and
                nothing in the repo reads rendered output (law 6).

                ⚠ **DECIDED FROM `endpoint_source`, WHICH THE SERVER SERVES.**
                Not from `is_standard`, and emphatically not by comparing the
                printed address with the connector's field — that would be a
                screen re-deriving the address ladder, which is a second source
                by another name and exactly what `DEF-INT-5613` was (§7.7).

                ⚠ **AND IT IS DROPPED RATHER THAN REPLACED WITH A SECOND
                SENTENCE.** B14 rule 32 gives a section ONE sentence, and every
                row already prints its own address in monospace directly above:
                a clerk who can see four addresses does not need a paragraph
                telling them the addresses differ. */}
            {operations.every(
              (one) =>
                one.endpoint_source === undefined ||
                one.endpoint_source !== "api_row",
            ) && (
              <p className="mt-2 text-sm text-neutral-600" data-endpoint-note="">
                {word("integrations.setup.allUseAddress", "All use the address above.")}
              </p>
            )}
            <p className="text-sm text-neutral-600" data-limit-note="">
              {/* ⚠ **WHO SETS THE CEILING IS READ OFF `initiative`, NOT OFF
                  `direction`.** This said *"These are the limits they allow
                  us"* on Aclarian — a connector nobody here dials, whose
                  ceiling `serve.check_rate_limit` enforces against THEM. The
                  drawing says the true half in its own words: *"These are the
                  limits we allow them."* `twoWay` was measuring in/out, which
                  answers which way the DATA moves and not whose ceiling it
                  is. */}
              {theyCallUs && weCall
                ? word(
                    "integrations.setup.limitsBoth",
                    "Outward they set the limit. Inward we do.",
                  )
                : theyCallUs
                  ? word("integrations.setup.limitsOurs", "These are the limits we allow them.")
                  : word("integrations.setup.limitsTheirs", "These are the limits they allow us.")}
            </p>
            {/* Rule 32: the drawing ends this *"See CR-3 and CR-11"*. The
                sentence ships; the pointer does not. */}
            <RefusalStrip data-limit-refusal="">
              {word("integrations.setup.notAClerkControl", "Set when we configure this connector.")}
            </RefusalStrip>
          </Panel>

          {/* ══ PANEL 3 · The key we give them ═══════════════════════════════
              ONLY on `they_hold_ours`, which is two connectors of eighteen. The
              word is **key** throughout — PO: *"if you want to called it key -
              you can call it key"* — and there is no expiry line, no renewal
              and no re-authorise, because there is no vendor to ask. */}
          {weIssueTheKey && (
            <Panel
              as="section"
              title={word("integrations.setup.keyTitle", "The key for them to use")}
            >
              {issued === null ? (
                <>
                  <p className="text-sm text-neutral-600">
                    {card.connection === null
                      ? word("integrations.setup.keyAfterSave", "Save this connector, then generate one.")
                      : word("integrations.setup.keyOnce", "Shown once. Copy it then.")}
                  </p>
                  <Button
                    type="button"
                    variant="secondary"
                    disabled={card.connection === null || issue.isPending}
                    onClick={() => issue.mutate()}
                    data-generate-key=""
                  >
                    {word("integrations.setup.generateKey", "Generate a key")}
                  </Button>
                </>
              ) : (
                // ⚠ THE ONLY COPY THAT WILL EVER EXIST. Nothing stores it —
                // not the server, not this client, not the query cache — so it
                // is rendered here and nowhere else, and re-fetching will not
                // bring it back. Losing it means issuing another.
                <p className="break-all font-mono text-base" data-issued-key="">
                  {issued}
                </p>
              )}
            </Panel>
          )}

          {/* ══ FOOTER ══════════════════════════════════════════════════════
              `Save and test` then `Cancel`, in the drawing's order, which is
              also our footer order (B14 rule 38 hands button order to the UI
              rules and the two agree here). */}
          <div className="flex items-center gap-2" data-setup-footer="">
            <Button
              type="button"
              variant="primary"
              disabled={save.isPending}
              onClick={() => {
                setRefusal(null);
                save.mutate();
              }}
              data-save-and-test=""
            >
              {word("integrations.setup.save", "Save and test")}
            </Button>
            <Button
              type="button"
              variant="secondary"
              onClick={() => navigate(tenantPath(GRID_ROUTE))}
            >
              {word("integrations.setup.cancel", "Cancel")}
            </Button>
          </div>
          {refusal !== null && <RefusalStrip data-save-refusal="">{refusal}</RefusalStrip>}
          <p className="text-sm text-neutral-600">
            {word("integrations.setup.runsFootnote", "Runs are kept exactly as they happened.")}
          </p>
        </>
      )}
    </section>
  );
}
