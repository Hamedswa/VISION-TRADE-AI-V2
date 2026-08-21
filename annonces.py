"""
Vision Trade AI V2
annonces.py

Gestion des annonces économiques.

Responsabilités :
- récupérer les événements économiques ;
- normaliser les événements ;
- déterminer leur impact ;
- associer les annonces aux marchés ;
- calculer la proximité temporelle ;
- déterminer si les nouveaux signaux doivent être bloqués.

IMPORTANT :
Ce module ne prend aucune décision BUY/SELL.
Il fournit uniquement un contexte fondamental au moteur.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional

import requests

from config import (
    NEWS_BLOCK_BEFORE_MINUTES,
    NEWS_BLOCK_AFTER_MINUTES,
    NEWS_HIGH_IMPACTS,
)


# ============================================================
# LOGGING
# ============================================================

logger = logging.getLogger(__name__)


# ============================================================
# CONSTANTES
# ============================================================

REQUEST_TIMEOUT = 15
MAX_RETRIES = 3

NEWS_NORMAL = "NORMAL"
NEWS_CAUTION = "PRUDENCE"
NEWS_BLOCKED = "BLOQUÉ"

IMPACT_LOW = "low"
IMPACT_MEDIUM = "medium"
IMPACT_HIGH = "high"

SUPPORTED_CURRENCIES = {
    "USD",
    "EUR",
    "GBP",
    "JPY",
    "AUD",
    "CAD",
    "CHF",
    "NZD",
}


# ============================================================
# MARCHÉS ET DEVISES
# ============================================================

MARKET_CURRENCIES = {
    "XAU/USD": {"USD"},
    "EUR/USD": {"EUR", "USD"},
    "GBP/USD": {"GBP", "USD"},
    "USD/JPY": {"USD", "JPY"},
    "AUD/USD": {"AUD", "USD"},
    "USD/CAD": {"USD", "CAD"},
    "USD/CHF": {"USD", "CHF"},
    "NZD/USD": {"NZD", "USD"},
    "BTC/USD": {"USD"},
}


# ============================================================
# MODÈLE D'ÉVÉNEMENT
# ============================================================

@dataclass
class EconomicEvent:
    """
    Représente une annonce économique normalisée.
    """

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

        return normalize_impact(self.impact) == IMPACT_HIGH


# ============================================================
# OUTILS DATETIME
# ============================================================

def _ensure_utc(value: datetime) -> datetime:
    """
    Rend un datetime timezone-aware en UTC.
    """

    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)

    return value.astimezone(timezone.utc)


def parse_datetime(value: Any) -> Optional[datetime]:
    """
    Convertit différents formats de date en datetime UTC.
    """

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
        text = text[:-1] + "+00:00"

    try:
        parsed = datetime.fromisoformat(text)
        return _ensure_utc(parsed)
    except ValueError:
        pass

    # Formats courants.
    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
    ]

    for fmt in formats:
        try:
            parsed = datetime.strptime(text, fmt)
            return parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            continue

    return None


# ============================================================
# NORMALISATION IMPACT
# ============================================================

def normalize_impact(value: Any) -> str:
    """
    Convertit les différentes représentations d'impact
    vers low / medium / high.
    """

    if value is None:
        return IMPACT_LOW

    text = str(value).strip().lower()

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


# ============================================================
# NORMALISATION DEVISE
# ============================================================

def normalize_currency(value: Any) -> str:
    """
    Normalise une devise.
    """

    if value is None:
        return ""

    text = str(value).strip().upper()

    # Quelques variantes fréquentes.
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

    return aliases.get(text, text)


# ============================================================
# NORMALISATION ÉVÉNEMENT
# ============================================================

def normalize_event(
    raw: Dict[str, Any],
    source: str = "",
) -> Optional[EconomicEvent]:
    """
    Transforme un événement provenant d'une API externe
    en EconomicEvent standardisé.

    Cette fonction accepte plusieurs noms de champs afin
    de faciliter l'intégration avec différents fournisseurs.
    """

    if not isinstance(raw, dict):
        return None

    event_id = (
        raw.get("id")
        or raw.get("event_id")
        or raw.get("eventId")
        or ""
    )

    title = (
        raw.get("title")
        or raw.get("event")
        or raw.get("name")
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

    date_value = (
        raw.get("timestamp")
        or raw.get("datetime")
        or raw.get("date")
        or raw.get("time")
    )

    timestamp = parse_datetime(date_value)

    if not timestamp:
        return None

    if not currency or currency not in SUPPORTED_CURRENCIES:
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
        event_id=str(event_id),
        title=str(title),
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
        raw=dict(raw),
    )


def _safe_float(value: Any) -> Optional[float]:
    """
    Convertit une valeur en float sans provoquer d'exception.
    """

    if value in (None, "", "N/A", "n/a", "-"):
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


# ============================================================
# FOURNISSEUR D'ANNONCES
# ============================================================

class NewsProvider:
    """
    Interface de base pour un fournisseur d'annonces.

    Un fournisseur réel pourra être branché ici sans modifier
    le reste du moteur.
    """

    name = "base"

    def get_events(
        self,
        start: datetime,
        end: datetime,
    ) -> List[EconomicEvent]:
        raise NotImplementedError


class HTTPNewsProvider(NewsProvider):
    """
    Fournisseur générique HTTP.

    Il est volontairement configurable afin de ne pas
    verrouiller Vision Trade AI V2 sur une API inventée.

    L'URL et les paramètres seront définis lorsque le
    fournisseur économique réel sera choisi.
    """

    name = "http"

    def __init__(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ):
        if not url:
            raise ValueError(
                "L'URL du fournisseur d'annonces est obligatoire."
            )

        self.url = url
        self.params = params or {}
        self.headers = headers or {}

    def get_events(
        self,
        start: datetime,
        end: datetime,
    ) -> List[EconomicEvent]:

        params = dict(self.params)

        params.setdefault(
            "start",
            _ensure_utc(start).isoformat(),
        )

        params.setdefault(
            "end",
            _ensure_utc(end).isoformat(),
        )

        last_error = None

        for attempt in range(1, MAX_RETRIES + 1):

            try:
                response = requests.get(
                    self.url,
                    params=params,
                    headers=self.headers,
                    timeout=REQUEST_TIMEOUT,
                )

                response.raise_for_status()

                payload = response.json()

                raw_events = _extract_event_list(payload)

                events = []

                for raw_event in raw_events:
                    event = normalize_event(
                        raw_event,
                        source=self.name,
                    )

                    if event:
                        events.append(event)

                return events

            except (
                requests.RequestException,
                ValueError,
            ) as exc:

                last_error = exc

                logger.warning(
                    "Erreur fournisseur news "
                    "(tentative %s/%s) : %s",
                    attempt,
                    MAX_RETRIES,
                    exc,
                )

        raise RuntimeError(
            "Impossible de récupérer les annonces : "
            f"{last_error}"
        )


def _extract_event_list(payload: Any) -> List[dict]:
    """
    Extrait une liste d'événements depuis différentes structures
    JSON courantes.
    """

    if isinstance(payload, list):
        return [
            item
            for item in payload
            if isinstance(item, dict)
        ]

    if not isinstance(payload, dict):
        return []

    for key in (
        "events",
        "data",
        "results",
        "calendar",
    ):
        value = payload.get(key)

        if isinstance(value, list):
            return [
                item
                for item in value
                if isinstance(item, dict)
            ]

    return []


# ============================================================
# MOTEUR DES ANNONCES
# ============================================================

class NewsManager:
    """
    Moteur central de gestion des annonces.

    Il ne décide jamais BUY ou SELL.
    Il décide uniquement du niveau de risque lié aux annonces.
    """

    def __init__(
        self,
        provider: Optional[NewsProvider] = None,
    ):
        self.provider = provider
        self.events: List[EconomicEvent] = []

    # --------------------------------------------------------
    # Chargement
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
            key=lambda event: event.timestamp
        )

        self.events = events

        return list(events)

    # --------------------------------------------------------
    # Recherche marché
    # --------------------------------------------------------

    def get_market_events(
        self,
        symbol: str,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> List[EconomicEvent]:
        """
        Retourne les annonces concernant directement
        le marché demandé.
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

            if start and event.timestamp < _ensure_utc(start):
                continue

            if end and event.timestamp > _ensure_utc(end):
                continue

            result.append(event)

        return result

    # --------------------------------------------------------
    # Événement proche
    # --------------------------------------------------------

    def get_nearby_events(
        self,
        symbol: str,
        now: Optional[datetime] = None,
    ) -> List[EconomicEvent]:
        """
        Retourne les événements situés dans la fenêtre
        de protection avant/après publication.
        """

        if now is None:
            now = datetime.now(timezone.utc)

        now = _ensure_utc(now)

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
    # État
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
            annonce importante mais hors fenêtre
            de blocage stricte.

        BLOQUÉ :
            annonce majeure imminente ou récemment publiée.
        """

        if now is None:
            now = datetime.now(timezone.utc)

        now = _ensure_utc(now)

        currencies = MARKET_CURRENCIES.get(
            symbol.upper().strip(),
            set(),
        )

        if not currencies:
            return {
                "status": NEWS_NORMAL,
                "blocked": False,
                "symbol": symbol,
                "reason": "Marché non associé à un calendrier news.",
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

            minutes = event.minutes_to_event(now)

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
                key=lambda item: abs(
                    item["minutes_to_event"]
                ),
            )

            event = closest["event"]

            if closest["minutes_to_event"] > 0:
                reason = (
                    f"Annonce majeure imminente : "
                    f"{event.title} ({event.currency})"
                )
            else:
                reason = (
                    f"Annonce majeure récente : "
                    f"{event.title} ({event.currency})"
                )

            return {
                "status": NEWS_BLOCKED,
                "blocked": True,
                "symbol": symbol,
                "reason": reason,
                "event": event,
                "minutes_to_event": (
                    closest["minutes_to_event"]
                ),
                "events": [
                    item["event"]
                    for item in blocked_events
                ],
            }

        # Une annonce high impact dans une fenêtre plus large
        # déclenche un état de prudence.
        upcoming = []

        for event in high_events:

            minutes = event.minutes_to_event(now)

            if 0 < minutes <= 120:
                upcoming.append(
                    {
                        "event": event,
                        "minutes_to_event": minutes,
                    }
                )

        if upcoming:

            closest = min(
                upcoming,
                key=lambda item: item["minutes_to_event"],
            )

            event = closest["event"]

            return {
                "status": NEWS_CAUTION,
                "blocked": False,
                "symbol": symbol,
                "reason": (
                    f"Annonce majeure à venir : "
                    f"{event.title} ({event.currency})"
                ),
                "event": event,
                "minutes_to_event": (
                    closest["minutes_to_event"]
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
            "reason": "Aucune annonce majeure proche.",
            "events": [],
        }


# ============================================================
# FONCTIONS SIMPLES
# ============================================================

def market_currencies(symbol: str) -> set[str]:
    """
    Retourne les devises associées à un marché.
    """

    return MARKET_CURRENCIES.get(
        symbol.upper().strip(),
        set(),
    ).copy()


def is_market_blocked(
    symbol: str,
    events: Iterable[EconomicEvent],
    now: Optional[datetime] = None,
) -> bool:
    """
    Fonction pratique permettant de vérifier rapidement
    si un marché est bloqué par une annonce majeure.
    """

    manager = NewsManager()
    manager.events = list(events)

    return bool(
        manager.get_status(
            symbol=symbol,
            now=now,
        )["blocked"]
    )


# ============================================================
# TEST LOCAL DU MODULE
# ============================================================

def _test_with_fake_events() -> None:
    """
    Test interne sans API externe.

    Ce test permet de vérifier la logique du filtre news
    avant même de brancher le fournisseur réel.
    """

    now = datetime.now(timezone.utc)

    fake_event = EconomicEvent(
        event_id="TEST-001",
        title="Test USD High Impact",
        currency="USD",
        impact=IMPACT_HIGH,
        timestamp=now + timedelta(minutes=10),
        source="internal-test",
    )

    manager = NewsManager()
    manager.events = [fake_event]

    status = manager.get_status(
        symbol="XAU/USD",
        now=now,
    )

    assert status["blocked"] is True
    assert status["status"] == NEWS_BLOCKED

    logger.info(
        "Test news interne réussi : %s",
        status["reason"],
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
    print("VISION TRADE AI V2 - TEST ANNONCES")
    print("=" * 60)

    try:
        _test_with_fake_events()

        print("\n✅ LOGIQUE DU MODULE ANNONCES : OK")
        print(
            "Le test a confirmé qu'une annonce USD majeure "
            "à 10 minutes bloque XAU/USD."
        )

    except Exception as exc:

        print("\n❌ TEST ANNONCES ÉCHOUÉ")
        print(f"Erreur : {exc}")