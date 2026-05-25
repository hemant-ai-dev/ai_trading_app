"""English + Marathi copy for signals, factors, and combined decision block."""

from __future__ import annotations

SIGNAL_EN_MR = {
    "BUY": ("BUY", "खरेदी (BUY)"),
    "SELL": ("SELL", "विक्री (SELL)"),
    "HOLD": ("HOLD", "प्रतीक्षा (HOLD)"),
}

SIGNAL_GUIDE = {
    "BUY": {
        "en": (
            "The model sees **more bullish evidence than bearish** on the latest bar: "
            "trend, momentum, and price vs VWAP lean upward. Target is a reference stretch above spot; "
            "stop is where the read would be wrong. This is **not** a guaranteed profit call."
        ),
        "mr": (
            "नवीनतम बारवर **जास्त बुलिश पुरावा** दिसतो: ट्रेंड, मोमेंटम आणि VWAP वरची किंमत वरच्या बाजूने आहेत. "
            "लक्ष्य हे स्पॉटपेक्षा वरचा संदर्भ स्तर आहे; स्टॉप म्हणजे चुकीचे ठरल्यास पुनर्मूल्यांकन करा. "
            "हे **नफा निश्चित** करणारा आदेश नाही — फक्त शैक्षणिक अंदाज."
        ),
    },
    "SELL": {
        "en": (
            "Bearish factors dominate: weaker structure vs moving averages, softer RSI/MACD, "
            "and/or price below VWAP. Target references a downward stretch; stop marks invalidation upward. "
            "Use for learning and monitoring — not as direct trading advice."
        ),
        "mr": (
            "बेअरिश घटक वर्चस्वावर आहेत: सरासरी खाली कमकुवत रचना, RSI/MACD कमकुवत, "
            "आणि/किंवा VWAP खाली किंमत. लक्ष्य खालीचा संदर्भ मार्ग; स्टॉप वरच्या बाजूने चुकीचे ठरल्यास. "
            "शिकण्यासाठी आणि निरीक्षणासाठी — थेट ट्रेड सल्ला नाही."
        ),
    },
    "HOLD": {
        "en": (
            "Signals are **mixed or neutral** — neither buy nor sell threshold is met. "
            "Wait for clearer break above/below VWAP with trend confirmation. "
            "Band levels show possible range until structure resolves."
        ),
        "mr": (
            "संकेत **मिश्र किंवा तटस्थ** — खरेदी किंवा विक्रीची पूर्ण अट पूर्ण होत नाही. "
            "VWAP वर/खाली स्पष्ट भंग आणि ट्रेंड पुष्टी होईपर्यंत प्रतीक्षा करा. "
            "बँड स्तरांवर रेंज संभाव्य आहे जोपर्यंत रचना स्पष्ट होत नाही."
        ),
    },
}

FACTOR_MR = {
    "EMA Bullish": "EMA9 > EMA20 — लघुकालीन ट्रेंड मध्यमकालीन वर.",
    "EMA Bearish": "EMA9 < EMA20 — लघुकालीन ट्रेंड खाली.",
    "RSI Strong": "RSI 55 पेक्षा वर — मोमेंटम मजबूत.",
    "RSI Weak": "RSI 45 पेक्षा खाली — मोमेंटम कमकुवत.",
    "RSI Mild Bull": "RSI हलका बुलिश.",
    "RSI Mild Bear": "RSI हलका बेअरिश.",
    "RSI Neutral": "RSI तटस्थ झोन.",
    "MACD Bullish cross": "MACD सिग्नल वर — बुलिश क्रॉस.",
    "MACD Bearish cross": "MACD सिग्नल खाली — बेअरिश क्रॉस.",
    "MACD Positive": "MACD सकारात्मक.",
    "MACD Negative": "MACD नकारात्मक.",
    "Above VWAP": "किंमत VWAP वर.",
    "Below VWAP": "किंमत VWAP खाली.",
    "Volume supports up-move": "व्हॉल्यूम वरच्या हालचालीस पाठिंबा.",
    "Volume supports down-move": "व्हॉल्यूम खालच्या हालचालीस पाठिंबा.",
    "High volume, mixed trend": "जास्त व्हॉल्यूम, मिश्र ट्रेंड.",
}

REGIME_MR = {
    "bullish_trend": "बुलिश ट्रेंड",
    "bearish_trend": "बेअरिश ट्रेंड",
    "range_bound_vwap": "VWAP जवळ रेंज",
    "overbought_stretch": "ओव्हरबॉट झोन",
    "oversold_stretch": "ओव्हरसोल्ड झोन",
    "mixed_transition": "मिश्र संक्रमण",
}


def parse_reason_tags(reason: str) -> list[str]:
    return [t.strip() for t in (reason or "").split(",") if t.strip()]


def _factor_mr(tag: str) -> str:
    if tag in FACTOR_MR:
        return FACTOR_MR[tag]
    base = tag.split("(")[0].strip()
    for k, v in FACTOR_MR.items():
        if k in tag or base.startswith(k.split()[0]):
            return v
    return "या घटकाचा स्कोअरमध्ये समावेश."


def factors_table_rows(reason: str) -> list[dict]:
    rows = []
    for tag in parse_reason_tags(reason):
        rows.append({"Factor (EN)": tag, "Logic (Marathi)": _factor_mr(tag)})
    return rows


def build_steps_table(brain: dict | None, rule_reason: str) -> list[dict]:
    rows = []
    steps_en = (brain or {}).get("reasoning_steps") or []
    steps_mr = (brain or {}).get("reasoning_steps_mr") or []
    if steps_en:
        for i, en in enumerate(steps_en, 1):
            mr = steps_mr[i - 1] if i - 1 < len(steps_mr) else "—"
            rows.append({"Step": i, "Logic (English)": en, "Logic (Marathi)": mr})
    else:
        for i, tag in enumerate(parse_reason_tags(rule_reason), 1):
            rows.append(
                {
                    "Step": i,
                    "Logic (English)": tag,
                    "Logic (Marathi)": FACTOR_MR.get(tag, "—"),
                }
            )
    return rows
