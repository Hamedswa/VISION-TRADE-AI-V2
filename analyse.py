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
    RÉSULTAT

IMPORTANT :
- Ce module orchestre les modules déterministes.
- Il ne remplace pas structure.py, score.py ou rr.py.
- Aucune décision basée sur Groq ici.
- Aucune décision Telegram ici.
- L'IA sera ajoutée après validation complète du pipeline.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from data import get_candles
from indicateurs import (
    calculer_ema,
    calculer_rsi,
    calculer_atr,
)
from structure import (
    analyser_structure,
    detecter_fvg,
    detecter_order_blocks,
)
from fibonacci import *
from score import calculer_score
from rr import calculer_rr_complet
from filtre_qualite import filtrer_qualite


logger = logging.getLogger(__name__)


# ============================================================
# CONSTANTES
# ============================================================

BUY = "BUY"
SELL = "SELL"

NEUTRAL = "NEUTRAL"

DEFAULT_SYMBOL = "XAU/USD"

DEFAULT_TIMEFRAMES = (
    "H4",
    "H1",
    "M15",
    "M5",
)

DEFAULT_MIN_SCORE = 80
DEFAULT_MIN_RR = 2.0


# ============================================================
# OUTILS
# ============================================================

def _safe_float(
    value: Any,
    default: float = 0.0,
) -> float:
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

    value = str(
        direction or ""
    ).upper().strip()

    if value not in {
        BUY,
        SELL,
    }:
        return NEUTRAL

    return value


def _get_last_close(
    candles: list,
) -> float:
    """
    Récupère le dernier prix de clôture.
    """

    if not candles:
        raise ValueError(
            "Aucune bougie disponible."
        )

    last = candles[-1]

    if isinstance(last, dict):

        for key in (
            "close",
            "Close",
            "CLOSE",
        ):

            if key in last:
                return _safe_float(
                    last[key]
                )

    raise ValueError(
        "Impossible de récupérer le prix de clôture."
    )


def _get_value(
    obj: Any,
    key: str,
    default: Any = None,
) -> Any:
    """
    Récupération sécurisée d'une valeur
    depuis un dictionnaire ou un objet.
    """

    if obj is None:
        return default

    if isinstance(obj, dict):

        return obj.get(
            key,
            default,
        )

    return getattr(
        obj,
        key,
        default,
    )


# ============================================================
# EXTRACTION DE BIAIS
# ============================================================

def _extract_bias(
    structure_result: Any,
) -> str:
    """
    Extrait le biais d'une analyse de structure.
    """

    bias = _get_value(
        structure_result,
        "bias",
        None,
    )

    if bias is None:
        return NEUTRAL

    value = str(
        bias
    ).lower().strip()

    if value in {
        "buy",
        "bullish",
        "long",
    }:
        return BUY

    if value in {
        "sell",
        "bearish",
        "short",
    }:
        return SELL

    return NEUTRAL


# ============================================================
# EXTRACTION DES DERNIERS ÉLÉMENTS
# ============================================================

def _extract_latest(
    structure_result: Any,
) -> Dict[str, Any]:
    """
    Extrait les informations récentes
    d'une analyse de structure.
    """

    latest = _get_value(
        structure_result,
        "latest",
        {},
    )

    if isinstance(latest, dict):
        return latest

    return {}


# ============================================================
# ANALYSE D'UNE TIMEFRAME
# ============================================================

def analyser_timeframe(
    candles: list,
    timeframe: str,
) -> Dict[str, Any]:
    """
    Analyse une timeframe.

    Étapes :

        bougies
          ↓
        indicateurs
          ↓
        structure
          ↓
        FVG
          ↓
        Order Blocks
    """

    if not candles:

        raise ValueError(
            f"Aucune donnée disponible pour {timeframe}."
        )

    # ========================================================
    # INDICATEURS
    # ========================================================

    ema20 = calculer_ema(
        candles,
        period=20,
    )

    ema50 = calculer_ema(
        candles,
        period=50,
    )

    rsi = calculer_rsi(
        candles,
    )

    atr = calculer_atr(
        candles,
    )

    # ========================================================
    # STRUCTURE
    # ========================================================

    structure = analyser_structure(
        candles
    )

    # ========================================================
    # FVG
    # ========================================================

    try:

        fvg = detecter_fvg(
            candles
        )

    except Exception as exc:

        logger.warning(
            "Détection FVG échouée sur %s : %s",
            timeframe,
            exc,
        )

        fvg = []

    # ========================================================
    # ORDER BLOCKS
    # ========================================================

    try:

        order_blocks = detecter_order_blocks(
            candles
        )

    except Exception as exc:

        logger.warning(
            "Détection Order Block échouée sur %s : %s",
            timeframe,
            exc,
        )

        order_blocks = []

    # ========================================================
    # BIAIS
    # ========================================================

    bias = _extract_bias(
        structure
    )

    latest = _extract_latest(
        structure
    )

    return {
        "timeframe": timeframe,

        "candles_count": len(
            candles
        ),

        "ema20": ema20,
        "ema50": ema50,

        "rsi": rsi,
        "atr": atr,

        "structure": structure,

        "bias": bias,

        "latest": latest,

        "fvg": fvg,

        "order_blocks": order_blocks,
    }


