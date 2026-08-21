"""
Vision Trade AI V2
structure.py

Moteur déterministe de structure de marché.

Responsabilités :
- Swing High / Swing Low
- HH / HL / LH / LL
- BOS
- CHoCH
- Order Blocks
- Fair Value Gaps
- Liquidité
- Liquidity Sweeps
- contexte structurel

IMPORTANT :
Ce module ne prend aucune décision BUY/SELL.
Il fournit uniquement des données structurelles
au moteur de scoring.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional, Sequence


logger = logging.getLogger(__name__)


# ============================================================
# CONSTANTES
# ============================================================

DEFAULT_SWING_LOOKBACK = 2
DEFAULT_FVG_MIN_SIZE = 0.0
DEFAULT_OB_LOOKBACK = 10

BULLISH = "bullish"
BEARISH = "bearish"
NEUTRAL = "neutral"


# ============================================================
# OUTILS
# ============================================================

def _validate_candles(
    candles: Sequence[dict],
) -> None:
    """Valide les données OHLC."""

    if not candles:
        raise ValueError(
            "La liste de bougies est vide."
        )

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
                f"Colonnes manquantes à l'index "
                f"{index}: {sorted(missing)}"
            )


def _price(candle: dict, key: str) -> float:
    """Convertit un prix en float."""

    return float(candle[key])


# ============================================================
# MODÈLES
# ============================================================

@dataclass
class SwingPoint:
    """Point de structure."""

    index: int
    price: float
    type: str
    strength: int = 1


@dataclass
class StructureBreak:
    """BOS ou CHoCH."""

    index: int
    price: float
    direction: str
    break_type: str
    reference_index: Optional[int] = None


@dataclass
class FairValueGap:
    """Fair Value Gap."""

    index: int
    direction: str
    top: float
    bottom: float
    size: float


@dataclass
class OrderBlock:
    """Order Block."""

    index: int
    direction: str
    high: float
    low: float
    body_high: float
    body_low: float


@dataclass
class LiquidityLevel:
    """Niveau de liquidité."""

    price: float
    direction: str
    source_indices: List[int]
    strength: int


@dataclass
class LiquiditySweep:
    """Sweep d'un niveau de liquidité."""

    index: int
    direction: str
    liquidity_price: float
    candle_high: float
    candle_low: float


# ============================================================
# SWINGS
# ============================================================

def detecter_swing_highs(
    candles: Sequence[dict],
    lookback: int = DEFAULT_SWING_LOOKBACK,
) -> List[SwingPoint]:
    """
    Détecte les Swing High.

    Un sommet est considéré comme swing high si son plus haut
    est supérieur ou égal aux highs des bougies voisines.
    """

    _validate_candles(candles)

    if lookback < 1:
        raise ValueError(
            "lookback doit être >= 1."
        )

    swings = []

    for i in range(
        lookback,
        len(candles) - lookback,
    ):

        current_high = _price(
            candles[i],
            "high",
        )

        left = [
            _price(
                candles[j],
                "high",
            )
            for j in range(
                i - lookback,
                i,
            )
        ]

        right = [
            _price(
                candles[j],
                "high",
            )
            for j in range(
                i + 1,
                i + lookback + 1,
            )
        ]

        if (
            current_high >= max(left)
            and current_high >= max(right)
        ):

            strength = sum(
                current_high >= value
                for value in left + right
            )

            swings.append(
                SwingPoint(
                    index=i,
                    price=current_high,
                    type="high",
                    strength=strength,
                )
            )

    return swings


def detecter_swing_lows(
    candles: Sequence[dict],
    lookback: int = DEFAULT_SWING_LOOKBACK,
) -> List[SwingPoint]:
    """
    Détecte les Swing Low.
    """

    _validate_candles(candles)

    if lookback < 1:
        raise ValueError(
            "lookback doit être >= 1."
        )

    swings = []

    for i in range(
        lookback,
        len(candles) - lookback,
    ):

        current_low = _price(
            candles[i],
            "low",
        )

        left = [
            _price(
                candles[j],
                "low",
            )
            for j in range(
                i - lookback,
                i,
            )
        ]

        right = [
            _price(
                candles[j],
                "low",
            )
            for j in range(
                i + 1,
                i + lookback + 1,
            )
        ]

        if (
            current_low <= min(left)
            and current_low <= min(right)
        ):

            strength = sum(
                current_low <= value
                for value in left + right
            )

            swings.append(
                SwingPoint(
                    index=i,
                    price=current_low,
                    type="low",
                    strength=strength,
                )
            )

    return swings


