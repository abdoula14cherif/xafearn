import os, json, traceback
from flask import Flask, request, Response
import requests as req
from datetime import date

app = Flask(__name__)

TOKEN  = os.environ.get("BOT_TOKEN", "")
SB_URL = os.environ.get("SUPABASE_URL", "")
SB_KEY = os.environ.get("SUPABASE_KEY", "")
API    = f"https://api.telegram.org/bot{TOKEN}"
DB     = f"{SB_URL}/rest/v1"
ADMIN_IDS = [int(x.strip()) for x in os.environ.get("ADMIN_IDS","").split(",") if x.strip().isdigit()]
RETRAIT_CHANNEL_ID = os.environ.get("RETRAIT_CHANNEL_ID", "0")
BOT_USERNAME = "xafearn_bot"

CHANNELS_CHECK = ["@xafearn_money"]
CHANNELS_DISPLAY = [
    "https://t.me/xafearn_money",
    "https://t.me/+JlqLH_-LD4syZmY0"
]

# ── Pays et méthodes de paiement ─────────────────────
PAYS_METHODES = {
    "🇹🇬 Togo":         ["Flooz", "T-Money"],
    "🇨🇮 Cote d Ivoire": ["Orange Money", "Wave", "MTN Money", "Moov Money"],
    "🇸🇳 Senegal":       ["Orange Money", "Wave", "Free Money"],
    "🇧🇫 Burkina Faso":  ["Orange Money", "Moov Money"],
    "🇲🇱 Mali":          ["Orange Money", "Moov Money"],
    "🇧🇯 Benin":         ["MTN Money", "Moov Money"],
    "🇨🇲 Cameroun":      ["Orange Money", "MTN Money"],
    "🇬🇳 Guinee":        ["Orange Money", "MTN Money"],
    "🇳🇪 Niger":         ["Airtel Money", "Moov Money"],
    "🇨🇬 Congo":         ["Airtel Money", "MTN Money"],
    "🇬🇦 Gabon":         ["Airtel Money", "Moov Money"],
    "🇹🇩 Tchad":         ["Airtel Money", "Moov Money"],
    "Autre":             ["Virement Bancaire", "PayPal"]
}

H = {
    "apikey": SB_KEY,
    "Authorization": f"Bearer {SB_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation"
}

def tg(method, **kw):
    try:
        return req.post(f"{API}/{method}", json=kw, timeout=15).json()
    except:
        return {}

def send(uid, text, kb=None):
    d = {"chat_id": uid, "text": text}
    if kb:
        d["reply_markup"] = kb
    tg("sendMessage", **d)

def edit(uid, mid, text, kb=None):
    d = {"chat_id": uid, "message_id": mid, "text": text}
    if kb:
        d["reply_markup"] = kb
    tg("editMessageText", **d)

def main_kb():
    return {"keyboard": [
        ["🎁 Bonus", "👥 Parrainage"],
        ["💰 Solde", "📋 Historique"],
        ["💸 Retrait", "✅ Taches"],
        ["🏆 Classement", "❓ Aide"]
    ], "resize_keyboard": True}

def admin_kb():
    return {"keyboard": [
        ["👥 Tous les Users", "📊 Statistiques"],
        ["⚙️ Prix", "➕ Ajouter Tache"],
        ["💸 Retraits", "🚫 Bannir"],
        ["💵 Ajouter Solde", "📢 Broadcast"],
        ["🔙 Mode User", ""]
    ], "resize_keyboard": True}

def pays_keyboard():
    pays_list = list(PAYS_METHODES.keys())
    buttons = []
    for i in range(0, len(pays_list), 2):
        row = [{"text": pays_list[i], "callback_data": "pays_" + str(i)}]
        if i+1 < len(pays_list):
            row.append({"text": pays_list[i+1], "callback_data": "pays_" + str(i+1)})
        buttons.append(row)
    buttons.append([{"text": "❌ Annuler", "callback_data": "cancel_retrait"}])
    return {"inline_keyboard": buttons}

