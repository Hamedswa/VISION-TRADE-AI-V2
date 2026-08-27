“””
Vision Trade AI V2
annonces.py

Gestion des annonces économiques avec SiftingIO.

Responsabilités :

* récupérer les événements économiques ;
* normaliser les événements ;
* déterminer leur impact ;
* associer les annonces aux marchés ;
* calculer la proximité temporelle ;
* déterminer si les nouveaux signaux doivent être bloqués.

IMPORTANT :
Ce module ne prend aucune décision BUY/SELL.
Il fournit uniquement un contexte fondamental au moteur.

Fournisseur :
SiftingIO Economic Calendar API

Variable d’environnement :
NEWS_API_KEY
“””

from future import annotations

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional

import requests

from config import (
NEWS_BLOCK_BEFORE_MINUTES,
NEWS_BLOCK_AFTER_MINUTES,
NEWS_HIGH_IMPACTS,
)

============================================================

LOGGING

============================================================

logger = logging.getLogger(name)

============================================================

CONSTANTES

============================================================

REQUEST_TIMEOUT = 15
MAX_RETRIES = 3

SIFTING_API_URL = (
“https://api.sifting.io/v1/fnd/economic-calendar”
)

NEWS_API_KEY_ENV = “NEWS_API_KEY”

NEWS_NORMAL = “NORMAL”
NEWS_CAUTION = “PRUDENCE”
NEWS_BLOCKED = “BLOQUÉ”

IMPACT_LOW = “low”
IMPACT_MEDIUM = “medium”
IMPACT_HIGH = “high”

SUPPORTED_CURRENCIES = {
“USD”,
“EUR”,
“GBP”,
“JPY”,
“AUD”,
“CAD”,
“CHF”,
“NZD”,
}

============================================================

MARCHÉS ET DEVISES

============================================================

MARKET_CURRENCIES = {
“XAU/USD”: {“USD”},
“EUR/USD”: {“EUR”, “USD”},
“GBP/USD”: {“GBP”, “USD”},
“USD/JPY”: {“USD”, “JPY”},
“AUD/USD”: {“AUD”, “USD”},
“USD/CAD”: {“USD”, “CAD”},
“USD/CHF”: {“USD”, “CHF”},
“NZD/USD”: {“NZD”, “USD”},
“BTC/USD”: {“USD”},
}

============================================================

MODÈLE D’ÉVÉNEMENT

============================================================

@dataclass
class EconomicEvent:
“””
Représente une annonce économique normalisée.
“””

event_id: str
title: str
currency: str
impact: str
timestamp: datetime
actual: Optional[float] = None
forecast: Optional[float] = None
previous: Optional[float] = None
source: str = ""
raw: Dict[str, Any] = field(default_factory=dict)
def minutes_to_event(
    self,
    now: Optional[datetime] = None,
) -> float:
    """
    Retourne le nombre de minutes avant l'événement.
    Résultat négatif = événement déjà passé.
    """
    if now is None:
        now = datetime.now(timezone.utc)
    now = _ensure_utc(now)
    return (
        self.timestamp - now
    ).total_seconds() / 60.0
def is_high_impact(self) -> bool:
    """
    Détermine si l'événement est fortement impactant.
    """
    return normalize_impact(
        self.impact
    ) == IMPACT_HIGH

============================================================

OUTILS DATETIME

============================================================

def _ensure_utc(value: datetime) -> datetime:
“””
Rend un datetime timezone-aware en UTC.
“””

if value.tzinfo is None:
    return value.replace(
        tzinfo=timezone.utc
    )
return value.astimezone(
    timezone.utc
)

def parse_datetime(
value: Any,
) -> Optional[datetime]:
“””
Convertit différents formats de date
en datetime UTC.
“””

if value is None:
    return None
if isinstance(value, datetime):
    return _ensure_utc(value)
if not isinstance(value, str):
    return None
text = value.strip()
if not text:
    return None
# ISO 8601 avec Z.
if text.endswith("Z"):
    text = (
        text[:-1]
        + "+00:00"
    )
try:
    parsed = datetime.fromisoformat(
        text
    )
    return _ensure_utc(
        parsed
    )
