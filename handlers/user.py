import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from telegram import Bot, InlineKeyboardMarkup, InlineKeyboardButton
from datetime import date
from lib.config import BOT_TOKEN, CHANNELS, BOT_USERNAME
from lib.database import (
    add_user, get_user, get_referral_count, update_balance,
    set_last_bonus, get_config, get_tasks_today, user_completed_task,
    complete_task, add_transaction, get_user_transactions,
    get_user_withdrawals, activate_user, get_top_referrers
)
from lib.keyboards import main_keyboard, join_verify_keyboard, retry_join_keyboard, tasks_keyboard

bot = Bot(token=BOT_TOKEN)

async def check_membership(user_id):
    for ch in CHANNELS:
        try:
            m = await bot.get_chat_member(ch, user_id)
            if m.status in ["left", "kicked"]:
                return False
        except:
            return False
    return True

def is_user_valid(user_id):
    u = get_user(user_id)
    if not u:
        return None, "❌ Utilise /start pour t'inscrire."
    if u.get("is_banned"):
        return None, "🚫 Ton compte est suspendu."
    if not u.get("is_registered"):
        return None, "⚠️ Rejoins d'abord nos canaux. Envoie /start"
    return u, None

async def handle_start(user_id, username, arg=None):
    referred_by = None
    if arg:
        try:
            ref = int(arg)
            if ref != user_id:
                referred_by = ref
        except:
            pass
    existing = get_user(user_id)
    if existing and existing.get("is_banned"):
        await bot.send_message(user_id, "🚫 *Compte suspendu.*", parse_mode="Markdown")
        return
    if not existing:
        add_user(user_id, username, referred_by)
    channels_list = "\n".join([f"  ➤ {ch}" for ch in CHANNELS])
    await bot.send_message(user_id,
        f"👑 *Bienvenue sur XAFEARN, {username} !*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💰 Gagne de l'argent chaque jour :\n"
        f"  🎁 Bonus journalier\n"
        f"  👥 Parrainage de proches\n"
        f"  ✅ Tâches quotidiennes\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📌 *Étape 1* — Rejoins nos canaux :\n\n"
        f"{channels_list}\n\n"
        f"📌 *Étape 2* — Clique sur le bouton ✅",
        parse_mode="Markdown", reply_markup=join_verify_keyboard()
    )

async def handle_check_join(user_id, message_id):
    user = get_user(user_id)
    if not user:
        await bot.send_message(user_id, "❌ Utilise /start d'abord.")
        return
    if not await check_membership(user_id):
        channels_list = "\n".join([f"  ➤ {ch}" for ch in CHANNELS])
        await bot.edit_message_text(
            f"❌ *Tu n'as pas encore tout rejoint.*\n\n{channels_list}\n\n_Puis clique sur Vérifier_ 👇",
            chat_id=user_id, message_id=message_id,
            parse_mode="Markdown", reply_markup=retry_join_keyboard()
        )
        return
    activate_user(user_id)
    if user.get("referred_by") and not user.get("is_registered"):
        parrain_id = user["referred_by"]
        parrain = get_user(parrain_id)
        if parrain and parrain.get("is_registered") and not parrain.get("is_banned"):
            bonus_ref = get_config("bonus_referral")
            update_balance(parrain_id, bonus_ref)
            add_transaction(parrain_id, "parrainage", bonus_ref, f"Filleul @{user.get('username','?')}")
            try:
                await bot.send_message(parrain_id,
                    f"🎉 *+{bonus_ref}F crédité !*\n\nTon filleul *@{user.get('username','?')}* vient de valider !",
                    parse_mode="Markdown")
            except:
                pass
    ref_link = f"https://t.me/{BOT_USERNAME}?start={user_id}"
    await bot.edit_message_text(
        f"✅ *Compte activé !*\n━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🔗 *Ton lien de parrainage :*\n`{ref_link}`",
        chat_id=user_id, message_id=message_id, parse_mode="Markdown"
    )
    await bot.send_message(user_id,
        "🏠 *Menu Principal — XAFEARN*\n\n_Que veux-tu faire ?_ 👇",
        parse_mode="Markdown", reply_markup=main_keyboard())

async def handle_bonus(user_id):
    u, err = is_user_valid(user_id)
    if err:
        await bot.send_message(user_id, err); return
    today = date.today()
    bonus = get_config("bonus_daily")
    if str(u.get("last_bonus")) == str(today):
        await bot.send_message(user_id,
            f"⏳ *Bonus déjà récupéré !*\n\n💼 Solde : *{u['balance']}F*\n🔔 Reviens demain pour +{bonus}F",
            parse_mode="Markdown"); return
    update_balance(user_id, bonus)
    set_last_bonus(user_id, str(today))
    add_transaction(user_id, "bonus", bonus, "Bonus journalier")
    new_user = get_user(user_id)
    await bot.send_message(user_id,
        f"🎁 *BONUS JOURNALIER REÇU !*\n━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💵 +*{bonus}F* crédité ✅\n💼 Nouveau solde : *{new_user['balance']}F*\n\n"
        f"📅 _Reviens demain pour un nouveau bonus !_",
        parse_mode="Markdown")

async def handle_solde(user_id):
    u, err = is_user_valid(user_id)
    if err:
        await bot.send_message(user_id, err); return
    nb = get_referral_count(user_id)
    bonus_ref = get_config("bonus_referral")
    ref_link = f"https://t.me/{BOT_USERNAME}?start={user_id}"
    await bot.send_message(user_id,
        f"💼 *TON COMPTE XAFEARN*\n━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💵 Solde : *{u['balance']}F*\n"
        f"👥 Filleuls : *{nb}*\n"
        f"💰 Gains parrainage : *{nb * bonus_ref}F*\n\n"
        f"🔗 *Lien :*\n`{ref_link}`",
        parse_mode="Markdown")

