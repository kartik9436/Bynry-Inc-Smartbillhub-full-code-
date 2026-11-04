"""G15 — i18n catalogue parity.

Added 2026-08-10 by Eng-Lead, from a gap the gate suite had never looked at:
`07-frontend/src/i18n/locales/` holds five catalogues and NOTHING compared them.
The S1 landing-page port (US-TEN-018) added eighteen `public.plan.*` keys to
`en.json` and to no other catalogue. Every one of G1–G14 passed. A Spanish,
German or Hindi prospect saw the raw key `public.plan.starter.f1` printed in the
pricing card, because i18next renders the key itself when the lookup misses and
`fallbackLng: "en"` only helps when the key is absent from the *active* bundle —
it is, so the fallback fires, and the page silently reverts to English mid-card.
Either way the shipped page is wrong and no check said so.

This is hard-won law 1 in catalogue form: `index.ts` registers five languages,
which reads as a promise that five languages work. The promise was a comment.

Two assertions, both cheap and both exact:

  1. KEY SETS — every catalogue carries exactly the keys `en.json` carries.
     Missing keys are the defect above. EXTRA keys are the same defect running
     backwards: a key deleted from English but left behind elsewhere is dead
     weight nothing renders, and it hides the next real drift in the diff.
  2. UNTRANSLATED VALUES — a value byte-identical to English in a non-English
     catalogue is a paste-in that was never translated. Genuine exceptions
     (the product name, acronyms, units, sample data, and the loanwords German
     really does spell the English way) are named ONE BY ONE in the allowlists
     below. No heuristic decides this: a word is exempt because a human wrote
     it down here, and adding a word is a reviewable diff.

The allowlists are keyed by VALUE, not by catalogue key, so a new "Status"
column in German needs no new row — but an untranslated *sentence* never
matches one and always fails.

Proven RED before trusted green (law 7): with `public.plan.scale.f5` deleted
from `de.json` the gate named it — "de.json is missing 1 key(s) en.json has:
public.plan.scale.f5" — and with the key restored it went green.

RATIFIED 2026-08-11 by the PO (option A, "keep all four blocking"): G1-G16 are
the confirmed merge-blocking set. G13-G16 were Eng-Lead additions made from
defects that reached the running product; they are now confirmed law, so a
loosening here - an allowlist entry, a skipped check, a widened pattern - is a
change to a ratified decision and belongs in the daily PO batch.

Python 3.12 stdlib only. Safe to run from any cwd.
"""

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
LOCALES = REPO / "07-frontend" / "src" / "i18n" / "locales"
BASE = "en.json"

# ── Allowlist: values that may legitimately read the same in a translated
# catalogue as they do in English. EXPLICIT, one entry per string. If a new
# string belongs here, add it here — do not widen the rule.

