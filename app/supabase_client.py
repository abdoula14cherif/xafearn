import os
import requests

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

def _headers():
    return {
        "apikey": SERVICE_KEY,
        "Authorization": f"Bearer {SERVICE_KEY}",
        "Content-Type": "application/json",
    }

def create_user(nom, email, telephone, pays, mot_de_passe_hash):
    url = f"{SUPABASE_URL}/rest/v1/utilisateurs"
    payload = {
        "nom": nom,
        "email": email,
        "telephone": telephone,
        "pays": pays,
        "mot_de_passe_hash": mot_de_passe_hash,
    }
    r = requests.post(url, json=payload, headers=_headers(), timeout=10)
    return r

def get_user_by_email(email):
    url = f"{SUPABASE_URL}/rest/v1/utilisateurs"
    params = {"email": f"eq.{email}", "select": "*"}
    r = requests.get(url, params=params, headers=_headers(), timeout=10)
    if r.status_code == 200 and r.json():
        return r.json()[0]
    return None

def get_cycle_ouvert(jeu_id):
    url = f"{SUPABASE_URL}/rest/v1/cycles"
    params = {
        "jeu_id": f"eq.{jeu_id}", "statut": "eq.ouvert",
        "select": "*", "order": "created_at.desc", "limit": "1",
    }
    r = requests.get(url, params=params, headers=_headers(), timeout=10)
    if r.status_code == 200 and r.json():
        return r.json()[0]
    return None

def get_jeux():
    url = f"{SUPABASE_URL}/rest/v1/jeux"
    params = {"select": "*", "order": "created_at.asc"}
    r = requests.get(url, params=params, headers=_headers(), timeout=10)
    return r.json() if r.status_code == 200 else []

def get_jeu_par_slug(slug):
    url = f"{SUPABASE_URL}/rest/v1/jeux"
    params = {"slug": f"eq.{slug}", "select": "*"}
    r = requests.get(url, params=params, headers=_headers(), timeout=10)
    if r.status_code == 200 and r.json():
        return r.json()[0]
    return None

def compter_tickets_cycle(cycle_id):
    url = f"{SUPABASE_URL}/rest/v1/tickets"
    params = {"cycle_id": f"eq.{cycle_id}", "select": "id"}
    r = requests.get(url, params=params, headers=_headers(), timeout=10)
    return len(r.json()) if r.status_code == 200 else 0

def creer_ticket(user_id, cycle_id, score, montant, paiement_id=None):
    url = f"{SUPABASE_URL}/rest/v1/tickets"
    payload = {"user_id": user_id, "cycle_id": cycle_id, "score": score, "montant": montant}
    if paiement_id:
        payload["paiement_id"] = paiement_id
    r = requests.post(url, json=payload, headers=_headers(), timeout=10)
    return r

def get_historique_user(user_id):
    url = f"{SUPABASE_URL}/rest/v1/tickets"
    params = {"user_id": f"eq.{user_id}", "select": "*", "order": "created_at.desc"}
    r = requests.get(url, params=params, headers=_headers(), timeout=10)
    return r.json() if r.status_code == 200 else []

def get_gains_user(user_id):
    url = f"{SUPABASE_URL}/rest/v1/gains"
    params = {"user_id": f"eq.{user_id}", "select": "*", "order": "created_at.desc"}
    r = requests.get(url, params=params, headers=_headers(), timeout=10)
    return r.json() if r.status_code == 200 else []

def get_solde_user(user_id):
    gains_list = get_gains_user(user_id)
    return sum(g["montant"] for g in gains_list)

def get_classement_cycle(cycle_id):
    url = f"{SUPABASE_URL}/rest/v1/tickets"
    params = {
        "cycle_id": f"eq.{cycle_id}",
        "select": "score,user_id,utilisateurs(nom)",
        "order": "score.desc",
    }
    r = requests.get(url, params=params, headers=_headers(), timeout=10)
    return r.json() if r.status_code == 200 else []

def incrementer_pot(cycle_id, montant):
    url = f"{SUPABASE_URL}/rest/v1/rpc/incrementer_pot_cycle"
    payload = {"p_cycle_id": cycle_id, "p_montant": montant}
    r = requests.post(url, json=payload, headers=_headers(), timeout=10)
    return r

def creer_paiement(user_id, cycle_id, order_id, montant, telephone, operateur, pays):
    url = f"{SUPABASE_URL}/rest/v1/paiements"
    payload = {
        "user_id": user_id, "cycle_id": cycle_id, "order_id": order_id,
        "montant": montant, "telephone": telephone, "operateur": operateur, "pays": pays,
    }
    r = requests.post(url, json=payload, headers=_headers(), timeout=10)
    if r.status_code in (200, 201):
        data = r.json()
        return data[0] if isinstance(data, list) else data
    return None

def get_paiement_par_order_id(order_id):
    url = f"{SUPABASE_URL}/rest/v1/paiements"
    params = {"order_id": f"eq.{order_id}", "select": "*"}
    r = requests.get(url, params=params, headers=_headers(), timeout=10)
    if r.status_code == 200 and r.json():
        return r.json()[0]
    return None

def maj_statut_paiement(order_id, statut, token=None):
    url = f"{SUPABASE_URL}/rest/v1/paiements"
    params = {"order_id": f"eq.{order_id}"}
    payload = {"statut": statut}
    if token:
        payload["token"] = token
    r = requests.patch(url, params=params, json=payload, headers=_headers(), timeout=10)
    return r

def get_paiement_paye_non_consomme(user_id, cycle_id):
    url = f"{SUPABASE_URL}/rest/v1/paiements"
    params = {
        "user_id": f"eq.{user_id}", "cycle_id": f"eq.{cycle_id}",
        "statut": "eq.paid", "select": "*,tickets(id)",
        "order": "created_at.desc",
    }
    r = requests.get(url, params=params, headers=_headers(), timeout=10)
    if r.status_code == 200:
        for p in r.json():
            if not p.get("tickets"):
                return p
    return None

def creer_gain(user_id, cycle_id, montant):
    url = f"{SUPABASE_URL}/rest/v1/gains"
    payload = {"user_id": user_id, "cycle_id": cycle_id, "montant": montant}
    r = requests.post(url, json=payload, headers=_headers(), timeout=10)
    return r

def cloturer_cycle_db(cycle_id):
    from datetime import datetime, timezone
    url = f"{SUPABASE_URL}/rest/v1/cycles"
    params = {"id": f"eq.{cycle_id}"}
    payload = {"statut": "cloture", "cloture_at": datetime.now(timezone.utc).isoformat()}
    r = requests.patch(url, params=params, json=payload, headers=_headers(), timeout=10)
    return r

def creer_nouveau_cycle(seuil, prix_ticket, jeu_id):
    url = f"{SUPABASE_URL}/rest/v1/cycles"
    payload = {"seuil": seuil, "prix_ticket": prix_ticket, "pot": 0, "statut": "ouvert", "jeu_id": jeu_id}
    r = requests.post(url, json=payload, headers=_headers(), timeout=10)
    if r.status_code in (200, 201):
        data = r.json()
        return data[0] if isinstance(data, list) else data
    return None

def get_paiement_par_id(paiement_id):
    url = f"{SUPABASE_URL}/rest/v1/paiements"
    params = {"id": f"eq.{paiement_id}", "select": "*"}
    r = requests.get(url, params=params, headers=_headers(), timeout=10)
    if r.status_code == 200 and r.json():
        return r.json()[0]
    return None
