"""
Vision Trade AI V2
rr.py

MOTEUR DÉTERMINISTE DU RISK / REWARD

Responsabilités :
- validation Entry / SL ;
- calcul du risque ;
- calcul des TP ;
- calcul des récompenses ;
- calcul des ratios RR ;
- validation du RR minimum ;
- qualification du setup ;
- gestion BUY / SELL.

IMPORTANT :
- aucune IA ;
- aucun appel API ;
- aucune décision Telegram ;
- aucun calcul de taille de position ;
- aucun calcul de risque monétaire ;
- aucune dépendance externe.

Le moteur est purement mathématique,
déterministe et reproductible.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional, Sequence, Tuple


logger = logging.getLogger(__name__)


# ============================================================
# CONSTANTES
# ============================================================

BUY = "BUY"
SELL = "SELL"

DEFAULT_MIN_RR = 2.0

DEFAULT_TP_LEVELS: Tuple[float, float, float] = (
    1.0,
    2.0,
    3.0,
)

MIN_PRICE = 0.0


# ============================================================
# MODÈLE DE RÉSULTAT
# ============================================================

@dataclass
class RRResult:
    """
    Résultat complet du moteur Risk / Reward.
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
# VALIDATION NUMÉRIQUE
# ============================================================

def _validate_number(
    value: Any,
    name: str,
) -> float:
    """
    Convertit et valide une valeur numérique.

    Refuse :
    - None ;
    - texte non numérique ;
    - NaN ;
    - infini.
    """

    if value is None:
        raise ValueError(
            f"{name} est obligatoire."
        )

    try:
        number = float(value)

    except (
        TypeError,
        ValueError,
    ) as exc:

        raise ValueError(
            f"{name} doit être numérique."
        ) from exc

    if not math.isfinite(number):
        raise ValueError(
            f"{name} doit être une valeur "
            "numérique finie."
        )

    return number


def _validate_price(
    value: Any,
    name: str,
) -> float:
    """
    Valide un prix strictement positif.
    """

    value = _validate_number(
        value,
        name,
    )

    if value <= MIN_PRICE:
        raise ValueError(
            f"{name} doit être supérieur à 0."
        )

    return value


# ============================================================
# VALIDATION DIRECTION
# ============================================================

def _validate_direction(
    direction: Any,
) -> str:
    """
    Normalise et valide BUY / SELL.
    """

    if direction is None:
        raise ValueError(
            "direction est obligatoire."
        )

    normalized = str(
        direction
    ).upper().strip()

    aliases = {
        "BUY": BUY,
        "LONG": BUY,

        "SELL": SELL,
        "SHORT": SELL,
    }

    normalized = aliases.get(
        normalized,
        normalized,
    )

    if normalized not in {
        BUY,
        SELL,
    }:
        raise ValueError(
            "direction doit être BUY ou SELL."
        )

    return normalized


# ============================================================
# VALIDATION RR
# ============================================================

def _validate_rr(
    value: Any,
    name: str = "RR",
) -> float:
    """
    Valide un ratio RR strictement positif.
    """

    value = _validate_number(
        value,
        name,
    )

    if value <= 0:
        raise ValueError(
            f"{name} doit être supérieur à 0."
        )

    return value


# ============================================================
# VALIDATION DES NIVEAUX TP
# ============================================================

def _validate_tp_levels(
    tp_levels: Sequence[Any],
) -> List[float]:
    """
    Valide les multiples RR utilisés pour les TP.

    Exemple valide :

        (1.0, 2.0, 3.0)

    Les niveaux doivent être :
    - numériques ;
    - > 0 ;
    - strictement croissants.
    """

    if tp_levels is None:
        raise ValueError(
            "tp_levels est obligatoire."
        )

    try:
        levels = list(tp_levels)

    except TypeError as exc:

        raise ValueError(
            "tp_levels doit être une séquence "
            "de niveaux numériques."
        ) from exc

    if not levels:
        raise ValueError(
            "tp_levels ne peut pas être vide."
        )

    normalized: List[float] = []

    for index, level in enumerate(levels):

        value = _validate_rr(
            level,
            f"tp_levels[{index}]",
        )

        normalized.append(value)

    # --------------------------------------------------------
    # Les niveaux doivent être strictement croissants
    # --------------------------------------------------------

    for previous, current in zip(
        normalized,
        normalized[1:],
    ):

        if current <= previous:
            raise ValueError(
                "Les niveaux TP doivent être "
                "strictement croissants."
            )

    return normalized


