"""CR-029 RC-W3c · the strings the WIRED Routes & Cycles screens need.

WHAT THIS WAVE CHANGED, AND WHY THE CATALOGUES MOVE WITH IT
------------------------------------------------------------
RC-W2 landed the period engine and RC-W3b mounted the routes that serve it, so
five sentences the screens had been showing — *"the next windows are not shown
yet"*, *"Read history is not available yet"*, *"the accounts on this route are
not listed yet"*, *"why a meter was left off is not shown yet"*, *"those
accounts are not listed yet"* — became FALSE. They are deleted here rather than
left to rot: hard-won law 1 read backwards is a screen apologising for a feature
that shipped, and G18 counts a key nothing renders as dead weight either way.

⚠ **THE KEY ORDER IS PRESERVED AND NEW KEYS ARE APPENDED.** The locale files are
not sorted; writing them back sorted turns a 45-key addition into 700 changed
lines per file, in a tree six lanes share. `wave_d_i18n.py` states the rule and
this script obeys it: `dict` preserves insertion order, `setdefault` appends,
and nothing re-sorts.

⚠ **THE PLURALS ARE ORDINARY KEYS, NOT i18next SUFFIXES** — `cr029_i18n.py`
argues it in full: `key_one`/`key_other` resolve per LANGUAGE, so the key SET
would differ between catalogues and G15 requires them identical.

⚠ **FIVE KEYS HERE ARE BACKEND REFUSALS THE BACKEND DOES NOT RAISE YET.**
`metering.readWindow.result_unknown` and the four `metering.route.walk_order_*`
sentences exist so a lane that may edit `06-backend/` can point the constants at
them in one line. Until it does they have no call site and G18 counts them as
dead — REPORTED in this lane's hand-off rather than hidden, because the
alternative is what the repo has today: three real refusals wearing another
surface's sentence (*"We couldn't read that change"* for a duplicated stop).

Run: python3 07-frontend/scripts/cr029_w3c_i18n.py
"""

import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1] / "src" / "i18n" / "locales"

# ── The English source ─────────────────────────────────────────────────────

EN: dict[str, str] = {
    # ── SET-07D · the next-windows card (B17 §4) ──────────────────────────
    "settings.cycles.detail.nextWindows": "Next three windows",
    "settings.cycles.detail.col.occurrence": "Occurrence",
    "settings.cycles.detail.col.window": "Window",
    "settings.cycles.detail.col.windowStatus": "Window status",
    "settings.cycles.window.status.next": "Next",
    "settings.cycles.window.status.scheduled": "Scheduled",
    "settings.cycles.detail.nextCycleDate": "Next cycle date",
    "settings.cycles.detail.noWindowsTitle": "No windows are proposed",
    "settings.cycles.detail.noWindowsBody": (
        "A cycle proposes windows once it has a first run and a length. Edit the cycle "
        "and set both."
    ),
    # ── SET-07D · `schedule_gap` — three OPEN questions, said plainly ─────
    #
    # ⚠ NEVER A DATE, NEVER A GUESS, NEVER A CODE. Each sentence names the
    # decision the product is missing and the one thing a clerk can do today.
    # The open-question ids, the rule ids and the engine's module path stay out
    # of the copy (G28) and live in `routesCyclesShared.scheduleGapKey`.
    "settings.cycles.gap.title": "The next reading windows are not proposed",
    "settings.cycles.gap.cycle_month_end_anchor_unruled": (
        "This cycle reads on a day some months do not have. Pick a start day of 28 or "
        "earlier, or type the period on the bill run."
    ),
    "settings.cycles.gap.cycle_first_run_disagrees_with_start_day": (
        "This cycle's first run is not on its start day. Move the first run onto the "
        "start day, or type the period on the bill run."
    ),
    "settings.cycles.gap.cycle_windows_would_overlap": (
        "This cycle takes longer to read than the gap between its readings. Shorten "
        "the days to complete, or read less often."
    ),
    "settings.cycles.gap.unknown": (
        "This cycle's schedule has a case we cannot work out. Type the period on the "
        "bill run instead."
    ),
    # ── SET-07D · the uncovered list (D13 — a fact, never an action) ──────
    "settings.cycles.detail.col.account": "Account",
    "settings.cycles.detail.col.customer": "Customer",
    "settings.cycles.detail.col.lacks": "What is missing",
    "settings.cycles.detail.lacks.route": "No route",
    "settings.cycles.detail.uncoveredTruncated": "Showing the first {{count}}. There are more.",
    "settings.cycles.detail.allCoveredTitle": "Every account is covered",
    "settings.cycles.detail.allCoveredBody": (
        "Every account reaches a cycle through the route its unit is on."
    ),
    # ── SET-06D · Read history (B17 §4) ───────────────────────────────────
    "settings.routes.detail.readHistory": "Read history",
    "settings.routes.detail.col.readWindow": "Window",
    "settings.routes.detail.col.readOn": "Read on",
    "settings.routes.detail.col.collected": "Collected",
    "settings.routes.detail.col.expected": "Expected",
    "settings.routes.detail.col.result": "Result",
    "settings.routes.detail.readResult.complete": "Complete",
    "settings.routes.detail.readResult.incomplete": "Incomplete",
    "settings.routes.detail.readResult.open": "Still open",
    "settings.routes.detail.noReadHistoryTitle": "This route has not been walked yet",
    "settings.routes.detail.noReadHistoryBody": (
        "A row appears here each time a reading window on this route is closed."
    ),
    # ── SET-06D · Accounts (D12 — status only, no money) ──────────────────
    "settings.routes.detail.accountsLede": (
        "Who a missed read on this route affects. What an account owes lives on the "
        "account, never here."
    ),
    "settings.routes.detail.col.account": "Account",
    "settings.routes.detail.col.customer": "Customer",
    "settings.routes.detail.accountsSummary": (
        "{{accounts}} accounts across {{units}} units · {{without}} units with no account"
    ),
    "settings.routes.detail.noAccountsTitle": "No accounts on this route",
    "settings.routes.detail.noAccountsBody": (
        "None of the units on this route has an account yet."
    ),
    # ── SET-06D · an exclusion explains itself in place (B17 §6) ──────────
    "settings.routes.detail.col.why": "Why",
    "settings.routes.detail.noReason": "No reason kept",
    # ── S31 step 1 · the due-days override (CR-029 D9) ────────────────────
    "billing.run.field.dueDays": "Due days",
    "billing.run.field.dueDaysHelp": (
        "Days after the bill date that payment is due. Zero means due on the bill date."
    ),
    "billing.run.field.dueDaysCycle": "{{days}} from the cycle",
    "billing.run.field.dueDateOverridden": (
        "{{days}} days, for this run only. The cycle keeps its own default."
    ),
    # ⚠ RAISED BY THE SERVER **AND** RENDERED BY THE WIZARD'S OWN CHECK, so one
    # sentence covers both and they cannot drift into two wordings.
    "billing.run.due_days_invalid": "Enter a whole number of days, zero or more.",
    # ── Backend refusals that currently borrow another surface's sentence ──
    #
    # Each replaces a REUSE the owning lane reported rather than hid. Named in
    # this lane's hand-off with the constant that must point at it.
    "metering.readWindow.result_unknown": "Pick one of: {{allowed}}.",
    "metering.route.walk_order_incomplete": (
        "The walking order leaves out some of this route's premises. Every stop has to "
        "be in it."
    ),
    "metering.route.walk_order_duplicate_premises": (
        "A premises appears twice in the walking order. Each stop appears once."
    ),
    "metering.route.walk_order_duplicate_position": (
        "Two stops claim the same position. Give each stop its own number."
    ),
    "metering.route.walk_order_not_a_member": (
        "Some of those stops are not on this route. Only its own premises can be "
        "ordered."
    ),
    # ── The dashboard's cycle window, withdrawn by D8① ────────────────────
    # ── SET-07D · the Runs tab (B17 §4) — SERVED by RC-W4b ────────────────
    #
    # ⚠ **NO `Run #` COLUMN AND NO `Status` COLUMN, AND BOTH ARE SERVED.**
    # `run_no` is always null (no number column, no series, and D5 never ruled a
    # grammar for runs), and `status` is a stored column nothing in the product
    # ever advances — every historical run reads "draft". So the row is
    # identified by its PERIOD and its outcome is composed from `issued_at` and
    # `held`, the two fields with evidence behind them.
    "settings.cycles.detail.col.period": "Period",
    "settings.cycles.detail.col.issued": "Issued",
    "settings.cycles.detail.col.run": "Run",
    "settings.cycles.detail.col.runStatus": "Status",
    "settings.cycles.detail.runBills": "{{issued}} of {{accounts}}",
    "settings.cycles.detail.runStatus.issued": "Issued",
    "settings.cycles.detail.runStatus.issuedHeld": "Issued · {{held}} held",
    "settings.cycles.detail.runStatus.notIssued": "Not issued yet",
    "settings.cycles.detail.col.accounts": "Accounts",
    "settings.cycles.detail.notIssued": "Not issued",
    "settings.cycles.detail.noRunsTitle": "This cycle has not been billed yet",
    "settings.cycles.detail.noRunsBody": "A row appears here for each bill run started on this cycle.",
    "finance.gap.billing_cycle_window_is_not_offered": (
        "Reporting over a whole billing cycle is not offered. Every window you can pick "
        "states the exact dates it covers."
    ),
}

