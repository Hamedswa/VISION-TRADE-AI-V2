"""
Vision Trade AI V2
analyse.py

Orchestrateur principal de l'analyse technique.

Architecture :

    H4  -> tendance globale
    H1  -> structure
    M15 -> zones / contexte
    M5  -> confirmation / trigger

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
    STOP LOSS
      ↓
    RR
      ↓
    FILTRE QUALITÉ
      ↓
    RÉSULTAT

IMPORTANT :
- Ce module orchestre les modules déterministes.
- structure.py reste responsable de la structure.
- score.py reste responsable du score.
- rr.py reste responsable du calcul RR.
- filtre_qualite.py reste responsable du filtre final.
- Le M5 ne détermine jamais seul la direction principale.
- Aucune décision Telegram ici.
- Aucune décision Groq ici.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from config import (
    H4_TIMEFRAME,
    H1_TIMEFRAME,
    M15_TIMEFRAME,
    M5_TIMEFRAME,
    CANDLE_LIMIT,
    MIN_CANDLES,
)

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
# MAPPING TIMEFRAME
# ============================================================

TIMEFRAME_TO_API = {
    "H4": H4_TIMEFRAME,
    "H1": H1_TIMEFRAME,
    "M15": M15_TIMEFRAME,
    "M5": M5_TIMEFRAME,
}


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

    if value in {
        BUY,
        "BULLISH",
        "LONG",
    }:
        return BUY

    if value in {
        SELL,
        "BEARISH",
        "SHORT",
    }:
        return SELL

    return NEUTRAL


def _get_value(
    obj: Any,
    key: str,
    default: Any = None,
) -> Any:
    """
    Récupère une valeur depuis un dictionnaire
    ou un objet.
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

    if not isinstance(last, dict):
        raise ValueError(
            "Format de bougie invalide."
        )

    for key in (
        "close",
        "Close",
        "CLOSE",
    ):
        if key in last:
            price = _safe_float(
                last[key]
            )

            if price > 0:
                return price

    raise ValueError(
        "Impossible de récupérer le dernier prix de clôture."
    )


# ============================================================
# EXTRACTION BIAIS
# ============================================================

