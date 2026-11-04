#!/usr/bin/env python3
"""CR-067 task C1 — insert the seventeen `audit.diagnostic.*` keys IN PLACE.

⚠ IT INSERTS AND IT NEVER RE-SORTS. The DEF-2375 lane's own handover names the
trap: its first draft re-sorted the catalogues alphabetically and silently
destroyed the provisioning steps' RUN order — "no byte lost, and information
lost anyway", caught only by reading the numstat as arithmetic. So this script
finds ONE anchor line per file and writes the new lines after it; every other
line is copied through untouched, and the caller must see 17 insertions and 0
deletions in each of the eleven.

⚠ AND IT BUILDS THE WHOLE FILE BEFORE IT OPENS THE DESTINATION (CLAUDE.md law
11's near-miss: a repair script that opened its output first truncated CLAUDE.md
to zero bytes when its read failed).

Throwaway: delete it with the lane's own housekeeping if it is still here.
"""

import json
import pathlib
import sys

ANCHOR = '  "audit.denied":'

TRANSLATIONS = {
    "en": {
        "audit.diagnostic.advice": "What to do",
        "audit.diagnostic.adviceKnockOn": "An earlier step failed first, so fix that one and run this again.",
        "audit.diagnostic.adviceRoot": "This is where it started, and the screen that ran it has the full wording.",
        "audit.diagnostic.copied": "Copied",
        "audit.diagnostic.copy": "Copy",
        "audit.diagnostic.doing": "What was running",
        "audit.diagnostic.gapBody": "The exception, the code it came from, the step of the job, the release and the settings in force are kept beside this entry for 90 days, and nothing reads them onto a screen yet.",
        "audit.diagnostic.gapTitle": "The full technical record is not on this screen yet",
        "audit.diagnostic.reference": "Reference",
        "audit.diagnostic.result": "Result",
        "audit.diagnostic.resultFailed": "Stopped before it finished",
        "audit.diagnostic.techCode": "Error code",
        "audit.diagnostic.techEvent": "Event",
        "audit.diagnostic.techRoot": "Started at",
        "audit.diagnostic.techTitle": "Technical detail",
        "audit.diagnostic.techWhere": "Where",
        "audit.diagnostic.title": "Why this failed",
    },
    "de": {
        "audit.diagnostic.advice": "Was zu tun ist",
        "audit.diagnostic.adviceKnockOn": "Ein früherer Schritt ist zuerst fehlgeschlagen; beheben Sie diesen und starten Sie diesen hier erneut.",
        "audit.diagnostic.adviceRoot": "Hier hat es begonnen, und den vollständigen Wortlaut zeigt der Bildschirm, der es ausgeführt hat.",
        "audit.diagnostic.copied": "Kopiert",
        "audit.diagnostic.copy": "Kopieren",
        "audit.diagnostic.doing": "Was lief",
        "audit.diagnostic.gapBody": "Die Ausnahme, der Code, aus dem sie stammt, der Schritt des Auftrags, die Version und die geltenden Einstellungen werden 90 Tage lang neben diesem Eintrag aufbewahrt, und noch nichts zeigt sie auf einem Bildschirm an.",
        "audit.diagnostic.gapTitle": "Der vollständige technische Datensatz ist noch nicht auf diesem Bildschirm",
        "audit.diagnostic.reference": "Referenz",
        "audit.diagnostic.result": "Ergebnis",
        "audit.diagnostic.resultFailed": "Vor dem Abschluss abgebrochen",
        "audit.diagnostic.techCode": "Fehlercode",
        "audit.diagnostic.techEvent": "Ereignis",
        "audit.diagnostic.techRoot": "Begonnen bei",
        "audit.diagnostic.techTitle": "Technische Details",
        "audit.diagnostic.techWhere": "Wo",
        "audit.diagnostic.title": "Warum dies fehlgeschlagen ist",
    },
    "es": {
        "audit.diagnostic.advice": "Qué hacer",
        "audit.diagnostic.adviceKnockOn": "Un paso anterior falló primero, así que corrige ese y vuelve a ejecutar este.",
        "audit.diagnostic.adviceRoot": "Aquí es donde empezó, y la pantalla que lo ejecutó tiene el texto completo.",
        "audit.diagnostic.copied": "Copiado",
        "audit.diagnostic.copy": "Copiar",
        "audit.diagnostic.doing": "Qué se estaba ejecutando",
        "audit.diagnostic.gapBody": "La excepción, el código del que proviene, el paso del trabajo, la versión y los ajustes vigentes se guardan junto a esta entrada durante 90 días, y todavía nada los muestra en una pantalla.",
        "audit.diagnostic.gapTitle": "El registro técnico completo aún no está en esta pantalla",
        "audit.diagnostic.reference": "Referencia",
        "audit.diagnostic.result": "Resultado",
        "audit.diagnostic.resultFailed": "Se detuvo antes de terminar",
        "audit.diagnostic.techCode": "Código de error",
        "audit.diagnostic.techEvent": "Evento",
        "audit.diagnostic.techRoot": "Empezó en",
        "audit.diagnostic.techTitle": "Detalle técnico",
        "audit.diagnostic.techWhere": "Dónde",
        "audit.diagnostic.title": "Por qué falló",
    },
    "es-MX": {
        "audit.diagnostic.advice": "Qué hacer",
        "audit.diagnostic.adviceKnockOn": "Un paso anterior falló primero, así que corrige ese y vuelve a ejecutar este.",
        "audit.diagnostic.adviceRoot": "Aquí fue donde empezó, y la pantalla que lo ejecutó tiene el texto completo.",
        "audit.diagnostic.copied": "Copiado",
        "audit.diagnostic.copy": "Copiar",
        "audit.diagnostic.doing": "Qué se estaba ejecutando",
        "audit.diagnostic.gapBody": "La excepción, el código del que proviene, el paso del trabajo, la versión y los ajustes vigentes se guardan junto a esta entrada durante 90 días, y todavía nada los muestra en una pantalla.",
        "audit.diagnostic.gapTitle": "El registro técnico completo aún no está en esta pantalla",
        "audit.diagnostic.reference": "Referencia",
        "audit.diagnostic.result": "Resultado",
        "audit.diagnostic.resultFailed": "Se detuvo antes de terminar",
        "audit.diagnostic.techCode": "Código de error",
        "audit.diagnostic.techEvent": "Evento",
        "audit.diagnostic.techRoot": "Empezó en",
        "audit.diagnostic.techTitle": "Detalle técnico",
        "audit.diagnostic.techWhere": "Dónde",
        "audit.diagnostic.title": "Por qué falló",
    },
    "fr-FR": {
        "audit.diagnostic.advice": "Que faire",
        "audit.diagnostic.adviceKnockOn": "Une étape antérieure a échoué en premier ; corrigez celle-là puis relancez celle-ci.",
        "audit.diagnostic.adviceRoot": "C'est ici que cela a commencé, et l'écran qui l'a lancé contient le texte complet.",
        "audit.diagnostic.copied": "Copié",
        "audit.diagnostic.copy": "Copier",
        "audit.diagnostic.doing": "Ce qui était en cours",
        "audit.diagnostic.gapBody": "L'exception, le code dont elle provient, l'étape du travail, la version et les réglages en vigueur sont conservés à côté de cette entrée pendant 90 jours, et rien ne les affiche encore à l'écran.",
        "audit.diagnostic.gapTitle": "L'enregistrement technique complet n'est pas encore sur cet écran",
        "audit.diagnostic.reference": "Référence",
        "audit.diagnostic.result": "Résultat",
        "audit.diagnostic.resultFailed": "Arrêté avant la fin",
        "audit.diagnostic.techCode": "Code d'erreur",
        "audit.diagnostic.techEvent": "Événement",
        "audit.diagnostic.techRoot": "Commencé à",
        "audit.diagnostic.techTitle": "Détail technique",
        "audit.diagnostic.techWhere": "Où",
        "audit.diagnostic.title": "Pourquoi cela a échoué",
    },
    "hi": {
        "audit.diagnostic.advice": "क्या करें",
        "audit.diagnostic.adviceKnockOn": "पहले का एक चरण पहले विफल हुआ था, इसलिए उसे ठीक करें और इसे दोबारा चलाएँ.",
        "audit.diagnostic.adviceRoot": "यहीं से शुरुआत हुई थी, और पूरा विवरण उसी स्क्रीन पर है जिसने इसे चलाया था.",
        "audit.diagnostic.copied": "कॉपी हो गया",
        "audit.diagnostic.copy": "कॉपी करें",
        "audit.diagnostic.doing": "क्या चल रहा था",
        "audit.diagnostic.gapBody": "अपवाद, वह कोड जहाँ से वह आया, कार्य का चरण, रिलीज़ और लागू सेटिंग्स इस प्रविष्टि के साथ 90 दिन तक रखी जाती हैं, और अभी तक कुछ भी उन्हें स्क्रीन पर नहीं दिखाता.",
        "audit.diagnostic.gapTitle": "पूरा तकनीकी रिकॉर्ड अभी इस स्क्रीन पर नहीं है",
        "audit.diagnostic.reference": "संदर्भ",
        "audit.diagnostic.result": "परिणाम",
        "audit.diagnostic.resultFailed": "पूरा होने से पहले रुक गया",
        "audit.diagnostic.techCode": "त्रुटि कोड",
        "audit.diagnostic.techEvent": "घटना",
        "audit.diagnostic.techRoot": "यहाँ से शुरू",
        "audit.diagnostic.techTitle": "तकनीकी विवरण",
        "audit.diagnostic.techWhere": "कहाँ",
        "audit.diagnostic.title": "यह क्यों विफल हुआ",
    },
    "id-ID": {
        "audit.diagnostic.advice": "Yang harus dilakukan",
        "audit.diagnostic.adviceKnockOn": "Langkah sebelumnya gagal lebih dulu, jadi perbaiki langkah itu lalu jalankan ini lagi.",
        "audit.diagnostic.adviceRoot": "Di sinilah awalnya, dan layar yang menjalankannya memuat keterangan lengkapnya.",
        "audit.diagnostic.copied": "Tersalin",
        "audit.diagnostic.copy": "Salin",
        "audit.diagnostic.doing": "Yang sedang berjalan",
        "audit.diagnostic.gapBody": "Eksepsi, kode asalnya, langkah pekerjaan, rilis, dan pengaturan yang berlaku disimpan di samping entri ini selama 90 hari, dan belum ada yang menampilkannya di layar.",
        "audit.diagnostic.gapTitle": "Catatan teknis lengkap belum ada di layar ini",
        "audit.diagnostic.reference": "Referensi",
        "audit.diagnostic.result": "Hasil",
        "audit.diagnostic.resultFailed": "Berhenti sebelum selesai",
        "audit.diagnostic.techCode": "Kode kesalahan",
        "audit.diagnostic.techEvent": "Peristiwa",
        "audit.diagnostic.techRoot": "Dimulai di",
        "audit.diagnostic.techTitle": "Rincian teknis",
        "audit.diagnostic.techWhere": "Di mana",
        "audit.diagnostic.title": "Mengapa ini gagal",
    },
    "it-IT": {
        "audit.diagnostic.advice": "Che cosa fare",
        "audit.diagnostic.adviceKnockOn": "Un passaggio precedente non è riuscito per primo, quindi correggi quello e riesegui questo.",
        "audit.diagnostic.adviceRoot": "È qui che è cominciato, e la schermata che lo ha avviato contiene il testo completo.",
        "audit.diagnostic.copied": "Copiato",
        "audit.diagnostic.copy": "Copia",
        "audit.diagnostic.doing": "Che cosa era in corso",
        "audit.diagnostic.gapBody": "L'eccezione, il codice da cui proviene, il passaggio del lavoro, la versione e le impostazioni in vigore sono conservati accanto a questa voce per 90 giorni, e nulla li mostra ancora su una schermata.",
        "audit.diagnostic.gapTitle": "Il registro tecnico completo non è ancora in questa schermata",
        "audit.diagnostic.reference": "Riferimento",
        "audit.diagnostic.result": "Esito",
        "audit.diagnostic.resultFailed": "Interrotto prima di finire",
        "audit.diagnostic.techCode": "Codice di errore",
        "audit.diagnostic.techEvent": "Evento",
        "audit.diagnostic.techRoot": "Iniziato a",
        "audit.diagnostic.techTitle": "Dettaglio tecnico",
        "audit.diagnostic.techWhere": "Dove",
        "audit.diagnostic.title": "Perché non è riuscito",
    },
    "ja-JP": {
        "audit.diagnostic.advice": "対応方法",
        "audit.diagnostic.adviceKnockOn": "先行するステップが先に失敗しているため、そちらを直してからこれを実行し直してください。",
        "audit.diagnostic.adviceRoot": "ここが起点で、詳しい説明は実行した画面にあります。",
        "audit.diagnostic.copied": "コピーしました",
        "audit.diagnostic.copy": "コピー",
        "audit.diagnostic.doing": "実行していた処理",
        "audit.diagnostic.gapBody": "例外、その発生元のコード、ジョブの手順、リリース、有効だった設定はこの記録の横に90日間保存されますが、それを画面に表示するものはまだありません。",
        "audit.diagnostic.gapTitle": "完全な技術記録はまだこの画面にありません",
        "audit.diagnostic.reference": "参照番号",
        "audit.diagnostic.result": "結果",
        "audit.diagnostic.resultFailed": "完了前に停止しました",
        "audit.diagnostic.techCode": "エラーコード",
        "audit.diagnostic.techEvent": "イベント",
        "audit.diagnostic.techRoot": "起点",
        "audit.diagnostic.techTitle": "技術情報",
        "audit.diagnostic.techWhere": "発生箇所",
        "audit.diagnostic.title": "失敗した理由",
    },
    "ko-KR": {
        "audit.diagnostic.advice": "조치 방법",
        "audit.diagnostic.adviceKnockOn": "앞선 단계가 먼저 실패했으므로 그 단계를 해결한 뒤 이 작업을 다시 실행하세요.",
        "audit.diagnostic.adviceRoot": "여기에서 시작되었으며, 자세한 설명은 이를 실행한 화면에 있습니다.",
        "audit.diagnostic.copied": "복사됨",
        "audit.diagnostic.copy": "복사",
        "audit.diagnostic.doing": "실행 중이던 작업",
        "audit.diagnostic.gapBody": "예외, 예외가 발생한 코드, 작업 단계, 릴리스, 적용 중이던 설정은 이 항목 옆에 90일 동안 보관되지만 아직 이를 화면에 보여 주는 기능은 없습니다.",
        "audit.diagnostic.gapTitle": "전체 기술 기록은 아직 이 화면에 없습니다",
        "audit.diagnostic.reference": "참조 번호",
        "audit.diagnostic.result": "결과",
        "audit.diagnostic.resultFailed": "완료되기 전에 중단됨",
        "audit.diagnostic.techCode": "오류 코드",
        "audit.diagnostic.techEvent": "이벤트",
        "audit.diagnostic.techRoot": "시작 지점",
        "audit.diagnostic.techTitle": "기술 세부 정보",
        "audit.diagnostic.techWhere": "위치",
        "audit.diagnostic.title": "실패한 이유",
    },
    "pt-BR": {
        "audit.diagnostic.advice": "O que fazer",
        "audit.diagnostic.adviceKnockOn": "Uma etapa anterior falhou primeiro, então corrija aquela e execute esta novamente.",
        "audit.diagnostic.adviceRoot": "Foi aqui que começou, e a tela que executou isto tem o texto completo.",
        "audit.diagnostic.copied": "Copiado",
        "audit.diagnostic.copy": "Copiar",
        "audit.diagnostic.doing": "O que estava em execução",
        "audit.diagnostic.gapBody": "A exceção, o código de onde ela veio, a etapa do trabalho, a versão e as configurações em vigor ficam guardadas ao lado desta entrada por 90 dias, e ainda nada as mostra em uma tela.",
        "audit.diagnostic.gapTitle": "O registro técnico completo ainda não está nesta tela",
        "audit.diagnostic.reference": "Referência",
        "audit.diagnostic.result": "Resultado",
        "audit.diagnostic.resultFailed": "Parou antes de terminar",
        "audit.diagnostic.techCode": "Código de erro",
        "audit.diagnostic.techEvent": "Evento",
        "audit.diagnostic.techRoot": "Começou em",
        "audit.diagnostic.techTitle": "Detalhe técnico",
        "audit.diagnostic.techWhere": "Onde",
        "audit.diagnostic.title": "Por que isto falhou",
    },
}


