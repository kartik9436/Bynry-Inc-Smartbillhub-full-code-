"""CR-029 RC-W3 · the Routes & Cycles screen strings, in all eleven catalogues.

WHY A SCRIPT AND NOT ELEVEN HAND EDITS. G15 makes two assertions and both are
exact: every catalogue carries EXACTLY en.json's key set, and a value
byte-identical to English in a non-English catalogue FAILS — i18next resolves
the key, finds it, and the page reverts to English mid-card without ever firing
the missing-key fallback. DEF-215 records what happens when a CR ignores that:
CR-006 shipped 201 English strings into all ten non-English catalogues and took
G15's untranslated count from 109 to 304. This lane translates instead.

⚠ THE PLURALS ARE TWO ORDINARY KEYS, NOT i18next PLURAL SUFFIXES, AND THAT IS A
DELIBERATE CHOICE AGAINST THE FRAMEWORK'S OWN FEATURE. i18next resolves
`key_one` / `key_other` / `key_many` per LANGUAGE, so the key set differs
between catalogues by construction — and G15 requires the key sets to be
identical. The eleven languages this product ships (de · en · es · es-MX ·
fr-FR · hi · id-ID · it-IT · ja-JP · ko-KR · pt-BR) are all one/other or
other-only; none is Slavic, none needs a `few` or a `many`. So `<base>.one` and
`<base>.other` are chosen in code by `pluralKey()`, which is correct for all
eleven and keeps the catalogues parallel. Recorded here because the next lane
will otherwise "fix" it back to `_one`/`_other` and turn G15 red.

Run: python3 07-frontend/scripts/cr029_i18n.py
"""

import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1] / "src" / "i18n" / "locales"

EN: dict[str, str] = {
    # ── the sub-tabs (B17 §4 — "Routes | Cycles sub-tabs") ────────────────
    "settings.routesCycles.subTabsLabel": "Routes and cycles",
    "settings.routesCycles.subTab.routes": "Routes",
    "settings.routesCycles.subTab.cycles": "Cycles",
    # ── SET-05 columns ────────────────────────────────────────────────────
    "settings.routes.col.routeNo": "Route #",
    "settings.routes.col.services": "Service(s)",
    "settings.routes.col.area": "Area",
    # ── SET-05.cycles columns ─────────────────────────────────────────────
    "settings.cycles.col.cycleNo": "Cycle #",
    "settings.cycles.col.startDay": "Start day",
    "settings.cycles.col.daysToComplete": "Days to complete",
    # BR-MET-080 · D13 — the landing coverage sentence names what the accounts
    # LACK. There is no account-level cycle assignment in this product.
    "settings.cycles.coverage.gap": (
        "{{count}} accounts sit on no cycle — they are never read and never billed "
        "until one is assigned."
    ),
    "settings.cycles.coverage.allCovered": "Every account sits on a cycle.",
    # ── the eight one-word business names (B17 §2) ────────────────────────
    "settings.cycles.frequency.daily": "Daily",
    "settings.cycles.frequency.weekly": "Weekly",
    "settings.cycles.frequency.fortnightly": "Fortnightly",
    "settings.cycles.frequency.monthly": "Monthly",
    "settings.cycles.frequency.bimonthly": "Bimonthly",
    "settings.cycles.frequency.quarterly": "Quarterly",
    "settings.cycles.frequency.semiannual": "Semiannual",
    "settings.cycles.frequency.annual": "Annual",
    # ── the window, which is DERIVED and never stored ─────────────────────
    "settings.cycles.window.derived": "Derived, not stored",
    "settings.cycles.window.stored": "Kept from an earlier run",
    "settings.cycles.window.none": "No window yet — set a start day and a length",
    # ── SET-06D · the route detail ────────────────────────────────────────
    "settings.routes.detail.tab.premises": "Premises",
    "settings.routes.detail.tab.units": "Units",
    "settings.routes.detail.tab.assets": "Assets",
    "settings.routes.detail.tab.accounts": "Accounts",
    "settings.routes.detail.tab.audit": "Audit",
    "settings.routes.detail.tabsLabel": "Route sections",
    "settings.routes.detail.factsTitle": "Facts",
    "settings.routes.detail.edit": "Edit",
    "settings.routes.detail.fact.routeNo": "Route #",
    "settings.routes.detail.fact.readType": "Read type",
    "settings.routes.detail.fact.services": "Service(s)",
    "settings.routes.detail.fact.area": "Area",
    "settings.routes.detail.fact.members": "Premises · units",
    "settings.routes.detail.fact.meters": "Meters on route",
    "settings.routes.detail.fact.cycle": "Cycle",
    "settings.routes.detail.metersOnRoute": "{{meters}} ({{excluded}} left off)",
    "settings.routes.detail.membersHint": (
        "Members derive from area tags — changes apply at the next read window."
    ),
    "settings.routes.detail.walkOrderLede": (
        "The order the stops are visited in. One building is one stop, however many "
        "units are inside it. Drag a stop, or use the arrows."
    ),
    "settings.routes.detail.saveOrder": "Save order ✓",
    "settings.routes.detail.resetOrder": "Undo changes",
    "settings.routes.detail.orderSaved": "Walking order saved.",
    "settings.routes.detail.orderRouteAbsent": (
        "The walking order can't be saved yet — nothing stores it on the server."
    ),
    "settings.routes.detail.printSheet": "Print route sheet",
    "settings.routes.detail.unitsOnStop.one": "{{count}} unit",
    "settings.routes.detail.unitsOnStop.other": "{{count}} units",
    "settings.routes.detail.noMeterVerify": "No meter · verify",
    "settings.routes.detail.moveUp": "Move {{stop}} earlier",
    "settings.routes.detail.moveDown": "Move {{stop}} later",
    "settings.routes.detail.noMembersTitle": "Nothing is on this route yet",
    "settings.routes.detail.noMembersBody": "Edit the route and pick the premises it covers.",
    "settings.routes.detail.sheet.stop": "Stop",
    "settings.routes.detail.sheet.premises": "Premises",
    "settings.routes.detail.sheet.units": "Units",
    "settings.routes.detail.sheet.meters": "Meters",
    "settings.routes.detail.col.unit": "Unit",
    "settings.routes.detail.col.onRoute": "On route",
    "settings.routes.detail.included": "Included",
    "settings.routes.detail.excluded": "Left off",
    "settings.routes.detail.exclusionReasonAbsentTitle": "Why a meter was left off is not shown yet",
    "settings.routes.detail.exclusionReasonAbsentBody": (
        "A short reason is kept with every meter left off this route, and nothing "
        "sends it to this screen yet."
    ),
    "settings.routes.detail.accountsAbsentTitle": "The accounts on this route are not listed yet",
    "settings.routes.detail.accountsAbsentBody": (
        "This tab says who is on the route and nothing about what they are charged — "
        "a route is a grouping. Listing them needs a request that returns a route's "
        "accounts, and there isn't one yet."
    ),
    "settings.routes.detail.readHistoryAbsentTitle": "Read history is not available yet",
    "settings.routes.detail.readHistoryAbsentBody": (
        "Every read window is kept as a record that can be closed — the window, how "
        "many were collected, how many were expected and the result. Nothing sends "
        "them to this screen yet."
    ),
    # ── SET-07D · the cycle detail ────────────────────────────────────────
    "settings.cycles.detail.tab.schedule": "Schedule",
    "settings.cycles.detail.tab.routes": "Routes",
    "settings.cycles.detail.tab.coverage": "Coverage",
    "settings.cycles.detail.tab.runs": "Runs",
    "settings.cycles.detail.tab.audit": "Audit",
    "settings.cycles.detail.tabsLabel": "Cycle sections",
    "settings.cycles.detail.factsTitle": "Facts",
    "settings.cycles.detail.edit": "Edit",
    "settings.cycles.detail.fact.cycleNo": "Cycle #",
    "settings.cycles.detail.starts": "Starts",
    "settings.cycles.detail.daysToComplete": "Days to complete",
    "settings.cycles.detail.window": "Window",
    "settings.cycles.detail.firstRun": "First run",
    "settings.cycles.detail.fromNextTag": "FROM NEXT",
    "settings.cycles.detail.fromNext": (
        "Changing the schedule applies from the next window — nothing already issued changes."
    ),
    # ⚠ D9 — this REPLACES the prototype's "Bill and due dates belong to the
    # run, not the cycle", which the PO reversed the day it was drawn.
    "settings.cycles.detail.defaultsFootnote": (
        "Charges and taxes live on the plan, never here. The bill day and due day are "
        "this cycle's defaults — a run starts from them and can change them for that "
        "run without changing what is saved here."
    ),
    # ⚠ THIS PAIR SHIPPED AND WAS CORRECTED HOURS LATER — the corrected text is
    # in `EN_FIX` / `FIX` below, which is the table that OVERWRITES. Left here
    # as it shipped so a fresh run of this script is idempotent and the two
    # tables never disagree about which one owns the key.
    "settings.cycles.detail.windowsAbsentTitle": "The next windows are not worked out yet",
    "settings.cycles.detail.windowsAbsentBody": (
        "Turning a start day, a frequency and a length into dated windows is being "
        "built. Nothing is shown here rather than a date nobody has confirmed."
    ),
    "settings.cycles.detail.monthEndUnruledTitle": (
        "Day {{day}} does not exist in every month"
    ),
    "settings.cycles.detail.monthEndUnruledBody": (
        "February is shorter. Whether this cycle then reads on the last day of the "
        "month, skips that month, or moves into the next one has not been decided — "
        "so no date is shown until it is."
    ),
    "settings.cycles.detail.moveFootnote": (
        "Moving one here removes it from its old cycle at the next window."
    ),
    "settings.cycles.detail.noRoutesTitle": "No routes on this cycle",
    "settings.cycles.detail.noRoutesBody": "Edit the cycle and pick the routes it bills.",
    "settings.cycles.detail.kpi.accounts": "Accounts on this cycle",
    "settings.cycles.detail.kpi.routes": "Routes on this cycle",
    "settings.cycles.detail.kpi.uncovered": "Accounts on no cycle",
    # ⚠ D13 — the remedy is a ROUTE. No account is assigned to a cycle here or
    # anywhere: the cycle is worked out from the account's unit at run time.
    "settings.cycles.detail.uncoveredLack": (
        "An account reaches a cycle through its unit's route, and that is worked out "
        "when the bill run happens. The accounts counted here are on no route — put "
        "them on one and they are covered."
    ),
    "settings.cycles.detail.uncoveredListAbsentTitle": "Those accounts are not listed yet",
    "settings.cycles.detail.uncoveredListAbsentBody": (
        "The coverage request answers with a count and no rows."
    ),
    "settings.cycles.detail.runsAbsentTitle": "Past runs are not listed yet",
    "settings.cycles.detail.runsAbsentBody": (
        "Bill runs are started in Billing, and nothing lists the runs a cycle has had."
    ),
    "settings.cycles.detail.openInBilling": "Open in Billing →",
    "settings.cycles.detail.notFoundTitle": "That cycle is not in this list",
    "settings.cycles.detail.notFoundBody": "It may have been deleted. Go back and pick one.",
    # ── W3-T5 · the wizards as addressable pages ──────────────────────────
    "settings.routes.wizard.loading": "Opening the route…",
    "settings.cycles.wizard.loading": "Opening the cycle…",
    # ── W3-T7 · DEF-224's plurals, as one/other pairs ─────────────────────
    "settings.routes.wizard.selectedCount.one": "{{count}} selected",
    "settings.routes.wizard.selectedCount.other": "{{count}} selected",
    "settings.cycles.wizard.routesSelected.one": "{{count}} route selected",
    "settings.cycles.wizard.routesSelected.other": "{{count}} routes selected",
    "settings.cycles.wizard.routesMembers.one": "{{routes}} route · {{members}} members",
    "settings.cycles.wizard.routesMembers.other": "{{routes}} routes · {{members}} members",
    # ── W3-T6 · the ops tabs adopt the schedule vocabulary ────────────────
    "metering.cycles.col.frequency": "Frequency",
    "metering.cycles.col.startDay": "Start day",
    "metering.cycles.col.daysToComplete": "Days to complete",
    "metering.routes.col.services": "Service(s)",
    "metering.ops.openDetail": "Open {{code}}",
}

T: dict[str, dict[str, str]] = {}

