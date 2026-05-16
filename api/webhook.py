import os, json
from flask import Flask, request, Response
import requests as req

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

# ── Telegram ─────────────────────────────────────
def tg(method, **kw):
    try:
        return req.post(f"{API}/{method}", json=kw, timeout=15).json()
    except Exception as e:
        print(f"tg error {method}: {e}")
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

# ── Claviers ─────────────────────────────────────
def main_kb():
    return {"keyboard": [
        ["🎁 Bonus", "👥 Parrainage"],
        ["💰 Solde", "📋 Historique"],
        ["💸 Retrait", "✅ Tâches"],
        ["🏆 Classement", "❓ Aide"]
    ], "resize_keyboard": True}

def admin_kb():
    return {"keyboard": [
        ["👥 Tous les Users", "📊 Statistiques"],
        ["⚙️ Modifier les Prix", "➕ Ajouter une Tâche"],
        ["💸 Demandes Retrait", "🚫 Bannir / Débannir"],
        ["📢 Broadcast", "🔙 Mode Utilisateur"]
    ], "resize_keyboard": True}

# ── Supabase ─────────────────────────────────────
def db_get(table, f={}):
    try:
        r = req.get(f"{DB}/{table}", headers=H, params=f, timeout=15)
        if r.status_code in [200, 206]:
            data = r.json()
            return data if isinstance(data, list) else []
        return []
    except Exception as e:
        print(f"db_get error {table}: {e}")
        return []

def db_post(table, data):
    try:
        r = req.post(f"{DB}/{table}", headers=H, json=data, timeout=15)
        if r.status_code in [200, 201]:
            result = r.json()
            return result if isinstance(result, list) else []
        return []
    except Exception as e:
        print(f"db_post error {table}: {e}")
        return []

def db_patch(table, f, data):
    try:
        req.patch(f"{DB}/{table}", headers=H, params=f, json=data, timeout=15)
    except Exception as e:
        print(f"db_patch error {table}: {e}")

def db_del(table, f):
    try:
        req.delete(f"{DB}/{table}", headers=H, params=f, timeout=15)
    except Exception as e:
        print(f"db_del error {table}: {e}")

# ── Helpers DB ────────────────────────────────────
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
    r = db_get("users", {"referred_by": f"eq.{uid}", "is_registered": "eq.true"})
    return len(r)

def check_joined(uid):
    for ch in CHANNELS:
        try:
            r = tg("getChatMember", chat_id=ch, user_id=uid)
            if r.get("result", {}).get("status") in ["left", "kicked"]:
                return False
        except:
            return False
    return True

# ── Sessions ──────────────────────────────────────
def get_session(uid):
    try:
        r = db_get("sessions", {"user_id": f"eq.{uid}"})
        if r:
            return json.loads(r[0]["data"])
        return {}
    except:
        return {}

def set_session(uid, data):
    try:
        r = db_get("sessions", {"user_id": f"eq.{uid}"})
        if r:
            db_patch("sessions", {"user_id": f"eq.{uid}"}, {"data": json.dumps(data)})
        else:
            db_post("sessions", {"user_id": uid, "data": json.dumps(data)})
    except Exception as e:
        print(f"set_session error: {e}")

def clear_session(uid):
    try:
        db_del("sessions", {"user_id": f"eq.{uid}"})
    except:
        pass

# ── Routes ────────────────────────────────────────
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
            if text:
                try:
                    handle_msg(uid, uname, text)
                except Exception as e:
                    print(f"handle_msg error: {e}")
                    try:
                        send(uid, f"❌ Erreur : `{str(e)[:100]}`")
                    except:
                        pass

        elif "callback_query" in body:
            cq   = body["callback_query"]
            uid  = cq["from"]["id"]
            data = cq.get("data", "")
            mid  = cq["message"]["message_id"]
            cid  = cq["message"]["chat"]["id"]
            tg("answerCallbackQuery", callback_query_id=cq["id"])
            try:
                handle_cb(uid, data, mid, cid)
            except Exception as e:
                print(f"handle_cb error: {e}")

    except Exception as e:
        print(f"webhook error: {e}")

    return Response('{"ok":true}', mimetype="application/json")


