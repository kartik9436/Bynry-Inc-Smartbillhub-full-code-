"""Add the Wave D tax-model strings to all eleven locales, translated.

CR-013 part 4's TAX-02 gained real controls where it carried named absences
(DEF-380/382/383/385/387), and every new user-visible string needs a key in all
eleven locales — not an English fallback, which is what an untranslated key
renders as and what nobody notices until a Spanish-speaking clerk hits it.

Run once from 07-frontend. Idempotent: an existing key is never overwritten, so
re-running cannot clobber a human's correction.
"""

from __future__ import annotations

import json
import pathlib

LOCALES = pathlib.Path("src/i18n/locales")

# key -> {locale: text}
STRINGS: dict[str, dict[str, str]] = {}


def add(key: str, **by_locale: str) -> None:
    STRINGS[key] = by_locale


# ── Step 1 · identity (DEF-385) ─────────────────────────────────────────────
add(
    "rating.taxWiz.identity.codeLabel",
    en="Code",
    de="Code",
    es="Código",
    fr="Code",
    hi="कोड",
    it="Codice",
    ja="コード",
    ko="코드",
    pt="Código",
    id="Kode",
    esmx="Código",
)
add(
    "rating.taxWiz.identity.codeHelp",
    en="Your own short identifier for this tax, unique across your taxes. Leave blank if you do not use codes.",
    de="Ihre eigene Kurzkennung für diese Steuer, eindeutig unter Ihren Steuern. Leer lassen, wenn Sie keine Codes verwenden.",
    es="Su propio identificador corto para este impuesto, único entre sus impuestos. Déjelo en blanco si no usa códigos.",
    fr="Votre identifiant court pour cette taxe, unique parmi vos taxes. Laissez vide si vous n'utilisez pas de codes.",
    hi="इस कर के लिए आपका अपना संक्षिप्त पहचानकर्ता, आपके करों में अद्वितीय। यदि आप कोड का उपयोग नहीं करते तो खाली छोड़ें।",
    it="Il vostro identificativo breve per questa imposta, univoco fra le vostre imposte. Lasciare vuoto se non usate codici.",
    ja="この税の短い識別子です。税の中で一意である必要があります。コードを使用しない場合は空欄のままにしてください。",
    ko="이 세금에 대한 자체 short 식별자이며 세금 간에 고유해야 합니다. 코드를 사용하지 않으면 비워 두십시오.",
    pt="O seu próprio identificador curto para este imposto, único entre os seus impostos. Deixe em branco se não usar códigos.",
    id="Pengenal singkat Anda untuk pajak ini, unik di antara pajak Anda. Kosongkan jika Anda tidak memakai kode.",
    esmx="Su propio identificador corto para este impuesto, único entre sus impuestos. Déjelo en blanco si no usa códigos.",
)
add(
    "rating.taxWiz.identity.billLabel",
    en="Bill label",
    de="Rechnungsbezeichnung",
    es="Etiqueta en la factura",
    fr="Libellé sur la facture",
    hi="बिल लेबल",
    it="Etichetta in fattura",
    ja="請求書上の表示名",
    ko="청구서 표시명",
    pt="Rótulo na fatura",
    id="Label pada tagihan",
    esmx="Etiqueta en la factura",
)
add(
    "rating.taxWiz.identity.billLabelHelp",
    en="What the customer reads on their bill. Leave blank to show the name above.",
    de="Was der Kunde auf seiner Rechnung liest. Leer lassen, um den Namen oben anzuzeigen.",
    es="Lo que el cliente lee en su factura. Déjelo en blanco para mostrar el nombre de arriba.",
    fr="Ce que le client lit sur sa facture. Laissez vide pour afficher le nom ci-dessus.",
    hi="ग्राहक अपने बिल पर क्या पढ़ता है। ऊपर दिया नाम दिखाने के लिए खाली छोड़ें।",
    it="Ciò che il cliente legge in fattura. Lasciare vuoto per mostrare il nome sopra.",
    ja="お客様が請求書で目にする表記です。上の名称を表示する場合は空欄のままにしてください。",
    ko="고객이 청구서에서 보는 문구입니다. 위의 이름을 표시하려면 비워 두십시오.",
    pt="O que o cliente lê na fatura. Deixe em branco para mostrar o nome acima.",
    id="Yang dibaca pelanggan pada tagihannya. Kosongkan untuk menampilkan nama di atas.",
    esmx="Lo que el cliente lee en su factura. Déjelo en blanco para mostrar el nombre de arriba.",
)
add(
    "rating.taxWiz.identity.typeLabel",
    en="Tax type",
    de="Steuerart",
    es="Tipo de impuesto",
    fr="Type de taxe",
    hi="कर का प्रकार",
    it="Tipo di imposta",
    ja="税の種類",
    ko="세금 유형",
    pt="Tipo de imposto",
    id="Jenis pajak",
    esmx="Tipo de impuesto",
)
add(
    "rating.taxWiz.identity.typeHelp",
    en="What sort of levy this is. This is not the same as the basis below — a franchise fee and a sales tax are both percentages, but they are filed differently.",
    de="Um welche Art von Abgabe es sich handelt. Das ist nicht dasselbe wie die Berechnungsgrundlage unten — eine Konzessionsabgabe und eine Umsatzsteuer sind beide prozentual, werden aber unterschiedlich gemeldet.",
    es="Qué clase de gravamen es. No es lo mismo que la base de cálculo de abajo: una tasa de concesión y un impuesto sobre ventas son ambos porcentajes, pero se declaran de forma distinta.",
    fr="De quel type de prélèvement il s'agit. Ce n'est pas la base de calcul ci-dessous : une redevance de concession et une taxe sur les ventes sont toutes deux des pourcentages, mais elles se déclarent différemment.",
    hi="यह किस प्रकार का शुल्क है। यह नीचे दिए गणना-आधार जैसा नहीं है — फ़्रैंचाइज़ शुल्क और बिक्री कर दोनों प्रतिशत हैं, पर दाखिल अलग-अलग होते हैं।",
    it="Che tipo di prelievo è. Non coincide con la base di calcolo qui sotto: un canone di concessione e un'imposta sulle vendite sono entrambi percentuali, ma si dichiarano diversamente.",
    ja="どの種類の賦課かを示します。下の算定方式とは別です。フランチャイズ料と売上税はいずれも率ですが、申告方法は異なります。",
    ko="어떤 종류의 부과금인지입니다. 아래의 산정 방식과는 다릅니다. 프랜차이즈 수수료와 판매세는 모두 백분율이지만 신고 방식이 다릅니다.",
    pt="Que tipo de tributo é este. Não é o mesmo que a base de cálculo abaixo: uma taxa de concessão e um imposto sobre vendas são ambos percentuais, mas são declarados de forma diferente.",
    id="Jenis pungutan ini. Ini tidak sama dengan dasar perhitungan di bawah — biaya waralaba dan pajak penjualan keduanya persentase, tetapi pelaporannya berbeda.",
    esmx="Qué clase de gravamen es. No es lo mismo que la base de cálculo de abajo: una tasa de concesión y un impuesto sobre ventas son ambos porcentajes, pero se declaran de forma distinta.",
)
add(
    "rating.taxWiz.identity.typeUnset",
    en="Not stated",
    de="Nicht angegeben",
    es="Sin especificar",
    fr="Non précisé",
    hi="निर्दिष्ट नहीं",
    it="Non indicato",
    ja="未設定",
    ko="지정되지 않음",
    pt="Não indicado",
    id="Tidak dinyatakan",
    esmx="Sin especificar",
)
for code, texts in {
    "sales_tax": ("Sales tax", "Umsatzsteuer", "Impuesto sobre ventas", "Taxe sur les ventes", "बिक्री कर", "Imposta sulle vendite", "売上税", "판매세", "Imposto sobre vendas", "Pajak penjualan", "Impuesto sobre ventas"),
    "franchise_fee": ("Franchise fee", "Konzessionsabgabe", "Tasa de concesión", "Redevance de concession", "फ़्रैंचाइज़ शुल्क", "Canone di concessione", "フランチャイズ料", "프랜차이즈 수수료", "Taxa de concessão", "Biaya waralaba", "Tasa de concesión"),
    "regulatory_fee": ("Regulatory fee", "Regulierungsgebühr", "Tasa regulatoria", "Redevance réglementaire", "नियामक शुल्क", "Tassa regolatoria", "規制手数料", "규제 수수료", "Taxa regulatória", "Biaya regulator", "Tasa regulatoria"),
    "utility_tax": ("Utility tax", "Versorgungssteuer", "Impuesto de servicios públicos", "Taxe sur les services publics", "उपयोगिता कर", "Imposta sui servizi pubblici", "公益事業税", "공공요금세", "Imposto sobre serviços públicos", "Pajak utilitas", "Impuesto de servicios públicos"),
    "environmental_fee": ("Environmental fee", "Umweltabgabe", "Tasa ambiental", "Redevance environnementale", "पर्यावरण शुल्क", "Tassa ambientale", "環境賦課金", "환경 부담금", "Taxa ambiental", "Biaya lingkungan", "Tasa ambiental"),
    "other": ("Other", "Sonstige", "Otro", "Autre", "अन्य", "Altro", "その他", "기타", "Outro", "Lainnya", "Otro"),
}.items():
    en, de, es, fr, hi, it, ja, ko, pt, idn, esmx = texts
    add(
        f"rating.taxWiz.identity.type.{code}",
        en=en, de=de, es=es, fr=fr, hi=hi, it=it, ja=ja, ko=ko, pt=pt, id=idn, esmx=esmx,
    )

