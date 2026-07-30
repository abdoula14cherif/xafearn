from flask import Blueprint, render_template, session, redirect, url_for
from app.supabase_client import (
    get_cycle_ouvert, compter_tickets_cycle, get_historique_user,
    get_gains_user, get_solde_user, get_classement_cycle,
)

dashboard_bp = Blueprint("dashboard", __name__, url_prefix="/dashboard")

def _require_login():
    return "user_id" in session

@dashboard_bp.route("/")
def accueil():
    if not _require_login():
        return redirect(url_for("auth.connexion"))

    cycle = get_cycle_ouvert()
    tickets_joues = compter_tickets_cycle(cycle["id"]) if cycle else 0
    historique = get_historique_user(session["user_id"])
    dernier_score = historique[0]["score"] if historique else 0

    classement = get_classement_cycle(cycle["id"]) if cycle else []
    position = next((i + 1 for i, t in enumerate(classement) if t["user_id"] == session["user_id"]), "—")

    return render_template(
        "dashboard/accueil.html", active="accueil",
        pot=cycle["pot"] if cycle else 0,
        tickets_joues=tickets_joues,
        seuil=cycle["seuil"] if cycle else 30,
        prix_ticket=cycle["prix_ticket"] if cycle else 500,
        dernier_score=dernier_score,
        position=position,
        total_joueurs=len(classement),
    )

@dashboard_bp.route("/historique")
def historique():
    if not _require_login():
        return redirect(url_for("auth.connexion"))
    tickets = get_historique_user(session["user_id"])
    vue = [
        {
            "date": t["created_at"][:10],
            "score": t["score"],
            "gain": None,
        }
        for t in tickets
    ]
    return render_template("dashboard/historique.html", active="historique", historique=vue)

@dashboard_bp.route("/gains")
def gains():
    if not _require_login():
        return redirect(url_for("auth.connexion"))
    gains_list = get_gains_user(session["user_id"])
    solde = get_solde_user(session["user_id"])
    vue = [{"date": g["created_at"][:10], "montant": g["montant"]} for g in gains_list]
    return render_template("dashboard/gains.html", active="gains", solde=solde, gains_recents=vue)

@dashboard_bp.route("/classement")
def classement():
    if not _require_login():
        return redirect(url_for("auth.connexion"))
    cycle = get_cycle_ouvert()
    joueurs = get_classement_cycle(cycle["id"]) if cycle else []
    vue = []
    for i, j in enumerate(joueurs):
        vue.append({
            "rang": i + 1,
            "nom": j.get("utilisateurs", {}).get("nom", "Joueur"),
            "score": j["score"],
            "part": "—",
            "moi": j["user_id"] == session["user_id"],
        })
    return render_template("dashboard/classement.html", active="classement", classement=vue)

@dashboard_bp.route("/profil")
def profil():
    if not _require_login():
        return redirect(url_for("auth.connexion"))
    user = {
        "nom": session.get("nom", "—"),
        "email": session.get("email", "—"),
        "telephone": session.get("telephone", "—"),
        "pays": session.get("pays", "—"),
    }
    return render_template("dashboard/profil.html", active="profil", user=user)