# ── Messages ──────────────────────────────────────
def handle_msg(uid, uname, text):
    from datetime import date

    # Sessions actives
    sess = get_session(uid)
    if sess.get("action") == "retrait":
        handle_retrait_step(uid, text, sess)
        return
    if sess.get("action") in ["add_task", "ban", "broadcast"] and uid in ADMIN_IDS:
        handle_admin_step(uid, text, sess)
        return

    # /start
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
            f"💰 Gagne de l'argent chaque jour :\n"
            f"  🎁 Bonus journalier\n"
            f"  👥 Parrainage\n"
            f"  ✅ Tâches quotidiennes\n\n"
            f"📌 *Étape 1* — Rejoins nos canaux :\n{channels_list}\n\n"
            f"📌 *Étape 2* — Clique ✅",
            kb={"inline_keyboard": [[
                {"text": "✅ J'ai tout rejoint — Vérifier", "callback_data": "check_join"}
            ]]}
        )
        return

    # Vérif user
    u = get_user(uid)
    if not u:
        send(uid, "❌ Utilise /start pour t'inscrire.")
        return
    if u.get("is_banned"):
        send(uid, "🚫 Compte suspendu.")
        return

    # ADMIN
    if uid in ADMIN_IDS:
        if text in ["/admin", "📊 Statistiques"]:
            users = db_get("users")
            ws    = db_get("withdrawals")
            send(uid,
                f"⚙️ *PANEL ADMIN — XAFEARN*\n━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"👥 Total : *{len(users)}*\n"
                f"✅ Actifs : *{sum(1 for x in users if x.get('is_registered'))}*\n"
                f"🚫 Bannis : *{sum(1 for x in users if x.get('is_banned'))}*\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"💵 Soldes : *{sum(x.get('balance',0) for x in users)}F*\n"
                f"✅ Payé : *{sum(x.get('amount',0) for x in ws if x.get('status')=='approved')}F*\n"
                f"⏳ En attente : *{sum(1 for x in ws if x.get('status')=='pending')}*",
                kb=admin_kb()
            )
            return

        if text == "👥 Tous les Users":
            users = db_get("users")
            t = f"👥 *UTILISATEURS ({len(users)})*\n━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            for uu in users[:20]:
                s = "🚫" if uu.get("is_banned") else ("✅" if uu.get("is_registered") else "⏳")
                t += f"{s} @{uu.get('username','N/A')} — *{uu.get('balance',0)}F*\n"
            send(uid, t)
            return

        if text == "⚙️ Modifier les Prix":
            send(uid,
                f"⚙️ *CONFIG ACTUELLE*\n━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"🎁 Bonus journalier : *{get_cfg('bonus_daily')}F*\n"
                f"👥 Bonus parrainage : *{get_cfg('bonus_referral')}F*\n"
                f"✅ Bonus tâche : *{get_cfg('bonus_task')}F*\n"
                f"💸 Retrait min : *{get_cfg('min_withdrawal')}F*\n\n"
                f"`/setbonus 50`\n`/setref 75`\n`/settask 35`\n`/setmin 2500`"
            )
            return

        if text.startswith("/setbonus "):
            set_cfg("bonus_daily", text.split()[1])
            send(uid, f"✅ Bonus journalier → *{text.split()[1]}F*"); return
        if text.startswith("/setref "):
            set_cfg("bonus_referral", text.split()[1])
            send(uid, f"✅ Bonus parrainage → *{text.split()[1]}F*"); return
        if text.startswith("/settask "):
            set_cfg("bonus_task", text.split()[1])
            send(uid, f"✅ Bonus tâche → *{text.split()[1]}F*"); return
        if text.startswith("/setmin "):
            set_cfg("min_withdrawal", text.split()[1])
            send(uid, f"✅ Retrait min → *{text.split()[1]}F*"); return

        if text == "➕ Ajouter une Tâche":
            set_session(uid, {"action": "add_task", "step": "description"})
            send(uid, "➕ *NOUVELLE TÂCHE*\n\nDécris la tâche :"); return

        if text == "💸 Demandes Retrait":
            pending = db_get("withdrawals", {"status": "eq.pending"})
            if not pending:
                send(uid, "💸 *Aucune demande en attente.* ✅")
            else:
                t = f"💸 *EN ATTENTE ({len(pending)})*\n━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                for w in pending:
                    t += f"🆔 *#{w['id']}* · *{w['amount']}F* · {w.get('name','')}\n"
                send(uid, t)
            return

        if text == "🚫 Bannir / Débannir":
            set_session(uid, {"action": "ban"})
            send(uid, "🚫 *BANNIR / DÉBANNIR*\n\nEnvoie l'ID :\nBannir : `123456789`\nDébannir : `debannir 123456789`"); return

        if text == "📢 Broadcast":
            set_session(uid, {"action": "broadcast"})
            send(uid, "📢 Écris le message à envoyer à tous :"); return

        if text == "🔙 Mode Utilisateur":
            send(uid, "👤 *Mode Utilisateur activé*", kb=main_kb()); return

    # Vérif inscription
    if not u.get("is_registered"):
        send(uid, "⚠️ Rejoins nos canaux d'abord.\n\nEnvoie /start")
        return

    today = str(date.today())

    # 🎁 Bonus
    if text == "🎁 Bonus":
        bonus = get_cfg("bonus_daily")
        if str(u.get("last_bonus")) == today:
            send(uid,
                f"⏳ *Bonus déjà récupéré aujourd'hui !*\n\n"
                f"💼 Solde actuel : *{u['balance']}F*\n\n"
                f"🔔 Reviens demain pour *+{bonus}F* 📅"
            )
            return
        update_balance(uid, bonus)
        db_patch("users", {"user_id": f"eq.{uid}"}, {"last_bonus": today})
        db_post("transactions", {"user_id": uid, "type": "bonus", "amount": bonus, "description": "Bonus journalier"})
        new_u = get_user(uid)
        send(uid,
            f"🎁 *BONUS JOURNALIER REÇU !*\n━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"💵 +*{bonus}F* crédité ✅\n"
            f"💼 Nouveau solde : *{new_u['balance']}F*\n\n"
            f"📅 _Reviens demain pour un nouveau bonus !_ 🔥"
        )

    # 💰 Solde
    elif text == "💰 Solde":
        nb = get_ref_count(uid)
        bonus_ref = get_cfg("bonus_referral")
        ref_link = f"https://t.me/{BOT_USERNAME}?start={uid}"
        send(uid,
            f"💼 *TON COMPTE XAFEARN*\n━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"💵 Solde disponible : *{u['balance']}F*\n"
            f"👥 Filleuls actifs : *{nb}*\n"
            f"💰 Gains parrainage : *{nb * bonus_ref}F*\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🔗 *Ton lien de parrainage :*\n`{ref_link}`"
        )

    # 👥 Parrainage
    elif text == "👥 Parrainage":
        nb = get_ref_count(uid)
        bonus_ref = get_cfg("bonus_referral")
        ref_link = f"https://t.me/{BOT_USERNAME}?start={uid}"
        send(uid,
            f"👥 *TON LIEN D'AFFILIATION*\n━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🔗 {ref_link}\n\n"
            f"📊 Parrainages validés : *{nb}*\n"
            f"💰 Gain par parrainage : *{bonus_ref}F*\n"
            f"💵 Total gagné : *{nb * bonus_ref}F*\n\n"
            f"📤 _Partage et gagne {bonus_ref}F à chaque inscription !_ 🚀"
        )

    # 📋 Historique
    elif text == "📋 Historique":
        txs = db_get("transactions", {"user_id": f"eq.{uid}", "order": "created_at.desc", "limit": "10"})
        wds = db_get("withdrawals", {"user_id": f"eq.{uid}", "order": "requested_at.desc", "limit": "5"})
        t = f"📋 *HISTORIQUE DE TON COMPTE*\n━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        t += "💰 *Transactions :*\n"
        if txs:
            for tx in txs:
                sign = "+" if tx["amount"] > 0 else ""
                d = str(tx.get("created_at", ""))[:10]
                t += f"  {sign}{tx['amount']}F · {tx['description']} · _{d}_\n"
        else:
            t += "  _Aucune transaction._\n"
        t += "\n💸 *Retraits :*\n"
        se = {"pending": "⏳", "approved": "✅", "rejected": "❌"}
        if wds:
            for w in wds:
                d = str(w.get("requested_at", ""))[:10]
                t += f"  {se.get(w.get('status'),'?')} *{w['amount']}F* · {w['method']} · _{d}_\n"
        else:
            t += "  _Aucun retrait._\n"
        send(uid, t)

    # 💸 Retrait
    elif text == "💸 Retrait":
        min_w = get_cfg("min_withdrawal")
        balance = u["balance"]
        if balance < min_w:
            send(uid,
                f"❌ *Solde insuffisant*\n\n"
                f"💼 Ton solde : *{balance}F*\n"
                f"📌 Minimum requis : *{min_w}F*\n\n"
                f"💡 _Continue à parrainer pour atteindre {min_w}F !_"
            )
            return
        pending = db_get("withdrawals", {"user_id": f"eq.{uid}", "status": "eq.pending"})
        if pending:
            send(uid,
                f"⏳ *Tu as déjà une demande en attente*\n\n"
                f"💵 Montant : *{pending[0]['amount']}F*\n"
                f"_Attends qu'elle soit traitée avant d'en faire une nouvelle._"
            )
            return
        send(uid,
            f"💸 *DEMANDE DE RETRAIT*\n━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"💼 Solde disponible : *{balance}F*\n"
            f"📌 Minimum : *{min_w}F*\n\n"
            f"Choisis ta méthode de paiement 👇",
            kb={"inline_keyboard": [
                [{"text": "📱 Mobile Money", "callback_data": "method_mobile"}],
                [{"text": "🏦 Virement Bancaire", "callback_data": "method_bank"}],
                [{"text": "❌ Annuler", "callback_data": "cancel_retrait"}]
            ]}
        )

    # ✅ Tâches
    elif text == "✅ Tâches":
        tasks = db_get("tasks", {"date": f"eq.{today}", "is_active": "eq.true"})
        if not tasks:
            send(uid, "📋 *Aucune tâche disponible aujourd'hui.*\n\n⏳ Reviens plus tard !")
            return
        msg_text = f"✅ *TÂCHES DU JOUR*\n━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        buttons = []
        for t in tasks:
            done = len(db_get("user_tasks", {"user_id": f"eq.{uid}", "task_id": f"eq.{t['id']}"})) > 0
            msg_text += f"{'✅' if done else '⭕'} *{t['description']}*\n"
            if t.get("link"):
                msg_text += f"   🔗 {t['link']}\n"
            msg_text += f"   💰 Récompense : *{t['reward']}F*\n\n"
            if not done:
                buttons.append([{"text": f"✅ Valider · {t['description'][:25]}", "callback_data": f"task_{t['id']}"}])
        if not buttons:
            msg_text += "🎊 *Toutes les tâches sont complétées !* 🏆"
        send(uid, msg_text, kb={"inline_keyboard": buttons} if buttons else None)

    # 🏆 Classement
    elif text == "🏆 Classement":
        users = db_get("users", {"is_registered": "eq.true"})
        ranked = sorted(users, key=lambda x: get_ref_count(x["user_id"]), reverse=True)[:10]
        medals = ["🥇","🥈","🥉","4️⃣","5️⃣","6️⃣","7️⃣","8️⃣","9️⃣","🔟"]
        t = "🏆 *TOP PARRAINEURS XAFEARN*\n━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        for i, uu in enumerate(ranked):
            t += f"{medals[i]} @{uu.get('username','Anonyme')} — *{get_ref_count(uu['user_id'])} filleuls*\n"
        if not ranked:
            t += "_Sois le premier !_ 🚀"
        send(uid, t)

    # ❓ Aide
    elif text == "❓ Aide":
        send(uid,
            f"❓ *AIDE — XAFEARN*\n━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🎁 *Bonus journalier*\n"
            f"   Récupère *{get_cfg('bonus_daily')}F* chaque jour\n\n"
            f"👥 *Parrainage*\n"
            f"   Invite un ami = *{get_cfg('bonus_referral')}F* pour toi\n\n"
            f"✅ *Tâches*\n"
            f"   Complète des tâches = *{get_cfg('bonus_task')}F* chacune\n\n"
            f"💸 *Retrait*\n"
            f"   Minimum : *{get_cfg('min_withdrawal')}F*\n"
            f"   Méthodes : Mobile Money / Virement\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📩 *Support WhatsApp :*\n"
            f"https://wa.me/22890000000"
        )


