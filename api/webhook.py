import os, json, hmac, hashlib, time
from urllib.parse import parse_qsl
from flask import Flask, request, jsonify
import requests as req

app = Flask(__name__)

BOT_TOKEN    = os.environ.get("BOT_TOKEN", "")
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")
DB = f"{SUPABASE_URL}/rest/v1"
H = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation"
}
REFERRAL_BONUS = 10

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

def check_telegram_auth(init_data):
    """Valide la signature Telegram WebApp (voir doc officielle Mini Apps). Retourne le dict user ou None."""
    if not init_data or not BOT_TOKEN:
        return None
    try:
        parsed = dict(parse_qsl(init_data, strict_parsing=True))
    except Exception:
        return None
    recv_hash = parsed.pop("hash", None)
    if not recv_hash:
        return None
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(parsed.items()))
    secret_key = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
    computed_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(computed_hash, recv_hash):
        return None
    try:
        auth_date = int(parsed.get("auth_date", 0))
    except: auth_date = 0
    if time.time() - auth_date > 86400:
        return None
    user_raw = parsed.get("user")
    if not user_raw:
        return None
    try:
        return json.loads(user_raw)
    except Exception:
        return None

def credit_referrer(tg_id):
    rows = db_get("bot_users", {"user_id": f"eq.{tg_id}", "limit": "1"})
    if not rows or not rows[0].get("referred_by"):
        return
    ref_tg_id = rows[0]["referred_by"]
    ref_rows = db_get("xa_users", {"telegram_id": f"eq.{ref_tg_id}", "limit": "1"})
    if not ref_rows:
        return
    ru = ref_rows[0]
    db_patch("xa_users", {"id": f"eq.{ru['id']}"}, {"xacoins": (ru.get("xacoins") or 0) + REFERRAL_BONUS})
    db_post("xa_transactions", {
        "user_id": ru["id"], "type": "parrainage", "xacoins": REFERRAL_BONUS,
        "description": "Bonus parrainage - filleul inscrit"
    })

def cors(resp):
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
    resp.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
    return resp

@app.route("/api/game_auth", methods=["POST", "OPTIONS"])
def game_auth():
    if request.method == "OPTIONS":
        return cors(jsonify({}))

    body = request.get_json(force=True) or {}
    init_data = body.get("initData", "")
    tg_user = check_telegram_auth(init_data)
    if not tg_user:
        return cors(jsonify({"error": "auth_invalide"})), 401

    tg_id = tg_user.get("id")
    nom = (str(tg_user.get("first_name","")) + " " + str(tg_user.get("last_name",""))).strip()
    nom = nom or tg_user.get("username") or "Joueur"

    rows = db_get("xa_users", {"telegram_id": f"eq.{tg_id}", "limit": "1"})
    is_new = False
    if rows:
        u = rows[0]
    else:
        created = db_post("xa_users", {
            "telegram_id": tg_id, "nom": nom, "telephone": None, "pays": None,
            "xacoins": 100, "fcfa_balance": 0, "niveau": 1, "experience": 0
        })
        if not created:
            return cors(jsonify({"error": "creation_echouee"})), 500
        u = created[0]
        is_new = True
        db_post("xa_mining", {"user_id": u["id"], "niveau": 1, "xacoins_total": 0})
        db_post("xa_empire", {"user_id": u["id"], "nom_empire": nom + " Empire", "niveau": 1, "soldats": 10, "ressources": 100})
        credit_referrer(tg_id)

    return cors(jsonify({"user": u, "is_new": is_new}))

application = app
handler = app
