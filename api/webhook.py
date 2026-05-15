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
    try:
        body = request.get_json(force=True)
        if body:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(process_update(body))
            loop.close()
    except Exception as e:
        print(f"Error: {e}")
    return Response('{"ok":true}', mimetype="application/json")

async def process_update(body):
    uid = None
    try:
        if "message" in body:
            uid = body["message"]["from"]["id"]
            text = body["message"].get("text", "")
            uname = body["message"]["from"].get("username") or body["message"]["from"].get("first_name", "User")

            # Test import
            try:
                from lib.keyboards import main_keyboard
                from lib.database import get_user, add_user
                from handlers.user import handle_start
            except Exception as import_err:
                await bot.send_message(uid, f"❌ Erreur import:\n`{import_err}`", parse_mode="Markdown")
                return

            if text.startswith("/start"):
                parts = text.split(" ")
                await handle_start(uid, uname, parts[1] if len(parts) > 1 else None)
            else:
                await bot.send_message(uid, f"Tu as écrit : {text}")

    except Exception as e:
        print(f"Error: {e}")
        if uid:
            try:
                await bot.send_message(uid, f"❌ Erreur:\n`{e}`", parse_mode="Markdown")
            except:
                pass

# Vercel entry point
application = app