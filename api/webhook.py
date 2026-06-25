import os, json, traceback, random, string
from flask import Flask, request, Response
import requests as req
from datetime import date, datetime, timedelta

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
    "https://t.me/+JlqLH_-LD4syZmY0",
    "https://t.me/xafearn_money",
    "https://t.me/xafearn_info"
]

AUTO_TASK_ID   = "auto_sniper"
AUTO_TASK_DESC = "S inscrire sur Sniper Business Center et activer ton compte"
AUTO_TASK_LINK = "https://www.sniperbuisnesscenter.com/signup?affiliationCode=abdoula"
AUTO_TASK_REW  = 500

# ════════════════════════════════════
# LIMITES SÉCURITÉ — invisibles users
# ════════════════════════════════════
MAX_RETRAIT_PAR_SEMAINE = 1
MAX_RETRAIT_PAR_JOUR    = 5000
DELAI_ENTRE_RETRAITS    = 7
BLACKLIST_NUMEROS       = []

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
    "Autre":             ["Virement Bancaire", "PayPal"],
    "💰 Crypto":         ["USDT TRC20", "USDT BEP20 (BSC)", "BNB BSC", "SOL (Solana)"]
}

H = {
    "apikey": SB_KEY,
    "Authorization": f"Bearer {SB_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation"
}

# ════════════════════════════════════
# HELPERS TELEGRAM
# ════════════════════════════════════
def tg(method, **kw):
    try:
        return req.post(f"{API}/{method}", json=kw, timeout=15).json()
    except:
        return {}

def send(uid, text, kb=None):
    d = {"chat_id": uid, "text": text}
    if kb: d["reply_markup"] = kb
    tg("sendMessage", **d)

def edit(uid, mid, text, kb=None):
    d = {"chat_id": uid, "message_id": mid, "text": text}
    if kb: d["reply_markup"] = kb
    tg("editMessageText", **d)

# ════════════════════════════════════
# CLAVIERS
# ════════════════════════════════════
def main_kb():
    return {"keyboard": [
        ["🎁 Bonus", "👥 Parrainage"],
        ["💰 Solde", "📋 Historique"],
        ["💸 Retrait", "✅ Taches"],
        ["🏆 Classement", "❓ Aide"],
        [{"text": "🚀 Ouvrir XAFEARN App", "web_app": {"url": "https://abdoula14cherif-xafearn.vercel.app/miniapp"}}]
    ], "resize_keyboard": True}

def admin_kb():
    return {"keyboard": [
        ["👥 Tous les Users", "📊 Statistiques"],
        ["⚙️ Prix", "➕ Ajouter Tache"],
        ["💸 Retraits", "🚫 Bannir"],
        ["💵 Ajouter Solde", "📢 Broadcast"],
        ["🗑️ Supprimer Tache", "⛔ Pause Retraits"],
        ["🔍 Verif Canaux", "📢 Rappel Bonus"],
        ["📋 Log Actions", "🔙 Mode User"]
    ], "resize_keyboard": True}

def pays_keyboard():
    pays_list = list(PAYS_METHODES.keys())
    buttons = []
    for i in range(0, len(pays_list), 2):
        row = [{"text": pays_list[i], "callback_data": "pays_" + str(i)}]
        if i+1 < len(pays_list):
            row.append({"text": pays_list[i+1], "callback_data": "pays_" + str(i+1)})
        buttons.append(row)
    buttons.append([{"text": "Annuler", "callback_data": "cancel_retrait"}])
    return {"inline_keyboard": buttons}

def methodes_keyboard(pays):
    methodes = PAYS_METHODES.get(pays, [])
    buttons = []
    for i, m in enumerate(methodes):
        buttons.append([{"text": m, "callback_data": "methode_" + str(i) + "_" + pays}])
    buttons.append([{"text": "Annuler", "callback_data": "cancel_retrait"}])
    return {"inline_keyboard": buttons}

# ════════════════════════════════════
# BASE DE DONNÉES
# ════════════════════════════════════
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

# ════════════════════════════════════
# HELPERS USERS
# ════════════════════════════════════
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
        try: return int(r[0]["value"])
        except: return 0
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

def mask_number(number):
    n = number.strip()
    if len(n) >= 6:
        return n[:4] + " *** ** ** " + n[-2:]
    return n

def is_crypto(pays, methode):
    return "Crypto" in str(pays) or str(methode) in ["USDT TRC20","USDT BEP20 (BSC)","BNB BSC","SOL (Solana)"]

# ════════════════════════════════════
# LOG ACTIONS ADMIN
# ════════════════════════════════════
def log_action(admin_id, action, detail=""):
    try:
        db_post("admin_logs", {
            "admin_id": admin_id,
            "action": action,
            "detail": str(detail)[:200],
            "created_at": datetime.now().isoformat()
        })
    except:
        pass

# ════════════════════════════════════
# SÉCURITÉ — Vérifications invisibles
# ════════════════════════════════════
def check_retrait_security(uid, amount, number):
    today = str(date.today())

    # 1. Retraits en pause
    pause = db_get("config", {"key": "eq.retraits_pauses"})
    if pause and pause[0].get("value") == "1":
        return False, "Les retraits sont temporairement suspendus.\nIls reprendront tres prochainement.\nMerci de ta patience."

    # 2. Numéro blacklisté
    if number:
        clean = number.strip().replace(" ","")
        for blocked in BLACKLIST_NUMEROS:
            if clean == blocked.replace(" ",""):
                return False, "Une verification est en cours sur ton compte.\nContacte le support : https://wa.me/699663183"

    # 3. Délai entre retraits approuvés
    last_ws = db_get("withdrawals", {
        "user_id": f"eq.{uid}",
        "status": "eq.approved",
        "order": "requested_at.desc",
        "limit": "1"
    })
    if last_ws:
        last_str = str(last_ws[0].get("requested_at",""))[:10]
        if last_str:
            try:
                last_date = datetime.strptime(last_str, "%Y-%m-%d")
                days_since = (datetime.now() - last_date).days
                if days_since < DELAI_ENTRE_RETRAITS:
                    remaining = DELAI_ENTRE_RETRAITS - days_since
                    return False, "Ton prochain retrait sera disponible dans " + str(remaining) + " jour(s).\nContinue a parrainer pour augmenter ton solde !"
            except:
                pass

    # 4. Limite semaine
    week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    week_ws  = db_get("withdrawals", {"user_id": f"eq.{uid}", "status": "eq.approved"})
    week_count = sum(1 for w in week_ws if str(w.get("requested_at",""))[:10] >= week_ago)
    if week_count >= MAX_RETRAIT_PAR_SEMAINE:
        return False, "Tu as atteint la limite de retraits pour cette semaine.\nReviens la semaine prochaine !"

    # 5. Limite montant jour
    if amount > 0:
        today_ws    = db_get("withdrawals", {"user_id": f"eq.{uid}", "status": "eq.approved"})
        today_total = sum(w.get("amount",0) for w in today_ws if str(w.get("requested_at",""))[:10] == today)
        if today_total + amount > MAX_RETRAIT_PAR_JOUR:
            remaining = MAX_RETRAIT_PAR_JOUR - today_total
            if remaining <= 0:
                return False, "Tu as atteint la limite de retrait journaliere.\nReviens demain !"
            return False, "Le montant depasse ta limite journaliere.\nTu peux retirer au maximum " + str(remaining) + "F aujourd hui."

    return True, None