# Identical in EVERY catalogue: nothing here is a word of any language.
UNIVERSAL = frozenset(
    {
        # Added 2026-10-21 (CR-187-BRC10 integration lane: the gettingIn, theDay and reads waves'
        # field.* keys fanned in): the value as this language writes it.
        "{{address}} · {{n}}",
        "{{lat}}, {{lng}} · ±{{acc}} m {{away}}",
        "Google Maps",
        "Apple Maps",
        "{{mb}} MB",
        # ⚠ THE PRODUCT NAME IS NOT HERE ANY MORE — see `PRODUCT_NAME_KEYS`
        # below. From 2.445.15 until 2026-10-02 its halves sat in this list,
        # and because this list matches on TEXT, the edition half "Next"
        # exempted EVERY key whose value was the bare word "Next": a pager
        # button pasted in English would have passed unflagged.
        # "Runbooks" — a COINED WORD, not an English one, and the PO ruled it
        # deliberately: "we coin the word Runbooks - we should make this
        # industry standard" (2026-09-06). The decision log of that day says the
        # name "governs the module, the nav word, the page head and every
        # catalogue string in all eleven languages", which is what puts it here
        # rather than in LOANWORDS: it is the same proper noun everywhere, like
        # the product name above, and NOT a paste-in nobody translated.
        # ⚠ This exempts the NAME and nothing else. The prose that goes with it
        # is translated in all eleven catalogues and would fail here if it were
        # not (B14 rule 35) — `runbooks.home.subtitle`, *"Checks report. Actions
        # send."*, is the sentence to check that claim against today.
        # ⚠ THIS NOTE NAMED `shell.notBuilt.runbooks.body` AND `.waiting` UNTIL
        # 2026-09-06: those two keys were the not-built-yet copy for the rail
        # entry, and they LEFT all eleven catalogues the hour CR-075 wave D task
        # D2 landed RBS-001 at `/{tenant}/runbooks`. A comment naming a key
        # nothing holds is hard-won law 1 inside a gate.
        "Runbooks",
        "SMARTBillHub — W0 scaffold",
        # Pure interpolation, punctuation and glyphs — no translatable word.
        "{{amount}}",
        "{{user}}",
        "×{{multiplier}}",
        "{{label}}: {{value}}",
        # The sidebar user block's second line (S48). Two interpolations and a
        # middle dot: the EMAIL is not translatable and the ROLE arrives from
        # the server already localised, so a "translation" here could only
        # reorder two placeholders. Added 2026-08-11 with the user menu.
        "{{email}} · {{role}}",
        # The one-time bill's counted-asset cell (`1 cart · CART-J70A1`,
        # DEF-BIL-8316, 2026-09-30): the UNIT arrives from the tariff and the
        # LABELS are asset numbers, so nothing here is a word of any language.
        "{{count}} {{unit}} · {{labels}}",
        # SET-10's history entries, in the rail beside the rendered document
        # (2026-09-07). A DATE the server formats in the tenant's own Regional
        # format, a middle dot, and the version — so the only letter in the
        # string is the `v`, and a "translation" could only reorder two
        # placeholders. It is the same shape as `templates.detail.
        # changeRecordTitle` (`v{{from}} → v{{version}}`) two panels along, which
        # is carried in `g15_untranslated_baseline.txt` instead; that is the
        # BACKLOG file, and a string with no translatable word in it is not
        # backlog — it is this list's own case, in this list's own words:
        # *"nothing here is a word of any language"*.
        "{{date}} · v{{version}}",
        # CWP-034's METER cell and CWP-037's EQUIPMENT cell (2026-09-05).
        # Both join two values the SERVER supplies already in the tenant's own
        # words — a service's name and a meter's serial, a service's name and
        # an asset type's name — so a catalogue that keeps the English order
        # has nothing left to translate but a space or a middle dot. Exactly
        # `{{email}} · {{role}}`'s case two lines up. The catalogues that DO
        # reorder them have: de writes `{{kind}} ({{service}})`, es and pt-BR
        # write `{{kind}} de {{service}}`, ja-JP drops the space entirely.
        "{{service}} · {{serial}}",
        "{{service}} {{kind}}",
        # The APPROVE window's CHECKS list (DEF-CUS-6350, 2026-09-23). Each
        # fact beside a tick is a value the server supplies in the tenant's own
        # words — the property's name and town already composed as `place`, a
        # unit's number and its label — so a catalogue has nothing to
        # translate but a middle dot. `{{email}} · {{role}}`'s case again.
        "{{place}}",
        "{{unit_no}} · {{label}}",
        "—",
        "9+",
        # Industry acronyms and units of measure (A16 glossary terms).
        "AMI",
        "kWh",
        "kgal",
        "LATE, CONN, DISC, NSF, DEPO-R, TAMPER",
        # Sample/placeholder data shown in a field, not prose.
        "alex@utility.com",
        # Language endonyms: every catalogue names a language the way that
        # language names itself, so the switcher reads the same everywhere.
        "Deutsch",
        "English",
        "English (US)",
        "Español",
        "Español (México)",
        "हिन्दी",
        # Added 2026-10-04 by lane I18N (CR-168-BRC10 §25). Work's joins and
        # times: two server values and a middle dot or a space, or a 24-hour
        # window every one of the ten languages writes this way. The order
        # number, a job type's name, a holder's name and kind, a photo's time
        # and device, and a builder column's own label all arrive already in
        # the tenant's words. `{{email}} · {{role}}`'s case again.
        "{{order}} · {{type}}",
        "{{name}} · {{kind}}",
        "{{taken}} · {{device}}",
        "{{column}} {{row}}",
        # `DEF-MET-10164` (2026-10-17): the Age cell's join, `30 yrs` + `7 mos`.
        # Both halves are already translated plural forms (`common.age.years_*`,
        # `common.age.months_*`); the join is two placeholders and a space, and
        # the catalogue that writes it differently (ja-JP: no space) does.
        "{{years}} {{months}}",
        "08:00–12:00",
        "12:00–17:00",
        # Added 2026-10-04 by lane I18N (CR-168-BRC10 §25.5, DEF-GOV-9597): ageing
        # bands, file formats and industry acronyms (DSO, ERP, ACH, SMS, API), two
        # e-mail providers' names, sample numbers shown in a field, and strings
        # that are only placeholders joined by a dot, a dash, a sign or a
        # currency symbol — nothing in them is a word of any language. A
        # percent sign, a colon and a month-year order are NOT here: French and
        # German set them apart with a space, Japanese reorders the date, so
        # those four sit on the per-language lists of the catalogues that write
        # them the English way.
        "1–30",
        "31–60",
        "61–90",
        "90+",
        "CSV",
        "DSO",
        "ERP",
        "SMS",
        "ACH",
        "+ API",
        "{{count}} API",
        "Postmark",
        "SendGrid",
        "AC-2026-00027",
        "BL-2608-0141",
        "billing@yourutility.example",
        "{{kw}} kW",
        "{{sentence}}",
        "{{total}}",
        "{{period}}",
        "{{n}} × {{amount}}",
        "{{word}} {{on}}",
        "{{service}} · {{from}} — {{to}}",
        "{{category}} · {{plan}}",
        "{{unit}} · {{premises}}",
        "{{register}} · {{unit}}",
        "{{number}} · {{amount}}",
        "{{number}} · {{customer}}",
        "{{report}} →",
        "{{name}} +{{count}}",
        "{{name}}, {{date}}",
        "({{current}} − {{prior}}) × {{multiplier}} = {{usage}}",
        "{{kind}} · {{size}}",
        "~{{pages}}",
        "{{from}}–{{to}}",
        "${{amount}}",
        # Added 2026-10-05 by lane MVI-I18N (CR-171-BRC10 P2.37, DEF-CUS-9746):
        # the move-in completed screen's unit line. The unit's label and its
        # before/after states arrive already in the tenant's words, joined by
        # a middle dot and an arrow — nothing in it is a word of any language.
        "{{unit}} · {{was}} → {{now}}",
        # Added 2026-10-15 (DEF-CUS-10162, the Usage tab's Source cell): the
        # read log's own transport word and method word, each already
        # translated, joined by brackets. ja-JP and ko-KR write their own
        # bracket forms; the Latin-script catalogues keep these.
        "{{source}} ({{method}})",
        # Added 2026-10-21 (CR-187-BRC10, the field app's words fanned in under field.*): symbols and units, the same in every language —
        # the QR and PDF names, the file-size units, the hour sign in
        # "1h 12m", and a distance in kilometres.
        "QR",
        "PDF",
        "KB",
        "MB",
        "h",
        "{{value}} km",
        "{{value}} km · {{minutes}} min",
    }
)

