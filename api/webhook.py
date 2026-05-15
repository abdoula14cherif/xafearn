import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, request, Response
from lib.config import BOT_TOKEN
import requests as req

app = Flask(__name__)
API = f"https://api.telegram.org/bot{BOT_TOKEN}"

def send(chat_id, text, reply_markup=None, parse_mode="Markdown"):
    data = {"chat_id": chat_id, "text": text, "parse_mode": parse_mode}
    if reply_markup:
        import json
        data["reply_markup"] = json.dumps(reply_markup)
    req.post(f"{API}/sendMessage", json=data)

def main_menu():
    return {
        "keyboard": [
            ["🎁 Bonus Journalier", "👥 Parrainage"],
            ["💰 Mon Solde", "✅ Tâches du Jour"],
            ["📋 Historique", "💸 Retrait"],
            ["🏆 Classement", "❓ Aide"]
        ],
        "resize_keyboard": True
    }

@app.route("/api/webhook", methods=["GET"])
def health():
    return "XAFEARN BOT OK", 200

@app.route("/api/webhook", methods=["POST"])
def webhook():
    try:
        body = request.get_json(force=True)
        if not body:
            return Response('{"ok":true}', mimetype="application/json")

        if "message" in body:
            msg   = body["message"]
            uid   = msg["from"]["id"]
            uname = msg["from"].get("username") or msg["from"].get("first_name", "User")
            text  = msg.get("text", "")

            if not text:
                return Response('{"ok":true}', mimetype="application/json")

            handle_message(uid, uname, text)

        elif "callback_query" in body:
            cq      = body["callback_query"]
            uid     = cq["from"]["id"]
            data    = cq.get("data", "")
            msg_id  = cq["message"]["message_id"]
            chat_id = cq["message"]["chat"]["id"]
            req.post(f"{API}/answerCallbackQuery", json={"callback_query_id": cq["id"]})
            handle_callback(uid, data, msg_id, chat_id)

    except Exception as e:
        print(f"Error: {e}")

    return Response('{"ok":true}', mimetype="application/json")


