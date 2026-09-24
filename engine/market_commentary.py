"""Piyasa yorumu. Strateji sinyallerini kesmez, yalnızca metin üretir."""
from __future__ import annotations

from engine.portfolio import now_tr

_MOVE = 0.10

_DOWN_FIT = (
    "düşüş evresi satışı",
    "hacim negatif uyumsuzluk satışı",
    "CCI satışı",
    "RSI aşırı alım satışı",
    "rejim osilatör satışı",
    "RSI dip alışı",
    "destek mumu alışı",
)
_DOWN_WEAK = (
    "Dominance alt yükselişi",
    "CCI alışı",
    "MACD alışı",
    "Ichimoku alışı",
    "Bollinger sıkışması alışı",
    "üçgen alışı",
    "rejim osilatör alışı",
)
_DOWN_LATE = (
    "EMA fib satışı",
    "yapı kırılımı satışı",
    "yükselen takoz satışı",
)
_UP_FIT = (
    "yükseliş evresi alışı",
    "hacim pozitif uyumsuzluk alışı",
    "Dominance alt yükselişi",
    "CCI alışı",
    "MACD alışı",
    "Ichimoku alışı",
    "rejim osilatör alışı",
)
_UP_WEAK = (
    "düşüş evresi satışı",
    "hacim negatif uyumsuzluk satışı",
    "CCI satışı",
    "RSI aşırı alım satışı",
    "rejim osilatör satışı",
)

_CLOSING = "Bu bir yorumdur. Stratejiler sinyal üretmeye devam eder."


def empty_stage_note() -> dict:
    return {"btc_stage": None, "counts": {}}


def note_symbol_stage(symbol: str, stage: str, bucket: dict) -> None:
    """Tur sayımına ekler. ETH ayrı tutulur. Sinyal kararını değiştirmez."""
    if symbol == "BTCUSDT":
        bucket["btc_stage"] = stage
        return
    if symbol == "ETHUSDT":
        return
    counts = bucket.setdefault("counts", {})
    counts[stage] = int(counts.get(stage) or 0) + 1


def _sign(value) -> int:
    if value is None:
        return 0
    try:
        num = float(value)
    except (TypeError, ValueError):
        return 0
    if num >= _MOVE:
        return 1
    if num <= -_MOVE:
        return -1
    return 0


def _num(value):
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _pct(value) -> str:
    num = _num(value)
    if num is None:
        return ""
    return f"{num:.2f}".replace(".", ",")


def _signed_points(value) -> str:
    num = _num(value)
    if num is None:
        return ""
    text = f"{num:+.2f}".replace(".", ",")
    return f"{text} puan"


def build_market_commentary(
    *,
    btc_stage: str | None,
    dominance: dict | None,
    stage_counts: dict | None,
) -> dict:
    dominance = dominance or {}
    counts = stage_counts or {}
    stage = str(btc_stage or "unknown")
    btc_chg = _num(dominance.get("btc_chg"))
    btc_d = _num(dominance.get("btc_d"))
    usdt_d = _num(dominance.get("usdt_d"))
    btc_d_chg = _num(dominance.get("btc_d_chg")) if dominance.get("btc_d_chg") is not None else None
    usdt_d_chg = _num(dominance.get("usdt_d_chg")) if dominance.get("usdt_d_chg") is not None else None

    btc_d_sign = _sign(btc_d_chg)
    usdt_sign = _sign(usdt_d_chg)
    advancing = int(counts.get("advancing") or 0)
    declining = int(counts.get("declining") or 0)
    known = (
        advancing
        + declining
        + int(counts.get("accumulation") or 0)
        + int(counts.get("distribution") or 0)
    )
    alt_bull = known > 0 and advancing > declining and advancing / known >= 0.45
    alt_bear = known > 0 and declining > advancing and declining / known >= 0.45

    weak_marks: list[str] = []
    strong_marks: list[str] = []
    if stage == "declining":
        weak_marks.append("btc")
    elif stage == "advancing":
        strong_marks.append("btc")
    if btc_d_sign > 0:
        weak_marks.append("btc_d")
    elif btc_d_sign < 0:
        strong_marks.append("btc_d")
    if usdt_sign > 0:
        weak_marks.append("usdt")
    elif usdt_sign < 0:
        strong_marks.append("usdt")
    if alt_bear:
        weak_marks.append("alts")
    elif alt_bull:
        strong_marks.append("alts")

    bitcoin_leads = stage == "advancing" and btc_d_sign > 0
    if bitcoin_leads and "btc" in strong_marks:
        strong_marks = [mark for mark in strong_marks if mark != "btc"]
        weak_marks.append("btc_leads")

    regime = _regime(stage, weak_marks, strong_marks, btc_d, btc_chg)
    fit, weak, late, together = _lists(regime)
    text = _text(
        regime=regime,
        stage=stage,
        btc_chg=btc_chg,
        btc_d=btc_d,
        btc_d_chg=btc_d_chg,
        usdt_d=usdt_d,
        usdt_d_chg=usdt_d_chg,
        advancing=advancing,
        declining=declining,
        fit=fit,
        weak=weak,
        late=late,
        together=together,
    )
    return {
        "regime": regime,
        "text": text,
        "uygun": list(fit),
        "zayif": list(weak),
        "gec_kalan": list(late),
        "birlikte": list(together),
        "btc_stage": stage,
        "btc_chg": btc_chg,
        "btc_d": btc_d,
        "btc_d_chg": btc_d_chg,
        "usdt_d": usdt_d,
        "usdt_d_chg": usdt_d_chg,
        "alt_advancing": advancing,
        "alt_declining": declining,
        "updated_at": now_tr(),
    }