# Identical in ONE language because that language spells the word that way.
# Scoped per catalogue on purpose: "Compliance" is a real German business word
# and is NOT a Spanish one, so leaving it English in es.json must still fail.
LOANWORDS = {
    # "Cheque" added 2026-08-24 (CR-030 W4 payment methods): it is the ordinary
    # Spanish noun for a cheque, not an untranslated paste-in. Same word, same
    # spelling, in both catalogues and in pt-BR below.
    "es": frozenset(
        {
            # Added 2026-10-21 (CR-187-BRC10 integration lane: the gettingIn, theDay and reads waves'
            # field.* keys fanned in): the value as this language writes it.
            "{{m}} min",
            # Added 2026-10-21 (CR-187-BRC10, the field app's words fanned in under field.*): the word as
            # this language writes it.
            "Normal",
            "Material",
            "No",
            "Plan",
            "Gas",
            "Solar",
            "Federal",
            "Firmware",
            "Mult.",
            "(sub)",
            "Cheque",
            # Added 2026-10-04 by lane WORDS, judged one by one under the PO's
            # test of that day (decision log, *"A WORD SPELLED THE SAME AS
            # ENGLISH STAYS ONLY IF IT IS WHAT A NATIVE SPEAKER ACTUALLY
            # SAYS"*; CR-168-BRC10 §19.2). NATIVE-REVIEW-OWED (B14 rule 35).
            # "min" is this language's own abbreviation for minutes, the one
            # the catalogue already prints on the bill-run tile.
            "{{value}} min",
            # Added 2026-10-04 by lane I18N (CR-168-BRC10 round 6, §25), judged one
            # by one under the PO's native-speaker test (decision log *"A WORD
            # SPELLED THE SAME AS ENGLISH STAYS ONLY IF IT IS WHAT A NATIVE SPEAKER
            # ACTUALLY SAYS"*). NATIVE-REVIEW-OWED (B14 rule 35).
            # "KB"/"MB" are the unit symbols this language writes for a file
            # size (French alone writes Ko/Mo, and its catalogue does).
            "{{count}} KB",
            "{{size}} MB",
            # The same "min" abbreviation lane WORDS kept, on the field
            # visit, the phone card and the template task rows.
            "{{count}} min",
            "{{minutes}} min",
            # the version prefix "v", as fr/it/id/ja/ko/pt already carry.
            "v{{version}}",
            # Added 2026-10-04 by lane I18N (CR-168-BRC10 §25.5, DEF-GOV-9597),
            # judged one by one under the PO's native-speaker test.
            # NATIVE-REVIEW-OWED (B14 rule 35).
            # Spanish words spelled the English way: *total*, *manual*, *portal*,
            # *digital*, *base*, *plan*; *hash* as Spanish IT staff say it; *sub*
            # and *est.* the abbreviations of submedidor and estimada.
            "Total",
            "Manual",
            "Hash",
            "Portal",
            "Digital",
            "Sub",
            "{{name}} (portal)",
            "est.",
            "{{size}} × {{count}} · base {{base}}",
            "{{units}} · {{count}} plan",
            "{{what}}: ${{amount}}",
        }
    ),
    "es-MX": frozenset(
        {
            # Added 2026-10-21 (CR-187-BRC10 integration lane: the gettingIn, theDay and reads waves'
            # field.* keys fanned in): the value as this language writes it.
            "{{m}} min",
            # Added 2026-10-21 (CR-187-BRC10, the field app's words fanned in under field.*): the word as
            # this language writes it.
            "Normal",
            "Material",
            "No",
            "Plan",
            "Gas",
            "Solar",
            "Federal",
            "Firmware",
            "Mult.",
            "(sub)",
            "Cheque",
            # Added 2026-10-04 by lane WORDS, judged one by one under the PO's
            # test of that day (decision log, *"A WORD SPELLED THE SAME AS
            # ENGLISH STAYS ONLY IF IT IS WHAT A NATIVE SPEAKER ACTUALLY
            # SAYS"*; CR-168-BRC10 §19.2). NATIVE-REVIEW-OWED (B14 rule 35).
            # "min" is this language's own abbreviation for minutes, the one
            # the catalogue already prints on the bill-run tile.
            "{{value}} min",
            # Added 2026-10-04 by lane I18N (CR-168-BRC10 round 6, §25), judged one
            # by one under the PO's native-speaker test (decision log *"A WORD
            # SPELLED THE SAME AS ENGLISH STAYS ONLY IF IT IS WHAT A NATIVE SPEAKER
            # ACTUALLY SAYS"*). NATIVE-REVIEW-OWED (B14 rule 35).
            # "KB"/"MB" are the unit symbols this language writes for a file
            # size (French alone writes Ko/Mo, and its catalogue does).
            "{{count}} KB",
            "{{size}} MB",
            # The same "min" abbreviation lane WORDS kept, on the field
            # visit, the phone card and the template task rows.
            "{{count}} min",
            "{{minutes}} min",
            # the version prefix "v", as fr/it/id/ja/ko/pt already carry.
            "v{{version}}",
            # Added 2026-10-04 by lane I18N (CR-168-BRC10 §25.5, DEF-GOV-9597),
            # judged one by one under the PO's native-speaker test.
            # NATIVE-REVIEW-OWED (B14 rule 35).
            # Spanish words spelled the English way: *total*, *manual*, *portal*,
            # *digital*, *base*, *plan*; *hash* as Spanish IT staff say it; *sub*
            # and *est.* the abbreviations of submedidor and estimada.
            "Total",
            "Manual",
            "Hash",
            "Portal",
            "Digital",
            "Sub",
            "{{name}} (portal)",
            "est.",
            "{{size}} × {{count}} · base {{base}}",
            "{{units}} · {{count}} plan",
            "{{what}}: ${{amount}}",
            "Industrial",
        }
    ),
    "de": frozenset(
        {
            # Added 2026-10-21 (CR-187-BRC10 integration lane: the gettingIn, theDay and reads waves'
            # field.* keys fanned in): the value as this language writes it.
            "Normal",
            # Added 2026-10-21 (CR-187-BRC10, the field app's words fanned in under field.*): the word as
            # this language writes it.
            "Material",
            "Online",
            "Offline",
            # Everyday German nouns that happen to be spelled the English way.
            "Status",
            "Audit",
            "Code",
            # Added 2026-08-24 with the CR-030 W4 catalogue. German writes the
            # actor of an automated timeline entry as "System", exactly as
            # English does — the same class as "Status" and "Audit" above.
            "System",
            "Name",
            "Route",
            # Added 2026-08-26 with the CR-038 W5 catalogue (the S29 tag row).
            # German writes "Route R-1" exactly as English does — the same
            # noun as the bare "Route" above, with the code interpolated.
            # ⚠ Allowlist addition — rides the daily PO batch per this file's
            # ratification note.
            "Route {{route}}",
            # Added 2026-10-04 by lane WORDS, judged one by one under the PO's
            # test of that day (decision log, *"A WORD SPELLED THE SAME AS
            # ENGLISH STAYS ONLY IF IT IS WHAT A NATIVE SPEAKER ACTUALLY
            # SAYS"*; CR-168-BRC10 §19.2). NATIVE-REVIEW-OWED (B14 rule 35).
            # "Person" is the ordinary German noun for the person a crew
            # member is (eine Person); nobody would say anything else.
            "Person",
            # Added 2026-10-04 by lane I18N (CR-168-BRC10 round 6, §25), judged one
            # by one under the PO's native-speaker test (decision log *"A WORD
            # SPELLED THE SAME AS ENGLISH STAYS ONLY IF IT IS WHAT A NATIVE SPEAKER
            # ACTUALLY SAYS"*). NATIVE-REVIEW-OWED (B14 rule 35).
            # "KB"/"MB" are the unit symbols this language writes for a file
            # size (French alone writes Ko/Mo, and its catalogue does).
            "{{count}} KB",
            "{{size}} MB",
            # the version prefix "v", as fr/it/id/ja/ko/pt already carry.
            "v{{version}}",
            # Ordinary German words: der Link, optional, die Routine (a routine
            # job, beside Dringend), die Version (the template list column).
            "Link",
            "Optional",
            "Routine",
            "Version",
            # Added 2026-10-04 by lane I18N (CR-168-BRC10 §25.5, DEF-GOV-9597),
            # judged one by one under the PO's native-speaker test.
            # NATIVE-REVIEW-OWED (B14 rule 35).
            # Ordinary German words spelled the English way.
            "Standard",
            "Digital",
            "Export",
            "Budget",
            "Format",
            "Option",
            "Bank",
            "optional",
            "Post",
            "Block",
            "APIs",
            "{{count}} APIs",
            "Version {{version}}",
            "Route {{route}} — {{name}}",
            "Route · {{name}}",
            "{{month}} {{year}}",
            "Details",
            "Website",
            "Compliance",
            "Dashboard",
            "Firmware",
            "Gas",
            "Solar",
            # Meter-reading method — the trade uses the English term.
            "Drive-by",
            # Months German spells exactly as English does (März, Mai and the
            # rest differ and are deliberately absent).
            "April",
            "August",
            "September",
            "November",
        }
    ),
    # ── The six locales added 2026-08-11 (BR-SHL-041's eleven-locale expansion,
    # PO ruling 2026-08-10) ────────────────────────────────────────────────────
    # Every entry below is a value the machine-translation pass returned
    # UNCHANGED and a reader has confirmed the language really spells that way.
    # Scoped per catalogue exactly like the German block above: "Total" is a
    # French and a Portuguese word and is NOT an Italian one, so leaving it
    # English in it-IT must still fail.
    #
    # ⚠ ADDING TO THIS BLOCK IS A LOOSENING OF A RATIFIED GATE and belongs in
    # the daily PO batch (see the ratification note in this file's docstring).
    # The block as it stands is on the batch for 2026-08-11.
    "fr-FR": frozenset(
        {
            # Added 2026-10-21 (CR-187-BRC10 integration lane: the gettingIn, theDay and reads waves'
            # field.* keys fanned in): the value as this language writes it.
            "Normal",
            "{{count}} photo",
            "{{count}} photos",
            "{{n}} photos",
            "{{photos}} photos",
            "{{miles}} miles",
            "miles",
            "Position · ±{{acc}} m",
            "{{m}} min",
            # Added 2026-10-21 (CR-187-BRC10, the field app's words fanned in under field.*): the word as
            # this language writes it.
            "Distance",
            "Klaxon",
            "Menu",
            "Miles",
            "Photos",
            "{{value}} miles",
            "{{value}} miles · {{minutes}} min",
            # Ordinary French words that happen to be spelled the English way.
            "Action",
            # Added 2026-10-04 with CR-168 round 2 (the work order page, lane
            # ORDER-PAGE): *une signature*, *des minutes* (a column of minutes)
            # and *une photo* are the ordinary French nouns, spelled the English
            # way. NATIVE-REVIEW-OWED (B14 rule 35).
            "Signature",
            "Minutes",
            "Photo",
            "Actions",
            # Added 2026-10-04 by lane WORDS, judged one by one under the PO's
            # test of that day (decision log, *"A WORD SPELLED THE SAME AS
            # ENGLISH STAYS ONLY IF IT IS WHAT A NATIVE SPEAKER ACTUALLY
            # SAYS"*; CR-168-BRC10 §19.2). NATIVE-REVIEW-OWED (B14 rule 35).
            # "Active"/"Inactive" are the FEMININE of actif/inactif, agreeing
            # with *une équipe* (a crew) - the catalogue agrees by gender
            # already (a key is "Active", a person "Actif").
            "Active",
            "Inactive",
            # *une certification* is the French word, and this catalogue's own
            # for it ("Suivi des certifications", "Ajouter une certification").
            "Certification",
            "Certifications",
            # *la performance* is French; the Work module already titles its
            # Performance page and tab with it, so one word, not two.
            "Performance",
            # "min" is this language's own abbreviation for minutes, the one
            # the catalogue already prints on the bill-run tile.
            "{{value}} min",
            # Added 2026-10-04 by lane I18N (CR-168-BRC10 round 6, §25), judged one
            # by one under the PO's native-speaker test (decision log *"A WORD
            # SPELLED THE SAME AS ENGLISH STAYS ONLY IF IT IS WHAT A NATIVE SPEAKER
            # ACTUALLY SAYS"*). NATIVE-REVIEW-OWED (B14 rule 35).
            "{{minutes}} min",
            "{{count}} min",
            # French abbreviates minimum and maximum exactly so; *un module*;
            # *en route* is French and what a French dispatcher says of a
            # technician on the way; *une version*, *des versions*.
            "Min",
            "Max",
            "Module",
            "En route",
            "Versions",
            "{{count}} version",
            "{{count}} versions",
            # Added 2026-10-04 by lane I18N (CR-168-BRC10 §25.5, DEF-GOV-9597),
            # judged one by one under the PO's native-speaker test.
            # NATIVE-REVIEW-OWED (B14 rule 35).
            # Ordinary French words, spelled the English way.
            "Services",
            "Standard",
            "Minimum",
            "Latitude",
            "Longitude",
            "Export",
            "Budget",
            "Format",
            "Occupant",
            "Occupants",
            "Option",
            "Options",
            "Dates",
            "Pages",
            "Message",
            "Messages",
            "Contact",
            "Communication",
            "Composition",
            "Correction",
            "+ Correction",
            "Net",
            "Mode",
            "Protection",
            "Point",
            "Points",
            "Question",
            "+ Service",
            "Confirmation",
            "Confirmations",
            "Session",
            "Sessions",
            "Notes",
            "NOTE",
            "Imports",
            "1 cycle",
            "{{count}} cycles",
            "Cycle · {{frequency}}",
            "{{count}} document",
            "{{count}} documents",
            "DOCUMENTS",
            "{{count}} minute",
            "{{count}} minutes",
            "{{name}}, version {{version}}",
            "{{month}} {{year}}",
            # Added 2026-09-10 with CR-087's tax Audit tab. "Audit" is the
            # ordinary French noun (*un audit*) and the same class as "Audit"
            # in the German set above. It is not a new word this lane chose:
            # `rating.rateDetail.tab.versions` and `rating.planDetail.panel.
            # versions` already ship it in fr-FR, so the alternative was to
            # give ONE of four sibling Audit tabs a different French title.
            # NATIVE-REVIEW-OWED (B14 rule 35) — a French reader may overturn
            # this, and then all four labels move together.
            "Audit",
            # Added 2026-08-24 with the CR-030 W4 catalogue. Each is the
            # ordinary French noun, identically spelled — "Note" (a written
            # remark), "Document"/"Documents", "Type" (a kind), and
            # "Conditions" (terms to be met). None is an untranslated paste-in.
            "Note",
            "Document",
            "Type",
            "Conditions",
            "Code",
            "Commercial",
            "Corrections",
            "Cycle",
            "Cycle {{code}}",
            # Added 2026-08-26 with the CR-038 W5 catalogue (the S29 tag row) —
            # the same French noun as "Cycle {{code}}" one line up, with the
            # cycle CODE under the tag's own param name. PO batch, as above.
            "Cycle {{cycle}}",
            "Cycles",
            "Date",
            "Documents",
            "Formats",
            "Mobile",
            "Notifications",
            "Service",
            "Source",
            "Structure",
            "Taxable",
            "Total",
            "Version",
            "Version {{version}}",
            # French writes the duration the same way.
            "30 minutes",
            # Abbreviations: "est." (estimé) and the version prefix "v".
            "est.",
            "v{{version}}",
        }
    ),
    "id-ID": frozenset(
        {
            # Added 2026-10-21 (CR-187-BRC10 integration lane: the gettingIn, theDay and reads waves'
            # field.* keys fanned in): the value as this language writes it.
            "Normal",
            "{{address}} · {{count}} meter",
            "{{n}}%",
            # Added 2026-10-21 (CR-187-BRC10, the field app's words fanned in under field.*): the word as
            # this language writes it.
            "Menu",
            "Barcode",
            "Dispatch",
            "Sub-meter",
            "{{count}} sub-meter",
            "meter {{serial}}",
            # Indonesian spells these the English way (many are direct loans).
            "Audit",
            # Added 2026-10-04 with CR-168 round 2 (lane ORDER-PAGE): *area*
            # (wilayah kerja) and *meter* (the instrument) are the Indonesian
            # words, spelled the English way. NATIVE-REVIEW-OWED (B14 rule 35).
            "Area",
            "Meter",
            # Added 2026-10-04 by lane I18N (CR-168-BRC10 round 6, §25), judged one
            # by one under the PO's native-speaker test (decision log *"A WORD
            # SPELLED THE SAME AS ENGLISH STAYS ONLY IF IT IS WHAT A NATIVE SPEAKER
            # ACTUALLY SAYS"*). NATIVE-REVIEW-OWED (B14 rule 35).
            # "KB"/"MB" are the unit symbols this language writes for a file
            # size (French alone writes Ko/Mo, and its catalogue does).
            "{{count}} KB",
            "{{size}} MB",
            # "Min" is the Indonesian abbreviation of *minimum* (the catalogue
            # writes its partner as *Maks*).
            "Min",
            # Added 2026-10-04 by lane I18N (CR-168-BRC10 §25.5, DEF-GOV-9597),
            # judged one by one under the PO's native-speaker test.
            # NATIVE-REVIEW-OWED (B14 rule 35).
            # Indonesian words spelled the English way (total, manual, portal,
            # digital, minimum, register, deposit, format, debit, bank, label,
            # item, model, memo, lift, target, platform), *per*, *No.*; *batch* and
            # *hash* as Indonesian staff say them; *Lockbox* is the bank service's
            # own name.
            "Total",
            "Manual",
            "Hash",
            "Portal",
            "Digital",
            "Sub",
            "{{name}} (portal)",
            "Minimum",
            "Register",
            "Deposit",
            "Format",
            "Debit",
            "Bank",
            "Per {{unit}}",
            "Label",
            "Batch",
            "Item",
            "Model",
            "{{count, number}} unit",
            "Meter {{label}}",
            "Lockbox",
            "Memo",
            "Lift",
            "1 meter",
            "No.",
            "Federal",
            "Target",
            "Platform",
            "{{what}}: ${{amount}}",
            "{{percent}}%",
            "{{pct}}%",
            # Added 2026-10-05 by lane MVI-I18N (CR-171-BRC10 P2.37): an owner's
            # share on the move-in Review, written with no space as above.
            "{{value}}%",
            "{{month}} {{year}}",
            # Added 2026-08-24: Indonesian writes "Email" exactly this way —
            # the same direct-loan class as "Audit" and "Firmware" beside it.
            "Email",
            "Firmware",
            "Gas",
            "Status",
            "Subtotal",
            # Indonesian month names: April, September and November are
            # identical (Januari, Februari, Maret, Mei … deliberately absent).
            "April",
            "September",
            "November",
            # "per" is the Indonesian preposition too, so a rate line reads the
            # same once the two interpolations are removed.
            "{{amount}} per {{unit}}",
            "{{rate}} per {{unit}}",
            # Added 2026-08-26 with the CR-038 W5 catalogue: "Unit" is the
            # Indonesian word too (the S29 linkage line reads "Unit A" in both
            # languages). PO batch, as above.
            "Unit {{unit}}",
            # Added 2026-08-31 with CR-054 task 24's chase-list column. This
            # rests on NO new claim: the confirmation this list asks for is the
            # one three lines up, in this same locale, about this same word —
            # *"Unit is the Indonesian word too"*. The interpolated form was
            # allowed and the bare noun was not, so the chase list's `Unit`
            # header left this gate RED on the branch tip from 8d661ec1
            # (DEF-2595, filed by a sibling lane two hours earlier). PO batch, as above.
            "Unit",
            # Trade terms and abbreviations kept in English by the trade.
            "(sub)",
            "Alt UoM",
            "Sub-meter #",
            "v{{version}}",
            # The meter-type sample is a list of trade terms; MT returns it
            # unchanged in Indonesian, as it does the German "Drive-by" above.
            "AMI, AMR, walk-by, sub-meter, master",
        }
    ),
    "it-IT": frozenset(
        {
            # Added 2026-10-21 (CR-187-BRC10 integration lane: the gettingIn, theDay and reads waves'
            # field.* keys fanned in): the value as this language writes it.
            "{{m}} min",
            "{{n}}%",
            # Added 2026-10-21 (CR-187-BRC10, the field app's words fanned in under field.*): the word as
            # this language writes it.
            "Menu",
            # Italian spells these the English way.
            # "Audit" added 2026-09-10 with CR-087's tax Audit tab: the
            # ordinary Italian business noun, already shipped by
            # `rating.planDetail.tab.audit` and `rating.rateDetail.tab.
            # versions`. NATIVE-REVIEW-OWED (B14 rule 35), and all four
            # sibling labels move together if a native reader overturns it.
            "Audit",
            "Firmware",
            "Gas",
            "No",
            "OK",
            # Added 2026-10-04 by lane WORDS, judged one by one under the PO's
            # test of that day (decision log, *"A WORD SPELLED THE SAME AS
            # ENGLISH STAYS ONLY IF IT IS WHAT A NATIVE SPEAKER ACTUALLY
            # SAYS"*; CR-168-BRC10 §19.2). NATIVE-REVIEW-OWED (B14 rule 35).
            # "min" is this language's own abbreviation for minutes, the one
            # the catalogue already prints on the bill-run tile.
            "{{value}} min",
            # Added 2026-10-04 by lane I18N (CR-168-BRC10 round 6, §25), judged one
            # by one under the PO's native-speaker test (decision log *"A WORD
            # SPELLED THE SAME AS ENGLISH STAYS ONLY IF IT IS WHAT A NATIVE SPEAKER
            # ACTUALLY SAYS"*). NATIVE-REVIEW-OWED (B14 rule 35).
            # "KB"/"MB" are the unit symbols this language writes for a file
            # size (French alone writes Ko/Mo, and its catalogue does).
            "{{count}} KB",
            "{{size}} MB",
            "{{count}} min",
            "{{minutes}} min",
            # Italian abbreviates minimo/massimo as Min/Max, and says *il link*.
            "Min",
            "Max",
            "Link",
            # Added 2026-10-04 by lane I18N (CR-168-BRC10 §25.5, DEF-GOV-9597),
            # judged one by one under the PO's native-speaker test.
            # NATIVE-REVIEW-OWED (B14 rule 35).
            # What an Italian office says: *il file*, *il report*, *la password*,
            # *la home*, *il budget*, *standard*, *zero*, *per*, *hash*.
            "File",
            "Standard",
            "Hash",
            "Report",
            "Budget",
            "Per {{unit}}",
            "Zero",
            "Password",
            "Home",
            "{{percent}}%",
            # Added 2026-10-05 by lane MVI-I18N (CR-171-BRC10 P2.37): Italian
            # writes a share with no space too (an owner's share on the move-in
            # Customer and Review steps).
            "{{pct}}%",
            "{{value}}%",
            "{{month}} {{year}}",
            # "per" is the Italian preposition too.
            "{{amount}} per {{unit}}",
            "{{rate}} per {{unit}}",
            # Added 2026-08-26 with the CR-038 W5 catalogue: "Unit" is the
            # Indonesian word too (the S29 linkage line reads "Unit A" in both
            # languages). PO batch, as above.
            "Unit {{unit}}",
            # Abbreviations: "Mult." (moltiplicatore), "est." (estimato), "v".
            "Mult.",
            "est.",
            "v{{version}}",
            # Meter-type sample — trade terms, unchanged by MT (see id-ID).
            "AMI, AMR, walk-by, sub-meter, master",
        }
    ),
    # Japanese and Korean translate everything except the Latin version prefix.
    # KB/MB added 2026-10-04 by lane I18N (CR-168-BRC10 §25): both languages
    # write a file size with the Latin unit symbol. NATIVE-REVIEW-OWED.
    # "{{value}}%" added 2026-10-05 by lane MVI-I18N (CR-171-BRC10 P2.37): an
    # owner's share on the move-in Review, the same no-space percent.
    "ja-JP": frozenset({"{{n}}%", "v{{version}}", "{{count}} KB", "{{size}} MB", "{{percent}}%", "{{pct}}%", "{{value}}%"}),
    "ko-KR": frozenset({"{{n}}%", "v{{version}}", "{{count}} KB", "{{size}} MB", "{{percent}}%", "{{pct}}%", "{{value}}%"}),
    # Hindi, added 2026-10-04 by lane I18N (CR-168-BRC10 §25): a Hindi screen
    # writes a file size and a version with the Latin symbols. NATIVE-REVIEW-OWED.
    # The percent sign with no space, the date as month-year and the dollar
    # amount after a colon are how a Hindi screen writes them too (lane I18N).
    "hi": frozenset(
        {"{{n}}%", "v{{version}}", "{{count}} KB", "{{size}} MB", "{{percent}}%", "{{pct}}%",
         "{{month}} {{year}}", "{{what}}: ${{amount}}", "{{value}}%"}
    ),
    "pt-BR": frozenset(
        {
            # Added 2026-10-21 (CR-187-BRC10 integration lane: the gettingIn, theDay and reads waves'
            # field.* keys fanned in): the value as this language writes it.
            "{{m}} min",
            "{{n}}%",
            # Added 2026-10-21 (CR-187-BRC10, the field app's words fanned in under field.*): the word as
            # this language writes it.
            "Normal",
            "Material",
            "Menu",
            # Ordinary Portuguese words spelled the English way.
            # "Cheque" added 2026-08-24 (CR-030 W4 payment methods) — the
            # ordinary Portuguese noun, as in Spanish.
            "Cheque",
            "Federal",
            "Firmware",
            "OK",
            # Added 2026-10-04 by lane WORDS, judged one by one under the PO's
            # test of that day (decision log, *"A WORD SPELLED THE SAME AS
            # ENGLISH STAYS ONLY IF IT IS WHAT A NATIVE SPEAKER ACTUALLY
            # SAYS"*; CR-168-BRC10 §19.2). NATIVE-REVIEW-OWED (B14 rule 35).
            # "min" is this language's own abbreviation for minutes, the one
            # the catalogue already prints on the bill-run tile.
            "{{value}} min",
            # Added 2026-10-04 by lane I18N (CR-168-BRC10 round 6, §25), judged one
            # by one under the PO's native-speaker test (decision log *"A WORD
            # SPELLED THE SAME AS ENGLISH STAYS ONLY IF IT IS WHAT A NATIVE SPEAKER
            # ACTUALLY SAYS"*). NATIVE-REVIEW-OWED (B14 rule 35).
            # "KB"/"MB" are the unit symbols this language writes for a file
            # size (French alone writes Ko/Mo, and its catalogue does).
            "{{count}} KB",
            "{{size}} MB",
            "{{count}} min",
            "{{minutes}} min",
            # *o link* and *o checklist* are what a Brazilian says; the order
            # page already writes "não tem checklist" in its own sentence.
            "Link",
            "Checklist",
            # Added 2026-10-04 by lane I18N (CR-168-BRC10 §25.5, DEF-GOV-9597),
            # judged one by one under the PO's native-speaker test.
            # NATIVE-REVIEW-OWED (B14 rule 35).
            # Portuguese words spelled the English way.
            "Manual",
            "Hash",
            "Portal",
            "Digital",
            "Sub",
            "{{name}} (portal)",
            "Latitude",
            "Longitude",
            "{{size}} × {{count}} · base {{base}}",
            "APIs",
            "{{count}} APIs",
            "Item",
            "Zero",
            "Classes",
            "{{count}} classes",
            "Industrial",
            "{{percent}}%",
            # Added 2026-10-05 by lane MVI-I18N (CR-171-BRC10 P2.37): an owner's
            # share on the move-in, the same no-space percent as above.
            "{{pct}}%",
            "{{value}}%",
            "Solar",
            "Subtotal",
            "Total",
            # Abbreviations and the meter qualifier.
            "(sub)",
            "Mult.",
            "est.",
            "v{{version}}",
        }
    ),
}

