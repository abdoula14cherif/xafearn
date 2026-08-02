from functools import wraps
from flask import Blueprint, render_template, session, redirect, url_for
from app.supabase_client import get_jeux, get_jeu_par_id, basculer_jeu_actif

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

def require_admin(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("auth.connexion"))
        if not session.get("est_admin"):
            return redirect(url_for("dashboard.jeux_hub"))
        return f(*args, **kwargs)
    return wrapper

@admin_bp.route("/jeux")
@require_admin
def jeux():
    liste = get_jeux()
    return render_template("admin/jeux.html", jeux=liste)

@admin_bp.route("/jeux/<jeu_id>/toggle", methods=["POST"])
@require_admin
def toggle_jeu(jeu_id):
    jeu = get_jeu_par_id(jeu_id)
    if jeu:
        basculer_jeu_actif(jeu_id, not jeu["actif"])
    return redirect(url_for("admin.jeux"))
