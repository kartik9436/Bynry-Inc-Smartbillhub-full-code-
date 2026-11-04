"""CR-007 · the five backend `message_key`s the templates API mints.

**Found by G18, not by a reviewer, and it was a real hole:** an endpoint that
raises a catalog error with `message_key="notifications.templates.refused"` and
no catalogue entry for it renders **the raw key id to a user** — the screen
would print `notifications.templates.refused` where the refusal should be. G18
names exactly that: *"key(s) used in code and defined in NO catalogue (renders
raw to a user)"*.

Each of these is a WRAPPER sentence. The refusal's own words travel in
`params.detail` — the server's sentence, which names the rule and the fix — and
the catalogue string is the frame around it, exactly as
`notifications.dispatch.refused` already works.
"""

import json
import pathlib
import sys

KEYS: dict[str, dict[str, str]] = {
    "notifications.templates.refused": {
        "en": "That template change was refused.",
        "de": "Diese Vorlagenänderung wurde abgelehnt.",
        "es": "Ese cambio de plantilla fue rechazado.",
        "es-MX": "Ese cambio de plantilla fue rechazado.",
        "fr-FR": "Cette modification de modèle a été refusée.",
        "hi": "टेम्पलेट में यह परिवर्तन अस्वीकार कर दिया गया।",
        "id-ID": "Perubahan templat itu ditolak.",
        "it-IT": "Questa modifica al modello è stata rifiutata.",
        "ja-JP": "そのテンプレートの変更は受け付けられませんでした。",
        "ko-KR": "해당 템플릿 변경은 거부되었습니다.",
        "pt-BR": "Essa alteração de modelo foi recusada.",
    },
    "notifications.templates.bodyRequired": {
        "en": "Write the body before saving.",
        "de": "Schreiben Sie den Textkörper, bevor Sie speichern.",
        "es": "Escriba el cuerpo antes de guardar.",
        "es-MX": "Escribe el cuerpo antes de guardar.",
        "fr-FR": "Rédigez le corps avant d'enregistrer.",
        "hi": "सहेजने से पहले मुख्य पाठ लिखें।",
        "id-ID": "Tulis isinya sebelum menyimpan.",
        "it-IT": "Scrivi il corpo prima di salvare.",
        "ja-JP": "保存する前に本文を入力してください。",
        "ko-KR": "저장하기 전에 본문을 작성하세요.",
        "pt-BR": "Escreva o corpo antes de salvar.",
    },
    "notifications.templates.nameRequired": {
        "en": "Give the variant a name.",
        "de": "Geben Sie der Variante einen Namen.",
        "es": "Dé un nombre a la variante.",
        "es-MX": "Dale un nombre a la variante.",
        "fr-FR": "Donnez un nom à la variante.",
        "hi": "रूपांतर को कोई नाम दें।",
        "id-ID": "Beri nama untuk varian ini.",
        "it-IT": "Assegna un nome alla variante.",
        "ja-JP": "バリアントに名前を付けてください。",
        "ko-KR": "변형에 이름을 지정하세요.",
        "pt-BR": "Dê um nome à variante.",
    },
    "notifications.templates.variantRequired": {
        "en": "Choose which variant this applies to.",
        "de": "Wählen Sie, für welche Variante dies gilt.",
        "es": "Elija a qué variante se aplica esto.",
        "es-MX": "Elige a qué variante se aplica esto.",
        "fr-FR": "Choisissez la variante concernée.",
        "hi": "चुनें कि यह किस रूपांतर पर लागू होता है।",
        "id-ID": "Pilih varian mana yang berlaku untuk ini.",
        "it-IT": "Scegli a quale variante si riferisce.",
        "ja-JP": "どのバリアントに対する操作かを選択してください。",
        "ko-KR": "어느 변형에 적용할지 선택하세요.",
        "pt-BR": "Escolha a qual variante isto se aplica.",
    },
    "notifications.templates.versionRequired": {
        "en": "Choose which version this applies to.",
        "de": "Wählen Sie, für welche Fassung dies gilt.",
        "es": "Elija a qué versión se aplica esto.",
        "es-MX": "Elige a qué versión se aplica esto.",
        "fr-FR": "Choisissez la version concernée.",
        "hi": "चुनें कि यह किस संस्करण पर लागू होता है।",
        "id-ID": "Pilih versi mana yang berlaku untuk ini.",
        "it-IT": "Scegli a quale versione si riferisce.",
        "ja-JP": "どのバージョンに対する操作かを選択してください。",
        "ko-KR": "어느 버전에 적용할지 선택하세요.",
        "pt-BR": "Escolha a qual versão isto se aplica.",
    },
}


def main() -> int:
    root = pathlib.Path(__file__).resolve().parent.parent / "src" / "i18n" / "locales"
    for path in sorted(root.glob("*.json")):
        locale = path.stem
        catalogue = json.loads(path.read_text(encoding="utf-8"))
        added = 0
        for key, byLocale in KEYS.items():
            if key in catalogue:
                print(f"{path.name}: {key} already present — refusing", file=sys.stderr)
                return 1
            if locale not in byLocale:
                print(f"{path.name}: no string for {key} — refusing", file=sys.stderr)
                return 1
            catalogue[key] = byLocale[locale]
            added += 1
        ordered = {key: catalogue[key] for key in sorted(catalogue)}
        path.write_text(
            json.dumps(ordered, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(f"{path.name}: +{added} keys")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
