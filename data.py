"""
Vision Trade AI V2
data.py

Responsabilité :
- communiquer avec Twelve Data ;
- récupérer les bougies OHLCV ;
- normaliser les données ;
- fournir H4 / H1 / M15 / M5 ;
- gérer proprement les erreurs API ;
- empêcher l'analyse de travailler sur des données invalides.

Aucune logique SMC, aucun indicateur et aucune décision de trading
ne doivent être placés dans ce fichier.
"""

import logging
import time
from typing import Dict, List, Optional

import requests

from config import (
    TWELVE_DATA_KEY,
    CANDLE_LIMIT,
    MIN_CANDLES,
    H4_TIMEFRAME,
    H1_TIMEFRAME,
    M15_TIMEFRAME,
    M5_TIMEFRAME,
)


# ============================================================
# CONFIGURATION
# ============================================================

logger = logging.getLogger(__name__)

BASE_URL = "https://api.twelvedata.com/time_series"

REQUEST_TIMEOUT = 15

MAX_RETRIES = 3

RETRY_DELAYS = (1, 2, 4)

VALID_INTERVALS = {
    "5min",
    "15min",
    "1h",
    "4h",
}


# ============================================================
# EXCEPTIONS
# ============================================================

class DataError(Exception):
    """Erreur générale liée aux données de marché."""


class DataConfigurationError(DataError):
    """Erreur de configuration de Twelve Data."""


class DataAPIError(DataError):
    """Erreur retournée par Twelve Data."""


class InsufficientDataError(DataError):
    """Pas assez de bougies disponibles."""


# ============================================================
# VALIDATION
# ============================================================

def _validate_api_key() -> None:
    """
    Vérifie que la clé Twelve Data est disponible.
    """

    if not TWELVE_DATA_KEY:
        raise DataConfigurationError(
            "TWELVE_DATA_KEY est absente des variables d'environnement."
        )


def _validate_symbol(symbol: str) -> str:
    """
    Valide et normalise le symbole.
    """

    if not isinstance(symbol, str):
        raise ValueError("Le symbole doit être une chaîne de caractères.")

    symbol = symbol.strip().upper()

    if not symbol:
        raise ValueError("Le symbole ne peut pas être vide.")

    return symbol


def _validate_interval(interval: str) -> str:
    """
    Vérifie que l'intervalle est supporté.
    """

    if not isinstance(interval, str):
        raise ValueError("L'intervalle doit être une chaîne.")

    interval = interval.strip().lower()

    if interval not in VALID_INTERVALS:
        raise ValueError(
            f"Intervalle invalide : {interval}. "
            f"Valeurs autorisées : {sorted(VALID_INTERVALS)}"
        )

    return interval


# ============================================================
# NORMALISATION DES BOUGIES
# ============================================================

def _normalize_candle(candle: dict) -> Optional[dict]:
    """
    Transforme une bougie Twelve Data en structure interne standard.

    Format retourné :

    {
        "datetime": "...",
        "open": float,
        "high": float,
        "low": float,
        "close": float,
        "volume": float
    }

    Une bougie invalide est ignorée.
    """

    try:
        datetime_value = candle.get("datetime")

        if not datetime_value:
            return None

        open_price = float(candle["open"])
        high_price = float(candle["high"])
        low_price = float(candle["low"])
        close_price = float(candle["close"])

        volume_raw = candle.get("volume", 0)

        if volume_raw in (None, "", "None"):
            volume = 0.0
        else:
            volume = float(volume_raw)

        # Contrôle de cohérence OHLC.
        if open_price <= 0:
            return None

        if high_price <= 0 or low_price <= 0 or close_price <= 0:
            return None

        if high_price < low_price:
            return None

        if high_price < max(open_price, close_price):
            return None

        if low_price > min(open_price, close_price):
            return None

        return {
            "datetime": str(datetime_value),
            "open": open_price,
            "high": high_price,
            "low": low_price,
            "close": close_price,
            "volume": volume,
        }

    except (KeyError, TypeError, ValueError):
        return None


