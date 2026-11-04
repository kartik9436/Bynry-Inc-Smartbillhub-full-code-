# CR-199-BRC10 · Templates screen redesigned, built from the drawing

**Raised:** 2026-10-29 by the Product Owner, in chat.

**Requester's words, verbatim:** *"Please build template redeisgn UI product screen using images and not content. Use -https://claude.ai/artifact/AoKYfff93LEMN5b2x5J6MB this html artifact start and complete all tasks"* — after approving the mock-up changes (*"1 A,2 A - update"*) and the language rule (*"B"*).

**The drawing:** `05-prototype/templates-redesign-2026-10-29/images/` (22 PNGs; README lists each). Built per B14 rules 42 (from the image), 37 (figures are illustrations) and 44 (our UI standard wins on construction).

## 1 · Classification
**MAINTENANCE — a live screen redrawn end to end** (`22-product-maintenance-process.md`: Settings › Templates exists and is used today), plus seven PO-reported defects (no + New variant, no Actions column, no rollback, earlier actions removed, no rich email/logo link, links not clickable, language when sending) and new capability (customer-category variants, logo link, rich email). Not the fast path: a schema change (variant axis), a money-adjacent dispatch rule (language), and a safety surface (rich content).

## 2 · What signed statement moves, and what stands
**SUPERSEDED (2026-10-29):** `OQ-CUS-12619` (a) for messages and `BR-NOT-006` as amended 2026-09-23 — a customer message now goes in `accounts.preferred_language`, falling back to the utility's default variant (decision log *"A message goes in the customer's preferred language"*). **Ruled the same day and built here:** A1 C, A2 A, A3 A, A4 B, 1A, 2A (decision log *"twelve questions"* and this CR's PO messages). **Stands:** BR-BIL-026 pin-at-queue; a reprint renders its pinned version and language; legal notices' System Admin approval; every rights footer; B4/B5 ❄️ untouched — no figure moves.

## 3 · Tasks (34) and lanes
Before building P1–P4 · server S1–S8 · screen F1–F9 · tests T1–T9 · prove-and-release R1–R4 — the list put to the PO on 2026-10-29. Lanes: **A Screens** (F1–F3, F6, F7, F9) · **B Variants & history** (S1–S3, F4, F5) · **C Email** (S4–S7, F8, T2) · **D Language + proof** (S8, T5, then R1–R4 by the coordinator).

## 4 · Already built and now wrong
`test_def_not_6354_messages_use_the_utility_language.py` asserts the superseded rule (replaced by lane D, never deleted for green). Every notification currently queued was pinned to the utility's language and keeps it (pin-at-queue) — no data rewritten.