# ============================================================
# CHARGEMENT MULTI-TIMEFRAME
# ============================================================

def charger_donnees_multi_timeframe(
    symbol: str = DEFAULT_SYMBOL,
) -> Dict[str, list]:
    """
    Charge les données H4 / H1 / M15 / M5.
    """

    result = {}

    for timeframe in DEFAULT_TIMEFRAMES:

        logger.info(
            "Chargement %s %s...",
            symbol,
            timeframe,
        )

        try:

            candles = get_candles(
                symbol,
                timeframe,
            )

        except TypeError:

            # Compatibilité avec une éventuelle
            # signature différente.
            candles = get_candles(
                symbol=symbol,
                timeframe=timeframe,
            )

        if not candles:

            logger.warning(
                "Aucune bougie pour %s.",
                timeframe,
            )

            result[timeframe] = []

        else:

            result[timeframe] = candles

    return result


# ============================================================
# DÉTERMINATION DE LA DIRECTION
# ============================================================

def determiner_direction(
    h4: Dict[str, Any],
    h1: Dict[str, Any],
    m15: Dict[str, Any],
) -> str:
    """
    Détermine la direction principale.

    Priorité :

        H4
        H1
        M15

    Le M5 ne détermine pas la direction principale.
    Il sert de confirmation.
    """

    biases = [
        h4.get("bias", NEUTRAL),
        h1.get("bias", NEUTRAL),
        m15.get("bias", NEUTRAL),
    ]

    buy_count = biases.count(BUY)
    sell_count = biases.count(SELL)

    if buy_count > sell_count:
        return BUY

    if sell_count > buy_count:
        return SELL

    return NEUTRAL


# ============================================================
# CONTEXTE INDICATEURS
# ============================================================

def construire_contexte_indicateurs(
    analysis: Dict[str, Any],
    direction: str,
) -> Dict[str, Any]:
    """
    Construit le contexte utilisé par score.py.
    """

    ema20 = _safe_float(
        analysis.get("ema20")
    )

    ema50 = _safe_float(
        analysis.get("ema50")
    )

    rsi = _safe_float(
        analysis.get("rsi")
    )

    ema_context = NEUTRAL

    if ema20 > 0 and ema50 > 0:

        if ema20 > ema50:
            ema_context = "bullish"

        elif ema20 < ema50:
            ema_context = "bearish"

    rsi_context = ""

    if direction == BUY:

        if rsi <= 30:
            rsi_context = "oversold"

        elif rsi >= 70:
            rsi_context = "overbought"

        elif rsi >= 50:
            rsi_context = "bullish_bias"

    elif direction == SELL:

        if rsi >= 70:
            rsi_context = "overbought"

        elif rsi <= 30:
            rsi_context = "oversold"

        elif rsi <= 50:
            rsi_context = "bearish_bias"

    return {
        "ema20": ema20,
        "ema50": ema50,
        "rsi": rsi,

        "ema_context": ema_context,
        "rsi_context": rsi_context,

        "direction": direction,
    }


# ============================================================
# FIBONACCI
# ============================================================

def construire_fibonacci(
    candles: list,
    direction: str,
) -> Dict[str, Any]:
    """
    Prépare l'analyse Fibonacci.

    Le module fibonacci.py reste responsable
    des calculs Fibonacci.
    """

    if not candles:
        return {}

    try:

        # Tentative d'utilisation de la fonction publique
        # si elle existe dans fibonacci.py.

        if direction == BUY:

            fonction = globals().get(
                "calculer_fibonacci"
            )

        else:

            fonction = globals().get(
                "calculer_fibonacci"
            )

        if fonction:

            try:

                result = fonction(
                    candles,
                    direction,
                )

            except TypeError:

                result = fonction(
                    candles
                )

            if isinstance(
                result,
                dict,
            ):

                return result

    except Exception as exc:

        logger.warning(
            "Analyse Fibonacci indisponible : %s",
            exc,
        )

    return {}


