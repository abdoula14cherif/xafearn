from app.supabase_client import (
    get_classement_cycle, creer_gain, cloturer_cycle_db, creer_nouveau_cycle,
    compter_tickets_cycle,
)

# Paliers décidés : 1er 33%, 2e-3e 12% chacun, 4e-5e 6% chacun, 6e-7e 3% chacun
# Total distribué : 75% du pot — marge nette ~20-25% pour la plateforme
PALIERS = [
    {"rang_min": 1, "rang_max": 1, "pct": 0.33},
    {"rang_min": 2, "rang_max": 3, "pct": 0.12},
    {"rang_min": 4, "rang_max": 5, "pct": 0.06},
    {"rang_min": 6, "rang_max": 7, "pct": 0.03},
]

def verifier_et_cloturer(cycle):
    """Appelée après chaque achat de ticket. Clôture le cycle et distribue
    les gains si le seuil est atteint, puis ouvre un nouveau cycle."""
    tickets_joues = compter_tickets_cycle(cycle["id"])
    if tickets_joues < cycle["seuil"]:
        return None  # rien à faire, le cycle continue

    classement = get_classement_cycle(cycle["id"])  # trié par score décroissant
    pot = cycle["pot"]

    for palier in PALIERS:
        gagnants = classement[palier["rang_min"] - 1 : palier["rang_max"]]
        montant = round(pot * palier["pct"])
        for gagnant in gagnants:
            creer_gain(gagnant["user_id"], cycle["id"], montant)

    cloturer_cycle_db(cycle["id"])
    nouveau_cycle = creer_nouveau_cycle(cycle["seuil"], cycle["prix_ticket"], cycle["jeu_id"])
    return nouveau_cycle