def detecter_swings(
    candles: Sequence[dict],
    lookback: int = DEFAULT_SWING_LOOKBACK,
) -> Dict[str, List[SwingPoint]]:
    """
    Retourne les swings hauts et bas.
    """

    return {
        "highs": detecter_swing_highs(
            candles,
            lookback,
        ),
        "lows": detecter_swing_lows(
            candles,
            lookback,
        ),
    }


# ============================================================
# CLASSIFICATION HH / HL / LH / LL
# ============================================================

def classifier_swings(
    swing_highs: Sequence[SwingPoint],
    swing_lows: Sequence[SwingPoint],
) -> List[Dict[str, Any]]:
    """
    Classe les swings en :

        HH
        LH
        HL
        LL
    """

    points = []

    for swing in swing_highs:
        points.append(swing)

    for swing in swing_lows:
        points.append(swing)

    points.sort(
        key=lambda point: point.index
    )

    previous_high = None
    previous_low = None

    result = []

    for swing in points:

        label = None

        if swing.type == "high":

            if previous_high is None:
                label = "H"

            elif swing.price > previous_high.price:
                label = "HH"

            else:
                label = "LH"

            previous_high = swing

        else:

            if previous_low is None:
                label = "L"

            elif swing.price > previous_low.price:
                label = "HL"

            else:
                label = "LL"

            previous_low = swing

        result.append(
            {
                "index": swing.index,
                "price": swing.price,
                "type": swing.type,
                "label": label,
                "strength": swing.strength,
            }
        )

    return result


# ============================================================
# BOS
# ============================================================

def detecter_bos(
    candles: Sequence[dict],
    swing_highs: Sequence[SwingPoint],
    swing_lows: Sequence[SwingPoint],
) -> List[StructureBreak]:
    """
    Détecte les Break Of Structure.

    BOS haussier :
        clôture au-dessus d'un swing high.

    BOS baissier :
        clôture sous un swing low.
    """

    _validate_candles(candles)

    events = []

    broken_highs = set()
    broken_lows = set()

    for i, candle in enumerate(candles):

        close = _price(
            candle,
            "close",
        )

        # BOS haussier.
        for swing in swing_highs:

            if swing.index >= i:
                continue

            if swing.index in broken_highs:
                continue

            if close > swing.price:

                events.append(
                    StructureBreak(
                        index=i,
                        price=close,
                        direction=BULLISH,
                        break_type="BOS",
                        reference_index=swing.index,
                    )
                )

                broken_highs.add(
                    swing.index
                )

        # BOS baissier.
        for swing in swing_lows:

            if swing.index >= i:
                continue

            if swing.index in broken_lows:
                continue

            if close < swing.price:

                events.append(
                    StructureBreak(
                        index=i,
                        price=close,
                        direction=BEARISH,
                        break_type="BOS",
                        reference_index=swing.index,
                    )
                )

                broken_lows.add(
                    swing.index
                )

    events.sort(
        key=lambda event: event.index
    )

    return events


# ============================================================
# CHoCH
# ============================================================

