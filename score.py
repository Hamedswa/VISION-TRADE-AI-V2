"""
Vision Trade AI V2
score.py

Moteur de scoring déterministe.

Responsabilités :
- analyser les confluences techniques ;
- attribuer des points BUY / SELL ;
- pénaliser les contradictions ;
- calculer un score final ;
- déterminer la qualité du setup.

IMPORTANT :
- aucune IA ;
- aucun appel API ;
- aucun calcul de SL/TP ;
- aucun signal Telegram.

Le score est purement mathématique et reproductible.
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

DEFAULT_SIGNAL_THRESHOLD = 80


# ============================================================
# NORMALISATION DES DIRECTIONS
# ============================================================

def _normalize_direction(direction: Any) -> str:
    """
    Convertit toutes les représentations possibles
    vers une direction interne standardisée.

    BUY / bullish / long  -> bullish
    SELL / bearish / short -> bearish
    NEUTRAL -> neutral
    """

    value = str(direction).lower().strip()

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

    return mapping.get(value, value)


def _direction_label(direction: str) -> str:
    """
    Convertit une direction interne vers BUY / SELL.
    """

    normalized = _normalize_direction(direction)

    if normalized == BULLISH:
        return BUY

    if normalized == BEARISH:
        return SELL

    return NEUTRAL


# ============================================================
# MODÈLE DE SCORE
# ============================================================

@dataclass
class ScoreResult:
    """
    Résultat complet du moteur de scoring.
    """

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
    Force une valeur dans une plage.
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
    Convertit proprement une valeur numérique.
    """

    if value is None:
        return None

    try:
        return float(value)

    except (
        TypeError,
        ValueError,
    ):
        return None


# ============================================================
# SCORE ENGINE
# ============================================================