#: Keys this wave ORPHANED — deleted from all eleven catalogues.
#:
#: The first thirteen are stated absences whose absence ENDED: RC-W2 and RC-W3b
#: served every one of them, so the sentence became a false claim on a shipped
#: feature. The `orderRouteAbsent` line is the same shape read the other way —
#: it told a user the walking order *"can't be saved yet"* on a route that saves
#: it. The last two are D8①'s: the dashboard no longer offers a
#: last-completed-cycle window, so its option label and its named variant have
#: no caller (PO 2026-08-23, *"what makes a cycle completed - dont build it"*).
ORPHANED: tuple[str, ...] = (
    "settings.cycles.detail.windowsAbsentTitle",
    "settings.cycles.detail.windowsAbsentBody",
    "settings.cycles.detail.monthEndUnruledTitle",
    "settings.cycles.detail.monthEndUnruledBody",
    "settings.cycles.detail.uncoveredListAbsentTitle",
    "settings.cycles.detail.uncoveredListAbsentBody",
    "settings.routes.detail.readHistoryAbsentTitle",
    "settings.routes.detail.readHistoryAbsentBody",
    "settings.routes.detail.accountsAbsentTitle",
    "settings.routes.detail.accountsAbsentBody",
    "settings.routes.detail.exclusionReasonAbsentTitle",
    "settings.routes.detail.exclusionReasonAbsentBody",
    "settings.routes.detail.orderRouteAbsent",
    "dashboard.period.option.last_cycle",
    "dashboard.period.optionNamed.last_cycle",
    # RC-W4b served `GET /billing/runs` while this wave was shipping, so the
    # Runs tab's "Past runs are not listed yet" became false on the same branch.
    "settings.cycles.detail.runsAbsentTitle",
    "settings.cycles.detail.runsAbsentBody",
)

# ── The ten translations ───────────────────────────────────────────────────

T: dict[str, dict[str, str]] = {}

T["de"] = {
    "settings.cycles.detail.nextWindows": "Nächste drei Zeitfenster",
    "settings.cycles.detail.col.occurrence": "Durchlauf",
    "settings.cycles.detail.col.window": "Zeitfenster",
    "settings.cycles.detail.col.windowStatus": "Fensterstatus",
    "settings.cycles.window.status.next": "Als Nächstes",
    "settings.cycles.window.status.scheduled": "Geplant",
    "settings.cycles.detail.nextCycleDate": "Nächstes Zyklusdatum",
    "settings.cycles.detail.noWindowsTitle": "Es werden keine Zeitfenster vorgeschlagen",
    "settings.cycles.detail.noWindowsBody": (
        "Ein Zyklus schlägt Zeitfenster vor, sobald er einen ersten Lauf und eine Dauer "
        "hat. Bearbeiten Sie den Zyklus und legen Sie beides fest."
    ),
    "settings.cycles.gap.title": "Die nächsten Ablesefenster werden nicht vorgeschlagen",
    "settings.cycles.gap.cycle_month_end_anchor_unruled": (
        "Dieser Zyklus liest an einem Tag ab, den manche Monate nicht haben. Wählen Sie "
        "einen Starttag bis 28 oder geben Sie den Zeitraum beim Abrechnungslauf ein."
    ),
    "settings.cycles.gap.cycle_first_run_disagrees_with_start_day": (
        "Der erste Lauf dieses Zyklus liegt nicht auf seinem Starttag. Verlegen Sie den "
        "ersten Lauf auf den Starttag oder geben Sie den Zeitraum beim Abrechnungslauf ein."
    ),
    "settings.cycles.gap.cycle_windows_would_overlap": (
        "Dieser Zyklus braucht länger zum Ablesen als der Abstand zwischen den Ablesungen. "
        "Verkürzen Sie die Dauer oder lesen Sie seltener ab."
    ),
    "settings.cycles.gap.unknown": (
        "Der Zeitplan dieses Zyklus enthält einen Fall, den wir nicht auflösen können. "
        "Geben Sie den Zeitraum stattdessen beim Abrechnungslauf ein."
    ),
    "settings.cycles.detail.col.account": "Konto",
    "settings.cycles.detail.col.customer": "Kunde",
    "settings.cycles.detail.col.lacks": "Was fehlt",
    "settings.cycles.detail.lacks.route": "Keine Route",
    "settings.cycles.detail.uncoveredTruncated": (
        "Es werden die ersten {{count}} gezeigt. Es gibt weitere."
    ),
    "settings.cycles.detail.allCoveredTitle": "Jedes Konto ist abgedeckt",
    "settings.cycles.detail.allCoveredBody": (
        "Jedes Konto erreicht einen Zyklus über die Route seiner Einheit."
    ),
    "settings.routes.detail.readHistory": "Ableseverlauf",
    "settings.routes.detail.col.readWindow": "Zeitfenster",
    "settings.routes.detail.col.readOn": "Abgelesen am",
    "settings.routes.detail.col.collected": "Erfasst",
    "settings.routes.detail.col.expected": "Erwartet",
    "settings.routes.detail.col.result": "Ergebnis",
    "settings.routes.detail.readResult.complete": "Vollständig",
    "settings.routes.detail.readResult.incomplete": "Unvollständig",
    "settings.routes.detail.readResult.open": "Noch offen",
    "settings.routes.detail.noReadHistoryTitle": "Diese Route wurde noch nicht abgelaufen",
    "settings.routes.detail.noReadHistoryBody": (
        "Hier erscheint eine Zeile, sobald ein Ablesefenster dieser Route geschlossen wird."
    ),
    "settings.routes.detail.accountsLede": (
        "Wen eine ausgefallene Ablesung auf dieser Route trifft. Was ein Konto schuldet, "
        "steht beim Konto, nie hier."
    ),
    "settings.routes.detail.col.account": "Konto",
    "settings.routes.detail.col.customer": "Kunde",
    "settings.routes.detail.accountsSummary": (
        "{{accounts}} Konten auf {{units}} Einheiten · {{without}} Einheiten ohne Konto"
    ),
    "settings.routes.detail.noAccountsTitle": "Keine Konten auf dieser Route",
    "settings.routes.detail.noAccountsBody": (
        "Noch keine der Einheiten auf dieser Route hat ein Konto."
    ),
    "settings.routes.detail.col.why": "Grund",
    "settings.routes.detail.noReason": "Kein Grund hinterlegt",
    "billing.run.field.dueDays": "Zahlungsfrist in Tagen",
    "billing.run.field.dueDaysHelp": (
        "Tage nach dem Rechnungsdatum bis zur Fälligkeit. Null bedeutet fällig am "
        "Rechnungsdatum."
    ),
    "billing.run.field.dueDaysCycle": "{{days}} aus dem Zyklus",
    "billing.run.field.dueDateOverridden": (
        "{{days}} Tage, nur für diesen Lauf. Der Zyklus behält seinen eigenen Standardwert."
    ),
    "billing.run.due_days_invalid": "Geben Sie eine ganze Anzahl Tage ein, null oder mehr.",
    "metering.readWindow.result_unknown": "Wählen Sie eines von: {{allowed}}.",
    "metering.route.walk_order_incomplete": (
        "Die Ablaufreihenfolge lässt Objekte dieser Route aus. Jeder Halt muss darin stehen."
    ),
    "metering.route.walk_order_duplicate_premises": (
        "Ein Objekt kommt zweimal in der Ablaufreihenfolge vor. Jeder Halt kommt einmal vor."
    ),
    "metering.route.walk_order_duplicate_position": (
        "Zwei Halte beanspruchen dieselbe Position. Geben Sie jedem Halt eine eigene Nummer."
    ),
    "metering.route.walk_order_not_a_member": (
        "Einige dieser Halte liegen nicht auf dieser Route. Nur ihre eigenen Objekte "
        "lassen sich ordnen."
    ),
    "finance.gap.billing_cycle_window_is_not_offered": (
        "Eine Auswertung über einen ganzen Abrechnungszyklus wird nicht angeboten. Jedes "
        "wählbare Zeitfenster nennt die genauen Tage, die es abdeckt."
    ),
    "settings.cycles.detail.col.period": "Zeitraum",
    "settings.cycles.detail.col.issued": "Versendet",
    "settings.cycles.detail.col.run": "Lauf",
    "settings.cycles.detail.col.runStatus": "Stand",
    "settings.cycles.detail.runBills": "{{issued}} von {{accounts}}",
    "settings.cycles.detail.runStatus.issued": "Versendet",
    "settings.cycles.detail.runStatus.issuedHeld": "Versendet · {{held}} zurückgehalten",
    "settings.cycles.detail.runStatus.notIssued": "Noch nicht versendet",
    "settings.cycles.detail.col.accounts": "Konten",
    "settings.cycles.detail.notIssued": "Nicht versendet",
    "settings.cycles.detail.noRunsTitle": "Dieser Zyklus wurde noch nicht abgerechnet",
    "settings.cycles.detail.noRunsBody": "Für jeden Abrechnungslauf dieses Zyklus erscheint hier eine Zeile.",
}