def _normalize_candles(values: list) -> List[dict]:
    """
    Normalise toutes les bougies reçues.
    """

    if not isinstance(values, list):
        raise DataAPIError(
            "La réponse Twelve Data ne contient pas une liste 'values' valide."
        )

    candles = []

    for raw_candle in values:
        if not isinstance(raw_candle, dict):
            continue

        candle = _normalize_candle(raw_candle)

        if candle is not None:
            candles.append(candle)

    if not candles:
        raise DataAPIError(
            "Aucune bougie valide n'a été trouvée dans la réponse."
        )

    # Twelve Data retourne généralement les dernières bougies
    # dans l'ordre décroissant. On remet toujours les données
    # dans l'ordre chronologique.
    candles.sort(key=lambda x: x["datetime"])

    return candles


# ============================================================
# REQUÊTE TWELVE DATA
# ============================================================

def _request_time_series(
    symbol: str,
    interval: str,
    outputsize: int = CANDLE_LIMIT,
) -> List[dict]:
    """
    Effectue une requête robuste vers Twelve Data.
    """

    _validate_api_key()

    symbol = _validate_symbol(symbol)
    interval = _validate_interval(interval)

    if outputsize <= 0:
        raise ValueError("outputsize doit être supérieur à 0.")

    if outputsize > 5000:
        raise ValueError("outputsize ne peut pas dépasser 5000.")

    params = {
        "symbol": symbol,
        "interval": interval,
        "outputsize": outputsize,
        "apikey": TWELVE_DATA_KEY,
        "format": "JSON",
        "order": "asc",
    }

    last_error = None

    for attempt in range(1, MAX_RETRIES + 1):

        try:
            response = requests.get(
                BASE_URL,
                params=params,
                timeout=REQUEST_TIMEOUT,
            )

            response.raise_for_status()

            try:
                payload = response.json()
            except ValueError as exc:
                raise DataAPIError(
                    "Twelve Data a retourné une réponse JSON invalide."
                ) from exc

            # Twelve Data peut retourner HTTP 200 tout en indiquant
            # une erreur dans le JSON.
            if payload.get("status") == "error":
                message = payload.get(
                    "message",
                    "Erreur inconnue de Twelve Data.",
                )

                code = payload.get("code", "unknown")

                raise DataAPIError(
                    f"Twelve Data error {code}: {message}"
                )

            values = payload.get("values")

            if values is None:
                raise DataAPIError(
                    "Réponse Twelve Data sans champ 'values'."
                )

            candles = _normalize_candles(values)

            return candles

        except requests.RequestException as exc:
            last_error = exc

            logger.warning(
                "Erreur réseau Twelve Data "
                "(tentative %s/%s) : %s",
                attempt,
                MAX_RETRIES,
                exc,
            )

            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAYS[attempt - 1])

        except DataAPIError:
            raise

    raise DataAPIError(
        f"Impossible de récupérer les données Twelve Data après "
        f"{MAX_RETRIES} tentatives : {last_error}"
    )


# ============================================================
# API PUBLIQUE
# ============================================================

def get_candles(
    symbol: str,
    interval: str,
    limit: int = CANDLE_LIMIT,
    require_minimum: bool = True,
) -> List[dict]:
    """
    Récupère les bougies d'un marché et d'un timeframe.

    Args:
        symbol:
            Exemple : XAU/USD

        interval:
            5min, 15min, 1h ou 4h

        limit:
            Nombre de bougies demandé.

        require_minimum:
            Vérifie que le nombre minimum de bougies est disponible.

    Returns:
        Liste chronologique de bougies OHLCV.
    """

    candles = _request_time_series(
        symbol=symbol,
        interval=interval,
        outputsize=limit,
    )

    if require_minimum and len(candles) < MIN_CANDLES:
        raise InsufficientDataError(
            f"Données insuffisantes pour {symbol} {interval} : "
            f"{len(candles)} bougies disponibles, "
            f"{MIN_CANDLES} nécessaires."
        )

    return candles


