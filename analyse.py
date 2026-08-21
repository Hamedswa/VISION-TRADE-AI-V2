"""
Vision Trade AI V2
analyse.py

Orchestrateur principal de l'analyse technique.

Pipeline :

DATA
 ↓
INDICATEURS
 ↓
STRUCTURE
 ↓
FIBONACCI
 ↓
SCORE
 ↓
RR
 ↓
FILTRE QUALITÉ
 ↓
RÉSULTAT FINAL

IMPORTANT :
- aucun appel Groq ;
- aucune décision prise par une IA ;
- aucun message Telegram ;
- aucun envoi de signal ;
- les calculs techniques restent déterministes.

Ce module orchestre les modules spécialisés.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional


logger = logging.getLogger(__name__)


# ============================================================
# IMPORTS
# ============================================================

from data import get_candles

from indicateurs import (
    calculer_ema,
    calculer_rsi,
    calculer_atr,
)

from structure import (
    analyser_structure,
)

from fibonacci import (
    analyser_fibonacci,
)

from score import (
    calculer_score,
)

from rr import (
    calculer_rr_complet,
    resume_rr,
)

from filtre_qualite import (
    filtrer_qualite,
)


# ============================================================
# CONSTANTES
# ============================================================

BUY = "BUY"
SELL = "SELL"
NEUTRAL = "NEUTRAL"

DEFAULT_SYMBOL = "XAU/USD"

DEFAULT_TIMEFRAME = "15min"

HIGHER_TIMEFRAMES = (
    "H4",
    "H1",
    "M15",
    "M5",
)


# ============================================================
# OUTILS
# ============================================================

def _safe_float(
    value: Any,
    default: Optional[float] = None,
) -> Optional[float]:
    """
    Conversion numérique sécurisée.
    """

    if value is None:
        return default

    try:
        return float(value)

    except (
        TypeError,
        ValueError,
    ):
        return default


def _normalize_direction(
    direction: Any,
) -> str:
    """
    Normalise une direction.
    """

    if direction is None:
        return NEUTRAL

    value = str(
        direction
    ).upper().strip()

    if value in {
        BUY,
        SELL,
    }:
        return value

    return NEUTRAL


def _normalize_bias(
    bias: Any,
) -> str:
    """
    Normalise un biais technique.
    """

    if bias is None:
        return NEUTRAL.lower()

    value = str(
        bias
    ).lower().strip()

    if value in {
        "bullish",
        "buy",
        "long",
    }:
        return "bullish"

    if value in {
        "bearish",
        "sell",
        "short",
    }:
        return "bearish"

    return NEUTRAL.lower()


def _extract_latest_close(
    candles: list[dict],
) -> Optional[float]:
    """
    Récupère le dernier prix de clôture.
    """

    if not candles:
        return None

    candle = candles[-1]

    if not isinstance(candle, dict):
        return None

    for key in (
        "close",
        "Close",
        "CLOSE",
    ):

        if key in candle:
            return _safe_float(
                candle[key]
            )

    return None


def _extract_latest_atr(
    atr_data: Any,
) -> Optional[float]:
    """
    Extrait proprement la dernière valeur ATR.

    Supporte :
        float
        int
        list
        tuple
        dict
    """

    if atr_data is None:
        return None

    if isinstance(
        atr_data,
        (int, float),
    ):
        return float(atr_data)

    if isinstance(
        atr_data,
        (list, tuple),
    ):

        if not atr_data:
            return None

        return _safe_float(
            atr_data[-1]
        )

    if isinstance(
        atr_data,
        dict,
    ):

        for key in (
            "atr",
            "ATR",
            "value",
            "last",
        ):

            if key in atr_data:

                value = atr_data[key]

                if isinstance(
                    value,
                    (list, tuple),
                ):

                    if value:
                        return _safe_float(
                            value[-1]
                        )

                return _safe_float(
                    value
                )

    return None


# ============================================================
# INDICATEURS
# ============================================================

def _calculer_indicateurs(
    candles: list[dict],
) -> Dict[str, Any]:
    """
    Calcule les indicateurs nécessaires au pipeline.
    """

    if not candles:
        return {}

    result: Dict[str, Any] = {}

    try:

        result["ema20"] = calculer_ema(
            candles,
            20,
        )

    except Exception as exc:

        logger.warning(
            "EMA20 impossible : %s",
            exc,
        )

        result["ema20"] = None

    try:

        result["ema50"] = calculer_ema(
            candles,
            50,
        )

    except Exception as exc:

        logger.warning(
            "EMA50 impossible : %s",
            exc,
        )

        result["ema50"] = None

    try:

        result["rsi"] = calculer_rsi(
            candles,
        )

    except Exception as exc:

        logger.warning(
            "RSI impossible : %s",
            exc,
        )

        result["rsi"] = None

    try:

        result["atr"] = calculer_atr(
            candles,
        )

    except Exception as exc:

        logger.warning(
            "ATR impossible : %s",
            exc,
        )

        result["atr"] = None

    return result


# ============================================================
# CONTEXTE INDICATEURS
# ============================================================

def _construire_contexte_indicateurs(
    indicators: Dict[str, Any],
    price: Optional[float],
) -> Dict[str, Any]:
    """
    Transforme les indicateurs bruts en contexte exploitable
    par le moteur de score.
    """

    result = dict(
        indicators
    )

    ema20 = _safe_float(
        indicators.get("ema20")
    )

    ema50 = _safe_float(
        indicators.get("ema50")
    )

    rsi = _safe_float(
        indicators.get("rsi")
    )

    # --------------------------------------------------------
    # EMA CONTEXT
    # --------------------------------------------------------

    if (
        ema20 is not None
        and ema50 is not None
    ):

        if ema20 > ema50:

            result["ema_context"] = "bullish"

        elif ema20 < ema50:

            result["ema_context"] = "bearish"

        else:

            result["ema_context"] = "neutral"

    else:

        result["ema_context"] = "neutral"

    # --------------------------------------------------------
    # RSI CONTEXT
    # --------------------------------------------------------

    if rsi is None:

        result["rsi_context"] = "neutral"

    elif rsi <= 30:

        result["rsi_context"] = "oversold"

    elif rsi >= 70:

        result["rsi_context"] = "overbought"

    elif rsi >= 50:

        result["rsi_context"] = "bullish_bias"

    else:

        result["rsi_context"] = "bearish_bias"

    result["price"] = price

    return result


# ============================================================
# EXTRACTION BIAS
# ============================================================

def _extract_bias(
    analysis: Dict[str, Any],
) -> str:
    """
    Extrait le biais d'une analyse structurelle.
    """

    if not isinstance(
        analysis,
        dict,
    ):
        return NEUTRAL.lower()

    bias = analysis.get(
        "bias"
    )

    return _normalize_bias(
        bias
    )


# ============================================================
# DIRECTION GLOBALE
# ============================================================

def _determiner_direction(
    h4_bias: str,
    h1_bias: str,
    m15_bias: str,
) -> str:
    """
    Détermine la direction dominante H4/H1/M15.

    Aucun signal n'est généré ici.
    """

    bullish = 0
    bearish = 0

    for bias in (
        h4_bias,
        h1_bias,
        m15_bias,
    ):

        normalized = _normalize_bias(
            bias
        )

        if normalized == "bullish":
            bullish += 1

        elif normalized == "bearish":
            bearish += 1

    if bullish > bearish:
        return BUY

    if bearish > bullish:
        return SELL

    return NEUTRAL


# ============================================================
# EXTRACTION SWING
# ============================================================

def _extract_swing_range(
    structure_analysis: Dict[str, Any],
    candles: list[dict],
) -> tuple[Optional[float], Optional[float]]:
    """
    Cherche un swing high / swing low exploitable.

    Supporte plusieurs formats possibles provenant de
    structure.py.
    """

    swing_high = None
    swing_low = None

    if isinstance(
        structure_analysis,
        dict,
    ):

        # ----------------------------------------------------
        # Format direct
        # ----------------------------------------------------

        swing_high = (
            structure_analysis.get(
                "swing_high"
            )
            or structure_analysis.get(
                "latest_swing_high"
            )
        )

        swing_low = (
            structure_analysis.get(
                "swing_low"
            )
            or structure_analysis.get(
                "latest_swing_low"
            )
        )

        # ----------------------------------------------------
        # Format swings
        # ----------------------------------------------------

        swings = structure_analysis.get(
            "swings"
        )

        if isinstance(
            swings,
            dict,
        ):

            if swing_high is None:

                swing_high = (
                    swings.get(
                        "high"
                    )
                    or swings.get(
                        "swing_high"
                    )
                )

            if swing_low is None:

                swing_low = (
                    swings.get(
                        "low"
                    )
                    or swings.get(
                        "swing_low"
                    )
                )

    swing_high = _safe_float(
        swing_high
    )

    swing_low = _safe_float(
        swing_low
    )

    # --------------------------------------------------------
    # Fallback sécurisé
    # --------------------------------------------------------

    if (
        swing_high is None
        or swing_low is None
    ):

        highs = []
        lows = []

        for candle in candles:

            if not isinstance(
                candle,
                dict,
            ):
                continue

            high = _safe_float(
                candle.get("high")
            )

            low = _safe_float(
                candle.get("low")
            )

            if high is not None:
                highs.append(high)

            if low is not None:
                lows.append(low)

        if highs:
            swing_high = max(highs)

        if lows:
            swing_low = min(lows)

    if (
        swing_high is None
        or swing_low is None
    ):
        return None, None

    if swing_high <= swing_low:
        return None, None

    return (
        swing_high,
        swing_low,
    )


# ============================================================
# ANALYSE D'UNE TIMEFRAME
# ============================================================

def analyser_timeframe(
    symbol: str,
    timeframe: str,
    limit: int = 200,
) -> Dict[str, Any]:
    """
    Analyse une timeframe complète.

    Retourne :
        candles
        price
        indicators
        structure
        bias
    """

    logger.info(
        "Analyse %s | %s",
        symbol,
        timeframe,
    )

    candles = get_candles(
        symbol,
        timeframe,
        limit=limit,
    )

    if not candles:
        raise ValueError(
            f"Aucune donnée reçue pour "
            f"{symbol} {timeframe}."
        )

    price = _extract_latest_close(
        candles
    )

    indicators_raw = _calculer_indicateurs(
        candles
    )

    indicators = (
        _construire_contexte_indicateurs(
            indicators_raw,
            price,
        )
    )

    structure = analyser_structure(
        candles
    )

    if not isinstance(
        structure,
        dict,
    ):
        structure = {}

    bias = _extract_bias(
        structure
    )

    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "candles": candles,
        "price": price,
        "indicators": indicators,
        "structure": structure,
        "bias": bias,
    }


# ============================================================
# ANALYSE PRINCIPALE
# ============================================================

def analyser_marche(
    symbol: str = DEFAULT_SYMBOL,
    timeframe: str = DEFAULT_TIMEFRAME,
    limit: int = 200,
    minimum_rr: float = 2.0,
    minimum_score: int = 80,
) -> Dict[str, Any]:
    """
    Analyse complète du marché.

    Pipeline :

        H4
        H1
        M15
        M5
          ↓
        structure
          ↓
        Fibonacci
          ↓
        score
          ↓
        RR
          ↓
        filtre qualité

    Aucun signal Telegram n'est envoyé ici.
    """

    logger.info(
        "=============================================="
    )

    logger.info(
        "VISION TRADE AI V2 | ANALYSE | %s",
        symbol,
    )

    logger.info(
        "=============================================="
    )

    # ========================================================
    # 1. H4
    # ========================================================

    h4 = analyser_timeframe(
        symbol,
        "H4",
        limit,
    )

    # ========================================================
    # 2. H1
    # ========================================================

    h1 = analyser_timeframe(
        symbol,
        "H1",
        limit,
    )

    # ========================================================
    # 3. M15
    # ========================================================

    m15 = analyser_timeframe(
        symbol,
        "M15",
        limit,
    )

    # ========================================================
    # 4. M5
    # ========================================================

    m5 = analyser_timeframe(
        symbol,
        "M5",
        limit,
    )

    # ========================================================
    # BIAIS
    # ========================================================

    h4_bias = h4["bias"]
    h1_bias = h1["bias"]
    m15_bias = m15["bias"]
    m5_bias = m5["bias"]

    direction = _determiner_direction(
        h4_bias,
        h1_bias,
        m15_bias,
    )

    # ========================================================
    # PAS DE DIRECTION = PAS DE SETUP
    # ========================================================

    if direction == NEUTRAL:

        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "status": "WAIT",
            "direction": NEUTRAL,
            "reason": (
                "Aucune direction dominante "
                "H4/H1/M15."
            ),
            "h4": h4,
            "h1": h1,
            "m15": m15,
            "m5": m5,
        }

    # ========================================================
    # FIBONACCI
    # ========================================================

    swing_high, swing_low = (
        _extract_swing_range(
            m15["structure"],
            m15["candles"],
        )
    )

    fibonacci = {}

    if (
        swing_high is not None
        and swing_low is not None
        and m15["price"] is not None
    ):

        try:

            fibonacci = analyser_fibonacci(
                price=m15["price"],
                swing_high=swing_high,
                swing_low=swing_low,
                direction=(
                    "bullish"
                    if direction == BUY
                    else "bearish"
                ),
            )

        except Exception as exc:

            logger.warning(
                "Fibonacci indisponible : %s",
                exc,
            )

    # ========================================================
    # INDICATEURS
    # ========================================================

    indicators = m15["indicators"]

    # ========================================================
    # SCORE
    # ========================================================

    score = calculer_score(
        direction=direction,
        h4_bias=h4_bias,
        h1_analysis=h1["structure"],
        m15_analysis=m15["structure"],
        m5_analysis=m5["structure"],
        fibonacci_analysis=fibonacci,
        indicators=indicators,
    )

    # ========================================================
    # RR
    # ========================================================

    price = m15["price"]

    atr = _extract_latest_atr(
        indicators.get("atr")
    )

    rr_result = {}
    rr_summary = {}

    # --------------------------------------------------------
    # SL basé sur ATR
    # --------------------------------------------------------

    if (
        price is not None
        and atr is not None
        and atr > 0
    ):

        if direction == BUY:

            stop_loss = (
                price - atr
            )

        else:

            stop_loss = (
                price + atr
            )

        try:

            rr_object = calculer_rr_complet(
                entry=price,
                stop_loss=stop_loss,
                direction=direction,
                minimum_rr=minimum_rr,
            )

            rr_result = {
                "direction": rr_object.direction,
                "entry": rr_object.entry,
                "stop_loss": rr_object.stop_loss,
                "risk": rr_object.risk,
                "tp1": rr_object.tp1,
                "tp2": rr_object.tp2,
                "tp3": rr_object.tp3,
                "rr_tp1": rr_object.rr_tp1,
                "rr_tp2": rr_object.rr_tp2,
                "rr_tp3": rr_object.rr_tp3,
                "minimum_rr": rr_object.minimum_rr,
                "passes_rr_filter": (
                    rr_object.passes_rr_filter
                ),
            }

            rr_summary = resume_rr(
                rr_object
            )

        except Exception as exc:

            logger.warning(
                "Calcul RR impossible : %s",
                exc,
            )

    # ========================================================
    # FILTRE QUALITÉ
    # ========================================================

    quality = filtrer_qualite(
        direction=direction,

        score_result=score,

        rr_result=rr_result,

        h4_bias=h4_bias,
        h1_bias=h1_bias,
        m15_bias=m15_bias,
        m5_bias=m5_bias,

        news=None,

        minimum_score=minimum_score,
        minimum_rr=minimum_rr,
    )

    # ========================================================
    # RÉSULTAT
    # ========================================================

    result = {
        "symbol": symbol,
        "timeframe": timeframe,

        "status": quality["status"],

        "direction": direction,

        "price": price,

        "h4_bias": h4_bias,
        "h1_bias": h1_bias,
        "m15_bias": m15_bias,
        "m5_bias": m5_bias,

        "h4": h4,
        "h1": h1,
        "m15": m15,
        "m5": m5,

        "fibonacci": fibonacci,

        "indicators": indicators,

        "score": score,

        "rr": rr_result,
        "rr_summary": rr_summary,

        "quality": quality,

        "ready_for_signal": (
            quality["ready_for_signal"]
        ),
    }

    logger.info(
        "Analyse terminée | %s | score=%s | RR=%s | status=%s",
        direction,
        score.get("final_score"),
        rr_result.get("rr_tp2"),
        quality.get("status"),
    )

    return result


# ============================================================
# INTERFACE PUBLIQUE
# ============================================================

def analyser(
    symbol: str = DEFAULT_SYMBOL,
    timeframe: str = DEFAULT_TIMEFRAME,
) -> Dict[str, Any]:
    """
    Interface publique simplifiée.
    """

    return analyser_marche(
        symbol=symbol,
        timeframe=timeframe,
    )


# ============================================================
# TEST INTERNE
# ============================================================

def _run_internal_test() -> None:
    """
    Test structurel du module.

    Le test vérifie uniquement les fonctions locales
    qui ne nécessitent pas d'appel API.
    """

    assert _normalize_direction(
        "buy"
    ) == BUY

    assert _normalize_direction(
        "SELL"
    ) == SELL

    assert _normalize_bias(
        "bullish"
    ) == "bullish"

    assert _normalize_bias(
        "bearish"
    ) == "bearish"

    assert _normalize_bias(
        None
    ) == "neutral"

    assert _determiner_direction(
        "bullish",
        "bullish",
        "bullish",
    ) == BUY

    assert _determiner_direction(
        "bearish",
        "bearish",
        "bearish",
    ) == SELL

    candles = [
        {
            "open": 100,
            "high": 105,
            "low": 95,
            "close": 102,
        },
        {
            "open": 102,
            "high": 108,
            "low": 99,
            "close": 106,
        },
    ]

    assert _extract_latest_close(
        candles
    ) == 106.0

    logger.info(
        "Test analyse.py réussi."
    )


# ============================================================
# EXÉCUTION DIRECTE
# ============================================================

if __name__ == "__main__":

    logging.basicConfig(
        level=logging.INFO,
        format=(
            "%(asctime)s | %(levelname)s | "
            "%(name)s | %(message)s"
        ),
    )

    print("=" * 60)
    print(
        "VISION TRADE AI V2 - TEST ANALYSE"
    )
    print("=" * 60)

    try:

        _run_internal_test()

        print(
            "\n✅ ANALYSE : OK"
        )

        print(
            "Orchestrateur déterministe opérationnel."
        )

    except Exception as exc:

        print(
            "\n❌ TEST ANALYSE ÉCHOUÉ"
        )

        print(
            f"Erreur : {exc}"
        )