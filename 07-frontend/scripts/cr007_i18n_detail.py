"""CR-007 · the six strings the PO's SET-10.corrected shape added (2026-08-17).

The right rail's two-column merge-field panel, the "Where it's used" panel and
the preview header strip. Translated rather than left in English, for the reason
`cr007_i18n_translate.py` records: G15 fails a value byte-identical to English,
because the key resolves and the page reverts to English mid-card.
"""

import json
import pathlib
import sys

KEYS: dict[str, dict[str, str]] = {
    "templates.detail.field": {
        "en": "Field",
        "de": "Feld",
        "es": "Campo",
        "es-MX": "Campo",
        "fr-FR": "Champ",
        "hi": "फ़ील्ड",
        "id-ID": "Kolom",
        "it-IT": "Campo",
        "ja-JP": "項目",
        "ko-KR": "항목",
        "pt-BR": "Campo",
    },
    "templates.detail.sampleValue": {
        "en": "Sample value",
        "de": "Beispielwert",
        "es": "Valor de muestra",
        "es-MX": "Valor de muestra",
        "fr-FR": "Valeur d'exemple",
        "hi": "नमूना मान",
        "id-ID": "Nilai contoh",
        "it-IT": "Valore di esempio",
        "ja-JP": "サンプル値",
        "ko-KR": "예시 값",
        "pt-BR": "Valor de exemplo",
    },
    "templates.detail.whereUsed": {
        "en": "Where it's used",
        "de": "Wo sie verwendet wird",
        "es": "Dónde se usa",
        "es-MX": "Dónde se usa",
        "fr-FR": "Où il est utilisé",
        "hi": "कहाँ प्रयोग होती है",
        "id-ID": "Di mana dipakai",
        "it-IT": "Dove viene usato",
        "ja-JP": "使用箇所",
        "ko-KR": "사용되는 곳",
        "pt-BR": "Onde é usado",
    },
    "templates.detail.previewingAs": {
        "en": "Previewing as",
        "de": "Vorschau als",
        "es": "Vista previa como",
        "es-MX": "Vista previa como",
        "fr-FR": "Aperçu en tant que",
        "hi": "पूर्वावलोकन इस रूप में",
        "id-ID": "Pratinjau sebagai",
        "it-IT": "Anteprima come",
        "ja-JP": "プレビュー表示",
        "ko-KR": "미리보기 형식",
        "pt-BR": "Pré-visualizando como",
    },
    "templates.detail.sampleDataIs": {
        "en": "sample data: {{customer}} · {{account}}",
        "de": "Beispieldaten: {{customer}} · {{account}}",
        "es": "datos de muestra: {{customer}} · {{account}}",
        "es-MX": "datos de muestra: {{customer}} · {{account}}",
        "fr-FR": "données d'exemple : {{customer}} · {{account}}",
        "hi": "नमूना डेटा: {{customer}} · {{account}}",
        "id-ID": "data contoh: {{customer}} · {{account}}",
        "it-IT": "dati di esempio: {{customer}} · {{account}}",
        "ja-JP": "サンプルデータ: {{customer}} · {{account}}",
        "ko-KR": "예시 데이터: {{customer}} · {{account}}",
        "pt-BR": "dados de exemplo: {{customer}} · {{account}}",
    },
    "templates.detail.defaultVariantPill": {
        "en": "Default variant",
        "de": "Standardvariante",
        "es": "Variante predeterminada",
        "es-MX": "Variante predeterminada",
        "fr-FR": "Variante par défaut",
        "hi": "डिफ़ॉल्ट रूपांतर",
        "id-ID": "Varian bawaan",
        "it-IT": "Variante predefinita",
        "ja-JP": "既定のバリアント",
        "ko-KR": "기본 변형",
        "pt-BR": "Variante padrão",
    },
}


def main() -> int:
    root = pathlib.Path(__file__).resolve().parent.parent / "src" / "i18n" / "locales"
    for path in sorted(root.glob("*.json")):
        locale = path.stem
        catalogue = json.loads(path.read_text(encoding="utf-8"))
        for key, byLocale in KEYS.items():
            if key in catalogue:
                print(f"{path.name}: {key} already present — refusing", file=sys.stderr)
                return 1
            catalogue[key] = byLocale[locale]
        ordered = {key: catalogue[key] for key in sorted(catalogue)}
        path.write_text(
            json.dumps(ordered, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(f"{path.name}: +{len(KEYS)} keys")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
