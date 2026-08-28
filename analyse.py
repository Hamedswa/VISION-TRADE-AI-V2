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
- Fibonacci reçoit toujours une structure normalisée.
- Aucune logique Telegram ici.
- Aucune logique Groq ici.
SEUIL ACTUEL :
- Score minimum : 50/100
- RR minimum : 1:2
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
    MIN_SCORE,
    MIN_RR,
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
# ============================================================
# IMPORTANT
# Les seuils viennent maintenant directement de config.py
# ============================================================
DEFAULT_MIN_SCORE = MIN_SCORE
DEFAULT_MIN_RR = MIN_RR
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
    Conversion robuste vers float.
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
    BUY / BULLISH / LONG -> BUY
    SELL / BEARISH / SHORT -> SELL
    Tout le reste -> NEUTRAL.
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
    Extrait le bias d'une analyse.
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
        structure = {}
    bias = _extract_bias(
        structure
    )
    # ========================================================
    # LATEST
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
    # RESULTAT
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
    result: Dict[str, list] = {}
    for timeframe in TIMEFRAMES:
        api_timeframe = TIMEFRAME_TO_API[
            timeframe
        ]
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
    Détermine la direction principale du marché.
    Hiérarchie :
        H4  = tendance globale
        H1  = structure principale
        M15 = contexte
    Règles :
    1. H4 + H1 + M15 alignés
       -> direction commune
    2. H4 + H1 alignés
       -> direction H4/H1
    3. H4 + M15 alignés
       -> direction H4/M15
    4. H4 seul avec H1/M15 NEUTRAL
       -> direction H4
    5. H4 NEUTRAL :
       H1 + M15 doivent être alignés
       pour produire une direction.
    6. Tout conflit non résolu
       -> NEUTRAL
    M5 n'intervient jamais ici.
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
    logger.debug(
        "DIRECTION INPUT : H4=%s | H1=%s | M15=%s",
        h4_bias,
        h1_bias,
        m15_bias,
    )
    # ========================================================
    # H4 NEUTRAL
    # ========================================================
    if h4_bias == NEUTRAL:
        if (
            h1_bias != NEUTRAL
            and h1_bias == m15_bias
        ):
            logger.debug(
                "DIRECTION : H4 NEUTRAL, H1/M15 alignés -> %s",
                h1_bias,
            )
            return h1_bias
        logger.debug(
            "DIRECTION : H4 NEUTRAL sans confirmation -> NEUTRAL"
        )
        return NEUTRAL
    # ========================================================
    # H4 + H1 ALIGNÉS
    # ========================================================
    if h1_bias == h4_bias:
        logger.debug(
            "DIRECTION : H4/H1 alignés -> %s",
            h4_bias,
        )
        return h4_bias
    # ========================================================
    # H4 + M15 ALIGNÉS
    # ========================================================
    if m15_bias == h4_bias:
        logger.debug(
            "DIRECTION : H4/M15 alignés -> %s",
            h4_bias,
        )
        return h4_bias
    # ========================================================
    # H4 SEUL
    # ========================================================
    if (
        h1_bias == NEUTRAL
        and m15_bias == NEUTRAL
    ):
        logger.debug(
            "DIRECTION : H4 seul -> %s",
            h4_bias,
        )
        return h4_bias
    # ========================================================
    # CONFLIT
    # ========================================================
    logger.debug(
        "DIRECTION : conflit H4/H1/M15 -> NEUTRAL"
    )
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
    if not isinstance(m5, dict):
        m5 = {}
    if direction == NEUTRAL:
        return {
            "direction": NEUTRAL,
            "m5_bias": NEUTRAL,
            "confirmed": False,
            "confirmation_type": None,
            "reason": "NO_MAIN_DIRECTION",
        }
    m5_bias = _extract_bias(m5)
    latest = m5.get(
        "latest",
        {},
    )
    if not isinstance(latest, dict):
        latest = {}
    confirmations = []
    # ========================================================
    # BIAIS M5
    # ========================================================
    if m5_bias == direction:
        confirmations.append(
            "M5_BIAS"
        )
    # ========================================================
    # BOS
    # ========================================================
    latest_bos = latest.get(
        "bos"
    )
    bos_direction = NEUTRAL
    if isinstance(
        latest_bos,
        dict,
    ):
        bos_direction = _normalize_direction(
            latest_bos.get(
                "direction"
            )
        )
        if bos_direction == direction:
            confirmations.append(
                "M5_BOS"
            )
    # ========================================================
    # CHOCH
    # ========================================================
    latest_choch = latest.get(
        "choch"
    )
    choch_direction = NEUTRAL
    if isinstance(
        latest_choch,
        dict,
    ):
        choch_direction = _normalize_direction(
            latest_choch.get(
                "direction"
            )
        )
        if choch_direction == direction:
            confirmations.append(
                "M5_CHOCH"
            )
    # ========================================================
    # CONTRADICTION
    # ========================================================
    opposite = (
        SELL
        if direction == BUY
        else BUY
    )
    contradiction = False
    if m5_bias == opposite:
        contradiction = True
    if bos_direction == opposite:
        contradiction = True
    if choch_direction == opposite:
        contradiction = True
    # ========================================================
    # RÉSULTAT
    # ========================================================
    confirmed = (
        len(confirmations) > 0
        and not contradiction
    )
    confirmation_type = (
        confirmations[-1]
        if confirmations
        else None
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
        "confirmations":
            confirmations,
        "contradiction":
            contradiction,
    }
