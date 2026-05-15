import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from telegram import ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton

def main_keyboard():
    return ReplyKeyboardMarkup([
        ["🎁 Bonus Journalier",   "👥 Parrainage"],
        ["💰 Mon Solde",          "✅ Tâches du Jour"],
        ["📋 Historique",         "💸 Retrait"],
        ["🏆 Classement",         "❓ Aide"],
    ], resize_keyboard=True)

def admin_keyboard():
    return ReplyKeyboardMarkup([
        ["👥 Tous les Users",      "📊 Statistiques"],
        ["⚙️ Modifier les Prix",   "➕ Ajouter une Tâche"],
        ["💸 Demandes Retrait",    "🚫 Bannir / Débannir"],
        ["📢 Broadcast",           "🔙 Mode Utilisateur"],
    ], resize_keyboard=True)

def join_verify_keyboard():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ J'ai tout rejoint — Vérifier", callback_data="check_join")
    ]])

def retry_join_keyboard():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("🔄 Vérifier à nouveau", callback_data="check_join")
    ]])

def methode_retrait_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📱 Mobile Money",      callback_data="method_mobile")],
        [InlineKeyboardButton("🏦 Virement Bancaire", callback_data="method_bank")],
        [InlineKeyboardButton("❌ Annuler",            callback_data="cancel_retrait")],
    ])

def retrait_channel_keyboard(w_id: int):
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Approuver", callback_data=f"approve_{w_id}"),
        InlineKeyboardButton("❌ Rejeter",   callback_data=f"reject_{w_id}"),
    ]])

def tasks_keyboard(tasks: list, completed_ids: list):
    buttons = []
    for t in tasks:
        if t["id"] not in completed_ids:
            label = f"✅ Valider · {t['description'][:30]}"
            buttons.append([InlineKeyboardButton(label, callback_data=f"task_{t['id']}")])
    return InlineKeyboardMarkup(buttons) if buttons else None