def detecter_choch(
    candles: Sequence[dict],
    swing_highs: Sequence[SwingPoint],
    swing_lows: Sequence[SwingPoint],
) -> List[StructureBreak]:
    """
    Détecte les changements de caractère.

    La logique utilise le dernier biais structurel confirmé :

        tendance haussière + cassure du dernier low
            -> CHoCH bearish

        tendance baissière + cassure du dernier high
            -> CHoCH bullish
    """

    _validate_candles(candles)

    events = []

    structure_bias = NEUTRAL

    last_high = None
    last_low = None

    highs = sorted(
        swing_highs,
        key=lambda x: x.index,
    )

    lows = sorted(
        swing_lows,
        key=lambda x: x.index,
    )

    high_cursor = 0
    low_cursor = 0

    for i, candle in enumerate(candles):

        while (
            high_cursor < len(highs)
            and highs[high_cursor].index < i
        ):
            last_high = highs[high_cursor]
            high_cursor += 1

        while (
            low_cursor < len(lows)
            and lows[low_cursor].index < i
        ):
            last_low = lows[low_cursor]
            low_cursor += 1

        close = _price(
            candle,
            "close",
        )

        if (
            structure_bias == BULLISH
            and last_low is not None
            and close < last_low.price
        ):

            events.append(
                StructureBreak(
                    index=i,
                    price=close,
                    direction=BEARISH,
                    break_type="CHoCH",
                    reference_index=last_low.index,
                )
            )

            structure_bias = BEARISH

        elif (
            structure_bias == BEARISH
            and last_high is not None
            and close > last_high.price
        ):

            events.append(
                StructureBreak(
                    index=i,
                    price=close,
                    direction=BULLISH,
                    break_type="CHoCH",
                    reference_index=last_high.index,
                )
            )

            structure_bias = BULLISH

        elif (
            structure_bias == NEUTRAL
            and last_high is not None
            and close > last_high.price
        ):

            structure_bias = BULLISH

        elif (
            structure_bias == NEUTRAL
            and last_low is not None
            and close < last_low.price
        ):

            structure_bias = BEARISH

    return events


# ============================================================
# ORDER BLOCKS
# ============================================================

def detecter_order_blocks(
    candles: Sequence[dict],
    structure_breaks: Sequence[StructureBreak],
    lookback: int = DEFAULT_OB_LOOKBACK,
) -> List[OrderBlock]:
    """
    Détecte les Order Blocks associés aux cassures.

    Pour un BOS bullish :
        dernière bougie baissière avant la cassure.

    Pour un BOS bearish :
        dernière bougie haussière avant la cassure.
    """

    _validate_candles(candles)

    if lookback < 1:
        raise ValueError(
            "lookback doit être >= 1."
        )

    order_blocks = []

    for event in structure_breaks:

        if event.break_type not in {
            "BOS",
            "CHoCH",
        }:
            continue

        start = max(
            0,
            event.index - lookback,
        )

        candidate_indices = range(
            event.index - 1,
            start - 1,
            -1,
        )

        selected = None

        for index in candidate_indices:

            candle = candles[index]

            open_price = _price(
                candle,
                "open",
            )

            close_price = _price(
                candle,
                "close",
            )

            if event.direction == BULLISH:

                # Dernière bougie bearish.
                if close_price < open_price:
                    selected = index
                    break

            elif event.direction == BEARISH:

                # Dernière bougie bullish.
                if close_price > open_price:
                    selected = index
                    break

        if selected is None:
            continue

        candle = candles[selected]

        high = _price(
            candle,
            "high",
        )

        low = _price(
            candle,
            "low",
        )

        body_high = max(
            _price(candle, "open"),
            _price(candle, "close"),
        )

        body_low = min(
            _price(candle, "open"),
            _price(candle, "close"),
        )

        order_blocks.append(
            OrderBlock(
                index=selected,
                direction=event.direction,
                high=high,
                low=low,
                body_high=body_high,
                body_low=body_low,
            )
        )

    return _deduplicate_order_blocks(
        order_blocks
    )


def _deduplicate_order_blocks(
    order_blocks: Sequence[OrderBlock],
) -> List[OrderBlock]:
    """Supprime les OB identiques."""

    seen = set()
    result = []

    for ob in order_blocks:

        key = (
            ob.index,
            ob.direction,
        )

        if key in seen:
            continue

        seen.add(key)
        result.append(ob)

    return result


# ============================================================
# FAIR VALUE GAPS
# ============================================================

