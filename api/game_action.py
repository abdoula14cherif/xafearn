import os, json, hmac, hashlib, time, random
from urllib.parse import parse_qsl
from flask import Flask, request, jsonify
import requests as req
from datetime import datetime

app = Flask(__name__)

BOT_TOKEN    = os.environ.get("BOT_TOKEN", "")
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")
ADMIN_IDS    = [int(x.strip()) for x in os.environ.get("ADMIN_IDS", "").split(",") if x.strip().isdigit()]
API = f"https://api.telegram.org/bot{BOT_TOKEN}"
DB  = f"{SUPABASE_URL}/rest/v1"
H = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation"
}

ANIMAUX = {
    "poule":    {"prix": 500,  "ph": 1.04},
    "mouton":   {"prix": 1500, "ph": 3.33},
    "vache":    {"prix": 3000, "ph": 8.33},
    "troupeau": {"prix": 8000, "ph": 25},
}
MINE_RATES  = [0, 1, 5, 15]
MINE_PRIX   = {2: 1000, 3: 2500}
CONV_RATE   = 2
MISE_BATTLE = 200
CARTE_FORCE = {"👑": 6, "🐯": 5, "🦁": 4, "🐻": 3, "🦊": 2, "🐰": 1}

def db_get(table, params):
    try:
        r = req.get(f"{DB}/{table}", headers=H, params=params, timeout=15)
        d = r.json()
        return d if isinstance(d, list) else []
    except: return []

def db_post(table, data):
    try:
        r = req.post(f"{DB}/{table}", headers=H, json=data, timeout=15)
        d = r.json()
        return d if isinstance(d, list) else []
    except: return []

def db_patch(table, params, data):
    try: req.patch(f"{DB}/{table}", headers=H, params=params, json=data, timeout=15)
    except: pass

def tg_send(chat_id, text, kb=None):
    d = {"chat_id": chat_id, "text": text}
    if kb: d["reply_markup"] = kb
    try: req.post(f"{API}/sendMessage", json=d, timeout=10)
    except: pass

def hours_ago(iso_str):
    if not iso_str: return 0
    try:
        dt = datetime.fromisoformat(str(iso_str).replace("Z", "+00:00"))
        now = datetime.now(dt.tzinfo) if dt.tzinfo else datetime.now()
        return max(0, (now - dt).total_seconds() / 3600)
    except: return 0

def today():
    return datetime.now().date().isoformat()

def check_telegram_auth(init_data):
    if not init_data:
        return None, "init_data_vide"
    if not BOT_TOKEN:
        return None, "bot_token_absent"
    try:
        parsed = dict(parse_qsl(init_data, strict_parsing=True))
    except Exception:
        return None, "parse_echec"
    recv_hash = parsed.pop("hash", None)
    if not recv_hash:
        return None, "hash_absent"
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(parsed.items()))
    secret_key = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
    computed_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(computed_hash, recv_hash):
        return None, "signature_invalide"
    try:
        auth_date = int(parsed.get("auth_date", 0))
    except:
        auth_date = 0
    if time.time() - auth_date > 86400:
        return None, "expire"
    user_raw = parsed.get("user")
    if not user_raw:
        return None, "user_absent"
    try:
        return json.loads(user_raw), "ok"
    except Exception:
        return None, "json_invalide"

def cors(resp):
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
    resp.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
    return resp

def get_authed_user(body):
    tg_user, reason = check_telegram_auth(body.get("initData", ""))
    if not tg_user:
        return None, ("auth_invalide:" + reason, 401)
    tg_id = tg_user.get("id")
    rows = db_get("xa_users", {"telegram_id": f"eq.{tg_id}", "limit": "1"})
    if not rows:
        return None, ("utilisateur_introuvable", 404)
    return rows[0], None

def fresh_user(uid):
    rows = db_get("xa_users", {"id": f"eq.{uid}", "limit": "1"})
    return rows[0] if rows else None