T["es"] = {
    "settings.cycles.detail.nextWindows": "Próximas tres ventanas",
    "settings.cycles.detail.col.occurrence": "Repetición",
    "settings.cycles.detail.col.window": "Ventana",
    "settings.cycles.detail.col.windowStatus": "Estado de la ventana",
    "settings.cycles.window.status.next": "Siguiente",
    "settings.cycles.window.status.scheduled": "Programada",
    "settings.cycles.detail.nextCycleDate": "Próxima fecha del ciclo",
    "settings.cycles.detail.noWindowsTitle": "No se proponen ventanas",
    "settings.cycles.detail.noWindowsBody": (
        "Un ciclo propone ventanas cuando tiene una primera ejecución y una duración. "
        "Edite el ciclo y defina ambas."
    ),
    "settings.cycles.gap.title": "No se proponen las próximas ventanas de lectura",
    "settings.cycles.gap.cycle_month_end_anchor_unruled": (
        "Este ciclo lee en un día que algunos meses no tienen. Elija un día de inicio "
        "hasta el 28, o escriba el periodo en la facturación."
    ),
    "settings.cycles.gap.cycle_first_run_disagrees_with_start_day": (
        "La primera ejecución de este ciclo no cae en su día de inicio. Mueva la primera "
        "ejecución al día de inicio, o escriba el periodo en la facturación."
    ),
    "settings.cycles.gap.cycle_windows_would_overlap": (
        "Este ciclo tarda más en leerse que el intervalo entre sus lecturas. Reduzca los "
        "días para completar, o lea con menos frecuencia."
    ),
    "settings.cycles.gap.unknown": (
        "El calendario de este ciclo tiene un caso que no podemos resolver. Escriba el "
        "periodo en la facturación."
    ),
    "settings.cycles.detail.col.account": "Cuenta",
    "settings.cycles.detail.col.customer": "Cliente",
    "settings.cycles.detail.col.lacks": "Qué falta",
    "settings.cycles.detail.lacks.route": "Sin ruta",
    "settings.cycles.detail.uncoveredTruncated": (
        "Se muestran las primeras {{count}}. Hay más."
    ),
    "settings.cycles.detail.allCoveredTitle": "Todas las cuentas están cubiertas",
    "settings.cycles.detail.allCoveredBody": (
        "Cada cuenta llega a un ciclo por la ruta de su unidad."
    ),
    "settings.routes.detail.readHistory": "Historial de lecturas",
    "settings.routes.detail.col.readWindow": "Ventana",
    "settings.routes.detail.col.readOn": "Leído el",
    "settings.routes.detail.col.collected": "Recogidas",
    "settings.routes.detail.col.expected": "Previstas",
    "settings.routes.detail.col.result": "Resultado",
    "settings.routes.detail.readResult.complete": "Completa",
    "settings.routes.detail.readResult.incomplete": "Incompleta",
    "settings.routes.detail.readResult.open": "Aún abierta",
    "settings.routes.detail.noReadHistoryTitle": "Esta ruta aún no se ha recorrido",
    "settings.routes.detail.noReadHistoryBody": (
        "Aquí aparece una fila cada vez que se cierra una ventana de lectura de esta ruta."
    ),
    "settings.routes.detail.accountsLede": (
        "A quién afecta una lectura perdida en esta ruta. Lo que debe una cuenta está en "
        "la cuenta, nunca aquí."
    ),
    "settings.routes.detail.col.account": "Cuenta",
    "settings.routes.detail.col.customer": "Cliente",
    "settings.routes.detail.accountsSummary": (
        "{{accounts}} cuentas en {{units}} unidades · {{without}} unidades sin cuenta"
    ),
    "settings.routes.detail.noAccountsTitle": "Sin cuentas en esta ruta",
    "settings.routes.detail.noAccountsBody": (
        "Ninguna de las unidades de esta ruta tiene cuenta todavía."
    ),
    "settings.routes.detail.col.why": "Motivo",
    "settings.routes.detail.noReason": "Sin motivo registrado",
    "billing.run.field.dueDays": "Días de vencimiento",
    "billing.run.field.dueDaysHelp": (
        "Días después de la fecha de factura en que vence el pago. Cero significa que "
        "vence ese mismo día."
    ),
    "billing.run.field.dueDaysCycle": "{{days}} del ciclo",
    "billing.run.field.dueDateOverridden": (
        "{{days}} días, solo para esta ejecución. El ciclo conserva su propio valor."
    ),
    "billing.run.due_days_invalid": "Escriba un número entero de días, cero o más.",
    "metering.readWindow.result_unknown": "Elija uno de: {{allowed}}.",
    "metering.route.walk_order_incomplete": (
        "El orden de recorrido deja fuera predios de esta ruta. Cada parada debe estar en él."
    ),
    "metering.route.walk_order_duplicate_premises": (
        "Un predio aparece dos veces en el orden de recorrido. Cada parada aparece una vez."
    ),
    "metering.route.walk_order_duplicate_position": (
        "Dos paradas ocupan la misma posición. Dé a cada parada su propio número."
    ),
    "metering.route.walk_order_not_a_member": (
        "Algunas de esas paradas no están en esta ruta. Solo se pueden ordenar sus propios "
        "predios."
    ),
    "finance.gap.billing_cycle_window_is_not_offered": (
        "No se ofrece informar sobre un ciclo de facturación completo. Cada ventana que "
        "puede elegir indica las fechas exactas que cubre."
    ),
    "settings.cycles.detail.col.period": "Periodo",
    "settings.cycles.detail.col.issued": "Emitidas",
    "settings.cycles.detail.col.run": "Facturación",
    "settings.cycles.detail.col.runStatus": "Estado",
    "settings.cycles.detail.runBills": "{{issued}} de {{accounts}}",
    "settings.cycles.detail.runStatus.issued": "Emitida",
    "settings.cycles.detail.runStatus.issuedHeld": "Emitida · {{held}} retenidas",
    "settings.cycles.detail.runStatus.notIssued": "Aún sin emitir",
    "settings.cycles.detail.col.accounts": "Cuentas",
    "settings.cycles.detail.notIssued": "Sin emitir",
    "settings.cycles.detail.noRunsTitle": "Este ciclo aún no se ha facturado",
    "settings.cycles.detail.noRunsBody": "Aquí aparece una fila por cada facturación iniciada en este ciclo.",
}

T["es-MX"] = dict(T["es"])
T["es-MX"].update(
    {
        "settings.routes.detail.col.why": "Razón",
        "settings.routes.detail.noReason": "Sin razón registrada",
        "settings.cycles.detail.col.lacks": "Qué hace falta",
        "metering.route.walk_order_incomplete": (
            "El orden de recorrido deja fuera predios de esta ruta. Cada parada tiene que "
            "estar en él."
        ),
        "settings.cycles.detail.noRunsBody": (
            "Aquí aparece un renglón por cada facturación iniciada en este ciclo."
        ),
        "settings.cycles.detail.runStatus.notIssued": "Todavía sin emitir",
    }
)