def detecter_fvg(
    candles: Sequence[dict],
    min_size: float = DEFAULT_FVG_MIN_SIZE,
) -> List[FairValueGap]:
    """
    Détecte les FVG avec une structure de trois bougies.

    Bullish FVG :
        low[i] > high[i-2]

    Bearish FVG :
        high[i] < low[i-2]
    """

    _validate_candles(candles)

    if min_size < 0:
        raise ValueError(
            "min_size doit être >= 0."
        )

    fvgs = []

    for i in range(
        2,
        len(candles),
    ):

        candle_1 = candles[i - 2]
        candle_3 = candles[i]

        high_1 = _price(
            candle_1,
            "high",
        )

        low_1 = _price(
            candle_1,
            "low",
        )

        high_3 = _price(
            candle_3,
            "high",
        )

        low_3 = _price(
            candle_3,
            "low",
        )

        # Bullish FVG.
        if low_3 > high_1:

            size = low_3 - high_1

            if size >= min_size:

                fvgs.append(
                    FairValueGap(
                        index=i,
                        direction=BULLISH,
                        top=low_3,
                        bottom=high_1,
                        size=size,
                    )
                )

        # Bearish FVG.
        elif high_3 < low_1:

            size = low_1 - high_3

            if size >= min_size:

                fvgs.append(
                    FairValueGap(
                        index=i,
                        direction=BEARISH,
                        top=low_1,
                        bottom=high_3,
                        size=size,
                    )
                )

    return fvgs


# ============================================================
# LIQUIDITÉ
# ============================================================

def _group_nearby_levels(
    points: Sequence[SwingPoint],
    tolerance: float,
) -> List[LiquidityLevel]:
    """
    Regroupe les swings proches afin de détecter
    les zones potentielles de liquidité.
    """

    if not points:
        return []

    sorted_points = sorted(
        points,
        key=lambda point: point.price,
    )

    groups = []

    current_group = [
        sorted_points[0]
    ]

    for point in sorted_points[1:]:

        reference_price = (
            sum(
                p.price
                for p in current_group
            )
            / len(current_group)
        )

        if abs(
            point.price - reference_price
        ) <= tolerance:

            current_group.append(
                point
            )

        else:

            groups.append(
                current_group
            )

            current_group = [
                point
            ]

    groups.append(
        current_group
    )

    levels = []

    for group in groups:

        if len(group) < 2:
            continue

        average_price = (
            sum(
                point.price
                for point in group
            )
            / len(group)
        )

        direction = (
            "buy_side"
            if group[0].type == "high"
            else "sell_side"
        )

        levels.append(
            LiquidityLevel(
                price=average_price,
                direction=direction,
                source_indices=[
                    point.index
                    for point in group
                ],
                strength=len(group),
            )
        )

    return levels


def detecter_liquidite(
    swing_highs: Sequence[SwingPoint],
    swing_lows: Sequence[SwingPoint],
    tolerance: float,
) -> List[LiquidityLevel]:
    """
    Détecte les zones où plusieurs swings se concentrent.
    """

    if tolerance < 0:
        raise ValueError(
            "tolerance doit être >= 0."
        )

    high_levels = _group_nearby_levels(
        swing_highs,
        tolerance,
    )

    low_levels = _group_nearby_levels(
        swing_lows,
        tolerance,
    )

    return high_levels + low_levels


# ============================================================
# LIQUIDITY SWEEP
# ============================================================

def detecter_liquidity_sweeps(
    candles: Sequence[dict],
    liquidity_levels: Sequence[LiquidityLevel],
) -> List[LiquiditySweep]:
    """
    Détecte les sweeps de liquidité.

    Buy-side sweep :
        le prix dépasse un high de liquidité
        puis clôture sous ce niveau.

    Sell-side sweep :
        le prix passe sous un low de liquidité
        puis clôture au-dessus.
    """

    _validate_candles(candles)

    sweeps = []

    for i, candle in enumerate(candles):

        high = _price(
            candle,
            "high",
        )

        low = _price(
            candle,
            "low",
        )

        close = _price(
            candle,
            "close",
        )

        for level in liquidity_levels:

            if i in level.source_indices:
                continue

            if level.direction == "buy_side":

                if (
                    high > level.price
                    and close < level.price
                ):

                    sweeps.append(
                        LiquiditySweep(
                            index=i,
                            direction=BEARISH,
                            liquidity_price=level.price,
                            candle_high=high,
                            candle_low=low,
                        )
                    )

            elif level.direction == "sell_side":

                if (
                    low < level.price
                    and close > level.price
                ):

                    sweeps.append(
                        LiquiditySweep(
                            index=i,
                            direction=BULLISH,
                            liquidity_price=level.price,
                            candle_high=high,
                            candle_low=low,
                        )
                    )

    return sweeps