# ════════════════════════════════════
# SÉCURITÉ — Détection multi-comptes
# ════════════════════════════════════
def check_multi_compte(uid, number):
    """Vérifie si le numéro est déjà utilisé par un autre user"""
    try:
        all_ws = db_get("withdrawals", {"number": f"eq.{number.strip()}"})
        for w in all_ws:
            if w.get("user_id") != uid:
                # Alerte silencieuse à l'admin
                for admin_id in ADMIN_IDS:
                    try:
                        send(admin_id,
                            "ALERTE MULTI-COMPTES\n\n"
                            "Le numero " + mask_number(number) + "\n"
                            "est utilise par plusieurs users :\n"
                            "User actuel : " + str(uid) + "\n"
                            "Autre user  : " + str(w.get("user_id","?")) + "\n\n"
                            "Verifiez manuellement.")
                    except:
                        pass
                log_action(0, "ALERTE_MULTI_COMPTE", "numero=" + number + " uid1=" + str(uid) + " uid2=" + str(w.get("user_id","")))
                return True
    except:
        pass
    return False

# ════════════════════════════════════
# SÉCURITÉ — Code de confirmation
# ════════════════════════════════════
def generate_code():
    return str(random.randint(1000, 9999))

# ════════════════════════════════════
# NOTIFICATIONS
# ════════════════════════════════════
def notif_rappel_bonus():
    """Envoie un rappel aux users qui n'ont pas récupéré leur bonus aujourd'hui"""
    today = str(date.today())
    users = db_get("users", {"is_registered": "eq.true", "is_banned": "eq.false"})
    sent  = 0
    for u in users:
        if str(u.get("last_bonus","")) != today:
            try:
                bonus = get_cfg("bonus_daily")
                tg("sendMessage",
                    chat_id=u["user_id"],
                    text="Rappel XAFEARN\n\n"
                         "Tu n as pas encore recupere ton bonus aujourd hui !\n\n"
                         "Clique sur Bonus dans le menu pour recevoir +"
                         + str(bonus) + "F maintenant !\n\n"
                         "Ne laisse pas ton argent dormir !")
                sent += 1
            except:
                pass
    return sent

def notif_palier(uid, balance):
    """Notifie l'user quand il atteint 50% du minimum"""
    min_w = get_cfg("min_withdrawal")
    mi    = min_w // 2
    if balance >= mi and (balance - 50) < mi:
        try:
            reste = min_w - balance
            send(uid,
                "Tu es a mi-chemin !\n\n"
                "Solde actuel : " + str(balance) + "F\n"
                "Plus que " + str(reste) + "F pour pouvoir retirer !\n\n"
                "Continue comme ca !")
        except:
            pass

def notif_bienvenue_1h(uid, uname):
    """Message de bienvenue personnalisé envoyé après inscription"""
    bonus    = get_cfg("bonus_daily")
    bonus_ref = get_cfg("bonus_referral")
    ref_link = "https://t.me/" + BOT_USERNAME + "?start=" + str(uid)
    try:
        send(uid,
            "Felicitations " + str(uname) + " !\n\n"
            "Ton compte XAFEARN est active.\n\n"
            "Voici comment maximiser tes gains :\n\n"
            "1. Recupere ton bonus de " + str(bonus) + "F chaque jour\n\n"
            "2. Partage ton lien de parrainage :\n"
            + ref_link + "\n"
            "Tu gagnes " + str(bonus_ref) + "F par ami inscrit !\n\n"
            "3. Complete les taches quotidiennes\n"
            "pour gagner encore plus !\n\n"
            "Bonne chance !")
    except:
        pass

# ════════════════════════════════════
# ROUTES
# ════════════════════════════════════
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
            uname = body["message"]["from"].get("username") or body["message"]["from"].get("first_name","User")
            text  = body["message"].get("text","")
            if text:
                handle_msg(uid, uname, text)
        elif "callback_query" in body:
            cq   = body["callback_query"]
            uid  = cq["from"]["id"]
            data = cq.get("data","")
            mid  = cq["message"]["message_id"]
            cid  = cq["message"]["chat"]["id"]
            tg("answerCallbackQuery", callback_query_id=cq["id"])
            handle_cb(uid, data, mid, cid)
    except Exception as e:
        print(f"ERROR: {traceback.format_exc()}")
        if uid:
            try: send(uid, "Erreur technique. Reessaie.")
            except: pass
    return Response('{"ok":true}', mimetype="application/json")