T["de"] = {
    "settings.routesCycles.subTabsLabel": "Routen und Zyklen",
    "settings.routesCycles.subTab.routes": "Routen",
    "settings.routesCycles.subTab.cycles": "Zyklen",
    "settings.routes.col.routeNo": "Routen-Nr.",
    "settings.routes.col.services": "Sparte(n)",
    "settings.routes.col.area": "Gebiet",
    "settings.cycles.col.cycleNo": "Zyklus-Nr.",
    "settings.cycles.col.startDay": "Starttag",
    "settings.cycles.col.daysToComplete": "Tage bis zum Abschluss",
    "settings.cycles.coverage.gap": (
        "{{count}} Konten gehören zu keinem Zyklus — sie werden weder abgelesen noch "
        "abgerechnet, bis einer zugeordnet ist."
    ),
    "settings.cycles.coverage.allCovered": "Jedes Konto gehört zu einem Zyklus.",
    "settings.cycles.frequency.daily": "Täglich",
    "settings.cycles.frequency.weekly": "Wöchentlich",
    "settings.cycles.frequency.fortnightly": "Zweiwöchentlich",
    "settings.cycles.frequency.monthly": "Monatlich",
    "settings.cycles.frequency.bimonthly": "Zweimonatlich",
    "settings.cycles.frequency.quarterly": "Vierteljährlich",
    "settings.cycles.frequency.semiannual": "Halbjährlich",
    "settings.cycles.frequency.annual": "Jährlich",
    "settings.cycles.window.derived": "Abgeleitet, nicht gespeichert",
    "settings.cycles.window.stored": "Aus einem früheren Lauf übernommen",
    "settings.cycles.window.none": "Noch kein Zeitfenster — Starttag und Dauer festlegen",
    "settings.routes.detail.tab.premises": "Objekte",
    "settings.routes.detail.tab.units": "Einheiten",
    "settings.routes.detail.tab.assets": "Anlagen",
    "settings.routes.detail.tab.accounts": "Konten",
    "settings.routes.detail.tab.audit": "Protokoll",
    "settings.routes.detail.tabsLabel": "Routenbereiche",
    "settings.routes.detail.factsTitle": "Eckdaten",
    "settings.routes.detail.edit": "Bearbeiten",
    "settings.routes.detail.fact.routeNo": "Routen-Nr.",
    "settings.routes.detail.fact.readType": "Ableseart",
    "settings.routes.detail.fact.services": "Sparte(n)",
    "settings.routes.detail.fact.area": "Gebiet",
    "settings.routes.detail.fact.members": "Objekte · Einheiten",
    "settings.routes.detail.fact.meters": "Zähler auf der Route",
    "settings.routes.detail.fact.cycle": "Zyklus",
    "settings.routes.detail.metersOnRoute": "{{meters}} ({{excluded}} ausgenommen)",
    "settings.routes.detail.membersHint": (
        "Die Mitglieder ergeben sich aus den Gebietsmarkierungen — Änderungen gelten ab "
        "dem nächsten Ablesefenster."
    ),
    "settings.routes.detail.walkOrderLede": (
        "Die Reihenfolge der Halte. Ein Gebäude ist ein Halt, egal wie viele Einheiten "
        "darin liegen. Ziehen Sie einen Halt oder nutzen Sie die Pfeile."
    ),
    "settings.routes.detail.saveOrder": "Reihenfolge speichern ✓",
    "settings.routes.detail.resetOrder": "Änderungen verwerfen",
    "settings.routes.detail.orderSaved": "Ablaufreihenfolge gespeichert.",
    "settings.routes.detail.orderRouteAbsent": (
        "Die Reihenfolge lässt sich noch nicht speichern — auf dem Server nimmt sie "
        "noch nichts entgegen."
    ),
    "settings.routes.detail.printSheet": "Routenblatt drucken",
    "settings.routes.detail.unitsOnStop.one": "{{count}} Einheit",
    "settings.routes.detail.unitsOnStop.other": "{{count}} Einheiten",
    "settings.routes.detail.noMeterVerify": "Kein Zähler · prüfen",
    "settings.routes.detail.moveUp": "{{stop}} nach vorn verschieben",
    "settings.routes.detail.moveDown": "{{stop}} nach hinten verschieben",
    "settings.routes.detail.noMembersTitle": "Auf dieser Route liegt noch nichts",
    "settings.routes.detail.noMembersBody": (
        "Bearbeiten Sie die Route und wählen Sie die Objekte aus, die sie abdeckt."
    ),
    "settings.routes.detail.sheet.stop": "Halt",
    "settings.routes.detail.sheet.premises": "Objekt",
    "settings.routes.detail.sheet.units": "Einheiten",
    "settings.routes.detail.sheet.meters": "Zähler",
    "settings.routes.detail.col.unit": "Einheit",
    "settings.routes.detail.col.onRoute": "Auf der Route",
    "settings.routes.detail.included": "Enthalten",
    "settings.routes.detail.excluded": "Ausgenommen",
    "settings.routes.detail.exclusionReasonAbsentTitle": (
        "Warum ein Zähler ausgenommen wurde, wird noch nicht angezeigt"
    ),
    "settings.routes.detail.exclusionReasonAbsentBody": (
        "Zu jedem ausgenommenen Zähler wird eine kurze Begründung gespeichert, und sie "
        "erreicht diese Ansicht noch nicht."
    ),
    "settings.routes.detail.accountsAbsentTitle": (
        "Die Konten auf dieser Route werden noch nicht aufgelistet"
    ),
    "settings.routes.detail.accountsAbsentBody": (
        "Dieser Bereich sagt, wer auf der Route liegt, und nichts darüber, was berechnet "
        "wird — eine Route ist nur eine Gruppierung. Für die Liste fehlt noch eine "
        "Abfrage, die die Konten einer Route zurückgibt."
    ),
    "settings.routes.detail.readHistoryAbsentTitle": "Der Ableseverlauf ist noch nicht verfügbar",
    "settings.routes.detail.readHistoryAbsentBody": (
        "Jedes Ablesefenster wird als abschließbarer Datensatz geführt — Fenster, wie "
        "viele erfasst, wie viele erwartet, und das Ergebnis. Diese Ansicht erhält sie "
        "noch nicht."
    ),
    "settings.cycles.detail.tab.schedule": "Zeitplan",
    "settings.cycles.detail.tab.routes": "Routen",
    "settings.cycles.detail.tab.coverage": "Abdeckung",
    "settings.cycles.detail.tab.runs": "Läufe",
    "settings.cycles.detail.tab.audit": "Protokoll",
    "settings.cycles.detail.tabsLabel": "Zyklusbereiche",
    "settings.cycles.detail.factsTitle": "Eckdaten",
    "settings.cycles.detail.edit": "Bearbeiten",
    "settings.cycles.detail.fact.cycleNo": "Zyklus-Nr.",
    "settings.cycles.detail.starts": "Beginnt",
    "settings.cycles.detail.daysToComplete": "Tage bis zum Abschluss",
    "settings.cycles.detail.window": "Zeitfenster",
    "settings.cycles.detail.firstRun": "Erster Lauf",
    "settings.cycles.detail.fromNextTag": "AB DEM NÄCHSTEN",
    "settings.cycles.detail.fromNext": (
        "Eine Änderung des Zeitplans gilt ab dem nächsten Fenster — bereits erstellte "
        "Rechnungen ändern sich nicht."
    ),
    "settings.cycles.detail.defaultsFootnote": (
        "Entgelte und Steuern gehören zum Tarif, niemals hierher. Rechnungstag und "
        "Fälligkeitstag sind die Vorgaben dieses Zyklus — ein Lauf übernimmt sie und "
        "kann sie für diesen Lauf ändern, ohne das Gespeicherte zu ändern."
    ),
    "settings.cycles.detail.windowsAbsentTitle": (
        "Die nächsten Fenster sind noch nicht berechnet"
    ),
    "settings.cycles.detail.windowsAbsentBody": (
            "Die Termine ergeben sich aus Starttag, Häufigkeit und Dauer — nur sendet sie noch nichts an diese Ansicht, und hier steht lieber nichts als ein Datum, das niemand bestätigt hat."
    ),
    "settings.cycles.detail.monthEndUnruledTitle": (
        "Den {{day}}. gibt es nicht in jedem Monat"
    ),
    "settings.cycles.detail.monthEndUnruledBody": (
        "Der Februar ist kürzer. Ob dieser Zyklus dann am letzten Tag des Monats abliest, "
        "den Monat auslässt oder in den nächsten rutscht, ist nicht entschieden — bis "
        "dahin wird kein Datum angezeigt."
    ),
    "settings.cycles.detail.moveFootnote": (
        "Wird eine hierher verschoben, verlässt sie ihren alten Zyklus zum nächsten Fenster."
    ),
    "settings.cycles.detail.noRoutesTitle": "Keine Routen in diesem Zyklus",
    "settings.cycles.detail.noRoutesBody": (
        "Bearbeiten Sie den Zyklus und wählen Sie die Routen, die er abrechnet."
    ),
    "settings.cycles.detail.kpi.accounts": "Konten in diesem Zyklus",
    "settings.cycles.detail.kpi.routes": "Routen in diesem Zyklus",
    "settings.cycles.detail.kpi.uncovered": "Konten ohne Zyklus",
    "settings.cycles.detail.uncoveredLack": (
        "Ein Konto erreicht seinen Zyklus über die Route seiner Einheit, und das wird "
        "beim Rechnungslauf ermittelt. Die hier gezählten Konten liegen auf keiner Route "
        "— ordnen Sie sie einer zu, dann sind sie abgedeckt."
    ),
    "settings.cycles.detail.uncoveredListAbsentTitle": (
        "Diese Konten werden noch nicht aufgelistet"
    ),
    "settings.cycles.detail.uncoveredListAbsentBody": (
        "Die Abdeckungsabfrage liefert eine Anzahl und keine Zeilen."
    ),
    "settings.cycles.detail.runsAbsentTitle": "Frühere Läufe werden noch nicht aufgelistet",
    "settings.cycles.detail.runsAbsentBody": (
        "Rechnungsläufe werden in der Abrechnung gestartet, und nichts listet die Läufe "
        "eines Zyklus auf."
    ),
    "settings.cycles.detail.openInBilling": "In der Abrechnung öffnen →",
    "settings.cycles.detail.notFoundTitle": "Dieser Zyklus steht nicht in dieser Liste",
    "settings.cycles.detail.notFoundBody": (
        "Er wurde möglicherweise gelöscht. Gehen Sie zurück und wählen Sie einen aus."
    ),
    "settings.routes.wizard.loading": "Route wird geöffnet…",
    "settings.cycles.wizard.loading": "Zyklus wird geöffnet…",
    "settings.routes.wizard.selectedCount.one": "{{count}} ausgewählt",
    "settings.routes.wizard.selectedCount.other": "{{count}} ausgewählt",
    "settings.cycles.wizard.routesSelected.one": "{{count}} Route ausgewählt",
    "settings.cycles.wizard.routesSelected.other": "{{count}} Routen ausgewählt",
    "settings.cycles.wizard.routesMembers.one": "{{routes}} Route · {{members}} Mitglieder",
    "settings.cycles.wizard.routesMembers.other": "{{routes}} Routen · {{members}} Mitglieder",
    "metering.cycles.col.frequency": "Häufigkeit",
    "metering.cycles.col.startDay": "Starttag",
    "metering.cycles.col.daysToComplete": "Tage bis zum Abschluss",
    "metering.routes.col.services": "Sparte(n)",
    "metering.ops.openDetail": "{{code}} öffnen",
}

T["es"] = {
    "settings.routesCycles.subTabsLabel": "Rutas y ciclos",
    "settings.routesCycles.subTab.routes": "Rutas",
    "settings.routesCycles.subTab.cycles": "Ciclos",
    "settings.routes.col.routeNo": "N.º de ruta",
    "settings.routes.col.services": "Servicio(s)",
    "settings.routes.col.area": "Zona",
    "settings.cycles.col.cycleNo": "N.º de ciclo",
    "settings.cycles.col.startDay": "Día de inicio",
    "settings.cycles.col.daysToComplete": "Días para completar",
    "settings.cycles.coverage.gap": (
        "{{count}} cuentas no están en ningún ciclo: no se leen ni se facturan hasta "
        "que se les asigne uno."
    ),
    "settings.cycles.coverage.allCovered": "Todas las cuentas están en un ciclo.",
    "settings.cycles.frequency.daily": "Diaria",
    "settings.cycles.frequency.weekly": "Semanal",
    "settings.cycles.frequency.fortnightly": "Quincenal",
    "settings.cycles.frequency.monthly": "Mensual",
    "settings.cycles.frequency.bimonthly": "Bimestral",
    "settings.cycles.frequency.quarterly": "Trimestral",
    "settings.cycles.frequency.semiannual": "Semestral",
    "settings.cycles.frequency.annual": "Anual",
    "settings.cycles.window.derived": "Se deduce, no se guarda",
    "settings.cycles.window.stored": "Heredada de una ejecución anterior",
    "settings.cycles.window.none": "Sin ventana todavía: fije un día de inicio y una duración",
    "settings.routes.detail.tab.premises": "Inmuebles",
    "settings.routes.detail.tab.units": "Unidades",
    "settings.routes.detail.tab.assets": "Activos",
    "settings.routes.detail.tab.accounts": "Cuentas",
    "settings.routes.detail.tab.audit": "Auditoría",
    "settings.routes.detail.tabsLabel": "Secciones de la ruta",
    "settings.routes.detail.factsTitle": "Datos clave",
    "settings.routes.detail.edit": "Editar",
    "settings.routes.detail.fact.routeNo": "N.º de ruta",
    "settings.routes.detail.fact.readType": "Tipo de lectura",
    "settings.routes.detail.fact.services": "Servicio(s)",
    "settings.routes.detail.fact.area": "Zona",
    "settings.routes.detail.fact.members": "Inmuebles · unidades",
    "settings.routes.detail.fact.meters": "Medidores en la ruta",
    "settings.routes.detail.fact.cycle": "Ciclo",
    "settings.routes.detail.metersOnRoute": "{{meters}} ({{excluded}} fuera)",
    "settings.routes.detail.membersHint": (
        "Los miembros se deducen de las etiquetas de zona: los cambios se aplican en la "
        "siguiente ventana de lectura."
    ),
    "settings.routes.detail.walkOrderLede": (
        "El orden en que se visitan las paradas. Un edificio es una parada, tenga las "
        "unidades que tenga. Arrastre una parada o use las flechas."
    ),
    "settings.routes.detail.saveOrder": "Guardar el orden ✓",
    "settings.routes.detail.resetOrder": "Deshacer los cambios",
    "settings.routes.detail.orderSaved": "Orden de recorrido guardado.",
    "settings.routes.detail.orderRouteAbsent": (
        "El orden todavía no se puede guardar: en el servidor aún no hay nada que lo reciba."
    ),
    "settings.routes.detail.printSheet": "Imprimir la hoja de ruta",
    "settings.routes.detail.unitsOnStop.one": "{{count}} unidad",
    "settings.routes.detail.unitsOnStop.other": "{{count}} unidades",
    "settings.routes.detail.noMeterVerify": "Sin medidor · verificar",
    "settings.routes.detail.moveUp": "Adelantar {{stop}}",
    "settings.routes.detail.moveDown": "Retrasar {{stop}}",
    "settings.routes.detail.noMembersTitle": "Todavía no hay nada en esta ruta",
    "settings.routes.detail.noMembersBody": (
        "Edite la ruta y elija los inmuebles que cubre."
    ),
    "settings.routes.detail.sheet.stop": "Parada",
    "settings.routes.detail.sheet.premises": "Inmueble",
    "settings.routes.detail.sheet.units": "Unidades",
    "settings.routes.detail.sheet.meters": "Medidores",
    "settings.routes.detail.col.unit": "Unidad",
    "settings.routes.detail.col.onRoute": "En la ruta",
    "settings.routes.detail.included": "Incluido",
    "settings.routes.detail.excluded": "Fuera",
    "settings.routes.detail.exclusionReasonAbsentTitle": (
        "Todavía no se muestra por qué se dejó fuera un medidor"
    ),
    "settings.routes.detail.exclusionReasonAbsentBody": (
        "Con cada medidor dejado fuera se guarda un motivo breve, y aún no llega a esta "
        "pantalla."
    ),
    "settings.routes.detail.accountsAbsentTitle": (
        "Las cuentas de esta ruta todavía no se listan"
    ),
    "settings.routes.detail.accountsAbsentBody": (
        "Esta pestaña dice quién está en la ruta y nada sobre lo que se le cobra: una "
        "ruta es solo una agrupación. Para listarlas falta una consulta que devuelva las "
        "cuentas de una ruta."
    ),
    "settings.routes.detail.readHistoryAbsentTitle": (
        "El historial de lecturas todavía no está disponible"
    ),
    "settings.routes.detail.readHistoryAbsentBody": (
        "Cada ventana de lectura se guarda como un registro que puede cerrarse: la "
        "ventana, cuántas se recogieron, cuántas se esperaban y el resultado. Todavía no "
        "llegan a esta pantalla."
    ),
    "settings.cycles.detail.tab.schedule": "Calendario",
    "settings.cycles.detail.tab.routes": "Rutas",
    "settings.cycles.detail.tab.coverage": "Cobertura",
    "settings.cycles.detail.tab.runs": "Ejecuciones",
    "settings.cycles.detail.tab.audit": "Auditoría",
    "settings.cycles.detail.tabsLabel": "Secciones del ciclo",
    "settings.cycles.detail.factsTitle": "Datos clave",
    "settings.cycles.detail.edit": "Editar",
    "settings.cycles.detail.fact.cycleNo": "N.º de ciclo",
    "settings.cycles.detail.starts": "Empieza",
    "settings.cycles.detail.daysToComplete": "Días para completar",
    "settings.cycles.detail.window": "Ventana",
    "settings.cycles.detail.firstRun": "Primera ejecución",
    "settings.cycles.detail.fromNextTag": "DESDE LA SIGUIENTE",
    "settings.cycles.detail.fromNext": (
        "Cambiar el calendario se aplica desde la siguiente ventana: nada de lo ya "
        "emitido cambia."
    ),
    "settings.cycles.detail.defaultsFootnote": (
        "Los cargos y los impuestos viven en el plan, nunca aquí. El día de facturación y "
        "el día de vencimiento son los valores por defecto de este ciclo: cada ejecución "
        "parte de ellos y puede cambiarlos para esa ejecución sin cambiar lo guardado."
    ),
    "settings.cycles.detail.windowsAbsentTitle": (
        "Las próximas ventanas todavía no están calculadas"
    ),
    "settings.cycles.detail.windowsAbsentBody": (
            "Las fechas se desprenden del día de inicio, la frecuencia y la duración, pero todavía nada las envía a esta pantalla, y aquí no se muestra nada antes que una fecha que nadie ha confirmado."
    ),
    "settings.cycles.detail.monthEndUnruledTitle": (
        "El día {{day}} no existe en todos los meses"
    ),
    "settings.cycles.detail.monthEndUnruledBody": (
        "Febrero es más corto. No se ha decidido si este ciclo lee entonces el último día "
        "del mes, se salta ese mes o pasa al siguiente, así que no se muestra ninguna "
        "fecha hasta que se decida."
    ),
    "settings.cycles.detail.moveFootnote": (
        "Al traer una aquí, sale de su ciclo anterior en la siguiente ventana."
    ),
    "settings.cycles.detail.noRoutesTitle": "Este ciclo no tiene rutas",
    "settings.cycles.detail.noRoutesBody": (
        "Edite el ciclo y elija las rutas que factura."
    ),
    "settings.cycles.detail.kpi.accounts": "Cuentas en este ciclo",
    "settings.cycles.detail.kpi.routes": "Rutas en este ciclo",
    "settings.cycles.detail.kpi.uncovered": "Cuentas sin ciclo",
    "settings.cycles.detail.uncoveredLack": (
        "Una cuenta llega a su ciclo por la ruta de su unidad, y eso se resuelve al "
        "ejecutar la facturación. Las cuentas contadas aquí no están en ninguna ruta: "
        "póngalas en una y quedan cubiertas."
    ),
    "settings.cycles.detail.uncoveredListAbsentTitle": "Esas cuentas todavía no se listan",
    "settings.cycles.detail.uncoveredListAbsentBody": (
        "La consulta de cobertura responde con un recuento y sin filas."
    ),
    "settings.cycles.detail.runsAbsentTitle": (
        "Las ejecuciones anteriores todavía no se listan"
    ),
    "settings.cycles.detail.runsAbsentBody": (
        "Las ejecuciones de facturación se inician en Facturación, y nada lista las de un "
        "ciclo."
    ),
    "settings.cycles.detail.openInBilling": "Abrir en Facturación →",
    "settings.cycles.detail.notFoundTitle": "Ese ciclo no está en esta lista",
    "settings.cycles.detail.notFoundBody": (
        "Puede que se haya eliminado. Vuelva atrás y elija uno."
    ),
    "settings.routes.wizard.loading": "Abriendo la ruta…",
    "settings.cycles.wizard.loading": "Abriendo el ciclo…",
    "settings.routes.wizard.selectedCount.one": "{{count}} seleccionado",
    "settings.routes.wizard.selectedCount.other": "{{count}} seleccionados",
    "settings.cycles.wizard.routesSelected.one": "{{count}} ruta seleccionada",
    "settings.cycles.wizard.routesSelected.other": "{{count}} rutas seleccionadas",
    "settings.cycles.wizard.routesMembers.one": "{{routes}} ruta · {{members}} miembros",
    "settings.cycles.wizard.routesMembers.other": "{{routes}} rutas · {{members}} miembros",
    "metering.cycles.col.frequency": "Frecuencia",
    "metering.cycles.col.startDay": "Día de inicio",
    "metering.cycles.col.daysToComplete": "Días para completar",
    "metering.routes.col.services": "Servicio(s)",
    "metering.ops.openDetail": "Abrir {{code}}",
}