except ValueError:
    pass
formats = [
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%Y-%m-%d",
]
for fmt in formats:
    try:
        parsed = datetime.strptime(
            text,
            fmt,
        )
        return parsed.replace(
            tzinfo=timezone.utc
        )
    except ValueError:
        continue
return None

============================================================

NORMALISATION IMPACT

============================================================

def normalize_impact(
value: Any,
) -> str:
“””
Convertit les différentes représentations
d’impact vers low / medium / high.
“””

if value is None:
    return IMPACT_LOW
text = str(
    value
).strip().lower()
if text in {
    "high",
    "3",
    "major",
    "important",
    "red",
    "3.0",
}:
    return IMPACT_HIGH
if text in {
    "medium",
    "med",
    "2",
    "moderate",
    "orange",
    "2.0",
}:
    return IMPACT_MEDIUM
return IMPACT_LOW

============================================================

NORMALISATION DEVISE

============================================================

def normalize_currency(
value: Any,
) -> str:
“””
Normalise une devise.
“””

if value is None:
    return ""
text = str(
    value
).strip().upper()
aliases = {
    "US DOLLAR": "USD",
    "DOLLAR": "USD",
    "EURO": "EUR",
    "POUND": "GBP",
    "POUND STERLING": "GBP",
    "YEN": "JPY",
    "AUSTRALIAN DOLLAR": "AUD",
    "CANADIAN DOLLAR": "CAD",
    "SWISS FRANC": "CHF",
    "NEW ZEALAND DOLLAR": "NZD",
}
return aliases.get(
    text,
    text,
)

============================================================

UTILITAIRE FLOAT

============================================================

def _safe_float(
value: Any,
) -> Optional[float]:
“””
Convertit une valeur en float sans exception.
“””

if value in (
    None,
    "",
    "N/A",
    "n/a",
    "-",
):
    return None
try:
    return float(
        value
    )
except (
    TypeError,
    ValueError,
):
    return None

============================================================

NORMALISATION ÉVÉNEMENT

============================================================

def normalize_event(
raw: Dict[str, Any],
source: str = “”,
) -> Optional[EconomicEvent]:
“””
Transforme un événement externe
en EconomicEvent standardisé.

Compatible avec SiftingIO :
    event_id
    name
    currency
    impact
    scheduled_at
    actual
    consensus
    previous
"""
if not isinstance(
    raw,
    dict,
):
    return None
event_id = (
    raw.get("event_id")
    or raw.get("id")
    or raw.get("eventId")
    or ""
)
title = (
    raw.get("name")
    or raw.get("title")
    or raw.get("event")
    or raw.get("description")
    or ""
)
currency = normalize_currency(
    raw.get("currency")
    or raw.get("country_currency")
    or raw.get("code")
)
impact = normalize_impact(
    raw.get("impact")
    or raw.get("importance")
    or raw.get("priority")
)
timestamp_value = (
    raw.get("scheduled_at")
    or raw.get("timestamp")
    or raw.get("datetime")
    or raw.get("date")
    or raw.get("time")
)
timestamp = parse_datetime(
    timestamp_value
)
if not timestamp:
    return None
if (
    not currency
    or currency not in SUPPORTED_CURRENCIES
):
    return None
if not title:
    title = "Economic event"
if not event_id:
    event_id = (
        f"{currency}-"
        f"{timestamp.isoformat()}-"
        f"{title}"
    )
return EconomicEvent(
    event_id=str(
        event_id
    ),
    title=str(
        title
    ),
    currency=currency,
    impact=impact,
    timestamp=timestamp,
    actual=_safe_float(
        raw.get("actual")
    ),
    forecast=_safe_float(
        raw.get("forecast")
        or raw.get("consensus")
    ),
    previous=_safe_float(
        raw.get("previous")
    ),
    source=source,
    raw=dict(
        raw
    ),
)

============================================================

EXTRACTION RÉPONSE API

============================================================

def _extract_event_list(
payload: Any,
) -> List[dict]:
“””
Extrait les événements de plusieurs formats JSON.

SiftingIO peut retourner les événements dans :
    events
ou :
    data
On accepte également :
    results
    calendar
"""
if isinstance(
    payload,
    list,
):
    return [
        item
        for item in payload
        if isinstance(
            item,
            dict,
        )
    ]