T["fr-FR"] = {
    "settings.cycles.detail.nextWindows": "Trois prochaines fenêtres",
    # ⚠ NOT "Occurrence": French spells it exactly as English does, and G15
    # fails a value byte-identical to en.json in a translated catalogue —
    # correctly, because that is what an untranslated paste-in looks like.
    # Widening the allowlist instead would be a loosening of a ratified gate.
    "settings.cycles.detail.col.occurrence": "Numéro",
    "settings.cycles.detail.col.window": "Fenêtre",
    "settings.cycles.detail.col.windowStatus": "État de la fenêtre",
    "settings.cycles.window.status.next": "Prochaine",
    "settings.cycles.window.status.scheduled": "Planifiée",
    "settings.cycles.detail.nextCycleDate": "Prochaine date du cycle",
    "settings.cycles.detail.noWindowsTitle": "Aucune fenêtre n'est proposée",
    "settings.cycles.detail.noWindowsBody": (
        "Un cycle propose des fenêtres dès qu'il a une première exécution et une durée. "
        "Modifiez le cycle et renseignez les deux."
    ),
    "settings.cycles.gap.title": "Les prochaines fenêtres de relève ne sont pas proposées",
    "settings.cycles.gap.cycle_month_end_anchor_unruled": (
        "Ce cycle relève un jour que certains mois n'ont pas. Choisissez un jour de début "
        "au plus tard le 28, ou saisissez la période sur la facturation."
    ),
    "settings.cycles.gap.cycle_first_run_disagrees_with_start_day": (
        "La première exécution de ce cycle ne tombe pas sur son jour de début. Déplacez-la "
        "sur le jour de début, ou saisissez la période sur la facturation."
    ),
    "settings.cycles.gap.cycle_windows_would_overlap": (
        "Ce cycle met plus de temps à être relevé que l'intervalle entre ses relèves. "
        "Réduisez les jours nécessaires, ou relevez moins souvent."
    ),
    "settings.cycles.gap.unknown": (
        "Le calendrier de ce cycle présente un cas que nous ne savons pas trancher. "
        "Saisissez plutôt la période sur la facturation."
    ),
    "settings.cycles.detail.col.account": "Compte",
    "settings.cycles.detail.col.customer": "Client",
    "settings.cycles.detail.col.lacks": "Ce qui manque",
    "settings.cycles.detail.lacks.route": "Aucune tournée",
    "settings.cycles.detail.uncoveredTruncated": (
        "Les {{count}} premiers sont affichés. Il y en a d'autres."
    ),
    "settings.cycles.detail.allCoveredTitle": "Tous les comptes sont couverts",
    "settings.cycles.detail.allCoveredBody": (
        "Chaque compte atteint un cycle par la tournée de son local."
    ),
    "settings.routes.detail.readHistory": "Historique des relèves",
    "settings.routes.detail.col.readWindow": "Fenêtre",
    "settings.routes.detail.col.readOn": "Relevé le",
    "settings.routes.detail.col.collected": "Collectés",
    "settings.routes.detail.col.expected": "Attendus",
    "settings.routes.detail.col.result": "Résultat",
    "settings.routes.detail.readResult.complete": "Complète",
    "settings.routes.detail.readResult.incomplete": "Incomplète",
    "settings.routes.detail.readResult.open": "Encore ouverte",
    "settings.routes.detail.noReadHistoryTitle": "Cette tournée n'a pas encore été parcourue",
    "settings.routes.detail.noReadHistoryBody": (
        "Une ligne apparaît ici chaque fois qu'une fenêtre de relève de cette tournée est "
        "clôturée."
    ),
    "settings.routes.detail.accountsLede": (
        "Qui est touché par une relève manquée sur cette tournée. Ce qu'un compte doit "
        "figure sur le compte, jamais ici."
    ),
    "settings.routes.detail.col.account": "Compte",
    "settings.routes.detail.col.customer": "Client",
    "settings.routes.detail.accountsSummary": (
        "{{accounts}} comptes sur {{units}} locaux · {{without}} locaux sans compte"
    ),
    "settings.routes.detail.noAccountsTitle": "Aucun compte sur cette tournée",
    "settings.routes.detail.noAccountsBody": (
        "Aucun des locaux de cette tournée n'a encore de compte."
    ),
    "settings.routes.detail.col.why": "Motif",
    "settings.routes.detail.noReason": "Aucun motif conservé",
    "billing.run.field.dueDays": "Jours avant échéance",
    "billing.run.field.dueDaysHelp": (
        "Jours après la date de facture avant l'échéance. Zéro signifie exigible le jour "
        "même."
    ),
    "billing.run.field.dueDaysCycle": "{{days}} d'après le cycle",
    "billing.run.field.dueDateOverridden": (
        "{{days}} jours, pour cette exécution seulement. Le cycle garde sa propre valeur."
    ),
    "billing.run.due_days_invalid": "Saisissez un nombre entier de jours, zéro ou plus.",
    "metering.readWindow.result_unknown": "Choisissez parmi : {{allowed}}.",
    "metering.route.walk_order_incomplete": (
        "L'ordre de parcours omet des locaux de cette tournée. Chaque arrêt doit y figurer."
    ),
    "metering.route.walk_order_duplicate_premises": (
        "Un local figure deux fois dans l'ordre de parcours. Chaque arrêt figure une fois."
    ),
    "metering.route.walk_order_duplicate_position": (
        "Deux arrêts revendiquent la même position. Donnez à chacun son propre numéro."
    ),
    "metering.route.walk_order_not_a_member": (
        "Certains de ces arrêts ne sont pas sur cette tournée. Seuls ses propres locaux "
        "peuvent être ordonnés."
    ),
    "finance.gap.billing_cycle_window_is_not_offered": (
        "Le suivi sur un cycle de facturation entier n'est pas proposé. Chaque fenêtre "
        "proposée indique les dates exactes qu'elle couvre."
    ),
    "settings.cycles.detail.col.period": "Période",
    "settings.cycles.detail.col.issued": "Émises",
    "settings.cycles.detail.col.run": "Facturation",
    "settings.cycles.detail.col.runStatus": "État",
    "settings.cycles.detail.runBills": "{{issued}} sur {{accounts}}",
    "settings.cycles.detail.runStatus.issued": "Émise",
    "settings.cycles.detail.runStatus.issuedHeld": "Émise · {{held}} retenues",
    "settings.cycles.detail.runStatus.notIssued": "Pas encore émise",
    "settings.cycles.detail.col.accounts": "Comptes",
    "settings.cycles.detail.notIssued": "Non émise",
    "settings.cycles.detail.noRunsTitle": "Ce cycle n'a pas encore été facturé",
    "settings.cycles.detail.noRunsBody": "Une ligne apparaît ici pour chaque facturation lancée sur ce cycle.",
}

T["hi"] = {
    "settings.cycles.detail.nextWindows": "अगली तीन अवधियाँ",
    "settings.cycles.detail.col.occurrence": "आवृत्ति",
    "settings.cycles.detail.col.window": "अवधि",
    "settings.cycles.detail.col.windowStatus": "अवधि की स्थिति",
    "settings.cycles.window.status.next": "अगली",
    "settings.cycles.window.status.scheduled": "निर्धारित",
    "settings.cycles.detail.nextCycleDate": "अगली चक्र तिथि",
    "settings.cycles.detail.noWindowsTitle": "कोई अवधि प्रस्तावित नहीं है",
    "settings.cycles.detail.noWindowsBody": (
        "चक्र तभी अवधियाँ प्रस्तावित करता है जब उसकी पहली रन और अवधि की लंबाई तय हो। "
        "चक्र संपादित करें और दोनों तय करें।"
    ),
    "settings.cycles.gap.title": "अगली रीडिंग अवधियाँ प्रस्तावित नहीं हैं",
    "settings.cycles.gap.cycle_month_end_anchor_unruled": (
        "यह चक्र ऐसे दिन पढ़ता है जो कुछ महीनों में होता ही नहीं। प्रारंभ दिन 28 या उससे "
        "पहले चुनें, या बिल रन पर अवधि लिखें।"
    ),
    "settings.cycles.gap.cycle_first_run_disagrees_with_start_day": (
        "इस चक्र की पहली रन उसके प्रारंभ दिन पर नहीं है। पहली रन को प्रारंभ दिन पर लाएँ, "
        "या बिल रन पर अवधि लिखें।"
    ),
    "settings.cycles.gap.cycle_windows_would_overlap": (
        "इस चक्र को पढ़ने में दो रीडिंग के बीच के अंतर से अधिक समय लगता है। पूरा करने के "
        "दिन घटाएँ, या कम बार पढ़ें।"
    ),
    "settings.cycles.gap.unknown": (
        "इस चक्र के कार्यक्रम में ऐसी स्थिति है जिसे हम तय नहीं कर सकते। इसके बजाय बिल रन "
        "पर अवधि लिखें।"
    ),
    "settings.cycles.detail.col.account": "खाता",
    "settings.cycles.detail.col.customer": "ग्राहक",
    "settings.cycles.detail.col.lacks": "क्या नहीं है",
    "settings.cycles.detail.lacks.route": "कोई मार्ग नहीं",
    "settings.cycles.detail.uncoveredTruncated": (
        "पहले {{count}} दिखाए जा रहे हैं। और भी हैं।"
    ),
    "settings.cycles.detail.allCoveredTitle": "हर खाता कवर है",
    "settings.cycles.detail.allCoveredBody": (
        "हर खाता अपनी इकाई के मार्ग के ज़रिए किसी चक्र तक पहुँचता है।"
    ),
    "settings.routes.detail.readHistory": "रीडिंग इतिहास",
    "settings.routes.detail.col.readWindow": "अवधि",
    "settings.routes.detail.col.readOn": "पढ़ा गया",
    "settings.routes.detail.col.collected": "एकत्र",
    "settings.routes.detail.col.expected": "अपेक्षित",
    "settings.routes.detail.col.result": "परिणाम",
    "settings.routes.detail.readResult.complete": "पूर्ण",
    "settings.routes.detail.readResult.incomplete": "अपूर्ण",
    "settings.routes.detail.readResult.open": "अब भी खुली",
    "settings.routes.detail.noReadHistoryTitle": "इस मार्ग पर अभी तक कोई दौरा नहीं हुआ",
    "settings.routes.detail.noReadHistoryBody": (
        "जब भी इस मार्ग की कोई रीडिंग अवधि बंद होती है, यहाँ एक पंक्ति दिखती है।"
    ),
    "settings.routes.detail.accountsLede": (
        "इस मार्ग पर छूटी रीडिंग किन पर असर डालती है। खाते पर कितना बकाया है यह खाते पर "
        "रहता है, यहाँ कभी नहीं।"
    ),
    "settings.routes.detail.col.account": "खाता",
    "settings.routes.detail.col.customer": "ग्राहक",
    "settings.routes.detail.accountsSummary": (
        "{{units}} इकाइयों पर {{accounts}} खाते · {{without}} इकाइयाँ बिना खाते के"
    ),
    "settings.routes.detail.noAccountsTitle": "इस मार्ग पर कोई खाता नहीं",
    "settings.routes.detail.noAccountsBody": (
        "इस मार्ग की किसी भी इकाई का अभी तक कोई खाता नहीं है।"
    ),
    "settings.routes.detail.col.why": "कारण",
    "settings.routes.detail.noReason": "कोई कारण दर्ज नहीं",
    "billing.run.field.dueDays": "देय दिन",
    "billing.run.field.dueDaysHelp": (
        "बिल तिथि के बाद कितने दिनों में भुगतान देय है। शून्य का अर्थ है बिल तिथि को ही देय।"
    ),
    "billing.run.field.dueDaysCycle": "चक्र से {{days}}",
    "billing.run.field.dueDateOverridden": (
        "{{days}} दिन, केवल इस रन के लिए। चक्र का अपना मान वैसा ही रहता है।"
    ),
    "billing.run.due_days_invalid": "दिनों की पूरी संख्या लिखें, शून्य या अधिक।",
    "metering.readWindow.result_unknown": "इनमें से एक चुनें: {{allowed}}।",
    "metering.route.walk_order_incomplete": (
        "दौरे के क्रम में इस मार्ग के कुछ परिसर छूट गए हैं। हर पड़ाव उसमें होना चाहिए।"
    ),
    "metering.route.walk_order_duplicate_premises": (
        "दौरे के क्रम में एक परिसर दो बार है। हर पड़ाव एक ही बार आता है।"
    ),
    "metering.route.walk_order_duplicate_position": (
        "दो पड़ाव एक ही स्थान पर हैं। हर पड़ाव को उसका अपना क्रमांक दें।"
    ),
    "metering.route.walk_order_not_a_member": (
        "उनमें से कुछ पड़ाव इस मार्ग पर नहीं हैं। केवल इसी के परिसर क्रम में रखे जा सकते हैं।"
    ),
    "finance.gap.billing_cycle_window_is_not_offered": (
        "पूरे बिलिंग चक्र पर रिपोर्ट देना उपलब्ध नहीं है। आप जो भी अवधि चुन सकते हैं वह "
        "अपनी सटीक तिथियाँ बताती है।"
    ),
    "settings.cycles.detail.col.period": "अवधि",
    "settings.cycles.detail.col.issued": "जारी",
    "settings.cycles.detail.col.run": "बिल रन",
    "settings.cycles.detail.col.runStatus": "स्थिति",
    "settings.cycles.detail.runBills": "{{accounts}} में से {{issued}}",
    "settings.cycles.detail.runStatus.issued": "जारी",
    "settings.cycles.detail.runStatus.issuedHeld": "जारी · {{held}} रोके गए",
    "settings.cycles.detail.runStatus.notIssued": "अभी जारी नहीं",
    "settings.cycles.detail.col.accounts": "खाते",
    "settings.cycles.detail.notIssued": "जारी नहीं",
    "settings.cycles.detail.noRunsTitle": "इस चक्र का बिल अभी तक नहीं बना",
    "settings.cycles.detail.noRunsBody": "इस चक्र पर शुरू हुए हर बिल रन के लिए यहाँ एक पंक्ति दिखती है।",
}

