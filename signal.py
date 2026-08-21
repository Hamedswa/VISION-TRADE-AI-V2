"""
Vision Trade AI V2
signal.py

Générateur déterministe de signal.

Responsabilités :
- transformer une analyse validée en signal exploitable ;
- vérifier ACCEPT / REJECT / WAIT ;
- récupérer Entry / SL / TP ;
- construire le message structuré ;
- ne prendre aucune décision avec l'IA.

IMPORTANT :
- aucune API ;
- aucune décision Groq ;
- aucune modification du score ;
- aucune modification du RR ;
- aucun envoi Telegram.
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

ACCEPT = "ACCEPT"
REJECT = "REJECT"
WAIT = "WAIT"


# ============================================================
# MODÈLE
# ============================================================

@dataclass
class SignalResult:
    """
    Signal final structuré.
    """

    status: str
    symbol: str
    direction: str

    entry: float
    stop_loss: float

    tp1: float
    tp2: float
    tp3: float

    score: float
    rr: float
    quality: str

    ready: bool

    message: str


# ============================================================
# OUTILS
# ============================================================

def _safe_float(
    value: Any,
    default: float = 0.0,
) -> float:
    """
    Conversion numérique sécurisée.
    """

    if value is None:
        return default

    try:
        return float(value)

    except (
        TypeError,
        ValueError,
    ):
        return default


def _normalize_direction(
    direction: Any,
) -> str:
    """
    Normalise BUY / SELL.
    """

    value = str(
        direction or ""
    ).upper().strip()

    if value not in {
        BUY,
        SELL,
    }:
        raise ValueError(
            "Direction invalide. "
            "Utiliser BUY ou SELL."
        )

    return value


# ============================================================
# VALIDATION
# ============================================================

def valider_analyse(
    analysis: Dict[str, Any],
) -> bool:
    """
    Vérifie qu'une analyse peut produire un signal.
    """

    if not isinstance(
        analysis,
        dict,
    ):
        return False

    if analysis.get(
        "status"
    ) != ACCEPT:

        return False

    if analysis.get(
        "ready_for_signal"
    ) is not True:

        return False

    return True


# ============================================================
# EXTRACTION
# ============================================================

def extraire_donnees_signal(
    analysis: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Extrait les données nécessaires au signal.
    """

    score_data = analysis.get(
        "score",
        {},
    )

    rr_data = analysis.get(
        "rr",
        {},
    )

    quality_data = analysis.get(
        "quality",
        {},
    )

    return {
        "symbol": analysis.get(
            "symbol",
            "",
        ),

        "direction": analysis.get(
            "direction",
            "",
        ),

        "entry": _safe_float(
            analysis.get(
                "entry",
                rr_data.get(
                    "entry",
                    0,
                ),
            )
        ),

        "stop_loss": _safe_float(
            analysis.get(
                "stop_loss",
                rr_data.get(
                    "stop_loss",
                    0,
                ),
            )
        ),

        "tp1": _safe_float(
            rr_data.get(
                "tp1",
                0,
            )
        ),

        "tp2": _safe_float(
            rr_data.get(
                "tp2",
                0,
            )
        ),

        "tp3": _safe_float(
            rr_data.get(
                "tp3",
                0,
            )
        ),

        "score": _safe_float(
            score_data.get(
                "final_score",
                score_data.get(
                    "score",
                    0,
                ),
            )
        ),

        "rr": _safe_float(
            rr_data.get(
                "rr_tp2",
                rr_data.get(
                    "rr",
                    0,
                ),
            )
        ),

        "quality": quality_data.get(
            "quality",
            "UNKNOWN",
        ),
    }


# ============================================================
# FORMATAGE
# ============================================================

def formater_prix(
    value: float,
) -> str:
    """
    Formate proprement un prix.
    """

    if value <= 0:
        return "N/A"

    return f"{value:.5f}".rstrip(
        "0"
    ).rstrip(".")


def construire_message(
    data: Dict[str, Any],
) -> str:
    """
    Construit le message texte du signal.

    Ce message pourra ensuite être envoyé par annonces.py
    ou par le module Telegram.
    """

    direction = data[
        "direction"
    ]

    symbol = data[
        "symbol"
    ]

    entry = formater_prix(
        data["entry"]
    )

    stop_loss = formater_prix(
        data["stop_loss"]
    )

    tp1 = formater_prix(
        data["tp1"]
    )

    tp2 = formater_prix(
        data["tp2"]
    )

    tp3 = formater_prix(
        data["tp3"]
    )

    score = data[
        "score"
    ]

    rr = data[
        "rr"
    ]

    quality = data[
        "quality"
    ]

    return (
        "🚨 VISION TRADE AI V2\n"
        "\n"
        f"📊 {symbol}\n"
        f"📌 Direction : {direction}\n"
        "\n"
        f"🎯 Entry : {entry}\n"
        f"🛑 Stop Loss : {stop_loss}\n"
        "\n"
        f"💰 TP1 : {tp1}\n"
        f"💰 TP2 : {tp2}\n"
        f"💰 TP3 : {tp3}\n"
        "\n"
        f"📈 Score : {score:.0f}/100\n"
        f"⚖️ RR : {rr:.2f}\n"
        f"🏆 Qualité : {quality}\n"
        "\n"
        "✅ Setup validé."
    )