if not isinstance(
    payload,
    dict,
):
    return []
for key in (
    "events",
    "data",
    "results",
    "calendar",
):
    value = payload.get(
        key
    )
    if isinstance(
        value,
        list,
    ):
        return [
            item
            for item in value
            if isinstance(
                item,
                dict,
            )
        ]
return []

============================================================

FOURNISSEUR DE BASE

============================================================

class NewsProvider:
“””
Interface de base pour un fournisseur d’annonces.
“””

name = "base"
def get_events(
    self,
    start: datetime,
    end: datetime,
) -> List[EconomicEvent]:
    raise NotImplementedError

============================================================

SIFTINGIO

============================================================

class SiftingIONewsProvider(
NewsProvider
):
“””
Fournisseur officiel SiftingIO.

Authentification :
    NEWS_API_KEY
Endpoint :
    /v1/fnd/economic-calendar
"""
name = "siftingio"
def __init__(
    self,
    api_key: Optional[str] = None,
):
    self.api_key = (
        api_key
        or os.getenv(
            NEWS_API_KEY_ENV
        )
    )
    if not self.api_key:
        raise ValueError(
            "NEWS_API_KEY est absente."
        )
def get_events(
    self,
    start: datetime,
    end: datetime,
) -> List[EconomicEvent]:
    start = _ensure_utc(
        start
    )
    end = _ensure_utc(
        end
    )
    headers = {
        "X-API-Key": self.api_key,
        "Accept": "application/json",
    }
    params = {
        "from": start.date().isoformat(),
        "to": end.date().isoformat(),
        "limit": 200,
    }
    last_error = None
    for attempt in range(
        1,
        MAX_RETRIES + 1,
    ):
        try:
            response = requests.get(
                SIFTING_API_URL,
                headers=headers,
                params=params,
                timeout=REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            payload = response.json()
            raw_events = (
                _extract_event_list(
                    payload
                )
            )
            events = []
            for raw_event in raw_events:
                event = normalize_event(
                    raw_event,
                    source=self.name,
                )
                if event:
                    # On garde uniquement
                    # la période demandée.
                    if (
                        start
                        <= event.timestamp
                        <= end
                    ):
                        events.append(
                            event
                        )
            logger.info(
                "SiftingIO : %s annonce(s) récupérée(s).",
                len(events),
            )
            return events
        except (
            requests.RequestException,
            ValueError,
        ) as exc:
            last_error = exc
            logger.warning(
                "Erreur SiftingIO "
                "(tentative %s/%s) : %s",
                attempt,
                MAX_RETRIES,
                exc,
            )
    raise RuntimeError(
        "Impossible de récupérer les annonces "
        f"depuis SiftingIO : {last_error}"
    )

============================================================

MOTEUR DES ANNONCES

============================================================

class NewsManager:
“””
Moteur central de gestion des annonces.

Il ne décide jamais BUY ou SELL.
Il décide uniquement du niveau de risque
lié aux annonces.
"""
def __init__(
    self,
    provider: Optional[NewsProvider] = None,
):
    self.provider = provider
    self.events: List[
        EconomicEvent
    ] = []
# --------------------------------------------------------
# CHARGEMENT
# --------------------------------------------------------
def load_events(
    self,
    start: datetime,
    end: datetime,
) -> List[EconomicEvent]:
    """
    Charge les annonces sur une période.
    """
    if self.provider is None:
        logger.warning(
            "Aucun fournisseur d'annonces configuré."
        )
        self.events = []
        return []
    events = self.provider.get_events(
        start=_ensure_utc(start),
        end=_ensure_utc(end),
    )
    events.sort(
        key=lambda event:
        event.timestamp
    )
    self.events = events
    return list(
        events
    )
