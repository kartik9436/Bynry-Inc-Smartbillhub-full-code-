# `CR-101-BRC03` · step 2 · §06 **Fix a bill** — what was built, measured

**Lane:** §06, the Fix a bill surface. **Branch:** `claude/eager-johnson-r0k88b`.
**Date:** 2026-09-14. **Commit:** `3b8fb578` (code + guard) · `b6fe8821` (the eleven
catalogues, pushed by a sibling — see *What a sibling carried*, below).

**What this is.** The record of one commitment built end to end: `DEF-BIL-5233` /
`BIL-S83`, *"a clerk never reads a rule id or an internal code on screen"*, on screens
`26` and `26.1`. It carries the before and after measurements, the reds with their
dates, and — at least as important — **what was deliberately not built and the blocker
that was read rather than assumed.**

**What this is NOT.** It is not a second diff of §06. The two-way diff is
`CR-100-BRC03-diff-03-08.md` §06 and nothing here supersedes it.

---

## 1 · The defect, measured before and after

> **`DEF-BIL-5233`** — all thirteen correction reasons reach a clerk as raw
> `snake_case` enum codes, in every language, **on the control that decides whether a
> credit note issues.**

| | Before (measured 2026-09-14 09:05, Chromium) | After (measured 09:20) |
|---|---|---|
| `billing.fix.reason.*` keys, all eleven catalogues | **0** | **13** |
| Strings shipped | 0 | **143** (13 × 11), every one differing from English |
| What the select rendered | `charge_billed_in_error`, `customer_name`, `goodwill`, `meter_number_or_read_dates`, `missed_charge`, `premises_or_unit_label`, `service_or_mailing_address`, `template_or_language`, `theft_restated`, `wrong_period_or_service`, `wrong_rate_plan`, `wrong_read`, `wrong_tax` | *A charge was billed in error · A charge was missed · Customer name · Goodwill · Meter number or read dates · Premises or unit label · Service or mailing address · Template or language · Theft, restated · Wrong period or service · Wrong rate or plan · Wrong read · Wrong tax* |
| Doors affected | **2**, not 1 | both fixed |

⚠ **THE DEFECT ROW NAMED ONE ADDRESS AND THERE ARE TWO.** `FixABillTab` is mounted at
`/:tenant/billing/fix` **and** at `/:tenant/accounts/:accountId/issue-credit`. Both were
reproduced broken before the fix and both were walked after it. *(The lane brief gave the
second address as `/billing/issue-credit`; the `issue-credit` mount is a child of the
**accounts** route, not of billing.)*

**Where the words came from.** p133 of `05-prototype/04 Billing, As Built.pdf`, read **as
an image at scale 4** (B14 rule 42), from a copy derived out of the default branch with
`git show` and hash-checked — `137a2a48c0398c39897f49aafa0bbb9c44ff21d6258eed78cd7558e6cc200971`,
14,363,163 bytes. **Not one sentence was paraphrased from an enum name**, which is the
shortcut that would have produced thirteen plausible wrong sentences with every check
green. The server's `SEEDED_REASON_CLASSES` was confirmed to hold the same thirteen codes
in the same order — **7 R · 1 C · 5 D**, exactly as drawn.

---

## 2 · The two things built beside the words, and why each was necessary

**(a) The order moved with the words.** The server sorts by CODE
(`sorted(SEEDED_REASON_CLASSES.items())`). That read as alphabetical *only while the codes
were the visible text*. Showing sentences leaves it looking arbitrary: **`A charge was
missed` lands fifth, between `Meter number or read dates` and `Premises or unit label`.**
The rendered list is now sorted by the words a clerk reads, `localeCompare` in the clerk's
own language. **The server is untouched** — the brief's own finding is that the server is
right and only the words were missing.

**(b) The fallback keeps its job; its silence does not.** `defaultValue: reason.code` is
deliberate — a tenant-extensible reason would otherwise render an empty option — but a
silent fallback is *how this defect lived*. `FixABillReasonWords.test.ts` **derives the
thirteen from the server's own map rather than restating them**, because a list restated
in a test agrees with itself forever. It goes RED when a reason arrives without words,
when one language is missed, or when a word echoes its own code.