# ── Step 1 · the matched premise count (DEF-380) ────────────────────────────
add(
    "rating.taxWiz.matched.everywhere",
    en="With no boundary chosen, this tax applies to every premises you have.",
    de="Ohne gewählte Abgrenzung gilt diese Steuer für alle Ihre Objekte.",
    es="Sin un límite elegido, este impuesto se aplica a todos sus predios.",
    fr="Sans limite choisie, cette taxe s'applique à tous vos sites.",
    hi="कोई सीमा चुने बिना यह कर आपके सभी परिसरों पर लागू होता है।",
    it="Senza un confine scelto, questa imposta si applica a tutti i vostri immobili.",
    ja="範囲を選択しない場合、この税はすべての施設に適用されます。",
    ko="경계를 선택하지 않으면 이 세금은 모든 사업장에 적용됩니다.",
    pt="Sem um limite escolhido, este imposto aplica-se a todos os seus imóveis.",
    id="Tanpa batas yang dipilih, pajak ini berlaku untuk semua properti Anda.",
    esmx="Sin un límite elegido, este impuesto se aplica a todos sus predios.",
)
add(
    "rating.taxWiz.matched.counting",
    en="Counting the premises this boundary matches…",
    de="Objekte werden gezählt, auf die diese Abgrenzung zutrifft …",
    es="Contando los predios que coinciden con este límite…",
    fr="Comptage des sites correspondant à cette limite…",
    hi="इस सीमा से मेल खाने वाले परिसर गिने जा रहे हैं…",
    it="Conteggio degli immobili che rientrano in questo confine…",
    ja="この範囲に一致する施設を集計しています…",
    ko="이 경계에 해당하는 사업장을 세는 중…",
    pt="A contar os imóveis que correspondem a este limite…",
    id="Menghitung properti yang cocok dengan batas ini…",
    esmx="Contando los predios que coinciden con este límite…",
)
add(
    "rating.taxWiz.matched.count",
    en="{{count}} of {{total}} premises match this boundary.",
    de="{{count}} von {{total}} Objekten entsprechen dieser Abgrenzung.",
    es="{{count}} de {{total}} predios coinciden con este límite.",
    fr="{{count}} sites sur {{total}} correspondent à cette limite.",
    hi="{{total}} में से {{count}} परिसर इस सीमा से मेल खाते हैं।",
    it="{{count}} immobili su {{total}} rientrano in questo confine.",
    ja="{{total}} 件中 {{count}} 件の施設がこの範囲に一致します。",
    ko="{{total}}개 중 {{count}}개 사업장이 이 경계에 해당합니다.",
    pt="{{count}} de {{total}} imóveis correspondem a este limite.",
    id="{{count}} dari {{total}} properti cocok dengan batas ini.",
    esmx="{{count}} de {{total}} predios coinciden con este límite.",
)
add(
    "rating.taxWiz.matched.none",
    en="No premises match. Check the boundary before entering rates — as it stands this tax would reach nobody.",
    de="Kein Objekt entspricht. Prüfen Sie die Abgrenzung, bevor Sie Sätze eingeben — so würde diese Steuer niemanden erreichen.",
    es="Ningún predio coincide. Revise el límite antes de introducir tarifas: tal como está, este impuesto no alcanzaría a nadie.",
    fr="Aucun site ne correspond. Vérifiez la limite avant de saisir des taux : en l'état, cette taxe n'atteindrait personne.",
    hi="कोई परिसर मेल नहीं खाता। दरें दर्ज करने से पहले सीमा जाँचें — इस स्थिति में यह कर किसी तक नहीं पहुँचेगा।",
    it="Nessun immobile corrisponde. Verificate il confine prima di inserire le tariffe: così com'è, questa imposta non raggiungerebbe nessuno.",
    ja="一致する施設がありません。料率を入力する前に範囲をご確認ください。このままではこの税は誰にも適用されません。",
    ko="일치하는 사업장이 없습니다. 요율을 입력하기 전에 경계를 확인하십시오. 현재 상태로는 이 세금이 아무에게도 적용되지 않습니다.",
    pt="Nenhum imóvel corresponde. Verifique o limite antes de introduzir taxas: assim, este imposto não chegaria a ninguém.",
    id="Tidak ada properti yang cocok. Periksa batasnya sebelum memasukkan tarif — seperti ini, pajak tidak akan menjangkau siapa pun.",
    esmx="Ningún predio coincide. Revise el límite antes de introducir tarifas: tal como está, este impuesto no alcanzaría a nadie.",
)
add(
    "rating.taxWiz.matched.unresolvableCount",
    en="We cannot count this yet. This product records county, taxing district and premise-list boundaries but cannot evaluate them, so a tax scoped this way reaches nobody — all {{total}} of your premises are outside it.",
    de="Das lässt sich noch nicht zählen. Dieses Produkt erfasst Landkreis-, Steuerbezirks- und Objektlisten-Abgrenzungen, kann sie aber nicht auswerten; eine so abgegrenzte Steuer erreicht daher niemanden — alle {{total}} Objekte liegen außerhalb.",
    es="Todavía no podemos contarlo. El producto registra los límites de condado, distrito fiscal y lista de predios, pero no puede evaluarlos, así que un impuesto delimitado así no alcanza a nadie: los {{total}} predios quedan fuera.",
    fr="Nous ne pouvons pas encore compter. Le produit enregistre les limites de comté, de district fiscal et de liste de sites, mais ne sait pas les évaluer : une taxe ainsi délimitée n'atteint personne — vos {{total}} sites sont tous en dehors.",
    hi="हम इसे अभी नहीं गिन सकते। यह उत्पाद काउंटी, कर-जिला और परिसर-सूची सीमाएँ दर्ज करता है पर उनका मूल्यांकन नहीं कर सकता, इसलिए इस तरह सीमित कर किसी तक नहीं पहुँचता — आपके सभी {{total}} परिसर इससे बाहर हैं।",
    it="Non possiamo ancora contarlo. Il prodotto registra i confini di contea, distretto fiscale ed elenco immobili ma non sa valutarli, quindi un'imposta così delimitata non raggiunge nessuno: tutti i {{total}} immobili ne restano fuori.",
    ja="現時点では集計できません。本製品は郡・課税区・施設リストの範囲を記録できますが評価はできないため、この方法で範囲を定めた税は誰にも適用されません。{{total}} 件すべてが対象外です。",
    ko="아직 집계할 수 없습니다. 이 제품은 카운티, 과세구, 사업장 목록 경계를 기록하지만 평가할 수는 없으므로 이렇게 범위를 정한 세금은 아무에게도 적용되지 않습니다. {{total}}개 사업장 모두가 대상 밖입니다.",
    pt="Ainda não conseguimos contar. O produto regista limites de condado, distrito fiscal e lista de imóveis mas não os consegue avaliar, pelo que um imposto assim delimitado não chega a ninguém — todos os {{total}} imóveis ficam de fora.",
    id="Kami belum dapat menghitungnya. Produk ini mencatat batas kabupaten, distrik pajak, dan daftar properti tetapi belum dapat mengevaluasinya, sehingga pajak dengan lingkup ini tidak menjangkau siapa pun — seluruh {{total}} properti berada di luar.",
    esmx="Todavía no podemos contarlo. El producto registra los límites de condado, distrito fiscal y lista de predios, pero no puede evaluarlos, así que un impuesto delimitado así no alcanza a nadie: los {{total}} predios quedan fuera.",
)
add(
    "rating.taxWiz.matched.unavailable",
    en="The premises count could not be read just now. Nothing is wrong with your boundary — try again before you rely on it.",
    de="Die Objektanzahl konnte gerade nicht gelesen werden. An Ihrer Abgrenzung ist nichts falsch — versuchen Sie es erneut, bevor Sie sich darauf verlassen.",
    es="No se pudo leer el recuento de predios en este momento. Su límite no tiene ningún problema; inténtelo de nuevo antes de confiar en él.",
    fr="Le décompte des sites n'a pas pu être lu à l'instant. Votre limite n'a rien d'incorrect — réessayez avant de vous y fier.",
    hi="अभी परिसरों की गिनती नहीं पढ़ी जा सकी। आपकी सीमा में कोई गड़बड़ी नहीं है — भरोसा करने से पहले फिर से प्रयास करें।",
    it="Il conteggio degli immobili non è stato leggibile in questo momento. Il vostro confine non ha problemi: riprovate prima di farvi affidamento.",
    ja="ただいま施設数を読み取れませんでした。範囲設定に問題はありません。信頼して進める前にもう一度お試しください。",
    ko="지금은 사업장 수를 읽지 못했습니다. 경계 설정에는 문제가 없습니다. 신뢰하기 전에 다시 시도하십시오.",
    pt="Não foi possível ler agora a contagem de imóveis. O seu limite não tem qualquer problema — tente de novo antes de confiar nele.",
    id="Jumlah properti tidak dapat dibaca saat ini. Tidak ada yang salah dengan batas Anda — coba lagi sebelum mengandalkannya.",
    esmx="No se pudo leer el recuento de predios en este momento. Su límite no tiene ningún problema; inténtelo de nuevo antes de confiar en él.",
)