def get_h4(symbol: str, limit: int = CANDLE_LIMIT) -> List[dict]:
    """Récupère les données H4."""

    return get_candles(
        symbol=symbol,
        interval=H4_TIMEFRAME,
        limit=limit,
    )


def get_h1(symbol: str, limit: int = CANDLE_LIMIT) -> List[dict]:
    """Récupère les données H1."""

    return get_candles(
        symbol=symbol,
        interval=H1_TIMEFRAME,
        limit=limit,
    )


def get_m15(symbol: str, limit: int = CANDLE_LIMIT) -> List[dict]:
    """Récupère les données M15."""

    return get_candles(
        symbol=symbol,
        interval=M15_TIMEFRAME,
        limit=limit,
    )


def get_m5(symbol: str, limit: int = CANDLE_LIMIT) -> List[dict]:
    """Récupère les données M5."""

    return get_candles(
        symbol=symbol,
        interval=M5_TIMEFRAME,
        limit=limit,
    )


def get_multi_timeframe_data(
    symbol: str,
    limit: int = CANDLE_LIMIT,
) -> Dict[str, List[dict]]:
    """
    Récupère les quatre timeframes nécessaires au moteur.

    Retour :

    {
        "H4": [...],
        "H1": [...],
        "M15": [...],
        "M5": [...]
    }

    Si un timeframe échoue, l'analyse complète échoue.
    Cela évite de produire un signal avec des données incomplètes.
    """

    symbol = _validate_symbol(symbol)

    logger.info(
        "Récupération multi-timeframe : %s",
        symbol,
    )

    data = {
        "H4": get_h4(symbol, limit),
        "H1": get_h1(symbol, limit),
        "M15": get_m15(symbol, limit),
        "M5": get_m5(symbol, limit),
    }

    for timeframe, candles in data.items():
        logger.info(
            "%s %s : %s bougies",
            symbol,
            timeframe,
            len(candles),
        )

    return data


# ============================================================
# PRIX ACTUEL
# ============================================================

def get_price(symbol: str) -> float:
    """
    Récupère le dernier prix disponible via une bougie M5.

    On utilise ici la dernière clôture M5 afin de conserver
    une source cohérente avec le moteur d'analyse.
    """

    candles = get_m5(
        symbol=symbol,
        limit=2,
    )

    if not candles:
        raise DataError(
            f"Impossible de récupérer le prix de {symbol}."
        )

    return float(candles[-1]["close"])


# ============================================================
# TEST DU MODULE
# ============================================================

def test_data_connection(
    symbol: str = "XAU/USD",
) -> dict:
    """
    Teste la récupération des quatre timeframes.

    Retourne un résumé exploitable pour le diagnostic.
    """

    result = {
        "symbol": symbol,
        "success": False,
        "timeframes": {},
        "price": None,
        "error": None,
    }

    try:
        data = get_multi_timeframe_data(symbol)

        for timeframe, candles in data.items():
            result["timeframes"][timeframe] = {
                "count": len(candles),
                "first": candles[0]["datetime"],
                "last": candles[-1]["datetime"],
            }

        result["price"] = get_price(symbol)
        result["success"] = True

    except Exception as exc:
        result["error"] = str(exc)

        logger.exception(
            "Test data.py échoué pour %s",
            symbol,
        )

    return result


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
    print("VISION TRADE AI V2 - TEST DATA.PY")
    print("=" * 60)

    test = test_data_connection("XAU/USD")

    if test["success"]:
        print("\n✅ CONNEXION TWELVE DATA OK")
        print(f"Marché : {test['symbol']}")
        print(f"Prix M5 : {test['price']}")

        for timeframe, info in test["timeframes"].items():
            print(
                f"{timeframe} : "
                f"{info['count']} bougies | "
                f"{info['first']} → {info['last']}"
            )

    else:
        print("\n❌ ÉCHEC DE LA CONNEXION")
        print(f"Erreur : {test['error']}")