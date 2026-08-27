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
- calculer un score final ;
- déterminer la qualité du setup.

IMPORTANT :
- aucune IA ;
- aucun appel API ;
- aucun calcul de SL/TP ;
- aucun signal Telegram ;
- aucune création de direction.

La direction est fournie par analyse.py.

Le score ne fait que mesurer la qualité
de cette direction.
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

def _normalize_direction(
    direction: Any,
) -> str:
    """
    Normalise toutes les représentations de direction.

    BUY / BULLISH / LONG  -> bullish
    SELL / BEARISH / SHORT -> bearish
    NEUTRAL / NONE / vide -> neutral

    Toute valeur inconnue devient neutral.
    """

    if direction is None:
        return NEUTRAL.lower()

    value = str(
        direction
    ).lower().strip()

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


def _direction_label(
    direction: Any,
) -> str:
    """
    Convertit une direction interne vers :

        BUY
        SELL
        NEUTRAL
    """

    normalized = _normalize_direction(
        direction
    )

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
    Conversion robuste vers float.
    """

    if value is None:
        return None

    if isinstance(
        value,
        bool,
    ):
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

    if isinstance(
        value,
        dict,
    ):
        return value

    return {}


# ============================================================
# SCORE ENGINE
# ============================================================

class ScoreEngine:
    """
    Moteur déterministe de scoring.

    Pondération maximale théorique :

        H4 tendance             15
        H1 structure            20
        M15 SMC                 20
        M5 confirmation         15
        Fibonacci               10
        Indicateurs             10
        Liquidité               10
        ---------------------------
        TOTAL                   100

    IMPORTANT :

    Les pénalités peuvent réduire le score,
    mais ne créent jamais une nouvelle direction.

    La direction est imposée par analyse.py.
    """

    WEIGHTS = {

        "h4_trend":
            15,

        "h1_structure":
            20,

        "m15_smc":
            20,

        "m5_confirmation":
            15,

        "fibonacci":
            10,

        "indicators":
            10,

        "liquidity":
            10,
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

        bias = _normalize_direction(
            h4_bias
        )

        target = _normalize_direction(
            direction
        )

        if target == NEUTRAL.lower():
            return 0, None

        if bias == NEUTRAL.lower():
            return 0, None

        if bias == target:

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

        h1_analysis = _safe_dict(
            h1_analysis
        )

        target = _normalize_direction(
            direction
        )

        if target == NEUTRAL.lower():
            return 0, []

        score = 0
        reasons = []

        # ----------------------------------------------------
        # BIAIS H1
        # ----------------------------------------------------

        bias = _normalize_direction(
            h1_analysis.get(
                "bias",
                NEUTRAL,
            )
        )

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
        # LATEST
        # ----------------------------------------------------

        latest = _safe_dict(
            h1_analysis.get(
                "latest",
                {},
            )
        )

        # ----------------------------------------------------
        # BOS H1
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
        # CHOCH H1
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

        m15_analysis = _safe_dict(
            m15_analysis
        )

        target = _normalize_direction(
            direction
        )

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
        # LIQUIDITY SWEEP
        # ----------------------------------------------------

        latest_sweep = _safe_dict(
            latest.get(
                "liquidity_sweep"
            )
        )

        if latest_sweep:

            sweep_direction = _normalize_direction(
                latest_sweep.get(
                    "direction"
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
    # M5 CONFIRMATION
    # ========================================================

    def score_m5_confirmation(
        self,
        m5_analysis: Dict[str, Any],
        direction: str,
    ) -> tuple[int, list[str]]:

        m5_analysis = _safe_dict(
            m5_analysis
        )

        target = _normalize_direction(
            direction
        )

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
                "Biais M5 opposé."
            )

        # ----------------------------------------------------
        # LATEST
        # ----------------------------------------------------

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
    ) -> tuple[int, list[str]]:

        fibonacci_analysis = _safe_dict(
            fibonacci_analysis
        )

        target = _normalize_direction(
            direction
        )

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
        # NIVEAU DE RETRACEMENT
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
                    ""
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

        indicators = _safe_dict(
            indicators
        )

        target = _normalize_direction(
            direction
        )

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

        # ----------------------------------------------------
        # EMA
        # ----------------------------------------------------

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

        target = _normalize_direction(
            direction
        )

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

        if sweep_direction == target:

            return (
                self.WEIGHTS["liquidity"],
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

        # ----------------------------------------------------
        # LA DIRECTION DOIT ÊTRE FOURNIE PAR ANALYSE.PY
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

        final_score = _clamp(
            final_score
        )

        # ----------------------------------------------------
        # LES SCORES RESTENT DANS 0-100
        # ----------------------------------------------------

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
        """
        Classe la qualité du setup.

        A+ : >= 90
        A  : >= 85
        B  : >= 80
        C  : >= 70
        D  : >= 60
        REJECT : < 60
        """

        score = _clamp(
            score
        )

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

    Compatible avec analyse.py.
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

    data = asdict(
        result
    )

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
    Tests complets du moteur de scoring.
    """

    # ========================================================
    # NORMALISATION
    # ========================================================

    assert (
        _normalize_direction("BUY")
        == BULLISH
    )

    assert (
        _normalize_direction("buy")
        == BULLISH
    )

    assert (
        _normalize_direction("bullish")
        == BULLISH
    )

    assert (
        _normalize_direction("LONG")
        == BULLISH
    )

    assert (
        _normalize_direction("SELL")
        == BEARISH
    )

    assert (
        _normalize_direction("sell")
        == BEARISH
    )

    assert (
        _normalize_direction("bearish")
        == BEARISH
    )

    assert (
        _normalize_direction("SHORT")
        == BEARISH
    )

    assert (
        _normalize_direction("xxx")
        == NEUTRAL.lower()
    )

    # ========================================================
    # LABEL
    # ========================================================

    assert (
        _direction_label("bullish")
        == BUY
    )

    assert (
        _direction_label("bearish")
        == SELL
    )

    assert (
        _direction_label("neutral")
        == NEUTRAL
    )

    # ========================================================
    # H4
    # ========================================================

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

    h4_neutral = engine.score_h4_trend(
        "neutral",
        "BUY",
    )

    assert h4_neutral[0] == 0

    # ========================================================
    # H1
    # ========================================================

    h1 = {

        "bias":
            "bullish",

        "latest": {

            "bos": {

                "direction":
                    "bullish",

                "break_type":
                    "BOS",
            }
        },
    }

    h1_score = engine.score_h1_structure(
        h1,
        BUY,
    )

    assert h1_score[0] == 20

    # ========================================================
    # M15
    # ========================================================

    m15 = {

        "bias":
            "bullish",

        "latest": {

            "order_block": {

                "direction":
                    "bullish",
            },

            "fvg": {

                "direction":
                    "bullish",
            },

            "liquidity_sweep": {

                "direction":
                    "bullish",
            },
        },
    }

    m15_score = engine.score_m15_smc(
        m15,
        BUY,
    )

    assert m15_score[0] == 20

    # ========================================================
    # M5
    # ========================================================

    m5 = {

        "bias":
            "bullish",

        "latest": {

            "bos": {

                "direction":
                    "bullish",
            }
        },
    }

    m5_score = engine.score_m5_confirmation(
        m5,
        BUY,
    )

    assert m5_score[0] == 12

    # ========================================================
    # FIBONACCI
    # ========================================================

    fibonacci = {

        "position": {

            "zone":
                "discount",
        },

        "closest_level": {

            "level":
                "0.705",
        },
    }

    fib_score = engine.score_fibonacci(
        fibonacci,
        BUY,
    )

    assert fib_score[0] == 10

    # ========================================================
    # INDICATEURS
    # ========================================================

    indicators = {

        "ema_context":
            "bullish",

        "rsi_context":
            "bullish_bias",

        "rsi":
            56,
    }

    indicator_score = engine.score_indicators(
        indicators,
        BUY,
    )

    assert indicator_score[0] == 8

    # ========================================================
    # LIQUIDITÉ
    # ========================================================

    liquidity_score = engine.score_liquidity(
        m15,
        BUY,
    )

    assert liquidity_score[0] == 10

    # ========================================================
    # CALCUL BUY
    # ========================================================

    result = calculer_score(

        direction="BUY",

        h4_bias="bullish",

        h1_analysis=h1,

        m15_analysis=m15,

        m5_analysis=m5,

        fibonacci_analysis=fibonacci,

        indicators=indicators,
    )

    assert (
        result["direction"]
        == "BUY"
    )

    assert (
        result["buy_score"]
        > 0
    )

    assert (
        result["final_score"]
        > 0
    )

    assert (
        result["final_score"]
        >= 80
    )

    assert (
        result["passes_threshold"]
        is True
    )

    assert (
        result["quality"]
        != "REJECT"
    )

    assert (
        result["confirmations"]
        > 0
    )

    logger.info(
        "Test score BUY réussi : %s",
        result,
    )

    print(
        "BUY SCORE:",
        result["buy_score"],
    )

    print(
        "BUY FINAL SCORE:",
        result["final_score"],
    )

    print(
        "BUY QUALITY:",
        result["quality"],
    )

    print(
        "BUY CONFIRMATIONS:",
        result["confirmations"],
    )

    print(
        "BUY CONTRADICTIONS:",
        result["contradictions"],
    )

    # ========================================================
    # TEST SELL
    # ========================================================

    sell_h1 = {

        "bias":
            "bearish",

        "latest": {

            "bos": {

                "direction":
                    "bearish",

                "break_type":
                    "BOS",
            }
        },
    }

    sell_m15 = {

        "bias":
            "bearish",

        "latest": {

            "order_block": {

                "direction":
                    "bearish",
            },

            "fvg": {

                "direction":
                    "bearish",
            },

            "liquidity_sweep": {

                "direction":
                    "bearish",
            },
        },
    }

    sell_m5 = {

        "bias":
            "bearish",

        "latest": {

            "bos": {

                "direction":
                    "bearish",
            }
        },
    }

    sell_fibonacci = {

        "position": {

            "zone":
                "premium",
        },

        "closest_level": {

            "level":
                "0.705",
        },
    }

    sell_indicators = {

        "ema_context":
            "bearish",

        "rsi_context":
            "bearish_bias",

        "rsi":
            44,
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

    assert (
        sell_result["direction"]
        == "SELL"
    )

    assert (
        sell_result["sell_score"]
        > 0
    )

    assert (
        sell_result["final_score"]
        > 0
    )

    assert (
        sell_result["final_score"]
        >= 80
    )

    assert (
        sell_result["passes_threshold"]
        is True
    )

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

    # ========================================================
    # TEST DIRECTION NEUTRE
    # ========================================================

    try:

        calculer_score(
            direction="NEUTRAL"
        )

        raise AssertionError(
            "Une direction NEUTRAL aurait dû être refusée."
        )

    except ValueError:

        pass

    # ========================================================
    # TEST CONTRADICTION
    # ========================================================

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

    assert (
        contradiction_result["direction"]
        == "BUY"
    )

    assert (
        contradiction_result["final_score"]
        < 80
    )

    assert (
        contradiction_result["contradictions"]
        > 0
    )

    assert (
        contradiction_result["passes_threshold"]
        is False
    )

    print(
        "CONTRADICTION TEST : OK"
    )

    logger.info(
        "Tous les tests score.py sont réussis."
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

    print(
        "VISION TRADE AI V2"
    )

    print(
        "TEST SCORE.PY"
    )

    print("=" * 60)

    try:

        _run_internal_test()

        print()

        print(
            "✅ SCORE : OK"
        )

        print(
            "Moteur de scoring déterministe opérationnel."
        )

    except Exception as exc:

        print()

        print(
            "❌ TEST SCORE ÉCHOUÉ"
        )

        print(
            f"Erreur : {type(exc).__name__}: {exc}"
        )

        raise