# ── Step 2 · discount treatment (DEF-382) and rounding (DEF-385 / OQ-309) ───
add(
    "rating.taxWiz.discountTreatment.label",
    en="Discounts",
    de="Rabatte",
    es="Descuentos",
    fr="Remises",
    hi="छूट",
    it="Sconti",
    ja="割引",
    ko="할인",
    pt="Descontos",
    id="Diskon",
    esmx="Descuentos",
)
add(
    "rating.taxWiz.discountTreatment.before",
    en="Taxed after discounts (discount applies first)",
    de="Besteuerung nach Rabatten (Rabatt zuerst)",
    es="Se grava después de los descuentos (el descuento se aplica primero)",
    fr="Taxé après remises (la remise s'applique d'abord)",
    hi="छूट के बाद कर (पहले छूट लागू)",
    it="Tassato dopo gli sconti (lo sconto si applica prima)",
    ja="割引後に課税（割引が先に適用）",
    ko="할인 후 과세 (할인이 먼저 적용)",
    pt="Tributado após descontos (o desconto aplica-se primeiro)",
    id="Dikenai pajak setelah diskon (diskon berlaku lebih dulu)",
    esmx="Se grava después de los descuentos (el descuento se aplica primero)",
)
add(
    "rating.taxWiz.discountTreatment.after",
    en="Taxed before discounts (full amount is taxed)",
    de="Besteuerung vor Rabatten (voller Betrag wird besteuert)",
    es="Se grava antes de los descuentos (se grava el importe total)",
    fr="Taxé avant remises (le montant total est taxé)",
    hi="छूट से पहले कर (पूरी राशि पर कर)",
    it="Tassato prima degli sconti (si tassa l'importo pieno)",
    ja="割引前に課税（全額が課税対象）",
    ko="할인 전 과세 (전액이 과세 대상)",
    pt="Tributado antes dos descontos (é tributado o valor total)",
    id="Dikenai pajak sebelum diskon (jumlah penuh dikenai pajak)",
    esmx="Se grava antes de los descuentos (se grava el importe total)",
)
add(
    "rating.taxWiz.discountTreatment.help",
    en="This is set by the authority's own rules, so it differs between them. On a bill with a $1.00 credit, a 2% tax comes to $3.78 taxed after discounts and $3.80 taxed before.",
    de="Das richtet sich nach den Vorschriften der jeweiligen Behörde und unterscheidet sich daher. Bei einer Rechnung mit 1,00 $ Gutschrift ergibt eine Steuer von 2 % 3,78 $ bei Besteuerung nach Rabatten und 3,80 $ davor.",
    es="Lo fijan las normas de cada autoridad, por lo que varía entre ellas. En una factura con un abono de 1,00 $, un impuesto del 2 % da 3,78 $ si se grava tras los descuentos y 3,80 $ si se grava antes.",
    fr="Cela dépend des règles de chaque administration et diffère donc de l'une à l'autre. Sur une facture avec un avoir de 1,00 $, une taxe de 2 % donne 3,78 $ taxée après remises et 3,80 $ taxée avant.",
    hi="यह संबंधित प्राधिकरण के नियमों से तय होता है, इसलिए हर प्राधिकरण में अलग होता है। $1.00 क्रेडिट वाले बिल पर 2% कर छूट के बाद $3.78 और छूट से पहले $3.80 बनता है।",
    it="Lo stabiliscono le norme della singola autorità, quindi varia. Su una fattura con 1,00 $ di accredito, un'imposta del 2 % dà 3,78 $ se tassata dopo gli sconti e 3,80 $ se tassata prima.",
    ja="課税当局の規則で決まるため当局ごとに異なります。1.00 ドルの割引がある請求書では、2 % の税は割引後課税で 3.78 ドル、割引前課税で 3.80 ドルになります。",
    ko="과세 당국의 규정에 따라 정해지므로 당국마다 다릅니다. 1.00달러 크레딧이 있는 청구서에서 2% 세금은 할인 후 과세 시 3.78달러, 할인 전 과세 시 3.80달러입니다.",
    pt="É definido pelas regras da própria autoridade, pelo que difere entre elas. Numa fatura com 1,00 $ de crédito, um imposto de 2 % dá 3,78 $ tributado após descontos e 3,80 $ antes.",
    id="Ini ditetapkan oleh aturan otoritas terkait, sehingga berbeda-beda. Pada tagihan dengan kredit $1,00, pajak 2% menjadi $3,78 bila dikenai setelah diskon dan $3,80 bila sebelum.",
    esmx="Lo fijan las normas de cada autoridad, por lo que varía entre ellas. En una factura con un abono de $1.00, un impuesto del 2 % da $3.78 si se grava tras los descuentos y $3.80 si se grava antes.",
)
add(
    "rating.taxWiz.rounding.label",
    en="Rounding required by the authority",
    de="Von der Behörde geforderte Rundung",
    es="Redondeo exigido por la autoridad",
    fr="Arrondi exigé par l'administration",
    hi="प्राधिकरण द्वारा अपेक्षित पूर्णांकन",
    it="Arrotondamento richiesto dall'autorità",
    ko="과세 당국이 요구하는 반올림",
    ja="課税当局が求める端数処理",
    pt="Arredondamento exigido pela autoridade",
    id="Pembulatan yang diwajibkan otoritas",
    esmx="Redondeo exigido por la autoridad",
)
add(
    "rating.taxWiz.rounding.b4",
    en="Standard rounding (half up)",
    de="Standardrundung (kaufmännisch)",
    es="Redondeo estándar (medio hacia arriba)",
    fr="Arrondi standard (au demi supérieur)",
    hi="मानक पूर्णांकन (आधा ऊपर)",
    it="Arrotondamento standard (mezzo per eccesso)",
    ja="標準の端数処理（四捨五入）",
    ko="표준 반올림 (0.5 올림)",
    pt="Arredondamento padrão (meio para cima)",
    id="Pembulatan standar (setengah ke atas)",
    esmx="Redondeo estándar (medio hacia arriba)",
)
add(
    "rating.taxWiz.rounding.help",
    en="Record what your authority requires. Leave blank to use standard rounding.",
    de="Halten Sie fest, was Ihre Behörde verlangt. Leer lassen für die Standardrundung.",
    es="Registre lo que exige su autoridad. Déjelo en blanco para usar el redondeo estándar.",
    fr="Consignez ce qu'exige votre administration. Laissez vide pour l'arrondi standard.",
    hi="अपने प्राधिकरण की अपेक्षा दर्ज करें। मानक पूर्णांकन के लिए खाली छोड़ें।",
    it="Annotate ciò che richiede la vostra autorità. Lasciare vuoto per l'arrotondamento standard.",
    ja="課税当局の要求を記録します。標準の端数処理を使う場合は空欄のままにしてください。",
    ko="과세 당국의 요구 사항을 기록하십시오. 표준 반올림을 사용하려면 비워 두십시오.",
    pt="Registe o que a sua autoridade exige. Deixe em branco para usar o arredondamento padrão.",
    id="Catat apa yang diwajibkan otoritas Anda. Kosongkan untuk memakai pembulatan standar.",
    esmx="Registre lo que exige su autoridad. Déjelo en blanco para usar el redondeo estándar.",
)
add(
    "rating.taxWiz.rounding.notHonoured",
    en="Recorded only. Bills still use standard rounding — changing the arithmetic needs a finance sign-off, which is open as OQ-309.",
    de="Nur erfasst. Rechnungen verwenden weiterhin die Standardrundung — eine Änderung der Berechnung erfordert eine Finanzfreigabe (offen als OQ-309).",
    es="Solo registrado. Las facturas siguen usando el redondeo estándar; cambiar el cálculo requiere la aprobación de finanzas, abierta como OQ-309.",
    fr="Enregistré seulement. Les factures utilisent toujours l'arrondi standard — modifier le calcul exige une validation financière, ouverte sous OQ-309.",
    hi="केवल दर्ज। बिल अब भी मानक पूर्णांकन ही उपयोग करते हैं — गणना बदलने के लिए वित्त की स्वीकृति चाहिए, जो OQ-309 के रूप में खुली है।",
    it="Solo registrato. Le fatture usano ancora l'arrotondamento standard: modificare il calcolo richiede l'approvazione della funzione finanziaria, aperta come OQ-309.",
    ja="記録のみです。請求は引き続き標準の端数処理を使用します。計算の変更には財務の承認が必要で、OQ-309 として未決です。",
    ko="기록만 됩니다. 청구서는 여전히 표준 반올림을 사용합니다. 계산 방식 변경에는 재무 승인이 필요하며 OQ-309로 미결 상태입니다.",
    pt="Apenas registado. As faturas continuam a usar o arredondamento padrão — alterar o cálculo exige aprovação da área financeira, em aberto como OQ-309.",
    id="Hanya dicatat. Tagihan tetap memakai pembulatan standar — mengubah perhitungan memerlukan persetujuan keuangan, yang terbuka sebagai OQ-309.",
    esmx="Solo registrado. Las facturas siguen usando el redondeo estándar; cambiar el cálculo requiere la aprobación de finanzas, abierta como OQ-309.",
)
for code, texts in {
    "half_up": ("Half up", "Kaufmännisch aufrunden", "Medio hacia arriba", "Au demi supérieur", "आधा ऊपर", "Mezzo per eccesso", "四捨五入", "0.5 올림", "Meio para cima", "Setengah ke atas", "Medio hacia arriba"),
    "half_even": ("Half to even", "Auf gerade Zahl", "Medio al par", "Au demi pair", "आधा सम की ओर", "Mezzo al pari", "銀行家丸め", "은행가 반올림", "Meio para par", "Setengah ke genap", "Medio al par"),
    "up": ("Always up", "Immer aufrunden", "Siempre hacia arriba", "Toujours au supérieur", "हमेशा ऊपर", "Sempre per eccesso", "常に切り上げ", "항상 올림", "Sempre para cima", "Selalu ke atas", "Siempre hacia arriba"),
    "down": ("Always down", "Immer abrunden", "Siempre hacia abajo", "Toujours à l'inférieur", "हमेशा नीचे", "Sempre per difetto", "常に切り下げ", "항상 내림", "Sempre para baixo", "Selalu ke bawah", "Siempre hacia abajo"),
    "truncate": ("Cut off", "Abschneiden", "Truncar", "Troncature", "काट देना", "Troncamento", "切り捨て", "절사", "Truncar", "Pemotongan", "Truncar"),
}.items():
    en, de, es, fr, hi, it, ja, ko, pt, idn, esmx = texts
    add(
        f"rating.taxWiz.rounding.{code}",
        en=en, de=de, es=es, fr=fr, hi=hi, it=it, ja=ja, ko=ko, pt=pt, id=idn, esmx=esmx,
    )

