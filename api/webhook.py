import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import asyncio
from http.server import BaseHTTPRequestHandler
from lib.config import BOT_TOKEN
from lib.keyboards import main_keyboard
from telegram import Bot

bot = Bot(token=BOT_TOKEN)

class handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"XAFEARN BOT OK")

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            if length == 0:
                self._ok()
                return
            body = self.rfile.read(length)
            update = json.loads(body.decode("utf-8"))
            asyncio.run(process_update(update))
        except Exception as e:
            print(f"Error: {e}")
        self._ok()

    def _ok(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"ok":true}')


async def process_update(body):
    try:
        from handlers.user import (
            handle_start, handle_check_join, handle_bonus, handle_solde,
            handle_parrainage, handle_tasks, handle_task_complete,
            handle_historique, handle_classement, handle_aide
        )
        from handlers.admin import (
            is_admin, handle_admin_panel, handle_all_users, handle_modify_prices,
            handle_add_task_start, handle_list_withdrawals, handle_ban_start,
            handle_broadcast_start, handle_admin_session, handle_admin_command,
            admin_sessions
        )
        from handlers.retrait import (
            handle_retrait_start, handle_retrait_method, handle_retrait_step,
            handle_cancel_retrait, handle_retrait_decision, retrait_sessions
        )

        if "message" in body:
            msg   = body["message"]
            user  = msg.get("from", {})
            uid   = user.get("id")
            uname = user.get("username") or user.get("first_name", "User")
            text  = msg.get("text", "")
            if not uid or not text:
                return

            if uid in retrait_sessions:
                await handle_retrait_step(uid, text)
                return
            if is_admin(uid) and uid in admin_sessions:
                await handle_admin_session(uid, text)
                return
            if is_admin(uid):
                if await handle_admin_command(uid, text):
                    return
                admin_map = {
                    "👥 Tous les Users":     handle_all_users,
                    "📊 Statistiques":        handle_admin_panel,
                    "⚙️ Modifier les Prix":  handle_modify_prices,
                    "➕ Ajouter une Tâche":  handle_add_task_start,
                    "💸 Demandes Retrait":   handle_list_withdrawals,
                    "🚫 Bannir / Débannir":  handle_ban_start,
                    "📢 Broadcast":           handle_broadcast_start,
                }
                if text in admin_map:
                    await admin_map[text](uid)
                    return
                if text == "🔙 Mode Utilisateur":
                    await bot.send_message(uid, "👤 *Mode Utilisateur*",
                        parse_mode="Markdown", reply_markup=main_keyboard())
                    return

            if text.startswith("/start"):
                parts = text.split(" ")
                await handle_start(uid, uname, parts[1] if len(parts) > 1 else None)
            elif text == "🎁 Bonus Journalier":  await handle_bonus(uid)
            elif text == "💰 Mon Solde":          await handle_solde(uid)
            elif text == "👥 Parrainage":          await handle_parrainage(uid)
            elif text == "✅ Tâches du Jour":      await handle_tasks(uid)
            elif text == "📋 Historique":          await handle_historique(uid)
            elif text == "💸 Retrait":             await handle_retrait_start(uid)
            elif text == "🏆 Classement":          await handle_classement(uid)
            elif text == "❓ Aide":               await handle_aide(uid)
            elif text == "/admin" and is_admin(uid):
                await handle_admin_panel(uid)

        elif "callback_query" in body:
            cq      = body["callback_query"]
            uid     = cq["from"]["id"]
            data    = cq.get("data", "")
            msg_id  = cq["message"]["message_id"]
            chat_id = cq["message"]["chat"]["id"]
            cq_id   = cq.get("id", "")
            try:
                await bot.answer_callback_query(cq_id)
            except:
                pass

            if data == "check_join":
                await handle_check_join(uid, msg_id)
            elif data.startswith("task_"):
                await handle_task_complete(uid, int(data.split("_")[1]), cq_id)
            elif data.startswith("method_"):
                await handle_retrait_method(uid, data.split("_")[1], msg_id)
            elif data == "cancel_retrait":
                await handle_cancel_retrait(uid, msg_id)
            elif data.startswith("approve_") or data.startswith("reject_"):
                parts = data.split("_")
                await handle_retrait_decision(uid, parts[0], int(parts[1]), msg_id, chat_id)

    except Exception as e:
        print(f"process_update error: {e}")
