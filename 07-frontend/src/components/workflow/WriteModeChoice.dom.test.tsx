// ── Trace ──────────────────────────────────────────────
// Change:   CR-042 — "in all imports - we need 2 option on step 1 insert,
//           insert & update; replace option is not required; currently many
//           places this option is at step 4 of import- can you check all
//           imports and make the corrections" (PO, 2026-08-27).
// Rules:    BR-MET-210 (two modes, that order, those words, step 1, ONE
//           control) · DEF-770 (the commit step STATES, never re-offers) ·
//           hard-won law 3 (the safe option is the default)
// ───────────────────────────────────────────────────────
// **WHAT THIS ANSWERS THAT NO OTHER CHECK IN THIS REPO CAN.**
//
// `tsc` proves the props line up. G15 proves the eleven catalogues are in
// PARITY. G27 proves every key a component asks for exists somewhere. **Not one
// of them can answer "do the two importers print the SAME WORDS", and that is
// the entire content of the PO's complaint.** Before CR-042 the two rails held
// separate key sets that were each internally complete, each in parity, each
// resolving — and had drifted:
//
//     de   Nur neue einfügen        ·  Nur Neue einfügen
//     es   Solo insertar nuevas     ·  Solo insertar nuevos
//     ja   新規のみ登録              ·  新規のみ追加
//     ko   신규만 추가               ·  새 항목만 추가
//     it   Inserisci solo le nuove  ·  Inserisci solo i nuovi
//
// Eight of eleven languages, one product, one decision, two sets of words. Every
// gate was green. So this suite renders BOTH rails' controls and compares them.
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import de from "@/i18n/locales/de.json";
import en from "@/i18n/locales/en.json";
import esMX from "@/i18n/locales/es-MX.json";
import es from "@/i18n/locales/es.json";
import fr from "@/i18n/locales/fr-FR.json";
import hi from "@/i18n/locales/hi.json";
import idID from "@/i18n/locales/id-ID.json";
import itIT from "@/i18n/locales/it-IT.json";
import ja from "@/i18n/locales/ja-JP.json";
import ko from "@/i18n/locales/ko-KR.json";
import ptBR from "@/i18n/locales/pt-BR.json";

import {
  DEFAULT_WRITE_MODE,
  WRITE_MODES,
  WriteModeField,
  WriteModeStated,
  writeModeOptions,
} from "./WriteModeChoice";
import { readWriteModeChoices } from "@/features/metering/readsImportRail";

const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

const CATALOGUES: Record<string, Record<string, string>> = {
  de,
  en,
  "es-MX": esMX,
  es,
  "fr-FR": fr,
  hi,
  "id-ID": idID,
  "it-IT": itIT,
  "ja-JP": ja,
  "ko-KR": ko,
  "pt-BR": ptBR,
};

/** The keys the ONE control resolves. Every one must exist in every catalogue. */
const SHARED_KEYS = [
  "workflow.writeMode.label",
  "workflow.writeMode.help",
  "workflow.writeMode.insert",
  "workflow.writeMode.upsert",
  "workflow.writeMode.stated",
  "workflow.writeMode.change",
];

/** The reads rail's options, as `UploadReadsWizard` mounts them. */
const readsOptions = () => readWriteModeChoices(t);

/** The ETL runner's options, as `ImportWorkflowPage` builds them. */
const importOptions = () =>
  writeModeOptions(t, {
    insert: t("metering.import.writeMode.insertConsequence"),
    upsert: t("metering.import.writeMode.upsertConsequence"),
  });