def handle_message(uid, uname, text):
    from lib.database import (
        get_user, add_user, activate_user, update_balance,
        set_last_bonus, get_config, get_referral_count,
        get_tasks_today, user_completed_task, complete_task,
        add_transaction, get_user_transactions, get_user_withdrawals,
        get_top_referrers, get_stats, get_all_users, ban_user,
        set_config, add_task, get_pending_withdrawals
    )
    from lib.config import ADMIN_IDS, BOT_USERNAME, CHANNELS

    # ── /start ──────────────────────────────────────
    if text.startswith("/start"):
        parts = text.split(" ")
        arg = parts[1] if len(parts) > 1 else None
        referred_by = None
        if arg:
            try:
                ref = int(arg)
                if ref != uid:
                    referred_by = ref
            except:
                pass

        existing = get_user(uid)
        if existing and existing.get("is_banned"):
            send(uid, "🚫 *Compte suspendu.*")
            return
        if not existing:
            add_user(uid, uname, referred_by)

        channels_list = "\n".join([f"  ➤ {ch}" for ch in CHANNELS])
        kb = {"inline_keyboard": [[{"text": "✅ J'ai tout rejoint — Vérifier", "callback_data": "check_join"}]]}
        send(uid,
            f"👑 *Bienvenue sur XAFEARN, {uname} !*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"💰 Gagne de l'argent chaque jour :\n"
            f"  🎁 Bonus journalier\n"
            f"  👥 Parrainage\n"
            f"  ✅ Tâches quotidiennes\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📌 Rejoins nos canaux :\n\n{channels_list}\n\n"
            f"📌 Puis clique ✅",
            reply_markup=kb
        )
        return

    # ── Vérif user ──────────────────────────────────
    u = get_user(uid)
    if not u:
        send(uid, "❌ Utilise /start pour t'inscrire.")
        return
    if u.get("is_banned"):
        send(uid, "🚫 Compte suspendu.")
        return

    # ── ADMIN ───────────────────────────────────────
    if uid in ADMIN_IDS:
        if text == "/admin" or text == "📊 Statistiques":
            stats = get_stats()
            send(uid,
                f"⚙️ *PANEL ADMIN*\n━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"👥 Total : *{stats['total_users']}*\n"
                f"✅ Actifs : *{stats['registered_users']}*\n"
                f"💵 Soldes : *{stats['total_balance']}F*\n"
                f"✅ Payé : *{stats['total_paid']}F*\n"
                f"⏳ Retraits : *{stats['pending_withdrawals']}*",
                reply_markup={
                    "keyboard": [
                        ["👥 Tous les Users", "📊 Statistiques"],
                        ["⚙️ Modifier les Prix", "➕ Ajouter une Tâche"],
                        ["💸 Demandes Retrait", "🚫 Bannir / Débannir"],
                        ["📢 Broadcast", "🔙 Mode Utilisateur"]
                    ],
                    "resize_keyboard": True
                }
            )
            return

        if text == "👥 Tous les Users":
            users = get_all_users()
            t = f"👥 *UTILISATEURS ({len(users)})*\n━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            for uu in users[:20]:
                s = "🚫" if uu.get("is_banned") else ("✅" if uu.get("is_registered") else "⏳")
                t += f"{s} @{uu.get('username','N/A')} — *{uu.get('balance',0)}F*\n"
            send(uid, t)
            return

        if text == "⚙️ Modifier les Prix":
            send(uid,
                f"⚙️ *CONFIG*\n\n"
                f"🎁 Bonus journalier : *{get_config('bonus_daily')}F*\n"
                f"👥 Bonus parrainage : *{get_config('bonus_referral')}F*\n"
                f"✅ Bonus tâche : *{get_config('bonus_task')}F*\n"
                f"💸 Retrait min : *{get_config('min_withdrawal')}F*\n\n"
                f"`/setbonus 150`\n`/setref 100`\n`/settask 50`\n`/setmin 1000`"
            )
            return

        if text.startswith("/setbonus "):
            set_config("bonus_daily", text.split()[1])
            send(uid, f"✅ Bonus journalier → *{text.split()[1]}F*")
            return
        if text.startswith("/setref "):
            set_config("bonus_referral", text.split()[1])
            send(uid, f"✅ Bonus parrainage → *{text.split()[1]}F*")
            return
        if text.startswith("/settask "):
            set_config("bonus_task", text.split()[1])
            send(uid, f"✅ Bonus tâche → *{text.split()[1]}F*")
            return
        if text.startswith("/setmin "):
            set_config("min_withdrawal", text.split()[1])
            send(uid, f"✅ Retrait min → *{text.split()[1]}F*")
            return

        if text == "💸 Demandes Retrait":
            pending = get_pending_withdrawals()
            if not pending:
                send(uid, "💸 *Aucune demande en attente.* ✅")
            else:
                t = f"💸 *EN ATTENTE ({len(pending)})*\n━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                for w in pending:
                    t += f"🆔 *#{w['id']}* · *{w['amount']}F* · {w['name']}\n"
                send(uid, t)
            return

        if text == "🔙 Mode Utilisateur":
            send(uid, "👤 *Mode Utilisateur*", reply_markup=main_menu())
            return

    # ── Vérif inscription ───────────────────────────
    if not u.get("is_registered"):
        send(uid, "⚠️ Rejoins d'abord nos canaux. Envoie /start")
        return

    # ── BOUTONS UTILISATEUR ─────────────────────────
    from datetime import date
    from lib.config import BOT_USERNAME

    if text == "🎁 Bonus Journalier":
        bonus = get_config("bonus_daily")
        today = str(date.today())
        if str(u.get("last_bonus")) == today:
            send(uid, f"⏳ *Bonus déjà récupéré !*\n\n💼 Solde : *{u['balance']}F*\n🔔 Reviens demain pour +{bonus}F")
            return
        update_balance(uid, bonus)
        set_last_bonus(uid, today)
        add_transaction(uid, "bonus", bonus, "Bonus journalier")
        new_u = get_user(uid)
        send(uid, f"🎁 *BONUS REÇU !*\n━━━━━━━━━━━━━━━━━━━━━━━\n\n💵 +*{bonus}F* ✅\n💼 Solde : *{new_u['balance']}F*")

    elif text == "💰 Mon Solde":
        nb = get_referral_count(uid)
        ref_link = f"https://t.me/{BOT_USERNAME}?start={uid}"
        send(uid,
            f"💼 *TON COMPTE*\n━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"💵 Solde : *{u['balance']}F*\n"
            f"👥 Filleuls : *{nb}*\n\n"
            f"🔗 Lien :\n`{ref_link}`"
        )

    elif text == "👥 Parrainage":
        nb = get_referral_count(uid)
        bonus_ref = get_config("bonus_referral")
        ref_link = f"https://t.me/{BOT_USERNAME}?start={uid}"
        send(uid,
            f"👥 *TON LIEN D'AFFILIATION*\n━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🔗 {ref_link}\n\n"
            f"📊 Parrainages : *{nb}*\n"
            f"💰 Gain/parrainage : *{bonus_ref}F*\n"
            f"💵 Total gagné : *{nb * bonus_ref}F*"
        )

    elif text == "✅ Tâches du Jour":
        tasks = get_tasks_today()
        if not tasks:
            send(uid, "📋 *Aucune tâche aujourd'hui.*\n\n⏳ Reviens plus tard !")
            return
        completed_ids = [t["id"] for t in tasks if user_completed_task(uid, t["id"])]
        msg_text = "✅ *TÂCHES DU JOUR*\n━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        buttons = []
        for t in tasks:
            done = t["id"] in completed_ids
            msg_text += f"{'✅' if done else '⭕'} *{t['description']}*\n"
            if t.get("link"):
                msg_text += f"   🔗 _{t['link']}_\n"
            msg_text += f"   💰 *{t['reward']}F*\n\n"
            if not done:
                buttons.append([{"text": f"✅ {t['description'][:30]}", "callback_data": f"task_{t['id']}"}])
        kb = {"inline_keyboard": buttons} if buttons else None
        send(uid, msg_text, reply_markup=kb)

    elif text == "📋 Historique":
        txs = get_user_transactions(uid)
        wds = get_user_withdrawals(uid)
        t = "📋 *HISTORIQUE*\n━━━━━━━━━━━━━━━━━━━━━━━\n\n💰 *Transactions :*\n"
        if txs:
            for tx in txs[:8]:
                sign = "+" if tx["amount"] > 0 else ""
                t += f"  {sign}{tx['amount']}F · {tx['description']}\n"
        else:
            t += "  _Aucune._\n"
        t += "\n💸 *Retraits :*\n"
        s_emoji = {"pending": "⏳", "approved": "✅", "rejected": "❌"}
        if wds:
            for w in wds[:5]:
                t += f"  {s_emoji.get(w.get('status'),'?')} {w['amount']}F\n"
        else:
            t += "  _Aucun._\n"
        send(uid, t)

    elif text == "💸 Retrait":
        min_w = get_config("min_withdrawal")
        if u["balance"] < min_w:
            send(uid, f"❌ *Solde insuffisant*\n\n💼 Solde : *{u['balance']}F*\n📌 Minimum : *{min_w}F*")
            return
        kb = {"inline_keyboard": [
            [{"text": "📱 Mobile Money", "callback_data": "method_mobile"}],
            [{"text": "🏦 Virement Bancaire", "callback_data": "method_bank"}],
            [{"text": "❌ Annuler", "callback_data": "cancel_retrait"}]
        ]}
        send(uid, f"💸 *RETRAIT*\n\n💼 Solde : *{u['balance']}F*\n📌 Min : *{min_w}F*\n\nChoisis ta méthode 👇", reply_markup=kb)

    elif text == "🏆 Classement":
        top = get_top_referrers(10)
        medals = ["🥇","🥈","🥉","4️⃣","5️⃣","6️⃣","7️⃣","8️⃣","9️⃣","🔟"]
        t = "🏆 *TOP PARRAINEURS*\n━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        for i, ud in enumerate(top):
            t += f"{medals[i]} @{ud.get('username','Anonyme')} — *{ud['referral_count']} filleuls*\n"
        if not top:
            t += "_Sois le premier !_ 🚀"
        send(uid, t)

    elif text == "❓ Aide":
        send(uid,
            f"❓ *AIDE XAFEARN*\n━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🎁 Bonus : *{get_config('bonus_daily')}F*/jour\n"
            f"👥 Parrainage : *{get_config('bonus_referral')}F*/ami\n"
            f"✅ Tâche : *{get_config('bonus_task')}F*/tâche\n"
            f"💸 Retrait min : *{get_config('min_withdrawal')}F*\n\n"
            f"📩 Support : @xafearn_support"
        )


