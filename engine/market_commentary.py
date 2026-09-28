"""Piyasa yorumu. Strateji sinyallerini kesmez, yalnızca metin üretir."""
from __future__ import annotations

from engine.portfolio import now_tr

COMMENTARY_TFS = ("15m", "1h", "4h", "1d")
TF_CHART = {
    "15m": "15 dakikalık grafikte",
    "1h": "saatlik grafikte",
    "4h": "4 saatlik grafikte",
    "1d": "günlük grafikte",
}
TF_CHG_WINDOW = {
    "15m": "son 15 dakikada",
    "1h": "son saatte",
    "4h": "son 4 saatte",
    "1d": "son 24 saatte",
}
TF_SHORT = {"15m": "15m", "1h": "1s", "4h": "4s", "1d": "1g"}
UYUM_LABEL = {"Uyumlu": "Uyumlu", "Karsi": "Karsi", "Notr": "Notr"}

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
    return {tf: {"btc_stage": None, "counts": {}, "btc_chg": None} for tf in COMMENTARY_TFS}


def note_symbol_stage(symbol: str, stage: str, bucket: dict) -> None:
    """Tur sayımına ekler. ETH ayrı tutulur. Sinyal kararını değiştirmez."""
    if symbol == "BTCUSDT":
        bucket["btc_stage"] = stage
        return
    if symbol == "ETHUSDT":
        return
    counts = bucket.setdefault("counts", {})
    counts[stage] = int(counts.get(stage) or 0) + 1


def last_closed_bar_pct(df) -> float | None:
    if df is None or len(df) < 2 or "close" not in getattr(df, "columns", ()):
        return None
    try:
        prev = float(df["close"].iloc[-2])
        last = float(df["close"].iloc[-1])
    except (TypeError, ValueError, IndexError):
        return None
    if prev == 0:
        return None
    return (last - prev) / prev * 100.0


def note_symbol_stages(symbol: str, frames: dict | None, bucket: dict) -> None:
    """Her yorum TF'sinde evre sayar. BTC fiyat değişimi 15m/1h/4h son mumdan gelir."""
    from structure.core import market_stage

    frames = frames or {}
    for tf in COMMENTARY_TFS:
        tf_bucket = bucket.setdefault(tf, {"btc_stage": None, "counts": {}, "btc_chg": None})
        df = frames.get(tf)
        if df is None:
            continue
        try:
            stage = market_stage(df)
            value = stage.value if hasattr(stage, "value") else str(stage)
        except Exception:
            continue
        note_symbol_stage(symbol, value, tf_bucket)
        if symbol == "BTCUSDT" and tf != "1d":
            chg = last_closed_bar_pct(df)
            if chg is not None:
                tf_bucket["btc_chg"] = chg


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


def bias_from_regime(regime: str) -> str:
    if regime == "yukselis":
        return "long"
    if regime in ("dusus", "bitcoin_lider"):
        return "short"
    return "notr"


def side_to_bias(side) -> str:
    value = side.value if hasattr(side, "value") else str(side or "")
    if value == "BUY":
        return "long"
    if value == "SELL":
        return "short"
    return ""


def alignment_for_side(side, bias: str | None) -> str:
    want = side_to_bias(side)
    tag = str(bias or "notr")
    if not want or tag in ("", "notr"):
        return "Notr"
    if want == tag:
        return "Uyumlu"
    return "Karsi"


def alignment_summary(side, by_tf: dict | None) -> str:
    parts = []
    by_tf = by_tf or {}
    for tf in COMMENTARY_TFS:
        note = by_tf.get(tf) if isinstance(by_tf.get(tf), dict) else {}
        al = alignment_for_side(side, (note or {}).get("bias") or "notr")
        parts.append(f"{TF_SHORT[tf]}:{al}")
    return " ".join(parts)


def stamp_side_alignment(side, commentary: dict | None) -> dict:
    commentary = commentary if isinstance(commentary, dict) else {}
    by_tf = commentary.get("by_tf") if isinstance(commentary.get("by_tf"), dict) else {}
    bias = commentary.get("trade_bias") or "notr"
    return {
        "piyasa_bias": bias,
        "piyasa_uyum": alignment_for_side(side, bias),
        "piyasa_uyum_ozet": alignment_summary(side, by_tf),
        "piyasa_trade_tf": commentary.get("trade_tf") or "",
    }


def commentary_allows_side(side, commentary: dict | None = None, *, enabled: bool | None = None) -> bool:
    """MARKET_SIDE_FILTER kapaliyken her zaman True — sinyal kesilmez."""
    if enabled is None:
        from engine.config import MARKET_SIDE_FILTER

        enabled = MARKET_SIDE_FILTER
    if not enabled:
        return True
    bias = str((commentary or {}).get("trade_bias") or "notr")
    if bias == "notr":
        return True
    want = side_to_bias(side)
    return bool(want) and want == bias