def handle_msg(uid, uname, text):
    sess = get_session(uid)

    if sess.get("action") == "retrait":
        handle_retrait_step(uid, text, sess); return
    if sess.get("action") in ["add_task","ban","broadcast","add_solde"] and uid in ADMIN_IDS:
        handle_admin_step(uid, text, sess); return

    # Vérification code de confirmation retrait
    if sess.get("action") == "confirm_code":
        if text.strip() == sess.get("code"):
            clear_session(uid)
            # Lancer le processus de retrait
            set_session(uid, {
                "action": "retrait",
                "step": "amount",
                "pays": sess.get("pays",""),
                "methode": sess.get("methode","")
            })
            u = get_user(uid)
            min_w = get_cfg("min_withdrawal")
            send(uid,
                "Code confirme !\n\n"
                "Solde : " + str(u["balance"]) + "F\n"
                "Minimum : " + str(min_w) + "F\n\n"
                "Combien veux-tu retirer ? (en F)")
        else:
            send(uid, "Code incorrect. Reessaie.\n\nEnvoie le code a 4 chiffres :")
        return

    if text.startswith("/start"):
        parts = text.split(" ")
        referred_by = None
        if len(parts) > 1:
            try:
                ref = int(parts[1])
                if ref != uid: referred_by = ref
            except: pass
        u = get_user(uid)
        if u and u.get("is_banned"):
            send(uid, "Compte suspendu."); return
        is_new = not u
        if not u:
            db_post("users", {
                "user_id": uid, "username": uname,
                "referred_by": referred_by, "balance": 0,
                "is_banned": False, "is_registered": False
            })
        msg  = "Bienvenue sur XAFEARN " + str(uname) + "!\n\n"
        msg += "Gagne de l argent chaque jour :\n"
        msg += "- Bonus journalier\n- Parrainage\n- Taches quotidiennes\n\n"
        msg += "Rejoins nos 3 canaux ci-dessous\npuis clique Verifier"
        req.post(f"{API}/sendMessage", json={
            "chat_id": uid, "text": msg,
            "reply_markup": {"inline_keyboard": [
                [{"text": "📢 Canal 1 — Rejoindre", "url": CHANNELS_DISPLAY[0]}],
                [{"text": "📢 Canal 2 — Rejoindre", "url": CHANNELS_DISPLAY[1]}],
                [{"text": "📢 Canal 3 — Rejoindre", "url": CHANNELS_DISPLAY[2]}],
                [{"text": "✅ J ai tout rejoint — Verifier", "callback_data": "check_join"}]
            ]}
        }, timeout=15)
        return

    u = get_user(uid)
    if not u:
        send(uid, "Utilise /start pour t inscrire."); return
    if u.get("is_banned"):
        send(uid, "Compte suspendu."); return

    today = str(date.today())

    # ══════════════════════════════
    # ADMIN
    # ══════════════════════════════
    if uid in ADMIN_IDS:
        if text in ["/admin", "📊 Statistiques"]:
            users = db_get("users")
            ws    = db_get("withdrawals")
            pause = db_get("config", {"key": "eq.retraits_pauses"})
            ps    = "OUI" if pause and pause[0].get("value") == "1" else "NON"
            send(uid,
                "PANEL ADMIN XAFEARN\n\n"
                "Total : " + str(len(users)) + "\n"
                "Actifs : " + str(sum(1 for x in users if x.get("is_registered"))) + "\n"
                "Bannis : " + str(sum(1 for x in users if x.get("is_banned"))) + "\n"
                "Soldes : " + str(sum(x.get("balance",0) for x in users)) + "F\n"
                "Payes : " + str(sum(x.get("amount",0) for x in ws if x.get("status")=="approved")) + "F\n"
                "En attente : " + str(sum(1 for x in ws if x.get("status")=="pending")) + "\n\n"
                "Retraits pauses : " + ps,
                kb=admin_kb())
            return

        if text == "⛔ Pause Retraits":
            pause = db_get("config", {"key": "eq.retraits_pauses"})
            curr  = pause[0].get("value","0") if pause else "0"
            if curr == "1":
                set_cfg("retraits_pauses","0")
                send(uid, "Retraits REACTIVES.")
                log_action(uid, "RETRAITS_REACTIVES")
            else:
                set_cfg("retraits_pauses","1")
                send(uid, "Retraits PAUSES. Personne ne peut retirer.")
                log_action(uid, "RETRAITS_PAUSES")
            return

        if text == "📋 Log Actions":
            logs = db_get("admin_logs", {"order": "created_at.desc", "limit": "15"})
            if not logs:
                send(uid, "Aucun log disponible.")
            else:
                t = "HISTORIQUE ACTIONS ADMIN\n\n"
                for l in logs:
                    d = str(l.get("created_at",""))[:16]
                    t += d + " — " + str(l.get("action","")) + "\n"
                    if l.get("detail"):
                        t += "  " + str(l.get("detail",""))[:50] + "\n"
                send(uid, t)
            return

        if text == "🔍 Verif Canaux":
            users = db_get("users", {"is_registered": "eq.true", "is_banned": "eq.false"})
            send(uid, "Verification en cours sur " + str(len(users[:30])) + " users...")
            not_in = []
            for uu in users[:30]:
                if not check_joined(uu["user_id"]):
                    not_in.append(uu)
                    # Désactiver le compte silencieusement
                    db_patch("users", {"user_id": f"eq.{uu['user_id']}"}, {"is_registered": False})
            if not not_in:
                send(uid, "Tous les users actifs sont dans les canaux.")
            else:
                t = "USERS HORS CANAL (" + str(len(not_in)) + ")\nComptes desactives automatiquement :\n\n"
                for uu in not_in:
                    t += "@" + str(uu.get("username","N/A")) + " - " + str(uu.get("balance",0)) + "F\n"
                send(uid, t)
                log_action(uid, "VERIF_CANAUX", "desactives=" + str(len(not_in)))
            return

        if text == "📢 Rappel Bonus":
            sent = notif_rappel_bonus()
            send(uid, "Rappel envoye a " + str(sent) + " utilisateurs.")
            log_action(uid, "RAPPEL_BONUS", "sent=" + str(sent))
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
                "/setbonus 25\n/setref 75\n/settask 35\n/setmin 2500"); return

        if text.startswith("/setbonus "):
            set_cfg("bonus_daily",text.split()[1]); log_action(uid,"SET_BONUS",text.split()[1]); send(uid,"Bonus -> "+text.split()[1]+"F"); return
        if text.startswith("/setref "):
            set_cfg("bonus_referral",text.split()[1]); log_action(uid,"SET_REF",text.split()[1]); send(uid,"Parrainage -> "+text.split()[1]+"F"); return
        if text.startswith("/settask "):
            set_cfg("bonus_task",text.split()[1]); log_action(uid,"SET_TASK",text.split()[1]); send(uid,"Tache -> "+text.split()[1]+"F"); return
        if text.startswith("/setmin "):
            set_cfg("min_withdrawal",text.split()[1]); log_action(uid,"SET_MIN",text.split()[1]); send(uid,"Min retrait -> "+text.split()[1]+"F"); return

        if text == "➕ Ajouter Tache":
            set_session(uid, {"action":"add_task","step":"description"})
            send(uid, "NOUVELLE TACHE\n\nDecris la tache :"); return

        if text == "🗑️ Supprimer Tache":
            tasks = db_get("tasks", {"date":f"eq.{today}","is_active":"eq.true"})
            if not tasks:
                send(uid, "Aucune tache a supprimer.")
            else:
                t = "Taches du jour :\n\n"
                buttons = []
                for task in tasks:
                    t += "#" + str(task["id"]) + " - " + str(task["description"])[:30] + "\n"
                    buttons.append([{"text":"Supprimer #"+str(task["id"])+" - "+str(task["description"])[:20],"callback_data":"del_task_"+str(task["id"])}])
                send(uid, t + "\nClique pour supprimer :", kb={"inline_keyboard": buttons})
            return

        if text == "💵 Ajouter Solde":
            set_session(uid, {"action":"add_solde","step":"user_id"})
            send(uid, "ID Telegram du user :"); return

        if text == "💸 Retraits":
            pending = db_get("withdrawals", {"status":"eq.pending"})
            if not pending:
                send(uid, "Aucune demande en attente.")
            else:
                t = "EN ATTENTE (" + str(len(pending)) + ")\n\n"
                for w in pending:
                    u2 = get_user(w["user_id"])
                    t += "#"+str(w["id"])+" - "+str(w["amount"])+"F\n"
                    t += "Methode : "+str(w.get("method",""))+"\n"
                    t += "Numero  : "+str(w.get("number",""))+"\n"
                    t += "Nom     : "+str(w.get("name",""))+"\n"
                    t += "User    : @"+str(u2.get("username","N/A") if u2 else "N/A")+"\n"
                    t += "---\n"
                send(uid, t); return

        if text == "🚫 Bannir":
            set_session(uid, {"action":"ban"})
            send(uid, "ID a bannir :\n123456789\nDebannir : debannir 123456789"); return

        if text == "📢 Broadcast":
            set_session(uid, {"action":"broadcast"})
            send(uid,
                "Ecris le message a envoyer a tous :\n\n"
                "Le message sera envoye avec un bouton\n"
                "[Publier mon annonce] qui ouvre la Mini App."); return

        if text == "🔙 Mode User":
            send(uid, "Mode Utilisateur", kb=main_kb()); return

    if not u.get("is_registered"):
        send(uid, "Rejoins nos canaux d abord.\nEnvoie /start"); return

    # ══════════════════════════════
    # UTILISATEUR
    # ══════════════════════════════