# ── The product name, exempt by KEY and not by text (2026-10-02).
#
# "SMART360 Next" since 2026-10-02 (CR-088, PO: "We want to make it SMART360
# SMB = SMART360 Next"); a product name is not translated. It is DRAWN in two
# halves ("SMART360" large, "Next" smaller in the accent — `app.nameFamily`,
# `app.nameEdition`, `components/ProductName.tsx`), and the browser tab carries
# it after the page name (`shell.docTitle`). Before CR-088 the allowance was the
# value "SMARTBillHub" in `UNIVERSAL`; the history of that entry
# (38abf0acf, 54c545834) shows these four keys are what it existed for.
#
# ⚠ WHY A KEY MAP AND NOT THE VALUE LIST ABOVE: "Next" is also an ordinary
# English word — `finance.entryDetail.next`, `work.rules.builder.next`, a pager
# button — and a value-keyed exemption for it exempts every one of those. So a
# key is exempt here only when it is one of these four AND still holds exactly
# the name; the same text under any other key is a paste-in and is counted.
# Proven RED through run_gates on 2026-10-02 (law 7): `de.json`'s
# `finance.entryDetail.next` planted as "Next" took G15 from 802 fresh values
# to 803, and `measure()["fresh"]` held `de :: finance.entryDetail.next`;
# the value-keyed version counted 802 over the same
# plant. Unplanted, the count is 802 before and after this change.
PRODUCT_NAME_KEYS: dict[str, str] = {
    "app.name": "SMART360 Next",
    "app.nameFamily": "SMART360",
    "app.nameEdition": "Next",
    "shell.docTitle": "{{leaf}} · SMART360 Next",
}