def main() -> int:
    root = pathlib.Path(__file__).resolve().parents[1] / "src" / "i18n" / "locales"
    for name, entries in TRANSLATIONS.items():
        path = root / f"{name}.json"
        original = path.read_text(encoding="utf-8")
        lines = original.splitlines(keepends=True)
        anchors = [index for index, line in enumerate(lines) if line.startswith(ANCHOR)]
        if len(anchors) != 1:
            print(f"{name}: expected exactly one anchor, found {len(anchors)}")
            return 1
        if any(f'"{key}"' in original for key in entries):
            print(f"{name}: a key is already present — refusing to write twice")
            return 1
        added = [
            f"  {json.dumps(key, ensure_ascii=False)}: {json.dumps(value, ensure_ascii=False)},\n"
            for key, value in sorted(entries.items())
        ]
        rebuilt = "".join(lines[: anchors[0] + 1] + added + lines[anchors[0] + 1 :])
        # Build it whole, prove it, THEN open the destination (law 11).
        if len(rebuilt) <= len(original):
            print(f"{name}: rebuilt file is not longer than the original — refusing")
            return 1
        parsed = json.loads(rebuilt)
        if len(parsed) != len(json.loads(original)) + len(entries):
            print(f"{name}: key count did not grow by {len(entries)}")
            return 1
        path.write_text(rebuilt, encoding="utf-8")
        print(f"{name}: +{len(added)} keys, inserted in place")
    return 0


if __name__ == "__main__":
    sys.exit(main())
