from flask import Blueprint, render_template, request, redirect, url_for, session
from werkzeug.security import generate_password_hash, check_password_hash
from app.security import limiter
from app.supabase_client import create_user, get_user_by_email
import re

auth_bp = Blueprint("auth", __name__)

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

@auth_bp.route("/inscription", methods=["GET", "POST"])
@limiter.limit("10 per hour")
def inscription():
    if request.method == "GET":
        return render_template("inscription.html")

    nom = request.form.get("nom", "").strip()
    email = request.form.get("email", "").strip().lower()
    telephone = request.form.get("telephone", "").strip()
    pays = request.form.get("pays", "").strip()
    mot_de_passe = request.form.get("mot_de_passe", "")

    if not all([nom, email, telephone, pays, mot_de_passe]):
        return render_template("inscription.html", erreur="Tous les champs sont obligatoires.")
    if not EMAIL_RE.match(email):
        return render_template("inscription.html", erreur="Adresse e-mail invalide.")
    if len(mot_de_passe) < 8:
        return render_template("inscription.html", erreur="Le mot de passe doit faire au moins 8 caractères.")

    if get_user_by_email(email):
        return render_template("inscription.html", erreur="Un compte existe déjà avec cet e-mail.")

    hash_mdp = generate_password_hash(mot_de_passe)
    r = create_user(nom, email, telephone, pays, hash_mdp)

    if r.status_code not in (200, 201):
        return render_template("inscription.html", erreur="Erreur lors de la création du compte. Réessaie.")

    user_data = r.json()[0] if isinstance(r.json(), list) else r.json()
    session["user_id"] = user_data.get("id")
    session["nom"] = nom
    session["email"] = email
    session["telephone"] = telephone
    session["pays"] = pays
    session["est_admin"] = user_data.get("est_admin", False)

    return redirect(url_for("dashboard.accueil"))

@auth_bp.route("/connexion", methods=["GET", "POST"])
@limiter.limit("10 per hour")
def connexion():
    if request.method == "GET":
        return render_template("connexion.html")

    email = request.form.get("email", "").strip().lower()
    mot_de_passe = request.form.get("mot_de_passe", "")

    user = get_user_by_email(email)
    if not user or not check_password_hash(user["mot_de_passe_hash"], mot_de_passe):
        return render_template("connexion.html", erreur="E-mail ou mot de passe incorrect.")

    session["user_id"] = user["id"]
    session["nom"] = user["nom"]
    session["email"] = user["email"]
    session["telephone"] = user["telephone"]
    session["pays"] = user["pays"]
    session["est_admin"] = user.get("est_admin", False)

    return redirect(url_for("dashboard.accueil"))

@auth_bp.route("/deconnexion")
def deconnexion():
    session.clear()
    return redirect(url_for("main.home"))
