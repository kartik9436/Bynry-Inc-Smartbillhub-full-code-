// ── Trace ──────────────────────────────────────────────
// Change:  CR-110-BRC04 — the rename to Connector.
// Defect:  the PO, twice, from the deployed product. First: "on tab it still
//          says integration, on detail view page it says connector - please
//          fix tab". Then, having opened a connection screen: "here it again
//          says integration - so please check".
// Ruling:  PO 2026-09-16 — "use connector - instead of integration", and, on
//          the address, "keep it - The grid's address is still
//          /settings/integrations".
// Rules:   B14 rule 35 (a catalogue is written in its own language, never
//          translated word-for-word from English) · B14 rule 33 (a LABEL is
//          <= 3 words, a FACT <= 6) · CLAUDE.md hard-won law 7 ("what would
//          make this check pass wrongly?") and law 2 (a string nobody renders
//          is a string nobody has checked).
// ───────────────────────────────────────────────────────
//
// WHY THIS FILE EXISTS, AND WHY IT IS SCOPED THE WAY IT IS.
//
// The word moved on SIX values and the keys did NOT move: `integrations.*` is
// 328 keys cited across the front end, the tests and the gates, and renaming
// them would move every citation at once for zero clerk-visible benefit. So
// there is nothing structural left to check — **the only thing that can go
// wrong now is a VALUE**, and a value is exactly what no gate in this repo
// reads.
//
// ⚠ THE SCOPE IS THE CONNECTORS NAMESPACE, NOT THE WHOLE CATALOGUE, AND THAT
// IS A MEASURED DECISION RATHER THAN A CONVENIENCE. Swept over all 18,147
// keys, a per-language search for the noun returns SIX hits that have nothing
// to do with this module and would make the suite red on purpose:
//
//   * it-IT x3 — "Integrazione al minimo fatturabile" is the Italian for a
//     minimum-bill TOP-UP. Same letters, different word.
//   * ja-JP x3 — 連携 is ordinary Japanese for "linkage": a linked meter, a
//     linked accounting package, a data sync.
//   * ko-KR x1 — "통합도 하지 않습니다" is the VERB, in a sentence about
//     supplier lists.
//
// A check that is red for reasons its reader must learn to ignore is worse
// than no check, because the next lane silences it. Scoped to the 328 keys the
// ruling actually governs, it is green and it is TRUE.
//
// ⚠ THE PRICING KEY WAS PINNED POSITIVELY HERE UNTIL 2026-10-02. `public.plan.
// growth.f4` read "AMR / AMI integrations" on the public pricing page the PO had
// frozen (DEF-TEN-4222). The freeze ended by the trigger it named — the PO took
// the tier cards down pending the new pricing model ("I dont want to display the
// pricing") — so the key is RETIRED, and the pin below now asserts the absence.
// The home page's "50+ integrations" is the industry's sense of the word too; it
// lives outside `integrations.*`, which is all this ruling governs.
import { describe, expect, it } from "vitest";

import { LOCALE_REGISTRY } from "@/i18n";

/**
 * Each language's own word for an *integration*, as a NOUN.
 *
 * ⚠ Deliberately not one regex over eleven languages. `/integration/i` catches
 * the English and the German and silently misses "Integraciones",
 * "Intégrations", "Integrasi", "Integrazioni", "Integrações", "इंटीग्रेशन",
 * 統合 and 통합 — so a Spanish regression would pass a check that looked
 * thorough. That is law 7's *reporting zero over a scope it silently
 * excludes*, and the fix is to name the word in every language.
 *
 * ⚠ The Italian is `integrazion[ei]` and not `integrat`: the loose form also
 * matches *integrate*, the ordinary verb, which is why the whole-catalogue
 * sweep is not the check being made here.
 */