async def handle_parrainage(user_id):
    u, err = is_user_valid(user_id)
    if err:
        await bot.send_message(user_id, err); return
    nb = get_referral_count(user_id)
    bonus_ref = get_config("bonus_referral")
    ref_link = f"https://t.me/{BOT_USERNAME}?start={user_id}"
    await bot.send_message(user_id,
        f"👥 *TON LIEN D'AFFILIATION*\n━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🔗 {ref_link}\n\n"
        f"📊 Parrainages validés : *{nb}*\n"
        f"💰 Gain par parrainage : *{bonus_ref}F*\n"
        f"💵 Total gagné : *{nb * bonus_ref}F*\n\n"
        f"📤 _Partage et gagne {bonus_ref}F à chaque inscription !_ 🚀",
        parse_mode="Markdown")

async def handle_tasks(user_id):
    u, err = is_user_valid(user_id)
    if err:
        await bot.send_message(user_id, err); return
    tasks = get_tasks_today()
    if not tasks:
        await bot.send_message(user_id,
            "📋 *Aucune tâche disponible aujourd'hui.*\n\n⏳ Reviens plus tard !",
            parse_mode="Markdown"); return
    completed_ids = [t["id"] for t in tasks if user_completed_task(user_id, t["id"])]
    text = f"✅ *TÂCHES DU JOUR*\n━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    all_done = True
    for t in tasks:
        done = t["id"] in completed_ids
        status = "✅" if done else "⭕"
        text += f"{status} *{t['description']}*\n"
        if t.get("link"):
            text += f"   🔗 _{t['link']}_\n"
        text += f"   💰 Récompense : *{t['reward']}F*\n\n"
        if not done:
            all_done = False
    if all_done:
        text += "🎊 *Toutes les tâches complétées !* 🏆"
        kb = None
    else:
        kb = tasks_keyboard(tasks, completed_ids)
    await bot.send_message(user_id, text, parse_mode="Markdown", reply_markup=kb)

async def handle_task_complete(user_id, task_id, query_id):
    u, err = is_user_valid(user_id)
    if err:
        await bot.answer_callback_query(query_id, err, show_alert=True); return
    tasks = get_tasks_today()
    task = next((t for t in tasks if t["id"] == task_id), None)
    if not task:
        await bot.answer_callback_query(query_id, "❌ Tâche introuvable.", show_alert=True); return
    if user_completed_task(user_id, task_id):
        await bot.answer_callback_query(query_id, "⚠️ Déjà complétée !", show_alert=True); return
    if complete_task(user_id, task_id):
        update_balance(user_id, task["reward"])
        add_transaction(user_id, "tâche", task["reward"], f"Tâche: {task['description'][:50]}")
        new_user = get_user(user_id)
        await bot.answer_callback_query(query_id,
            f"✅ +{task['reward']}F ! Solde: {new_user['balance']}F", show_alert=True)
        await handle_tasks(user_id)

async def handle_historique(user_id):
    u, err = is_user_valid(user_id)
    if err:
        await bot.send_message(user_id, err); return
    transactions = get_user_transactions(user_id)
    withdrawals  = get_user_withdrawals(user_id)
    text = f"📋 *TON HISTORIQUE*\n━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    if transactions:
        text += "💰 *Transactions :*\n"
        for t in transactions[:8]:
            sign = "+" if t["amount"] > 0 else ""
            d = str(t.get("created_at", ""))[:10]
            text += f"  {sign}{t['amount']}F · {t['description']} · _{d}_\n"
    else:
        text += "💰 _Aucune transaction._\n"
    text += "\n💸 *Retraits :*\n"
    s_emoji = {"pending": "⏳", "approved": "✅", "rejected": "❌"}
    if withdrawals:
        for w in withdrawals[:5]:
            s = s_emoji.get(w.get("status"), "?")
            d = str(w.get("requested_at", ""))[:10]
            text += f"  {s} {w['amount']}F · {w['method']} · _{d}_\n"
    else:
        text += "  _Aucun retrait._\n"
    await bot.send_message(user_id, text, parse_mode="Markdown")

async def handle_classement(user_id):
    u, err = is_user_valid(user_id)
    if err:
        await bot.send_message(user_id, err); return
    top = get_top_referrers(10)
    medals = ["🥇","🥈","🥉","4️⃣","5️⃣","6️⃣","7️⃣","8️⃣","9️⃣","🔟"]
    text = f"🏆 *TOP PARRAINEURS XAFEARN*\n━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    for i, ud in enumerate(top):
        m = medals[i] if i < len(medals) else f"{i+1}."
        name = f"@{ud.get('username') or 'Anonyme'}"
        text += f"{m} {name} — *{ud['referral_count']} filleuls*\n"
    if not top:
        text += "_Sois le premier !_ 🚀"
    await bot.send_message(user_id, text, parse_mode="Markdown")

async def handle_aide(user_id):
    d = get_config("bonus_daily")
    r = get_config("bonus_referral")
    t = get_config("bonus_task")
    m = get_config("min_withdrawal")
    await bot.send_message(user_id,
        f"❓ *AIDE — XAFEARN*\n━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🎁 Bonus journalier : *{d}F* / jour\n"
        f"👥 Parrainage : *{r}F* par ami\n"
        f"✅ Tâches : *{t}F* par tâche\n"
        f"💸 Retrait minimum : *{m}F*\n\n"
        f"📩 Support : @xafearn_support",
        parse_mode="Markdown")