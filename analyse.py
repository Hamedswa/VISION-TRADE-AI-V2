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

Règles :

- H4/H1/M15 déterminent la direction principale.
- M5 ne peut jamais créer une direction seul.
- NEUTRAL reste NEUTRAL.
- structure.py reste déterministe.
- score.py reste responsable du score.
- rr.py reste responsable du RR.
- filtre_qualite.py reste responsable du filtre final.
- Fibonacci reçoit toujours un dictionnaire de structure valide.
- Aucune logique Telegram ici.
- Aucune logique Groq ici.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional


# ============================================================
# IMPORTS
# ============================================================

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

    Accepte :
    - int
    - float
    - string numérique
    - liste / tuple
    - dictionnaire contenant une valeur numérique
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

    if isinstance(value, dict):

        value = (
            value.get("direction")
            or value.get("bias")
            or value.get("trend")
            or value.get("signal")
            or ""
        )

    value = str(
        value or ""
    ).upper().strip()

    if value in {
        BUY,
        "BULLISH",
        "LONG",
        "UP",
    }:

        return BUY

    if value in {
        SELL,
        "BEARISH",
        "SHORT",
        "DOWN",
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

    Recherche plusieurs formats possibles.
    """

    if not isinstance(
        analysis,
        dict,
    ):

        return NEUTRAL

    # --------------------------------------------------------
    # Bias direct
    # --------------------------------------------------------

    bias = analysis.get(
        "bias"
    )

    normalized = _normalize_direction(
        bias
    )

    if normalized != NEUTRAL:
        return normalized

    # --------------------------------------------------------
    # Direction
    # --------------------------------------------------------

    direction = analysis.get(
        "direction"
    )

    normalized = _normalize_direction(
        direction
    )

    if normalized != NEUTRAL:
        return normalized

    # --------------------------------------------------------
    # Trend
    # --------------------------------------------------------

    trend = analysis.get(
        "trend"
    )

    normalized = _normalize_direction(
        trend
    )

    if normalized != NEUTRAL:
        return normalized

    # --------------------------------------------------------
    # Structure
    # --------------------------------------------------------

    structure = analysis.get(
        "structure"
    )

    if isinstance(
        structure,
        dict,
    ):

        for key in (
            "bias",
            "direction",
            "trend",
        ):

            normalized = _normalize_direction(
                structure.get(key)
            )

            if normalized != NEUTRAL:

                return normalized

    return NEUTRAL


# ============================================================
# NORMALISATION STRUCTURE
# ============================================================

def _normalize_structure_analysis(
    structure_analysis: Any,
) -> Dict[str, Any]:
    """
    Garantit que Fibonacci reçoit TOUJOURS un dictionnaire.

    Cette fonction protège contre l'erreur :

        'str' object has no attribute 'get'

    Formats acceptés :

        {
            "swings": ...,
            "latest": ...,
            "fvg": ...,
            ...
        }

    ou :

        {
            "structure": {
                "swings": ...,
                ...
            }
        }

    Si un mauvais type arrive, un dictionnaire vide est retourné.
    """

    if not isinstance(
        structure_analysis,
        dict,
    ):

        return {}

    # --------------------------------------------------------
    # Cas normal :
    #
    # structure_analysis =
    # {
    #     "swings": ...,
    #     "latest": ...,
    # }
    # --------------------------------------------------------

    if any(
        key in structure_analysis
        for key in (
            "swings",
            "latest",
            "fvg",
            "order_blocks",
            "bos",
            "choch",
            "liquidity",
            "liquidity_sweeps",
        )
    ):

        return structure_analysis

    # --------------------------------------------------------
    # Cas imbriqué :
    #
    # {
    #     "structure": {...}
    # }
    # --------------------------------------------------------

    nested = structure_analysis.get(
        "structure"
    )

    if isinstance(
        nested,
        dict,
    ):

        return nested

    return structure_analysis


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

    if not isinstance(
        structure,
        dict,
    ):

        logger.warning(
            "%s : structure.py a retourné un type invalide : %s",
            timeframe,
            type(structure).__name__,
        )

        structure = {}

    bias = _extract_bias(
        structure
    )

    # ========================================================
    # DERNIÈRE STRUCTURE
    # ========================================================

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
    # SWINGS
    # ========================================================

    swings = structure.get(
        "swings",
        {},
    )

    if not isinstance(
        swings,
        dict,
    ):

        swings = {}

    # ========================================================
    # FVG
    # ========================================================

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

        "swings":
            swings,

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

        candles = []

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

        except Exception as exc:

            logger.exception(
                "Erreur chargement %s : %s",
                timeframe,
                exc,
            )

        if not isinstance(
            candles,
            list,
        ):

            candles = []

        result[timeframe] = candles

        logger.info(
            "%s %s : %s bougies",
            symbol,
            timeframe,
            len(candles),
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
    3. H4 seul peut donner la direction.
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

    h4_bias = _extract_bias(h4)
    h1_bias = _extract_bias(h1)
    m15_bias = _extract_bias(m15)

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
    # CONFLIT
    # ========================================================

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

            "confirmation_type":
                None,

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
    confirmation_types = []

    # ========================================================
    # BIAIS M5
    # ========================================================

    if m5_bias == direction:

        confirmed = True

        confirmation_types.append(
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

            confirmation_types.append(
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

            confirmation_types.append(
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
            (
                confirmation_types[-1]
                if confirmation_types
                else None
            ),

        "confirmation_types":
            confirmation_types,
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

    CORRECTION IMPORTANTE :

    Fibonacci doit recevoir une analyse de structure
    sous forme de dictionnaire.

    Jamais :

        calculer_fibonacci(candles, "SELL")

    Toujours :

        calculer_fibonacci(candles, structure_dict)
    """

    if not candles:

        logger.warning(
            "Fibonacci : aucune bougie."
        )

        return {}

    direction = _normalize_direction(
        direction
    )

    if direction == NEUTRAL:

        logger.info(
            "Fibonacci : direction NEUTRAL."
        )

        return {}

    # ========================================================
    # NORMALISATION STRUCTURE
    # ========================================================

    structure = (
        _normalize_structure_analysis(
            structure_analysis
        )
    )

    if not structure:

        logger.warning(
            "Fibonacci : analyse de structure absente ou invalide."
        )

        return {}

    # ========================================================
    # PROTECTION CONTRE LES VALEURS STRING
    # ========================================================

    # Fibonacci travaille avec un dictionnaire.
    # On vérifie explicitement les champs susceptibles
    # de contenir accidentellement une chaîne.

    safe_structure = dict(
        structure
    )

    for key in (
        "swings",
        "latest",
        "fvg",
        "order_blocks",
        "bos",
        "choch",
        "liquidity",
        "liquidity_sweeps",
    ):

        if key not in safe_structure:

            if key in {
                "fvg",
                "order_blocks",
                "liquidity_sweeps",
            }:

                safe_structure[key] = []

            else:

                safe_structure[key] = {}

    # ========================================================
    # APPEL FIBONACCI
    # ========================================================

    try:

        result = calculer_fibonacci(
            candles,
            safe_structure,
        )

    except AttributeError as exc:

        logger.exception(
            "Erreur interne Fibonacci : %s",
            exc,
        )

        return {}

    except Exception as exc:

        logger.exception(
            "Analyse Fibonacci indisponible : %s",
            exc,
        )

        return {}

    # ========================================================
    # VALIDATION RESULTAT
    # ========================================================

    if isinstance(
        result,
        dict,
    ):

        return result

    logger.warning(
        "Fibonacci a retourné un type invalide : %s",
        type(result).__name__,
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

    Accepte :
        analysis["swings"]

    ou :
        analysis["structure"]["swings"]
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

    # ========================================================
    # STRUCTURE
    # ========================================================

    structure = analysis.get(
        "structure",
        analysis,
    )

    if not isinstance(
        structure,
        dict,
    ):

        return result

    swings = structure.get(
        "swings",
        {},
    )

    if not isinstance(
        swings,
        dict,
    ):

        return result

    # ========================================================
    # SWING HIGHS
    # ========================================================

    highs = swings.get(
        "highs",
        [],
    )

    if isinstance(
        highs,
        list,
    ):

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

                    result[
                        "highs"
                    ].append(
                        price
                    )

            else:

                price = _safe_float(
                    swing
                )

                if price > 0:

                    result[
                        "highs"
                    ].append(
                        price
                    )

    # ========================================================
    # SWING LOWS
    # ========================================================

    lows = swings.get(
        "lows",
        [],
    )

    if isinstance(
        lows,
        list,
    ):

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

                    result[
                        "lows"
                    ].append(
                        price
                    )

            else:

                price = _safe_float(
                    swing
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
# RESULTAT D'ERREUR STANDARD
# ============================================================

def _error_result(
    status: str,
    symbol: str,
    direction: str,
    biases: Dict[str, str],
    analyses: Dict[str, Any],
    error: str,
    **extra: Any,
) -> Dict[str, Any]:
    """
    Construit une sortie d'erreur standardisée.
    """

    result = {

        "status":
            status,

        "symbol":
            symbol,

        "direction":
            direction,

        "biases":
            biases,

        "score":
            {
                "final_score": 0
            },

        "rr":
            {},

        "quality":
            {},

        "error":
            error,

        "analyses":
            analyses,

        "ready_for_signal":
            False,
    }

    result.update(
        extra
    )

    return result


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
                "error":
                    str(exc)
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

    biases = {

        "H4":
            h4_bias,

        "H1":
            h1_bias,

        "M15":
            m15_bias,

        "M5":
            m5_bias,
    }

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

            "biases":
                biases,

            "entry":
                None,

            "stop_loss":
                None,

            "score":
                {
                    "final_score": 0
                },

            "rr":
                {},

            "quality":
                {},

            "indicators":
                {},

            "fibonacci":
                {},

            "m5_confirmation":
                {
                    "confirmed":
                        False,

                    "direction":
                        NEUTRAL,

                    "m5_bias":
                        m5_bias,
                },

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

    logger.info(
        "CONFIRMATION M5 : %s",
        m5_confirmation,
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

        m15_structure = (
            m15.get(
                "structure",
                {},
            )
        )

    # --------------------------------------------------------
    # IMPORTANT :
    #
    # On passe uniquement le dictionnaire structure.
    # Jamais la chaîne BUY/SELL.
    # --------------------------------------------------------

    fibonacci_analysis = (
        construire_fibonacci(
            candles=m15_candles,
            direction=direction,
            structure_analysis=m15_structure,
        )
    )

    logger.info(
        "FIBONACCI : %s",
        (
            "OK"
            if fibonacci_analysis
            else "INDISPONIBLE"
        ),
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

        return _error_result(
            "SCORE_ERROR",
            symbol,
            direction,
            biases,
            analyses,
            str(exc),
            fibonacci=
                fibonacci_analysis,
            indicators=
                indicator_context,
            m5_confirmation=
                m5_confirmation,
        )

    # ========================================================
    # NORMALISATION SCORE
    # ========================================================

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

        return _error_result(
            "NO_ENTRY",
            symbol,
            direction,
            biases,
            analyses,
            str(exc),
            fibonacci=
                fibonacci_analysis,
            indicators=
                indicator_context,
            m5_confirmation=
                m5_confirmation,
        )

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

        return _error_result(
            "NO_STOP_LOSS",
            symbol,
            direction,
            biases,
            analyses,
            "Stop-loss invalide ou introuvable.",
            entry=
                entry,
            stop_loss=
                None,
            score=
                score_result,
            indicators=
                indicator_context,
            fibonacci=
                fibonacci_analysis,
            m5_confirmation=
                m5_confirmation,
        )

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

        # ----------------------------------------------------
        # RR OBJECT
        # ----------------------------------------------------

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

        return _error_result(
            "RR_ERROR",
            symbol,
            direction,
            biases,
            analyses,
            str(exc),
            entry=
                entry,
            stop_loss=
                stop_loss,
            score=
                score_result,
            fibonacci=
                fibonacci_analysis,
        )

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

        return _error_result(
            "QUALITY_ERROR",
            symbol,
            direction,
            biases,
            analyses,
            str(exc),
            entry=
                entry,
            stop_loss=
                stop_loss,
            score=
                score_result,
            rr=
                rr_data,
            fibonacci=
                fibonacci_analysis,
            indicators=
                indicator_context,
            m5_confirmation=
                m5_confirmation,
        )

    # ========================================================
    # NORMALISATION QUALITÉ
    # ========================================================

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

    # ========================================================
    # SÉCURITÉ SUPPLÉMENTAIRE
    # ========================================================

    # Même si un module aval retourne accidentellement
    # ready_for_signal=True, le moteur principal refuse
    # le signal si le score ou le RR ne passent pas.

    score_passed = (
        final_score
        >= DEFAULT_MIN_SCORE
    )

    rr_passed = bool(
        rr_data.get(
            "passes_rr_filter",
            False,
        )
    )

    if not score_passed:

        ready = False

        if status == "ACCEPT":

            status = "REJECT"

    if not rr_passed:

        ready = False

        if status == "ACCEPT":

            status = "REJECT"

    # --------------------------------------------------------
    # M5
    #
    # Le M5 reste une confirmation.
    # Il ne crée jamais la direction.
    # --------------------------------------------------------

    if not m5_confirmation.get(
        "confirmed",
        False,
    ):

        ready = False

        if status == "ACCEPT":

            status = "REJECT"

    logger.info(
        (
            "RÉSULTAT : "
            "status=%s | "
            "direction=%s | "
            "score=%.2f | "
            "score_ok=%s | "
            "rr_ok=%s | "
            "m5_ok=%s | "
            "ready=%s"
        ),
        status,
        direction,
        final_score,
        score_passed,
        rr_passed,
        m5_confirmation.get(
            "confirmed",
            False,
        ),
        ready,
    )

    # ========================================================
    # RÉSULTAT FINAL
    # ========================================================

    return {

        "status":
            status,

        "symbol":
            symbol,

        "direction":
            direction,

        "biases":
            biases,

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
    # NORMALISATION DIRECTION
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
        _normalize_direction("LONG")
        == BUY
    )

    assert (
        _normalize_direction("SHORT")
        == SELL
    )

    assert (
        _normalize_direction("xxx")
        == NEUTRAL
    )

    # ========================================================
    # EXTRACTION BIAS
    # ========================================================

    assert (
        _extract_bias(
            {
                "bias": "BUY"
            }
        )
        == BUY
    )

    assert (
        _extract_bias(
            {
                "direction": "SELL"
            }
        )
        == SELL
    )

    assert (
        _extract_bias(
            {}
        )
        == NEUTRAL
    )

    # ========================================================
    # NORMALISATION STRUCTURE
    # ========================================================

    structure = {

        "swings": {

            "highs": [],
            "lows": [],
        },

        "latest": {},

        "fvg": [],

        "order_blocks": [],
    }

    normalized = (
        _normalize_structure_analysis(
            structure
        )
    )

    assert isinstance(
        normalized,
        dict,
    )

    # ========================================================
    # STRUCTURE IMBRIQUÉE
    # ========================================================

    nested = (
        _normalize_structure_analysis(
            {
                "structure":
                    structure
            }
        )
    )

    assert isinstance(
        nested,
        dict,
    )

    assert (
        "swings"
        in nested
    )

    # ========================================================
    # FIBONACCI : MAUVAIS TYPE
    # ========================================================

    invalid_structure = (
        _normalize_structure_analysis(
            "SELL"
        )
    )

    assert isinstance(
        invalid_structure,
        dict,
    )

    assert (
        invalid_structure
        == {}
    )

    # ========================================================
    # DIRECTION H4 + H1 BUY
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
    # DIRECTION H4 + H1 SELL
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
                "ema20":
                    [100, 110],

                "ema50":
                    [90, 100],

                "rsi":
                    [50, 55],

                "atr":
                    [5, 6],
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
    # VALIDATION SL BUY
    # ========================================================

    assert (
        _validate_stop_loss(
            BUY,
            100,
            90,
        )
        is True
    )

    # ========================================================
    # VALIDATION SL SELL
    # ========================================================

    assert (
        _validate_stop_loss(
            SELL,
            100,
            110,
        )
        is True
    )

    # ========================================================
    # INVALID SL BUY
    # ========================================================

    assert (
        _validate_stop_loss(
            BUY,
            100,
            110,
        )
        is False
    )

    # ========================================================
    # INVALID SL SELL
    # ========================================================

    assert (
        _validate_stop_loss(
            SELL,
            100,
            90,
        )
        is False
    )

    # ========================================================
    # M5 CONFIRMATION
    # ========================================================

    confirmation = (
        verifier_confirmation_m5(
            SELL,
            {
                "bias":
                    SELL,

                "latest": {

                    "bos": {

                        "direction":
                            SELL
                    }
                },
            },
        )
    )

    assert (
        confirmation["confirmed"]
        is True
    )

    # ========================================================
    # M5 NEUTRAL
    # ========================================================

    confirmation = (
        verifier_confirmation_m5(
            SELL,
            {
                "bias":
                    NEUTRAL,

                "latest":
                    {},
            },
        )
    )

    assert (
        confirmation["confirmed"]
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