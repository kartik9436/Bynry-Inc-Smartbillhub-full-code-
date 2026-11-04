# Portal accessibility — Groups D and E inventory (2026-10-23)

Lane A11Y-D. Group D: language, titles, headings (F-05, F-07, F-20). Group E: names of controls and links (F-12, F-14, F-23, F-24).
Rulings: decision log 2026-10-23, *"Group D … three choices confirmed"* and *"Group E … two answers"*. How it is built: decision log, *"Groups D and E: how it is built"*.
Defect rows: `DEF-CWP-10561` (F-05), `DEF-CWP-10562` (F-07), `DEF-CWP-10563` (F-20), `DEF-CWP-10564` (F-12), `DEF-CWP-10565` (F-14), `DEF-CWP-10566` (F-23), `DEF-CWP-10567` (F-24).

## How it was measured

- **Data:** a private copy of the Pine Hill / Oak Ridge sample fixture (`seed_portal_demo`; fake data only), signed in as the sample portal login.
- **Tool:** `10-scripts/a11y/portal_outline_scan.mjs` (read-only) in Chromium 1194 at 1280×900, with axe-core 4.10.3 pinned. It reads every route in `portalRoutes.tsx`: signed out and signed in, English then Spanish (switched through the app's own i18n handle). Per load it records `<html lang>` on arrival and after the switch, `document.title`, the heading outline with each heading's computed size, link names against their destinations, the quick-pay doors, unnamed controls, and axe's `select-name`, `link-name`, `button-name`, `label`, `aria-prohibited-attr`, `page-has-heading-one`, `heading-order`, `document-title`, `html-has-lang` and `valid-lang`.
- **Coverage:** the router holds **55** routes. **53** were loaded. Two were not: `/start-service/:draft`, whose link the form mints, and `/requests/:reference`, because this login has no request. That is **212 page loads** (53 × signed out/in × en/es). The tester counted 23 pages; these 53 include every one of them, since every portal page is a route here.
- **Dialogs:** the portal has none (`role="dialog"` / `aria-modal` / `<dialog>` occur 0 times under `src/portal`). The title rule for dialogs is built (an open dialog's heading wins) and has nothing to apply to yet.
- **Not run here:** screen readers (VoiceOver, NVDA, JAWS), Firefox and Safari. Only Chromium was available.

## Baseline (before any fix)

| Check | Before |
|---|---|
| `<html lang>` after switching to Español | `en` on **106 of 106** Spanish loads; the front page's own selector gives `i18n=es`, `html lang=en` |
| `<html lang>` on arrival | `en` on all 212 |
| Language names in the selector carrying their own `lang` | **0 of 2** options (`English`, `Español`) |
| Distinct tab titles | **1** — *"SMART360 Next"* on all 212 loads |
| Loads with no h1 | **77**: 72 signed out (36 signed-in addresses × 2 languages show the shared failure card, which has no heading), plus Home ×2 addresses × 2 languages, plus one load whose tab crashed |
| Loads with a skipped level (h1→h3, or an h3 above the h1) | **85** loads, **111** skips; axe `heading-order` 43 |
| Loads with an h3 above the page's h1 | **68** (the frame's *"Is anyone in danger?"* panel on every guest page) |
| h1 shared by two different pages | *"What do you need?"* (`CWP-001` front page, `CWP-046` Requests) and *"We cannot show that receipt here"* (`CWP-004`, `CWP-077` — both no-receipt states) |
| Links with one name and different destinations | **14** loads: *Start →* ×4 (front page), ×8 (What you have paid), ×3 (Requests); *See this center* ×2; *Open this document* ×2; *Download this document* ×2; *Open the bill this is on* ×2 — and their Spanish twins |
| *"Pay with a bill number →"* destinations | `/pine-hill/portal` (sign-in page) and `/pine-hill/portal/pay` (enrol) |
| axe `select-name` | **4** — Home's bill-month chooser (`#home-bill-month`), on `/` and `/home` in both languages |
| axe `aria-prohibited-attr` | 0 in the scan — the loading placeholder is on screen only while a read is in flight, and the scan waits for it to clear. It was confirmed in the code (below) and is asserted by a unit test |

## Group D — every similar place, and what was done

### F-05 · Language (3.1.1, 3.1.2)
| Place | Before | Done |
|---|---|---|
| `07-frontend/index.html` `lang="en"`, never updated | static | **The root:** `src/i18n/index.ts` sets `document.documentElement.lang` on every `languageChanged`, first load included. Both the portal and the staff app switch only through it |
| Guest language selector (`portal/shell/GuestLanguage.tsx`) | options unmarked | each option carries `lang={code}` |
| *How we contact you* → Language (`portal/details/Preferences.tsx`) | options unmarked | each option carries `lang` (through the shared `SelectInput`, which gained an optional `lang` per option) |
| Start-service *Preferences* → Language (`portal/guest/ApplicationPreferences.tsx`) | options unmarked | same |
| Help answer, *Also written in* list (`portal/guest/HelpPage.tsx`) | names joined as plain text | each name in its own `<span lang>` |
| Help answer, fallback sentence *"…shown in English"* | the name is unmarked inside the reader's sentence | the name is marked; the catalogue sentence is cut at the name, not re-keyed |
| Help answer body | in the server's chosen language, unmarked | `<article lang={shown_in}>` |
| Help answer's question (its h1) | unmarked | **not changed** — the shared `PageHeader` takes the title as a plain string |
| *Check and send* summary (`ApplyForService.tsx` `preferencesLine`) | a joined text line naming the language | **not changed** — a one-word value in a joined line |
| Staff settings language pickers (`SettingsRegionalTab`, `PortalLanguageField`, `BuildMessagesTab`) | catalogue-translated names | not in scope (staff app; their names are in the reader's language) |

### F-07 · Titles (2.4.2)
| Place | Before | Done |
|---|---|---|
| Every portal route (55) | *"SMART360 Next"* | **The root:** `portal/components/PortalDocumentTitle.tsx`, mounted once in `PortalApp`, writes *"<the page's h1> · <utility name>"* and follows the h1 as it changes (a wizard step, a sent panel, a language switch). A loading page shows the utility's name alone |
| Lane A11Y-BC's page announcement (`portal/components/a11y.tsx` `announcePage`) | read the h1 text itself | now speaks the same page name the tab title is built from (`portalPageName`), so what is heard and the tab agree; no second announcer was added |
| Staff app | per-screen title (BR-SHL-004, `AppShell.tsx`) | unchanged |

### F-20 · Headings (2.4.6, 1.3.1)
| Place | Before | Done |
|---|---|---|
| Shared `Panel` (`components/Panel.tsx`) title | always `<h3>` | in the portal, the outline's level (h2 under a page h1, h3 inside a section). Staff unchanged |
| `FormSection` (`portal/components/FormSection.tsx`) | always `<h3>` | outline level |
| `ErrandCard` (`portal/components/primitives.tsx`) | always `<h2>` | outline level (h2 on every card grid today) |
| Shared failure card `FailedWithRetry` (`components/StateFrame.tsx`), 27 portal call sites | `<p>` title, no heading | in the portal, `role="heading" aria-level="1"` on the same `<p>` |
| The signed-out card of `/final-bill` and `/stop-or-restart` (`portal/requests/signedOutState.tsx`) | no heading | a hidden h1 with the same words the other 34 addresses show, *"We could not open this page."* |
| Signed-in Home (`portal/home/Home.tsx`) | no h1 | hidden h1 *"Your account home"* on all three branches (loading, failed, loaded) |
| Front page vs Requests | both *"What do you need?"* | Requests reads *"Your requests"* (`portal.requests.title`, all eleven catalogues, from each catalogue's existing wording for that list) |
| `SectionTitle` (`primitives.tsx`) | a `<p>` small-caps label, not a heading | not changed — it is not in the outline at all |
| `content.tsx` FAQ question and centre name, `ReportSent`, `ReportRouted`, `AgreementAcceptance`, `FrontDoor` brand name | fixed `<h2>` | not changed — each sits directly under the page h1 or in the frame, so it is already correct |
| *"We cannot show that receipt here"* (`CWP-004`, `CWP-077`) | shared h1 in two no-receipt states | **not changed** — refusal states, not pages; rewording one is a product choice |

## Group E — every similar place, and what was done

### F-12 / unnamed controls
| Place | Before | Done |
|---|---|---|
| Home bill-month chooser `#home-bill-month` | no name (axe `select-name` ×4) | `aria-label` *"Bill month"* (`portal.home.billMonth`, eleven catalogues) through `SelectInput`'s new `ariaLabel` |
| Every other select / input / textarea / icon-only button on the 212 loads | named | — (the scan lists any unnamed control; none other found) |

### F-14 / loading placeholder
| Place | Before | Done |
|---|---|---|
| `LoadingSkeleton` (`components/StateFrame.tsx`), used by every portal `*Page.tsx` while it reads | `aria-label` on a role-less `<div>` (prohibited, dropped by browsers) | `role="status"`, so the name is allowed and announced. One shared root; the staff app's skeletons gain the same role |

### F-23 / repeated link names
| Place | Before | Done |
|---|---|---|
| `ErrandCard` actions — front page *Start →*, What you have paid *Start →*, Requests *Start →*, Help paying (`ErrandLink`); held cards (`HeldButton`) | one name, many places | the card provides its heading to its action: *"Start: Pay a bill"* (`portal.actionName`). Visible text unchanged |
| Ask us for something *Ask →* ×6 (`QuickService.tsx`, buttons) | one name | *"Ask: <card>"* |
| Documents rows and cards: *Open this document*, *Download this document* | one name per row | *"Open this document: BL-2610-000052"* |
| Readings rows: *Open the bill this is on* | one name | *"… : BL-2610-000052"* |
| Centre cards: *See this center* | one name | *"See this center: Main Office"* |
| Bills cards (phone layout): *See the whole bill →*, *See the bill we sent →* | one name per card | named for the card's bill number |
| *Pay* on the bills list, bill cards and bill detail | one name, ONE destination (`/pay-now`) | not changed — same name, same place is what 2.4.4 asks |

### F-24 / one function, one door, one name
| Place | Before | Done |
|---|---|---|
| Sign-in page *"Pay with a bill number →"* | went to the front page | goes to `/pay`, as on enrol |
| Home *"Ask for a plan"* vs elsewhere *"Ask for a payment plan"* | two names | Home takes each catalogue's *"Ask for a payment plan"* wording |
| *Your account* door *"Equipment"* vs Usage *"Meters and equipment"* | two names | *Your account* uses *"Meters and equipment"* (`portal.usage.seeEquipment`) |

## Emails and the bill PDF (report only)

- **Emails:** the HTML wrapper every email goes out in (`06-backend/apps/integrations/adapters/email_format.py`, `_WRAPPER`) declares **no** `<html lang>` at all, in any language. A Spanish email is therefore undeclared, as is an English one. Not changed (out of this group's scope).
- **Bill PDF:** after Group H (`DEF-BIL-10546`) the tagged PDF declares `/Lang en` from `DOCUMENT_LANGUAGE = "en"` in `apps/billing/documents.py`. Every word the bill prints is English, so the declaration is true. A Spanish bill does not exist.

## After (same scan, same data, build `bc33e4bb5`)

`10-scripts/a11y/portal_outline_scan.mjs --assert` judges every load against the rules above. It printed **596 failures before** and **2 after**:

| Check | Before | After |
|---|---|---|
| `<html lang>` after switching to Español | `en` on 106 of 106 | `es` on 106 of 106; English loads say `en` |
| Language selector options with their own `lang` | 0 of 2 | 2 of 2 (`English:en`, `Español:es`) |
| Distinct tab titles over 212 loads | 1 | 106. Each is the page's h1 then *"· Pine Hill Water & Power"*, e.g. *"Find your bill · Pine Hill Water & Power"*, *"Busque su factura · Pine Hill Water & Power"* |
| Loads with no h1 | 77 | 1 (see below) |
| Skipped levels | 111 | 0 |
| A heading deeper than h2 above the h1 | 64 | 0 |
| Loads with one link name for several destinations | 14 | 0 |
| Quick-pay destinations | front page and `/pay` | `/pay` only |
| axe `select-name` / `link-name` / `button-name` / `label` / `aria-prohibited-attr` | 4 / 0 / 0 / 0 / 0 | 0 / 0 / 0 / 0 / 0 |
| axe `heading-order` / `page-has-heading-one` | 43 / 77 | 0 / 1 |
| h1 shared by two pages | *"What do you need?"* on the front page and Requests | none. The no-receipt pair (`CWP-004`, `CWP-077`) is reported and left; the failure card on 71 signed-out loads is a state, not a page, and is counted apart |
| **Visual size of every heading** (computed font size, weight, bottom margin, case) | — | **382 of 382** headings present before and after are identical. New ones: the hidden h1s, *"Your requests"*, and the failure card's line (unchanged in look, now a heading) |

**The 2 remaining failures are one load:** signed-out English `/overdue` was captured blank (no heading, the default tab title), a page that had not drawn yet. The Spanish load of the same address passed. Re-opened by hand afterwards, it shows *"We could not open this page. · Pine Hill Water & Power"* with that line as its h1.

### Tests (red first)

`07-frontend/src/portal/a11y/groupDE.dom.test.tsx`, 19 cases. Run against the tip before the fix (`e5b264fb1`, product files only), **16 fail**; with the fix, **19 pass**. The 3 that pass on both are unit cases of the new title helper (the dialog rule, the failure-card line) and of the new outline component. They cover:
- `lang` after a switch, and every portal language picker carrying `lang`;
- the title format and that it follows the h1;
- a dialog's heading winning;
- the title component mounted once at the portal root;
- a Panel being h3 on a staff screen and the outline's level in the portal;
- the failure card's level-1 line;
- Home's hidden h1 and Requests' *"Your requests"* with clean outlines;
- the front page and Requests heading differing in all eleven catalogues;
- *"Bill month"*, and no unnamed control on Home;
- the placeholder's `role="status"`;
- each card's link named for its card;
- no two links of one name and different destinations on the front page and Requests;
- quick pay to `/pay` from sign-in, and from any source file using the quick-pay words;
- one name per function.

Every route is covered by the browser scan above, not by a unit test.

**Changed because they asserted the old behaviour:**
- `FrontDoor.dom.test.tsx` (quick pay expected the front page);
- `Documents.dom.test.tsx` (row controls selected by their old shared name);
- `pageHeadCensus.test.ts` (a hidden h1 on the one CORRECTLY_HEADLESS screen is not a second page head; any other h1 still is).

### Not run here

Screen readers (VoiceOver, NVDA, JAWS), Firefox and Safari. Only Chromium 1194 was available in this container.
