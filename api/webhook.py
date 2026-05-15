import os, json
from flask import Flask, request, Response
import requests as req

app = Flask(__name__)

# ── Config ──────────────────────────────────────────────────────────
TOKEN   = os.environ.get("BOT_TOKEN", "")
SB_URL  = os.environ.get("SUPABASE_URL", "")
SB_KEY  = os.environ.get("SUPABASE_KEY", "")
API     = f"https://api.telegram.org/bot{TOKEN}"
DB      = f"{SB_URL}/rest/v1"
ADMIN_IDS = [int(x.strip()) for x in os.environ.get("ADMIN_IDS","").split(",") if x.strip().isdigit()]
RETRAIT_CHANNEL_ID = os.environ.get("RETRAIT_CHANNEL_ID", "0")
BOT_USERNAME = "xafearn_bot"
CHANNELS = [
    os.environ.get("CHANNEL_1", "@xafearn_money"),
    os.environ.get("CHANNEL_2", "@xafearn_money"),
    os.environ.get("CHANNEL_3", "@xafearn_money"),
]

SB_HEADERS = {
    "apikey": SB_KEY,
    "Authorization": f"Bearer {SB_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation"
}

# ── Telegram helpers ─────────────────────────────────────────────────
def tg(method, **kwargs):
    try:
        return req.post(f"{API}/{method}", json=kwargs, timeout=10).json()
    except:
        return {}

def send(uid, text, kb=None):
    data = {"chat_id": uid, "text": text, "parse_mode": "Markdown"}
    if kb:
        data["reply_markup"] = kb
    tg("sendMessage", **data)

def edit(uid, mid, text, kb=None):
    data = {"chat_id": uid, "message_id": mid, "text": text, "parse_mode": "Markdown"}
    if kb:
        data["reply_markup"] = kb
    tg("editMessageText", **data)

def main_kb():
    return {"keyboard": [
        ["🎁 Bonus Journalier", "👥 Parrainage"],
        ["💰 Mon Solde", "✅ Tâches du Jour"],
        ["📋 Historique", "💸 Retrait"],
        ["🏆 Classement", "❓ Aide"]
    ], "resize_keyboard": True}

def admin_kb():
    return {"keyboard": [
        ["👥 Tous les Users", "📊 Statistiques"],
        ["⚙️ Modifier les Prix", "➕ Ajouter une Tâche"],
        ["💸 Demandes Retrait", "🚫 Bannir / Débannir"],
        ["📢 Broadcast", "🔙 Mode Utilisateur"]
    ], "resize_keyboard": True}

# ── Supabase helpers ─────────────────────────────────────────────────
def db_get(table, filters={}):
    try:
        params = {k: v for k, v in filters.items()}
        r = req.get(f"{DB}/{table}", headers=SB_HEADERS, params=params, timeout=10)
        return r.json() or []
    except:
        return []

def db_post(table, data):
    try:
        r = req.post(f"{DB}/{table}", headers=SB_HEADERS, json=data, timeout=10)
        return r.json()
    except:
        return []

def db_patch(table, filters, data):
    try:
        params = {k: v for k, v in filters.items()}
        req.patch(f"{DB}/{table}", headers=SB_HEADERS, params=params, json=data, timeout=10)
    except:
        pass

def db_delete(table, filters):
    try:
        params = {k: v for k, v in filters.items()}
        req.delete(f"{DB}/{table}", headers=SB_HEADERS, params=params, timeout=10)
    except:
        pass

# ── Sessions (pour retrait multi-étapes) ────────────────────────────
def get_session(uid):
    rows = db_get("sessions", {"user_id": f"eq.{uid}"})
    if rows:
        try:
            return json.loads(rows[0]["data"])
        except:
            return {}
    return {}

def set_session(uid, data):
    existing = db_get("sessions", {"user_id": f"eq.{uid}"})
    if existing:
        db_patch("sessions", {"user_id": f"eq.{uid}"}, {"data": json.dumps(data)})
    else:
        db_post("sessions", {"user_id": uid, "data": json.dumps(data)})

