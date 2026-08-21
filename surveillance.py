"""
Vision Trade AI V2
surveillance.py

Moteur de surveillance automatique des marchés.

Responsabilités :
- surveiller plusieurs symboles ;
- respecter l'état du marché ;
- lancer les analyses ;
- éviter les doublons ;
- appliquer l'anti-spam ;
- transmettre uniquement les résultats exploitables ;
- ne pas effectuer lui-même les calculs techniques.

IMPORTANT :
- aucune IA directement dans ce module ;
- aucun calcul de score ;
- aucun calcul de RR ;
- aucune modification du signal ;
- aucune décision Groq ;
- aucun envoi Telegram direct.

analyse.py reste responsable de la chaîne d'analyse.
signal.py reste responsable de la génération du signal.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


logger = logging.getLogger(__name__)


# ============================================================
# CONSTANTES
# ============================================================

DEFAULT_SCAN_INTERVAL = 900
DEFAULT_ANTISPAM_SECONDS = 4 * 60 * 60

DEFAULT_SYMBOLS = (
    "XAU/USD",
    "BTC/USD",
    "EUR/USD",
)


# ============================================================
# MODÈLE
# ============================================================

@dataclass
class SurveillanceResult:
    """
    Résultat d'une surveillance.
    """

    symbol: str
    status: str
    direction: str
    score: float
    rr: float
    quality: str
    signal: Optional[Dict[str, Any]]
    timestamp: float


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


# ============================================================
# CLASSE DE SURVEILLANCE
# ============================================================

class MarketSurveillance:
    """
    Gestionnaire de surveillance automatique.
    """

    def __init__(
        self,
        symbols: Optional[List[str]] = None,
        scan_interval: int = DEFAULT_SCAN_INTERVAL,
        antispam_seconds: int = DEFAULT_ANTISPAM_SECONDS,
    ) -> None:

        self.symbols = tuple(
            symbols
            or DEFAULT_SYMBOLS
        )

        self.scan_interval = _safe_int(
            scan_interval,
            DEFAULT_SCAN_INTERVAL,
        )

        self.antispam_seconds = _safe_int(
            antispam_seconds,
            DEFAULT_ANTISPAM_SECONDS,
        )

        if self.scan_interval <= 0:
            raise ValueError(
                "scan_interval doit être supérieur à 0."
            )

        if self.antispam_seconds < 0:
            raise ValueError(
                "antispam_seconds ne peut pas être négatif."
            )

        self.last_signals: Dict[
            str,
            float,
        ] = {}

        self.last_results: Dict[
            str,
            Dict[str, Any],
        ] = {}

        self.running = False

    # ========================================================
    # ANTI-SPAM
    # ========================================================

    def peut_generer_signal(
        self,
        symbol: str,
        now: Optional[float] = None,
    ) -> bool:
        """
        Vérifie si un nouveau signal peut être généré
        pour un symbole.
        """

        symbol = str(
            symbol
        ).upper().strip()

        current_time = (
            time.time()
            if now is None
            else float(now)
        )

        last_signal = self.last_signals.get(
            symbol
        )

        if last_signal is None:
            return True

        elapsed = (
            current_time
            - last_signal
        )

        return (
            elapsed
            >= self.antispam_seconds
        )

    # ========================================================
    # ENREGISTREMENT SIGNAL
    # ========================================================

    def enregistrer_signal(
        self,
        symbol: str,
        timestamp: Optional[float] = None,
    ) -> None:
        """
        Enregistre l'heure du dernier signal.
        """

        symbol = str(
            symbol
        ).upper().strip()

        self.last_signals[
            symbol
        ] = (
            time.time()
            if timestamp is None
            else float(timestamp)
        )

    # ========================================================
    # EXTRACTION
    # ========================================================

    def _extraire_score(
        self,
        analysis: Dict[str, Any],
    ) -> float:
        """
        Extrait le score d'une analyse.
        """

        score = analysis.get(
            "score",
            {},
        )

        if isinstance(
            score,
            dict,
        ):
            return _safe_float(
                score.get(
                    "final_score",
                    score.get(
                        "score",
                        0,
                    ),
                )
            )

        return _safe_float(
            score
        )

    def _extraire_rr(
        self,
        analysis: Dict[str, Any],
    ) -> float:
        """
        Extrait le RR.
        """

        rr = analysis.get(
            "rr",
            {},
        )

        if isinstance(
            rr,
            dict,
        ):
            return _safe_float(
                rr.get(
                    "rr_tp2",
                    rr.get(
                        "rr",
                        0,
                    ),
                )
            )

        return _safe_float(
            rr
        )

    def _extraire_quality(
        self,
        analysis: Dict[str, Any],
    ) -> str:
        """
        Extrait la qualité.
        """

        quality = analysis.get(
            "quality",
            {},
        )

        if isinstance(
            quality,
            dict,
        ):
            return str(
                quality.get(
                    "quality",
                    "UNKNOWN",
                )
            )

        return str(
            quality
            or "UNKNOWN"
        )

    # ========================================================
    # ANALYSE D'UN MARCHÉ
    # ========================================================

    def analyser_symbol(
        self,
        symbol: str,
    ) -> SurveillanceResult:
        """
        Lance l'analyse complète d'un symbole.
        """

        symbol = str(
            symbol
        ).upper().strip()

        timestamp = time.time()

        logger.info(
            "Surveillance de %s...",
            symbol,
        )

        try:

            from analyse import analyser_marche

            analysis = analyser_marche(
                symbol=symbol
            )

            if not isinstance(
                analysis,
                dict,
            ):
                raise ValueError(
                    "analyse_marche() doit retourner un dictionnaire."
                )

            status = str(
                analysis.get(
                    "status",
                    "REJECT",
                )
            ).upper()

            direction = str(
                analysis.get(
                    "direction",
                    "",
                )
            ).upper()

            score = self._extraire_score(
                analysis
            )

            rr = self._extraire_rr(
                analysis
            )

            quality = self._extraire_quality(
                analysis
            )

            signal = None

            # ------------------------------------------------
            # SIGNAL
            # ------------------------------------------------

            if status == "ACCEPT":

                if self.peut_generer_signal(
                    symbol
                ):

                    try:

                        from signal import generer_signal

                        signal = generer_signal(
                            analysis
                        )

                        if (
                            isinstance(
                                signal,
                                dict,
                            )
                            and signal.get(
                                "ready"
                            )
                        ):

                            self.enregistrer_signal(
                                symbol
                            )

                            logger.info(
                                "Nouveau signal généré pour %s.",
                                symbol,
                            )

                    except Exception:

                        logger.exception(
                            "Erreur génération signal %s.",
                            symbol,
                        )

                else:

                    logger.info(
                        "Anti-spam actif pour %s.",
                        symbol,
                    )

            result = SurveillanceResult(
                symbol=symbol,

                status=status,

                direction=direction,

                score=score,

                rr=rr,

                quality=quality,

                signal=signal,

                timestamp=timestamp,
            )

            self.last_results[
                symbol
            ] = {
                "symbol": symbol,
                "status": status,
                "direction": direction,
                "score": score,
                "rr": rr,
                "quality": quality,
                "signal": signal,
                "timestamp": timestamp,
            }

            return result

        except Exception as exc:

            logger.exception(
                "Erreur surveillance %s.",
                symbol,
            )

            result = SurveillanceResult(
                symbol=symbol,

                status="ERROR",

                direction="",

                score=0.0,

                rr=0.0,

                quality="ERROR",

                signal=None,

                timestamp=timestamp,
            )

            self.last_results[
                symbol
            ] = {
                "symbol": symbol,
                "status": "ERROR",
                "direction": "",
                "score": 0.0,
                "rr": 0.0,
                "quality": "ERROR",
                "signal": None,
                "timestamp": timestamp,
                "error": str(exc),
            }

            return result

    # ========================================================
    # SCAN COMPLET
    # ========================================================

    def scanner(
        self,
    ) -> List[SurveillanceResult]:
        """
        Effectue une analyse sur tous les symboles.
        """

        results = []

        logger.info(
            "Début du scan de %d marché(s).",
            len(self.symbols),
        )

        for symbol in self.symbols:

            try:

                result = self.analyser_symbol(
                    symbol
                )

                results.append(
                    result
                )

            except Exception:

                logger.exception(
                    "Erreur pendant le scan de %s.",
                    symbol,
                )

        logger.info(
            "Scan terminé : %d résultat(s).",
            len(results),
        )

        return results

    # ========================================================
    # SIGNALS PRÊTS
    # ========================================================

    def recuperer_signaux(
        self,
        results: Optional[
            List[SurveillanceResult]
        ] = None,
    ) -> List[Dict[str, Any]]:
        """
        Retourne uniquement les signaux prêts.
        """

        if results is None:

            results = [
                SurveillanceResult(
                    symbol=data.get(
                        "symbol",
                        "",
                    ),
                    status=data.get(
                        "status",
                        "ERROR",
                    ),
                    direction=data.get(
                        "direction",
                        "",
                    ),
                    score=_safe_float(
                        data.get(
                            "score",
                            0,
                        )
                    ),
                    rr=_safe_float(
                        data.get(
                            "rr",
                            0,
                        )
                    ),
                    quality=str(
                        data.get(
                            "quality",
                            "UNKNOWN",
                        )
                    ),
                    signal=data.get(
                        "signal"
                    ),
                    timestamp=_safe_float(
                        data.get(
                            "timestamp",
                            0,
                        )
                    ),
                )
                for data in self.last_results.values()
            ]

        signals = []

        for result in results:

            if not result.signal:
                continue

            if not isinstance(
                result.signal,
                dict,
            ):
                continue

            if result.signal.get(
                "ready"
            ) is not True:
                continue

            signals.append(
                result.signal
            )

        return signals

    # ========================================================
    # DÉMARRAGE
    # ========================================================

    def start(
        self,
    ) -> None:
        """
        Active la surveillance.
        """

        self.running = True

        logger.info(
            "Surveillance activée."
        )

    # ========================================================
    # ARRÊT
    # ========================================================

    def stop(
        self,
    ) -> None:
        """
        Désactive la surveillance.
        """

        self.running = False

        logger.info(
            "Surveillance arrêtée."
        )

    # ========================================================
    # BOUCLE
    # ========================================================

    def run_once(
        self,
    ) -> List[SurveillanceResult]:
        """
        Effectue un seul cycle de surveillance.
        """

        if not self.running:

            self.start()

        return self.scanner()


# ============================================================
# FONCTION PUBLIQUE
# ============================================================

def surveiller_marches(
    symbols: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """
    Interface simple pour effectuer un scan.
    """

    surveillance = MarketSurveillance(
        symbols=symbols
    )

    surveillance.start()

    results = surveillance.run_once()

    return [
        {
            "symbol": result.symbol,
            "status": result.status,
            "direction": result.direction,
            "score": result.score,
            "rr": result.rr,
            "quality": result.quality,
            "signal": result.signal,
            "timestamp": result.timestamp,
        }
        for result in results
    ]


# ============================================================
# TEST
# ============================================================

def _run_internal_test() -> None:
    """
    Tests internes du moteur de surveillance.
    """

    surveillance = MarketSurveillance(
        symbols=[
            "XAU/USD",
        ],
        scan_interval=900,
        antispam_seconds=14400,
    )

    # --------------------------------------------------------
    # ANTI-SPAM
    # --------------------------------------------------------

    assert surveillance.peut_generer_signal(
        "XAU/USD",
        now=1000,
    ) is True

    surveillance.enregistrer_signal(
        "XAU/USD",
        timestamp=1000,
    )

    assert surveillance.peut_generer_signal(
        "XAU/USD",
        now=1000 + 100,
    ) is False

    assert surveillance.peut_generer_signal(
        "XAU/USD",
        now=1000 + 14400,
    ) is True

    # --------------------------------------------------------
    # NORMALISATION
    # --------------------------------------------------------

    assert (
        surveillance.peut_generer_signal(
            "xau/usd",
            now=1000 + 14400,
        )
        is True
    )

    logger.info(
        "Test surveillance réussi."
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
        "VISION TRADE AI V2 - TEST SURVEILLANCE"
    )
    print("=" * 60)

    try:

        _run_internal_test()

        print(
            "\n✅ SURVEILLANCE : OK"
        )

        print(
            "Moteur de surveillance opérationnel."
        )

    except Exception as exc:

        print(
            "\n❌ TEST SURVEILLANCE ÉCHOUÉ"
        )

        print(
            f"Erreur : {exc}"
        )