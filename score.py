"""
Vision Trade AI V2
score.py
MOTEUR DE SCORING DÉTERMINISTE
Architecture :
    H4  -> tendance globale
    H1  -> structure principale
    M15 -> contexte / zones
    M5  -> confirmation / trigger
IMPORTANT :
- aucune IA ;
- aucun appel API ;
- aucun calcul SL/TP ;
- aucune création de direction ;
- la direction est fournie par analyse.py ;
- le score mesure uniquement la qualité de cette direction.
Score toujours sur 100.
Seuil par défaut : 50.
"""
from __future__ import annotations
import logging
from dataclasses import dataclass, asdict
from typing import Any, Dict, Optional
logger = logging.getLogger(__name__)
# ============================================================
# CONSTANTES
# ============================================================
BUY = "BUY"
SELL = "SELL"
NEUTRAL = "NEUTRAL"
BULLISH = "bullish"
BEARISH = "bearish"
MIN_SCORE = 0
MAX_SCORE = 100
DEFAULT_SIGNAL_THRESHOLD = 50
# ============================================================
# NORMALISATION
# ============================================================
def _normalize_direction(direction: Any) -> str:
    if direction is None:
        return NEUTRAL.lower()
    value = str(direction).lower().strip()
    mapping = {
        "buy": BULLISH,
        "bull": BULLISH,
        "bullish": BULLISH,
        "long": BULLISH,
        "up": BULLISH,
        "sell": BEARISH,
        "bear": BEARISH,
        "bearish": BEARISH,
        "short": BEARISH,
        "down": BEARISH,
        "neutral": NEUTRAL.lower(),
        "none": NEUTRAL.lower(),
        "": NEUTRAL.lower(),
    }
    return mapping.get(value, NEUTRAL.lower())
def _direction_label(direction: Any) -> str:
    normalized = _normalize_direction(direction)
    if normalized == BULLISH:
        return BUY
    if normalized == BEARISH:
        return SELL
    return NEUTRAL
# ============================================================
# OUTILS ROBUSTES
# ============================================================
def _safe_float(value: Any) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
def _safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}
def _safe_list(value: Any) -> list:
    return value if isinstance(value, list) else []
def _clamp(
    value: float,
    minimum: float = MIN_SCORE,
    maximum: float = MAX_SCORE,
) -> int:
    return int(
        max(
            minimum,
            min(
                maximum,
                round(value),
            ),
        )
    )
def _clamp_signed(
    value: float,
    minimum: float,
    maximum: float,
) -> int:
    return int(
        max(
            minimum,
            min(
                maximum,
                round(value),
            ),
        )
    )
