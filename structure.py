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

DEFAULT_LIQUIDITY_TOLERANCE = 0.05

# Nombre de décimales utilisées pour les sorties.
# Les calculs internes restent en float complet.
PRICE_DECIMALS = 2
SIZE_DECIMALS = 4

BULLISH = "bullish"
BEARISH = "bearish"
NEUTRAL = "neutral"

BUY_SIDE = "buy_side"
SELL_SIDE = "sell_side"


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


def _price(
    candle: dict,
    key: str,
) -> float:
    """Convertit un prix en float."""

    try:
        return float(candle[key])
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"Prix invalide pour '{key}': "
            f"{candle.get(key)!r}"
        ) from exc


def _round_price(
    value: Any,
    decimals: int = PRICE_DECIMALS,
) -> Any:
    """Arrondit proprement un prix."""

    if value is None:
        return None

    try:
        return round(float(value), decimals)
    except (TypeError, ValueError):
        return value


def _round_size(
    value: Any,
    decimals: int = SIZE_DECIMALS,
) -> Any:
    """Arrondit une taille/distance."""

    if value is None:
        return None

    try:
        return round(float(value), decimals)
    except (TypeError, ValueError):
        return value


# ============================================================
# MODÈLES
# ============================================================

@dataclass
class SwingPoint:
    index: int
    price: float
    type: str
    strength: int = 1


@dataclass
class StructureBreak:
    index: int
    price: float
    direction: str
    break_type: str
    reference_index: Optional[int] = None


@dataclass
class FairValueGap:
    index: int
    direction: str
    top: float
    bottom: float
    size: float


@dataclass
class OrderBlock:
    index: int
    direction: str
    high: float
    low: float
    body_high: float
    body_low: float


@dataclass
class LiquidityLevel:
    price: float
    direction: str
    source_indices: List[int]
    strength: int


@dataclass
class LiquiditySweep:
    index: int
    direction: str
    liquidity_price: float
    candle_high: float
    candle_low: float


# ============================================================
# SWING HIGH
# ============================================================

