import os
from flask import Flask, request, Response
import requests as req

app = Flask(__name__)
TOKEN = os.environ.get("BOT_TOKEN", "")
API   = f"https://api.telegram.org/bot{TOKEN}"

@app.route("/api/webhook", methods=["GET"])
def health():
    return "XAFEARN BOT OK", 200

@app.route("/api/webhook", methods=["POST"])
def webhook():
    try:
        body = request.get_json(force=True)
        if body and "message" in body:
            uid = body["message"]["from"]["id"]
            req.post(f"{API}/sendMessage", json={
                "chat_id": uid,
                "text": "✅ Bot en ligne !"
            }, timeout=10)
    except Exception as e:
        print(f"Error: {e}")
    return Response('{"ok":true}', mimetype="application/json")

application = app
handler = app