# ── Retrait étapes ────────────────────────────────
def handle_retrait_step(uid, text, sess):
    step = sess.get("step")
    u = get_user(uid)
    min_w = get_cfg("min_withdrawal")

    if step == "amount":
        try:
            amount = int(text.strip())
        except:
            send(uid, "❌ Montant invalide. Envoie un nombre (ex: 2500)")
            return
        if amount < min_w:
            send(uid, f"❌ Minimum : *{min_w}F*")
            return
        if amount > u["balance"]:
            send(uid, f"❌ Solde insuffisant ! Ton solde : *{u['balance']}F*")
            return
        sess["amount"] = amount
        sess["step"] = "number"
        set_session(uid, sess)
        send(uid, f"✅ Montant : *{amount}F*\n\n📱 Envoie ton *numéro de paiement* :")

    elif step == "number":
        if len(text.strip()) < 8:
            send(uid, "❌ Numéro invalide. Réessaie.")
            return
        sess["number"] = text.strip()
        sess["step"] = "name"
        set_session(uid, sess)
        send(uid, "✅ Numéro enregistré.\n\n👤 Envoie ton *nom complet* :")

    elif step == "name":
        if len(text.strip()) < 3:
            send(uid, "❌ Nom invalide. Réessaie.")
            return
        sess["name"] = text.strip()
        amount = sess["amount"]
        method = sess["method"]
        number = sess["number"]
        name   = sess["name"]

        update_balance(uid, -amount)
        r = db_post("withdrawals", {
            "user_id": uid, "amount": amount,
            "method": method, "number": number,
            "name": name, "status": "pending"
        })
        w_id = r[0]["id"] if r else "?"
        db_post("transactions", {"user_id": uid, "type": "retrait", "amount": -amount, "description": f"Demande retrait #{w_id}"})

        masked = number[:4] + " *** ** ** " + number[-2:] if len(number) >= 6 else number
        label  = "📱 Mobile Money" if method == "mobile" else "🏦 Virement"

        if RETRAIT_CHANNEL_ID and RETRAIT_CHANNEL_ID != "0":
            try:
                tg("sendMessage",
                    chat_id=int(RETRAIT_CHANNEL_ID),
                    text=f"💸 *DEMANDE DE RETRAIT #{w_id}*\n━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                         f"💵 Montant : *{amount}F*\n"
                         f"⚙️ Méthode : *{label}*\n"
                         f"📱 Numéro : *{masked}*\n"
                         f"👤 Nom : *{name}*\n\n"
                         f"👤 User : @{u.get('username','N/A')}\n"
                         f"🆔 ID : `{uid}`\n━━━━━━━━━━━━━━━━━━━━━━━",
                    parse_mode="Markdown",
                    reply_markup={"inline_keyboard": [[
                        {"text": "✅ Approuver", "callback_data": f"approve_{w_id}"},
                        {"text": "❌ Rejeter",   "callback_data": f"reject_{w_id}"}
                    ]]}
                )
            except Exception as e:
                print(f"canal retrait error: {e}")

        new_u = get_user(uid)
        send(uid,
            f"✅ *Demande envoyée !*\n━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"💵 Montant : *{amount}F*\n"
            f"⚙️ Méthode : *{label}*\n"
            f"📱 Numéro : *{masked}*\n"
            f"👤 Nom : *{name}*\n\n"
            f"💼 Solde restant : *{new_u['balance']}F*\n\n"
            f"⏳ _En cours de traitement..._"
        )
        clear_session(uid)


