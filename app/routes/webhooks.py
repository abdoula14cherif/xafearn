from flask import Blueprint, request, jsonify
from app.supabase_client import get_paiement_par_order_id, maj_statut_paiement

webhooks_bp = Blueprint("webhooks", __name__)

@webhooks_bp.route("/webhooks/flinpay", methods=["POST"])
def flinpay_webhook():
    data = request.get_json(silent=True) or {}
    event = data.get("event")
    payload = data.get("data", {})

    order_id = payload.get("order_id")
    montant_recu = payload.get("amount")
    token = payload.get("token")

    if not order_id:
        return jsonify({"ok": False, "error": "order_id manquant"}), 400

    paiement = get_paiement_par_order_id(order_id)
    if not paiement:
        return jsonify({"ok": False, "error": "paiement inconnu"}), 404

    # Flinpay ne signe pas ses webhooks : on vérifie nous-même la cohérence
    # du montant avant de faire confiance à la notification.
    if montant_recu is not None and int(montant_recu) != int(paiement["montant"]):
        return jsonify({"ok": False, "error": "montant incohérent"}), 400

    if event == "payment.success":
        maj_statut_paiement(order_id, "paid", token=token)
    elif event == "payment.failed":
        maj_statut_paiement(order_id, "failed", token=token)

    return jsonify({"ok": True})
