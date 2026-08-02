from flask import Blueprint, render_template, session, redirect, url_for, request
from app.supabase_client import (
    get_cycle_ouvert, compter_tickets_cycle, get_historique_user,
    get_gains_user, get_solde_user, get_classement_cycle,
    creer_ticket, incrementer_pot,
    creer_paiement, get_paiement_par_order_id, get_paiement_paye_non_consomme, get_paiement_par_id,
    get_jeux, get_jeu_par_slug,
)
from app.flinpay_client import initier_paiement
from app.cycle_logic import verifier_et_cloturer

dashboard_bp = Blueprint("dashboard", __name__, url_prefix="/dashboard")

def _require_login():
    return "user_id" in session

@dashboard_bp.route("/")
def accueil():
    if not _require_login():
        return redirect(url_for("auth.connexion"))
    return redirect(url_for("dashboard.jeux_hub"))

@dashboard_bp.route("/jeux")
def jeux_hub():
    if not _require_login():
        return redirect(url_for("auth.connexion"))
    jeux = get_jeux()
    return render_template("dashboard/jeux_hub.html", active="accueil", jeux=jeux)

@dashboard_bp.route("/jeux/<slug>")
def jeu_detail(slug):
    if not _require_login():
        return redirect(url_for("auth.connexion"))
    jeu = get_jeu_par_slug(slug)
    if not jeu or not jeu["actif"]:
        return redirect(url_for("dashboard.jeux_hub"))

    cycle = get_cycle_ouvert(jeu["id"])
    tickets_joues = compter_tickets_cycle(cycle["id"]) if cycle else 0

    return render_template(
        "dashboard/jeu_detail.html", active="accueil", jeu=jeu,
        pot=cycle["pot"] if cycle else 0,
        tickets_joues=tickets_joues,
        seuil=cycle["seuil"] if cycle else jeu["seuil"],
    )

MONTANTS_AUTORISES = [300, 500, 700, 1000]

@dashboard_bp.route("/jeux/<slug>/demo")
def demo(slug):
    if not _require_login():
        return redirect(url_for("auth.connexion"))
    jeu = get_jeu_par_slug(slug)
    if not jeu or not jeu["actif"]:
        return redirect(url_for("dashboard.jeux_hub"))
    if slug != "calcul":
        return redirect(url_for("dashboard.jeu_detail", slug=slug))
    return render_template("dashboard/demo.html", jeu=jeu)

@dashboard_bp.route("/jeux/<slug>/acheter", methods=["GET", "POST"])
def acheter(slug):
    if not _require_login():
        return redirect(url_for("auth.connexion"))

    jeu = get_jeu_par_slug(slug)
    if not jeu or not jeu["actif"]:
        return redirect(url_for("dashboard.jeux_hub"))

    cycle = get_cycle_ouvert(jeu["id"])
    if not cycle:
        return render_template("dashboard/acheter.html", jeu=jeu, erreur="Aucune cagnotte en cours pour ce jeu. Reviens plus tard.")

    if request.method == "GET":
        return render_template("dashboard/acheter.html", jeu=jeu)

    country = request.form.get("country")
    operator = request.form.get("operator")
    phone = request.form.get("phone", "").strip()
    try:
        montant = int(request.form.get("montant", 0))
    except ValueError:
        montant = 0

    if montant not in MONTANTS_AUTORISES:
        return render_template("dashboard/acheter.html", jeu=jeu, erreur="Montant invalide.")

    if not all([country, operator, phone]):
        return render_template("dashboard/acheter.html", jeu=jeu, erreur="Tous les champs sont obligatoires.")

    order_id, r = initier_paiement(
        amount=montant, phone=phone,
        client_name=session.get("nom", "Client"), country=country, operator=operator,
    )

    if r.status_code != 200 or not r.json().get("ok"):
        detail = r.json().get("error", "erreur inconnue") if r.headers.get("content-type","").startswith("application/json") else r.text[:200]
        return render_template("dashboard/acheter.html", jeu=jeu, erreur=f"Échec Flinpay ({r.status_code}) : {detail}")

    creer_paiement(session["user_id"], cycle["id"], order_id, montant, phone, operator, country)

    return render_template("dashboard/attente.html", order_id=order_id, slug=slug)

@dashboard_bp.route("/paiement/<order_id>/verifier")
def verifier_paiement(order_id):
    if not _require_login():
        return redirect(url_for("auth.connexion"))

    paiement = get_paiement_par_order_id(order_id)
    if not paiement:
        return redirect(url_for("dashboard.jeux_hub"))

    jeu_slug = request.args.get("slug", "calcul")

    if paiement["statut"] == "paid":
        return redirect(url_for("dashboard.jouer", slug=jeu_slug))
    elif paiement["statut"] == "failed":
        jeu = get_jeu_par_slug(jeu_slug)
        return render_template("dashboard/acheter.html", jeu=jeu, prix_ticket=paiement["montant"], erreur="Le paiement a échoué ou a été annulé.")
    else:
        return render_template("dashboard/attente.html", order_id=order_id, slug=jeu_slug)

@dashboard_bp.route("/jeux/<slug>/jouer")
def jouer(slug):
    if not _require_login():
        return redirect(url_for("auth.connexion"))

    jeu = get_jeu_par_slug(slug)
    if not jeu or not jeu["actif"]:
        return redirect(url_for("dashboard.jeux_hub"))

    cycle = get_cycle_ouvert(jeu["id"])
    if not cycle:
        return redirect(url_for("dashboard.jeu_detail", slug=slug))

    paiement = get_paiement_paye_non_consomme(session["user_id"], cycle["id"])
    if not paiement:
        return redirect(url_for("dashboard.acheter", slug=slug))

    if slug != "calcul":
        # Les mécaniques des autres jeux ne sont pas encore développées
        return redirect(url_for("dashboard.jeux_hub"))

    return render_template("dashboard/jouer.html", prix_ticket=cycle["prix_ticket"], paiement_id=paiement["id"], slug=slug)

@dashboard_bp.route("/jouer/soumettre", methods=["POST"])
def jouer_soumettre():
    if not _require_login():
        return {"error": "non connecté"}, 401
    data = request.get_json(silent=True) or {}
    score = int(data.get("score", 0))
    paiement_id = data.get("paiement_id")
    slug = data.get("slug", "calcul")

    jeu = get_jeu_par_slug(slug)
    cycle = get_cycle_ouvert(jeu["id"]) if jeu else None
    if not cycle or not paiement_id:
        return {"error": "session de jeu invalide"}, 400

    montant_paye = paiement_row["montant"] if (paiement_row := get_paiement_par_id(paiement_id)) else 0

    creer_ticket(session["user_id"], cycle["id"], score, montant_paye, paiement_id=paiement_id)
    incrementer_pot(cycle["id"], montant_paye)

    cycle_a_jour = dict(cycle)
    cycle_a_jour["pot"] = cycle["pot"] + montant_paye
    verifier_et_cloturer(cycle_a_jour)

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
    jeu = get_jeu_par_slug(request.args.get("slug", "calcul"))
    cycle = get_cycle_ouvert(jeu["id"]) if jeu else None
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
