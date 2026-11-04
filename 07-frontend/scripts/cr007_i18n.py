"""CR-007 · add SET-09/SET-10 strings to all eleven locale catalogues.

NFR-37 / the repo's i18n rule: a key exists in every locale or it exists
nowhere — a missing key renders the raw key id to a user. The ENGLISH string is
written into all eleven, which is this repo's convention for a new surface:
translation is a later pass, and an English sentence is a readable fallback
while a bare `templates.detail.publish` is not.

**No existing key is read, moved or rewritten** — the script refuses to
overwrite one, so it cannot quietly change a string another lane owns.
"""

import json
import pathlib
import sys

STRINGS = {
    "templates.catalog.title": "Templates",
    "templates.catalog.separation": (
        "Notifications decide WHEN a message goes out. Templates define WHAT it says. "
        "Nothing on this screen schedules, triggers or sends anything."
    ),
    "templates.catalog.search": "Search templates",
    "templates.catalog.category": "Category",
    "templates.catalog.columns": "Columns",
    "templates.catalog.perPage": "Rows per page",
    "templates.catalog.newVariant": "+ New variant",
    "templates.catalog.newFor": "Template",
    "templates.catalog.choose": "Choose a template…",
    "templates.catalog.variantName": "Variant name",
    "templates.catalog.audience": "Audience (consumer category)",
    "templates.catalog.language": "Language tag",
    "templates.catalog.create": "Create variant",
    "templates.catalog.variantCreated": "Variant “{{name}}” created.",
    "templates.catalog.open": "Open",
    "templates.catalog.empty": "No template matches this search or category.",
    "templates.catalog.neverEdited": "Never edited",
    "templates.catalog.prev": "Previous",
    "templates.catalog.next": "Next",
    "templates.catalog.pageOf": "Page {{page}} of {{last}}",
    "templates.catalog.denied": (
        "You do not have access to Settings. Ask a System Admin if you need to read the "
        "template catalog."
    ),
    "templates.catalog.failedTitle": "The template catalog could not be loaded",
    "templates.category.all": "All ({{count}})",
    "templates.category.billing": "Billing",
    "templates.category.collections": "Collections",
    "templates.category.payments": "Payments",
    "templates.category.service_field": "Service & field",
    "templates.category.account_lifecycle": "Account lifecycle",
    "templates.column.name": "Template name",
    "templates.column.category": "Category",
    "templates.column.kind": "Kind",
    "templates.column.variants": "Variants",
    "templates.column.used_by": "Used by",
    "templates.column.edited": "Last edited",
    "templates.column.actions": "Actions",
    "templates.audience.default": "Default (every audience)",
    "templates.audience.residential": "Residential",
    "templates.audience.commercial": "Commercial",
    "templates.audience.industrial": "Industrial",
    "templates.audience.government": "Government",
    "templates.detail.back": "← Back to all templates",
    "templates.detail.failedTitle": "This template could not be loaded",
    "templates.detail.variants": "Variants",
    "templates.detail.noVariants": (
        "This template has no variant on this utility yet. Create one from the catalog to "
        "start writing it."
    ),
    "templates.detail.default": "Default",
    "templates.detail.inactive": "Inactive",
    "templates.detail.setDefault": "Set as default",
    "templates.detail.deactivate": "Deactivate variant",
    "templates.detail.editorTitle": "Wording",
    "templates.detail.editorHelper": (
        "Every save creates a new version. The published version keeps going out until a "
        "System Admin publishes the new one."
    ),
    "templates.detail.subject": "Subject line",
    "templates.detail.body": "Body",
    "templates.detail.smsCounter": "{{count}} characters (SMS segment: {{limit}})",
    "templates.detail.saveAsNewVersion": "Save as new version",
    "templates.detail.saved": "Saved as v{{version}} — a draft. Publish it to make it live.",
    "templates.detail.testSend": "Send test to me",
    "templates.detail.downloadPdf": "Download sample PDF",
    "templates.detail.previewPending": "Type a body to see it render.",
    "templates.detail.absences": "{{count}} merge field(s) will print as an absence",
    "templates.detail.unsampled": "Fields the preview deliberately does not sample",
    "templates.detail.mergeFields": "Merge fields",
    "templates.detail.insertHelper": "Click a field to insert it where the cursor is.",
    "templates.detail.derivedSpelling": "engineering spelling",
    "templates.detail.mandatory": "This template may never be saved without: {{phrases}}",
    "templates.detail.history": "Version history",
    "templates.detail.historyHelper": (
        "Versions are append-only. Restoring an old version brings its wording back as a "
        "new draft; the old version is never rewritten, because it is the record of what "
        "customers were sent."
    ),
    "templates.detail.version": "Version",
    "templates.detail.status": "Status",
    "templates.detail.updated": "Updated",
    "templates.detail.pinnedBy": "Messages using it",
    "templates.detail.publish": "Publish",
    "templates.detail.published": "v{{version}} published. It applies to future messages only.",
    "templates.detail.restore": "Restore",
    "templates.detail.noVersions": "Nothing has been written for this variant yet.",
    "templates.status.draft": "Draft",
    "templates.status.published": "Published",
    "templates.status.archived": "Archived",
}


def main() -> int:
    root = pathlib.Path(__file__).resolve().parent.parent / "src" / "i18n" / "locales"
    files = sorted(root.glob("*.json"))
    if len(files) != 11:
        print(f"expected 11 locale files, found {len(files)}", file=sys.stderr)
        return 1
    for path in files:
        catalogue = json.loads(path.read_text(encoding="utf-8"))
        clashes = [key for key in STRINGS if key in catalogue]
        if clashes:
            # Never overwrite a string another lane owns.
            print(f"{path.name}: refusing, keys already present: {clashes}", file=sys.stderr)
            return 1
        catalogue.update(STRINGS)
        ordered = {key: catalogue[key] for key in sorted(catalogue)}
        path.write_text(
            json.dumps(ordered, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(f"{path.name}: +{len(STRINGS)} keys")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
