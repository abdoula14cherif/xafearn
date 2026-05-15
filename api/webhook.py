import os, json
from flask import Flask, request, Response
import requests as req

app = Flask(__name__)

TOKEN = os.environ.get("BOT_TOKEN", "")
API   = f"https://api.telegram.org/bot{TOKEN}"

def tg(method, **kwargs):
    try:
        return req.post(f"{API}/{method}", json=kwargs, timeout=10).json()
    except Exception as e:
        print(f"tg error: {e}")
        return {}

def send(uid, text):
    tg("sendMessage", chat_id=uid, text=text, parse_mode="Markdown")

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
            uname = body["message"]["from"].get("username") or "User"
            text  = body["message"].get("text", "")

            if not text:
                return Response('{"ok":true}', mimetype="application/json")

            # Test étape par étape
            if text == "/test1":
                send(uid, "✅ Étape 1 OK — Flask marche")

            elif text == "/test2":
                try:
                    SB_URL = os.environ.get("SUPABASE_URL","")
                    SB_KEY = os.environ.get("SUPABASE_KEY","")
                    headers = {"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}"}
                    r = req.get(f"{SB_URL}/rest/v1/config", headers=headers, timeout=10)
                    send(uid, f"✅ Étape 2 OK — Supabase : {r.status_code}")
                except Exception as e:
                    send(uid, f"❌ Étape 2 FAIL — Supabase :\n`{e}`")

            elif text == "/test3":
                try:
                    ADMIN_IDS = [int(x) for x in os.environ.get("ADMIN_IDS","").split(",") if x.strip().isdigit()]
                    CHANNELS  = [os.environ.get("CHANNEL_1",""), os.environ.get("CHANNEL_2",""), os.environ.get("CHANNEL_3","")]
                    send(uid, f"✅ Étape 3 OK\nAdmin IDs: {ADMIN_IDS}\nCanaux: {CHANNELS}")
                except Exception as e:
                    send(uid, f"❌ Étape 3 FAIL :\n`{e}`")

            elif text.startswith("/start"):
                send(uid, "✅ /start reçu — En cours de chargement...")
                try:
                    SB_URL = os.environ.get("SUPABASE_URL","")
                    SB_KEY = os.environ.get("SUPABASE_KEY","")
                    headers = {
                        "apikey": SB_KEY,
                        "Authorization": f"Bearer {SB_KEY}",
                        "Content-Type": "application/json",
                        "Prefer": "return=representation"
                    }
                    # Vérifier si user existe
                    r = req.get(f"{SB_URL}/rest/v1/users",
                        headers=headers,
                        params={"user_id": f"eq.{uid}"},
                        timeout=10
                    )
                    data = r.json()
                    if not data:
                        # Créer user
                        req.post(f"{SB_URL}/rest/v1/users",
                            headers=headers,
                            json={"user_id": uid, "username": uname, "balance": 0, "is_banned": False, "is_registered": False},
                            timeout=10
                        )
                        send(uid, "✅ Compte créé dans Supabase !")
                    else:
                        send(uid, f"✅ User trouvé ! Solde : *{data[0].get('balance',0)}F*")
                except Exception as e:
                    send(uid, f"❌ Erreur Supabase :\n`{str(e)[:200]}`")
            else:
                send(uid, f"Tu as écrit : `{text}`\n\nTest avec /test1, /test2, /test3")

    except Exception as e:
        import traceback
        err = traceback.format_exc()
        print(f"ERREUR TOTALE: {err}")
        if uid:
            try:
                send(uid, f"❌ Erreur critique :\n`{str(e)[:200]}`")
            except:
                pass

    return Response('{"ok":true}', mimetype="application/json")

application = app
handler = app