#: Card networks, as printed on the card (New request step 3, `DEF-CUS-10041`,
#: 2026-10-11). A trademark is the same in every catalogue. KEY-SCOPED, never by
#: text, for `PRODUCT_NAME_KEYS`' reason: "Discover" is also an English verb, and
#: a value-matched entry would exempt every button that reads "Discover".
CARD_BRAND_KEYS: dict[str, str] = {
    "customers.serviceRequest.pay.brand.amex": "American Express",
    "customers.serviceRequest.pay.brand.discover": "Discover",
    "customers.serviceRequest.pay.brand.mastercard": "Mastercard",
    "customers.serviceRequest.pay.brand.visa": "Visa",
}

MAX_NAMED = 3  # keys named in a one-line detail before it says "+N more"

#: ⚠ **THE UNTRANSLATED-VALUE BACKLOG, RE-BASELINED AT TODAY'S REALITY ON
#: 2026-08-31 — PO ruling 2026-08-30: "this family BORN ASPIRATIONAL it cannot
#: be ASPIRATIONAL any more - there are so many bugs becuase of this."**
#:
#: This gate asks TWO questions and used to fail them as one number, which is
#: the second thing that ruling is about. Measured 2026-08-31 across the ten
#: translated catalogues:
#:
#:   KEY SETS       0 missing, 0 extra.  **This is the defect G15 was written
#:                  for** — the S1 landing page printing `public.plan.starter.f1`
#:                  at a prospect — and it is CLEAN. It stays a HARD ZERO with
#:                  no baseline and no allowance. Nothing below relaxes it.
#:   UNTRANSLATED   5,856 values byte-identical to English. A German reader sees
#:                  correct English, not a raw key. It is a translation PROJECT
#:                  (DEF-2603), not a defect one lane can close, and it is what
#:                  kept this gate red every day it has existed.
#:
#: A gate that can never pass stops being read, and a gate nobody reads stops
#: being right — which is exactly how this one came to report "10 parity
#: failure(s)" for a 5,856-value backlog and no key gaps at all (DEF-2604).
#: So the 5,856 are named here, one per line, and the file MAY ONLY SHRINK.
#:
#: ⚠ **KEYED ON `<locale> :: <key>` AND NOT ON THE VALUE, WHICH IS A DIFFERENT
#: CHOICE FROM G33's AND DELIBERATE.** The growth vector for this backlog is a
#: lane adding a NEW key to en.json and pasting the English into the other ten —
#: ten new lines, all of them fresh, all of them failing. That is what must be
#: stopped. Editing the English of a key that is ALREADY untranslated changes
#: nothing about the debt, and keying on the value would turn every unrelated
#: copy fix into ten translations owed before the commit can land. G33 keys on
#: the text because its ruling binds "every new or CHANGED refusal"; this one
#: binds new PASTE-INS.
UNTRANSLATED_BASELINE = Path(__file__).resolve().parent / "g15_untranslated_baseline.txt"


