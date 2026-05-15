import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from telegram import Bot
from lib.config import BOT_TOKEN, RETRAIT_CHANNEL_ID, BOT_USERNAME
from lib.database import (
    get_user, get_config, update_balance, create_withdrawal,
    update_withdrawal_status, get_withdrawal_by_id, add_transaction
)
from lib.keyboards import methode_retrait_keyboard, retrait_channel_keyboard

bot = Bot(token=BOT_TOKEN)
retrait_sessions: dict = {}

def _mask(number):
    n = number.replace(" ", "")
    return n[:4] + " *** ** ** " + n[-2:] if len(n) >= 6 else number

async def handle_retrait_start(user_id):
    u = get_user(user_id)
    if not u or u.get("is_banned") or not u.get("is_registered"):
        await bot.send_message(user_id, "❌ Compte non valide."); return
    min_w = get_config("min_withdrawal")
    if u["balance"] < min_w:
        await bot.send_message(user_id,
            f"❌ *Solde insuffisant*\n\n💼 Solde : *{u['balance']}F*\n📌 Minimum : *{min_w}F*",
            parse_mode="Markdown"); return
    await bot.send_message(user_id,
        f"💸 *DEMANDE DE RETRAIT*\n━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💼 Solde : *{u['balance']}F*\n📌 Minimum : *{min_w}F*\n\nChoisis ta méthode 👇",
        parse_mode="Markdown", reply_markup=methode_retrait_keyboard())

async def handle_retrait_method(user_id, method, message_id):
    retrait_sessions[user_id] = {"method": method, "step": "amount"}
    label = "📱 Mobile Money" if method == "mobile" else "🏦 Virement Bancaire"
    await bot.edit_message_text(
        f"💸 *{label}*\n━━━━━━━━━━━━━━━━━━━━━━━\n\nCombien veux-tu retirer ? (en F) 👇",
        chat_id=user_id, message_id=message_id, parse_mode="Markdown")

async def handle_retrait_step(user_id, text):
    session = retrait_sessions.get(user_id)
    if not session:
        return False
    u = get_user(user_id)
    min_w = get_config("min_withdrawal")
    step = session.get("step")
    if step == "amount":
        try:
            amount = int(text.strip())
        except:
            await bot.send_message(user_id, "❌ Montant invalide (ex: 500)"); return True
        if amount < min_w:
            await bot.send_message(user_id, f"❌ Minimum : *{min_w}F*", parse_mode="Markdown"); return True
        if amount > u["balance"]:
            await bot.send_message(user_id, f"❌ Solde insuffisant ! (*{u['balance']}F*)", parse_mode="Markdown"); return True
        session["amount"] = amount
        session["step"] = "number"
        await bot.send_message(user_id, f"✅ Montant : *{amount}F*\n\n📱 Ton numéro de paiement :", parse_mode="Markdown")
        return True
    elif step == "number":
        if len(text.strip()) < 8:
            await bot.send_message(user_id, "❌ Numéro invalide."); return True
        session["number"] = text.strip()
        session["step"] = "name"
        await bot.send_message(user_id, "✅ Numéro enregistré.\n\n👤 Ton nom complet :", parse_mode="Markdown")
        return True
    elif step == "name":
        if len(text.strip()) < 3:
            await bot.send_message(user_id, "❌ Nom invalide."); return True
        session["name"] = text.strip()
        amount = session["amount"]
        update_balance(user_id, -amount)
        w_id = create_withdrawal(user_id, amount, session["method"], session["number"], session["name"])
        add_transaction(user_id, "retrait", -amount, f"Demande retrait #{w_id}")
        if w_id:
            await _send_to_channel(user_id, session, w_id)
        new_u = get_user(user_id)
        await bot.send_message(user_id,
            f"✅ *Demande envoyée !*\n━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"💵 Montant : *{amount}F*\n"
            f"📱 Numéro : *{_mask(session['number'])}*\n"
            f"👤 Nom : *{session['name']}*\n\n"
            f"💼 Solde restant : *{new_u['balance']}F*\n\n⏳ _En cours de traitement..._",
            parse_mode="Markdown")
        del retrait_sessions[user_id]
        return True
    return True

async def _send_to_channel(user_id, session, w_id):
    if not RETRAIT_CHANNEL_ID:
        return
    u = get_user(user_id)
    label = "📱 Mobile Money" if session["method"] == "mobile" else "🏦 Virement"
    await bot.send_message(RETRAIT_CHANNEL_ID,
        f"💸 *DEMANDE DE RETRAIT #{w_id}*\n━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💵 Montant : *{session['amount']}F*\n"
        f"⚙️ Méthode : *{label}*\n"
        f"📱 Numéro : *{_mask(session['number'])}*\n"
        f"👤 Nom : *{session['name']}*\n\n"
        f"👤 User : @{u.get('username','N/A')}\n"
        f"🆔 ID : `{user_id}`\n━━━━━━━━━━━━━━━━━━━━━━━",
        parse_mode="Markdown", reply_markup=retrait_channel_keyboard(w_id))

async def handle_cancel_retrait(user_id, message_id):
    if user_id in retrait_sessions:
        del retrait_sessions[user_id]
    await bot.edit_message_text("❌ *Retrait annulé.*",
        chat_id=user_id, message_id=message_id, parse_mode="Markdown")

async def handle_retrait_decision(admin_id, decision, w_id, message_id, chat_id):
    w = get_withdrawal_by_id(w_id)
    if not w or w.get("status") != "pending":
        return
    u = get_user(w["user_id"])
    label = "📱 Mobile Money" if w["method"] == "mobile" else "🏦 Virement"
    masked = _mask(w["number"])
    if decision == "approve":
        update_withdrawal_status(w_id, "approved")
        await bot.edit_message_text(
            f"✅ *PAIEMENT EFFECTUÉ*\n━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"💰 Montant : *{w['amount']}F*\n⚙️ Méthode : *{label}*\n"
            f"📱 Numéro : *{masked}*\n👤 Nom : *{w['name']}*\n\n"
            f"🤖 Via @{BOT_USERNAME}\n➡️ _Rejoins et gagne toi aussi !_",
            chat_id=chat_id, message_id=message_id, parse_mode="Markdown")
        try:
            await bot.send_message(w["user_id"],
                f"✅ *Retrait approuvé !*\n\n💵 *{w['amount']}F* envoyé. Merci ! 🙏",
                parse_mode="Markdown")
        except:
            pass
    else:
        update_withdrawal_status(w_id, "rejected")
        update_balance(w["user_id"], w["amount"])
        add_transaction(w["user_id"], "remboursement", w["amount"], f"Retrait #{w_id} refusé")
        await bot.edit_message_text(f"❌ *RETRAIT REJETÉ #{w_id}*",
            chat_id=chat_id, message_id=message_id, parse_mode="Markdown")
        try:
            await bot.send_message(w["user_id"],
                f"❌ *Retrait refusé*\n\n💵 *{w['amount']}F* remboursé.\n📩 @xafearn_support",
                parse_mode="Markdown")
        except:
            pass