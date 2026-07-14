
import json
import asyncio
import hmac
import hashlib
from http.server import BaseHTTPRequestHandler

from lib.config import BOT_TOKEN, ADMIN_IDS, WEBHOOK_SECRET
from handlers.user import (
    handle_start, handle_check_join, handle_bonus, handle_solde,
    handle_parrainage, handle_tasks, handle_task_complete,
    handle_historique, handle_classement, handle_aide
)
from handlers.admin import (
    is_admin, handle_admin_panel, handle_all_users, handle_modify_prices,
    handle_add_task_start, handle_list_withdrawals, handle_ban_start,
    handle_broadcast_start, handle_admin_session, handle_admin_command,
    handle_stats
)
from handlers.retrait import (
    handle_retrait_start, handle_retrait_method, handle_retrait_step,
    handle_cancel_retrait, handle_retrait_decision
)
from lib.keyboards import main_keyboard
from telegram import Bot

bot = Bot(token=BOT_TOKEN)

# ════════════════════════════════════════════════════════════════════
#  Handler Vercel
# ════════════════════════════════════════════════════════════════════

class handler(BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        pass  # Silencer les logs HTTP

    def do_GET(self):
        """Health check"""
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"XAFEARN BOT is running OK")

    def do_POST(self):
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length == 0:
                self._respond(400)
                return

            body = self.rfile.read(content_length)

            # ── Vérification sécurité du secret webhook ──
            secret_header = self.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
            if WEBHOOK_SECRET and secret_header != WEBHOOK_SECRET:
                self._respond(403)
                return

            update = json.loads(body.decode("utf-8"))
            asyncio.run(process_update(update))
            self._respond(200)

        except Exception as e:
            print(f"Webhook error: {e}")
            self._respond(200)  # Toujours 200 pour Telegram

    def _respond(self, code: int):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"ok":true}')


# ════════════════════════════════════════════════════════════════════
#  Traitement des updates
# ════════════════════════════════════════════════════════════════════

async def process_update(body: dict):
    try:
        # ── Message texte ────────────────────────────────────────
        if "message" in body:
            msg     = body["message"]
            user    = msg.get("from", {})
            uid     = user.get("id")
            uname   = user.get("username") or user.get("first_name", "User")
            text    = msg.get("text", "")
            chat_id = msg.get("chat", {}).get("id")

            if not uid or not text:
                return

            # ── Sessions retrait actives ──
            from handlers.retrait import retrait_sessions
            if uid in retrait_sessions:
                await handle_retrait_step(uid, text)
                return

            # ── Sessions admin actives ──
            if is_admin(uid):
                from handlers.admin import admin_sessions
                if uid in admin_sessions:
                    await handle_admin_session(uid, text)
                    return

            # ── Commandes admin directes ──
            if is_admin(uid):
                handled = await handle_admin_command(uid, text)
                if handled:
                    return

                # Boutons du panel admin
                admin_actions = {
                    "👥 Tous les Users":      handle_all_users,
                    "📊 Statistiques":         handle_stats,
                    "⚙️ Modifier les Prix":   handle_modify_prices,
                    "➕ Ajouter une Tâche":   handle_add_task_start,
                    "💸 Demandes Retrait":    handle_list_withdrawals,
                    "🚫 Bannir / Débannir":   handle_ban_start,
                    "📢 Broadcast":            handle_broadcast_start,
                }
                if text in admin_actions:
                    await admin_actions[text](uid)
                    return
                if text == "🔙 Mode Utilisateur":
                    await bot.send_message(uid,
                        "👤 *Mode Utilisateur activé*",
                        parse_mode="Markdown",
                        reply_markup=main_keyboard()
                    )
                    return

            # ── Commandes utilisateur ──
            if text.startswith("/start"):
                parts = text.split(" ")
                arg   = parts[1] if len(parts) > 1 else None
                await handle_start(uid, uname, arg)

            elif text == "🎁 Bonus Journalier":  await handle_bonus(uid)
            elif text == "💰 Mon Solde":          await handle_solde(uid)
            elif text == "👥 Parrainage":          await handle_parrainage(uid)
            elif text == "✅ Tâches du Jour":      await handle_tasks(uid)
            elif text == "📋 Historique":          await handle_historique(uid)
            elif text == "💸 Retrait":             await handle_retrait_start(uid)
            elif text == "🏆 Classement":          await handle_classement(uid)
            elif text == "❓ Aide":               await handle_aide(uid)

            # ── Commandes cachées ──
            elif text == "/admin" and is_admin(uid):
                await handle_admin_panel(uid)

        # ── Callback Query (boutons inline) ──────────────────────
        elif "callback_query" in body:
            cq      = body["callback_query"]
            uid     = cq["from"]["id"]
            data    = cq.get("data", "")
            msg_id  = cq["message"]["message_id"]
            chat_id = cq["message"]["chat"]["id"]
            cq_id   = cq.get("id", "")

            # Répondre immédiatement pour enlever le loading
            try:
                await bot.answer_callback_query(cq_id)
            except Exception:
                pass

            if data == "check_join":
                await handle_check_join(uid, msg_id)

            elif data.startswith("task_"):
                task_id = int(data.split("_")[1])
                await handle_task_complete(uid, task_id, cq_id)

            elif data.startswith("method_"):
                method = data.split("_")[1]
                await handle_retrait_method(uid, method, msg_id)

            elif data == "cancel_retrait":
                await handle_cancel_retrait(uid, msg_id)

            elif data.startswith("approve_") or data.startswith("reject_"):
                parts    = data.split("_")
                decision = parts[0]
                w_id     = int(parts[1])
                await handle_retrait_decision(uid, decision, w_id, msg_id, chat_id)

    except Exception as e:
        print(f"process_update error: {e}")
