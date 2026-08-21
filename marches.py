"""
Vision Trade AI V2
marches.py

Responsabilité :
- définir les marchés surveillés ;
- exclure les instruments de volatilité ;
- centraliser les informations des paires ;
- vérifier qu'un symbole est autorisé ;
- fournir la liste des marchés au moteur de surveillance.

IMPORTANT :
- aucune analyse technique ;
- aucun calcul d'indicateur ;
- aucune décision BUY/SELL ;
- aucune requête API.
"""

from __future__ import annotations

import logging
from typing import Dict, List


logger = logging.getLogger(__name__)


# ============================================================
# MARCHÉS AUTORISÉS
# ============================================================

MARKETS: Dict[str, Dict[str, str]] = {

    # --------------------------------------------------------
    # FOREX
    # --------------------------------------------------------

    "EUR/USD": {
        "category": "forex",
        "name": "Euro / Dollar américain",
    },

    "GBP/USD": {
        "category": "forex",
        "name": "Livre sterling / Dollar américain",
    },

    "USD/JPY": {
        "category": "forex",
        "name": "Dollar américain / Yen japonais",
    },

    "USD/CHF": {
        "category": "forex",
        "name": "Dollar américain / Franc suisse",
    },

    "AUD/USD": {
        "category": "forex",
        "name": "Dollar australien / Dollar américain",
    },

    "USD/CAD": {
        "category": "forex",
        "name": "Dollar américain / Dollar canadien",
    },

    "NZD/USD": {
        "category": "forex",
        "name": "Dollar néo-zélandais / Dollar américain",
    },

    # --------------------------------------------------------
    # MÉTAUX
    # --------------------------------------------------------

    "XAU/USD": {
        "category": "metals",
        "name": "Or / Dollar américain",
    },

    "XAG/USD": {
        "category": "metals",
        "name": "Argent / Dollar américain",
    },

    # --------------------------------------------------------
    # CRYPTO
    # --------------------------------------------------------

    "BTC/USD": {
        "category": "crypto",
        "name": "Bitcoin / Dollar américain",
    },

    "ETH/USD": {
        "category": "crypto",
        "name": "Ethereum / Dollar américain",
    },
}


# ============================================================
# INSTRUMENTS EXCLUS
# ============================================================

EXCLUDED_MARKETS = {
    "volatility",
    "volatility 10",
    "volatility 25",
    "volatility 50",
    "volatility 75",
    "volatility 100",
    "volatility 10 index",
    "volatility 25 index",
    "volatility 50 index",
    "volatility 75 index",
    "volatility 100 index",
}


# ============================================================
# LISTE DES MARCHÉS
# ============================================================

def get_markets() -> List[str]:
    """
    Retourne tous les marchés autorisés.

    Les instruments de volatilité ne sont pas inclus.
    """

    return list(MARKETS.keys())


def get_markets_by_category(
    category: str,
) -> List[str]:
    """
    Retourne les marchés d'une catégorie.

    Catégories disponibles :

        forex
        metals
        crypto
    """

    if not isinstance(category, str):
        return []

    category = category.strip().lower()

    return [
        symbol
        for symbol, info in MARKETS.items()
        if info["category"] == category
    ]


# ============================================================
# VALIDATION
# ============================================================

def normalize_symbol(
    symbol: str,
) -> str:
    """
    Normalise un symbole.
    """

    if not isinstance(symbol, str):
        raise ValueError(
            "Le symbole doit être une chaîne de caractères."
        )

    return symbol.strip().upper()


def is_market_allowed(
    symbol: str,
) -> bool:
    """
    Vérifie si un marché est autorisé.
    """

    try:
        symbol = normalize_symbol(symbol)
    except ValueError:
        return False

    return symbol in MARKETS


def is_volatility_market(
    symbol: str,
) -> bool:
    """
    Vérifie si un symbole correspond à un marché
    de type Volatility.
    """

    if not isinstance(symbol, str):
        return False

    normalized = (
        symbol
        .strip()
        .lower()
    )

    if "volatility" in normalized:
        return True

    return normalized in EXCLUDED_MARKETS


def validate_market(
    symbol: str,
) -> str:
    """
    Valide un marché et retourne son symbole normalisé.

    Lève ValueError si le marché n'est pas autorisé.
    """

    symbol = normalize_symbol(symbol)

    if is_volatility_market(symbol):
        raise ValueError(
            f"Marché exclu : {symbol}. "
            "Les instruments Volatility ne sont pas surveillés."
        )

    if not is_market_allowed(symbol):
        raise ValueError(
            f"Marché non autorisé : {symbol}."
        )

    return symbol


# ============================================================
# INFORMATIONS MARCHÉ
# ============================================================

def get_market_info(
    symbol: str,
) -> Dict[str, str]:
    """
    Retourne les informations d'un marché.
    """

    symbol = validate_market(symbol)

    return {
        "symbol": symbol,
        **MARKETS[symbol],
    }


# ============================================================
# RÉSUMÉ
# ============================================================

def get_market_summary() -> Dict[str, object]:
    """
    Retourne un résumé de la configuration des marchés.
    """

    markets = get_markets()

    return {
        "total": len(markets),
        "forex": len(
            get_markets_by_category("forex")
        ),
        "metals": len(
            get_markets_by_category("metals")
        ),
        "crypto": len(
            get_markets_by_category("crypto")
        ),
        "volatility_included": False,
        "markets": markets,
    }


# ============================================================
# TEST INTERNE
# ============================================================

def _run_internal_test() -> None:
    """
    Vérifie le fonctionnement du module.
    """

    markets = get_markets()

    assert markets

    # Aucun marché Volatility ne doit être présent.
    for symbol in markets:
        assert not is_volatility_market(symbol)

    # Marchés principaux.
    assert "XAU/USD" in markets
    assert "EUR/USD" in markets
    assert "BTC/USD" in markets

    # Volatility explicitement exclu.
    assert not is_market_allowed(
        "Volatility 100"
    )

    assert is_volatility_market(
        "Volatility 100"
    )

    # Validation.
    assert validate_market(
        " xau/usd "
    ) == "XAU/USD"

    info = get_market_info(
        "EUR/USD"
    )

    assert info["category"] == "forex"

    summary = get_market_summary()

    assert summary["volatility_included"] is False

    logger.info(
        "Test marchés réussi : %s",
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
    print("VISION TRADE AI V2 - TEST MARCHÉS")
    print("=" * 60)

    try:

        _run_internal_test()

        summary = get_market_summary()

        print("\n✅ MARCHÉS : OK")
        print(
            f"Marchés surveillés : {summary['total']}"
        )

        for category in (
            "forex",
            "metals",
            "crypto",
        ):
            print(
                f"{category.upper()} : "
                f"{get_markets_by_category(category)}"
            )

        print(
            "Volatility : EXCLUS"
        )

    except Exception as exc:

        print("\n❌ TEST MARCHÉS ÉCHOUÉ")
        print(f"Erreur : {exc}")