# es-MX shares Spanish grammar and differs in register; the strings that read
# identically to `es` would fail G15's byte-equality check ONLY against
# English, not against another translation, so the Mexican catalogue is
# translated in its own register where the wording genuinely differs and
# otherwise reuses the Castilian sentence — which is what a Mexican utility
# would read anyway.
T["es-MX"] = dict(T["es"])
T["es-MX"].update(
    {
        "settings.routes.detail.tab.premises": "Predios",
        "settings.routes.detail.fact.members": "Predios · unidades",
        "settings.routes.detail.sheet.premises": "Predio",
        "settings.routes.detail.noMembersBody": "Edita la ruta y elige los predios que cubre.",
        "settings.routes.detail.walkOrderLede": (
            "El orden en que se visitan las paradas. Un edificio es una parada, sin "
            "importar cuántas unidades tenga. Arrastra una parada o usa las flechas."
        ),
        "settings.cycles.detail.noRoutesBody": "Edita el ciclo y elige las rutas que factura.",
        "settings.cycles.detail.notFoundBody": (
            "Puede que se haya eliminado. Regresa y elige uno."
        ),
        "settings.routes.detail.accountsAbsentBody": (
            "Esta pestaña dice quién está en la ruta y nada sobre lo que se le cobra: una "
            "ruta es solo una agrupación. Para listarlas falta una consulta que devuelva "
            "las cuentas de una ruta."
        ),
    }
)

T["fr-FR"] = {
    "settings.routesCycles.subTabsLabel": "Tournées et cycles",
    "settings.routesCycles.subTab.routes": "Tournées",
    "settings.routesCycles.subTab.cycles": "Cycles de facturation",
    "settings.routes.col.routeNo": "N° de tournée",
    "settings.routes.col.services": "Prestation(s)",
    "settings.routes.col.area": "Secteur",
    "settings.cycles.col.cycleNo": "N° de cycle",
    "settings.cycles.col.startDay": "Jour de début",
    "settings.cycles.col.daysToComplete": "Jours pour terminer",
    "settings.cycles.coverage.gap": (
        "{{count}} comptes ne sont sur aucun cycle — ils ne sont ni relevés ni facturés "
        "tant qu'aucun ne leur est attribué."
    ),
    "settings.cycles.coverage.allCovered": "Chaque compte est sur un cycle.",
    "settings.cycles.frequency.daily": "Quotidien",
    "settings.cycles.frequency.weekly": "Hebdomadaire",
    "settings.cycles.frequency.fortnightly": "Bimensuel",
    "settings.cycles.frequency.monthly": "Mensuel",
    "settings.cycles.frequency.bimonthly": "Bimestriel",
    "settings.cycles.frequency.quarterly": "Trimestriel",
    "settings.cycles.frequency.semiannual": "Semestriel",
    "settings.cycles.frequency.annual": "Annuel",
    "settings.cycles.window.derived": "Déduite, pas enregistrée",
    "settings.cycles.window.stored": "Reprise d'une exécution précédente",
    "settings.cycles.window.none": "Pas encore de fenêtre — indiquez un jour de début et une durée",
    "settings.routes.detail.tab.premises": "Sites",
    "settings.routes.detail.tab.units": "Lots",
    "settings.routes.detail.tab.assets": "Équipements",
    "settings.routes.detail.tab.accounts": "Comptes",
    "settings.routes.detail.tab.audit": "Journal",
    "settings.routes.detail.tabsLabel": "Sections de la tournée",
    "settings.routes.detail.factsTitle": "Repères",
    "settings.routes.detail.edit": "Modifier",
    "settings.routes.detail.fact.routeNo": "N° de tournée",
    "settings.routes.detail.fact.readType": "Type de relevé",
    "settings.routes.detail.fact.services": "Prestation(s)",
    "settings.routes.detail.fact.area": "Secteur",
    "settings.routes.detail.fact.members": "Sites · lots",
    "settings.routes.detail.fact.meters": "Compteurs sur la tournée",
    "settings.routes.detail.fact.cycle": "Cycle de facturation",
    "settings.routes.detail.metersOnRoute": "{{meters}} ({{excluded}} écartés)",
    "settings.routes.detail.membersHint": (
        "Les membres découlent des étiquettes de secteur — les changements s'appliquent à "
        "la prochaine fenêtre de relevé."
    ),
    "settings.routes.detail.walkOrderLede": (
        "L'ordre de passage des arrêts. Un immeuble est un arrêt, quel que soit le nombre "
        "de lots. Faites glisser un arrêt ou utilisez les flèches."
    ),
    "settings.routes.detail.saveOrder": "Enregistrer l'ordre ✓",
    "settings.routes.detail.resetOrder": "Annuler les changements",
    "settings.routes.detail.orderSaved": "Ordre de passage enregistré.",
    "settings.routes.detail.orderRouteAbsent": (
        "L'ordre ne peut pas encore être enregistré — rien ne le reçoit côté serveur."
    ),
    "settings.routes.detail.printSheet": "Imprimer la feuille de tournée",
    "settings.routes.detail.unitsOnStop.one": "{{count}} lot",
    "settings.routes.detail.unitsOnStop.other": "{{count}} lots",
    "settings.routes.detail.noMeterVerify": "Pas de compteur · à vérifier",
    "settings.routes.detail.moveUp": "Avancer {{stop}}",
    "settings.routes.detail.moveDown": "Reculer {{stop}}",
    "settings.routes.detail.noMembersTitle": "Rien n'est encore sur cette tournée",
    "settings.routes.detail.noMembersBody": (
        "Modifiez la tournée et choisissez les sites qu'elle couvre."
    ),
    "settings.routes.detail.sheet.stop": "Arrêt",
    "settings.routes.detail.sheet.premises": "Site",
    "settings.routes.detail.sheet.units": "Lots",
    "settings.routes.detail.sheet.meters": "Compteurs",
    "settings.routes.detail.col.unit": "Lot",
    "settings.routes.detail.col.onRoute": "Sur la tournée",
    "settings.routes.detail.included": "Inclus",
    "settings.routes.detail.excluded": "Écarté",
    "settings.routes.detail.exclusionReasonAbsentTitle": (
        "La raison pour laquelle un compteur a été écarté n'est pas encore affichée"
    ),
    "settings.routes.detail.exclusionReasonAbsentBody": (
        "Une raison courte est conservée pour chaque compteur écarté, et elle n'arrive pas "
        "encore jusqu'à cet écran."
    ),
    "settings.routes.detail.accountsAbsentTitle": (
        "Les comptes de cette tournée ne sont pas encore listés"
    ),
    "settings.routes.detail.accountsAbsentBody": (
        "Cet onglet dit qui est sur la tournée et rien sur ce qui lui est facturé — une "
        "tournée n'est qu'un regroupement. Il manque une requête qui renvoie les comptes "
        "d'une tournée."
    ),
    "settings.routes.detail.readHistoryAbsentTitle": (
        "L'historique des relevés n'est pas encore disponible"
    ),
    "settings.routes.detail.readHistoryAbsentBody": (
        "Chaque fenêtre de relevé est conservée comme un enregistrement que l'on peut "
        "clore — la fenêtre, le nombre de relevés obtenus, le nombre attendu et le "
        "résultat. Rien ne les transmet encore à cet écran."
    ),
    "settings.cycles.detail.tab.schedule": "Calendrier",
    "settings.cycles.detail.tab.routes": "Tournées",
    "settings.cycles.detail.tab.coverage": "Couverture",
    "settings.cycles.detail.tab.runs": "Exécutions",
    "settings.cycles.detail.tab.audit": "Journal",
    "settings.cycles.detail.tabsLabel": "Sections du cycle",
    "settings.cycles.detail.factsTitle": "Repères",
    "settings.cycles.detail.edit": "Modifier",
    "settings.cycles.detail.fact.cycleNo": "N° de cycle",
    "settings.cycles.detail.starts": "Commence",
    "settings.cycles.detail.daysToComplete": "Jours pour terminer",
    "settings.cycles.detail.window": "Fenêtre",
    "settings.cycles.detail.firstRun": "Première exécution",
    "settings.cycles.detail.fromNextTag": "À PARTIR DE LA SUIVANTE",
    "settings.cycles.detail.fromNext": (
        "Modifier le calendrier s'applique à partir de la prochaine fenêtre — rien de ce "
        "qui est déjà émis ne change."
    ),
    "settings.cycles.detail.defaultsFootnote": (
        "Les frais et les taxes vivent sur le tarif, jamais ici. Le jour de facturation et "
        "le jour d'échéance sont les valeurs par défaut de ce cycle — une exécution part "
        "d'elles et peut les changer pour cette exécution sans changer l'enregistrement."
    ),
    "settings.cycles.detail.windowsAbsentTitle": (
        "Les prochaines fenêtres ne sont pas encore calculées"
    ),
    "settings.cycles.detail.windowsAbsentBody": (
            "Les dates découlent du jour de début, de la fréquence et de la durée, mais rien ne les transmet encore à cet écran, et mieux vaut ne rien afficher qu'une date que personne n'a confirmée."
    ),
    "settings.cycles.detail.monthEndUnruledTitle": (
        "Le {{day}} n'existe pas dans tous les mois"
    ),
    "settings.cycles.detail.monthEndUnruledBody": (
        "Février est plus court. Savoir si ce cycle relève alors le dernier jour du mois, "
        "saute ce mois ou passe au suivant n'a pas été tranché — aucune date n'est donc "
        "affichée tant que ce n'est pas le cas."
    ),
    "settings.cycles.detail.moveFootnote": (
        "En amener une ici la retire de son ancien cycle à la prochaine fenêtre."
    ),
    "settings.cycles.detail.noRoutesTitle": "Aucune tournée sur ce cycle",
    "settings.cycles.detail.noRoutesBody": (
        "Modifiez le cycle et choisissez les tournées qu'il facture."
    ),
    "settings.cycles.detail.kpi.accounts": "Comptes sur ce cycle",
    "settings.cycles.detail.kpi.routes": "Tournées sur ce cycle",
    "settings.cycles.detail.kpi.uncovered": "Comptes sans cycle",
    "settings.cycles.detail.uncoveredLack": (
        "Un compte atteint son cycle par la tournée de son lot, et cela se résout au "
        "moment de la facturation. Les comptes comptés ici ne sont sur aucune tournée — "
        "mettez-les sur une tournée et ils sont couverts."
    ),
    "settings.cycles.detail.uncoveredListAbsentTitle": (
        "Ces comptes ne sont pas encore listés"
    ),
    "settings.cycles.detail.uncoveredListAbsentBody": (
        "La requête de couverture renvoie un décompte et aucune ligne."
    ),
    "settings.cycles.detail.runsAbsentTitle": (
        "Les exécutions passées ne sont pas encore listées"
    ),
    "settings.cycles.detail.runsAbsentBody": (
        "Les exécutions de facturation démarrent dans Facturation, et rien ne liste celles "
        "d'un cycle."
    ),
    "settings.cycles.detail.openInBilling": "Ouvrir dans Facturation →",
    "settings.cycles.detail.notFoundTitle": "Ce cycle ne figure pas dans cette liste",
    "settings.cycles.detail.notFoundBody": (
        "Il a peut-être été supprimé. Revenez en arrière et choisissez-en un."
    ),
    "settings.routes.wizard.loading": "Ouverture de la tournée…",
    "settings.cycles.wizard.loading": "Ouverture du cycle…",
    "settings.routes.wizard.selectedCount.one": "{{count}} sélectionné",
    "settings.routes.wizard.selectedCount.other": "{{count}} sélectionnés",
    "settings.cycles.wizard.routesSelected.one": "{{count}} tournée sélectionnée",
    "settings.cycles.wizard.routesSelected.other": "{{count}} tournées sélectionnées",
    "settings.cycles.wizard.routesMembers.one": "{{routes}} tournée · {{members}} membres",
    "settings.cycles.wizard.routesMembers.other": "{{routes}} tournées · {{members}} membres",
    "metering.cycles.col.frequency": "Fréquence",
    "metering.cycles.col.startDay": "Jour de début",
    "metering.cycles.col.daysToComplete": "Jours pour terminer",
    "metering.routes.col.services": "Prestation(s)",
    "metering.ops.openDetail": "Ouvrir {{code}}",
}

