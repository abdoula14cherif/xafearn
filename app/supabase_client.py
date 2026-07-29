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
