import os, json, traceback
from flask import Flask, request, Response
import requests as req

app = Flask(__name__)

TOKEN = os.environ.get("BOT_TOKEN", "")
API   = f"https://api.telegram.org/bot{TOKEN}"

def send(uid, text):
    try:
        req.post(f"{API}/sendMessage", json={
            "chat_id": uid, "text": text, "parse_mode": "Markdown"
        }, timeout=10)
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
            uid  = body["message"]["from"]["id"]
            text = body["message"].get("text", "")

            try:
                # Test 1 — Variables env
                SB_URL = os.environ.get("SUPABASE_URL", "MANQUANT")
                SB_KEY = os.environ.get("SUPABASE_KEY", "MANQUANT")
                ADMIN  = os.environ.get("ADMIN_IDS", "MANQUANT")

                # Test 2 — Supabase
                H = {
                    "apikey": SB_KEY,
                    "Authorization": f"Bearer {SB_KEY}",
                    "Content-Type": "application/json",
                    "Prefer": "return=representation"
                }
                r = req.get(f"{SB_URL}/rest/v1/users",
                    headers=H,
                    params={"user_id": f"eq.{uid}"},
                    timeout=10
                )

                send(uid,
                    f"✅ *Diagnostic OK*\n\n"
                    f"📦 SB\\_URL : `{SB_URL[:30]}...`\n"
                    f"🔑 SB\\_KEY : `{SB_KEY[:20]}...`\n"
                    f"👤 ADMIN : `{ADMIN}`\n"
                    f"🗄️ Supabase status : `{r.status_code}`\n"
                    f"📝 Réponse : `{str(r.text[:100])}`"
                )

            except Exception as e:
                err = traceback.format_exc()
                send(uid, f"❌ *Erreur interne :*\n`{str(e)[:300]}`")
                print(f"ERREUR: {err}")

    except Exception as e:
        err = traceback.format_exc()
        print(f"WEBHOOK ERREUR: {err}")
        if uid:
            send(uid, f"❌ *Erreur webhook :*\n`{str(e)[:200]}`")

    return Response('{"ok":true}', mimetype="application/json")

application = app
handler = app