T["it-IT"] = {
    "settings.routesCycles.subTabsLabel": "Percorsi e cicli",
    "settings.routesCycles.subTab.routes": "Percorsi",
    "settings.routesCycles.subTab.cycles": "Cicli",
    "settings.routes.col.routeNo": "N. percorso",
    "settings.routes.col.services": "Servizio/i",
    "settings.routes.col.area": "Zona",
    "settings.cycles.col.cycleNo": "N. ciclo",
    "settings.cycles.col.startDay": "Giorno di inizio",
    "settings.cycles.col.daysToComplete": "Giorni per completare",
    "settings.cycles.coverage.gap": (
        "{{count}} conti non sono su nessun ciclo: non vengono né letti né fatturati "
        "finché non se ne assegna uno."
    ),
    "settings.cycles.coverage.allCovered": "Ogni conto è su un ciclo.",
    "settings.cycles.frequency.daily": "Giornaliera",
    "settings.cycles.frequency.weekly": "Settimanale",
    "settings.cycles.frequency.fortnightly": "Quindicinale",
    "settings.cycles.frequency.monthly": "Mensile",
    "settings.cycles.frequency.bimonthly": "Bimestrale",
    "settings.cycles.frequency.quarterly": "Trimestrale",
    "settings.cycles.frequency.semiannual": "Semestrale",
    "settings.cycles.frequency.annual": "Annuale",
    "settings.cycles.window.derived": "Ricavata, non salvata",
    "settings.cycles.window.stored": "Ereditata da un'esecuzione precedente",
    "settings.cycles.window.none": "Nessuna finestra: imposta un giorno di inizio e una durata",
    "settings.routes.detail.tab.premises": "Immobili",
    "settings.routes.detail.tab.units": "Unità",
    "settings.routes.detail.tab.assets": "Apparati",
    "settings.routes.detail.tab.accounts": "Conti",
    "settings.routes.detail.tab.audit": "Registro",
    "settings.routes.detail.tabsLabel": "Sezioni del percorso",
    "settings.routes.detail.factsTitle": "Dati chiave",
    "settings.routes.detail.edit": "Modifica",
    "settings.routes.detail.fact.routeNo": "N. percorso",
    "settings.routes.detail.fact.readType": "Tipo di lettura",
    "settings.routes.detail.fact.services": "Servizio/i",
    "settings.routes.detail.fact.area": "Zona",
    "settings.routes.detail.fact.members": "Immobili · unità",
    "settings.routes.detail.fact.meters": "Contatori sul percorso",
    "settings.routes.detail.fact.cycle": "Ciclo",
    "settings.routes.detail.metersOnRoute": "{{meters}} ({{excluded}} esclusi)",
    "settings.routes.detail.membersHint": (
        "I membri derivano dalle etichette di area: le modifiche valgono dalla prossima "
        "finestra di lettura."
    ),
    "settings.routes.detail.walkOrderLede": (
        "L'ordine in cui si visitano le fermate. Un edificio è una fermata, quante che "
        "siano le unità al suo interno. Trascina una fermata o usa le frecce."
    ),
    "settings.routes.detail.saveOrder": "Salva l'ordine ✓",
    "settings.routes.detail.resetOrder": "Annulla le modifiche",
    "settings.routes.detail.orderSaved": "Ordine di percorrenza salvato.",
    "settings.routes.detail.orderRouteAbsent": (
        "L'ordine non si può ancora salvare: sul server non c'è nulla che lo riceva."
    ),
    "settings.routes.detail.printSheet": "Stampa il foglio di percorso",
    "settings.routes.detail.unitsOnStop.one": "{{count}} unità",
    "settings.routes.detail.unitsOnStop.other": "{{count}} unità in tutto",
    "settings.routes.detail.noMeterVerify": "Nessun contatore · verificare",
    "settings.routes.detail.moveUp": "Anticipa {{stop}}",
    "settings.routes.detail.moveDown": "Posticipa {{stop}}",
    "settings.routes.detail.noMembersTitle": "Su questo percorso non c'è ancora nulla",
    "settings.routes.detail.noMembersBody": (
        "Modifica il percorso e scegli gli immobili che copre."
    ),
    "settings.routes.detail.sheet.stop": "Fermata",
    "settings.routes.detail.sheet.premises": "Immobile",
    "settings.routes.detail.sheet.units": "Unità",
    "settings.routes.detail.sheet.meters": "Contatori",
    "settings.routes.detail.col.unit": "Unità",
    "settings.routes.detail.col.onRoute": "Sul percorso",
    "settings.routes.detail.included": "Incluso",
    "settings.routes.detail.excluded": "Escluso",
    "settings.routes.detail.exclusionReasonAbsentTitle": (
        "Il motivo per cui un contatore è escluso non è ancora visibile"
    ),
    "settings.routes.detail.exclusionReasonAbsentBody": (
        "Per ogni contatore escluso viene conservato un motivo breve, che a questa "
        "schermata non arriva ancora."
    ),
    "settings.routes.detail.accountsAbsentTitle": (
        "I conti di questo percorso non sono ancora elencati"
    ),
    "settings.routes.detail.accountsAbsentBody": (
        "Questa scheda dice chi sta sul percorso e nulla su ciò che gli viene addebitato: "
        "un percorso è solo un raggruppamento. Per elencarli manca una richiesta che "
        "restituisca i conti di un percorso."
    ),
    "settings.routes.detail.readHistoryAbsentTitle": (
        "Lo storico delle letture non è ancora disponibile"
    ),
    "settings.routes.detail.readHistoryAbsentBody": (
        "Ogni finestra di lettura è conservata come un record che si può chiudere: la "
        "finestra, quante ne sono state raccolte, quante attese e l'esito. A questa "
        "schermata non arrivano ancora."
    ),
    "settings.cycles.detail.tab.schedule": "Calendario",
    "settings.cycles.detail.tab.routes": "Percorsi",
    "settings.cycles.detail.tab.coverage": "Copertura",
    "settings.cycles.detail.tab.runs": "Esecuzioni",
    "settings.cycles.detail.tab.audit": "Registro",
    "settings.cycles.detail.tabsLabel": "Sezioni del ciclo",
    "settings.cycles.detail.factsTitle": "Dati chiave",
    "settings.cycles.detail.edit": "Modifica",
    "settings.cycles.detail.fact.cycleNo": "N. ciclo",
    "settings.cycles.detail.starts": "Inizia",
    "settings.cycles.detail.daysToComplete": "Giorni per completare",
    "settings.cycles.detail.window": "Finestra",
    "settings.cycles.detail.firstRun": "Prima esecuzione",
    "settings.cycles.detail.fromNextTag": "DALLA PROSSIMA",
    "settings.cycles.detail.fromNext": (
        "La modifica del calendario vale dalla prossima finestra: nulla di già emesso cambia."
    ),
    "settings.cycles.detail.defaultsFootnote": (
        "Oneri e imposte vivono sul piano, mai qui. Il giorno di fatturazione e il giorno "
        "di scadenza sono i valori predefiniti di questo ciclo: ogni esecuzione parte da "
        "lì e può cambiarli solo per sé, senza toccare quanto è salvato."
    ),
    "settings.cycles.detail.windowsAbsentTitle": (
        "Le prossime finestre non sono ancora calcolate"
    ),
    "settings.cycles.detail.windowsAbsentBody": (
            "Le date discendono dal giorno di inizio, dalla frequenza e dalla durata, ma nulla le invia ancora a questa schermata, e meglio non mostrare nulla che una data non confermata."
    ),
    "settings.cycles.detail.monthEndUnruledTitle": (
        "Il giorno {{day}} non esiste in tutti i mesi"
    ),
    "settings.cycles.detail.monthEndUnruledBody": (
        "Febbraio è più corto. Non è stato deciso se questo ciclo legga allora l'ultimo "
        "giorno del mese, salti quel mese o passi al successivo: finché non si decide, "
        "non viene mostrata alcuna data."
    ),
    "settings.cycles.detail.moveFootnote": (
        "Portarne uno qui lo toglie dal suo vecchio ciclo alla prossima finestra."
    ),
    "settings.cycles.detail.noRoutesTitle": "Nessun percorso su questo ciclo",
    "settings.cycles.detail.noRoutesBody": (
        "Modifica il ciclo e scegli i percorsi che fattura."
    ),
    "settings.cycles.detail.kpi.accounts": "Conti su questo ciclo",
    "settings.cycles.detail.kpi.routes": "Percorsi su questo ciclo",
    "settings.cycles.detail.kpi.uncovered": "Conti senza ciclo",
    "settings.cycles.detail.uncoveredLack": (
        "Un conto raggiunge il suo ciclo attraverso il percorso della sua unità, e questo "
        "si risolve al momento della fatturazione. I conti contati qui non sono su alcun "
        "percorso: mettili su uno e sono coperti."
    ),
    "settings.cycles.detail.uncoveredListAbsentTitle": (
        "Quei conti non sono ancora elencati"
    ),
    "settings.cycles.detail.uncoveredListAbsentBody": (
        "La richiesta di copertura risponde con un conteggio e nessuna riga."
    ),
    "settings.cycles.detail.runsAbsentTitle": (
        "Le esecuzioni passate non sono ancora elencate"
    ),
    "settings.cycles.detail.runsAbsentBody": (
        "Le esecuzioni di fatturazione partono da Fatturazione, e nulla elenca quelle di "
        "un ciclo."
    ),
    "settings.cycles.detail.openInBilling": "Apri in Fatturazione →",
    "settings.cycles.detail.notFoundTitle": "Quel ciclo non è in questo elenco",
    "settings.cycles.detail.notFoundBody": (
        "Potrebbe essere stato eliminato. Torna indietro e scegline uno."
    ),
    "settings.routes.wizard.loading": "Apertura del percorso…",
    "settings.cycles.wizard.loading": "Apertura del ciclo…",
    "settings.routes.wizard.selectedCount.one": "{{count}} selezionato",
    "settings.routes.wizard.selectedCount.other": "{{count}} selezionati",
    "settings.cycles.wizard.routesSelected.one": "{{count}} percorso selezionato",
    "settings.cycles.wizard.routesSelected.other": "{{count}} percorsi selezionati",
    "settings.cycles.wizard.routesMembers.one": "{{routes}} percorso · {{members}} membri",
    "settings.cycles.wizard.routesMembers.other": "{{routes}} percorsi · {{members}} membri",
    "metering.cycles.col.frequency": "Frequenza",
    "metering.cycles.col.startDay": "Giorno di inizio",
    "metering.cycles.col.daysToComplete": "Giorni per completare",
    "metering.routes.col.services": "Servizio/i",
    "metering.ops.openDetail": "Apri {{code}}",
}

T["pt-BR"] = {
    "settings.routesCycles.subTabsLabel": "Rotas e ciclos",
    "settings.routesCycles.subTab.routes": "Rotas",
    "settings.routesCycles.subTab.cycles": "Ciclos",
    "settings.routes.col.routeNo": "N.º da rota",
    "settings.routes.col.services": "Serviço(s)",
    "settings.routes.col.area": "Área",
    "settings.cycles.col.cycleNo": "N.º do ciclo",
    "settings.cycles.col.startDay": "Dia de início",
    "settings.cycles.col.daysToComplete": "Dias para concluir",
    "settings.cycles.coverage.gap": (
        "{{count}} contas não estão em nenhum ciclo — não são lidas nem faturadas até que "
        "um seja atribuído."
    ),
    "settings.cycles.coverage.allCovered": "Toda conta está em um ciclo.",
    "settings.cycles.frequency.daily": "Diária",
    "settings.cycles.frequency.weekly": "Semanal",
    "settings.cycles.frequency.fortnightly": "Quinzenal",
    "settings.cycles.frequency.monthly": "Mensal",
    "settings.cycles.frequency.bimonthly": "Bimestral",
    "settings.cycles.frequency.quarterly": "Trimestral",
    "settings.cycles.frequency.semiannual": "Semestral",
    "settings.cycles.frequency.annual": "Anual",
    "settings.cycles.window.derived": "Deduzida, não guardada",
    "settings.cycles.window.stored": "Herdada de uma execução anterior",
    "settings.cycles.window.none": "Ainda sem janela — defina um dia de início e uma duração",
    "settings.routes.detail.tab.premises": "Imóveis",
    "settings.routes.detail.tab.units": "Unidades",
    "settings.routes.detail.tab.assets": "Ativos",
    "settings.routes.detail.tab.accounts": "Contas",
    "settings.routes.detail.tab.audit": "Auditoria",
    "settings.routes.detail.tabsLabel": "Seções da rota",
    "settings.routes.detail.factsTitle": "Dados principais",
    "settings.routes.detail.edit": "Editar",
    "settings.routes.detail.fact.routeNo": "N.º da rota",
    "settings.routes.detail.fact.readType": "Tipo de leitura",
    "settings.routes.detail.fact.services": "Serviço(s)",
    "settings.routes.detail.fact.area": "Área",
    "settings.routes.detail.fact.members": "Imóveis · unidades",
    "settings.routes.detail.fact.meters": "Medidores na rota",
    "settings.routes.detail.fact.cycle": "Ciclo",
    "settings.routes.detail.metersOnRoute": "{{meters}} ({{excluded}} de fora)",
    "settings.routes.detail.membersHint": (
        "Os membros vêm das etiquetas de área — as mudanças valem a partir da próxima "
        "janela de leitura."
    ),
    "settings.routes.detail.walkOrderLede": (
        "A ordem em que as paradas são visitadas. Um prédio é uma parada, tenha as "
        "unidades que tiver. Arraste uma parada ou use as setas."
    ),
    "settings.routes.detail.saveOrder": "Salvar a ordem ✓",
    "settings.routes.detail.resetOrder": "Desfazer as mudanças",
    "settings.routes.detail.orderSaved": "Ordem de percurso salva.",
    "settings.routes.detail.orderRouteAbsent": (
        "A ordem ainda não pode ser salva — no servidor ainda não há nada que a receba."
    ),
    "settings.routes.detail.printSheet": "Imprimir a folha de rota",
    "settings.routes.detail.unitsOnStop.one": "{{count}} unidade",
    "settings.routes.detail.unitsOnStop.other": "{{count}} unidades",
    "settings.routes.detail.noMeterVerify": "Sem medidor · verificar",
    "settings.routes.detail.moveUp": "Adiantar {{stop}}",
    "settings.routes.detail.moveDown": "Atrasar {{stop}}",
    "settings.routes.detail.noMembersTitle": "Ainda não há nada nesta rota",
    "settings.routes.detail.noMembersBody": (
        "Edite a rota e escolha os imóveis que ela cobre."
    ),
    "settings.routes.detail.sheet.stop": "Parada",
    "settings.routes.detail.sheet.premises": "Imóvel",
    "settings.routes.detail.sheet.units": "Unidades",
    "settings.routes.detail.sheet.meters": "Medidores",
    "settings.routes.detail.col.unit": "Unidade",
    "settings.routes.detail.col.onRoute": "Na rota",
    "settings.routes.detail.included": "Incluído",
    "settings.routes.detail.excluded": "De fora",
    "settings.routes.detail.exclusionReasonAbsentTitle": (
        "Por que um medidor ficou de fora ainda não aparece"
    ),
    "settings.routes.detail.exclusionReasonAbsentBody": (
        "Uma justificativa curta é guardada com cada medidor deixado de fora, e ela ainda "
        "não chega a esta tela."
    ),
    "settings.routes.detail.accountsAbsentTitle": (
        "As contas desta rota ainda não são listadas"
    ),
    "settings.routes.detail.accountsAbsentBody": (
        "Esta aba diz quem está na rota e nada sobre o que é cobrado — uma rota é apenas "
        "um agrupamento. Para listá-las falta uma consulta que devolva as contas de uma "
        "rota."
    ),
    "settings.routes.detail.readHistoryAbsentTitle": (
        "O histórico de leituras ainda não está disponível"
    ),
    "settings.routes.detail.readHistoryAbsentBody": (
        "Cada janela de leitura é guardada como um registro que pode ser fechado — a "
        "janela, quantas foram coletadas, quantas eram esperadas e o resultado. Nada as "
        "envia para esta tela ainda."
    ),
    "settings.cycles.detail.tab.schedule": "Calendário",
    "settings.cycles.detail.tab.routes": "Rotas",
    "settings.cycles.detail.tab.coverage": "Cobertura",
    "settings.cycles.detail.tab.runs": "Execuções",
    "settings.cycles.detail.tab.audit": "Auditoria",
    "settings.cycles.detail.tabsLabel": "Seções do ciclo",
    "settings.cycles.detail.factsTitle": "Dados principais",
    "settings.cycles.detail.edit": "Editar",
    "settings.cycles.detail.fact.cycleNo": "N.º do ciclo",
    "settings.cycles.detail.starts": "Começa",
    "settings.cycles.detail.daysToComplete": "Dias para concluir",
    "settings.cycles.detail.window": "Janela",
    "settings.cycles.detail.firstRun": "Primeira execução",
    "settings.cycles.detail.fromNextTag": "A PARTIR DA PRÓXIMA",
    "settings.cycles.detail.fromNext": (
        "Mudar o calendário vale a partir da próxima janela — nada do que já foi emitido muda."
    ),
    "settings.cycles.detail.defaultsFootnote": (
        "Encargos e impostos vivem no plano, nunca aqui. O dia de faturamento e o dia de "
        "vencimento são os padrões deste ciclo — cada execução parte deles e pode alterá-los "
        "só para aquela execução, sem mudar o que está salvo."
    ),
    "settings.cycles.detail.windowsAbsentTitle": (
        "As próximas janelas ainda não estão calculadas"
    ),
    "settings.cycles.detail.windowsAbsentBody": (
            "As datas decorrem do dia de início, da frequência e da duração, mas nada as envia para esta tela ainda, e aqui não se mostra nada em vez de uma data que ninguém confirmou."
    ),
    "settings.cycles.detail.monthEndUnruledTitle": (
        "O dia {{day}} não existe em todos os meses"
    ),
    "settings.cycles.detail.monthEndUnruledBody": (
        "Fevereiro é mais curto. Se este ciclo passa então a ler no último dia do mês, "
        "pula o mês ou vai para o seguinte ainda não foi decidido — até lá, nenhuma data "
        "é mostrada."
    ),
    "settings.cycles.detail.moveFootnote": (
        "Trazer uma para cá a tira do ciclo antigo na próxima janela."
    ),
    "settings.cycles.detail.noRoutesTitle": "Nenhuma rota neste ciclo",
    "settings.cycles.detail.noRoutesBody": (
        "Edite o ciclo e escolha as rotas que ele fatura."
    ),
    "settings.cycles.detail.kpi.accounts": "Contas neste ciclo",
    "settings.cycles.detail.kpi.routes": "Rotas neste ciclo",
    "settings.cycles.detail.kpi.uncovered": "Contas sem ciclo",
    "settings.cycles.detail.uncoveredLack": (
        "Uma conta chega ao seu ciclo pela rota da sua unidade, e isso é resolvido na hora "
        "do faturamento. As contas contadas aqui não estão em nenhuma rota — coloque-as em "
        "uma e ficam cobertas."
    ),
    "settings.cycles.detail.uncoveredListAbsentTitle": (
        "Essas contas ainda não são listadas"
    ),
    "settings.cycles.detail.uncoveredListAbsentBody": (
        "A consulta de cobertura responde com uma contagem e nenhuma linha."
    ),
    "settings.cycles.detail.runsAbsentTitle": (
        "As execuções anteriores ainda não são listadas"
    ),
    "settings.cycles.detail.runsAbsentBody": (
        "As execuções de faturamento começam em Faturamento, e nada lista as de um ciclo."
    ),
    "settings.cycles.detail.openInBilling": "Abrir em Faturamento →",
    "settings.cycles.detail.notFoundTitle": "Esse ciclo não está nesta lista",
    "settings.cycles.detail.notFoundBody": (
        "Ele pode ter sido excluído. Volte e escolha um."
    ),
    "settings.routes.wizard.loading": "Abrindo a rota…",
    "settings.cycles.wizard.loading": "Abrindo o ciclo…",
    "settings.routes.wizard.selectedCount.one": "{{count}} selecionado",
    "settings.routes.wizard.selectedCount.other": "{{count}} selecionados",
    "settings.cycles.wizard.routesSelected.one": "{{count}} rota selecionada",
    "settings.cycles.wizard.routesSelected.other": "{{count}} rotas selecionadas",
    "settings.cycles.wizard.routesMembers.one": "{{routes}} rota · {{members}} membros",
    "settings.cycles.wizard.routesMembers.other": "{{routes}} rotas · {{members}} membros",
    "metering.cycles.col.frequency": "Frequência",
    "metering.cycles.col.startDay": "Dia de início",
    "metering.cycles.col.daysToComplete": "Dias para concluir",
    "metering.routes.col.services": "Serviço(s)",
    "metering.ops.openDetail": "Abrir {{code}}",
}

