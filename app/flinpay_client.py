import os
import uuid
import requests

FLINPAY_API_KEY = os.environ.get("FLINPAY_API_KEY")
FLINPAY_BASE_URL = "https://www.flinpay.cfd"

def initier_paiement(amount, phone, client_name, country, operator):
    order_id = f"SWK-{uuid.uuid4().hex[:12]}"
    r = requests.post(
        f"{FLINPAY_BASE_URL}/api/pay",
        headers={"Authorization": f"Bearer {FLINPAY_API_KEY}"},
        json={
            "amount": amount,
            "phone": phone,
            "client_name": client_name,
            "order_id": order_id,
            "country": country,
            "operator": operator,
        },
        timeout=15,
    )
    return order_id, r