describe("CR-042 / BR-MET-210 — two write modes, one control, every import", () => {
  it("offers exactly two modes, and `insert` is first", () => {
    // Clause 1 and clause 2. The ORDER is not cosmetic: `insert` is the only
    // mode that cannot alter a record already on file, so the clerk who never
    // touches this control gets the safe one (hard-won law 3 — the unsafe
    // option must be the one you type).
    expect(WRITE_MODES).toEqual(["insert", "upsert"]);
    expect(DEFAULT_WRITE_MODE).toBe("insert");
    expect(writeModeOptions(t).map((option) => option.id)).toEqual(["insert", "upsert"]);
  });

  it("⛔ THE TWO RAILS PRINT THE SAME WORDS FOR THE SAME OPTION", () => {
    // **THE TEST THIS SUITE EXISTS FOR**, and it is written the second way it
    // was written. ⚠ The first version compared `readsOptions()` to
    // `importOptions()` — and **could never fail**, because both call
    // `writeModeOptions`, so breaking that one function broke both sides of the
    // comparison identically. It was proved green over a deliberately corrupted
    // label. That is the DEF-182 shape: *a check whose output cannot
    // distinguish pass from fail is worse than no check, because it is
    // trusted.*
    //
    // So the labels are compared to the CATALOGUE instead — an independent
    // authority neither rail can move. Re-introduce a per-rail key on either
    // side and this goes red, which is exactly the drift that was live in eight
    // languages before CR-042.
    const reads = readsOptions();
    const imports = importOptions();
    expect(reads.map((option) => option.id)).toEqual(imports.map((option) => option.id));
    for (const options of [reads, imports]) {
      expect(options[0].label).toBe(en["workflow.writeMode.insert"]);
      expect(options[1].label).toBe(en["workflow.writeMode.upsert"]);
    }
  });

  it("…and the CONSEQUENCE sentences differ, which is correct and deliberate", () => {
    // The one thing that legitimately differs between rails. "Already on file"
    // means a reading at a meter/date/register with BR-MET-127's billed refusal
    // attached; on the ETL runner it means a record under the same reference.
    // Flattening them into one sentence would make the control LIE on one rail,
    // which is the BR-MET-099 mistake in a different costume — so this asserts
    // they are different rather than tolerating it.
    expect(readsOptions()[1].consequence).not.toEqual(importOptions()[1].consequence);
    expect(readsOptions()[1].consequence).toContain("billed");
  });

  it("every shared key resolves in ALL ELEVEN catalogues", () => {
    // G27 asks whether a key exists at all. G15 asks whether the catalogues
    // agree on which keys they hold. Neither asks THIS: that the six keys this
    // one control depends on are present in each file by name. `DryRunPanel`'s
    // step-4 sentence used to be a `defaultValue` with no key at all, so a
    // Hindi operator read English on the last screen before a commit.
    for (const [locale, catalogue] of Object.entries(CATALOGUES)) {
      for (const key of SHARED_KEYS) {
        expect(`${locale}:${key}:${key in catalogue}`).toBe(`${locale}:${key}:true`);
      }
    }
  });

  it("the withdrawn mode is gone from the option list in all eleven catalogues", () => {
    // A key left behind after the control that used it is deleted is the
    // stale-comment failure (hard-won law 1) applied to copy: the next lane
    // greps for "Replace the batch", finds it, and believes the mode exists.
    for (const [locale, catalogue] of Object.entries(CATALOGUES)) {
      for (const key of [
        "workflow.dry.mode.replace",
        "workflow.dry.mode.replaceRetire",
        "workflow.dry.mode.replaceRuled",
        "metering.upload.writeMode.replace",
      ]) {
        expect(`${locale}:${key}:${key in catalogue}`).toBe(`${locale}:${key}:false`);
      }
    }
  });

  it("renders two radios in one radiogroup, and the chosen mode's sentence only", () => {
    const html = renderToStaticMarkup(
      <WriteModeField
        value="upsert"
        onChange={() => undefined}
        options={importOptions()}
        idPrefix="import"
        t={t}
      />,
    );
    expect([...html.matchAll(/type="radio"/g)].length).toBe(2);
    expect([...html.matchAll(/role="radiogroup"/g)].length).toBe(1);
    expect(html).toContain('data-workflow="write-mode-consequence"');
    expect(html).not.toContain("Replace");
  });

  it("⛔ DEF-770 — the commit step STATES the mode and offers no second control", () => {
    // PO on the deployed v2.51.0: *"Write mode from this screen may not
    // required . it is already added on step 1"*. Two controls for one setting
    // invite the question of which one wins, and there is no good answer.
    const html = renderToStaticMarkup(
      <WriteModeStated
        value="upsert"
        options={importOptions()}
        onChangeRequested={() => undefined}
        t={t}
      />,
    );
    expect(html).toContain('data-workflow="write-mode-stated"');
    expect(html).not.toContain('role="radiogroup"');
    expect(html).not.toContain('type="radio"');
    expect(html).toContain(renderToStaticMarkup(<>{t("workflow.writeMode.change")}</>));
  });

  it("a run stored with the WITHDRAWN mode still renders a sentence, not a gap", () => {
    // Runs committed before 2026-08-27 carry `write_mode="replace"`, which is in
    // no option list any more. `options.find` misses. A screen that printed
    // nothing there would show a historical receipt with the premise silently
    // missing — and the premise is the thing that explains its figures.
    const html = renderToStaticMarkup(
      <WriteModeStated
        value="replace"
        options={importOptions()}
        onChangeRequested={() => undefined}
        t={t}
      />,
    );
    expect(html).toContain("replace");
  });
});
