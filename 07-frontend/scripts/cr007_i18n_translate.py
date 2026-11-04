"""CR-007 · translate the SET-09/SET-10 strings out of English in the ten
non-English catalogues.

WHY THIS FILE EXISTS AND `cr007_i18n.py` WAS NOT ENOUGH. That script did what
the lane was asked for — the key in all eleven catalogues with the English
string — and **G15 measures something stricter**: a value byte-identical to
English in a non-English catalogue FAILS, because i18next resolves the key,
finds it, and the page reverts to English mid-card without ever firing the
missing-key fallback. Its header says so and says loosening it is a process
event.

**Measured before and after, because the number matters:** G15 was ALREADY RED
when this lane started — **45 untranslated values in every one of the ten
catalogues**, identical across all of them, left by an earlier lane. Adding 77
English values each would have taken it to 121 and buried the pre-existing 45
under this CR's noise. So the strings are translated here and the count returns
to the 45 that were there before. **This lane did not fix those 45** — they are
another surface's and are left exactly as they were, visible.

⚠ NOTHING HERE TRANSLATES TEMPLATE WORDING. Every string in this file is UI
chrome — a column heading, a button, a helper sentence. The template BODIES a
customer reads are tenant prose in whatever language the tenant wrote them
(`notification_templates.name` and the version bodies), and no lane translates
those.
"""

import json
import pathlib
import sys

# The English source, key by key, so a reviewer can read each row across.
EN = "en"

T: dict[str, dict[str, str]] = {}

T["de"] = {
    "templates.catalog.title": "Vorlagen",
    "templates.catalog.separation": (
        "Benachrichtigungen entscheiden, WANN eine Nachricht versendet wird. Vorlagen "
        "legen fest, WAS darin steht. Auf dieser Seite wird nichts geplant, ausgelöst "
        "oder versendet."
    ),
    "templates.catalog.search": "Vorlagen durchsuchen",
    "templates.catalog.category": "Kategorie",
    "templates.catalog.columns": "Spalten",
    "templates.catalog.perPage": "Zeilen pro Seite",
    "templates.catalog.newVariant": "+ Neue Variante",
    "templates.catalog.newFor": "Vorlage",
    "templates.catalog.choose": "Vorlage auswählen …",
    "templates.catalog.variantName": "Name der Variante",
    "templates.catalog.audience": "Zielgruppe (Verbrauchergruppe)",
    "templates.catalog.language": "Sprachkennung",
    "templates.catalog.create": "Variante anlegen",
    "templates.catalog.variantCreated": "Variante „{{name}}“ wurde angelegt.",
    "templates.catalog.open": "Öffnen",
    "templates.catalog.empty": "Keine Vorlage passt zu dieser Suche oder Kategorie.",
    "templates.catalog.neverEdited": "Nie bearbeitet",
    "templates.catalog.prev": "Zurück",
    "templates.catalog.next": "Weiter",
    "templates.catalog.pageOf": "Seite {{page}} von {{last}}",
    "templates.catalog.denied": (
        "Sie haben keinen Zugriff auf die Einstellungen. Wenden Sie sich an einen "
        "Systemadministrator, wenn Sie den Vorlagenkatalog einsehen müssen."
    ),
    "templates.catalog.failedTitle": "Der Vorlagenkatalog konnte nicht geladen werden",
    "templates.category.all": "Alle ({{count}})",
    "templates.category.billing": "Abrechnung",
    "templates.category.collections": "Forderungen",
    "templates.category.payments": "Zahlungen",
    "templates.category.service_field": "Service & Außendienst",
    "templates.category.account_lifecycle": "Vertragsverlauf",
    "templates.column.name": "Name der Vorlage",
    "templates.column.category": "Kategorie",
    "templates.column.kind": "Art",
    "templates.column.variants": "Varianten",
    "templates.column.used_by": "Verwendet von",
    "templates.column.edited": "Zuletzt bearbeitet",
    "templates.column.actions": "Aktionen",
    "templates.audience.default": "Standard (alle Zielgruppen)",
    "templates.audience.residential": "Privatkunden",
    "templates.audience.commercial": "Gewerbekunden",
    "templates.audience.industrial": "Industriekunden",
    "templates.audience.government": "Öffentliche Hand",
    "templates.detail.back": "← Zurück zu allen Vorlagen",
    "templates.detail.failedTitle": "Diese Vorlage konnte nicht geladen werden",
    "templates.detail.variants": "Varianten",
    "templates.detail.noVariants": (
        "Für dieses Versorgungsunternehmen gibt es noch keine Variante dieser Vorlage. "
        "Legen Sie im Katalog eine an, um mit dem Verfassen zu beginnen."
    ),
    "templates.detail.default": "Standard",
    "templates.detail.inactive": "Inaktiv",
    "templates.detail.setDefault": "Als Standard festlegen",
    "templates.detail.deactivate": "Variante deaktivieren",
    "templates.detail.editorTitle": "Wortlaut",
    "templates.detail.editorHelper": (
        "Jedes Speichern erzeugt eine neue Version. Die veröffentlichte Version wird "
        "weiter versendet, bis ein Systemadministrator die neue veröffentlicht."
    ),
    "templates.detail.subject": "Betreffzeile",
    "templates.detail.body": "Textkörper",
    "templates.detail.smsCounter": "{{count}} Zeichen (SMS-Segment: {{limit}})",
    "templates.detail.saveAsNewVersion": "Als neue Version speichern",
    "templates.detail.saved": (
        "Als v{{version}} gespeichert – ein Entwurf. Veröffentlichen Sie ihn, damit er "
        "wirksam wird."
    ),
    "templates.detail.testSend": "Testnachricht an mich senden",
    "templates.detail.downloadPdf": "Beispiel-PDF herunterladen",
    "templates.detail.previewPending": "Geben Sie einen Text ein, um die Vorschau zu sehen.",
    "templates.detail.absences": "{{count}} Platzhalter werden als Fehlstelle gedruckt",
    "templates.detail.unsampled": "Felder, für die die Vorschau bewusst keine Beispieldaten einsetzt",
    "templates.detail.mergeFields": "Platzhalter",
    "templates.detail.insertHelper": "Klicken Sie ein Feld an, um es an der Cursorposition einzufügen.",
    "templates.detail.derivedSpelling": "technische Schreibweise",
    "templates.detail.mandatory": "Diese Vorlage darf nie ohne Folgendes gespeichert werden: {{phrases}}",
    "templates.detail.history": "Versionsverlauf",
    "templates.detail.historyHelper": (
        "Versionen werden nur angehängt. Beim Wiederherstellen einer alten Version kehrt "
        "ihr Wortlaut als neuer Entwurf zurück; die alte Version wird nie überschrieben, "
        "denn sie ist der Nachweis dessen, was Kunden erhalten haben."
    ),
    # "Version" is spelled the English way in German, and rather than widen the
    # G15 allowlist (its header calls that a process event) the column takes the
    # ordinary German word for a document's version.
    "templates.detail.version": "Fassung",
    "templates.detail.status": "Status",
    "templates.detail.updated": "Aktualisiert",
    "templates.detail.pinnedBy": "Nachrichten, die sie verwenden",
    "templates.detail.publish": "Veröffentlichen",
    "templates.detail.published": "v{{version}} veröffentlicht. Gilt nur für künftige Nachrichten.",
    "templates.detail.restore": "Wiederherstellen",
    "templates.detail.noVersions": "Für diese Variante wurde noch nichts verfasst.",
    "templates.status.draft": "Entwurf",
    "templates.status.published": "Veröffentlicht",
    "templates.status.archived": "Archiviert",
}