# ============================================================
# CALCUL DU SL
# ============================================================

def determiner_stop_loss(
    direction: str,
    entry: float,
    m15_analysis: Dict[str, Any],
    h1_analysis: Dict[str, Any],
    atr: float = 0.0,
) -> Optional[float]:
    """
    Détermine un SL technique.

    Priorité :

        structure M15
        structure H1
        ATR de sécurité

    Cette fonction ne calcule pas le RR.
    """

    latest_m15 = m15_analysis.get(
        "latest",
        {},
    )

    latest_h1 = h1_analysis.get(
        "latest",
        {},
    )

    candidates = []

    # --------------------------------------------------------
    # M15
    # --------------------------------------------------------

    for source in (
        latest_m15,
        latest_h1,
    ):

        if not isinstance(
            source,
            dict,
        ):
            continue

        for key in (
            "swing_low",
            "swing_high",
            "low",
            "high",
        ):

            value = source.get(
                key
            )

            if value is not None:

                value = _safe_float(
                    value
                )

                if value > 0:
                    candidates.append(
                        value
                    )

    # --------------------------------------------------------
    # SL structurel
    # --------------------------------------------------------

    if direction == BUY:

        below_entry = [
            value
            for value in candidates
            if value < entry
        ]

        if below_entry:

            return max(
                below_entry
            )

        if atr > 0:

            return entry - (
                atr * 1.5
            )

    else:

        above_entry = [
            value
            for value in candidates
            if value > entry
        ]

        if above_entry:

            return min(
                above_entry
            )

        if atr > 0:

            return entry + (
                atr * 1.5
            )

    return None


# ============================================================
# ANALYSE PRINCIPALE
# ============================================================

