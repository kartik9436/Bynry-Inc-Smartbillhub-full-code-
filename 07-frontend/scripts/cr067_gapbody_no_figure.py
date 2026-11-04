#!/usr/bin/env python3
"""Take the ninety out of `audit.diagnostic.gapBody`, in all eleven catalogues.

⚠ **WHY THE FIGURE CAME OUT AGAIN THE SAME DAY IT WENT IN.** `OQ-1390` is OPEN —
*"is 90 days right, and does a diagnostic fall under `audit_log`'s retention
regime or its own?"* — and the prime directive is that a lane never resolves an
open question by choosing a value. Printing **90 days** on a screen in eleven
languages is choosing one, twice over: it states an unratified window as fact,
and `DIAGNOSTIC_RETENTION_DAYS` is a per-deployment setting the screen cannot
read, so a utility that sets 30 would be told 90 by its own product.

The sentence loses nothing that matters. What a System Admin needs from it is
that the technical record EXISTS, is kept beside this entry, does not last for
ever, and is not readable here yet. The window itself belongs to whoever answers
`OQ-1390`, and to a surface that can read the setting.

One value per file, replaced in place: 1 insertion / 1 deletion in each of the
eleven, nothing re-sorted.
"""

import json
import pathlib
import sys

KEY = "audit.diagnostic.gapBody"

REPLACEMENTS = {
    "en": "The exception, the code it came from, the step of the job, the release and the settings in force are kept beside this entry for a limited period, and nothing reads them onto a screen yet.",
    "de": "Die Ausnahme, der Code, aus dem sie stammt, der Schritt des Auftrags, die Version und die geltenden Einstellungen werden für eine begrenzte Zeit neben diesem Eintrag aufbewahrt, und noch nichts zeigt sie auf einem Bildschirm an.",
    "es": "La excepción, el código del que proviene, el paso del trabajo, la versión y los ajustes vigentes se guardan junto a esta entrada durante un tiempo limitado, y todavía nada los muestra en una pantalla.",
    "es-MX": "La excepción, el código del que proviene, el paso del trabajo, la versión y los ajustes vigentes se guardan junto a esta entrada durante un tiempo limitado, y todavía nada los muestra en una pantalla.",
    "fr-FR": "L'exception, le code dont elle provient, l'étape du travail, la version et les réglages en vigueur sont conservés à côté de cette entrée pendant une durée limitée, et rien ne les affiche encore à l'écran.",
    "hi": "अपवाद, वह कोड जहाँ से वह आया, कार्य का चरण, रिलीज़ और लागू सेटिंग्स इस प्रविष्टि के साथ सीमित समय तक रखी जाती हैं, और अभी तक कुछ भी उन्हें स्क्रीन पर नहीं दिखाता.",
    "id-ID": "Eksepsi, kode asalnya, langkah pekerjaan, rilis, dan pengaturan yang berlaku disimpan di samping entri ini untuk jangka waktu terbatas, dan belum ada yang menampilkannya di layar.",
    "it-IT": "L'eccezione, il codice da cui proviene, il passaggio del lavoro, la versione e le impostazioni in vigore sono conservati accanto a questa voce per un periodo limitato, e nulla li mostra ancora su una schermata.",
    "ja-JP": "例外、その発生元のコード、ジョブの手順、リリース、有効だった設定はこの記録の横に一定期間保存されますが、それを画面に表示するものはまだありません。",
    "ko-KR": "예외, 예외가 발생한 코드, 작업 단계, 릴리스, 적용 중이던 설정은 이 항목 옆에 일정 기간 보관되지만 아직 이를 화면에 보여 주는 기능은 없습니다.",
    "pt-BR": "A exceção, o código de onde ela veio, a etapa do trabalho, a versão e as configurações em vigor ficam guardadas ao lado desta entrada por um período limitado, e ainda nada as mostra em uma tela.",
}


def main() -> int:
    root = pathlib.Path(__file__).resolve().parents[1] / "src" / "i18n" / "locales"
    for name, value in REPLACEMENTS.items():
        path = root / f"{name}.json"
        original = path.read_text(encoding="utf-8")
        lines = original.splitlines(keepends=True)
        prefix = f"  {json.dumps(KEY, ensure_ascii=False)}: "
        hits = [index for index, line in enumerate(lines) if line.startswith(prefix)]
        if len(hits) != 1:
            print(f"{name}: expected one {KEY} line, found {len(hits)}")
            return 1
        lines[hits[0]] = prefix + json.dumps(value, ensure_ascii=False) + ",\n"
        rebuilt = "".join(lines)
        parsed = json.loads(rebuilt)
        if parsed[KEY] != value or len(parsed) != len(json.loads(original)):
            print(f"{name}: rebuilt catalogue is not what was intended")
            return 1
        if "90" in parsed[KEY]:
            print(f"{name}: the figure is still in the sentence")
            return 1
        path.write_text(rebuilt, encoding="utf-8")
        print(f"{name}: {KEY} rewritten without the figure")
    return 0


if __name__ == "__main__":
    sys.exit(main())