def clear_session(uid):
    db_delete("sessions", {"user_id": f"eq.{uid}"})

# ── DB functions ─────────────────────────────────────────────────────
def get_user(uid):
    rows = db_get("users", {"user_id": f"eq.{uid}"})
    return rows[0] if rows else None

def add_user(uid, username, referred_by=None):
    try:
        db_post("users", {
            "user_id": uid, "username": username,
            "referred_by": referred_by, "balance": 0,
            "is_banned": False, "is_registered": False
        })
    except:
        pass

def update_balance(uid, amount):
    u = get_user(uid)
    if u:
        new_bal = max(0, u["balance"] + amount)
        db_patch("users", {"user_id": f"eq.{uid}"}, {"balance": new_bal})

def get_cfg(key):
    rows = db_get("config", {"key": f"eq.{key}"})
    if rows:
        try:
            return int(rows[0]["value"])
        except:
            return 0
    defaults = {"bonus_daily":100,"bonus_referral":75,"bonus_task":35,"min_withdrawal":500}
    return defaults.get(key, 0)

def set_cfg(key, val):
    db_patch("config", {"key": f"eq.{key}"}, {"value": str(val)})

def get_ref_count(uid):
    rows = db_get("users", {"referred_by": f"eq.{uid}", "is_registered": "eq.true"})
    return len(rows)

# ── Vérifier canaux ─────────────────────────────────────────────────
def check_membership(uid):
    for ch in CHANNELS:
        r = tg("getChatMember", chat_id=ch, user_id=uid)
        status = r.get("result", {}).get("status", "left")
        if status in ["left", "kicked"]:
            return False
    return True

# ── Routes ──────────────────────────────────────────────────────────
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
                handle_msg(uid, uname, text)

        elif "callback_query" in body:
            cq    = body["callback_query"]
            uid   = cq["from"]["id"]
            data  = cq.get("data", "")
            mid   = cq["message"]["message_id"]
            cid   = cq["message"]["chat"]["id"]
            tg("answerCallbackQuery", callback_query_id=cq["id"])
            handle_cb(uid, data, mid, cid)

    except Exception as e:
        print(f"webhook error: {e}")

    return Response('{"ok":true}', mimetype="application/json")