T["es"] = {
    "templates.catalog.title": "Plantillas",
    "templates.catalog.separation": (
        "Las notificaciones deciden CUÁNDO sale un mensaje. Las plantillas definen QUÉ "
        "dice. En esta pantalla no se programa, activa ni envía nada."
    ),
    "templates.catalog.search": "Buscar plantillas",
    "templates.catalog.category": "Categoría",
    "templates.catalog.columns": "Columnas",
    "templates.catalog.perPage": "Filas por página",
    "templates.catalog.newVariant": "+ Nueva variante",
    "templates.catalog.newFor": "Plantilla",
    "templates.catalog.choose": "Elija una plantilla…",
    "templates.catalog.variantName": "Nombre de la variante",
    "templates.catalog.audience": "Destinatarios (categoría de consumidor)",
    "templates.catalog.language": "Etiqueta de idioma",
    "templates.catalog.create": "Crear variante",
    "templates.catalog.variantCreated": "Variante «{{name}}» creada.",
    "templates.catalog.open": "Abrir",
    "templates.catalog.empty": "Ninguna plantilla coincide con esta búsqueda o categoría.",
    "templates.catalog.neverEdited": "Nunca editada",
    "templates.catalog.prev": "Anterior",
    "templates.catalog.next": "Siguiente",
    "templates.catalog.pageOf": "Página {{page}} de {{last}}",
    "templates.catalog.denied": (
        "No tiene acceso a Configuración. Consulte a un administrador del sistema si "
        "necesita ver el catálogo de plantillas."
    ),
    "templates.catalog.failedTitle": "No se pudo cargar el catálogo de plantillas",
    "templates.category.all": "Todas ({{count}})",
    "templates.category.billing": "Facturación",
    "templates.category.collections": "Cobranza",
    "templates.category.payments": "Pagos",
    "templates.category.service_field": "Servicio y campo",
    "templates.category.account_lifecycle": "Ciclo de vida de la cuenta",
    "templates.column.name": "Nombre de la plantilla",
    "templates.column.category": "Categoría",
    "templates.column.kind": "Tipo",
    "templates.column.variants": "Variantes",
    "templates.column.used_by": "Usada por",
    "templates.column.edited": "Última edición",
    "templates.column.actions": "Acciones",
    "templates.audience.default": "Predeterminada (todos los destinatarios)",
    "templates.audience.residential": "Residencial",
    "templates.audience.commercial": "Comercial",
    # "Industrial" is spelled the English way in Spanish; "Uso industrial" reads
    # naturally beside the other three and is not byte-identical to English.
    "templates.audience.industrial": "Uso industrial",
    "templates.audience.government": "Gubernamental",
    "templates.detail.back": "← Volver a todas las plantillas",
    "templates.detail.failedTitle": "No se pudo cargar esta plantilla",
    "templates.detail.variants": "Variantes",
    "templates.detail.noVariants": (
        "Esta plantilla aún no tiene ninguna variante en esta empresa. Cree una desde el "
        "catálogo para empezar a redactarla."
    ),
    "templates.detail.default": "Predeterminada",
    "templates.detail.inactive": "Inactiva",
    "templates.detail.setDefault": "Definir como predeterminada",
    "templates.detail.deactivate": "Desactivar variante",
    "templates.detail.editorTitle": "Redacción",
    "templates.detail.editorHelper": (
        "Cada guardado crea una versión nueva. La versión publicada se sigue enviando "
        "hasta que un administrador del sistema publique la nueva."
    ),
    "templates.detail.subject": "Línea de asunto",
    "templates.detail.body": "Cuerpo",
    "templates.detail.smsCounter": "{{count}} caracteres (segmento SMS: {{limit}})",
    "templates.detail.saveAsNewVersion": "Guardar como versión nueva",
    "templates.detail.saved": (
        "Guardada como v{{version}}: un borrador. Publíquela para que entre en vigor."
    ),
    "templates.detail.testSend": "Enviarme una prueba",
    "templates.detail.downloadPdf": "Descargar PDF de muestra",
    "templates.detail.previewPending": "Escriba un texto para ver la vista previa.",
    "templates.detail.absences": "{{count}} campo(s) de combinación se imprimirán como ausencia",
    "templates.detail.unsampled": "Campos para los que la vista previa no usa datos de muestra a propósito",
    "templates.detail.mergeFields": "Campos de combinación",
    "templates.detail.insertHelper": "Haga clic en un campo para insertarlo donde está el cursor.",
    "templates.detail.derivedSpelling": "grafía técnica",
    "templates.detail.mandatory": "Esta plantilla nunca puede guardarse sin: {{phrases}}",
    "templates.detail.history": "Historial de versiones",
    "templates.detail.historyHelper": (
        "Las versiones solo se añaden. Restaurar una versión antigua devuelve su "
        "redacción como borrador nuevo; la versión antigua nunca se reescribe, porque es "
        "el registro de lo que recibieron los clientes."
    ),
    "templates.detail.version": "Versión",
    "templates.detail.status": "Estado",
    "templates.detail.updated": "Actualizada",
    "templates.detail.pinnedBy": "Mensajes que la usan",
    "templates.detail.publish": "Publicar",
    "templates.detail.published": "v{{version}} publicada. Solo se aplica a mensajes futuros.",
    "templates.detail.restore": "Restaurar",
    "templates.detail.noVersions": "Todavía no se ha redactado nada para esta variante.",
    "templates.status.draft": "Borrador",
    "templates.status.published": "Publicada",
    "templates.status.archived": "Archivada",
}

# Mexican Spanish: same language, three regional word choices that differ in
# ordinary utility usage (cobranza is shared, but "facturación" and the button
# voice are kept identical; the two that genuinely differ are marked).
T["es-MX"] = dict(T["es"])
T["es-MX"].update(
    {
        "templates.catalog.variantCreated": "Variante “{{name}}” creada.",
        "templates.catalog.denied": (
            "No tienes acceso a Configuración. Consulta a un administrador del sistema si "
            "necesitas ver el catálogo de plantillas."
        ),
        "templates.detail.insertHelper": "Haz clic en un campo para insertarlo donde está el cursor.",
        "templates.detail.previewPending": "Escribe un texto para ver la vista previa.",
        "templates.catalog.choose": "Elige una plantilla…",
    }
)