# ═══════════════════════════════════════
# PUBLICITÉ — lien sponsorisé
# ═══════════════════════════════════════
AD_URL = "https://omg10.com/4/11160450"

def show_ad_then(uid, action_cb_data, content_preview):
    """Affiche la pub. 1er clic = pub, 2e clic = contenu."""
    req.post(f"{API}/sendMessage", json={
        "chat_id": uid,
        "text":
            "📣 Message sponsorise\n\n"
            "Clique sur Voir l annonce\n"
            "puis reviens et clique Continuer\n\n"
            + content_preview,
        "reply_markup": {"inline_keyboard": [
            [{"text": "📣 Voir l annonce", "url": AD_URL}],
            [{"text": "✅ Continuer →",    "callback_data": action_cb_data}]
        ]}
    }, timeout=10)

def ad_seen_today(uid):
    """Retourne True si l'user a déjà vu une pub aujourd'hui."""
    today = str(date.today())
    u = get_user(uid)
    return str(u.get("last_ad_view","")) == today

def mark_ad_seen(uid):
    """Marque la pub comme vue aujourd'hui."""
    db_patch("users", {"user_id": f"eq.{uid}"}, {"last_ad_view": str(date.today())})

    if text == "🎁 Bonus":
        # Re-vérifier canal
        if not check_joined(uid):
            db_patch("users", {"user_id": f"eq.{uid}"}, {"is_registered": False})
            send(uid,
                "Tu as quitte nos canaux !\n\n"
                "Rejoins-les pour continuer a gagner :",
                kb={"inline_keyboard": [
                    [{"text": "📢 Canal 1 — Rejoindre", "url": CHANNELS_DISPLAY[0]}],
                    [{"text": "📢 Canal 2 — Rejoindre", "url": CHANNELS_DISPLAY[1]}],
                    [{"text": "📢 Canal 3 — Rejoindre", "url": CHANNELS_DISPLAY[2]}],
                    [{"text": "✅ J ai tout rejoint — Verifier", "callback_data": "check_join"}]
                ]})
            return
        bonus = get_cfg("bonus_daily")
        if str(u.get("last_bonus","")) == today:
            send(uid, "Bonus deja recupere !\n\nSolde : "+str(u["balance"])+"F\nReviens demain pour +"+str(bonus)+"F"); return
        # ── PUB 1er clic ──
        if not ad_seen_today(uid):
            mark_ad_seen(uid)
            show_ad_then(uid, "ad_bonus", "Tu recevras +" + str(bonus) + "F apres la pub !")
            return
        # ── Donner le bonus ──
        update_balance(uid, bonus)
        db_patch("users",{"user_id":f"eq.{uid}"},{"last_bonus":today})
        db_post("transactions",{"user_id":uid,"type":"bonus","amount":bonus,"description":"Bonus journalier"})
        new_u = get_user(uid)
        send(uid, "BONUS RECU !\n\n+"+str(bonus)+"F credite\nNouveau solde : "+str(new_u["balance"])+"F\n\nReviens demain !")
        notif_palier(uid, new_u["balance"])

    elif text == "💰 Solde":
        nb = get_ref_count(uid)
        ref_link = "https://t.me/"+BOT_USERNAME+"?start="+str(uid)
        min_w = get_cfg("min_withdrawal")
        reste = max(0, min_w - u["balance"])
        # ── PUB 1er clic ──
        if not ad_seen_today(uid):
            mark_ad_seen(uid)
            show_ad_then(uid, "ad_solde", "Ton solde : "+str(u["balance"])+"F")
            return
        send(uid,
            "TON COMPTE XAFEARN\n\n"
            "Solde : " + str(u["balance"]) + "F\n"
            "Filleuls : " + str(nb) + "\n"
            "Gains parrainage : " + str(nb*get_cfg("bonus_referral")) + "F\n\n"
            + ("Plus que " + str(reste) + "F pour retirer !\n\n" if reste > 0 else "Tu peux retirer maintenant !\n\n")
            + "Ton lien :\n" + ref_link)

    elif text == "👥 Parrainage":
        nb = get_ref_count(uid)
        bonus_ref = get_cfg("bonus_referral")
        ref_link = "https://t.me/"+BOT_USERNAME+"?start="+str(uid)
        send(uid,
            "TON LIEN D AFFILIATION\n\n"
            + ref_link + "\n\n"
            "Parrainages : " + str(nb) + "\n"
            "Gain/parrainage : " + str(bonus_ref) + "F\n"
            "Total gagne : " + str(nb*bonus_ref) + "F\n\n"
            "Partage et gagne " + str(bonus_ref) + "F a chaque inscription !")

    elif text == "📋 Historique":
        txs = db_get("transactions",{"user_id":f"eq.{uid}","order":"created_at.desc","limit":"10"})
        wds = db_get("withdrawals",{"user_id":f"eq.{uid}","order":"requested_at.desc","limit":"5"})
        t = "HISTORIQUE\n\nTransactions :\n"
        for tx in (txs or []):
            t += ("+" if tx["amount"]>0 else "")+str(tx["amount"])+"F - "+str(tx["description"])+"\n"
        if not txs: t += "Aucune.\n"
        t += "\nRetraits :\n"
        se = {"pending":"EN ATTENTE","approved":"PAYE","rejected":"REFUSE"}
        for w in (wds or []):
            t += se.get(w.get("status"),"?")+" "+str(w["amount"])+"F\n"
        if not wds: t += "Aucun.\n"
        send(uid, t)

    elif text == "💸 Retrait":
        min_w = get_cfg("min_withdrawal")
        if u["balance"] < min_w:
            reste = min_w - u["balance"]
            send(uid, "Solde insuffisant\n\nSolde : "+str(u["balance"])+"F\nMinimum : "+str(min_w)+"F\nIl te manque : "+str(reste)+"F"); return
        pending = db_get("withdrawals",{"user_id":f"eq.{uid}","status":"eq.pending"})
        if pending:
            send(uid, "Tu as deja une demande en attente de "+str(pending[0]["amount"])+"F"); return
        ok, msg = check_retrait_security(uid, 0, "")
        if not ok:
            send(uid, msg); return
        send(uid,
            "DEMANDE DE RETRAIT\n\n"
            "Solde : " + str(u["balance"]) + "F\n"
            "Minimum : " + str(min_w) + "F\n\n"
            "Choisis ton pays :",
            kb=pays_keyboard())

    elif text == "✅ Taches":
        # ── PUB 1er clic ──
        if not ad_seen_today(uid):
            mark_ad_seen(uid)
            show_ad_then(uid, "ad_tasks", "Vois les taches du jour et gagne des recompenses !")
            return
        tasks = db_get("tasks",{"date":f"eq.{today}","is_active":"eq.true"})
        auto_rows = db_get("user_tasks",{"user_id":f"eq.{uid}","task_id":f"eq.{AUTO_TASK_ID}"})
        auto_done = any(str(r.get("completed_at",""))[:10]==today for r in auto_rows)
        auto_pend = db_get("task_validations",{"user_id":f"eq.{uid}","task_id":f"eq.{AUTO_TASK_ID}","status":"eq.pending"})
        auto_pend_today = any(str(r.get("created_at",""))[:10]==today for r in auto_pend)

        msg_text = "TACHES DU JOUR\n\n================================\n\n"
        if auto_done:
            msg_text += "OK " + AUTO_TASK_DESC + "\nRecompense : "+str(AUTO_TASK_REW)+"F - VALIDEE\n\n"
        elif auto_pend_today:
            msg_text += "EN ATTENTE " + AUTO_TASK_DESC + "\nRecompense : "+str(AUTO_TASK_REW)+"F - En verification\n\n"
        else:
            msg_text += "-- " + AUTO_TASK_DESC + "\nLien : " + AUTO_TASK_LINK + "\nRecompense : "+str(AUTO_TASK_REW)+"F\nGagne jusqu a 10 000F par jour !\n\n"

        msg_text += "================================\n\n"
        buttons = []
        if not auto_done and not auto_pend_today:
            buttons.append([{"text":"Valider : S inscrire Sniper Business","callback_data":"auto_task_"+AUTO_TASK_ID}])
        for t in tasks:
            done = len(db_get("user_tasks",{"user_id":f"eq.{uid}","task_id":f"eq.{t['id']}"})) > 0
            msg_text += ("OK " if done else "-- ")+str(t["description"])+"\n"
            if t.get("link"): msg_text += "Lien : "+str(t["link"])+"\n"
            msg_text += "Recompense : "+str(t["reward"])+"F\n\n"
            if not done:
                buttons.append([{"text":"Valider : "+str(t["description"])[:30],"callback_data":"task_"+str(t["id"])}])
        if auto_done and not tasks:
            msg_text += "Toutes les taches completees ! Reviens demain."
        send(uid, msg_text, kb={"inline_keyboard":buttons} if buttons else None)

    elif text == "🏆 Classement":
        users = db_get("users",{"is_registered":"eq.true"})
        ranked = sorted(users, key=lambda x: get_ref_count(x["user_id"]), reverse=True)[:10]
        t = "TOP PARRAINEURS XAFEARN\n\n"
        for i, uu in enumerate(ranked):
            t += str(i+1)+". @"+str(uu.get("username","Anonyme"))+" - "+str(get_ref_count(uu["user_id"]))+" filleuls\n"
        if not ranked: t += "Sois le premier !"
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
    step    = sess.get("step")
    u       = get_user(uid)
    min_w   = get_cfg("min_withdrawal")
    pays    = sess.get("pays","")
    methode = sess.get("methode","")
    crypto  = is_crypto(pays, methode)

    if step == "amount":
        try:
            amount = int(text.strip().replace("f","").replace("F","").replace(" ",""))
        except:
            send(uid, "Montant invalide. Envoie un chiffre ex: 2500"); return
        if amount < min_w:
            send(uid, "Minimum : "+str(min_w)+"F"); return
        if amount > u["balance"]:
            send(uid, "Solde insuffisant. Ton solde : "+str(u["balance"])+"F"); return
        ok, msg = check_retrait_security(uid, amount, "")
        if not ok:
            send(uid, msg); clear_session(uid); return
        sess["amount"] = amount; sess["step"] = "number"
        set_session(uid, sess)
        if crypto:
            send(uid, "Montant : "+str(amount)+"F\nReseau  : "+methode+"\n\nEnvoie ton adresse wallet :")
        else:
            send(uid, "Montant : "+str(amount)+"F\nPays : "+pays+"\nMethode : "+methode+"\n\nEnvoie ton numero de paiement :")

    elif step == "number":
        min_len = 26 if crypto else 8
        if len(text.strip()) < min_len:
            if crypto:
                send(uid, "Adresse wallet invalide.\nMin 26 caracteres.")
            else:
                send(uid, "Numero invalide. Reessaie.")
            return
        number = text.strip()

        # Vérification blacklist
        ok, msg = check_retrait_security(uid, sess.get("amount",0), number)
        if not ok:
            send(uid, msg); clear_session(uid); return

        # Détection multi-comptes (silencieuse)
        check_multi_compte(uid, number)

        sess["number"] = number; sess["step"] = "name"
        set_session(uid, sess)
        if crypto:
            send(uid, "Adresse enregistree.\n\nEnvoie ton nom ou pseudo :")
        else:
            send(uid, "Numero enregistre.\n\nEnvoie ton nom complet :")

    elif step == "name":
        if len(text.strip()) < 3:
            send(uid, "Nom invalide. Reessaie."); return
        sess["name"] = text.strip()

        # Générer code de confirmation
        code = generate_code()
        sess["step"]   = "code"
        sess["code"]   = code
        set_session(uid, sess)
        send(uid,
            "Presque fini !\n\n"
            "Pour securiser ton retrait, entre le code suivant :\n\n"
            "CODE : " + code + "\n\n"
            "Saisis ce code pour confirmer :")

    elif step == "code":
        if text.strip() != sess.get("code",""):
            send(uid, "Code incorrect. Reessaie.\n\nCode : " + sess.get("code","")); return

        amount  = sess["amount"]
        number  = sess["number"]
        name    = sess["name"]
        masked  = number if crypto else mask_number(number)

        update_balance(uid, -amount)
        r = db_post("withdrawals", {
            "user_id": uid, "amount": amount,
            "method": pays + " - " + methode,
            "number": number, "name": name,
            "status": "pending"
        })
        w_id = r[0]["id"] if r else "?"
        db_post("transactions",{"user_id":uid,"type":"retrait","amount":-amount,"description":"Retrait #"+str(w_id)})

        # Message canal admin
        if RETRAIT_CHANNEL_ID and RETRAIT_CHANNEL_ID != "0":
            try:
                canal_lbl = "Adresse wallet" if crypto else "Numero"
                tg("sendMessage",
                    chat_id=int(RETRAIT_CHANNEL_ID),
                    text="EN ATTENTE - RETRAIT #"+str(w_id)+"\n================================\n\n"
                         "Montant  : "+str(amount)+"F\n"
                         "Methode  : "+pays+" - "+methode+"\n"
                         +canal_lbl+" : "+number+"\n"
                         "Nom      : "+name+"\n\n"
                         "User     : @"+str(u.get("username","N/A"))+"\n"
                         "ID       : "+str(uid)+"\n"
                         "================================",
                    reply_markup={"inline_keyboard":[[
                        {"text":"✅ Approuver","callback_data":"approve_"+str(w_id)},
                        {"text":"❌ Rejeter","callback_data":"reject_"+str(w_id)}
                    ]]})
            except: pass

        new_u = get_user(uid)
        lbl2  = "Adresse" if crypto else "Numero"
        send(uid,
            "Demande confirmee !\n================================\n\n"
            "Montant  : "+str(amount)+"F\n"
            "Methode  : "+methode+"\n"
            +lbl2+"  : "+masked+"\n"
            "Nom      : "+name+"\n\n"
            "Solde restant : "+str(new_u["balance"])+"F\n\n"
            "En cours de traitement...\nTu seras notifie des que c est traite.")
        clear_session(uid)