# ============================================================
# BIAIS STRUCTUREL
# ============================================================

def determiner_biais_structure(
    swings: Sequence[Dict[str, Any]],
) -> str:
    """
    Détermine un biais structurel simple à partir
    des derniers HH/HL/LH/LL.
    """

    if not swings:
        return NEUTRAL

    recent = swings[-8:]

    bullish_points = sum(
        1
        for swing in recent
        if swing["label"] in {
            "HH",
            "HL",
        }
    )

    bearish_points = sum(
        1
        for swing in recent
        if swing["label"] in {
            "LH",
            "LL",
        }
    )

    if bullish_points > bearish_points:
        return BULLISH

    if bearish_points > bullish_points:
        return BEARISH

    return NEUTRAL


# ============================================================
# ANALYSE STRUCTURE COMPLÈTE
# ============================================================

def analyser_structure(
    candles: Sequence[dict],
    swing_lookback: int = DEFAULT_SWING_LOOKBACK,
    ob_lookback: int = DEFAULT_OB_LOOKBACK,
    fvg_min_size: float = DEFAULT_FVG_MIN_SIZE,
    liquidity_tolerance: float = 0.0,
) -> Dict[str, Any]:
    """
    Analyse complète de la structure du marché.
    """

    _validate_candles(candles)

    swings = detecter_swings(
        candles,
        lookback=swing_lookback,
    )

    swing_highs = swings["highs"]
    swing_lows = swings["lows"]

    classified_swings = classifier_swings(
        swing_highs,
        swing_lows,
    )

    bos = detecter_bos(
        candles,
        swing_highs,
        swing_lows,
    )

    choch = detecter_choch(
        candles,
        swing_highs,
        swing_lows,
    )

    structure_breaks = (
        bos + choch
    )

    structure_breaks.sort(
        key=lambda event: event.index
    )

    order_blocks = detecter_order_blocks(
        candles,
        structure_breaks,
        lookback=ob_lookback,
    )

    fvgs = detecter_fvg(
        candles,
        min_size=fvg_min_size,
    )

    liquidity = detecter_liquidite(
        swing_highs,
        swing_lows,
        tolerance=liquidity_tolerance,
    )

    sweeps = detecter_liquidity_sweeps(
        candles,
        liquidity,
    )

    bias = determiner_biais_structure(
        classified_swings
    )

    return {
        "swings": {
            "highs": [
                asdict(point)
                for point in swing_highs
            ],
            "lows": [
                asdict(point)
                for point in swing_lows
            ],
            "classified": classified_swings,
        },

        "bos": [
            asdict(event)
            for event in bos
        ],

        "choch": [
            asdict(event)
            for event in choch
        ],

        "order_blocks": [
            asdict(ob)
            for ob in order_blocks
        ],

        "fvg": [
            asdict(fvg)
            for fvg in fvgs
        ],

        "liquidity": [
            asdict(level)
            for level in liquidity
        ],

        "liquidity_sweeps": [
            asdict(sweep)
            for sweep in sweeps
        ],

        "bias": bias,

        "latest": {
            "bos": (
                asdict(bos[-1])
                if bos
                else None
            ),
            "choch": (
                asdict(choch[-1])
                if choch
                else None
            ),
            "order_block": (
                asdict(order_blocks[-1])
                if order_blocks
                else None
            ),
            "fvg": (
                asdict(fvgs[-1])
                if fvgs
                else None
            ),
            "liquidity_sweep": (
                asdict(sweeps[-1])
                if sweeps
                else None
            ),
        },
    }


