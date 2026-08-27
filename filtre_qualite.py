"""
Vision Trade AI V2
filtre_qualite.py

Filtre final de qualité avant génération d'un signal.

Responsabilités :
- vérifier le score ;
- vérifier le RR ;
- vérifier les confirmations ;
- détecter les contradictions ;
- vérifier la cohérence multi-timeframe ;
- contrôler les annonces économiques ;
- appliquer les règles de sécurité ;
- retourner ACCEPT / REJECT / WAIT.

IMPORTANT :
- 100 % déterministe ;
- aucune IA ;
- aucun appel API ;
- aucune décision de Groq.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional


logger = logging.getLogger(__name__)


# ============================================================
# CONSTANTES
# ============================================================

BUY = "BUY"
SELL = "SELL"

ACCEPT = "ACCEPT"
REJECT = "REJECT"
WAIT = "WAIT"

DEFAULT_MIN_SCORE = 80
DEFAULT_MIN_RR = 2.0

DEFAULT_MIN_CONFIRMATIONS = 3
DEFAULT_MAX_CONTRADICTIONS = 1

DEFAULT_NEWS_BLOCK_MINUTES = 30


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

    except (TypeError, ValueError):
        return default


def _safe_int(
    value: Any,
    default: int = 0,
) -> int:
    """
    Conversion entière sécurisée.
    """

    if value is None:
        return default

    try:
        return int(value)

    except (TypeError, ValueError):
        return default


def _normalize_direction(
    direction: Any,
) -> str:
    """
    Normalise toutes les représentations de direction.

    BUY / bullish / long  -> BUY
    SELL / bearish / short -> SELL
    NEUTRAL / none / vide -> NEUTRAL
    """

    value = str(
        direction or ""
    ).lower().strip()

    mapping = {
        "buy": BUY,
        "bullish": BUY,
        "long": BUY,

        "sell": SELL,
        "bearish": SELL,
        "short": SELL,

        "neutral": "NEUTRAL",
        "none": "NEUTRAL",
        "": "NEUTRAL",
    }

    return mapping.get(
        value,
        "NEUTRAL",
    )


def _normalize_impact(
    impact: Any,
) -> str:
    """
    Normalise l'impact d'une annonce.
    """

    return str(
        impact or ""
    ).lower().strip()


# ============================================================
# VÉRIFICATION SCORE
# ============================================================

def verifier_score(
    score: float,
    minimum_score: float = DEFAULT_MIN_SCORE,
) -> tuple[bool, str]:
    """
    Vérifie le score final.
    """

    score = _safe_float(score)
    minimum_score = _safe_float(
        minimum_score
    )

    if minimum_score < 0:
        raise ValueError(
            "minimum_score ne peut pas être négatif."
        )

    if score >= minimum_score:
        return (
            True,
            f"Score {score:.1f}/100 >= "
            f"{minimum_score:.1f}.",
        )

    return (
        False,
        f"Score insuffisant : "
        f"{score:.1f}/100 < "
        f"{minimum_score:.1f}.",
    )


# ============================================================
# VÉRIFICATION RR
# ============================================================

def verifier_rr(
    rr: float,
    minimum_rr: float = DEFAULT_MIN_RR,
) -> tuple[bool, str]:
    """
    Vérifie le Risk / Reward.
    """

    rr = _safe_float(rr)
    minimum_rr = _safe_float(
        minimum_rr
    )

    if minimum_rr <= 0:
        raise ValueError(
            "minimum_rr doit être > 0."
        )

    if rr >= minimum_rr:
        return (
            True,
            f"RR {rr:.2f} >= "
            f"{minimum_rr:.2f}.",
        )

    return (
        False,
        f"RR insuffisant : "
        f"{rr:.2f} < "
        f"{minimum_rr:.2f}.",
    )


# ============================================================
# CONFIRMATIONS
# ============================================================

def verifier_confirmations(
    confirmations: int,
    minimum_confirmations: int = DEFAULT_MIN_CONFIRMATIONS,
) -> tuple[bool, str]:
    """
    Vérifie le nombre de confirmations.
    """

    confirmations = _safe_int(
        confirmations
    )

    minimum_confirmations = _safe_int(
        minimum_confirmations
    )

    if minimum_confirmations < 0:
        raise ValueError(
            "minimum_confirmations ne peut pas être négatif."
        )

    if confirmations >= minimum_confirmations:
        return (
            True,
            f"{confirmations} confirmation(s) présentes.",
        )

    return (
        False,
        f"Seulement {confirmations} confirmation(s). "
        f"Minimum : {minimum_confirmations}.",
    )


# ============================================================
# CONTRADICTIONS
# ============================================================

def verifier_contradictions(
    contradictions: int,
    maximum_contradictions: int = DEFAULT_MAX_CONTRADICTIONS,
) -> tuple[bool, str]:
    """
    Vérifie le nombre de contradictions.
    """

    contradictions = _safe_int(
        contradictions
    )

    maximum_contradictions = _safe_int(
        maximum_contradictions
    )

    if maximum_contradictions < 0:
        raise ValueError(
            "maximum_contradictions ne peut pas être négatif."
        )

    if contradictions <= maximum_contradictions:
        return (
            True,
            f"{contradictions} contradiction(s).",
        )

    return (
        False,
        f"Trop de contradictions : "
        f"{contradictions}. Maximum autorisé : "
        f"{maximum_contradictions}.",
    )


# ============================================================
# COHÉRENCE MULTI-TIMEFRAME
# ============================================================

def verifier_coherence_mtf(
    direction: str,
    h4_bias: Optional[str] = None,
    h1_bias: Optional[str] = None,
    m15_bias: Optional[str] = None,
    m5_bias: Optional[str] = None,
) -> tuple[bool, List[str]]:
    """
    Vérifie la cohérence H4 / H1 / M15 / M5.

    Règles :

    - timeframe absente -> ignorée ;
    - NEUTRAL -> ignorée ;
    - timeframe alignée -> confirmation ;
    - timeframe opposée -> conflit.

    IMPORTANT :
    BUY / bullish sont considérés comme équivalents.
    SELL / bearish sont considérés comme équivalents.

    Une seule timeframe opposée suffit à considérer
    l'alignement MTF comme faux.
    """

    direction = _normalize_direction(
        direction
    )

    if direction not in {
        BUY,
        SELL,
    }:
        raise ValueError(
            "La direction doit être BUY ou SELL."
        )

    biases = {
        "H4": h4_bias,
        "H1": h1_bias,
        "M15": m15_bias,
        "M5": m5_bias,
    }

    reasons: List[str] = []

    oppositions = 0
    alignments = 0

    for timeframe, bias in biases.items():

        if bias is None:
            continue

        normalized = _normalize_direction(
            bias
        )

        if normalized == "NEUTRAL":
            continue

        if normalized == direction:

            alignments += 1

            reasons.append(
                f"{timeframe} aligné."
            )

        elif normalized in {
            BUY,
            SELL,
        }:

            oppositions += 1

            reasons.append(
                f"{timeframe} opposé."
            )

    # Une opposition = conflit MTF.
    mtf_aligned = oppositions == 0

    if alignments == 0 and oppositions == 0:
        reasons.append(
            "Aucune direction MTF exploitable."
        )

    return (
        mtf_aligned,
        reasons,
    )


# ============================================================
# ANNONCES ÉCONOMIQUES
# ============================================================

def analyser_annonce(
    news: Optional[Dict[str, Any]],
    block_minutes: int = DEFAULT_NEWS_BLOCK_MINUTES,
) -> tuple[bool, str]:
    """
    Analyse une éventuelle annonce économique.

    Formats acceptés :

        {
            "impact": "high",
            "minutes_to_event": 10
        }

    ou :

        {
            "impact": "HIGH",
            "minutes_until": 10
        }

    ou :

        {
            "blocked": True
        }

    annonces.py récupère les données.

    filtre_qualite.py décide uniquement si
    l'annonce bloque le setup.
    """

    if block_minutes < 0:
        raise ValueError(
            "block_minutes ne peut pas être négatif."
        )

    if not news:
        return (
            False,
            "Aucune annonce bloquante détectée.",
        )

    if news.get("blocked") is True:
        return (
            True,
            "Le calendrier économique indique "
            "une période bloquée.",
        )

    impact = _normalize_impact(
        news.get("impact")
    )

    minutes = news.get(
        "minutes_to_event"
    )

    if minutes is None:
        minutes = news.get(
            "minutes_until"
        )

    minutes = _safe_float(
        minutes,
        default=999999,
    )

    # --------------------------------------------------------
    # AVANT L'ÉVÉNEMENT
    # --------------------------------------------------------

    if (
        impact == "high"
        and 0 <= minutes <= block_minutes
    ):

        return (
            True,
            f"Annonce HIGH impact dans "
            f"{minutes:.0f} minute(s).",
        )

    # --------------------------------------------------------
    # APRÈS L'ÉVÉNEMENT
    # --------------------------------------------------------

    minutes_after = news.get(
        "minutes_after_event"
    )

    if (
        impact == "high"
        and minutes_after is not None
    ):

        minutes_after = _safe_float(
            minutes_after
        )

        if (
            0 <= minutes_after
            <= block_minutes
        ):

            return (
                True,
                f"Annonce HIGH impact : "
                f"{minutes_after:.0f} minute(s) "
                f"depuis la publication.",
            )

    # --------------------------------------------------------
    # HIGH HORS FENÊTRE
    # --------------------------------------------------------

    if impact == "high":

        return (
            False,
            "Annonce HIGH impact détectée "
            "mais hors fenêtre de blocage.",
        )

    # --------------------------------------------------------
    # MEDIUM
    # --------------------------------------------------------

    if impact == "medium":

        return (
            False,
            "Annonce MEDIUM impact détectée.",
        )

    # --------------------------------------------------------
    # LOW / UNKNOWN
    # --------------------------------------------------------

    return (
        False,
        "Annonce sans impact bloquant.",
    )


# ============================================================
# QUALITÉ DU SETUP
# ============================================================

def determiner_qualite(
    score: float,
    rr: float,
    mtf_aligned: bool,
    news_blocked: bool,
) -> str:
    """
    Détermine la qualité globale du setup.
    """

    score = _safe_float(score)
    rr = _safe_float(rr)

    if news_blocked:
        return "BLOCKED"

    if not mtf_aligned:
        return "CONFLICT"

    if score >= 90 and rr >= 3.0:
        return "A+"

    if score >= 85 and rr >= 2.5:
        return "A"

    if score >= 80 and rr >= 2.0:
        return "B"

    if score >= 70 and rr >= 1.5:
        return "C"

    return "D"


# ============================================================
# FILTRE PRINCIPAL
# ============================================================

def filtrer_qualite(
    direction: str,
    score_result: Optional[Dict[str, Any]] = None,
    rr_result: Optional[Dict[str, Any]] = None,
    h4_bias: Optional[str] = None,
    h1_bias: Optional[str] = None,
    m15_bias: Optional[str] = None,
    m5_bias: Optional[str] = None,
    news: Optional[Dict[str, Any]] = None,
    minimum_score: int = DEFAULT_MIN_SCORE,
    minimum_rr: float = DEFAULT_MIN_RR,
    minimum_confirmations: int = DEFAULT_MIN_CONFIRMATIONS,
    maximum_contradictions: int = DEFAULT_MAX_CONTRADICTIONS,
    news_block_minutes: int = DEFAULT_NEWS_BLOCK_MINUTES,
) -> Dict[str, Any]:
    """
    Filtre global de qualité.

    Retourne :

        ACCEPT
        REJECT
        WAIT
    """

    direction = _normalize_direction(
        direction
    )

    if direction not in {
        BUY,
        SELL,
    }:
        raise ValueError(
            "La direction doit être BUY ou SELL."
        )

    score_result = score_result or {}
    rr_result = rr_result or {}

    reasons: List[str] = []
    warnings: List[str] = []

    passed_checks = 0
    failed_checks = 0

    # ========================================================
    # SCORE
    # ========================================================

    score = _safe_float(
        score_result.get(
            "final_score",
            score_result.get(
                "score",
                0,
            ),
        )
    )

    score_ok, score_reason = verifier_score(
        score,
        minimum_score,
    )

    if score_ok:
        passed_checks += 1
        reasons.append(score_reason)
    else:
        failed_checks += 1
        warnings.append(score_reason)

    # ========================================================
    # RR
    # ========================================================

    rr = _safe_float(
        rr_result.get(
            "rr_tp2",
            rr_result.get(
                "rr",
                0,
            ),
        )
    )

    rr_ok, rr_reason = verifier_rr(
        rr,
        minimum_rr,
    )

    if rr_ok:
        passed_checks += 1
        reasons.append(rr_reason)
    else:
        failed_checks += 1
        warnings.append(rr_reason)

    # ========================================================
    # CONFIRMATIONS
    # ========================================================

    confirmations = _safe_int(
        score_result.get(
            "confirmations",
            0,
        )
    )

    confirmations_ok, confirmation_reason = (
        verifier_confirmations(
            confirmations,
            minimum_confirmations,
        )
    )

    if confirmations_ok:
        passed_checks += 1
        reasons.append(
            confirmation_reason
        )
    else:
        failed_checks += 1
        warnings.append(
            confirmation_reason
        )

    # ========================================================
    # CONTRADICTIONS
    # ========================================================

    contradictions = _safe_int(
        score_result.get(
            "contradictions",
            0,
        )
    )

    contradictions_ok, contradiction_reason = (
        verifier_contradictions(
            contradictions,
            maximum_contradictions,
        )
    )

    if contradictions_ok:
        passed_checks += 1
        reasons.append(
            contradiction_reason
        )
    else:
        failed_checks += 1
        warnings.append(
            contradiction_reason
        )

    # ========================================================
    # COHÉRENCE MTF
    # ========================================================

    mtf_aligned, mtf_reasons = (
        verifier_coherence_mtf(
            direction=direction,
            h4_bias=h4_bias,
            h1_bias=h1_bias,
            m15_bias=m15_bias,
            m5_bias=m5_bias,
        )
    )

    if mtf_aligned:

        passed_checks += 1

        reasons.extend(
            mtf_reasons
        )

    else:

        failed_checks += 1

        warnings.extend(
            mtf_reasons
        )

    # ========================================================
    # ANNONCES
    # ========================================================

    news_blocked, news_reason = (
        analyser_annonce(
            news,
            block_minutes=news_block_minutes,
        )
    )

    if news_blocked:

        failed_checks += 1

        warnings.append(
            news_reason
        )

    else:

        passed_checks += 1

        reasons.append(
            news_reason
        )

    # ========================================================
    # QUALITÉ
    # ========================================================

    quality = determiner_qualite(
        score=score,
        rr=rr,
        mtf_aligned=mtf_aligned,
        news_blocked=news_blocked,
    )

    # ========================================================
    # DÉCISION
    # ========================================================

    # Une annonce HIGH impact proche ne détruit pas
    # définitivement le setup : on attend.
    if news_blocked:

        status = WAIT

    elif (
        score_ok
        and rr_ok
        and confirmations_ok
        and contradictions_ok
        and mtf_aligned
    ):

        status = ACCEPT

    else:

        status = REJECT

    ready_for_signal = (
        status == ACCEPT
    )

    # ========================================================
    # SORTIE
    # ========================================================

    return {
        "status": status,

        "direction": direction,

        "score": score,
        "minimum_score": minimum_score,

        "rr": rr,
        "minimum_rr": minimum_rr,

        "confirmations": confirmations,

        "minimum_confirmations": (
            minimum_confirmations
        ),

        "contradictions": contradictions,

        "maximum_contradictions": (
            maximum_contradictions
        ),

        "mtf_aligned": mtf_aligned,

        "news_blocked": news_blocked,

        "quality": quality,

        "reasons": reasons,

        "warnings": warnings,

        "passed_checks": passed_checks,

        "failed_checks": failed_checks,

        "ready_for_signal": ready_for_signal,
    }


# ============================================================
# RÉSUMÉ
# ============================================================

def resume_filtre(
    result: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Résumé destiné aux modules supérieurs.
    """

    return {
        "status": result.get(
            "status"
        ),

        "direction": result.get(
            "direction"
        ),

        "score": result.get(
            "score"
        ),

        "rr": result.get(
            "rr"
        ),

        "quality": result.get(
            "quality"
        ),

        "ready_for_signal": result.get(
            "ready_for_signal"
        ),

        "warnings": result.get(
            "warnings",
            [],
        ),
    }