# --------------------------------------------------------
# RECHERCHE MARCHÉ
# --------------------------------------------------------
def get_market_events(
    self,
    symbol: str,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
) -> List[EconomicEvent]:
    """
    Retourne les annonces concernant
    directement le marché demandé.
    """
    currencies = MARKET_CURRENCIES.get(
        symbol.upper().strip(),
        set(),
    )
    if not currencies:
        return []
    result = []
    for event in self.events:
        if event.currency not in currencies:
            continue
        if (
            start
            and event.timestamp
            < _ensure_utc(start)
        ):
            continue
        if (
            end
            and event.timestamp
            > _ensure_utc(end)
        ):
            continue
        result.append(
            event
        )
    return result
# --------------------------------------------------------
# ÉVÉNEMENTS PROCHES
# --------------------------------------------------------
def get_nearby_events(
    self,
    symbol: str,
    now: Optional[datetime] = None,
) -> List[EconomicEvent]:
    """
    Retourne les événements HIGH situés
    dans la fenêtre de protection.
    """
    if now is None:
        now = datetime.now(
            timezone.utc
        )
    now = _ensure_utc(
        now
    )
    before = timedelta(
        minutes=NEWS_BLOCK_BEFORE_MINUTES
    )
    after = timedelta(
        minutes=NEWS_BLOCK_AFTER_MINUTES
    )
    start = now - after
    end = now + before
    events = self.get_market_events(
        symbol=symbol,
        start=start,
        end=end,
    )
    return [
        event
        for event in events
        if event.is_high_impact()
    ]
