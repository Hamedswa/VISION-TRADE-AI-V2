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
- aucun calcul SL/TP ;
- aucun signal Telegram.

Le moteur accepte :
    BUY / SELL
et convertit automatiquement vers :
    bullish / bearish
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
# MODÈLE
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
    Limite une valeur entre minimum et maximum.
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

    if value is None:
        return None

    try:
        return float(value)

    except (TypeError, ValueError):
        return None


def _normalize_direction(
    direction: str,
) -> str:
    """
    Convertit :

        BUY  -> bullish
        SELL -> bearish

    Les analyses techniques utilisent bullish/bearish.
    """

    value = str(
        direction
    ).lower().strip()

    if value in {
        "buy",
        "bullish",
        "long",
    }:
        return BULLISH

    if value in {
        "sell",
        "bearish",
        "short",
    }:
        return BEARISH

    if value in {
        "neutral",
        "none",
    }:
        return NEUTRAL

    raise ValueError(
        "Direction inconnue. Utiliser BUY, SELL, bullish ou bearish."
    )


# ============================================================
# SCORE ENGINE
# ============================================================

class ScoreEngine:
    """
    Moteur déterministe.

    Pondération :

        H4 tendance       15
        H1 structure      20
        M15 SMC           20
        M5 confirmation   15
        Fibonacci         10
        Indicateurs       10
        Liquidité         10
        --------------------
        TOTAL            100
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

        target = _normalize_direction(direction)

        bias = str(
            h4_bias or NEUTRAL
        ).lower().strip()

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
    # H1
    # ========================================================

    def score_h1_structure(
        self,
        h1_analysis: Dict[str, Any],
        direction: str,
    ) -> tuple[int, Optional[str]]:

        if not h1_analysis:
            return 0, None

        target = _normalize_direction(direction)

        bias = str(
            h1_analysis.get(
                "bias",
                NEUTRAL,
            )
        ).lower().strip()

        score = 0
        reason = None

        if bias == target:

            score += 10
            reason = "Biais H1 aligné."

        elif (
            bias != NEUTRAL.lower()
            and bias != target
        ):

            score -= 10
            reason = "Biais H1 opposé."

        latest = h1_analysis.get(
            "latest",
            {},
        )

        if not isinstance(latest, dict):
            latest = {}

        bos = latest.get("bos")
        choch = latest.get("choch")

        if bos:

            bos_direction = str(
                bos.get("direction", "")
            ).lower().strip()

            if bos_direction == target:

                score += 10

            else:

                score -= 10

        elif choch:

            choch_direction = str(
                choch.get("direction", "")
            ).lower().strip()

            if choch_direction == target:

                score += 5

            else:

                score -= 5

        return (
            max(
                -self.WEIGHTS["h1_structure"],
                min(
                    self.WEIGHTS["h1_structure"],
                    score,
                ),
            ),
            reason,
        )

    # ========================================================
    # M15
    # ========================================================

    def score_m15_smc(
        self,
        m15_analysis: Dict[str, Any],
        direction: str,
    ) -> tuple[int, list[str]]:

        if not m15_analysis:
            return 0, []

        target = _normalize_direction(direction)

        score = 0
        reasons = []

        latest = m15_analysis.get(
            "latest",
            {},
        )

        if not isinstance(latest, dict):
            latest = {}

        # ----------------------------------------------------
        # ORDER BLOCK
        # ----------------------------------------------------

        ob = latest.get(
            "order_block"
        )

        if ob:

            ob_direction = str(
                ob.get("direction", "")
            ).lower().strip()

            if ob_direction == target:

                score += 7
                reasons.append(
                    "Order Block aligné."
                )

            else:

                score -= 5
                reasons.append(
                    "Order Block opposé."
                )

        # ----------------------------------------------------
        # FVG
        # ----------------------------------------------------

        fvg = latest.get(
            "fvg"
        )

        if fvg:

            fvg_direction = str(
                fvg.get("direction", "")
            ).lower().strip()

            if fvg_direction == target:

                score += 6
                reasons.append(
                    "FVG aligné."
                )

            else:

                score -= 4
                reasons.append(
                    "FVG opposé."
                )

        # ----------------------------------------------------
        # BIAIS M15
        # ----------------------------------------------------

        bias = str(
            m15_analysis.get(
                "bias",
                NEUTRAL,
            )
        ).lower().strip()

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

        sweep = latest.get(
            "liquidity_sweep"
        )

        if sweep:

            sweep_direction = str(
                sweep.get("direction", "")
            ).lower().strip()

            if sweep_direction == target:

                score += 3
                reasons.append(
                    "Liquidity sweep aligné."
                )

            else:

                score -= 3
                reasons.append(
                    "Liquidity sweep opposé."
                )

        return (
            max(
                -self.WEIGHTS["m15_smc"],
                min(
                    self.WEIGHTS["m15_smc"],
                    score,
                ),
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

        target = _normalize_direction(direction)

        score = 0
        reasons = []

        bias = str(
            m5_analysis.get(
                "bias",
                NEUTRAL,
            )
        ).lower().strip()

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

        latest = m5_analysis.get(
            "latest",
            {},
        )

        if not isinstance(latest, dict):
            latest = {}

        # ----------------------------------------------------
        # BOS
        # ----------------------------------------------------

        bos = latest.get(
            "bos"
        )

        if bos:

            bos_direction = str(
                bos.get("direction", "")
            ).lower().strip()

            if bos_direction == target:

                score += 5
                reasons.append(
                    "BOS M5 confirmé."
                )

            else:

                score -= 5
                reasons.append(
                    "BOS M5 opposé."
                )

        # ----------------------------------------------------
        # CHOCH
        # ----------------------------------------------------

        choch = latest.get(
            "choch"
        )

        if choch:

            choch_direction = str(
                choch.get("direction", "")
            ).lower().strip()

            if choch_direction == target:

                score += 3
                reasons.append(
                    "CHoCH M5 confirmé."
                )

            else:

                score -= 3
                reasons.append(
                    "CHoCH M5 opposé."
                )

        return (
            max(
                -self.WEIGHTS["m5_confirmation"],
                min(
                    self.WEIGHTS["m5_confirmation"],
                    score,
                ),
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

        target = _normalize_direction(direction)

        score = 0

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

        closest = fibonacci_analysis.get(
            "closest_level"
        )

        if closest:

            level = str(
                closest.get("level", "")
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
            max(
                -self.WEIGHTS["fibonacci"],
                min(
                    self.WEIGHTS["fibonacci"],
                    score,
                ),
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

        target = _normalize_direction(direction)

        score = 0
        reasons = []

        ema_context = str(
            indicators.get(
                "ema_context",
                "",
            )
        ).lower().strip()

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
            max(
                -self.WEIGHTS["indicators"],
                min(
                    self.WEIGHTS["indicators"],
                    score,
                ),
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

        target = _normalize_direction(direction)

        latest = structure_analysis.get(
            "latest",
            {},
        )

        if not isinstance(latest, dict):
            latest = {}

        sweep = latest.get(
            "liquidity_sweep"
        )

        if not sweep:
            return 0, []

        sweep_direction = str(
            sweep.get("direction", "")
        ).lower().strip()

        if sweep_direction == target:

            return (
                self.WEIGHTS["liquidity"],
                ["Sweep de liquidité confirmé."],
            )

        return (
            -self.WEIGHTS["liquidity"],
            ["Sweep de liquidité opposé."],
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

        direction = str(
            direction
        ).upper().strip()

        if direction not in {
            BUY,
            SELL,
        }:

            raise ValueError(
                "direction doit être BUY ou SELL."
            )

        buy_score = 0
        sell_score = 0

        reasons = []
        warnings = []

        confirmations = 0
        contradictions = 0

        def add_score(
            points: int,
            reason: Optional[str] = None,
        ) -> None:

            nonlocal buy_score
            nonlocal sell_score
            nonlocal confirmations
            nonlocal contradictions

            if direction == BUY:

                buy_score += points

            else:

                sell_score += points

            if points > 0:
                confirmations += 1

            elif points < 0:
                contradictions += 1

            if reason:

                if points > 0:
                    reasons.append(reason)

                elif points < 0:
                    warnings.append(reason)

        # ----------------------------------------------------
        # H4
        # ----------------------------------------------------

        points, reason = self.score_h4_trend(
            h4_bias,
            direction,
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
            direction,
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
            direction,
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
            direction,
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
            direction,
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
            direction,
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
            direction,
        )

        add_score(points)

        if points > 0:
            reasons.extend(liquidity_reasons)

        elif points < 0:
            warnings.extend(liquidity_reasons)

        # ----------------------------------------------------
        # SCORE FINAL
        # ----------------------------------------------------

        if direction == BUY:
            final_score = buy_score
        else:
            final_score = sell_score

        # Important :
        # le score interne peut être négatif.
        # Le score public est limité à 0-100.

        final_score = _clamp(
            final_score,
            0,
            MAX_SCORE,
        )

        quality = self.determine_quality(
            final_score
        )

        return ScoreResult(
            buy_score=_clamp(
                buy_score,
                0,
                MAX_SCORE,
            ),
            sell_score=_clamp(
                sell_score,
                0,
                MAX_SCORE,
            ),
            final_score=final_score,
            direction=direction,
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

    h1 = {
        "bias": "bullish",
        "latest": {
            "bos": {
                "direction": "bullish",
                "break_type": "BOS",
            }
        },
    }

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

    m5 = {
        "bias": "bullish",
        "latest": {
            "bos": {
                "direction": "bullish",
            }
        },
    }

    fibonacci = {
        "position": {
            "zone": "discount",
        },
        "closest_level": {
            "level": "0.705",
        },
    }

    indicators = {
        "ema_context": "bullish",
        "rsi_context": "bullish_bias",
        "rsi": 56,
    }

    result = calculer_score(
        direction=BUY,
        h4_bias="bullish",
        h1_analysis=h1,
        m15_analysis=m15,
        m5_analysis=m5,
        fibonacci_analysis=fibonacci,
        indicators=indicators,
    )

    # --------------------------------------------------------
    # TESTS DE NORMALISATION
    # --------------------------------------------------------

    assert _normalize_direction("BUY") == "bullish"
    assert _normalize_direction("SELL") == "bearish"
    assert _normalize_direction("bullish") == "bullish"
    assert _normalize_direction("bearish") == "bearish"

    # --------------------------------------------------------
    # TEST H4
    # --------------------------------------------------------

    h4_points, _ = ScoreEngine().score_h4_trend(
        "bullish",
        "BUY",
    )

    assert h4_points == 15

    # --------------------------------------------------------
    # TEST H1
    # --------------------------------------------------------

    h1_points, _ = ScoreEngine().score_h1_structure(
        h1,
        "BUY",
    )

    assert h1_points == 20

    # --------------------------------------------------------
    # TEST FINAL
    # --------------------------------------------------------

    assert result["direction"] == BUY
    assert result["final_score"] > 0
    assert result["confirmations"] > 0
    assert result["quality"] != "REJECT"

    logger.info(
        "Test score réussi : %s",
        result,
    )

    print("BUY TEST :", result)
    print()
    print("H4 TEST :", h4_points)
    print("H1 TEST :", h1_points)
    print()
    print("✅ TEST SCORE RÉUSSI")


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
            f"Type : {type(exc).__name__}"
        )
        print(
            f"Erreur : {exc}"
        )

        raise