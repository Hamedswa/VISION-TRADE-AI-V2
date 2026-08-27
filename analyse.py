"""
Vision Trade AI V2
analyse.py

ORCHESTRATEUR PRINCIPAL

Architecture :

    H4  -> tendance globale
    H1  -> structure principale
    M15 -> contexte / zones
    M5  -> confirmation / trigger

Pipeline :

    DATA
      ↓
    INDICATEURS
      ↓
    STRUCTURE
      ↓
    DIRECTION H4/H1/M15
      ↓
    CONFIRMATION M5
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

Règles importantes :

- H4/H1/M15 déterminent la direction principale.
- M5 ne peut jamais créer une direction seul.
- Un timeframe NEUTRAL ne doit pas être forcé.
- structure.py reste déterministe.
- score.py reste responsable du score.
- rr.py reste responsable du RR.
- filtre_qualite.py reste responsable du filtre final.
- Fibonacci reçoit toujours l'analyse de structure correspondante.
- Aucune logique Telegram ici.
- Aucune logique Groq ici.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from config import (
    H4_TIMEFRAME,
    H1_TIMEFRAME,
    M15_TIMEFRAME,
    M5_TIMEFRAME,
    MIN_CANDLES,
)

from data import get_candles

from indicateurs import (
    calculer_ema,
    calculer_rsi,
    calculer_atr,
)

from structure import analyser_structure

from fibonacci import calculer_fibonacci

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

TIMEFRAMES = (
    "H4",
    "H1",
    "M15",
    "M5",
)

DEFAULT_MIN_SCORE = 80
DEFAULT_MIN_RR = 2.0


TIMEFRAME_TO_API = {
    "H4": H4_TIMEFRAME,
    "H1": H1_TIMEFRAME,
    "M15": M15_TIMEFRAME,
    "M5": M5_TIMEFRAME,
}


# ============================================================
# OUTILS NUMÉRIQUES
# ============================================================

def _safe_float(
    value: Any,
    default: float = 0.0,
) -> float:
    """
    Convertit proprement une valeur en float.
    """

    if value is None:
        return default

    if isinstance(value, (list, tuple)):

        if not value:
            return default

        for item in reversed(value):

            result = _safe_float(
                item,
                default=None,
            )

            if result is not None:
                return result

        return default

    if isinstance(value, dict):

        for key in (
            "value",
            "close",
            "price",
            "result",
            "last",
        ):

            if key in value:

                result = _safe_float(
                    value[key],
                    default=None,
                )

                if result is not None:
                    return result

        return default

    try:
        return float(value)

    except (
        TypeError,
        ValueError,
    ):
        return default


def _last_value(
    value: Any,
    default: float = 0.0,
) -> float:
    """
    Retourne la dernière valeur d'une série.
    """

    if isinstance(value, (list, tuple)):

        if not value:
            return default

        return _safe_float(
            value[-1],
            default,
        )

    return _safe_float(
        value,
        default,
    )


# ============================================================
# NORMALISATION DIRECTION
# ============================================================

def _normalize_direction(
    value: Any,
) -> str:
    """
    Normalise toutes les représentations de direction.

    BUY / BULLISH / LONG -> BUY
    SELL / BEARISH / SHORT -> SELL
    Tout le reste -> NEUTRAL
    """

    value = str(
        value or ""
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


# ============================================================
# EXTRACTION BIAS
# ============================================================

def _extract_bias(
    analysis: Dict[str, Any],
) -> str:
    """
    Extrait le bias d'une analyse de timeframe.
    """

    if not isinstance(
        analysis,
        dict,
    ):
        return NEUTRAL

    return _normalize_direction(
        analysis.get(
            "bias",
            NEUTRAL,
        )
    )


# ============================================================
# PRIX DE CLÔTURE
# ============================================================

def _get_last_close(
    candles: list,
) -> float:
    """
    Retourne le dernier prix de clôture.
    """

    if not candles:

        raise ValueError(
            "Aucune bougie disponible."
        )

    candle = candles[-1]

    if not isinstance(
        candle,
        dict,
    ):

        raise ValueError(
            "Format de bougie invalide."
        )

    for key in (
        "close",
        "Close",
        "CLOSE",
    ):

        if key in candle:

            value = _safe_float(
                candle[key]
            )

            if value > 0:
                return value

    raise ValueError(
        "Prix de clôture introuvable."
    )


# ============================================================
# ANALYSE D'UNE TIMEFRAME
# ============================================================

def analyser_timeframe(
    candles: list,
    timeframe: str,
) -> Dict[str, Any]:
    """
    Analyse complète d'un timeframe.

    DATA
      ↓
    INDICATEURS
      ↓
    STRUCTURE
    """

    if not candles:

        raise ValueError(
            f"Aucune bougie pour {timeframe}."
        )

    if len(candles) < MIN_CANDLES:

        logger.warning(
            "%s : seulement %s bougies disponibles.",
            timeframe,
            len(candles),
        )

    # ========================================================
    # INDICATEURS
    # ========================================================

    ema20 = _last_value(
        calculer_ema(
            candles,
            period=20,
        )
    )

    ema50 = _last_value(
        calculer_ema(
            candles,
            period=50,
        )
    )

    rsi = _last_value(
        calculer_rsi(
            candles,
        )
    )

    atr = _last_value(
        calculer_atr(
            candles,
        )
    )

    # ========================================================
    # STRUCTURE
    # ========================================================

    structure = analyser_structure(
        candles
    )

    bias = _extract_bias(
        structure
    )

    # ========================================================
    # DERNIÈRE STRUCTURE
    # ========================================================

    latest = {}

    if isinstance(
        structure,
        dict,
    ):

        latest = structure.get(
            "latest",
            {},
        )

        if not isinstance(
            latest,
            dict,
        ):
            latest = {}

    # ========================================================
    # FVG
    # ========================================================

    fvg = []

    if isinstance(
        structure,
        dict,
    ):

        fvg = structure.get(
            "fvg",
            [],
        )

        if not isinstance(
            fvg,
            list,
        ):
            fvg = []

    # ========================================================
    # ORDER BLOCKS
    # ========================================================

    order_blocks = []

    if isinstance(
        structure,
        dict,
    ):

        order_blocks = structure.get(
            "order_blocks",
            [],
        )

        if not isinstance(
            order_blocks,
            list,
        ):
            order_blocks = []

    # ========================================================
    # RÉSULTAT
    # ========================================================

    return {

        "timeframe":
            timeframe,

        "api_timeframe":
            TIMEFRAME_TO_API.get(
                timeframe,
                timeframe,
            ),

        "candles_count":
            len(candles),

        "ema20":
            ema20,

        "ema50":
            ema50,

        "rsi":
            rsi,

        "atr":
            atr,

        "structure":
            structure,

        "bias":
            bias,

        "latest":
            latest,

        "fvg":
            fvg,

        "order_blocks":
            order_blocks,
    }


# ============================================================
# CHARGEMENT MULTI-TIMEFRAME
# ============================================================

def charger_donnees_multi_timeframe(
    symbol: str = DEFAULT_SYMBOL,
) -> Dict[str, list]:
    """
    Charge H4, H1, M15 et M5.
    """

    result = {}

    for timeframe in TIMEFRAMES:

        api_timeframe = (
            TIMEFRAME_TO_API[
                timeframe
            ]
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

        result[timeframe] = (
            candles
            if candles
            else []
        )

        logger.info(
            "%s %s : %s bougies",
            symbol,
            timeframe,
            len(
                result[timeframe]
            ),
        )

    return result


# ============================================================
# DIRECTION PRINCIPALE
# ============================================================

def determiner_direction(
    h4: Dict[str, Any],
    h1: Dict[str, Any],
    m15: Dict[str, Any],
) -> str:
    """
    Détermine la direction principale.

    H4  = tendance globale
    H1  = structure principale
    M15 = contexte

    Règles :

    1. H4 est l'ancrage principal.
    2. H1 et M15 peuvent être NEUTRAL.
    3. H4 seul peut donner la direction si
       H1 et M15 sont NEUTRAL.
    4. H4 + H1 alignés -> direction H4.
    5. H4 + M15 alignés -> direction H4.
    6. H1 + M15 opposés à H4 -> NEUTRAL.
    7. H4 NEUTRAL + H1/M15 alignés -> direction.
    8. M5 n'intervient jamais.
    """

    if not isinstance(h4, dict):
        h4 = {}

    if not isinstance(h1, dict):
        h1 = {}

    if not isinstance(m15, dict):
        m15 = {}

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

    # ========================================================
    # H4 NEUTRAL
    # ========================================================

    if h4_bias == NEUTRAL:

        if (
            h1_bias != NEUTRAL
            and h1_bias == m15_bias
        ):

            return h1_bias

        return NEUTRAL

    # ========================================================
    # H4 + H1 ALIGNÉS
    # ========================================================

    if h1_bias == h4_bias:

        return h4_bias

    # ========================================================
    # H4 + M15 ALIGNÉS
    # ========================================================

    if m15_bias == h4_bias:

        return h4_bias

    # ========================================================
    # H4 SEUL
    # ========================================================

    if (
        h1_bias == NEUTRAL
        and m15_bias == NEUTRAL
    ):

        return h4_bias

    # ========================================================
    # H1 NEUTRAL MAIS M15 OPPOSE H4
    # ========================================================

    if (
        h1_bias == NEUTRAL
        and m15_bias != h4_bias
    ):

        return NEUTRAL

    # ========================================================
    # M15 NEUTRAL MAIS H1 OPPOSE H4
    # ========================================================

    if (
        m15_bias == NEUTRAL
        and h1_bias != h4_bias
    ):

        return NEUTRAL

    # ========================================================
    # H1 + M15 OPPOSÉS À H4
    # ========================================================

    if (
        h1_bias != NEUTRAL
        and m15_bias != NEUTRAL
        and h1_bias != h4_bias
        and m15_bias != h4_bias
        and h1_bias == m15_bias
    ):

        return NEUTRAL

    return NEUTRAL


# ============================================================
# CONFIRMATION M5
# ============================================================

def verifier_confirmation_m5(
    direction: str,
    m5: Dict[str, Any],
) -> Dict[str, Any]:
    """
    M5 confirme la direction.

    M5 ne peut jamais créer une direction.
    """

    direction = _normalize_direction(
        direction
    )

    if not isinstance(
        m5,
        dict,
    ):
        m5 = {}

    if direction == NEUTRAL:

        return {

            "direction":
                NEUTRAL,

            "m5_bias":
                NEUTRAL,

            "confirmed":
                False,

            "reason":
                "NO_MAIN_DIRECTION",
        }

    m5_bias = _extract_bias(
        m5
    )

    latest = m5.get(
        "latest",
        {},
    )

    if not isinstance(
        latest,
        dict,
    ):
        latest = {}

    confirmed = False
    confirmation_type = None

    # ========================================================
    # BIAIS M5
    # ========================================================

    if m5_bias == direction:

        confirmed = True

        confirmation_type = (
            "M5_BIAS"
        )

    # ========================================================
    # BOS
    # ========================================================

    latest_bos = latest.get(
        "bos"
    )

    if isinstance(
        latest_bos,
        dict,
    ):

        bos_direction = (
            _normalize_direction(
                latest_bos.get(
                    "direction"
                )
            )
        )

        if bos_direction == direction:

            confirmed = True

            confirmation_type = (
                "M5_BOS"
            )

    # ========================================================
    # CHOCH
    # ========================================================

    latest_choch = latest.get(
        "choch"
    )

    if isinstance(
        latest_choch,
        dict,
    ):

        choch_direction = (
            _normalize_direction(
                latest_choch.get(
                    "direction"
                )
            )
        )

        if choch_direction == direction:

            confirmed = True

            confirmation_type = (
                "M5_CHOCH"
            )

    return {

        "direction":
            direction,

        "m5_bias":
            m5_bias,

        "confirmed":
            confirmed,

        "confirmation_type":
            confirmation_type,
    }


# ============================================================
# CONTEXTE INDICATEURS
# ============================================================

def construire_contexte_indicateurs(
    analysis: Dict[str, Any],
    direction: str,
) -> Dict[str, Any]:
    """
    Construit le contexte EMA / RSI / ATR.
    """

    if not isinstance(
        analysis,
        dict,
    ):
        analysis = {}

    direction = _normalize_direction(
        direction
    )

    ema20 = _last_value(
        analysis.get(
            "ema20",
            0,
        )
    )

    ema50 = _last_value(
        analysis.get(
            "ema50",
            0,
        )
    )

    rsi = _last_value(
        analysis.get(
            "rsi",
            0,
        )
    )

    atr = _last_value(
        analysis.get(
            "atr",
            0,
        )
    )

    # ========================================================
    # EMA
    # ========================================================

    if ema20 > ema50:

        ema_context = "bullish"

    elif ema20 < ema50:

        ema_context = "bearish"

    else:

        ema_context = "neutral"

    # ========================================================
    # RSI
    # ========================================================

    if rsi >= 70:

        rsi_context = "overbought"

    elif rsi <= 30:

        rsi_context = "oversold"

    elif rsi >= 50:

        rsi_context = "bullish_bias"

    else:

        rsi_context = "bearish_bias"

    return {

        "ema20":
            ema20,

        "ema50":
            ema50,

        "rsi":
            rsi,

        "atr":
            atr,

        "ema_context":
            ema_context,

        "rsi_context":
            rsi_context,

        "direction":
            direction,
    }


# ============================================================
# FIBONACCI
# ============================================================

def construire_fibonacci(
    candles: list,
    direction: str,
    structure_analysis: Optional[
        Dict[str, Any]
    ] = None,
) -> Dict[str, Any]:
    """
    Construit l'analyse Fibonacci.

    IMPORTANT :

    fibonacci.py attend :

        calculer_fibonacci(
            candles,
            structure_analysis
        )

    Il ne faut PAS envoyer simplement :

        calculer_fibonacci(
            candles,
            direction
        )

    Sinon fibonacci.py reçoit une chaîne
    à la place d'un dictionnaire et provoque :

        'str' object has no attribute 'get'
    """

    if not candles:

        logger.warning(
            "Fibonacci : aucune bougie."
        )

        return {}

    direction = _normalize_direction(
        direction
    )

    if not isinstance(
        structure_analysis,
        dict,
    ):

        logger.warning(
            "Fibonacci : analyse de structure absente."
        )

        return {}

    try:

        result = calculer_fibonacci(
            candles,
            structure_analysis,
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
# EXTRACTION SWINGS
# ============================================================

def _extract_swing_prices(
    analysis: Dict[str, Any],
) -> Dict[str, list]:
    """
    Extrait les prix des swings.
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

    # --------------------------------------------------------
    # Certains moteurs placent les swings directement ici
    # --------------------------------------------------------

    swings = analysis.get(
        "swings",
        {},
    )

    # --------------------------------------------------------
    # Sécurité si swings est absent
    # --------------------------------------------------------

    if not isinstance(
        swings,
        dict,
    ):
        return result

    # --------------------------------------------------------
    # SWING HIGHS
    # --------------------------------------------------------

    for swing in swings.get(
        "highs",
        [],
    ):

        if not isinstance(
            swing,
            dict,
        ):
            continue

        price = _safe_float(
            swing.get(
                "price"
            )
        )

        if price > 0:

            result[
                "highs"
            ].append(
                price
            )

    # --------------------------------------------------------
    # SWING LOWS
    # --------------------------------------------------------

    for swing in swings.get(
        "lows",
        [],
    ):

        if not isinstance(
            swing,
            dict,
        ):
            continue

        price = _safe_float(
            swing.get(
                "price"
            )
        )

        if price > 0:

            result[
                "lows"
            ].append(
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
    Détermine le Stop Loss à partir des swings M15/H1.

    BUY :
        SL sous le dernier swing low exploitable.

    SELL :
        SL au-dessus du dernier swing high exploitable.

    Fallback :
        ATR x 1.5
    """

    direction = _normalize_direction(
        direction
    )

    entry = _safe_float(
        entry
    )

    atr = _last_value(
        atr
    )

    if entry <= 0:
        return None

    m15_swings = _extract_swing_prices(
        m15_analysis
    )

    h1_swings = _extract_swing_prices(
        h1_analysis
    )

    # ========================================================
    # BUY
    # ========================================================

    if direction == BUY:

        candidates = []

        candidates.extend(
            price
            for price in m15_swings["lows"]
            if price < entry
        )

        candidates.extend(
            price
            for price in h1_swings["lows"]
            if price < entry
        )

        if candidates:

            return max(
                candidates
            )

        if atr > 0:

            return entry - (
                atr * 1.5
            )

    # ========================================================
    # SELL
    # ========================================================

    if direction == SELL:

        candidates = []

        candidates.extend(
            price
            for price in m15_swings["highs"]
            if price > entry
        )

        candidates.extend(
            price
            for price in h1_swings["highs"]
            if price > entry
        )

        if candidates:

            return min(
                candidates
            )

        if atr > 0:

            return entry + (
                atr * 1.5
            )

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
    Vérifie que le SL est du bon côté du marché.
    """

    if stop_loss is None:
        return False

    entry = _safe_float(
        entry
    )

    stop_loss = _safe_float(
        stop_loss
    )

    direction = _normalize_direction(
        direction
    )

    if entry <= 0:
        return False

    if stop_loss <= 0:
        return False

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

    Fonction principale appelée par le bot.
    """

    logger.info(
        "Analyse Vision Trade AI V2 : %s",
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
    # ANALYSE DES TIMEFRAMES
    # ========================================================

    analyses = {}

    for timeframe in TIMEFRAMES:

        candles = market_data.get(
            timeframe,
            [],
        )

        if not candles:

            analyses[timeframe] = {}

            logger.warning(
                "%s : aucune donnée.",
                timeframe,
            )

            continue

        try:

            analyses[timeframe] = (
                analyser_timeframe(
                    candles,
                    timeframe,
                )
            )

        except Exception as exc:

            logger.exception(
                "Erreur analyse %s",
                timeframe,
            )

            analyses[timeframe] = {
                "error": str(exc)
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
    # BIAIS
    # ========================================================

    h4_bias = _extract_bias(
        h4
    )

    h1_bias = _extract_bias(
        h1
    )

    m15_bias = _extract_bias(
        m15
    )

    m5_bias = _extract_bias(
        m5
    )

    # ========================================================
    # DIRECTION PRINCIPALE
    # ========================================================

    direction = determiner_direction(
        h4,
        h1,
        m15,
    )

    logger.info(
        "BIAIS : H4=%s | H1=%s | M15=%s | M5=%s",
        h4_bias,
        h1_bias,
        m15_bias,
        m5_bias,
    )

    logger.info(
        "DIRECTION PRINCIPALE : %s",
        direction,
    )

    # ========================================================
    # AUCUNE DIRECTION
    # ========================================================

    if direction == NEUTRAL:

        return {

            "status":
                "NO_DIRECTION",

            "symbol":
                symbol,

            "direction":
                NEUTRAL,

            "biases": {

                "H4":
                    h4_bias,

                "H1":
                    h1_bias,

                "M15":
                    m15_bias,

                "M5":
                    m5_bias,
            },

            "entry":
                None,

            "stop_loss":
                None,

            "score": {
                "final_score": 0
            },

            "rr":
                {},

            "quality":
                {},

            "analyses":
                analyses,

            "ready_for_signal":
                False,
        }

    # ========================================================
    # CONFIRMATION M5
    # ========================================================

    m5_confirmation = (
        verifier_confirmation_m5(
            direction,
            m5,
        )
    )

    # ========================================================
    # CONTEXTE INDICATEURS M15
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

    m15_candles = market_data.get(
        "M15",
        [],
    )

    m15_structure = {}

    if isinstance(
        m15,
        dict,
    ):

        m15_structure = m15.get(
            "structure",
            {},
        )

    fibonacci_analysis = (
        construire_fibonacci(
            candles=m15_candles,
            direction=direction,
            structure_analysis=m15_structure,
        )
    )

    logger.info(
        "FIBONACCI : %s",
        "OK"
        if fibonacci_analysis
        else "INDISPONIBLE",
    )

    # ========================================================
    # SCORE
    # ========================================================

    try:

        score_result = calculer_score(

            direction=direction,

            h4_bias=h4_bias,

            h1_analysis=h1,

            m15_analysis=m15,

            m5_analysis=m5,

            fibonacci_analysis=
                fibonacci_analysis,

            indicators=
                indicator_context,

            threshold=
                DEFAULT_MIN_SCORE,
        )

    except Exception as exc:

        logger.exception(
            "Erreur score"
        )

        return {

            "status":
                "SCORE_ERROR",

            "symbol":
                symbol,

            "direction":
                direction,

            "biases": {

                "H4":
                    h4_bias,

                "H1":
                    h1_bias,

                "M15":
                    m15_bias,

                "M5":
                    m5_bias,
            },

            "error":
                str(exc),

            "score": {
                "final_score": 0
            },

            "fibonacci":
                fibonacci_analysis,

            "analyses":
                analyses,

            "ready_for_signal":
                False,
        }

    if not isinstance(
        score_result,
        dict,
    ):

        score_result = {
            "final_score":
                _safe_float(
                    score_result
                )
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
        "SCORE FINAL : %.2f",
        final_score,
    )

    # ========================================================
    # ENTRY M15
    # ========================================================

    try:

        entry = _get_last_close(
            m15_candles
        )

    except Exception as exc:

        return {

            "status":
                "NO_ENTRY",

            "symbol":
                symbol,

            "direction":
                direction,

            "biases": {

                "H4":
                    h4_bias,

                "H1":
                    h1_bias,

                "M15":
                    m15_bias,

                "M5":
                    m5_bias,
            },

            "score":
                score_result,

            "fibonacci":
                fibonacci_analysis,

            "error":
                str(exc),

            "analyses":
                analyses,

            "ready_for_signal":
                False,
        }

    # ========================================================
    # ATR M15
    # ========================================================

    atr = _last_value(
        m15.get(
            "atr",
            0,
        )
    )

    # ========================================================
    # STOP LOSS
    # ========================================================

    stop_loss = (
        determiner_stop_loss(
            direction=direction,
            entry=entry,
            m15_analysis=m15,
            h1_analysis=h1,
            atr=atr,
        )
    )

    if not _validate_stop_loss(
        direction,
        entry,
        stop_loss,
    ):

        return {

            "status":
                "NO_STOP_LOSS",

            "symbol":
                symbol,

            "direction":
                direction,

            "biases": {

                "H4":
                    h4_bias,

                "H1":
                    h1_bias,

                "M15":
                    m15_bias,

                "M5":
                    m5_bias,
            },

            "entry":
                entry,

            "stop_loss":
                None,

            "score":
                score_result,

            "indicators":
                indicator_context,

            "fibonacci":
                fibonacci_analysis,

            "m5_confirmation":
                m5_confirmation,

            "analyses":
                analyses,

            "ready_for_signal":
                False,
        }

    # ========================================================
    # RR
    # ========================================================

    try:

        rr_result = (
            calculer_rr_complet(
                entry=entry,
                stop_loss=stop_loss,
                direction=direction,
                minimum_rr=DEFAULT_MIN_RR,
            )
        )

        rr_data = {

            "direction":
                rr_result.direction,

            "entry":
                rr_result.entry,

            "stop_loss":
                rr_result.stop_loss,

            "risk":
                rr_result.risk,

            "tp1":
                rr_result.tp1,

            "tp2":
                rr_result.tp2,

            "tp3":
                rr_result.tp3,

            "reward_tp1":
                rr_result.reward_tp1,

            "reward_tp2":
                rr_result.reward_tp2,

            "reward_tp3":
                rr_result.reward_tp3,

            "rr_tp1":
                rr_result.rr_tp1,

            "rr_tp2":
                rr_result.rr_tp2,

            "rr_tp3":
                rr_result.rr_tp3,

            "minimum_rr":
                rr_result.minimum_rr,

            "passes_rr_filter":
                rr_result.passes_rr_filter,
        }

    except Exception as exc:

        logger.exception(
            "Erreur RR"
        )

        return {

            "status":
                "RR_ERROR",

            "symbol":
                symbol,

            "direction":
                direction,

            "biases": {

                "H4":
                    h4_bias,

                "H1":
                    h1_bias,

                "M15":
                    m15_bias,

                "M5":
                    m5_bias,
            },

            "entry":
                entry,

            "stop_loss":
                stop_loss,

            "score":
                score_result,

            "fibonacci":
                fibonacci_analysis,

            "error":
                str(exc),

            "analyses":
                analyses,

            "ready_for_signal":
                False,
        }

    # ========================================================
    # FILTRE QUALITÉ
    # ========================================================

    try:

        quality_result = (
            filtrer_qualite(

                direction=direction,

                score_result=score_result,

                rr_result=rr_data,

                h4_bias=h4_bias,

                h1_bias=h1_bias,

                m15_bias=m15_bias,

                m5_bias=m5_bias,

                news=None,

                minimum_score=
                    DEFAULT_MIN_SCORE,

                minimum_rr=
                    DEFAULT_MIN_RR,
            )
        )

    except Exception as exc:

        logger.exception(
            "Erreur filtre qualité"
        )

        return {

            "status":
                "QUALITY_ERROR",

            "symbol":
                symbol,

            "direction":
                direction,

            "biases": {

                "H4":
                    h4_bias,

                "H1":
                    h1_bias,

                "M15":
                    m15_bias,

                "M5":
                    m5_bias,
            },

            "entry":
                entry,

            "stop_loss":
                stop_loss,

            "score":
                score_result,

            "rr":
                rr_data,

            "fibonacci":
                fibonacci_analysis,

            "error":
                str(exc),

            "analyses":
                analyses,

            "ready_for_signal":
                False,
        }

    if not isinstance(
        quality_result,
        dict,
    ):

        quality_result = {
            "status":
                "REJECT",
            "ready_for_signal":
                False,
        }

    # ========================================================
    # RÉSULTAT FINAL
    # ========================================================

    ready = bool(
        quality_result.get(
            "ready_for_signal",
            False,
        )
    )

    status = quality_result.get(
        "status",
        "REJECT",
    )

    logger.info(
        "RÉSULTAT : status=%s | direction=%s | score=%.2f | ready=%s",
        status,
        direction,
        final_score,
        ready,
    )

    return {

        "status":
            status,

        "symbol":
            symbol,

        "direction":
            direction,

        "biases": {

            "H4":
                h4_bias,

            "H1":
                h1_bias,

            "M15":
                m15_bias,

            "M5":
                m5_bias,
        },

        "entry":
            entry,

        "stop_loss":
            stop_loss,

        "score":
            score_result,

        "rr":
            rr_data,

        "quality":
            quality_result,

        "indicators":
            indicator_context,

        "fibonacci":
            fibonacci_analysis,

        "m5_confirmation":
            m5_confirmation,

        "analyses":
            analyses,

        "ready_for_signal":
            ready,
    }


# ============================================================
# ALIAS
# ============================================================

def analyse(
    symbol: str = DEFAULT_SYMBOL,
) -> Dict[str, Any]:

    return analyser_marche(
        symbol
    )


# ============================================================
# TESTS INTERNES
# ============================================================

def _run_internal_test():
    """
    Tests unitaires de base.
    """

    # ========================================================
    # NORMALISATION
    # ========================================================

    assert (
        _normalize_direction("BUY")
        == BUY
    )

    assert (
        _normalize_direction("SELL")
        == SELL
    )

    assert (
        _normalize_direction("BULLISH")
        == BUY
    )

    assert (
        _normalize_direction("BEARISH")
        == SELL
    )

    assert (
        _normalize_direction("xxx")
        == NEUTRAL
    )

    # ========================================================
    # H4 + H1 BUY
    # ========================================================

    assert (
        determiner_direction(
            {"bias": BUY},
            {"bias": BUY},
            {"bias": NEUTRAL},
        )
        == BUY
    )

    # ========================================================
    # H4 + H1 SELL
    # ========================================================

    assert (
        determiner_direction(
            {"bias": SELL},
            {"bias": SELL},
            {"bias": NEUTRAL},
        )
        == SELL
    )

    # ========================================================
    # H4 SEUL SELL
    # ========================================================

    assert (
        determiner_direction(
            {"bias": SELL},
            {"bias": NEUTRAL},
            {"bias": NEUTRAL},
        )
        == SELL
    )

    # ========================================================
    # H4 SEUL BUY
    # ========================================================

    assert (
        determiner_direction(
            {"bias": BUY},
            {"bias": NEUTRAL},
            {"bias": NEUTRAL},
        )
        == BUY
    )

    # ========================================================
    # H4 NEUTRAL + H1/M15 BUY
    # ========================================================

    assert (
        determiner_direction(
            {"bias": NEUTRAL},
            {"bias": BUY},
            {"bias": BUY},
        )
        == BUY
    )

    # ========================================================
    # H4 NEUTRAL + H1/M15 SELL
    # ========================================================

    assert (
        determiner_direction(
            {"bias": NEUTRAL},
            {"bias": SELL},
            {"bias": SELL},
        )
        == SELL
    )

    # ========================================================
    # CONTRADICTION SELL / BUY / BUY
    # ========================================================

    assert (
        determiner_direction(
            {"bias": SELL},
            {"bias": BUY},
            {"bias": BUY},
        )
        == NEUTRAL
    )

    # ========================================================
    # CONTRADICTION BUY / SELL / SELL
    # ========================================================

    assert (
        determiner_direction(
            {"bias": BUY},
            {"bias": SELL},
            {"bias": SELL},
        )
        == NEUTRAL
    )

    # ========================================================
    # INDICATEURS
    # ========================================================

    indicators = (
        construire_contexte_indicateurs(
            {
                "ema20": [100, 110],
                "ema50": [90, 100],
                "rsi": [50, 55],
                "atr": [5, 6],
            },
            BUY,
        )
    )

    assert (
        indicators["ema20"]
        == 110
    )

    assert (
        indicators["ema50"]
        == 100
    )

    assert (
        indicators["rsi"]
        == 55
    )

    assert (
        indicators["atr"]
        == 6
    )

    # ========================================================
    # STOP LOSS BUY
    # ========================================================

    fake = {

        "swings": {

            "highs": [
                {
                    "price": 110
                }
            ],

            "lows": [
                {
                    "price": 90
                }
            ],
        }
    }

    assert (
        determiner_stop_loss(
            BUY,
            100,
            fake,
            {},
            5,
        )
        == 90
    )

    # ========================================================
    # STOP LOSS SELL
    # ========================================================

    assert (
        determiner_stop_loss(
            SELL,
            100,
            fake,
            {},
            5,
        )
        == 110
    )

    # ========================================================
    # VALIDATION SL
    # ========================================================

    assert (
        _validate_stop_loss(
            BUY,
            100,
            90,
        )
        is True
    )

    assert (
        _validate_stop_loss(
            SELL,
            100,
            110,
        )
        is True
    )

    assert (
        _validate_stop_loss(
            BUY,
            100,
            110,
        )
        is False
    )

    assert (
        _validate_stop_loss(
            SELL,
            100,
            90,
        )
        is False
    )

    logger.info(
        "analyse.py : tests OK"
    )


# ============================================================
# EXÉCUTION DIRECTE
# ============================================================

if __name__ == "__main__":

    logging.basicConfig(
        level=logging.INFO,
        format=(
            "%(asctime)s | "
            "%(levelname)s | "
            "%(name)s | "
            "%(message)s"
        ),
    )

    print(
        "=" * 60
    )

    print(
        "VISION TRADE AI V2"
    )

    print(
        "Test analyse.py"
    )

    print(
        "=" * 60
    )

    try:

        _run_internal_test()

        print(
            "ANALYSE : OK"
        )

    except Exception as exc:

        print(
            "ANALYSE : ERREUR"
        )

        print(
            exc
        )