def _regime(stage: str, weak: list[str], strong: list[str], btc_d, btc_chg) -> str:
    if stage in ("unknown", "") and btc_d is None and btc_chg is None and not weak and not strong:
        return "belirsiz"
    if "btc_leads" in weak and len(strong) <= 1:
        return "bitcoin_lider"
    if len(weak) >= 2 and not strong:
        return "dusus"
    if len(strong) >= 2 and not weak:
        return "yukselis"
    if weak and strong:
        return "karisik"
    if len(weak) == 1 and not strong:
        return "dusus"
    if len(strong) == 1 and not weak:
        return "yukselis"
    return "karisik"


def _lists(regime: str) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    if regime in ("dusus", "bitcoin_lider"):
        return (
            _DOWN_FIT,
            _DOWN_WEAK,
            _DOWN_LATE,
            (
                "düşüş evresi satışı ile hacim negatif uyumsuzluk",
                "destek mumu alışı ile Stoch aşırı satım",
                "SMC alışı ile StochRSI aşırı satım",
            ),
        )
    if regime == "yukselis":
        return _UP_FIT, _UP_WEAK, (), ()
    return (), (), (), ()


def _stage_sentence(stage: str, btc_chg) -> str:
    if stage == "advancing":
        base = "Bitcoin günlük grafikte yükseliş evresinde."
    elif stage == "declining":
        base = "Bitcoin günlük grafikte düşüş evresinde."
    elif stage in ("accumulation", "distribution"):
        base = "Bitcoin günlük grafikte yatay evrede."
    else:
        base = "Bitcoin evresi bu turda okunamadı."
    if btc_chg is None:
        return base
    if btc_chg > 0:
        direction = "yükseldi"
    elif btc_chg < 0:
        direction = "düştü"
    else:
        direction = "yatay kaldı"
    return base[:-1] + f", son 24 saatte yüzde {_pct(abs(btc_chg))} {direction}."


def _dominance_sentence(btc_d, btc_d_chg, usdt_d, usdt_d_chg) -> str:
    parts = []
    if btc_d is not None:
        bit = f"Bitcoin hakimiyeti yüzde {_pct(btc_d)}"
        if btc_d_chg is not None:
            bit += f", bir önceki taramaya göre {_signed_points(btc_d_chg)}"
        parts.append(bit)
    if usdt_d is not None:
        bit = f"Tether hakimiyeti yüzde {_pct(usdt_d)}"
        if usdt_d_chg is not None:
            bit += f", bir önceki taramaya göre {_signed_points(usdt_d_chg)}"
        parts.append(bit)
    if not parts:
        return "Hakimiyet verisi bu turda gelmedi."
    return ". ".join(parts) + "."


def _text(
    *,
    regime: str,
    stage: str,
    btc_chg,
    btc_d,
    btc_d_chg,
    usdt_d,
    usdt_d_chg,
    advancing: int,
    declining: int,
    fit: tuple[str, ...],
    weak: tuple[str, ...],
    late: tuple[str, ...],
    together: tuple[str, ...],
) -> str:
    sentences = [
        _stage_sentence(stage, btc_chg),
        _dominance_sentence(btc_d, btc_d_chg, usdt_d, usdt_d_chg),
    ]
    if advancing or declining:
        sentences.append(
            f"Bitcoin ve Ethereum hariç {declining} coin düşüş evresinde, {advancing} coin yükseliş evresinde."
        )
    if regime == "dusus":
        sentences.append("Bu yapı altcoinler için zayıf. Satışlar ve dip alışları daha uygun. Trend alışları zayıf kalır.")
    elif regime == "bitcoin_lider":
        sentences.append(
            "Bitcoin yükselirken hakimiyeti de artıyor. Yükseliş Bitcoin'de kalıyor. "
            "Altcoin trend alışları bu yapıda zayıf kalır. Satışlar ve dip alışları daha uygun."
        )
    elif regime == "yukselis":
        sentences.append("Bu yapı altcoinler için daha elverişli. Trend alışları daha uygun. Satış stratejileri zayıf kalır.")
    elif regime == "belirsiz":
        sentences.append("Piyasa yapısı bu turda net değil. Uygun veya zayıf strateji listesi yazılmadı.")
    else:
        sentences.append(
            "Bitcoin, hakimiyet ve altcoin evreleri aynı yönü göstermiyor. Keskin bir uygun veya zayıf liste yazılmadı."
        )
    if fit:
        sentences.append("Daha uygun görünenler: " + ", ".join(fit) + ".")
    if together:
        sentences.append("Birlikte bakılınca öne çıkanlar: " + "; ".join(together) + ".")
    if weak:
        sentences.append("Zayıf kalanlar: " + ", ".join(weak) + ".")
    if late:
        sentences.append("Geç kalan satışlar ayrı izlenmeli: " + ", ".join(late) + ".")
    sentences.append(_CLOSING)
    return " ".join(sentences)