# --------------------------------------------------------
# ÉTAT DU MARCHÉ
# --------------------------------------------------------
def get_status(
    self,
    symbol: str,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """
    Détermine l'état fondamental du marché.
    NORMAL :
        aucune annonce majeure proche.
    PRUDENCE :
        annonce majeure à venir mais
        hors fenêtre stricte.
    BLOQUÉ :
        annonce majeure imminente
        ou récemment publiée.
    """
    if now is None:
        now = datetime.now(
            timezone.utc
        )
    now = _ensure_utc(
        now
    )
    currencies = MARKET_CURRENCIES.get(
        symbol.upper().strip(),
        set(),
    )
    if not currencies:
        return {
            "status": NEWS_NORMAL,
            "blocked": False,
            "symbol": symbol,
            "reason": (
                "Marché non associé "
                "à un calendrier news."
            ),
            "events": [],
        }
    relevant_events = [
        event
        for event in self.events
        if event.currency in currencies
    ]
    high_events = [
        event
        for event in relevant_events
        if event.is_high_impact()
    ]
    blocked_events = []
    for event in high_events:
        minutes = (
            event.minutes_to_event(
                now
            )
        )
        if (
            -NEWS_BLOCK_AFTER_MINUTES
            <= minutes
            <= NEWS_BLOCK_BEFORE_MINUTES
        ):
            blocked_events.append(
                {
                    "event": event,
                    "minutes_to_event": minutes,
                }
            )
    if blocked_events:
        closest = min(
            blocked_events,
            key=lambda item:
            abs(
                item[
                    "minutes_to_event"
                ]
            ),
        )
        event = closest[
            "event"
        ]
        minutes = closest[
            "minutes_to_event"
        ]
        if minutes > 0:
            reason = (
                f"Annonce majeure imminente : "
                f"{event.title} "
                f"({event.currency})"
            )
        else:
            reason = (
                f"Annonce majeure récente : "
                f"{event.title} "
                f"({event.currency})"
            )
        return {
            "status": NEWS_BLOCKED,
            "blocked": True,
            "symbol": symbol,
            "reason": reason,
            "event": event,
            "minutes_to_event": minutes,
            "events": [
                item["event"]
                for item in blocked_events
            ],
        }
    # Fenêtre de prudence de 120 minutes.
    upcoming = []
    for event in high_events:
        minutes = (
            event.minutes_to_event(
                now
            )
        )
        if (
            0
            < minutes
            <= 120
        ):
            upcoming.append(
                {
                    "event": event,
                    "minutes_to_event": minutes,
                }
            )
    if upcoming:
        closest = min(
            upcoming,
            key=lambda item:
            item[
                "minutes_to_event"
            ],
        )
        event = closest[
            "event"
        ]
        return {
            "status": NEWS_CAUTION,
            "blocked": False,
            "symbol": symbol,
            "reason": (
                f"Annonce majeure à venir : "
                f"{event.title} "
                f"({event.currency})"
            ),
            "event": event,
            "minutes_to_event": (
                closest[
                    "minutes_to_event"
                ]
            ),
            "events": [
                item["event"]
                for item in upcoming
            ],
        }
    return {
        "status": NEWS_NORMAL,
        "blocked": False,
        "symbol": symbol,
        "reason": (
            "Aucune annonce majeure proche."
        ),
        "events": [],
    }

============================================================

FONCTIONS SIMPLES

============================================================

def market_currencies(
symbol: str,
) -> set[str]:
“””
Retourne les devises associées à un marché.
“””

return MARKET_CURRENCIES.get(
    symbol.upper().strip(),
    set(),
).copy()

def is_market_blocked(
symbol: str,
events: Iterable[EconomicEvent],
now: Optional[datetime] = None,
) -> bool:
“””
Vérifie rapidement si un marché
est bloqué par une annonce majeure.
“””

manager = NewsManager()
manager.events = list(
    events
)
return bool(
    manager.get_status(
        symbol=symbol,
        now=now,
    )["blocked"]
)

============================================================

TEST API SIFTINGIO

============================================================

def _test_siftingio() -> None:
“””
Test réel de connexion SiftingIO.

Utilise NEWS_API_KEY depuis l'environnement.
Aucune clé n'est affichée.
"""
api_key = os.getenv(
    NEWS_API_KEY_ENV
)
if not api_key:
    raise RuntimeError(
        "NEWS_API_KEY absente."
    )
provider = SiftingIONewsProvider(
    api_key=api_key
)
now = datetime.now(
    timezone.utc
)
end = (
    now
    + timedelta(days=7)
)
events = provider.get_events(
    start=now,
    end=end,
)
print(
    f"Connexion SiftingIO : OK"
)
print(
    f"Événements récupérés : "
    f"{len(events)}"
)
high_events = [
    event
    for event in events
    if event.is_high_impact()
]
print(
    f"Événements HIGH : "
    f"{len(high_events)}"
)
for event in high_events[:10]:
    minutes = (
        event.minutes_to_event(
            now
        )
    )
    print(
        f"- {event.title} | "
        f"{event.currency} | "
        f"{event.impact} | "
        f"{minutes:.0f} min"
    )

============================================================

TEST LOGIQUE SANS API

============================================================

def _test_with_fake_events() -> None:
“””
Test interne sans API externe.
“””

now = datetime.now(
    timezone.utc
)
fake_event = EconomicEvent(
    event_id="TEST-001",
    title="Test USD High Impact",
    currency="USD",
    impact=IMPACT_HIGH,
    timestamp=(
        now
        + timedelta(
            minutes=10
        )
    ),
    source="internal-test",
)
manager = NewsManager()
manager.events = [
    fake_event
]
status = manager.get_status(
    symbol="XAU/USD",
    now=now,
)
assert (
    status["blocked"]
    is True
)
assert (
    status["status"]
    == NEWS_BLOCKED
)
logger.info(
    "Test logique annonces réussi : %s",
    status["reason"],
)

============================================================

EXÉCUTION DIRECTE

============================================================

if name == “main”:

logging.basicConfig(
    level=logging.INFO,
    format=(
        "%(asctime)s | %(levelname)s | "
        "%(name)s | %(message)s"
    ),
)
print("=" * 60)
print(
    "VISION TRADE AI V2 - TEST ANNONCES"
)
print("=" * 60)
try:
    # Test logique local.
    _test_with_fake_events()
    print(
        "\n✅ LOGIQUE ANNONCES : OK"
    )
    # Test réel SiftingIO.
    _test_siftingio()
    print(
        "\n✅ SIFTINGIO : CONNEXION OK"
    )
    print(
        "\n✅ MODULE ANNONCES : OPÉRATIONNEL"
    )
except Exception as exc:
    print(
        "\n❌ TEST ANNONCES ÉCHOUÉ"
    )
    print(
        f"Erreur : {exc}"
    )