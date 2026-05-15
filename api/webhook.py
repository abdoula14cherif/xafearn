import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
from flask import Flask, request, Response
from telegram import Bot
from lib.config import BOT_TOKEN

app = Flask(__name__)
bot = Bot(token=BOT_TOKEN)

@app.route("/api/webhook", methods=["GET"])
def health():
    return "XAFEARN BOT OK", 200

@app.route("/api/webhook", methods=["POST"])
def webhook():
    uid = None
    try:
        body = request.get_json(force=True)
        if body and "message" in body:
            uid = body["message"]["from"]["id"]
            text = body["message"].get("text", "")
            uname = body["message"]["from"].get("username") or "User"

            try:
                from lib.database import get_user
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(
                    bot.send_message(uid, "✅ Import OK !")
                )
                loop.close()
            except Exception as e:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(
                    bot.send_message(uid, f"❌ Erreur:\n`{str(e)[:200]}`", parse_mode="Markdown")
                )
                loop.close()

    except Exception as e:
        print(f"Error: {e}")

    return Response('{"ok":true}', mimetype="application/json", status=200)

application = app
handler = app