class ScoreEngine:
    """
    Moteur déterministe de scoring.

    Pondération maximale :

        H4 tendance             15
        H1 structure            20
        M15 zones SMC           20
        M5 confirmation         15
        Fibonacci               10
        Indicateurs             10
        Liquidité / sweep       10
        ---------------------------
        TOTAL                   100
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

        if not h4_bias:
            return 0, None

        bias = _normalize_direction(h4_bias)
        target = _normalize_direction(direction)

        if bias == target:
            return (
                self.WEIGHTS["h4_trend"],
                "Tendance H4 alignée.",
            )

        if bias == NEUTRAL.lower():
            return 0, None

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
    ) -> tuple[int, Optional[str]]:

        if not h1_analysis:
            return 0, None

        target = _normalize_direction(direction)

        bias = _normalize_direction(
            h1_analysis.get(
                "bias",
                NEUTRAL,
            )
        )

        score = 0
        reasons = []

        # ----------------------------------------------------
        # BIAIS H1
        # ----------------------------------------------------

        if bias == target:

            score += 10

            reasons.append(
                "Biais H1 aligné."
            )

        elif (
            bias != NEUTRAL.lower()
            and bias != target
        ):

            score -= 10

            reasons.append(
                "Biais H1 opposé."
            )

        # ----------------------------------------------------
        # DERNIER BOS
        # ----------------------------------------------------

        latest = h1_analysis.get(
            "latest",
            {},
        )

        if not isinstance(latest, dict):
            latest = {}

        bos = latest.get("bos")

        if bos:

            bos_direction = _normalize_direction(
                bos.get(
                    "direction",
                    "",
                )
            )

            if bos_direction == target:

                score += 10

                reasons.append(
                    "BOS H1 aligné."
                )

            elif (
                bos_direction != NEUTRAL.lower()
            ):

                score -= 10

                reasons.append(
                    "BOS H1 opposé."
                )

        # ----------------------------------------------------
        # CHoCH
        # ----------------------------------------------------

        choch = latest.get("choch")

        if choch:

            choch_direction = _normalize_direction(
                choch.get(
                    "direction",
                    "",
                )
            )

            if choch_direction == target:

                score += 5

                reasons.append(
                    "CHoCH H1 aligné."
                )

            elif (
                choch_direction != NEUTRAL.lower()
            ):

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
            reasons[0] if reasons else None,
        )

    # ========================================================
    # M15 SMC
    # ========================================================

    def score_m15_smc(
        self,
        m15_analysis: Dict[str, Any],
        direction: str,
    ) -> tuple[int, list[str]]:

        if not m15_analysis:
            return 0, []

        score = 0
        reasons = []

        target = _normalize_direction(direction)

        latest = m15_analysis.get(
            "latest",
            {},
        )

        if not isinstance(latest, dict):
            latest = {}

        # ----------------------------------------------------
        # ORDER BLOCK
        # ----------------------------------------------------

        latest_ob = latest.get(
            "order_block"
        )

        if latest_ob:

            ob_direction = _normalize_direction(
                latest_ob.get(
                    "direction",
                    "",
                )
            )

            if ob_direction == target:

                score += 7

                reasons.append(
                    "Order Block aligné."
                )

            elif (
                ob_direction != NEUTRAL.lower()
            ):

                score -= 5

                reasons.append(
                    "Order Block opposé."
                )

        # ----------------------------------------------------
        # FVG
        # ----------------------------------------------------

        latest_fvg = latest.get(
            "fvg"
        )

        if latest_fvg:

            fvg_direction = _normalize_direction(
                latest_fvg.get(
                    "direction",
                    "",
                )
            )

            if fvg_direction == target:

                score += 6

                reasons.append(
                    "FVG aligné."
                )

            elif (
                fvg_direction != NEUTRAL.lower()
            ):

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

        if bias == target:

            score += 4

            reasons.append(
                "Structure M15 alignée."
            )

        elif (
            bias != NEUTRAL.lower()
            and bias != target
        ):

            score -= 4

            reasons.append(
                "Structure M15 opposée."
            )

        # ----------------------------------------------------
        # SWEEP
        # ----------------------------------------------------

        latest_sweep = latest.get(
            "liquidity_sweep"
        )

        if latest_sweep:

            sweep_direction = _normalize_direction(
                latest_sweep.get(
                    "direction",
                    "",
                )
            )

            if sweep_direction == target:

                score += 3

                reasons.append(
                    "Liquidity sweep aligné."
                )

            elif (
                sweep_direction != NEUTRAL.lower()
            ):

                score -= 3

                reasons.append(
                    "Liquidity sweep opposé."
                )

        return (
            _clamp_signed(
                score,
                -self.WEIGHTS["m15_smc"],
                self.WEIGHTS["m15_smc"],
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

        if not m5_analysis:
            return 0, []

        score = 0
        reasons = []

        target = _normalize_direction(direction)

        # ----------------------------------------------------
        # BIAIS M5
        # ----------------------------------------------------

        bias = _normalize_direction(
            m5_analysis.get(
                "bias",
                NEUTRAL,
            )
        )

        if bias == target:

            score += 7

            reasons.append(
                "Biais M5 confirmé."
            )

        elif (
            bias != NEUTRAL.lower()
            and bias != target
        ):

            score -= 7

            reasons.append(
                "M5 opposé."
            )

        # ----------------------------------------------------
        # DERNIER BOS / CHoCH
        # ----------------------------------------------------

        latest = m5_analysis.get(
            "latest",
            {},
        )

        if not isinstance(latest, dict):
            latest = {}

        bos = latest.get("bos")

        if bos:

            bos_direction = _normalize_direction(
                bos.get(
                    "direction",
                    "",
                )
            )

            if bos_direction == target:

                score += 5

                reasons.append(
                    "BOS M5 confirmé."
                )

            elif (
                bos_direction != NEUTRAL.lower()
            ):

                score -= 5

                reasons.append(
                    "BOS M5 opposé."
                )

        choch = latest.get("choch")

        if choch:

            choch_direction = _normalize_direction(
                choch.get(
                    "direction",
                    "",
                )
            )

            if choch_direction == target:

                score += 3

                reasons.append(
                    "CHoCH M5 confirmé."
                )

            elif (
                choch_direction != NEUTRAL.lower()
            ):

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
    ) -> tuple[int, Optional[str]]:

        if not fibonacci_analysis:
            return 0, None

        score = 0

        target = _normalize_direction(direction)

        position = fibonacci_analysis.get(
            "position",
            {},
        )

        if not isinstance(position, dict):
            position = {}

        zone = str(
            position.get(
                "zone",
                "",
            )
        ).lower().strip()

        # ----------------------------------------------------
        # BUY = DISCOUNT
        # SELL = PREMIUM
        # ----------------------------------------------------

        if target == BULLISH:

            if zone == "discount":
                score += 6

            elif zone == "premium":
                score -= 6

        elif target == BEARISH:

            if zone == "premium":
                score += 6

            elif zone == "discount":
                score -= 6

        # ----------------------------------------------------
        # RETRACEMENT
        # ----------------------------------------------------

        closest = fibonacci_analysis.get(
            "closest_level"
        )

        if closest:

            level = str(
                closest.get("level")
            )

            if level in {
                "0.618",
                "0.705",
                "0.786",
            }:

                score += 4

        reason = (
            f"Prix en zone {zone}."
            if zone
            else None
        )

        return (
            _clamp_signed(
                score,
                -self.WEIGHTS["fibonacci"],
                self.WEIGHTS["fibonacci"],
            ),
            reason,
        )

    # ========================================================
    # INDICATEURS
    # ========================================================

    def score_indicators(
        self,
        indicators: Dict[str, Any],
        direction: str,
    ) -> tuple[int, list[str]]:

        if not indicators:
            return 0, []

        score = 0
        reasons = []

        target = _normalize_direction(direction)

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
        ).lower().strip()

        rsi = _safe_float(
            indicators.get("rsi")
        )

        # ----------------------------------------------------
        # EMA
        # ----------------------------------------------------

        if ema_context == target:

            score += 5

            reasons.append(
                "EMA alignées."
            )

        elif (
            ema_context
            and ema_context != NEUTRAL.lower()
        ):

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

        if not structure_analysis:
            return 0, []

        score = 0
        reasons = []

        target = _normalize_direction(direction)

        latest = structure_analysis.get(
            "latest",
            {},
        )

        if not isinstance(latest, dict):
            latest = {}

        latest_sweep = latest.get(
            "liquidity_sweep"
        )

        if not latest_sweep:
            return 0, []

        sweep_direction = _normalize_direction(
            latest_sweep.get(
                "direction",
                "",
            )
        )

        if sweep_direction == target:

            score += 10

            reasons.append(
                "Sweep de liquidité confirmé."
            )

        elif (
            sweep_direction != NEUTRAL.lower()
        ):

            score -= 8

            reasons.append(
                "Sweep de liquidité opposé."
            )

        return (
            _clamp_signed(
                score,
                -self.WEIGHTS["liquidity"],
                self.WEIGHTS["liquidity"],
            ),
            reasons,
        )

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

        reasons = []
        warnings = []

        confirmations = 0
        contradictions = 0

        # ----------------------------------------------------
        # AJOUT SCORE
        # ----------------------------------------------------

        def add_score(
            points: int,
            reason: Optional[str] = None,
        ) -> None:

            nonlocal buy_score
            nonlocal sell_score
            nonlocal confirmations
            nonlocal contradictions

            if normalized_direction == BULLISH:
                buy_score += points
            else:
                sell_score += points

            if points > 0:
                confirmations += 1

                if reason:
                    reasons.append(reason)

            elif points < 0:
                contradictions += 1

                if reason:
                    warnings.append(reason)

        # ----------------------------------------------------
        # H4
        # ----------------------------------------------------

        points, reason = self.score_h4_trend(
            h4_bias,
            normalized_direction,
        )

        add_score(
            points,
            reason,
        )

        # ----------------------------------------------------
        # H1
        # ----------------------------------------------------

        points, reason = self.score_h1_structure(
            h1_analysis or {},
            normalized_direction,
        )

        add_score(
            points,
            reason,
        )

        # ----------------------------------------------------
        # M15
        # ----------------------------------------------------

        points, m15_reasons = self.score_m15_smc(
            m15_analysis or {},
            normalized_direction,
        )

        add_score(points)

        if points > 0:
            reasons.extend(m15_reasons)

        elif points < 0:
            warnings.extend(m15_reasons)

        # ----------------------------------------------------
        # M5
        # ----------------------------------------------------

        points, m5_reasons = self.score_m5_confirmation(
            m5_analysis or {},
            normalized_direction,
        )

        add_score(points)

        if points > 0:
            reasons.extend(m5_reasons)

        elif points < 0:
            warnings.extend(m5_reasons)

        # ----------------------------------------------------
        # FIBONACCI
        # ----------------------------------------------------

        points, reason = self.score_fibonacci(
            fibonacci_analysis or {},
            normalized_direction,
        )

        add_score(
            points,
            reason,
        )

        # ----------------------------------------------------
        # INDICATEURS
        # ----------------------------------------------------

        points, indicator_reasons = self.score_indicators(
            indicators or {},
            normalized_direction,
        )

        add_score(points)

        if points > 0:
            reasons.extend(indicator_reasons)

        elif points < 0:
            warnings.extend(indicator_reasons)

        # ----------------------------------------------------
        # LIQUIDITÉ
        # ----------------------------------------------------

        points, liquidity_reasons = self.score_liquidity(
            m15_analysis or {},
            normalized_direction,
        )

        add_score(points)

        if points > 0:
            reasons.extend(liquidity_reasons)

        elif points < 0:
            warnings.extend(liquidity_reasons)

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

        # ----------------------------------------------------
        # QUALITÉ
        # ----------------------------------------------------

        quality = self.determine_quality(
            final_score
        )

        return ScoreResult(
            buy_score=_clamp(
                buy_score
            ),
            sell_score=_clamp(
                sell_score
            ),
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
        """
        Classe la qualité du setup.
        """

        if score >= 90:
            return "A+"

        if score >= 85:
            return "A"

        if score >= 80:
            return "B"

        if score >= 70:
            return "C"

        if score >= 60:
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
    Interface publique du moteur de score.
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
# TEST INTERNE
# ============================================================

def _run_internal_test() -> None:
    """
    Test complet du moteur de scoring.
    """

    # --------------------------------------------------------
    # TEST NORMALISATION
    # --------------------------------------------------------

    assert _normalize_direction("BUY") == BULLISH
    assert _normalize_direction("buy") == BULLISH
    assert _normalize_direction("bullish") == BULLISH

    assert _normalize_direction("SELL") == BEARISH
    assert _normalize_direction("sell") == BEARISH
    assert _normalize_direction("bearish") == BEARISH

    # --------------------------------------------------------
    # H4
    # --------------------------------------------------------

    engine = ScoreEngine()

    h4_buy = engine.score_h4_trend(
        "bullish",
        "BUY",
    )

    assert h4_buy[0] == 15

    h4_sell = engine.score_h4_trend(
        "bearish",
        "SELL",
    )

    assert h4_sell[0] == 15

    h4_wrong = engine.score_h4_trend(
        "bearish",
        "BUY",
    )

    assert h4_wrong[0] == -15

    # --------------------------------------------------------
    # H1
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

    # --------------------------------------------------------
    # M15
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

    # --------------------------------------------------------
    # M5
    # --------------------------------------------------------

    m5 = {
        "bias": "bullish",
        "latest": {
            "bos": {
                "direction": "bullish",
            }
        },
    }

    # --------------------------------------------------------
    # FIBONACCI
    # --------------------------------------------------------

    fibonacci = {
        "position": {
            "zone": "discount",
        },
        "closest_level": {
            "level": "0.705",
        },
    }

    # --------------------------------------------------------
    # INDICATEURS
    # --------------------------------------------------------

    indicators = {
        "ema_context": "bullish",
        "rsi_context": "bullish_bias",
        "rsi": 56,
    }

    # --------------------------------------------------------
    # CALCUL BUY
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

    # --------------------------------------------------------
    # VÉRIFICATIONS
    # --------------------------------------------------------

    assert result["direction"] == "BUY"

    assert result["buy_score"] > 0

    assert result["final_score"] > 0

    assert result["confirmations"] > 0

    assert result["quality"] != "REJECT"

    # Le setup synthétique doit être suffisamment fort.
    assert result["final_score"] >= 80

    logger.info(
        "Test score BUY réussi : %s",
        result,
    )

    print(
        "BUY SCORE:",
        result["buy_score"],
    )

    print(
        "FINAL SCORE:",
        result["final_score"],
    )

    print(
        "QUALITY:",
        result["quality"],
    )

    print(
        "CONFIRMATIONS:",
        result["confirmations"],
    )

    print(
        "CONTRADICTIONS:",
        result["contradictions"],
    )

    # --------------------------------------------------------
    # TEST SELL
    # --------------------------------------------------------

    sell_h1 = {
        "bias": "bearish",
        "latest": {
            "bos": {
                "direction": "bearish",
                "break_type": "BOS",
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

    assert sell_result["sell_score"] > 0

    assert sell_result["final_score"] > 0

    assert sell_result["final_score"] >= 80

    logger.info(
        "Test score SELL réussi : %s",
        sell_result,
    )

    print(
        "SELL SCORE:",
        sell_result["sell_score"],
    )

    print(
        "SELL FINAL SCORE:",
        sell_result["final_score"],
    )

    print(
        "SELL QUALITY:",
        sell_result["quality"],
    )

    print(
        "SELL CONFIRMATIONS:",
        sell_result["confirmations"],
    )

    print(
        "SELL CONTRADICTIONS:",
        sell_result["contradictions"],
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
    print("VISION TRADE AI V2 - TEST SCORE")
    print("=" * 60)

    try:

        _run_internal_test()

        print()
        print("✅ SCORE : OK")
        print(
            "Moteur de scoring déterministe opérationnel."
        )

    except Exception as exc:

        print()
        print("❌ TEST SCORE ÉCHOUÉ")
        print(
            f"Erreur : {type(exc).__name__}: {exc}"
        )