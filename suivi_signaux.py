"""
Vision Trade AI V2
suivi_signaux.py

Gestion du suivi des signaux générés.

Responsabilités :
- mémoriser les signaux actifs ;
- suivre leur état ;
- éviter les doublons ;
- enregistrer TP / SL atteints ;
- fournir un historique simple.

IMPORTANT :
- aucune IA ;
- aucun appel API ;
- aucune modification du score ;
- aucune modification du RR.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


logger = logging.getLogger(__name__)


# ============================================================
# CONSTANTES
# ============================================================

ACTIVE = "ACTIVE"
TP1 = "TP1"
TP2 = "TP2"
TP3 = "TP3"
STOP_LOSS = "STOP_LOSS"
CLOSED = "CLOSED"


# ============================================================
# MODÈLE
# ============================================================

@dataclass
class SignalSuivi:
    """
    Représente un signal en cours de suivi.
    """

    signal_id: str
    symbol: str
    direction: str

    entry: float
    stop_loss: float

    tp1: float
    tp2: float
    tp3: float

    score: float
    rr: float

    status: str

    created_at: str
    closed_at: Optional[str] = None

    result: Optional[str] = None


# ============================================================
# OUTILS
# ============================================================

def _now() -> str:
    """
    Retourne l'heure UTC actuelle.
    """

    return datetime.now(
        timezone.utc
    ).isoformat()


def _safe_float(
    value: Any,
    default: float = 0.0,
) -> float:

    try:
        return float(value)

    except (
        TypeError,
        ValueError,
    ):
        return default


# ============================================================
# GESTIONNAIRE
# ============================================================

class SuiviSignaux:
    """
    Gestionnaire des signaux.
    """

    def __init__(self) -> None:

        self.signaux: Dict[
            str,
            SignalSuivi
        ] = {}

        self.historique: List[
            Dict[str, Any]
        ] = []

    # ========================================================
    # AJOUT
    # ========================================================

    def ajouter_signal(
        self,
        signal: Dict[str, Any],
    ) -> SignalSuivi:

        if not isinstance(
            signal,
            dict,
        ):
            raise ValueError(
                "signal doit être un dictionnaire."
            )

        signal_id = str(
            signal.get(
                "signal_id",
                f"{signal.get('symbol', '')}_"
                f"{signal.get('direction', '')}_"
                f"{_now()}",
            )
        )

        objet = SignalSuivi(
            signal_id=signal_id,

            symbol=str(
                signal.get(
                    "symbol",
                    "",
                )
            ),

            direction=str(
                signal.get(
                    "direction",
                    "",
                )
            ).upper(),

            entry=_safe_float(
                signal.get(
                    "entry"
                )
            ),

            stop_loss=_safe_float(
                signal.get(
                    "stop_loss"
                )
            ),

            tp1=_safe_float(
                signal.get(
                    "tp1"
                )
            ),

            tp2=_safe_float(
                signal.get(
                    "tp2"
                )
            ),

            tp3=_safe_float(
                signal.get(
                    "tp3"
                )
            ),

            score=_safe_float(
                signal.get(
                    "score"
                )
            ),

            rr=_safe_float(
                signal.get(
                    "rr"
                )
            ),

            status=ACTIVE,

            created_at=_now(),
        )

        self.signaux[
            signal_id
        ] = objet

        logger.info(
            "Signal ajouté au suivi : %s",
            signal_id,
        )

        return objet

    # ========================================================
    # RÉCUPÉRATION
    # ========================================================

    def obtenir_signal(
        self,
        signal_id: str,
    ) -> Optional[SignalSuivi]:

        return self.signaux.get(
            signal_id
        )

    # ========================================================
    # VÉRIFICATION PRIX
    # ========================================================

    def verifier_prix(
        self,
        signal_id: str,
        price: float,
    ) -> Optional[str]:
        """
        Vérifie si le prix a atteint SL ou TP.
        """

        signal = self.obtenir_signal(
            signal_id
        )

        if signal is None:
            return None

        if signal.status in {
            CLOSED,
            STOP_LOSS,
            TP3,
        }:
            return signal.status

        price = _safe_float(price)

        if price <= 0:
            return None

        # ----------------------------------------------------
        # BUY
        # ----------------------------------------------------

        if signal.direction == "BUY":

            if price <= signal.stop_loss:

                return self.cloturer(
                    signal_id,
                    STOP_LOSS,
                )

            if price >= signal.tp3:

                return self.cloturer(
                    signal_id,
                    TP3,
                )

            if price >= signal.tp2:

                signal.status = TP2

                return TP2

            if price >= signal.tp1:

                signal.status = TP1

                return TP1

        # ----------------------------------------------------
        # SELL
        # ----------------------------------------------------

        elif signal.direction == "SELL":

            if price >= signal.stop_loss:

                return self.cloturer(
                    signal_id,
                    STOP_LOSS,
                )

            if price <= signal.tp3:

                return self.cloturer(
                    signal_id,
                    TP3,
                )

            if price <= signal.tp2:

                signal.status = TP2

                return TP2

            if price <= signal.tp1:

                signal.status = TP1

                return TP1

        return signal.status

    # ========================================================
    # CLÔTURE
    # ========================================================

    def cloturer(
        self,
        signal_id: str,
        result: str,
    ) -> str:

        signal = self.obtenir_signal(
            signal_id
        )

        if signal is None:
            raise ValueError(
                "Signal introuvable."
            )

        signal.status = (
            result
        )

        signal.result = (
            result
        )

        signal.closed_at = _now()

        self.historique.append(
            asdict(signal)
        )

        logger.info(
            "Signal clôturé : %s -> %s",
            signal_id,
            result,
        )

        return result

    # ========================================================
    # SIGNALS ACTIFS
    # ========================================================

    def signaux_actifs(
        self,
    ) -> List[Dict[str, Any]]:

        return [
            asdict(signal)
            for signal in self.signaux.values()
            if signal.status
            not in {
                CLOSED,
                STOP_LOSS,
                TP3,
            }
        ]

    # ========================================================
    # HISTORIQUE
    # ========================================================

    def obtenir_historique(
        self,
    ) -> List[Dict[str, Any]]:

        return list(
            self.historique
        )


# ============================================================
# FONCTION PUBLIQUE
# ============================================================

def creer_suivi() -> SuiviSignaux:
    """
    Crée le gestionnaire de suivi.
    """

    return SuiviSignaux()


# ============================================================
# TEST
# ============================================================

def _run_internal_test() -> None:

    suivi = SuiviSignaux()

    signal = suivi.ajouter_signal(
        {
            "signal_id": "TEST_001",
            "symbol": "XAU/USD",
            "direction": "BUY",
            "entry": 3350,
            "stop_loss": 3340,
            "tp1": 3360,
            "tp2": 3370,
            "tp3": 3380,
            "score": 88,
            "rr": 2,
        }
    )

    assert (
        signal.status
        == ACTIVE
    )

    result = suivi.verifier_prix(
        "TEST_001",
        3360,
    )

    assert result == TP1

    result = suivi.verifier_prix(
        "TEST_001",
        3380,
    )

    assert result == TP3

    logger.info(
        "Test suivi_signaux réussi."
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
    print(
        "VISION TRADE AI V2 - TEST SUIVI SIGNAUX"
    )
    print("=" * 60)

    try:

        _run_internal_test()

        print(
            "\n✅ SUIVI SIGNAUX : OK"
        )

    except Exception as exc:

        print(
            "\n❌ TEST ÉCHOUÉ"
        )

        print(
            f"Erreur : {exc}"
        )