# ============================================================
# RISQUE
# ============================================================

def calculer_risque(
    entry: float,
    stop_loss: float,
    direction: str,
) -> float:
    """
    Calcule la distance entre Entry et Stop Loss.

    BUY :
        risk = Entry - SL

    SELL :
        risk = SL - Entry
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
            f"pour une position {direction}."
        )

    return risk


# ============================================================
# VALIDATION STOP LOSS
# ============================================================

def valider_stop_loss(
    entry: float,
    stop_loss: float,
    direction: str,
) -> bool:
    """
    Vérifie que le SL est correctement placé.

    BUY :
        SL < Entry

    SELL :
        SL > Entry
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
    Calcule un Take Profit à partir
    d'un multiple de risque.

    BUY :
        TP = Entry + Risk × RR

    SELL :
        TP = Entry - Risk × RR
    """

    entry = _validate_price(
        entry,
        "entry",
    )

    risk = _validate_number(
        risk,
        "risk",
    )

    direction = _validate_direction(
        direction
    )

    rr = _validate_rr(
        rr
    )

    if risk <= 0:
        raise ValueError(
            "Le risque doit être supérieur à 0."
        )

    if direction == BUY:

        tp = entry + (
            risk * rr
        )

    else:

        tp = entry - (
            risk * rr
        )

    if tp <= 0:
        raise ValueError(
            "Le Take Profit calculé est invalide."
        )

    return tp


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

    BUY :
        Reward = TP - Entry

    SELL :
        Reward = Entry - TP
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
            f"pour une position {direction}."
        )

    return reward


# ============================================================
# CALCUL RR
# ============================================================

def calculer_rr(
    risk: float,
    reward: float,
) -> float:
    """
    Calcule :

        RR = Reward / Risk
    """

    risk = _validate_number(
        risk,
        "risk",
    )

    reward = _validate_number(
        reward,
        "reward",
    )

    if risk <= 0:
        raise ValueError(
            "Le risque doit être supérieur à 0."
        )

    if reward <= 0:
        raise ValueError(
            "La récompense doit être supérieure à 0."
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
    Calcule directement le RR depuis :

        Entry
        SL
        TP
        Direction
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
# FILTRE RR MINIMUM
# ============================================================

def verifier_rr_minimum(
    rr: float,
    minimum_rr: float = DEFAULT_MIN_RR,
) -> bool:
    """
    Vérifie si le RR respecte le minimum requis.
    """

    rr = _validate_rr(
        rr,
        "rr",
    )

    minimum_rr = _validate_rr(
        minimum_rr,
        "minimum_rr",
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
    tp_levels: Sequence[Any] = DEFAULT_TP_LEVELS,
) -> RRResult:
    """
    Calcul complet du Risk / Reward.

    Produit :

        Entry
        SL
        Risk

        TP1
        TP2
        TP3

        Reward TP1
        Reward TP2
        Reward TP3

        RR TP1
        RR TP2
        RR TP3

        filtre RR minimum
    """

    # --------------------------------------------------------
    # VALIDATION
    # --------------------------------------------------------

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

    minimum_rr = _validate_rr(
        minimum_rr,
        "minimum_rr",
    )

    normalized_levels = _validate_tp_levels(
        tp_levels
    )

    # --------------------------------------------------------
    # GARANTIE : AU MOINS 3 TP
    # --------------------------------------------------------

    while len(normalized_levels) < 3:

        next_level = (
            normalized_levels[-1] + 1.0
        )

        normalized_levels.append(
            next_level
        )

    # --------------------------------------------------------
    # VALIDATION SL
    # --------------------------------------------------------

    valid_sl = valider_stop_loss(
        entry,
        stop_loss,
        direction,
    )

    if not valid_sl:
        raise ValueError(
            "Stop Loss invalide pour la direction "
            f"{direction}."
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

    tps: List[float] = []

    rewards: List[float] = []

    rrs: List[float] = []

    for level in normalized_levels:

        tp = calculer_tp(
            entry=entry,
            risk=risk,
            direction=direction,
            rr=level,
        )

        reward = calculer_reward(
            entry=entry,
            take_profit=tp,
            direction=direction,
        )

        rr_value = calculer_rr(
            risk=risk,
            reward=reward,
        )

        tps.append(tp)
        rewards.append(reward)
        rrs.append(rr_value)

    # --------------------------------------------------------
    # TP1 / TP2 / TP3
    # --------------------------------------------------------

    tp1 = tps[0]
    tp2 = tps[1]
    tp3 = tps[2]

    reward_tp1 = rewards[0]
    reward_tp2 = rewards[1]
    reward_tp3 = rewards[2]

    rr_tp1 = rrs[0]
    rr_tp2 = rrs[1]
    rr_tp3 = rrs[2]

    # --------------------------------------------------------
    # FILTRE RR
    #
    # Le filtre principal de Vision Trade AI V2
    # utilise TP2 comme référence.
    #
    # TP2 par défaut = RR 2.0
    # --------------------------------------------------------

    passes_rr_filter = verifier_rr_minimum(
        rr_tp2,
        minimum_rr,
    )

    return RRResult(
        direction=direction,

        entry=entry,
        stop_loss=stop_loss,

        risk=risk,

        tp1=tp1,
        tp2=tp2,
        tp3=tp3,

        reward_tp1=reward_tp1,
        reward_tp2=reward_tp2,
        reward_tp3=reward_tp3,

        rr_tp1=rr_tp1,
        rr_tp2=rr_tp2,
        rr_tp3=rr_tp3,

        valid_stop_loss=valid_sl,

        minimum_rr=minimum_rr,

        passes_rr_filter=passes_rr_filter,
    )


# ============================================================
# QUALIFICATION RR
# ============================================================

def qualifier_rr(
    rr: float,
) -> str:
    """
    Classe la qualité du RR.
    """

    rr = _validate_rr(
        rr
    )

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
) -> Dict[str, Any]:
    """
    Transforme RRResult en dictionnaire
    exploitable par les modules supérieurs.
    """

    if not isinstance(
        result,
        RRResult,
    ):
        raise TypeError(
            "result doit être une instance "
            "de RRResult."
        )

    return {
        "direction": result.direction,

        "entry": result.entry,

        "stop_loss": result.stop_loss,

        "risk": result.risk,

        "tp1": result.tp1,
        "tp2": result.tp2,
        "tp3": result.tp3,

        "reward_tp1": result.reward_tp1,
        "reward_tp2": result.reward_tp2,
        "reward_tp3": result.reward_tp3,

        "rr_tp1": result.rr_tp1,
        "rr_tp2": result.rr_tp2,
        "rr_tp3": result.rr_tp3,

        "minimum_rr": result.minimum_rr,

        "valid_stop_loss": (
            result.valid_stop_loss
        ),

        "passes_rr_filter": (
            result.passes_rr_filter
        ),

        "quality_tp1": qualifier_rr(
            result.rr_tp1
        ),

        "quality_tp2": qualifier_rr(
            result.rr_tp2
        ),

        "quality_tp3": qualifier_rr(
            result.rr_tp3
        ),
    }


# ============================================================
# DICTIONNAIRE COMPLET
# ============================================================

def rr_to_dict(
    result: RRResult,
) -> Dict[str, Any]:
    """
    Convertit RRResult en dictionnaire complet.
    """

    if not isinstance(
        result,
        RRResult,
    ):
        raise TypeError(
            "result doit être une instance "
            "de RRResult."
        )

    return asdict(result)


# ============================================================
# TESTS INTERNES
# ============================================================

def _run_internal_test() -> None:
    """
    Batterie de tests du moteur RR.
    """

    # ========================================================
    # BUY
    # ========================================================

    buy = calculer_rr_complet(
        entry=100.0,
        stop_loss=98.0,
        direction=BUY,
    )

    assert buy.valid_stop_loss is True

    assert buy.risk == 2.0

    assert buy.tp1 == 102.0
    assert buy.tp2 == 104.0
    assert buy.tp3 == 106.0

    assert buy.reward_tp1 == 2.0
    assert buy.reward_tp2 == 4.0
    assert buy.reward_tp3 == 6.0

    assert buy.rr_tp1 == 1.0
    assert buy.rr_tp2 == 2.0
    assert buy.rr_tp3 == 3.0

    assert buy.passes_rr_filter is True

    # ========================================================
    # SELL
    # ========================================================

    sell = calculer_rr_complet(
        entry=100.0,
        stop_loss=102.0,
        direction=SELL,
    )

    assert sell.valid_stop_loss is True

    assert sell.risk == 2.0

    assert sell.tp1 == 98.0
    assert sell.tp2 == 96.0
    assert sell.tp3 == 94.0

    assert sell.reward_tp1 == 2.0
    assert sell.reward_tp2 == 4.0
    assert sell.reward_tp3 == 6.0

    assert sell.rr_tp1 == 1.0
    assert sell.rr_tp2 == 2.0
    assert sell.rr_tp3 == 3.0

    assert sell.passes_rr_filter is True

    # ========================================================
    # RR DIRECT
    # ========================================================

    rr_buy = calculer_rr_prix(
        entry=100.0,
        stop_loss=98.0,
        take_profit=104.0,
        direction=BUY,
    )

    assert rr_buy == 2.0

    rr_sell = calculer_rr_prix(
        entry=100.0,
        stop_loss=102.0,
        take_profit=96.0,
        direction=SELL,
    )

    assert rr_sell == 2.0

    # ========================================================
    # VALIDATION SL
    # ========================================================

    assert valider_stop_loss(
        100.0,
        98.0,
        BUY,
    ) is True

    assert valider_stop_loss(
        100.0,
        102.0,
        SELL,
    ) is True

    assert valider_stop_loss(
        100.0,
        102.0,
        BUY,
    ) is False

    assert valider_stop_loss(
        100.0,
        98.0,
        SELL,
    ) is False

    # ========================================================
    # FILTRE RR
    # ========================================================

    assert verifier_rr_minimum(
        2.0,
        2.0,
    ) is True

    assert verifier_rr_minimum(
        2.5,
        2.0,
    ) is True

    assert verifier_rr_minimum(
        1.9,
        2.0,
    ) is False

    # ========================================================
    # QUALIFICATION
    # ========================================================

    assert qualifier_rr(
        4.0
    ) == "EXCELLENT"

    assert qualifier_rr(
        3.0
    ) == "TRÈS BON"

    assert qualifier_rr(
        2.0
    ) == "BON"

    assert qualifier_rr(
        1.5
    ) == "ACCEPTABLE"

    assert qualifier_rr(
        1.0
    ) == "FAIBLE"

    # ========================================================
    # TP PERSONNALISÉS
    # ========================================================

    custom = calculer_rr_complet(
        entry=100.0,
        stop_loss=95.0,
        direction=BUY,
        minimum_rr=2.0,
        tp_levels=(
            1.0,
            2.5,
            4.0,
        ),
    )

    assert custom.risk == 5.0

    assert custom.tp1 == 105.0
    assert custom.tp2 == 112.5
    assert custom.tp3 == 120.0

    assert custom.rr_tp1 == 1.0
    assert custom.rr_tp2 == 2.5
    assert custom.rr_tp3 == 4.0

    assert custom.passes_rr_filter is True

    # ========================================================
    # RR INSUFFISANT
    # ========================================================

    weak = calculer_rr_complet(
        entry=100.0,
        stop_loss=98.0,
        direction=BUY,
        minimum_rr=3.0,
        tp_levels=(
            1.0,
            2.0,
            3.0,
        ),
    )

    assert weak.passes_rr_filter is False

    # ========================================================
    # TEST ERREURS
    # ========================================================

    try:

        calculer_risque(
            entry=100.0,
            stop_loss=102.0,
            direction=BUY,
        )

        raise AssertionError(
            "Un SL BUY invalide aurait dû "
            "lever une exception."
        )

    except ValueError:
        pass

    try:

        calculer_risque(
            entry=100.0,
            stop_loss=98.0,
            direction=SELL,
        )

        raise AssertionError(
            "Un SL SELL invalide aurait dû "
            "lever une exception."
        )

    except ValueError:
        pass

    try:

        calculer_rr_complet(
            entry=100.0,
            stop_loss=98.0,
            direction=BUY,
            tp_levels=(
                2.0,
                1.0,
                3.0,
            ),
        )

        raise AssertionError(
            "Des niveaux TP non croissants "
            "auraient dû lever une exception."
        )

    except ValueError:
        pass

    try:

        calculer_rr_complet(
            entry=100.0,
            stop_loss=98.0,
            direction=BUY,
            minimum_rr=0,
        )

        raise AssertionError(
            "minimum_rr=0 aurait dû "
            "lever une exception."
        )

    except ValueError:
        pass

    try:

        calculer_rr_complet(
            entry=float("nan"),
            stop_loss=98.0,
            direction=BUY,
        )

        raise AssertionError(
            "NaN aurait dû être refusé."
        )

    except ValueError:
        pass

    logger.info(
        "Tous les tests RR sont réussis."
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

        print()
        print("✅ RR : OK")
        print(
            "Risk / Reward déterministe opérationnel."
        )

        # ----------------------------------------------------
        # DÉMONSTRATION BUY
        # ----------------------------------------------------

        demo_buy = calculer_rr_complet(
            entry=100.0,
            stop_loss=98.0,
            direction=BUY,
        )

        print()
        print("----- BUY -----")
        print(
            f"Entry      : {demo_buy.entry}"
        )
        print(
            f"Stop Loss  : {demo_buy.stop_loss}"
        )
        print(
            f"Risk       : {demo_buy.risk}"
        )
        print(
            f"TP1        : {demo_buy.tp1}"
        )
        print(
            f"TP2        : {demo_buy.tp2}"
        )
        print(
            f"TP3        : {demo_buy.tp3}"
        )
        print(
            f"RR TP1     : {demo_buy.rr_tp1}"
        )
        print(
            f"RR TP2     : {demo_buy.rr_tp2}"
        )
        print(
            f"RR TP3     : {demo_buy.rr_tp3}"
        )
        print(
            f"RR FILTER  : "
            f"{demo_buy.passes_rr_filter}"
        )

        # ----------------------------------------------------
        # DÉMONSTRATION SELL
        # ----------------------------------------------------

        demo_sell = calculer_rr_complet(
            entry=100.0,
            stop_loss=102.0,
            direction=SELL,
        )

        print()
        print("----- SELL -----")
        print(
            f"Entry      : {demo_sell.entry}"
        )
        print(
            f"Stop Loss  : {demo_sell.stop_loss}"
        )
        print(
            f"Risk       : {demo_sell.risk}"
        )
        print(
            f"TP1        : {demo_sell.tp1}"
        )
        print(
            f"TP2        : {demo_sell.tp2}"
        )
        print(
            f"TP3        : {demo_sell.tp3}"
        )
        print(
            f"RR TP1     : {demo_sell.rr_tp1}"
        )
        print(
            f"RR TP2     : {demo_sell.rr_tp2}"
        )
        print(
            f"RR TP3     : {demo_sell.rr_tp3}"
        )
        print(
            f"RR FILTER  : "
            f"{demo_sell.passes_rr_filter}"
        )

    except Exception as exc:

        print()
        print("❌ TEST RR ÉCHOUÉ")
        print(
            f"Erreur : {type(exc).__name__}: {exc}"
        )