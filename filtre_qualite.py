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
Ce module est 100 % déterministe.
Aucune IA.
Aucun appel API.
Aucune décision de Groq.
Configuration :
- Score minimum : MIN_SCORE depuis config.py
- RR minimum : MIN_RR depuis config.py
"""
from __future__ import annotations
import logging
from typing import Any, Dict, List, Optional
from config import (
    MIN_SCORE,
    MIN_RR,
    NEWS_BLOCK_BEFORE_MINUTES,
)
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
# CONFIGURATION CENTRALE
# ============================================================
# Le seuil réel vient maintenant de config.py.
DEFAULT_MIN_SCORE = MIN_SCORE
DEFAULT_MIN_RR = MIN_RR
DEFAULT_MIN_CONFIRMATIONS = 3
DEFAULT_MAX_CONTRADICTIONS = 1
DEFAULT_NEWS_BLOCK_MINUTES = NEWS_BLOCK_BEFORE_MINUTES
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
    except (
        TypeError,
        ValueError,
    ):
        return default
def _normalize_direction(
    direction: str,
) -> str:
    """
    Normalise BUY / SELL / bullish / bearish.
    """
    value = str(
        direction or ""
    ).lower().strip()
    if value in {
        "buy",
        "bullish",
        "long",
    }:
        return BUY
    if value in {
        "sell",
        "bearish",
        "short",
    }:
        return SELL
    raise ValueError(
        "La direction doit être BUY ou SELL."
    )
def _normalize_bias(
    bias: Any,
) -> str:
    """
    Normalise un biais de marché.
    Retourne :
        bullish
        bearish
        neutral
    """
    value = str(
        bias or ""
    ).lower().strip()
    if value in {
        "buy",
        "bullish",
        "long",
    }:
        return "bullish"
    if value in {
        "sell",
        "bearish",
        "short",
    }:
        return "bearish"
    if value in {
        "",
        "neutral",
        "none",
        "null",
        "unknown",
    }:
        return "neutral"
    return "neutral"
# ============================================================
# VÉRIFICATION SCORE
# ============================================================
def verifier_score(
    score: float,
    minimum_score: float = DEFAULT_MIN_SCORE,
) -> tuple[bool, str]:
    """
    Vérifie le score final.
    Le seuil par défaut est celui de config.py.
    Avec la configuration actuelle :
        MIN_SCORE = 50
    un score >= 50 est considéré comme suffisant
    pour passer ce contrôle.
    IMPORTANT :
    Passer le contrôle du score ne garantit PAS
    qu'un signal sera généré. Les autres filtres
    doivent également être validés.
    """
    score = _safe_float(score)
    minimum_score = _safe_float(
        minimum_score,
        DEFAULT_MIN_SCORE,
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
    Le minimum reste actuellement :
        RR >= 2.0
    """
    rr = _safe_float(rr)
    minimum_rr = _safe_float(
        minimum_rr,
        DEFAULT_MIN_RR,
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
        minimum_confirmations,
        DEFAULT_MIN_CONFIRMATIONS,
    )
    if confirmations >= minimum_confirmations:
        return (
            True,
            f"{confirmations} confirmations présentes.",
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
        maximum_contradictions,
        DEFAULT_MAX_CONTRADICTIONS,
    )
    if contradictions <= maximum_contradictions:
        return (
            True,
            f"{contradictions} contradiction(s).",
        )
    return (
        False,
        f"Trop de contradictions : "
        f"{contradictions}. "
        f"Maximum autorisé : "
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
    Une timeframe NEUTRAL est ignorée.
    Une timeframe opposée crée un conflit.
    La direction principale reste déterminée
    par analyse.py.
    """
    normalized_direction = _normalize_direction(
        direction
    )
    target = (
        "bullish"
        if normalized_direction == BUY
        else "bearish"
    )
    biases = {
        "H4": h4_bias,
        "H1": h1_bias,
        "M15": m15_bias,
        "M5": m5_bias,
    }
    reasons: List[str] = []
    oppositions = 0
    for timeframe, bias in biases.items():
        normalized = _normalize_bias(
            bias
        )
        # ----------------------------------------------------
        # NEUTRAL
        # ----------------------------------------------------
        if normalized == "neutral":
            reasons.append(
                f"{timeframe} neutre : ignoré."
            )
            continue
        # ----------------------------------------------------
        # ALIGNÉ
        # ----------------------------------------------------
        if normalized == target:
            reasons.append(
                f"{timeframe} aligné."
            )
        # ----------------------------------------------------
        # OPPOSÉ
        # ----------------------------------------------------
        else:
            oppositions += 1
            reasons.append(
                f"{timeframe} opposé."
            )
    aligned = (
        oppositions == 0
    )
    return (
        aligned,
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
    """
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
    impact = str(
        news.get(
            "impact",
            "",
        )
    ).lower().strip()
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
    # AVANT L'ANNONCE
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
    # APRÈS L'ANNONCE
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
    if impact == "high":
        return (
            False,
            "Annonce HIGH impact détectée "
            "mais hors fenêtre de blocage.",
        )
    if impact == "medium":
        return (
            False,
            "Annonce MEDIUM impact détectée.",
        )
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
    Nouvelle logique adaptée au seuil de 50 :
        A+ : score >= 90 et RR >= 3.0
        A  : score >= 80 et RR >= 2.5
        B  : score >= 70 et RR >= 2.0
        C  : score >= 50 et RR >= 2.0
        D  : en dessous des critères minimum
    IMPORTANT :
    La qualité ne remplace pas les contrôles de sécurité.
    """
    if news_blocked:
        return "BLOCKED"
    if not mtf_aligned:
        return "CONFLICT"
    if score >= 90 and rr >= 3.0:
        return "A+"
    if score >= 80 and rr >= 2.5:
        return "A"
    if score >= 70 and rr >= 2.0:
        return "B"
    if score >= DEFAULT_MIN_SCORE and rr >= DEFAULT_MIN_RR:
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
    Le score minimum par défaut est maintenant
    récupéré depuis config.py.
    """
    direction = _normalize_direction(
        direction
    )
    score_result = (
        score_result
        if isinstance(score_result, dict)
        else {}
    )
    rr_result = (
        rr_result
        if isinstance(rr_result, dict)
        else {}
    )
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
        reasons.append(
            score_reason
        )
    else:
        failed_checks += 1
        warnings.append(
            score_reason
        )
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
        reasons.append(
            rr_reason
        )
    else:
        failed_checks += 1
        warnings.append(
            rr_reason
        )
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
    # LOG
    # ========================================================
    logger.info(
        "FILTRE QUALITÉ | direction=%s | "
        "score=%.2f/%s | RR=%.2f/%s | "
        "MTF=%s | confirmations=%s | "
        "contradictions=%s | status=%s | quality=%s",
        direction,
        score,
        minimum_score,
        rr,
        minimum_rr,
        mtf_aligned,
        confirmations,
        contradictions,
        status,
        quality,
    )
    # ========================================================
    # RESULTAT
    # ========================================================
    return {
        "status":
            status,
        "direction":
            direction,
        "score":
            score,
        "minimum_score":
            minimum_score,
        "rr":
            rr,
        "minimum_rr":
            minimum_rr,
        "confirmations":
            confirmations,
        "minimum_confirmations":
            minimum_confirmations,
        "contradictions":
            contradictions,
        "maximum_contradictions":
            maximum_contradictions,
        "mtf_aligned":
            mtf_aligned,
        "news_blocked":
            news_blocked,
        "quality":
            quality,
        "reasons":
            reasons,
        "warnings":
            warnings,
        "passed_checks":
            passed_checks,
        "failed_checks":
            failed_checks,
        "ready_for_signal":
            ready_for_signal,
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
        "status":
            result.get(
                "status"
            ),
        "direction":
            result.get(
                "direction"
            ),
        "score":
            result.get(
                "score"
            ),
        "rr":
            result.get(
                "rr"
            ),
        "quality":
            result.get(
                "quality"
            ),
        "ready_for_signal":
            result.get(
                "ready_for_signal"
            ),
        "warnings":
            result.get(
                "warnings",
                [],
            ),
    }
# ============================================================
# TEST INTERNE
# ============================================================
def _run_internal_test() -> None:
    """
    Tests internes du filtre qualité.
    La configuration actuelle utilise :
        MIN_SCORE = 50
        MIN_RR = 2.0
    """
    # ========================================================
    # VÉRIFICATION CONFIG
    # ========================================================
    assert DEFAULT_MIN_SCORE == MIN_SCORE
    assert DEFAULT_MIN_RR == MIN_RR
    assert MIN_SCORE == 50
    assert MIN_RR == 2.0
    # ========================================================
    # TEST COHÉRENCE BUY
    # ========================================================
    mtf_buy, reasons_buy = verifier_coherence_mtf(
        direction="BUY",
        h4_bias="bullish",
        h1_bias="bullish",
        m15_bias="bullish",
        m5_bias="bullish",
    )
    assert mtf_buy is True
    assert len(reasons_buy) == 4
    # ========================================================
    # CAS ACCEPTÉ A
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
    assert result["ready_for_signal"] is True
    assert result["mtf_aligned"] is True
    assert result["quality"] == "A"
    # ========================================================
    # CAS ACCEPTÉ À 50
    # ========================================================
    result = filtrer_qualite(
        direction=BUY,
        score_result={
            "final_score": 50,
            "confirmations": 3,
            "contradictions": 0,
        },
        rr_result={
            "rr_tp2": 2.0,
        },
        h4_bias="bullish",
        h1_bias="bullish",
        m15_bias="bullish",
        m5_bias="bullish",
        news=None,
    )
    assert result["status"] == ACCEPT
    assert result["ready_for_signal"] is True
    assert result["score"] == 50
    assert result["minimum_score"] == 50
    assert result["rr"] == 2.0
    assert result["quality"] == "C"
    # ========================================================
    # SCORE 49 = REJECT
    # ========================================================
    result = filtrer_qualite(
        direction=BUY,
        score_result={
            "final_score": 49,
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
    )
    assert result["status"] == REJECT
    assert result["ready_for_signal"] is False
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
    assert result["ready_for_signal"] is False
    # ========================================================
    # CAS ANNONCE HIGH IMPACT
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
    assert result["ready_for_signal"] is False
    assert result["news_blocked"] is True
    # ========================================================
    # CAS CONFLIT MTF
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
    assert result["ready_for_signal"] is False
    assert result["mtf_aligned"] is False
    assert result["quality"] == "CONFLICT"
    # ========================================================
    # TEST SELL
    # ========================================================
    result = filtrer_qualite(
        direction=SELL,
        score_result={
            "final_score": 90,
            "confirmations": 5,
            "contradictions": 0,
        },
        rr_result={
            "rr_tp2": 2.5,
        },
        h4_bias="bearish",
        h1_bias="bearish",
        m15_bias="bearish",
        m5_bias="bearish",
        news=None,
    )
    assert result["status"] == ACCEPT
    assert result["ready_for_signal"] is True
    assert result["mtf_aligned"] is True
    logger.info(
        "Test filtre_qualite réussi."
    )
    print(
        "CONFIG SCORE 50 : OK"
    )
    print(
        "ACCEPT SCORE 50 : OK"
    )
    print(
        "SCORE 49 REJECT : OK"
    )
    print(
        "ACCEPT TEST : OK"
    )
    print(
        "RR TEST : OK"
    )
    print(
        "NEWS TEST : OK"
    )
    print(
        "MTF TEST : OK"
    )
    print(
        "SELL TEST : OK"
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
        print()
        print(
            "✅ FILTRE QUALITÉ : OK"
        )
        print(
            "Score minimum configuré : "
            f"{DEFAULT_MIN_SCORE}/100"
        )
        print(
            "RR minimum configuré : "
            f"{DEFAULT_MIN_RR}"
        )
        print(
            "Le filtre final est opérationnel."
        )
    except Exception as exc:
        print()
        print(
            "❌ TEST FILTRE QUALITÉ ÉCHOUÉ"
        )
        print(
            f"Erreur : {type(exc).__name__}: {exc}"
        )
        raise