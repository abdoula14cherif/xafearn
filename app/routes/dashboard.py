from flask import Blueprint, render_template, session, redirect, url_for, request
from app.supabase_client import (
    get_cycle_ouvert, compter_tickets_cycle, get_historique_user,
    get_gains_user, get_solde_user, get_classement_cycle,
    creer_ticket, incrementer_pot,
    creer_paiement, get_paiement_par_order_id, get_paiement_paye_non_consomme,
)
from app.flinpay_client import initier_paiement

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

@dashboard_bp.route("/acheter", methods=["GET", "POST"])
def acheter():
    if not _require_login():
        return redirect(url_for("auth.connexion"))

    cycle = get_cycle_ouvert()
    if not cycle:
        return render_template("dashboard/acheter.html", prix_ticket=500, erreur="Aucun cycle ouvert pour l'instant.")

    if request.method == "GET":
        return render_template("dashboard/acheter.html", prix_ticket=cycle["prix_ticket"])

    country = request.form.get("country")
    operator = request.form.get("operator")
    phone = request.form.get("phone", "").strip()

    if not all([country, operator, phone]):
        return render_template("dashboard/acheter.html", prix_ticket=cycle["prix_ticket"], erreur="Tous les champs sont obligatoires.")

    order_id, r = initier_paiement(
        amount=cycle["prix_ticket"], phone=phone,
        client_name=session.get("nom", "Client"), country=country, operator=operator,
    )

    if r.status_code != 200 or not r.json().get("ok"):
        detail = r.json().get("error", "erreur inconnue") if r.headers.get("content-type","").startswith("application/json") else r.text[:200]
        return render_template("dashboard/acheter.html", prix_ticket=cycle["prix_ticket"], erreur=f"Échec Flinpay ({r.status_code}) : {detail}")

    creer_paiement(session["user_id"], cycle["id"], order_id, cycle["prix_ticket"], phone, operator, country)

    return render_template("dashboard/attente.html", order_id=order_id)

@dashboard_bp.route("/paiement/<order_id>/verifier")
def verifier_paiement(order_id):
    if not _require_login():
        return redirect(url_for("auth.connexion"))

    paiement = get_paiement_par_order_id(order_id)
    if not paiement:
        return redirect(url_for("dashboard.acheter"))

    if paiement["statut"] == "paid":
        return redirect(url_for("dashboard.jouer"))
    elif paiement["statut"] == "failed":
        return render_template("dashboard/acheter.html", prix_ticket=paiement["montant"], erreur="Le paiement a échoué ou a été annulé.")
    else:
        return render_template("dashboard/attente.html", order_id=order_id)

@dashboard_bp.route("/jouer")
def jouer():
    if not _require_login():
        return redirect(url_for("auth.connexion"))
    cycle = get_cycle_ouvert()
    if not cycle:
        return redirect(url_for("dashboard.accueil"))

    paiement = get_paiement_paye_non_consomme(session["user_id"], cycle["id"])
    if not paiement:
        return redirect(url_for("dashboard.acheter"))

    return render_template("dashboard/jouer.html", prix_ticket=cycle["prix_ticket"], paiement_id=paiement["id"])

@dashboard_bp.route("/jouer/soumettre", methods=["POST"])
def jouer_soumettre():
    if not _require_login():
        return {"error": "non connecté"}, 401
    data = request.get_json(silent=True) or {}
    score = int(data.get("score", 0))
    paiement_id = data.get("paiement_id")

    cycle = get_cycle_ouvert()
    if not cycle or not paiement_id:
        return {"error": "session de jeu invalide"}, 400

    creer_ticket(session["user_id"], cycle["id"], score, paiement_id=paiement_id)
    incrementer_pot(cycle["id"], cycle["prix_ticket"])

    return {"status": "ok"}

@dashboard_bp.route("/historique")
def historique():
    if not _require_login():
        return redirect(url_for("auth.connexion"))
    tickets = get_historique_user(session["user_id"])
    vue = [{"date": t["created_at"][:10], "score": t["score"], "gain": None} for t in tickets]
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