const THE_OLD_NOUN: Readonly<Record<string, RegExp>> = {
  en: /\bintegrations?\b/i,
  de: /\bIntegrationen?\b/i,
  es: /\bintegraci[oó]n(es)?\b/i,
  "es-MX": /\bintegraci[oó]n(es)?\b/i,
  "fr-FR": /\bint[ée]grations?\b/i,
  "it-IT": /\bintegrazion[ei]\b/i,
  "pt-BR": /\bintegraç(ão|ões)\b/i,
  "id-ID": /\bintegrasi\b/i,
  hi: /इंटीग्रेशन|एकीकरण/,
  "ja-JP": /統合|連携/,
  "ko-KR": /통합|연동/,
};

/** A key belongs to the connectors module's clerk-facing copy. */
const inScope = (key: string) =>
  key.startsWith("integrations.") || key === "settings.tab.integrations";

/**
 * The six the PO reported, in the eleven languages the product ships.
 *
 * ⚠ The ten non-English values are NOT translations of the English. Each takes
 * the word this repository had ALREADY agreed for that language in
 * `integrations.footnote` — Konnektoren, conectores, connecteurs, कनेक्टर,
 * konektor, connettori, コネクタ, 커넥터 — which is B14 rule 35 obeyed by
 * reusing a decision rather than by making a new one.
 */
const WORD: Readonly<Record<string, string>> = {
  en: "Connectors",
  de: "Konnektoren",
  es: "Conectores",
  "es-MX": "Conectores",
  "fr-FR": "Connecteurs",
  hi: "कनेक्टर",
  "id-ID": "Konektor",
  "it-IT": "Connettori",
  "ja-JP": "コネクタ",
  "ko-KR": "커넥터",
  "pt-BR": "Conectores",
};

/** The four keys that render that one word, and the two sentences around it. */
const THE_SIX = [
  "settings.tab.integrations",
  "integrations.title",
  "integrations.runs.backTo",
  "integrations.mappings.backTo",
] as const;

const codes = LOCALE_REGISTRY.map((entry) => entry.code);
const catalogueOf = (code: string) =>
  LOCALE_REGISTRY.find((entry) => entry.code === code)!.catalog as Record<string, string>;

describe("CR-110-BRC04 — the word a clerk reads is Connector, in all eleven languages", () => {
  it("the eleven this asserts are the eleven the product ships", () => {
    // Guards the check itself: a twelfth language added to the registry and not
    // to `THE_OLD_NOUN` would otherwise be swept silently, which is the shape
    // of a check that reports zero over a scope it excludes.
    expect([...codes].sort()).toEqual(Object.keys(THE_OLD_NOUN).sort());
    expect([...codes].sort()).toEqual(Object.keys(WORD).sort());
  });

  it.each(codes)(
    "%s: no clerk-facing connector string says integration any more",
    (code) => {
      const catalogue = catalogueOf(code);
      const noun = THE_OLD_NOUN[code];
      const offenders = Object.entries(catalogue)
        .filter(([key, value]) => inScope(key) && typeof value === "string" && noun.test(value))
        .map(([key, value]) => `${key} = ${value}`);
      expect(offenders).toEqual([]);
    },
  );

  it.each(codes)("%s: the four one-word surfaces read the connector noun", (code) => {
    const catalogue = catalogueOf(code);
    for (const key of THE_SIX) {
      expect(catalogue[key], `${code} · ${key}`).toBe(WORD[code]);
    }
  });

  it("the failure title and the disconnect toast carry the noun too", () => {
    const en = catalogueOf("en");
    // B14 rule 33: a FACT is six words or fewer. This one is exactly six.
    expect(en["integrations.failedTitle"]).toBe("We could not load your connectors");
    expect(en["integrations.failedTitle"].split(" ")).toHaveLength(6);
    expect(en["integrations.disconnect.toast"]).toBe("Connector disconnected");
  });

  it.each(codes)("%s: the failure title and the toast changed as well", (code) => {
    const catalogue = catalogueOf(code);
    // Asserted through the noun sweep above rather than by pinning eleven
    // sentences: what matters is that neither still says *integration*, and
    // pinning the prose would make every future rewording a test edit.
    expect(catalogue["integrations.failedTitle"]).toBeTruthy();
    expect(catalogue["integrations.disconnect.toast"]).toBeTruthy();
  });
});

