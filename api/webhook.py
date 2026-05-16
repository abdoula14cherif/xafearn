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
CHANNELS = [
    os.environ.get("CHANNEL_1", "@xafearn_money"),
    os.environ.get("CHANNEL_2", "@xafearn_money"),
    os.environ.get("CHANNEL_3", "@xafearn_money"),
]
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
    d = {"chat_id": uid, "text": text, "parse_mode": "Markdown"}
    if kb:
        d["reply_markup"] = kb
    tg("sendMessage", **d)

def edit(uid, mid, text, kb=None):
    d = {"chat_id": uid, "message_id": mid, "text": text, "parse_mode": "Markdown"}
    if kb:
        d["reply_markup"] = kb
    tg("editMessageText", **d)

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
    for ch in CHANNELS:
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
        ["📢 Broadcast", "🔙 Mode User"]
    ], "resize_keyboard": True}

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
                send(uid, f"❌ Erreur:\n`{str(e)[:200]}`")
            except:
                pass

    return Response('{"ok":true}', mimetype="application/json")


def handle_msg(uid, uname, text):
    sess = get_session(uid)
    if sess.get("action") == "retrait":
        handle_retrait_step(uid, text, sess)
        return
    if sess.get("action") in ["add_task","ban","broadcast"] and uid in ADMIN_IDS:
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
            send(uid, "🚫 *Compte suspendu.*")
            return
        if not u:
            db_post("users", {
                "user_id": uid, "username": uname,
                "referred_by": referred_by, "balance": 0,
                "is_banned": False, "is_registered": False
            })
        channels_list = "\n".join([f"  ➤ {ch}" for ch in CHANNELS])
        send(uid,
            f"👑 *Bienvenue sur XAFEARN, {uname} !*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"💰 Gagne de l'argent chaque jour\n\n"
            f"📌 Rejoins nos canaux :\n{channels_list}\n\n"
            f"📌 Puis clique ✅",
            kb={"inline_keyboard": [[
                {"text": "✅ J'ai tout rejoint — Verifier", "callback_data": "check_join"}
            ]]}
        )
        return

    u = get_user(uid)
    if not u:
        send(uid, "❌ Utilise /start pour t'inscrire.")
        return
    if u.get("is_banned"):
        send(uid, "🚫 Compte suspendu.")
        return

    if uid in ADMIN_IDS:
        if text in ["/admin", "📊 Statistiques"]:
            users = db_get("users")
            ws = db_get("withdrawals")
            send(uid,
                f"⚙️ *PANEL ADMIN*\n━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"👥 Total : *{len(users)}*\n"
                f"✅ Actifs : *{sum(1 for x in users if x.get('is_registered'))}*\n"
                f"💵 Soldes : *{sum(x.get('balance',0) for x in users)}F*\n"
                f"⏳ En attente : *{sum(1 for x in ws if x.get('status')=='pending')}*",
                kb=admin_kb())
            return
        if text == "👥 Tous les Users":
            users = db_get("users")
            t = f"👥 *UTILISATEURS ({len(users)})*\n\n"
            for uu in users[:20]:
                s = "🚫" if uu.get("is_banned") else ("✅" if uu.get("is_registered") else "⏳")
                t += f"{s} @{uu.get('username','N/A')} — *{uu.get('balance',0)}F*\n"
            send(uid, t)
            return
        if text == "⚙️ Prix":
            send(uid, f"⚙️ *CONFIG*\n\n🎁 Bonus : *{get_cfg('bonus_daily')}F*\n👥 Parrainage : *{get_cfg('bonus_referral')}F*\n✅ Tache : *{get_cfg('bonus_task')}F*\n💸 Min retrait : *{get_cfg('min_withdrawal')}F*\n\n`/setbonus 50`\n`/setref 75`\n`/settask 35`\n`/setmin 2500`")
            return
        if text.startswith("/setbonus "):
            set_cfg("bonus_daily", text.split()[1]); send(uid, f"✅ Bonus → *{text.split()[1]}F*"); return
        if text.startswith("/setref "):
            set_cfg("bonus_referral", text.split()[1]); send(uid, f"✅ Parrainage → *{text.split()[1]}F*"); return
        if text.startswith("/settask "):
            set_cfg("bonus_task", text.split()[1]); send(uid, f"✅ Tache → *{text.split()[1]}F*"); return
        if text.startswith("/setmin "):
            set_cfg("min_withdrawal", text.split()[1]); send(uid, f"✅ Min retrait → *{text.split()[1]}F*"); return
        if text == "➕ Ajouter Tache":
            set_session(uid, {"action": "add_task", "step": "description"})
            send(uid, "➕ *NOUVELLE TACHE*\n\nDecris la tache :"); return
        if text == "💸 Retraits":
            pending = db_get("withdrawals", {"status": "eq.pending"})
            if not pending:
                send(uid, "💸 *Aucune demande.* ✅")
            else:
                t = f"💸 *EN ATTENTE ({len(pending)})*\n\n"
                for w in pending:
                    t += f"*#{w['id']}* · *{w['amount']}F* · {w.get('name','')}\n"
                send(uid, t)
            return
        if text == "🚫 Bannir":
            set_session(uid, {"action": "ban"})
            send(uid, "🚫 ID a bannir :\n`123456789`\nDebannir : `debannir 123456789`"); return
        if text == "📢 Broadcast":
            set_session(uid, {"action": "broadcast"})
            send(uid, "📢 Ecris le message :"); return
        if text == "🔙 Mode User":
            send(uid, "👤 Mode Utilisateur", kb=main_kb()); return

    if not u.get("is_registered"):
        send(uid, "⚠️ Rejoins nos canaux d'abord.\nEnvoie /start")
        return

    today = str(date.today())

    if text == "🎁 Bonus":
        bonus = get_cfg("bonus_daily")
        if str(u.get("last_bonus")) == today:
            send(uid, f"⏳ *Bonus deja recupere !*\n\n💼 Solde : *{u['balance']}F*\n🔔 Reviens demain pour +{bonus}F")
            return
        update_balance(uid, bonus)
        db_patch("users", {"user_id": f"eq.{uid}"}, {"last_bonus": today})
        db_post("transactions", {"user_id": uid, "type": "bonus", "amount": bonus, "description": "Bonus journalier"})
        new_u = get_user(uid)
        send(uid, f"🎁 *BONUS RECU !*\n\n💵 +*{bonus}F* ✅\n💼 Solde : *{new_u['balance']}F*\n\n📅 Reviens demain !")

    elif text == "💰 Solde":
        nb = get_ref_count(uid)
        ref_link = f"https://t.me/{BOT_USERNAME}?start={uid}"
        send(uid, f"💼 *TON COMPTE*\n\n💵 Solde : *{u['balance']}F*\n👥 Filleuls : *{nb}*\n💰 Gains : *{nb*get_cfg('bonus_referral')}F*\n\n🔗 Lien :\n`{ref_link}`")

    elif text == "👥 Parrainage":
        nb = get_ref_count(uid)
        bonus_ref = get_cfg("bonus_referral")
        ref_link = f"https://t.me/{BOT_USERNAME}?start={uid}"
        send(uid, f"👥 *TON LIEN D'AFFILIATION*\n\n🔗 {ref_link}\n\n📊 Parrainages : *{nb}*\n💰 Gain/parrainage : *{bonus_ref}F*\n💵 Total : *{nb*bonus_ref}F*")

    elif text == "📋 Historique":
        txs = db_get("transactions", {"user_id": f"eq.{uid}", "order": "created_at.desc", "limit": "10"})
        wds = db_get("withdrawals", {"user_id": f"eq.{uid}", "order": "requested_at.desc", "limit": "5"})
        t = "📋 *HISTORIQUE*\n\n💰 *Transactions :*\n"
        for tx in (txs or []):
            t += f"  {'+'if tx['amount']>0 else ''}{tx['amount']}F · {tx['description']}\n"
        if not txs:
            t += "  Aucune.\n"
        t += "\n💸 *Retraits :*\n"
        se = {"pending": "⏳", "approved": "✅", "rejected": "❌"}
        for w in (wds or []):
            t += f"  {se.get(w.get('status'),'?')} {w['amount']}F\n"
        if not wds:
            t += "  Aucun.\n"
        send(uid, t)

    elif text == "💸 Retrait":
        min_w = get_cfg("min_withdrawal")
        if u["balance"] < min_w:
            send(uid, f"❌ *Solde insuffisant*\n\n💼 Solde : *{u['balance']}F*\n📌 Minimum : *{min_w}F*")
            return
        pending = db_get("withdrawals", {"user_id": f"eq.{uid}", "status": "eq.pending"})
        if pending:
            send(uid, f"⏳ *Demande deja en attente*\n\n💵 Montant : *{pending[0]['amount']}F*")
            return
        send(uid,
            f"💸 *RETRAIT*\n\n💼 Solde : *{u['balance']}F*\nMinimum : *{min_w}F*\n\nChoisis ta methode 👇",
            kb={"inline_keyboard": [
                [{"text": "📱 Mobile Money", "callback_data": "method_mobile"}],
                [{"text": "🏦 Virement Bancaire", "callback_data": "method_bank"}],
                [{"text": "❌ Annuler", "callback_data": "cancel_retrait"}]
            ]})

    elif text == "✅ Taches":
        tasks = db_get("tasks", {"date": f"eq.{today}", "is_active": "eq.true"})
        if not tasks:
            send(uid, "📋 *Aucune tache aujourd'hui.*\n\n⏳ Reviens plus tard !")
            return
        msg_text = "✅ *TACHES DU JOUR*\n\n"
        buttons = []
        for t in tasks:
            done = len(db_get("user_tasks", {"user_id": f"eq.{uid}", "task_id": f"eq.{t['id']}"})) > 0
            msg_text += f"{'✅'if done else '⭕'} *{t['description']}*\n"
            if t.get("link"):
                msg_text += f"   🔗 {t['link']}\n"
            msg_text += f"   💰 *{t['reward']}F*\n\n"
            if not done:
                buttons.append([{"text": f"✅ {t['description'][:30]}", "callback_data": f"task_{t['id']}"}])
        send(uid, msg_text, kb={"inline_keyboard": buttons} if buttons else None)

    elif text == "🏆 Classement":
        users = db_get("users", {"is_registered": "eq.true"})
        ranked = sorted(users, key=lambda x: get_ref_count(x["user_id"]), reverse=True)[:10]
        medals = ["🥇","🥈","🥉","4️⃣","5️⃣","6️⃣","7️⃣","8️⃣","9️⃣","🔟"]
        t = "🏆 *TOP PARRAINEURS*\n\n"
        for i, uu in enumerate(ranked):
            t += f"{medals[i]} @{uu.get('username','Anonyme')} — *{get_ref_count(uu['user_id'])} filleuls*\n"
        if not ranked:
            t += "Sois le premier ! 🚀"
        send(uid, t)

    elif text == "❓ Aide":
        send(uid,
            f"❓ *AIDE XAFEARN*\n\n"
            f"🎁 Bonus : *{get_cfg('bonus_daily')}F*/jour\n"
            f"👥 Parrainage : *{get_cfg('bonus_referral')}F*/ami\n"
            f"✅ Tache : *{get_cfg('bonus_task')}F*/tache\n"
            f"💸 Retrait min : *{get_cfg('min_withdrawal')}F*\n\n"
            f"📩 Support WhatsApp :\nhttps://wa.me/22890000000")