add(
    "rating.taxWiz.exemptions.built",
    en="Exemption categories and the certificates accounts hold against them are managed on this tax's own Exemptions tab, because each one belongs to an account and has its own expiry date.",
    de="Befreiungskategorien und die dafür hinterlegten Bescheinigungen werden im Reiter „Befreiungen“ dieser Steuer verwaltet, da jede zu einem Konto gehört und ein eigenes Ablaufdatum hat.",
    es="Las categorías de exención y los certificados que las cuentas tienen para ellas se gestionan en la pestaña Exenciones de este impuesto, porque cada una pertenece a una cuenta y tiene su propia fecha de caducidad.",
    fr="Les catégories d'exonération et les certificats détenus par les comptes se gèrent dans l'onglet Exonérations de cette taxe, car chacun appartient à un compte et possède sa propre date d'expiration.",
    hi="छूट श्रेणियाँ और उनके विरुद्ध खातों के प्रमाणपत्र इस कर के अपने “छूट” टैब में प्रबंधित होते हैं, क्योंकि हर एक किसी खाते का होता है और उसकी अपनी समाप्ति तिथि होती है।",
    it="Le categorie di esenzione e i certificati che i conti detengono si gestiscono nella scheda Esenzioni di questa imposta, perché ognuno appartiene a un conto e ha una propria scadenza.",
    ja="免税区分と各アカウントが保持する証明書は、この税の「免税」タブで管理します。いずれもアカウントに属し、それぞれ有効期限を持つためです。",
    ko="면세 범주와 각 계정이 보유한 증명서는 이 세금의 면세 탭에서 관리합니다. 각각이 계정에 속하고 자체 만료일을 갖기 때문입니다.",
    pt="As categorias de isenção e os certificados que as contas detêm são geridos no separador Isenções deste imposto, porque cada um pertence a uma conta e tem a sua própria data de validade.",
    id="Kategori pembebasan dan sertifikat yang dimiliki akun dikelola di tab Pembebasan pajak ini, karena masing-masing milik satu akun dan punya tanggal kedaluwarsa sendiri.",
    esmx="Las categorías de exención y los certificados que las cuentas tienen para ellas se gestionan en la pestaña Exenciones de este impuesto, porque cada una pertenece a una cuenta y tiene su propia fecha de caducidad.",
)

# ── Step 3 · filing detail (DEF-385) ────────────────────────────────────────
add("rating.taxWiz.filing.dueDateLabel", en="Due-date rule", de="Fälligkeitsregel", es="Regla de vencimiento", fr="Règle d'échéance", hi="देय-तिथि नियम", it="Regola di scadenza", ja="納期限のルール", ko="납기 규칙", pt="Regra de vencimento", id="Aturan jatuh tempo", esmx="Regla de vencimiento")
add(
    "rating.taxWiz.filing.dueDateHelp",
    en="How the authority sets the deadline, in your own words — for example “20th of following month”.",
    de="Wie die Behörde die Frist festlegt, in Ihren eigenen Worten — zum Beispiel „20. des Folgemonats“.",
    es="Cómo fija el plazo la autoridad, con sus propias palabras: por ejemplo, «el 20 del mes siguiente».",
    fr="Comment l'administration fixe l'échéance, dans vos propres mots — par exemple « le 20 du mois suivant ».",
    hi="प्राधिकरण समय-सीमा कैसे तय करता है, अपने शब्दों में — जैसे “अगले माह की 20 तारीख”।",
    it="Come l'autorità fissa la scadenza, con parole vostre — ad esempio «il 20 del mese successivo».",
    ja="当局が期限をどう定めるかを自分の言葉で記入します。例：「翌月20日」。",
    ko="당국이 기한을 정하는 방식을 직접 적으십시오. 예: “다음 달 20일”.",
    pt="Como a autoridade define o prazo, nas suas palavras — por exemplo, «dia 20 do mês seguinte».",
    id="Bagaimana otoritas menetapkan tenggat, dengan kata-kata Anda sendiri — misalnya “tanggal 20 bulan berikutnya”.",
    esmx="Cómo fija el plazo la autoridad, con sus propias palabras: por ejemplo, «el 20 del mes siguiente».",
)
add("rating.taxWiz.filing.methodLabel", en="Payment method", de="Zahlungsweg", es="Forma de pago", fr="Mode de paiement", hi="भुगतान का तरीका", it="Modalità di pagamento", ja="納付方法", ko="납부 방법", pt="Forma de pagamento", id="Metode pembayaran", esmx="Forma de pago")
add("rating.taxWiz.filing.methodUnset", en="Not stated", de="Nicht angegeben", es="Sin especificar", fr="Non précisé", hi="निर्दिष्ट नहीं", it="Non indicato", ja="未設定", ko="지정되지 않음", pt="Não indicado", id="Tidak dinyatakan", esmx="Sin especificar")
for code, texts in {
    "ach": ("Bank transfer (ACH)", "Bankeinzug (ACH)", "Transferencia bancaria (ACH)", "Virement bancaire (ACH)", "बैंक हस्तांतरण (ACH)", "Bonifico bancario (ACH)", "銀行振替（ACH）", "은행 이체 (ACH)", "Transferência bancária (ACH)", "Transfer bank (ACH)", "Transferencia bancaria (ACH)"),
    "eft": ("Electronic transfer", "Elektronische Überweisung", "Transferencia electrónica", "Transfert électronique", "इलेक्ट्रॉनिक हस्तांतरण", "Trasferimento elettronico", "電子振込", "전자 이체", "Transferência eletrónica", "Transfer elektronik", "Transferencia electrónica"),
    "cheque": ("Cheque", "Scheck", "Cheque", "Chèque", "चेक", "Assegno", "小切手", "수표", "Cheque", "Cek", "Cheque"),
    "portal": ("Authority's online portal", "Online-Portal der Behörde", "Portal en línea de la autoridad", "Portail en ligne de l'administration", "प्राधिकरण का ऑनलाइन पोर्टल", "Portale online dell'autorità", "当局のオンラインポータル", "당국 온라인 포털", "Portal online da autoridade", "Portal daring otoritas", "Portal en línea de la autoridad"),
    "other": ("Other", "Sonstige", "Otro", "Autre", "अन्य", "Altro", "その他", "기타", "Outro", "Lainnya", "Otro"),
}.items():
    en, de, es, fr, hi, it, ja, ko, pt, idn, esmx = texts
    add(f"rating.taxWiz.filing.method.{code}", en=en, de=de, es=es, fr=fr, hi=hi, it=it, ja=ja, ko=ko, pt=pt, id=idn, esmx=esmx)