def handle_callback(uid, data, msg_id, chat_id):
    from lib.database import (
        get_user, activate_user, update_balance, get_config,
        get_referral_count, add_transaction, create_withdrawal,
        update_withdrawal_status, get_withdrawal_by_id,
        complete_task, user_completed_task, get_tasks_today
    )
    from lib.config import RETRAIT_CHANNEL_ID, BOT_USERNAME, CHANNELS

    # ── Vérifier les canaux ─────────────────────────
    if data == "check_join":
        user = get_user(uid)
        if not user:
            return

        # Vérifier membership
        all_joined = True
        for ch in CHANNELS:
            r = req.get(f"{API}/getChatMember", params={"chat_id": ch, "user_id": uid})
            result = r.json().get("result", {})
            if result.get("status") in ["left", "kicked"]:
                all_joined = False
                break

        if not all_joined:
            channels_list = "\n".join([f"  ➤ {ch}" for ch in CHANNELS])
            kb = {"inline_keyboard": [[{"text": "🔄 Vérifier à nouveau", "callback_data": "check_join"}]]}
            req.post(f"{API}/editMessageText", json={
                "chat_id": uid, "message_id": msg_id,
                "text": f"❌ *Tu n'as pas tout rejoint.*\n\n{channels_list}",
                "parse_mode": "Markdown", "reply_markup": kb
            })
            return

        activate_user(uid)

        # Créditer parrain
        if user.get("referred_by") and not user.get("is_registered"):
            parrain_id = user["referred_by"]
            parrain = get_user(parrain_id)
            if parrain and parrain.get("is_registered") and not parrain.get("is_banned"):
                bonus_ref = get_config("bonus_referral")
                update_balance(parrain_id, bonus_ref)
                add_transaction(parrain_id, "parrainage", bonus_ref, f"Filleul @{user.get('username','?')}")
                send(parrain_id, f"🎉 *+{bonus_ref}F* — Filleul *@{user.get('username','?')}* inscrit !")

        ref_link = f"https://t.me/{BOT_USERNAME}?start={uid}"
        req.post(f"{API}/editMessageText", json={
            "chat_id": uid, "message_id": msg_id,
            "text": f"✅ *Compte activé !*\n━━━━━━━━━━━━━━━━━━━━━━━\n\n🔗 Ton lien :\n`{ref_link}`",
            "parse_mode": "Markdown"
        })
        send(uid, "🏠 *Menu Principal*", reply_markup={
            "keyboard": [
                ["🎁 Bonus Journalier", "👥 Parrainage"],
                ["💰 Mon Solde", "✅ Tâches du Jour"],
                ["📋 Historique", "💸 Retrait"],
                ["🏆 Classement", "❓ Aide"]
            ],
            "resize_keyboard": True
        })

    # ── Valider une tâche ───────────────────────────
    elif data.startswith("task_"):
        task_id = int(data.split("_")[1])
        if user_completed_task(uid, task_id):
            req.post(f"{API}/answerCallbackQuery", json={
                "callback_query_id": str(msg_id),
                "text": "⚠️ Déjà complétée !",
                "show_alert": True
            })
            return
        tasks = get_tasks_today()
        task = next((t for t in tasks if t["id"] == task_id), None)
        if task and complete_task(uid, task_id):
            update_balance(uid, task["reward"])
            add_transaction(uid, "tâche", task["reward"], task["description"][:50])
            u = get_user(uid)
            send(uid, f"🎯 *Tâche validée !*\n\n💵 +{task['reward']}F ✅\n💼 Solde : *{u['balance']}F*")

    # ── Méthode retrait ─────────────────────────────
    elif data.startswith("method_"):
        method = data.split("_")[1]
        label = "📱 Mobile Money" if method == "mobile" else "🏦 Virement"
        from lib.config import SUPABASE_URL
        # Stocker la session dans Supabase
        from lib.database import get_client_headers, BASE
        req.post(f"{BASE}/retrait_sessions", headers=get_client_headers(), json={
            "user_id": uid, "method": method, "step": "amount"
        })
        req.post(f"{API}/editMessageText", json={
            "chat_id": uid, "message_id": msg_id,
            "text": f"💸 *{label}*\n\nCombien veux-tu retirer ? (en F) 👇",
            "parse_mode": "Markdown"
        })

    elif data == "cancel_retrait":
        req.post(f"{API}/editMessageText", json={
            "chat_id": uid, "message_id": msg_id,
            "text": "❌ *Retrait annulé.*",
            "parse_mode": "Markdown"
        })

    # ── Décision retrait (admin) ────────────────────
    elif data.startswith("approve_") or data.startswith("reject_"):
        parts = data.split("_")
        decision = parts[0]
        w_id = int(parts[1])
        w = get_withdrawal_by_id(w_id)
        if not w or w.get("status") != "pending":
            return
        masked = w["number"][:4] + " *** ** ** " + w["number"][-2:]
        label = "📱 Mobile Money" if w["method"] == "mobile" else "🏦 Virement"

        if decision == "approve":
            update_withdrawal_status(w_id, "approved")
            req.post(f"{API}/editMessageText", json={
                "chat_id": chat_id, "message_id": msg_id,
                "text": f"✅ *PAIEMENT EFFECTUÉ*\n━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                        f"💰 *{w['amount']}F*\n⚙️ {label}\n📱 {masked}\n👤 {w['name']}\n\n"
                        f"🤖 Via @xafearn_bot\n➡️ _Rejoins et gagne toi aussi !_",
                "parse_mode": "Markdown"
            })
            send(w["user_id"], f"✅ *Retrait approuvé !*\n\n💵 *{w['amount']}F* envoyé ! 🙏")
        else:
            update_withdrawal_status(w_id, "rejected")
            update_balance(w["user_id"], w["amount"])
            add_transaction(w["user_id"], "remboursement", w["amount"], f"Retrait #{w_id} refusé")
            req.post(f"{API}/editMessageText", json={
                "chat_id": chat_id, "message_id": msg_id,
                "text": f"❌ *RETRAIT REJETÉ #{w_id}*",
                "parse_mode": "Markdown"
            })
            send(w["user_id"], f"❌ *Retrait refusé*\n\n💵 *{w['amount']}F* remboursé.")

application = app
handler = app