T["id-ID"] = {
    "settings.routesCycles.subTabsLabel": "Rute dan siklus",
    "settings.routesCycles.subTab.routes": "Rute",
    "settings.routesCycles.subTab.cycles": "Siklus",
    "settings.routes.col.routeNo": "No. rute",
    "settings.routes.col.services": "Layanan",
    "settings.routes.col.area": "Wilayah",
    "settings.cycles.col.cycleNo": "No. siklus",
    "settings.cycles.col.startDay": "Hari mulai",
    "settings.cycles.col.daysToComplete": "Hari untuk selesai",
    "settings.cycles.coverage.gap": (
        "{{count}} akun tidak berada di siklus mana pun — tidak dibaca dan tidak "
        "ditagih sampai satu siklus diberikan."
    ),
    "settings.cycles.coverage.allCovered": "Semua akun berada di sebuah siklus.",
    "settings.cycles.frequency.daily": "Harian",
    "settings.cycles.frequency.weekly": "Mingguan",
    "settings.cycles.frequency.fortnightly": "Dua mingguan",
    "settings.cycles.frequency.monthly": "Bulanan",
    "settings.cycles.frequency.bimonthly": "Dua bulanan",
    "settings.cycles.frequency.quarterly": "Triwulanan",
    "settings.cycles.frequency.semiannual": "Semesteran",
    "settings.cycles.frequency.annual": "Tahunan",
    "settings.cycles.window.derived": "Diturunkan, tidak disimpan",
    "settings.cycles.window.stored": "Dibawa dari proses sebelumnya",
    "settings.cycles.window.none": "Belum ada jendela — tetapkan hari mulai dan lamanya",
    "settings.routes.detail.tab.premises": "Properti",
    "settings.routes.detail.tab.units": "Unit",
    "settings.routes.detail.tab.assets": "Aset",
    "settings.routes.detail.tab.accounts": "Akun",
    "settings.routes.detail.tab.audit": "Jejak audit",
    "settings.routes.detail.tabsLabel": "Bagian rute",
    "settings.routes.detail.factsTitle": "Ringkasan",
    "settings.routes.detail.edit": "Ubah",
    "settings.routes.detail.fact.routeNo": "No. rute",
    "settings.routes.detail.fact.readType": "Jenis pembacaan",
    "settings.routes.detail.fact.services": "Layanan",
    "settings.routes.detail.fact.area": "Wilayah",
    "settings.routes.detail.fact.members": "Properti · unit",
    "settings.routes.detail.fact.meters": "Meter di rute",
    "settings.routes.detail.fact.cycle": "Siklus",
    "settings.routes.detail.metersOnRoute": "{{meters}} ({{excluded}} dikecualikan)",
    "settings.routes.detail.membersHint": (
        "Anggota diturunkan dari label wilayah — perubahan berlaku pada jendela "
        "pembacaan berikutnya."
    ),
    "settings.routes.detail.walkOrderLede": (
        "Urutan pemberhentian dikunjungi. Satu gedung adalah satu pemberhentian, berapa "
        "pun unit di dalamnya. Seret pemberhentian atau gunakan panah."
    ),
    "settings.routes.detail.saveOrder": "Simpan urutan ✓",
    "settings.routes.detail.resetOrder": "Batalkan perubahan",
    "settings.routes.detail.orderSaved": "Urutan penyusuran tersimpan.",
    "settings.routes.detail.orderRouteAbsent": (
        "Urutan belum bisa disimpan — belum ada yang menerimanya di server."
    ),
    "settings.routes.detail.printSheet": "Cetak lembar rute",
    "settings.routes.detail.unitsOnStop.one": "{{count}} unit hunian",
    "settings.routes.detail.unitsOnStop.other": "{{count}} unit seluruhnya",
    "settings.routes.detail.noMeterVerify": "Tanpa meter · periksa",
    "settings.routes.detail.moveUp": "Majukan {{stop}}",
    "settings.routes.detail.moveDown": "Mundurkan {{stop}}",
    "settings.routes.detail.noMembersTitle": "Belum ada apa pun di rute ini",
    "settings.routes.detail.noMembersBody": (
        "Ubah rute lalu pilih properti yang dicakupnya."
    ),
    "settings.routes.detail.sheet.stop": "Pemberhentian",
    "settings.routes.detail.sheet.premises": "Properti",
    "settings.routes.detail.sheet.units": "Unit",
    "settings.routes.detail.sheet.meters": "Meter",
    "settings.routes.detail.col.unit": "Unit hunian",
    "settings.routes.detail.col.onRoute": "Di rute",
    "settings.routes.detail.included": "Termasuk",
    "settings.routes.detail.excluded": "Dikecualikan",
    "settings.routes.detail.exclusionReasonAbsentTitle": (
        "Alasan sebuah meter dikecualikan belum ditampilkan"
    ),
    "settings.routes.detail.exclusionReasonAbsentBody": (
        "Alasan singkat disimpan untuk setiap meter yang dikecualikan, dan belum sampai "
        "ke layar ini."
    ),
    "settings.routes.detail.accountsAbsentTitle": (
        "Akun di rute ini belum didaftar"
    ),
    "settings.routes.detail.accountsAbsentBody": (
        "Tab ini menyebut siapa yang ada di rute dan tidak menyebut apa yang ditagihkan — "
        "rute hanyalah pengelompokan. Untuk mendaftarnya masih diperlukan permintaan yang "
        "mengembalikan akun sebuah rute."
    ),
    "settings.routes.detail.readHistoryAbsentTitle": (
        "Riwayat pembacaan belum tersedia"
    ),
    "settings.routes.detail.readHistoryAbsentBody": (
        "Setiap jendela pembacaan disimpan sebagai catatan yang bisa ditutup — jendela, "
        "berapa yang terkumpul, berapa yang diharapkan, dan hasilnya. Belum ada yang "
        "mengirimkannya ke layar ini."
    ),
    "settings.cycles.detail.tab.schedule": "Jadwal",
    "settings.cycles.detail.tab.routes": "Rute",
    "settings.cycles.detail.tab.coverage": "Cakupan",
    "settings.cycles.detail.tab.runs": "Proses",
    "settings.cycles.detail.tab.audit": "Jejak audit",
    "settings.cycles.detail.tabsLabel": "Bagian siklus",
    "settings.cycles.detail.factsTitle": "Ringkasan",
    "settings.cycles.detail.edit": "Ubah",
    "settings.cycles.detail.fact.cycleNo": "No. siklus",
    "settings.cycles.detail.starts": "Mulai",
    "settings.cycles.detail.daysToComplete": "Hari untuk selesai",
    "settings.cycles.detail.window": "Jendela",
    "settings.cycles.detail.firstRun": "Proses pertama",
    "settings.cycles.detail.fromNextTag": "MULAI BERIKUTNYA",
    "settings.cycles.detail.fromNext": (
        "Perubahan jadwal berlaku mulai jendela berikutnya — yang sudah diterbitkan tidak berubah."
    ),
    "settings.cycles.detail.defaultsFootnote": (
        "Biaya dan pajak ada di paket tarif, tidak pernah di sini. Hari penagihan dan hari "
        "jatuh tempo adalah nilai bawaan siklus ini — setiap proses memakainya dan boleh "
        "mengubahnya hanya untuk proses itu, tanpa mengubah yang tersimpan."
    ),
    "settings.cycles.detail.windowsAbsentTitle": (
        "Jendela berikutnya belum dihitung"
    ),
    "settings.cycles.detail.windowsAbsentBody": (
            "Tanggalnya mengikuti hari mulai, frekuensi, dan lamanya, tetapi belum ada yang mengirimkannya ke layar ini, dan lebih baik tidak menampilkan apa pun daripada tanggal yang belum dipastikan."
    ),
    "settings.cycles.detail.monthEndUnruledTitle": (
        "Tanggal {{day}} tidak ada di setiap bulan"
    ),
    "settings.cycles.detail.monthEndUnruledBody": (
        "Februari lebih pendek. Belum diputuskan apakah siklus ini lalu membaca pada hari "
        "terakhir bulan itu, melewati bulan itu, atau bergeser ke bulan berikutnya — "
        "sampai diputuskan, tidak ada tanggal yang ditampilkan."
    ),
    "settings.cycles.detail.moveFootnote": (
        "Memindahkan satu ke sini mengeluarkannya dari siklus lamanya pada jendela berikutnya."
    ),
    "settings.cycles.detail.noRoutesTitle": "Tidak ada rute di siklus ini",
    "settings.cycles.detail.noRoutesBody": (
        "Ubah siklus lalu pilih rute yang ditagihnya."
    ),
    "settings.cycles.detail.kpi.accounts": "Akun di siklus ini",
    "settings.cycles.detail.kpi.routes": "Rute di siklus ini",
    "settings.cycles.detail.kpi.uncovered": "Akun tanpa siklus",
    "settings.cycles.detail.uncoveredLack": (
        "Sebuah akun sampai ke siklusnya lewat rute unitnya, dan itu ditentukan saat "
        "penagihan dijalankan. Akun yang dihitung di sini tidak berada di rute mana pun — "
        "masukkan ke sebuah rute dan mereka tercakup."
    ),
    "settings.cycles.detail.uncoveredListAbsentTitle": "Akun-akun itu belum didaftar",
    "settings.cycles.detail.uncoveredListAbsentBody": (
        "Permintaan cakupan menjawab dengan jumlah dan tanpa baris."
    ),
    "settings.cycles.detail.runsAbsentTitle": "Proses sebelumnya belum didaftar",
    "settings.cycles.detail.runsAbsentBody": (
        "Proses penagihan dimulai di Penagihan, dan tidak ada yang mendaftar proses sebuah siklus."
    ),
    "settings.cycles.detail.openInBilling": "Buka di Penagihan →",
    "settings.cycles.detail.notFoundTitle": "Siklus itu tidak ada dalam daftar ini",
    "settings.cycles.detail.notFoundBody": (
        "Mungkin sudah dihapus. Kembali dan pilih satu."
    ),
    "settings.routes.wizard.loading": "Membuka rute…",
    "settings.cycles.wizard.loading": "Membuka siklus…",
    "settings.routes.wizard.selectedCount.one": "{{count}} dipilih",
    "settings.routes.wizard.selectedCount.other": "{{count}} dipilih semuanya",
    "settings.cycles.wizard.routesSelected.one": "{{count}} rute dipilih",
    "settings.cycles.wizard.routesSelected.other": "{{count}} rute terpilih",
    "settings.cycles.wizard.routesMembers.one": "{{routes}} rute · {{members}} anggota",
    "settings.cycles.wizard.routesMembers.other": "{{routes}} rute · {{members}} anggota seluruhnya",
    "metering.cycles.col.frequency": "Frekuensi",
    "metering.cycles.col.startDay": "Hari mulai",
    "metering.cycles.col.daysToComplete": "Hari untuk selesai",
    "metering.routes.col.services": "Layanan",
    "metering.ops.openDetail": "Buka {{code}}",
}