# ============================================================
# EXTRACTION ROBUSTE DES STRUCTURES
# ============================================================
def _get_latest(
    analysis: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Récupère latest même si le module amont utilise
    un format légèrement différent.
    """
    if not isinstance(analysis, dict):
        return {}
    latest = analysis.get("latest")
    if isinstance(latest, dict):
        return latest
    return {}
def _get_structure_item(
    analysis: Dict[str, Any],
    latest_keys: tuple[str, ...],
    root_keys: tuple[str, ...],
) -> Dict[str, Any]:
    """
    Recherche un élément structurel dans plusieurs formats.
    Exemple :
        latest["bos"]
        analysis["bos"]
        analysis["latest_bos"]
    """
    latest = _get_latest(analysis)
    for key in latest_keys:
        value = latest.get(key)
        if isinstance(value, dict):
            return value
    for key in root_keys:
        value = analysis.get(key)
        if isinstance(value, dict):
            return value
    return {}
def _get_direction_from_item(
    item: Any,
) -> str:
    """
    Extrait la direction d'un élément structurel.
    """
    if not isinstance(item, dict):
        return NEUTRAL.lower()
    for key in (
        "direction",
        "bias",
        "type",
        "side",
        "signal",
    ):
        if key in item:
            direction = _normalize_direction(
                item.get(key)
            )
            if direction != NEUTRAL.lower():
                return direction
    return NEUTRAL.lower()
def _has_structure_item(
    analysis: Dict[str, Any],
    latest_keys: tuple[str, ...],
    root_keys: tuple[str, ...],
) -> bool:
    return bool(
        _get_structure_item(
            analysis,
            latest_keys,
            root_keys,
        )
    )
# ============================================================
# RESULTAT
# ============================================================
@dataclass
class ScoreResult:
    buy_score: int
    sell_score: int
    final_score: int
    direction: str
    quality: str
    confirmations: int
    contradictions: int
    reasons: list[str]
    warnings: list[str]
# ============================================================
# SCORE ENGINE
# ============================================================
class ScoreEngine:
    WEIGHTS = {
        "h4_trend": 15,
        "h1_structure": 20,
        "m15_smc": 20,
        "m5_confirmation": 15,
        "fibonacci": 10,
        "indicators": 10,
        "liquidity": 10,
    }
    def __init__(
        self,
        threshold: int = DEFAULT_SIGNAL_THRESHOLD,
    ) -> None:
        if not isinstance(threshold, int):
            raise ValueError(
                "Le threshold doit être un entier."
            )
        if not 1 <= threshold <= 100:
            raise ValueError(
                "Le threshold doit être compris entre 1 et 100."
            )
        self.threshold = threshold
    # ========================================================
    # H4
    # ========================================================
    def score_h4_trend(
        self,
        h4_bias: str,
        direction: str,
    ) -> tuple[int, Optional[str]]:
        bias = _normalize_direction(h4_bias)
        target = _normalize_direction(direction)
        if target == NEUTRAL.lower():
            return 0, None
        if bias == NEUTRAL.lower():
            return 0, None
        if bias == target:
            return (
                15,
                "Tendance H4 alignée.",
            )
        return (
            -15,
            "Tendance H4 opposée.",
        )
    # ========================================================
    # H1
    # ========================================================
    def score_h1_structure(
        self,
        h1_analysis: Dict[str, Any],
        direction: str,
    ) -> tuple[int, list[str]]:
        h1_analysis = _safe_dict(h1_analysis)
        target = _normalize_direction(direction)
        if target == NEUTRAL.lower():
            return 0, []
        score = 0
        reasons = []
        # ----------------------------------------------------
        # BIAIS
        # ----------------------------------------------------
        bias = _normalize_direction(
            h1_analysis.get(
                "bias",
                h1_analysis.get(
                    "direction",
                    NEUTRAL,
                ),
            )
        )
        if bias == target:
            score += 10
            reasons.append(
                "Biais H1 aligné."
            )
        elif bias != NEUTRAL.lower():
            score -= 10
            reasons.append(
                "Biais H1 opposé."
            )
        # ----------------------------------------------------
        # BOS
        # ----------------------------------------------------
        bos = _get_structure_item(
            h1_analysis,
            (
                "bos",
                "BOS",
                "latest_bos",
            ),
            (
                "bos",
                "BOS",
                "latest_bos",
            ),
        )
        if bos:
            bos_direction = _get_direction_from_item(
                bos
            )
            if bos_direction == target:
                score += 10
                reasons.append(
                    "BOS H1 aligné."
                )
            elif bos_direction != NEUTRAL.lower():
                score -= 10
                reasons.append(
                    "BOS H1 opposé."
                )
        # ----------------------------------------------------
        # CHOCH
        # ----------------------------------------------------
        choch = _get_structure_item(
            h1_analysis,
            (
                "choch",
                "CHoCH",
                "CHOC",
                "latest_choch",
            ),
            (
                "choch",
                "CHoCH",
                "CHOC",
                "latest_choch",
            ),
        )
        if choch:
            choch_direction = _get_direction_from_item(
                choch
            )
            if choch_direction == target:
                score += 5
                reasons.append(
                    "CHoCH H1 aligné."
                )
            elif choch_direction != NEUTRAL.lower():
                score -= 5
                reasons.append(
                    "CHoCH H1 opposé."
                )
        return (
            _clamp_signed(
                score,
                -20,
                20,
            ),
            reasons,
        )
    # ========================================================
    # M15 SMC
    # ========================================================
    def score_m15_smc(
        self,
        m15_analysis: Dict[str, Any],
        direction: str,
    ) -> tuple[int, list[str]]:
        m15_analysis = _safe_dict(m15_analysis)
        target = _normalize_direction(direction)
        if target == NEUTRAL.lower():
            return 0, []
        score = 0
        reasons = []
        # ----------------------------------------------------
        # BIAS
        # ----------------------------------------------------
        bias = _normalize_direction(
            m15_analysis.get(
                "bias",
                m15_analysis.get(
                    "direction",
                    NEUTRAL,
                ),
            )
        )
        if bias == target:
            score += 4
            reasons.append(
                "Structure M15 alignée."
            )
        elif bias != NEUTRAL.lower():
            score -= 4
            reasons.append(
                "Structure M15 opposée."
            )
        # ----------------------------------------------------
        # ORDER BLOCK
        # ----------------------------------------------------
        ob = _get_structure_item(
            m15_analysis,
            (
                "order_block",
                "orderblock",
                "ob",
                "latest_order_block",
            ),
            (
                "order_block",
                "orderblock",
                "ob",
                "latest_order_block",
            ),
        )
        if ob:
            ob_direction = _get_direction_from_item(ob)
            if ob_direction == target:
                score += 7
                reasons.append(
                    "Order Block aligné."
                )
            elif ob_direction != NEUTRAL.lower():
                score -= 5
                reasons.append(
                    "Order Block opposé."
                )
        # ----------------------------------------------------
        # FVG
        # ----------------------------------------------------
        fvg = _get_structure_item(
            m15_analysis,
            (
                "fvg",
                "FVG",
                "fair_value_gap",
                "latest_fvg",
            ),
            (
                "fvg",
                "FVG",
                "fair_value_gap",
                "latest_fvg",
            ),
        )
        if fvg:
            fvg_direction = _get_direction_from_item(fvg)
            if fvg_direction == target:
                score += 6
                reasons.append(
                    "FVG aligné."
                )
            elif fvg_direction != NEUTRAL.lower():
                score -= 4
                reasons.append(
                    "FVG opposé."
                )
        return (
            _clamp_signed(
                score,
                -20,
                20,
            ),
            reasons,
        )
    # ========================================================
    # M5
    # ========================================================
    def score_m5_confirmation(
        self,
        m5_analysis: Dict[str, Any],
        direction: str,
    ) -> tuple[int, list[str]]:
        m5_analysis = _safe_dict(m5_analysis)
        target = _normalize_direction(direction)
        if target == NEUTRAL.lower():
            return 0, []
        score = 0
        reasons = []
        # ----------------------------------------------------
        # BIAS
        # ----------------------------------------------------
        bias = _normalize_direction(
            m5_analysis.get(
                "bias",
                m5_analysis.get(
                    "direction",
                    NEUTRAL,
                ),
            )
        )
        if bias == target:
            score += 7
            reasons.append(
                "Biais M5 confirmé."
            )
        elif bias != NEUTRAL.lower():
            score -= 7
            reasons.append(
                "Biais M5 opposé."
            )
        # ----------------------------------------------------
        # BOS M5
        # ----------------------------------------------------
        bos = _get_structure_item(
            m5_analysis,
            (
                "bos",
                "BOS",
                "latest_bos",
            ),
            (
                "bos",
                "BOS",
                "latest_bos",
            ),
        )
        if bos:
            bos_direction = _get_direction_from_item(bos)
            if bos_direction == target:
                score += 5
                reasons.append(
                    "BOS M5 confirmé."
                )
            elif bos_direction != NEUTRAL.lower():
                score -= 5
                reasons.append(
                    "BOS M5 opposé."
                )
        # ----------------------------------------------------
        # CHOCH M5
        # ----------------------------------------------------
        choch = _get_structure_item(
            m5_analysis,
            (
                "choch",
                "CHoCH",
                "CHOC",
                "latest_choch",
            ),
            (
                "choch",
                "CHoCH",
                "CHOC",
                "latest_choch",
            ),
        )
        if choch:
            choch_direction = _get_direction_from_item(
                choch
            )
            if choch_direction == target:
                score += 3
                reasons.append(
                    "CHoCH M5 confirmé."
                )
            elif choch_direction != NEUTRAL.lower():
                score -= 3
                reasons.append(
                    "CHoCH M5 opposé."
                )
        return (
            _clamp_signed(
                score,
                -15,
                15,
            ),
            reasons,
        )
    # ========================================================
    # FIBONACCI
    # ========================================================
    def score_fibonacci(
        self,
        fibonacci_analysis: Dict[str, Any],
        direction: str,
    ) -> tuple[int, list[str]]:
        fibonacci_analysis = _safe_dict(
            fibonacci_analysis
        )
        target = _normalize_direction(direction)
        if target == NEUTRAL.lower():
            return 0, []
        score = 0
        reasons = []
        position = _safe_dict(
            fibonacci_analysis.get(
                "position",
                {},
            )
        )
        zone = str(
            position.get(
                "zone",
                "",
            )
            or ""
        ).lower().strip()
        if target == BULLISH:
            if zone == "discount":
                score += 6
                reasons.append(
                    "Prix en zone Discount."
                )
            elif zone == "premium":
                score -= 6
                reasons.append(
                    "Prix en zone Premium défavorable au BUY."
                )
        elif target == BEARISH:
            if zone == "premium":
                score += 6
                reasons.append(
                    "Prix en zone Premium."
                )
            elif zone == "discount":
                score -= 6
                reasons.append(
                    "Prix en zone Discount défavorable au SELL."
                )
        closest = _safe_dict(
            fibonacci_analysis.get(
                "closest_level"
            )
        )
        if closest:
            level = str(
                closest.get(
                    "level",
                    "",
                )
            ).strip()
            if level in {
                "0.618",
                "0.705",
                "0.786",
            }:
                score += 4
                reasons.append(
                    f"Retracement Fibonacci {level} favorable."
                )
        return (
            _clamp_signed(
                score,
                -10,
                10,
            ),
            reasons,
        )
    # ========================================================
    # INDICATEURS
    # ========================================================
    def score_indicators(
        self,
        indicators: Dict[str, Any],
        direction: str,
    ) -> tuple[int, list[str]]:
        indicators = _safe_dict(indicators)
        target = _normalize_direction(direction)
        if target == NEUTRAL.lower():
            return 0, []
        score = 0
        reasons = []
        ema_context = _normalize_direction(
            indicators.get(
                "ema_context",
                "",
            )
        )
        rsi_context = str(
            indicators.get(
                "rsi_context",
                "",
            )
            or ""
        ).lower().strip()
        rsi = _safe_float(
            indicators.get(
                "rsi"
            )
        )
        # EMA
        if ema_context == target:
            score += 5
            reasons.append(
                "EMA alignées."
            )
        elif (
            ema_context != NEUTRAL.lower()
            and ema_context
        ):
            score -= 5
            reasons.append(
                "EMA opposées."
            )
        # RSI
        if target == BULLISH:
            if rsi_context == "bullish_bias":
                score += 3
                reasons.append(
                    "RSI favorable aux acheteurs."
                )
            elif rsi_context == "oversold":
                score += 2
                reasons.append(
                    "RSI en zone survendue."
                )
            elif rsi_context == "overbought":
                score -= 3
                reasons.append(
                    "RSI en zone surachetée."
                )
        elif target == BEARISH:
            if rsi_context == "bearish_bias":
                score += 3
                reasons.append(
                    "RSI favorable aux vendeurs."
                )
            elif rsi_context == "overbought":
                score += 2
                reasons.append(
                    "RSI en zone surachetée."
                )
            elif rsi_context == "oversold":
                score -= 3
                reasons.append(
                    "RSI en zone survendue."
                )
        # RSI extrême
        if rsi is not None:
            if target == BULLISH and rsi >= 80:
                score -= 2
                reasons.append(
                    "RSI extrêmement élevé."
                )
            elif target == BEARISH and rsi <= 20:
                score -= 2
                reasons.append(
                    "RSI extrêmement bas."
                )
        return (
            _clamp_signed(
                score,
                -10,
                10,
            ),
            reasons,
        )
    # ========================================================
    # LIQUIDITÉ
    # ========================================================
    def score_liquidity(
        self,
        structure_analysis: Dict[str, Any],
        direction: str,
    ) -> tuple[int, list[str]]:
        structure_analysis = _safe_dict(
            structure_analysis
        )
        target = _normalize_direction(direction)
        if target == NEUTRAL.lower():
            return 0, []
        sweep = _get_structure_item(
            structure_analysis,
            (
                "liquidity_sweep",
                "liquidity_sweeps",
                "sweep",
                "latest_liquidity_sweep",
            ),
            (
                "liquidity_sweep",
                "latest_liquidity_sweep",
                "sweep",
            ),
        )
        if not sweep:
            return 0, []
        sweep_direction = _get_direction_from_item(
            sweep
        )
        if sweep_direction == target:
            return (
                10,
                [
                    "Sweep de liquidité confirmé."
                ],
            )
        if sweep_direction != NEUTRAL.lower():
            return (
                -8,
                [
                    "Sweep de liquidité opposé."
                ],
            )
        return 0, []
    # ========================================================
    # CALCUL GLOBAL
    # ========================================================
    def calculate(
        self,
        direction: str,
        h4_bias: str = NEUTRAL,
        h1_analysis: Optional[Dict] = None,
        m15_analysis: Optional[Dict] = None,
        m5_analysis: Optional[Dict] = None,
        fibonacci_analysis: Optional[Dict] = None,
        indicators: Optional[Dict] = None,
    ) -> ScoreResult:
        normalized_direction = _normalize_direction(
            direction
        )
        if normalized_direction not in {
            BULLISH,
            BEARISH,
        }:
            raise ValueError(
                "direction doit être BUY ou SELL."
            )
        output_direction = _direction_label(
            normalized_direction
        )
        buy_score = 0
        sell_score = 0
        reasons: list[str] = []
        warnings: list[str] = []
        confirmations = 0
        contradictions = 0
        # ----------------------------------------------------
        # AJOUT SCORE
        # ----------------------------------------------------
        def add_score(
            points: int,
            block_reasons: Optional[list[str]] = None,
        ) -> None:
            nonlocal buy_score
            nonlocal sell_score
            nonlocal confirmations
            nonlocal contradictions
            if normalized_direction == BULLISH:
                buy_score += points
            else:
                sell_score += points
            block_reasons = (
                block_reasons
                if isinstance(
                    block_reasons,
                    list,
                )
                else []
            )
            if points > 0:
                confirmations += 1
                reasons.extend(
                    str(reason)
                    for reason in block_reasons
                    if reason
                )
            elif points < 0:
                contradictions += 1
                warnings.extend(
                    str(reason)
                    for reason in block_reasons
                    if reason
                )
        # ----------------------------------------------------
        # H4
        # ----------------------------------------------------
        points, reason = self.score_h4_trend(
            h4_bias,
            normalized_direction,
        )
        add_score(
            points,
            [reason] if reason else [],
        )
        # ----------------------------------------------------
        # H1
        # ----------------------------------------------------
        points, block_reasons = self.score_h1_structure(
            h1_analysis or {},
            normalized_direction,
        )
        add_score(
            points,
            block_reasons,
        )
        # ----------------------------------------------------
        # M15
        # ----------------------------------------------------
        points, block_reasons = self.score_m15_smc(
            m15_analysis or {},
            normalized_direction,
        )
        add_score(
            points,
            block_reasons,
        )
        # ----------------------------------------------------
        # M5
        # ----------------------------------------------------
        points, block_reasons = self.score_m5_confirmation(
            m5_analysis or {},
            normalized_direction,
        )
        add_score(
            points,
            block_reasons,
        )
        # ----------------------------------------------------
        # FIBONACCI
        # ----------------------------------------------------
        points, block_reasons = self.score_fibonacci(
            fibonacci_analysis or {},
            normalized_direction,
        )
        add_score(
            points,
            block_reasons,
        )
        # ----------------------------------------------------
        # INDICATEURS
        # ----------------------------------------------------
        points, block_reasons = self.score_indicators(
            indicators or {},
            normalized_direction,
        )
        add_score(
            points,
            block_reasons,
        )
        # ----------------------------------------------------
        # LIQUIDITÉ
        # ----------------------------------------------------
        points, block_reasons = self.score_liquidity(
            m15_analysis or {},
            normalized_direction,
        )
        add_score(
            points,
            block_reasons,
        )
        # ----------------------------------------------------
        # SCORE FINAL
        # ----------------------------------------------------
        if normalized_direction == BULLISH:
            final_score = buy_score
        else:
            final_score = sell_score
        final_score = _clamp(
            final_score
        )
        buy_score = _clamp(
            buy_score
        )
        sell_score = _clamp(
            sell_score
        )
        # ----------------------------------------------------
        # QUALITÉ
        # ----------------------------------------------------
        quality = self.determine_quality(
            final_score
        )
        return ScoreResult(
            buy_score=buy_score,
            sell_score=sell_score,
            final_score=final_score,
            direction=output_direction,
            quality=quality,
            confirmations=confirmations,
            contradictions=contradictions,
            reasons=reasons,
            warnings=warnings,
        )
    # ========================================================
    # QUALITÉ
    # ========================================================
    def determine_quality(
        self,
        score: int,
    ) -> str:
        score = _clamp(score)
        if score >= 90:
            return "A+"
        if score >= 80:
            return "A"
        if score >= 70:
            return "B"
        if score >= 60:
            return "C"
        if score >= 50:
            return "D"
        return "REJECT"
# ============================================================
# FONCTION PUBLIQUE
# ============================================================
def calculer_score(
    direction: str,
    h4_bias: str = NEUTRAL,
    h1_analysis: Optional[Dict] = None,
    m15_analysis: Optional[Dict] = None,
    m5_analysis: Optional[Dict] = None,
    fibonacci_analysis: Optional[Dict] = None,
    indicators: Optional[Dict] = None,
    threshold: int = DEFAULT_SIGNAL_THRESHOLD,
) -> Dict[str, Any]:
    engine = ScoreEngine(
        threshold=threshold
    )
    result = engine.calculate(
        direction=direction,
        h4_bias=h4_bias,
        h1_analysis=h1_analysis,
        m15_analysis=m15_analysis,
        m5_analysis=m5_analysis,
        fibonacci_analysis=fibonacci_analysis,
        indicators=indicators,
    )
    data = asdict(result)
    data["threshold"] = threshold
    data["passes_threshold"] = (
        result.final_score >= threshold
    )
    return data
# ============================================================
# TEST DE COMPATIBILITÉ
# ============================================================
def _run_internal_test() -> None:
    engine = ScoreEngine()
    # --------------------------------------------------------
    # BUY COMPLET
    # --------------------------------------------------------
    h1 = {
        "bias": "bullish",
        "latest": {
            "bos": {
                "direction": "bullish"
            },
            "choch": {
                "direction": "bullish"
            },
        },
    }
    m15 = {
        "bias": "bullish",
        "latest": {
            "order_block": {
                "direction": "bullish"
            },
            "fvg": {
                "direction": "bullish"
            },
            "liquidity_sweep": {
                "direction": "bullish"
            },
        },
    }
    m5 = {
        "bias": "bullish",
        "latest": {
            "bos": {
                "direction": "bullish"
            },
            "choch": {
                "direction": "bullish"
            },
        },
    }
    fibonacci = {
        "position": {
            "zone": "discount"
        },
        "closest_level": {
            "level": "0.705"
        },
    }
    indicators = {
        "ema_context": "bullish",
        "rsi_context": "bullish_bias",
        "rsi": 56,
    }
    result = calculer_score(
        direction="BUY",
        h4_bias="bullish",
        h1_analysis=h1,
        m15_analysis=m15,
        m5_analysis=m5,
        fibonacci_analysis=fibonacci,
        indicators=indicators,
    )
    assert result["direction"] == "BUY"
    assert result["final_score"] > 0
    assert result["final_score"] <= 100
    assert result["passes_threshold"] is True
    print(
        "BUY FINAL SCORE:",
        result["final_score"],
    )
    # --------------------------------------------------------
    # SELL
    # --------------------------------------------------------
    sell_result = calculer_score(
        direction="SELL",
        h4_bias="bearish",
        h1_analysis={
            "bias": "bearish",
            "latest": {
                "bos": {
                    "direction": "bearish"
                }
            },
        },
        m15_analysis={
            "bias": "bearish",
            "latest": {
                "order_block": {
                    "direction": "bearish"
                },
                "fvg": {
                    "direction": "bearish"
                },
                "liquidity_sweep": {
                    "direction": "bearish"
                },
            },
        },
        m5_analysis={
            "bias": "bearish",
            "latest": {
                "bos": {
                    "direction": "bearish"
                }
            },
        },
        fibonacci_analysis={
            "position": {
                "zone": "premium"
            },
            "closest_level": {
                "level": "0.705"
            },
        },
        indicators={
            "ema_context": "bearish",
            "rsi_context": "bearish_bias",
            "rsi": 44,
        },
    )
    assert sell_result["direction"] == "SELL"
    assert sell_result["final_score"] > 0
    assert sell_result["final_score"] <= 100
    print(
        "SELL FINAL SCORE:",
        sell_result["final_score"],
    )
    # --------------------------------------------------------
    # NEUTRAL REFUSÉ
    # --------------------------------------------------------
    try:
        calculer_score(
            direction="NEUTRAL"
        )
        raise AssertionError(
            "NEUTRAL aurait dû être refusé."
        )
    except ValueError:
        pass
    # --------------------------------------------------------
    # AUCUNE DONNÉE = 0
    # --------------------------------------------------------
    empty = calculer_score(
        direction="BUY"
    )
    assert empty["final_score"] == 0
    assert empty["passes_threshold"] is False
    # --------------------------------------------------------
    # CONTRADICTION
    # --------------------------------------------------------
    contradiction = calculer_score(
        direction="BUY",
        h4_bias="bearish",
        h1_analysis={
            "bias": "bearish"
        },
        m15_analysis={
            "bias": "bearish"
        },
        m5_analysis={
            "bias": "bearish"
        },
        fibonacci_analysis={
            "position": {
                "zone": "premium"
            }
        },
        indicators={
            "ema_context": "bearish",
            "rsi_context": "overbought",
            "rsi": 85,
        },
    )
    assert contradiction["final_score"] < 50
    assert contradiction["passes_threshold"] is False
    assert contradiction["contradictions"] > 0
    print(
        "CONTRADICTION TEST : OK"
    )
    # --------------------------------------------------------
    # QUALITÉ
    # --------------------------------------------------------
    assert engine.determine_quality(100) == "A+"
    assert engine.determine_quality(90) == "A+"
    assert engine.determine_quality(89) == "A"
    assert engine.determine_quality(80) == "A"
    assert engine.determine_quality(79) == "B"
    assert engine.determine_quality(70) == "B"
    assert engine.determine_quality(69) == "C"
    assert engine.determine_quality(60) == "C"
    assert engine.determine_quality(59) == "D"
    assert engine.determine_quality(50) == "D"
    assert engine.determine_quality(49) == "REJECT"
    print(
        "QUALITÉ TEST : OK"
    )
    print(
        "TOUS LES TESTS SCORE.PY : OK"
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
    print("=" * 60)
    print("VISION TRADE AI V2")
    print("TEST SCORE.PY")
    print("SCORE SUR 100")
    print("SEUIL : 50/100")
    print("=" * 60)
    try:
        _run_internal_test()
        print()
        print("✅ SCORE.PY : OK")
        print("Moteur de scoring opérationnel.")
    except Exception as exc:
        print()
        print("❌ SCORE.PY : ÉCHEC")
        print(
            f"Erreur : {type(exc).__name__}: {exc}"
        )
        raise