# ============================================================
# TESTS INTERNES
# ============================================================

def _run_internal_test() -> None:
    """
    Tests internes du filtre qualité.
    """

    # ========================================================
    # TEST NORMALISATION
    # ========================================================

    assert _normalize_direction("BUY") == BUY
    assert _normalize_direction("buy") == BUY
    assert _normalize_direction("bullish") == BUY
    assert _normalize_direction("long") == BUY

    assert _normalize_direction("SELL") == SELL
    assert _normalize_direction("sell") == SELL
    assert _normalize_direction("bearish") == SELL
    assert _normalize_direction("short") == SELL

    # ========================================================
    # CAS ACCEPTÉ
    # ========================================================

    result = filtrer_qualite(
        direction=BUY,

        score_result={
            "final_score": 88,
            "confirmations": 5,
            "contradictions": 0,
        },

        rr_result={
            "rr_tp2": 2.5,
        },

        h4_bias="bullish",
        h1_bias="bullish",
        m15_bias="bullish",
        m5_bias="bullish",

        news=None,
    )

    assert result["status"] == ACCEPT

    assert (
        result["ready_for_signal"]
        is True
    )

    assert result["mtf_aligned"] is True

    # ========================================================
    # CAS SCORE INSUFFISANT
    # ========================================================

    result = filtrer_qualite(
        direction=BUY,

        score_result={
            "final_score": 65,
            "confirmations": 4,
            "contradictions": 0,
        },

        rr_result={
            "rr_tp2": 2.5,
        },

        h4_bias="bullish",
        h1_bias="bullish",
        m15_bias="bullish",
        m5_bias="bullish",
    )

    assert result["status"] == REJECT

    assert (
        result["ready_for_signal"]
        is False
    )

    # ========================================================
    # CAS RR INSUFFISANT
    # ========================================================

    result = filtrer_qualite(
        direction=BUY,

        score_result={
            "final_score": 90,
            "confirmations": 5,
            "contradictions": 0,
        },

        rr_result={
            "rr_tp2": 1.2,
        },

        h4_bias="bullish",
        h1_bias="bullish",
        m15_bias="bullish",
        m5_bias="bullish",
    )

    assert result["status"] == REJECT

    # ========================================================
    # CAS ANNONCE HIGH
    # ========================================================

    result = filtrer_qualite(
        direction=BUY,

        score_result={
            "final_score": 92,
            "confirmations": 6,
            "contradictions": 0,
        },

        rr_result={
            "rr_tp2": 3.0,
        },

        h4_bias="bullish",
        h1_bias="bullish",
        m15_bias="bullish",
        m5_bias="bullish",

        news={
            "impact": "high",
            "minutes_to_event": 10,
        },
    )

    assert result["status"] == WAIT

    assert (
        result["ready_for_signal"]
        is False
    )

    assert result["news_blocked"] is True

    # ========================================================
    # CAS CONTRADICTION MTF
    # ========================================================

    result = filtrer_qualite(
        direction=BUY,

        score_result={
            "final_score": 88,
            "confirmations": 5,
            "contradictions": 0,
        },

        rr_result={
            "rr_tp2": 2.5,
        },

        h4_bias="bearish",
        h1_bias="bullish",
        m15_bias="bullish",
        m5_bias="bullish",
    )

    assert result["status"] == REJECT

    assert result["mtf_aligned"] is False

    # ========================================================
    # TEST BUY / SELL MIXTE
    # ========================================================

    mtf_buy = verifier_coherence_mtf(
        direction="BUY",
        h4_bias="bullish",
        h1_bias="BUY",
        m15_bias="bullish",
        m5_bias="BUY",
    )

    assert mtf_buy[0] is True

    mtf_sell = verifier_coherence_mtf(
        direction="SELL",
        h4_bias="bearish",
        h1_bias="SELL",
        m15_bias="bearish",
        m5_bias="SELL",
    )

    assert mtf_sell[0] is True

    logger.info(
        "Test filtre_qualite réussi."
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
        "VISION TRADE AI V2 - TEST FILTRE QUALITÉ"
    )
    print("=" * 60)

    try:

        _run_internal_test()

        print(
            "\n✅ FILTRE QUALITÉ : OK"
        )

        print(
            "Le filtre final est opérationnel."
        )

    except Exception as exc:

        print(
            "\n❌ TEST FILTRE QUALITÉ ÉCHOUÉ"
        )

        print(
            f"Erreur : {type(exc).__name__}: {exc}"
        )