@app.route("/api/game_action", methods=["POST", "OPTIONS"])
def game_action():
    if request.method == "OPTIONS":
        return cors(jsonify({}))
    body = request.get_json(force=True) or {}
    u, err = get_authed_user(body)
    if err:
        return cors(jsonify({"error": err[0]})), err[1]

    action = body.get("action", "")
    handlers = {
        "claim_bonus": claim_bonus, "collect_ferme": collect_ferme, "mine": mine_action,
        "upgrade_mine": upgrade_mine, "buy_animal": buy_animal, "empire_collect": empire_collect,
        "empire_upgrade": empire_upgrade, "empire_attack": empire_attack, "battle_join": battle_join,
        "convert": convert_action, "withdraw": withdraw_action,
    }
    fn = handlers.get(action)
    if not fn:
        return cors(jsonify({"error": "action_inconnue"})), 400
    try:
        return cors(jsonify(fn(u, body)))
    except Exception:
        return cors(jsonify({"error": "erreur_serveur"})), 500

def claim_bonus(u, body):
    if u.get("derniere_connexion") == today():
        return {"error": "deja_reclame"}
    bonus = 50 + (u.get("niveau") or 1) * 10
    db_patch("xa_users", {"id": f"eq.{u['id']}"}, {"xacoins": (u.get("xacoins") or 0) + bonus, "derniere_connexion": today()})
    db_post("xa_transactions", {"user_id": u["id"], "type": "bonus", "xacoins": bonus, "description": "Bonus connexion jour " + today()})
    return {"user": fresh_user(u["id"]), "gain": bonus}

def collect_ferme(u, body):
    anims = db_get("xa_animaux", {"user_id": f"eq.{u['id']}"})
    if not anims:
        return {"error": "aucun_animal"}
    total = 0
    now = datetime.now().isoformat()
    for a in anims:
        info = ANIMAUX.get(a.get("type_animal"))
        if not info or not a.get("quantite"): continue
        h = hours_ago(a.get("derniere_collecte"))
        pending = min(h * info["ph"] * a["quantite"], info["ph"] * a["quantite"] * 24)
        total += pending
        db_patch("xa_animaux", {"id": f"eq.{a['id']}"}, {"derniere_collecte": now})
    total = int(total)
    if total < 1:
        return {"error": "rien_a_collecter"}
    db_patch("xa_users", {"id": f"eq.{u['id']}"}, {"xacoins": (u.get("xacoins") or 0) + total})
    db_post("xa_transactions", {"user_id": u["id"], "type": "ferme", "xacoins": total, "description": "Collecte ferme"})
    return {"user": fresh_user(u["id"]), "gain": total}

def mine_action(u, body):
    rows = db_get("xa_mining", {"user_id": f"eq.{u['id']}", "limit": "1"})
    if not rows:
        rows = db_post("xa_mining", {"user_id": u["id"], "niveau": 1, "xacoins_total": 0})
    m = rows[0]
    niveau = m.get("niveau") or 1
    rate = MINE_RATES[niveau] if niveau < len(MINE_RATES) else MINE_RATES[-1]
    h = hours_ago(m.get("derniere_mine"))
    gain = min(int(h * rate), rate * 24)
    if gain < 1:
        return {"error": "trop_tot"}
    now = datetime.now().isoformat()
    db_patch("xa_mining", {"id": f"eq.{m['id']}"}, {"derniere_mine": now, "xacoins_total": (m.get("xacoins_total") or 0) + gain})
    db_patch("xa_users", {"id": f"eq.{u['id']}"}, {"xacoins": (u.get("xacoins") or 0) + gain})
    db_post("xa_transactions", {"user_id": u["id"], "type": "mining", "xacoins": gain, "description": "Mining niveau " + str(niveau)})
    return {"user": fresh_user(u["id"]), "gain": gain}

def upgrade_mine(u, body):
    niveau = body.get("niveau")
    ref = str(body.get("ref", "")).strip()
    if niveau not in MINE_PRIX or len(ref) < 4:
        return {"error": "donnees_invalides"}
    rows = db_get("xa_mining", {"user_id": f"eq.{u['id']}", "limit": "1"})
    if not rows:
        return {"error": "mine_introuvable"}
    m = rows[0]
    if (m.get("niveau") or 1) >= niveau:
        return {"error": "deja_ce_niveau"}
    db_patch("xa_mining", {"id": f"eq.{m['id']}"}, {"niveau": niveau})
    db_post("xa_transactions", {"user_id": u["id"], "type": "upgrade_mine", "fcfa": MINE_PRIX[niveau], "description": "Upgrade mine niveau " + str(niveau) + " ref:" + ref})
    return {"niveau": niveau}