# ============================================================
# GÉNÉRATION
# ============================================================

def generer_signal(
    analysis: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Génère un signal uniquement si l'analyse est ACCEPT.
    """

    if not isinstance(
        analysis,
        dict,
    ):
        raise ValueError(
            "analysis doit être un dictionnaire."
        )

    status = analysis.get(
        "status"
    )

    symbol = analysis.get(
        "symbol",
        "",
    )

    direction = analysis.get(
        "direction",
        "",
    )

    # --------------------------------------------------------
    # REJECT / WAIT
    # --------------------------------------------------------

    if status != ACCEPT:

        return {
            "status": status
            or REJECT,

            "symbol": symbol,

            "direction": direction,

            "ready": False,

            "message": (
                "Aucun signal généré : "
                f"statut {status or REJECT}."
            ),
        }

    if not valider_analyse(
        analysis
    ):

        return {
            "status": REJECT,

            "symbol": symbol,

            "direction": direction,

            "ready": False,

            "message": (
                "Analyse non validée "
                "pour génération du signal."
            ),
        }

    # --------------------------------------------------------
    # DONNÉES
    # --------------------------------------------------------

    data = extraire_donnees_signal(
        analysis
    )

    data["direction"] = (
        _normalize_direction(
            data["direction"]
        )
    )

    # --------------------------------------------------------
    # VALIDATION PRIX
    # --------------------------------------------------------

    required_prices = (
        "entry",
        "stop_loss",
        "tp1",
        "tp2",
        "tp3",
    )

    for key in required_prices:

        if data[key] <= 0:

            logger.warning(
                "Prix invalide : %s=%s",
                key,
                data[key],
            )

            return {
                "status": REJECT,

                "symbol": data["symbol"],

                "direction": data["direction"],

                "ready": False,

                "message": (
                    f"Prix invalide : {key}."
                ),
            }

    # --------------------------------------------------------
    # MESSAGE
    # --------------------------------------------------------

    message = construire_message(
        data
    )

    result = SignalResult(
        status=ACCEPT,

        symbol=data["symbol"],

        direction=data["direction"],

        entry=data["entry"],

        stop_loss=data["stop_loss"],

        tp1=data["tp1"],
        tp2=data["tp2"],
        tp3=data["tp3"],

        score=data["score"],

        rr=data["rr"],

        quality=data["quality"],

        ready=True,

        message=message,
    )

    return asdict(
        result
    )


# ============================================================
# TEST
# ============================================================

def _run_internal_test() -> None:
    """
    Test interne du générateur de signal.
    """

    analysis = {
        "status": ACCEPT,

        "symbol": "XAU/USD",

        "direction": BUY,

        "entry": 3350.0,

        "stop_loss": 3340.0,

        "ready_for_signal": True,

        "score": {
            "final_score": 88,
        },

        "rr": {
            "entry": 3350.0,
            "stop_loss": 3340.0,
            "tp1": 3360.0,
            "tp2": 3370.0,
            "tp3": 3380.0,
            "rr_tp2": 2.0,
        },

        "quality": {
            "quality": "A",
        },
    }

    result = generer_signal(
        analysis
    )

    assert (
        result["status"]
        == ACCEPT
    )

    assert (
        result["ready"]
        is True
    )

    assert (
        result["direction"]
        == BUY
    )

    assert (
        result["entry"]
        == 3350.0
    )

    assert (
        result["tp2"]
        == 3370.0
    )

    assert (
        "XAU/USD"
        in result["message"]
    )

    logger.info(
        "Test signal.py réussi."
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
    print(
        "VISION TRADE AI V2 - TEST SIGNAL"
    )
    print("=" * 60)

    try:

        _run_internal_test()

        print(
            "\n✅ SIGNAL : OK"
        )

        print(
            "Générateur de signal opérationnel."
        )

    except Exception as exc:

        print(
            "\n❌ TEST SIGNAL ÉCHOUÉ"
        )

        print(
            f"Erreur : {exc}"
        )