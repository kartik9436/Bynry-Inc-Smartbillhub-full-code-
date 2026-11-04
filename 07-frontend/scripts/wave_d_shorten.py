"""G33 — shorten four Wave D refusals, by deleting RATIONALE and never INSTRUCTION.

G33's own warning is the thing to obey here: *"shorten by deleting RATIONALE,
never INSTRUCTION"*, because cutting the sentence that says what to do next
passes the gate and makes the message worse.

So each of these keeps the instruction and loses the WHY, which belongs in a
docstring and now lives in `apps/rating/services.py`:

* `in_force_edit_refused` — dropped *"and how it is worked out"* and *"the rate
  history is an audit record"*. KEPT: *"Record a correction with a reason
  instead."*, which is the whole point of the refusal (DEF-384 was filed because
  the road ENDED here).
* `already_corrected` — dropped *"not this one — it is history now"*. KEPT the
  instruction to correct the replacement.
* `correct_draft` — dropped *"so nothing has been charged under it"*. KEPT
  *"Edit it directly instead of correcting it."*
* `already_activated` — split one 13-word sentence into two short ones; nothing
  was removed at all.

Run once from 07-frontend.
"""

from __future__ import annotations

import json
import pathlib

NEW: dict[str, dict[str, str]] = {
    "en": {
        "rating.taxes.in_force_edit_refused": "This tax is in force, so its rate cannot be changed here. Record a correction with a reason instead.",
        "rating.taxes.already_activated": "This tax is already in force. It is {{status}}, not a draft.",
        "rating.taxes.already_corrected": "This rate has already been corrected. Correct the rate that replaced it.",
        "rating.taxes.correct_draft": "This tax is still a draft. Edit it directly instead of correcting it.",
    },
    "de": {
        "rating.taxes.in_force_edit_refused": "Diese Steuer ist in Kraft; ihr Satz kann hier nicht geändert werden. Erfassen Sie stattdessen eine Korrektur mit Begründung.",
        "rating.taxes.already_activated": "Diese Steuer ist bereits in Kraft. Sie ist {{status}}, kein Entwurf.",
        "rating.taxes.already_corrected": "Dieser Satz wurde bereits korrigiert. Korrigieren Sie den Satz, der ihn ersetzt hat.",
        "rating.taxes.correct_draft": "Diese Steuer ist noch ein Entwurf. Bearbeiten Sie sie direkt, statt sie zu korrigieren.",
    },
    "es": {
        "rating.taxes.in_force_edit_refused": "Este impuesto está en vigor, así que su tipo no puede cambiarse aquí. Registre en su lugar una corrección con un motivo.",
        "rating.taxes.already_activated": "Este impuesto ya está en vigor. Es {{status}}, no un borrador.",
        "rating.taxes.already_corrected": "Este tipo ya se corrigió. Corrija el tipo que lo sustituyó.",
        "rating.taxes.correct_draft": "Este impuesto sigue siendo un borrador. Edítelo directamente en lugar de corregirlo.",
    },
    "es-MX": {
        "rating.taxes.in_force_edit_refused": "Este impuesto está en vigor, así que su tasa no puede cambiarse aquí. Registre en su lugar una corrección con un motivo.",
        "rating.taxes.already_activated": "Este impuesto ya está en vigor. Es {{status}}, no un borrador.",
        "rating.taxes.already_corrected": "Esta tasa ya se corrigió. Corrija la tasa que la sustituyó.",
        "rating.taxes.correct_draft": "Este impuesto sigue siendo un borrador. Edítelo directamente en lugar de corregirlo.",
    },
    "fr-FR": {
        "rating.taxes.in_force_edit_refused": "Cette taxe est en vigueur : son taux ne peut pas être modifié ici. Enregistrez plutôt une correction avec un motif.",
        "rating.taxes.already_activated": "Cette taxe est déjà en vigueur. Elle est {{status}}, pas un brouillon.",
        "rating.taxes.already_corrected": "Ce taux a déjà été corrigé. Corrigez le taux qui l'a remplacé.",
        "rating.taxes.correct_draft": "Cette taxe est encore un brouillon. Modifiez-la directement au lieu de la corriger.",
    },
    "hi": {
        "rating.taxes.in_force_edit_refused": "यह कर लागू है, इसलिए इसकी दर यहाँ नहीं बदली जा सकती। इसके बजाय कारण सहित एक सुधार दर्ज करें।",
        "rating.taxes.already_activated": "यह कर पहले से लागू है। यह {{status}} है, मसौदा नहीं।",
        "rating.taxes.already_corrected": "यह दर पहले ही सुधारी जा चुकी है। इसके स्थान पर आई दर को सुधारें।",
        "rating.taxes.correct_draft": "यह कर अभी मसौदा है। इसे सुधारने के बजाय सीधे संपादित करें।",
    },
    "id-ID": {
        "rating.taxes.in_force_edit_refused": "Pajak ini sedang berlaku, jadi tarifnya tidak dapat diubah di sini. Catat koreksi disertai alasan sebagai gantinya.",
        "rating.taxes.already_activated": "Pajak ini sudah berlaku. Statusnya {{status}}, bukan draf.",
        "rating.taxes.already_corrected": "Tarif ini sudah dikoreksi. Koreksilah tarif penggantinya.",
        "rating.taxes.correct_draft": "Pajak ini masih draf. Edit langsung saja, bukan dikoreksi.",
    },
    "it-IT": {
        "rating.taxes.in_force_edit_refused": "Questa imposta è in vigore, quindi l'aliquota non si può modificare qui. Registrate invece una correzione con una motivazione.",
        "rating.taxes.already_activated": "Questa imposta è già in vigore. È {{status}}, non una bozza.",
        "rating.taxes.already_corrected": "Questa aliquota è già stata corretta. Correggete l'aliquota che l'ha sostituita.",
        "rating.taxes.correct_draft": "Questa imposta è ancora una bozza. Modificatela direttamente anziché correggerla.",
    },
    "ja-JP": {
        "rating.taxes.in_force_edit_refused": "この税は有効なため、税率をここでは変更できません。代わりに理由を付けて訂正を登録してください。",
        "rating.taxes.already_activated": "この税はすでに有効です。状態は {{status}} で、下書きではありません。",
        "rating.taxes.already_corrected": "この税率はすでに訂正済みです。これを置き換えた税率を訂正してください。",
        "rating.taxes.correct_draft": "この税はまだ下書きです。訂正ではなく直接編集してください。",
    },
    "ko-KR": {
        "rating.taxes.in_force_edit_refused": "이 세금은 시행 중이므로 세율을 여기서 변경할 수 없습니다. 대신 사유를 적어 정정을 기록하십시오.",
        "rating.taxes.already_activated": "이 세금은 이미 시행 중입니다. 상태는 {{status}}이며 임시 저장이 아닙니다.",
        "rating.taxes.already_corrected": "이 세율은 이미 정정되었습니다. 이를 대체한 세율을 정정하십시오.",
        "rating.taxes.correct_draft": "이 세금은 아직 임시 저장 상태입니다. 정정 대신 직접 편집하십시오.",
    },
    "pt-BR": {
        "rating.taxes.in_force_edit_refused": "Este imposto está em vigor, pelo que a taxa não pode ser alterada aqui. Registe antes uma correção com um motivo.",
        "rating.taxes.already_activated": "Este imposto já está em vigor. É {{status}}, não um rascunho.",
        "rating.taxes.already_corrected": "Esta taxa já foi corrigida. Corrija a taxa que a substituiu.",
        "rating.taxes.correct_draft": "Este imposto ainda é um rascunho. Edite-o diretamente em vez de o corrigir.",
    },
}


def main() -> None:
    for locale, updates in NEW.items():
        path = pathlib.Path(f"src/i18n/locales/{locale}.json")
        data = json.loads(path.read_text(encoding="utf-8"))
        for key, value in updates.items():
            if key not in data:
                raise SystemExit(f"{locale}: {key} is not in the catalogue")
            data[key] = value
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"{locale}: {len(updates)} shortened")


if __name__ == "__main__":
    main()