def _catalogues() -> list[Path]:
    """Every non-English catalogue beside en.json, in a stable order.

    Globbed rather than listed, so a sixth language is covered the day its file
    lands — a catalogue this gate does not know about is the failure mode it
    exists to prevent.
    """
    return sorted(p for p in LOCALES.glob("*.json") if p.name != BASE)


def _named(keys: list[str]) -> str:
    shown = ", ".join(keys[:MAX_NAMED])
    extra = len(keys) - MAX_NAMED
    return shown + (f" (+{extra} more)" if extra > 0 else "")


def _untranslated_baseline() -> set[str]:
    if not UNTRANSLATED_BASELINE.is_file():
        return set()
    return {
        line.strip()
        for line in UNTRANSLATED_BASELINE.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    }


def measure() -> dict:
    """What this gate actually measured, as numbers, before anything is worded.

    ⚠ **THE SUMMARY IS BUILT FROM THIS AND NOT THE OTHER WAY ROUND (DEF-2604).**
    `run()` used to count its own FAILURE LINES — one per catalogue per class —
    and report the total as "10 parity failure(s)". Ten reads as ten items; the
    truth on that day was **0 missing keys, 0 extra keys and 5,856 untranslated
    values**, a translation backlog and a raw-key defect added together into a
    number that was neither. The 2026-08-27 decision-log entry names this gate
    for exactly that: *"another counted a ~5,600-value translation backlog and
    about ten real gaps as one number."* Every count in the detail line now
    comes from this dict.
    """
    english = json.loads((LOCALES / BASE).read_text(encoding="utf-8"))
    known = _untranslated_baseline()
    catalogues = _catalogues()
    missing: list[str] = []
    extra: list[str] = []
    untranslated: list[str] = []
    fresh: list[str] = []
    seen: set[str] = set()
    checked_values = 0

    for path in catalogues:
        locale = path.stem
        catalogue = json.loads(path.read_text(encoding="utf-8"))
        missing += [f"{path.name}::{k}" for k in sorted(set(english) - set(catalogue))]
        extra += [f"{path.name}::{k}" for k in sorted(set(catalogue) - set(english))]
        exempt = UNIVERSAL | LOANWORDS.get(locale, frozenset())
        for key in sorted(catalogue):
            if english.get(key) != catalogue[key] or catalogue[key] in exempt:
                continue
            if PRODUCT_NAME_KEYS.get(key) == catalogue[key]:
                continue
            if CARD_BRAND_KEYS.get(key) == catalogue[key]:
                continue
            line = f"{locale} :: {key}"
            seen.add(line)
            untranslated.append(line)
            if line not in known:
                fresh.append(line)
        checked_values += len(catalogue)

    return {
        "english_keys": len(english),
        "catalogues": len(catalogues),
        "values": checked_values,
        "missing": missing,
        "extra": extra,
        "untranslated": untranslated,
        "fresh": fresh,
        "baselined": len(known),
        "stale": sorted(known - seen),
    }