def _extract_bias(
    structure_result: Any,
) -> str:
    """
    Extrait le biais structurel.
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
# EXTRACTION DERNIERS ÉLÉMENTS
# ============================================================

def _extract_latest(
    structure_result: Any,
) -> Dict[str, Any]:
    """
    Extrait le bloc latest.
    """

    latest = _get_value(
        structure_result,
        "latest",
        {},
    )

    if isinstance(
        latest,
        dict,
    ):
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

    if len(candles) < MIN_CANDLES:
        logger.warning(
            "%s : seulement %s bougies disponibles "
            "(minimum recommandé : %s).",
            timeframe,
            len(candles),
            MIN_CANDLES,
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

        structure_breaks = []

        if isinstance(
            structure,
            dict,
        ):

            structure_breaks.extend(
                structure.get(
                    "bos",
                    [],
                )
            )

            structure_breaks.extend(
                structure.get(
                    "choch",
                    [],
                )
            )

        try:

            order_blocks = detecter_order_blocks(
                candles,
                structure_breaks,
            )

        except TypeError:

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

        "api_timeframe": TIMEFRAME_TO_API.get(
            timeframe,
            timeframe,
        ),

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
    Charge :

        H4  -> 4h
        H1  -> 1h
        M15 -> 15min
        M5  -> 5min
    """

    result: Dict[str, list] = {}

    for timeframe in DEFAULT_TIMEFRAMES:

        api_timeframe = TIMEFRAME_TO_API.get(
            timeframe
        )

        if not api_timeframe:

            logger.error(
                "Timeframe inconnue : %s",
                timeframe,
            )

            result[timeframe] = []

            continue

        logger.info(
            "Chargement %s %s -> %s...",
            symbol,
            timeframe,
            api_timeframe,
        )

        try:

            candles = get_candles(
                symbol,
                api_timeframe,
            )

        except TypeError:

            try:

                candles = get_candles(
                    symbol=symbol,
                    timeframe=api_timeframe,
                )

            except Exception as exc:

                logger.exception(
                    "Erreur chargement %s : %s",
                    timeframe,
                    exc,
                )

                candles = []

        except Exception as exc:

            logger.exception(
                "Erreur chargement %s : %s",
                timeframe,
                exc,
            )

            candles = []

        if not candles:

            logger.warning(
                "Aucune bougie pour %s.",
                timeframe,
            )

            result[timeframe] = []

        else:

            logger.info(
                "%s : %s bougies chargées.",
                timeframe,
                len(candles),
            )

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

    Hiérarchie :

        H4  = tendance globale
        H1  = structure
        M15 = zone / contexte

    Le M5 ne détermine PAS la direction principale.
    """

    h4_bias = _normalize_direction(
        h4.get(
            "bias",
            NEUTRAL,
        )
    )

    h1_bias = _normalize_direction(
        h1.get(
            "bias",
            NEUTRAL,
        )
    )

    m15_bias = _normalize_direction(
        m15.get(
            "bias",
            NEUTRAL,
        )
    )

    biases = [
        h4_bias,
        h1_bias,
        m15_bias,
    ]

    buy_count = biases.count(
        BUY
    )

    sell_count = biases.count(
        SELL
    )

    # --------------------------------------------------------
    # Accord fort
    # --------------------------------------------------------

    if buy_count >= 2 and buy_count > sell_count:
        return BUY

    if sell_count >= 2 and sell_count > buy_count:
        return SELL

    # --------------------------------------------------------
    # Priorité H4 + H1
    # --------------------------------------------------------

    if (
        h4_bias == BUY
        and h1_bias == BUY
    ):
        return BUY

    if (
        h4_bias == SELL
        and h1_bias == SELL
    ):
        return SELL

    return NEUTRAL


# ============================================================
# CONFIRMATION M5
# ============================================================

def verifier_confirmation_m5(
    direction: str,
    m5: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Vérifie le contexte M5.

    Le M5 confirme ou affaiblit le setup.
    Il ne crée jamais seul une direction.
    """

    direction = _normalize_direction(
        direction
    )

    m5_bias = _normalize_direction(
        m5.get(
            "bias",
            NEUTRAL,
        )
    )

    structure = m5.get(
        "structure",
        {},
    )

    latest = m5.get(
        "latest",
        {},
    )

    confirmation = False

    if m5_bias == direction:
        confirmation = True

    # --------------------------------------------------------
    # Vérification supplémentaire avec le dernier BOS/CHoCH
    # --------------------------------------------------------

    if isinstance(
        latest,
        dict,
    ):

        latest_bos = latest.get(
            "bos"
        )

        latest_choch = latest.get(
            "choch"
        )

        for event in (
            latest_bos,
            latest_choch,
        ):

            if not isinstance(
                event,
                dict,
            ):
                continue

            event_direction = _normalize_direction(
                event.get(
                    "direction"
                )
            )

            if event_direction == direction:
                confirmation = True

    return {
        "direction": direction,
        "m5_bias": m5_bias,
        "confirmed": confirmation,
        "structure_available": bool(
            structure
        ),
    }


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
        analysis.get(
            "ema20"
        )
    )

    ema50 = _safe_float(
        analysis.get(
            "ema50"
        )
    )

    rsi = _safe_float(
        analysis.get(
            "rsi"
        )
    )

    atr = _safe_float(
        analysis.get(
            "atr"
        )
    )

    direction = _normalize_direction(
        direction
    )

    ema_context = NEUTRAL

    if (
        ema20 > 0
        and ema50 > 0
    ):

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

        else:
            rsi_context = "bearish_bias"

    elif direction == SELL:

        if rsi >= 70:
            rsi_context = "overbought"

        elif rsi <= 30:
            rsi_context = "oversold"

        elif rsi <= 50:
            rsi_context = "bearish_bias"

        else:
            rsi_context = "bullish_bias"

    return {
        "ema20": ema20,
        "ema50": ema50,

        "rsi": rsi,

        "atr": atr,

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

    fibonacci.py reste responsable
    des calculs Fibonacci.
    """

    if not candles:
        return {}

    direction = _normalize_direction(
        direction
    )

    try:

        fonction = globals().get(
            "calculer_fibonacci"
        )

        if not callable(
            fonction
        ):
            return {}

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
# EXTRACTION DES SWINGS POUR LE SL
# ============================================================

def _extract_swing_prices(
    analysis: Dict[str, Any],
) -> Dict[str, list]:
    """
    Extrait correctement les swings depuis
    le résultat de structure.py.

    structure.py retourne :

        swings:
            highs: [...]
            lows: [...]

    et non directement :

        latest:
            swing_high
            swing_low
    """

    result = {
        "highs": [],
        "lows": [],
    }

    if not isinstance(
        analysis,
        dict,
    ):
        return result

    swings = analysis.get(
        "swings",
        {},
    )

    if not isinstance(
        swings,
        dict,
    ):
        return result

    highs = swings.get(
        "highs",
        [],
    )

    lows = swings.get(
        "lows",
        [],
    )

    for swing in highs:

        if isinstance(
            swing,
            dict,
        ):

            price = _safe_float(
                swing.get(
                    "price"
                )
            )

            if price > 0:
                result["highs"].append(
                    price
                )

    for swing in lows:

        if isinstance(
            swing,
            dict,
        ):

            price = _safe_float(
                swing.get(
                    "price"
                )
            )

            if price > 0:
                result["lows"].append(
                    price
                )

    return result


# ============================================================
# STOP LOSS
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

        1. Swing M15
        2. Swing H1
        3. Structure récente M15/H1
        4. ATR de sécurité

    BUY :

        SL sous le dernier swing low.

    SELL :

        SL au-dessus du dernier swing high.

    Le SL doit toujours être cohérent avec l'entrée.
    """

    direction = _normalize_direction(
        direction
    )

    entry = _safe_float(
        entry
    )

    atr = _safe_float(
        atr
    )

    if entry <= 0:
        return None

    # --------------------------------------------------------
    # Extraction correcte des swings
    # --------------------------------------------------------

    m15_swings = _extract_swing_prices(
        m15_analysis
    )

    h1_swings = _extract_swing_prices(
        h1_analysis
    )

    # --------------------------------------------------------
    # Candidats
    # --------------------------------------------------------

    if direction == BUY:

        candidates = []

        # M15 en priorité
        candidates.extend(
            value
            for value in m15_swings["lows"]
            if value < entry
        )

        # H1 ensuite
        candidates.extend(
            value
            for value in h1_swings["lows"]
            if value < entry
        )

        if candidates:

            # Le niveau le plus proche sous l'entrée.
            return max(
                candidates
            )

        # ----------------------------------------------------
        # Fallback ATR
        # ----------------------------------------------------

        if atr > 0:

            stop = entry - (
                atr * 1.5
            )

            if stop > 0:
                return stop

    elif direction == SELL:

        candidates = []

        # M15 en priorité
        candidates.extend(
            value
            for value in m15_swings["highs"]
            if value > entry
        )

        # H1 ensuite
        candidates.extend(
            value
            for value in h1_swings["highs"]
            if value > entry
        )

        if candidates:

            # Le niveau le plus proche au-dessus de l'entrée.
            return min(
                candidates
            )

        # ----------------------------------------------------
        # Fallback ATR
        # ----------------------------------------------------

        if atr > 0:

            stop = entry + (
                atr * 1.5
            )

            if stop > 0:
                return stop

    return None


# ============================================================
# VALIDATION STOP LOSS
# ============================================================

def _validate_stop_loss(
    direction: str,
    entry: float,
    stop_loss: Optional[float],
) -> bool:
    """
    Vérifie que le SL est réellement exploitable.
    """

    if stop_loss is None:
        return False

    entry = _safe_float(
        entry
    )

    stop_loss = _safe_float(
        stop_loss
    )

    if entry <= 0:
        return False

    if stop_loss <= 0:
        return False

    direction = _normalize_direction(
        direction
    )

    if direction == BUY:
        return stop_loss < entry

    if direction == SELL:
        return stop_loss > entry

    return False


# ============================================================
# ANALYSE PRINCIPALE
# ============================================================

def analyser_marche(
    symbol: str = DEFAULT_SYMBOL,
) -> Dict[str, Any]:
    """
    Analyse complète du marché.
    """

    logger.info(
        "Début analyse Vision Trade AI V2 : %s",
        symbol,
    )

    # ========================================================
    # DATA
    # ========================================================

    market_data = charger_donnees_multi_timeframe(
        symbol
    )

    # ========================================================
    # VÉRIFICATION DATA
    # ========================================================

    missing = [
        timeframe
        for timeframe in DEFAULT_TIMEFRAMES
        if not market_data.get(
            timeframe
        )
    ]

    if missing:

        logger.warning(
            "Timeframes indisponibles : %s",
            ", ".join(
                missing
            ),
        )

    # ========================================================
    # ANALYSE TIMEFRAMES
    # ========================================================

    analyses: Dict[str, Dict[str, Any]] = {}

    for timeframe in DEFAULT_TIMEFRAMES:

        candles = market_data.get(
            timeframe,
            [],
        )

        if not candles:

            analyses[timeframe] = {}

            continue

        try:

            analyses[timeframe] = analyser_timeframe(
                candles,
                timeframe,
            )

        except Exception as exc:

            logger.exception(
                "Erreur analyse %s : %s",
                timeframe,
                exc,
            )

            analyses[timeframe] = {
                "error": str(exc),
            }

    # ========================================================
    # EXTRACTION
    # ========================================================

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

        logger.info(
            "Aucune direction claire : %s",
            symbol,
        )

        return {
            "status": "NO_DIRECTION",

            "symbol": symbol,

            "direction": NEUTRAL,

            "entry": None,

            "stop_loss": None,

            "score": {
                "final_score": 0,
            },

            "rr": {},

            "quality": {},

            "analyses": analyses,

            "ready_for_signal": False,
        }

    logger.info(
        "Direction principale : %s",
        direction,
    )

    # ========================================================
    # M5 CONFIRMATION
    # ========================================================

    m5_confirmation = verifier_confirmation_m5(
        direction,
        m5,
    )

    logger.info(
        "Confirmation M5 : %s | biais=%s",
        m5_confirmation.get(
            "confirmed"
        ),
        m5_confirmation.get(
            "m5_bias"
        ),
    )

    # ========================================================
    # INDICATEURS
    # ========================================================

    indicator_context = construire_contexte_indicateurs(
        m15,
        direction,
    )

    # ========================================================
    # FIBONACCI
    # ========================================================

    fibonacci_analysis = construire_fibonacci(
        market_data.get(
            "M15",
            [],
        ),
        direction,
    )

    # ========================================================
    # SCORE
    # ========================================================

    try:

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

    except Exception as exc:

        logger.exception(
            "Erreur calcul score."
        )

        return {
            "status": "SCORE_ERROR",

            "symbol": symbol,

            "direction": direction,

            "score": {
                "final_score": 0,
                "error": str(exc),
            },

            "analyses": analyses,

            "ready_for_signal": False,
        }

    final_score = _safe_float(
        score_result.get(
            "final_score",
            score_result.get(
                "score",
                0,
            ),
        )
    )

    logger.info(
        "Score %s : %.2f/100",
        direction,
        final_score,
    )

    # ========================================================
    # ENTRY
    # ========================================================

    m15_candles = market_data.get(
        "M15",
        [],
    )

    if not m15_candles:

        return {
            "status": "NO_ENTRY_DATA",

            "symbol": symbol,

            "direction": direction,

            "score": score_result,

            "analyses": analyses,

            "ready_for_signal": False,
        }

    try:

        entry = _get_last_close(
            m15_candles
        )

    except Exception as exc:

        logger.exception(
            "Impossible de déterminer l'entrée."
        )

        return {
            "status": "NO_ENTRY",

            "symbol": symbol,

            "direction": direction,

            "score": score_result,

            "error": str(exc),

            "analyses": analyses,

            "ready_for_signal": False,
        }

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
    # VALIDATION SL
    # ========================================================

    if not _validate_stop_loss(
        direction,
        entry,
        stop_loss,
    ):

        logger.warning(
            "SL invalide ou introuvable | "
            "symbol=%s direction=%s entry=%s atr=%s",
            symbol,
            direction,
            entry,
            atr,
        )

        return {
            "status": "NO_STOP_LOSS",

            "symbol": symbol,

            "direction": direction,

            "entry": entry,

            "stop_loss": None,

            "score": score_result,

            "analyses": analyses,

            "indicators": indicator_context,

            "fibonacci": fibonacci_analysis,

            "ready_for_signal": False,
        }

    logger.info(
        "Stop Loss : %.5f",
        stop_loss,
    )

    # ========================================================
    # RR
    # ========================================================

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

            "ready_for_signal": False,
        }

    # ========================================================
    # FILTRE QUALITÉ
    # ========================================================

    try:

        quality_result = filtrer_qualite(
            direction=direction,

            score_result=score_result,

            rr_result=rr_data,

            h4_bias=h4.get(
                "bias",
                NEUTRAL,
            ),

            h1_bias=h1.get(
                "bias",
                NEUTRAL,
            ),

            m15_bias=m15.get(
                "bias",
                NEUTRAL,
            ),

            m5_bias=m5.get(
                "bias",
                NEUTRAL,
            ),

            news=None,

            minimum_score=DEFAULT_MIN_SCORE,

            minimum_rr=DEFAULT_MIN_RR,
        )

    except Exception as exc:

        logger.exception(
            "Erreur filtre qualité."
        )

        return {
            "status": "QUALITY_ERROR",

            "symbol": symbol,

            "direction": direction,

            "entry": entry,

            "stop_loss": stop_loss,

            "score": score_result,

            "rr": rr_data,

            "error": str(exc),

            "analyses": analyses,

            "ready_for_signal": False,
        }

    # ========================================================
    # RÉSULTAT FINAL
    # ========================================================

    status = quality_result.get(
        "status",
        "REJECT",
    )

    ready_for_signal = bool(
        quality_result.get(
            "ready_for_signal",
            False,
        )
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

        "m5_confirmation": m5_confirmation,

        "analyses": analyses,

        "ready_for_signal": ready_for_signal,
    }

    logger.info(
        "Analyse terminée : %s | %s | "
        "score=%.2f | RR=%.2f | ready=%s",
        symbol,
        status,
        final_score,
        _safe_float(
            rr_data.get(
                "rr_tp2",
                0,
            )
        ),
        ready_for_signal,
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
# TEST INTERNE
# ============================================================

def _run_internal_test() -> None:
    """
    Test minimal sans appel API.
    """

    # Direction
    assert _normalize_direction(
        "buy"
    ) == BUY

    assert _normalize_direction(
        "SELL"
    ) == SELL

    assert _normalize_direction(
        "xxx"
    ) == NEUTRAL

    # Float
    assert _safe_float(
        "100.5"
    ) == 100.5

    # Indicateurs
    indicators = (
        construire_contexte_indicateurs(
            {
                "ema20": 2000,
                "ema50": 1990,
                "rsi": 55,
                "atr": 10,
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

    # Extraction swings
    fake_analysis = {
        "swings": {
            "highs": [
                {
                    "index": 10,
                    "price": 2050,
                },
            ],
            "lows": [
                {
                    "index": 12,
                    "price": 1980,
                },
            ],
        }
    }

    swings = _extract_swing_prices(
        fake_analysis
    )

    assert swings["highs"] == [
        2050
    ]

    assert swings["lows"] == [
        1980
    ]

    # SL BUY
    buy_sl = determiner_stop_loss(
        direction=BUY,

        entry=2000,

        m15_analysis=fake_analysis,

        h1_analysis={},

        atr=10,
    )

    assert buy_sl == 1980

    # SL SELL
    sell_sl = determiner_stop_loss(
        direction=SELL,

        entry=2000,

        m15_analysis=fake_analysis,

        h1_analysis={},

        atr=10,
    )

    assert sell_sl == 2050

    # Validation SL
    assert _validate_stop_loss(
        BUY,
        2000,
        1980,
    )

    assert _validate_stop_loss(
        SELL,
        2000,
        2050,
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

    print(
        "\nTIMEFRAME_TO_API :"
    )

    print(
        TIMEFRAME_TO_API
    )

    print(
        "\nDEFAULT_TIMEFRAMES :"
    )

    print(
        DEFAULT_TIMEFRAMES
    )

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