## 5 · API for the screen lane — variants and history (lane B, TPL-SRV-VAR: S1–S3)
All under `/api/<tenant>/template-catalog/{code}/`; `{code}` is the class for the chosen CHANNEL (`email_bill_ready` vs `sms_bill_ready` — a channel is a class). Writes are System Admin only (403 otherwise). Refusals are `BIZ-STATE` with the `message_key` below (all eleven catalogues carry them); `params.detail` is diagnostic only.
- **`GET variant-options`** (any role) → `{code, channel, needs_approval, categories:[{value,label}], languages:[{value, code, is_utility_language}], start_from:["blank","published","variant"], taken:[{category, language, variant}], can_edit}`. `categories[0]` is `{value:"default", label:"All customers"}`, then the utility's own customer classes. `languages[0]` is `{value:"default", code:<utility tag>}`. `needs_approval` true = legal notice (primary button reads *Send for approval*).
- **`POST new-variant`** — *+ New variant* and *Duplicate as variant*. Body `{language, category, channel?, start_from, source_variant?, effective_from?, name?}`; `start_from:"published"` with no `source_variant` = the All-customers wording (*Start from English*); `"variant"` + `source_variant` = Duplicate. → 201 `{variant, version|null, started_from_version}`; `version` is the DRAFT (null for blank). Refusals: `notifications.templates.variant.exists` · `.languageNotOn` · `.categoryUnknown` · `.channelMismatch` · `.noSourceWording`.
- **`POST make-live-again`** — body `{version_id}` → 201 `{outcome:"live"|"sent_for_approval", version, restored_from_version, replaced_version}`. `live`: a NEW version holding that version's wording is published, the replaced one is archived (*"v1 goes out from now. v3 stays in history."* — the new number is `version.version`, its source `restored_from_version`). `sent_for_approval` (legal notice): the copy is a DRAFT and the live version keeps going out. Refusals: `notifications.templates.history.alreadyLive` · `.notEarlierPublished` · `.contractHasDates`.
- **History** (`GET {code}?variant=` → `versions[]`) now also carries `restored_from_version`, `can_make_live_again` (draw the button only when true) and `make_live_again_needs_approval`; each row's `subject`/`body` is THAT version's stored wording — preview from it.
- Judgments behind these (customer category = the utility's customer classes, not programmes; language before category; how "switched-on languages" is derived; a new version, never a moved pointer): decision log 2026-10-29, *"Templates: customer-category variants…"*.

## 5b · API for the screen lane — email (lane C, TPL-SRV-EMAIL: S4–S7)
Rule `BR-NOT-1042`; judgments: decision log 2026-10-29, *"Rich email wording is stored as a closed text markup"*.
- **Stored markup** (what Bold / Link / Button / List write): `**text**` · `[label](target)` · `[[label|target]]` · `- item` lines · blank line = new paragraph. `target` = `https://…` or ONE link placeholder (`{pay_link}`). Never write HTML.
- **`GET {code}`** adds `body_formats` (`["plain","rich"]` on email, `["plain"]` otherwise); each `versions[]` row has `body_format`; each `merge_field_rows[]` row has `label` ("First name") and `kind` (`"link"`|`"text"`, the picker's *link* tag); `pay_link`/`portal_link` carry the REAL address as `sample_value` (or `sample_unavailable` "No public address on this server").
- **`POST draft`** and **`POST preview`** accept `body_format` (`plain` default | `rich`; else 422 `notifications.templates.bodyFormatUnknown`).
- **Preview response** adds `text` (plain-text part, links as full addresses) · `html` (the whole branded document — draw it ONLY in `<iframe sandbox="" srcdoc=…>`) · `body_format` · `branding {brand_primary_hex, band_hex, ink_hex, has_logo, logo_url, logo_link_url, utility_name}` (image 02's "Springfield blue · Logo links to …") · `errors[]`/`warnings[]` each `{code, message_key, params}` · `plain_source` (markup turned into plain wording, for Rich → Plain). An unknown placeholder no longer fails the preview: it renders as typed and is in `errors`.
- **Save refusals** (422, `field_errors` on `body`): `notifications.templates.placeholderUnknown` (`params.placeholder` = `{bogus}`) · `…htmlNotAllowed` · `…linkTargetNotAllowed` (`params.target`). **Warning only**: `…linkAsText` (`params.placeholder`). All in the eleven catalogues.
- **Settings › Company › Branding**: `brand_logo_link_url` on `GET/PUT /settings/company`, `https://` only (`settings.company.logoLinkHttps`); the "Logo link" input is BUILT under the two colours.
- **Lane B:** `make-live-again` and `new-variant` copy `body_format` with the wording (wired by lane C in `template_variants.py`).

## 5c · API for the screen lane — language (lane D, TPL-SRV-LANG: S8)
- **`GET /template-languages`** — lane D (TPL-SRV-LANG, S8). For the tenant in context: `{default_language, languages: [{value, language, accounts, is_default, no_preference}], total}` — how many accounts prefer each language. The rows are exactly §5's switched-on languages (`variant-options` → `languages[]`), joined by the same `value` (`default` = the utility's language); accounts with no preference, or preferring the utility's own language, count on the `default` row (`no_preference` says how many stated nothing); a stored code the picker does not list is still a row, so rows sum to `total`. Codes are exact (`es-MX` ≠ `es`; an `es-MX` account receives `es` wording when only `es` is published, so the screen adds regional rows to their base for a variant). One grouped statement — an aggregate, not a list. A literal prefix of its own so no `template-catalog/<code>` path can claim it. Served by `apps/notifications/template_languages_api.py`. Feeds the drawing's *"Español · 312 customers"* (image 16).
- **Messages (S8, no new route):** `queue_document` gains `preferred_language=` (default: read from `account_id`); `language=` is now the utility's FALLBACK. `GET /accounts/{id}/communication` adds `fallback_language` beside `language` (now the account's language, or the utility's when none is stated).

## 5d · API for the screen lane — the list's facets (lane TPL-SRV-FACETS, `DEF-NOT-10672`)
- **`GET /template-catalog`** adds, over the whole filtered catalogue and never a page: `channels:[{key,count}]` (`email` · `sms` · `in_app` · `pdf_print`, counted under every filter but the channel) and `channels_total`; `languages:[{key,count}]` (the switched-on languages, `key` the BCP-47 tag, `count` templates written in it); `statuses:[{key,count}]` (`published` · `draft` · `not_published` · `needs_approval`). Each row adds `languages:[{code,written}]`, `has_draft`, `status` (one of the first three, as the pill reads) and `needs_approval`. Filters `f.channel`, `f.language`, `f.status`; an unknown value falls back. No `label` on a language — the screen names it (`languageName`). Served by `apps/notifications/template_list.py`; judgments in the decision log 2026-10-29, *"Templates list: what the chips…"*.
- **Not built:** a second sample customer for the preview's sample switch — the preview holds one typed sample set per class, and a second would be invented data.

## 6 · P2 — every action the live screen offers today, and where it lives in the redesign

Measured 2026-10-29 by lane TPL-WEB on `f89a2ea1c` (`TemplateCatalog.tsx`, `TemplateDetail.tsx`), before any change. **Nothing on this list may be lost** (PO defect #4, *"actions removed"*); `templateNothingRemoved.dom.test.tsx` asserts each one by its control.

**List (SET-09)**

| # | Today | In the redesign |
|---|---|---|
| L1 | Search box (name, code, category, used-by) | Same box, the table toolbar |
| L2 | Category filter (`f.category`) | Category filter |
| L3 | Kind filter — letters vs bill layouts (`f.template_kind`) | Kept as a filter beside Category / Language / Status |
| L4 | Sort by name, kind, category, variants, last edited | Same sorts |
| L5 | Column chooser, page footer (shared `DataTable`) | Unchanged |
| L6 | Open a template by its name | Unchanged |
| L7 | Row 👁 View | Row 👁 View |
| L8 | Row ✎ Edit (disabled with its reason for a read-only role) | Row ✎ Edit wording — opens the workspace already editing |
| L9 | Per-channel icon buttons on a folded event row (open the email / the text of one event) | The Channels cell's chips, each opens that channel |
| L10 | `+ New variant` in the title row (inline form: template, name, audience, language) | `+ New variant` in the workspace action bar (`06`), and row `…` → Duplicate as variant (`10`) |
| L11 | A bill-layout row opens the layout chooser, with a back button | Unchanged |
| L12 | Read-only strip with the server's reason | Unchanged |
| L13 | In-use / not-in-use / no-wording status pill with its sentence on hover | Status cell, beside Published / Needs approval |
| L14 | Rows grouped by event (email + text of one notice fold into one row) | Unchanged — that fold IS the Channels column |

**Workspace (SET-10)**

| # | Today | In the redesign |
|---|---|---|
| W1 | ← Templates (back, keeps the list's filters) | ← Templates |
| W2 | Variant tabs (audience × language), default and state badges | Language + Customers pickers (`02`); the state is the status line |
| W3 | Sibling-surface switcher (other channels of the same notice) | Channel picker (`02`, `05`) |
| W4 | Edit wording / Done editing | View · Edit wording (`02`, `03`) |
| W5 | Send test to me + its reason + the result sentence | Send test (`12`) — same reason, same result line |
| W6 | Duplicate as variant (inline form) | Duplicate as variant (`10`) |
| W7 | Preview-as tabs (printed page / email of one wording) | Kept inside the Preview panel |
| W8 | Print preview | Kept inside the Preview panel |
| W9 | Set as default (disabled, with its reason) + Default pill | Kept inside the Preview panel |
| W10 | Preview caption, unfilled placeholders, unsampled tokens, locked rights blocks | Kept inside the Preview panel |
| W11 | Merge-field panel with sample values; insert on click while editing | `+ Insert placeholder` picker with search (`03`) |
| W12 | Where it's used | Head line under the title |
| W13 | History summary + link to `?view=history` | History (`07`) — still `?view=history`, so it links and reloads |
| W14 | History: open a version in the editor | History row action |
| W15 | History: Publish a draft | History row action + the bar's Publish (`11`) |
| W16 | History: Restore an old version as a new draft | History row `…` → Copy to draft; Make live again (`08`) when the server lands it |
| W17 | History: Changed cell → change record (fields moved, letters still on the old wording) | Kept, History's Changed column |
| W18 | History: pinned-by count, never-deleted mark | Kept, in the Status cell |
| W19 | Deactivate variant (danger, confirm) · Reactivate (disabled, with the way back) · language note | Kept, a `Variant` panel under the workspace |
| W20 | Create from our default (contracts, dated) + the offered wording | Kept, in the Preview panel's place for a class with no variant |
| W21 | Subject (email), body, SMS meter (count · texts · left · cost warning) | Wording panel (`02`, `05`) |
| W22 | Save as new version | Save draft |
| W23 | Download sample PDF (disabled, with its reason) | Kept in the Preview panel |
| W24 | Live preview while typing (server render, 400ms) | Unchanged — always the server's render |
| W25 | Refusal strip, read-only strip, "nobody has written this" strip | Unchanged |
| W26 | Customer rights wording card under a disconnection letter | Unchanged |

## 7 · Version
Assigned at release by the coordinator.