add("rating.taxWiz.filing.referenceLabel", en="Your account number with the authority", de="Ihre Kontonummer bei der Behörde", es="Su número de cuenta ante la autoridad", fr="Votre numéro de compte auprès de l'administration", hi="प्राधिकरण के पास आपका खाता नंबर", it="Il vostro numero di conto presso l'autorità", ja="当局における貴社の口座番号", ko="당국에 등록된 귀사의 계정 번호", pt="O seu número de conta junto da autoridade", id="Nomor akun Anda pada otoritas", esmx="Su número de cuenta ante la autoridad")
add(
    "rating.taxWiz.filing.referenceHelp",
    en="The reference the authority knows you by, quoted on every filing.",
    de="Das Aktenzeichen, unter dem die Behörde Sie führt und das auf jeder Meldung anzugeben ist.",
    es="La referencia con la que la autoridad le identifica, citada en cada declaración.",
    fr="La référence sous laquelle l'administration vous connaît, indiquée sur chaque déclaration.",
    hi="वह संदर्भ जिससे प्राधिकरण आपको जानता है, हर विवरणी में लिखा जाता है।",
    it="Il riferimento con cui l'autorità vi identifica, indicato su ogni dichiarazione.",
    ja="当局が貴社を識別するための参照番号で、申告のたびに記載します。",
    ko="당국이 귀사를 식별하는 참조 번호이며 모든 신고서에 기재됩니다.",
    pt="A referência pela qual a autoridade o identifica, indicada em cada declaração.",
    id="Referensi yang dipakai otoritas untuk mengenali Anda, dicantumkan pada setiap pelaporan.",
    esmx="La referencia con la que la autoridad le identifica, citada en cada declaración.",
)
add("rating.taxWiz.filing.allowanceLabel", en="Collection allowance you keep", de="Einbehaltene Erhebungsvergütung", es="Compensación por recaudación que usted retiene", fr="Remise de perception que vous conservez", hi="संग्रहण भत्ता जो आप रखते हैं", it="Compenso di riscossione trattenuto", ja="収納手数料（自社取分）", ko="징수 수수료 (자사 보유분)", pt="Compensação de cobrança que retém", id="Imbalan pemungutan yang Anda simpan", esmx="Compensación por recaudación que usted retiene")
add(
    "rating.taxWiz.filing.allowanceHelp",
    en="The share of what you collect that the authority lets you keep for filing on time, as a fraction — enter 0.005 for 0.5%. On $2,400.00 remitted that is $12.00 of your own income.",
    de="Der Anteil des Einbehalts, den die Behörde Ihnen für fristgerechte Meldung überlässt, als Bruchteil — geben Sie 0,005 für 0,5 % ein. Bei 2.400,00 $ Abführung sind das 12,00 $ eigener Ertrag.",
    es="La parte de lo recaudado que la autoridad le permite retener por declarar a tiempo, como fracción: introduzca 0,005 para 0,5 %. Sobre 2.400,00 $ remitidos son 12,00 $ de ingreso propio.",
    fr="La part de ce que vous percevez que l'administration vous laisse conserver pour une déclaration dans les délais, en fraction — saisissez 0,005 pour 0,5 %. Sur 2 400,00 $ reversés, cela fait 12,00 $ de revenu propre.",
    hi="समय पर विवरणी देने के लिए प्राधिकरण आपको संग्रहित राशि का जो हिस्सा रखने देता है, भिन्न के रूप में — 0.5% के लिए 0.005 दर्ज करें। $2,400.00 भेजने पर यह $12.00 की आपकी अपनी आय है।",
    it="La quota di quanto riscuotete che l'autorità vi lascia trattenere per la dichiarazione puntuale, come frazione: inserite 0,005 per 0,5 %. Su 2.400,00 $ versati sono 12,00 $ di ricavo proprio.",
    ja="期限内申告に対して当局が保持を認める収納額の割合を、小数で入力します（0.5 % なら 0.005）。2,400.00 ドルを納付する場合、12.00 ドルが自社の収益になります。",
    ko="기한 내 신고에 대해 당국이 보유를 허용하는 징수액의 비율을 소수로 입력하십시오(0.5%는 0.005). 2,400.00달러를 납부하면 12.00달러가 자사 수익입니다.",
    pt="A parte do que cobra que a autoridade lhe permite reter por declarar a tempo, como fração — introduza 0,005 para 0,5 %. Sobre 2.400,00 $ entregues são 12,00 $ de receita própria.",
    id="Bagian dari yang Anda pungut yang boleh Anda simpan karena melapor tepat waktu, dalam bentuk pecahan — masukkan 0,005 untuk 0,5%. Atas $2.400,00 yang disetor, itu $12,00 pendapatan Anda sendiri.",
    esmx="La parte de lo recaudado que la autoridad le permite retener por declarar a tiempo, como fracción: introduzca 0.005 para 0.5 %. Sobre $2,400.00 remitidos son $12.00 de ingreso propio.",
)
add("rating.taxWiz.filing.allowanceGlLabel", en="Account the allowance is posted to", de="Konto für die Erhebungsvergütung", es="Cuenta a la que se registra la compensación", fr="Compte d'imputation de la remise", hi="भत्ता जिस खाते में दर्ज होता है", it="Conto su cui è registrato il compenso", ja="収納手数料の計上先勘定", ko="수수료가 기표되는 계정", pt="Conta onde a compensação é registada", id="Akun tempat imbalan dibukukan", esmx="Cuenta a la que se registra la compensación")
add("rating.taxWiz.filing.interestLabel", en="Interest or penalty for filing late", de="Zinsen oder Säumniszuschlag bei verspäteter Meldung", es="Interés o recargo por declarar fuera de plazo", fr="Intérêts ou pénalité de déclaration tardive", hi="देर से विवरणी देने पर ब्याज या शास्ति", it="Interessi o sanzione per dichiarazione tardiva", ja="申告遅延時の利息・加算金", ko="신고 지연 시 이자 또는 가산금", pt="Juros ou penalidade por declaração tardia", id="Bunga atau denda keterlambatan pelaporan", esmx="Interés o recargo por declarar fuera de plazo")
add(
    "rating.taxWiz.filing.interestHelp",
    en="What the authority charges you, as a fraction — enter 0.015 for 1.5%. State the period beside it, or the figure means nothing.",
    de="Was die Behörde Ihnen berechnet, als Bruchteil — geben Sie 0,015 für 1,5 % ein. Geben Sie daneben den Zeitraum an, sonst ist die Zahl bedeutungslos.",
    es="Lo que le cobra la autoridad, como fracción: introduzca 0,015 para 1,5 %. Indique el periodo al lado, o la cifra no significa nada.",
    fr="Ce que l'administration vous facture, en fraction — saisissez 0,015 pour 1,5 %. Précisez la période à côté, sinon le chiffre ne veut rien dire.",
    hi="प्राधिकरण आपसे जो वसूलता है, भिन्न के रूप में — 1.5% के लिए 0.015 दर्ज करें। साथ में अवधि बताएँ, वरना यह आंकड़ा निरर्थक है।",
    it="Quanto vi addebita l'autorità, come frazione: inserite 0,015 per 1,5 %. Indicate accanto il periodo, altrimenti il numero non significa nulla.",
    ja="当局が課す割合を小数で入力します（1.5 % なら 0.015）。隣で期間を指定してください。指定しないと数値に意味がありません。",
    ko="당국이 부과하는 비율을 소수로 입력하십시오(1.5%는 0.015). 옆에서 기간을 지정하십시오. 그렇지 않으면 이 수치는 의미가 없습니다.",
    pt="O que a autoridade lhe cobra, como fração — introduza 0,015 para 1,5 %. Indique o período ao lado, ou o valor não significa nada.",
    id="Yang dikenakan otoritas kepada Anda, dalam bentuk pecahan — masukkan 0,015 untuk 1,5%. Sebutkan periodenya di sebelahnya, jika tidak angka ini tak bermakna.",
    esmx="Lo que le cobra la autoridad, como fracción: introduzca 0.015 para 1.5 %. Indique el periodo al lado, o la cifra no significa nada.",
)
add("rating.taxWiz.filing.interestBasisLabel", en="Charged per", de="Berechnet je", es="Se cobra por", fr="Facturé par", hi="प्रति अवधि लगाया जाता है", it="Addebitato per", ja="適用期間", ko="적용 주기", pt="Cobrado por", id="Dikenakan per", esmx="Se cobra por")
add("rating.taxWiz.filing.basisUnset", en="Not stated", de="Nicht angegeben", es="Sin especificar", fr="Non précisé", hi="निर्दिष्ट नहीं", it="Non indicato", ja="未設定", ko="지정되지 않음", pt="Não indicado", id="Tidak dinyatakan", esmx="Sin especificar")
for code, texts in {
    "daily": ("Day", "Tag", "Día", "Jour", "दिन", "Giorno", "日", "일", "Dia", "Hari", "Día"),
    "monthly": ("Month", "Monat", "Mes", "Mois", "माह", "Mese", "月", "월", "Mês", "Bulan", "Mes"),
    "annual": ("Year", "Jahr", "Año", "An", "वर्ष", "Anno", "年", "년", "Ano", "Tahun", "Año"),
}.items():
    en, de, es, fr, hi, it, ja, ko, pt, idn, esmx = texts
    add(f"rating.taxWiz.filing.basis.{code}", en=en, de=de, es=es, fr=fr, hi=hi, it=it, ja=ja, ko=ko, pt=pt, id=idn, esmx=esmx)

