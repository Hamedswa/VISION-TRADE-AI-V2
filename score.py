"""
Vision Trade AI V2
score.py
MOTEUR DE SCORING DÉTERMINISTE

Architecture :
    H4  -> tendance globale
    H1  -> structure principale
    M15 -> contexte / zones
    M5  -> confirmation / trigger

Responsabilités :
- analyser les confluences techniques ;
- attribuer des points BUY / SELL ;
- pénaliser les contradictions ;
- calculer un score final sur 100 ;
- déterminer la qualité du setup.

IMPORTANT :
- aucune IA ;
- aucun appel API ;
- aucun calcul de SL/TP ;
- aucun signal Telegram ;
- aucune création de direction.

La direction est fournie par analyse.py.
Le score mesure uniquement la qualité de cette direction.

SEUIL :
    50 / 100

Le score est toujours calculé sur 100.
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
# NORMALISATION DES DIRECTIONS
# ============================================================

def _normalize_direction(direction: Any) -> str:
    """
    Normalise toutes les représentations de direction.

    BUY / BULLISH / LONG  -> bullish
    SELL / BEARISH / SHORT -> bearish
    NEUTRAL / NONE / vide -> neutral
    """

    if direction is None:
        return NEUTRAL.lower()

    value = str(direction).strip().lower()

    mapping = {
        "buy": BULLISH,
        "bullish": BULLISH,
        "long": BULLISH,

        "sell": BEARISH,
        "bearish": BEARISH,
        "short": BEARISH,

        "neutral": NEUTRAL.lower(),
        "none": NEUTRAL.lower(),
        "": NEUTRAL.lower(),
    }

    return mapping.get(
        value,
        NEUTRAL.lower(),
    )


def _direction_label(direction: Any) -> str:
    """
    Convertit une direction interne vers BUY / SELL / NEUTRAL.
    """

    normalized = _normalize_direction(direction)

    if normalized == BULLISH:
        return BUY

    if normalized == BEARISH:
        return SELL

    return NEUTRAL


def _same_direction(
    first: Any,
    second: Any,
) -> bool:
    """
    Compare deux directions après normalisation.

    Exemple :
        BUY == bullish -> True
        SELL == bearish -> True
    """

    first_normalized = _normalize_direction(first)
    second_normalized = _normalize_direction(second)

    return (
        first_normalized != NEUTRAL.lower()
        and first_normalized == second_normalized
    )


# ============================================================
# MODÈLE DE SCORE
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
# OUTILS
# ============================================================

def _clamp(
    value: float,
    minimum: float = MIN_SCORE,
    maximum: float = MAX_SCORE,
) -> int:
    """
    Force une valeur dans 0-100.
    """

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
    """
    Force une valeur dans une plage signée.
    """

    return int(
        max(
            minimum,
            min(
                maximum,
                round(value),
            ),
        )
    )


def _safe_float(
    value: Any,
) -> Optional[float]:
    """
    Conversion robuste vers float.
    """

    if value is None:
        return None

    if isinstance(value, bool):
        return None

    try:
        return float(value)
    except (
        TypeError,
        ValueError,
    ):
        return None


def _safe_dict(
    value: Any,
) -> Dict[str, Any]:
    """
    Retourne un dictionnaire sûr.
    """

    if isinstance(value, dict):
        return value

    return {}


# ============================================================
# SCORE ENGINE
# ============================================================

class ScoreEngine:
    """
    Moteur déterministe de scoring.

    Pondération maximale :

        H4 tendance       15
        H1 structure      20
        M15 SMC           20
        M5 confirmation   15
        Fibonacci         10
        Indicateurs       10
        Liquidité         10
        --------------------
        TOTAL            100

    Les pénalités réduisent le score.
    Elles ne créent jamais de direction.
    """

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

        if not isinstance(
            threshold,
            int,
        ):
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

        if _same_direction(bias, target):
            return (
                self.WEIGHTS["h4_trend"],
                "Tendance H4 alignée.",
            )

        return (
            -self.WEIGHTS["h4_trend"],
            "Tendance H4 opposée.",
        )

    # ========================================================
    # H1 STRUCTURE
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

        bias = _normalize_direction(
            h1_analysis.get(
                "bias",
                NEUTRAL,
            )
        )

        if _same_direction(bias, target):

            score += 10

            reasons.append(
                "Biais H1 aligné."
            )

        elif (
            bias != NEUTRAL.lower()
            and not _same_direction(
                bias,
                target,
            )
        ):

            score -= 10

            reasons.append(
                "Biais H1 opposé."
            )

        latest = _safe_dict(
            h1_analysis.get(
                "latest",
                {},
            )
        )

        # ----------------------------------------------------
        # BOS
        # ----------------------------------------------------

        bos = _safe_dict(
            latest.get(
                "bos"
            )
        )

        if bos:

            bos_direction = _normalize_direction(
                bos.get(
                    "direction"
                )
            )

            if _same_direction(
                bos_direction,
                target,
            ):

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

        choch = _safe_dict(
            latest.get(
                "choch"
            )
        )

        if choch:

            choch_direction = _normalize_direction(
                choch.get(
                    "direction"
                )
            )

            if _same_direction(
                choch_direction,
                target,
            ):

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
                -self.WEIGHTS["h1_structure"],
                self.WEIGHTS["h1_structure"],
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

        latest = _safe_dict(
            m15_analysis.get(
                "latest",
                {},
            )
        )

        # ----------------------------------------------------
        # ORDER BLOCK
        # ----------------------------------------------------

        latest_ob = _safe_dict(
            latest.get(
                "order_block"
            )
        )

        if latest_ob:

            ob_direction = _normalize_direction(
                latest_ob.get(
                    "direction"
                )
            )

            if _same_direction(
                ob_direction,
                target,
            ):

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

        latest_fvg = _safe_dict(
            latest.get(
                "fvg"
            )
        )

        if latest_fvg:

            fvg_direction = _normalize_direction(
                latest_fvg.get(
                    "direction"
                )
            )

            if _same_direction(
                fvg_direction,
                target,
            ):

                score += 6

                reasons.append(
                    "FVG aligné."
                )

            elif fvg_direction != NEUTRAL.lower():

                score -= 4

                reasons.append(
                    "FVG opposé."
                )

        # ----------------------------------------------------
        # BIAIS M15
        # ----------------------------------------------------

        bias = _normalize_direction(
            m15_analysis.get(
                "bias",
                NEUTRAL,
            )
        )

        if _same_direction(
            bias,
            target,
        ):

            score += 4

            reasons.append(
                "Structure M15 alignée."
            )

        elif bias != NEUTRAL.lower():

            score -= 4

            reasons.append(
                "Structure M15 opposée."
            )

        # Le liquidity sweep est calculé uniquement
        # dans score_liquidity().

        return (
            _clamp_signed(
                score,
                -self.WEIGHTS["m15_smc"],
                self.WEIGHTS["m15_smc"],
            ),
            reasons,
        )

    # ========================================================
    # M5 CONFIRMATION
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
        # BIAIS M5
        # ----------------------------------------------------

        bias = _normalize_direction(
            m5_analysis.get(
                "bias",
                NEUTRAL,
            )
        )

        if _same_direction(
            bias,
            target,
        ):

            score += 7

            reasons.append(
                "Biais M5 confirmé."
            )

        elif bias != NEUTRAL.lower():

            score -= 7

            reasons.append(
                "Biais M5 opposé."
            )

        latest = _safe_dict(
            m5_analysis.get(
                "latest",
                {},
            )
        )

        # ----------------------------------------------------
        # BOS M5
        # ----------------------------------------------------

        bos = _safe_dict(
            latest.get(
                "bos"
            )
        )

        if bos:

            bos_direction = _normalize_direction(
                bos.get(
                    "direction"
                )
            )

            if _same_direction(
                bos_direction,
                target,
            ):

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

        choch = _safe_dict(
            latest.get(
                "choch"
            )
        )

        if choch:

            choch_direction = _normalize_direction(
                choch.get(
                    "direction"
                )
            )

            if _same_direction(
                choch_direction,
                target,
            ):

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
                -self.WEIGHTS["m5_confirmation"],
                self.WEIGHTS["m5_confirmation"],
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
        ).strip().lower()

        # ----------------------------------------------------
        # BUY = DISCOUNT
        # SELL = PREMIUM
        # ----------------------------------------------------

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

        # ----------------------------------------------------
        # RETRACEMENT
        # ----------------------------------------------------

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

            # Accepte aussi les variantes numériques.
            try:
                level_normalized = f"{float(level):.3f}"
            except (
                TypeError,
                ValueError,
            ):
                level_normalized = level

            if level_normalized in {
                "0.618",
                "0.705",
                "0.786",
            }:

                score += 4

                reasons.append(
                    f"Retracement Fibonacci {level_normalized} favorable."
                )

        return (
            _clamp_signed(
                score,
                -self.WEIGHTS["fibonacci"],
                self.WEIGHTS["fibonacci"],
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
        ).strip().lower()

        rsi = _safe_float(
            indicators.get(
                "rsi"
            )
        )

        # ----------------------------------------------------
        # EMA
        # ----------------------------------------------------

        if _same_direction(
            ema_context,
            target,
        ):

            score += 5

            reasons.append(
                "EMA alignées."
            )

        elif ema_context != NEUTRAL.lower():

            score -= 5

            reasons.append(
                "EMA opposées."
            )

        # ----------------------------------------------------
        # RSI
        # ----------------------------------------------------

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

        # ----------------------------------------------------
        # RSI EXTRÊME
        # ----------------------------------------------------

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
                -self.WEIGHTS["indicators"],
                self.WEIGHTS["indicators"],
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

        latest = _safe_dict(
            structure_analysis.get(
                "latest",
                {},
            )
        )

        latest_sweep = _safe_dict(
            latest.get(
                "liquidity_sweep"
            )
        )

        if not latest_sweep:
            return 0, []

        sweep_direction = _normalize_direction(
            latest_sweep.get(
                "direction",
                "",
            )
        )

        # ----------------------------------------------------
        # SWEEP ALIGNÉ
        # ----------------------------------------------------

        if _same_direction(
            sweep_direction,
            target,
        ):

            return (
                self.WEIGHTS["liquidity"],
                [
                    "Sweep de liquidité confirmé."
                ],
            )

        # ----------------------------------------------------
        # SWEEP OPPOSÉ
        # ----------------------------------------------------

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

        # ----------------------------------------------------
        # DIRECTION OBLIGATOIRE
        # ----------------------------------------------------

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

            block_reasons = (
                block_reasons
                if isinstance(
                    block_reasons,
                    list,
                )
                else []
            )

            if normalized_direction == BULLISH:

                buy_score += points

            else:

                sell_score += points

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

        # ====================================================
        # H4
        # ====================================================

        points, reason = self.score_h4_trend(
            h4_bias,
            normalized_direction,
        )

        add_score(
            points,
            [reason] if reason else [],
        )

        # ====================================================
        # H1
        # ====================================================

        points, h1_reasons = self.score_h1_structure(
            h1_analysis or {},
            normalized_direction,
        )

        add_score(
            points,
            h1_reasons,
        )

        # ====================================================
        # M15
        # ====================================================

        points, m15_reasons = self.score_m15_smc(
            m15_analysis or {},
            normalized_direction,
        )

        add_score(
            points,
            m15_reasons,
        )

        # ====================================================
        # M5
        # ====================================================

        points, m5_reasons = self.score_m5_confirmation(
            m5_analysis or {},
            normalized_direction,
        )

        add_score(
            points,
            m5_reasons,
        )

        # ====================================================
        # FIBONACCI
        # ====================================================

        points, fibonacci_reasons = self.score_fibonacci(
            fibonacci_analysis or {},
            normalized_direction,
        )

        add_score(
            points,
            fibonacci_reasons,
        )

        # ====================================================
        # INDICATEURS
        # ====================================================

        points, indicator_reasons = self.score_indicators(
            indicators or {},
            normalized_direction,
        )

        add_score(
            points,
            indicator_reasons,
        )

        # ====================================================
        # LIQUIDITÉ
        # ====================================================

        points, liquidity_reasons = self.score_liquidity(
            m15_analysis or {},
            normalized_direction,
        )

        add_score(
            points,
            liquidity_reasons,
        )

        # ====================================================
        # SCORE FINAL
        # ====================================================

        if normalized_direction == BULLISH:

            final_score = buy_score

        else:

            final_score = sell_score

        # Toujours 0-100.
        final_score = _clamp(
            final_score
        )

        buy_score = _clamp(
            buy_score
        )

        sell_score = _clamp(
            sell_score
        )

        # ====================================================
        # QUALITÉ
        # ====================================================

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
    """
    Interface publique utilisée par analyse.py.
    """

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
# TESTS
# ============================================================

def _run_internal_test() -> None:

    print("=" * 60)
    print("VISION TRADE AI V2")
    print("TEST SCORE.PY")
    print("=" * 60)

    # --------------------------------------------------------
    # NORMALISATION
    # --------------------------------------------------------

    assert _normalize_direction("BUY") == BULLISH
    assert _normalize_direction("buy") == BULLISH
    assert _normalize_direction("bullish") == BULLISH
    assert _normalize_direction("LONG") == BULLISH

    assert _normalize_direction("SELL") == BEARISH
    assert _normalize_direction("sell") == BEARISH
    assert _normalize_direction("bearish") == BEARISH
    assert _normalize_direction("SHORT") == BEARISH

    assert _normalize_direction("xxx") == NEUTRAL.lower()

    # --------------------------------------------------------
    # COMPARAISON DIRECTIONS
    # --------------------------------------------------------

    assert _same_direction("BUY", "bullish") is True
    assert _same_direction("bullish", "BUY") is True

    assert _same_direction("SELL", "bearish") is True
    assert _same_direction("bearish", "SELL") is True

    assert _same_direction("BUY", "SELL") is False

    # --------------------------------------------------------
    # H4
    # --------------------------------------------------------

    engine = ScoreEngine()

    assert engine.score_h4_trend(
        "bullish",
        "BUY",
    )[0] == 15

    assert engine.score_h4_trend(
        "bearish",
        "SELL",
    )[0] == 15

    assert engine.score_h4_trend(
        "bearish",
        "BUY",
    )[0] == -15

    # Test très important :
    # BUY et bullish doivent être identiques.

    assert engine.score_h4_trend(
        "BUY",
        "bullish",
    )[0] == 15

    assert engine.score_h4_trend(
        "SELL",
        "bearish",
    )[0] == 15

    # --------------------------------------------------------
    # H1 BUY
    # --------------------------------------------------------

    h1 = {
        "bias": "bullish",
        "latest": {
            "bos": {
                "direction": "bullish",
                "break_type": "BOS",
            }
        },
    }

    assert engine.score_h1_structure(
        h1,
        "BUY",
    )[0] == 20

    # --------------------------------------------------------
    # M15 BUY
    # --------------------------------------------------------

    m15 = {
        "bias": "bullish",
        "latest": {
            "order_block": {
                "direction": "bullish",
            },
            "fvg": {
                "direction": "bullish",
            },
            "liquidity_sweep": {
                "direction": "bullish",
            },
        },
    }

    assert engine.score_m15_smc(
        m15,
        "BUY",
    )[0] == 17

    assert engine.score_liquidity(
        m15,
        "BUY",
    )[0] == 10

    # --------------------------------------------------------
    # M5 BUY
    # --------------------------------------------------------

    m5 = {
        "bias": "bullish",
        "latest": {
            "bos": {
                "direction": "bullish",
            }
        },
    }

    assert engine.score_m5_confirmation(
        m5,
        "BUY",
    )[0] == 12

    # --------------------------------------------------------
    # FIBONACCI BUY
    # --------------------------------------------------------

    fibonacci = {
        "position": {
            "zone": "discount",
        },
        "closest_level": {
            "level": "0.705",
        },
    }

    assert engine.score_fibonacci(
        fibonacci,
        "BUY",
    )[0] == 10

    # --------------------------------------------------------
    # INDICATEURS BUY
    # --------------------------------------------------------

    indicators = {
        "ema_context": "bullish",
        "rsi_context": "bullish_bias",
        "rsi": 56,
    }

    assert engine.score_indicators(
        indicators,
        "BUY",
    )[0] == 8

    # --------------------------------------------------------
    # SCORE BUY COMPLET
    # --------------------------------------------------------

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
    assert result["buy_score"] == 92
    assert result["final_score"] == 92
    assert result["quality"] == "A+"
    assert result["passes_threshold"] is True
    assert result["threshold"] == 50

    print("BUY SCORE :", result["buy_score"])
    print("BUY FINAL :", result["final_score"])
    print("BUY QUALITY :", result["quality"])

    # --------------------------------------------------------
    # SCORE SELL COMPLET
    # --------------------------------------------------------

    sell_h1 = {
        "bias": "bearish",
        "latest": {
            "bos": {
                "direction": "bearish",
            }
        },
    }

    sell_m15 = {
        "bias": "bearish",
        "latest": {
            "order_block": {
                "direction": "bearish",
            },
            "fvg": {
                "direction": "bearish",
            },
            "liquidity_sweep": {
                "direction": "bearish",
            },
        },
    }

    sell_m5 = {
        "bias": "bearish",
        "latest": {
            "bos": {
                "direction": "bearish",
            }
        },
    }

    sell_fibonacci = {
        "position": {
            "zone": "premium",
        },
        "closest_level": {
            "level": "0.705",
        },
    }

    sell_indicators = {
        "ema_context": "bearish",
        "rsi_context": "bearish_bias",
        "rsi": 44,
    }

    sell_result = calculer_score(
        direction="SELL",
        h4_bias="bearish",
        h1_analysis=sell_h1,
        m15_analysis=sell_m15,
        m5_analysis=sell_m5,
        fibonacci_analysis=sell_fibonacci,
        indicators=sell_indicators,
    )

    assert sell_result["direction"] == "SELL"
    assert sell_result["sell_score"] == 92
    assert sell_result["final_score"] == 92
    assert sell_result["quality"] == "A+"
    assert sell_result["passes_threshold"] is True

    print("SELL SCORE :", sell_result["sell_score"])
    print("SELL FINAL :", sell_result["final_score"])
    print("SELL QUALITY :", sell_result["quality"])

    # --------------------------------------------------------
    # CONTRADICTION
    # --------------------------------------------------------

    contradiction_result = calculer_score(
        direction="BUY",
        h4_bias="bearish",
        h1_analysis={
            "bias": "bearish",
        },
        m15_analysis={
            "bias": "bearish",
        },
        m5_analysis={
            "bias": "bearish",
        },
        fibonacci_analysis={
            "position": {
                "zone": "premium",
            }
        },
        indicators={
            "ema_context": "bearish",
            "rsi_context": "overbought",
            "rsi": 85,
        },
    )

    assert contradiction_result["direction"] == "BUY"
    assert contradiction_result["final_score"] < 50
    assert contradiction_result["passes_threshold"] is False
    assert contradiction_result["contradictions"] > 0

    print("CONTRADICTION TEST : OK")

    # --------------------------------------------------------
    # DONNÉES VIDES
    # --------------------------------------------------------

    empty_result = calculer_score(
        direction="SELL",
    )

    assert empty_result["direction"] == "SELL"
    assert empty_result["final_score"] == 0
    assert empty_result["passes_threshold"] is False
    assert empty_result["quality"] == "REJECT"

    print("EMPTY DATA TEST : OK")

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

    print("NEUTRAL TEST : OK")

    print("=" * 60)
    print("✅ TOUS LES TESTS SCORE.PY SONT RÉUSSIS")
    print("=" * 60)


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

    _run_internal_test()