**Proved RED three ways before green, 2026-09-14, in `npx vitest run` — the harness that
runs it:** one key removed from **one** catalogue (named `ko-KR:theft_restated`); a
fourteenth code added to the Python map with no words (named it in all eleven); a word set
equal to its own code (named it in all eleven). Restored each time; `correction_reasons.py`
was confirmed **byte-identical to HEAD** afterwards.

---

## 3 · A copy judgment, recorded because it changed four strings

**These thirteen are a `FACT` under B14 rule 33, not a `LABEL`.** A picked reason names
what went wrong on the bill, so the cap is **6 words, not 3**. All thirteen English
sentences fit; the longest, *A charge was billed in error*, is exactly six.

**Four Romance translations came in at 7 words and were tightened to 5** — *Número de
contador o fechas de lectura* → *Contador o fechas de lectura*, and the same in `es-MX`,
`fr-FR`, `pt-BR`. **The cap was not widened.** The check that caught them is this lane's
own, which is the point: widening a cap to pass your own strings is the baseline-edit the
skill forbids.

---

## 4 · What was NOT built, and the blocker was read rather than assumed

**§06 carries no `BUILD THIS` band on any of its nine entries**, and four of them
(`26`, `26.1`, `26.2`, `26.3`) are `Blocked` on `BIL-S61`.

⚠ **`BIL-Snn` IS A POINTER INTO A PDF, NOT A REPO TICKET** — the blueprint says so of
itself — so the blocker was found by **opening `BIL-S61`'s commitment card as an image
(p192)**, not by grepping the tree. Its `WAITS ON`, verbatim:

> *"**The taxonomy is written; two things are not.** Thirteen reasons in three classes,
> the strongest-class rule, the refusal of a document-class case with a money delta, and
> the five routed-away reasons all exist in code. ⚠ **The reason→class map is PROPOSED,
> not ratified**, and the tenant-extensible reason table **has no class column and is not
> built** — so a tenant's own reason is refused rather than defaulted."*

**Both halves are still live. Neither is what this lane fixed** — which is why the work
was not blocked. `BIL-S83`, the commitment that *is* this defect, reads **`STATUS New
build · WAITS ON —`**: nothing.

**And `BIL-S61`'s own `DONE LOOKS LIKE` is now met on its reachable half, walked to prove
it:** *"Ticking Goodwill renders 'issues a goodwill credit on the account, excluding tax:
the bill is not touched…' in the operator's words, and no mechanism dropdown exists
anywhere in the workflow."* Selecting **Goodwill** — now that word, not `goodwill` —
renders that exact sentence, at both doors, at both widths.

| Not built | Why |
|---|---|
| The four-step rail (`What and why · The correction · What it changes · Generate and send`) | REDESIGN, no `BUILD THIS` band; the tab is two stacked panels today |
| `WHY — PICK ONE OR MORE` as **checkboxes** (multi-select) | A behaviour change on a money path, inside a `Blocked` entry. The API already accepts `reason_codes` as an array; the screen was not changed to send more than one |
| The three `CLASS` group headings and the `CLASS` column | **A rule collision — see below** |
| The account's six-row bill history, `26.2`–`26.5` (per-class step 2s), `26.6`–`26.8` | No comparable surface; all REDESIGN, none with a `BUILD THIS` band |

⚠ **THE CLASS GROUP HEADINGS ARE A RULE COLLISION AND ARE LEFT FOR THE PO.** The drawn
heading `CLASS R · THE MONEY AND THE DOCUMENT BOTH MOVE — 7` is a **six-word heading
against rule 33's three-word LABEL cap**, and **`CLASS R` is an internal code against rule
32** — so building it as drawn would breach the very rule this fix exists to honour. Under
**B14 rule 41**, a drawing that contradicts a signed rule is what reaches the PO. **Nothing
was decided here and no substitute wording was invented.** The data is already on the
payload (`correction_class` travels beside every reason), so this is a copy decision, not a
build one.

---

