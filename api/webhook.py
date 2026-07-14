import os, json, traceback
from flask import Flask, request, Response
import requests as req

app = Flask(__name__)

TOKEN  = os.environ.get("BOT_TOKEN", "")
SB_URL = os.environ.get("SUPABASE_URL", "")
SB_KEY = os.environ.get("SUPABASE_KEY", "")
API    = f"https://api.telegram.org/bot{TOKEN}"
DB     = f"{SB_URL}/rest/v1"
ADMIN_IDS = [int(x.strip()) for x in os.environ.get("ADMIN_IDS", "").split(",") if x.strip().isdigit()]
BOT_USERNAME = "xafearn_bot"

# ── URLS ──────────────────────────────────────────────────
GAME_URL = os.environ.get("GAME_URL", "https://abdoula14cherif-xafearn.vercel.app/miniapp")

CHANNELS_CHECK   = ["@xafearn_money"]
CHANNELS_DISPLAY = [
    "https://t.me/+JlqLH_-LD4syZmY0",
    "https://t.me/xafearn_money",
    "https://t.me/xafearn_info"
]

H = {
    "apikey": SB_KEY,
    "Authorization": f"Bearer {SB_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation"
}

def tg(method, **kw):
    try: return req.post(f"{API}/{method}", json=kw, timeout=15).json()
    except: return {}

def send(uid, text, kb=None):
    d = {"chat_id": uid, "text": text}
    if kb: d["reply_markup"] = kb
    tg("sendMessage", **d)

def db_get(table, f={}):
    try:
        r = req.get(f"{DB}/{table}", headers=H, params=f, timeout=15)
        data = r.json()
        return data if isinstance(data, list) else []
    except: return []

def db_post(table, data):
    try:
        r = req.post(f"{DB}/{table}", headers=H, json=data, timeout=15)
        result = r.json()
        return result if isinstance(result, list) else []
    except: return []

def db_patch(table, f, data):
    try: req.patch(f"{DB}/{table}", headers=H, params=f, json=data, timeout=15)
    except: pass

def get_user(uid):
    r = db_get("bot_users", {"user_id": f"eq.{uid}"})
    return r[0] if r else None

def check_joined(uid):
    for ch in CHANNELS_CHECK:
        try:
            r = tg("getChatMember", chat_id=ch, user_id=uid)
            if r.get("result", {}).get("status") in ["left", "kicked"]:
                return False
        except: return False
    return True

# ── MENU (4 boutons) ─────────────────────────────────────
def main_kb():
    return {"keyboard": [
        [{"text": "\U0001f680 Jouer maintenant", "web_app": {"url": GAME_URL}}],
        ["\U0001f4e2 Nos Canaux", "\U0001f465 Parrainage"],
        ["\U00002753 Aide"]
    ], "resize_keyboard": True}

def join_kb():
    return {"inline_keyboard": [
        [{"text": "Canal 1 - Rejoindre", "url": CHANNELS_DISPLAY[0]}],
        [{"text": "Canal 2 - Rejoindre", "url": CHANNELS_DISPLAY[1]}],
        [{"text": "Canal 3 - Rejoindre", "url": CHANNELS_DISPLAY[2]}],
        [{"text": "J ai tout rejoint - Verifier", "callback_data": "check_join"}]
    ]}

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
            if text: handle_msg(uid, uname, text)
        elif "callback_query" in body:
            cq   = body["callback_query"]
            uid  = cq["from"]["id"]
            data = cq.get("data", "")
            mid  = cq["message"]["message_id"]
            tg("answerCallbackQuery", callback_query_id=cq["id"])
            handle_cb(uid, data, mid)
    except Exception:
        print(f"ERROR: {traceback.format_exc()}")
        if uid:
            try: send(uid, "Erreur technique. Reessaie.")
            except: pass
    return Response('{"ok":true}', mimetype="application/json")