def handle_retrait_step(uid, text, sess):
    step = sess.get("step")
    u = get_user(uid)
    min_w = get_cfg("min_withdrawal")

    if step == "amount":
        try:
            amount = int(text.strip())
        except:
            send(uid, "❌ Montant invalide (ex: 2500)")
            return
        if amount < min_w:
            send(uid, f"❌ Minimum : *{min_w}F*")
            return
        if amount > u["balance"]:
            send(uid, f"❌ Solde insuffisant ! (*{u['balance']}F*)")
            return
        sess["amount"] = amount
        sess["step"] = "number"
        set_session(uid, sess)
        send(uid, f"✅ Montant : *{amount}F*\n\n📱 Ton numero de paiement :")

    elif step == "number":
        if len(text.strip()) < 8:
            send(uid, "❌ Numero invalide.")
            return
        sess["number"] = text.strip()
        sess["step"] = "name"
        set_session(uid, sess)
        send(uid, "✅ Numero enregistre.\n\n👤 Ton nom complet :")

    elif step == "name":
        if len(text.strip()) < 3:
            send(uid, "❌ Nom invalide.")
            return
        sess["name"] = text.strip()
        amount = sess["amount"]
        method = sess["method"]
        number = sess["number"]
        name   = sess["name"]
        update_balance(uid, -amount)
        r = db_post("withdrawals", {"user_id": uid, "amount": amount, "method": method, "number": number, "name": name, "status": "pending"})
        w_id = r[0]["id"] if r else "?"
        db_post("transactions", {"user_id": uid, "type": "retrait", "amount": -amount, "description": f"Retrait #{w_id}"})
        masked = number[:4] + " *** ** ** " + number[-2:] if len(number) >= 6 else number
        label  = "📱 Mobile Money" if method == "mobile" else "🏦 Virement"
        if RETRAIT_CHANNEL_ID and RETRAIT_CHANNEL_ID != "0":
            try:
                tg("sendMessage",
                    chat_id=int(RETRAIT_CHANNEL_ID),
                    text=f"💸 *DEMANDE #{w_id}*\n\n💵 *{amount}F* · {label}\n📱 {masked}\n👤 {name}\n🆔 `{uid}`",
                    parse_mode="Markdown",
                    reply_markup={"inline_keyboard": [[
                        {"text": "✅ Approuver", "callback_data": f"approve_{w_id}"},
                        {"text": "❌ Rejeter",   "callback_data": f"reject_{w_id}"}
                    ]]})
            except:
                pass
        new_u = get_user(uid)
        send(uid, f"✅ *Demande envoyee !*\n\n💵 *{amount}F* · {label}\n📱 {masked}\n👤 {name}\n\n💼 Solde restant : *{new_u['balance']}F*\n\n⏳ En cours de traitement...")
        clear_session(uid)


