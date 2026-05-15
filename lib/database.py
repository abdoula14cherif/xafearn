import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
from lib.config import SUPABASE_URL, SUPABASE_KEY

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation"
}

BASE = f"{SUPABASE_URL}/rest/v1"

# ── USERS ──────────────────────────────────────────

def add_user(user_id, username, referred_by=None):
    try:
        requests.post(f"{BASE}/users", headers=HEADERS, json={
            "user_id": user_id,
            "username": username,
            "referred_by": referred_by,
            "balance": 0,
            "is_banned": False,
            "is_registered": False
        })
    except:
        pass

def get_user(user_id):
    r = requests.get(f"{BASE}/users",
        headers=HEADERS,
        params={"user_id": f"eq.{user_id}"}
    )
    data = r.json()
    return data[0] if data else None

def get_all_users():
    r = requests.get(f"{BASE}/users",
        headers=HEADERS,
        params={"order": "joined_at.desc"}
    )
    return r.json() or []

def activate_user(user_id):
    requests.patch(f"{BASE}/users",
        headers=HEADERS,
        params={"user_id": f"eq.{user_id}"},
        json={"is_registered": True}
    )

def update_balance(user_id, amount):
    user = get_user(user_id)
    if user:
        new_balance = max(0, user["balance"] + amount)
        requests.patch(f"{BASE}/users",
            headers=HEADERS,
            params={"user_id": f"eq.{user_id}"},
            json={"balance": new_balance}
        )

def set_last_bonus(user_id, today):
    requests.patch(f"{BASE}/users",
        headers=HEADERS,
        params={"user_id": f"eq.{user_id}"},
        json={"last_bonus": str(today)}
    )

def ban_user(user_id, state=True):
    requests.patch(f"{BASE}/users",
        headers=HEADERS,
        params={"user_id": f"eq.{user_id}"},
        json={"is_banned": state}
    )

def get_referral_count(user_id):
    r = requests.get(f"{BASE}/users",
        headers={**HEADERS, "Prefer": "count=exact"},
        params={"referred_by": f"eq.{user_id}", "is_registered": "eq.true"}
    )
    count = r.headers.get("Content-Range", "0")
    try:
        return int(count.split("/")[-1])
    except:
        return len(r.json() or [])

def get_top_referrers(limit=10):
    users = requests.get(f"{BASE}/users",
        headers=HEADERS,
        params={"is_registered": "eq.true"}
    ).json() or []
    result = []
    for u in users:
        count = get_referral_count(u["user_id"])
        result.append({**u, "referral_count": count})
    result.sort(key=lambda x: x["referral_count"], reverse=True)
    return result[:limit]

# ── CONFIG ─────────────────────────────────────────

def get_config(key):
    r = requests.get(f"{BASE}/config",
        headers=HEADERS,
        params={"key": f"eq.{key}"}
    )
    data = r.json()
    if data:
        try:
            return int(data[0]["value"])
        except:
            return 0
    defaults = {"bonus_daily": 100, "bonus_referral": 75, "bonus_task": 35, "min_withdrawal": 500}
    return defaults.get(key, 0)

def set_config(key, value):
    requests.patch(f"{BASE}/config",
        headers=HEADERS,
        params={"key": f"eq.{key}"},
        json={"value": str(value)}
    )

# ── TÂCHES ─────────────────────────────────────────

def get_tasks_today():
    from datetime import date
    r = requests.get(f"{BASE}/tasks",
        headers=HEADERS,
        params={"date": f"eq.{date.today()}", "is_active": "eq.true"}
    )
    return r.json() or []

def add_task(description, link, reward):
    from datetime import date
    requests.post(f"{BASE}/tasks",
        headers=HEADERS,
        json={
            "description": description,
            "link": link,
            "reward": reward,
            "date": str(date.today()),
            "is_active": True
        }
    )

def user_completed_task(user_id, task_id):
    r = requests.get(f"{BASE}/user_tasks",
        headers=HEADERS,
        params={"user_id": f"eq.{user_id}", "task_id": f"eq.{task_id}"}
    )
    return len(r.json() or []) > 0

def complete_task(user_id, task_id):
    try:
        r = requests.post(f"{BASE}/user_tasks",
            headers=HEADERS,
            json={"user_id": user_id, "task_id": task_id}
        )
        return r.status_code in [200, 201]
    except:
        return False

# ── RETRAITS ───────────────────────────────────────

def create_withdrawal(user_id, amount, method, number, name):
    r = requests.post(f"{BASE}/withdrawals",
        headers=HEADERS,
        json={
            "user_id": user_id,
            "amount": amount,
            "method": method,
            "number": number,
            "name": name,
            "status": "pending"
        }
    )
    data = r.json()
    return data[0]["id"] if data else None

def get_pending_withdrawals():
    r = requests.get(f"{BASE}/withdrawals",
        headers=HEADERS,
        params={"status": "eq.pending"}
    )
    return r.json() or []

def get_withdrawal_by_id(w_id):
    r = requests.get(f"{BASE}/withdrawals",
        headers=HEADERS,
        params={"id": f"eq.{w_id}"}
    )
    data = r.json()
    return data[0] if data else None

def update_withdrawal_status(w_id, status):
    requests.patch(f"{BASE}/withdrawals",
        headers=HEADERS,
        params={"id": f"eq.{w_id}"},
        json={"status": status}
    )

def get_user_withdrawals(user_id):
    r = requests.get(f"{BASE}/withdrawals",
        headers=HEADERS,
        params={"user_id": f"eq.{user_id}", "order": "requested_at.desc", "limit": "10"}
    )
    return r.json() or []

# ── TRANSACTIONS ───────────────────────────────────

def add_transaction(user_id, type_, amount, description):
    try:
        requests.post(f"{BASE}/transactions",
            headers=HEADERS,
            json={
                "user_id": user_id,
                "type": type_,
                "amount": amount,
                "description": description
            }
        )
    except:
        pass

def get_user_transactions(user_id):
    r = requests.get(f"{BASE}/transactions",
        headers=HEADERS,
        params={"user_id": f"eq.{user_id}", "order": "created_at.desc", "limit": "15"}
    )
    return r.json() or []

# ── STATS ──────────────────────────────────────────

def get_stats():
    users = get_all_users()
    ws = requests.get(f"{BASE}/withdrawals", headers=HEADERS).json() or []
    return {
        "total_users": len(users),
        "registered_users": sum(1 for u in users if u.get("is_registered")),
        "banned_users": sum(1 for u in users if u.get("is_banned")),
        "total_balance": sum(u.get("balance", 0) for u in users),
        "total_paid": sum(w.get("amount", 0) for w in ws if w.get("status") == "approved"),
        "pending_withdrawals": sum(1 for w in ws if w.get("status") == "pending"),
    }
def get_client_headers():
    return HEADERS

BASE = f"{SUPABASE_URL}/rest/v1"