def analyser_marche(
    symbol: str = DEFAULT_SYMBOL,
) -> Dict[str, Any]:
    """
    Analyse complète du marché.

    Retourne toutes les données nécessaires
    aux modules supérieurs.
    """

    logger.info(
        "Début analyse Vision Trade AI V2 : %s",
        symbol,
    )

    # ========================================================
    # DATA
    # ========================================================

    market_data = (
        charger_donnees_multi_timeframe(
            symbol
        )
    )

    # ========================================================
    # ANALYSE TIMEFRAMES
    # ========================================================

    analyses = {}

    for timeframe in DEFAULT_TIMEFRAMES:

        candles = market_data.get(
            timeframe,
            [],
        )

        if not candles:

            analyses[timeframe] = {}

            continue

        analyses[timeframe] = analyser_timeframe(
            candles,
            timeframe,
        )

    h4 = analyses.get(
        "H4",
        {},
    )

    h1 = analyses.get(
        "H1",
        {},
    )

    m15 = analyses.get(
        "M15",
        {},
    )

    m5 = analyses.get(
        "M5",
        {},
    )

    # ========================================================
    # DIRECTION
    # ========================================================

    direction = determiner_direction(
        h4,
        h1,
        m15,
    )

    if direction == NEUTRAL:

        return {
            "status": "NO_DIRECTION",
            "symbol": symbol,
            "direction": NEUTRAL,
            "analyses": analyses,
        }

    logger.info(
        "Direction principale : %s",
        direction,
    )

    # ========================================================
    # INDICATEURS
    # ========================================================

    indicator_context = (
        construire_contexte_indicateurs(
            m15,
            direction,
        )
    )

    # ========================================================
    # FIBONACCI
    # ========================================================

    fibonacci_analysis = (
        construire_fibonacci(
            market_data.get(
                "M15",
                [],
            ),
            direction,
        )
    )

    # ========================================================
    # SCORE
    # ========================================================

    score_result = calculer_score(
        direction=direction,

        h4_bias=h4.get(
            "bias",
            NEUTRAL,
        ),

        h1_analysis=h1,

        m15_analysis=m15,

        m5_analysis=m5,

        fibonacci_analysis=fibonacci_analysis,

        indicators=indicator_context,

        threshold=DEFAULT_MIN_SCORE,
    )

    logger.info(
        "Score %s : %s/100",
        direction,
        score_result.get(
            "final_score"
        ),
    )

    # ========================================================
    # ENTRY
    # ========================================================

    entry = _get_last_close(
        market_data.get(
            "M15",
            [],
        )
    )

    # ========================================================
    # ATR
    # ========================================================

    atr = _safe_float(
        m15.get(
            "atr",
            0,
        )
    )

    # ========================================================
    # STOP LOSS
    # ========================================================

    stop_loss = determiner_stop_loss(
        direction=direction,

        entry=entry,

        m15_analysis=m15,

        h1_analysis=h1,

        atr=atr,
    )

    # ========================================================
    # RR
    # ========================================================

    if stop_loss is None:

        logger.warning(
            "Impossible de déterminer le Stop Loss."
        )

        return {
            "status": "NO_STOP_LOSS",
            "symbol": symbol,
            "direction": direction,
            "entry": entry,
            "score": score_result,
            "analyses": analyses,
        }

    try:

        rr_result = calculer_rr_complet(
            entry=entry,

            stop_loss=stop_loss,

            direction=direction,

            minimum_rr=DEFAULT_MIN_RR,
        )

        rr_data = {
            "direction": rr_result.direction,

            "entry": rr_result.entry,

            "stop_loss": rr_result.stop_loss,

            "risk": rr_result.risk,

            "tp1": rr_result.tp1,
            "tp2": rr_result.tp2,
            "tp3": rr_result.tp3,

            "reward_tp1": rr_result.reward_tp1,
            "reward_tp2": rr_result.reward_tp2,
            "reward_tp3": rr_result.reward_tp3,

            "rr_tp1": rr_result.rr_tp1,
            "rr_tp2": rr_result.rr_tp2,
            "rr_tp3": rr_result.rr_tp3,

            "minimum_rr": rr_result.minimum_rr,

            "passes_rr_filter": (
                rr_result.passes_rr_filter
            ),
        }

    except Exception as exc:

        logger.exception(
            "Erreur calcul RR."
        )

        return {
            "status": "RR_ERROR",
            "symbol": symbol,
            "direction": direction,
            "entry": entry,
            "stop_loss": stop_loss,
            "score": score_result,
            "error": str(exc),
            "analyses": analyses,
        }

    # ========================================================
    # FILTRE QUALITÉ
    # ========================================================

    quality_result = filtrer_qualite(
        direction=direction,

        score_result=score_result,

        rr_result=rr_data,

        h4_bias=h4.get(
            "bias"
        ),

        h1_bias=h1.get(
            "bias"
        ),

        m15_bias=m15.get(
            "bias"
        ),

        m5_bias=m5.get(
            "bias"
        ),

        news=None,

        minimum_score=DEFAULT_MIN_SCORE,

        minimum_rr=DEFAULT_MIN_RR,
    )

    # ========================================================
    # RÉSULTAT FINAL
    # ========================================================

    status = quality_result.get(
        "status",
        "REJECT",
    )

    result = {
        "status": status,

        "symbol": symbol,

        "direction": direction,

        "entry": entry,

        "stop_loss": stop_loss,

        "score": score_result,

        "rr": rr_data,

        "quality": quality_result,

        "indicators": indicator_context,

        "fibonacci": fibonacci_analysis,

        "analyses": analyses,

        "ready_for_signal": (
            quality_result.get(
                "ready_for_signal",
                False,
            )
        ),
    }

    logger.info(
        "Analyse terminée : %s | %s | score=%s | RR=%.2f",
        symbol,
        status,
        score_result.get(
            "final_score"
        ),
        rr_data.get(
            "rr_tp2",
            0,
        ),
    )

    return result


# ============================================================
# ALIAS COMPATIBILITÉ
# ============================================================

def analyse(
    symbol: str = DEFAULT_SYMBOL,
) -> Dict[str, Any]:
    """
    Alias public de analyser_marche().
    """

    return analyser_marche(
        symbol
    )


# ============================================================
# TEST
# ============================================================

def _run_internal_test() -> None:
    """
    Test minimal du module.

    Ce test vérifie surtout que les fonctions
    utilitaires fonctionnent sans appeler l'API.
    """

    assert _normalize_direction(
        "buy"
    ) == BUY

    assert _normalize_direction(
        "SELL"
    ) == SELL

    assert _normalize_direction(
        "xxx"
    ) == NEUTRAL

    assert _safe_float(
        "100.5"
    ) == 100.5

    indicators = (
        construire_contexte_indicateurs(
            {
                "ema20": 2000,
                "ema50": 1990,
                "rsi": 55,
            },
            BUY,
        )
    )

    assert (
        indicators["ema_context"]
        == "bullish"
    )

    assert (
        indicators["rsi_context"]
        == "bullish_bias"
    )

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
    print("VISION TRADE AI V2 - TEST ANALYSE")
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