"""
Vision Trade AI V2
Configuration centrale du bot.

Aucune logique de trading ne doit être placée ici.
Les secrets sont récupérés depuis les variables d'environnement.
"""

import os


# ============================================================
# API / SERVICES
# ============================================================

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "").strip()
CANAL_ID = os.getenv("CANAL_ID", "").strip()

TWELVE_DATA_KEY = os.getenv("TWELVE_DATA_KEY", "").strip()
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()


# ============================================================
# MARCHÉS
# ============================================================

# Aucun indice "Volatility" n'est inclus.
# La liste peut être étendue ultérieurement.

MARKETS = [
    "XAU/USD",
    "EUR/USD",
    "GBP/USD",
    "USD/JPY",
    "AUD/USD",
    "USD/CAD",
    "USD/CHF",
    "NZD/USD",
    "BTC/USD",
]


# ============================================================
# TIMEFRAMES
# ============================================================

TIMEFRAMES = {
    "trend": "4h",
    "structure": "1h",
    "zone": "15min",
    "trigger": "5min",
}


H4_TIMEFRAME = TIMEFRAMES["trend"]
H1_TIMEFRAME = TIMEFRAMES["structure"]
M15_TIMEFRAME = TIMEFRAMES["zone"]
M5_TIMEFRAME = TIMEFRAMES["trigger"]


# ============================================================
# DONNÉES DE MARCHÉ
# ============================================================

# Nombre de bougies demandées pour chaque analyse.
CANDLE_LIMIT = 300

# Nombre minimum de bougies nécessaires
# pour considérer une analyse exploitable.
MIN_CANDLES = 100


# ============================================================
# INDICATEURS
# ============================================================

EMA_FAST = 20
EMA_SLOW = 50

RSI_PERIOD = 14
ATR_PERIOD = 14


# ============================================================
# SCORE
# ============================================================

# Score minimum permettant de poursuivre l'analyse.
MIN_SCORE = 50

# Score recommandé pour générer un signal.
SIGNAL_SCORE = 50

# Classification des setups.
SCORE_A_PLUS = 90
SCORE_A = 80
SCORE_B = 50


# ============================================================
# RISK / REWARD
# ============================================================

MIN_RR = 2.0

# Risque théorique maximal par trade.
# Cette valeur sert de configuration du moteur.
RISK_PER_TRADE = 0.01

# Limites de sécurité.
MAX_DAILY_SIGNALS = 5
MAX_CONSECUTIVE_LOSSES = 3


# ============================================================
# ANNONCES ÉCONOMIQUES
# ============================================================

# Fenêtre avant une annonce majeure pendant laquelle
# le bot peut bloquer les nouveaux signaux.
NEWS_BLOCK_BEFORE_MINUTES = 30

# Temps d'attente après une annonce majeure.
NEWS_BLOCK_AFTER_MINUTES = 15


# Impacts considérés comme importants.
NEWS_HIGH_IMPACTS = {
    "high",
    "3",
}


# ============================================================
# SURVEILLANCE
# ============================================================

# Intervalle général entre deux cycles de surveillance.
SCAN_INTERVAL_SECONDS = 60

# Délai minimum entre deux signaux similaires.
SIGNAL_COOLDOWN_MINUTES = 60


# ============================================================
# GROQ
# ============================================================

GROQ_MODEL = "llama-3.3-70b-versatile"

GROQ_TIMEOUT_SECONDS = 30


# ============================================================
# LOGGING
# ============================================================

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()


# ============================================================
# VALIDATION DE CONFIGURATION
# ============================================================

def configuration_status():
    """
    Retourne l'état des principales variables de configuration.

    Les clés secrètes elles-mêmes ne sont jamais retournées.
    """

    return {
        "telegram_token": bool(TELEGRAM_TOKEN),
        "canal_id": bool(CANAL_ID),
        "twelve_data_key": bool(TWELVE_DATA_KEY),
        "groq_api_key": bool(GROQ_API_KEY),
        "markets_count": len(MARKETS),
        "timeframes": TIMEFRAMES.copy(),
    }


def validate_configuration(require_secrets=False):
    """
    Vérifie la cohérence de la configuration.

    Args:
        require_secrets:
            Si True, les clés API et Telegram deviennent obligatoires.

    Raises:
        ValueError:
            Si une configuration obligatoire est absente ou invalide.
    """

    if not MARKETS:
        raise ValueError("MARKETS est vide.")

    required_timeframes = {
        "trend",
        "structure",
        "zone",
        "trigger",
    }

    missing_timeframes = required_timeframes - set(TIMEFRAMES)

    if missing_timeframes:
        raise ValueError(
            f"Timeframes manquants : {sorted(missing_timeframes)}"
        )

    if CANDLE_LIMIT < MIN_CANDLES:
        raise ValueError(
            "CANDLE_LIMIT doit être supérieur ou égal à MIN_CANDLES."
        )

    if MIN_RR <= 0:
        raise ValueError("MIN_RR doit être supérieur à 0.")

    if not 0 < RISK_PER_TRADE <= 1:
        raise ValueError(
            "RISK_PER_TRADE doit être compris entre 0 et 1."
        )

    if MIN_SCORE < 0 or MIN_SCORE > 100:
        raise ValueError("MIN_SCORE doit être compris entre 0 et 100.")

    if SIGNAL_SCORE < MIN_SCORE:
        raise ValueError(
            "SIGNAL_SCORE ne peut pas être inférieur à MIN_SCORE."
        )

    if require_secrets:
        missing = []

        if not TELEGRAM_TOKEN:
            missing.append("TELEGRAM_TOKEN")

        if not CANAL_ID:
            missing.append("CANAL_ID")

        if not TWELVE_DATA_KEY:
            missing.append("TWELVE_DATA_KEY")

        if not GROQ_API_KEY:
            missing.append("GROQ_API_KEY")

        if missing:
            raise ValueError(
                "Variables d'environnement manquantes : "
                + ", ".join(missing)
            )

    return True


# Validation structurelle au chargement du module.
validate_configuration()