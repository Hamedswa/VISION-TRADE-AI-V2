"""
Vision Trade AI V2
rr.py

Moteur déterministe du Risk / Reward.

Responsabilités :
- calcul du risque ;
- calcul de la récompense ;
- calcul du ratio RR ;
- validation du SL ;
- calcul des TP ;
- vérification du RR minimum ;
- gestion BUY / SELL.

IMPORTANT :
Ce module ne prend aucune décision basée sur l'IA.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional


logger = logging.getLogger(__name__)


# ============================================================
# CONSTANTES
# ============================================================

BUY = "BUY"
SELL = "SELL"

DEFAULT_MIN_RR = 2.0

DEFAULT_TP_LEVELS = (
    1.0,
    2.0,
    3.0,
)


# ============================================================
# MODÈLE
# ============================================================

@dataclass
class RRResult:
    """
    Résultat complet du calcul Risk / Reward.
    """

    direction: str

    entry: float
    stop_loss: float

    risk: float

    tp1: float
    tp2: float
    tp3: float

    reward_tp1: float
    reward_tp2: float
    reward_tp3: float

    rr_tp1: float
    rr_tp2: float
    rr_tp3: float

    valid_stop_loss: bool
    minimum_rr: float
    passes_rr_filter: bool


# ============================================================
# VALIDATION
# ============================================================

def _validate_price(
    value: float,
    name: str,
) -> float:
    """
    Valide un prix.
    """

    if value is None:
        raise ValueError(
            f"{name} est obligatoire."
        )

    try:
        value = float(value)

    except (
        TypeError,
        ValueError,
    ):
        raise ValueError(
            f"{name} doit être numérique."
        )

    if value <= 0:
        raise ValueError(
            f"{name} doit être supérieur à 0."
        )

    return value


def _validate_direction(
    direction: str,
) -> str:
    """
    Valide BUY / SELL.
    """

    direction = str(
        direction
    ).upper().strip()

    if direction not in {
        BUY,
        SELL,
    }:
        raise ValueError(
            "direction doit être BUY ou SELL."
        )

    return direction


# ============================================================
# RISQUE
# ============================================================

def calculer_risque(
    entry: float,
    stop_loss: float,
    direction: str,
) -> float:
    """
    Calcule la distance entre Entry et SL.
    """

    entry = _validate_price(
        entry,
        "entry",
    )

    stop_loss = _validate_price(
        stop_loss,
        "stop_loss",
    )

    direction = _validate_direction(
        direction
    )

    if direction == BUY:

        risk = entry - stop_loss

    else:

        risk = stop_loss - entry

    if risk <= 0:
        raise ValueError(
            "Le Stop Loss est invalide "
            "pour cette direction."
        )

    return risk


# ============================================================
# VALIDATION SL
# ============================================================

def valider_stop_loss(
    entry: float,
    stop_loss: float,
    direction: str,
) -> bool:
    """
    Vérifie que le SL est placé du bon côté.
    """

    entry = _validate_price(
        entry,
        "entry",
    )

    stop_loss = _validate_price(
        stop_loss,
        "stop_loss",
    )

    direction = _validate_direction(
        direction
    )

    if direction == BUY:

        return stop_loss < entry

    return stop_loss > entry


# ============================================================
# TAKE PROFIT
# ============================================================

def calculer_tp(
    entry: float,
    risk: float,
    direction: str,
    rr: float,
) -> float:
    """
    Calcule un TP selon un multiple RR.
    """

    entry = _validate_price(
        entry,
        "entry",
    )

    risk = float(risk)

    direction = _validate_direction(
        direction
    )

    rr = float(rr)

    if risk <= 0:
        raise ValueError(
            "Le risque doit être > 0."
        )

    if rr <= 0:
        raise ValueError(
            "Le RR doit être > 0."
        )

    if direction == BUY:

        return entry + (
            risk * rr
        )

    return entry - (
        risk * rr
    )


# ============================================================
# REWARD
# ============================================================

def calculer_reward(
    entry: float,
    take_profit: float,
    direction: str,
) -> float:
    """
    Calcule la récompense potentielle.
    """

    entry = _validate_price(
        entry,
        "entry",
    )

    take_profit = _validate_price(
        take_profit,
        "take_profit",
    )

    direction = _validate_direction(
        direction
    )

    if direction == BUY:

        reward = (
            take_profit - entry
        )

    else:

        reward = (
            entry - take_profit
        )

    if reward <= 0:
        raise ValueError(
            "Le Take Profit est invalide "
            "pour cette direction."
        )

    return reward


# ============================================================
# RR
# ============================================================

def calculer_rr(
    risk: float,
    reward: float,
) -> float:
    """
    Calcule le ratio Risk / Reward.
    """

    risk = float(risk)
    reward = float(reward)

    if risk <= 0:
        raise ValueError(
            "Le risque doit être > 0."
        )

    if reward <= 0:
        raise ValueError(
            "La récompense doit être > 0."
        )

    return reward / risk


# ============================================================
# RR À PARTIR DES PRIX
# ============================================================

def calculer_rr_prix(
    entry: float,
    stop_loss: float,
    take_profit: float,
    direction: str,
) -> float:
    """
    Calcule directement le RR à partir de Entry / SL / TP.
    """

    risk = calculer_risque(
        entry,
        stop_loss,
        direction,
    )

    reward = calculer_reward(
        entry,
        take_profit,
        direction,
    )

    return calculer_rr(
        risk,
        reward,
    )


# ============================================================
# FILTRE RR
# ============================================================

def verifier_rr_minimum(
    rr: float,
    minimum_rr: float = DEFAULT_MIN_RR,
) -> bool:
    """
    Vérifie si le RR respecte le minimum demandé.
    """

    rr = float(rr)
    minimum_rr = float(minimum_rr)

    if minimum_rr <= 0:
        raise ValueError(
            "minimum_rr doit être > 0."
        )

    return rr >= minimum_rr


# ============================================================
# CALCUL COMPLET
# ============================================================

def calculer_rr_complet(
    entry: float,
    stop_loss: float,
    direction: str,
    minimum_rr: float = DEFAULT_MIN_RR,
    tp_levels: tuple = DEFAULT_TP_LEVELS,
) -> RRResult:
    """
    Calcule Entry / SL / TP / Risk / Reward / RR.
    """

    entry = _validate_price(
        entry,
        "entry",
    )

    stop_loss = _validate_price(
        stop_loss,
        "stop_loss",
    )

    direction = _validate_direction(
        direction
    )

    minimum_rr = float(
        minimum_rr
    )

    if minimum_rr <= 0:
        raise ValueError(
            "minimum_rr doit être > 0."
        )

    if not tp_levels:
        raise ValueError(
            "tp_levels ne peut pas être vide."
        )

    # --------------------------------------------------------
    # SL
    # --------------------------------------------------------

    valid_sl = valider_stop_loss(
        entry,
        stop_loss,
        direction,
    )

    if not valid_sl:
        raise ValueError(
            "Stop Loss invalide."
        )

    # --------------------------------------------------------
    # RISQUE
    # --------------------------------------------------------

    risk = calculer_risque(
        entry,
        stop_loss,
        direction,
    )

    # --------------------------------------------------------
    # TP
    # --------------------------------------------------------

    normalized_levels = [
        float(level)
        for level in tp_levels
    ]

    for level in normalized_levels:

        if level <= 0:
            raise ValueError(
                "Les niveaux TP doivent être > 0."
            )

    tps = [
        calculer_tp(
            entry,
            risk,
            direction,
            level,
        )
        for level in normalized_levels
    ]

    rewards = [
        calculer_reward(
            entry,
            tp,
            direction,
        )
        for tp in tps
    ]

    rrs = [
        calculer_rr(
            risk,
            reward,
        )
        for reward in rewards
    ]

    # --------------------------------------------------------
    # SÉCURITÉ : au moins 3 TP
    # --------------------------------------------------------

    while len(tps) < 3:

        next_level = (
            normalized_levels[-1]
            + 1.0
        )

        normalized_levels.append(
            next_level
        )

        tps.append(
            calculer_tp(
                entry,
                risk,
                direction,
                next_level,
            )
        )

        rewards.append(
            calculer_reward(
                entry,
                tps[-1],
                direction,
            )
        )

        rrs.append(
            calculer_rr(
                risk,
                rewards[-1],
            )
        )

    return RRResult(
        direction=direction,

        entry=entry,
        stop_loss=stop_loss,

        risk=risk,

        tp1=tps[0],
        tp2=tps[1],
        tp3=tps[2],

        reward_tp1=rewards[0],
        reward_tp2=rewards[1],
        reward_tp3=rewards[2],

        rr_tp1=rrs[0],
        rr_tp2=rrs[1],
        rr_tp3=rrs[2],

        valid_stop_loss=valid_sl,

        minimum_rr=minimum_rr,

        passes_rr_filter=(
            rrs[1] >= minimum_rr
        ),
    )


# ============================================================
# ANALYSE DE QUALITÉ DU RR
# ============================================================

def qualifier_rr(
    rr: float,
) -> str:
    """
    Classe le RR.
    """

    rr = float(rr)

    if rr >= 4.0:
        return "EXCELLENT"

    if rr >= 3.0:
        return "TRÈS BON"

    if rr >= 2.0:
        return "BON"

    if rr >= 1.5:
        return "ACCEPTABLE"

    return "FAIBLE"


# ============================================================
# RÉSUMÉ
# ============================================================

def resume_rr(
    result: RRResult,
) -> Dict:
    """
    Retourne un résumé exploitable par les modules supérieurs.
    """

    return {
        "direction": result.direction,

        "entry": result.entry,

        "stop_loss": result.stop_loss,

        "risk": result.risk,

        "tp1": result.tp1,
        "tp2": result.tp2,
        "tp3": result.tp3,

        "rr_tp1": result.rr_tp1,
        "rr_tp2": result.rr_tp2,
        "rr_tp3": result.rr_tp3,

        "minimum_rr": result.minimum_rr,

        "passes_rr_filter": (
            result.passes_rr_filter
        ),

        "quality_tp2": qualifier_rr(
            result.rr_tp2
        ),
    }


# ============================================================
# TEST
# ============================================================

def _run_internal_test() -> None:
    """
    Test du moteur RR.
    """

    # --------------------------------------------------------
    # BUY
    # --------------------------------------------------------

    buy = calculer_rr_complet(
        entry=100.0,
        stop_loss=98.0,
        direction=BUY,
    )

    assert buy.risk == 2.0
    assert buy.tp1 == 102.0
    assert buy.tp2 == 104.0
    assert buy.tp3 == 106.0

    assert buy.rr_tp1 == 1.0
    assert buy.rr_tp2 == 2.0
    assert buy.rr_tp3 == 3.0

    assert buy.passes_rr_filter is True

    # --------------------------------------------------------
    # SELL
    # --------------------------------------------------------

    sell = calculer_rr_complet(
        entry=100.0,
        stop_loss=102.0,
        direction=SELL,
    )

    assert sell.risk == 2.0
    assert sell.tp1 == 98.0
    assert sell.tp2 == 96.0
    assert sell.tp3 == 94.0

    assert sell.rr_tp1 == 1.0
    assert sell.rr_tp2 == 2.0
    assert sell.rr_tp3 == 3.0

    assert sell.passes_rr_filter is True

    # --------------------------------------------------------
    # RR
    # --------------------------------------------------------

    rr = calculer_rr_prix(
        entry=100.0,
        stop_loss=98.0,
        take_profit=104.0,
        direction=BUY,
    )

    assert rr == 2.0

    # --------------------------------------------------------
    # QUALIFICATION
    # --------------------------------------------------------

    assert (
        qualifier_rr(4.0)
        == "EXCELLENT"
    )

    assert (
        qualifier_rr(2.0)
        == "BON"
    )

    logger.info(
        "Test RR réussi."
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
    print("VISION TRADE AI V2 - TEST RR")
    print("=" * 60)

    try:

        _run_internal_test()

        print("\n✅ RR : OK")
        print(
            "Risk / Reward déterministe opérationnel."
        )

    except Exception as exc:

        print("\n❌ TEST RR ÉCHOUÉ")
        print(f"Erreur : {exc}")