def handle_admin_step(uid, text, sess):
    action = sess.get("action")

    if action == "add_task":
        step = sess.get("step")
        if step == "description":
            sess["description"] = text; sess["step"] = "link"
            set_session(uid, sess); send(uid, "Lien (ou - si aucun) :")
        elif step == "link":
            sess["link"] = None if text.strip()=="-" else text.strip()
            sess["step"] = "reward"; set_session(uid, sess)
            send(uid, "Recompense en F (defaut : "+str(get_cfg("bonus_task"))+"F) :")
        elif step == "reward":
            try: reward = int(text.strip())
            except: reward = get_cfg("bonus_task")
            db_post("tasks",{"description":sess["description"],"link":sess.get("link"),"reward":reward,"date":str(date.today()),"is_active":True})
            log_action(uid,"ADD_TASK",sess["description"][:50])
            send(uid,"Tache ajoutee !\n\n"+str(sess["description"])+"\nRecompense : "+str(reward)+"F")
            clear_session(uid)

    elif action == "add_solde":
        step = sess.get("step")
        if step == "user_id":
            try:
                target_id = int(text.strip())
                u = get_user(target_id)
                if not u:
                    send(uid,"User introuvable."); clear_session(uid); return
                sess["target_id"] = target_id; sess["step"] = "amount"
                set_session(uid, sess)
                send(uid,"User : @"+str(u.get("username","N/A"))+"\nSolde : "+str(u["balance"])+"F\n\nCombien ajouter ?")
            except:
                send(uid,"ID invalide."); clear_session(uid)
        elif step == "amount":
            try:
                amount = int(text.strip().replace("f","").replace("F","").replace(" ",""))
                target_id = sess["target_id"]
                update_balance(target_id, amount)
                db_post("transactions",{"user_id":target_id,"type":"credit_admin","amount":amount,"description":"Credit admin"})
                new_u = get_user(target_id)
                log_action(uid,"ADD_SOLDE","target="+str(target_id)+" amount="+str(amount))
                send(uid,"+"+str(amount)+"F credite a @"+str(new_u.get("username","N/A"))+"\nNouveau solde : "+str(new_u["balance"])+"F")
                try: send(target_id,"+"+str(amount)+"F credite sur ton compte !\nNouveau solde : "+str(new_u["balance"])+"F\n\nL equipe XAFEARN")
                except: pass
                clear_session(uid)
            except:
                send(uid,"Montant invalide."); clear_session(uid)

    elif action == "ban":
        t = text.strip()
        if t.startswith("debannir "):
            try:
                tid = int(t.replace("debannir ",""))
                db_patch("users",{"user_id":f"eq.{tid}"},{"is_banned":False})
                log_action(uid,"DEBANNIR","user_id="+str(tid))
                send(uid,"User "+str(tid)+" debanni.")
                send(tid,"Ton compte a ete reactive.")
            except: send(uid,"ID invalide.")
        else:
            try:
                tid = int(t)
                db_patch("users",{"user_id":f"eq.{tid}"},{"is_banned":True})
                log_action(uid,"BANNIR","user_id="+str(tid))
                send(uid,"User "+str(tid)+" banni.")
                send(tid,"Ton compte a ete suspendu.")
            except: send(uid,"ID invalide.")
        clear_session(uid)

    elif action == "broadcast":
        users = db_get("users", {"is_registered": "eq.true"})
        sent  = 0
        MINIAPP_URL = "https://abdoula14cherif-xafearn.vercel.app/miniapp"
        kb = {"inline_keyboard": [[
            {"text": "📢 Publier mon annonce", "web_app": {"url": MINIAPP_URL}}
        ]]}
        for uu in users:
            if not uu.get("is_banned"):
                try:
                    req.post(f"{API}/sendMessage", json={
                        "chat_id":      uu["user_id"],
                        "text":         "Message XAFEARN\n\n" + text,
                        "reply_markup": kb
                    }, timeout=10)
                    sent += 1
                except:
                    pass
        log_action(uid, "BROADCAST", "sent="+str(sent)+" msg="+text[:50])
        send(uid, "Broadcast envoye a " + str(sent) + " utilisateurs.\nBouton [Publier mon annonce] inclus.")
        clear_session(uid)