add("rating.taxWiz.filing.reminderLabel", en="Who gets the filing reminder", de="Wer die Erinnerung zur Meldung erhält", es="Quién recibe el recordatorio de declaración", fr="Qui reçoit le rappel de déclaration", hi="विवरणी की याद किसे मिलेगी", it="Chi riceve il promemoria della dichiarazione", ja="申告リマインダーの宛先", ko="신고 알림 수신자", pt="Quem recebe o lembrete de declaração", id="Siapa yang menerima pengingat pelaporan", esmx="Quién recibe el recordatorio de declaración")
add(
    "rating.taxWiz.filing.reminderHelp",
    en="An email address. It does not have to be someone who uses this product — an outside bookkeeper is fine.",
    de="Eine E-Mail-Adresse. Es muss keine Person sein, die dieses Produkt nutzt — auch eine externe Buchhaltung ist möglich.",
    es="Una dirección de correo. No tiene que ser alguien que use este producto: un contable externo también sirve.",
    fr="Une adresse e-mail. Il ne s'agit pas nécessairement d'un utilisateur du produit — un comptable externe convient.",
    hi="एक ईमेल पता। यह ज़रूरी नहीं कि वह इस उत्पाद का उपयोगकर्ता हो — बाहरी लेखाकार भी चलेगा।",
    it="Un indirizzo e-mail. Non deve essere una persona che usa questo prodotto: va bene anche un contabile esterno.",
    ja="メールアドレスを入力します。本製品の利用者である必要はなく、外部の記帳担当者でも構いません。",
    ko="이메일 주소입니다. 이 제품 사용자가 아니어도 되며 외부 회계 담당자도 괜찮습니다.",
    pt="Um endereço de e-mail. Não tem de ser alguém que use este produto — um contabilista externo serve.",
    id="Alamat email. Tidak harus pengguna produk ini — pemegang buku eksternal pun boleh.",
    esmx="Una dirección de correo. No tiene que ser alguien que use este producto: un contador externo también sirve.",
)
add(
    "rating.taxWiz.filing.worksheetTitle",
    en="The remittance worksheet",
    de="Das Abführungsformular",
    es="La hoja de liquidación",
    fr="La feuille de reversement",
    hi="प्रेषण कार्यपत्रक",
    it="Il prospetto di versamento",
    ja="納付明細ワークシート",
    ko="납부 정산표",
    pt="A folha de entrega",
    id="Lembar kerja penyetoran",
    esmx="La hoja de liquidación",
)
add(
    "rating.taxWiz.filing.worksheetMessage",
    en="What you record here is saved and shown back to you, but the product does not yet produce a return from it. Preparing a filing is still a manual step.",
    de="Was Sie hier erfassen, wird gespeichert und angezeigt, aber das Produkt erstellt daraus noch keine Meldung. Die Vorbereitung einer Meldung bleibt vorerst ein manueller Schritt.",
    es="Lo que registre aquí se guarda y se le muestra, pero el producto todavía no genera una declaración a partir de ello. Preparar la presentación sigue siendo un paso manual.",
    fr="Ce que vous saisissez ici est enregistré et vous est restitué, mais le produit n'en tire pas encore de déclaration. Préparer un dépôt reste une étape manuelle.",
    hi="यहाँ दर्ज की गई जानकारी सहेजी जाती है और आपको दिखाई जाती है, पर उत्पाद अभी इससे विवरणी नहीं बनाता। दाखिल करने की तैयारी अभी भी मैनुअल है।",
    it="Quanto registrate qui viene salvato e mostrato, ma il prodotto non genera ancora una dichiarazione. Preparare il versamento resta un passaggio manuale.",
    ja="ここに記録した内容は保存され、表示もされますが、本製品はまだそこから申告書を作成しません。申告の準備は現時点では手作業です。",
    ko="여기에 기록한 내용은 저장되고 다시 표시되지만, 제품이 아직 이를 바탕으로 신고서를 만들지는 않습니다. 신고 준비는 여전히 수작업입니다.",
    pt="O que registar aqui é guardado e mostrado de volta, mas o produto ainda não gera uma declaração a partir disso. Preparar a entrega continua a ser um passo manual.",
    id="Yang Anda catat di sini disimpan dan ditampilkan kembali, tetapi produk belum menghasilkan laporan darinya. Menyiapkan pelaporan masih langkah manual.",
    esmx="Lo que registre aquí se guarda y se le muestra, pero el producto todavía no genera una declaración a partir de ello. Preparar la presentación sigue siendo un paso manual.",
)

# ── Step 4 · the save outcomes (DEF-387) ────────────────────────────────────
add(
    "rating.taxWiz.outcomes.active",
    en="Saving puts this tax in force now. Save it as a draft instead if you are not ready — a draft charges nobody until you activate it.",
    de="Mit dem Speichern tritt diese Steuer sofort in Kraft. Speichern Sie sie stattdessen als Entwurf, wenn Sie noch nicht so weit sind — ein Entwurf belastet niemanden, bis Sie ihn aktivieren.",
    es="Al guardar, este impuesto entra en vigor ahora. Guárdelo como borrador si aún no está listo: un borrador no cobra a nadie hasta que lo active.",
    fr="Enregistrer met cette taxe en vigueur immédiatement. Enregistrez-la plutôt comme brouillon si vous n'êtes pas prêt : un brouillon ne facture personne tant que vous ne l'activez pas.",
    hi="सहेजने पर यह कर अभी लागू हो जाएगा। यदि आप तैयार नहीं हैं तो इसे मसौदे के रूप में सहेजें — मसौदा सक्रिय करने तक किसी से शुल्क नहीं लेता।",
    it="Il salvataggio mette subito in vigore questa imposta. Salvatela come bozza se non siete pronti: una bozza non addebita nulla finché non la attivate.",
    ja="保存するとこの税は直ちに有効になります。まだ確定でない場合は下書きとして保存してください。下書きは有効化するまで誰にも課金しません。",
    ko="저장하면 이 세금이 즉시 적용됩니다. 아직 준비되지 않았다면 임시 저장하십시오. 임시 저장 상태에서는 활성화 전까지 아무에게도 부과되지 않습니다.",
    pt="Ao guardar, este imposto entra em vigor agora. Guarde-o como rascunho se ainda não estiver pronto — um rascunho não cobra a ninguém até o ativar.",
    id="Menyimpan akan memberlakukan pajak ini sekarang. Simpan sebagai draf jika Anda belum siap — draf tidak menagih siapa pun sampai Anda mengaktifkannya.",
    esmx="Al guardar, este impuesto entra en vigor ahora. Guárdelo como borrador si aún no está listo: un borrador no cobra a nadie hasta que lo active.",
)
add(
    "rating.taxWiz.outcomes.scheduled",
    en="This tax is dated to start on {{date}}. It will show as Scheduled and charges nobody until that date.",
    de="Diese Steuer ist auf den {{date}} datiert. Sie wird als „Geplant“ angezeigt und belastet bis dahin niemanden.",
    es="Este impuesto está fechado para comenzar el {{date}}. Aparecerá como Programado y no cobrará a nadie hasta esa fecha.",
    fr="Cette taxe est datée du {{date}}. Elle apparaîtra comme Planifiée et ne facturera personne avant cette date.",
    hi="यह कर {{date}} से शुरू होने के लिए दिनांकित है। यह “निर्धारित” दिखेगा और उस तिथि तक किसी से शुल्क नहीं लेगा।",
    it="Questa imposta decorre dal {{date}}. Risulterà Programmata e non addebiterà nulla fino a quella data.",
    ja="この税は {{date}} 開始で登録されています。「予定」と表示され、その日まで誰にも課金されません。",
    ko="이 세금은 {{date}}부터 시작하도록 지정되었습니다. “예정”으로 표시되며 그 날짜까지는 아무에게도 부과되지 않습니다.",
    pt="Este imposto está datado para começar a {{date}}. Aparecerá como Agendado e não cobra a ninguém até essa data.",
    id="Pajak ini dijadwalkan mulai {{date}}. Akan tampil sebagai Terjadwal dan tidak menagih siapa pun sampai tanggal itu.",
    esmx="Este impuesto está fechado para comenzar el {{date}}. Aparecerá como Programado y no cobrará a nadie hasta esa fecha.",
)