def buy_animal(u, body):
    typ = body.get("type")
    ref = str(body.get("ref", "")).strip()
    if typ not in ANIMAUX or len(ref) < 4:
        return {"error": "donnees_invalides"}
    rows = db_get("xa_animaux", {"user_id": f"eq.{u['id']}", "type_animal": f"eq.{typ}", "limit": "1"})
    if rows:
        db_patch("xa_animaux", {"id": f"eq.{rows[0]['id']}"}, {"quantite": rows[0]["quantite"] + 1})
    else:
        db_post("xa_animaux", {"user_id": u["id"], "type_animal": typ, "quantite": 1, "derniere_collecte": datetime.now().isoformat()})
    db_post("xa_transactions", {"user_id": u["id"], "type": "achat_animal", "fcfa": ANIMAUX[typ]["prix"], "description": "Achat " + typ + " ref:" + ref})
    return {"ok": True}

def empire_collect(u, body):
    rows = db_get("xa_empire", {"user_id": f"eq.{u['id']}", "limit": "1"})
    if not rows:
        return {"error": "empire_introuvable"}
    em = rows[0]
    h = hours_ago(em.get("derniere_collecte"))
    gain = int(h * (em.get("niveau") or 1) * 5)
    if gain < 1:
        return {"error": "trop_tot"}
    db_patch("xa_empire", {"id": f"eq.{em['id']}"}, {"ressources": em["ressources"] + gain, "derniere_collecte": datetime.now().isoformat()})
    return {"gain": gain}

def empire_upgrade(u, body):
    rows = db_get("xa_empire", {"user_id": f"eq.{u['id']}", "limit": "1"})
    if not rows:
        return {"error": "empire_introuvable"}
    em = rows[0]
    cout = (em.get("niveau") or 1) * 100
    if em["ressources"] < cout:
        return {"error": "ressources_insuffisantes"}
    db_patch("xa_empire", {"id": f"eq.{em['id']}"}, {
        "niveau": em["niveau"] + 1, "ressources": em["ressources"] - cout,
        "soldats": em["soldats"] + 5,
        "points_attaque": (em.get("points_attaque") or 5) + 2,
        "points_defense": (em.get("points_defense") or 5) + 2
    })
    return {"ok": True}

def empire_attack(u, body):
    target_id = body.get("target_id")
    my_rows = db_get("xa_empire", {"user_id": f"eq.{u['id']}", "limit": "1"})
    tgt_rows = db_get("xa_empire", {"id": f"eq.{target_id}", "limit": "1"})
    if not my_rows or not tgt_rows:
        return {"error": "empire_introuvable"}
    me = my_rows[0]; tgt = tgt_rows[0]
    if tgt.get("user_id") == u["id"]:
        return {"error": "cible_invalide"}
    score_moi = me["soldats"] * (me.get("points_attaque") or 5)
    score_enn = tgt["soldats"] * 5
    victoire = score_moi > score_enn or random.random() > 0.4
    if victoire:
        butin = random.randint(20, 70)
        db_patch("xa_empire", {"id": f"eq.{me['id']}"}, {"ressources": me["ressources"] + butin})
        return {"victoire": True, "gain": butin}
    perte = random.randint(5, 25)
    db_patch("xa_empire", {"id": f"eq.{me['id']}"}, {"soldats": max(1, me["soldats"] - perte)})
    return {"victoire": False, "perte": perte}