T["hi"] = {
    "settings.routesCycles.subTabsLabel": "रूट और चक्र",
    "settings.routesCycles.subTab.routes": "रूट",
    "settings.routesCycles.subTab.cycles": "चक्र",
    "settings.routes.col.routeNo": "रूट सं.",
    "settings.routes.col.services": "सेवा(एँ)",
    "settings.routes.col.area": "क्षेत्र",
    "settings.cycles.col.cycleNo": "चक्र सं.",
    "settings.cycles.col.startDay": "आरंभ दिन",
    "settings.cycles.col.daysToComplete": "पूरा करने के दिन",
    "settings.cycles.coverage.gap": (
        "{{count}} खाते किसी चक्र पर नहीं हैं — जब तक कोई चक्र नहीं दिया जाता, न उनकी रीडिंग "
        "होती है और न बिल बनता है।"
    ),
    "settings.cycles.coverage.allCovered": "हर खाता किसी चक्र पर है।",
    "settings.cycles.frequency.daily": "दैनिक",
    "settings.cycles.frequency.weekly": "साप्ताहिक",
    "settings.cycles.frequency.fortnightly": "पाक्षिक",
    "settings.cycles.frequency.monthly": "मासिक",
    "settings.cycles.frequency.bimonthly": "द्वैमासिक",
    "settings.cycles.frequency.quarterly": "त्रैमासिक",
    "settings.cycles.frequency.semiannual": "अर्धवार्षिक",
    "settings.cycles.frequency.annual": "वार्षिक",
    "settings.cycles.window.derived": "निकाली गई, संग्रहित नहीं",
    "settings.cycles.window.stored": "पिछली प्रक्रिया से ली गई",
    "settings.cycles.window.none": "अभी कोई अवधि नहीं — आरंभ दिन और अवधि तय करें",
    "settings.routes.detail.tab.premises": "परिसर",
    "settings.routes.detail.tab.units": "इकाइयाँ",
    "settings.routes.detail.tab.assets": "उपकरण",
    "settings.routes.detail.tab.accounts": "खाते",
    "settings.routes.detail.tab.audit": "अंकेक्षण",
    "settings.routes.detail.tabsLabel": "रूट के हिस्से",
    "settings.routes.detail.factsTitle": "मुख्य तथ्य",
    "settings.routes.detail.edit": "संपादित करें",
    "settings.routes.detail.fact.routeNo": "रूट सं.",
    "settings.routes.detail.fact.readType": "रीडिंग का प्रकार",
    "settings.routes.detail.fact.services": "सेवा(एँ)",
    "settings.routes.detail.fact.area": "क्षेत्र",
    "settings.routes.detail.fact.members": "परिसर · इकाइयाँ",
    "settings.routes.detail.fact.meters": "रूट पर मीटर",
    "settings.routes.detail.fact.cycle": "चक्र",
    "settings.routes.detail.metersOnRoute": "{{meters}} ({{excluded}} बाहर)",
    "settings.routes.detail.membersHint": (
        "सदस्य क्षेत्र-टैग से बनते हैं — बदलाव अगली रीडिंग अवधि से लागू होते हैं।"
    ),
    "settings.routes.detail.walkOrderLede": (
        "पड़ावों पर जाने का क्रम। एक इमारत एक ही पड़ाव है, चाहे उसमें कितनी भी इकाइयाँ हों। "
        "पड़ाव खींचें या तीरों का उपयोग करें।"
    ),
    "settings.routes.detail.saveOrder": "क्रम सहेजें ✓",
    "settings.routes.detail.resetOrder": "बदलाव पूर्ववत करें",
    "settings.routes.detail.orderSaved": "चलने का क्रम सहेजा गया।",
    "settings.routes.detail.orderRouteAbsent": (
        "क्रम अभी सहेजा नहीं जा सकता — सर्वर पर इसे लेने वाला कुछ भी नहीं है।"
    ),
    "settings.routes.detail.printSheet": "रूट शीट छापें",
    "settings.routes.detail.unitsOnStop.one": "{{count}} इकाई",
    "settings.routes.detail.unitsOnStop.other": "{{count}} इकाइयाँ",
    "settings.routes.detail.noMeterVerify": "मीटर नहीं · जाँचें",
    "settings.routes.detail.moveUp": "{{stop}} को पहले करें",
    "settings.routes.detail.moveDown": "{{stop}} को बाद में करें",
    "settings.routes.detail.noMembersTitle": "इस रूट पर अभी कुछ नहीं है",
    "settings.routes.detail.noMembersBody": (
        "रूट संपादित करें और वे परिसर चुनें जिन्हें यह कवर करता है।"
    ),
    "settings.routes.detail.sheet.stop": "पड़ाव",
    "settings.routes.detail.sheet.premises": "परिसर",
    "settings.routes.detail.sheet.units": "इकाइयाँ",
    "settings.routes.detail.sheet.meters": "मीटर",
    "settings.routes.detail.col.unit": "इकाई",
    "settings.routes.detail.col.onRoute": "रूट पर",
    "settings.routes.detail.included": "शामिल",
    "settings.routes.detail.excluded": "बाहर",
    "settings.routes.detail.exclusionReasonAbsentTitle": (
        "मीटर को बाहर क्यों रखा गया, यह अभी नहीं दिखता"
    ),
    "settings.routes.detail.exclusionReasonAbsentBody": (
        "बाहर रखे हर मीटर के साथ एक छोटा कारण रखा जाता है, और वह अभी इस स्क्रीन तक नहीं आता।"
    ),
    "settings.routes.detail.accountsAbsentTitle": (
        "इस रूट के खाते अभी सूचीबद्ध नहीं हैं"
    ),
    "settings.routes.detail.accountsAbsentBody": (
        "यह टैब बताता है कि रूट पर कौन है, यह नहीं कि उनसे क्या वसूला जाता है — रूट केवल एक "
        "समूह है। सूची के लिए ऐसा अनुरोध चाहिए जो किसी रूट के खाते लौटाए, और वह अभी नहीं है।"
    ),
    "settings.routes.detail.readHistoryAbsentTitle": (
        "रीडिंग का इतिहास अभी उपलब्ध नहीं है"
    ),
    "settings.routes.detail.readHistoryAbsentBody": (
        "हर रीडिंग अवधि एक ऐसे अभिलेख के रूप में रखी जाती है जिसे बंद किया जा सकता है — अवधि, "
        "कितनी रीडिंग मिलीं, कितनी अपेक्षित थीं और परिणाम। इन्हें इस स्क्रीन तक भेजने वाला "
        "अभी कुछ नहीं है।"
    ),
    "settings.cycles.detail.tab.schedule": "समय-सारणी",
    "settings.cycles.detail.tab.routes": "रूट",
    "settings.cycles.detail.tab.coverage": "कवरेज",
    "settings.cycles.detail.tab.runs": "प्रक्रियाएँ",
    "settings.cycles.detail.tab.audit": "अंकेक्षण",
    "settings.cycles.detail.tabsLabel": "चक्र के हिस्से",
    "settings.cycles.detail.factsTitle": "मुख्य तथ्य",
    "settings.cycles.detail.edit": "संपादित करें",
    "settings.cycles.detail.fact.cycleNo": "चक्र सं.",
    "settings.cycles.detail.starts": "शुरू",
    "settings.cycles.detail.daysToComplete": "पूरा करने के दिन",
    "settings.cycles.detail.window": "अवधि",
    "settings.cycles.detail.firstRun": "पहली प्रक्रिया",
    "settings.cycles.detail.fromNextTag": "अगली से",
    "settings.cycles.detail.fromNext": (
        "समय-सारणी बदलना अगली अवधि से लागू होता है — जो बिल जारी हो चुके हैं, वे नहीं बदलते।"
    ),
    "settings.cycles.detail.defaultsFootnote": (
        "शुल्क और कर योजना पर रहते हैं, यहाँ कभी नहीं। बिल का दिन और देय दिन इस चक्र के "
        "डिफ़ॉल्ट हैं — हर प्रक्रिया इन्हीं से शुरू होती है और उसी प्रक्रिया के लिए इन्हें "
        "बदल सकती है, यहाँ सहेजा गया मान बदले बिना।"
    ),
    "settings.cycles.detail.windowsAbsentTitle": (
        "अगली अवधियाँ अभी गणना नहीं हुई हैं"
    ),
    "settings.cycles.detail.windowsAbsentBody": (
            "तिथियाँ आरंभ दिन, आवृत्ति और अवधि से निकलती हैं, पर उन्हें इस स्क्रीन तक भेजने वाला अभी कुछ नहीं है — और किसी अपुष्ट तिथि के बजाय यहाँ कुछ नहीं दिखाया जाता।"
    ),
    "settings.cycles.detail.monthEndUnruledTitle": (
        "{{day}} तारीख हर महीने में नहीं होती"
    ),
    "settings.cycles.detail.monthEndUnruledBody": (
        "फ़रवरी छोटी होती है। तब यह चक्र महीने के अंतिम दिन पढ़े, उस महीने को छोड़े, या अगले "
        "महीने में जाए — यह तय नहीं हुआ है, इसलिए तय होने तक कोई तिथि नहीं दिखाई जाती।"
    ),
    "settings.cycles.detail.moveFootnote": (
        "किसी को यहाँ लाने पर वह अगली अवधि में अपने पुराने चक्र से हट जाता है।"
    ),
    "settings.cycles.detail.noRoutesTitle": "इस चक्र पर कोई रूट नहीं",
    "settings.cycles.detail.noRoutesBody": (
        "चक्र संपादित करें और वे रूट चुनें जिनका यह बिल बनाता है।"
    ),
    "settings.cycles.detail.kpi.accounts": "इस चक्र पर खाते",
    "settings.cycles.detail.kpi.routes": "इस चक्र पर रूट",
    "settings.cycles.detail.kpi.uncovered": "बिना चक्र वाले खाते",
    "settings.cycles.detail.uncoveredLack": (
        "खाता अपनी इकाई के रूट से चक्र तक पहुँचता है, और यह बिल प्रक्रिया के समय तय होता है। "
        "यहाँ गिने गए खाते किसी रूट पर नहीं हैं — उन्हें किसी रूट पर रखें और वे कवर हो जाएँगे।"
    ),
    "settings.cycles.detail.uncoveredListAbsentTitle": "वे खाते अभी सूचीबद्ध नहीं हैं",
    "settings.cycles.detail.uncoveredListAbsentBody": (
        "कवरेज अनुरोध केवल एक गिनती लौटाता है, कोई पंक्ति नहीं।"
    ),
    "settings.cycles.detail.runsAbsentTitle": "पिछली प्रक्रियाएँ अभी सूचीबद्ध नहीं हैं",
    "settings.cycles.detail.runsAbsentBody": (
        "बिल प्रक्रियाएँ बिलिंग में शुरू होती हैं, और किसी चक्र की प्रक्रियाओं की सूची कहीं नहीं है।"
    ),
    "settings.cycles.detail.openInBilling": "बिलिंग में खोलें →",
    "settings.cycles.detail.notFoundTitle": "वह चक्र इस सूची में नहीं है",
    "settings.cycles.detail.notFoundBody": (
        "संभव है वह हटा दिया गया हो। वापस जाएँ और कोई एक चुनें।"
    ),
    "settings.routes.wizard.loading": "रूट खोला जा रहा है…",
    "settings.cycles.wizard.loading": "चक्र खोला जा रहा है…",
    "settings.routes.wizard.selectedCount.one": "{{count}} चुना गया",
    "settings.routes.wizard.selectedCount.other": "{{count}} चुने गए",
    "settings.cycles.wizard.routesSelected.one": "{{count}} रूट चुना गया",
    "settings.cycles.wizard.routesSelected.other": "{{count}} रूट चुने गए",
    "settings.cycles.wizard.routesMembers.one": "{{routes}} रूट · {{members}} सदस्य",
    "settings.cycles.wizard.routesMembers.other": "{{routes}} रूट · {{members}} सदस्य कुल",
    "metering.cycles.col.frequency": "आवृत्ति",
    "metering.cycles.col.startDay": "आरंभ दिन",
    "metering.cycles.col.daysToComplete": "पूरा करने के दिन",
    "metering.routes.col.services": "सेवा(एँ)",
    "metering.ops.openDetail": "{{code}} खोलें",
}