def handle_msg(uid, uname, text):
    if text.startswith("/start"):
        parts = text.split(" ")
        referred_by = None
        if len(parts) > 1:
            try:
                ref = int(parts[1])
                if ref != uid: referred_by = ref
            except: pass
        u = get_user(uid)
        if u and u.get("is_banned"): send(uid, "Compte suspendu."); return
        if not u:
            db_post("bot_users", {"user_id": uid, "username": uname, "referred_by": referred_by, "is_banned": False, "is_registered": False})
        send(uid,
            "Bienvenue sur XAFEARN " + str(uname) + " !\n\n"
            "Rejoins nos 3 canaux puis clique Verifier pour acceder au jeu.",
            kb=join_kb())
        return

    u = get_user(uid)
    if not u:
        send(uid, "Utilise /start pour commencer."); return
    if u.get("is_banned"):
        send(uid, "Compte suspendu."); return

    # ── ADMIN (cache, pas dans les boutons) ──────────────
    if uid in ADMIN_IDS:
        if text == "/admin":
            users = db_get("bot_users")
            send(uid, "STATS\n\nTotal : " + str(len(users)) +
                 "\nBannis : " + str(sum(1 for x in users if x.get("is_banned"))))
            return
        if text.startswith("/ban "):
            try:
                tid = int(text.split()[1])
                db_patch("bot_users", {"user_id": f"eq.{tid}"}, {"is_banned": True})
                send(uid, "User " + str(tid) + " banni.")
            except: send(uid, "ID invalide.")
            return
        if text.startswith("/unban "):
            try:
                tid = int(text.split()[1])
                db_patch("bot_users", {"user_id": f"eq.{tid}"}, {"is_banned": False})
                send(uid, "User " + str(tid) + " debanni.")
            except: send(uid, "ID invalide.")
            return
        if text.startswith("/broadcast "):
            msg = text[len("/broadcast "):]
            users = db_get("bot_users")
            sent = 0
            for uu in users:
                if not uu.get("is_banned"):
                    try:
                        tg("sendMessage", chat_id=uu["user_id"], text="Message XAFEARN\n\n" + msg)
                        sent += 1
                    except: pass
            send(uid, "Broadcast envoye a " + str(sent) + " utilisateurs.")
            return

    if not u.get("is_registered"):
        send(uid, "Rejoins nos canaux d abord.\nEnvoie /start"); return

    # ── MENU UTILISATEUR (4 boutons) ─────────────────────
    if text == "\U0001f4e2 Nos Canaux":
        send(uid, "Nos canaux officiels :", kb={"inline_keyboard": [
            [{"text": "Canal 1", "url": CHANNELS_DISPLAY[0]}],
            [{"text": "Canal 2", "url": CHANNELS_DISPLAY[1]}],
            [{"text": "Canal 3", "url": CHANNELS_DISPLAY[2]}]
        ]})

    elif text == "\U0001f465 Parrainage":
        ref_link = "https://t.me/" + BOT_USERNAME + "?start=" + str(uid)
        send(uid,
            "TON LIEN D AFFILIATION\n\n" + ref_link + "\n\n"
            "Partage ce lien : tes filleuls jouent et tu gagnes des recompenses dans le jeu !")

    elif text == "\U00002753 Aide":
        send(uid,
            "AIDE XAFEARN\n\n"
            "Clique sur Jouer maintenant pour ouvrir le jeu.\n"
            "Toutes tes recompenses, ton solde et tes retraits se gerent directement dans le jeu.\n\n"
            "Support WhatsApp :\nhttps://wa.me/699663183")

def handle_cb(uid, data, mid):
    if data == "check_join":
        u = get_user(uid)
        if not u: return
        if not check_joined(uid):
            tg("editMessageText", chat_id=uid, message_id=mid,
               text="Tu n as pas encore tout rejoint.\nRejoins les 3 canaux puis clique Verifier.",
               reply_markup=join_kb())
            return
        db_patch("bot_users", {"user_id": f"eq.{uid}"}, {"is_registered": True})
        tg("editMessageText", chat_id=uid, message_id=mid, text="Compte active ! Bienvenue dans XAFEARN.")
        send(uid, "Menu Principal XAFEARN\n\nClique sur Jouer maintenant pour commencer !", kb=main_kb())

    elif data.startswith("gwok_") or data.startswith("gwno_"):
        if uid not in ADMIN_IDS:
            return
        decision = "ok" if data.startswith("gwok_") else "no"
        w_id = data.split("_", 1)[1]
        rows = db_get("xa_withdrawals", {"id": f"eq.{w_id}"})
        if not rows:
            send(uid, "Retrait introuvable."); return
        w = rows[0]
        if w.get("status") != "pending":
            send(uid, "Deja traite."); return
        if decision == "ok":
            db_patch("xa_withdrawals", {"id": f"eq.{w_id}"}, {"status": "approved"})
            send(uid, "PAIEMENT EFFECTUE\n\nMontant : " + str(w["amount"]) + "F\nMethode : " + str(w.get("method", "")) +
                 "\nNumero : " + str(w.get("number", "")) + "\nNom : " + str(w.get("name", "")))
            try: send(w["telegram_id"], "Retrait approuve !\n\n" + str(w["amount"]) + "F envoye. Merci de ta confiance !")
            except: pass
        else:
            db_patch("xa_withdrawals", {"id": f"eq.{w_id}"}, {"status": "rejected"})
            u2rows = db_get("xa_users", {"id": f"eq.{w['user_id']}"})
            if u2rows:
                u2 = u2rows[0]
                db_patch("xa_users", {"id": f"eq.{w['user_id']}"}, {"fcfa_balance": (u2.get("fcfa_balance") or 0) + w["amount"]})
            send(uid, "RETRAIT REJETE #" + str(w_id))
            try: send(w["telegram_id"], "Retrait refuse.\n\n+" + str(w["amount"]) + "F rembourse.\nSupport : https://wa.me/699663183")
            except: pass

application = app
handler = app