def handle_admin_step(uid, text, sess):
    action = sess.get("action")
    if action == "add_task":
        step = sess.get("step")
        if step == "description":
            sess["description"] = text
            sess["step"] = "link"
            set_session(uid, sess)
            send(uid, "🔗 Lien (ou `-` si aucun) :")
        elif step == "link":
            sess["link"] = None if text.strip() == "-" else text.strip()
            sess["step"] = "reward"
            set_session(uid, sess)
            send(uid, f"💰 Recompense en F (defaut: {get_cfg('bonus_task')}F) :")
        elif step == "reward":
            try:
                reward = int(text.strip())
            except:
                reward = get_cfg("bonus_task")
            db_post("tasks", {"description": sess["description"], "link": sess.get("link"), "reward": reward, "date": str(date.today()), "is_active": True})
            send(uid, f"✅ Tache ajoutee !\n\n📝 {sess['description']}\n💰 *{reward}F*")
            clear_session(uid)
    elif action == "ban":
        t = text.strip()
        if t.startswith("debannir "):
            try:
                tid = int(t.replace("debannir ", ""))
                db_patch("users", {"user_id": f"eq.{tid}"}, {"is_banned": False})
                send(uid, f"✅ User `{tid}` debanni.")
                send(tid, "✅ Ton compte a ete reactive.")
            except:
                send(uid, "❌ ID invalide.")
        else:
            try:
                tid = int(t)
                db_patch("users", {"user_id": f"eq.{tid}"}, {"is_banned": True})
                send(uid, f"🚫 User `{tid}` banni.")
                send(tid, "🚫 Compte suspendu.")
            except:
                send(uid, "❌ ID invalide.")
        clear_session(uid)
    elif action == "broadcast":
        users = db_get("users", {"is_registered": "eq.true"})
        sent = 0
        for uu in users:
            if not uu.get("is_banned"):
                try:
                    tg("sendMessage", chat_id=uu["user_id"], text=f"📢 *Message XAFEARN*\n\n{text}", parse_mode="Markdown")
                    sent += 1
                except:
                    pass
        send(uid, f"✅ Broadcast : *{sent}* envoyes.")
        clear_session(uid)


