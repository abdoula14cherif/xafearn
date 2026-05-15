import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
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
    try:
        body = request.get_json(force=True)
        if body and "message" in body:
            uid = body["message"]["from"]["id"]
            import asyncio
            loop = asyncio.new_event_loop()
            loop.run_until_complete(
                bot.send_message(uid, "✅ Bot en ligne !")
            )
            loop.close()
    except Exception as e:
        print(f"Error: {e}")
    return Response('{"ok":true}', mimetype="application/json")

handler = app