def methodes_keyboard(pays):
    methodes = PAYS_METHODES.get(pays, [])
    buttons = []
    for i, m in enumerate(methodes):
        buttons.append([{"text": m, "callback_data": "methode_" + str(i) + "_" + pays}])
    buttons.append([{"text": "❌ Annuler", "callback_data": "cancel_retrait"}])
    return {"inline_keyboard": buttons}

def db_get(table, f={}):
    try:
        r = req.get(f"{DB}/{table}", headers=H, params=f, timeout=15)
        data = r.json()
        return data if isinstance(data, list) else []
    except:
        return []

def db_post(table, data):
    try:
        r = req.post(f"{DB}/{table}", headers=H, json=data, timeout=15)
        result = r.json()
        return result if isinstance(result, list) else []
    except:
        return []

def db_patch(table, f, data):
    try:
        req.patch(f"{DB}/{table}", headers=H, params=f, json=data, timeout=15)
    except:
        pass

def db_del(table, f):
    try:
        req.delete(f"{DB}/{table}", headers=H, params=f, timeout=15)
    except:
        pass

def get_user(uid):
    r = db_get("users", {"user_id": f"eq.{uid}"})
    return r[0] if r else None

def update_balance(uid, amount):
    u = get_user(uid)
    if u:
        db_patch("users", {"user_id": f"eq.{uid}"}, {"balance": max(0, u["balance"] + amount)})

def get_cfg(key):
    r = db_get("config", {"key": f"eq.{key}"})
    if r:
        try:
            return int(r[0]["value"])
        except:
            return 0
    return {"bonus_daily":50,"bonus_referral":75,"bonus_task":35,"min_withdrawal":2500}.get(key, 0)

def set_cfg(key, val):
    db_patch("config", {"key": f"eq.{key}"}, {"value": str(val)})

def get_ref_count(uid):
    return len(db_get("users", {"referred_by": f"eq.{uid}", "is_registered": "eq.true"}))

def check_joined(uid):
    for ch in CHANNELS_CHECK:
        try:
            r = tg("getChatMember", chat_id=ch, user_id=uid)
            if r.get("result", {}).get("status") in ["left", "kicked"]:
                return False
        except:
            return False
    return True

def get_session(uid):
    try:
        r = db_get("sessions", {"user_id": f"eq.{uid}"})
        return json.loads(r[0]["data"]) if r else {}
    except:
        return {}

def set_session(uid, data):
    try:
        r = db_get("sessions", {"user_id": f"eq.{uid}"})
        if r:
            db_patch("sessions", {"user_id": f"eq.{uid}"}, {"data": json.dumps(data)})
        else:
            db_post("sessions", {"user_id": uid, "data": json.dumps(data)})
    except:
        pass

def clear_session(uid):
    try:
        db_del("sessions", {"user_id": f"eq.{uid}"})
    except:
        pass

@app.route("/api/webhook", methods=["GET"])
def health():
    return "XAFEARN BOT OK", 200

@app.route("/api/webhook", methods=["POST"])
def webhook():
    uid = None
    try:
        body = request.get_json(force=True)
        if not body:
            return Response('{"ok":true}', mimetype="application/json")
        if "message" in body:
            uid   = body["message"]["from"]["id"]
            uname = body["message"]["from"].get("username") or body["message"]["from"].get("first_name", "User")
            text  = body["message"].get("text", "")
            if text:
                handle_msg(uid, uname, text)
        elif "callback_query" in body:
            cq   = body["callback_query"]
            uid  = cq["from"]["id"]
            data = cq.get("data", "")
            mid  = cq["message"]["message_id"]
            cid  = cq["message"]["chat"]["id"]
            tg("answerCallbackQuery", callback_query_id=cq["id"])
            handle_cb(uid, data, mid, cid)
    except Exception as e:
        print(f"ERROR: {traceback.format_exc()}")
        if uid:
            try:
                send(uid, "Erreur technique. Reessaie.")
            except:
                pass
    return Response('{"ok":true}', mimetype="application/json")


