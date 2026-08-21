"""
Vision Trade AI V2
indicateurs.py

Responsabilité :
- calculer les indicateurs techniques ;
- EMA ;
- RSI ;
- ATR ;
- fournir des résultats déterministes.

Ce module ne prend aucune décision de trading.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Sequence


logger = logging.getLogger(__name__)


# ============================================================
# VALIDATION
# ============================================================

def _validate_candles(candles: Sequence[dict]) -> None:
    """
    Vérifie que les données OHLC sont exploitables.
    """

    if not candles:
        raise ValueError("La liste de bougies est vide.")

    required = {
        "open",
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
                f"Colonnes manquantes à l'index {index} : "
                f"{sorted(missing)}"
            )


def _closes(candles: Sequence[dict]) -> List[float]:
    """Retourne les prix de clôture."""

    _validate_candles(candles)

    return [
        float(candle["close"])
        for candle in candles
    ]


def _highs(candles: Sequence[dict]) -> List[float]:
    """Retourne les plus hauts."""

    _validate_candles(candles)

    return [
        float(candle["high"])
        for candle in candles
    ]


def _lows(candles: Sequence[dict]) -> List[float]:
    """Retourne les plus bas."""

    _validate_candles(candles)

    return [
        float(candle["low"])
        for candle in candles
    ]


# ============================================================
# EMA
# ============================================================

def calculer_ema(
    candles: Sequence[dict],
    period: int,
) -> List[float]:
    """
    Calcule une EMA classique.

    La première valeur est initialisée avec la SMA
    de la première période.

    Args:
        candles:
            Bougies OHLC.

        period:
            Période de l'EMA.

    Returns:
        Liste de valeurs EMA.
    """

    if period <= 0:
        raise ValueError(
            "La période EMA doit être supérieure à 0."
        )

    closes = _closes(candles)

    if len(closes) < period:
        raise ValueError(
            f"Pas assez de données pour EMA{period} : "
            f"{len(closes)} disponibles."
        )

    multiplier = 2.0 / (period + 1)

    # Première EMA = SMA initiale.
    initial_sma = sum(
        closes[:period]
    ) / period

    ema_values = [
        initial_sma
    ]

    previous_ema = initial_sma

    for price in closes[period:]:

        current_ema = (
            (price - previous_ema)
            * multiplier
            + previous_ema
        )

        ema_values.append(current_ema)

        previous_ema = current_ema

    # Pour conserver la même longueur que candles,
    # les premières valeurs sont None.
    return (
        [None] * (period - 1)
        + ema_values
    )


# ============================================================
# RSI
# ============================================================

def calculer_rsi(
    candles: Sequence[dict],
    period: int = 14,
) -> List[float]:
    """
    Calcule le RSI de Wilder.

    Args:
        candles:
            Bougies OHLC.

        period:
            Période RSI.

    Returns:
        Liste de valeurs RSI.
    """

    if period <= 0:
        raise ValueError(
            "La période RSI doit être supérieure à 0."
        )

    closes = _closes(candles)

    if len(closes) <= period:
        raise ValueError(
            f"Pas assez de données pour RSI{period}."
        )

    changes = [
        closes[i] - closes[i - 1]
        for i in range(1, len(closes))
    ]

    gains = [
        max(change, 0.0)
        for change in changes
    ]

    losses = [
        max(-change, 0.0)
        for change in changes
    ]

    average_gain = (
        sum(gains[:period]) / period
    )

    average_loss = (
        sum(losses[:period]) / period
    )

    rsi_values = [
        None
    ] * period

    def calculate_rsi(
        avg_gain: float,
        avg_loss: float,
    ) -> float:

        if avg_loss == 0:

            if avg_gain == 0:
                return 50.0

            return 100.0

        relative_strength = (
            avg_gain / avg_loss
        )

        return (
            100.0
            - (
                100.0
                / (1.0 + relative_strength)
            )
        )

    rsi_values.append(
        calculate_rsi(
            average_gain,
            average_loss,
        )
    )

    for i in range(period, len(changes)):

        average_gain = (
            (
                average_gain
                * (period - 1)
            )
            + gains[i]
        ) / period

        average_loss = (
            (
                average_loss
                * (period - 1)
            )
            + losses[i]
        ) / period

        rsi_values.append(
            calculate_rsi(
                average_gain,
                average_loss,
            )
        )

    return rsi_values


# ============================================================
# TRUE RANGE
# ============================================================

def calculer_true_range(
    candles: Sequence[dict],
) -> List[float]:
    """
    Calcule le True Range pour chaque bougie.
    """

    _validate_candles(candles)

    if len(candles) < 1:
        return []

    true_ranges = []

    previous_close = None

    for candle in candles:

        high = float(candle["high"])
        low = float(candle["low"])
        close = float(candle["close"])

        if previous_close is None:

            true_range = high - low

        else:

            true_range = max(
                high - low,
                abs(high - previous_close),
                abs(low - previous_close),
            )

        true_ranges.append(
            true_range
        )

        previous_close = close

    return true_ranges


# ============================================================
# ATR
# ============================================================

def calculer_atr(
    candles: Sequence[dict],
    period: int = 14,
) -> List[float]:
    """
    Calcule l'ATR avec le lissage de Wilder.

    Args:
        candles:
            Bougies OHLC.

        period:
            Période ATR.

    Returns:
        Liste des ATR.
    """

    if period <= 0:
        raise ValueError(
            "La période ATR doit être supérieure à 0."
        )

    true_ranges = calculer_true_range(
        candles
    )

    if len(true_ranges) < period:
        raise ValueError(
            f"Pas assez de données pour ATR{period}."
        )

    initial_atr = (
        sum(true_ranges[:period])
        / period
    )

    atr_values = [
        None
    ] * (period - 1)

    atr_values.append(
        initial_atr
    )

    previous_atr = initial_atr

    for true_range in true_ranges[period:]:

        current_atr = (
            (
                previous_atr
                * (period - 1)
            )
            + true_range
        ) / period

        atr_values.append(
            current_atr
        )

        previous_atr = current_atr

    return atr_values


# ============================================================
# DERNIÈRE VALEUR VALIDE
# ============================================================

def derniere_valeur(
    values: Sequence,
):
    """
    Retourne la dernière valeur non nulle/non-None.
    """

    for value in reversed(values):

        if value is not None:
            return value

    return None


# ============================================================
# ANALYSE INDICATEURS
# ============================================================

def analyser_indicateurs(
    candles: Sequence[dict],
    ema_fast: int = 20,
    ema_slow: int = 50,
    rsi_period: int = 14,
    atr_period: int = 14,
) -> Dict:
    """
    Calcule tous les indicateurs utilisés par Vision Trade AI V2.

    Retourne les séries complètes ainsi que leurs dernières valeurs.
    """

    _validate_candles(candles)

    ema_fast_values = calculer_ema(
        candles,
        ema_fast,
    )

    ema_slow_values = calculer_ema(
        candles,
        ema_slow,
    )

    rsi_values = calculer_rsi(
        candles,
        rsi_period,
    )

    atr_values = calculer_atr(
        candles,
        atr_period,
    )

    return {
        "ema_fast": ema_fast_values,
        "ema_slow": ema_slow_values,
        "rsi": rsi_values,
        "atr": atr_values,

        "latest": {
            "ema_fast": derniere_valeur(
                ema_fast_values
            ),
            "ema_slow": derniere_valeur(
                ema_slow_values
            ),
            "rsi": derniere_valeur(
                rsi_values
            ),
            "atr": derniere_valeur(
                atr_values
            ),
        },
    }


# ============================================================
# CONTEXTE INDICATEURS
# ============================================================

def determiner_contexte_ema(
    ema_fast: float,
    ema_slow: float,
    tolerance: float = 0.0,
) -> str:
    """
    Détermine simplement la relation EMA20/EMA50.

    Retour :
        bullish
        bearish
        neutral
    """

    if ema_fast is None or ema_slow is None:
        return "neutral"

    difference = ema_fast - ema_slow

    if abs(difference) <= tolerance:
        return "neutral"

    if difference > 0:
        return "bullish"

    return "bearish"


def determiner_contexte_rsi(
    rsi: float,
) -> str:
    """
    Classe le RSI sans produire de signal.
    """

    if rsi is None:
        return "unknown"

    if rsi >= 70:
        return "overbought"

    if rsi <= 30:
        return "oversold"

    if rsi >= 50:
        return "bullish_bias"

    return "bearish_bias"


def determiner_volatilite(
    atr: float,
    close: float,
) -> str:
    """
    Donne une classification simple de volatilité
    basée sur ATR / prix.

    Cette fonction ne décide pas si un trade est autorisé.
    """

    if atr is None or close is None:
        return "unknown"

    if close <= 0:
        return "unknown"

    atr_percentage = (
        atr / close
    ) * 100.0

    # Ces seuils sont volontairement génériques.
    # Le moteur de régime de marché pourra les affiner
    # plus tard avec un historique de volatilité.

    if atr_percentage < 0.10:
        return "low"

    if atr_percentage < 0.50:
        return "normal"

    return "high"


# ============================================================
# RÉSUMÉ INDICATEURS
# ============================================================

def resume_indicateurs(
    candles: Sequence[dict],
    ema_fast: int = 20,
    ema_slow: int = 50,
    rsi_period: int = 14,
    atr_period: int = 14,
) -> Dict:
    """
    Retourne uniquement le contexte nécessaire au moteur.
    """

    result = analyser_indicateurs(
        candles=candles,
        ema_fast=ema_fast,
        ema_slow=ema_slow,
        rsi_period=rsi_period,
        atr_period=atr_period,
    )

    latest = result["latest"]

    ema_context = determiner_contexte_ema(
        latest["ema_fast"],
        latest["ema_slow"],
    )

    rsi_context = determiner_contexte_rsi(
        latest["rsi"]
    )

    closes = _closes(candles)

    volatility = determiner_volatilite(
        latest["atr"],
        closes[-1],
    )

    return {
        "ema20": latest["ema_fast"],
        "ema50": latest["ema_slow"],
        "rsi": latest["rsi"],
        "atr": latest["atr"],
        "ema_context": ema_context,
        "rsi_context": rsi_context,
        "volatility": volatility,
    }


# ============================================================
# TEST INTERNE
# ============================================================

def _generate_test_candles(
    count: int = 100,
) -> List[dict]:
    """
    Génère des données synthétiques uniquement pour tester
    les calculs mathématiques du module.
    """

    candles = []

    price = 100.0

    for i in range(count):

        open_price = price

        close_price = (
            price
            + 0.10
            + ((i % 5) * 0.01)
        )

        high_price = (
            max(
                open_price,
                close_price,
            )
            + 0.20
        )

        low_price = (
            min(
                open_price,
                close_price,
            )
            - 0.20
        )

        candles.append(
            {
                "datetime": (
                    f"2026-01-01 "
                    f"{i:02d}:00:00"
                ),
                "open": open_price,
                "high": high_price,
                "low": low_price,
                "close": close_price,
                "volume": 1000.0,
            }
        )

        price = close_price

    return candles


def _run_internal_test() -> None:
    """
    Vérifie les fonctions principales.
    """

    candles = _generate_test_candles()

    ema20 = calculer_ema(
        candles,
        20,
    )

    ema50 = calculer_ema(
        candles,
        50,
    )

    rsi = calculer_rsi(
        candles,
        14,
    )

    atr = calculer_atr(
        candles,
        14,
    )

    assert len(ema20) == len(candles)
    assert len(ema50) == len(candles)
    assert len(rsi) == len(candles)
    assert len(atr) == len(candles)

    assert derniere_valeur(ema20) is not None
    assert derniere_valeur(ema50) is not None
    assert derniere_valeur(rsi) is not None
    assert derniere_valeur(atr) is not None

    summary = resume_indicateurs(
        candles
    )

    assert summary["ema20"] is not None
    assert summary["ema50"] is not None
    assert summary["rsi"] is not None
    assert summary["atr"] is not None

    logger.info(
        "Test indicateurs réussi : %s",
        summary,
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
    print("VISION TRADE AI V2 - TEST INDICATEURS")
    print("=" * 60)

    try:

        _run_internal_test()

        print("\n✅ INDICATEURS : OK")
        print(
            "EMA20 / EMA50 / RSI14 / ATR14 "
            "fonctionnent correctement."
        )

    except Exception as exc:

        print("\n❌ TEST INDICATEURS ÉCHOUÉ")
        print(f"Erreur : {exc}")