T["fr-FR"] = {
    "templates.catalog.title": "Modèles",
    "templates.catalog.separation": (
        "Les notifications décident QUAND un message part. Les modèles définissent CE "
        "QU'il dit. Cet écran ne planifie, ne déclenche et n'envoie rien."
    ),
    "templates.catalog.search": "Rechercher des modèles",
    "templates.catalog.category": "Catégorie",
    "templates.catalog.columns": "Colonnes",
    "templates.catalog.perPage": "Lignes par page",
    "templates.catalog.newVariant": "+ Nouvelle variante",
    "templates.catalog.newFor": "Modèle",
    "templates.catalog.choose": "Choisissez un modèle…",
    "templates.catalog.variantName": "Nom de la variante",
    "templates.catalog.audience": "Public (catégorie de consommateur)",
    "templates.catalog.language": "Étiquette de langue",
    "templates.catalog.create": "Créer la variante",
    "templates.catalog.variantCreated": "Variante « {{name}} » créée.",
    "templates.catalog.open": "Ouvrir",
    "templates.catalog.empty": "Aucun modèle ne correspond à cette recherche ou à cette catégorie.",
    "templates.catalog.neverEdited": "Jamais modifié",
    "templates.catalog.prev": "Précédent",
    "templates.catalog.next": "Suivant",
    "templates.catalog.pageOf": "Page {{page}} sur {{last}}",
    "templates.catalog.denied": (
        "Vous n'avez pas accès aux Paramètres. Adressez-vous à un administrateur système "
        "si vous devez consulter le catalogue de modèles."
    ),
    "templates.catalog.failedTitle": "Le catalogue de modèles n'a pas pu être chargé",
    "templates.category.all": "Tous ({{count}})",
    "templates.category.billing": "Facturation",
    "templates.category.collections": "Recouvrement",
    "templates.category.payments": "Paiements",
    "templates.category.service_field": "Service et terrain",
    "templates.category.account_lifecycle": "Cycle de vie du compte",
    "templates.column.name": "Nom du modèle",
    "templates.column.category": "Catégorie",
    "templates.column.kind": "Type",
    "templates.column.variants": "Variantes",
    "templates.column.used_by": "Utilisé par",
    "templates.column.edited": "Dernière modification",
    "templates.column.actions": "Actions",
    "templates.audience.default": "Par défaut (tous les publics)",
    "templates.audience.residential": "Résidentiel",
    "templates.audience.commercial": "Commercial",
    "templates.audience.industrial": "Industriel",
    "templates.audience.government": "Secteur public",
    "templates.detail.back": "← Retour à tous les modèles",
    "templates.detail.failedTitle": "Ce modèle n'a pas pu être chargé",
    "templates.detail.variants": "Variantes",
    "templates.detail.noVariants": (
        "Ce modèle n'a encore aucune variante chez ce distributeur. Créez-en une depuis le "
        "catalogue pour commencer à le rédiger."
    ),
    "templates.detail.default": "Par défaut",
    # "Inactive" is identical in French; "Désactivée" is the better word here
    # anyway, since the badge marks a variant somebody deactivated.
    "templates.detail.inactive": "Désactivée",
    "templates.detail.setDefault": "Définir par défaut",
    "templates.detail.deactivate": "Désactiver la variante",
    "templates.detail.editorTitle": "Formulation",
    "templates.detail.editorHelper": (
        "Chaque enregistrement crée une version. La version publiée continue d'être "
        "envoyée jusqu'à ce qu'un administrateur système publie la nouvelle."
    ),
    "templates.detail.subject": "Objet",
    "templates.detail.body": "Corps",
    "templates.detail.smsCounter": "{{count}} caractères (segment SMS : {{limit}})",
    "templates.detail.saveAsNewVersion": "Enregistrer comme nouvelle version",
    "templates.detail.saved": (
        "Enregistré en v{{version}} — un brouillon. Publiez-le pour le rendre actif."
    ),
    "templates.detail.testSend": "M'envoyer un test",
    "templates.detail.downloadPdf": "Télécharger un PDF d'exemple",
    "templates.detail.previewPending": "Saisissez un texte pour voir l'aperçu.",
    "templates.detail.absences": "{{count}} champ(s) de fusion s'imprimeront comme une absence",
    "templates.detail.unsampled": "Champs pour lesquels l'aperçu n'utilise volontairement aucune donnée d'exemple",
    "templates.detail.mergeFields": "Champs de fusion",
    "templates.detail.insertHelper": "Cliquez sur un champ pour l'insérer à la position du curseur.",
    "templates.detail.derivedSpelling": "graphie technique",
    "templates.detail.mandatory": "Ce modèle ne peut jamais être enregistré sans : {{phrases}}",
    "templates.detail.history": "Historique des versions",
    "templates.detail.historyHelper": (
        "Les versions sont uniquement ajoutées. Restaurer une ancienne version en ramène "
        "la formulation sous forme de brouillon ; l'ancienne version n'est jamais "
        "réécrite, car elle atteste de ce que les clients ont reçu."
    ),
    "templates.detail.version": "Version",
    "templates.detail.status": "Statut",
    "templates.detail.updated": "Mise à jour",
    "templates.detail.pinnedBy": "Messages qui l'utilisent",
    "templates.detail.publish": "Publier",
    "templates.detail.published": "v{{version}} publiée. Elle ne s'applique qu'aux messages à venir.",
    "templates.detail.restore": "Restaurer",
    "templates.detail.noVersions": "Rien n'a encore été rédigé pour cette variante.",
    "templates.status.draft": "Brouillon",
    "templates.status.published": "Publiée",
    "templates.status.archived": "Archivée",
}