def handle_msg(uid, uname, text):
    sess = get_session(uid)
    if sess.get("action") == "retrait":
        handle_retrait_step(uid, text, sess)
        return
    if sess.get("action") in ["add_task","ban","broadcast","add_solde"] and uid in ADMIN_IDS:
        handle_admin_step(uid, text, sess)
        return

    if text.startswith("/start"):
        parts = text.split(" ")
        referred_by = None
        if len(parts) > 1:
            try:
                ref = int(parts[1])
                if ref != uid:
                    referred_by = ref
            except:
                pass
        u = get_user(uid)
        if u and u.get("is_banned"):
            send(uid, "Compte suspendu.")
            return
        if not u:
            db_post("users", {
                "user_id": uid, "username": uname,
                "referred_by": referred_by, "balance": 0,
                "is_banned": False, "is_registered": False
            })
        msg  = "Bienvenue sur XAFEARN " + str(uname) + "!\n\n"
        msg += "Gagne de l argent chaque jour :\n"
        msg += "- Bonus journalier\n- Parrainage\n- Taches quotidiennes\n\n"
        msg += "Rejoins nos canaux :\n"
        msg += "1. " + CHANNELS_DISPLAY[0] + "\n"
        msg += "2. " + CHANNELS_DISPLAY[1] + "\n\n"
        msg += "Puis clique le bouton ci-dessous"
        req.post(f"{API}/sendMessage", json={
            "chat_id": uid, "text": msg,
            "reply_markup": {"inline_keyboard": [[
                {"text": "J ai tout rejoint - Verifier", "callback_data": "check_join"}
            ]]}
        }, timeout=15)
        return

    u = get_user(uid)
    if not u:
        send(uid, "Utilise /start pour t inscrire.")
        return
    if u.get("is_banned"):
        send(uid, "Compte suspendu.")
        return

    if uid in ADMIN_IDS:
        if text in ["/admin", "📊 Statistiques"]:
            users = db_get("users")
            ws    = db_get("withdrawals")
            send(uid,
                "PANEL ADMIN XAFEARN\n\n"
                "Total : " + str(len(users)) + "\n"
                "Actifs : " + str(sum(1 for x in users if x.get("is_registered"))) + "\n"
                "Bannis : " + str(sum(1 for x in users if x.get("is_banned"))) + "\n"
                "Soldes : " + str(sum(x.get("balance",0) for x in users)) + "F\n"
                "Payes : " + str(sum(x.get("amount",0) for x in ws if x.get("status")=="approved")) + "F\n"
                "En attente : " + str(sum(1 for x in ws if x.get("status")=="pending")),
                kb=admin_kb())
            return
        if text == "👥 Tous les Users":
            users = db_get("users")
            t = "UTILISATEURS (" + str(len(users)) + ")\n\n"
            for uu in users[:20]:
                s = "BANNI" if uu.get("is_banned") else ("OK" if uu.get("is_registered") else "EN ATTENTE")
                t += s + " @" + str(uu.get("username","N/A")) + " - " + str(uu.get("balance",0)) + "F\n"
            send(uid, t); return
        if text == "⚙️ Prix":
            send(uid,
                "CONFIG ACTUELLE\n\n"
                "Bonus : " + str(get_cfg("bonus_daily")) + "F\n"
                "Parrainage : " + str(get_cfg("bonus_referral")) + "F\n"
                "Tache : " + str(get_cfg("bonus_task")) + "F\n"
                "Min retrait : " + str(get_cfg("min_withdrawal")) + "F\n\n"
                "/setbonus 50\n/setref 75\n/settask 35\n/setmin 2500"); return
        if text.startswith("/setbonus "):
            set_cfg("bonus_daily", text.split()[1]); send(uid, "Bonus -> " + text.split()[1] + "F"); return
        if text.startswith("/setref "):
            set_cfg("bonus_referral", text.split()[1]); send(uid, "Parrainage -> " + text.split()[1] + "F"); return
        if text.startswith("/settask "):
            set_cfg("bonus_task", text.split()[1]); send(uid, "Tache -> " + text.split()[1] + "F"); return
        if text.startswith("/setmin "):
            set_cfg("min_withdrawal", text.split()[1]); send(uid, "Min retrait -> " + text.split()[1] + "F"); return
        if text == "➕ Ajouter Tache":
            set_session(uid, {"action": "add_task", "step": "description"})
            send(uid, "NOUVELLE TACHE\n\nDecris la tache :"); return
        if text == "💵 Ajouter Solde":
            set_session(uid, {"action": "add_solde", "step": "user_id"})
            send(uid, "ID Telegram du user :\n(ex: 123456789)"); return
        if text == "💸 Retraits":
            pending = db_get("withdrawals", {"status": "eq.pending"})
            if not pending:
                send(uid, "Aucune demande en attente.")
            else:
                t = "EN ATTENTE (" + str(len(pending)) + ")\n\n"
                for w in pending:
                    u2 = get_user(w["user_id"])
                    t += "#" + str(w["id"]) + " - " + str(w["amount"]) + "F\n"
                    t += "Methode : " + str(w.get("method","")) + "\n"
                    t += "Numero  : " + str(w.get("number","")) + "\n"
                    t += "Nom     : " + str(w.get("name","")) + "\n"
                    t += "User    : @" + str(u2.get("username","N/A") if u2 else "N/A") + "\n"
                    t += "---\n"
                send(uid, t); return
        if text == "🚫 Bannir":
            set_session(uid, {"action": "ban"})
            send(uid, "ID a bannir :\n123456789\nDebannir : debannir 123456789"); return
        if text == "📢 Broadcast":
            set_session(uid, {"action": "broadcast"})
            send(uid, "Ecris le message a envoyer a tous :"); return
        if text == "🔙 Mode User":
            send(uid, "Mode Utilisateur", kb=main_kb()); return

    if not u.get("is_registered"):
        send(uid, "Rejoins nos canaux d abord.\nEnvoie /start")
        return

    today = str(date.today())

    if text == "🎁 Bonus":
        bonus = get_cfg("bonus_daily")
        if str(u.get("last_bonus")) == today:
            send(uid, "Bonus deja recupere !\n\nSolde : " + str(u["balance"]) + "F\nReviens demain pour +" + str(bonus) + "F")
            return
        update_balance(uid, bonus)
        db_patch("users", {"user_id": f"eq.{uid}"}, {"last_bonus": today})
        db_post("transactions", {"user_id": uid, "type": "bonus", "amount": bonus, "description": "Bonus journalier"})
        new_u = get_user(uid)
        send(uid, "BONUS RECU !\n\n+" + str(bonus) + "F credite\nNouveau solde : " + str(new_u["balance"]) + "F\n\nReviens demain !")

    elif text == "💰 Solde":
        nb = get_ref_count(uid)
        ref_link = "https://t.me/" + BOT_USERNAME + "?start=" + str(uid)
        send(uid,
            "TON COMPTE XAFEARN\n\n"
            "Solde : " + str(u["balance"]) + "F\n"
            "Filleuls : " + str(nb) + "\n"
            "Gains parrainage : " + str(nb * get_cfg("bonus_referral")) + "F\n\n"
            "Ton lien :\n" + ref_link)

    elif text == "👥 Parrainage":
        nb = get_ref_count(uid)
        bonus_ref = get_cfg("bonus_referral")
        ref_link = "https://t.me/" + BOT_USERNAME + "?start=" + str(uid)
        send(uid,
            "TON LIEN D AFFILIATION\n\n"
            + ref_link + "\n\n"
            "Parrainages : " + str(nb) + "\n"
            "Gain/parrainage : " + str(bonus_ref) + "F\n"
            "Total gagne : " + str(nb * bonus_ref) + "F\n\n"
            "Partage et gagne " + str(bonus_ref) + "F a chaque inscription !")

    elif text == "📋 Historique":
        txs = db_get("transactions", {"user_id": f"eq.{uid}", "order": "created_at.desc", "limit": "10"})
        wds = db_get("withdrawals", {"user_id": f"eq.{uid}", "order": "requested_at.desc", "limit": "5"})
        t = "HISTORIQUE\n\nTransactions :\n"
        for tx in (txs or []):
            t += ("+" if tx["amount"] > 0 else "") + str(tx["amount"]) + "F - " + str(tx["description"]) + "\n"
        if not txs:
            t += "Aucune.\n"
        t += "\nRetraits :\n"
        se = {"pending": "EN ATTENTE", "approved": "PAYE", "rejected": "REFUSE"}
        for w in (wds or []):
            t += se.get(w.get("status"), "?") + " " + str(w["amount"]) + "F\n"
        if not wds:
            t += "Aucun.\n"
        send(uid, t)

    elif text == "💸 Retrait":
        min_w = get_cfg("min_withdrawal")
        if u["balance"] < min_w:
            send(uid, "Solde insuffisant\n\nSolde : " + str(u["balance"]) + "F\nMinimum : " + str(min_w) + "F")
            return
        pending = db_get("withdrawals", {"user_id": f"eq.{uid}", "status": "eq.pending"})
        if pending:
            send(uid, "Tu as deja une demande en attente de " + str(pending[0]["amount"]) + "F")
            return
        send(uid,
            "DEMANDE DE RETRAIT\n\n"
            "Solde : " + str(u["balance"]) + "F\n"
            "Minimum : " + str(min_w) + "F\n\n"
            "Choisis ton pays :",
            kb=pays_keyboard())

    elif text == "✅ Taches":
        tasks = db_get("tasks", {"date": f"eq.{today}", "is_active": "eq.true"})
        if not tasks:
            send(uid, "Aucune tache disponible aujourd hui.\nReviens plus tard !")
            return
        msg_text = "TACHES DU JOUR\n\n"
        buttons = []
        for t in tasks:
            done = len(db_get("user_tasks", {"user_id": f"eq.{uid}", "task_id": f"eq.{t['id']}"})) > 0
            msg_text += ("OK " if done else "-- ") + str(t["description"]) + "\n"
            if t.get("link"):
                msg_text += "Lien : " + str(t["link"]) + "\n"
            msg_text += "Recompense : " + str(t["reward"]) + "F\n\n"
            if not done:
                buttons.append([{"text": "Valider : " + str(t["description"])[:30], "callback_data": "task_" + str(t["id"])}])
        send(uid, msg_text, kb={"inline_keyboard": buttons} if buttons else None)

    elif text == "🏆 Classement":
        users = db_get("users", {"is_registered": "eq.true"})
        ranked = sorted(users, key=lambda x: get_ref_count(x["user_id"]), reverse=True)[:10]
        t = "TOP PARRAINEURS XAFEARN\n\n"
        for i, uu in enumerate(ranked):
            t += str(i+1) + ". @" + str(uu.get("username","Anonyme")) + " - " + str(get_ref_count(uu["user_id"])) + " filleuls\n"
        if not ranked:
            t += "Sois le premier !"
        send(uid, t)

    elif text == "❓ Aide":
        send(uid,
            "AIDE XAFEARN\n\n"
            "Bonus : " + str(get_cfg("bonus_daily")) + "F par jour\n"
            "Parrainage : " + str(get_cfg("bonus_referral")) + "F par ami\n"
            "Tache : " + str(get_cfg("bonus_task")) + "F par tache\n"
            "Retrait minimum : " + str(get_cfg("min_withdrawal")) + "F\n\n"
            "Support WhatsApp :\nhttps://wa.me/699663183")