def build_market_commentary(
    *,
    btc_stage: str | None,
    dominance: dict | None,
    stage_counts: dict | None,
    tf: str = "1d",
) -> dict:
    dominance = dominance or {}
    counts = stage_counts or {}
    tf = tf if tf in COMMENTARY_TFS else "1d"
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
        tf=tf,
    )
    bias = bias_from_regime(regime)
    return {
        "regime": regime,
        "bias": bias,
        "tf": tf,
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


def _legacy_stage_note(stage_note: dict) -> bool:
    return "btc_stage" in stage_note and not any(
        isinstance(stage_note.get(tf), dict) for tf in COMMENTARY_TFS
    )


def build_round_commentary(
    *,
    stage_note: dict | None,
    dominance: dict | None,
    trade_tf: str | None = None,
) -> dict:
    from engine.config import MARKET_TRADE_BIAS_TF

    dominance = dominance or {}
    stage_note = stage_note or {}
    chosen = trade_tf or MARKET_TRADE_BIAS_TF
    if chosen not in COMMENTARY_TFS:
        chosen = "4h"

    buckets: dict[str, dict] = {}
    if _legacy_stage_note(stage_note):
        buckets["1d"] = stage_note
    else:
        for tf in COMMENTARY_TFS:
            raw = stage_note.get(tf)
            buckets[tf] = raw if isinstance(raw, dict) else {"btc_stage": None, "counts": {}}

    by_tf: dict[str, dict] = {}
    for tf in COMMENTARY_TFS:
        bucket = buckets.get(tf) or {}
        dom = dict(dominance)
        if tf != "1d" and bucket.get("btc_chg") is not None:
            dom["btc_chg"] = bucket.get("btc_chg")
        note = build_market_commentary(
            btc_stage=bucket.get("btc_stage"),
            dominance=dom,
            stage_counts=bucket.get("counts") or {},
            tf=tf,
        )
        by_tf[tf] = note

    trade_note = by_tf.get(chosen) or by_tf.get("4h") or {}
    summary = " ".join(f"{TF_SHORT[tf]}:{by_tf[tf]['bias']}" for tf in COMMENTARY_TFS if tf in by_tf)
    text = f"Islem yonu ({TF_SHORT.get(chosen, chosen)}): {trade_note.get('bias') or 'notr'}. {summary}. {trade_note.get('text') or ''}".strip()
    return {
        "by_tf": by_tf,
        "trade_tf": chosen,
        "trade_bias": trade_note.get("bias") or "notr",
        "summary": summary,
        "regime": trade_note.get("regime"),
        "bias": trade_note.get("bias") or "notr",
        "tf": chosen,
        "text": text,
        "uygun": list(trade_note.get("uygun") or []),
        "zayif": list(trade_note.get("zayif") or []),
        "gec_kalan": list(trade_note.get("gec_kalan") or []),
        "birlikte": list(trade_note.get("birlikte") or []),
        "btc_stage": trade_note.get("btc_stage"),
        "btc_chg": trade_note.get("btc_chg"),
        "btc_d": trade_note.get("btc_d"),
        "btc_d_chg": trade_note.get("btc_d_chg"),
        "usdt_d": trade_note.get("usdt_d"),
        "usdt_d_chg": trade_note.get("usdt_d_chg"),
        "alt_advancing": trade_note.get("alt_advancing"),
        "alt_declining": trade_note.get("alt_declining"),
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


def _stage_sentence(stage: str, btc_chg, tf: str = "1d") -> str:
    chart = TF_CHART.get(tf, TF_CHART["1d"])
    window = TF_CHG_WINDOW.get(tf, TF_CHG_WINDOW["1d"])
    if stage == "advancing":
        base = f"Bitcoin {chart} yükseliş evresinde."
    elif stage == "declining":
        base = f"Bitcoin {chart} düşüş evresinde."
    elif stage in ("accumulation", "distribution"):
        base = f"Bitcoin {chart} yatay evrede."
    else:
        base = f"Bitcoin evresi bu turda ({tf}) okunamadı."
    if btc_chg is None:
        return base
    if btc_chg > 0:
        direction = "yükseldi"
    elif btc_chg < 0:
        direction = "düştü"
    else:
        direction = "yatay kaldı"
    return base[:-1] + f", {window} yüzde {_pct(abs(btc_chg))} {direction}."


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
    tf: str = "1d",
) -> str:
    sentences = [
        _stage_sentence(stage, btc_chg, tf),
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