def run():
    base_path = LOCALES / BASE
    if not base_path.is_file():
        return (
            "SKIP",
            f"nothing to compare against — {BASE} not present in {LOCALES.name}/",
        )
    if not _catalogues():
        return "SKIP", f"only {BASE} exists — no translated catalogue to check yet"

    m = measure()
    failures = []
    # -- Class 1 . KEY SETS. Hard zero, no baseline, no allowance. This is the
    # defect this gate was written for: a key en.json has and a catalogue does
    # not renders the raw key to a prospect (US-TEN-018, the S1 pricing card).
    if m["missing"]:
        failures.append(
            f"{len(m['missing'])} key(s) en.json has that a catalogue does not "
            f"(renders raw or silently reverts to English): {_named(m['missing'])}"
        )
    if m["extra"]:
        failures.append(
            f"{len(m['extra'])} key(s) a catalogue has that en.json does not "
            f"(dead weight that hides the next real drift): {_named(m['extra'])}"
        )
    # -- Class 2 . UNTRANSLATED VALUES. Ratcheted against a baseline file, and
    # the count is in the detail on EVERY run, pass or fail. It is never hidden.
    if m["fresh"]:
        failures.append(
            f"{len(m['fresh'])} NEW value(s) pasted in English rather than "
            f"translated (baseline holds {m['baselined']}, "
            f"{UNTRANSLATED_BASELINE.name}): {_named(m['fresh'])}"
        )

    tail = (
        f"{m['catalogues']} catalogue(s) vs {m['english_keys']} {BASE} key(s); "
        f"{len(m['missing'])} missing, {len(m['extra'])} extra, "
        f"{len(m['untranslated'])} still identical to English "
        f"({m['baselined']} baselined, DEF-2603)"
    )
    if failures:
        return "FAIL", "; ".join(failures) + f" — {tail}"
    if m["stale"]:
        return "PASS", (
            f"{tail}; {len(m['stale'])} baselined value(s) are now translated — "
            f"delete them from {UNTRANSLATED_BASELINE.name} to hold the gain"
        )
    return "PASS", tail


if __name__ == "__main__":
    status, detail = run()
    print(f"{status}: {detail}")
    raise SystemExit(0 if status != "FAIL" else 1)