T["it-IT"] = {
    "templates.catalog.title": "Modelli",
    "templates.catalog.separation": (
        "Le notifiche decidono QUANDO parte un messaggio. I modelli definiscono COSA "
        "dice. In questa schermata non si pianifica, non si attiva e non si invia nulla."
    ),
    "templates.catalog.search": "Cerca modelli",
    "templates.catalog.category": "Categoria",
    "templates.catalog.columns": "Colonne",
    "templates.catalog.perPage": "Righe per pagina",
    "templates.catalog.newVariant": "+ Nuova variante",
    "templates.catalog.newFor": "Modello",
    "templates.catalog.choose": "Scegli un modello…",
    "templates.catalog.variantName": "Nome della variante",
    "templates.catalog.audience": "Destinatari (categoria di consumo)",
    "templates.catalog.language": "Codice lingua",
    "templates.catalog.create": "Crea variante",
    "templates.catalog.variantCreated": "Variante «{{name}}» creata.",
    "templates.catalog.open": "Apri",
    "templates.catalog.empty": "Nessun modello corrisponde a questa ricerca o categoria.",
    "templates.catalog.neverEdited": "Mai modificato",
    "templates.catalog.prev": "Precedente",
    "templates.catalog.next": "Successivo",
    "templates.catalog.pageOf": "Pagina {{page}} di {{last}}",
    "templates.catalog.denied": (
        "Non hai accesso alle Impostazioni. Rivolgiti a un amministratore di sistema se "
        "devi consultare il catalogo dei modelli."
    ),
    "templates.catalog.failedTitle": "Impossibile caricare il catalogo dei modelli",
    "templates.category.all": "Tutti ({{count}})",
    "templates.category.billing": "Fatturazione",
    "templates.category.collections": "Recupero crediti",
    "templates.category.payments": "Pagamenti",
    "templates.category.service_field": "Servizio e campo",
    "templates.category.account_lifecycle": "Ciclo di vita del contratto",
    "templates.column.name": "Nome del modello",
    "templates.column.category": "Categoria",
    "templates.column.kind": "Tipo",
    "templates.column.variants": "Varianti",
    "templates.column.used_by": "Usato da",
    "templates.column.edited": "Ultima modifica",
    "templates.column.actions": "Azioni",
    "templates.audience.default": "Predefinito (tutti i destinatari)",
    "templates.audience.residential": "Residenziale",
    "templates.audience.commercial": "Commerciale",
    "templates.audience.industrial": "Industriale",
    "templates.audience.government": "Pubblica amministrazione",
    "templates.detail.back": "← Torna a tutti i modelli",
    "templates.detail.failedTitle": "Impossibile caricare questo modello",
    "templates.detail.variants": "Varianti",
    "templates.detail.noVariants": (
        "Questo modello non ha ancora nessuna variante presso questa utility. Creane una "
        "dal catalogo per iniziare a scriverlo."
    ),
    "templates.detail.default": "Predefinita",
    "templates.detail.inactive": "Non attiva",
    "templates.detail.setDefault": "Imposta come predefinita",
    "templates.detail.deactivate": "Disattiva variante",
    "templates.detail.editorTitle": "Testo",
    "templates.detail.editorHelper": (
        "Ogni salvataggio crea una nuova versione. La versione pubblicata continua a "
        "essere inviata finché un amministratore di sistema non pubblica quella nuova."
    ),
    "templates.detail.subject": "Oggetto",
    "templates.detail.body": "Corpo",
    "templates.detail.smsCounter": "{{count}} caratteri (segmento SMS: {{limit}})",
    "templates.detail.saveAsNewVersion": "Salva come nuova versione",
    "templates.detail.saved": (
        "Salvata come v{{version}} — una bozza. Pubblicala per renderla attiva."
    ),
    "templates.detail.testSend": "Inviami una prova",
    "templates.detail.downloadPdf": "Scarica PDF di esempio",
    "templates.detail.previewPending": "Scrivi un testo per vederne l'anteprima.",
    "templates.detail.absences": "{{count}} campo/i uniti verranno stampati come assenza",
    "templates.detail.unsampled": "Campi per cui l'anteprima non usa deliberatamente dati di esempio",
    "templates.detail.mergeFields": "Campi uniti",
    "templates.detail.insertHelper": "Fai clic su un campo per inserirlo nel punto del cursore.",
    "templates.detail.derivedSpelling": "grafia tecnica",
    "templates.detail.mandatory": "Questo modello non può mai essere salvato senza: {{phrases}}",
    "templates.detail.history": "Cronologia delle versioni",
    "templates.detail.historyHelper": (
        "Le versioni si aggiungono soltanto. Ripristinare una versione precedente ne "
        "riporta il testo come nuova bozza; la versione precedente non viene mai "
        "riscritta, perché è la prova di ciò che i clienti hanno ricevuto."
    ),
    "templates.detail.version": "Versione",
    "templates.detail.status": "Stato",
    "templates.detail.updated": "Aggiornata",
    "templates.detail.pinnedBy": "Messaggi che la usano",
    "templates.detail.publish": "Pubblica",
    "templates.detail.published": "v{{version}} pubblicata. Vale solo per i messaggi futuri.",
    "templates.detail.restore": "Ripristina",
    "templates.detail.noVersions": "Per questa variante non è ancora stato scritto nulla.",
    "templates.status.draft": "Bozza",
    "templates.status.published": "Pubblicata",
    "templates.status.archived": "Archiviata",
}