T["ja-JP"] = {
    "settings.routesCycles.subTabsLabel": "ルートと請求サイクル",
    "settings.routesCycles.subTab.routes": "ルート",
    "settings.routesCycles.subTab.cycles": "請求サイクル",
    "settings.routes.col.routeNo": "ルート番号",
    "settings.routes.col.services": "サービス",
    "settings.routes.col.area": "エリア",
    "settings.cycles.col.cycleNo": "サイクル番号",
    "settings.cycles.col.startDay": "開始日",
    "settings.cycles.col.daysToComplete": "完了までの日数",
    "settings.cycles.coverage.gap": (
        "{{count}} 件の顧客がどのサイクルにも属していません。サイクルが割り当てられるまで、"
        "検針も請求も行われません。"
    ),
    "settings.cycles.coverage.allCovered": "すべての顧客がいずれかのサイクルに属しています。",
    "settings.cycles.frequency.daily": "毎日",
    "settings.cycles.frequency.weekly": "毎週",
    "settings.cycles.frequency.fortnightly": "隔週",
    "settings.cycles.frequency.monthly": "毎月",
    "settings.cycles.frequency.bimonthly": "隔月",
    "settings.cycles.frequency.quarterly": "四半期ごと",
    "settings.cycles.frequency.semiannual": "半年ごと",
    "settings.cycles.frequency.annual": "毎年",
    "settings.cycles.window.derived": "保存せず、その都度算出",
    "settings.cycles.window.stored": "以前の処理から引き継ぎ",
    "settings.cycles.window.none": "期間は未設定です。開始日と日数を指定してください",
    "settings.routes.detail.tab.premises": "物件",
    "settings.routes.detail.tab.units": "区画",
    "settings.routes.detail.tab.assets": "設備",
    "settings.routes.detail.tab.accounts": "顧客",
    "settings.routes.detail.tab.audit": "監査",
    "settings.routes.detail.tabsLabel": "ルートの各項目",
    "settings.routes.detail.factsTitle": "主な情報",
    "settings.routes.detail.edit": "編集",
    "settings.routes.detail.fact.routeNo": "ルート番号",
    "settings.routes.detail.fact.readType": "検針方式",
    "settings.routes.detail.fact.services": "サービス",
    "settings.routes.detail.fact.area": "エリア",
    "settings.routes.detail.fact.members": "物件・区画",
    "settings.routes.detail.fact.meters": "ルート上のメーター",
    "settings.routes.detail.fact.cycle": "請求サイクル",
    "settings.routes.detail.metersOnRoute": "{{meters}}（{{excluded}} 件は対象外）",
    "settings.routes.detail.membersHint": (
        "対象はエリアのタグから決まります。変更は次の検針期間から反映されます。"
    ),
    "settings.routes.detail.walkOrderLede": (
        "訪問する順序です。建物は中の区画がいくつあっても 1 か所として数えます。"
        "行をドラッグするか、矢印で並べ替えてください。"
    ),
    "settings.routes.detail.saveOrder": "順序を保存 ✓",
    "settings.routes.detail.resetOrder": "変更を取り消す",
    "settings.routes.detail.orderSaved": "巡回順序を保存しました。",
    "settings.routes.detail.orderRouteAbsent": (
        "順序はまだ保存できません。サーバー側に受け取る仕組みがありません。"
    ),
    "settings.routes.detail.printSheet": "検針票を印刷",
    "settings.routes.detail.unitsOnStop.one": "{{count}} 区画",
    "settings.routes.detail.unitsOnStop.other": "{{count}} 区画",
    "settings.routes.detail.noMeterVerify": "メーターなし・要確認",
    "settings.routes.detail.moveUp": "{{stop}} を前へ",
    "settings.routes.detail.moveDown": "{{stop}} を後ろへ",
    "settings.routes.detail.noMembersTitle": "このルートにはまだ何も含まれていません",
    "settings.routes.detail.noMembersBody": (
        "ルートを編集して、対象とする物件を選んでください。"
    ),
    "settings.routes.detail.sheet.stop": "順番",
    "settings.routes.detail.sheet.premises": "物件",
    "settings.routes.detail.sheet.units": "区画",
    "settings.routes.detail.sheet.meters": "メーター",
    "settings.routes.detail.col.unit": "区画",
    "settings.routes.detail.col.onRoute": "ルート上",
    "settings.routes.detail.included": "対象",
    "settings.routes.detail.excluded": "対象外",
    "settings.routes.detail.exclusionReasonAbsentTitle": (
        "メーターを対象外にした理由はまだ表示されません"
    ),
    "settings.routes.detail.exclusionReasonAbsentBody": (
        "対象外にしたメーターごとに短い理由が保存されていますが、この画面にはまだ届いていません。"
    ),
    "settings.routes.detail.accountsAbsentTitle": (
        "このルートの顧客はまだ一覧表示できません"
    ),
    "settings.routes.detail.accountsAbsentBody": (
        "このタブが示すのはルートに含まれる相手だけで、請求内容は扱いません。ルートは"
        "まとまりにすぎないからです。一覧にはルートの顧客を返す仕組みが必要で、まだありません。"
    ),
    "settings.routes.detail.readHistoryAbsentTitle": "検針履歴はまだ表示できません",
    "settings.routes.detail.readHistoryAbsentBody": (
        "検針期間ごとに、期間・取得件数・予定件数・結果を締めることができる記録として"
        "残していますが、この画面に届ける仕組みはまだありません。"
    ),
    "settings.cycles.detail.tab.schedule": "スケジュール",
    "settings.cycles.detail.tab.routes": "ルート",
    "settings.cycles.detail.tab.coverage": "カバー状況",
    "settings.cycles.detail.tab.runs": "実行履歴",
    "settings.cycles.detail.tab.audit": "監査",
    "settings.cycles.detail.tabsLabel": "請求サイクルの各項目",
    "settings.cycles.detail.factsTitle": "主な情報",
    "settings.cycles.detail.edit": "編集",
    "settings.cycles.detail.fact.cycleNo": "サイクル番号",
    "settings.cycles.detail.starts": "開始",
    "settings.cycles.detail.daysToComplete": "完了までの日数",
    "settings.cycles.detail.window": "期間",
    "settings.cycles.detail.firstRun": "初回実行",
    "settings.cycles.detail.fromNextTag": "次回から",
    "settings.cycles.detail.fromNext": (
        "スケジュールの変更は次の期間から適用されます。発行済みの請求は変わりません。"
    ),
    "settings.cycles.detail.defaultsFootnote": (
        "料金と税は料金プランに属し、ここには置きません。請求日と支払期限日はこのサイクルの"
        "既定値で、実行時にその回だけ変更でき、ここに保存された値は変わりません。"
    ),
    "settings.cycles.detail.windowsAbsentTitle": "次の期間はまだ算出されていません",
    "settings.cycles.detail.windowsAbsentBody": (
            "日付は開始日・頻度・日数から決まりますが、この画面に届ける仕組みがまだありません。誰も確認していない日付を出すより、何も表示しません。"
    ),
    "settings.cycles.detail.monthEndUnruledTitle": (
        "{{day}} 日は存在しない月があります"
    ),
    "settings.cycles.detail.monthEndUnruledBody": (
        "2 月は日数が少なくなります。その場合に月末で検針するのか、その月を飛ばすのか、"
        "翌月へずらすのかは決まっていません。決まるまで日付は表示しません。"
    ),
    "settings.cycles.detail.moveFootnote": (
        "ここへ移すと、そのルートは次の期間から元のサイクルを外れます。"
    ),
    "settings.cycles.detail.noRoutesTitle": "このサイクルにルートはありません",
    "settings.cycles.detail.noRoutesBody": (
        "サイクルを編集して、請求対象のルートを選んでください。"
    ),
    "settings.cycles.detail.kpi.accounts": "このサイクルの顧客数",
    "settings.cycles.detail.kpi.routes": "このサイクルのルート数",
    "settings.cycles.detail.kpi.uncovered": "サイクル未設定の顧客",
    "settings.cycles.detail.uncoveredLack": (
        "顧客は区画のルートを通じてサイクルにたどり着き、それは請求処理のときに決まります。"
        "ここで数えている顧客はどのルートにも属していません。ルートに入れればカバーされます。"
    ),
    "settings.cycles.detail.uncoveredListAbsentTitle": "その顧客はまだ一覧表示できません",
    "settings.cycles.detail.uncoveredListAbsentBody": (
        "カバー状況の問い合わせは件数だけを返し、明細は返しません。"
    ),
    "settings.cycles.detail.runsAbsentTitle": "過去の実行はまだ一覧表示できません",
    "settings.cycles.detail.runsAbsentBody": (
        "請求処理は請求業務の画面から開始します。サイクルごとの実行を並べる仕組みはありません。"
    ),
    "settings.cycles.detail.openInBilling": "請求業務で開く →",
    "settings.cycles.detail.notFoundTitle": "その請求サイクルはこの一覧にありません",
    "settings.cycles.detail.notFoundBody": (
        "削除された可能性があります。戻って選び直してください。"
    ),
    "settings.routes.wizard.loading": "ルートを開いています…",
    "settings.cycles.wizard.loading": "請求サイクルを開いています…",
    "settings.routes.wizard.selectedCount.one": "{{count}} 件選択",
    "settings.routes.wizard.selectedCount.other": "{{count}} 件を選択",
    "settings.cycles.wizard.routesSelected.one": "ルート {{count}} 件を選択",
    "settings.cycles.wizard.routesSelected.other": "ルート {{count}} 件選択",
    "settings.cycles.wizard.routesMembers.one": "ルート {{routes}} 件・{{members}} 件の対象",
    "settings.cycles.wizard.routesMembers.other": "ルート {{routes}} 件・対象 {{members}} 件",
    "metering.cycles.col.frequency": "頻度",
    "metering.cycles.col.startDay": "開始日",
    "metering.cycles.col.daysToComplete": "完了までの日数",
    "metering.routes.col.services": "サービス",
    "metering.ops.openDetail": "{{code}} を開く",
}

T["ko-KR"] = {
    "settings.routesCycles.subTabsLabel": "검침 경로와 청구 주기",
    "settings.routesCycles.subTab.routes": "경로",
    "settings.routesCycles.subTab.cycles": "청구 주기",
    "settings.routes.col.routeNo": "경로 번호",
    "settings.routes.col.services": "서비스",
    "settings.routes.col.area": "구역",
    "settings.cycles.col.cycleNo": "주기 번호",
    "settings.cycles.col.startDay": "시작일",
    "settings.cycles.col.daysToComplete": "완료 소요 일수",
    "settings.cycles.coverage.gap": (
        "{{count}}개 계정이 어느 주기에도 속해 있지 않습니다. 주기가 지정될 때까지 검침도 "
        "청구도 이루어지지 않습니다."
    ),
    "settings.cycles.coverage.allCovered": "모든 계정이 주기에 속해 있습니다.",
    "settings.cycles.frequency.daily": "매일",
    "settings.cycles.frequency.weekly": "매주",
    "settings.cycles.frequency.fortnightly": "격주",
    "settings.cycles.frequency.monthly": "매월",
    "settings.cycles.frequency.bimonthly": "격월",
    "settings.cycles.frequency.quarterly": "분기별",
    "settings.cycles.frequency.semiannual": "반기별",
    "settings.cycles.frequency.annual": "매년",
    "settings.cycles.window.derived": "저장하지 않고 그때 산출",
    "settings.cycles.window.stored": "이전 실행에서 이어받음",
    "settings.cycles.window.none": "아직 기간이 없습니다 — 시작일과 일수를 정하세요",
    "settings.routes.detail.tab.premises": "건물",
    "settings.routes.detail.tab.units": "세대",
    "settings.routes.detail.tab.assets": "설비",
    "settings.routes.detail.tab.accounts": "계정",
    "settings.routes.detail.tab.audit": "감사",
    "settings.routes.detail.tabsLabel": "경로 항목",
    "settings.routes.detail.factsTitle": "주요 정보",
    "settings.routes.detail.edit": "편집",
    "settings.routes.detail.fact.routeNo": "경로 번호",
    "settings.routes.detail.fact.readType": "검침 방식",
    "settings.routes.detail.fact.services": "서비스",
    "settings.routes.detail.fact.area": "구역",
    "settings.routes.detail.fact.members": "건물 · 세대",
    "settings.routes.detail.fact.meters": "경로의 계량기",
    "settings.routes.detail.fact.cycle": "청구 주기",
    "settings.routes.detail.metersOnRoute": "{{meters}}개({{excluded}}개 제외)",
    "settings.routes.detail.membersHint": (
        "구성원은 구역 태그에서 정해집니다. 변경은 다음 검침 기간부터 적용됩니다."
    ),
    "settings.routes.detail.walkOrderLede": (
        "방문 순서입니다. 한 건물은 안에 세대가 몇 개든 한 곳으로 셉니다. 행을 끌거나 "
        "화살표로 옮기세요."
    ),
    "settings.routes.detail.saveOrder": "순서 저장 ✓",
    "settings.routes.detail.resetOrder": "변경 취소",
    "settings.routes.detail.orderSaved": "순회 순서를 저장했습니다.",
    "settings.routes.detail.orderRouteAbsent": (
        "순서를 아직 저장할 수 없습니다. 서버에 이를 받는 곳이 없습니다."
    ),
    "settings.routes.detail.printSheet": "검침표 인쇄",
    "settings.routes.detail.unitsOnStop.one": "{{count}}세대",
    "settings.routes.detail.unitsOnStop.other": "세대 {{count}}개",
    "settings.routes.detail.noMeterVerify": "계량기 없음 · 확인 필요",
    "settings.routes.detail.moveUp": "{{stop}} 앞으로",
    "settings.routes.detail.moveDown": "{{stop}} 뒤로",
    "settings.routes.detail.noMembersTitle": "이 경로에는 아직 아무것도 없습니다",
    "settings.routes.detail.noMembersBody": (
        "경로를 편집해 담당할 건물을 선택하세요."
    ),
    "settings.routes.detail.sheet.stop": "순번",
    "settings.routes.detail.sheet.premises": "건물",
    "settings.routes.detail.sheet.units": "세대",
    "settings.routes.detail.sheet.meters": "계량기",
    "settings.routes.detail.col.unit": "세대",
    "settings.routes.detail.col.onRoute": "경로 포함",
    "settings.routes.detail.included": "포함",
    "settings.routes.detail.excluded": "제외",
    "settings.routes.detail.exclusionReasonAbsentTitle": (
        "계량기를 제외한 이유는 아직 표시되지 않습니다"
    ),
    "settings.routes.detail.exclusionReasonAbsentBody": (
        "제외한 계량기마다 짧은 사유가 보관되지만 이 화면까지는 아직 전달되지 않습니다."
    ),
    "settings.routes.detail.accountsAbsentTitle": (
        "이 경로의 계정은 아직 목록으로 볼 수 없습니다"
    ),
    "settings.routes.detail.accountsAbsentBody": (
        "이 탭은 경로에 누가 포함되는지만 말하고 무엇이 부과되는지는 다루지 않습니다. "
        "경로는 묶음일 뿐입니다. 목록을 만들려면 경로의 계정을 돌려주는 요청이 필요한데 "
        "아직 없습니다."
    ),
    "settings.routes.detail.readHistoryAbsentTitle": "검침 이력은 아직 볼 수 없습니다",
    "settings.routes.detail.readHistoryAbsentBody": (
        "검침 기간마다 기간·수집 건수·예상 건수·결과를 담아 마감할 수 있는 기록으로 "
        "남기지만, 이 화면으로 보내주는 것이 아직 없습니다."
    ),
    "settings.cycles.detail.tab.schedule": "일정",
    "settings.cycles.detail.tab.routes": "경로",
    "settings.cycles.detail.tab.coverage": "적용 범위",
    "settings.cycles.detail.tab.runs": "실행 이력",
    "settings.cycles.detail.tab.audit": "감사",
    "settings.cycles.detail.tabsLabel": "청구 주기 항목",
    "settings.cycles.detail.factsTitle": "주요 정보",
    "settings.cycles.detail.edit": "편집",
    "settings.cycles.detail.fact.cycleNo": "주기 번호",
    "settings.cycles.detail.starts": "시작",
    "settings.cycles.detail.daysToComplete": "완료 소요 일수",
    "settings.cycles.detail.window": "기간",
    "settings.cycles.detail.firstRun": "첫 실행",
    "settings.cycles.detail.fromNextTag": "다음부터",
    "settings.cycles.detail.fromNext": (
        "일정 변경은 다음 기간부터 적용됩니다. 이미 발행된 청구서는 바뀌지 않습니다."
    ),
    "settings.cycles.detail.defaultsFootnote": (
        "요금과 세금은 요금제에 있으며 여기에는 두지 않습니다. 청구일과 납기일은 이 주기의 "
        "기본값이며, 실행할 때 그 회차에 한해 바꿀 수 있고 여기에 저장된 값은 그대로입니다."
    ),
    "settings.cycles.detail.windowsAbsentTitle": "다음 기간은 아직 계산되지 않았습니다",
    "settings.cycles.detail.windowsAbsentBody": (
            "날짜는 시작일·주기·일수에서 정해지지만, 이 화면으로 보내주는 것이 아직 없습니다. 아무도 확인하지 않은 날짜를 보이느니 아무것도 보이지 않습니다."
    ),
    "settings.cycles.detail.monthEndUnruledTitle": (
        "{{day}}일은 모든 달에 있지 않습니다"
    ),
    "settings.cycles.detail.monthEndUnruledBody": (
        "2월은 더 짧습니다. 그럴 때 이 주기가 말일에 검침하는지, 그 달을 건너뛰는지, 다음 "
        "달로 넘기는지는 정해지지 않았습니다. 정해질 때까지 날짜를 표시하지 않습니다."
    ),
    "settings.cycles.detail.moveFootnote": (
        "여기로 옮기면 다음 기간에 이전 주기에서 빠집니다."
    ),
    "settings.cycles.detail.noRoutesTitle": "이 주기에 경로가 없습니다",
    "settings.cycles.detail.noRoutesBody": (
        "주기를 편집해 청구할 경로를 선택하세요."
    ),
    "settings.cycles.detail.kpi.accounts": "이 주기의 계정 수",
    "settings.cycles.detail.kpi.routes": "이 주기의 경로 수",
    "settings.cycles.detail.kpi.uncovered": "주기가 없는 계정",
    "settings.cycles.detail.uncoveredLack": (
        "계정은 세대의 경로를 통해 주기에 이르며, 그것은 청구 실행 시점에 정해집니다. 여기서 "
        "세는 계정은 어느 경로에도 없습니다. 경로에 넣으면 적용 범위에 들어옵니다."
    ),
    "settings.cycles.detail.uncoveredListAbsentTitle": "그 계정은 아직 목록으로 볼 수 없습니다",
    "settings.cycles.detail.uncoveredListAbsentBody": (
        "적용 범위 요청은 개수만 돌려주고 행은 돌려주지 않습니다."
    ),
    "settings.cycles.detail.runsAbsentTitle": "지난 실행은 아직 목록으로 볼 수 없습니다",
    "settings.cycles.detail.runsAbsentBody": (
        "청구 실행은 청구 화면에서 시작하며, 주기별 실행을 나열하는 곳은 없습니다."
    ),
    "settings.cycles.detail.openInBilling": "청구에서 열기 →",
    "settings.cycles.detail.notFoundTitle": "그 주기는 이 목록에 없습니다",
    "settings.cycles.detail.notFoundBody": (
        "삭제되었을 수 있습니다. 돌아가서 다시 선택하세요."
    ),
    "settings.routes.wizard.loading": "경로를 여는 중…",
    "settings.cycles.wizard.loading": "청구 주기를 여는 중…",
    "settings.routes.wizard.selectedCount.one": "{{count}}건 선택",
    "settings.routes.wizard.selectedCount.other": "{{count}}건을 선택",
    "settings.cycles.wizard.routesSelected.one": "경로 {{count}}개 선택",
    "settings.cycles.wizard.routesSelected.other": "경로 {{count}}개를 선택",
    "settings.cycles.wizard.routesMembers.one": "경로 {{routes}}개 · 대상 {{members}}개",
    "settings.cycles.wizard.routesMembers.other": "경로 {{routes}}개 · {{members}}개 대상",
    "metering.cycles.col.frequency": "주기",
    "metering.cycles.col.startDay": "시작일",
    "metering.cycles.col.daysToComplete": "완료 소요 일수",
    "metering.routes.col.services": "서비스",
    "metering.ops.openDetail": "{{code}} 열기",
}