def handle_msg(uid, uname, text):
    from datetime import date

    # ── Session retrait active ───────────────────────
    sess = get_session(uid)
    if sess.get("action") == "retrait":
        handle_retrait_step(uid, text, sess)
        return

    # ── Session admin active ─────────────────────────
    if sess.get("action") in ["add_task", "ban", "broadcast"] and uid in ADMIN_IDS:
        handle_admin_step(uid, text, sess)
        return

    # ── /start ───────────────────────────────────────
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
            add_user(uid, uname, referred_by)

        channels_list = "\n".join([f"  ➤ {ch}" for ch in CHANNELS])
        send(uid,
            f"👑 *Bienvenue sur XAFEARN, {uname} !*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"💰 Gagne de l'argent chaque jour :\n"
            f"  🎁 Bonus journalier\n  👥 Parrainage\n  ✅ Tâches\n\n"
            f"📌 Rejoins nos canaux :\n{channels_list}\n\n"
            f"📌 Puis clique ✅",
            kb={"inline_keyboard": [[{"text": "✅ J'ai tout rejoint — Vérifier", "callback_data": "check_join"}]]}
        )
        return

    # ── Vérif user ───────────────────────────────────
    u = get_user(uid)
    if not u:
        send(uid, "❌ Utilise /start pour t'inscrire.")
        return
    if u.get("is_banned"):
        send(uid, "🚫 Compte suspendu.")
        return

    # ── ADMIN ────────────────────────────────────────
    if uid in ADMIN_IDS:
        if text in ["/admin", "📊 Statistiques"]:
            users = db_get("users")
            ws    = db_get("withdrawals")
            total_bal  = sum(x.get("balance",0) for x in users)
            total_paid = sum(x.get("amount",0) for x in ws if x.get("status")=="approved")
            pending    = sum(1 for x in ws if x.get("status")=="pending")
            send(uid,
                f"⚙️ *PANEL ADMIN*\n━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"👥 Total : *{len(users)}*\n"
                f"✅ Actifs : *{sum(1 for x in users if x.get('is_registered'))}*\n"
                f"💵 Soldes : *{total_bal}F*\n"
                f"✅ Payé : *{total_paid}F*\n"
                f"⏳ Retraits en attente : *{pending}*",
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
                f"⚙️ *CONFIG ACTUELLE*\n\n"
                f"🎁 Bonus journalier : *{get_cfg('bonus_daily')}F*\n"
                f"👥 Bonus parrainage : *{get_cfg('bonus_referral')}F*\n"
                f"✅ Bonus tâche : *{get_cfg('bonus_task')}F*\n"
                f"💸 Retrait min : *{get_cfg('min_withdrawal')}F*\n\n"
                f"`/setbonus 150`\n`/setref 100`\n`/settask 50`\n`/setmin 1000`"
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
            send(uid, "🚫 Envoie l'ID à bannir\nOu `debannir 123456789` pour débannir")
            return

        if text == "📢 Broadcast":
            set_session(uid, {"action": "broadcast"})
            send(uid, "📢 Écris le message à envoyer à tous :"); return

        if text == "🔙 Mode Utilisateur":
            send(uid, "👤 *Mode Utilisateur*", kb=main_kb()); return

    # ── Vérif inscription ────────────────────────────
    if not u.get("is_registered"):
        send(uid, "⚠️ Rejoins nos canaux d'abord. Envoie /start")
        return

    # ── Boutons utilisateur ──────────────────────────
    today = str(date.today())

    if text == "🎁 Bonus Journalier":
        bonus = get_cfg("bonus_daily")
        if str(u.get("last_bonus")) == today:
            send(uid, f"⏳ *Bonus déjà récupéré !*\n\n💼 Solde : *{u['balance']}F*\n🔔 Reviens demain pour +{bonus}F")
            return
        update_balance(uid, bonus)
        db_patch("users", {"user_id": f"eq.{uid}"}, {"last_bonus": today})
        db_post("transactions", {"user_id": uid, "type": "bonus", "amount": bonus, "description": "Bonus journalier"})
        new_u = get_user(uid)
        send(uid, f"🎁 *BONUS REÇU !*\n━━━━━━━━━━━━━━━━━━━━━━━\n\n💵 +*{bonus}F* ✅\n💼 Solde : *{new_u['balance']}F*")

    elif text == "💰 Mon Solde":
        nb = get_ref_count(uid)
        ref_link = f"https://t.me/{BOT_USERNAME}?start={uid}"
        send(uid,
            f"💼 *TON COMPTE XAFEARN*\n━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"💵 Solde : *{u['balance']}F*\n"
            f"👥 Filleuls : *{nb}*\n"
            f"💰 Gains parrainage : *{nb * get_cfg('bonus_referral')}F*\n\n"
            f"🔗 Lien :\n`{ref_link}`"
        )

    elif text == "👥 Parrainage":
        nb = get_ref_count(uid)
        bonus_ref = get_cfg("bonus_referral")
        ref_link = f"https://t.me/{BOT_USERNAME}?start={uid}"
        send(uid,
            f"👥 *TON LIEN D'AFFILIATION*\n━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🔗 {ref_link}\n\n"
            f"📊 Parrainages : *{nb}*\n"
            f"💰 Gain/parrainage : *{bonus_ref}F*\n"
            f"💵 Total gagné : *{nb * bonus_ref}F*"
        )

    elif text == "✅ Tâches du Jour":
        tasks = db_get("tasks", {"date": f"eq.{today}", "is_active": "eq.true"})
        if not tasks:
            send(uid, "📋 *Aucune tâche aujourd'hui.*\n\n⏳ Reviens plus tard !")
            return
        msg_text = "✅ *TÂCHES DU JOUR*\n━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        buttons = []
        for t in tasks:
            done_rows = db_get("user_tasks", {"user_id": f"eq.{uid}", "task_id": f"eq.{t['id']}"})
            done = len(done_rows) > 0
            msg_text += f"{'✅' if done else '⭕'} *{t['description']}*\n"
            if t.get("link"):
                msg_text += f"   🔗 _{t['link']}_\n"
            msg_text += f"   💰 *{t['reward']}F*\n\n"
            if not done:
                buttons.append([{"text": f"✅ {t['description'][:30]}", "callback_data": f"task_{t['id']}"}])
        kb = {"inline_keyboard": buttons} if buttons else None
        send(uid, msg_text, kb=kb)

    elif text == "📋 Historique":
        txs = db_get("transactions", {"user_id": f"eq.{uid}", "order": "created_at.desc", "limit": "8"})
        wds = db_get("withdrawals", {"user_id": f"eq.{uid}", "order": "requested_at.desc", "limit": "5"})
        t = "📋 *HISTORIQUE*\n━━━━━━━━━━━━━━━━━━━━━━━\n\n💰 *Transactions :*\n"
        if txs:
            for tx in txs:
                sign = "+" if tx["amount"] > 0 else ""
                t += f"  {sign}{tx['amount']}F · {tx['description']}\n"
        else:
            t += "  _Aucune._\n"
        t += "\n💸 *Retraits :*\n"
        s_e = {"pending":"⏳","approved":"✅","rejected":"❌"}
        if wds:
            for w in wds:
                t += f"  {s_e.get(w.get('status'),'?')} {w['amount']}F\n"
        else:
            t += "  _Aucun._\n"
        send(uid, t)

    elif text == "💸 Retrait":
        min_w = get_cfg("min_withdrawal")
        if u["balance"] < min_w:
            send(uid, f"❌ *Solde insuffisant*\n\n💼 Solde : *{u['balance']}F*\n📌 Minimum : *{min_w}F*")
            return
        kb = {"inline_keyboard": [
            [{"text": "📱 Mobile Money", "callback_data": "method_mobile"}],
            [{"text": "🏦 Virement Bancaire", "callback_data": "method_bank"}],
            [{"text": "❌ Annuler", "callback_data": "cancel_retrait"}]
        ]}
        send(uid, f"💸 *RETRAIT*\n\n💼 Solde : *{u['balance']}F*\nMinimum : *{min_w}F*\n\nChoisis ta méthode 👇", kb=kb)

    elif text == "🏆 Classement":
        users = db_get("users", {"is_registered": "eq.true"})
        ranked = sorted(users, key=lambda x: get_ref_count(x["user_id"]), reverse=True)[:10]
        medals = ["🥇","🥈","🥉","4️⃣","5️⃣","6️⃣","7️⃣","8️⃣","9️⃣","🔟"]
        t = "🏆 *TOP PARRAINEURS*\n━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        for i, uu in enumerate(ranked):
            t += f"{medals[i]} @{uu.get('username','Anonyme')} — *{get_ref_count(uu['user_id'])} filleuls*\n"
        if not ranked:
            t += "_Sois le premier !_ 🚀"
        send(uid, t)

    elif text == "❓ Aide":
        send(uid,
            f"❓ *AIDE XAFEARN*\n━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🎁 Bonus : *{get_cfg('bonus_daily')}F*/jour\n"
            f"👥 Parrainage : *{get_cfg('bonus_referral')}F*/ami\n"
            f"✅ Tâche : *{get_cfg('bonus_task')}F*/tâche\n"
            f"💸 Retrait min : *{get_cfg('min_withdrawal')}F*\n\n"
            f"📩 Support : @xafearn_support"
        )


def handle_retrait_step(uid, text, sess):
    step = sess.get("step")
    u = get_user(uid)

    if step == "amount":
        try:
            amount = int(text.strip())
        except:
            send(uid, "❌ Montant invalide (ex: 500)"); return
        min_w = get_cfg("min_withdrawal")
        if amount < min_w:
            send(uid, f"❌ Minimum : *{min_w}F*"); return
        if amount > u["balance"]:
            send(uid, f"❌ Solde insuffisant ! (*{u['balance']}F*)"); return
        sess["amount"] = amount
        sess["step"] = "number"
        set_session(uid, sess)
        send(uid, f"✅ Montant : *{amount}F*\n\n📱 Ton numéro de paiement :")

    elif step == "number":
        if len(text.strip()) < 8:
            send(uid, "❌ Numéro invalide."); return
        sess["number"] = text.strip()
        sess["step"] = "name"
        set_session(uid, sess)
        send(uid, "✅ Numéro enregistré.\n\n👤 Ton nom complet :")

    elif step == "name":
        if len(text.strip()) < 3:
            send(uid, "❌ Nom invalide."); return
        sess["name"] = text.strip()
        amount = sess["amount"]
        method = sess["method"]
        number = sess["number"]
        name   = sess["name"]

        # Débiter
        update_balance(uid, -amount)

        # Créer retrait
        r = db_post("withdrawals", {
            "user_id": uid, "amount": amount,
            "method": method, "number": number,
            "name": name, "status": "pending"
        })
        w_id = r[0]["id"] if r else "?"

        # Transaction
        db_post("transactions", {"user_id": uid, "type": "retrait", "amount": -amount, "description": f"Retrait #{w_id}"})

        # Masquer numéro
        masked = number[:4] + " *** ** ** " + number[-2:] if len(number) >= 6 else number
        label  = "📱 Mobile Money" if method == "mobile" else "🏦 Virement"

        # Envoyer dans canal retraits
        if RETRAIT_CHANNEL_ID and RETRAIT_CHANNEL_ID != "0":
            kb = {"inline_keyboard": [[
                {"text": "✅ Approuver", "callback_data": f"approve_{w_id}"},
                {"text": "❌ Rejeter",   "callback_data": f"reject_{w_id}"}
            ]]}
            tg("sendMessage",
                chat_id=int(RETRAIT_CHANNEL_ID),
                text=f"💸 *DEMANDE #{w_id}*\n━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                     f"💵 *{amount}F* · {label}\n"
                     f"📱 {masked}\n👤 {name}\n"
                     f"🆔 `{uid}` · @{get_user(uid).get('username','N/A')}",
                parse_mode="Markdown",
                reply_markup=kb
            )

        new_u = get_user(uid)
        send(uid,
            f"✅ *Demande envoyée !*\n━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"💵 *{amount}F* · {label}\n"
            f"📱 {masked}\n👤 {name}\n\n"
            f"💼 Solde restant : *{new_u['balance']}F*\n\n"
            f"⏳ _En cours de traitement..._"
        )
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
            send(uid, f"💰 Récompense en F (défaut: {get_cfg('bonus_task')}F) :")
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
            send(uid, f"✅ *Tâche ajoutée !*\n\n📝 {sess['description']}\n💰 *{reward}F*")
            clear_session(uid)

    elif action == "ban":
        t = text.strip()
        if t.startswith("debannir "):
            try:
                tid = int(t.replace("debannir ", ""))
                db_patch("users", {"user_id": f"eq.{tid}"}, {"is_banned": False})
                send(uid, f"✅ User `{tid}` débanni.")
                send(tid, "✅ *Ton compte a été réactivé.*")
            except:
                send(uid, "❌ ID invalide.")
        else:
            try:
                tid = int(t)
                db_patch("users", {"user_id": f"eq.{tid}"}, {"is_banned": True})
                send(uid, f"🚫 User `{tid}` banni.")
                send(tid, "🚫 *Compte suspendu.*")
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
        send(uid, f"✅ *Broadcast : {sent} envoyés.*")
        clear_session(uid)


def handle_cb(uid, data, mid, cid):
    from datetime import date

    if data == "check_join":
        u = get_user(uid)
        if not u:
            return
        if not check_membership(uid):
            channels_list = "\n".join([f"  ➤ {ch}" for ch in CHANNELS])
            edit(uid, mid,
                f"❌ *Tu n'as pas tout rejoint.*\n\n{channels_list}\n\n_Puis clique Vérifier_ 👇",
                kb={"inline_keyboard": [[{"text": "🔄 Vérifier à nouveau", "callback_data": "check_join"}]]}
            )
            return

        db_patch("users", {"user_id": f"eq.{uid}"}, {"is_registered": True})

        if u.get("referred_by") and not u.get("is_registered"):
            parrain = get_user(u["referred_by"])
            if parrain and parrain.get("is_registered") and not parrain.get("is_banned"):
                bonus_ref = get_cfg("bonus_referral")
                update_balance(u["referred_by"], bonus_ref)
                db_post("transactions", {"user_id": u["referred_by"], "type": "parrainage", "amount": bonus_ref, "description": f"Filleul @{u.get('username','?')}"})
                send(u["referred_by"], f"🎉 *+{bonus_ref}F* — Filleul *@{u.get('username','?')}* inscrit !")

        ref_link = f"https://t.me/{BOT_USERNAME}?start={uid}"
        edit(uid, mid, f"✅ *Compte activé !*\n━━━━━━━━━━━━━━━━━━━━━━━\n\n🔗 Ton lien :\n`{ref_link}`")
        send(uid, "🏠 *Menu Principal — XAFEARN*\n\n_Que veux-tu faire ?_ 👇", kb=main_kb())

    elif data.startswith("task_"):
        task_id = int(data.split("_")[1])
        done = db_get("user_tasks", {"user_id": f"eq.{uid}", "task_id": f"eq.{task_id}"})
        if done:
            tg("answerCallbackQuery", callback_query_id=str(mid), text="⚠️ Déjà complétée !", show_alert=True)
            return
        tasks = db_get("tasks", {"id": f"eq.{task_id}"})
        if tasks:
            task = tasks[0]
            db_post("user_tasks", {"user_id": uid, "task_id": task_id})
            update_balance(uid, task["reward"])
            db_post("transactions", {"user_id": uid, "type": "tâche", "amount": task["reward"], "description": task["description"][:50]})
            u = get_user(uid)
            send(uid, f"🎯 *Tâche validée !*\n\n💵 +{task['reward']}F ✅\n💼 Solde : *{u['balance']}F*")

    elif data.startswith("method_"):
        method = data.split("_")[1]
        label  = "📱 Mobile Money" if method == "mobile" else "🏦 Virement"
        set_session(uid, {"action": "retrait", "method": method, "step": "amount"})
        edit(uid, mid, f"💸 *{label}*\n\nCombien veux-tu retirer ? (en F) 👇")

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
                f"💰 *{w['amount']}F* · {label}\n"
                f"📱 {masked}\n👤 {w['name']}\n\n"
                f"🤖 Via @{BOT_USERNAME}\n➡️ _Rejoins et gagne toi aussi !_"
            )
            send(w["user_id"], f"✅ *Retrait approuvé !*\n\n💵 *{w['amount']}F* envoyé ! 🙏")
        else:
            db_patch("withdrawals", {"id": f"eq.{w_id}"}, {"status": "rejected"})
            update_balance(w["user_id"], w["amount"])
            db_post("transactions", {"user_id": w["user_id"], "type": "remboursement", "amount": w["amount"], "description": f"Retrait #{w_id} refusé"})
            edit(cid, mid, f"❌ *RETRAIT REJETÉ #{w_id}*")
            send(w["user_id"], f"❌ *Retrait refusé*\n\n💵 *{w['amount']}F* remboursé.\n📩 @xafearn_support")


application = app
handler = app