def handle_retrait_step(uid, text, sess):
    step = sess.get("step")
    u    = get_user(uid)
    min_w = get_cfg("min_withdrawal")

    if step == "amount":
        try:
            amount = int(text.strip().replace("f","").replace("F","").replace(" ",""))
        except:
            send(uid, "Montant invalide. Envoie un chiffre ex: 2500")
            return
        if amount < min_w:
            send(uid, "Minimum : " + str(min_w) + "F")
            return
        if amount > u["balance"]:
            send(uid, "Solde insuffisant. Ton solde : " + str(u["balance"]) + "F")
            return
        sess["amount"] = amount
        sess["step"]   = "number"
        set_session(uid, sess)
        send(uid,
            "Montant : " + str(amount) + "F\n"
            "Pays : " + str(sess.get("pays","")) + "\n"
            "Methode : " + str(sess.get("methode","")) + "\n\n"
            "Envoie ton numero de paiement :")

    elif step == "number":
        if len(text.strip()) < 8:
            send(uid, "Numero invalide. Reessaie.")
            return
        sess["number"] = text.strip()
        sess["step"]   = "name"
        set_session(uid, sess)
        send(uid, "Numero enregistre.\n\nEnvoie ton nom complet :")

    elif step == "name":
        if len(text.strip()) < 3:
            send(uid, "Nom invalide. Reessaie.")
            return
        sess["name"] = text.strip()

        amount  = sess["amount"]
        pays    = sess.get("pays", "")
        methode = sess.get("methode", "")
        number  = sess["number"]
        name    = sess["name"]

        update_balance(uid, -amount)
        r = db_post("withdrawals", {
            "user_id": uid, "amount": amount,
            "method": pays + " - " + methode,
            "number": number, "name": name,
            "status": "pending"
        })
        w_id = r[0]["id"] if r else "?"
        db_post("transactions", {
            "user_id": uid, "type": "retrait",
            "amount": -amount,
            "description": "Retrait #" + str(w_id)
        })

        masked = number[:2] + "X" * (len(number)-4) + number[-2:] if len(number) >= 4 else number

        if RETRAIT_CHANNEL_ID and RETRAIT_CHANNEL_ID != "0":
            try:
                tg("sendMessage",
                    chat_id=int(RETRAIT_CHANNEL_ID),
                    text="DEMANDE DE RETRAIT #" + str(w_id) + "\n"
                         "================================\n\n"
                         "Montant  : " + str(amount) + "F\n"
                         "Pays     : " + pays + "\n"
                         "Methode  : " + methode + "\n"
                         "Numero   : " + number + "\n"
                         "Nom      : " + name + "\n\n"
                         "User     : @" + str(u.get("username","N/A")) + "\n"
                         "ID       : " + str(uid) + "\n"
                         "================================",
                    reply_markup={"inline_keyboard": [[
                        {"text": "✅ Approuver", "callback_data": "approve_" + str(w_id)},
                        {"text": "❌ Rejeter",   "callback_data": "reject_"  + str(w_id)}
                    ]]})
            except:
                pass

        new_u = get_user(uid)
        send(uid,
            "Demande envoyee !\n"
            "================================\n\n"
            "Montant  : " + str(amount) + "F\n"
            "Pays     : " + pays + "\n"
            "Methode  : " + methode + "\n"
            "Numero   : " + masked + "\n"
            "Nom      : " + name + "\n\n"
            "Solde restant : " + str(new_u["balance"]) + "F\n\n"
            "En cours de traitement...")
        clear_session(uid)