T["id-ID"] = {
    "settings.cycles.detail.nextWindows": "Tiga jendela berikutnya",
    "settings.cycles.detail.col.occurrence": "Kemunculan",
    "settings.cycles.detail.col.window": "Jendela",
    "settings.cycles.detail.col.windowStatus": "Status jendela",
    "settings.cycles.window.status.next": "Berikutnya",
    "settings.cycles.window.status.scheduled": "Terjadwal",
    "settings.cycles.detail.nextCycleDate": "Tanggal siklus berikutnya",
    "settings.cycles.detail.noWindowsTitle": "Tidak ada jendela yang diusulkan",
    "settings.cycles.detail.noWindowsBody": (
        "Siklus mengusulkan jendela setelah punya proses pertama dan lama pengerjaan. "
        "Ubah siklus dan isi keduanya."
    ),
    "settings.cycles.gap.title": "Jendela pembacaan berikutnya tidak diusulkan",
    "settings.cycles.gap.cycle_month_end_anchor_unruled": (
        "Siklus ini membaca pada tanggal yang tidak dimiliki sebagian bulan. Pilih hari "
        "mulai 28 atau lebih awal, atau ketik periodenya pada proses tagihan."
    ),
    "settings.cycles.gap.cycle_first_run_disagrees_with_start_day": (
        "Proses pertama siklus ini tidak jatuh pada hari mulainya. Pindahkan proses "
        "pertama ke hari mulai, atau ketik periodenya pada proses tagihan."
    ),
    "settings.cycles.gap.cycle_windows_would_overlap": (
        "Siklus ini butuh waktu baca lebih lama daripada jarak antar pembacaannya. "
        "Persingkat lama pengerjaan, atau baca lebih jarang."
    ),
    "settings.cycles.gap.unknown": (
        "Jadwal siklus ini punya kasus yang tidak dapat kami putuskan. Ketik saja "
        "periodenya pada proses tagihan."
    ),
    "settings.cycles.detail.col.account": "Akun",
    "settings.cycles.detail.col.customer": "Pelanggan",
    "settings.cycles.detail.col.lacks": "Yang kurang",
    "settings.cycles.detail.lacks.route": "Tanpa rute",
    "settings.cycles.detail.uncoveredTruncated": (
        "Menampilkan {{count}} pertama. Masih ada lagi."
    ),
    "settings.cycles.detail.allCoveredTitle": "Semua akun tercakup",
    "settings.cycles.detail.allCoveredBody": (
        "Setiap akun mencapai siklus lewat rute unitnya."
    ),
    "settings.routes.detail.readHistory": "Riwayat pembacaan",
    "settings.routes.detail.col.readWindow": "Jendela",
    "settings.routes.detail.col.readOn": "Dibaca pada",
    "settings.routes.detail.col.collected": "Terkumpul",
    "settings.routes.detail.col.expected": "Diharapkan",
    "settings.routes.detail.col.result": "Hasil",
    "settings.routes.detail.readResult.complete": "Lengkap",
    "settings.routes.detail.readResult.incomplete": "Belum lengkap",
    "settings.routes.detail.readResult.open": "Masih terbuka",
    "settings.routes.detail.noReadHistoryTitle": "Rute ini belum pernah dijalani",
    "settings.routes.detail.noReadHistoryBody": (
        "Satu baris muncul di sini setiap kali jendela pembacaan rute ini ditutup."
    ),
    "settings.routes.detail.accountsLede": (
        "Siapa yang terdampak jika pembacaan di rute ini terlewat. Jumlah tagihan sebuah "
        "akun ada di akunnya, tidak pernah di sini."
    ),
    "settings.routes.detail.col.account": "Akun",
    "settings.routes.detail.col.customer": "Pelanggan",
    "settings.routes.detail.accountsSummary": (
        "{{accounts}} akun pada {{units}} unit · {{without}} unit tanpa akun"
    ),
    "settings.routes.detail.noAccountsTitle": "Tidak ada akun di rute ini",
    "settings.routes.detail.noAccountsBody": (
        "Belum ada satu pun unit di rute ini yang punya akun."
    ),
    "settings.routes.detail.col.why": "Alasan",
    "settings.routes.detail.noReason": "Alasan tidak dicatat",
    "billing.run.field.dueDays": "Hari jatuh tempo",
    "billing.run.field.dueDaysHelp": (
        "Jumlah hari setelah tanggal tagihan sampai jatuh tempo. Nol berarti jatuh tempo "
        "pada tanggal tagihan."
    ),
    "billing.run.field.dueDaysCycle": "{{days}} dari siklus",
    "billing.run.field.dueDateOverridden": (
        "{{days}} hari, hanya untuk proses ini. Siklus tetap memakai nilainya sendiri."
    ),
    "billing.run.due_days_invalid": "Masukkan jumlah hari bulat, nol atau lebih.",
    "metering.readWindow.result_unknown": "Pilih salah satu: {{allowed}}.",
    "metering.route.walk_order_incomplete": (
        "Urutan jalan melewatkan sebagian persil rute ini. Setiap perhentian harus ada di "
        "dalamnya."
    ),
    "metering.route.walk_order_duplicate_premises": (
        "Satu persil muncul dua kali dalam urutan jalan. Tiap perhentian muncul sekali."
    ),
    "metering.route.walk_order_duplicate_position": (
        "Dua perhentian menempati posisi yang sama. Beri tiap perhentian nomornya sendiri."
    ),
    "metering.route.walk_order_not_a_member": (
        "Sebagian perhentian itu bukan bagian rute ini. Hanya persilnya sendiri yang bisa "
        "diurutkan."
    ),
    "finance.gap.billing_cycle_window_is_not_offered": (
        "Pelaporan atas satu siklus penagihan penuh tidak disediakan. Setiap jendela yang "
        "dapat dipilih menyebutkan tanggal persis yang dicakupnya."
    ),
    "settings.cycles.detail.col.period": "Periode",
    "settings.cycles.detail.col.issued": "Diterbitkan",
    "settings.cycles.detail.col.run": "Proses tagihan",
    "settings.cycles.detail.col.runStatus": "Status penagihan",
    "settings.cycles.detail.runBills": "{{issued}} dari {{accounts}}",
    "settings.cycles.detail.runStatus.issued": "Diterbitkan",
    "settings.cycles.detail.runStatus.issuedHeld": "Diterbitkan · {{held}} ditahan",
    "settings.cycles.detail.runStatus.notIssued": "Belum diterbitkan",
    "settings.cycles.detail.col.accounts": "Akun",
    "settings.cycles.detail.notIssued": "Belum diterbitkan",
    "settings.cycles.detail.noRunsTitle": "Siklus ini belum pernah ditagihkan",
    "settings.cycles.detail.noRunsBody": "Satu baris muncul di sini untuk tiap proses tagihan pada siklus ini.",
}

