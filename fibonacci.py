"""
Vision Trade AI V2
fibonacci.py

Moteur déterministe Fibonacci.

Responsabilités :
- déterminer le dernier swing exploitable ;
- calculer les niveaux Fibonacci ;
- déterminer premium / discount ;
- identifier le niveau de retracement le plus proche.

Aucune IA.
Aucun appel API.
Aucune décision de trading.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Sequence


logger = logging.getLogger(__name__)

BULLISH = "bullish"
BEARISH = "bearish"
NEUTRAL = "neutral"


# ============================================================
# NIVEAUX FIBONACCI
# ============================================================

FIBONACCI_LEVELS = (
    0.0,
    0.236,
    0.382,
    0.5,
    0.618,
    0.705,
    0.786,
    1.0,
)


# ============================================================
# VALIDATION
# ============================================================

def _validate_candles(
    candles: Sequence[dict],
) -> None:

    if not candles:
        raise ValueError(
            "La liste de bougies est vide."
        )

    required = {
        "high",
        "low",
        "close",
    }

    for index, candle in enumerate(candles):

        if not isinstance(candle, dict):
            raise ValueError(
                f"Bougie invalide à l'index {index}."
            )

        missing = required - set(candle.keys())

        if missing:
            raise ValueError(
                f"Colonnes manquantes à l'index "
                f"{index}: {sorted(missing)}"
            )


# ============================================================
# DERNIER SWING
# ============================================================

def _find_swing_range(
    structure_analysis: Dict[str, Any],
) -> tuple[float, float, str]:

    swings = structure_analysis.get(
        "swings",
        {},
    )

    highs = swings.get(
        "highs",
        [],
    )

    lows = swings.get(
        "lows",
        [],
    )

    if not highs or not lows:
        raise ValueError(
            "Impossible de calculer Fibonacci : "
            "swings insuffisants."
        )

    latest_high = max(
        highs,
        key=lambda x: x["index"],
    )

    latest_low = max(
        lows,
        key=lambda x: x["index"],
    )

    high_price = float(
        latest_high["price"]
    )

    low_price = float(
        latest_low["price"]
    )

    if latest_low["index"] < latest_high["index"]:

        direction = BULLISH

    else:

        direction = BEARISH

    return (
        high_price,
        low_price,
        direction,
    )


# ============================================================
# CALCUL FIBONACCI
# ============================================================

def calculer_fibonacci(
    candles: Sequence[dict],
    structure_analysis: Dict[str, Any],
) -> Dict[str, Any]:

    _validate_candles(candles)

    high_price, low_price, direction = (
        _find_swing_range(
            structure_analysis
        )
    )

    if high_price <= low_price:
        raise ValueError(
            "Range Fibonacci invalide."
        )

    range_size = high_price - low_price

    levels = {}

    for ratio in FIBONACCI_LEVELS:

        if direction == BULLISH:

            price = (
                high_price
                - range_size * ratio
            )

        else:

            price = (
                low_price
                + range_size * ratio
            )

        levels[f"{ratio:.3f}"] = price

    current_price = float(
        candles[-1]["close"]
    )

    midpoint = (
        high_price + low_price
    ) / 2.0

    if current_price < midpoint:

        zone = "discount"

    elif current_price > midpoint:

        zone = "premium"

    else:

        zone = "equilibrium"

    closest_ratio = min(
        FIBONACCI_LEVELS,
        key=lambda ratio: abs(
            current_price
            - levels[f"{ratio:.3f}"]
        ),
    )

    closest_price = levels[
        f"{closest_ratio:.3f}"
    ]

    return {
        "swing_high": high_price,
        "swing_low": low_price,
        "direction": direction,
        "range": range_size,

        "levels": levels,

        "position": {
            "price": current_price,
            "zone": zone,
        },

        "closest_level": {
            "level": f"{closest_ratio:.3f}",
            "price": closest_price,
            "distance": abs(
                current_price
                - closest_price
            ),
        },
    }


# ============================================================
# FONCTION PUBLIQUE
# ============================================================

def analyser_fibonacci(
    candles: Sequence[dict],
    structure_analysis: Dict[str, Any],
) -> Dict[str, Any]:

    return calculer_fibonacci(
        candles=candles,
        structure_analysis=structure_analysis,
    )


# ============================================================
# TEST
# ============================================================

def _run_internal_test() -> None:

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

    structure = {
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

    result = analyser_fibonacci(
        candles,
        structure,
    )

    assert "levels" in result
    assert "position" in result
    assert "closest_level" in result

    logger.info(
        "Test Fibonacci réussi : %s",
        result,
    )


if __name__ == "__main__":

    logging.basicConfig(
        level=logging.INFO,
        format=(
            "%(asctime)s | %(levelname)s | "
            "%(name)s | %(message)s"
        ),
    )

    print("=" * 60)
    print("VISION TRADE AI V2 - TEST FIBONACCI")
    print("=" * 60)

    try:

        _run_internal_test()

        print("\n✅ FIBONACCI : OK")

    except Exception as exc:

        print("\n❌ TEST FIBONACCI ÉCHOUÉ")
        print(f"Erreur : {exc}")