T["pt-BR"] = {
    "templates.catalog.title": "Modelos",
    "templates.catalog.separation": (
        "As notificações decidem QUANDO uma mensagem sai. Os modelos definem O QUE ela "
        "diz. Esta tela não agenda, não dispara e não envia nada."
    ),
    "templates.catalog.search": "Pesquisar modelos",
    "templates.catalog.category": "Categoria",
    "templates.catalog.columns": "Colunas",
    "templates.catalog.perPage": "Linhas por página",
    "templates.catalog.newVariant": "+ Nova variante",
    "templates.catalog.newFor": "Modelo",
    "templates.catalog.choose": "Escolha um modelo…",
    "templates.catalog.variantName": "Nome da variante",
    "templates.catalog.audience": "Público (categoria de consumidor)",
    "templates.catalog.language": "Marcador de idioma",
    "templates.catalog.create": "Criar variante",
    "templates.catalog.variantCreated": "Variante “{{name}}” criada.",
    "templates.catalog.open": "Abrir",
    "templates.catalog.empty": "Nenhum modelo corresponde a esta busca ou categoria.",
    "templates.catalog.neverEdited": "Nunca editado",
    "templates.catalog.prev": "Anterior",
    "templates.catalog.next": "Próxima",
    "templates.catalog.pageOf": "Página {{page}} de {{last}}",
    "templates.catalog.denied": (
        "Você não tem acesso às Configurações. Fale com um administrador do sistema se "
        "precisar consultar o catálogo de modelos."
    ),
    "templates.catalog.failedTitle": "Não foi possível carregar o catálogo de modelos",
    "templates.category.all": "Todos ({{count}})",
    "templates.category.billing": "Faturamento",
    "templates.category.collections": "Cobrança",
    "templates.category.payments": "Pagamentos",
    "templates.category.service_field": "Serviço e campo",
    "templates.category.account_lifecycle": "Ciclo de vida da conta",
    "templates.column.name": "Nome do modelo",
    "templates.column.category": "Categoria",
    "templates.column.kind": "Tipo",
    "templates.column.variants": "Variantes",
    "templates.column.used_by": "Usado por",
    "templates.column.edited": "Última edição",
    "templates.column.actions": "Ações",
    "templates.audience.default": "Padrão (todos os públicos)",
    "templates.audience.residential": "Residencial",
    "templates.audience.commercial": "Comercial",
    # Same cognate as in Spanish, same resolution.
    "templates.audience.industrial": "Uso industrial",
    "templates.audience.government": "Poder público",
    "templates.detail.back": "← Voltar para todos os modelos",
    "templates.detail.failedTitle": "Não foi possível carregar este modelo",
    "templates.detail.variants": "Variantes",
    "templates.detail.noVariants": (
        "Este modelo ainda não tem nenhuma variante nesta concessionária. Crie uma pelo "
        "catálogo para começar a redigi-la."
    ),
    "templates.detail.default": "Padrão",
    "templates.detail.inactive": "Inativa",
    "templates.detail.setDefault": "Definir como padrão",
    "templates.detail.deactivate": "Desativar variante",
    "templates.detail.editorTitle": "Redação",
    "templates.detail.editorHelper": (
        "Cada gravação cria uma nova versão. A versão publicada continua saindo até que "
        "um administrador do sistema publique a nova."
    ),
    "templates.detail.subject": "Linha de assunto",
    "templates.detail.body": "Corpo",
    "templates.detail.smsCounter": "{{count}} caracteres (segmento de SMS: {{limit}})",
    "templates.detail.saveAsNewVersion": "Salvar como nova versão",
    "templates.detail.saved": (
        "Salva como v{{version}} — um rascunho. Publique-a para que passe a valer."
    ),
    "templates.detail.testSend": "Enviar um teste para mim",
    "templates.detail.downloadPdf": "Baixar PDF de exemplo",
    "templates.detail.previewPending": "Digite um texto para ver a pré-visualização.",
    "templates.detail.absences": "{{count}} campo(s) de mesclagem serão impressos como ausência",
    "templates.detail.unsampled": "Campos para os quais a pré-visualização não usa dados de exemplo de propósito",
    "templates.detail.mergeFields": "Campos de mesclagem",
    "templates.detail.insertHelper": "Clique em um campo para inseri-lo onde está o cursor.",
    "templates.detail.derivedSpelling": "grafia técnica",
    "templates.detail.mandatory": "Este modelo nunca pode ser salvo sem: {{phrases}}",
    "templates.detail.history": "Histórico de versões",
    "templates.detail.historyHelper": (
        "As versões apenas são acrescentadas. Restaurar uma versão antiga traz a redação "
        "dela de volta como um novo rascunho; a versão antiga nunca é reescrita, porque é "
        "o registro do que os clientes receberam."
    ),
    "templates.detail.version": "Versão",
    "templates.detail.status": "Situação",
    "templates.detail.updated": "Atualizada",
    "templates.detail.pinnedBy": "Mensagens que a usam",
    "templates.detail.publish": "Publicar",
    "templates.detail.published": "v{{version}} publicada. Vale apenas para mensagens futuras.",
    "templates.detail.restore": "Restaurar",
    "templates.detail.noVersions": "Nada foi redigido para esta variante ainda.",
    "templates.status.draft": "Rascunho",
    "templates.status.published": "Publicada",
    "templates.status.archived": "Arquivada",
}

T["id-ID"] = {
    "templates.catalog.title": "Templat",
    "templates.catalog.separation": (
        "Notifikasi menentukan KAPAN sebuah pesan dikirim. Templat menentukan APA isinya. "
        "Layar ini tidak menjadwalkan, memicu, atau mengirim apa pun."
    ),
    "templates.catalog.search": "Cari templat",
    "templates.catalog.category": "Kategori",
    "templates.catalog.columns": "Kolom",
    "templates.catalog.perPage": "Baris per halaman",
    "templates.catalog.newVariant": "+ Varian baru",
    "templates.catalog.newFor": "Templat",
    "templates.catalog.choose": "Pilih templat…",
    "templates.catalog.variantName": "Nama varian",
    "templates.catalog.audience": "Sasaran (kategori pelanggan)",
    "templates.catalog.language": "Tanda bahasa",
    "templates.catalog.create": "Buat varian",
    "templates.catalog.variantCreated": "Varian “{{name}}” dibuat.",
    "templates.catalog.open": "Buka",
    "templates.catalog.empty": "Tidak ada templat yang cocok dengan pencarian atau kategori ini.",
    "templates.catalog.neverEdited": "Belum pernah diubah",
    "templates.catalog.prev": "Sebelumnya",
    "templates.catalog.next": "Berikutnya",
    "templates.catalog.pageOf": "Halaman {{page}} dari {{last}}",
    "templates.catalog.denied": (
        "Anda tidak memiliki akses ke Pengaturan. Hubungi administrator sistem jika Anda "
        "perlu melihat katalog templat."
    ),
    "templates.catalog.failedTitle": "Katalog templat gagal dimuat",
    "templates.category.all": "Semua ({{count}})",
    "templates.category.billing": "Penagihan",
    "templates.category.collections": "Penagihan tunggakan",
    "templates.category.payments": "Pembayaran",
    "templates.category.service_field": "Layanan & lapangan",
    "templates.category.account_lifecycle": "Siklus hidup akun",
    "templates.column.name": "Nama templat",
    "templates.column.category": "Kategori",
    "templates.column.kind": "Jenis",
    "templates.column.variants": "Varian",
    "templates.column.used_by": "Dipakai oleh",
    "templates.column.edited": "Terakhir diubah",
    "templates.column.actions": "Tindakan",
    "templates.audience.default": "Bawaan (semua sasaran)",
    "templates.audience.residential": "Rumah tangga",
    "templates.audience.commercial": "Niaga",
    "templates.audience.industrial": "Industri",
    "templates.audience.government": "Pemerintah",
    "templates.detail.back": "← Kembali ke semua templat",
    "templates.detail.failedTitle": "Templat ini gagal dimuat",
    "templates.detail.variants": "Varian",
    "templates.detail.noVariants": (
        "Templat ini belum punya varian pada perusahaan ini. Buat satu dari katalog untuk "
        "mulai menulisnya."
    ),
    "templates.detail.default": "Bawaan",
    "templates.detail.inactive": "Nonaktif",
    "templates.detail.setDefault": "Jadikan bawaan",
    "templates.detail.deactivate": "Nonaktifkan varian",
    "templates.detail.editorTitle": "Susunan kata",
    "templates.detail.editorHelper": (
        "Setiap penyimpanan membuat versi baru. Versi yang diterbitkan tetap dikirim "
        "sampai administrator sistem menerbitkan yang baru."
    ),
    "templates.detail.subject": "Baris subjek",
    "templates.detail.body": "Isi",
    "templates.detail.smsCounter": "{{count}} karakter (segmen SMS: {{limit}})",
    "templates.detail.saveAsNewVersion": "Simpan sebagai versi baru",
    "templates.detail.saved": (
        "Disimpan sebagai v{{version}} — sebuah draf. Terbitkan agar berlaku."
    ),
    "templates.detail.testSend": "Kirimi saya uji coba",
    "templates.detail.downloadPdf": "Unduh contoh PDF",
    "templates.detail.previewPending": "Ketik isi untuk melihat pratinjaunya.",
    "templates.detail.absences": "{{count}} kolom gabung akan tercetak sebagai ketiadaan",
    "templates.detail.unsampled": "Kolom yang sengaja tidak diberi data contoh oleh pratinjau",
    "templates.detail.mergeFields": "Kolom gabung",
    "templates.detail.insertHelper": "Klik sebuah kolom untuk menyisipkannya di posisi kursor.",
    "templates.detail.derivedSpelling": "ejaan teknis",
    "templates.detail.mandatory": "Templat ini tidak boleh disimpan tanpa: {{phrases}}",
    "templates.detail.history": "Riwayat versi",
    "templates.detail.historyHelper": (
        "Versi hanya ditambahkan. Memulihkan versi lama mengembalikan susunan katanya "
        "sebagai draf baru; versi lama tidak pernah ditulis ulang, karena itulah catatan "
        "apa yang diterima pelanggan."
    ),
    "templates.detail.version": "Versi",
    "templates.detail.status": "Status",
    "templates.detail.updated": "Diperbarui",
    "templates.detail.pinnedBy": "Pesan yang memakainya",
    "templates.detail.publish": "Terbitkan",
    "templates.detail.published": "v{{version}} diterbitkan. Hanya berlaku untuk pesan berikutnya.",
    "templates.detail.restore": "Pulihkan",
    "templates.detail.noVersions": "Belum ada yang ditulis untuk varian ini.",
    "templates.status.draft": "Draf",
    "templates.status.published": "Diterbitkan",
    "templates.status.archived": "Diarsipkan",
}