# ============================================================
# ANALYSE MULTI-TIMEFRAME
# ============================================================

def analyser_structure_multi_tf(
    data: Dict[str, Sequence[dict]],
    swing_lookback: int = DEFAULT_SWING_LOOKBACK,
) -> Dict[str, Dict[str, Any]]:
    """
    Analyse la structure de plusieurs timeframes.

    Exemple :

        {
            "H4": candles_h4,
            "H1": candles_h1,
            "M15": candles_m15,
            "M5": candles_m5
        }

    Chaque timeframe est analysé indépendamment.
    """

    result = {}

    for timeframe, candles in data.items():

        try:

            result[timeframe] = analyser_structure(
                candles=candles,
                swing_lookback=swing_lookback,
            )

        except Exception as exc:

            logger.exception(
                "Erreur analyse structure %s",
                timeframe,
            )

            result[timeframe] = {
                "error": str(exc),
            }

    return result


# ============================================================
# RÉSUMÉ STRUCTUREL
# ============================================================

def resume_structure(
    analysis: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Retourne uniquement les éléments essentiels
    destinés aux modules supérieurs.
    """

    return {
        "bias": analysis.get(
            "bias",
            NEUTRAL,
        ),

        "swing_highs": len(
            analysis.get(
                "swings",
                {},
            ).get(
                "highs",
                [],
            )
        ),

        "swing_lows": len(
            analysis.get(
                "swings",
                {},
            ).get(
                "lows",
                [],
            )
        ),

        "bos_count": len(
            analysis.get(
                "bos",
                [],
            )
        ),

        "choch_count": len(
            analysis.get(
                "choch",
                [],
            )
        ),

        "order_blocks_count": len(
            analysis.get(
                "order_blocks",
                [],
            )
        ),

        "fvg_count": len(
            analysis.get(
                "fvg",
                [],
            )
        ),

        "liquidity_count": len(
            analysis.get(
                "liquidity",
                [],
            )
        ),

        "sweep_count": len(
            analysis.get(
                "liquidity_sweeps",
                [],
            )
        ),

        "latest": analysis.get(
            "latest",
            {},
        ),
    }


# ============================================================
# TEST SYNTHÉTIQUE
# ============================================================

def _generate_test_candles(
    count: int = 80,
) -> List[dict]:
    """
    Génère des bougies synthétiques uniquement pour
    tester le moteur structurel.
    """

    candles = []

    base = 100.0

    for i in range(count):

        # Mouvement oscillant simple.
        wave = (
            ((i % 10) - 5)
            * 0.35
        )

        open_price = base + wave

        close_price = (
            open_price
            + (
                0.8
                if i % 4 != 0
                else -0.6
            )
        )

        high_price = (
            max(
                open_price,
                close_price,
            )
            + 0.5
        )

        low_price = (
            min(
                open_price,
                close_price,
            )
            - 0.5
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
                "volume": 1000,
            }
        )

        base = close_price

    return candles


def _run_internal_test() -> None:
    """
    Test principal du moteur structurel.
    """

    candles = _generate_test_candles()

    analysis = analyser_structure(
        candles,
        swing_lookback=2,
        ob_lookback=10,
        fvg_min_size=0.0,
        liquidity_tolerance=0.5,
    )

    assert "swings" in analysis
    assert "bos" in analysis
    assert "choch" in analysis
    assert "order_blocks" in analysis
    assert "fvg" in analysis
    assert "liquidity" in analysis
    assert "liquidity_sweeps" in analysis
    assert "bias" in analysis

    summary = resume_structure(
        analysis
    )

    assert "bias" in summary

    logger.info(
        "Test structure réussi : %s",
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
    print("VISION TRADE AI V2 - TEST STRUCTURE")
    print("=" * 60)

    try:

        _run_internal_test()

        print("\n✅ STRUCTURE : OK")
        print(
            "Swing / BOS / CHoCH / OB / FVG / "
            "Liquidité / Sweeps : moteur chargé."
        )

    except Exception as exc:

        print("\n❌ TEST STRUCTURE ÉCHOUÉ")
        print(f"Erreur : {exc}")