def battle_join(u, body):
    carte = body.get("carte")
    if carte not in CARTE_FORCE:
        return {"error": "carte_invalide"}
    if (u.get("xacoins") or 0) < MISE_BATTLE:
        return {"error": "solde_insuffisant"}
    waiting = db_get("xa_battles", {"status": "eq.waiting", "order": "created_at.asc", "limit": "1"})
    if waiting and waiting[0]["player1_id"] != u["id"]:
        bt = waiting[0]
        adv_carte = bt["player1_carte"]
        win = CARTE_FORCE[carte] > CARTE_FORCE[adv_carte]
        commission = int(bt["mise_xacoins"] * 0.15)
        gain = int(bt["mise_xacoins"] * 2 * 0.85)
        gagnant_id = u["id"] if win else bt["player1_id"]
        db_patch("xa_users", {"id": f"eq.{u['id']}"}, {"xacoins": u["xacoins"] - bt["mise_xacoins"]})
        gagnant_rows = db_get("xa_users", {"id": f"eq.{gagnant_id}", "limit": "1"})
        if gagnant_rows:
            gu = gagnant_rows[0]
            db_patch("xa_users", {"id": f"eq.{gagnant_id}"}, {"xacoins": (gu.get("xacoins") or 0) + gain})
        db_patch("xa_battles", {"id": f"eq.{bt['id']}"}, {
            "player2_id": u["id"], "player2_carte": carte, "status": "finished",
            "gagnant_id": gagnant_id, "commission": commission,
            "finished_at": datetime.now().isoformat()
        })
        return {"user": fresh_user(u["id"]), "victoire": win, "adversaire_carte": adv_carte, "gain": gain if win else 0}
    db_patch("xa_users", {"id": f"eq.{u['id']}"}, {"xacoins": u["xacoins"] - MISE_BATTLE})
    created = db_post("xa_battles", {"player1_id": u["id"], "player1_carte": carte, "mise_xacoins": MISE_BATTLE, "status": "waiting"})
    if not created:
        db_patch("xa_users", {"id": f"eq.{u['id']}"}, {"xacoins": u["xacoins"]})
        return {"error": "creation_echouee"}
    return {"user": fresh_user(u["id"]), "en_attente": True}

def convert_action(u, body):
    try: amt = int(body.get("amount", 0))
    except: amt = 0
    if amt < 2000 or amt > (u.get("xacoins") or 0):
        return {"error": "montant_invalide"}
    fcfa = amt // CONV_RATE
    db_patch("xa_users", {"id": f"eq.{u['id']}"}, {"xacoins": u["xacoins"] - amt, "fcfa_balance": (u.get("fcfa_balance") or 0) + fcfa})
    db_post("xa_transactions", {"user_id": u["id"], "type": "conversion", "xacoins": -amt, "fcfa": fcfa, "description": "Conversion " + str(amt) + " XAC -> " + str(fcfa) + "F"})
    return {"user": fresh_user(u["id"]), "fcfa": fcfa}

def withdraw_action(u, body):
    method = str(body.get("method", "")).strip()
    number = str(body.get("number", "")).strip()
    name   = str(body.get("name", "")).strip()
    try: amt = int(body.get("amount", 0))
    except: amt = 0
    if len(number) < 4 or len(name) < 3 or amt < 1000 or amt > (u.get("fcfa_balance") or 0):
        return {"error": "donnees_invalides"}
    db_patch("xa_users", {"id": f"eq.{u['id']}"}, {"fcfa_balance": u["fcfa_balance"] - amt})
    created = db_post("xa_withdrawals", {
        "user_id": u["id"], "telegram_id": u.get("telegram_id"),
        "amount": amt, "method": method, "number": number, "name": name, "status": "pending"
    })
    w_id = created[0]["id"] if created else "?"
    db_post("xa_transactions", {"user_id": u["id"], "type": "retrait", "fcfa": amt, "description": "Retrait " + method + " " + number + " - " + name})
    for admin_id in ADMIN_IDS:
        tg_send(admin_id,
            "NOUVEAU RETRAIT JEU #" + str(w_id) + "\n\nMontant : " + str(amt) + "F\nMethode : " + method +
            "\nNumero : " + number + "\nNom : " + name + "\nUser (telegram) : " + str(u.get("telegram_id")),
            kb={"inline_keyboard": [[
                {"text": "Approuver", "callback_data": "gwok_" + str(w_id)},
                {"text": "Rejeter", "callback_data": "gwno_" + str(w_id)}
            ]]})
    return {"user": fresh_user(u["id"]), "demande_id": w_id}

application = app
handler = app
