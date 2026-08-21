"""
Vision Trade AI V2
fibonacci.py

Responsabilité :
- calcul des niveaux de Fibonacci ;
- détermination Premium / Discount ;
- calcul de l'Equilibrium ;
- identification de la zone actuelle du prix.

Aucune décision BUY/SELL n'est prise ici.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, Optional


logger = logging.getLogger(__name__)


# ============================================================
# CONSTANTES FIBONACCI
# ============================================================

FIB_LEVELS = (
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
# MODÈLE
# ============================================================

@dataclass
class FibonacciRange:
    """
    Représente une plage Fibonacci construite à partir
    d'un swing high et d'un swing low.
    """

    swing_high: float
    swing_low: float
    direction: str

    def __post_init__(self) -> None:

        if self.swing_high <= self.swing_low:
            raise ValueError(
                "swing_high doit être supérieur à swing_low."
            )

        if self.direction not in {
            "bullish",
            "bearish",
        }:
            raise ValueError(
                "direction doit être bullish ou bearish."
            )

    @property
    def range_size(self) -> float:
        """Amplitude totale du range."""

        return self.swing_high - self.swing_low

    @property
    def equilibrium(self) -> float:
        """
        Niveau 50 %.
        """

        return (
            self.swing_low
            + self.range_size * 0.5
        )

    def levels(self) -> Dict[str, float]:
        """
        Calcule les niveaux Fibonacci.
        """

        result = {}

        for level in FIB_LEVELS:

            price = (
                self.swing_low
                + self.range_size * level
            )

            result[str(level)] = price

        return result

    def retracement_levels(self) -> Dict[str, float]:
        """
        Retourne les niveaux de retracement dans le sens
        du mouvement principal.

        Bullish :
            retracement depuis le high vers le low.

        Bearish :
            retracement depuis le low vers le high.
        """

        if self.direction == "bullish":

            return {
                str(level): (
                    self.swing_high
                    - self.range_size * level
                )
                for level in FIB_LEVELS
            }

        return {
            str(level): (
                self.swing_low
                + self.range_size * level
            )
            for level in FIB_LEVELS
        }


# ============================================================
# VALIDATION
# ============================================================

def validate_swing_range(
    swing_high: float,
    swing_low: float,
) -> None:
    """
    Vérifie qu'un range est exploitable.
    """

    if swing_high is None or swing_low is None:
        raise ValueError(
            "Les deux swings sont obligatoires."
        )

    swing_high = float(swing_high)
    swing_low = float(swing_low)

    if swing_high <= 0 or swing_low <= 0:
        raise ValueError(
            "Les prix doivent être supérieurs à 0."
        )

    if swing_high <= swing_low:
        raise ValueError(
            "swing_high doit être supérieur à swing_low."
        )


# ============================================================
# CRÉATION DU RANGE
# ============================================================

def creer_fibonacci(
    swing_high: float,
    swing_low: float,
    direction: str,
) -> FibonacciRange:
    """
    Crée un range Fibonacci validé.
    """

    validate_swing_range(
        swing_high,
        swing_low,
    )

    return FibonacciRange(
        swing_high=float(swing_high),
        swing_low=float(swing_low),
        direction=direction.lower().strip(),
    )


# ============================================================
# NIVEAUX
# ============================================================

def calculer_niveaux_fibonacci(
    swing_high: float,
    swing_low: float,
    direction: str,
) -> Dict[str, float]:
    """
    Retourne les niveaux Fibonacci.
    """

    fib = creer_fibonacci(
        swing_high,
        swing_low,
        direction,
    )

    return fib.retracement_levels()


# ============================================================
# PREMIUM / DISCOUNT
# ============================================================

def determiner_zone_premium_discount(
    price: float,
    swing_high: float,
    swing_low: float,
) -> str:
    """
    Détermine la position du prix dans le range.

    Résultats :

        discount
        equilibrium
        premium
    """

    validate_swing_range(
        swing_high,
        swing_low,
    )

    price = float(price)

    equilibrium = (
        swing_low
        + (
            (swing_high - swing_low)
            * 0.5
        )
    )

    if price < equilibrium:
        return "discount"

    if price > equilibrium:
        return "premium"

    return "equilibrium"


def calculer_premium_discount(
    swing_high: float,
    swing_low: float,
) -> Dict[str, float]:
    """
    Retourne les bornes Premium / Discount.
    """

    validate_swing_range(
        swing_high,
        swing_low,
    )

    equilibrium = (
        swing_low
        + (
            (swing_high - swing_low)
            * 0.5
        )
    )

    return {
        "premium_high": float(swing_high),
        "equilibrium": equilibrium,
        "discount_low": float(swing_low),
    }


# ============================================================
# POSITION DANS LE RANGE
# ============================================================

def position_dans_range(
    price: float,
    swing_high: float,
    swing_low: float,
) -> Dict:
    """
    Détermine la position relative du prix dans le range.
    """

    validate_swing_range(
        swing_high,
        swing_low,
    )

    price = float(price)

    range_size = (
        swing_high - swing_low
    )

    percentage = (
        (price - swing_low)
        / range_size
    ) * 100.0

    zone = determiner_zone_premium_discount(
        price,
        swing_high,
        swing_low,
    )

    return {
        "price": price,
        "swing_high": float(swing_high),
        "swing_low": float(swing_low),
        "percentage": percentage,
        "zone": zone,
        "equilibrium": (
            swing_low
            + range_size * 0.5
        ),
    }


# ============================================================
# PROXIMITÉ D'UN NIVEAU
# ============================================================

def niveau_le_plus_proche(
    price: float,
    levels: Dict[str, float],
) -> Optional[Dict]:
    """
    Retourne le niveau Fibonacci le plus proche du prix.
    """

    if not levels:
        return None

    price = float(price)

    closest_name = min(
        levels,
        key=lambda name: abs(
            float(levels[name]) - price
        ),
    )

    closest_price = float(
        levels[closest_name]
    )

    distance = abs(
        closest_price - price
    )

    return {
        "level": closest_name,
        "price": closest_price,
        "distance": distance,
    }


# ============================================================
# ZONE FIBONACCI
# ============================================================

def determiner_zone_fibonacci(
    price: float,
    levels: Dict[str, float],
    tolerance_percent: float = 0.5,
) -> Dict:
    """
    Détermine si le prix est proche d'un niveau Fibonacci.

    tolerance_percent :
        tolérance relative par rapport au prix.
    """

    if price <= 0:
        raise ValueError(
            "price doit être supérieur à 0."
        )

    if tolerance_percent < 0:
        raise ValueError(
            "tolerance_percent doit être >= 0."
        )

    closest = niveau_le_plus_proche(
        price,
        levels,
    )

    if closest is None:
        return {
            "near_level": False,
            "level": None,
            "distance": None,
        }

    tolerance = (
        price
        * tolerance_percent
        / 100.0
    )

    return {
        "near_level": (
            closest["distance"]
            <= tolerance
        ),
        "level": closest["level"],
        "price": closest["price"],
        "distance": closest["distance"],
        "tolerance": tolerance,
    }


# ============================================================
# RETRACEMENT OPTIMAL
# ============================================================

def zone_retracement_optimale(
    levels: Dict[str, float],
) -> Dict[str, float]:
    """
    Extrait les niveaux généralement utilisés comme
    zone de retracement profonde.

    Cette fonction ne dit pas si cette zone constitue
    une entrée valide.
    """

    wanted = {
        "0.618",
        "0.705",
        "0.786",
    }

    return {
        key: value
        for key, value in levels.items()
        if key in wanted
    }


# ============================================================
# ANALYSE FIBONACCI COMPLÈTE
# ============================================================

def analyser_fibonacci(
    price: float,
    swing_high: float,
    swing_low: float,
    direction: str,
) -> Dict:
    """
    Analyse complète du contexte Fibonacci.
    """

    fib = creer_fibonacci(
        swing_high=swing_high,
        swing_low=swing_low,
        direction=direction,
    )

    levels = fib.retracement_levels()

    position = position_dans_range(
        price=price,
        swing_high=swing_high,
        swing_low=swing_low,
    )

    closest = niveau_le_plus_proche(
        price,
        levels,
    )

    optimal_zone = (
        zone_retracement_optimale(
            levels
        )
    )

    return {
        "direction": direction,
        "swing_high": swing_high,
        "swing_low": swing_low,
        "range_size": fib.range_size,
        "equilibrium": fib.equilibrium,
        "levels": levels,
        "position": position,
        "closest_level": closest,
        "optimal_retracement": optimal_zone,
    }


# ============================================================
# TEST INTERNE
# ============================================================

def _run_internal_test() -> None:
    """
    Teste les fonctions principales.
    """

    swing_high = 200.0
    swing_low = 100.0
    price = 140.0

    fib = creer_fibonacci(
        swing_high,
        swing_low,
        "bullish",
    )

    assert fib.range_size == 100.0
    assert fib.equilibrium == 150.0

    levels = fib.retracement_levels()

    assert "0.618" in levels
    assert "0.705" in levels
    assert "0.786" in levels

    zone = determiner_zone_premium_discount(
        price,
        swing_high,
        swing_low,
    )

    assert zone == "discount"

    position = position_dans_range(
        price,
        swing_high,
        swing_low,
    )

    assert position["zone"] == "discount"
    assert position["percentage"] == 40.0

    analysis = analyser_fibonacci(
        price=price,
        swing_high=swing_high,
        swing_low=swing_low,
        direction="bullish",
    )

    assert analysis["levels"]
    assert analysis["optimal_retracement"]

    logger.info(
        "Test Fibonacci réussi."
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
    print("VISION TRADE AI V2 - TEST FIBONACCI")
    print("=" * 60)

    try:

        _run_internal_test()

        print("\n✅ FIBONACCI : OK")
        print(
            "Fibonacci + Premium/Discount "
            "fonctionnent correctement."
        )

    except Exception as exc:

        print("\n❌ TEST FIBONACCI ÉCHOUÉ")
        print(f"Erreur : {exc}")