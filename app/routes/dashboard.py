from flask import Blueprint, render_template, session, redirect, url_for

dashboard_bp = Blueprint("dashboard", __name__, url_prefix="/dashboard")

def _require_login():
    return "user_id" in session

@dashboard_bp.route("/")
def accueil():
    if not _require_login():
        return redirect(url_for("auth.connexion"))
    return render_template(
        "dashboard/accueil.html", active="accueil",
        pot=15000, tickets_joues=19, seuil=30, prix_ticket=500,
        dernier_score=90, position=4, total_joueurs=12,
    )

@dashboard_bp.route("/historique")
def historique():
    if not _require_login():
        return redirect(url_for("auth.connexion"))
    mock = [
        {"date": "29/07/2026", "score": 90, "gain": None},
        {"date": "27/07/2026", "score": 140, "gain": "1 800 F"},
    ]
    return render_template("dashboard/historique.html", active="historique", historique=mock)

@dashboard_bp.route("/gains")
def gains():
    if not _require_login():
        return redirect(url_for("auth.connexion"))
    mock = [{"date": "27/07/2026", "montant": "1 800"}]
    return render_template("dashboard/gains.html", active="gains", solde="1 800", gains_recents=mock)

@dashboard_bp.route("/classement")
def classement():
    if not _require_login():
        return redirect(url_for("auth.connexion"))
    mock = [
        {"rang": 1, "nom": "A. Ngassa", "score": 840, "part": "33%"},
        {"rang": 2, "nom": "M. Foka", "score": 790, "part": "12%"},
        {"rang": 3, "nom": "S. Biya", "score": 760, "part": "12%"},
        {"rang": 4, "nom": session.get("nom", "Toi"), "score": 705, "part": "6%", "moi": True},
    ]
    return render_template("dashboard/classement.html", active="classement", classement=mock)

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
