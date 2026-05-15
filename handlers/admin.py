import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from telegram import Bot
from lib.config import BOT_TOKEN, ADMIN_IDS
from lib.database import (
    get_all_users, get_user, get_config, set_config, get_stats,
    add_task, ban_user, get_pending_withdrawals
)
from lib.keyboards import admin_keyboard, main_keyboard

bot = Bot(token=BOT_TOKEN)
admin_sessions: dict = {}

def is_admin(user_id):
    return user_id in ADMIN_IDS

async def handle_admin_panel(user_id):
    stats = get_stats()
    await bot.send_message(user_id,
        f"⚙️ *PANEL ADMIN — XAFEARN*\n━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👥 Total inscrits : *{stats['total_users']}*\n"
        f"✅ Comptes actifs : *{stats['registered_users']}*\n"
        f"🚫 Bannis : *{stats['banned_users']}*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💵 Soldes totaux : *{stats['total_balance']}F*\n"
        f"✅ Total payé : *{stats['total_paid']}F*\n"
        f"⏳ Retraits en attente : *{stats['pending_withdrawals']}*",
        parse_mode="Markdown", reply_markup=admin_keyboard())

async def handle_all_users(user_id):
    users = get_all_users()
    text = f"👥 *UTILISATEURS ({len(users)})*\n━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    for u in users[:25]:
        status = "🚫" if u.get("is_banned") else ("✅" if u.get("is_registered") else "⏳")
        text += f"{status} @{u.get('username','N/A')} — *{u.get('balance',0)}F*\n"
    if len(users) > 25:
        text += f"\n_...et {len(users)-25} autres_"
    await bot.send_message(user_id, text, parse_mode="Markdown")

async def handle_modify_prices(user_id):
    await bot.send_message(user_id,
        f"⚙️ *CONFIG ACTUELLE*\n━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🎁 Bonus journalier : *{get_config('bonus_daily')}F*\n"
        f"👥 Bonus parrainage : *{get_config('bonus_referral')}F*\n"
        f"✅ Bonus tâche : *{get_config('bonus_task')}F*\n"
        f"💸 Retrait minimum : *{get_config('min_withdrawal')}F*\n\n"
        f"`/setbonus 150` → bonus journalier\n"
        f"`/setref 100` → bonus parrainage\n"
        f"`/settask 50` → bonus tâche\n"
        f"`/setmin 1000` → retrait minimum",
        parse_mode="Markdown")

async def handle_add_task_start(user_id):
    admin_sessions[user_id] = {"action": "add_task", "step": "description"}
    await bot.send_message(user_id, "➕ *NOUVELLE TÂCHE*\n\nDécris la tâche :", parse_mode="Markdown")

async def handle_list_withdrawals(user_id):
    pending = get_pending_withdrawals()
    if not pending:
        await bot.send_message(user_id, "💸 *Aucune demande en attente.* ✅", parse_mode="Markdown"); return
    text = f"💸 *EN ATTENTE ({len(pending)})*\n━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    for w in pending:
        u = get_user(w["user_id"])
        name = f"@{u.get('username','N/A')}" if u else "N/A"
        text += f"🆔 *#{w['id']}* · {name} · *{w['amount']}F*\n"
    await bot.send_message(user_id, text, parse_mode="Markdown")

async def handle_ban_start(user_id):
    admin_sessions[user_id] = {"action": "ban"}
    await bot.send_message(user_id,
        "🚫 *BANNIR / DÉBANNIR*\n\nEnvoie l'ID du user :\n"
        "Bannir : `123456789`\nDébannir : `debannir 123456789`",
        parse_mode="Markdown")

async def handle_broadcast_start(user_id):
    admin_sessions[user_id] = {"action": "broadcast"}
    await bot.send_message(user_id, "📢 *BROADCAST*\n\nÉcris le message à envoyer à tous :", parse_mode="Markdown")

async def handle_admin_session(user_id, text):
    session = admin_sessions.get(user_id)
    if not session:
        return False
    action = session.get("action")
    if action == "add_task":
        step = session.get("step")
        if step == "description":
            session["description"] = text
            session["step"] = "link"
            await bot.send_message(user_id, "🔗 Lien de la tâche (ou `-` si aucun) :")
        elif step == "link":
            session["link"] = None if text.strip() == "-" else text.strip()
            session["step"] = "reward"
            await bot.send_message(user_id, f"💰 Récompense en F (défaut: {get_config('bonus_task')}F) :")
        elif step == "reward":
            try:
                reward = int(text.strip())
            except:
                reward = get_config("bonus_task")
            add_task(session["description"], session.get("link"), reward)
            await bot.send_message(user_id,
                f"✅ *Tâche ajoutée !*\n\n📝 {session['description']}\n💰 *{reward}F*",
                parse_mode="Markdown")
            del admin_sessions[user_id]
        return True
    elif action == "ban":
        t = text.strip()
        if t.startswith("debannir "):
            try:
                tid = int(t.replace("debannir ", ""))
                ban_user(tid, False)
                await bot.send_message(user_id, f"✅ User `{tid}` débanni.", parse_mode="Markdown")
                try:
                    await bot.send_message(tid, "✅ *Ton compte a été réactivé.*", parse_mode="Markdown")
                except:
                    pass
            except:
                await bot.send_message(user_id, "❌ ID invalide.")
        else:
            try:
                tid = int(t)
                ban_user(tid, True)
                await bot.send_message(user_id, f"🚫 User `{tid}` banni.", parse_mode="Markdown")
                try:
                    await bot.send_message(tid, "🚫 *Compte suspendu.*", parse_mode="Markdown")
                except:
                    pass
            except:
                await bot.send_message(user_id, "❌ ID invalide.")
        del admin_sessions[user_id]
        return True
    elif action == "broadcast":
        users = get_all_users()
        sent = 0
        for u in users:
            if u.get("is_registered") and not u.get("is_banned"):
                try:
                    await bot.send_message(u["user_id"],
                        f"📢 *Message XAFEARN*\n━━━━━━━━━━━━━━━━━━━━━━━\n\n{text}",
                        parse_mode="Markdown")
                    sent += 1
                except:
                    pass
        await bot.send_message(user_id, f"✅ *Broadcast : {sent} envoyés.*", parse_mode="Markdown")
        del admin_sessions[user_id]
        return True
    return False

async def handle_admin_command(user_id, text):
    parts = text.strip().split()
    cmd = parts[0] if parts else ""
    if cmd == "/setbonus" and len(parts) == 2:
        set_config("bonus_daily", parts[1])
        await bot.send_message(user_id, f"✅ Bonus journalier → *{parts[1]}F*", parse_mode="Markdown"); return True
    if cmd == "/setref" and len(parts) == 2:
        set_config("bonus_referral", parts[1])
        await bot.send_message(user_id, f"✅ Bonus parrainage → *{parts[1]}F*", parse_mode="Markdown"); return True
    if cmd == "/settask" and len(parts) == 2:
        set_config("bonus_task", parts[1])
        await bot.send_message(user_id, f"✅ Bonus tâche → *{parts[1]}F*", parse_mode="Markdown"); return True
    if cmd == "/setmin" and len(parts) == 2:
        set_config("min_withdrawal", parts[1])
        await bot.send_message(user_id, f"✅ Retrait minimum → *{parts[1]}F*", parse_mode="Markdown"); return True
    if cmd == "/admin":
        await handle_admin_panel(user_id); return True
    return False