# ── The landing's two new status words (DEF-387) ────────────────────────────
add("rating.status.scheduled", en="Scheduled", de="Geplant", es="Programado", fr="Planifiée", hi="निर्धारित", it="Programmata", ja="予定", ko="예정", pt="Agendado", id="Terjadwal", esmx="Programado")
add("rating.status.expired", en="Expired", de="Abgelaufen", es="Caducado", fr="Expirée", hi="समाप्त", it="Scaduta", ja="期限切れ", ko="만료됨", pt="Expirado", id="Kedaluwarsa", esmx="Caducado")

# ── The two new server refusals (DEF-384, DEF-387) ──────────────────────────
add(
    "rating.taxes.in_force_edit_refused",
    en="This tax is in force, so its rate and how it is worked out cannot be changed here — the rate history is an audit record. Record a correction instead, with a reason.",
    de="Diese Steuer ist in Kraft; ihr Satz und ihre Berechnung können hier nicht geändert werden — die Satzhistorie ist ein Prüfnachweis. Erfassen Sie stattdessen eine Korrektur mit Begründung.",
    es="Este impuesto está en vigor, así que su tipo y su forma de cálculo no pueden cambiarse aquí: el histórico de tipos es un registro de auditoría. Registre en su lugar una corrección, con un motivo.",
    fr="Cette taxe est en vigueur : son taux et son mode de calcul ne peuvent pas être modifiés ici — l'historique des taux est une pièce d'audit. Enregistrez plutôt une correction, avec un motif.",
    hi="यह कर लागू है, इसलिए इसकी दर और गणना यहाँ नहीं बदली जा सकती — दर का इतिहास एक अंकेक्षण अभिलेख है। इसके बजाय कारण सहित एक सुधार दर्ज करें।",
    it="Questa imposta è in vigore, quindi l'aliquota e il modo in cui è calcolata non si possono modificare qui: lo storico delle aliquote è un documento di audit. Registrate invece una correzione, con una motivazione.",
    ja="この税は有効なため、税率と算定方法はここでは変更できません。税率の履歴は監査記録です。代わりに理由を付けて訂正を登録してください。",
    ko="이 세금은 시행 중이므로 세율과 산정 방식을 여기서 변경할 수 없습니다. 세율 이력은 감사 기록입니다. 대신 사유를 적어 정정을 기록하십시오.",
    pt="Este imposto está em vigor, pelo que a taxa e a forma de cálculo não podem ser alteradas aqui — o histórico de taxas é um registo de auditoria. Registe antes uma correção, com um motivo.",
    id="Pajak ini sedang berlaku, sehingga tarif dan cara perhitungannya tidak dapat diubah di sini — riwayat tarif adalah catatan audit. Sebagai gantinya, catat koreksi disertai alasan.",
    esmx="Este impuesto está en vigor, así que su tasa y su forma de cálculo no pueden cambiarse aquí: el historial de tasas es un registro de auditoría. Registre en su lugar una corrección, con un motivo.",
)
add(
    "rating.taxes.correction_reason",
    en="Say why this rate is being corrected, in a sentence someone will still understand in a year.",
    de="Begründen Sie die Korrektur in einem Satz, der auch in einem Jahr noch verständlich ist.",
    es="Explique por qué se corrige este tipo, en una frase que siga entendiéndose dentro de un año.",
    fr="Indiquez pourquoi ce taux est corrigé, en une phrase encore compréhensible dans un an.",
    hi="बताएँ कि यह दर क्यों सुधारी जा रही है — ऐसे वाक्य में जो एक साल बाद भी समझ आए।",
    it="Spiegate perché questa aliquota viene corretta, in una frase comprensibile anche fra un anno.",
    ja="この税率を訂正する理由を、1 年後でも理解できる一文で記入してください。",
    ko="이 세율을 정정하는 이유를 1년 뒤에도 이해할 수 있는 문장으로 적으십시오.",
    pt="Explique porque esta taxa está a ser corrigida, numa frase que ainda se perceba daqui a um ano.",
    id="Jelaskan mengapa tarif ini dikoreksi, dalam kalimat yang masih dipahami setahun lagi.",
    esmx="Explique por qué se corrige esta tasa, en una frase que siga entendiéndose dentro de un año.",
)
add(
    "rating.taxes.correction_empty",
    en="A correction has to change something. Nothing here differs from the rate already in force.",
    de="Eine Korrektur muss etwas ändern. Hier weicht nichts von dem bereits geltenden Satz ab.",
    es="Una corrección tiene que cambiar algo. Aquí no hay nada distinto del tipo ya en vigor.",
    fr="Une correction doit modifier quelque chose. Rien ici ne diffère du taux déjà en vigueur.",
    hi="सुधार में कुछ बदलना ज़रूरी है। यहाँ पहले से लागू दर से कुछ भी भिन्न नहीं है।",
    it="Una correzione deve cambiare qualcosa. Qui non c'è nulla di diverso dall'aliquota già in vigore.",
    ja="訂正には何らかの変更が必要です。ここには現在有効な税率と異なる点がありません。",
    ko="정정에는 변경 사항이 있어야 합니다. 여기에는 이미 시행 중인 세율과 다른 점이 없습니다.",
    pt="Uma correção tem de alterar algo. Aqui nada difere da taxa já em vigor.",
    id="Koreksi harus mengubah sesuatu. Di sini tidak ada yang berbeda dari tarif yang sudah berlaku.",
    esmx="Una corrección tiene que cambiar algo. Aquí no hay nada distinto de la tasa ya en vigor.",
)
add(
    "rating.taxes.already_corrected",
    en="This rate has already been corrected. Correct the rate that replaced it, not this one — it is history now.",
    de="Dieser Satz wurde bereits korrigiert. Korrigieren Sie den Satz, der ihn ersetzt hat, nicht diesen — er ist jetzt Historie.",
    es="Este tipo ya se corrigió. Corrija el tipo que lo sustituyó, no este: ahora es historial.",
    fr="Ce taux a déjà été corrigé. Corrigez le taux qui l'a remplacé, pas celui-ci — il appartient désormais à l'historique.",
    hi="यह दर पहले ही सुधारी जा चुकी है। इसके स्थान पर आई दर को सुधारें, इसे नहीं — यह अब इतिहास है।",
    it="Questa aliquota è già stata corretta. Correggete l'aliquota che l'ha sostituita, non questa: ormai è storia.",
    ja="この税率はすでに訂正済みです。これを置き換えた税率を訂正してください。この行は履歴です。",
    ko="이 세율은 이미 정정되었습니다. 이를 대체한 세율을 정정하십시오. 이 행은 이제 이력입니다.",
    pt="Esta taxa já foi corrigida. Corrija a taxa que a substituiu, não esta — agora é histórico.",
    id="Tarif ini sudah dikoreksi. Koreksilah tarif penggantinya, bukan yang ini — ini kini riwayat.",
    esmx="Esta tasa ya se corrigió. Corrija la tasa que la sustituyó, no esta: ahora es historial.",
)
add(
    "rating.taxes.correct_draft",
    en="This tax is still a draft, so nothing has been charged under it. Edit it directly instead of correcting it.",
    de="Diese Steuer ist noch ein Entwurf, es wurde also nichts danach berechnet. Bearbeiten Sie sie direkt, statt sie zu korrigieren.",
    es="Este impuesto sigue siendo un borrador, así que no se ha cobrado nada con él. Edítelo directamente en lugar de corregirlo.",
    fr="Cette taxe est encore un brouillon : rien n'a été facturé sur cette base. Modifiez-la directement au lieu de la corriger.",
    hi="यह कर अभी मसौदा है, इसलिए इसके तहत कुछ भी वसूला नहीं गया। इसे सुधारने के बजाय सीधे संपादित करें।",
    it="Questa imposta è ancora una bozza, quindi non è stato addebitato nulla. Modificatela direttamente anziché correggerla.",
    ja="この税はまだ下書きで、これに基づく請求はありません。訂正ではなく直接編集してください。",
    ko="이 세금은 아직 임시 저장 상태이므로 이에 따라 부과된 금액이 없습니다. 정정 대신 직접 편집하십시오.",
    pt="Este imposto ainda é um rascunho, pelo que nada foi cobrado com ele. Edite-o diretamente em vez de o corrigir.",
    id="Pajak ini masih draf, jadi belum ada penagihan berdasarkan itu. Edit langsung saja, bukan dikoreksi.",
    esmx="Este impuesto sigue siendo un borrador, así que no se ha cobrado nada con él. Edítelo directamente en lugar de corregirlo.",
)
add(
    "rating.taxes.already_activated",
    en="This tax is already in force — it is {{status}}, not a draft.",
    de="Diese Steuer ist bereits in Kraft — sie ist {{status}}, kein Entwurf.",
    es="Este impuesto ya está en vigor: es {{status}}, no un borrador.",
    fr="Cette taxe est déjà en vigueur : elle est {{status}}, pas un brouillon.",
    hi="यह कर पहले से लागू है — यह {{status}} है, मसौदा नहीं।",
    it="Questa imposta è già in vigore: è {{status}}, non una bozza.",
    ja="この税はすでに有効です。状態は {{status}} であり、下書きではありません。",
    ko="이 세금은 이미 시행 중입니다. 상태는 {{status}}이며 임시 저장이 아닙니다.",
    pt="Este imposto já está em vigor — é {{status}}, não um rascunho.",
    id="Pajak ini sudah berlaku — statusnya {{status}}, bukan draf.",
    esmx="Este impuesto ya está en vigor: es {{status}}, no un borrador.",
)
add(
    "rating.taxes.duplicate_code",
    en="You already have a tax with this code.",
    de="Sie haben bereits eine Steuer mit diesem Code.",
    es="Ya tiene un impuesto con este código.",
    fr="Vous avez déjà une taxe portant ce code.",
    hi="इस कोड वाला कर आपके पास पहले से है।",
    it="Avete già un'imposta con questo codice.",
    ja="このコードの税はすでに存在します。",
    ko="이 코드를 사용하는 세금이 이미 있습니다.",
    pt="Já tem um imposto com este código.",
    id="Anda sudah punya pajak dengan kode ini.",
    esmx="Ya tiene un impuesto con este código.",
)
add(
    "rating.taxes.certificate_required",
    en="This exemption category needs a certificate on file. Enter the certificate reference.",
    de="Für diese Befreiungskategorie muss eine Bescheinigung vorliegen. Geben Sie die Bescheinigungsnummer ein.",
    es="Esta categoría de exención requiere un certificado archivado. Introduzca la referencia del certificado.",
    fr="Cette catégorie d'exonération exige un certificat au dossier. Saisissez la référence du certificat.",
    hi="इस छूट श्रेणी के लिए फ़ाइल में प्रमाणपत्र आवश्यक है। प्रमाणपत्र संदर्भ दर्ज करें।",
    it="Questa categoria di esenzione richiede un certificato agli atti. Inserite il riferimento del certificato.",
    ja="この免税区分には証明書の保管が必要です。証明書番号を入力してください。",
    ko="이 면세 범주에는 증명서 보관이 필요합니다. 증명서 번호를 입력하십시오.",
    pt="Esta categoria de isenção exige um certificado em arquivo. Introduza a referência do certificado.",
    id="Kategori pembebasan ini memerlukan sertifikat yang tersimpan. Masukkan nomor referensi sertifikat.",
    esmx="Esta categoría de exención requiere un certificado archivado. Introduzca la referencia del certificado.",
)
add(
    "rating.taxes.unknown_account",
    en="That account was not found.",
    de="Dieses Konto wurde nicht gefunden.",
    es="No se encontró esa cuenta.",
    fr="Ce compte est introuvable.",
    hi="वह खाता नहीं मिला।",
    it="Conto non trovato.",
    ja="その顧客アカウントが見つかりません。",
    ko="해당 계정을 찾을 수 없습니다.",
    pt="Essa conta não foi encontrada.",
    id="Akun tersebut tidak ditemukan.",
    esmx="No se encontró esa cuenta.",
)
add(
    "rating.taxes.duplicate_category",
    en="This tax already has an exemption category with that code.",
    de="Für diese Steuer gibt es bereits eine Befreiungskategorie mit diesem Code.",
    es="Este impuesto ya tiene una categoría de exención con ese código.",
    fr="Cette taxe possède déjà une catégorie d'exonération portant ce code.",
    hi="इस कर में उस कोड वाली छूट श्रेणी पहले से है।",
    it="Questa imposta ha già una categoria di esenzione con quel codice.",
    ja="この税にはそのコードの免税区分がすでに存在します。",
    ko="이 세금에는 해당 코드의 면세 범주가 이미 있습니다.",
    pt="Este imposto já tem uma categoria de isenção com esse código.",
    id="Pajak ini sudah punya kategori pembebasan dengan kode itu.",
    esmx="Este impuesto ya tiene una categoría de exención con ese código.",
)
add(
    "rating.taxes.category_inactive",
    en="That exemption category is no longer active.",
    de="Diese Befreiungskategorie ist nicht mehr aktiv.",
    es="Esa categoría de exención ya no está activa.",
    fr="Cette catégorie d'exonération n'est plus active.",
    hi="वह छूट श्रेणी अब सक्रिय नहीं है।",
    it="Quella categoria di esenzione non è più attiva.",
    ja="その免税区分は現在有効ではありません。",
    ko="해당 면세 범주는 더 이상 활성 상태가 아닙니다.",
    pt="Essa categoria de isenção já não está ativa.",
    id="Kategori pembebasan itu tidak lagi aktif.",
    esmx="Esa categoría de exención ya no está activa.",
)
add(
    "rating.taxes.certificate_exists",
    en="This account already holds a live certificate for {{category}}.",
    de="Für dieses Konto liegt bereits eine gültige Bescheinigung für {{category}} vor.",
    es="Esta cuenta ya tiene un certificado vigente para {{category}}.",
    fr="Ce compte détient déjà un certificat en cours pour {{category}}.",
    hi="इस खाते के पास {{category}} के लिए पहले से एक वैध प्रमाणपत्र है।",
    it="Questo conto ha già un certificato valido per {{category}}.",
    ja="このアカウントには {{category}} の有効な証明書がすでに登録されています。",
    ko="이 계정에는 {{category}}에 대한 유효한 증명서가 이미 있습니다.",
    pt="Esta conta já tem um certificado válido para {{category}}.",
    id="Akun ini sudah memiliki sertifikat aktif untuk {{category}}.",
    esmx="Esta cuenta ya tiene un certificado vigente para {{category}}.",
)
add(
    "rating.taxes.already_revoked",
    en="That certificate has already been withdrawn.",
    de="Diese Bescheinigung wurde bereits zurückgezogen.",
    es="Ese certificado ya fue retirado.",
    fr="Ce certificat a déjà été retiré.",
    hi="वह प्रमाणपत्र पहले ही वापस लिया जा चुका है।",
    it="Quel certificato è già stato ritirato.",
    ja="その証明書はすでに取り消されています。",
    ko="해당 증명서는 이미 철회되었습니다.",
    pt="Esse certificado já foi retirado.",
    id="Sertifikat itu sudah dicabut.",
    esmx="Ese certificado ya fue retirado.",
)