describe("CR-110-BRC04 — what deliberately did NOT change", () => {
  it.each(codes)(
    "%s: the old pricing page's AMR / AMI bullet is retired with the tier cards (DEF-TEN-4222, 2026-10-02)",
    (code) => {
      // It stood here as a positive pin while the pricing page was frozen. The
      // PO lifted the freeze by taking the prices down; a key that survived the
      // page it belonged to would be a translation of nothing.
      expect(catalogueOf(code)["public.plan.growth.f4"]).toBeUndefined();
    },
  );

  it("the 328 key NAMES are untouched — only their values moved", () => {
    // Renaming `integrations.*` would move every citation in the front end, the
    // tests and the gates at once, for nothing a clerk can see. The keys are the
    // stable interface; the values are the copy. Same reasoning that leaves the
    // grid at /settings/integrations while its tab reads Connectors.
    const en = catalogueOf("en");
    // ⚠ **328 → 336 ON 2026-09-16, AND THIS IS NOT A BASELINE BEING WIDENED TO
    // GO GREEN.** The claim this case makes is that the RENAME moved values and
    // not names; an exact total also catches an accidental deletion, which is
    // why it stays exact rather than becoming `toBeGreaterThan`. Eight keys were
    // ADDED by `CR-110-BRC04` phase 2 and every one of them is new vocabulary
    // rather than a renamed key: `integrations.when.{scheduled,manual,
    // dispatcher,webhook,partner,inline}` — the WHEN column's own words, split
    // from the run history's (`DEF-INT-5493`) — plus
    // `integrations.keys.column.mayCall` and `integrations.keys.mayCallUnknown`
    // for the drawn *Keys we issue* panel (`DEF-INT-5533`).
    // The rename's own four are asserted BY NAME two lines down, so this number
    // moving cannot hide one of them disappearing.
    //
    // ⚠ **336 → 339 ON 2026-09-16 (`DEF-INT-5484`, `ACC-01`), AND IT IS A NET OF
    // FOUR ADDED AND ONE RETIRED RATHER THAN THREE ADDED.** The access-log panel
    // could not tell *still loading* from *nobody has read anything* from *the
    // fetch failed* — one sentence covered all three, on the one screen whose job
    // is to show unusual access. The four new keys are the drawing's own two-line
    // pairs: `integrations.access.empty.{title,helper}` and
    // `integrations.access.failed.{title,reason}`. **`integrations.access.empty`
    // was RETIRED**, not re-worded — it WAS the one sentence, it has no call site
    // left, and a dead key is what `G18` fails on. So this number rising by three
    // over a change that added four is the arithmetic working, and an exact total
    // is what makes that visible.
    //
    // ⚠ **339 → 343 ON 2026-09-16 (`DEF-INT-5528`), AND AGAIN THIS IS NOT A
    // BASELINE BEING WIDENED TO GO GREEN.** FOUR keys were added, and they are
    // two i18next plural pairs rather than four ideas:
    // `integrations.card.apis_{one,other}` (`3 APIs`) and
    // `integrations.card.apisWorking_{one,other}` (`3 APIs · 2 working`) — the
    // ONE line that replaced the card's per-API list when the Product Owner
    // ruled *"don show all apis on screen … you canjust mention the number"*.
    // **`integrations.fact.operations` was RE-WORDED, not added** — *Operation
    // lines* → *API count*, because the `▦` chooser's label now names a count
    // and no longer names lines that exist — so it moves a VALUE and not the
    // total, which is exactly the distinction this case was written to make.
    //
    // ⚠ **343 → 364 ON 2026-09-17 (the grid→table override), AND IT IS 22 KEYS
    // ADDED MINUS ONE OVERWRITTEN RATHER THAN 21 IDEAS.** The Product Owner
    // ruled `CON-01` into a table (*"table only"*), approved ten columns and
    // ratified a four-icon actions cell, so the screen gained:
    //   * **10 column headers** — `integrations.column.*`, one per ruled column;
    //   * **2 API-cell forms** — `integrations.table.apis{,Working}`. The value
    //     lost the word *APIs* to the column header, so `16 APIs · 14 working`
    //     became `16 · 14 working`; `{{total}}` and NOT `{{count}}`, because
    //     i18next reads `count` as a plural request and would resolve
    //     `…_one`/`…_other` for a number that is never pluralised;
    //   * **4 action labels** — `integrations.rowAction.{connect,view,edit,keys}`,
    //     one word each (B14 rule 33);
    //   * **3 greyed-icon reasons** — `…notConnected`, `…alreadyConnected`,
    //     `…notBuilt`. These are the EXACT strings shown to the PO in the
    //     ratified matrix, which is what HUMAN-GUIDE §6 means by *write down
    //     what was shown*;
    //   * **2 empty-state lines** — `integrations.table.empty{Title,Helper}`.
    // 10 + 2 + 4 + 3 + 2 = **21 NEW**. The twenty-second key is
    // `integrations.intro`, **OVERWRITTEN and not added** — every language's
    // second sentence described a CARD (*"Each card says what it does…"*), and
    // there are no cards — so it moves a VALUE and not the total. Same
    // distinction `integrations.fact.operations` made above, and the reason an
    // exact total is worth keeping: 343 + 21 = 364 reconciles, and a lane that
    // had quietly added a twenty-second idea could not make it reconcile.
    //
    // ⚠ **364 → 375 ON 2026-09-17 (S142's rebuild), AND AGAIN THIS IS NOT A
    // BASELINE BEING WIDENED TO GO GREEN.** TWELVE keys were added and ONE was
    // retired, so the arithmetic is +11. Four groups, each traceable to one PO
    // sentence of 2026-09-17:
    //   * `integrations.actions.{connect,edit,keys}` — the page-head action row
    //     the PO moved to the top (*"actions on this screens - should be on
    //     top - like we follow as per our ui guideline"*). `Disconnect`,
    //     `Replace password` and `Re-authorise` reuse the keys they already
    //     had, so only the three NEW words cost a key.
    //   * `integrations.regenerate.{action,title,consequence}` — the control
    //     the PO named (*"you did not inlcude rEgenerate Keys button"*) and the
    //     red confirm it opens. The TOAST reuses `integrations.keys.issued`,
    //     because it is the same act S144 already reports.
    //   * `integrations.kpi.{apis,working,workingValue,lastRun,keysInUse}` —
    //     the strip the PO asked for (*"we did not include any KPIs line"*).
    //   * `integrations.setup.allowedAddressesHelp` — what a blank address list
    //     now means, after `allowed_addresses` became optional.
    //
    // ⚠ **AND THE ONE RETIRED IS `integrations.runs.title`** — the literal word
    // *Connector*, which was the kicker's whole value until the kicker became
    // the connector's own category and direction. `G18` named it as a dead key
    // the moment its last call site went, which is that gate doing exactly its
    // job, so it is DELETED from all eleven catalogues rather than left for
    // somebody to wonder about. A dead key is either wording to delete or a
    // control nobody built; this one is the first.
    //
    // ⚠ **AND A SECOND ONE WENT WITH IT, SO THE NET IS +10.**
    // `integrations.keys.link` was *Keys we issue* — the footer's link to S144
    // — and the ratified action table names that control **Keys**, one word, in
    // the page head. `G18` named it dead the moment the footer lost its
    // buttons. It is DELETED for the same reason and by the same tool.
    //
    // ⚠ **BOTH WERE FOUND BY READING `G18`'s NUMBER AGAINST THE TIP'S, NOT BY
    // READING ITS VERDICT.** That gate has been red for months over a 435-key
    // backlog, so *it is still red* says nothing; what says something is
    // `677 dead` at the base and `678` here. A gate that cannot go green is
    // only useful as an arithmetic difference, and that is how it was read.
    //
    // ⚠ **374 → 375 ON 2026-09-17, AND THE ONE KEY IS `integrations.field.url`**
    // (`DEF-INT-5589`, PO: *"a) build it now with the Edit fix"*). The
    // *Service address* field moved to a new kind that accepts a whole web
    // address, so its refusal needed a sentence of its own: *"Full web
    // address, starting with https."* — six words, B14 rule 33's instruction
    // cap, in all eleven languages through `i18n_fanin.py`.
    //
    // ⚠ **THE COUNT IS NOT AN OBSTACLE HERE, IT IS THE CHECK WORKING.** It
    // went red the moment a key was added, which is exactly what a locked
    // count is for: a new key arrives deliberately and with a reason written
    // down, or it does not arrive. Moving the number without this paragraph
    // would be the only way to get this wrong.
    //
    // ⚠ **374 → 379 ON 2026-09-17, AND IT IS **TWO** LANES' KEYS, NOT ONE.**
    // The number is written out because a count that moves by five with one
    // sentence of explanation teaches the next reader nothing.
    //
    //   374 → 375  `integrations.field.url` — *"Full web address, starting
    //               with https."* The *Service address* field moved to a kind
    //               that accepts a whole web address, so its refusal needed a
    //               sentence (`DEF-INT-5589`, PO: *"a) build it now with the
    //               Edit fix"*).
    //   375 → 378  **CR-112's three keys, a SIBLING's.** They landed in
    //               `1c658337` and **this assertion was not moved with them**,
    //               so this file was RED ON THE BRANCH before the commit that
    //               carries this paragraph — 378 keys against an assertion of
    //               375. It is fixed here because the same line has to move
    //               anyway, and it is NAMED here because a red repaired in
    //               passing and not mentioned is how the next lane learns to
    //               assume a red is theirs.
    //   378 → 379  `integrations.setup.allowlistCleared` — *"This allows any
    //               address."* (`OQ-INT-12398`, PO: *"a) A short line under
    //               the field when you clear it … yes okay"*). Four words: a
    //               CONSEQUENCE before a widening, B14 rule 33.
    //
    // ⚠ **THE COUNT IS NOT AN OBSTACLE HERE, IT IS THE CHECK WORKING.** It
    // went red the moment a key was added — twice, by two lanes — which is
    // exactly what a locked count is for: a new key arrives deliberately and
    // with a reason written down, or it does not arrive. Moving the number
    // without this paragraph would be the only way to get this wrong.
    //
    // ⚠ **AND 379 → 387 THE SAME DAY — THE EIGHT ARE ONE CONNECTOR'S OWN COPY**
    // (`CR-111-BRC04`, `DEF-INT-5574`, PO ruling of that date). The
    // twenty-ninth connector, `pay_invoicecloud_partner`, is the reading half
    // of InvoiceCloud, and it is the row whose COPY does the work: a utility
    // now sees two rows carrying the same company name, and *"(reads from us)"*
    // is the only thing telling them apart before either is opened. Carrying
    // that parenthesis into a German or Japanese screen in English is exactly
    // the mechanical carry B14 rule 35 forbids, so the eight keys are
    // `…partner.{name,summary}`, its FIVE `…operation.*` labels (four until
    // `DEF-INT-5622` gave `consumer-info` its own) and its two
    // `…field.*` labels, written in each language's own idiom through
    // `i18n_fanin.py`.
    //
    // ⚠ **THE OTHER TWENTY-EIGHT CONNECTORS STILL HAVE NO CATALOGUE COPY AT
    // ALL** and render their manifest's English fallback in every language.
    // That is a pre-existing gap, not this change's — it is FILED rather than
    // mentioned here, because a finding recorded only in the file you happen to
    // be in is a finding nobody can count.
    // ⚠ **AND 387 → 405 ON 2026-09-17 — EIGHTEEN KEYS FOR *RUN NOW*
    // (`CR-115-BRC05` R31, PO: *"i dont have Run button here"*).** Two are
    // REFUSALS the server raises by key — a run nobody is named for, and a mode
    // that is neither `preview` nor `apply` — and sixteen are the control and
    // its report: the two button words, the working line, the panel's own
    // title, the *nothing was written* line, the reason R28 makes necessary
    // (*"No address field is turned on."*), the two counted sentences, four row
    // labels, the queue link, the confirm's title and its consequence, and the
    // sentence for a pull that could not be read.
    //
    // ⚠ **THE REPORT'S SENTENCE IS COMPOSED ON THE SCREEN AND NOT SENT BY THE
    // SERVER, WHICH IS WHY THERE ARE THIS MANY.** `gis_match.headline` builds a
    // perfectly good English line and it is stored on the run row as the
    // summary; rendering it would put English on eleven catalogues' screens.
    // This file's own rule, one screen along: the server serves integers and
    // the screen writes the line.
    //
    // ⚠ **AND 405 → 425 ON 2026-09-17, IN TWO JUMPS BY TWO LANES, AND ONLY ONE
    // OF THEM IS THIS FILE'S OWN STORY.**
    //
    // **405 → 424 is the two email connectors** (`email_sendgrid` and
    // `email_postmark`, `36bf8cd67`) — nineteen keys. ⚠ **That commit did not
    // move this number, so this case was RED on the branch before the change
    // below was written.** It is corrected here rather than left, because a
    // number that is knowingly wrong is worse than one that is merely stale:
    // the next lane reads a red and cannot tell whose it is. That is the
    // ratifying-and-pointing split CLAUDE.md names over and over — landing the
    // keys and moving the count are two acts, and only the first feels like
    // the work.
    //
    // **424 → 425 is ONE key for the fifth Invoice Cloud API**
    // (`DEF-INT-5622`). `GET /partner/v1/consumer-info` was built, routed and
    // tested and declared by no manifest, so it drew no row and the PO counted
    // four APIs where five exist. It has its own operation now, so it has its
    // own label —
    // `integrations.provider.pay_invoicecloud_partner.operation.serve_consumer_info`
    // — in all eleven catalogues. **`…operation.serve_customer` moved from
    // *Read customers* to *Read accounts* in the same commit and adds no key**
    // (`DEF-INT-5623`, PO: *"it should be account and not customer"*), which is
    // why that half rises by one rather than by two.
    //
    // ⚠ **AND 425 → 458 ON 2026-09-17 — THIRTY-THREE KEYS FOR CUSTOM APIs ON A
    // CONNECTOR** (`CR-115-BRC05` §7, `BR-INT-078`, `2.296.0`). PO: *"here
    // Customer is giving custom URLs … hence we need a form to add them"*.
    //
    // Eleven are REFUSALS a clerk reads, and they are the reason the number
    // jumps rather than creeps: nine on the form and the row actions
    // (`integrations.customApi.*`) and two on the search itself
    // (`integrations.gis.lookup_off`, `…sync_off`). A refusal with no
    // catalogue line reaches a clerk as SILENCE — the shape `G32` exists for —
    // and `core.errors` asserts at the raise that the key resolves, so the
    // backend suite went red until every one of them was written in all eleven
    // languages. **The catalogue is load-bearing here, not decoration.**
    //
    // The other twenty-two are the table and the form: three column headings
    // (`kind`, `enabled`, `edit`), the *Standard* marker that answers §7.4's
    // *"ours marked as standard"*, the three KINDS from the closed list we
    // ship, and the Add/Edit dialog's own words.
    //
    // ⚠ **THE COUNT MOVES IN THE SAME COMMIT AS THE KEYS**, which is the whole
    // lesson the two paragraphs above record against an earlier lane: landing
    // the keys and moving the number are two acts and only the first feels
    // like the work.
    //
    // ⚠ **458 → 462 ON 2026-10-07, FOUR ADDED AND NONE RENAMED, BY TWO LANES.**
    // `integrations.gis.foreign_frame` (`DEF-INT-9844`, commit `8d21ecd10`) was
    // added WITHOUT moving this number — the lesson above, again — so the case
    // was red at the tip from that commit. `DEF-INT-9846` adds the three
    // refusal reasons `integrations.gis.city_{rejected_key,layer_moved,
    // service_error}`; `integrations.gis.parcel_taken` was RE-WORDED (it names
    // the property now, `DEF-MET-9847`), which moves a value, not the total.
    // ⚠ **462 → 485 THE SAME DAY (`CR-173-BRC10`).** Twenty-three keys for New
    // World's *Send to City folder*: `integrations.group.*` (13), the six
    // `integrations.provider.erp_newworld.field.sftp_*` names, the operation
    // `send_receipt_file`, `integrations.field.host_key` and the two resend refusals.
    // ⚠ **485 → 495 THE SAME DAY (`CR-174-BRC10`).** Ten keys for US Payments
    // (Prime): the USPayments card's summary, four field labels and three
    // operation labels (`integrations.provider.pay_uspayments.*` — its NAME stays
    // the manifest's, a brand reads the same in every language), the set-up
    // page's *Map their words →* door (`integrations.setup.mapWords`) and the
    // refusal when *Other* is unmapped (`integrations.refusal.fallback_unmapped`).
    // ⚠ **495 → 499 THE SAME DAY (`DEF-INT-9849`, PO GIS review gap 3).** A page
    // limit on the parcel check: two refusals (`integrations.gis.pages_preview_only`,
    // `integrations.gis.pages_whole_number`) and the result's two sentences
    // (`integrations.reconcile.stoppedAfterOf`, `integrations.reconcile.stoppedAfter`).
    // ⚠ **499 → 502 THE SAME DAY (GIS Lane D).** Two refusals
    // (`integrations.gis.no_layer`, `integrations.gis.connection_broken` —
    // `DEF-INT-10005`/`DEF-INT-10004`) and the parcel check's own name
    // (`integrations.provider.gis_esri.operation.reconcile_parcels`, *Parcel
    // check* — `DEF-INT-10007`).
    // ⚠ **502 → 509 (`DEF-INT-10117`, 2026-10-14), SEVEN ADDED AND NONE RENAMED,
    // BY TWO LANES THAT DID NOT MOVE THIS NUMBER — the lesson above, a third
    // time.** `integrations.gis.city_firewall_blocked` (`DEF-INT-10019`,
    // `56bad94ff`, 2026-10-07 — raised by `apps/integrations/gis_parcels.py`)
    // and the six `integrations.meterReading.{bad_date,connected_no_read,
    // meter_required,no_reading,not_connected,unavailable}` refusals of the
    // fetch-a-reading door (`8f618a620`, 2026-10-11 — raised by
    // `apps/integrations/meter_reading.py`, drawn by `FetchMeterReading.tsx`).
    // All seven are live keys; the case was red at the tip from `56bad94ff`.
    // ⚠ **509 → 537 (`CR-198-BRC10`, 2026-10-29), TWENTY-EIGHT ADDED AND NONE
    // RENAMED.** Texts provided by the PLATFORM (one shared Twilio account):
    // `integrations.platformSms.*` (24 — the S142 panel's facts, states,
    // problems, Test and its two answers), `integrations.rowAction.platformProvided`,
    // `integrations.refusal.platform_provided` and the adapter's two field
    // refusals `integrations.field.{oneSender,messagingService}`.
    expect(Object.keys(en).filter((key) => key.startsWith("integrations.")).length).toBe(537);
    for (const key of THE_SIX) expect(en[key]).toBeDefined();
  });
});