def detecter_swing_highs(
    candles: Sequence[dict],
    lookback: int = DEFAULT_SWING_LOOKBACK,
) -> List[SwingPoint]:

    _validate_candles(candles)

    if lookback < 1:
        raise ValueError(
            "lookback doit être >= 1."
        )

    swings: List[SwingPoint] = []

    for i in range(
        lookback,
        len(candles) - lookback,
    ):

        current_high = _price(
            candles[i],
            "high",
        )

        left = [
            _price(candles[j], "high")
            for j in range(
                i - lookback,
                i,
            )
        ]

        right = [
            _price(candles[j], "high")
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


# ============================================================
# SWING LOW
# ============================================================

def detecter_swing_lows(
    candles: Sequence[dict],
    lookback: int = DEFAULT_SWING_LOOKBACK,
) -> List[SwingPoint]:

    _validate_candles(candles)

    if lookback < 1:
        raise ValueError(
            "lookback doit être >= 1."
        )

    swings: List[SwingPoint] = []

    for i in range(
        lookback,
        len(candles) - lookback,
    ):

        current_low = _price(
            candles[i],
            "low",
        )

        left = [
            _price(candles[j], "low")
            for j in range(
                i - lookback,
                i,
            )
        ]

        right = [
            _price(candles[j], "low")
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


# ============================================================
# SWINGS
# ============================================================

def detecter_swings(
    candles: Sequence[dict],
    lookback: int = DEFAULT_SWING_LOOKBACK,
) -> Dict[str, List[SwingPoint]]:

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

    points: List[SwingPoint] = []

    points.extend(swing_highs)
    points.extend(swing_lows)

    points.sort(
        key=lambda point: point.index
    )

    previous_high: Optional[SwingPoint] = None
    previous_low: Optional[SwingPoint] = None

    result: List[Dict[str, Any]] = []

    for swing in points:

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
                "price": _round_price(swing.price),
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

    _validate_candles(candles)

    events: List[StructureBreak] = []

    broken_highs = set()
    broken_lows = set()

    for i, candle in enumerate(candles):

        close = _price(
            candle,
            "close",
        )

        # BOS BULLISH
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

        # BOS BEARISH
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

    _validate_candles(candles)

    events: List[StructureBreak] = []

    structure_bias = NEUTRAL

    last_high: Optional[SwingPoint] = None
    last_low: Optional[SwingPoint] = None

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

        # CHoCH BEARISH
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

        # CHoCH BULLISH
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

        # PREMIER BIAIS
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
    Détecte les Order Blocks associés aux BOS/CHoCH.

    Bullish :
        dernière bougie bearish avant la cassure.

    Bearish :
        dernière bougie bullish avant la cassure.
    """

    _validate_candles(candles)

    if lookback < 1:
        raise ValueError(
            "lookback doit être >= 1."
        )

    if structure_breaks is None:
        structure_breaks = []

    order_blocks: List[OrderBlock] = []

    for event in structure_breaks:

        if isinstance(event, dict):

            break_type = event.get(
                "break_type"
            )

            direction = event.get(
                "direction"
            )

            event_index = event.get(
                "index"
            )

        else:

            break_type = event.break_type
            direction = event.direction
            event_index = event.index

        if break_type not in {
            "BOS",
            "CHoCH",
        }:
            continue

        if event_index is None:
            continue

        event_index = int(event_index)

        if event_index <= 0:
            continue

        start = max(
            0,
            event_index - lookback,
        )

        selected = None

        for index in range(
            event_index - 1,
            start - 1,
            -1,
        ):

            candle = candles[index]

            open_price = _price(
                candle,
                "open",
            )

            close_price = _price(
                candle,
                "close",
            )

            if direction == BULLISH:

                if close_price < open_price:
                    selected = index
                    break

            elif direction == BEARISH:

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
                direction=direction,
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

    seen = set()
    result: List[OrderBlock] = []

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

    _validate_candles(candles)

    if min_size < 0:
        raise ValueError(
            "min_size doit être >= 0."
        )

    fvgs: List[FairValueGap] = []

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

        # BULLISH FVG
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

        # BEARISH FVG
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

    if not points:
        return []

    if tolerance < 0:
        raise ValueError(
            "tolerance doit être >= 0."
        )

    sorted_points = sorted(
        points,
        key=lambda point: point.price,
    )

    groups: List[List[SwingPoint]] = []

    current_group: List[SwingPoint] = [
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

            current_group.append(point)

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

    levels: List[LiquidityLevel] = []

    for group in groups:

        if len(group) < 2:
            continue

        point_type = group[0].type

        if any(
            point.type != point_type
            for point in group
        ):
            continue

        average_price = (
            sum(
                point.price
                for point in group
            )
            / len(group)
        )

        direction = (
            BUY_SIDE
            if point_type == "high"
            else SELL_SIDE
        )

        levels.append(
            LiquidityLevel(
                price=average_price,
                direction=direction,
                source_indices=sorted(
                    point.index
                    for point in group
                ),
                strength=len(group),
            )
        )

    return levels


def detecter_liquidite(
    swing_highs: Sequence[SwingPoint],
    swing_lows: Sequence[SwingPoint],
    tolerance: float = DEFAULT_LIQUIDITY_TOLERANCE,
) -> List[LiquidityLevel]:

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
# LIQUIDITY SWEEPS
# ============================================================

def detecter_liquidity_sweeps(
    candles: Sequence[dict],
    liquidity_levels: Sequence[LiquidityLevel],
) -> List[LiquiditySweep]:

    _validate_candles(candles)

    sweeps: List[LiquiditySweep] = []

    consumed_levels = set()

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

            source_indices = tuple(
                sorted(
                    level.source_indices
                )
            )

            level_key = (
                level.direction,
                source_indices,
            )

            if level_key in consumed_levels:
                continue

            if not source_indices:
                continue

            # Protection contre le look-ahead bias.
            if max(source_indices) >= i:
                continue

            # BUY-SIDE SWEEP
            if level.direction == BUY_SIDE:

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

                    consumed_levels.add(
                        level_key
                    )

            # SELL-SIDE SWEEP
            elif level.direction == SELL_SIDE:

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

                    consumed_levels.add(
                        level_key
                    )

    return _deduplicate_liquidity_sweeps(
        sweeps
    )


def _deduplicate_liquidity_sweeps(
    sweeps: Sequence[LiquiditySweep],
) -> List[LiquiditySweep]:

    seen = set()
    result: List[LiquiditySweep] = []

    for sweep in sweeps:

        key = (
            sweep.index,
            sweep.direction,
            round(
                sweep.liquidity_price,
                5,
            ),
        )

        if key in seen:
            continue

        seen.add(key)
        result.append(sweep)

    return result


# ============================================================
# BIAIS STRUCTUREL
# ============================================================

def determiner_biais_structure(
    swings: Sequence[Dict[str, Any]],
) -> str:

    if not swings:
        return NEUTRAL

    recent = swings[-8:]

    bullish_points = sum(
        1
        for swing in recent
        if swing.get("label") in {
            "HH",
            "HL",
        }
    )

    bearish_points = sum(
        1
        for swing in recent
        if swing.get("label") in {
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
# CONVERSION DES RÉSULTATS
# ============================================================

def _serialize_structure(
    analysis: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Convertit les dataclasses en dictionnaires
    et arrondit les prix pour les sorties.

    Les calculs internes ne sont PAS arrondis.
    """

    swings = analysis["swings"]

    return {
        "swings": {
            "highs": [
                {
                    **asdict(point),
                    "price": _round_price(
                        point.price
                    ),
                }
                for point in swings["highs"]
            ],

            "lows": [
                {
                    **asdict(point),
                    "price": _round_price(
                        point.price
                    ),
                }
                for point in swings["lows"]
            ],

            "classified": swings[
                "classified"
            ],
        },

        "bos": [
            {
                **asdict(event),
                "price": _round_price(
                    event.price
                ),
            }
            for event in analysis["bos"]
        ],

        "choch": [
            {
                **asdict(event),
                "price": _round_price(
                    event.price
                ),
            }
            for event in analysis["choch"]
        ],

        "order_blocks": [
            {
                **asdict(ob),
                "high": _round_price(ob.high),
                "low": _round_price(ob.low),
                "body_high": _round_price(
                    ob.body_high
                ),
                "body_low": _round_price(
                    ob.body_low
                ),
            }
            for ob in analysis[
                "order_blocks"
            ]
        ],

        "fvg": [
            {
                **asdict(fvg),
                "top": _round_price(fvg.top),
                "bottom": _round_price(
                    fvg.bottom
                ),
                "size": _round_size(
                    fvg.size
                ),
            }
            for fvg in analysis["fvg"]
        ],

        "liquidity": [
            {
                **asdict(level),
                "price": _round_price(
                    level.price
                ),
            }
            for level in analysis[
                "liquidity"
            ]
        ],

        "liquidity_sweeps": [
            {
                **asdict(sweep),
                "liquidity_price": _round_price(
                    sweep.liquidity_price
                ),
                "candle_high": _round_price(
                    sweep.candle_high
                ),
                "candle_low": _round_price(
                    sweep.candle_low
                ),
            }
            for sweep in analysis[
                "liquidity_sweeps"
            ]
        ],

        "bias": analysis["bias"],

        "latest": {
            "bos": (
                {
                    **asdict(
                        analysis["bos"][-1]
                    ),
                    "price": _round_price(
                        analysis["bos"][-1].price
                    ),
                }
                if analysis["bos"]
                else None
            ),

            "choch": (
                {
                    **asdict(
                        analysis["choch"][-1]
                    ),
                    "price": _round_price(
                        analysis["choch"][-1].price
                    ),
                }
                if analysis["choch"]
                else None
            ),

            "order_block": (
                {
                    **asdict(
                        analysis[
                            "order_blocks"
                        ][-1]
                    ),
                    "high": _round_price(
                        analysis[
                            "order_blocks"
                        ][-1].high
                    ),
                    "low": _round_price(
                        analysis[
                            "order_blocks"
                        ][-1].low
                    ),
                    "body_high": _round_price(
                        analysis[
                            "order_blocks"
                        ][-1].body_high
                    ),
                    "body_low": _round_price(
                        analysis[
                            "order_blocks"
                        ][-1].body_low
                    ),
                }
                if analysis["order_blocks"]
                else None
            ),

            "fvg": (
                {
                    **asdict(
                        analysis["fvg"][-1]
                    ),
                    "top": _round_price(
                        analysis["fvg"][-1].top
                    ),
                    "bottom": _round_price(
                        analysis["fvg"][-1].bottom
                    ),
                    "size": _round_size(
                        analysis["fvg"][-1].size
                    ),
                }
                if analysis["fvg"]
                else None
            ),

            "liquidity_sweep": (
                {
                    **asdict(
                        analysis[
                            "liquidity_sweeps"
                        ][-1]
                    ),
                    "liquidity_price":
                        _round_price(
                            analysis[
                                "liquidity_sweeps"
                            ][-1]
                            .liquidity_price
                        ),
                    "candle_high":
                        _round_price(
                            analysis[
                                "liquidity_sweeps"
                            ][-1]
                            .candle_high
                        ),
                    "candle_low":
                        _round_price(
                            analysis[
                                "liquidity_sweeps"
                            ][-1]
                            .candle_low
                        ),
                }
                if analysis[
                    "liquidity_sweeps"
                ]
                else None
            ),
        },
    }


# ============================================================
# ANALYSE STRUCTURE COMPLÈTE
# ============================================================

def analyser_structure(
    candles: Sequence[dict],
    swing_lookback: int = DEFAULT_SWING_LOOKBACK,
    ob_lookback: int = DEFAULT_OB_LOOKBACK,
    fvg_min_size: float = DEFAULT_FVG_MIN_SIZE,
    liquidity_tolerance: float = DEFAULT_LIQUIDITY_TOLERANCE,
) -> Dict[str, Any]:
    """
    Analyse complète de la structure du marché.
    """

    _validate_candles(candles)

    # SWINGS
    swings = detecter_swings(
        candles,
        lookback=swing_lookback,
    )

    swing_highs = swings["highs"]
    swing_lows = swings["lows"]

    # CLASSIFICATION
    classified_swings = classifier_swings(
        swing_highs,
        swing_lows,
    )

    # BOS
    bos = detecter_bos(
        candles,
        swing_highs,
        swing_lows,
    )

    # CHoCH
    choch = detecter_choch(
        candles,
        swing_highs,
        swing_lows,
    )

    # STRUCTURE BREAKS
    structure_breaks = (
        bos + choch
    )

    structure_breaks.sort(
        key=lambda event: event.index
    )

    # ORDER BLOCKS
    order_blocks = detecter_order_blocks(
        candles,
        structure_breaks,
        lookback=ob_lookback,
    )

    # FVG
    fvgs = detecter_fvg(
        candles,
        min_size=fvg_min_size,
    )

    # LIQUIDITÉ
    liquidity = detecter_liquidite(
        swing_highs,
        swing_lows,
        tolerance=liquidity_tolerance,
    )

    # LIQUIDITY SWEEPS
    sweeps = detecter_liquidity_sweeps(
        candles,
        liquidity,
    )

    # BIAIS
    bias = determiner_biais_structure(
        classified_swings
    )

    # ANALYSE INTERNE
    raw_analysis = {
        "swings": {
            "highs": swing_highs,
            "lows": swing_lows,
            "classified": classified_swings,
        },

        "bos": bos,

        "choch": choch,

        "order_blocks": order_blocks,

        "fvg": fvgs,

        "liquidity": liquidity,

        "liquidity_sweeps": sweeps,

        "bias": bias,
    }

    # SORTIE PROPRE
    return _serialize_structure(
        raw_analysis
    )


# ============================================================
# ANALYSE MULTI-TIMEFRAME
# ============================================================

def analyser_structure_multi_tf(
    data: Dict[str, Sequence[dict]],
    swing_lookback: int = DEFAULT_SWING_LOOKBACK,
) -> Dict[str, Dict[str, Any]]:
    """
    Analyse H4 / H1 / M15 / M5.
    """

    result: Dict[str, Dict[str, Any]] = {}

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

    swings = analysis.get(
        "swings",
        {},
    )

    return {
        "bias": analysis.get(
            "bias",
            NEUTRAL,
        ),

        "swing_highs": len(
            swings.get(
                "highs",
                [],
            )
        ),

        "swing_lows": len(
            swings.get(
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

    candles: List[dict] = []

    base = 100.0

    for i in range(count):

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

        print("\nSTRUCTURE : OK")

        print(
            "Swing / BOS / CHoCH / OB / FVG / "
            "Liquidité / Sweeps : moteur chargé."
        )

    except Exception as exc:

        print("\nTEST STRUCTURE ÉCHOUÉ")
        print(f"Erreur : {exc}")