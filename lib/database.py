import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from supabase import create_client
from lib.config import SUPABASE_URL, SUPABASE_KEY

def get_client():
    return create_client(SUPABASE_URL, SUPABASE_KEY)

def add_user(user_id, username, referred_by=None):
    try:
        get_client().table("users").insert({
            "user_id": user_id, "username": username,
            "referred_by": referred_by, "balance": 0,
            "is_banned": False, "is_registered": False
        }).execute()
    except:
        pass

def get_user(user_id):
    r = get_client().table("users").select("*").eq("user_id", user_id).execute()
    return r.data[0] if r.data else None

def get_all_users():
    return get_client().table("users").select("*").order("joined_at", desc=True).execute().data

def activate_user(user_id):
    get_client().table("users").update({"is_registered": True}).eq("user_id", user_id).execute()

def update_balance(user_id, amount):
    user = get_user(user_id)
    if user:
        new_balance = max(0, user["balance"] + amount)
        get_client().table("users").update({"balance": new_balance}).eq("user_id", user_id).execute()

def set_last_bonus(user_id, today):
    get_client().table("users").update({"last_bonus": str(today)}).eq("user_id", user_id).execute()

def ban_user(user_id, state=True):
    get_client().table("users").update({"is_banned": state}).eq("user_id", user_id).execute()

def get_referral_count(user_id):
    r = get_client().table("users").select("user_id", count="exact").eq("referred_by", user_id).eq("is_registered", True).execute()
    return r.count or 0

def get_top_referrers(limit=10):
    users = get_client().table("users").select("user_id, username, balance").eq("is_registered", True).execute().data
    result = []
    for u in users:
        count = get_referral_count(u["user_id"])
        result.append({**u, "referral_count": count})
    result.sort(key=lambda x: x["referral_count"], reverse=True)
    return result[:limit]

def get_config(key):
    r = get_client().table("config").select("value").eq("key", key).execute()
    if r.data:
        try:
            return int(r.data[0]["value"])
        except:
            return 0
    defaults = {"bonus_daily": 100, "bonus_referral": 75, "bonus_task": 35, "min_withdrawal": 500}
    return defaults.get(key, 0)

def set_config(key, value):
    try:
        get_client().table("config").update({"value": str(value)}).eq("key", key).execute()
    except:
        get_client().table("config").insert({"key": key, "value": str(value)}).execute()

def get_tasks_today():
    from datetime import date
    return get_client().table("tasks").select("*").eq("date", str(date.today())).eq("is_active", True).execute().data

def add_task(description, link, reward):
    from datetime import date
    get_client().table("tasks").insert({
        "description": description, "link": link,
        "reward": reward, "date": str(date.today()), "is_active": True
    }).execute()

def user_completed_task(user_id, task_id):
    r = get_client().table("user_tasks").select("*").eq("user_id", user_id).eq("task_id", task_id).execute()
    return len(r.data) > 0

def complete_task(user_id, task_id):
    try:
        get_client().table("user_tasks").insert({"user_id": user_id, "task_id": task_id}).execute()
        return True
    except:
        return False

def create_withdrawal(user_id, amount, method, number, name):
    r = get_client().table("withdrawals").insert({
        "user_id": user_id, "amount": amount, "method": method,
        "number": number, "name": name, "status": "pending"
    }).execute()
    return r.data[0]["id"] if r.data else None

def get_pending_withdrawals():
    return get_client().table("withdrawals").select("*").eq("status", "pending").execute().data

def get_withdrawal_by_id(w_id):
    r = get_client().table("withdrawals").select("*").eq("id", w_id).execute()
    return r.data[0] if r.data else None

def update_withdrawal_status(w_id, status):
    get_client().table("withdrawals").update({"status": status}).eq("id", w_id).execute()

def get_user_withdrawals(user_id):
    return get_client().table("withdrawals").select("*").eq("user_id", user_id).order("requested_at", desc=True).limit(10).execute().data

def add_transaction(user_id, type_, amount, description):
    try:
        get_client().table("transactions").insert({
            "user_id": user_id, "type": type_,
            "amount": amount, "description": description
        }).execute()
    except:
        pass

def get_user_transactions(user_id):
    return get_client().table("transactions").select("*").eq("user_id", user_id).order("created_at", desc=True).limit(15).execute().data

def get_stats():
    users = get_all_users()
    ws = get_client().table("withdrawals").select("*").execute().data
    return {
        "total_users": len(users),
        "registered_users": sum(1 for u in users if u.get("is_registered")),
        "banned_users": sum(1 for u in users if u.get("is_banned")),
        "total_balance": sum(u.get("balance", 0) for u in users),
        "total_paid": sum(w.get("amount", 0) for w in ws if w.get("status") == "approved"),
        "pending_withdrawals": sum(1 for w in ws if w.get("status") == "pending"),
    }