def handle_cb(uid, data, mid, cid):
    if data == "check_join":
        u = get_user(uid)
        if not u:
            return
        if not check_joined(uid):
            channels_list = "\n".join([f"  ➤ {ch}" for ch in CHANNELS])
            edit(uid, mid, f"❌ *Tu n'as pas tout rejoint.*\n\n{channels_list}\n\nPuis clique Verifier",
                kb={"inline_keyboard": [[{"text": "🔄 Verifier a nouveau", "callback_data": "check_join"}]]})
            return
        db_patch("users", {"user_id": f"eq.{uid}"}, {"is_registered": True})
        if u.get("referred_by") and not u.get("is_registered"):
            parrain = get_user(u["referred_by"])
            if parrain and parrain.get("is_registered") and not parrain.get("is_banned"):
                bonus_ref = get_cfg("bonus_referral")
                update_balance(u["referred_by"], bonus_ref)
                db_post("transactions", {"user_id": u["referred_by"], "type": "parrainage", "amount": bonus_ref, "description": f"Filleul @{u.get('username','?')}"})
                try:
                    send(u["referred_by"], f"🎉 *+{bonus_ref}F* — Filleul @{u.get('username','?')} inscrit !")
                except:
                    pass
        ref_link = f"https://t.me/{BOT_USERNAME}?start={uid}"
        edit(uid, mid, f"✅ *Compte active !*\n\n🔗 Ton lien :\n`{ref_link}`")
        send(uid, "🏠 *Menu Principal — XAFEARN*\n\nQue veux-tu faire ? 👇", kb=main_kb())

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
            db_post("transactions", {"user_id": uid, "type": "tache", "amount": task["reward"], "description": task["description"][:50]})
            u = get_user(uid)
            send(uid, f"🎯 *Tache validee !*\n\n💵 +{task['reward']}F ✅\n💼 Solde : *{u['balance']}F*")

    elif data.startswith("method_"):
        method = data.split("_")[1]
        label  = "📱 Mobile Money" if method == "mobile" else "🏦 Virement"
        set_session(uid, {"action": "retrait", "method": method, "step": "amount"})
        edit(uid, mid, f"💸 *{label}*\n\nCombien veux-tu retirer ? (en F)")

    elif data == "cancel_retrait":
        clear_session(uid)
        edit(uid, mid, "❌ *Retrait annule.*")

    elif data.startswith("approve_") or data.startswith("reject_"):
        parts = data.split("_")
        decision = parts[0]
        w_id = int(parts[1])
        ws = db_get("withdrawals", {"id": f"eq.{w_id}"})
        if not ws or ws[0].get("status") != "pending":
            return
        w = ws[0]
        masked = w["number"][:4] + " *** ** ** " + w["number"][-2:]
        label  = "📱 Mobile Money" if w["method"] == "mobile" else "🏦 Virement"
        if decision == "approve":
            db_patch("withdrawals", {"id": f"eq.{w_id}"}, {"status": "approved"})
            edit(cid, mid,
                f"✅ *PAIEMENT EFFECTUE*\n\n"
                f"💰 *{w['amount']}F* · {label}\n"
                f"📱 {masked}\n👤 {w['name']}\n\n"
                f"🤖 Via @{BOT_USERNAME}\n"
                f"Rejoins et gagne toi aussi !")
            try:
                send(w["user_id"], f"✅ *Retrait approuve !*\n\n💵 *{w['amount']}F* envoye ! 🙏")
            except:
                pass
        else:
            db_patch("withdrawals", {"id": f"eq.{w_id}"}, {"status": "rejected"})
            update_balance(w["user_id"], w["amount"])
            db_post("transactions", {"user_id": w["user_id"], "type": "remboursement", "amount": w["amount"], "description": f"Retrait #{w_id} refuse"})
            edit(cid, mid, f"❌ *RETRAIT REJETE #{w_id}*")
            try:
                send(w["user_id"], f"❌ *Retrait refuse*\n\n💵 *{w['amount']}F* rembourse.\n📩 @xafearn_support")
            except:
                pass

application = app
handler = app