# ── Admin étapes ──────────────────────────────────
def handle_admin_step(uid, text, sess):
    action = sess.get("action")

    if action == "add_task":
        step = sess.get("step")
        if step == "description":
            sess["description"] = text
            sess["step"] = "link"
            set_session(uid, sess)
            send(uid, "🔗 Lien de la tâche :\n_(Envoie `-` si pas de lien)_")
        elif step == "link":
            sess["link"] = None if text.strip() == "-" else text.strip()
            sess["step"] = "reward"
            set_session(uid, sess)
            send(uid, f"💰 Récompense en F :\n_(Défaut: {get_cfg('bonus_task')}F — envoie `-` pour garder)_")
        elif step == "reward":
            try:
                reward = int(text.strip())
            except:
                reward = get_cfg("bonus_task")
            from datetime import date
            db_post("tasks", {
                "description": sess["description"],
                "link": sess.get("link"),
                "reward": reward,
                "date": str(date.today()),
                "is_active": True
            })
            send(uid,
                f"✅ *Tâche ajoutée !*\n\n"
                f"📝 {sess['description']}\n"
                f"💰 Récompense : *{reward}F*"
            )
            clear_session(uid)

    elif action == "ban":
        t = text.strip()
        if t.startswith("debannir "):
            try:
                tid = int(t.replace("debannir ", ""))
                db_patch("users", {"user_id": f"eq.{tid}"}, {"is_banned": False})
                send(uid, f"✅ User `{tid}` débanni.")
                try:
                    send(tid, "✅ *Ton compte a été réactivé.*")
                except:
                    pass
            except:
                send(uid, "❌ ID invalide.")
        else:
            try:
                tid = int(t)
                db_patch("users", {"user_id": f"eq.{tid}"}, {"is_banned": True})
                send(uid, f"🚫 User `{tid}` banni.")
                try:
                    send(tid, "🚫 *Ton compte a été suspendu.*")
                except:
                    pass
            except:
                send(uid, "❌ ID invalide.")
        clear_session(uid)

    elif action == "broadcast":
        users = db_get("users", {"is_registered": "eq.true"})
        sent = 0
        for uu in users:
            if not uu.get("is_banned"):
                try:
                    tg("sendMessage",
                        chat_id=uu["user_id"],
                        text=f"📢 *Message XAFEARN*\n━━━━━━━━━━━━━━━━━━━━━━━\n\n{text}",
                        parse_mode="Markdown"
                    )
                    sent += 1
                except:
                    pass
        send(uid, f"✅ *Broadcast terminé !*\n\n📤 Envoyé à *{sent}* utilisateurs.")
        clear_session(uid)