def handle_cb(uid, data, mid, cid):
    today = str(date.today())

    # ── CALLBACKS PUBLICITÉ ──────────────────────────────
    if data == "ad_bonus":
        u = get_user(uid)
        if not u or u.get("is_banned"): return
        bonus = get_cfg("bonus_daily")
        if str(u.get("last_bonus","")) == today:
            edit(uid, mid, "Bonus deja recupere aujourd hui !\nReviens demain pour +"+str(bonus)+"F"); return
        update_balance(uid, bonus)
        db_patch("users",{"user_id":f"eq.{uid}"},{"last_bonus":today})
        db_post("transactions",{"user_id":uid,"type":"bonus","amount":bonus,"description":"Bonus journalier"})
        new_u = get_user(uid)
        edit(uid, mid,
            "BONUS RECU !\n\n"
            "+"+str(bonus)+"F credite\n"
            "Nouveau solde : "+str(new_u["balance"])+"F\n\n"
            "Reviens demain !")
        notif_palier(uid, new_u["balance"])
        return

    if data == "ad_solde":
        u = get_user(uid)
        if not u or u.get("is_banned"): return
        nb = get_ref_count(uid)
        ref_link = "https://t.me/"+BOT_USERNAME+"?start="+str(uid)
        min_w = get_cfg("min_withdrawal")
        reste = max(0, min_w - u["balance"])
        edit(uid, mid,
            "TON COMPTE XAFEARN\n\n"
            "Solde : " + str(u["balance"]) + "F\n"
            "Filleuls : " + str(nb) + "\n"
            "Gains parrainage : " + str(nb*get_cfg("bonus_referral")) + "F\n\n"
            + ("Plus que " + str(reste) + "F pour retirer !\n\n" if reste > 0 else "Tu peux retirer maintenant !\n\n")
            + "Ton lien :\n" + ref_link)
        return

    if data == "ad_tasks":
        u = get_user(uid)
        if not u or u.get("is_banned"): return
        tasks = db_get("tasks",{"date":f"eq.{today}","is_active":"eq.true"})
        auto_rows = db_get("user_tasks",{"user_id":f"eq.{uid}","task_id":f"eq.{AUTO_TASK_ID}"})
        auto_done = any(str(r.get("completed_at",""))[:10]==today for r in auto_rows)
        auto_pend = db_get("task_validations",{"user_id":f"eq.{uid}","task_id":f"eq.{AUTO_TASK_ID}","status":"eq.pending"})
        auto_pend_today = any(str(r.get("created_at",""))[:10]==today for r in auto_pend)
        msg_text = "TACHES DU JOUR\n\n================================\n\n"
        if auto_done:
            msg_text += "OK "+AUTO_TASK_DESC+"\nRecompense : "+str(AUTO_TASK_REW)+"F - VALIDEE\n\n"
        elif auto_pend_today:
            msg_text += "EN ATTENTE "+AUTO_TASK_DESC+"\nRecompense : "+str(AUTO_TASK_REW)+"F - En verification\n\n"
        else:
            msg_text += "-- "+AUTO_TASK_DESC+"\nLien : "+AUTO_TASK_LINK+"\nRecompense : "+str(AUTO_TASK_REW)+"F\n\n"
        msg_text += "================================\n\n"
        buttons = []
        if not auto_done and not auto_pend_today:
            buttons.append([{"text":"Valider : S inscrire Sniper Business","callback_data":"auto_task_"+AUTO_TASK_ID}])
        for t in (tasks or []):
            done = len(db_get("user_tasks",{"user_id":f"eq.{uid}","task_id":f"eq.{t['id']}"})) > 0
            msg_text += ("OK " if done else "-- ")+str(t["description"])+"\n"
            if t.get("link"): msg_text += "Lien : "+str(t["link"])+"\n"
            msg_text += "Recompense : "+str(t["reward"])+"F\n\n"
            if not done:
                buttons.append([{"text":"Valider : "+str(t["description"])[:30],"callback_data":"task_"+str(t["id"])}])
        edit(uid, mid, msg_text, kb={"inline_keyboard":buttons} if buttons else None)
        return

    if data.startswith("pays_"):
        idx = int(data.split("_")[1])
        pays_list = list(PAYS_METHODES.keys())
        if idx >= len(pays_list): return
        pays = pays_list[idx]
        set_session(uid,{"action":"retrait","step":"methode","pays":pays})
        edit(uid,mid,"Pays : "+pays+"\n\nChoisis ta methode :",kb=methodes_keyboard(pays))
        return

    if data.startswith("methode_"):
        parts = data.split("_",2)
        idx = int(parts[1]); pays = parts[2]
        methodes = PAYS_METHODES.get(pays,[])
        if idx >= len(methodes): return
        methode = methodes[idx]
        u = get_user(uid); min_w = get_cfg("min_withdrawal")
        set_session(uid,{"action":"retrait","step":"amount","pays":pays,"methode":methode})
        edit(uid,mid,"Pays    : "+pays+"\nMethode : "+methode+"\n\nSolde : "+str(u["balance"])+"F\nMinimum : "+str(min_w)+"F\n\nCombien veux-tu retirer ? (en F)")
        return

    if data == "check_join":
        u = get_user(uid)
        if not u: return
        if not check_joined(uid):
            edit(uid, mid,
                "Tu n as pas encore tout rejoint.\n\n"
                "Rejoins les 3 canaux puis clique Verifier :",
                kb={"inline_keyboard": [
                    [{"text": "📢 Canal 1 — Rejoindre", "url": CHANNELS_DISPLAY[0]}],
                    [{"text": "📢 Canal 2 — Rejoindre", "url": CHANNELS_DISPLAY[1]}],
                    [{"text": "📢 Canal 3 — Rejoindre", "url": CHANNELS_DISPLAY[2]}],
                    [{"text": "🔄 Verifier a nouveau", "callback_data": "check_join"}]
                ]})
            return
        db_patch("users",{"user_id":f"eq.{uid}"},{"is_registered":True})
        if u.get("referred_by") and not u.get("is_registered"):
            parrain = get_user(u["referred_by"])
            if parrain and parrain.get("is_registered") and not parrain.get("is_banned"):
                bonus_ref = get_cfg("bonus_referral")
                update_balance(u["referred_by"], bonus_ref)
                db_post("transactions",{"user_id":u["referred_by"],"type":"parrainage","amount":bonus_ref,"description":"Filleul @"+str(u.get("username","?"))})
                try: send(u["referred_by"],"+ "+str(bonus_ref)+"F credite !\nFilleul @"+str(u.get("username","?"))+" inscrit !")
                except: pass
        ref_link = "https://t.me/"+BOT_USERNAME+"?start="+str(uid)
        edit(uid,mid,"Compte active !\n\nTon lien de parrainage :\n"+ref_link)
        send(uid,"Menu Principal XAFEARN\n\nQue veux-tu faire ?",kb=main_kb())
        # Message de bienvenue 1h après
        notif_bienvenue_1h(uid, u.get("username",""))

    elif data.startswith("auto_task_"):
        u = get_user(uid)
        done_rows = db_get("user_tasks",{"user_id":f"eq.{uid}","task_id":f"eq.{AUTO_TASK_ID}"})
        done_today = any(str(r.get("completed_at",""))[:10]==today for r in done_rows)
        if done_today:
            tg("answerCallbackQuery",callback_query_id=str(mid),text="Tache deja completee !",show_alert=True); return
        pend_rows = db_get("task_validations",{"user_id":f"eq.{uid}","task_id":f"eq.{AUTO_TASK_ID}","status":"eq.pending"})
        pend_today = any(str(r.get("created_at",""))[:10]==today for r in pend_rows)
        if pend_today:
            tg("answerCallbackQuery",callback_query_id=str(mid),text="Demande deja envoyee ! Attends.",show_alert=True); return
        r = db_post("task_validations",{"user_id":uid,"task_id":AUTO_TASK_ID,"status":"pending"})
        val_id = r[0]["id"] if r else "?"
        for admin_id in ADMIN_IDS:
            try:
                tg("sendMessage",chat_id=admin_id,
                   text="VALIDATION TACHE SNIPER #"+str(val_id)+"\n================================\n\n"
                        "User  : @"+str(u.get("username","N/A"))+"\n"
                        "ID    : "+str(uid)+"\n"
                        "Gain  : "+str(AUTO_TASK_REW)+"F\n\n"
                        "Lien a verifier :\n"+AUTO_TASK_LINK,
                   reply_markup={"inline_keyboard":[[
                       {"text":"✅ Valider "+str(AUTO_TASK_REW)+"F","callback_data":"val_ok_"+str(val_id)+"_"+str(uid)},
                       {"text":"❌ Rejeter","callback_data":"val_no_"+str(val_id)+"_"+str(uid)}
                   ]]})
            except: pass
        edit(uid,mid,
            "Demande envoyee !\n\n"
            "Ton inscription est en cours de verification.\n"
            "Tu recevras "+str(AUTO_TASK_REW)+"F des validation.\n\n"
            "Assure-toi d avoir :\n1. Cree ton compte\n2. Active ton compte\n3. Recu ta 1ere commande\n\n"
            "Lien : "+AUTO_TASK_LINK)

    elif data.startswith("val_ok_") or data.startswith("val_no_"):
        if uid not in ADMIN_IDS:
            tg("answerCallbackQuery",callback_query_id=str(mid),text="Action reservee a l admin.",show_alert=True); return
        parts = data.split("_"); decision = parts[1]; val_id = int(parts[2]); target = int(parts[3])
        val_rows = db_get("task_validations",{"id":f"eq.{val_id}"})
        if not val_rows or val_rows[0].get("status") != "pending":
            edit(uid,mid,"Deja traite."); return
        if decision == "ok":
            db_patch("task_validations",{"id":f"eq.{val_id}"},{"status":"approved"})
            db_post("user_tasks",{"user_id":target,"task_id":AUTO_TASK_ID})
            update_balance(target, AUTO_TASK_REW)
            db_post("transactions",{"user_id":target,"type":"tache","amount":AUTO_TASK_REW,"description":"Tache Sniper validee"})
            log_action(uid,"VALIDER_TACHE_SNIPER","val_id="+str(val_id)+" target="+str(target))
            new_u = get_user(target)
            edit(uid,mid,"VALIDEE #"+str(val_id)+" — +"+str(AUTO_TASK_REW)+"F a @"+str(new_u.get("username","N/A") if new_u else "N/A"))
            try: send(target,"Tache validee !\n\n+"+str(AUTO_TASK_REW)+"F credite !\nNouveau solde : "+str(new_u["balance"] if new_u else "?")+"F\n\n"+AUTO_TASK_LINK)
            except: pass
        else:
            db_patch("task_validations",{"id":f"eq.{val_id}"},{"status":"rejected"})
            log_action(uid,"REJETER_TACHE_SNIPER","val_id="+str(val_id)+" target="+str(target))
            edit(uid,mid,"REJETEE #"+str(val_id))
            try: send(target,"Tache non validee.\n\nAssure-toi de t inscrire et d activer ton compte.\nLien : "+AUTO_TASK_LINK+"\n\nSupport : https://wa.me/699663183")
            except: pass

    elif data.startswith("del_task_"):
        if uid not in ADMIN_IDS: return
        task_id = int(data.split("_")[2])
        db_patch("tasks",{"id":f"eq.{task_id}"},{"is_active":False})
        log_action(uid,"DEL_TASK","task_id="+str(task_id))
        edit(uid,mid,"Tache #"+str(task_id)+" supprimee !")

    elif data.startswith("task_"):
        task_id = int(data.split("_")[1])
        if db_get("user_tasks",{"user_id":f"eq.{uid}","task_id":f"eq.{task_id}"}):
            tg("answerCallbackQuery",callback_query_id=str(mid),text="Deja completee !",show_alert=True); return
        tasks = db_get("tasks",{"id":f"eq.{task_id}"})
        if tasks:
            task = tasks[0]
            db_post("user_tasks",{"user_id":uid,"task_id":task_id})
            update_balance(uid,task["reward"])
            db_post("transactions",{"user_id":uid,"type":"tache","amount":task["reward"],"description":str(task["description"])[:50]})
            u = get_user(uid)
            send(uid,"Tache validee !\n\n+"+str(task["reward"])+"F credite\nNouveau solde : "+str(u["balance"])+"F")
            notif_palier(uid, u["balance"])

    elif data == "cancel_retrait":
        clear_session(uid); edit(uid,mid,"Retrait annule.")

    elif data.startswith("approve_") or data.startswith("reject_"):
        if uid not in ADMIN_IDS:
            tg("answerCallbackQuery",callback_query_id=str(mid),text="Action reservee a l admin.",show_alert=True); return
        parts = data.split("_"); decision = parts[0]; w_id = int(parts[1])
        ws = db_get("withdrawals",{"id":f"eq.{w_id}"})
        if not ws:
            edit(uid,mid,"Retrait introuvable."); return
        if ws[0].get("status") != "pending":
            edit(uid,mid,"Ce retrait a deja ete traite."); return
        w = ws[0]
        method_full = w.get("method","")
        masked = mask_number(w["number"])
        if decision == "approve":
            db_patch("withdrawals",{"id":f"eq.{w_id}"},{"status":"approved"})
            log_action(uid,"APPROVE_RETRAIT","w_id="+str(w_id)+" amount="+str(w["amount"]))
            edit(cid,mid,
                "PAIEMENT EFFECTUE\n================================\n\n"
                "Montant : "+str(w["amount"])+"F\n"
                "Methode : "+method_full+"\n"
                "Numero  : "+w["number"]+"\n"
                "Nom     : "+str(w["name"])+"\n\n"
                "Via @"+BOT_USERNAME+"\nRejoins et gagne toi aussi !")
            try: send(w["user_id"],"Retrait approuve !\n\n"+str(w["amount"])+"F envoye.\nMerci de ta confiance !")
            except: pass
        else:
            db_patch("withdrawals",{"id":f"eq.{w_id}"},{"status":"rejected"})
            update_balance(w["user_id"],w["amount"])
            db_post("transactions",{"user_id":w["user_id"],"type":"remboursement","amount":w["amount"],"description":"Retrait #"+str(w_id)+" refuse"})
            log_action(uid,"REJECT_RETRAIT","w_id="+str(w_id)+" amount="+str(w["amount"]))
            edit(cid,mid,"RETRAIT REJETE #"+str(w_id))
            try: send(w["user_id"],"Retrait refuse.\n\n+"+str(w["amount"])+"F rembourse.\nContacte le support : https://wa.me/699663183")
            except: pass

application = app
handler = app