# ═══════════════════════════════════════════════════════════════════════════
# HANDED OVER BY THE RC-W1 BACKEND LANE — two refusal strings it could not
# write, because a backend lane does not touch frontend files.
#
# ⚠ THESE ARE **OVERWRITES**, NOT ADDITIONS, AND THAT IS WHY THEY ARE A
# SEPARATE TABLE. Everything above lands through `setdefault` so a human
# correction outranks this script; `metering.cycle.frequency_unknown` has to go
# the other way — the sentence in the catalogues is WRONG and the script is the
# correction. A key in both tables would be a bug; `main()` refuses it.
#
#  1. `metering.cycle.days_to_complete_range` is raised by
#     `apps/metering/services.py` and defined in NO catalogue — G18 names it —
#     so an operator who typed 0 saw the raw key. `services.py`'s own comment
#     says why zero is refused rather than clamped: *"A window of ZERO days is
#     not a short window, it is no window at all: the crew would have no day to
#     read on"*, and the sentence says that instead of quoting a range.
#
#  2. `metering.cycle.frequency_unknown` read *"Pick Monthly, Bi-monthly or
#     Quarterly."* — CR-006's three, in a spelling the ruled vocabulary does
#     not contain. The PO ruled EIGHT one-word business names, and the message
#     now lists all eight.
#     ⚠ **AND IT DOES NOT SAY "BIWEEKLY" OR "BI-MONTHLY", DELIBERATELY.**
#     `Fortnightly` exists precisely because *biweekly* also means twice a week
#     in common use (B17 §2). A refusal message that reintroduced the ambiguous
#     word would teach the operator the vocabulary the ruling removed — in the
#     one place they are already confused enough to have been refused.
# ═══════════════════════════════════════════════════════════════════════════

EN_FIX: dict[str, str] = {
    # ⚠ CORRECTED HOURS AFTER IT SHIPPED (hard-won law 1). It said the
    # derivation was "being built" — and RC-W2-T1 landed
    # `apps/metering/period_engine.py` on this same branch the same day, so the
    # sentence became a stale claim about the state of the product. The real gap
    # is narrower and OUTLIVES the engine: the engine mounts no endpoint, so
    # nothing SENDS the windows to this screen. It closes when a route serves
    # them, not when the arithmetic exists.
    #
    # ⚠ AND IT MUST BE HERE RATHER THAN IN `EN`: that table lands through
    # `setdefault` so a human correction always outranks it, which means editing
    # it changes NOTHING for a key that already exists in the catalogues. A
    # correction has to go through the table that overwrites, or it silently
    # does not happen — checked by reading the catalogue back, not by trusting
    # the diff of this file.
    "settings.cycles.detail.windowsAbsentTitle": "The next windows are not shown yet",
    "settings.cycles.detail.windowsAbsentBody": (
        "The dates follow from the start day, the frequency and the length — but "
        "nothing sends them to this screen yet, and nothing is shown here rather "
        "than a date nobody has confirmed."
    ),
    "metering.cycle.days_to_complete_range": (
        "Days to complete has to be at least 1 — a window of no days leaves nobody a "
        "day to read on."
    ),
    "metering.cycle.frequency_unknown": (
        "Pick one of the eight: Daily, Weekly, Fortnightly, Monthly, Bimonthly, "
        "Quarterly, Semiannual or Annual."
    ),
}

FIX: dict[str, dict[str, str]] = {
    "de": {
        "settings.cycles.detail.windowsAbsentTitle": "Die nächsten Fenster werden noch nicht angezeigt",
        "settings.cycles.detail.windowsAbsentBody": (
            "Die Termine ergeben sich aus Starttag, Häufigkeit und Dauer — nur sendet sie noch nichts an diese Ansicht, und hier steht lieber nichts als ein Datum, das niemand bestätigt hat."
        ),
        "metering.cycle.days_to_complete_range": (
            "Die Dauer muss mindestens 1 Tag betragen — ohne Tag hat niemand einen Tag "
            "zum Ablesen."
        ),
        "metering.cycle.frequency_unknown": (
            "Wählen Sie eine der acht: Täglich, Wöchentlich, Zweiwöchentlich, Monatlich, "
            "Zweimonatlich, Vierteljährlich, Halbjährlich oder Jährlich."
        ),
    },
    "es": {
        "settings.cycles.detail.windowsAbsentTitle": "Las próximas ventanas todavía no se muestran",
        "settings.cycles.detail.windowsAbsentBody": (
            "Las fechas se desprenden del día de inicio, la frecuencia y la duración, pero todavía nada las envía a esta pantalla, y aquí no se muestra nada antes que una fecha que nadie ha confirmado."
        ),
        "metering.cycle.days_to_complete_range": (
            "Los días para completar tienen que ser al menos 1: sin días, nadie tiene un "
            "día para leer."
        ),
        "metering.cycle.frequency_unknown": (
            "Elija una de las ocho: Diaria, Semanal, Quincenal, Mensual, Bimestral, "
            "Trimestral, Semestral o Anual."
        ),
    },
    "es-MX": {
        "settings.cycles.detail.windowsAbsentTitle": "Las próximas ventanas todavía no se muestran",
        "settings.cycles.detail.windowsAbsentBody": (
            "Las fechas se desprenden del día de inicio, la frecuencia y la duración, pero todavía nada las envía a esta pantalla, y aquí no se muestra nada antes que una fecha que nadie ha confirmado."
        ),
        "metering.cycle.days_to_complete_range": (
            "Los días para completar deben ser al menos 1: sin días, nadie tiene un día "
            "para tomar la lectura."
        ),
        "metering.cycle.frequency_unknown": (
            "Elige una de las ocho: Diaria, Semanal, Quincenal, Mensual, Bimestral, "
            "Trimestral, Semestral o Anual."
        ),
    },
    "fr-FR": {
        "settings.cycles.detail.windowsAbsentTitle": "Les prochaines fenêtres ne sont pas encore affichées",
        "settings.cycles.detail.windowsAbsentBody": (
            "Les dates découlent du jour de début, de la fréquence et de la durée, mais rien ne les transmet encore à cet écran, et mieux vaut ne rien afficher qu'une date que personne n'a confirmée."
        ),
        "metering.cycle.days_to_complete_range": (
            "La durée doit être d'au moins 1 jour — sans jour, personne n'a de journée "
            "pour relever."
        ),
        "metering.cycle.frequency_unknown": (
            "Choisissez l'une des huit : Quotidien, Hebdomadaire, Bimensuel, Mensuel, "
            "Bimestriel, Trimestriel, Semestriel ou Annuel."
        ),
    },
    "it-IT": {
        "settings.cycles.detail.windowsAbsentTitle": "Le prossime finestre non sono ancora mostrate",
        "settings.cycles.detail.windowsAbsentBody": (
            "Le date discendono dal giorno di inizio, dalla frequenza e dalla durata, ma nulla le invia ancora a questa schermata, e meglio non mostrare nulla che una data non confermata."
        ),
        "metering.cycle.days_to_complete_range": (
            "I giorni per completare devono essere almeno 1: senza giorni nessuno ha una "
            "giornata per leggere."
        ),
        "metering.cycle.frequency_unknown": (
            "Scegli una delle otto: Giornaliera, Settimanale, Quindicinale, Mensile, "
            "Bimestrale, Trimestrale, Semestrale o Annuale."
        ),
    },
    "pt-BR": {
        "settings.cycles.detail.windowsAbsentTitle": "As próximas janelas ainda não são mostradas",
        "settings.cycles.detail.windowsAbsentBody": (
            "As datas decorrem do dia de início, da frequência e da duração, mas nada as envia para esta tela ainda, e aqui não se mostra nada em vez de uma data que ninguém confirmou."
        ),
        "metering.cycle.days_to_complete_range": (
            "Os dias para concluir precisam ser pelo menos 1: sem dias, ninguém tem um "
            "dia para fazer a leitura."
        ),
        "metering.cycle.frequency_unknown": (
            "Escolha uma das oito: Diária, Semanal, Quinzenal, Mensal, Bimestral, "
            "Trimestral, Semestral ou Anual."
        ),
    },
    "id-ID": {
        "settings.cycles.detail.windowsAbsentTitle": "Jendela berikutnya belum ditampilkan",
        "settings.cycles.detail.windowsAbsentBody": (
            "Tanggalnya mengikuti hari mulai, frekuensi, dan lamanya, tetapi belum ada yang mengirimkannya ke layar ini, dan lebih baik tidak menampilkan apa pun daripada tanggal yang belum dipastikan."
        ),
        "metering.cycle.days_to_complete_range": (
            "Hari untuk selesai minimal 1 — tanpa hari, tidak ada yang punya hari untuk "
            "membaca meter."
        ),
        "metering.cycle.frequency_unknown": (
            "Pilih salah satu dari delapan: Harian, Mingguan, Dua mingguan, Bulanan, Dua "
            "bulanan, Triwulanan, Semesteran, atau Tahunan."
        ),
    },
    "hi": {
        "settings.cycles.detail.windowsAbsentTitle": "अगली अवधियाँ अभी नहीं दिखाई जातीं",
        "settings.cycles.detail.windowsAbsentBody": (
            "तिथियाँ आरंभ दिन, आवृत्ति और अवधि से निकलती हैं, पर उन्हें इस स्क्रीन तक भेजने वाला अभी कुछ नहीं है — और किसी अपुष्ट तिथि के बजाय यहाँ कुछ नहीं दिखाया जाता।"
        ),
        "metering.cycle.days_to_complete_range": (
            "पूरा करने के दिन कम से कम 1 होने चाहिए — शून्य दिन में किसी के पास रीडिंग लेने का "
            "दिन ही नहीं बचता।"
        ),
        "metering.cycle.frequency_unknown": (
            "आठ में से कोई एक चुनें: दैनिक, साप्ताहिक, पाक्षिक, मासिक, द्वैमासिक, त्रैमासिक, "
            "अर्धवार्षिक या वार्षिक।"
        ),
    },
    "ja-JP": {
        "settings.cycles.detail.windowsAbsentTitle": "次の期間はまだ表示できません",
        "settings.cycles.detail.windowsAbsentBody": (
            "日付は開始日・頻度・日数から決まりますが、この画面に届ける仕組みがまだありません。誰も確認していない日付を出すより、何も表示しません。"
        ),
        "metering.cycle.days_to_complete_range": (
            "完了までの日数は 1 日以上にしてください。0 日では検針する日がありません。"
        ),
        "metering.cycle.frequency_unknown": (
            "次の 8 つから選んでください：毎日・毎週・隔週・毎月・隔月・四半期ごと・"
            "半年ごと・毎年。"
        ),
    },
    "ko-KR": {
        "settings.cycles.detail.windowsAbsentTitle": "다음 기간은 아직 표시되지 않습니다",
        "settings.cycles.detail.windowsAbsentBody": (
            "날짜는 시작일·주기·일수에서 정해지지만, 이 화면으로 보내주는 것이 아직 없습니다. 아무도 확인하지 않은 날짜를 보이느니 아무것도 보이지 않습니다."
        ),
        "metering.cycle.days_to_complete_range": (
            "완료 소요 일수는 최소 1일이어야 합니다. 0일이면 검침할 날이 없습니다."
        ),
        "metering.cycle.frequency_unknown": (
            "여덟 가지 중에서 고르세요: 매일, 매주, 격주, 매월, 격월, 분기별, 반기별, 매년."
        ),
    },
}


#: Keys this CR ORPHANED, deleted from all eleven catalogues.
#:
#: G18's second assertion is that a catalogue key with no call site is dead
#: weight nothing renders — and it hides the next real drift in the diff. The
#: RC-W3-T1/T2 rebuild dropped four cycle columns (the legacy `Read window`,
#: `Bill day`, `Due day` and the un-prefixed `Cycle` heading, replaced by
#: `Cycle #` and the three ruled schedule fields) and the route table's
#: single-service heading (D10 makes it a SET). Deleting them is the same sweep
#: CR-028 ran for four orphaned `assets.*` keys.
#:
#: ⚠ `metering.cycles.col.window` IS **NOT** IN THIS LIST and must not be: it is
#: a different key on a different screen (the S27 ops tab), and it is live.
ORPHANED: tuple[str, ...] = (
    "settings.cycles.col.code",
    "settings.cycles.col.window",
    "settings.cycles.col.billDay",
    "settings.cycles.col.dueDay",
    "settings.routes.col.service",
)


def main() -> int:
    """⚠ EXISTING KEY ORDER IS PRESERVED AND NEW KEYS ARE APPENDED.

    The catalogues are NOT sorted, so writing them back sorted rewrites every
    line of eleven files six other lanes also touch — a whole-file write
    wearing the costume of an addition, which is the mechanism CLAUDE.md law 11
    was written for. This lane learned it the expensive way: the first run of
    this script sorted them, produced 728 changed lines per catalogue for a
    113-key addition, and had to be undone. `scripts/wave_d_i18n.py` says
    exactly this in its own docstring and is the precedent.
    """
    en_path = ROOT / "en.json"
    en = json.loads(en_path.read_text(encoding="utf-8"))
    # A key in BOTH tables is legitimate for exactly one shape: this CR added
    # it, shipped it, and then corrected it. `EN` holds what shipped (so a fresh
    # run is idempotent) and `EN_FIX` holds the correction, which is applied
    # second and wins. Anything else in both is a mistake, so the two must be
    # declared equal here rather than tolerated silently.
    CORRECTED_AFTER_SHIPPING = {
        "settings.cycles.detail.windowsAbsentTitle",
        "settings.cycles.detail.windowsAbsentBody",
    }
    overlap = sorted(set(EN) & set(EN_FIX) - CORRECTED_AFTER_SHIPPING)
    if overlap:
        raise SystemExit(f"a key cannot be both an addition and a correction: {overlap}")
    for key, value in EN.items():
        en.setdefault(key, value)  # never overwrite: a human correction wins
    en.update(EN_FIX)  # …and these two ARE the correction — see the note above
    for key in ORPHANED:
        en.pop(key, None)
    en_path.write_text(
        json.dumps(en, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    problems: list[str] = []
    for code, table in T.items():
        path = ROOT / f"{code}.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        missing = sorted(set(EN) - set(table))
        if missing:
            problems.append(f"{code}: {len(missing)} untranslated key(s): {missing[:3]}")
        for key, value in table.items():
            if key not in EN:
                problems.append(f"{code}: {key} is not an English key")
            if value == EN.get(key):
                problems.append(f"{code}: {key} is byte-identical to English")
        for key, value in table.items():
            data.setdefault(key, value)
        fixes = FIX.get(code, {})
        missing_fix = sorted(set(EN_FIX) - set(fixes))
        if missing_fix:
            problems.append(f"{code}: {missing_fix} has no corrected translation")
        for key, value in fixes.items():
            if value == EN_FIX.get(key):
                problems.append(f"{code}: {key} is byte-identical to English")
        data.update(fixes)
        for key in ORPHANED:
            data.pop(key, None)
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    print(f"en.json: +{len(EN)} keys, {len(EN_FIX)} corrected")
    for problem in problems:
        print("  ⚠", problem)
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
