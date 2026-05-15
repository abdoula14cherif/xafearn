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
                f"👥 Bonus parrainage : *{get_