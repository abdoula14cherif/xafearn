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

def get_cycle_ouvert():
    url = f"{SUPABASE_URL}/rest/v1/cycles"
    params = {"statut": "eq.ouvert", "select": "*", "order": "created_at.desc", "limit": "1"}
    r = requests.get(url, params=params, headers=_headers(), timeout=10)
    if r.status_code == 200 and r.json():
        return r.json()[0]
    return None

def compter_tickets_cycle(cycle_id):
    url = f"{SUPABASE_URL}/rest/v1/tickets"
    params = {"cycle_id": f"eq.{cycle_id}", "select": "id"}
    r = requests.get(url, params=params, headers=_headers(), timeout=10)
    return len(r.json()) if r.status_code == 200 else 0

def creer_ticket(user_id, cycle_id, score):
    url = f"{SUPABASE_URL}/rest/v1/tickets"
    payload = {"user_id": user_id, "cycle_id": cycle_id, "score": score}
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
