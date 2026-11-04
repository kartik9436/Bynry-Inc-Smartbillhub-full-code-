# CR-076 — Three things the Product Owner asked for on the template designer

**Arrived:** 2026-09-07, from the Product Owner, using the deployed Settings → Templates screen
(`SET-10`) on the live product. **Classified:** CHANGE (not a defect — the screen does what it was
built to do; the PO wants it to do something else). **Built and pushed:** 2026-09-07, one lane.

---

## 0 · CAPTURE — the requester's words, verbatim

Three items, and two of them arrived as a proposal the PO then corrected themselves:

1. **A surface switcher over the preview.** The PO proposed a fixed list of five —
   `printable · email · sms · in_app · contract` — was told what a hardcoded list costs on this
   codebase, and ruled: ***"you are correct - dont use hard coding"***.
2. **The Wording panel takes 60% of the width**, wording on the left. It was 25 / 75.
3. **A Print / Export PDF control on the preview.** The PO's own snippet opened a blank window and
   wrote `<pre>${preview.body}</pre>` into it; they then ruled: ***"you should print real rendered
   document"***.

---

## 1 · CLASSIFY

A CHANGE, all three. Nothing here reverses a defect report: the screen previews one surface because
that is what `CR-048` E2 built, it is 25 / 75 because that is what `CR-048` E1 required, and it has
no Print control because nobody had asked for one.

---

## 2 · WHAT SIGNED STATEMENT IS BEING REVERSED

**One, and it is item 2.** `CR-048` E1, ratified as part of that change request, reads:

> *"a quarter of the screen for the controls, three quarters for what the customer will actually
> hold"*

…with the argument that on a regulated notice *"the page is not a preview of the work — it IS the
work"*. **That argument is still true of LOOKING at a notice and is not true of WRITING one**, which
is what this screen is for, and a 344px-wide rail is what the PO has been living with. E1's ratio is
**SUPERSEDED by this CR** for `DESIGNER_FRAME` and for nothing else. The reasoning in
`notificationsKit.ts` was amended in the same commit as the number — a comment describing the
opposite of the code beneath it is worse than no comment (hard-won law 1).

**Nothing else is reversed.** No ❄️ FROZEN `B4`/`B5` figure is anywhere near this change; no money is
computed, read or displayed by any of it.

---

## 3 · IMPACT

| Surface | Effect |
|---|---|
| Screens | `SET-10` only. `SET-09` (the catalogue) is untouched. |
| API | ONE new served field, `preview_surfaces`, on `GET /template-catalog/{code}`. Additive; no field changed shape or left. |
| Schema | **None.** No migration. The answer is derived from `catalogs.CHANNELS_BY_KIND`, which already existed. |
| Open questions | None opened, none closed. `OQ-252` and `OQ-254` are cited by this screen and are untouched. |
| Rules | None invented, none moved. `BR-SHL-010` and `BR-SHL-025` are applied, not amended. |
| B14 | No rule added. Rules **21** (Tailwind per file), **31**, **33** (a refusal is five or six words) and **36** (compose the kit) are obeyed and are asserted by the new cases. |
| Locale | 10 new keys × 11 catalogues, through `10-scripts/i18n_fanin.py`. 10 insertions, 0 deletions in every one. |
| Demo fixture | Unchanged. Every figure in this CR was read off the seeded Brazos Bend utility. |
| Defects | **`DEF-NOT-4414` opened and closed inside this CR** — see §6. |

---

## 4 · WHAT IS ALREADY BUILT AND IS NOW WRONG

* `templateDesigner.dom.test.tsx` asserted `lg:grid-cols-[minmax(0,1fr)_minmax(0,3fr)]` by name. It
  asserts `lg:grid-cols-[3fr_2fr]`, and the comment beside it says which ruling moved it and when.
* **Five test fixtures did not carry the new field and `tsc` named all five**, which is the point of
  making it required rather than optional. **A sixth did not carry it and `tsc` said nothing**,
  because `templateCatalogGrouping.dom.test.tsx`'s "minimum shape" object has no type annotation —
  it went red at runtime instead, on `data.preview_surfaces is not iterable`. A fixture that opts
  out of the type opts out of every check that reads it.
* **Two fixtures were saying two different things about one class:** three cases overrode `group` to
  `sms` / `email` / `in_app` without overriding the served surface list. Fixed rather than papered
  over, and the screen also unions the class's own `group` into the list so a disagreement can never
  preview a class as something its own group does not name.
* **No lane was building on any of it.** The two siblings live in this tree were in
  `apps/payments`, `apps/integrations` and `server.mjs`.

---

## 5 · SIZE, IN PLAIN ENGLISH WITH THE FIGURES

One lane, one day. Three commits plus a defect fix. What a person sees, measured in Chromium at
1440 × 950 on the seeded utility:

* **The 10-day disconnect notice now has two tabs — *Printed page* and *Email*** — because the
  server says that class is a form for two channels. `sms_bill_ready` has **no tab strip at all**,
  because one tab is a control that cannot do anything. **32 of the 38 seeded classes are in that
  position**, so the common case is that the screen is exactly what it was.
* **The Wording panel measures 662px of 1104px — 60.0%.** Measured, not asserted from a class name.
* **Print opens the document that is on the screen**, with the page's own styles: the letter, its
  margins, its preserved line breaks, the locked *Required — cannot be removed* blocks and the
  *Preview only — sample data, nothing is sent* line. Choosing **Save as PDF** in the dialog gives a
  two-page PDF of exactly that.

---

## 6 · EXECUTE — what was built, and the defect it produced