# ============================================================
# CONTEXTE INDICATEURS
# ============================================================
def construire_contexte_indicateurs(
    analysis: Dict[str, Any],
    direction: str,
) -> Dict[str, Any]:
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
    if ema20 > ema50:
        ema_context = "bullish"
    elif ema20 < ema50:
        ema_context = "bearish"
    else:
        ema_context = "neutral"
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
# NORMALISATION STRUCTURE POUR FIBONACCI
# ============================================================
def _normaliser_structure_fibonacci(
    structure_analysis: Any,
) -> Dict[str, Any]:
    """
    Prépare une structure strictement compatible
    avec fibonacci.py.
    """
    if not isinstance(
        structure_analysis,
        dict,
    ):
        return {
            "swings": {
                "highs": [],
                "lows": [],
            }
        }
    swings = structure_analysis.get(
        "swings",
        {},
    )
    if not isinstance(
        swings,
        dict,
    ):
        swings = {}
    normalized = {
        "swings": {
            "highs": [],
            "lows": [],
        }
    }
    # ========================================================
    # HIGH
    # ========================================================
    highs = swings.get(
        "highs",
        [],
    )
    if isinstance(
        highs,
        list,
    ):
        for position, swing in enumerate(highs):
            if not isinstance(
                swing,
                dict,
            ):
                continue
            price = _safe_float(
                swing.get(
                    "price"
                ),
                default=0.0,
            )
            index = swing.get(
                "index",
                position,
            )
            try:
                index = int(index)
            except (
                TypeError,
                ValueError,
            ):
                index = position
            if price > 0:
                normalized[
                    "swings"
                ][
                    "highs"
                ].append(
                    {
                        "index": index,
                        "price": price,
                    }
                )
    # ========================================================
    # LOW
    # ========================================================
    lows = swings.get(
        "lows",
        [],
    )
    if isinstance(
        lows,
        list,
    ):
        for position, swing in enumerate(lows):
            if not isinstance(
                swing,
                dict,
            ):
                continue
            price = _safe_float(
                swing.get(
                    "price"
                ),
                default=0.0,
            )
            index = swing.get(
                "index",
                position,
            )
            try:
                index = int(index)
            except (
                TypeError,
                ValueError,
            ):
                index = position
            if price > 0:
                normalized[
                    "swings"
                ][
                    "lows"
                ].append(
                    {
                        "index": index,
                        "price": price,
                    }
                )
    return normalized
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
    """
    if not candles:
        logger.warning(
            "Fibonacci : aucune bougie."
        )
        return {}
    if not isinstance(
        structure_analysis,
        dict,
    ):
        logger.warning(
            "Fibonacci : structure absente."
        )
        return {}
    normalized_structure = (
        _normaliser_structure_fibonacci(
            structure_analysis
        )
    )
    highs = (
        normalized_structure[
            "swings"
        ][
            "highs"
        ]
    )
    lows = (
        normalized_structure[
            "swings"
        ][
            "lows"
        ]
    )
    if not highs or not lows:
        logger.warning(
            "Fibonacci : swings insuffisants "
            "(highs=%s, lows=%s).",
            len(highs),
            len(lows),
        )
        return {}
    try:
        result = calculer_fibonacci(
            candles=candles,
            structure_analysis=normalized_structure,
        )
        if isinstance(
            result,
            dict,
        ):
            logger.info(
                "Fibonacci calculé avec succès."
            )
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
    if isinstance(
        highs,
        list,
    ):
        for swing in highs:
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
                result["highs"].append(
                    price
                )
    lows = swings.get(
        "lows",
        [],
    )
    if isinstance(
        lows,
        list,
    ):
        for swing in lows:
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
            return max(candidates)
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
            return min(candidates)
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
# RESULTAT STANDARD
# ============================================================
def _base_result(
    symbol: str,
    direction: str,
    h4_bias: str,
    h1_bias: str,
    m15_bias: str,
    m5_bias: str,
    analyses: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "status":
            "REJECT",
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
            None,
        "stop_loss":
            None,
        "score": {
            "buy_score": 0,
            "sell_score": 0,
            "final_score": 0,
            "direction": direction,
            "quality": "REJECT",
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
            {},
        "analyses":
            analyses,
        "ready_for_signal":
            False,
    }
# ============================================================
# ANALYSE PRINCIPALE
# ============================================================
def analyser_marche(
    symbol: str = DEFAULT_SYMBOL,
) -> Dict[str, Any]:
    logger.info(
        "Analyse Vision Trade AI V2 : %s",
        symbol,
    )
    logger.info(
        "SEUILS ACTIFS : SCORE >= %s/100 | RR >= 1:%s",
        DEFAULT_MIN_SCORE,
        DEFAULT_MIN_RR,
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
    # ANALYSES
    # ========================================================
    analyses: Dict[str, Dict[str, Any]] = {}
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
    h4_bias = _extract_bias(h4)
    h1_bias = _extract_bias(h1)
    m15_bias = _extract_bias(m15)
    m5_bias = _extract_bias(m5)
    # ========================================================
    # DIRECTION
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
                "final_score": 0,
                "minimum_required":
                    DEFAULT_MIN_SCORE,
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
                        False
                },
            "analyses":
                analyses,
            "ready_for_signal":
                False,
        }
    # ========================================================
    # M5
    # ========================================================
    m5_confirmation = (
        verifier_confirmation_m5(
            direction,
            m5,
        )
    )
    # ========================================================
    # INDICATEURS M15
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
        candidate_structure = (
            m15.get(
                "structure",
                {},
            )
        )
        if isinstance(
            candidate_structure,
            dict,
        ):
            m15_structure = (
                candidate_structure
            )
    fibonacci_analysis = (
        construire_fibonacci(
            candles=m15_candles,
            direction=direction,
            structure_analysis=m15_structure,
        )
    )
    fibonacci_available = bool(
        fibonacci_analysis
    )
    logger.info(
        "FIBONACCI : %s",
        "OK"
        if fibonacci_available
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
        result = _base_result(
            symbol,
            direction,
            h4_bias,
            h1_bias,
            m15_bias,
            m5_bias,
            analyses,
        )
        result.update({
            "status":
                "SCORE_ERROR",
            "error":
                str(exc),
            "fibonacci":
                fibonacci_analysis,
            "indicators":
                indicator_context,
            "m5_confirmation":
                m5_confirmation,
        })
        return result
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
        "SCORE FINAL : %.2f / 100 | MINIMUM : %s / 100",
        final_score,
        DEFAULT_MIN_SCORE,
    )
    # ========================================================
    # ENTRY
    # ========================================================
    try:
        entry = _get_last_close(
            m15_candles
        )
    except Exception as exc:
        result = _base_result(
            symbol,
            direction,
            h4_bias,
            h1_bias,
            m15_bias,
            m5_bias,
            analyses,
        )
        result.update({
            "status":
                "NO_ENTRY",
            "error":
                str(exc),
            "score":
                score_result,
            "fibonacci":
                fibonacci_analysis,
            "indicators":
                indicator_context,
            "m5_confirmation":
                m5_confirmation,
        })
        return result
    # ========================================================
    # ATR
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
        result = _base_result(
            symbol,
            direction,
            h4_bias,
            h1_bias,
            m15_bias,
            m5_bias,
            analyses,
        )
        result.update({
            "status":
                "NO_STOP_LOSS",
            "entry":
                entry,
            "score":
                score_result,
            "indicators":
                indicator_context,
            "fibonacci":
                fibonacci_analysis,
            "m5_confirmation":
                m5_confirmation,
        })
        return result
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
        result = _base_result(
            symbol,
            direction,
            h4_bias,
            h1_bias,
            m15_bias,
            m5_bias,
            analyses,
        )
        result.update({
            "status":
                "RR_ERROR",
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
            "indicators":
                indicator_context,
            "m5_confirmation":
                m5_confirmation,
        })
        return result
    # ========================================================
    # FILTRE QUALITÉ
    # ========================================================
    try:
        quality_result = filtrer_qualite(
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
    except Exception as exc:
        logger.exception(
            "Erreur filtre qualité"
        )
        result = _base_result(
            symbol,
            direction,
            h4_bias,
            h1_bias,
            m15_bias,
            m5_bias,
            analyses,
        )
        result.update({
            "status":
                "QUALITY_ERROR",
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
            "indicators":
                indicator_context,
            "m5_confirmation":
                m5_confirmation,
        })
        return result
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
    logger.info(
        "RÉSULTAT : status=%s | direction=%s | score=%.2f | seuil=%s | ready=%s",
        status,
        direction,
        final_score,
        DEFAULT_MIN_SCORE,
        ready,
    )
    # ========================================================
    # RESULTAT FINAL
    # ========================================================
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
        "fibonacci_available":
            fibonacci_available,
        "m5_confirmation":
            m5_confirmation,
        "analyses":
            analyses,
        "ready_for_signal":
            ready,
        "thresholds": {
            "minimum_score":
                DEFAULT_MIN_SCORE,
            "minimum_rr":
                DEFAULT_MIN_RR,
        },
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
    # ========================================================
    # VÉRIFICATION DES SEUILS
    # ========================================================
    assert DEFAULT_MIN_SCORE == MIN_SCORE
    assert DEFAULT_MIN_RR == MIN_RR
    assert DEFAULT_MIN_SCORE == 50
    assert DEFAULT_MIN_RR == 2.0
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
    # DIRECTION
    # ========================================================
    assert (
        determiner_direction(
            {"bias": BUY},
            {"bias": BUY},
            {"bias": NEUTRAL},
        )
        == BUY
    )
    assert (
        determiner_direction(
            {"bias": SELL},
            {"bias": SELL},
            {"bias": NEUTRAL},
        )
        == SELL
    )
    # H4 seul
    result = determiner_direction(
        {"bias": SELL},
        {"bias": NEUTRAL},
        {"bias": NEUTRAL},
    )
    assert result == SELL
    result = determiner_direction(
        {"bias": BUY},
        {"bias": NEUTRAL},
        {"bias": NEUTRAL},
    )
    assert result == BUY
    # H1 + M15 alignés avec H4 neutre
    assert (
        determiner_direction(
            {"bias": NEUTRAL},
            {"bias": BUY},
            {"bias": BUY},
        )
        == BUY
    )
    assert (
        determiner_direction(
            {"bias": NEUTRAL},
            {"bias": SELL},
            {"bias": SELL},
        )
        == SELL
    )
    # H4 + M15 alignés
    assert (
        determiner_direction(
            {"bias": BUY},
            {"bias": NEUTRAL},
            {"bias": BUY},
        )
        == BUY
    )
    assert (
        determiner_direction(
            {"bias": SELL},
            {"bias": NEUTRAL},
            {"bias": SELL},
        )
        == SELL
    )
    # Conflits
    assert (
        determiner_direction(
            {"bias": SELL},
            {"bias": BUY},
            {"bias": BUY},
        )
        == NEUTRAL
    )
    assert (
        determiner_direction(
            {"bias": BUY},
            {"bias": SELL},
            {"bias": SELL},
        )
        == NEUTRAL
    )
    assert (
        determiner_direction(
            {"bias": BUY},
            {"bias": SELL},
            {"bias": NEUTRAL},
        )
        == NEUTRAL
    )
    assert (
        determiner_direction(
            {"bias": SELL},
            {"bias": BUY},
            {"bias": NEUTRAL},
        )
        == NEUTRAL
    )
    # Tous NEUTRAL
    assert (
        determiner_direction(
            {"bias": NEUTRAL},
            {"bias": NEUTRAL},
            {"bias": NEUTRAL},
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
    assert indicators["ema20"] == 110
    assert indicators["ema50"] == 100
    assert indicators["rsi"] == 55
    assert indicators["atr"] == 6
    assert (
        indicators["ema_context"]
        == "bullish"
    )
    assert (
        indicators["rsi_context"]
        == "bullish_bias"
    )
    # ========================================================
    # NORMALISATION FIBONACCI
    # ========================================================
    fake_structure = {
        "swings": {
            "highs": [
                {
                    "index": 90,
                    "price": 190,
                }
            ],
            "lows": [
                {
                    "index": 80,
                    "price": 180,
                }
            ],
        }
    }
    normalized = (
        _normaliser_structure_fibonacci(
            fake_structure
        )
    )
    assert (
        normalized["swings"]["highs"][0]["price"]
        == 190
    )
    assert (
        normalized["swings"]["lows"][0]["price"]
        == 180
    )
    assert (
        normalized["swings"]["highs"][0]["index"]
        == 90
    )
    assert (
        normalized["swings"]["lows"][0]["index"]
        == 80
    )
    # ========================================================
    # FIBONACCI
    # ========================================================
    candles = [
        {
            "datetime": str(i),
            "open": 100 + i,
            "high": 101 + i,
            "low": 99 + i,
            "close": 100.5 + i,
        }
        for i in range(100)
    ]
    fib = construire_fibonacci(
        candles=candles,
        direction=BUY,
        structure_analysis=fake_structure,
    )
    assert isinstance(
        fib,
        dict,
    )
    assert "levels" in fib
    assert "position" in fib
    assert "closest_level" in fib
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
    # STOP LOSS ATR FALLBACK
    # ========================================================
    assert (
        determiner_stop_loss(
            BUY,
            100,
            {"swings": {}},
            {"swings": {}},
            5,
        )
        == 92.5
    )
    assert (
        determiner_stop_loss(
            SELL,
            100,
            {"swings": {}},
            {"swings": {}},
            5,
        )
        == 107.5
    )
    # ========================================================
    # VALIDATION STOP LOSS
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
    assert (
        _validate_stop_loss(
            NEUTRAL,
            100,
            90,
        )
        is False
    )
    logger.info(
        "analyse.py : tests OK"
    )
# ============================================================
# EXECUTION DIRECTE
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
    print("=" * 60)
    print(
        "VISION TRADE AI V2"
    )
    print(
        "Test analyse.py"
    )
    print("=" * 60)
    try:
        _run_internal_test()
        print(
            "ANALYSE : OK"
        )
        print(
            f"SCORE MINIMUM : {DEFAULT_MIN_SCORE}/100"
        )
        print(
            f"RR MINIMUM : 1:{DEFAULT_MIN_RR}"
        )
    except Exception as exc:
        print(
            "ANALYSE : ERREUR"
        )
        print(
            exc
        )