T["it-IT"] = {
    "settings.cycles.detail.nextWindows": "Prossime tre finestre",
    "settings.cycles.detail.col.occurrence": "Occorrenza",
    "settings.cycles.detail.col.window": "Finestra",
    "settings.cycles.detail.col.windowStatus": "Stato della finestra",
    "settings.cycles.window.status.next": "Prossima",
    "settings.cycles.window.status.scheduled": "Pianificata",
    "settings.cycles.detail.nextCycleDate": "Prossima data del ciclo",
    "settings.cycles.detail.noWindowsTitle": "Nessuna finestra proposta",
    "settings.cycles.detail.noWindowsBody": (
        "Un ciclo propone finestre quando ha una prima esecuzione e una durata. "
        "Modificate il ciclo e impostate entrambe."
    ),
    "settings.cycles.gap.title": "Le prossime finestre di lettura non sono proposte",
    "settings.cycles.gap.cycle_month_end_anchor_unruled": (
        "Questo ciclo legge in un giorno che alcuni mesi non hanno. Scegliete un giorno "
        "di avvio entro il 28, oppure digitate il periodo sull'elaborazione."
    ),
    "settings.cycles.gap.cycle_first_run_disagrees_with_start_day": (
        "La prima esecuzione di questo ciclo non cade nel suo giorno di avvio. Spostatela "
        "sul giorno di avvio, oppure digitate il periodo sull'elaborazione."
    ),
    "settings.cycles.gap.cycle_windows_would_overlap": (
        "Questo ciclo richiede più tempo dell'intervallo fra le sue letture. Riducete i "
        "giorni necessari, oppure leggete meno spesso."
    ),
    "settings.cycles.gap.unknown": (
        "Il calendario di questo ciclo presenta un caso che non sappiamo risolvere. "
        "Digitate il periodo sull'elaborazione."
    ),
    "settings.cycles.detail.col.account": "Conto",
    "settings.cycles.detail.col.customer": "Cliente",
    "settings.cycles.detail.col.lacks": "Che cosa manca",
    "settings.cycles.detail.lacks.route": "Nessun itinerario",
    "settings.cycles.detail.uncoveredTruncated": (
        "Sono mostrati i primi {{count}}. Ce ne sono altri."
    ),
    "settings.cycles.detail.allCoveredTitle": "Ogni conto è coperto",
    "settings.cycles.detail.allCoveredBody": (
        "Ogni conto raggiunge un ciclo tramite l'itinerario della sua unità."
    ),
    "settings.routes.detail.readHistory": "Storico letture",
    "settings.routes.detail.col.readWindow": "Finestra",
    "settings.routes.detail.col.readOn": "Letto il",
    "settings.routes.detail.col.collected": "Raccolte",
    "settings.routes.detail.col.expected": "Previste",
    "settings.routes.detail.col.result": "Esito",
    "settings.routes.detail.readResult.complete": "Completa",
    "settings.routes.detail.readResult.incomplete": "Incompleta",
    "settings.routes.detail.readResult.open": "Ancora aperta",
    "settings.routes.detail.noReadHistoryTitle": "Questo itinerario non è ancora stato percorso",
    "settings.routes.detail.noReadHistoryBody": (
        "Qui compare una riga ogni volta che una finestra di lettura di questo itinerario "
        "viene chiusa."
    ),
    "settings.routes.detail.accountsLede": (
        "Chi viene colpito da una lettura mancata su questo itinerario. Quanto deve un "
        "conto sta sul conto, mai qui."
    ),
    "settings.routes.detail.col.account": "Conto",
    "settings.routes.detail.col.customer": "Cliente",
    "settings.routes.detail.accountsSummary": (
        "{{accounts}} conti su {{units}} unità · {{without}} unità senza conto"
    ),
    "settings.routes.detail.noAccountsTitle": "Nessun conto su questo itinerario",
    "settings.routes.detail.noAccountsBody": (
        "Nessuna delle unità di questo itinerario ha ancora un conto."
    ),
    "settings.routes.detail.col.why": "Motivo",
    "settings.routes.detail.noReason": "Nessun motivo registrato",
    "billing.run.field.dueDays": "Giorni di scadenza",
    "billing.run.field.dueDaysHelp": (
        "Giorni dopo la data della fattura entro cui pagare. Zero significa scadenza il "
        "giorno stesso."
    ),
    "billing.run.field.dueDaysCycle": "{{days}} dal ciclo",
    "billing.run.field.dueDateOverridden": (
        "{{days}} giorni, solo per questa elaborazione. Il ciclo mantiene il proprio valore."
    ),
    "billing.run.due_days_invalid": "Inserite un numero intero di giorni, zero o più.",
    "metering.readWindow.result_unknown": "Scegliete uno fra: {{allowed}}.",
    "metering.route.walk_order_incomplete": (
        "L'ordine di percorrenza esclude alcuni immobili di questo itinerario. Ogni tappa "
        "deve esserci."
    ),
    "metering.route.walk_order_duplicate_premises": (
        "Un immobile compare due volte nell'ordine di percorrenza. Ogni tappa compare una "
        "volta."
    ),
    "metering.route.walk_order_duplicate_position": (
        "Due tappe occupano la stessa posizione. Date a ogni tappa un numero suo."
    ),
    "metering.route.walk_order_not_a_member": (
        "Alcune di quelle tappe non sono su questo itinerario. Si ordinano solo i suoi "
        "immobili."
    ),
    "finance.gap.billing_cycle_window_is_not_offered": (
        "Non è previsto un rendiconto su un intero ciclo di fatturazione. Ogni finestra "
        "selezionabile indica le date esatte che copre."
    ),
    "settings.cycles.detail.col.period": "Periodo",
    "settings.cycles.detail.col.issued": "Emesse",
    "settings.cycles.detail.col.run": "Elaborazione",
    "settings.cycles.detail.col.runStatus": "Stato",
    "settings.cycles.detail.runBills": "{{issued}} su {{accounts}}",
    "settings.cycles.detail.runStatus.issued": "Emessa",
    "settings.cycles.detail.runStatus.issuedHeld": "Emessa · {{held}} trattenute",
    "settings.cycles.detail.runStatus.notIssued": "Non ancora emessa",
    "settings.cycles.detail.col.accounts": "Conti",
    "settings.cycles.detail.notIssued": "Non emessa",
    "settings.cycles.detail.noRunsTitle": "Questo ciclo non è ancora stato fatturato",
    "settings.cycles.detail.noRunsBody": "Qui compare una riga per ogni elaborazione avviata su questo ciclo.",
}