# ── Callbacks ─────────────────────────────────────
def handle_cb(uid, data, mid, cid):
    from datetime import date
    today = str(date.today())

    if data == "check_join":
        u = get_user(uid)
        if not u:
            return
        if not check_joined(uid):
            channels_list = "\n".join([f"  ➤ {ch}" for ch in CHANNELS])
            edit(uid, mid,
                f"❌ *Tu n'as pas encore tout rejoint.*\n\n"
                f"{channels_list}\n\n"
                f"_Rejoins puis clique Vérifier_ 👇",
                kb={"inline_keyboard": [[
                    {"text": "🔄 Vérifier à nouveau", "callback_data": "check_join"}
                ]]}
            )
            return

        db_patch("users", {"user_id": f"eq.{uid}"}, {"is_registered": True})

        if u.get("referred_by") and not u.get("is_registered"):
            parrain = get_user(u["referred_by"])
            if parrain and parrain.get("is_registered") and not parrain.get("is_banned"):
                bonus_ref = get_cfg("bonus_referral")
                update_balance(u["referred_by"], bonus_ref)
                db_post("transactions", {
                    "user_id": u["referred_by"],
                    "type": "parrainage",
                    "amount": bonus_ref,
                    "description": f"Filleul @{u.get('username','?')} inscrit"
                })
                try:
                    send(u["referred_by"],
                        f"🎉 *+{bonus_ref}F crédité !*\n\n"
                        f"Ton filleul *@{u.get('username','?')}* vient de valider son inscription !"
                    )
                except:
                    pass

        ref_link = f"https://t.me/{BOT_USERNAME}?start={uid}"
        edit(uid, mid,
            f"✅ *Compte activé avec succès !*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🔗 *Ton lien de parrainage :*\n`{ref_link}`\n\n"
            f"💡 _Partage-le et gagne à chaque inscription !_"
        )
        send(uid,
            "🏠 *Menu Principal — XAFEARN*\n\n_Que veux-tu faire ?_ 👇",
            kb=main_kb()
        )

    elif data.startswith("task_"):
        task_id = int(data.split("_")[1])
        if db_get("user_tasks", {"user_id": f"eq.{uid}", "task_id": f"eq.{task_id}"}):
            tg("answerCallbackQuery", callback_query_id=str(mid), text="⚠️ Déjà complétée !", show_alert=True)
            return
        tasks = db_get("tasks", {"id": f"eq.{task_id}"})
        if tasks:
            task = tasks[0]
            db_post("user_tasks", {"user_id": uid, "task_id": task_id})
            update_balance(uid, task["reward"])
            db_post("transactions", {
                "user_id": uid, "type": "tâche",
                "amount": task["reward"],
                "description": task["description"][:50]
            })
            u = get_user(uid)
            send(uid,
                f"🎯 *Tâche validée !*\n\n"
                f"💵 +{task['reward']}F crédité ✅\n"
                f"💼 Nouveau solde : *{u['balance']}F*"
            )

    elif data.startswith("method_"):
        method = data.split("_")[1]
        label  = "📱 Mobile Money" if method == "mobile" else "🏦 Virement"
        set_session(uid, {"action": "retrait", "method": method, "step": "amount"})
        edit(uid, mid,
            f"💸 *{label}*\n━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"Quel montant veux-tu retirer ? _(en F)_\n\n"
            f"👇 Réponds avec le montant :"
        )

    elif data == "cancel_retrait":
        clear_session(uid)
        edit(uid, mid, "❌ *Retrait annulé.*")

    elif data.startswith("approve_") or data.startswith("reject_"):
        parts    = data.split("_")
        decision = parts[0]
        w_id     = int(parts[1])
        ws = db_get("withdrawals", {"id": f"eq.{w_id}"})
        if not ws or ws[0].get("status") != "pending":
            return
        w      = ws[0]
        masked = w["number"][:4] + " *** ** ** " + w["number"][-2:]
        label  = "📱 Mobile Money" if w["method"] == "mobile" else "🏦 Virement"

        if decision == "approve":
            db_patch("withdrawals", {"id": f"eq.{w_id}"}, {"status": "approved"})
            edit(cid, mid,
                f"✅ *PAIEMENT EFFECTUÉ*\n━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"💰 Montant : *{w['amount']}F*\n"
                f"⚙️ Méthode : *{label}*\n"
                f"📱 Numéro : *{masked}*\n"
                f"👤 Nom : *{w['name']}*\n\n"
                f"🤖 Via @{BOT_USERNAME}\n"
                f"➡️ _Rejoins et gagne toi aussi !_"
            )
            try:
                send(w["user_id"],
                    f"✅ *Retrait approuvé !*\n\n"
                    f"💵 *{w['amount']}F* envoyé sur ton compte.\n"
                    f"Merci de ta confiance ! 🙏"
                )
            except:
                pass
        else:
            db_patch("withdrawals", {"id": f"eq.{w_id}"}, {"status": "rejected"})
            update_balance(w["user_id"], w["amount"])
            db_post("transactions", {
                "user_id": w["user_id"], "type": "remboursement",
                "amount": w["amount"], "description": f"Retrait #{w_id} refusé"
            })
            edit(cid, mid, f"❌ *RETRAIT REJETÉ #{w_id}*")
            try:
                send(w["user_id"],
                    f"❌ *Retrait refusé*\n\n"
                    f"💵 *{w['amount']}F* remboursé sur ton solde.\n"
                    f"📩 Contacte le support : @xafearn_support"
                )
            except:
                pass


application = app
handler = app