def handle_admin_step(uid, text, sess):
    action = sess.get("action")

    if action == "add_task":
        step = sess.get("step")
        if step == "description":
            sess["description"] = text
            sess["step"] = "link"
            set_session(uid, sess)
            send(uid, "Lien de la tache (ou - si aucun) :")
        elif step == "link":
            sess["link"] = None if text.strip() == "-" else text.strip()
            sess["step"] = "reward"
            set_session(uid, sess)
            send(uid, "Recompense en F (defaut : " + str(get_cfg("bonus_task")) + "F) :")
        elif step == "reward":
            try:
                reward = int(text.strip())
            except:
                reward = get_cfg("bonus_task")
            db_post("tasks", {
                "description": sess["description"],
                "link": sess.get("link"),
                "reward": reward,
                "date": str(date.today()),
                "is_active": True
            })
            send(uid, "Tache ajoutee !\n\n" + str(sess["description"]) + "\nRecompense : " + str(reward) + "F")
            clear_session(uid)

    elif action == "add_solde":
        step = sess.get("step")
        if step == "user_id":
            try:
                target_id = int(text.strip())
                u = get_user(target_id)
                if not u:
                    send(uid, "User introuvable. Verifie l ID.")
                    clear_session(uid)
                    return
                sess["target_id"] = target_id
                sess["step"] = "amount"
                set_session(uid, sess)
                send(uid,
                    "User trouve : @" + str(u.get("username","N/A")) + "\n"
                    "Solde actuel : " + str(u["balance"]) + "F\n\n"
                    "Combien veux-tu ajouter ? (en F)")
            except:
                send(uid, "ID invalide. Reessaie.")
                clear_session(uid)
        elif step == "amount":
            try:
                amount = int(text.strip().replace("f","").replace("F","").replace(" ",""))
                target_id = sess["target_id"]
                update_balance(target_id, amount)
                db_post("transactions", {
                    "user_id": target_id, "type": "credit_admin",
                    "amount": amount, "description": "Credit manuel par admin"
                })
                new_u = get_user(target_id)
                send(uid,
                    "Solde ajoute !\n\n"
                    "User : @" + str(new_u.get("username","N/A")) + "\n"
                    "+" + str(amount) + "F credite\n"
                    "Nouveau solde : " + str(new_u["balance"]) + "F")
                try:
                    send(target_id,
                        "+" + str(amount) + "F credite sur ton compte !\n\n"
                        "Nouveau solde : " + str(new_u["balance"]) + "F\n\n"
                        "L equipe XAFEARN")
                except:
                    pass
                clear_session(uid)
            except:
                send(uid, "Montant invalide. Envoie un chiffre ex: 1000")
                clear_session(uid)

    elif action == "ban":
        t = text.strip()
        if t.startswith("debannir "):
            try:
                tid = int(t.replace("debannir ", ""))
                db_patch("users", {"user_id": f"eq.{tid}"}, {"is_banned": False})
                send(uid, "User " + str(tid) + " debanni.")
                send(tid, "Ton compte a ete reactive.")
            except:
                send(uid, "ID invalide.")
        else:
            try:
                tid = int(t)
                db_patch("users", {"user_id": f"eq.{tid}"}, {"is_banned": True})
                send(uid, "User " + str(tid) + " banni.")
                send(tid, "Ton compte a ete suspendu.")
            except:
                send(uid, "ID invalide.")
        clear_session(uid)

    elif action == "broadcast":
        users = db_get("users", {"is_registered": "eq.true"})
        sent = 0
        for uu in users:
            if not uu.get("is_banned"):
                try:
                    tg("sendMessage", chat_id=uu["user_id"], text="Message XAFEARN\n\n" + text)
                    sent += 1
                except:
                    pass
        send(uid, "Broadcast termine ! " + str(sent) + " messages envoyes.")
        clear_session(uid)