T["ja-JP"] = {
    "settings.cycles.detail.nextWindows": "次の3つの期間",
    "settings.cycles.detail.col.occurrence": "回次",
    "settings.cycles.detail.col.window": "期間",
    "settings.cycles.detail.col.windowStatus": "期間の状態",
    "settings.cycles.window.status.next": "次回",
    "settings.cycles.window.status.scheduled": "予定",
    "settings.cycles.detail.nextCycleDate": "次のサイクル日",
    "settings.cycles.detail.noWindowsTitle": "提案できる期間がありません",
    "settings.cycles.detail.noWindowsBody": (
        "サイクルは初回実行日と所要日数がそろってから期間を提案します。サイクルを編集して"
        "両方を設定してください。"
    ),
    "settings.cycles.gap.title": "次の検針期間は提案されていません",
    "settings.cycles.gap.cycle_month_end_anchor_unruled": (
        "このサイクルは、月によっては存在しない日に検針します。開始日を28日以前にするか、"
        "請求実行時に期間を入力してください。"
    ),
    "settings.cycles.gap.cycle_first_run_disagrees_with_start_day": (
        "このサイクルの初回実行日が開始日と一致していません。初回実行日を開始日に合わせるか、"
        "請求実行時に期間を入力してください。"
    ),
    "settings.cycles.gap.cycle_windows_would_overlap": (
        "このサイクルは検針の間隔よりも所要日数のほうが長くなっています。所要日数を短くするか、"
        "検針の頻度を下げてください。"
    ),
    "settings.cycles.gap.unknown": (
        "このサイクルの日程には当社では判断できない条件があります。請求実行時に期間を入力"
        "してください。"
    ),
    "settings.cycles.detail.col.account": "アカウント",
    "settings.cycles.detail.col.customer": "お客さま",
    "settings.cycles.detail.col.lacks": "不足しているもの",
    "settings.cycles.detail.lacks.route": "ルートなし",
    "settings.cycles.detail.uncoveredTruncated": "先頭の{{count}}件を表示しています。ほかにもあります。",
    "settings.cycles.detail.allCoveredTitle": "すべてのアカウントが対象です",
    "settings.cycles.detail.allCoveredBody": (
        "各アカウントは、その住戸のルートを通じてサイクルに結び付きます。"
    ),
    "settings.routes.detail.readHistory": "検針履歴",
    "settings.routes.detail.col.readWindow": "期間",
    "settings.routes.detail.col.readOn": "検針日",
    "settings.routes.detail.col.collected": "収集数",
    "settings.routes.detail.col.expected": "予定数",
    "settings.routes.detail.col.result": "結果",
    "settings.routes.detail.readResult.complete": "完了",
    "settings.routes.detail.readResult.incomplete": "未完了",
    "settings.routes.detail.readResult.open": "実施中",
    "settings.routes.detail.noReadHistoryTitle": "このルートはまだ巡回されていません",
    "settings.routes.detail.noReadHistoryBody": (
        "このルートの検針期間が締められるたびに、ここに1行が表示されます。"
    ),
    "settings.routes.detail.accountsLede": (
        "このルートで検針が漏れたときに影響を受ける方の一覧です。請求額はアカウント側にあり、"
        "ここには表示しません。"
    ),
    "settings.routes.detail.col.account": "アカウント",
    "settings.routes.detail.col.customer": "お客さま",
    "settings.routes.detail.accountsSummary": (
        "{{units}}住戸に{{accounts}}アカウント · アカウントのない住戸{{without}}件"
    ),
    "settings.routes.detail.noAccountsTitle": "このルートにアカウントはありません",
    "settings.routes.detail.noAccountsBody": (
        "このルートの住戸には、まだ1件もアカウントがありません。"
    ),
    "settings.routes.detail.col.why": "理由",
    "settings.routes.detail.noReason": "理由の記録なし",
    "billing.run.field.dueDays": "支払期日までの日数",
    "billing.run.field.dueDaysHelp": (
        "請求日から支払期日までの日数です。0は請求日当日が期日という意味になります。"
    ),
    "billing.run.field.dueDaysCycle": "サイクルの{{days}}",
    "billing.run.field.dueDateOverridden": (
        "{{days}}日。この実行のみに適用され、サイクルの既定値はそのままです。"
    ),
    "billing.run.due_days_invalid": "日数を0以上の整数で入力してください。",
    "metering.readWindow.result_unknown": "次のいずれかを選んでください: {{allowed}}。",
    "metering.route.walk_order_incomplete": (
        "巡回順にこのルートの一部の物件が含まれていません。すべての立寄先が必要です。"
    ),
    "metering.route.walk_order_duplicate_premises": (
        "巡回順に同じ物件が2回あります。立寄先は1回ずつです。"
    ),
    "metering.route.walk_order_duplicate_position": (
        "2つの立寄先が同じ位置を指しています。立寄先ごとに番号を分けてください。"
    ),
    "metering.route.walk_order_not_a_member": (
        "その立寄先の一部はこのルートにありません。並べ替えられるのは自ルートの物件だけです。"
    ),
    "finance.gap.billing_cycle_window_is_not_offered": (
        "請求サイクル全体を対象とした集計は提供していません。選べる期間はいずれも、"
        "対象となる日付をそのまま表示します。"
    ),
    "settings.cycles.detail.col.period": "対象期間",
    "settings.cycles.detail.col.issued": "発行日",
    "settings.cycles.detail.col.run": "請求実行",
    "settings.cycles.detail.col.runStatus": "状態",
    "settings.cycles.detail.runBills": "{{accounts}}件中{{issued}}件",
    "settings.cycles.detail.runStatus.issued": "発行済み",
    "settings.cycles.detail.runStatus.issuedHeld": "発行済み · 保留{{held}}件",
    "settings.cycles.detail.runStatus.notIssued": "未発行",
    "settings.cycles.detail.col.accounts": "アカウント数",
    "settings.cycles.detail.notIssued": "未発行",
    "settings.cycles.detail.noRunsTitle": "このサイクルはまだ請求されていません",
    "settings.cycles.detail.noRunsBody": "このサイクルで請求を実行するたびに、ここに1行が表示されます。",
}

T["ko-KR"] = {
    "settings.cycles.detail.nextWindows": "다음 세 기간",
    "settings.cycles.detail.col.occurrence": "회차",
    "settings.cycles.detail.col.window": "기간",
    "settings.cycles.detail.col.windowStatus": "기간 상태",
    "settings.cycles.window.status.next": "다음",
    "settings.cycles.window.status.scheduled": "예정",
    "settings.cycles.detail.nextCycleDate": "다음 주기 날짜",
    "settings.cycles.detail.noWindowsTitle": "제안되는 기간이 없습니다",
    "settings.cycles.detail.noWindowsBody": (
        "주기는 첫 실행일과 소요 일수가 있어야 기간을 제안합니다. 주기를 편집해 두 값을 "
        "모두 설정하십시오."
    ),
    "settings.cycles.gap.title": "다음 검침 기간이 제안되지 않았습니다",
    "settings.cycles.gap.cycle_month_end_anchor_unruled": (
        "이 주기는 일부 달에는 없는 날짜에 검침합니다. 시작일을 28일 이전으로 정하거나, "
        "청구 실행에서 기간을 직접 입력하십시오."
    ),
    "settings.cycles.gap.cycle_first_run_disagrees_with_start_day": (
        "이 주기의 첫 실행일이 시작일과 다릅니다. 첫 실행일을 시작일로 옮기거나, 청구 "
        "실행에서 기간을 직접 입력하십시오."
    ),
    "settings.cycles.gap.cycle_windows_would_overlap": (
        "이 주기는 검침 간격보다 소요 일수가 더 깁니다. 소요 일수를 줄이거나 검침 주기를 "
        "늘리십시오."
    ),
    "settings.cycles.gap.unknown": (
        "이 주기의 일정에는 저희가 판단할 수 없는 경우가 있습니다. 청구 실행에서 기간을 "
        "직접 입력하십시오."
    ),
    "settings.cycles.detail.col.account": "계정",
    "settings.cycles.detail.col.customer": "고객",
    "settings.cycles.detail.col.lacks": "부족한 항목",
    "settings.cycles.detail.lacks.route": "노선 없음",
    "settings.cycles.detail.uncoveredTruncated": "처음 {{count}}건만 표시했습니다. 더 있습니다.",
    "settings.cycles.detail.allCoveredTitle": "모든 계정이 포함되어 있습니다",
    "settings.cycles.detail.allCoveredBody": (
        "각 계정은 세대의 노선을 통해 주기에 연결됩니다."
    ),
    "settings.routes.detail.readHistory": "검침 이력",
    "settings.routes.detail.col.readWindow": "기간",
    "settings.routes.detail.col.readOn": "검침일",
    "settings.routes.detail.col.collected": "수집",
    "settings.routes.detail.col.expected": "예상",
    "settings.routes.detail.col.result": "결과",
    "settings.routes.detail.readResult.complete": "완료",
    "settings.routes.detail.readResult.incomplete": "미완료",
    "settings.routes.detail.readResult.open": "진행 중",
    "settings.routes.detail.noReadHistoryTitle": "이 노선은 아직 순회한 적이 없습니다",
    "settings.routes.detail.noReadHistoryBody": (
        "이 노선의 검침 기간이 마감될 때마다 여기에 한 줄씩 표시됩니다."
    ),
    "settings.routes.detail.accountsLede": (
        "이 노선에서 검침을 놓치면 영향을 받는 고객입니다. 청구 금액은 계정에 있으며 여기에는 "
        "표시하지 않습니다."
    ),
    "settings.routes.detail.col.account": "계정",
    "settings.routes.detail.col.customer": "고객",
    "settings.routes.detail.accountsSummary": (
        "{{units}}개 세대에 계정 {{accounts}}개 · 계정 없는 세대 {{without}}개"
    ),
    "settings.routes.detail.noAccountsTitle": "이 노선에는 계정이 없습니다",
    "settings.routes.detail.noAccountsBody": (
        "이 노선의 세대 중 아직 계정을 가진 곳이 없습니다."
    ),
    "settings.routes.detail.col.why": "사유",
    "settings.routes.detail.noReason": "기록된 사유 없음",
    "billing.run.field.dueDays": "납기 일수",
    "billing.run.field.dueDaysHelp": (
        "청구일로부터 납기까지의 일수입니다. 0은 청구일 당일이 납기라는 뜻입니다."
    ),
    "billing.run.field.dueDaysCycle": "주기의 {{days}}",
    "billing.run.field.dueDateOverridden": (
        "{{days}}일이며 이번 실행에만 적용됩니다. 주기의 기본값은 그대로 유지됩니다."
    ),
    "billing.run.due_days_invalid": "일수를 0 이상의 정수로 입력하십시오.",
    "metering.readWindow.result_unknown": "다음 중 하나를 선택하십시오: {{allowed}}.",
    "metering.route.walk_order_incomplete": (
        "순회 순서에 이 노선의 일부 건물이 빠져 있습니다. 모든 정차지가 포함되어야 합니다."
    ),
    "metering.route.walk_order_duplicate_premises": (
        "순회 순서에 같은 건물이 두 번 있습니다. 정차지는 한 번씩만 넣으십시오."
    ),
    "metering.route.walk_order_duplicate_position": (
        "두 정차지가 같은 순번을 차지하고 있습니다. 정차지마다 번호를 따로 주십시오."
    ),
    "metering.route.walk_order_not_a_member": (
        "그 정차지 가운데 일부는 이 노선에 없습니다. 이 노선의 건물만 정렬할 수 있습니다."
    ),
    "finance.gap.billing_cycle_window_is_not_offered": (
        "청구 주기 전체를 대상으로 한 집계는 제공하지 않습니다. 선택할 수 있는 기간은 모두 "
        "포함하는 날짜를 그대로 표시합니다."
    ),
    "settings.cycles.detail.col.period": "대상 기간",
    "settings.cycles.detail.col.issued": "발행일",
    "settings.cycles.detail.col.run": "청구 실행",
    "settings.cycles.detail.col.runStatus": "상태",
    "settings.cycles.detail.runBills": "{{accounts}}건 중 {{issued}}건",
    "settings.cycles.detail.runStatus.issued": "발행됨",
    "settings.cycles.detail.runStatus.issuedHeld": "발행됨 · {{held}}건 보류",
    "settings.cycles.detail.runStatus.notIssued": "아직 발행되지 않음",
    "settings.cycles.detail.col.accounts": "계정 수",
    "settings.cycles.detail.notIssued": "미발행",
    "settings.cycles.detail.noRunsTitle": "이 주기는 아직 청구된 적이 없습니다",
    "settings.cycles.detail.noRunsBody": "이 주기에서 청구를 실행할 때마다 여기에 한 줄씩 표시됩니다.",
}