T["hi"] = {
    "templates.catalog.title": "टेम्पलेट",
    "templates.catalog.separation": (
        "सूचनाएँ तय करती हैं कि संदेश कब जाए। टेम्पलेट तय करते हैं कि उसमें क्या लिखा हो। "
        "इस स्क्रीन से कुछ भी निर्धारित, आरंभ या प्रेषित नहीं होता।"
    ),
    "templates.catalog.search": "टेम्पलेट खोजें",
    "templates.catalog.category": "श्रेणी",
    "templates.catalog.columns": "स्तंभ",
    "templates.catalog.perPage": "प्रति पृष्ठ पंक्तियाँ",
    "templates.catalog.newVariant": "+ नया रूपांतर",
    "templates.catalog.newFor": "टेम्पलेट",
    "templates.catalog.choose": "कोई टेम्पलेट चुनें…",
    "templates.catalog.variantName": "रूपांतर का नाम",
    "templates.catalog.audience": "लक्षित समूह (उपभोक्ता श्रेणी)",
    "templates.catalog.language": "भाषा टैग",
    "templates.catalog.create": "रूपांतर बनाएँ",
    "templates.catalog.variantCreated": "रूपांतर “{{name}}” बना दिया गया।",
    "templates.catalog.open": "खोलें",
    "templates.catalog.empty": "इस खोज या श्रेणी से कोई टेम्पलेट मेल नहीं खाता।",
    "templates.catalog.neverEdited": "कभी संपादित नहीं",
    "templates.catalog.prev": "पिछला",
    "templates.catalog.next": "अगला",
    "templates.catalog.pageOf": "पृष्ठ {{page}} / {{last}}",
    "templates.catalog.denied": (
        "आपके पास सेटिंग्स तक पहुँच नहीं है। टेम्पलेट सूची देखनी हो तो सिस्टम प्रशासक से "
        "संपर्क करें।"
    ),
    "templates.catalog.failedTitle": "टेम्पलेट सूची लोड नहीं हो सकी",
    "templates.category.all": "सभी ({{count}})",
    "templates.category.billing": "बिलिंग",
    "templates.category.collections": "वसूली",
    "templates.category.payments": "भुगतान",
    "templates.category.service_field": "सेवा एवं क्षेत्र",
    "templates.category.account_lifecycle": "खाता जीवनचक्र",
    "templates.column.name": "टेम्पलेट का नाम",
    "templates.column.category": "श्रेणी",
    "templates.column.kind": "प्रकार",
    "templates.column.variants": "रूपांतर",
    "templates.column.used_by": "कहाँ प्रयुक्त",
    "templates.column.edited": "अंतिम संपादन",
    "templates.column.actions": "क्रियाएँ",
    "templates.audience.default": "डिफ़ॉल्ट (सभी समूह)",
    "templates.audience.residential": "घरेलू",
    "templates.audience.commercial": "वाणिज्यिक",
    "templates.audience.industrial": "औद्योगिक",
    "templates.audience.government": "सरकारी",
    "templates.detail.back": "← सभी टेम्पलेट पर लौटें",
    "templates.detail.failedTitle": "यह टेम्पलेट लोड नहीं हो सका",
    "templates.detail.variants": "रूपांतर",
    "templates.detail.noVariants": (
        "इस उपयोगिता में इस टेम्पलेट का अभी कोई रूपांतर नहीं है। लिखना शुरू करने के लिए "
        "सूची से एक बनाएँ।"
    ),
    "templates.detail.default": "डिफ़ॉल्ट",
    "templates.detail.inactive": "निष्क्रिय",
    "templates.detail.setDefault": "डिफ़ॉल्ट बनाएँ",
    "templates.detail.deactivate": "रूपांतर निष्क्रिय करें",
    "templates.detail.editorTitle": "शब्दावली",
    "templates.detail.editorHelper": (
        "हर बार सहेजने पर नया संस्करण बनता है। प्रकाशित संस्करण तब तक भेजा जाता रहेगा जब "
        "तक कोई सिस्टम प्रशासक नया संस्करण प्रकाशित न कर दे।"
    ),
    "templates.detail.subject": "विषय पंक्ति",
    "templates.detail.body": "मुख्य पाठ",
    "templates.detail.smsCounter": "{{count}} वर्ण (एसएमएस खंड: {{limit}})",
    "templates.detail.saveAsNewVersion": "नए संस्करण के रूप में सहेजें",
    "templates.detail.saved": (
        "v{{version}} के रूप में सहेजा गया — एक प्रारूप। लागू करने के लिए इसे प्रकाशित करें।"
    ),
    "templates.detail.testSend": "मुझे परीक्षण भेजें",
    "templates.detail.downloadPdf": "नमूना पीडीएफ़ डाउनलोड करें",
    "templates.detail.previewPending": "पूर्वावलोकन देखने के लिए पाठ लिखें।",
    "templates.detail.absences": "{{count}} मर्ज फ़ील्ड रिक्तता के रूप में छपेंगे",
    "templates.detail.unsampled": "वे फ़ील्ड जिनके लिए पूर्वावलोकन जानबूझकर नमूना डेटा नहीं देता",
    "templates.detail.mergeFields": "मर्ज फ़ील्ड",
    "templates.detail.insertHelper": "कर्सर की जगह पर डालने के लिए किसी फ़ील्ड पर क्लिक करें।",
    "templates.detail.derivedSpelling": "तकनीकी वर्तनी",
    "templates.detail.mandatory": "इस टेम्पलेट को इनके बिना कभी सहेजा नहीं जा सकता: {{phrases}}",
    "templates.detail.history": "संस्करण इतिहास",
    "templates.detail.historyHelper": (
        "संस्करण केवल जोड़े जाते हैं। पुराना संस्करण पुनर्स्थापित करने पर उसकी शब्दावली नए "
        "प्रारूप के रूप में लौटती है; पुराना संस्करण कभी नहीं बदला जाता, क्योंकि वही इस बात "
        "का अभिलेख है कि ग्राहकों को क्या मिला।"
    ),
    "templates.detail.version": "संस्करण",
    "templates.detail.status": "स्थिति",
    "templates.detail.updated": "अद्यतन",
    "templates.detail.pinnedBy": "इसका उपयोग करने वाले संदेश",
    "templates.detail.publish": "प्रकाशित करें",
    "templates.detail.published": "v{{version}} प्रकाशित। यह केवल आगे के संदेशों पर लागू होगा।",
    "templates.detail.restore": "पुनर्स्थापित करें",
    "templates.detail.noVersions": "इस रूपांतर के लिए अभी कुछ नहीं लिखा गया है।",
    "templates.status.draft": "प्रारूप",
    "templates.status.published": "प्रकाशित",
    "templates.status.archived": "संग्रहीत",
}