FILES = {
    "en": "en.json",
    "de": "de.json",
    "es": "es.json",
    "esmx": "es-MX.json",
    "fr": "fr-FR.json",
    "hi": "hi.json",
    "id": "id-ID.json",
    "it": "it-IT.json",
    "ja": "ja-JP.json",
    "ko": "ko-KR.json",
    "pt": "pt-BR.json",
}


def main() -> None:
    """⚠ EXISTING KEY ORDER IS PRESERVED AND NEW KEYS ARE APPENDED.

    The locale files are NOT sorted, so writing them back sorted would rewrite
    every line of eleven files six other lanes also touch — a whole-file write
    wearing the costume of an addition, which is precisely the mechanism
    CLAUDE.md law 11 and `10-scripts/file_defect.py` were both written for. A
    500-line diff for a 60-key addition hides whatever else is in it.
    """
    for locale, filename in FILES.items():
        path = LOCALES / filename
        data = json.loads(path.read_text(encoding="utf-8"))
        added = 0
        for key, by_locale in STRINGS.items():
            if key in data:
                continue  # never overwrite: a human correction outranks this file
            if locale not in by_locale:
                raise SystemExit(f"{key} has no {locale} translation — refusing to fall back")
            data[key] = by_locale[locale]
            added += 1
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"{filename}: +{added}")


if __name__ == "__main__":
    main()