## 5 · Two open items the brief asked this lane to record, deciding nothing

1. **The reason→class map is unratified.** Both the drawing and
   `correction_reasons.py` say so in the same words (*"PROPOSED — see the module
   docstring"*), and it decides whether a credit note issues. **It is `BIL-S61`'s first
   half and it is still open.** Not registered as an `OQ` by this lane — it is already
   named in `EP-BIL-04 §8` and ranked 8th of the nine that cost the most.
2. **The tenant-extensible reason table has no class column and is not built.**
   `BIL-S61`'s second half. The product already says so on screen and **that refusal is
   still true, so it was left standing**: `billing.fix.awaits` reads *"Cancelling a bill.
   Your own reason codes."* — grepped after landing, per the brief's rule that a refusal
   outliving its reason is the worse defect. It has not outlived its reason.

---

## 6 · Proof

| Check | Result |
|---|---|
| `npx tsc --noEmit` | **clean** — and proved *capable of failing* first: a planted type error was seen to fail, then removed. Local TypeScript 5.5.4 is installed, so it was not the silent-fetch false green |
| `npx vitest run` — the guard + `FixABillTab.dom.test.tsx` | **9/9** |
| `npx vitest run src/styles/routeBUtilities.test.ts` | **11/11** — `FixABillTab.tsx` is on `route-b-migrated.txt`, so the stricter checker owns it |
| Catalogue parity | all eleven at **16,784** keys after the fan-in, `+13 / −0 / ~0` each — no sibling row reworded |
| Built bundle | all **143** strings present in the artifact the browser downloads |
| Browser walk | `/billing/fix` and `/accounts/{id}/issue-credit`, at **1440 and 1280** |

**Screenshots:** `SCRATCH/step2-shots/` — `fix-reason-control-1440.png`,
`fix-reason-control-1280.png` (the control with a reason chosen and the derived sentence
under it), `fix-billing-tab-after-1440.png`, `fix-account-mount-after-1440.png`, and the
same two at 1280. The before state is the recorded option list in
`fix-reasons-before-1440.json` — **there is no matching before *screenshot* of the
control**, because the select sits below the fold until a bill is chosen, and that is
stated rather than implied.

### Reds, each with the date it was proved

**Two gates are red and NEITHER is this lane's.** Both were proved pre-existing by
running them **at the tip in a detached worktree, without this lane's change** — not by
assertion:

| Red | Dated how |
|---|---|
| **`G15`** — *398 NEW values pasted in English rather than translated* | **Identical output at the tip without this change**, same 398, same counts. And **0 of this lane's 130 non-English values are among them** — every one differs from English |
| **`G33`** — 3 refusal sentences over six words (`integrations.field.site_id`, `metering.import.parts_unwired`, `portal.documents.queueUnavailable`) | All three keys last touched in commit **`cf45a3d2`, 2026-09-13** — the day before this lane started. `git log -S` on each |

---

## 7 · What a sibling carried, and why the catalogues are not in this lane's commit

⚠ **A sibling's §03 commit `b6fe8821` swept all eleven catalogues while this lane was
mid-flight** — law 11 mechanism five, a pathspec commit publishing another lane's
in-flight work. That lane **self-filed it as `DEF-BIL-5241`**, which is the record working.

**Nothing was lost.** All **143** strings were verified landed at HEAD *with the tightened
wording*, so nothing needed re-landing. **The catalogues were deliberately left out of this
lane's commit**, because at the time of pushing they also carried that lane's in-flight
`billing.run.*` rewording — committing them would have been the same mechanism a second
time, in the other direction.

## 8 · Version

⚠ **Deliberately not bumped.** `2.261.4` is held by the Meter Reads lane **mid-bump** —
`07-frontend/package.json` has carried it since `c103ff7a` with **no CHANGELOG entry yet**
— and the standing rule is that a third number must not be written in that state. **This
change rides the next version**; its traceability is the commit sha recorded against
`DEF-BIL-5233` in the defect register. **No CHANGELOG entry was written**, for the same
reason: that file is mid-edit by the lane that owns `2.261.4`.