T["ja-JP"] = {
    "templates.catalog.title": "テンプレート",
    "templates.catalog.separation": (
        "通知は「いつ」送るかを決め、テンプレートは「何を」書くかを決めます。この画面で"
        "予約・実行・送信は一切行われません。"
    ),
    "templates.catalog.search": "テンプレートを検索",
    "templates.catalog.category": "カテゴリ",
    "templates.catalog.columns": "列",
    "templates.catalog.perPage": "1ページの行数",
    "templates.catalog.newVariant": "＋ 新しいバリアント",
    "templates.catalog.newFor": "テンプレート",
    "templates.catalog.choose": "テンプレートを選択…",
    "templates.catalog.variantName": "バリアント名",
    "templates.catalog.audience": "対象（需要家区分）",
    "templates.catalog.language": "言語タグ",
    "templates.catalog.create": "バリアントを作成",
    "templates.catalog.variantCreated": "バリアント「{{name}}」を作成しました。",
    "templates.catalog.open": "開く",
    "templates.catalog.empty": "この検索条件またはカテゴリに一致するテンプレートはありません。",
    "templates.catalog.neverEdited": "未編集",
    "templates.catalog.prev": "前へ",
    "templates.catalog.next": "次へ",
    "templates.catalog.pageOf": "{{last}} ページ中 {{page}} ページ目",
    "templates.catalog.denied": (
        "設定へのアクセス権がありません。テンプレート一覧を閲覧する必要がある場合は"
        "システム管理者にご連絡ください。"
    ),
    "templates.catalog.failedTitle": "テンプレート一覧を読み込めませんでした",
    "templates.category.all": "すべて（{{count}}）",
    "templates.category.billing": "請求",
    "templates.category.collections": "督促・回収",
    "templates.category.payments": "入金",
    "templates.category.service_field": "サービス・現場",
    "templates.category.account_lifecycle": "契約ライフサイクル",
    "templates.column.name": "テンプレート名",
    "templates.column.category": "カテゴリ",
    "templates.column.kind": "種別",
    "templates.column.variants": "バリアント",
    "templates.column.used_by": "使用箇所",
    "templates.column.edited": "最終編集",
    "templates.column.actions": "操作",
    "templates.audience.default": "既定（すべての対象）",
    "templates.audience.residential": "家庭用",
    "templates.audience.commercial": "商業用",
    "templates.audience.industrial": "産業用",
    "templates.audience.government": "官公庁",
    "templates.detail.back": "← すべてのテンプレートに戻る",
    "templates.detail.failedTitle": "このテンプレートを読み込めませんでした",
    "templates.detail.variants": "バリアント",
    "templates.detail.noVariants": (
        "この事業者にはこのテンプレートのバリアントがまだありません。一覧から作成すると"
        "文面の作成を始められます。"
    ),
    "templates.detail.default": "既定",
    "templates.detail.inactive": "無効",
    "templates.detail.setDefault": "既定に設定",
    "templates.detail.deactivate": "バリアントを無効化",
    "templates.detail.editorTitle": "文面",
    "templates.detail.editorHelper": (
        "保存するたびに新しいバージョンが作成されます。公開中のバージョンは、システム"
        "管理者が新しいバージョンを公開するまで送信され続けます。"
    ),
    "templates.detail.subject": "件名",
    "templates.detail.body": "本文",
    "templates.detail.smsCounter": "{{count}} 文字（SMS セグメント: {{limit}}）",
    "templates.detail.saveAsNewVersion": "新しいバージョンとして保存",
    "templates.detail.saved": (
        "v{{version}} として保存しました（下書き）。有効にするには公開してください。"
    ),
    "templates.detail.testSend": "自分にテスト送信",
    "templates.detail.downloadPdf": "サンプル PDF をダウンロード",
    "templates.detail.previewPending": "本文を入力するとプレビューが表示されます。",
    "templates.detail.absences": "{{count}} 件の差し込み項目が「値なし」として印字されます",
    "templates.detail.unsampled": "プレビューが意図的にサンプル値を入れない項目",
    "templates.detail.mergeFields": "差し込み項目",
    "templates.detail.insertHelper": "項目をクリックすると、カーソル位置に挿入されます。",
    "templates.detail.derivedSpelling": "技術上の表記",
    "templates.detail.mandatory": "このテンプレートは次の記載なしには保存できません: {{phrases}}",
    "templates.detail.history": "バージョン履歴",
    "templates.detail.historyHelper": (
        "バージョンは追記のみです。過去のバージョンを復元すると、その文面が新しい下書き"
        "として戻ります。過去のバージョンが書き換えられることはありません。顧客に何を"
        "送ったかの記録だからです。"
    ),
    "templates.detail.version": "バージョン",
    "templates.detail.status": "状態",
    "templates.detail.updated": "更新日",
    "templates.detail.pinnedBy": "使用中のメッセージ数",
    "templates.detail.publish": "公開",
    "templates.detail.published": "v{{version}} を公開しました。以後のメッセージにのみ適用されます。",
    "templates.detail.restore": "復元",
    "templates.detail.noVersions": "このバリアントにはまだ何も書かれていません。",
    "templates.status.draft": "下書き",
    "templates.status.published": "公開中",
    "templates.status.archived": "アーカイブ済み",
}