T["pt-BR"] = {
    "settings.cycles.detail.nextWindows": "Próximas três janelas",
    "settings.cycles.detail.col.occurrence": "Ocorrência",
    "settings.cycles.detail.col.window": "Janela",
    "settings.cycles.detail.col.windowStatus": "Situação da janela",
    "settings.cycles.window.status.next": "Próxima",
    "settings.cycles.window.status.scheduled": "Agendada",
    "settings.cycles.detail.nextCycleDate": "Próxima data do ciclo",
    "settings.cycles.detail.noWindowsTitle": "Nenhuma janela é proposta",
    "settings.cycles.detail.noWindowsBody": (
        "Um ciclo propõe janelas depois de ter uma primeira execução e uma duração. "
        "Edite o ciclo e defina as duas."
    ),
    "settings.cycles.gap.title": "As próximas janelas de leitura não são propostas",
    "settings.cycles.gap.cycle_month_end_anchor_unruled": (
        "Este ciclo lê num dia que alguns meses não têm. Escolha um dia de início até o "
        "dia 28, ou digite o período na execução de faturamento."
    ),
    "settings.cycles.gap.cycle_first_run_disagrees_with_start_day": (
        "A primeira execução deste ciclo não cai no seu dia de início. Mova a primeira "
        "execução para o dia de início, ou digite o período na execução de faturamento."
    ),
    "settings.cycles.gap.cycle_windows_would_overlap": (
        "Este ciclo leva mais tempo para ser lido do que o intervalo entre suas leituras. "
        "Reduza os dias para concluir, ou leia com menos frequência."
    ),
    "settings.cycles.gap.unknown": (
        "O calendário deste ciclo tem um caso que não conseguimos resolver. Digite o "
        "período na execução de faturamento."
    ),
    "settings.cycles.detail.col.account": "Conta",
    "settings.cycles.detail.col.customer": "Cliente",
    "settings.cycles.detail.col.lacks": "O que falta",
    "settings.cycles.detail.lacks.route": "Sem rota",
    "settings.cycles.detail.uncoveredTruncated": (
        "Mostrando as {{count}} primeiras. Existem mais."
    ),
    "settings.cycles.detail.allCoveredTitle": "Todas as contas estão cobertas",
    "settings.cycles.detail.allCoveredBody": (
        "Cada conta chega a um ciclo pela rota da sua unidade."
    ),
    "settings.routes.detail.readHistory": "Histórico de leituras",
    "settings.routes.detail.col.readWindow": "Janela",
    "settings.routes.detail.col.readOn": "Lido em",
    "settings.routes.detail.col.collected": "Coletadas",
    "settings.routes.detail.col.expected": "Previstas",
    "settings.routes.detail.col.result": "Resultado",
    "settings.routes.detail.readResult.complete": "Completa",
    "settings.routes.detail.readResult.incomplete": "Incompleta",
    "settings.routes.detail.readResult.open": "Ainda aberta",
    "settings.routes.detail.noReadHistoryTitle": "Esta rota ainda não foi percorrida",
    "settings.routes.detail.noReadHistoryBody": (
        "Uma linha aparece aqui sempre que uma janela de leitura desta rota é encerrada."
    ),
    "settings.routes.detail.accountsLede": (
        "Quem é afetado por uma leitura perdida nesta rota. O que uma conta deve fica na "
        "conta, nunca aqui."
    ),
    "settings.routes.detail.col.account": "Conta",
    "settings.routes.detail.col.customer": "Cliente",
    "settings.routes.detail.accountsSummary": (
        "{{accounts}} contas em {{units}} unidades · {{without}} unidades sem conta"
    ),
    "settings.routes.detail.noAccountsTitle": "Nenhuma conta nesta rota",
    "settings.routes.detail.noAccountsBody": (
        "Nenhuma das unidades desta rota tem conta ainda."
    ),
    "settings.routes.detail.col.why": "Motivo",
    "settings.routes.detail.noReason": "Sem motivo registrado",
    "billing.run.field.dueDays": "Dias para vencimento",
    "billing.run.field.dueDaysHelp": (
        "Dias após a data da fatura até o vencimento. Zero significa vencer na própria "
        "data da fatura."
    ),
    "billing.run.field.dueDaysCycle": "{{days}} do ciclo",
    "billing.run.field.dueDateOverridden": (
        "{{days}} dias, apenas para esta execução. O ciclo mantém o seu próprio valor."
    ),
    "billing.run.due_days_invalid": "Digite um número inteiro de dias, zero ou mais.",
    "metering.readWindow.result_unknown": "Escolha um destes: {{allowed}}.",
    "metering.route.walk_order_incomplete": (
        "A ordem de percurso deixa de fora imóveis desta rota. Cada parada precisa estar "
        "nela."
    ),
    "metering.route.walk_order_duplicate_premises": (
        "Um imóvel aparece duas vezes na ordem de percurso. Cada parada aparece uma vez."
    ),
    "metering.route.walk_order_duplicate_position": (
        "Duas paradas ocupam a mesma posição. Dê a cada parada o seu próprio número."
    ),
    "metering.route.walk_order_not_a_member": (
        "Algumas dessas paradas não estão nesta rota. Só os imóveis dela podem ser "
        "ordenados."
    ),
    "finance.gap.billing_cycle_window_is_not_offered": (
        "Não é oferecido um relatório sobre um ciclo de faturamento inteiro. Cada janela "
        "que você pode escolher informa as datas exatas que cobre."
    ),
    "settings.cycles.detail.col.period": "Período",
    "settings.cycles.detail.col.issued": "Emitidas",
    "settings.cycles.detail.col.run": "Faturamento",
    "settings.cycles.detail.col.runStatus": "Situação da execução",
    "settings.cycles.detail.runBills": "{{issued}} de {{accounts}}",
    "settings.cycles.detail.runStatus.issued": "Emitida",
    "settings.cycles.detail.runStatus.issuedHeld": "Emitida · {{held}} retidas",
    "settings.cycles.detail.runStatus.notIssued": "Ainda não emitida",
    "settings.cycles.detail.col.accounts": "Contas",
    "settings.cycles.detail.notIssued": "Não emitida",
    "settings.cycles.detail.noRunsTitle": "Este ciclo ainda não foi faturado",
    "settings.cycles.detail.noRunsBody": "Aqui aparece uma linha para cada execução de faturamento neste ciclo.",
}


def main() -> int:
    english = json.loads((ROOT / "en.json").read_text(encoding="utf-8"))
    for key, value in EN.items():
        english.setdefault(key, value)
    for key in ORPHANED:
        english.pop(key, None)
    (ROOT / "en.json").write_text(
        json.dumps(english, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
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
            elif value == EN[key]:
                problems.append(f"{code}: {key} is byte-identical to English")
        for key, value in table.items():
            data.setdefault(key, value)
        for key in ORPHANED:
            data.pop(key, None)
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

    print(f"en.json: +{len(EN)} keys, -{len(ORPHANED)} orphaned")
    for problem in problems:
        print("  ⚠", problem)
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