**Backend.** `catalogs.designer_surfaces(kind, group)` maps a class's channels onto the surfaces the
designer draws, reading `CHANNELS_BY_KIND` — the only place in this repo that says what
*"Print + email"* MEANS. `pdf_print` resolves through the class's own `group`, so a contract prints
as a contract. It **raises** for a `kind` nobody has stated channels for; `templates_api._surfaces_for`
catches that at the payload boundary and serves `[]`, so an unknown kind costs the tab bar and not
the whole designer.

**Frontend.** The tab strip is `SurfaceTabs`, built from the served list, drawn only at two or more.
The composer does **not** follow the tab: this class has one body, one whitelist and one save, so a
subject box summoned by pressing a preview tab would be a field the renderer refuses.

**Print.** `printPreview.ts` copies the preview NODE — not `preview.body` — into a window of its own
with the page's own stylesheets. There is no server-side PDF to ask for instead, and the payload
already says so (`can_download_pdf: false`, *"the platform's page writer is billing's and it writes
bills"*).

### `DEF-NOT-4414` — opened and closed inside this CR

The first version of the print window carried **the right DOM with no CSS at all**: the whole notice
as one wall of serif text, no page, no inbox chrome, no preserved line breaks. The built page links
its stylesheet as `/assets/index-<hash>.css`, a root-relative URL, and the window opens at
`about:blank`, which has no base to resolve it against.

**`tsc`, thirteen DOM cases and every gate were green over it**, because jsdom loads no stylesheets:
the case proving the preview node travels into the print sheet was TRUE and said nothing whatever
about the printout. **The Chromium walkthrough is what found it** — hard-won law 6, exactly as
written. Every copied `href` is absolutised now; the walkthrough reads `getComputedStyle` in the
print window rather than only its DOM, and is committed at
`10-scripts/cr076_template_designer_walkthrough.mjs`.

### Evidence

| What | Result |
|---|---|
| `06-backend/tests/test_cr076_designer_surfaces.py` | 5 cases green. RED-proved through a pytest plugin that replaces the derivation with the hardcoded five: **4 of 5 fail**; the fifth is a different question and says so. |
| `templateSurfacePrint.dom.test.tsx` | 13 cases green. RED-proved through `./node_modules/.bin/vitest run` against the pre-change screen: **9 failed, 3 passed**, every failure quoted in the file and each pass labelled with why it is not evidence. |
| Whole notifications front end | 18 files, 237 cases, 1 todo — green. |
| `tsc --noEmit` | clean, through the LOCAL compiler. |
| `G31` · `routeBUtilities.test.ts` | PASS — 0 undeclared classes; both new utilities compile. |
| Chromium walkthrough | **no findings**, on `disconnect_notice_10_day`, `sms_bill_ready` and `contract_payment_plan`. |
| Gates checked BY NAME | `G13` PASS · `G31` PASS · `G104` PASS · `routeBUtilities` PASS. `G07` `G10` `G15` `G18` `G26` `G28` `G32` `G33` `G106` FAIL and **none of them on anything this lane wrote** — each was checked by name rather than by exit code. `G15` is the one this lane could have made worse and nearly did: it counts a value byte-identical to English, and the SMS tab's bare acronym added **8** to it (190 with them, 182 without, measured through the gate's own `measure()`). Adding to a red gate is how a red gate stays unread, so the label is now written the way each language writes it — *SMS-Nachricht · Mensaje SMS · Message SMS · Pesan SMS · Messaggio SMS · SMS メッセージ · Mensagem SMS* — which is what B14 rule 35 asks for anyway. **Not** by adding an exemption: that is a loosening of a ratified gate and belongs in the PO's batch. |

---

## 7 · VERSION

**The `<change>` digit is the INTEGRATOR's**, per the PO ruling of 2026-08-26 — *"NEVER IN ITS OWN
BRANCH… the bump is the INTEGRATOR's act, not the lane's"*. This lane built on **2.218.0** and did
not move it. Recorded rather than silently skipped: a step that is somebody else's and a step that
was forgotten look identical afterwards.

---

## 8 · CLOSE, AND THE ROLLBACK, STATED BEFORE SHIPPING

**Rollback is three reverts and no data changes.** `preview_surfaces` is a served field nothing
stores; dropping it makes every template preview as its own `group`, which is the screen of
2026-09-06. `DESIGNER_FRAME` is one string. `printPreview.ts` is a new file nothing else imports.
**No migration, no column, no row, and no signed figure moved.**

**What is NOT covered by this CR, stated so it returns to the agenda rather than reading as done:**

* **Fire's own surfaces are not in `CHANNELS_BY_KIND`** and neither are billing's classes
  (`bill_residential`, `bill_commercial`, `statement`), which have their own registry and never
  appear in `LISTINGS`. They are unaffected: this field is served only where a listing exists.
* **The five drawable surfaces are still written out once, in the client**, as the type guard that
  narrows a served string before it can be drawn. That is the DRAWING vocabulary, not the tab list —
  and the drift it could cause is guarded on the other side, by a backend case that asserts the
  derivable set is exactly those five and fails naming `TemplateDetail.tsx`.
* **Nothing here has been put to the Product Owner.** The review-ledger row of 2026-09-07 says what
  would be shown, in plain English, with its figures.
* **A RED THIS LANE DID NOT CAUSE, DATED RATHER THAN DISMISSED — `DEF-NOT-4436`.** Six cases of
  `test_cr049_t8_template_change_trail.py` fail: a print notice rests `queued` where the suite
  expects `sent`, and five more then assert `0 == 1`. Checked the way the law asks rather than
  asserted: the same file was run in a private worktree at **`32f41e34`, the commit this session
  started from**, and the **same six** fail there — 6 failed, 7 passed, 1 skipped, identical names,
  with `JOBS_EAGER` on and off. Filed rather than mentioned, because *"pre-existing"* said out loud
  and not written down is how a true red acquires the colouring of a known one.
