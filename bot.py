"""
Vision Trade AI V2
bot.py

Interface Telegram principale.

Responsabilités :
- démarrer le bot Telegram ;
- afficher le menu principal ;
- recevoir les commandes utilisateur ;
- lancer une analyse à la demande ;
- afficher le statut du système ;
- transmettre les résultats des modules supérieurs ;
- ne pas effectuer lui-même les calculs techniques.

IMPORTANT :
- aucune logique de trading dans ce fichier ;
- aucun calcul de score ;
- aucun calcul de RR ;
- aucune décision Groq ;
- aucun calcul d'indicateurs ;
- aucune détection SMC ;
- aucun calcul de SL/TP.

Le bot sert uniquement d'interface Telegram.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)

from config import TELEGRAM_TOKEN


# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format=(
        "%(asctime)s | %(levelname)s | "
        "%(name)s | %(message)s"
    ),
)

logger = logging.getLogger(__name__)


# ============================================================
# CONSTANTES
# ============================================================

BOT_NAME = "VISION TRADE AI V2"

DEFAULT_SYMBOL = "XAU/USD"


# ============================================================
# ÉTAT DU BOT
# ============================================================

BOT_STATE: Dict[str, Any] = {
    "running": False,
    "last_analysis": None,
    "last_signal": None,
}


# ============================================================
# MENU
# ============================================================

def construire_menu() -> InlineKeyboardMarkup:
    """
    Construit le menu principal Telegram.
    """

    keyboard = [
        [
            InlineKeyboardButton(
                "🔎 Analyser",
                callback_data="analyse",
            ),
        ],
        [
            InlineKeyboardButton(
                "📊 Statut",
                callback_data="status",
            ),
            InlineKeyboardButton(
                "ℹ️ À propos",
                callback_data="about",
            ),
        ],
        [
            InlineKeyboardButton(
                "🔄 Actualiser",
                callback_data="refresh",
            ),
        ],
    ]

    return InlineKeyboardMarkup(
        keyboard
    )


# ============================================================
# MESSAGE D'ACCUEIL
# ============================================================

def message_accueil() -> str:
    """
    Message principal du bot.
    """

    return (
        "🤖 <b>VISION TRADE AI V2</b>\n"
        "\n"
        "Système d'analyse de marché "
        "déterministe + interprétation IA.\n"
        "\n"
        "📊 Analyse multi-timeframe\n"
        "🧠 SMC / ICT\n"
        "📐 Fibonacci\n"
        "📈 Indicateurs\n"
        "🎯 Score déterministe\n"
        "⚖️ Risk / Reward\n"
        "🛡️ Filtre qualité\n"
        "🚨 Génération de signal\n"
        "\n"
        "Choisis une action :"
    )


# ============================================================
# /START
# ============================================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """
    Commande /start.
    """

    if not update.effective_message:
        return

    BOT_STATE["running"] = True

    await update.effective_message.reply_text(
        message_accueil(),
        parse_mode=ParseMode.HTML,
        reply_markup=construire_menu(),
    )


# ============================================================
# /HELP
# ============================================================

async def help_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """
    Commande /help.
    """

    if not update.effective_message:
        return

    message = (
        "📚 <b>COMMANDES</b>\n"
        "\n"
        "/start — ouvrir le menu\n"
        "/analyse — lancer une analyse\n"
        "/status — afficher le statut\n"
        "/help — afficher cette aide\n"
        "\n"
        "Le bot ne génère un signal que "
        "si toutes les conditions déterministes "
        "sont validées."
    )

    await update.effective_message.reply_text(
        message,
        parse_mode=ParseMode.HTML,
        reply_markup=construire_menu(),
    )


# ============================================================
# /STATUS
# ============================================================

async def status_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """
    Commande /status.
    """

    if not update.effective_message:
        return

    running = BOT_STATE.get(
        "running",
        False,
    )

    last_analysis = BOT_STATE.get(
        "last_analysis"
    )

    last_signal = BOT_STATE.get(
        "last_signal"
    )

    status_text = (
        "🟢 EN LIGNE"
        if running
        else "🟡 INITIALISATION"
    )

    analysis_status = (
        "Disponible"
        if last_analysis
        else "Aucune analyse"
    )

    signal_status = (
        "Disponible"
        if last_signal
        else "Aucun signal"
    )

    message = (
        "📊 <b>STATUT VISION TRADE AI V2</b>\n"
        "\n"
        f"🤖 Bot : {status_text}\n"
        f"🔎 Dernière analyse : {analysis_status}\n"
        f"🚨 Dernier signal : {signal_status}\n"
        f"📌 Symbole par défaut : {DEFAULT_SYMBOL}\n"
    )

    await update.effective_message.reply_text(
        message,
        parse_mode=ParseMode.HTML,
        reply_markup=construire_menu(),
    )


# ============================================================
# /ANALYSE
# ============================================================

async def analyse_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """
    Commande /analyse.

    L'analyse réelle sera fournie par analyse.py.
    """

    if not update.effective_message:
        return

    await update.effective_message.reply_text(
        (
            "🔎 <b>ANALYSE</b>\n"
            "\n"
            f"📊 Marché : {DEFAULT_SYMBOL}\n"
            "\n"
            "⏳ Préparation de l'analyse..."
        ),
        parse_mode=ParseMode.HTML,
    )

    try:
        from analyse import analyser_marche

        result = analyser_marche(
            symbol=DEFAULT_SYMBOL
        )

        BOT_STATE["last_analysis"] = result

        message = formater_resultat_analyse(
            result
        )

        await update.effective_message.reply_text(
            message,
            parse_mode=ParseMode.HTML,
            reply_markup=construire_menu(),
        )

    except Exception as exc:

        logger.exception(
            "Erreur pendant l'analyse."
        )

        await update.effective_message.reply_text(
            (
                "❌ <b>ANALYSE IMPOSSIBLE</b>\n"
                "\n"
                f"Erreur : <code>{str(exc)}</code>"
            ),
            parse_mode=ParseMode.HTML,
            reply_markup=construire_menu(),
        )


# ============================================================
# FORMATAGE ANALYSE
# ============================================================

def formater_resultat_analyse(
    result: Any,
) -> str:
    """
    Transforme le résultat de analyse.py
    en message Telegram.

    Cette fonction ne modifie aucune donnée.
    """

    if not isinstance(
        result,
        dict,
    ):
        return (
            "📊 <b>RÉSULTAT</b>\n"
            "\n"
            f"<code>{str(result)}</code>"
        )

    status = result.get(
        "status",
        "UNKNOWN",
    )

    symbol = result.get(
        "symbol",
        DEFAULT_SYMBOL,
    )

    direction = result.get(
        "direction",
        "N/A",
    )

    score_data = result.get(
        "score",
        {},
    )

    rr_data = result.get(
        "rr",
        {},
    )

    quality_data = result.get(
        "quality",
        {},
    )

    score = (
        score_data.get(
            "final_score",
            score_data.get(
                "score",
                0,
            ),
        )
        if isinstance(
            score_data,
            dict,
        )
        else 0
    )

    rr = (
        rr_data.get(
            "rr_tp2",
            rr_data.get(
                "rr",
                0,
            ),
        )
        if isinstance(
            rr_data,
            dict,
        )
        else 0
    )

    quality = (
        quality_data.get(
            "quality",
            "N/A",
        )
        if isinstance(
            quality_data,
            dict,
        )
        else "N/A"
    )

    if status == "ACCEPT":
        emoji = "🟢"
    elif status == "WAIT":
        emoji = "🟡"
    else:
        emoji = "🔴"

    return (
        f"{emoji} <b>VISION TRADE AI V2</b>\n"
        "\n"
        f"📊 Marché : <b>{symbol}</b>\n"
        f"📌 Direction : <b>{direction}</b>\n"
        f"📈 Score : <b>{score}/100</b>\n"
        f"⚖️ RR : <b>{rr}</b>\n"
        f"🏆 Qualité : <b>{quality}</b>\n"
        f"📋 Statut : <b>{status}</b>\n"
    )


# ============================================================
# /ABOUT
# ============================================================

async def about_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """
    Informations sur Vision Trade AI V2.
    """

    if not update.effective_message:
        return

    message = (
        "ℹ️ <b>VISION TRADE AI V2</b>\n"
        "\n"
        "Architecture modulaire.\n"
        "\n"
        "📥 Données marché\n"
        "   ↓\n"
        "📈 Indicateurs\n"
        "   ↓\n"
        "🏗️ Structure / SMC\n"
        "   ↓\n"
        "📐 Fibonacci\n"
        "   ↓\n"
        "🧮 Score\n"
        "   ↓\n"
        "⚖️ Risk / Reward\n"
        "   ↓\n"
        "🛡️ Filtre qualité\n"
        "   ↓\n"
        "🔎 Analyse\n"
        "   ↓\n"
        "🚨 Signal\n"
        "   ↓\n"
        "📱 Telegram\n"
        "\n"
        "L'IA intervient uniquement pour "
        "l'interprétation prévue par l'architecture."
    )

    await update.effective_message.reply_text(
        message,
        parse_mode=ParseMode.HTML,
        reply_markup=construire_menu(),
    )


# ============================================================
# CALLBACK MENU
# ============================================================

async def callback_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """
    Gestion des boutons InlineKeyboard.
    """

    query = update.callback_query

    if query is None:
        return

    await query.answer()

    action = query.data

    if action == "analyse":

        await query.message.reply_text(
            "🔎 Lancement de l'analyse..."
        )

        try:
            from analyse import analyser_marche

            result = analyser_marche(
                symbol=DEFAULT_SYMBOL
            )

            BOT_STATE["last_analysis"] = result

            await query.message.reply_text(
                formater_resultat_analyse(
                    result
                ),
                parse_mode=ParseMode.HTML,
                reply_markup=construire_menu(),
            )

        except Exception as exc:

            logger.exception(
                "Erreur analyse bouton."
            )

            await query.message.reply_text(
                (
                    "❌ Erreur pendant l'analyse.\n"
                    f"<code>{str(exc)}</code>"
                ),
                parse_mode=ParseMode.HTML,
                reply_markup=construire_menu(),
            )

    elif action == "status":

        running = BOT_STATE.get(
            "running",
            False,
        )

        status = (
            "🟢 EN LIGNE"
            if running
            else "🟡 INITIALISATION"
        )

        await query.message.reply_text(
            (
                "📊 <b>STATUT</b>\n"
                "\n"
                f"Bot : {status}\n"
                f"Marché par défaut : {DEFAULT_SYMBOL}"
            ),
            parse_mode=ParseMode.HTML,
            reply_markup=construire_menu(),
        )

    elif action == "about":

        await query.message.reply_text(
            (
                "🤖 <b>VISION TRADE AI V2</b>\n"
                "\n"
                "Système modulaire d'analyse "
                "multi-timeframe et de génération "
                "de signaux."
            ),
            parse_mode=ParseMode.HTML,
            reply_markup=construire_menu(),
        )

    elif action == "refresh":

        await query.message.reply_text(
            message_accueil(),
            parse_mode=ParseMode.HTML,
            reply_markup=construire_menu(),
        )


# ============================================================
# ERREURS
# ============================================================

async def error_handler(
    update: object,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """
    Gestionnaire global des erreurs Telegram.
    """

    logger.error(
        "Erreur Telegram : %s",
        context.error,
        exc_info=context.error,
    )


# ============================================================
# CONSTRUCTION APPLICATION
# ============================================================

def construire_application() -> Application:
    """
    Construit l'application Telegram.
    """

    if not TELEGRAM_TOKEN:

        raise ValueError(
            "TELEGRAM_TOKEN est absent de config.py "
            "ou des variables d'environnement."
        )

    application = (
        Application.builder()
        .token(TELEGRAM_TOKEN)
        .build()
    )

    # --------------------------------------------------------
    # COMMANDES
    # --------------------------------------------------------

    application.add_handler(
        CommandHandler(
            "start",
            start,
        )
    )

    application.add_handler(
        CommandHandler(
            "help",
            help_command,
        )
    )

    application.add_handler(
        CommandHandler(
            "status",
            status_command,
        )
    )

    application.add_handler(
        CommandHandler(
            "analyse",
            analyse_command,
        )
    )

    application.add_handler(
        CommandHandler(
            "about",
            about_command,
        )
    )

    # --------------------------------------------------------
    # BOUTONS
    # --------------------------------------------------------

    application.add_handler(
        CallbackQueryHandler(
            callback_handler
        )
    )

    # --------------------------------------------------------
    # ERREURS
    # --------------------------------------------------------

    application.add_error_handler(
        error_handler
    )

    return application


# ============================================================
# DÉMARRAGE
# ============================================================

def main() -> None:
    """
    Point d'entrée principal.
    """

    logger.info(
        "%s démarrage...",
        BOT_NAME,
    )

    application = construire_application()

    BOT_STATE["running"] = True

    logger.info(
        "Bot Telegram prêt."
    )

    logger.info(
        "Commandes disponibles : "
        "/start /analyse /status /help /about"
    )

    application.run_polling(
        drop_pending_updates=True
    )


# ============================================================
# EXÉCUTION DIRECTE
# ============================================================

if __name__ == "__main__":
    main()