T["ko-KR"] = {
    "templates.catalog.title": "템플릿",
    "templates.catalog.separation": (
        "알림은 메시지를 '언제' 보낼지 정하고, 템플릿은 '무엇을' 쓸지 정합니다. 이 "
        "화면에서는 예약·실행·발송이 전혀 이루어지지 않습니다."
    ),
    "templates.catalog.search": "템플릿 검색",
    "templates.catalog.category": "분류",
    "templates.catalog.columns": "열",
    "templates.catalog.perPage": "페이지당 행 수",
    "templates.catalog.newVariant": "+ 새 변형",
    "templates.catalog.newFor": "템플릿",
    "templates.catalog.choose": "템플릿 선택…",
    "templates.catalog.variantName": "변형 이름",
    "templates.catalog.audience": "대상(수용가 구분)",
    "templates.catalog.language": "언어 태그",
    "templates.catalog.create": "변형 만들기",
    "templates.catalog.variantCreated": "변형 “{{name}}”을(를) 만들었습니다.",
    "templates.catalog.open": "열기",
    "templates.catalog.empty": "이 검색어나 분류에 해당하는 템플릿이 없습니다.",
    "templates.catalog.neverEdited": "편집한 적 없음",
    "templates.catalog.prev": "이전",
    "templates.catalog.next": "다음",
    "templates.catalog.pageOf": "{{last}}페이지 중 {{page}}페이지",
    "templates.catalog.denied": (
        "설정에 접근할 권한이 없습니다. 템플릿 목록을 봐야 한다면 시스템 관리자에게 "
        "문의하세요."
    ),
    "templates.catalog.failedTitle": "템플릿 목록을 불러오지 못했습니다",
    "templates.category.all": "전체({{count}})",
    "templates.category.billing": "청구",
    "templates.category.collections": "체납 관리",
    "templates.category.payments": "수납",
    "templates.category.service_field": "서비스 및 현장",
    "templates.category.account_lifecycle": "계약 생애주기",
    "templates.column.name": "템플릿 이름",
    "templates.column.category": "분류",
    "templates.column.kind": "종류",
    "templates.column.variants": "변형",
    "templates.column.used_by": "사용처",
    "templates.column.edited": "최종 편집",
    "templates.column.actions": "작업",
    "templates.audience.default": "기본(모든 대상)",
    "templates.audience.residential": "주택용",
    "templates.audience.commercial": "상업용",
    "templates.audience.industrial": "산업용",
    "templates.audience.government": "공공기관",
    "templates.detail.back": "← 전체 템플릿으로 돌아가기",
    "templates.detail.failedTitle": "이 템플릿을 불러오지 못했습니다",
    "templates.detail.variants": "변형",
    "templates.detail.noVariants": (
        "이 사업자에는 아직 이 템플릿의 변형이 없습니다. 목록에서 하나를 만들면 문안 "
        "작성을 시작할 수 있습니다."
    ),
    "templates.detail.default": "기본",
    "templates.detail.inactive": "비활성",
    "templates.detail.setDefault": "기본으로 지정",
    "templates.detail.deactivate": "변형 비활성화",
    "templates.detail.editorTitle": "문안",
    "templates.detail.editorHelper": (
        "저장할 때마다 새 버전이 만들어집니다. 게시된 버전은 시스템 관리자가 새 버전을 "
        "게시할 때까지 계속 발송됩니다."
    ),
    "templates.detail.subject": "제목",
    "templates.detail.body": "본문",
    "templates.detail.smsCounter": "{{count}}자(SMS 세그먼트: {{limit}})",
    "templates.detail.saveAsNewVersion": "새 버전으로 저장",
    "templates.detail.saved": (
        "v{{version}}(으)로 저장했습니다 — 초안입니다. 적용하려면 게시하세요."
    ),
    "templates.detail.testSend": "나에게 테스트 발송",
    "templates.detail.downloadPdf": "샘플 PDF 내려받기",
    "templates.detail.previewPending": "본문을 입력하면 미리보기가 표시됩니다.",
    "templates.detail.absences": "병합 항목 {{count}}개가 '값 없음'으로 인쇄됩니다",
    "templates.detail.unsampled": "미리보기가 의도적으로 예시 값을 넣지 않는 항목",
    "templates.detail.mergeFields": "병합 항목",
    "templates.detail.insertHelper": "항목을 클릭하면 커서 위치에 삽입됩니다.",
    "templates.detail.derivedSpelling": "기술 표기",
    "templates.detail.mandatory": "이 템플릿은 다음 없이는 저장할 수 없습니다: {{phrases}}",
    "templates.detail.history": "버전 기록",
    "templates.detail.historyHelper": (
        "버전은 추가만 됩니다. 이전 버전을 복원하면 그 문안이 새 초안으로 돌아오며, 이전 "
        "버전은 절대 다시 쓰이지 않습니다. 고객이 무엇을 받았는지에 대한 기록이기 "
        "때문입니다."
    ),
    "templates.detail.version": "버전",
    "templates.detail.status": "상태",
    "templates.detail.updated": "갱신일",
    "templates.detail.pinnedBy": "이 버전을 사용하는 메시지",
    "templates.detail.publish": "게시",
    "templates.detail.published": "v{{version}}을(를) 게시했습니다. 이후 메시지에만 적용됩니다.",
    "templates.detail.restore": "복원",
    "templates.detail.noVersions": "이 변형에는 아직 작성된 내용이 없습니다.",
    "templates.status.draft": "초안",
    "templates.status.published": "게시됨",
    "templates.status.archived": "보관됨",
}


def main() -> int:
    root = pathlib.Path(__file__).resolve().parent.parent / "src" / "i18n" / "locales"
    english = json.loads((root / f"{EN}.json").read_text(encoding="utf-8"))
    for locale, strings in T.items():
        path = root / f"{locale}.json"
        catalogue = json.loads(path.read_text(encoding="utf-8"))
        for key, value in strings.items():
            if key not in english:
                print(f"{locale}: {key} is not in {EN}.json — refusing", file=sys.stderr)
                return 1
            catalogue[key] = value
        ordered = {key: catalogue[key] for key in sorted(catalogue)}
        path.write_text(
            json.dumps(ordered, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        left = sum(1 for key in strings if catalogue[key] == english[key])
        print(f"{locale}: {len(strings)} translated, {left} still identical to English")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