def handle_cb(uid, data, mid, cid):

    # ── Sélection du pays ─────────────────────────────
    if data.startswith("pays_"):
        idx = int(data.split("_")[1])
        pays_list = list(PAYS_METHODES.keys())
        if idx >= len(pays_list):
            return
        pays = pays_list[idx]
        set_session(uid, {"action": "retrait", "step": "methode", "pays": pays})
        edit(uid, mid,
            "Pays : " + pays + "\n\n"
            "Choisis ta methode de paiement :",
            kb=methodes_keyboard(pays))
        return

    # ── Sélection de la méthode ───────────────────────
    if data.startswith("methode_"):
        parts   = data.split("_", 2)
        idx     = int(parts[1])
        pays    = parts[2]
        methodes = PAYS_METHODES.get(pays, [])
        if idx >= len(methodes):
            return
        methode = methodes[idx]
        u = get_user(uid)
        min_w = get_cfg("min_withdrawal")
        set_session(uid, {"action": "retrait", "step": "amount", "pays": pays, "methode": methode})
        edit(uid, mid,
            "Pays    : " + pays + "\n"
            "Methode : " + methode + "\n\n"
            "Solde disponible : " + str(u["balance"]) + "F\n"
            "Minimum : " + str(min_w) + "F\n\n"
            "Combien veux-tu retirer ? (en F)")
        return

    # ── Vérifier les canaux ───────────────────────────
    if data == "check_join":
        u = get_user(uid)
        if not u:
            return
        if not check_joined(uid):
            msg  = "Tu n as pas encore tout rejoint.\n\n"
            msg += "1. " + CHANNELS_DISPLAY[0] + "\n"
            msg += "2. " + CHANNELS_DISPLAY[1] + "\n\n"
            msg += "Rejoins puis clique Verifier"
            edit(uid, mid, msg,
                kb={"inline_keyboard": [[
                    {"text": "Verifier a nouveau", "callback_data": "check_join"}
                ]]})
            return
        db_patch("users", {"user_id": f"eq.{uid}"}, {"is_registered": True})
        if u.get("referred_by") and not u.get("is_registered"):
            parrain = get_user(u["referred_by"])
            if parrain and parrain.get("is_registered") and not parrain.get("is_banned"):
                bonus_ref = get_cfg("bonus_referral")
                update_balance(u["referred_by"], bonus_ref)
                db_post("transactions", {
                    "user_id": u["referred_by"], "type": "parrainage",
                    "amount": bonus_ref,
                    "description": "Filleul @" + str(u.get("username","?"))
                })
                try:
                    send(u["referred_by"],
                        "+" + str(bonus_ref) + "F credite !\n\n"
                        "Ton filleul @" + str(u.get("username","?")) + " vient de valider !")
                except:
                    pass
        ref_link = "https://t.me/" + BOT_USERNAME + "?start=" + str(uid)
        edit(uid, mid, "Compte active !\n\nTon lien de parrainage :\n" + ref_link)
        send(uid, "Menu Principal XAFEARN\n\nQue veux-tu faire ?", kb=main_kb())

    # ── Valider une tâche ─────────────────────────────
    elif data.startswith("task_"):
        task_id = int(data.split("_")[1])
        if db_get("user_tasks", {"user_id": f"eq.{uid}", "task_id": f"eq.{task_id}"}):
            tg("answerCallbackQuery", callback_query_id=str(mid), text="Deja completee !", show_alert=True)
            return
        tasks = db_get("tasks", {"id": f"eq.{task_id}"})
        if tasks:
            task = tasks[0]
            db_post("user_tasks", {"user_id": uid, "task_id": task_id})
            update_balance(uid, task["reward"])
            db_post("transactions", {
                "user_id": uid, "type": "tache",
                "amount": task["reward"],
                "description": str(task["description"])[:50]
            })
            u = get_user(uid)
            send(uid, "Tache validee !\n\n+" + str(task["reward"]) + "F credite\nNouveau solde : " + str(u["balance"]) + "F")

    # ── Annuler retrait ───────────────────────────────
    elif data == "cancel_retrait":
        clear_session(uid)
        edit(uid, mid, "Retrait annule.")

    # ── Approuver / Rejeter ───────────────────────────
    elif data.startswith("approve_") or data.startswith("reject_"):
        parts    = data.split("_")
        decision = parts[0]
        w_id     = int(parts[1])
        ws = db_get("withdrawals", {"id": f"eq.{w_id}"})
        if not ws or ws[0].get("status") != "pending":
            return
        w = ws[0]
        method_full = w.get("method","")
        masked = w["number"][:2] + "X" * (len(w["number"])-4) + w["number"][-2:] if len(w["number"]) >= 4 else w["number"]

        if decision == "approve":
            db_patch("withdrawals", {"id": f"eq.{w_id}"}, {"status": "approved"})
            edit(cid, mid,
                "PAIEMENT EFFECTUE\n"
                "================================\n\n"
                "Montant  : " + str(w["amount"]) + "F\n"
                "Methode  : " + method_full + "\n"
                "Numero   : " + w["number"] + "\n"
                "Nom      : " + str(w["name"]) + "\n\n"
                "Via @" + BOT_USERNAME + "\n"
                "Rejoins et gagne toi aussi !")
            try:
                send(w["user_id"],
                    "Retrait approuve !\n\n"
                    "Montant : " + str(w["amount"]) + "F\n"
                    "Methode : " + method_full + "\n"
                    "Numero  : " + masked + "\n\n"
                    "Merci de ta confiance !")
            except:
                pass
        else:
            db_patch("withdrawals", {"id": f"eq.{w_id}"}, {"status": "rejected"})
            update_balance(w["user_id"], w["amount"])
            db_post("transactions", {
                "user_id": w["user_id"], "type": "remboursement",
                "amount": w["amount"],
                "description": "Retrait #" + str(w_id) + " refuse"
            })
            edit(cid, mid, "RETRAIT REJETE #" + str(w_id))
            try:
                send(w["user_id"],
                    "Retrait refuse.\n\n"
                    "+" + str(w["amount"]) + "F rembourse sur ton solde.\n"
                    "Contacte le support : https://wa.me/699663183")
            except:
                pass

application = app
handler = app
